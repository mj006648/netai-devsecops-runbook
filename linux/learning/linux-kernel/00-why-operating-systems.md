# 00. 운영체제는 왜 필요한가: 자원, 추상화, 격리, 약속

다음: [부팅·시스템콜·인터럽트](02-boot-syscalls-and-interrupts.md)

보강·근거 확인일: **2026-09-22**. 이 장은 Linux 커널을 배우기 전에 “운영체제”라는 말이 무엇을 해결하려고 등장했는지 설명한다. 특정 배포판 사용법이 아니라, 어떤 컴퓨터에서도 반복해서 나오는 핵심 문제를 다룬다.

운영체제는 한 문장으로 말하면 **하드웨어 자원을 여러 프로그램이 안전하고 예측 가능하게 쓰도록 중재하는 시스템 소프트웨어**다. 조금 더 정확히는 CPU 시간, 메모리, 저장장치, 네트워크, 장치, 권한을 관리하고, 프로그램에는 파일·프로세스·주소 공간·소켓 같은 추상화를 제공한다.

## 1. 프로그램 하나만 돌리면 운영체제가 필요 없을까?

초기의 아주 단순한 기계라면 사람이 프로그램을 올리고, 실행하고, 끝나면 다음 프로그램을 올릴 수 있다. 이 방식은 “한 번에 하나”라서 이해하기 쉽다. 하지만 현실의 컴퓨터는 곧 네 가지 문제를 만난다.

| 문제 | 운영체제가 없을 때 | 운영체제가 하는 일 |
| --- | --- | --- |
| CPU 공유 | 한 프로그램이 CPU를 계속 차지할 수 있음 | 타이머와 스케줄러로 실행 순서를 나눔 |
| 메모리 보호 | 실수로 다른 프로그램 메모리를 덮어씀 | 주소 공간과 페이지 권한으로 격리 |
| 장치 공유 | 디스크·키보드·네트워크를 서로 충돌하며 사용 | 드라이버와 커널 인터페이스로 중재 |
| 실패 격리 | 한 프로그램 오류가 전체 기계를 망가뜨림 | 프로세스 종료로 피해 범위를 줄임 |

운영체제는 “컴퓨터를 편하게 쓰게 해 주는 메뉴”만이 아니다. 더 깊은 역할은 **위험한 권한을 한곳에 모으고, 나머지 프로그램은 제한된 약속을 통해 요청하게 만드는 것**이다.

## 2. 자원은 물건이고, 추상화는 다루는 방법이다

**자원(resource)**은 한계가 있는 대상이다. CPU 코어 수, RAM 용량, SSD 대역폭, 네트워크 큐, 파일 디스크립터 수, 전력과 냉각 여유도 자원이다. 자원은 누군가 많이 쓰면 다른 누군가가 덜 쓰게 된다.

**추상화(abstraction)**는 복잡한 실제 구조를 더 단순한 약속으로 보여 주는 방식이다. 예를 들어 SSD 내부에는 NAND page, erase block, FTL, wear leveling이 있지만 프로그램은 보통 “파일 offset 4096부터 100바이트 읽기”라고 요청한다. 파일은 추상화다.

좋은 추상화는 두 가지를 동시에 한다.

| 기능 | 뜻 | 예 |
| --- | --- | --- |
| 숨김 | 아래 복잡도를 모두 알지 않아도 쓰게 함 | 프로그램은 NVMe 명령을 직접 만들지 않고 `read()`를 호출 |
| 제한 | 위험한 동작을 직접 못 하게 함 | 사용자 프로그램은 임의 물리 메모리에 쓰지 못함 |

비유하면 운영체제는 도서관 사서와 비슷하다. 이용자는 서가 내부 규칙을 모두 몰라도 책을 빌릴 수 있고, 동시에 아무나 창고 열쇠를 들고 들어가 책을 훼손하지 못한다. 비유의 한계도 있다. 운영체제는 단순 안내자가 아니라 CPU privilege level, MMU, interrupt controller, 장치 DMA 같은 하드웨어 기능과 함께 강제력을 행사한다.

## 3. 격리는 “서로 모르게 한다”가 아니라 “피해 경계를 만든다”이다

**격리(isolation)**는 한 주체의 버그나 악의가 다른 주체에 미치는 영향을 줄이는 설계다. 프로세스 격리는 가장 기본적인 예다. 프로세스 A가 잘못된 포인터로 쓰기를 해도, 정상 상황에서는 프로세스 B의 메모리를 바꾸지 못한다.

격리는 여러 층에 있다.

| 층 | 격리 수단 | 막으려는 일 |
| --- | --- | --- |
| CPU 권한 | user mode와 kernel mode | 앱이 장치 제어 명령을 직접 실행 |
| 메모리 | page table과 접근 권한 | 다른 프로세스 주소 공간 읽기·쓰기 |
| 파일 | UID/GID, mode bit, ACL | 허가 없는 파일 접근 |
| 컨테이너 | namespace와 cgroup | 이름 공간 혼동, 자원 독점 |
| VM | 하이퍼바이저와 가상 하드웨어 | 게스트 OS 간 커널 공유 |

격리는 완전한 마법 벽이 아니다. 커널 취약점, 잘못된 권한, side channel, 공유 캐시, 장치 DMA 설정 오류 같은 경로가 있다. 그래서 “컨테이너 안이다”는 보안 결론이 아니라, 어떤 namespace·cgroup·capability·seccomp·LSM·runtime 설정을 썼는지 묻는 출발점이다.

## 4. 정책과 기작을 구분해야 커널을 읽을 수 있다

운영체제 설계에서 자주 나오는 말이 **policy**와 **mechanism**이다.

| 말 | 질문 | 예 |
| --- | --- | --- |
| 기작(mechanism) | 무엇을 할 수 있게 만드는가? | 타이머 인터럽트, context switch, page table 변경 |
| 정책(policy) | 그 능력을 언제 누구에게 적용할까? | 어떤 task를 다음에 실행할지, 어떤 page를 회수할지 |

스케줄러를 예로 들면 context switch는 기작이고, runnable task 중 누구를 고르는지는 정책이다. 메모리에서도 page를 디스크로 내보낼 수 있는 능력은 기작이고, 어떤 page를 먼저 reclaim할지는 정책이다.

정책과 기작은 완전히 분리되지 않는다. 어떤 기작은 특정 정책을 쉽게 만들고, 어떤 정책은 기작의 비용 때문에 불가능해진다. 그래도 문서를 읽을 때 “이 문장이 능력 설명인가, 선택 기준 설명인가”를 나누면 커널 개념이 훨씬 또렷해진다.

## 5. 배치 처리에서 시분할로: 운영체제 역사에서 반복된 질문

초기 컴퓨팅에서는 **batch processing**이 중요했다. 사용자는 카드나 테이프로 작업을 제출하고, 운영자는 작업 묶음을 순서대로 처리했다. 대화형 컴퓨터가 아니라 큰 계산 공장을 효율적으로 돌리는 느낌에 가깝다.

그 뒤 **time-sharing**이 핵심 아이디어로 떠올랐다. 사람 여러 명이 단말기를 통해 동시에 컴퓨터를 쓰는 것처럼 느끼도록, 운영체제가 CPU 시간을 아주 짧게 나눈다. 여기서 “동시에”는 물리적으로 한 코어가 한 순간에 여러 명령을 실행한다는 뜻이 아니라, 빠른 전환으로 사람의 체감에 맞춘다는 뜻이다.

Unix는 이 흐름에서 중요한 전환점이었다. Unix 계열은 작은 도구, 파일 중심 인터페이스, 프로세스와 pipe, C 언어 기반 이식성을 통해 운영체제와 개발 문화에 큰 영향을 주었다. Dennis Ritchie의 “The Evolution of the Unix Time-sharing System”은 Unix가 시분할 환경과 연구 개발의 맥락에서 자랐음을 설명한다. GNU 프로젝트의 1983년 초기 발표는 자유 소프트웨어 Unix 호환 운영체제를 만들겠다는 목표를 제시했고, “커널과 C 프로그램을 작성·실행하기 위한 유틸리티”를 함께 언급했다. Linux 0.01은 kernel.org Historic 아카이브에 보존되어 있으며, Linux는 이 Unix 계열 아이디어와 PC 하드웨어, 인터넷 협업이 만난 사례가 되었다.

중요한 점은 Linux가 “Unix 원본 코드”라는 뜻이 아니라는 것이다. Linux는 Unix-like 커널이며, POSIX 계열 인터페이스와 Unix에서 온 개념을 많이 따른다. GNU user space, libc, shell, compiler, package system, systemd 같은 구성요소와 함께 우리가 부르는 Linux 시스템이 된다.

## 6. 커널은 운영체제 전체가 아니라 가장 높은 권한의 핵심이다

**커널(kernel)**은 privileged mode에서 실행되며 하드웨어와 자원을 직접 관리하는 핵심 프로그램이다. 하지만 일상에서 “운영체제”라고 부르는 것은 커널만이 아니다.

| 구성요소 | 역할 |
| --- | --- |
| Linux kernel | 프로세스, 메모리, 파일시스템, 네트워크, 드라이버, 보안 훅 |
| libc | C/POSIX 함수와 syscall wrapper 제공 |
| init/PID 1 | 부팅 후 서비스 시작과 프로세스 수거 |
| shell/coreutils | 사용자가 명령을 실행하고 파일을 다룸 |
| package manager | 소프트웨어 설치·업데이트 |
| system services | logging, networking, time sync, container runtime 등 |

커널 안에도 모든 코드가 같은 성격은 아니다. scheduler, memory manager, VFS, block layer, networking stack, drivers, LSM은 각자 다른 문제를 푼다. 이 교재는 배포판 관리법이 아니라 Linux 커널의 핵심 경로를 중심으로 설명한다.

## 7. 모놀리식, 모듈식, 마이크로커널, 유니커널

운영체제 구조는 “커널에 무엇을 넣을 것인가”라는 질문으로 나눌 수 있다.

| 구조 | 핵심 아이디어 | 장점 | 대가 |
| --- | --- | --- | --- |
| monolithic kernel | 파일시스템·네트워크·드라이버 대부분이 kernel space에서 동작 | 직접 호출이 빠르고 통합 최적화 쉬움 | 커널 버그의 피해 범위가 큼 |
| modular monolithic | 큰 틀은 monolithic이지만 module을 동적으로 적재 | 필요 기능만 로드, 하드웨어 지원 확장 | module도 kernel 권한을 가짐 |
| microkernel | 주소 공간, IPC, scheduling 같은 최소 기능만 커널에 두고 서비스는 user space로 이동 | 서비스 격리와 구조적 명확성 | IPC 비용과 설계 복잡도 |
| unikernel | 하나의 앱과 필요한 OS 기능만 묶어 단일 이미지로 실행 | 작은 이미지, 특정 워크로드 최적화 | 일반 목적 격리·디버깅·운영 도구 제약 |

Linux는 보통 modular monolithic kernel로 설명한다. `ext4`, `xfs`, `nvme`, `ip_tables` 같은 기능이 module일 수 있지만, 적재되면 kernel address space에서 실행된다. 따라서 “모듈식이므로 microkernel처럼 안전하다”는 말은 틀리다.

## 8. API, ABI, 라이브러리, 시스템콜은 서로 다르다

초보자가 가장 많이 헷갈리는 축이다.

| 용어 | 뜻 | 예 |
| --- | --- | --- |
| API | 소스 코드 수준에서 호출하는 약속 | C의 `printf()`, POSIX의 `open()` |
| ABI | 컴파일된 바이너리 수준의 약속 | syscall 번호, register 전달 규칙, 구조체 배치 |
| library | 프로그램에 함수와 코드를 제공하는 묶음 | glibc, musl |
| system call | user program이 kernel에 서비스를 요청하는 공식 진입점 | `read(2)`, `write(2)`, `mmap(2)` |

`printf("hi\n")`는 libc 함수다. 출력 대상이 터미널이면 libc가 내부에서 `write()` 계열 시스템콜을 호출할 수 있다. 프로그램은 대개 syscall instruction을 직접 쓰지 않고 libc wrapper를 부른다. man-pages의 `syscalls(2)`는 system call을 application과 kernel 사이의 기본 인터페이스로 설명하고, `syscall(2)`는 architecture마다 argument 전달 규칙이 다름을 설명한다.

손으로 추적하면 다음과 같다.

~~~text
사용자 코드: printf("A\n")
  ↓ C library: formatting, buffering 판단
  ↓ write 계열 system call wrapper
  ↓ CPU가 user mode에서 kernel mode로 전환
  ↓ kernel VFS/tty/driver 경로
  ↓ 장치 또는 pseudo terminal로 데이터 전달
  ↓ return value와 errno 규칙으로 사용자 코드 복귀
~~~

여기서 `printf()` API가 안정적이라는 말과 Linux syscall ABI가 안정적이라는 말은 다르다. Linux 커널은 내부 함수 API를 안정적으로 유지하지 않는다는 문화를 갖고 있지만, userspace가 의존하는 syscall과 일부 stable ABI는 훨씬 강한 호환성 기대를 갖는다. kernel.org ABI 문서는 stable/testing/obsolete/removed 같은 안정성 등급을 나눠 설명한다.

## 9. kernel version은 기능, ABI, 배포판 정책을 동시에 뜻하지 않는다

`uname -r`로 보이는 커널 버전은 실행 중인 커널 빌드의 이름이다. 하지만 버전 하나만 보고 다음을 모두 알 수는 없다.

| 질문 | 버전만으로 충분한가? | 이유 |
| --- | --- | --- |
| 특정 syscall이 있는가? | 대체로 단서가 되지만 부족 | 배포판 backport나 configuration 차이 |
| 특정 보안 기능이 켜졌는가? | 부족 | `CONFIG_*`, boot option, LSM 순서, runtime 설정 필요 |
| 커널 내부 함수가 같은가? | 부족 | 내부 API는 안정 ABI가 아님 |
| 사용자 프로그램이 계속 실행되는가? | 일반적으로 강하게 기대 | syscall ABI와 userspace 호환성을 중시 |

그래서 운영에서 중요한 질문은 “버전이 몇인가”에서 끝나지 않는다. “어떤 configuration으로 빌드되었는가, 어떤 patch가 backport되었는가, 어떤 boot parameter와 runtime 설정인가”까지 확인해야 한다.

## 10. 손으로 보는 운영체제 계약: 같은 파일명, 다른 계층

다음 상황을 생각해 보자.

~~~text
프로그램이 /var/log/app.log에 "ok"를 쓴다.
~~~

이 한 문장은 여러 계약으로 쪼개진다.

| 단계 | 실제 질문 |
| --- | --- |
| 경로 해석 | `/`, `var`, `log`, `app.log` dentry/inode를 찾을 수 있는가? |
| 권한 검사 | 이 UID/GID/capability/LSM context가 쓰기를 할 수 있는가? |
| 파일 객체 | 현재 process의 fd table에 어떤 open file description이 생기는가? |
| page cache | 쓰기 바이트가 어느 page cache page를 dirty로 만드는가? |
| filesystem | inode size, block mapping, metadata journal은 어떻게 바뀌는가? |
| block layer | 어떤 bio/request가 장치 queue로 가는가? |
| device | NVMe queue와 completion은 어떻게 완료를 알리는가? |
| durability | `write()` return, `fsync()` return, 실제 전원 장애 내구성은 어떻게 다른가? |

이 표는 뒤 장의 로드맵이다. 운영체제를 잘한다는 것은 명령어를 많이 외우는 것이 아니라, 같은 사건을 계층별 계약으로 분해해 어디에서 막혔는지 찾는 능력이다.

## 11. 오개념 정리

| 오개념 | 바로잡기 |
| --- | --- |
| 운영체제는 GUI다 | GUI는 user space 구성요소다. 커널은 GUI 없이도 동작한다. |
| 커널은 모든 프로그램의 부모다 | Linux에서 PID 1은 user space init이다. 커널은 process를 만들고 관리하지만 일반 process가 아니다. |
| syscall은 함수 호출과 같다 | 호출처럼 보이지만 privilege transition, ABI, 검증, copy_from_user 같은 경계를 지난다. |
| Linux 내부 API는 안정적이다 | userspace ABI와 달리 kernel internal API는 바뀔 수 있다. |
| container는 VM과 같은 격리다 | container는 host kernel을 공유한다. VM은 보통 별도 guest kernel을 가진다. |
| 빠른 것은 항상 kernel bypass다 | bypass는 tradeoff다. 보안, 관측성, 운영 도구, TCP stack 기능을 잃을 수 있다. |

## 12. 해설 문제

1. `read(fd, buf, 4096)`은 API, ABI, syscall 중 무엇인가?
   - `read()`라는 C 함수 이름은 API다. 그 함수가 실제 Linux `read` syscall을 호출할 때 syscall ABI를 따른다. `fd`, pointer, length가 어떤 register에 들어가는지는 architecture ABI 문제다.

2. 모놀리식 커널에서 드라이버 버그가 위험한 이유는 무엇인가?
   - 드라이버가 kernel address space와 kernel privilege에서 실행되기 때문이다. 잘못된 포인터나 race가 같은 커널의 다른 구조를 망가뜨릴 수 있다.

3. 정책과 기작을 page reclaim에 적용해 보라.
   - page를 unmap하고 writeback/swap으로 밀어낼 수 있는 능력은 기작이다. 어떤 cgroup, 어떤 LRU list, 어떤 anon/file page를 먼저 회수할지는 정책이다.

4. “glibc가 안정적이면 kernel ABI를 몰라도 된다”는 말은 언제 틀릴까?
   - seccomp filter, static binary, 직접 `syscall()`, container runtime, observability tool, architecture별 syscall argument 처리, 새 syscall 채택을 다룰 때는 kernel ABI를 알아야 한다.

## 13. 1차 참고 자료

- Linux Kernel Documentation: [Linux ABI description](https://docs.kernel.org/admin-guide/abi.html), [sysfs rules](https://docs.kernel.org/admin-guide/sysfs-rules.html)
- Linux man-pages: [syscalls(2)](https://man7.org/linux/man-pages/man2/syscalls.2.html), [syscall(2)](https://man7.org/linux/man-pages/man2/syscall.2.html)
- kernel.org Historic archive: [Linux Historic releases](https://www.kernel.org/pub/linux/kernel/Historic/)
- GNU Project: [Initial Announcement](https://www.gnu.org/gnu/initial-announcement.html), [Overview of the GNU System](https://www.gnu.org/gnu/gnu-history.en.html)
- MIT PDOS xv6 book: [Operating system organization](https://mit-pdos.github.io/xv6-riscv-book/first.html)
