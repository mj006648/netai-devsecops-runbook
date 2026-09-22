# 05. VFS, 장치, I/O: 파일 이름에서 NVMe completion까지

이전: [가상 메모리와 reclaim](04-virtual-memory-and-reclaim.md) · 다음: [격리·보안·컨테이너](06-isolation-security-and-containers.md)

보강·근거 확인일: **2026-09-22**. 이 장은 Linux 커널 관점에서 파일 I/O가 어떤 객체와 queue를 거쳐 장치 완료로 돌아오는지 설명한다. 데이터 durability와 파일시스템 관점은 기존 [데이터 시스템 기초](../../../kubernetes/storage/data-systems-foundations/README.md)와 함께 읽으면 좋다.

## 1. VFS는 여러 파일시스템을 하나의 인터페이스로 보이게 한다

**VFS(Virtual File System)**는 user space에 `open`, `read`, `write`, `stat`, `chmod` 같은 파일 인터페이스를 제공하고, kernel 내부에서는 ext4, XFS, tmpfs, procfs, NFS 같은 서로 다른 구현을 연결하는 계층이다. kernel.org VFS 문서는 VFS를 userspace filesystem interface와 kernel 내부 filesystem abstraction을 제공하는 software layer로 설명한다.

프로그램은 `read(fd, buf, n)`이라고 부르지만, kernel은 `fd`가 regular file인지, pipe인지, socket인지, character device인지에 따라 다른 file operation을 호출한다. 이것이 VFS의 큰 힘이다.

## 2. 네 가지 핵심 객체: superblock, inode, dentry, file

| 객체 | 쉬운 뜻 | 수명과 역할 |
| --- | --- | --- |
| superblock | mounted filesystem 전체의 대표 객체 | mount 단위, filesystem type과 operation 보유 |
| inode | 파일 하나의 본체 metadata | mode, owner, size, block mapping 등 |
| dentry | 이름과 inode를 잇는 directory cache 항목 | pathname lookup 성능의 핵심, RAM cache |
| file | 열린 파일 instance | file offset, flags, file operations, fd table과 연결 |

`/var/log/app.log`를 열 때 path component마다 dentry lookup이 일어난다. dentry는 이름 cache이고, inode는 파일 객체의 본체 metadata다. hard link가 있으면 여러 dentry가 같은 inode를 가리킬 수 있다. 반대로 열린 `struct file`은 “이 process가 이 파일을 이런 flags와 offset으로 열었다”는 runtime 객체다.

## 3. file descriptor와 open file description

user space의 **file descriptor(fd)**는 process별 fd table index인 작은 정수다. 같은 숫자 `3`이라도 process가 다르면 다른 열린 파일을 뜻할 수 있다.

~~~text
process fd table
  fd 0 → stdin file object
  fd 1 → stdout file object
  fd 2 → stderr file object
  fd 3 → struct file for /tmp/a
~~~

`dup()`를 하면 두 fd가 같은 open file description을 가리킬 수 있다. 이때 file offset을 공유한다. `open()`을 두 번 하면 같은 inode라도 보통 다른 file object와 별도 offset을 갖는다. 이 차이는 log writer, multi-process worker, shell redirection에서 중요하다.

## 4. `open()` 수명 추적

~~~text
user: fd = open("/data/x", O_RDONLY)
kernel:
  1. user pointer에서 pathname 복사
  2. mount namespace의 root/current directory 기준으로 경로 해석
  3. dcache에서 dentry 찾기, 없으면 filesystem lookup 호출
  4. inode 획득
  5. DAC/ACL/capability/LSM 권한 검사
  6. struct file 할당과 file operations 설정
  7. process fd table에 빈 slot 할당
  8. fd integer를 user space로 반환
~~~

`open()`은 파일 내용을 읽는 syscall이 아니다. metadata lookup과 권한 검사, 열린 file 객체 생성이 중심이다. path lookup 중 directory block 읽기가 필요할 수 있지만, data block read와 같은 의미는 아니다.

## 5. buffered I/O: page cache를 통과하는 기본 경로

대부분의 regular file I/O는 buffered I/O다.

~~~text
read:
  user buffer ← copy ← page cache ← filesystem/block layer/storage

write:
  user buffer → copy → page cache dirty page
  나중에 writeback → filesystem/block layer/storage
~~~

장점은 cache hit, readahead, write coalescing, 작은 write 흡수다. 대가는 user/kernel copy, page cache memory 사용, durability 의미의 복잡성이다.

`write()` return은 보통 data가 page cache에 복사되었음을 뜻한다. storage에 안전하게 기록되었다는 뜻은 아니다. `fsync()`는 file data와 필요한 metadata를 storage에 밀어 durability를 높이는 syscall이지만, device cache와 flush 동작, filesystem mode, 오류 처리까지 봐야 한다.

## 6. direct I/O는 page cache 우회를 시도하지만 단순한 고속 버튼은 아니다

`O_DIRECT`는 page cache를 우회해 user buffer와 storage 사이의 direct transfer를 시도한다. DB가 자체 buffer pool을 관리할 때 쓸 수 있다.

하지만 direct I/O는 제약이 있다.

| 항목 | 이유 |
| --- | --- |
| alignment | device/filesystem block 크기에 맞춰야 할 수 있음 |
| 작은 I/O 비용 | merge/cache 장점을 잃을 수 있음 |
| metadata | 파일 크기 확장 등은 여전히 filesystem 경로 필요 |
| coherence | buffered I/O와 섞으면 일관성 규칙을 이해해야 함 |

따라서 direct I/O는 “page cache가 항상 나쁘다”는 결론이 아니라, application이 cache 정책을 직접 책임질 때 쓰는 선택지다.

## 7. block layer: bio, request, blk-mq

filesystem은 block device에 “이 logical block들을 읽거나 써 달라”고 요청한다. Linux block layer는 그 요청을 device driver가 처리하기 좋은 형태로 모은다.

| 용어 | 뜻 |
| --- | --- |
| bio | block I/O의 기본 조각. page/segment와 sector 범위를 표현 |
| request | 하나 이상의 bio를 합치거나 scheduler가 다루는 단위 |
| request queue | block device로 나갈 요청 관리 구조 |
| blk-mq | multi-queue block layer. CPU/NUMA와 device hardware queue 병렬성을 활용 |

kernel.org blk-mq 문서는 빠른 SSD/NVM 장치에서 단일 queue와 lock이 병목이 되자 software staging queue와 hardware dispatch queue를 두는 multi-queue 구조가 도입되었다고 설명한다. block layer나 device protocol은 completion order를 보장하지 않을 수 있으므로, 필요한 순서는 filesystem이나 higher layer가 처리해야 한다.

## 8. NVMe queue와 completion의 감각

NVMe는 submission queue와 completion queue를 중심으로 동작한다.

~~~text
1. kernel driver가 command를 submission queue에 작성
2. MMIO doorbell로 device에 새 command 알림
3. device가 DMA로 data buffer 읽기/쓰기
4. device가 completion queue entry 작성
5. interrupt 또는 polling으로 kernel이 completion 확인
6. block layer가 request 완료 처리
7. 기다리던 task 또는 aio/io_uring completion이 깨어남
~~~

여기서 “완료”는 계층별 의미가 다르다. device가 command를 완료했다는 뜻과 application transaction이 durable commit되었다는 뜻은 다르다. database WAL commit은 filesystem, block flush, storage power-loss protection까지 함께 봐야 한다.

## 9. synchronous, asynchronous, io_uring

**synchronous I/O**는 호출한 thread가 결과를 기다리는 형태다. `read()`가 data를 얻을 때까지 block될 수 있다. **asynchronous I/O**는 제출과 완료 확인을 분리한다.

**io_uring**은 submission queue와 completion queue를 user/kernel이 공유하는 구조로 syscall overhead와 async I/O 비용을 줄이려는 Linux 인터페이스다. 모든 I/O가 무조건 zero-copy가 되는 것은 아니고, operation, file type, kernel version, flags에 따라 동작이 달라진다. kernel.org에는 FUSE-over-io_uring, io_uring zero-copy receive 같은 특정 기능 문서가 있으며, 일반 application은 보통 liburing 같은 라이브러리로 다룬다.

비교:

| 방식 | 제출 | 완료 | 장점 | 대가 |
| --- | --- | --- | --- | --- |
| blocking read/write | syscall 호출 | return | 단순함 | thread가 잠들 수 있음 |
| POSIX AIO | API로 제출 | signal/callback/polling 등 | 일부 async | Linux regular file에서 제약 많음 |
| io_uring | SQE 제출 | CQE 수거 | batching, async, 다양한 opcode | ring 설정과 lifetime 복잡 |

## 10. completion과 durability는 다르다

파일 쓰기의 성공을 여러 수준으로 나눠 보자.

| 사건 | 보장 |
| --- | --- |
| `write()` return | kernel이 요청 byte를 수락했거나 일부 처리 |
| dirty page 생성 | page cache에 변경이 있음 |
| writeback 완료 | storage device로 write command가 완료됨 |
| `fsync()` return | file data와 필요한 metadata가 동기화되었음을 기대 |
| device flush 완료 | volatile device cache까지 고려한 내구성 강화 |
| application commit | DB나 app protocol이 정의한 transaction 성공 |

기존 데이터 시스템 문서의 [Linux 읽기·쓰기](../../../kubernetes/storage/data-systems-foundations/01-linux-read-write.md)와 [파일시스템·블록 장치](../../../kubernetes/storage/data-systems-foundations/02-filesystems-block-devices.md)는 이 차이를 데이터 보장 관점에서 더 자세히 다룬다. 이 장의 관점은 “그 보장이 kernel 객체와 I/O queue에서 어디에 걸리는가”이다.

## 11. 장치 파일은 파일처럼 보이지만 장치 operation으로 간다

`/dev/null`, `/dev/nvme0n1`, `/dev/tty`, `/dev/kvm` 같은 항목은 filesystem namespace 안에 있지만 일반 파일과 다르다.

| 종류 | 예 | 의미 |
| --- | --- | --- |
| character device | `/dev/null`, `/dev/tty` | byte stream 또는 device-specific operation |
| block device | `/dev/nvme0n1` | block I/O address space 제공 |
| pseudo filesystem | `/proc`, `/sys` | kernel state를 file-like interface로 노출 |

VFS는 file operation table을 통해 read/write/ioctl/mmap 같은 동작을 해당 driver나 pseudo filesystem 구현으로 보낸다. “모든 것이 파일이다”는 좋은 직관이지만, 모든 파일이 disk inode data block을 가진다는 뜻은 아니다.

## 12. 안전한 관찰 실습

아래 명령은 임시 파일에 쓰고 `fsync()`를 호출한다. `/tmp`가 tmpfs일 수도 있으므로 실제 물리 storage flush 실험으로 해석하면 안 된다. 목적은 API 경계와 return 값을 보는 것이다.

~~~bash
python3 - <<'PY'
import os
import tempfile

with tempfile.NamedTemporaryFile(prefix="kernel-io-", delete=True) as f:
    written = os.write(f.fileno(), b"hello\n")
    os.fsync(f.fileno())
    f.seek(0)
    data = os.read(f.fileno(), 100)
    print("written", written, "read_back", data.decode().strip())
PY
~~~

해석: `fsync()`가 return했다고 해서 이 교육용 임시 파일이 실제 SSD NAND에 내려갔다고 결론 내리면 안 된다. filesystem과 `/tmp` mount type, device cache, virtualization layer가 모두 영향을 준다.

## 13. 오개념 정리

| 오개념 | 바로잡기 |
| --- | --- |
| inode는 파일 이름이다 | 이름은 dentry가 다루고 inode는 파일 본체 metadata다. |
| fd 번호는 시스템 전체에서 유일하다 | fd는 process별 table index다. |
| write 성공은 전원 장애에도 안전하다는 뜻이다 | 보통 page cache 수락일 수 있다. durability에는 fsync/flush 계층이 필요하다. |
| direct I/O는 항상 빠르다 | workload와 alignment, cache 정책에 따라 느릴 수 있다. |
| NVMe completion은 app transaction commit이다 | 장치 command 완료와 app-level commit은 별개다. |
| `/proc` 파일은 디스크 파일이다 | kernel state를 file-like interface로 보여 주는 pseudo filesystem이다. |

## 14. 해설 문제

1. hard link 두 개가 같은 inode를 가리키면 `stat` 결과에서 무엇이 같을 수 있는가?
   - inode number, size, mode 등 파일 본체 metadata가 같다. 경로 이름은 서로 다를 수 있다.

2. `dup(fd)` 후 두 fd로 번갈아 읽으면 offset이 공유되는 이유는?
   - 두 fd entry가 같은 open file description 또는 kernel `struct file`을 가리키기 때문이다.

3. blk-mq가 single queue보다 현대 SSD에 유리한 이유는?
   - 여러 CPU와 hardware queue의 병렬성을 활용하고 단일 lock/queue 병목을 줄이기 때문이다.

4. buffered write 후 process가 crash하면 data는 어떻게 되는가?
   - process crash만으로 kernel page cache가 사라지지는 않는다. 하지만 system crash나 전원 장애에서는 fsync 여부와 storage flush 보장이 중요하다.

## 15. 1차 참고 자료

- Linux Kernel Documentation: [Overview of the Linux Virtual File System](https://docs.kernel.org/filesystems/vfs.html), [Linux Filesystems API summary](https://docs.kernel.org/filesystems/api-summary.html)
- Linux Kernel Documentation: [Multi-Queue Block IO Queueing Mechanism](https://docs.kernel.org/block/blk-mq.html)
- Linux Kernel Documentation: [FUSE-over-io_uring uapi](https://docs.kernel.org/filesystems/fuse/uapi/fuse-uapi-io-uring.html), [io_uring zero copy Rx](https://docs.kernel.org/networking/iou-zcrx.html)
- Linux man-pages: [open(2)](https://man7.org/linux/man-pages/man2/open.2.html), [read(2)](https://man7.org/linux/man-pages/man2/read.2.html), [write(2)](https://man7.org/linux/man-pages/man2/write.2.html), [fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)
