# Ubuntu/Linux internals 그림

모든 SVG는 1200px 너비의 직접 작성한 벡터 그림이며 `<title>`, `<desc>`, `role="img"`를 포함한다.

| 파일 | 연결 설명 |
| --- | --- |
| [ubuntu-stack.svg](ubuntu-stack.svg) | Application→libc/runtime→syscall→kernel subsystem→hardware 계층 |
| [cgroup-tree.svg](cgroup-tree.svg) | systemd slice와 cgroup v2 controller 상속·accounting 경계 |
| [cpu-memory-pressure.svg](cpu-memory-pressure.svg) | CPU quota, memory high/max, PSI를 증상과 연결 |
| [io-uring-lifecycle.svg](io-uring-lifecycle.svg) | SQE 제출, kernel 실행, CQE matching, buffer release 순서 |
| [io-uring-modes.svg](io-uring-modes.svg) | interrupt, polling, cancel race의 서로 다른 흐름 |
| [kernel-workload-path.svg](kernel-workload-path.svg) | 실제 kernel workload 경로와 순수 계산 모형의 경계 |

색은 계층을 보조한다. 의미는 색만이 아니라 상자 제목과 화살표 label로도 표시했다.
