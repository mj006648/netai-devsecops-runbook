# 01. Linux에서 읽기와 쓰기는 어떻게 일어나는가?

[학습 목차](README.md) · 이전: [바이트·페이로드·패킷](00a-bytes-payload-and-packets.md) · 기초: [계층과 용어](00-map-and-vocabulary.md) · 다음: [파일시스템과 장치](02-filesystems-block-devices.md)

범위: 일반적인 Linux buffered regular-file I/O. 네트워크 파일시스템, direct I/O, DAX와 특수 장치는 경로·보장이 다를 수 있다. 아래 흐름은 교육용이며 현재 클러스터의 내부를 추적한 결과가 아니다.

## 1. 파일을 열면 무엇을 얻는가?

애플리케이션이 경로를 열면 커널은 접근 권한과 경로를 해석하고 파일 descriptor를 반환한다. descriptor는 프로세스에서 사용하는 정수 핸들이며 디스크 주소가 아니다. 열려 있는 파일 상태에는 offset과 플래그 등이 연결된다.

~~~text
"/scratch/events.bin"
  → 경로 탐색·권한 검사
  → 파일시스템 객체/inode
  → open file description
  → 프로세스의 file descriptor
~~~

서로 다른 descriptor라도 같은 open file description을 공유하면 offset도 공유할 수 있다. 파일 이름과 inode, 열린 핸들을 동일한 것으로 보지 않아야 한다. [Linux open(2)](https://man7.org/linux/man-pages/man2/open.2.html)

## 2. Python의 write와 Linux의 write는 같은 호출이 아니다

Python의 파일 객체에는 user-space buffer가 있을 수 있다. 작은 쓰기를 모아 syscall 횟수를 줄이는 것이 목적이다.

~~~text
Python f.write(payload)
  → Python/런타임 buffer에 보관하거나 하위 계층에 전달
  → Linux write(fd, bytes, count)
  → 커널의 파일 데이터 처리
~~~

큰 쓰기나 buffer 설정에 따라 바로 하위 호출이 일어날 수도 있다. 따라서 “f.write는 언제나 RAM만 변경한다” 또는 “언제나 syscall 하나다”라고 단정하면 안 된다. Python text I/O라면 문자 인코딩 단계도 앞에 있다. [Python io](https://docs.python.org/3/library/io.html)

## 3. Buffered write를 단계별로 본다

1. 애플리케이션이 전달할 바이트를 준비한다.
2. 커널은 offset·권한·파일 상태를 확인한다.
3. 일반 buffered 경로에서는 파일 범위의 page cache에 데이터를 반영한다.
4. 변경된 cache가 dirty 상태가 된다.
5. 파일시스템은 필요한 공간·메타데이터를 관리한다. 물리 배치 결정이 뒤로 미뤄지는 구현도 있다.
6. writeback이 dirty 데이터를 하위 I/O로 제출한다.
7. 장치가 명령을 처리하고 완료를 보고한다.
8. 요구한 동기화 수준에 따라 대기와 오류 확인이 추가된다.

[VFS 문서](https://docs.kernel.org/filesystems/vfs.html)는 파일 객체와 page cache를 포함한 커널 인터페이스를 설명한다. 이 흐름은 CPU 실행과 I/O가 겹칠 수 있는 과정이지, 항상 한 줄로 순차 실행되는 시간표가 아니다.

### 왜 처음에는 빠르고 나중에는 갑자기 느려지는가?

교육용 상황:

- 저장장치가 지속적으로 받아들일 수 있는 속도보다 애플리케이션이 더 빠르게 쓴다.
- 처음에는 dirty 데이터가 메모리에 쌓이므로 write가 빠르게 반환한다.
- writeback이 따라잡지 못하면 dirty data가 증가한다.
- 커널이 쓰기 작업을 제어하거나 애플리케이션이 동기화를 기다린다.

즉, 앞부분의 속도만 재면 메모리에 빚을 쌓는 속도를 디스크 처리량으로 잘못 해석할 수 있다. dirty/writeback 설정은 성능뿐 아니라 공유 시스템 전체에 영향을 주므로 학습 중 변경하지 않는다. [Linux VM 설정 설명](https://docs.kernel.org/admin-guide/sysctl/vm.html)

## 4. write 반환값을 확인해야 하는 이유

Linux write는 요청한 모든 바이트가 아니라 일부만 처리하고 반환할 수 있다. 반환된 바이트 수를 확인하고, 남은 부분을 처리하거나 오류를 보고해야 한다. 디스크 공간 부족이나 하위 writeback 오류가 나중에 드러나는 경우도 있다. [write(2)](https://man7.org/linux/man-pages/man2/write.2.html)

~~~text
교육용 의사코드: 실제 언어·API의 예외 규칙에 맞춰 구현할 것

offset = 0
while offset < payload_size:
    written = write(remaining_bytes)
    if error or written <= 0:
        fail_without_claiming_success()
    offset += written
~~~

syscall 성공과 애플리케이션의 전체 레코드 성공은 다르다. 100개의 쓰기로 구성한 파일에서 99개가 성공해도 작업 전체 성공이라고 응답하면 안 된다.

## 5. flush·fsync·close를 구분한다

| 동작 | 주요 의미 | 이것만으로 주장하면 안 되는 것 |
| --- | --- | --- |
| Python flush | 런타임의 쓰기 buffer를 하위 스트림으로 전달 | 모든 바이트가 비휘발성 매체에 보존됨 |
| Linux write | 요청 바이트의 전부 또는 일부를 파일에 기록하도록 처리 | 정전 내성까지 완료 |
| fsync(fd) | 파일 데이터와 필요한 파일 메타데이터의 동기화를 요청하고 완료를 기다림 | 하위 장치·서비스가 계약을 위반해도 안전함 |
| fdatasync(fd) | 데이터 및 이후 데이터 접근에 필요한 메타데이터 동기화 | 모든 메타데이터 변경의 동기화 |
| close | 열린 핸들을 닫음; 라이브러리 close는 buffer를 비울 수 있음 | fsync와 같은 durability 장벽 |

**Python buffer를 먼저 flush하지 않고 fd만 fsync하면, 아직 user-space buffer에 남은 바이트를 동기화하지 못한다.**

반대로 fsync 성공은 중요한 동기화 근거지만, 물리 장치 전원 손실·컨트롤러 오류를 실제 시험한 결과는 아니다. 로컬 파일시스템과 원격 저장소의 보장도 구분한다. [fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)

## 6. 다른 프로세스에서 보이는 것과 디스크 보존

다른 프로세스가 같은 파일을 읽을 때 page cache에서 새 값을 얻을 수 있다. 이것은 유용한 visibility지만 비휘발성 매체에서 읽었다는 증거가 아니다.

~~~text
시간 A: process 1이 write
시간 B: process 2가 read → 새 값 확인
시간 C: 아직 남은 dirty page가 장치로 writeback
~~~

이 순서가 가능하므로 “다시 읽었고 hash가 같았다”는 실험은 현재 접근과 내용 일치를 검증한다. 전원 손실 후 보존성은 별도의 장애 시험과 저장 계약 확인이 필요하다.

## 7. 안전한 파일 게시에서 디렉터리가 중요한 이유

설정 파일이나 결과 파일을 완성된 상태로 교체할 때 흔히 사용하는 패턴이다.

~~~text
같은 디렉터리의 임시 파일 생성
  → 내용 쓰기
  → user-space flush
  → 파일 fsync
  → 같은 파일시스템 안에서 최종 이름으로 rename/replace
  → 부모 디렉터리 fsync
~~~

파일 내용과 “그 이름이 이 파일을 가리킨다”는 디렉터리 변경은 서로 다른 정보다. fsync 문서는 파일 fsync만으로 디렉터리 entry까지 보장되지 않으며 디렉터리 동기화가 필요할 수 있음을 설명한다.

이 패턴도 파일시스템·장치의 동기화 의미를 전제로 한다. 여러 파일을 동시에 게시하는 DB 트랜잭션을 대체하지 않으며, S3의 copy/delete를 로컬 rename과 같게 취급하지 않는다. 동봉 실습은 단계를 관측할 뿐 crash consistency 전체를 검증하지 않는다.

## 8. Buffered read의 경로

~~~text
read 요청
  → 경로/offset 또는 기존 fd 확인
  → page cache에 필요한 범위가 있는가?
      ├ yes: cache에서 애플리케이션으로 전달
      └ no: filesystem 매핑 → block I/O → cache 채움 → 전달
  → 필요하면 후속 범위를 미리 읽는 readahead
~~~

실제 I/O 크기는 read의 count와 다를 수 있다. 커널·파일시스템·장치가 합치거나 더 읽을 수 있고, cache hit라면 새 장치 I/O가 없을 수도 있다. read 역시 요청량보다 적은 바이트를 반환할 수 있으므로 EOF와 부분 읽기를 처리한다. [read(2)](https://man7.org/linux/man-pages/man2/read.2.html)

### 첫 번째와 두 번째 읽기의 시간 차이

같은 파일을 즉시 다시 읽으면 첫 번째 읽기로 데워진 page cache, 장치 cache, 데이터베이스 cache의 효과가 섞인다. 두 번째가 빠르다고 SSD가 갑자기 빨라진 것이 아니다.

Cold는 계층별 조건이다. OS cache가 차갑더라도 원격 객체 서비스나 장치 cache는 따뜻할 수 있다. 공유 서버에서 전역 cache를 비워 다른 사용자의 작업까지 느리게 만들지 않는다.

## 9. mmap은 “I/O가 사라지는 기능”이 아니다

mmap은 파일 범위를 프로세스 가상 주소 공간에 연결한다. 접근할 때 필요한 page가 준비되지 않았다면 fault 처리와 I/O가 필요할 수 있다. 페이지를 접근하는 시점에 비용이 나타날 수 있으므로 mmap 호출 시간만 재면 안 된다.

MAP_SHARED와 MAP_PRIVATE의 쓰기 의미가 다르고, 공유 mapping의 변경을 안정 저장하려면 해당 동기화 규칙을 따라야 한다. mmap 자체가 모든 복사·page fault·동기화 비용을 없애지는 않는다. [mmap(2)](https://man7.org/linux/man-pages/man2/mmap.2.html)

## 10. Direct I/O와 비동기 I/O는 서로 다른 축이다

- **Buffered/direct:** 일반적인 page cache 경로를 사용하는가?
- **Synchronous/asynchronous submission:** 호출자가 완료를 기다리는가, 나중에 완료를 받는가?
- **Durability:** 어느 동기화 수준까지 보장하는가?

O_DIRECT는 이 세 문제를 동시에 해결하는 마법의 플래그가 아니다. 정렬·파일시스템 지원 조건이 있고, buffered 경로와 섞으면 추가 고려가 필요하다. 장치 내부 cache까지 없애거나 항상 빨라진다는 뜻도 아니다. [open(2)의 O_DIRECT 설명](https://man7.org/linux/man-pages/man2/open.2.html)

## 11. Trident 실험에서 적용할 질문

1. Spark 결과 파일 쓰기 시간에 동기화·원격 ACK가 어느 정도 포함되는가?
2. catalog 게시 시간과 파일 생성 시간이 구분되는가?
3. staging 완료 후 첫 읽기가 page cache 덕분에 빨라진 것은 아닌가?
4. GPU 실행 시간 앞에 다운로드·decode·host/device 전송 비용이 빠졌는가?
5. 입력 Ready와 파일 읽기 성공, 정전 내성을 서로 다른 검증으로 기록했는가?

## 12. 개념 확인

**Q1. fsync 전에 Python flush가 필요한 이유는?**

커널은 Python buffer에만 남아 있는 바이트를 동기화할 수 없기 때문이다.

**Q2. write 한 번이 payload 전체를 항상 처리하는가?**

아니다. 반환된 바이트 수와 오류를 확인한다.

**Q3. rename이 성공했으면 전원 손실 후 이름도 반드시 남는가?**

그 사실만으로 단정하지 않는다. 디렉터리 동기화와 파일시스템·장치 보장이 필요하다.

**Q4. mmap의 생성 시간이 짧으면 파일 전체 읽기도 빠른가?**

아니다. 실제 page 접근·fault·I/O가 뒤에 발생할 수 있다.

**Q5. O_DIRECT이면 비동기이며 정전에도 안전한가?**

아니다. cache 경로, 완료 통지 방식, durability는 별개의 조건이다.

직접 확인은 [로컬 실습](08-guided-labs.md)에서 수행한다.
