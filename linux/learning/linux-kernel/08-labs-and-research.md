# 08. 안전한 Linux 커널 입문 실습과 연구형 문제

[학습 목차](README.md) · 이전: [관측과 문제 좁히기](07-observation-and-troubleshooting.md) · 다음: [용어집](09-glossary.md)

보강·근거 확인일: **2026-09-22**.

이 장은 운영체제 개념을 작은 Python 표준 라이브러리 실습으로 확인한다. 목표는 “명령을 많이 실행했다”가 아니라 **예상 → 관측 → 해석 → 한계**를 스스로 말하는 것이다. 모든 예제는 임시 디렉터리나 메모리 안에서 끝나며, `sudo`, 시스템 설정 변경, 패키지 설치, 인터넷 접근, 실제 block device 접근, 전역 cache 삭제를 하지 않는다.

## 1. 실습 안전 규칙

실습은 다음 범위 안에서만 실행한다.

| 규칙 | 이유 |
| --- | --- |
| Python 3 표준 라이브러리만 사용 | 설치·버전·권한 문제를 줄이기 위해 |
| 작은 임시 파일과 자동 cleanup 사용 | 운영 데이터와 공유 경로를 건드리지 않기 위해 |
| `timeout`과 유한 반복 사용 | 실습이 멈춰 터미널을 붙잡지 않게 하기 위해 |
| 외부 네트워크·인터넷 요청 없음 | 네트워크 정책과 다른 팀 실습 범위를 침범하지 않기 위해 |
| `sudo`, mount, sysctl, cache drop 없음 | 운영체제 전역 상태를 바꾸지 않기 위해 |
| 출력은 교육용 결과로만 사용 | 성능 benchmark나 장애 내성 검증으로 과장하지 않기 위해 |

실습 중 예외가 나면 먼저 Python 버전과 플랫폼을 확인한다. 이 장은 Linux 학습용이며 `os.pread`, Unix fd 동작, `mmap`의 세부 의미는 운영체제마다 다를 수 있다.

## 2. Python 코드를 읽기 전에 알아야 할 기본 문법

아래 실습은 초보자가 코드 앞에서 멈추지 않도록 같은 문법을 반복해서 쓴다.

| 문법 | 한 문장 설명 | 이 장에서 쓰는 이유 |
| --- | --- | --- |
| `import name` | 표준 라이브러리 모듈을 현재 코드에서 쓰겠다고 불러온다 | `os`, `subprocess`, `threading`, `mmap`, `tempfile` 기능 사용 |
| `with ... as x:` | 자원을 열고 블록이 끝날 때 자동 정리한다 | 임시 디렉터리와 파일을 안전하게 닫기 위해 |
| `try ... finally:` | 중간에 오류가 나도 `finally` 블록을 실행한다 | fd와 mmap을 반드시 닫기 위해 |
| `for item in items:` | 여러 항목을 차례로 처리한다 | 주소 목록, thread 목록, 반복 횟수 처리 |
| `def name(...):` | 나중에 호출할 함수 블록을 정의한다 | thread가 실행할 worker 정의 |
| `print(...)` | 값을 화면에 출력한다 | 예상한 관측을 사람이 볼 수 있게 하기 위해 |
| `assert condition` | 조건이 거짓이면 즉시 실패하게 한다 | 실습의 기본 전제가 깨졌는지 확인하기 위해 |
| `b"ABC"` | 문자열이 아니라 bytes literal을 만든다 | 파일·fd·mmap 실습이 바이트 단위임을 드러내기 위해 |

`assert`는 실습 검증에는 좋지만 운영 서비스의 입력 검증을 대신하지 않는다. Python을 최적화 모드로 실행하면 assert가 제거될 수 있기 때문이다. 운영 코드에서는 명시적인 오류 처리와 테스트를 따로 둔다.

## 3. 실습 1: subprocess에서 PID, 종료 코드, stdout을 분리한다

**예상:** 부모 Python 프로세스가 새 Python 자식 프로세스를 만든다. 자식은 자기 PID를 출력하고 종료 코드 3으로 끝난다. `subprocess.run()`은 stdout과 returncode를 분리해서 돌려준다. `shell=True`는 문자열을 셸이 해석하게 하므로, 보통은 인자 목록을 직접 넘기는 쪽이 안전하다.

코드 전 줄 읽기:

- `import os, shlex, subprocess, sys`: 현재 PID 확인, shell quoting, 자식 실행, 현재 Python 실행 파일 경로를 쓰기 위해 모듈을 불러온다.
- `code = ...`: 자식 Python에게 실행시킬 짧은 코드를 문자열로 만든다.
- `subprocess.run([...], capture_output=True, text=True, timeout=5)`: 인자 목록으로 자식을 실행하고, 출력은 문자열로 캡처하며, 5초 안에 끝나야 한다.
- `shlex.quote(...)`: shell 명령 문자열에 넣을 값을 안전하게 quoting한다.
- `print(...)`: 숫자가 환경마다 달라지는 PID 원문 대신 shape와 참/거짓을 출력한다.

~~~python
import os, shlex, subprocess, sys

code = "import os; print('child', os.getpid()); raise SystemExit(3)"
direct = subprocess.run(
    [sys.executable, "-c", code],
    capture_output=True,
    text=True,
    timeout=5,
)

shell_command = shlex.quote(sys.executable) + " -c " + shlex.quote("print('shell child')")
via_shell = subprocess.run(
    shell_command,
    shell=True,
    capture_output=True,
    text=True,
    timeout=5,
)

child_words = direct.stdout.split()
print("direct_return", direct.returncode)
print("direct_stdout_shape", child_words[0], child_words[1].isdigit())
print("direct_child_is_other_process", int(child_words[1]) != os.getpid())
print("shell_stdout", via_shell.stdout.strip())
print("shell_return", via_shell.returncode)
~~~

검증한 출력:

~~~text
direct_return 3
direct_stdout_shape child True
direct_child_is_other_process True
shell_stdout shell child
shell_return 0
~~~

해석:

- 자식의 화면 출력과 자식의 성공·실패 코드는 별도다. 예쁜 문장을 출력해도 종료 코드가 실패일 수 있다.
- PID는 실행마다 달라지므로 숫자 자체가 아니라 “부모와 다른 프로세스인가?”를 확인했다.
- `shell=True`는 shell 문법이 필요할 때만 쓴다. 사용자 입력을 shell 문자열에 붙이면 quoting 실수와 명령 주입 위험이 생긴다.

한계:

- 이 실습은 process 생성과 stdout 캡처를 보여 준다. `fork`, `execve`, dynamic loader, cgroup, namespace 내부 동작을 추적하지 않는다.
- `timeout=5`는 자식 실행 전체가 5초 안에 끝나야 함을 요구하지만, 플랫폼에 따라 프로세스 생성 단계 자체는 즉시 중단되지 않을 수 있다.

근거: Python `subprocess` 문서는 `run()`이 완료된 프로세스 객체를 반환하고 stdout/stderr/returncode를 따로 제공한다고 설명한다. `shell=True`는 셸 기능을 쓰게 하지만 보안 고려가 필요하다고 문서화되어 있다.

## 4. 실습 2: lost update를 결정적으로 만들고 lock으로 고친다

**예상:** 두 실행 흐름이 같은 값을 읽고 각각 1을 더해 쓰면 최종값이 2가 아니라 1이 될 수 있다. 실제 thread 실습에서는 `Barrier`로 출발선을 맞추고 `Lock`으로 공유 counter 변경을 감싸 최종값 3000을 만든다.

코드 전 줄 읽기:

- `import threading`: thread, lock, barrier를 쓰기 위해 불러온다.
- 첫 부분은 실제 thread 없이 interleave를 손으로 만든다. 그래서 lost update가 항상 재현된다.
- `counter`는 여러 thread가 공유할 숫자다.
- `Lock`은 한 번에 한 thread만 임계 구역에 들어오게 한다.
- `Barrier(4)`는 worker 3개와 main thread 1개가 모두 도착해야 시작하게 한다.
- `join(timeout=5)`와 `assert all(...)`은 deadlock이나 멈춤을 조용히 지나치지 않기 위한 안전장치다.

~~~python
import threading

counter = 0
first_reader_saw = counter
second_reader_saw = counter
first_writer_wants = first_reader_saw + 1
second_writer_wants = second_reader_saw + 1
counter = first_writer_wants
counter = second_writer_wants
print("simulated_lost_update", counter, "expected_without_race", 2)

counter = 0
lock = threading.Lock()
start_line = threading.Barrier(4)

def worker(repetitions):
    global counter
    start_line.wait(timeout=5)
    for _ in range(repetitions):
        with lock:
            counter += 1

threads = [threading.Thread(target=worker, args=(1000,)) for _ in range(3)]
for thread in threads:
    thread.start()
start_line.wait(timeout=5)
for thread in threads:
    thread.join(timeout=5)
assert all(not thread.is_alive() for thread in threads)
print("locked_counter", counter, "expected", 3000)
~~~

검증한 출력:

~~~text
simulated_lost_update 1 expected_without_race 2
locked_counter 3000 expected 3000
~~~

해석:

- lost update는 “CPU가 틀린 덧셈을 했다”가 아니다. 읽기, 계산, 쓰기가 하나의 원자적 작업이 아니기 때문에 interleave가 결과를 바꾼다.
- `Lock`은 counter 변경 구간을 한 번에 한 thread만 실행하게 한다.
- `Barrier`는 실험을 보기 좋게 시작시키는 도구다. barrier의 참여자 수를 잘못 잡으면 모든 thread가 영원히 기다릴 수 있으므로 timeout을 둔다.

한계:

- Python 구현과 GIL 때문에 이 실습이 모든 CPU memory model 문제를 보여 주지는 않는다.
- `counter += 1`이 어떤 bytecode와 lock으로 실행되는지는 Python 버전과 구현에 따라 달라질 수 있다.
- 실제 커널 scheduler 공정성이나 lock contention 측정은 하지 않는다.

근거: Python `threading` 문서는 `Thread`, `Lock`, `Barrier` 같은 thread 기반 동시성 도구를 제공한다. Barrier는 지정된 수의 thread가 모두 도착할 때까지 기다리게 하는 동기화 도구다.

## 5. 실습 3: 가상 주소를 page number와 offset으로 나눈다

**예상:** page size가 4096이면 주소의 몫은 virtual page number, 나머지는 page 안 offset이다. 같은 virtual page number라도 page table이 다른 frame을 가리키면 물리 주소가 달라진다.

코드 전 줄 읽기:

- 이 코드는 실제 프로세스의 page table을 읽지 않는다. 숫자 계산 모델이다.
- `page_table = {1: 7, 2: 12}`는 “가상 page 1은 frame 7, 가상 page 2는 frame 12”라는 장난감 표다.
- `divmod(a, b)`는 `a // b`와 `a % b`를 한 번에 구한다.
- `hex(...)`는 정수를 16진수 문자열로 보여 준다.
- `assert`는 `0x1234` 계산이 예상과 맞는지 확인한다.

~~~python
page_size = 4096
page_table = {1: 7, 2: 12}
addresses = [0x1234, 0x2000, 0x2FFF]

for virtual_address in addresses:
    virtual_page, page_offset = divmod(virtual_address, page_size)
    frame = page_table[virtual_page]
    physical_address = frame * page_size + page_offset
    print(hex(virtual_address), "vpn", virtual_page, "offset", page_offset, "->", hex(physical_address))

assert divmod(0x1234, page_size) == (1, 0x234)
~~~

검증한 출력:

~~~text
0x1234 vpn 1 offset 564 -> 0x7234
0x2000 vpn 2 offset 0 -> 0xc000
0x2fff vpn 2 offset 4095 -> 0xcfff
~~~

해석:

- `0x1234`는 decimal 4660이고, `4660 // 4096 = 1`, `4660 % 4096 = 564`다.
- page table이 virtual page 1을 frame 7로 매핑한다고 가정했으므로 물리 주소는 `7 * 4096 + 564 = 0x7234`가 된다.
- page 안 offset은 변환 뒤에도 유지된다. frame 번호만 바뀐다.

한계:

- 실제 Linux 프로세스의 page table, TLB, huge page, ASLR, permission bit를 읽은 것이 아니다.
- 실제 물리 주소는 일반 사용자 프로그램이 마음대로 볼 수 있는 값이 아니다.
- page size 4096은 흔한 예시다. 환경에 따라 기본 page size나 huge page 크기가 다를 수 있다.

근거: Linux kernel memory-management 문서는 virtual memory, page, page table, address translation의 기본 개념을 설명한다.

## 6. 실습 4: fd, `dup()`, `pread()`의 offset 차이를 본다

**예상:** `dup()`으로 복제한 fd는 같은 open file description을 공유하므로 offset도 공유한다. `pread()`는 명시 offset에서 읽고 open file offset을 바꾸지 않는다.

코드 전 줄 읽기:

- `tempfile.TemporaryDirectory(...)`는 실습용 디렉터리를 만들고 `with` 블록이 끝나면 지운다.
- `pathlib.Path`는 경로를 객체처럼 다루게 해 준다.
- `os.open`은 Python 고수준 파일 객체가 아니라 Unix fd를 얻는다.
- `try/finally`는 중간 실패에도 `os.close`가 실행되게 한다.
- `os.read(fd, 2)`는 현재 offset에서 최대 2바이트를 읽고 offset을 움직인다.
- `os.pread(fd, 2, 1)`은 file offset 1에서 2바이트를 읽지만 공유 offset을 바꾸지 않는다.

~~~python
import os, pathlib, tempfile

with tempfile.TemporaryDirectory(prefix="fd-lab-") as directory:
    path = pathlib.Path(directory) / "sample.bin"
    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_RDWR, 0o600)
    try:
        os.write(fd, b"ABCDE")
        os.lseek(fd, 0, os.SEEK_SET)
        dup_fd = os.dup(fd)
        try:
            first = os.read(fd, 2)
            second = os.read(dup_fd, 2)
            before_pread_offset = os.lseek(fd, 0, os.SEEK_CUR)
            middle = os.pread(fd, 2, 1)
            after_pread_offset = os.lseek(fd, 0, os.SEEK_CUR)
        finally:
            os.close(dup_fd)
    finally:
        os.close(fd)

    print(first, second, middle)
    print(before_pread_offset, after_pread_offset, path.exists())
~~~

검증한 출력:

~~~text
b'AB' b'CD' b'BC'
4 4 True
~~~

해석:

- 첫 `read(fd, 2)`는 `AB`를 읽고 공유 offset을 2로 만든다.
- `dup_fd`는 같은 열린 파일 상태를 공유하므로 다음 `read(dup_fd, 2)`는 `CD`를 읽고 offset을 4로 만든다.
- `pread(fd, 2, 1)`은 offset 1에서 `BC`를 읽지만 현재 offset은 4 그대로다.
- `path.exists()`는 with 블록 안에서 파일이 존재함을 보여 준다. 블록이 끝나면 임시 디렉터리는 정리된다.

한계:

- 이 실습은 Unix 계열 fd 동작을 보여 준다. Windows와 일부 파일 객체에서는 같은 API가 없거나 의미가 다를 수 있다.
- `fsync()`를 호출하지 않으므로 crash durability를 검증하지 않는다.
- Python 고수준 file object buffering은 일부러 피했다.

근거: Linux `open(2)`는 fd와 open file description, offset 관계를 설명한다. `pread(2)`는 지정 offset에서 읽되 file offset을 변경하지 않는 호출로 설명된다.

## 7. 실습 5: mmap shared/private의 차이를 작은 파일에서 본다

**예상:** `ACCESS_COPY`로 만든 private mapping에 쓴 변경은 mapping에서만 보이고 파일에는 반영되지 않는다. `ACCESS_WRITE`로 만든 shared/write mapping 변경은 파일에 반영될 수 있으며, `flush()`는 mapping 변경을 하위 계층으로 내보내도록 요청한다.

코드 전 줄 읽기:

- `mmap.mmap(file.fileno(), 0, access=...)`에서 길이 0은 현재 파일 전체를 mapping한다는 뜻이다.
- `private_map[0:1] = b"Z"`는 mapping의 첫 바이트만 바꾼다.
- `path.read_bytes()`는 파일 내용을 새로 읽어 mapping 변경이 파일에 보였는지 확인한다.
- `shared_map.flush()`는 mapping 변경을 파일 쪽에 반영하도록 요청한다. 전원 차단 실험은 아니다.
- 두 mapping은 모두 `finally`에서 닫는다.

~~~python
import mmap, pathlib, tempfile

with tempfile.TemporaryDirectory(prefix="mmap-lab-") as directory:
    path = pathlib.Path(directory) / "mapped.bin"
    path.write_bytes(b"abcdef")

    with path.open("r+b") as file:
        private_map = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_COPY)
        try:
            private_map[0:1] = b"Z"
            print("private_view", private_map[:3], "file_still", path.read_bytes()[:3])
        finally:
            private_map.close()

    with path.open("r+b") as file:
        shared_map = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_WRITE)
        try:
            shared_map[1:2] = b"Y"
            shared_map.flush()
        finally:
            shared_map.close()

    print("after_shared", path.read_bytes())
~~~

검증한 출력:

~~~text
private_view b'Zbc' file_still b'abc'
after_shared b'aYcdef'
~~~

해석:

- private mapping 안에서는 `Zbc`가 보이지만 파일은 아직 `abc`로 시작한다.
- shared/write mapping에서 둘째 바이트를 `Y`로 바꾸고 flush한 뒤 파일을 읽으면 `aYcdef`가 보인다.
- mapping에서 보이는 것, 다른 프로세스가 보는 것, crash 뒤 보존되는 것은 분리해서 말해야 한다.

한계:

- 이 실습은 작은 regular file에서 Python `mmap` API의 관측을 보여 준다.
- page fault 횟수, TLB, NUMA, huge page, DAX, remote filesystem 동작은 측정하지 않는다.
- `flush()`와 파일 내용 재읽기는 전원 손실 내구성 시험이 아니다.

근거: Python `mmap` 문서는 memory-mapped file 객체를 제공하고 access mode를 설명한다. Linux `mmap(2)`는 `MAP_SHARED`와 `MAP_PRIVATE`의 파일 반영 의미를 구분한다.

## 8. 실습 결과 기록 양식

실습마다 아래처럼 적는다. “성공”만 적지 않고 한계까지 적는 습관이 연구의 출발점이다.

| 항목 | 예시 |
| --- | --- |
| 실습 | fd/dup/pread offset 실습 |
| 예상 | dup fd는 offset을 공유하고 pread는 offset을 바꾸지 않는다 |
| 실행 환경 | Python 3.x, Linux, 임시 디렉터리 |
| 관측 | `b'AB' b'CD' b'BC'`, offset `4 4` |
| 해석 | read는 공유 offset을 이동, pread는 명시 offset 사용 |
| 실패 조건 | `os.pread` 미지원 플랫폼, timeout, assert 실패 |
| 한계 | crash durability와 Python buffering은 검증하지 않음 |

## 9. 상급 연구 수업 1: scheduler 공정성과 지연 tradeoff 설계

실행하지 않는 설계 문제다. 위험한 부하를 걸거나 우선순위를 바꾸지 않는다.

문제: 같은 서버에서 두 종류의 작업이 있다.

- A: 짧은 요청. CPU 2 ms가 필요하고 사용자는 20 ms 안의 응답을 원한다.
- B: 긴 batch. CPU 200 ms가 필요하고 총 처리량이 중요하다.
- CPU는 하나라고 가정한다. 문맥 교환 비용과 I/O는 처음에는 무시한다.

설계 질문:

1. 완전한 FIFO로 B가 먼저 오면 A의 지연은 어떻게 되는가?
2. A를 항상 먼저 실행하면 B의 throughput과 starvation 위험은 어떻게 되는가?
3. time slice를 작게 하면 어떤 장점과 비용이 생기는가?
4. 실제 시스템에서 무엇을 관측해야 “공정하다” 또는 “지연이 줄었다”고 말할 수 있는가?

모범 답안:

- FIFO에서 B가 먼저 CPU 200 ms를 쓰면 뒤의 A는 계산 2 ms뿐이어도 약 202 ms 뒤 끝난다. A의 SLO 20 ms를 넘는다.
- A 우선 정책은 짧은 지연에는 유리하지만 A가 계속 들어오면 B가 굶을 수 있다.
- 작은 time slice는 긴 작업이 CPU를 독점하는 시간을 줄여 interactive latency를 낮출 수 있다. 대신 context switch overhead와 cache locality 손실이 생긴다.
- 관측은 평균만으로 부족하다. A의 p50/p95/p99 latency, B의 throughput, runnable queue 길이, context switch 수, CPU 사용률, starvation 여부를 함께 본다.

제약:

- 실제 서버에서 `nice`, realtime priority, CPU affinity, cgroup quota를 바꾸지 않는다.
- 설계 검토만으로 실제 scheduler 구현을 단정하지 않는다. 커널 버전과 정책 문서를 확인한다.

평가 rubric:

| 점수 | 기준 |
| --- | --- |
| 3 | A/B의 목표가 다르고 latency와 throughput tradeoff가 있음을 숫자로 설명 |
| 2 | FIFO와 우선순위의 장단점을 말하지만 관측 지표가 부족 |
| 1 | “짧은 것을 먼저” 같은 직관만 있고 starvation이나 overhead 언급 없음 |
| 0 | CPU 사용률 하나로 결론 |

## 10. 상급 연구 수업 2: memory residency와 page fault를 cache drop 없이 연구하기

위험한 방법은 전역 cache drop이나 swap 설정 변경이다. 이 교재에서는 하지 않는다. 대신 안전한 연구 설계를 만든다.

질문: 큰 파일을 처음 읽을 때와 다시 읽을 때 지연이 다르다. 이 차이가 page cache 때문인지, 장치 cache 때문인지, 애플리케이션 처리 때문인지 어떻게 좁힐까?

안전한 설계:

1. 작은 전용 임시 파일을 사용하고 크기를 제한한다.
2. `time.monotonic()`으로 wall time을 재되 결과를 benchmark로 주장하지 않는다.
3. 같은 프로세스에서 첫 읽기와 두 번째 읽기를 비교하되, page cache·장치 cache·Python buffer가 섞였다고 기록한다.
4. `/proc/self/stat`이나 `resource.getrusage()` 같은 프로세스 단위 fault counter를 학습용으로 볼 수 있지만, 플랫폼별 의미와 단위를 확인한다.
5. 전역 `/proc/sys/vm/drop_caches`를 쓰지 않는다.

모범 해석:

- 두 번째 읽기가 빠른 것은 “SSD가 빨라졌다”가 아니라 어느 cache 계층이 따뜻해졌다는 증거다.
- major fault 증가가 보이면 저장장치나 backing store에서 page를 가져왔을 가능성이 있지만, 실험 조건과 counter 정의를 확인해야 한다.
- RSS가 증가했다는 사실은 실제 소유 메모리 증가, 공유 page, file-backed cache의 어느 것인지 더 나눠야 한다.

한계:

- 일반 사용자 권한에서 실제 물리 page residency를 완전하게 증명하기 어렵다.
- remote filesystem과 container 환경은 관측 위치를 바꾼다.
- 안전한 실습은 운영 장비의 cold-cache 성능을 재현하지 않는다.

## 11. 상급 연구 수업 3: symbol/source reading으로 toy kernel path 따라가기

위험한 kernel module을 빌드하거나 로드하지 않고, 문서와 소스 읽기 문제로 훈련한다.

문제: `read(fd, buf, 4096)`이 커널에서 어느 개념 경로를 지나는지 설명하라.

읽기 순서:

1. 사용자 API: Python `os.read` 또는 C `read(2)`가 fd와 count를 받는다.
2. syscall 경계: 커널은 fd가 유효한지, 읽을 수 있는지 확인한다.
3. VFS: fd가 가리키는 file object와 file operation을 찾는다.
4. Page cache: 요청 범위가 cache에 있으면 복사, 없으면 하위 filesystem으로 읽기 요청.
5. Filesystem mapping: file offset을 block 위치로 변환한다.
6. Block layer/device: read request를 queue에 넣고 completion을 기다린다.
7. 반환: 실제 읽은 바이트 수 또는 오류를 user space로 돌려준다.

모범 답안의 핵심:

- “read가 디스크를 읽는다”가 아니라 cache hit면 장치 I/O가 없을 수 있다고 말한다.
- fd, file object, inode, page cache, block request를 구분한다.
- 소스 symbol 이름은 kernel 버전에 따라 달라질 수 있으므로 특정 함수명 하나를 영원한 진리로 외우지 않는다.

검증 가능한 관측:

- 작은 파일을 두 번 읽고 두 번째가 빠른 현상은 cache 가능성을 보여 줄 수 있다.
- `strace` 같은 도구가 있으면 syscall 경계는 볼 수 있지만, page cache hit/miss 전체를 자동으로 설명하지 않는다.
- 이 교재의 기본 실습에는 추가 도구 설치나 kernel tracing을 포함하지 않는다.

## 12. Capstone 문제 1: “명령은 성공 출력인데 실패했다”

상황:

~~~text
한 배치 스크립트가 화면에 "uploaded"를 출력했다.
상위 orchestrator는 실패로 기록했다.
개발자는 "출력이 uploaded니까 성공인데 orchestrator 버그"라고 주장한다.
~~~

질문: 무엇을 확인해야 하는가?

모범 답안:

1. 프로세스 종료 코드와 stdout/stderr를 분리해 확인한다.
2. `subprocess.run(..., check=True)` 또는 returncode 검사로 실패를 판정했는지 본다.
3. 출력 문자열이 실제 업로드 완료 뒤에 찍힌 것인지, 시도 직후 찍힌 것인지 코드 위치를 확인한다.
4. timeout, signal 종료, 부분 출력, retry 중복 여부를 기록한다.
5. 원격 저장소나 DB의 최종 상태는 별도 API와 checksum/commit 정보로 확인한다.

증거:

- returncode, stdout, stderr, 시작·종료 시각, 요청 ID, 원격 응답 코드.

한계:

- 화면 출력만으로 원격 durability를 증명하지 못한다.
- orchestrator가 보는 namespace/env와 수동 실행 환경이 다를 수 있다.

Rubric:

| 점수 | 기준 |
| --- | --- |
| 3 | stdout과 exit status를 분리하고 원격 상태 검증까지 제안 |
| 2 | 종료 코드는 확인하지만 timeout/partial output 언급 부족 |
| 1 | 출력 문자열만 다시 확인 |
| 0 | 한쪽을 버그로 단정 |

## 13. Capstone 문제 2: “counter가 가끔 9998이다”

상황:

~~~text
두 thread가 공유 counter를 각각 5000번 증가시킨다.
가끔 최종값이 10000보다 작다.
~~~

질문: race를 어떻게 설명하고 고칠 것인가?

모범 답안:

- `counter += 1`은 읽기, 더하기, 쓰기의 논리 단계로 나눌 수 있다.
- 두 thread가 같은 이전 값을 읽으면 한쪽 증가가 덮인다.
- 공유 상태 변경 구간을 lock으로 보호하거나, thread별 local count를 모은 뒤 합산하거나, queue/message passing으로 공유 변경을 줄인다.
- 테스트는 운에 맡기지 않고 barrier나 수동 interleave simulation으로 race 모양을 설명한다.

증거:

- deterministic interleave에서 최종 1이 되는 표.
- lock 적용 뒤 기대 횟수와 실제 횟수 일치.

한계:

- Python GIL이 모든 언어와 kernel race 문제를 없애지 않는다.
- lock은 correctness를 주지만 contention과 deadlock 위험을 만든다.

Rubric:

| 점수 | 기준 |
| --- | --- |
| 3 | interleave 원리, lock/대안, deadlock·성능 한계까지 설명 |
| 2 | lock 필요성은 말하지만 왜 잃어버리는지 약함 |
| 1 | 반복 횟수를 줄이거나 sleep을 넣자고 함 |
| 0 | CPU 계산 오류라고 주장 |

## 14. Capstone 문제 3: “mmap이면 파일이 바로 안전하게 저장된다?”

상황:

~~~text
프로그램이 MAP_SHARED mmap에 값을 쓴 뒤 다른 프로세스가 그 값을 읽었다.
작성자는 "mmap은 메모리니까 fsync가 필요 없고 전원 손실에도 안전하다"고 말한다.
~~~

질문: 어떤 부분이 맞고 어떤 부분이 틀렸는가?

모범 답안:

- 다른 프로세스가 읽은 것은 visibility 관측이다. shared mapping 변경이 보였다는 뜻이다.
- 파일-backed shared mapping의 변경이 내구성을 갖는지는 별도 동기화가 필요하다. `msync`, file `fsync`, filesystem과 장치 계약을 확인해야 한다.
- `MAP_PRIVATE`라면 쓰기 변경은 COW private page에 생겨 원본 파일에 반영되지 않을 수 있다.
- `mmap()` 호출 자체가 파일 전체 I/O를 즉시 끝냈다는 뜻도 아니다. 접근 시 page fault가 발생할 수 있다.

증거:

- private/shared 작은 파일 실습에서 private view와 파일 내용 차이를 관측한다.
- shared 변경 후 파일 재읽기는 현재 내용 관측이다. crash test가 아니다.

한계:

- Python `mmap.flush()`와 Linux `msync`/`fsync`의 정확한 보장은 파일시스템·장치 stack을 같이 봐야 한다.
- 전원 차단 실험은 전용 장비와 절차 없이 하지 않는다.

Rubric:

| 점수 | 기준 |
| --- | --- |
| 3 | visibility, sharing, COW, durability, page fault를 모두 분리 |
| 2 | shared/private는 구분하지만 내구성 한계가 부족 |
| 1 | mmap은 빠르다는 말만 반복 |
| 0 | mmap이면 디스크 동기화가 불필요하다고 단정 |

## 15. 근거와 더 읽을 자료

- [Python subprocess](https://docs.python.org/3/library/subprocess.html): child process 실행, stdout/stderr capture, returncode, timeout, shell 사용 주의.
- [Python threading](https://docs.python.org/3/library/threading.html): `Thread`, `Lock`, `Barrier`.
- [Python os](https://docs.python.org/3/library/os.html): fd 기반 `open`, `read`, `write`, `dup`, `pread`.
- [Python mmap](https://docs.python.org/3/library/mmap.html): memory-mapped file 객체와 access mode.
- [Python tempfile](https://docs.python.org/3/library/tempfile.html), [pathlib](https://docs.python.org/3/library/pathlib.html): 안전한 임시 디렉터리와 경로 객체.
- [Linux `open(2)`](https://man7.org/linux/man-pages/man2/open.2.html), [Linux `pread(2)`](https://man7.org/linux/man-pages/man2/pread.2.html), [Linux `mmap(2)`](https://man7.org/linux/man-pages/man2/mmap.2.html): fd/open file description, positioned read, mapping 의미.
- [Linux memory-management concepts](https://docs.kernel.org/admin-guide/mm/concepts.html): virtual memory, page, address translation.
- [Linux scheduler docs](https://docs.kernel.org/scheduler/index.html), [kernel debugging docs](https://docs.kernel.org/process/debugging/index.html): 상급 연구 문제의 공식 출발점.
