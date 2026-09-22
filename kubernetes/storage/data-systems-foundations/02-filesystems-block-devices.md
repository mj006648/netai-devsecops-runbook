# 02. 파일시스템에서 블록 장치와 SSD까지

[학습 목차](README.md) · 이전: [Linux I/O](01-linux-read-write.md) · 다음: [HDFS](03-hdfs-distributed-files.md)

보강·근거 확인일: **2026-09-22**.

이 장은 “파일 이름이 어떻게 장치의 논리 블록 주소까지 이어지는가?”를 밑바닥부터 추적한다. ext4, XFS, btrfs, tmpfs, Ceph BlueStore, object store는 내부 구조가 다르다. 여기서는 개념을 잡기 위해 작은 toy filesystem을 만들고, 실제 Linux 문서로 용어의 경계를 확인한다. 숫자는 교육용 예시이며 운영 장치의 성능이나 실제 배치를 주장하지 않는다.

## 1. 파일시스템은 왜 필요한가?

블록 장치는 보통 “LBA N부터 몇 블록을 읽거나 써라” 같은 인터페이스를 제공한다. 사용자는 그렇게 살고 싶지 않다. 사용자는 `/data/a.txt`라는 이름, “내가 읽을 수 있는가?”, “파일 길이는 얼마인가?”, “앞에서 10바이트를 읽어라” 같은 요청을 한다.

파일시스템은 이 차이를 메우는 번역기다.

~~~text
사람과 프로그램의 요청
  /data/a.txt 의 offset 4096부터 100바이트 읽기

파일시스템이 해야 할 일
  경로 이름 해석
  권한 검사
  inode 찾기
  파일 offset → 파일 논리 block 계산
  논리 block → 물리 filesystem block/extent 계산
  filesystem block → block device LBA 계산
  block I/O 요청 제출
~~~

그래서 파일시스템에는 최소한 다음 정보가 필요하다.

| 정보 | 답하는 질문 | 예 |
| --- | --- | --- |
| superblock | 이 파일시스템 전체는 어떤 규칙으로 구성됐는가? | block 크기, inode 위치, 전체 block 수 |
| allocation bitmap | 어느 block/inode가 사용 중인가? | block 4와 5는 사용 중 |
| inode table | 파일 본체의 metadata는 어디 있는가? | inode 2는 root directory, inode 3은 일반 파일 |
| directory data | 이름을 어떤 inode로 해석하는가? | `hello.txt` → inode 3 |
| extent 또는 block map | 파일 offset이 어느 block에 있는가? | logical block 0..1 → physical block 4..5 |
| journal/COW/log | crash 중간 상태를 어떻게 복구할 것인가? | metadata transaction 또는 copy-on-write tree |

이 구조가 생긴 역사적 동기는 단순하다. 이름과 데이터를 직접 한 덩어리로 묶으면 rename, hard link, permission, sparse file, crash recovery, 공간 재사용을 안정적으로 처리하기 어렵다. 파일시스템은 “이름”, “파일 정체성”, “데이터 위치”, “복구 절차”를 분리해 관리한다.

## 2. 이름, inode, 열린 핸들은 서로 다르다

가장 중요한 분리다.

~~~text
경로/path:       /home/me/report.txt
디렉터리 entry:  report.txt → inode 12345
inode:           파일 종류, 권한, 크기, extent, link count
open file:       프로세스가 열어 둔 fd와 offset 상태
데이터 block:    실제 payload bytes가 들어 있는 block
~~~

이 분리 때문에 다음 동작이 가능하다.

| 동작 | 실제로 바뀌는 것 | payload 복사? |
| --- | --- | --- |
| rename | 디렉터리 entry의 이름 또는 연결 관계 | 보통 아님 |
| hard link 생성 | 새 이름이 같은 inode를 가리킴, link count 증가 | 아님 |
| symlink 생성 | “다른 경로 문자열”을 담은 별도 inode 생성 | 대상 payload 복사 아님 |
| unlink | 디렉터리 entry 제거, link count 감소 | 즉시 payload 삭제가 아닐 수 있음 |
| 열린 파일을 unlink | 이름은 사라져도 열린 fd가 inode를 붙잡음 | fd가 닫힐 때까지 공간 회수 지연 가능 |

Linux `open(2)`가 말하는 open file description은 경로 이름이 사라져도 영향을 받지 않을 수 있다. `unlink(2)`는 이름을 제거하는 호출이지, 모든 열린 참조를 강제로 무효화하는 호출이 아니다. 그래서 임시 파일 패턴, log rotation, package update가 가능하다.

## 3. 권한에서 directory execute는 “실행”이 아니라 search다

파일 권한의 `rwx`는 파일과 디렉터리에서 의미가 다르다.

| 대상 | read | write | execute/search |
| --- | --- | --- | --- |
| 일반 파일 | 내용 읽기 | 내용 변경·truncate | 프로그램으로 실행 가능 |
| 디렉터리 | 이름 목록 읽기 | entry 생성·삭제·rename | 경로 구성요소로 통과하고 이름 lookup 가능 |

예를 들어 `/a/b/c.txt`를 열려면 `/`, `/a`, `/a/b` 각 디렉터리를 통과할 search 권한이 필요하다. 디렉터리 read 권한은 목록을 볼 수 있는지에 가깝고, search 권한 없이 목록만 보여도 실제 entry에 접근하지 못할 수 있다. 이 구분은 “파일 자체는 644인데 왜 열리지 않는가?” 같은 문제를 설명한다.

권한 검사는 이름 탐색 중의 디렉터리 권한, 최종 inode의 권한, mount option, ACL, namespace, capability 같은 조건이 합쳐진 결과다. 이 장에서는 전통적인 Unix permission 중심으로만 설명한다.

## 4. 16-block toy filesystem을 손으로 만든다

아래는 교육용으로 아주 작은 파일시스템 이미지를 상상한 것이다. 실제 ext4 구조가 아니다.

조건:

~~~text
전체 크기: 16 blocks
block 크기: 64 bytes
block device 시작 LBA: 1,000,000
장치 logical block 크기: 512 bytes
filesystem block 1개 = 64 bytes라서 실제 장치 sector보다 작다.
  이 비현실적 설정은 계산을 쉽게 보이기 위한 장난감이다.
~~~

배치:

| FS block | byte offset | 장치 LBA 계산 | 용도 |
| --- | ---: | ---: | --- |
| 0 | 0 | 1,000,000 + floor(0/512) = 1,000,000 | superblock |
| 1 | 64 | 1,000,000 + floor(64/512) = 1,000,000 | block bitmap |
| 2 | 128 | 1,000,000 | inode table |
| 3 | 192 | 1,000,000 | root directory data |
| 4 | 256 | 1,000,000 | `hello.txt` data block 0 |
| 5 | 320 | 1,000,000 | `hello.txt` data block 1 |
| 6..15 | 384..960 | 1,000,000 or 1,000,001 | free |

이 예에서는 block 크기가 64바이트라 여러 FS block이 같은 512-byte LBA 안에 들어간다. 실제 파일시스템 block은 보통 장치 sector보다 작게 잡지 않는다. 여기서는 offset→block→LBA 변환을 눈으로 보기 위해 일부러 작게 만들었다. 따라서 이 toy FS block은 block device가 독립적으로 쓰는 최소 단위가 아니다. 같은 LBA 안의 64바이트 일부만 바꾸려면 상위 계층이 512바이트 단위 보존이나 read-modify-write 문제를 책임져야 한다.

Superblock의 교육용 내용:

| field | 값 | 뜻 |
| --- | --- | --- |
| magic | `TOYFS1` | 이 이미지가 toyfs라는 표식 |
| block_size | 64 | 파일시스템 block 크기 |
| block_count | 16 | 전체 block 수 |
| inode_table_start | 2 | inode table 시작 block |
| root_inode | 2 | root directory inode 번호 |

Root directory data block 3:

| 이름 | inode | file type |
| --- | ---: | --- |
| `.` | 2 | directory |
| `..` | 2 | directory |
| `hello.txt` | 3 | regular file |

Inode 3:

| field | 값 |
| --- | --- |
| type | regular file |
| mode | `0644` |
| size | 100 bytes |
| extent 0 | logical block 0..1 → physical FS block 4..5 |

파일 offset 70에서 10바이트를 읽어 보자.

~~~text
파일 offset = 70
파일시스템 block 크기 = 64
논리 block 번호 = floor(70 / 64) = 1
block 안 offset = 70 % 64 = 6
extent: logical block 0..1 → physical block 4..5
logical block 1 → physical FS block 5
FS block 5의 이미지 byte offset = 5 * 64 = 320
실제 시작 byte offset = 320 + 6 = 326
장치 LBA = 1,000,000 + floor(326 / 512) = 1,000,000
LBA 안 byte offset = 326 % 512 = 326
~~~

이 계산은 “파일 offset이 곧 LBA”가 아니라는 사실을 보여 준다. 파일 offset은 파일 안의 논리 위치다. 파일시스템이 extent를 보고 filesystem block을 찾고, 그 block이 다시 block device의 LBA 범위로 변환된다.

## 5. Python으로 16-block toy image를 읽어 본다

아래 실습은 메모리 안의 bytearray만 사용한다. 실제 block device, mount, root 권한을 쓰지 않는다. 글자 `한글\n`은 UTF-8 7바이트이고, block 크기를 4바이트로 잡아 두 block에 걸치게 했다. 이것도 실제 파일시스템 크기가 아니라 extent 조립을 보여 주는 작은 모형이다.

~~~python
BLOCK = 4
image = bytearray(BLOCK * 16)

file_bytes = "한글".encode("utf-8") + b"\n"
image[4 * BLOCK:5 * BLOCK] = file_bytes[:4]
image[5 * BLOCK:6 * BLOCK] = file_bytes[4:] + b"\x00"

# logical block 0..1 -> physical block 4..5
extents = [(0, 4, 2)]
out = bytearray()
for logical, physical, count in extents:
    for i in range(count):
        start = (physical + i) * BLOCK
        out.extend(image[start:start + BLOCK])

print(len(file_bytes), file_bytes.hex(), bytes(out[:len(file_bytes)]).decode("utf-8"))
~~~

검증한 출력:

~~~text
7 ed959ceab8800a 한글
~~~

해석:

- `한글\n`은 UTF-8로 `ed 95 9c ea b8 80 0a`, 총 7바이트다.
- 첫 4바이트는 physical block 4, 나머지 3바이트는 physical block 5에 있다.
- extent를 따라 block 4와 5를 붙인 뒤 파일 크기 7바이트까지만 읽어야 뒤쪽 padding `00`을 파일 내용으로 오해하지 않는다.

## 6. 32-block toy filesystem으로 경로 탐색을 확장한다

이번에는 block 32개, block 크기 128바이트라고 하자. 실제 장치의 시작 LBA는 2,000,000이고 장치 logical block 크기는 512바이트다. 따라서 FS block 4개가 장치 LBA 하나에 들어간다.

배치:

| FS block | 용도 |
| ---: | --- |
| 0 | superblock |
| 1 | block bitmap |
| 2..3 | inode table |
| 4 | root directory |
| 5 | `data` directory |
| 6 | `logs` directory |
| 7..9 | `app.log` data extent |
| 10 | symlink payload `latest -> logs/app.log` |
| 11..31 | free |

경로 `/data/latest`를 열 때:

~~~text
1. root inode 2에서 시작
2. root directory block 4를 읽어 "data" entry 확인 → inode 5
3. inode 5가 directory인지 확인하고 search 권한 검사
4. data directory block 5를 읽어 "latest" entry 확인 → inode 8
5. inode 8이 symlink면 symlink payload를 읽음: "logs/app.log"
6. symlink 해석 규칙에 따라 대상 경로를 다시 탐색
7. 상대 symlink target `logs/app.log`는 symlink가 들어 있는 디렉터리 `/data`를 기준으로 해석되어 `/data/logs/app.log`를 찾음
8. 최종 regular file inode 7 획득
~~~

Symlink는 대상 inode를 직접 들고 있는 hard link와 다르다. Symlink는 경로 문자열을 담고, 나중에 그 문자열을 다시 해석한다. 대상이 없어도 symlink 자체는 존재할 수 있다. Hard link는 같은 inode를 가리키는 디렉터리 entry가 하나 더 생기는 방식이라 보통 directory에 대해서는 제한된다.

`/data/logs/app.log`의 file offset 260을 계산해 보자.

~~~text
file offset = 260
FS block size = 128
logical block = floor(260 / 128) = 2
block 안 offset = 260 % 128 = 4
extent: logical block 0..2 → physical FS block 7..9
logical block 2 → physical FS block 9
FS image byte offset = 9 * 128 + 4 = 1156
장치 LBA = 2,000,000 + floor(1156 / 512) = 2,000,002
LBA 안 offset = 1156 % 512 = 132
~~~

이 숫자 추적을 할 수 있으면 ext4의 extent tree, database page file, Parquet footer offset을 읽을 때도 “이름 → metadata → offset → block → 요청”의 층을 잃지 않는다.

## 7. Extent는 왜 block 번호 나열보다 낫나?

파일이 1GiB이고 block 크기가 4KiB라면 데이터 block은 262,144개다. 모든 block 번호를 하나씩 inode 안에 적으면 metadata가 커지고, 큰 순차 파일에도 불필요한 목록이 길어진다. Extent는 연속 구간을 하나로 표현한다.

~~~text
block list 방식
  logical 0 -> physical 9000
  logical 1 -> physical 9001
  logical 2 -> physical 9002
  ...

extent 방식
  logical 0부터 262144개 -> physical 9000부터 연속
~~~

파일시스템이 extent를 쓰는 이유는 공간 효율과 탐색 효율이다. 다만 “logical extent가 연속”이라는 말이 SSD NAND 내부 물리 위치까지 연속이라는 뜻은 아니다. block device 아래에는 device mapper, RAID, 가상화, SSD FTL이 다시 주소를 바꿀 수 있다.

## 8. Sparse file, truncate, apparent size, allocated size

파일 크기에는 최소 두 관점이 있다.

| 이름 | 뜻 | 예 |
| --- | --- | --- |
| apparent size | 파일의 논리 길이. `stat.st_size` | offset 16KiB에 1바이트 쓰면 16KiB+1 |
| allocated size | 실제 할당된 block 총량. `stat.st_blocks` 등으로 추정 | hole에는 block이 없을 수 있음 |

Sparse file은 중간 hole을 실제 block으로 모두 채우지 않은 파일이다. Hole을 읽으면 0처럼 보일 수 있지만, 그 0들이 모두 장치에 기록된 것은 아닐 수 있다. `truncate`는 파일 길이를 늘리거나 줄인다. 늘린 구간은 hole이 될 수 있고, 줄이면 뒤쪽 데이터는 파일 이름으로 접근할 수 없게 된다.

아래 실습은 임시 파일 하나만 만들고 정리한다. 할당량은 파일시스템별로 달라질 수 있으므로 출력은 “이 검증 환경에서의 예”로 읽는다.

~~~python
import os, tempfile, pathlib

with tempfile.TemporaryDirectory(prefix="fs-doc-") as d:
    p = pathlib.Path(d) / "sparse.bin"
    fd = os.open(p, os.O_CREAT | os.O_TRUNC | os.O_RDWR, 0o600)
    try:
        os.write(fd, b"A")
        os.lseek(fd, 4096 * 4, os.SEEK_SET)
        os.write(fd, b"Z")
        st = os.stat(p)
    finally:
        os.close(fd)

    print(st.st_size, st.st_blocks * 512)
~~~

검증 환경 출력:

~~~text
16385 8192
~~~

해석:

- apparent size는 16,385바이트다. offset 0의 `A`, 16KiB hole, 마지막 `Z`가 논리 길이를 만든다.
- allocated size 추정값은 8,192바이트였다. 이 값은 파일시스템, block 크기, inline extent, delayed allocation, mount option에 따라 달라질 수 있다.
- 이 출력만으로 실제 SSD NAND에 8,192바이트만 프로그램됐다고 말하면 안 된다. 아래 장치 계층에서 write amplification이 다시 생길 수 있다.

Linux `lseek(2)`에는 hole과 data 위치를 찾기 위한 `SEEK_HOLE`, `SEEK_DATA`가 있지만, 지원과 의미는 파일시스템별로 다를 수 있다.

## 9. Path walk와 dentry cache

매번 `/a/b/c.txt`를 열 때 모든 디렉터리 block을 장치에서 다시 읽으면 느리다. Linux VFS는 dentry cache를 사용해 “이 디렉터리에서 이 이름을 찾으면 이 inode다”라는 lookup 결과를 재사용한다.

~~~text
첫 open("/data/logs/app.log")
  root lookup
  data lookup
  logs lookup
  app.log lookup
  inode 확인

다음 open
  dentry cache hit가 있으면 일부 directory I/O와 parsing 생략 가능
~~~

Dentry cache는 이름 해석 cache다. 파일 내용 cache인 page cache와 다르다. Negative dentry도 있을 수 있다. 즉 “이 이름은 없다”는 결과도 잠시 cache할 수 있다. 파일 생성·삭제·rename은 관련 dentry를 무효화하거나 갱신해야 하므로 metadata 작업이 성능에 영향을 준다.

Mount는 파일시스템 tree를 VFS namespace의 어떤 지점에 붙이는 일이다. 같은 경로처럼 보여도 mount point를 지나면 다른 superblock과 파일시스템 구현으로 넘어갈 수 있다. 그래서 `/data/a`와 `/data/mnt/b`가 같은 디렉터리 아래처럼 보여도 rename 가능성, fsync 범위, 장치 장애 영역이 다를 수 있다.

## 10. Journal, COW, WAL은 모두 log처럼 보여도 책임이 다르다

Crash 중간에는 이런 문제가 생긴다.

~~~text
파일을 0바이트에서 4096바이트로 늘리는 중
  inode size 변경
  block bitmap에서 새 block 사용 표시
  inode extent에 새 block 연결
  directory entry나 timestamp 갱신
  data block 내용 쓰기

전원이 중간에 꺼지면 일부만 반영될 수 있음
~~~

파일시스템은 이 문제를 여러 방식으로 다룬다.

| 방식 | 핵심 아이디어 | 보호하려는 것 | 주의 |
| --- | --- | --- | --- |
| metadata journal | metadata 변경 기록을 journal에 먼저 남기고 replay 가능하게 함 | 파일시스템 구조 일관성 | 사용자 data 전체가 transaction처럼 보호된다는 뜻이 아님 |
| data journaling | data도 journal에 포함하는 모드 | data와 metadata의 더 강한 순서 | 비용과 설정 차이 큼 |
| copy-on-write filesystem | 기존 block을 덮지 않고 새 위치에 쓰고 metadata root를 전환 | 일관된 tree 전환 | write amplification과 fragmentation 고려 |
| database WAL | DB page를 바꾸기 전 논리/물리 log record를 안정 저장 | DB transaction 복구 | 파일시스템 journal을 대체하거나 대체당하는 관계가 아님 |

시나리오로 보자.

| crash point | journaled metadata FS | COW FS | DB WAL |
| --- | --- | --- | --- |
| data block 일부 write 뒤 metadata commit 전 | metadata replay로 이전 일관 상태 또는 정해진 순서 회복 | 아직 새 root로 전환 전이면 이전 tree | DB commit record 없으면 transaction abort 가능 |
| metadata는 새 block을 가리키는데 data가 오래됨 | data=ordered 같은 모드와 flush 순서가 중요 | 새 block과 새 metadata가 함께 publish되는 설계 | WAL replay가 page를 다시 만들 수 있음 |
| directory entry 생성 중 crash | journal replay로 entry 생성 여부를 일관되게 결정 | 새 directory block/root 전환 여부에 따름 | DB catalog라면 DB transaction 규칙 적용 |

ext4의 기본 설명에서 가장 조심할 점은 “journal이 있으니 사용자 파일 내용이 모두 원자적이다”라고 확대하지 않는 것이다. ext4는 jbd2 journal을 사용하며 data mode에 따라 data와 metadata의 관계가 다르다. DB WAL은 row·index·transaction이라는 DB의 논리 규칙을 복구하기 위한 로그다. 파일시스템이 자신의 구조를 복구하는 것과 책임이 다르다.

## 11. HDD와 SSD의 장치 경계

파일시스템 아래에는 block layer와 block device가 있다. 이 경계부터 파일 이름은 사라지고 LBA와 길이 중심으로 요청이 내려간다.

~~~text
VFS / filesystem
  → bio/request: LBA, length, read/write/flush 같은 속성
  → block multi-queue
  → driver
  → 장치 또는 가상 backend
~~~

HDD와 SSD는 같은 block interface를 제공할 수 있지만 내부 비용 구조가 다르다.

| 항목 | HDD | SSD |
| --- | --- | --- |
| 랜덤 접근 비용 | 헤드 이동과 회전 대기가 큼 | 기계적 탐색 없음 |
| 쓰기 내부 동작 | 자기 디스크 위치에 기록 | NAND program/erase 제약, FTL mapping |
| 병렬성 | 플래터·헤드·컨트롤러 특성 | channel, die, plane, controller 병렬성 |
| 작은 쓰기 문제 | seek가 지배적일 수 있음 | erase block, garbage collection, write amplification |

SSD가 기존 바이트를 항상 제자리 수정하지 않는 이유는 NAND flash의 program/erase 제약 때문이다. SSD는 FTL을 통해 host LBA를 내부 flash 위치로 매핑한다.

~~~text
host: LBA 100에 새 4KiB 쓰기
SSD 내부 교육용 흐름:
  새 flash page에 데이터 기록
  LBA 100의 mapping을 새 위치로 변경
  이전 위치는 invalid 처리
  나중에 garbage collection이 유효 page를 모으고 erase block 회수
~~~

이 그림은 특정 SSD의 원자성이나 전원 손실 동작 명세가 아니다. 제품의 power-loss protection, volatile write cache, firmware 정책, NVMe feature 설정에 따라 달라진다.

## 12. Block queue, flush, FUA

Linux block layer는 여러 CPU와 여러 hardware queue를 활용하기 위해 blk-mq 구조를 사용한다. 애플리케이션 thread 수가 곧 장치 queue depth는 아니다. 중간에서 page cache hit, request merge, filesystem ordering, cgroup I/O control, device mapper, driver queue가 영향을 준다.

~~~text
여러 writeback/request
  → software staging queue
  → hardware dispatch queue
  → driver/NVMe/SATA 등
  → completion interrupt 또는 polling
  → 위 계층에 완료 보고
~~~

Durability에서 flush와 FUA를 구분한다.

| 용어 | 뜻 | 주의 |
| --- | --- | --- |
| volatile write cache | 장치나 controller가 전원 손실 시 잃을 수 있는 cache | 완료 응답만으로 안정 저장을 뜻하지 않을 수 있음 |
| flush | 이전에 받은 쓰기를 안정 매체까지 밀어 넣으라는 장벽성 요청 | 하위 장치가 계약을 지킨다는 전제 |
| FUA | 해당 쓰기를 volatile cache에만 두지 말고 안정 저장하라는 속성 | 모든 장치·stack에서 같은 방식으로 지원되는지 확인 필요 |
| completion | 장치/driver가 요청 완료를 보고 | 완료의 의미는 요청 flag와 장치 계약에 의존 |

`fsync()`는 파일시스템이 필요한 data/metadata를 내보내고, 하위 block layer에 flush/FUA 같은 명령을 사용해 순서를 만들 수 있다. 하지만 가상화 계층, RAID controller, 원격 block backend, 실제 SSD가 그 의미를 어떻게 구현하는지는 별도 계약이다. 그래서 “fsync를 호출했다”와 “전원 차단 시험으로 검증했다”를 구분한다.

## 13. Write amplification은 계층마다 따로 계산한다

1바이트를 고쳤는데 훨씬 많은 바이트가 움직일 수 있다.

~~~text
애플리케이션: JSON 파일의 1바이트 수정
파일시스템: 4KiB block read-modify-write, metadata update, journal write
SSD: 새 flash page write, mapping update, garbage collection
DB/LSM이 있으면: WAL write, memtable flush, compaction rewrite
~~~

교육용 계산:

| 계층 | 논리적으로 새로 쓴 양 | 누적 설명 |
| --- | ---: | --- |
| 앱 record | 1 KiB | 사용자가 바꾼 payload |
| DB/WAL | 4 KiB WAL + 8 KiB page = 12 KiB | DB 복구와 page 단위 때문 |
| 파일시스템 | journal 8 KiB + data 12 KiB = 20 KiB | metadata와 ordering 때문 |
| SSD 내부 | 40 KiB | FTL/GC 때문에 더 늘었다고 가정 |

증폭률을 말할 때는 분모를 분명히 한다.

~~~text
DB 계층 증폭 = 12 / 1 = 12
파일시스템까지 = 20 / 1 = 20
SSD 내부까지 = 40 / 1 = 40
SSD 내부 / 파일시스템 제출량 = 40 / 20 = 2
~~~

실제 논문이나 실험에서는 각 계층 counter의 단위와 기간을 맞춰야 한다. `iostat`, `/proc/diskstats`, NVMe SMART, DB metric, application log는 서로 다른 위치를 잰다.

## 14. Observability에서 숫자 하나로 결론 내리지 않는다

장치 사용률 100%, await 증가, throughput 감소 같은 숫자는 원인 자체가 아니다. 질문을 분해한다.

| 관측 | 가능한 설명 |
| --- | --- |
| throughput 낮음, await 낮음 | 애플리케이션이 충분히 요청을 안 보냄, CPU/lock 병목 |
| throughput 높음, await 높음 | 장치 포화 또는 queueing 증가 |
| util 낮음, 앱 느림 | 직렬 fsync, metadata lock, page fault, remote latency |
| write bytes 많음 | journal, compaction, writeback, GC, retry 중 하나일 수 있음 |
| read가 두 번째부터 빠름 | page cache 또는 장치/서버 cache 효과 |

Block queue를 볼 때는 요청 크기, queue depth, read/write 비율, sync write 비율, fsync 빈도, CPU 사용률, memory pressure를 같이 본다. 논문에서는 “더 빠르다”보다 “어떤 계층의 어떤 대기가 줄었는가?”가 더 중요하다.

## 15. 오개념 정리

| 오개념 | 바로잡기 |
| --- | --- |
| 파일 이름은 데이터 위치다 | 이름은 directory entry이고, inode와 extent를 거쳐 위치를 찾는다 |
| inode가 파일 이름을 저장한다 | 일반적으로 이름은 디렉터리 entry에 있고 inode는 파일 본체 metadata를 담는다 |
| hard link는 복사본이다 | 같은 inode를 가리키는 이름이 하나 더 생긴다 |
| symlink는 hard link의 다른 이름이다 | symlink는 경로 문자열을 담은 별도 객체다 |
| unlink하면 열린 fd도 즉시 실패한다 | 열린 참조가 남아 있으면 이름 없이도 접근 가능할 수 있다 |
| 파일 크기와 디스크 사용량은 같다 | sparse, compression, metadata, block rounding 때문에 다를 수 있다 |
| filesystem journal은 DB WAL을 대체한다 | 복구 대상과 transaction 의미가 다르다 |
| SSD는 overwrite가 공짜다 | FTL, erase, GC, write amplification을 고려해야 한다 |
| `fsync()`면 모든 하드웨어 고장에 안전하다 | 하위 stack과 장치 계약, 전원 보호, 실제 장애 시험이 별도다 |
| Kubernetes PVC 개수가 물리 디스크 개수다 | 논리 리소스와 물리 장애 영역은 다르다 |

## 16. 개념 확인

**Q1. `/data/a.txt`라는 이름만으로 LBA를 바로 알 수 있는가?**

아니다. path walk로 directory entry를 찾고, inode와 extent를 읽고, 파일 offset을 filesystem block과 block device LBA로 변환해야 한다.

**Q2. Hard link와 symlink의 가장 큰 차이는 무엇인가?**

Hard link는 같은 inode를 가리키는 디렉터리 entry다. Symlink는 대상 경로 문자열을 담은 별도 inode이며, 접근할 때 그 문자열을 다시 해석한다.

**Q3. 열린 파일을 `unlink()`하면 데이터는 즉시 사라지는가?**

이름은 사라지지만 열린 fd 같은 참조가 남아 있으면 inode와 data block은 회수되지 않을 수 있다.

**Q4. Sparse file의 apparent size가 16KiB여도 실제 할당량이 더 작을 수 있는 이유는?**

중간 hole을 실제 block으로 할당하지 않았기 때문이다. 읽으면 0처럼 보일 수 있지만 모든 0이 저장된 것은 아니다.

**Q5. Ext4 journal과 DB WAL은 같은가?**

아니다. 파일시스템 journal은 파일시스템 metadata/data ordering과 구조 일관성을 다루고, DB WAL은 DB transaction과 page 복구를 다룬다.

**Q6. SSD에서 logical block이 연속이면 NAND에서도 연속인가?**

그렇게 단정할 수 없다. SSD FTL이 host LBA를 내부 위치에 다시 매핑한다.

## 17. 근거와 더 읽을 자료

- [Linux VFS 문서](https://docs.kernel.org/filesystems/vfs.html): superblock, inode, dentry, file object, path lookup의 공통 계층.
- [Linux inode(7)](https://man7.org/linux/man-pages/man7/inode.7.html): inode metadata, file type, permission bit.
- [Linux open(2)](https://man7.org/linux/man-pages/man2/open.2.html), [unlink(2)](https://man7.org/linux/man-pages/man2/unlink.2.html), [link(2)](https://man7.org/linux/man-pages/man2/link.2.html), [symlink(2)](https://man7.org/linux/man-pages/man2/symlink.2.html): 이름과 열린 파일의 관계.
- [Linux lseek(2)](https://man7.org/linux/man-pages/man2/lseek.2.html): file offset, `SEEK_DATA`, `SEEK_HOLE`.
- [ext4 high level design](https://docs.kernel.org/filesystems/ext4/overview.html), [ext4 journal](https://docs.kernel.org/filesystems/ext4/journal.html): ext4 구조와 jbd2 journal.
- [Linux blk-mq 문서](https://docs.kernel.org/block/blk-mq.html): software queue와 hardware dispatch queue.
- [Python os](https://docs.python.org/3/library/os.html), [Python tempfile](https://docs.python.org/3/library/tempfile.html), [Python stat](https://docs.python.org/3/library/stat.html): 실습에 사용한 표준 라이브러리.

이 장의 실습은 임시 파일과 메모리 bytearray만 사용한다. 실제 filesystem mount, raw block device write, device cache 설정 변경, power-cut, controller reset은 수행하지 않는다.
