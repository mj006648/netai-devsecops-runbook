# Linux·운영체제·커널: 프로그램이 실행되는 밑바닥부터

[통합 학습 안내](../../../learning/README.md) · [하드웨어](../../../hardware/learning/server-hardware/README.md) · [네트워크](../../../kubernetes/networking/networking-foundations/README.md) · [파일·데이터 시스템](../../../kubernetes/storage/data-systems-foundations/README.md) · [AI 인프라](../../../ai/learning/ai-infrastructure/README.md)

이 교재는 **커널, 프로세스, 메모리, 파일이 무슨 뜻인지 모르는 독자**를 출발점으로 한다. 앞에서는 컴퓨터 자원을 나눠 쓰는 이유와 셸 명령의 문법을 설명하고, 뒤에서는 커널이 관리하는 자료구조·실행 순서·동기화·장애를 다룬다. 특정 배포판의 명령 모음이나 커널 소스 전체를 대신하는 문서는 아니다. 원리를 이해한 뒤 실제 구현과 관측 결과를 읽기 위한 경로다.

## 장별 순서

| 장 | 내용 | 끝나면 설명할 수 있어야 하는 것 |
| --- | --- | --- |
| [00. 왜 운영체제가 필요한가](00-why-operating-systems.md) | 자원·추상화·격리·역사·커널 구조 | 프로그램이 장치를 제멋대로 사용하면 생기는 문제 |
| [01. 프로그램·프로세스·셸](01-programs-processes-and-shell.md) | 터미널·명령·fd·스레드·주소·권한 | 명령 한 줄이 실행되고 파일을 요청하는 주체 |
| [02. 부팅·시스템 호출·인터럽트](02-boot-syscalls-and-interrupts.md) | UEFI·bootloader·initramfs·PID1·모드 전환·DMA | 전원 버튼부터 서비스까지, 사용자 코드부터 장치 완료까지의 경로 |
| [03. 스케줄링과 동시성](03-scheduling-and-concurrency.md) | runnable·대기·경쟁·atomic·mutex·futex·RCU | 한 CPU를 나눠 쓰는 문제와 공유 데이터를 보호하는 문제의 차이 |
| [04. 가상 메모리와 회수](04-virtual-memory-and-reclaim.md) | page table·TLB·COW·mmap·RSS/PSS·swap·OOM | 주소 공간, 실제 RAM, 파일 캐시, 메모리 압박의 관계 |
| [05. VFS·드라이버·I/O](05-vfs-devices-and-io.md) | inode·dentry·file·bio/request·blk-mq·io_uring | 파일 인터페이스가 장치 큐와 완료 통지로 바뀌는 과정 |
| [06. 격리·보안·컨테이너](06-isolation-security-and-containers.md) | UID·권한·capabilities·namespace·cgroup·seccomp·LSM·KVM | 보이는 자원, 쓸 수 있는 자원, 허용된 동작의 차이 |
| [07. 관측과 문제 해결](07-observation-and-troubleshooting.md) | mount·CPU/메모리/I/O·서비스·네트워크·PSI | 관측으로 원인 후보 둘을 구별하는 방법 |
| [08. 실습·설계·연구](08-labs-and-research.md) | 작은 로컬 실험·예상 출력·해설·연구 과제 | 원리와 실제 결과를 대조하고 검증 한계를 적는 방법 |
| [09. 용어 사전](09-glossary.md) | 풀네임·쉬운 정의·관리 주체·혼동 구분 | 낯선 단어에서 본문으로 돌아가기 |

완전 입문자는 00→01을 천천히 읽고 08장의 작은 예제와 함께 진행한다. 04장 전에 [하드웨어 메모리 장](../../../hardware/learning/server-hardware/02-cpu-memory-numa.md)을 읽으면 DRAM·캐시와 가상 메모리를 구별하기 쉽다. 파일 저장을 우선 배우려면 01→05와 [데이터 시스템 01·02](../../../kubernetes/storage/data-systems-foundations/01-linux-read-write.md)를 연결한다.

## 운영체제를 볼 때 반복할 다섯 질문

1. **누가 실행하는가?** 사용자 스레드인가, 커널 작업인가, 장치인가?
2. **어떤 이름을 사용하는가?** PID, 가상 주소, fd, inode, LBA 중 무엇인가?
3. **무엇을 공유하는가?** 주소 공간, 열린 파일 상태, CPU, 큐, 물리 장치인가?
4. **언제 기다리는가?** 스케줄링, 잠금, 페이지 준비, I/O, 동기화 중 무엇인가?
5. **무엇을 확인했는가?** 호출 성공, 가시성, 영속성, 격리, 처리량 중 어떤 계약인가?

## 이 교재가 피하는 오해

- syscall 진입이 반드시 다른 프로세스로의 문맥 교환인 것은 아니다.
- page fault가 반드시 오류나 swap I/O인 것은 아니다.
- 가상 메모리 크기가 실제 RAM 사용량인 것은 아니다.
- 컨테이너의 root가 언제나 호스트 모든 권한을 갖는다고 보거나, 반대로 자동으로 완전히 안전하다고 보지 않는다.
- 비동기 I/O, direct I/O, 영속성은 서로 다른 축이다.
- 프로그램의 실행·준비·응답 성공·정전 내성은 따로 확인한다.

이 문장들을 외우는 것이 아니라 각 장의 작은 실행 순서와 예제로 왜 그런지 확인한다. 교육용 주소·시간표는 실제 커널 trace와 구별해 표시한다.

## 실습 환경과 범위

Python 3 표준 라이브러리와 작은 임시 파일 중심이다. Linux 전용 기능은 해당 장에 조건을 표시한다. 다른 사람의 프로세스 종료, kernel parameter 변경, mount·네트워크 구성 변경, 패키지 설치, eBPF 부착을 실습의 필수 조건으로 삼지 않는다.

정전 시험, 커널 빌드·부팅, 실제 서비스 장애 주입은 이 교재의 로컬 예제로 검증되지 않는다. 커널 내부 구현은 설치 버전과 다를 수 있으므로 학습 시 사용한 커널·도구 버전을 기록하고, API의 약속과 현재 구현을 나누어 읽는다.

## 통합 보강 검증 — 2026-09-22

[검증 기록](../../../learning/VALIDATION.md): 네 교재의 Python 본문 예제 22개 실행, 기존 I/O 테스트 12개, 1 MiB·16 MiB 실제 파일 실습, 상대 링크·표·코드 구문 검사 및 독립 기술 검토를 완료했다. 실제 장치 고장·분산 서비스 장애·eBPF 부착은 이 검증에 포함되지 않는다.
