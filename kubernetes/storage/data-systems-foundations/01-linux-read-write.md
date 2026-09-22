# 01. Linux에서 읽기와 쓰기는 어떻게 일어나는가?

[학습 목차](README.md) · 이전: [바이트·페이로드·패킷](00a-bytes-payload-and-packets.md) · 기초: [계층과 용어](00-map-and-vocabulary.md) · 다음: [파일시스템과 장치](02-filesystems-block-devices.md)

보강·근거 확인일: **2026-09-22**.

범위: Linux의 일반적인 **buffered regular-file I/O**를 설명한다. 네트워크 파일시스템, FUSE, DAX, raw block device, database 전용 I/O 경로, 파일시스템별 mount option은 세부 보장이 다를 수 있다. 이 장의 숫자는 교육용 예시이며 운영 장비를 측정한 결과가 아니다.

핵심 질문은 하나다. **프로그램이 `write()`를 호출했을 때, 어떤 바이트가 어느 계층의 buffer·cache·queue를 지나고, 누가 무엇을 보장하며, 전원 손실 뒤에도 남는다고 말하려면 어디까지 기다려야 하는가?**

## 1. 먼저 “쓰기”라는 말을 네 단계로 나눈다

일상에서는 모두 “파일에 썼다”라고 말하지만, Linux에서는 최소 네 사건을 구분해야 한다.

| 사건 | 일어난 곳 | 뜻 | 아직 말하면 안 되는 것 |
| --- | --- | --- | --- |
| Python `f.write()` 반환 | Python 런타임 | Python 객체가 런타임 buffer 또는 하위 raw stream으로 전달됨 | 커널이 반드시 바이트를 받았음 |
| Linux `write(2)` 반환 | 커널 syscall | 커널이 반환값만큼의 바이트를 처리했음 | 모든 요청 바이트가 처리됐음, 정전 후 남음 |
| 다른 프로세스의 `read(2)`에서 관측 | 커널 page cache 또는 장치 | 현재 시스템 상태에서 새 내용이 보임 | 비휘발성 매체에 반드시 저장됨 |
| `fsync(2)` 성공 반환 | 파일시스템·block 계층·장치 계약 | 파일 데이터와 필요한 메타데이터 동기화를 요청하고 완료 확인 | 장치 firmware나 원격 backend가 계약을 어겨도 안전함 |

이 네 사건이 같은 시간에 일어나지 않기 때문에 성능 측정과 장애 복구 설명에서 문제가 생긴다. 특히 “다른 프로세스가 읽었다”는 **visibility**이고, `fsync()` 성공은 **durability 계약에 대한 동기화 완료**다. 둘은 서로 대신할 수 없다.

## 2. 단어를 계층별로 정확히 붙인다

처음 보는 사람에게 가장 위험한 단어는 익숙한 단어다. `file`, `buffer`, `page`, `write`는 계층마다 뜻이 조금씩 다르다.

| 단어 | 이 장에서의 뜻 | 왜 생겼는가 |
| --- | --- | --- |
| process | 실행 중인 프로그램 인스턴스. 주소 공간, 열린 fd table, 권한 정보를 가진다 | 여러 프로그램을 서로 격리하고 동시에 실행하기 위해 |
| user space | 일반 프로그램이 실행되는 영역 | 커널 메모리와 장치를 임의로 망가뜨리지 못하게 하기 위해 |
| kernel space | 커널 코드와 핵심 자료구조가 있는 영역 | 파일시스템·메모리·장치·권한을 공통으로 관리하기 위해 |
| syscall | user space가 커널에 서비스를 요청하는 진입점 | 프로그램이 직접 장치를 만지지 않고 표준 인터페이스로 요청하기 위해 |
| file descriptor, fd | 프로세스 fd table의 작은 정수 핸들 | 경로 문자열을 매번 해석하지 않고 열린 객체를 빠르게 참조하기 위해 |
| open file description | 커널의 열린 파일 상태. offset과 file status flag를 담는다 | `dup()`·`fork()` 뒤에도 같은 열린 상태를 공유할 수 있게 하기 위해 |
| inode | 파일의 종류·권한·소유자·크기·데이터 위치 정보를 담는 파일시스템 객체 | 이름과 파일 본체를 분리해 hard link·rename·unlink를 가능하게 하기 위해 |
| offset | 파일 시작부터 몇 바이트 떨어진 위치인지 나타내는 값 | 순차 읽기·쓰기의 “다음 위치”를 기억하기 위해 |
| VFS | 여러 파일시스템을 공통 객체와 함수 형태로 연결하는 Linux 계층 | ext4·xfs·tmpfs 등 구현이 달라도 `open/read/write` API를 유지하기 위해 |
| page cache | 파일 내용을 RAM page/folio 단위로 보관하는 커널 cache | 반복 읽기와 작은 쓰기를 빠르게 처리하고 I/O를 묶기 위해 |
| dirty page | RAM의 page cache 내용이 하위 저장소보다 최신인 상태 | `write()`를 빨리 끝내고 나중에 장치에 내보내기 위해 |
| writeback | dirty page를 파일시스템과 block 계층을 통해 장치로 내보내는 작업 | 메모리의 변경을 실제 저장 계층에 반영하기 위해 |
| I/O queue | 하위 장치가 처리할 읽기·쓰기 요청 대기열 | 여러 요청을 합치고, 순서를 정하고, 장치 병렬성을 쓰기 위해 |
| completion | 요청 처리 결과가 위 계층으로 올라오는 사건 | 기다리던 작업이 성공·부분 성공·오류인지 알리기 위해 |

역사적으로 Unix는 “거의 모든 것을 파일처럼 열고 fd로 조작한다”는 단순한 모델을 제공했다. 그 덕분에 프로그램은 디스크 파일, pipe, socket, device를 비슷한 함수로 다룰 수 있다. 대가는 `write()`라는 이름이 실제 매체 기록 완료를 뜻하지 않는다는 점이다. `write()`는 **fd가 가리키는 객체에 바이트를 전달하는 인터페이스**이고, 객체의 종류와 flag에 따라 의미가 달라진다.

## 3. 경로를 열면 디스크 주소가 아니라 fd를 얻는다

`open("/tmp/a.txt", O_RDWR)`는 “디스크의 몇 번 주소를 달라”가 아니다. 커널에게 경로를 해석해 접근 가능한 객체를 찾고, 열린 상태를 만들어, 프로세스가 쓸 fd 번호를 달라고 요청하는 것이다.

~~~text
"/tmp/a.txt"
  → "/" 디렉터리에서 tmp 이름 찾기
  → tmp 디렉터리에서 a.txt 이름 찾기
  → inode와 권한 확인
  → open file description 생성(offset=0, status flags 저장)
  → 프로세스 fd table의 빈 칸에 연결
  → 예: fd 3 반환
~~~

중요한 연결은 다음과 같다.

~~~text
프로세스 A fd table
  fd 3 ─┐
        ├─ open file description X(offset=0, O_RDWR 등)
  fd 4 ─┘        │
                 └─ inode 12345

프로세스 B fd table
  fd 3 ─────────── open file description Y(offset=0, O_RDONLY 등)
                    │
                    └─ 같은 inode 12345일 수도 있음
~~~

같은 정수 `3`이라도 프로세스가 다르면 같은 파일이라는 뜻이 아니다. 같은 프로세스 안에서도 `open()`을 두 번 호출하면 보통 서로 다른 open file description이 생겨 offset이 따로 움직인다. 반대로 `dup()`으로 복제한 fd나 `fork()`로 물려받은 fd는 같은 open file description을 공유하므로 offset도 공유한다. `open(2)`는 fd가 프로세스 fd table의 항목이고, open file description이 offset과 status flag를 기록한다고 설명한다.

## 4. `한` 한 글자를 저장하면 몇 바이트가 움직이는가?

예제로 한국어 한 글자 `한`을 쓴다. Unicode 문자 하나지만, UTF-8 바이트열은 3바이트다.

~~~text
문자: "한"
Unicode code point: U+D55C
UTF-8 bytes: ED 95 9C
길이: 3 bytes
~~~

파일 I/O API는 대부분 문자가 아니라 **바이트**를 다룬다. Python text file은 문자열을 받아 인코딩을 거쳐 바이트를 만들 수 있지만, Linux `write(fd, buf, count)`는 이미 준비된 `count` 바이트를 받는다. 따라서 “한 글자 썼다”는 말만으로 장치에 몇 바이트가 가는지 알 수 없다. 문자 인코딩을 확인해야 한다.

### 실습: 한 글자, fd offset, `dup()` 공유 offset

아래 예제는 임시 디렉터리 안의 작은 파일만 만들고 자동으로 정리한다. 권한 상승, 실제 장치 접근, cache 제거를 하지 않는다.

~~~python
import os, tempfile, pathlib

with tempfile.TemporaryDirectory(prefix="io-doc-") as d:
    path = pathlib.Path(d) / "one-char.txt"
    payload = "한".encode("utf-8")

    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_RDWR, 0o600)
    try:
        wrote = os.write(fd, payload)
        after_write = os.lseek(fd, 0, os.SEEK_CUR)

        dupfd = os.dup(fd)
        try:
            os.write(dupfd, b"!")
            after_dup_write = os.lseek(fd, 0, os.SEEK_CUR)
        finally:
            os.close(dupfd)

        reader = os.open(path, os.O_RDONLY)
        try:
            seen = os.read(reader, 16)
            reader_after = os.lseek(reader, 0, os.SEEK_CUR)
            writer_after_reader = os.lseek(fd, 0, os.SEEK_CUR)
        finally:
            os.close(reader)

        os.lseek(fd, 0, os.SEEK_SET)
        first_char = os.read(fd, 3).decode("utf-8")
        os.fsync(fd)
    finally:
        os.close(fd)

    print(payload.hex(), len(payload), wrote, after_write)
    print(after_dup_write, seen, reader_after, writer_after_reader)
    print(first_char, path.exists())
~~~

검증한 출력:

~~~text
ed959c 3 3 3
4 b'\xed\x95\x9c!' 4 4
한 True
~~~

해석:

- `ed959c`는 `한`의 UTF-8 3바이트다.
- 첫 `write()`는 3을 반환했고, 공유 offset은 3이 됐다.
- `dupfd`는 같은 open file description을 가리키므로 `!`를 쓰자 원래 `fd`에서 본 offset도 4가 됐다.
- 새로 `open()`한 `reader`는 별도 open file description이므로 읽기 offset이 따로 0에서 시작한다.
- `reader`가 4바이트를 읽어도 writer fd의 offset은 4 그대로다.

이 실습은 현재 파일 내용과 offset 공유를 보여 준다. `fsync()`를 호출하지만 실제 정전 내성을 검증하지는 않는다. 전원 차단, 장치 cache, 원격 파일시스템 보장은 별도 시험과 문서 확인이 필요하다.

## 5. `write()` 한 번을 시간표로 추적한다

예제 상황:

~~~text
프로세스 P1: "한"을 UTF-8 3바이트로 /tmp/demo.txt에 write
프로세스 P2: 같은 파일을 새로 open해서 read
파일시스템: 로컬 Linux 파일시스템의 일반 buffered I/O
초기 파일: 비어 있음
~~~

| 시간 | P1 user space | kernel/VFS/page cache | 파일시스템·block 계층 | P2에서 보이는 것 |
| --- | --- | --- | --- | --- |
| T0 | Python 문자열 `"한"` 보유 | 아직 모름 | 변화 없음 | 파일이 없거나 비어 있음 |
| T1 | UTF-8 인코딩으로 `ED 95 9C` 생성 | 아직 모름 | 변화 없음 | 변화 없음 |
| T2 | `write(fd, buf, 3)` syscall 진입 | fd가 open file description을 가리키는지 확인 | 변화 없음 | 변화 없음 |
| T3 | 커널 모드로 전환되어 대기 | offset 0, 쓰기 권한, 파일 종류 확인 | 필요하면 공간 예약·메타데이터 준비 | 변화 없음 |
| T4 | 대기 | page cache의 파일 offset 0..2 범위에 3바이트 반영, page dirty 표시 | 실제 장치 I/O는 아직 없을 수 있음 | 같은 파일을 읽으면 새 바이트를 볼 수 있음 |
| T5 | `write()`가 3 반환 | open file description offset이 3으로 이동 | writeback은 나중에 실행 가능 | P2 `read()`는 page cache에서 `ED 95 9C`를 받을 수 있음 |
| T6 | 다른 작업 수행 | dirty page가 메모리에 남음 | writeback 조건이 되면 bio/request 생성 | 계속 새 내용 관측 가능 |
| T7 | `fsync(fd)` 호출 가능 | 해당 파일의 dirty data와 필요한 metadata 동기화 요청 | block queue 제출, 장치 completion 대기 | visibility와 별도로 durability 동기화 진행 |
| T8 | `fsync()` 성공 반환 | 오류가 있으면 반환되거나 이후 fd에서 보고될 수 있음 | 파일시스템·장치 계약상 동기화 완료 | 전원 손실 뒤 남는다고 주장할 근거가 생김 |

이 표는 순서를 이해하기 위한 모델이다. 실제 커널에서는 lock, readahead, writeback thread, 장치 queue, interrupt, CPU scheduling이 겹친다. 그래도 핵심은 변하지 않는다. **`write()` 반환은 dirty page 생성과 offset 갱신의 성공 근거일 수 있지만, 자동으로 물리 저장 완료를 뜻하지 않는다.**

## 6. Page cache는 왜 생겼고 무엇을 숨기는가?

저장장치는 CPU와 메모리보다 느리고, 장치가 좋아하는 I/O 크기는 프로그램이 호출하는 크기와 다를 수 있다. 매번 작은 `write()`를 장치에 즉시 보내면 syscall·할당·queue·장치 처리 비용이 커진다. 그래서 Linux는 일반 파일 I/O에서 page cache를 사용한다.

쓰기 경로에서는 page cache가 다음 역할을 한다.

1. 작은 쓰기를 메모리에 빠르게 반영한다.
2. 변경 page를 dirty로 표시한다.
3. 여러 dirty page를 나중에 더 큰 I/O로 묶을 수 있게 한다.
4. 같은 파일을 다시 읽는 프로세스가 장치에 가지 않고 새 내용을 보게 한다.

읽기 경로에서는 다음 역할을 한다.

1. 첫 read에서 장치 또는 하위 계층에서 데이터를 가져와 page cache에 넣는다.
2. 같은 범위를 다시 읽으면 RAM에서 복사해 준다.
3. 순차 접근으로 보이면 뒤쪽 범위를 미리 읽을 수 있다.

오개념:

| 오개념 | 왜 틀렸는가 |
| --- | --- |
| page cache는 읽기 전용 cache다 | buffered write도 page cache에 dirty 상태를 만든다 |
| 다시 읽었으니 디스크에 쓴 것이다 | 다시 읽기는 page cache hit일 수 있다 |
| cache를 끄면 항상 더 정확한 성능이 나온다 | 운영 서버에서 전역 cache를 지우면 다른 작업을 망가뜨리고, 실제 서비스의 cache 효과를 제거한 비현실적 조건이 될 수 있다 |
| dirty page가 많으면 무조건 빠르다 | 나중에 writeback이 몰리거나 dirty 제한에 걸려 호출자가 멈출 수 있다 |

Linux VFS 문서는 superblock, inode, dentry, file object 같은 공통 객체를 설명한다. Page cache와 writeback은 이 공통 경로 위에서 파일시스템·block 계층과 연결된다. VM sysctl 문서는 dirty/writeback 관련 설정을 제공하지만, 학습 중 공유 시스템의 값을 바꾸지 않는다.

## 7. `read()`의 반환값: EOF와 short read를 구분한다

`read(fd, buf, count)`는 최대 `count` 바이트를 요청한다. 성공해도 `count`보다 적게 반환할 수 있다. 파일 끝에 도달하면 0을 반환한다.

일반 regular file에서 중간에 EOF가 없고 오류가 없으면 원하는 만큼 읽히는 일이 많다. 하지만 프로그램을 올바르게 쓰려면 API 계약대로 처리한다.

~~~text
목표: 정확히 N바이트 읽기

받은 총량 = 0
while 받은 총량 < N:
    n = read(fd, 남은 크기)
    if n > 0:
        받은 총량 += n
    elif n == 0:
        EOF: 파일이 기대보다 짧음
        break
    else:
        errno 확인
        EINTR이면 재시도 가능
        EAGAIN/EWOULDBLOCK이면 nonblocking 조건 처리
        그 밖은 실패
~~~

특히 pipe, socket, terminal, nonblocking fd에서는 short read가 자연스럽다. regular file에서도 signal로 syscall이 중단될 수 있고, 파일 크기가 읽는 중 바뀔 수 있다. “한 번 읽으면 다 온다”는 습관은 파일에서 우연히 통했더라도 socket·pipe·object client에서 바로 깨진다.

## 8. `write()`의 반환값: partial write와 늦은 오류를 처리한다

`write(fd, buf, count)`도 요청한 모든 바이트를 항상 처리하지 않는다. 성공 반환값이 양수이면서 `count`보다 작을 수 있다. 이유는 공간 부족, quota, signal, resource limit, nonblocking 조건, 파일 종류의 특성 등 다양하다.

안전한 구조는 다음과 같다.

~~~text
total = len(payload)
sent = 0
while sent < total:
    n = write(fd, payload[sent:])
    if n > 0:
        sent += n
    elif n == -1 and errno == EINTR:
        계속
    elif n == -1 and errno in (EAGAIN, EWOULDBLOCK):
        준비될 때까지 기다리거나 상위 정책 적용
    else:
        실패: 전체 레코드 성공이라고 응답하지 않음
~~~

오류는 즉시 나오지 않을 수도 있다. Buffered write는 page cache에 먼저 반영되고, 실제 writeback에서 장치나 원격 서버 오류를 만날 수 있다. 그런 오류는 이후 `write()`, `fsync()`, `close()` 등에서 보고될 수 있다. 따라서 중요한 파일 게시에서는 `write()` 반환값만 보지 말고 `flush()`와 `fsync()` 오류도 확인한다.

Python의 고수준 파일 객체는 예외로 오류를 보고하고 내부적으로 일부 반복을 처리할 수 있다. 하지만 원리는 같다. “함수가 반환했다”가 아니라 **몇 바이트를 어떤 계층까지 보냈고, 어떤 예외·오류를 확인했는지**가 중요하다.

## 9. `open()` 두 번, `dup()`, `fork()`의 offset 차이

Offset은 inode에 저장되는 값이 아니다. 열린 파일 상태인 open file description에 있다. 그래서 같은 파일을 가리켜도 offset 공유 여부가 달라진다.

| 상황 | open file description | offset 공유? | 예 |
| --- | --- | --- | --- |
| `fd1 = open(path); fd2 = open(path)` | 두 개 | 아니오 | fd1로 10바이트 읽어도 fd2 offset은 0 |
| `fd2 = dup(fd1)` | 하나를 두 fd가 참조 | 예 | fd2로 쓰면 fd1에서 본 offset도 이동 |
| `fork()` 뒤 부모·자식이 같은 fd 사용 | fork 전 open file description 공유 | 예 | 부모가 읽은 뒤 자식의 다음 read 위치도 바뀔 수 있음 |
| `pread()`/`pwrite()` 사용 | offset 인자를 별도로 줌 | open file offset을 바꾸지 않음 | 병렬 worker가 각자 범위를 읽을 때 유용 |

이 차이를 모르면 로그 파일, multi-process worker, 데이터 파일 shard writer에서 이상한 겹침이나 누락을 만든다. 공유 offset이 싫으면 각 프로세스가 따로 `open()`하거나 `pread()`/`pwrite()`처럼 명시 offset API를 쓴다. 공유 offset이 필요하면 `dup()`·상속된 fd의 의미를 의식적으로 사용한다.

`pread()`도 최대 `count` 바이트를 읽는 API다. 병렬 range reader가 정확히 N바이트를 원하면 `read()`와 마찬가지로 반환값을 누적하고, 다음 호출의 offset을 `처음 offset + 이미 읽은 바이트 수`로 계산해 반복해야 한다. `pwrite()`도 short write를 처리해야 한다. 또 Linux에서는 `O_APPEND`로 열린 fd에 `pwrite()`를 호출하면 POSIX의 기대와 달리 offset 인자 위치가 아니라 파일 끝에 쓸 수 있다. 그래서 fixed-offset writer와 append writer를 같은 fd flag로 섞지 않는다.

## 10. `O_APPEND`의 atomicity 범위

여러 프로세스가 같은 파일 끝에 로그를 추가할 때 흔히 `O_APPEND`를 쓴다. Linux `open(2)` 설명에 따르면 `O_APPEND`에서는 각 `write()` 전에 파일 offset을 파일 끝으로 이동시키는 동작과 쓰기 동작이 하나의 atomic step으로 수행된다.

이 말의 범위는 정확히 읽어야 한다.

| 주장 | 판단 |
| --- | --- |
| 두 프로세스가 각자 `write(fd, record, len)` 한 번으로 append하면, 각 write가 선택한 위치 계산과 쓰기는 한 단계로 처리된다 | 로컬 POSIX 파일시스템에서 기대하는 핵심 의미 |
| 레코드 두 개가 절대 섞이지 않는다 | 한 record가 여러 `write()` 호출로 나뉘면 호출 사이에 다른 writer가 들어올 수 있다 |
| NFS에서도 항상 안전하다 | `open(2)`는 NFS append race 가능성을 경고한다 |
| `O_APPEND`는 정전 내성을 준다 | 아니다. append 위치 atomicity와 durability는 다른 문제다 |
| 모든 writer가 같은 user-space buffer를 공유해도 안전하다 | 아니다. user-space 동시성은 별도 문제다 |

로그 record를 원자적으로 붙이고 싶다면 record 하나를 가능한 한 **한 번의 `write()` 호출**로 보낸다. 그리고 “붙었다”와 “정전 뒤 남는다”를 구분해 필요한 곳에서 `fsync()` 또는 상위 로그 프로토콜을 사용한다.

## 11. `flush()` → `fsync()` → `rename()` → directory `fsync()`의 crash point

완성된 파일을 한 번에 게시하는 고전적인 패턴은 다음 순서다.

~~~text
같은 디렉터리에 임시 파일 생성
  → 내용 쓰기
  → user-space flush
  → 파일 fsync
  → 같은 파일시스템 안에서 최종 이름으로 rename/replace
  → 부모 디렉터리 fsync
~~~

왜 이렇게 귀찮을까? 파일 내용과 “이 이름이 어떤 inode를 가리킨다”는 디렉터리 항목은 다른 메타데이터이기 때문이다. 기존 파일을 새 파일로 교체하는 예라면, “crash 뒤 old 또는 new 중 하나를 기대한다”는 표현도 전제가 필요하다. 기존 파일의 내용과 기존 디렉터리 entry가 이전에 이미 durable했고, 사용 중인 파일시스템·장치 stack이 `fsync()`와 `rename()` 계약을 올바르게 지킨다는 범위 안에서만 그런 복구 설명을 할 수 있다.

| 단계 뒤 crash | 관측 가능한 상태 | 계약상 기대 | 미보장·주의 |
| --- | --- | --- | --- |
| 임시 파일 생성 전 | 기존 파일만 있음 | 이전 상태가 이미 동기화돼 있었다면 기존 상태를 기준점으로 삼을 수 있음 | 기존 상태가 durable했다는 사실은 이 새 sequence가 만들지 않음 |
| 일부 write 뒤, fsync 전 | 실행 중에는 page cache에서 일부 내용이 보일 수 있음 | 정전 뒤 임시 파일 내용 보존을 주장하지 않음 | 파일 길이·내용이 부분적일 수 있음 |
| Python `flush()` 뒤, 파일 `fsync()` 전 | Python buffer는 커널로 내려감 | 커널 dirty page에 있을 수 있음 | 비휘발성 저장 완료 아님 |
| 파일 `fsync()` 성공 뒤, rename 전 | 임시 파일 내용과 필요한 파일 메타데이터 동기화 근거 | 임시 이름으로는 복구될 수 있음 | 최종 이름은 아직 바뀌지 않음 |
| `rename()` 성공 뒤, directory `fsync()` 전 | 실행 중에는 최종 이름이 새 inode를 가리킴 | 같은 파일시스템 내 rename은 이름 교체를 원자적으로 보이게 함 | crash 뒤 디렉터리 entry 지속성은 별도 동기화가 필요할 수 있음 |
| directory `fsync()` 성공 뒤 | 최종 이름 변경도 동기화 요청 완료 | 파일 내용과 이름 게시의 durability 근거 | 장치·가상화·원격 backend가 flush 계약을 지킨다는 전제 |

`rename()`의 원자성은 “실행 중 관측자가 중간 이름 상태를 보지 않는다”는 쪽에 가깝다. “어떤 crash point에서도 새 파일이 반드시 남는다”는 말과 다르다. 기존 이름이 항상 안전한 fallback이라는 뜻도 아니다. old-or-new crash recovery는 기존 상태의 사전 동기화, 같은 파일시스템 안의 rename, 파일시스템 ordering, 장치 flush 계약을 함께 전제한다. `fsync(2)`는 파일 fd 동기화만으로 파일이 들어 있는 디렉터리 entry까지 보장하지 않으므로 디렉터리 fd도 명시적으로 동기화해야 할 수 있음을 설명한다.

이 패턴은 단일 파일 게시에 유용하다. 여러 파일, DB index, object store copy/delete, 분산 metadata commit을 자동으로 transaction으로 만들어 주지 않는다.

## 12. `mmap()`은 I/O를 없애지 않고 page fault 위치를 바꾼다

`mmap()`은 파일 범위를 프로세스의 가상 주소 공간에 연결한다. 이후 프로그램은 `read()`를 호출하지 않고 메모리 load/store처럼 접근한다. 그러나 파일 데이터가 RAM에 없으면 처음 접근할 때 page fault가 발생하고, 커널이 필요한 page를 준비해야 한다.

~~~text
mmap(file)
  → 주소 범위 예약과 mapping 정보 생성
  → 아직 파일 전체를 읽지 않을 수 있음

프로그램이 mapped_address[0] 접근
  → page가 없으면 page fault
  → VFS/page cache/파일시스템/block I/O로 page 준비
  → 명령 재시도 후 값 읽기
~~~

MAP_PRIVATE와 MAP_SHARED는 쓰기 의미가 다르다.

| mapping | 쓰기 시 의미 | 파일에 반영? | 동기화 |
| --- | --- | --- | --- |
| `MAP_PRIVATE` | copy-on-write. 처음 쓸 때 프로세스 전용 page가 생길 수 있음 | 일반적으로 원본 파일에 쓰기 전파 안 함 | 프로세스 메모리 변경이며 파일 내구성과 별도 |
| `MAP_SHARED` | 변경이 같은 mapping을 공유하는 다른 프로세스와 파일에 반영될 수 있음 | 파일-backed shared mapping 변경 대상 | 내구성이 필요하면 `msync()`·`fsync()` 등 해당 규칙 확인 |

`MAP_PRIVATE`의 COW는 왜 생겼을까? 프로세스가 큰 파일이나 실행 파일을 mapping할 때 모두 복사하면 메모리와 시간이 낭비된다. 읽기만 할 때는 같은 page를 공유하고, 누군가 수정하려는 순간 그 프로세스 전용 복사본을 만들어 격리한다.

파일 mapping의 `offset`은 page size 배수여야 한다. `msync(addr, length, MS_SYNC)`도 Linux에서는 `addr`가 page-aligned여야 한다. 파일 내부의 byte offset 3부터 100바이트를 동기화하고 싶다는 요구가 있으면, mapping 시작 주소와 파일 offset을 page 경계로 맞추고 실제 flush range가 어느 file bytes에 대응하는지 계산해야 한다. 파일 offset과 process virtual address를 같은 숫자처럼 다루면 안 된다.

오개념:

- `mmap()` 호출이 빠르면 전체 파일 읽기가 빠른 것이다 → 실제 비용은 page fault 시점에 나타날 수 있다.
- `mmap()`은 복사를 완전히 없앤다 → page fault 처리, page cache, CPU cache miss, TLB miss, COW 복사는 여전히 있다.
- `MAP_SHARED`로 바꾸면 바로 정전 내성이 생긴다 → visibility와 durability를 구분해야 한다.

## 13. `O_DIRECT`는 page cache 우회 시도이지 마법 플래그가 아니다

`O_DIRECT`는 일반 page cache 효과를 최소화하려는 플래그다. 데이터베이스처럼 자체 buffer pool을 가진 프로그램이 OS page cache와 중복 cache를 피하고 싶을 때 쓰기도 한다. 그러나 `open(2)`는 `O_DIRECT` 자체가 `O_SYNC`의 보장을 주지 않는다고 설명한다.

정리하면 세 축은 서로 다르다.

| 축 | 질문 | 예 |
| --- | --- | --- |
| buffered/direct | page cache를 주 경로로 쓰는가? | 일반 `open()` vs `O_DIRECT` |
| sync/async completion | 호출자가 완료를 기다리는가? | blocking `read()` vs io_uring 제출 후 CQE 확인 |
| durability | 완료가 어느 저장 안정성까지 뜻하는가? | `write()` vs `fsync()` vs `O_SYNC` |

`O_DIRECT`의 흔한 제약:

- 사용자 buffer 주소, 길이, 파일 offset이 파일시스템·장치가 요구하는 정렬에 맞아야 할 수 있다.
- 파일시스템과 커널 버전에 따라 지원·fallback·오류가 다를 수 있다.
- buffered I/O와 섞으면 cache 일관성, 성능, flush 순서를 더 신중히 봐야 한다.
- page cache를 덜 쓴다는 말은 장치 내부 DRAM cache, RAID controller cache, 원격 backend cache가 사라진다는 뜻이 아니다.
- 내구성이 필요하면 `O_SYNC`, `fsync()`, 장치 flush/FUA 계약을 별도로 확인한다.

초보 단계에서는 `O_DIRECT`로 성능 실험을 시작하지 않는다. 먼저 일반 buffered I/O에서 offset, partial I/O, fsync, rename, page cache 효과를 이해한 뒤 “왜 직접 cache를 관리하려는가?”라는 이유가 있을 때만 검토한다.

## 14. 비동기 I/O와 io_uring의 최소 원리

Blocking `read()`는 호출한 thread가 결과를 받을 때까지 기다리는 방식이다. 비동기 I/O는 “요청 제출”과 “완료 수확”을 분리한다. io_uring은 submission queue(SQ)와 completion queue(CQ)를 user space와 kernel이 공유하는 구조를 제공한다.

~~~text
애플리케이션
  → SQE에 read/write 요청 작성
  → kernel에 제출 알림
  → 다른 계산 수행 가능
  → CQE를 확인해 성공/오류/처리 바이트 수 수확
~~~

io_uring이 생긴 동기는 syscall 횟수와 kernel/user 전환 비용을 줄이고, 많은 I/O를 효율적으로 제출·완료 처리하기 위해서다. 하지만 다음을 혼동하면 안 된다.

| 오개념 | 실제 |
| --- | --- |
| io_uring이면 항상 장치가 비동기로 처리한다 | 파일 종류·작업·커널 설정에 따라 내부 worker나 blocking 경로가 섞일 수 있다 |
| submit 성공이면 I/O 성공이다 | completion queue entry를 확인해야 최종 결과를 안다 |
| CQE가 성공이면 정전 내성이 있다 | 일반 read/write completion과 durability는 다른 축이다 |
| queue depth를 키우면 항상 빨라진다 | 장치·CPU·파일시스템이 포화되면 지연만 늘 수 있다 |

비동기 I/O를 공부할 때는 요청 하나의 평균 시간만 보지 않는다. 제출한 수, 완료한 수, in-flight 수, tail latency, 오류 처리, 취소, backpressure를 함께 본다.

## 15. 읽기 경로: cache hit와 miss의 차이

Buffered read는 다음 순서로 이해할 수 있다.

~~~text
read(fd, count)
  → fd와 open file description 확인
  → 현재 offset과 count로 파일 범위 계산
  → page cache에 해당 범위가 있는지 확인
      ├─ hit: cache에서 user buffer로 복사
      └─ miss: 파일시스템 mapping 확인 → block I/O 제출 → page cache 채움 → 복사
  → 실제 반환한 바이트 수만큼 offset 이동
~~~

첫 번째 read가 느리고 두 번째 read가 빠른 이유는 여러 계층 중 하나가 따뜻해졌기 때문일 수 있다.

| 빨라진 위치 | 가능한 원인 |
| --- | --- |
| OS page cache | 첫 read가 파일 page를 RAM에 올림 |
| 장치 cache | SSD/controller가 최근 LBA를 기억 |
| 원격 backend cache | 네트워크 저장소 서버가 객체·block을 cache |
| 애플리케이션 cache | DB buffer pool, 라이브러리 내부 cache |

따라서 “두 번째가 빠르다”만으로 SSD 원시 성능을 말하지 않는다. 반대로 실제 서비스는 cache가 있는 상태로 동작하므로, 모든 cache를 억지로 제거한 수치만으로 사용자 경험을 설명해도 안 된다.

## 16. 오류 이름을 두려워하지 말고 분류한다

처음에는 `EINTR`, `EIO`, `ENOSPC` 같은 이름이 암호처럼 보인다. 그러나 대부분은 “어느 층에서 어떤 조건 때문에 진행할 수 없었는가?”를 알려주는 표식이다.

| 오류 | 흔한 뜻 | 처리 방향 |
| --- | --- | --- |
| `EINTR` | signal 때문에 syscall이 중단됨 | 처리 바이트가 없으면 재시도 가능 여부 판단 |
| `EAGAIN`/`EWOULDBLOCK` | nonblocking 조건에서 지금은 진행 불가 | poll/epoll/select 또는 상위 대기 정책 |
| `ENOSPC` | 공간 없음 | 작업 실패, 임시 파일 정리, 사용자에게 명확히 보고 |
| `EDQUOT` | quota 초과 | 권한·quota 정책 문제로 보고 |
| `EFBIG` | 파일 크기 제한 초과 | limit·파일 설계 확인 |
| `EIO` | 하위 I/O 오류 | 저장장치·원격 backend·writeback 오류 가능성 조사 |
| `EINVAL` | 잘못된 인자 | flag, alignment, offset, file type 확인 |
| `EBADF` | fd가 유효하지 않거나 접근 모드가 맞지 않음 | fd lifetime과 open mode 확인 |

오류 처리는 “예외가 났으니 재시도”만으로 끝나지 않는다. 이미 일부 바이트를 썼는지, 임시 파일을 제거해야 하는지, 상위 transaction을 abort해야 하는지, 사용자에게 성공 응답을 보내면 안 되는지까지 포함한다.

## 17. 상태별로 성공 문장을 다르게 쓴다

문서나 논문에서 가장 위험한 문장은 “저장됐다”다. 더 정확히 쓴다.

| 더 정확한 표현 | 의미 |
| --- | --- |
| “Python buffer에 기록했다” | Python 런타임 안에서만 확인됨 |
| “커널 `write()`가 N바이트를 반환했다” | 커널이 N바이트를 처리했음 |
| “같은 호스트의 다른 프로세스가 새 내용을 읽었다” | 현재 visibility를 확인함 |
| “파일 fd에 대한 `fsync()`가 성공했다” | 파일 데이터와 필요한 메타데이터 동기화를 요청하고 성공 반환을 받음 |
| “파일 fsync 뒤 rename했고, 부모 디렉터리 fsync도 성공했다” | 단일 파일 게시 패턴의 이름 변경까지 동기화 근거가 있음 |
| “전원 차단 시험에서도 복구됐다” | 실제 fault injection 결과. 별도 실험 조건 필요 |

이 구분은 Kubernetes, HDFS, S3, DB, Iceberg로 올라가도 계속 중요하다. 각 계층에는 자기 나름의 buffer, ACK, commit, recovery가 있다. 아래 계층의 `write()` 성공을 위 계층의 transaction commit으로 바꾸어 말하지 않는다.

## 18. 개념 확인

**Q1. `한` 한 글자를 UTF-8로 쓰면 Linux `write()`의 count는 보통 몇 바이트인가?**

이 글자 하나는 UTF-8에서 `ED 95 9C` 세 바이트다. 문자의 개수와 바이트 수를 구분한다.

**Q2. `dup()`한 fd로 1바이트를 쓰면 원래 fd의 offset도 움직일 수 있는가?**

그렇다. `dup()`한 fd들은 같은 open file description을 참조하므로 offset을 공유한다.

**Q3. 다른 프로세스가 새 파일 내용을 읽었다. 전원 손실 뒤에도 반드시 남는가?**

그 사실만으로는 아니다. page cache visibility와 durability는 다르다.

**Q4. Python `flush()`와 `os.fsync()`은 왜 둘 다 필요할 수 있는가?**

`flush()`는 Python user-space buffer를 하위 계층으로 내리고, `fsync()`는 커널이 파일 데이터와 필요한 메타데이터를 저장 계층에 동기화하도록 요청한다. Python buffer에 남은 바이트는 커널이 `fsync()`할 수 없다.

**Q5. `O_DIRECT`를 쓰면 page cache, 비동기 완료, 정전 내성이 한꺼번에 해결되는가?**

아니다. Direct/buffered, sync/async, durability는 서로 다른 축이다.

**Q6. `rename()`이 성공하면 crash 뒤에도 새 이름이 반드시 남는가?**

실행 중 관측되는 이름 교체의 원자성과 crash durability는 다르다. 부모 디렉터리 `fsync()`와 파일시스템·장치 계약을 확인한다.

## 19. 근거와 더 읽을 자료

- [Linux `open(2)`](https://man7.org/linux/man-pages/man2/open.2.html): fd, open file description, `O_APPEND`, `O_DIRECT`, status flag.
- [Linux `read(2)`](https://man7.org/linux/man-pages/man2/read.2.html), [Linux `write(2)`](https://man7.org/linux/man-pages/man2/write.2.html): 반환값, short read/write, 오류 조건.
- [Linux `fsync(2)`](https://man7.org/linux/man-pages/man2/fsync.2.html): 파일 데이터·메타데이터 동기화와 디렉터리 entry 주의.
- [Linux `rename(2)`](https://man7.org/linux/man-pages/man2/rename.2.html): 이름 교체의 의미와 조건.
- [Linux `mmap(2)`](https://man7.org/linux/man-pages/man2/mmap.2.html): `MAP_SHARED`, `MAP_PRIVATE`, mapping flag.
- [Linux VFS 문서](https://docs.kernel.org/filesystems/vfs.html): superblock, inode, dentry, file object 등 공통 파일시스템 계층.
- [Linux blk-mq 문서](https://docs.kernel.org/block/blk-mq.html): block I/O queue와 hardware queue 모델.
- [Linux VM sysctl 문서](https://docs.kernel.org/admin-guide/sysctl/vm.html): dirty/writeback 관련 설정 설명.
- [io_uring setup](https://man7.org/linux/man-pages/man2/io_uring_setup.2.html), [io_uring enter](https://man7.org/linux/man-pages/man2/io_uring_enter.2.html): submission/completion queue 기반 비동기 I/O.
- [Python `io`](https://docs.python.org/3/library/io.html), [Python `os`](https://docs.python.org/3/library/os.html): Python buffering과 OS fd 함수.

직접 확인은 [로컬 실습](08-guided-labs.md)에서 이어진다. 이 장의 실습은 작은 임시 파일의 API 동작을 확인하며, 전원 차단·장치 고장·원격 저장소 장애를 검증하지 않는다.
