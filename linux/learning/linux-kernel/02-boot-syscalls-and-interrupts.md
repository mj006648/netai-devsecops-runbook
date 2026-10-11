# 02. 부팅, 시스템콜, 인터럽트: 커널로 들어가는 문

이전: [운영체제는 왜 필요한가](00-why-operating-systems.md) · 다음: [스케줄링과 동시성](03-scheduling-and-concurrency.md)

보강·근거 확인일: **2026-09-22**. 이 장은 전원이 들어온 뒤 Linux가 어떻게 시작되고, 실행 중인 프로그램과 장치가 어떤 문으로 커널에 들어오는지 설명한다. CPU 아키텍처(명령과 레지스터의 기본 설계)마다 커널 진입 때 상태를 저장하는 트랩 프레임(trap frame), 처리 위치를 찾는 벡터 테이블(vector table), 높은 권한에서만 실행할 수 있는 명령이 다르다. 여기서는 공통 개념을 잡고 x86의 IDT(Interrupt Descriptor Table, 인터럽트 처리 위치 표) 같은 이름은 대표 예로만 쓴다.

### 왜 배우며, 어떤 단어부터 잡아야 하는가

컴퓨터가 켜지지 않거나 `read()`가 오래 걸릴 때는 “어느 문 앞에서 멈췄는가”를 찾아야 한다. 부팅과 실행 중 사건은 겉보기에는 달라도, 제어권이 누구에게 넘어가는지를 추적한다는 점에서 같다.

- **부팅(boot)**: 전원이 들어온 뒤 펌웨어·커널·첫 사용자 프로세스를 차례로 준비하는 과정이다.
- **시스템 호출(system call, syscall)**: 사용자 프로그램이 파일 읽기처럼 권한이 필요한 일을 커널에 요청하는 공식 입구다.
- **예외(exception)**: 현재 CPU 명령을 실행하다 생긴 사건이다. 0으로 나누기, 아직 준비되지 않은 메모리 접근 등이 예다.
- **인터럽트(interrupt)**: 장치 완료나 타이머처럼 현재 명령 흐름 바깥에서 CPU에 도착하는 알림이다.
- **사용자 모드/커널 모드(user/kernel mode)**: CPU가 허용하는 권한 수준이다. 모드 전환은 같은 스레드가 커널 코드를 실행하는 일이며, 다른 스레드로 바뀌는 **문맥 교환(context switch)**과는 다르다.
- **DMA(Direct Memory Access, 직접 메모리 접근)**: 장치가 CPU로 바이트 하나씩 복사시키지 않고 메모리와 데이터를 주고받는 기능이다.

```mermaid
flowchart TD
    A[사용자 스레드 실행] -->|syscall: 의도한 요청| K[커널 진입]
    A -->|exception: 현재 명령에서 사건| K
    DEV[장치·타이머] -->|interrupt: 바깥 알림| K
    K --> C{바로 끝낼 수 있는가?}
    C -->|예| R[원래 스레드로 복귀]
    C -->|아니요, 기다림 필요| B[스레드를 blocked로 표시]
    B --> S[스케줄러가 다른 runnable 스레드 실행]
    DEV -->|완료 알림| W[기다리던 스레드를 깨움]
    W --> S
```

그림의 핵심은 커널 진입과 문맥 교환이 같은 사건이 아니라는 점이다. 짧은 시스템 호출은 같은 스레드로 바로 돌아올 수 있고, I/O를 기다려야 할 때에야 그 스레드가 잠들고 다른 스레드가 실행될 수 있다.

## 1. reset에서 PID 1까지 한 줄 지도

서버가 켜지면 처음부터 Linux가 실행되는 것이 아니다. 매우 단순화하면 흐름은 다음과 같다.

~~~text
전원/리셋
  → CPU가 firmware의 초기 코드 실행
  → UEFI firmware가 하드웨어와 부팅 항목 준비
  → bootloader 또는 EFI stub가 Linux kernel image와 initramfs 로드
  → kernel decompression과 초기화
  → initramfs에서 early userspace 실행
  → 실제 root filesystem 발견·마운트
  → PID 1 실행
  → systemd 같은 init system이 서비스 시작
~~~

이 순서는 모든 장비에서 같은 파일명과 같은 화면으로 보인다는 뜻이 아니다. firmware 설정, Secure Boot, bootloader, initramfs 생성 도구, root filesystem 위치, 배포판 정책에 따라 달라진다. 그래도 “firmware → loader → kernel → early userspace → real root → PID 1”이라는 뼈대는 Linux 장애 분석에서 자주 반복된다.

## 2. UEFI는 운영체제 이전의 표준 실행 환경이다

**UEFI(Unified Extensible Firmware Interface)**는 운영체제가 시작되기 전 firmware와 OS loader가 상호작용하는 인터페이스를 정의한다. UEFI specification은 boot services와 runtime services, configuration table, image loading 같은 개념을 제공한다. boot services는 OS loader가 플랫폼을 조사하고 장치를 사용해 커널을 불러오는 동안 쓴다. OS loader가 충분히 준비되면 `ExitBootServices()`로 firmware의 boot services 소유권을 내려놓고 운영체제가 계속 진행한다.

**bootloader**는 커널 이미지를 메모리에 올리고, kernel command line과 initramfs 위치 같은 정보를 넘긴다. GRUB 같은 전통적 bootloader가 있을 수도 있고, Linux EFI stub를 통해 커널 이미지 자체가 UEFI application처럼 로드될 수도 있다.

## 3. initramfs는 진짜 root로 가기 위한 임시 작업장이다

**initramfs**는 kernel image와 함께 로드되는 초기 root filesystem 역할의 cpio archive다. kernel.org의 ramfs/rootfs/initramfs 문서는 initramfs가 boot 과정에서 압축 해제되어 early userspace를 제공한다고 설명한다.

왜 필요할까? 실제 root filesystem이 LUKS 암호화 볼륨, LVM, RAID, iSCSI, NVMe over Fabrics, 특정 driver module 뒤에 있을 수 있기 때문이다. 커널이 모든 환경을 처음부터 built-in으로 알 수 없으므로, initramfs가 필요한 module과 도구를 갖고 실제 root를 찾는다.

손으로 추적하면 다음과 같다.

~~~text
kernel: 내장 rootfs 위에 initramfs 압축 해제
kernel: /init 실행
/init: 필요한 module 로드, 장치 발견 대기, root device 찾기
/init: 실제 root filesystem을 /sysroot 같은 위치에 mount
/init: switch_root 또는 pivot_root 계열 절차로 실제 root로 이동
kernel/userspace: 새 root의 /sbin/init 또는 systemd가 PID 1 역할 수행
~~~

오개념: initramfs는 “작은 Linux 배포판”일 수 있지만 영구 운영 환경은 아니다. 보통 부팅을 완료하기 위한 임시 구조다.

## 4. PID 1은 첫 user space 프로세스이자 특별한 책임을 가진다

Linux가 user space로 넘어가면 처음 실행되는 일반 프로세스가 PID 1이다. 현대 배포판에서는 대개 systemd가 PID 1이다. PID 1은 서비스를 시작할 뿐 아니라 고아 프로세스 수거, shutdown 처리, service supervision 등 특별한 역할을 맡는다.

커널이 부팅에 성공했는데 root filesystem이 없거나 PID 1 실행에 실패하면 “커널은 살았지만 시스템은 usable state에 못 갔다”가 된다. 부팅 장애를 볼 때 kernel panic, initramfs shell, emergency target, normal multi-user target을 구분해야 한다.

## 5. 커널로 들어가는 세 문: syscall, exception, interrupt

실행 중인 CPU가 커널 코드로 들어오는 대표 경로는 세 가지다.

| 경로 | 누가 원인인가? | 예 | 동기/비동기 |
| --- | --- | --- | --- |
| system call | user program이 요청 | `read`, `write`, `mmap`, `clone` | 현재 instruction 흐름과 동기 |
| exception/fault/trap | CPU가 instruction 실행 중 발견 | page fault, divide by zero, breakpoint | 대체로 현재 instruction과 동기 |
| interrupt | 외부 장치나 timer가 알림 | NIC packet, NVMe completion, timer tick | 비동기 |

MIT xv6 교재는 trap을 system call, exception, device interrupt를 포괄하는 일반 용어로 사용한다. Linux와 특정 architecture 문서에서는 용어 경계가 더 세밀하다. 중요한 것은 “왜 들어왔는가”와 “돌아가면 같은 instruction을 재시도하는가”를 나누는 것이다.

## 6. 시스템콜은 함수 호출처럼 보이지만 privilege transition이다

사용자 프로그램은 kernel memory와 device register를 직접 만질 수 없다. 대신 syscall ABI에 맞춰 번호와 인자를 준비하고, architecture별 syscall instruction으로 커널 진입을 요청한다.

~~~text
user mode
  1. libc wrapper가 syscall 번호와 인자를 ABI에 맞게 배치
  2. CPU instruction이 privilege level을 kernel mode로 전환
  3. kernel entry code가 register/state를 저장하고 검증 가능한 형태로 정리
  4. syscall table을 통해 구현 함수로 dispatch
  5. copy_from_user/copy_to_user 등으로 user pointer를 조심해서 접근
  6. return value 또는 -errno를 준비
  7. user mode로 복귀
~~~

**privilege transition**과 **context switch**는 같은 말이 아니다. syscall은 같은 thread가 user mode에서 kernel mode로 들어갔다가 돌아올 수 있다. context switch는 CPU가 실행 중인 task 자체를 다른 task로 바꾸는 일이다. syscall 도중 blocking I/O를 만나면 scheduler가 다른 task로 context switch할 수 있지만, syscall이 곧 context switch라는 뜻은 아니다.

### 같은 `read()` 안에서 syscall과 interrupt가 만나는 지점

syscall과 interrupt를 표로만 나누면 둘이 실제 I/O에서 어떻게 이어지는지 놓치기 쉽다. NVMe에서 4KiB를 읽는 상황을 시간축에 놓아 보자. 숫자는 구조를 설명하기 위한 예이며 장치별 지연 보장은 아니다.

```mermaid
sequenceDiagram
    participant U as 사용자 thread
    participant K as 커널 syscall 경로
    participant D as NVMe 장치
    participant I as IRQ/completion 경로
    U->>K: read(fd, buf, 4096)
    K->>D: command 제출 + doorbell
    K->>K: thread를 wait queue에 두고 schedule
    Note over U,K: 다른 task가 CPU를 사용할 수 있음
    D->>D: storage에서 data 읽고 DMA
    D->>I: completion 기록 + interrupt
    I->>K: request 완료, waiter wakeup
    K-->>U: copy/완료 후 4096 반환
```

각 단계의 주체를 분리한다.

| 시점 | 주체 | 사건 | syscall인가, interrupt인가 |
|---:|---|---|---|
| t0 | 사용자 thread | `read()` wrapper가 번호·인자를 register에 둠 | syscall 준비 |
| t1 | 같은 thread | syscall instruction으로 kernel mode 진입 | 동기 syscall entry |
| t2 | kernel/driver | queue에 command를 쓰고 MMIO doorbell | syscall을 처리하는 kernel code |
| t3 | scheduler | 현재 thread가 data를 기다리며 sleep, 다른 task 실행 | 필요하면 context switch |
| t4 | NVMe | DMA로 지정 RAM buffer에 4KiB 기록 | CPU instruction 흐름 밖의 장치 동작 |
| t5 | 장치/CPU | 장치가 completion을 기록하고 IRQ 알림 | 비동기 interrupt entry |
| t6 | kernel | 완료 처리 후 wait queue의 thread를 runnable로 바꿈 | interrupt/deferred work |
| t7 | scheduler/thread | 다시 선택된 thread가 syscall의 남은 경로를 마치고 복귀 | syscall return |

예를 들어 t0부터 t7까지 120µs가 걸렸고 CPU가 이 thread의 kernel code를 실제로 실행한 합계가 8µs라면, 나머지 약 112µs는 전부 “CPU가 read 코드를 실행한 시간”이 아니다. 장치, queue, sleep, scheduler 대기가 섞여 있다. 그래서 `strace`의 syscall 경과 시간만 보고 커널이 120µs 동안 CPU를 계속 썼다고 해석하면 안 된다.

여기서 interrupt가 현재 `read()`를 호출한 바로 그 CPU에 들어온다고 보장되지 않는다. MSI-X affinity, queue 배치, polling 여부에 따라 다른 CPU가 completion을 처리하고 원래 thread를 깨울 수 있다. 또 빠른 장치와 polling 구성에서는 매 요청마다 interrupt를 받지 않을 수 있다. 반례로 page cache hit인 regular-file `read()`는 장치 command나 interrupt 없이 syscall 안에서 data를 복사해 바로 끝날 수 있다.

“syscall이면 동기, interrupt이면 비동기”라는 문장도 API 의미와 진입 원인을 섞는다. blocking `read()` API는 호출자 관점에서 동기지만 내부 완료는 비동기 interrupt로 올 수 있다. 반대로 timer interrupt가 깨운 thread가 나중에 실행되는 시점은 scheduler가 정한다. 원인을 찾을 때는 **누가 커널에 들어왔는가 → 현재 thread가 계속 실행 가능한가 → 완료를 누가 알려 주는가 → 어느 thread를 깨우는가** 순서로 본다.

## 7. fault와 interrupt를 헷갈리면 page fault를 오해한다

**page fault**는 이름에 fault가 들어가지만 항상 “오류”가 아니다. 사용자가 처음 만지는 anonymous page에 대해 커널이 demand-zero page를 할당하는 정상 경로일 수 있다. 파일을 `mmap()`한 뒤 처음 읽을 때 해당 file page를 page cache에서 가져오거나 디스크에서 읽는 경로일 수도 있다.

반면 장치 인터럽트(device interrupt)는 현재 실행 중인 사용자 명령과 직접 관계가 없을 수 있다. 네트워크 카드(NIC)가 패킷 수신을 알릴 때 CPU는 전혀 다른 프로세스를 실행 중일 수 있다. 커널은 인터럽트 처리기에서 최소한의 일만 하고 나머지는 뒤의 지연 처리 경로로 미룬다. 구체적인 방식의 뜻과 실행 주체는 10절에서 처음부터 나눈다.

## 8. vector table과 IDT는 “어디로 뛸지” 찾는 표다

CPU는 사건이 생겼을 때 임의의 커널 함수 이름을 문자열로 찾아가지 않는다. architecture는 사건 번호와 handler 주소를 연결하는 표를 둔다. x86에서는 **IDT(Interrupt Descriptor Table)**라는 개념이 대표적이다. 다른 architecture는 다른 이름과 구조를 쓴다.

핵심은 다음 세 가지다.

| 단계 | 하는 일 |
| --- | --- |
| hardware entry | CPU가 privilege, stack, 일부 register/state 전환 |
| low-level entry code | 커널이 나머지 상태 저장, C 코드가 다룰 형태로 정리 |
| high-level handler | syscall dispatch, page fault 처리, IRQ 처리 등 실제 판단 |

아키텍처 일반화의 함정은 여기서 생긴다. “IDT가 있다”는 x86 중심 표현이고, 모든 CPU가 IDT라는 이름을 쓰지 않는다. 하지만 “사건 번호에서 handler로 가는 공식 진입표가 있다”는 모델은 유용하다.

## 9. DMA, MMIO, driver queue는 장치 I/O의 기본 단어다

장치는 CPU가 byte를 하나씩 손으로 옮겨 주기만 기다리지 않는다.

| 용어 | 뜻 | 예 |
| --- | --- | --- |
| MMIO | device register를 memory address처럼 보이는 영역에 매핑 | NIC queue doorbell register에 쓰기 |
| DMA | device가 system memory와 직접 data transfer | NVMe가 read data를 RAM buffer에 채움 |
| descriptor ring/queue | driver와 device가 작업 항목을 주고받는 원형/큐 구조 | NIC RX/TX ring, NVMe submission/completion queue |
| interrupt/completion | device가 작업 완료나 새 data를 알림 | NVMe completion interrupt |

흐름은 보통 이렇다.

~~~text
driver가 DMA 가능한 buffer 준비
driver가 device queue에 descriptor 제출
driver가 MMIO register에 doorbell write
device가 DMA로 memory 읽기/쓰기
device가 completion queue에 결과 기록
device가 interrupt 발생
kernel interrupt path가 completion을 처리하고 대기 task를 깨움
~~~

DMA는 강력하지만 위험하다. 장치가 잘못된 주소에 DMA하면 커널이나 다른 프로세스 메모리를 망가뜨릴 수 있다. **IOMMU(Input-Output Memory Management Unit, 입출력 주소 변환 장치)**는 장치가 사용하는 주소를 실제 메모리 주소로 변환하고 접근 범위를 제한한다. **DMA 매핑(mapping)**은 드라이버가 “이 버퍼를 이 방향의 장치 전송에 사용한다”고 커널에 등록해 장치가 쓸 주소와 일관성 규칙을 얻는 과정이다. CPU 포인터 값을 그대로 장치에 넘긴다는 뜻이 아니다.

## 10. 인터럽트 일을 “즉시”와 “나중”으로 나누는 이유

장치 인터럽트가 들어온 순간의 **하드 IRQ 문맥(hard IRQ context)**에서는 현재 실행 중이던 코드가 중단돼 있다. 여기서 오래 머물면 같은 CPU의 다른 작업과 추가 인터럽트 처리가 늦어진다. 반면 장치가 보낸 원인을 확인하거나 인터럽트를 확인했다는 **acknowledge(ack, 수신 확인)**를 하지 않으면 장치가 계속 알림을 보내거나 다음 작업을 진행하지 못할 수 있다. 그래서 꼭 필요한 일만 즉시 처리하고, 오래 걸릴 일은 나중 실행 경로로 넘긴다.

전통적으로 즉시 처리 부분을 **top half(상반부)**, 미룬 부분을 **bottom half(하반부)**라고 부른다. 이는 설계 개념이고, 현재 Linux의 구체적인 실행 수단은 다음처럼 나뉜다.

| 실행 방식 | 누가 실행하는가 | 잠들 수 있는가 | 대표 역할 |
| --- | --- | --- | --- |
| hard IRQ handler(하드 인터럽트 처리기) | 인터럽트가 끊어 들어온 CPU가 즉시 실행 | 아니요 | 원인 확인, 장치 ack, 완료 정보 최소 수거, 후속 작업 예약 |
| softirq(소프트 인터럽트) | 커널의 지연 처리 경로가 CPU별로 실행 | 일반적으로 잠드는 코드를 쓰지 않음 | 네트워크 수신처럼 양이 많고 빠른 후속 처리 |
| workqueue(작업 대기열) | 커널 워커 스레드가 스케줄되어 실행 | 예 | 잠금 대기나 메모리 할당처럼 sleep 가능한 후속 작업 |
| threaded IRQ(스레드형 인터럽트) | 해당 인터럽트용 커널 스레드가 실행 | 예 | 긴 장치 처리를 스케줄 가능한 문맥으로 이동 |

여기서 **문맥(context)**은 “지금 어떤 실행 규칙과 권한 아래에서 코드가 도는가”를 뜻한다. 하드 IRQ 문맥은 일반 프로세스 문맥과 달리 잠들 수 없고, workqueue와 threaded IRQ는 커널 스레드 문맥이라 스케줄러가 다룰 수 있다.

사건 흐름은 `장치 인터럽트 → hard IRQ에서 원인 확인·ack → softirq/workqueue/threaded IRQ 중 알맞은 경로 예약 → 미룬 작업 수행 → 기다리던 task 깨움`으로 읽는다. 모든 드라이버가 모든 단계를 쓰는 것은 아니다.

**PREEMPT_RT(실시간 선점 설정)**는 커널의 긴 비선점 구간을 줄여 최악 지연을 낮추려는 구성이다. 이 구성에서는 많은 인터럽트 처리가 스레드화되고 softirq 실행 방식도 일반 커널과 달라질 수 있다. 따라서 “softirq는 언제나 선점 불가”처럼 설정을 무시한 문장은 피한다. kernel.org generic IRQ 문서는 드라이버가 `request_threaded_irq()`로 인터럽트와 스레드 처리 함수를 등록하는 방식을 설명한다.

## 11. 손으로 추적하는 예: `read()`가 blocking 되는 순간

프로그램이 pipe에서 읽는데 아직 data가 없다고 하자.

~~~text
1. user program이 read(fd, buf, 4096) 호출
2. libc wrapper가 read syscall 진입
3. kernel이 fd table에서 file object를 찾음
4. pipe buffer가 비어 있음을 확인
5. nonblocking이 아니므로 현재 task state를 sleeping 계열로 바꾸고 wait queue에 등록
6. scheduler가 다른 runnable task로 context switch
7. 다른 task가 pipe에 write
8. kernel이 wait queue의 reader를 wake up
9. reader가 다시 runnable이 되고 scheduler가 선택하면 read syscall 계속 진행
10. data를 user buffer로 copy하고 user mode로 return
~~~

이 예에서 syscall 진입은 privilege transition이고, 6단계에서 실제 context switch가 일어난다. 두 사건을 분리해야 perf trace, strace, scheduler latency를 해석할 수 있다.

## 12. 안전한 관찰 실습

아래 명령은 host 설정을 바꾸지 않고 현재 shell에서 시스템콜이 user/kernel 경계를 지난다는 감각만 확인한다. `strace`가 없는 환경도 있으므로 필수 실습은 Python 표준 라이브러리만 쓴다.

~~~bash
python3 - <<'PY'
import os
r, w = os.pipe()
os.write(w, b"kernel boundary\n")
print(os.read(r, 1024).decode().strip())
os.close(r)
os.close(w)
PY
~~~

해석: Python 함수처럼 보이지만 `os.pipe`, `os.write`, `os.read`, `os.close`는 내부에서 운영체제 서비스를 요청한다. 출력 문자열 자체보다 중요한 것은 “파일 디스크립터라는 정수 핸들을 통해 커널 객체를 다룬다”는 점이다.

## 13. UEFI에서 PID 1까지: 소유권이 바뀌는 지점을 시간표로 읽기

부팅은 “파일을 차례로 실행한다”보다 “다음 단계가 실행에 필요한 메모리와 장치를 준비하고 제어권을 넘긴다”로 이해해야 한다.

| 단계 | 주 실행 주체 | 준비하는 객체·상태 | 실패하면 보이는 범위 |
|---|---|---|---|
| reset | CPU와 platform firmware | 초기 실행 주소, 기본 CPU·memory·chipset 상태 | 화면·serial log조차 없을 수 있음 |
| UEFI boot manager | firmware | boot entry, device path, UEFI image | firmware 화면 또는 boot entry 오류 |
| OS loader/EFI stub | loader | kernel image, initramfs, command line, memory map | loader 메시지 또는 즉시 reboot |
| `ExitBootServices()` 이후 | kernel이 platform 운영 책임 인수 | page table, interrupt, allocator, driver 초기화 | early console/kernel log |
| initramfs early userspace | `/init` 등 PID 1 | storage/network/crypto module, real root 발견·mount | emergency shell, root 찾기 실패 |
| real root의 init system | systemd 등 | mount, device, service dependency graph | rescue target, failed unit |

UEFI의 **Boot Services**는 loader가 device를 찾고 image와 memory를 준비할 때 쓰는 firmware 기능이다. loader는 `GetMemoryMap()`으로 현재 memory map과 key를 얻고 `ExitBootServices()`를 성공시키면 boot service를 더 사용할 수 없다. 그 시점부터 OS loader/kernel이 사용 가능한 platform resource의 관리 책임을 맡는다. UEFI **Runtime Services** 일부는 이후에도 남을 수 있으므로 “firmware가 완전히 사라진다”는 표현도 정확하지 않다.

kernel image가 실행되면 압축 해제, architecture별 초기화, memory allocator, interrupt, scheduler, driver/subsystem init이 이어진다. 이 목록의 실제 순서는 architecture와 build configuration에 따라 달라진다. kernel command line의 `root=`가 있다고 바로 storage를 읽을 수 있는 것도 아니다. root device에 접근할 controller driver, filesystem driver, 암호화/LVM/network 준비가 먼저 필요할 수 있다.

**initramfs**는 kernel이 초기 rootfs에 풀어 놓는 cpio archive 기반 early userspace다. `/init`가 있으면 PID 1로 실행되어 필요한 module을 올리고 real root를 mount한 뒤 `switch_root` 같은 절차로 새 root의 init을 실행할 수 있다. 예전 initrd와 initramfs는 구현 모델이 다르므로 이름을 아무 조건 없이 바꿔 쓰지 않는다.

real root 전환은 directory 문자열 하나를 바꾸는 일이 아니다. process의 current working directory, root directory, 열린 fd, 실행 파일과 mount reference가 old root를 계속 붙들 수 있다. old root를 해제하려면 남은 reference를 정리해야 한다. 부팅 장애에서 “root mount 성공”과 “real root의 init exec 성공”을 별도 단계로 보는 이유다.

## 14. 시스템 호출 한 번: CPU register에서 kernel object까지

user program이 `read(fd, buf, 4096)`를 호출하면 대개 libc wrapper가 architecture의 syscall 규약에 맞춰 syscall number와 argument를 register에 놓고 전용 instruction을 실행한다. x86-64라면 `syscall`, AArch64라면 `svc`처럼 instruction 이름과 register 배치는 다르다. 이 장에서는 공통 구조를 따른다.

```text
user mode
  1. syscall number = read, args = fd/buffer/count를 약속된 register에 배치
  2. syscall-entry instruction 실행
CPU/entry code
  3. 더 높은 privilege에서 지정된 kernel entry로 제어 이동
  4. user instruction pointer, stack, flags와 register state를 보존
kernel
  5. syscall number 범위 검사와 handler dispatch
  6. fd table에서 fd가 가리키는 file object lookup
  7. user buffer range와 access를 검증하며 filesystem/device 경로 수행
  8. 즉시 data가 없으면 current task를 wait queue에 두고 schedule 가능
  9. 완료 후 return value 또는 -errno 준비
return path
 10. pending signal, reschedule, tracing 같은 work 확인
 11. user register/privilege 상태 복원 후 다음 user instruction으로 복귀
```

**trap frame**은 kernel entry에서 중단된 실행을 복원하기 위해 보존한 register 상태를 가리키는 교육적 이름이다. Linux 내부의 실제 구조체 이름과 저장 위치는 architecture와 entry path에 따라 다르다. syscall instruction 하나가 모든 register를 자동으로 완전 저장한다고 일반화해서는 안 된다. 일부 상태는 hardware가, 나머지는 assembly entry code가 저장한다.

`read()`의 `buf`는 user virtual address다. kernel이 pointer 숫자를 믿고 직접 쓰는 것이 아니라 해당 process의 address space에서 접근 가능한지 확인하고 user-copy helper를 사용한다. 검증 뒤 mapping이 바뀌거나 page fault가 날 수 있으므로 안전한 copy primitive와 fault 처리 규칙이 필요하다. 잘못된 pointer는 보통 `EFAULT`로 끝날 수 있으며 kernel 자체가 임의 user pointer 때문에 무너지지 않도록 경계를 만든다.

`read()`가 disk I/O를 제출하고 기다리면 같은 syscall의 task가 blocked되고 scheduler가 다른 task를 선택한다. 나중에 device completion이 waiter를 runnable로 만들고, 다시 선택된 task가 kernel read 경로를 마친 뒤 user mode로 돌아온다. syscall entry, context switch, interrupt는 한 요청에서 모두 나타날 수 있지만 서로 같은 사건은 아니다.

## 15. exception, fault, trap과 signal 전달을 한 줄로 섞지 않기

CPU architecture 문서에서 **exception**은 현재 instruction 실행과 동기적으로 생긴 control transfer의 큰 범주다. **fault**는 원인을 처리한 뒤 같은 instruction을 재시도할 수 있는 유형을 가리키는 경우가 많고, page fault가 대표 예다. **trap**이라는 단어는 architecture와 교재에 따라 exception 전체 또는 특정 종류를 가리켜 사용 범위가 다르다. Linux의 signal은 user process에 사건을 전달하는 OS 수준 메커니즘이다.

가상 주소에 처음 쓰는 demand-zero 사례를 추적한다.

```text
1. user store instruction이 non-present PTE를 만남
2. CPU가 page-fault exception으로 kernel entry에 이동하고 fault address/reason을 제공
3. kernel이 VMA와 write permission을 검사
4. 합법적 anonymous mapping이면 zeroed page를 할당하고 PTE를 설정
5. exception return 뒤 같은 user store를 재시도
6. 두 번째 시도는 성공
```

반대로 주소가 VMA 밖이면 kernel은 정상 mapping을 만들 수 없다. 해당 task에 `SIGSEGV`를 pending시켜 user return 경로에서 default action 또는 handler로 전달할 수 있다. “CPU가 SIGSEGV를 발생시킨다”라고만 말하면 page-fault exception 처리와 Linux signal 정책을 한 단계로 합쳐 버린다.

## 16. hard IRQ, threaded IRQ, softirq, workqueue의 실행 문맥

장치 완료 interrupt가 오면 CPU는 현재 실행을 잠시 중단하고 kernel interrupt entry로 들어간다. **hard IRQ handler**는 빠르게 장치 상태를 확인하고 interrupt 원인을 acknowledge하며, 긴 일을 뒤로 미뤄야 한다. hard IRQ context에서는 일반적인 blocking sleep을 할 수 없다. 어떤 task의 syscall을 대신 수행하는 문맥이 아니기 때문이다.

미룬 일을 어디서 실행할지는 요구에 따라 달라진다.

| 문맥 | 무엇인가 | sleep 가능한가 | 대표 용도와 제약 |
|---|---|---|---|
| hard IRQ | hardware interrupt의 즉시 처리 | 아니오 | 장치 상태 확인, 최소한의 acknowledge와 후속 work 예약 |
| threaded IRQ | IRQ 처리를 kernel thread 문맥으로 옮긴 부분 | 가능 조건 존재 | 시간이 더 걸리거나 RT latency를 조절할 handler |
| softirq/BH | interrupt 뒤 수행하는 per-CPU deferred context | 일반 blocking sleep 불가 | network receive, timer 등 높은 빈도의 후속 처리 |
| workqueue | work item을 kworker thread가 실행 | 가능 | sleep이 필요하거나 process context에서 할 비동기 작업 |

**softirq**는 단순히 “software가 발생시킨 interrupt”라는 일상 문장보다 좁은 Linux deferred-work 메커니즘이다. 같은 종류가 여러 CPU에서 동시에 실행될 수 있어 공유 자료구조 동기화가 필요하다. 과부하에서는 `ksoftirqd` kernel thread가 처리할 수 있지만, 이 사실만으로 softirq code 안에서 마음대로 sleep해도 된다는 뜻은 아니다.

**workqueue**는 function을 나타내는 work item을 queue에 넣고 worker thread가 나중에 실행하는 framework다. threaded workqueue는 task context를 제공해 sleep 가능한 작업에 적합할 수 있다. 그러나 queue 지연, worker concurrency, flush/cancel과 object lifetime을 설계해야 한다. 이미 해제한 device object를 가리키는 work item이 뒤늦게 실행되면 use-after-free가 된다.

NVMe read의 단순화한 시간표는 다음과 같다.

| 시각 | CPU/task | 장치·kernel 상태 |
|---:|---|---|
| t0 | application이 `read()` syscall | buffer와 I/O request 준비 |
| t1 | request task가 blocked | NVMe queue에 command, DMA mapping 설정 |
| t2 | CPU는 다른 task 실행 | controller가 storage 작업과 DMA 수행 |
| t3 | hard IRQ 진입 | completion 존재 확인, 후속 처리 예약 |
| t4 | IRQ/softirq 또는 driver completion path | request 완료, waiter wake-up |
| t5 | scheduler가 원 task 선택 | read가 return value를 준비해 user mode 복귀 |

data 4KiB가 interrupt 안에 실려 오는 것은 아니다. DMA로 지정 memory에 전송되고 completion은 그 작업의 상태를 알린다. IOMMU mapping과 cache coherency 규칙은 architecture/device 조건에 따라 추가된다.

## 17. 최신 kernel의 실시간성 연구·개발을 읽는 경계

PREEMPT_RT는 Linux kernel의 많은 code path를 더 선점 가능하게 만들고 interrupt 처리와 lock 동작을 바꿔 worst-case latency를 줄이려는 실시간 kernel 작업이다. 최신 mainline에 관련 기능이 통합됐다는 소식은 “모든 일반 Linux workload가 자동으로 hard real-time deadline을 보장한다”는 뜻이 아니다. kernel configuration, driver의 non-preemptible 구간, firmware, SMI, hardware, workload admission과 측정 방법이 여전히 중요하다.

이 주제를 syscall/interrupt 장과 연결하는 이유는 latency의 합이 여러 문맥에서 나오기 때문이다.

```text
응답 지연 = syscall 경로
          + lock 대기
          + IRQ가 막힌 구간
          + hard/threaded IRQ 처리
          + softirq/workqueue queue 대기
          + scheduler가 원 task를 다시 고르는 시간
```

평균 latency만 줄었다고 최대 지연이 보장되는 것도 아니다. 연구나 benchmark를 읽을 때 kernel version/config, CPU isolation, interrupt affinity, device와 측정한 percentile 또는 maximum을 반드시 같이 기록한다.

## 18. 오개념 정리

| 오개념 | 바로잡기 |
| --- | --- |
| 부팅은 BIOS/UEFI가 Linux를 끝까지 실행하는 일이다 | firmware는 loader와 초기 환경을 제공하고, 어느 시점부터 kernel이 플랫폼을 소유한다. |
| syscall은 항상 context switch다 | 같은 task가 kernel mode로 들어갔다 돌아올 수 있다. blocking이나 preemption이 있어야 다른 task로 바뀐다. |
| page fault는 항상 crash다 | demand paging, COW, mmap 로딩의 정상 경로일 수 있다. |
| interrupt handler에서 오래 일해도 된다 | 긴 작업은 보통 미뤄야 latency와 interrupt masking을 줄인다. |
| DMA는 CPU보다 안전하다 | 잘못된 DMA는 더 위험할 수 있어 IOMMU와 mapping 규칙이 필요하다. |

## 19. 해설 문제

1. `open()` syscall 중 disk I/O가 항상 발생하는가?
   - 아니다. pathname lookup이 dcache/inode cache에서 해결될 수 있다. 권한 검사와 file object 생성은 필요하지만 data block read가 항상 필요한 것은 아니다.

2. timer interrupt가 왜 time-sharing에 필요한가?
   - 실행 중인 task가 자발적으로 CPU를 내놓지 않아도 kernel이 주기적으로 제어권을 회복해 scheduler를 실행할 수 있기 때문이다.

3. NVMe read에서 completion interrupt가 오면 data는 interrupt payload 안에 들어오는가?
   - 보통 아니다. data는 DMA로 memory buffer에 들어가고, interrupt/completion은 작업 완료와 상태를 알린다.

4. UEFI loader가 `ExitBootServices()`에 성공한 뒤 boot service로 disk를 계속 읽어도 되는가?
   - 안 된다. 성공 뒤 boot services는 종료되고 loader/kernel이 platform resource 운영 책임을 맡는다. 일부 runtime service가 남는 것과 boot service 사용은 구분한다.

5. initramfs에서 real root를 mount했는데 old root를 unmount하지 못한다. 어떤 reference를 의심하는가?
   - old root 안을 current directory나 root directory로 가진 process, 열린 fd, 실행 파일·library와 mount reference를 확인한다. mount 성공과 old root reference 정리는 별도 단계다.

6. `read()`가 호출될 때마다 다른 process로 context switch되는가?
   - 아니다. data가 즉시 준비되고 선점 이유가 없으면 같은 task가 user→kernel→user mode로 다녀올 수 있다. I/O 대기나 scheduling 결정이 생길 때 다른 task로 바뀔 수 있다.

7. 합법적인 anonymous 주소의 첫 write가 page fault를 냈다. 왜 crash하지 않는가?
   - kernel이 VMA와 권한을 확인한 뒤 zeroed physical page를 매핑하고 instruction을 재시도할 수 있기 때문이다. VMA 밖이거나 권한이 없으면 signal 경로가 될 수 있다.

8. hard IRQ handler에서 mutex로 기다려도 되는가?
   - 일반 mutex처럼 sleep이 필요한 primitive는 hard IRQ context에 맞지 않는다. handler는 짧게 처리하고 요구에 따라 threaded IRQ, softirq, workqueue로 미룬다. 정확한 primitive는 접근 문맥과 kernel API 규칙으로 결정한다.

9. workqueue로 옮기면 object lifetime 문제도 자동 해결되는가?
   - 아니다. work item이 실행될 때까지 대상 object가 살아 있어야 하고 cancel/flush와 teardown 순서를 설계해야 한다. 비동기 실행 문맥만 제공할 뿐 수명을 자동 소유하지 않는다.

## 20. 1차 참고 자료

- UEFI Forum: [UEFI Specification 2.10 Boot Services](https://uefi.org/specs/UEFI/2.10/07_Services_Boot_Services.html), [UEFI Overview](https://uefi.org/specs/UEFI/2.10/02_Overview.html)
- Linux Kernel Documentation: [Ramfs, rootfs and initramfs](https://docs.kernel.org/filesystems/ramfs-rootfs-initramfs.html), [Generic IRQ handling](https://docs.kernel.org/core-api/genericirq.html), [Real-time differences](https://docs.kernel.org/core-api/real-time/differences.html)
- Linux Kernel Documentation: [Workqueue](https://docs.kernel.org/core-api/workqueue.html), [PREEMPT_RT theory](https://docs.kernel.org/core-api/real-time/theory.html), [No working init found](https://docs.kernel.org/admin-guide/init.html)
- Linux man-pages: [syscalls(2)](https://man7.org/linux/man-pages/man2/syscalls.2.html), [syscall(2)](https://man7.org/linux/man-pages/man2/syscall.2.html)
- MIT PDOS xv6 book: [Traps and system calls](https://mit-pdos.github.io/xv6-riscv-book/trap.html)
