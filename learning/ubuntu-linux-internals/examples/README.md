# 안전한 로컬 계산 모형

세 파일은 Python 3 표준 라이브러리만 사용한다. 실제 sysfs, cgroup, systemd, kernel parameter, io_uring syscall을 읽거나 변경하지 않는다.

```text
python3 -B learning/ubuntu-linux-internals/examples/cgroup_budget.py
python3 -B learning/ubuntu-linux-internals/examples/ring_lifetime_model.py
python3 -B learning/ubuntu-linux-internals/examples/memory_pressure_model.py
```

| 파일 | 확인하는 작은 계약 | 확인하지 않는 것 |
| --- | --- | --- |
| `cgroup_budget.py` | quota/period 비율과 두 thread의 공유 예산 | 실제 scheduler timing |
| `ring_lifetime_model.py` | ID matching, out-of-order CQE, buffer 한 번 해제 | 실제 io_uring syscall |
| `memory_pressure_model.py` | high/max 판정, clean/dirty 회수 순서 | 실제 Linux reclaim 예측 |

각 파일의 assert는 고정된 작은 입력의 상태 전이를 확인한다. Kernel 기능 지원이나 성능 측정 결과로 사용하지 않는다.

2026-10-11에 Python 3.12.3에서 세 파일을 각각 한 번 실행해 아래 결과와 assert 통과를 확인했다.

| 모형 | 출력에서 확인한 값 |
| --- | --- |
| CPU | `0.50 CPU`, 첫 period에 A·B 각 25 ms, 남은 demand 10 ms |
| ring | ID 102가 먼저 완료, ID 101은 `EINVAL`, 대응 buffer를 한 번씩 해제 |
| memory | 360 MiB에서 clean 80 MiB 회수, dirty 40 MiB writeback·회수 뒤 240 MiB |

## 선택 C 예제: 실제 liburing API 모양

[uring_read.c](uring_read.c)는 사용자가 command-line 인자로 준 작은 일반 file을 `O_RDONLY`로 열고 offset 0에서 최대 4096 byte를 한 번 읽는다. Device 경로를 자동 선택하거나 system parameter를 바꾸지 않는다.

필요 조건:

- C compiler와 liburing header/library가 설치되어 있어야 한다.
- 실행 kernel이 사용한 io_uring operation을 지원해야 한다.
- Seccomp·LSM·container policy가 io_uring syscall을 허용해야 한다.
- 읽을 file에 일반적인 read 권한이 있어야 한다.

Compile 예시는 다음과 같다.

```text
cc -Wall -Wextra -O2 -o /tmp/uring_read \
  learning/ubuntu-linux-internals/examples/uring_read.c -luring
```

실행 예시는 사용자가 직접 만든 작은 일반 file 경로를 명시한다.

```text
/tmp/uring_read /path/to/small-regular-file
```

이 C 예제는 이 교재 작성 과정에서 compile하거나 실행하지 않았다. 최신 liburing를 사용해 compile된다고 실행 kernel이 모든 최신 기능을 자동 지원하는 것은 아니다. Queue 생성·operation submit 단계의 실제 오류를 각각 확인해야 한다.

이 예제는 한 번 읽고 종료하는 프로그램이다. 대응 read CQE를 확인한 정상 경로에서는 ring을 정리한 뒤 buffer를 해제한다. 제출 뒤 완료를 확인하지 못한 오류 경로에서는 buffer를 다시 쓰거나 `free()`하지 않고 process 전체를 종료한다. Ring close가 취소를 유발한다는 사실과 모든 완료를 확인했다는 사실을 혼동하지 않기 위한 구분이다. 장기 실행 서버라면 [취소 요청과 대상 CQE를 수거하는 절차](https://www.man7.org/linux/man-pages/man7/io_uring_cancelation.7@@liburing.html)를 설계해야 한다.
