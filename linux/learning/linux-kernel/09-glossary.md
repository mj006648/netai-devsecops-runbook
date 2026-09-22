# 09. Linux 커널 입문 용어집

[학습 목차](README.md) · 이전: [실습과 연구형 문제](08-labs-and-research.md)

보강·근거 확인일: **2026-09-22**.

이 용어집은 깊은 정의를 외우기 전에 “처음 보는 단어가 어느 계층의 말인지” 빠르게 찾기 위한 장이다. 각 항목은 풀네임, 한국어 한 문장, 주로 책임지는 계층, 헷갈리기 쉬운 대비, 연결 장을 함께 적는다. 실제 커널 구현의 세부 구조는 버전마다 바뀔 수 있으므로 공식 문서와 현재 시스템을 확인한다.

| 용어 | 풀네임 | 한국어 한 문장 | owner/layer | contrast | 연결 장 |
| --- | --- | --- | --- | --- | --- |
| OS | Operating System | 프로그램이 CPU·메모리·파일·장치를 나누어 쓰게 관리하는 기본 소프트웨어다. | 운영체제 전체 | 앱 자체가 아니라 앱을 실행시키는 기반 | 00 |
| Kernel | Kernel | 운영체제의 핵심으로 권한 있는 모드에서 메모리·스케줄링·파일·장치를 관리한다. | 커널 | 배포판 전체나 셸과 다름 | 00, 02 |
| Distribution | Linux Distribution | Linux 커널에 도구·라이브러리·패키지·설정을 묶은 설치 가능한 시스템이다. | 사용자 공간+커널 묶음 | 좁은 뜻의 Linux 커널과 다름 | 00, 01 |
| Shell | Shell | 사람이 입력한 명령 문법을 해석해 프로그램 실행과 리다이렉션을 준비하는 프로그램이다. | 사용자 공간 | 터미널 화면이나 커널과 다름 | 01 |
| Terminal | Terminal | 글자 입력과 출력을 주고받는 인터페이스다. | 사용자 인터페이스 | 셸 문법을 해석하는 주체가 아님 | 01 |
| Process | Process | 실행 중인 프로그램의 인스턴스로 PID, 주소 공간, 열린 fd, 권한을 가진다. | 커널 process 관리 | 프로그램 파일 그 자체와 다름 | 01, 03 |
| PID | Process ID | 커널이 프로세스를 구별하기 위해 붙이는 숫자 식별자다. | 커널 process 관리 | 포트 번호나 thread id와 다름 | 01 |
| Thread | Thread | 한 프로세스 안에서 명령을 실행하는 흐름이며 주소 공간을 공유할 수 있다. | 커널/런타임 실행 단위 | 프로세스보다 공유 범위가 넓음 | 03, 08 |
| Program | Program | 실행 가능한 코드와 관련 데이터이며 실행 전에는 단순한 파일일 수 있다. | 파일/사용자 공간 | process는 실행 중 상태 | 01 |
| Executable | Executable File | 커널과 loader가 실행 이미지로 사용할 수 있는 파일이다. | 파일시스템+loader | 스크립트나 라이브러리와 역할이 다를 수 있음 | 01, 02 |
| Exit Status | Exit Status | 프로세스가 끝나며 부모에게 남기는 작은 결과 코드다. | process 종료 계약 | stdout에 찍힌 문장과 다름 | 01, 08 |
| Environment Variable | Environment Variable | 프로세스 실행 시 전달되는 이름=문자열 값 쌍이다. | process 실행 환경 | 설정 파일이나 커널 전역값과 다름 | 01 |
| Syscall | System Call | 사용자 프로그램이 커널 기능을 요청하는 공식 진입점이다. | user/kernel 경계 | 일반 함수 호출과 권한 경계가 다름 | 02 |
| User Space | User Space | 일반 프로그램이 제한된 권한으로 실행되는 영역이다. | CPU 보호 모드/프로세스 | kernel space와 권한이 다름 | 02 |
| Kernel Space | Kernel Space | 커널 코드와 핵심 자료구조가 동작하는 권한 있는 영역이다. | CPU 보호 모드/커널 | 사용자 프로그램이 직접 접근하면 안 됨 | 02 |
| Mode Switch | Mode Switch | 같은 실행 흐름이 사용자 모드와 커널 모드 사이를 오가는 사건이다. | CPU/커널 경계 | 다른 프로세스로 바뀌는 context switch와 다름 | 02 |
| Context Switch | Context Switch | CPU가 실행하던 thread 상태를 저장하고 다른 thread 상태로 바꾸는 일이다. | scheduler | syscall 진입 자체와 항상 같지 않음 | 03 |
| Scheduler | Scheduler | 실행 가능한 thread 중 누가 CPU를 쓸지 고르는 커널 구성요소다. | CPU scheduling | 작업 큐 전체 관리와 구분 | 03, 08 |
| Runnable | Runnable State | CPU를 받을 준비가 된 실행 상태다. | scheduler 상태 | I/O를 기다리는 blocked와 다름 | 03 |
| Blocked | Blocked/Sleeping State | I/O나 lock 등 어떤 사건을 기다려 CPU를 바로 쓸 수 없는 상태다. | scheduler 상태 | CPU가 부족한 runnable과 다름 | 03 |
| Concurrency | Concurrency | 여러 일이 겹쳐 진행되는 구조이며 한 CPU에서도 가능하다. | 설계/실행 모델 | parallelism은 실제 동시 실행 | 03, 08 |
| Parallelism | Parallelism | 여러 CPU core 등이 실제 같은 시간에 일을 실행하는 상태다. | 하드웨어+스케줄러 | concurrency와 항상 같지 않음 | 03 |
| Race Condition | Race Condition | 실행 순서가 결과를 바꾸는 버그 조건이다. | 동시성 설계 | 단순 계산 오류와 다름 | 03, 08 |
| Lock | Lock/Mutex | 한 번에 하나의 실행 흐름만 임계 구역에 들어가게 하는 동기화 도구다. | 런타임/커널 동기화 | atomic 연산이나 lock-free 구조와 다름 | 03, 08 |
| Deadlock | Deadlock | 서로 필요한 자원을 기다려 모두 진행하지 못하는 상태다. | 동시성 실패 | 느림이나 starvation과 다름 | 03, 08 |
| Virtual Address | Virtual Address | 프로세스가 보는 메모리 주소이며 물리 주소로 변환될 수 있다. | 메모리 관리 | RAM의 실제 위치인 physical address와 다름 | 04, 08 |
| Physical Address | Physical Address | 메모리 하드웨어 쪽 위치를 가리키는 주소다. | 하드웨어/MMU | 일반 앱이 보통 직접 다루는 주소가 아님 | 04 |
| Page | Memory Page | 가상 메모리를 매핑하고 보호하는 고정 크기 구간이다. | 메모리 관리 | 파일시스템 block이나 SSD page와 다름 | 04 |
| Frame | Page Frame | 물리 메모리에서 page 크기로 나눈 구간이다. | 메모리 관리 | virtual page number와 다름 | 04, 08 |
| Page Table | Page Table | virtual page가 어떤 frame과 권한으로 연결되는지 기록하는 표다. | 커널+MMU | 파일의 목차나 DB index와 다름 | 04 |
| MMU | Memory Management Unit | CPU 쪽에서 주소 변환과 접근 보호를 수행하는 하드웨어 기능이다. | CPU 하드웨어 | 커널 자료구조 자체가 아님 | 04 |
| TLB | Translation Lookaside Buffer | 주소 변환 결과를 빠르게 재사용하는 CPU 캐시다. | CPU 하드웨어 | 데이터 cache와 저장 대상이 다름 | 04 |
| Page Fault | Page Fault | 현재 주소 접근을 바로 끝낼 수 없어 커널 처리가 필요한 사건이다. | CPU+커널 메모리 | 항상 프로그램 고장이라는 뜻이 아님 | 04 |
| COW | Copy-on-Write | 읽는 동안 공유하다가 쓰는 순간 사본을 만들어 분리하는 기법이다. | 메모리/파일시스템 | 단순 deep copy와 시점이 다름 | 04, 08 |
| RSS | Resident Set Size | 프로세스 page 중 현재 RAM에 올라온 양을 세는 대표 지표다. | 메모리 계정 | VIRT나 PSS와 다름 | 04, 07 |
| PSS | Proportional Set Size | 공유 page 비용을 공유자 수에 맞게 나누어 계산한 메모리 지표다. | 메모리 계정 | RSS 합산의 중복을 줄임 | 04, 07 |
| Swap | Swap Space | RAM 압박 시 일부 내용을 backing storage로 옮기는 메커니즘이다. | 메모리 관리+저장 | 공짜 RAM 확장이 아님 | 04, 07 |
| VFS | Virtual File System | 여러 파일시스템을 공통 객체와 연산으로 연결하는 Linux 계층이다. | 파일시스템 커널 계층 | ext4 같은 개별 파일시스템과 다름 | 05 |
| File Descriptor | File Descriptor | 프로세스가 열린 파일·파이프·소켓 등을 가리키는 작은 정수 핸들이다. | process fd table | 파일 이름이나 inode 번호와 다름 | 05, 08 |
| Open File Description | Open File Description | 열린 파일의 offset과 status flag를 담는 커널 상태다. | 커널 열린 파일 테이블 | fd 번호 자체와 다름 | 05, 08 |
| Inode | Index Node | 파일 종류·권한·크기·데이터 위치 같은 본체 metadata를 담는 객체다. | 파일시스템 | 파일 이름은 보통 directory entry에 있음 | 05 |
| Dentry | Directory Entry Cache/Object | 이름 lookup 결과를 표현·캐시하는 VFS 객체다. | VFS path lookup | 파일 내용 page cache와 다름 | 05 |
| Mount | Mount | 파일시스템을 디렉터리 tree의 한 지점에 붙이는 작업이다. | VFS namespace | 디렉터리 생성과 다름 | 05, 07 |
| Block Device | Block Device | LBA와 길이 중심으로 block read/write를 받는 저장 장치 인터페이스다. | block layer/driver | 파일 이름을 이해하지 않음 | 05 |
| Driver | Device Driver | 커널과 특정 장치 명령 사이를 연결하는 코드다. | 커널 장치 계층 | 장치 내부 firmware와 다름 | 05 |
| Firmware | Firmware | 장치나 플랫폼 내부에서 동작하는 제어 코드다. | 하드웨어/장치 | OS driver와 배포 위치가 다름 | 05 |
| Namespace | Namespace | 프로세스가 보는 PID, mount, network 같은 이름 공간을 분리하는 기능이다. | 격리 커널 기능 | 권한 제한 전체를 뜻하지 않음 | 06 |
| Cgroup | Control Group | 프로세스 묶음의 CPU·메모리·I/O 사용을 계정하고 제한하는 기능이다. | 자원 제어 | namespace처럼 보는 이름을 바꾸는 기능과 다름 | 06 |
| Capability | Linux Capability | root 권한을 더 작은 권한 조각으로 나누어 부여하는 기능이다. | 보안/권한 | 파일 permission bit와 다름 | 06 |
| Seccomp | Secure Computing Mode | 프로세스가 사용할 수 있는 syscall을 제한하는 Linux 보안 기능이다. | syscall 필터링 | namespace나 cgroup과 목적이 다름 | 06 |
| LSM | Linux Security Module | SELinux/AppArmor 같은 추가 접근 제어를 연결하는 커널 보안 프레임워크다. | 보안 커널 계층 | 전통 Unix mode bit만이 아님 | 06 |
| Signal | Signal | 프로세스나 thread에 사건을 알리는 비동기 통지 메커니즘이다. | process 제어 | 파일 descriptor I/O와 다름 | 06, 07 |
| OOM | Out Of Memory | 필요한 메모리를 확보하지 못해 커널이나 cgroup 정책이 개입하는 상황이다. | 메모리 관리 | CPU 과부하와 다름 | 07 |
| PSI | Pressure Stall Information | CPU·메모리·I/O 압박 때문에 작업이 멈춘 시간을 보여 주는 Linux 지표다. | 관측/accounting | 단순 사용률과 다름 | 07 |
| Load Average | Load Average | 실행 가능하거나 특정 대기 상태인 작업 수의 시간 평균이다. | 관측/scheduler | CPU 사용률 퍼센트가 아님 | 07 |
| Wall Time | Wall-clock Elapsed Time | 사람이 보는 실제 경과 시간이다. | 측정 | CPU time과 다름 | 07, 08 |
| CPU Time | CPU Time | 프로세스가 CPU에서 실제 실행된 시간 계정이다. | 측정/scheduler | I/O 대기까지 포함한 wall time과 다름 | 07 |
| Timeout | Timeout | 정해진 시간 안에 완료를 확인하지 못한 상태다. | API/운영 정책 | 상대가 아무 일도 안 했다는 증거가 아님 | 07, 08 |

## 읽는 순서

처음 읽는 독자는 `OS → Kernel → Process → Syscall → Virtual Address → Page Fault → VFS → File Descriptor → Namespace/Cgroup → PSI` 순서로 훑는다. 그다음 각 장의 실습과 관측 문제로 돌아가면 단어가 문장 속에서 움직이기 시작한다.

## 근거와 더 읽을 자료

- [Linux man-pages intro(7)](https://man7.org/linux/man-pages/man7/intro.7.html): 매뉴얼 섹션과 기본 Unix/Linux 개념.
- [Linux VFS 문서](https://docs.kernel.org/filesystems/vfs.html): VFS, inode, dentry, file object.
- [Linux memory-management concepts](https://docs.kernel.org/admin-guide/mm/concepts.html): virtual memory, page, address translation.
- [Linux cgroup v2 문서](https://docs.kernel.org/admin-guide/cgroup-v2.html): cgroup 자원 제어.
- [Linux PSI 문서](https://docs.kernel.org/accounting/psi.html): pressure stall 정보.
- [Python subprocess](https://docs.python.org/3/library/subprocess.html), [threading](https://docs.python.org/3/library/threading.html), [os](https://docs.python.org/3/library/os.html), [mmap](https://docs.python.org/3/library/mmap.html): 08장 실습의 표준 라이브러리 근거.
