# 16. 종합 문제, 연결 개념과 공식 출처

[이전: 15. 안전한 로컬 모형 실습](15-safe-local-model-labs.md) · [목차](README.md)

Linux 용어는 따로 떨어진 낱말이 아니다. 전원이 켜진 뒤 kernel이 memory와 device를 준비하고 PID 1이 service를 시작하며, process의 thread가 virtual address를 사용하고 system call로 I/O와 network를 요청한다. cgroup은 이 process 집합의 자원을 세고 제한하고, container는 namespace와 cgroup을 조합해 서로 다른 관점을 만든다. 문제가 생기면 이 객체들의 수명과 상태 전이를 같은 시간축에서 읽는다.

~~~mermaid
flowchart LR
    B["boot: firmware→kernel→PID 1"] --> P["process·thread"]
    P --> M["virtual memory·page fault"]
    P --> C["cgroup accounting·limits"]
    P --> I["VFS→filesystem→block/device"]
    I --> U["io_uring SQE→CQE"]
    P --> N["socket→network stack→NIC"]
    C --> K["container·Kubernetes workload"]
    M --> E["측정·가설·재현 연구"]
    I --> E
    N --> E
    K --> E
~~~

## 1. boot가 실행 환경을 만든다

**boot** 는 전원 인가 뒤 운영체제가 사용자 프로그램을 실행할 수 있는 상태가 되는 과정이다. firmware는 hardware 초기화와 boot 항목 선택을 담당한다. UEFI 환경의 boot loader는 Linux kernel image와 필요한 설정을 memory에 올려 kernel entry로 제어를 넘긴다.

kernel은 CPU, physical memory, interrupt, scheduler와 driver를 초기화한다. **initramfs** 는 root filesystem을 바로 사용할 수 없을 때 초기 user space 도구와 driver를 제공하는 memory 기반 임시 filesystem이다. 암호화·RAID·network root를 준비한 뒤 실제 root filesystem으로 전환할 수 있다.

kernel이 첫 user-space process를 시작하면 그 process는 PID 1을 갖는다. Ubuntu의 일반 구성에서는 systemd가 PID 1로 service와 mount, device 관련 **unit** 의 의존 관계를 관리한다. unit은 kernel 객체가 아니라 systemd가 읽고 상태를 추적하는 관리 객체다. service unit은 process 수명, slice unit은 resource hierarchy, scope unit은 systemd 밖에서 만들어진 process 집합을 관리하는 데 쓰인다.

boot가 느리다는 증상은 firmware, kernel driver, initramfs, mount, network-online, service 시작 중 어디에서 시간을 썼는지 나눠야 한다. 전체 wall time 하나로 특정 service를 원인이라 할 수 없다.

## 2. process와 thread의 탄생과 종료

**program** 은 저장장치에 있는 executable code와 data다. **process** 는 그 program이 실행되며 생긴 주소 공간, credential, file descriptor, signal 상태 같은 kernel 관리 객체의 묶음이다. **thread** 는 process 안에서 scheduler가 CPU 실행 대상으로 다루는 흐름이다. 여러 thread는 주소 공간과 file descriptor를 공유하지만 각자 register, stack, scheduling state를 가진다.

process가 fork/clone 계열 system call로 child를 만들고 exec 계열 호출로 새 program image를 적재할 수 있다. parent가 종료 status를 wait로 회수하기 전 종료 child는 zombie 상태로 남을 수 있다. zombie는 CPU를 쓰는 실행 process가 아니지만 PID와 종료 정보를 보관한다.

scheduler는 runnable thread를 CPU에 배정한다. **run queue** 는 실행 가능하지만 CPU 차례를 기다리는 task 집합이다. **context switch** 는 CPU register와 실행 문맥을 다른 thread로 바꾸는 사건이다. context switch가 많다는 값만으로 문제라고 할 수 없다. 짧은 I/O와 많은 thread가 정상적으로 높은 수를 만들 수 있으며 cache locality와 실제 latency를 함께 본다.

## 3. CPU time과 wall time을 연결한다

thread가 user code를 실행한 누적 시간은 user CPU time, system call과 page fault 처리처럼 kernel code를 실행한 누적 시간은 system CPU time으로 계측할 수 있다. wall time은 monotonic clock에서 시작과 끝의 차이다.

4개 thread가 각각 1초 동안 한 core를 완전히 쓰면 process CPU time은 약4초, wall은 약1초일 수 있다. 반대로 wall10초에 CPU0.5초라면 나머지9.5초가 모두 disk I/O라는 뜻은 아니다. sleep, futex lock, network, scheduler delay, cgroup throttling, page fault가 포함될 수 있다.

CPU **affinity** 는 thread가 실행할 수 있는 CPU 집합을 제한한다. host에 idle core가 있어도 affinity 밖이면 사용할 수 없다. cgroup quota도 별도 상한이다. host 사용률, affinity, cgroup cpu.max와 cpu.stat, per-thread state를 같은 범위에서 본다.

## 4. virtual memory와 page

process가 사용하는 pointer 값은 보통 **virtual address** 다. CPU의 memory-management unit과 kernel page table은 virtual page를 physical frame 또는 다른 backing 상태에 연결한다. process마다 주소 공간 관점이 달라 같은 virtual address가 다른 physical memory를 가리킬 수 있다.

**page fault** 는 현재 page-table 상태만으로 memory 접근을 완료할 수 없어 kernel 처리가 필요한 사건이다. minor fault는 필요한 page가 memory에 있어 storage I/O 없이 mapping을 만들 수 있고, major fault는 file이나 swap에서 읽는 I/O가 필요할 수 있다. 이름의 major/minor가 오류의 심각도를 뜻하지 않는다.

**anonymous memory** 는 heap, stack처럼 file content를 직접 backing으로 삼지 않는 page다. **page cache** 는 file content를 memory page에 두어 반복 read를 빠르게 한다. clean file page는 storage 원본과 같아 회수 뒤 다시 읽을 수 있다. dirty page는 memory에서 바뀌어 writeback이 필요하다.

**reclaim** 은 다른 allocation에 쓸 page를 확보하는 과정이다. clean cache를 drop하거나 dirty를 writeback하고, 설정에 따라 anonymous를 swap할 수 있다. 회수한 file page가 곧 다시 필요해지는 **refault** 가 반복되면 I/O와 stall이 커진다. free memory 하나만 보지 않고 workingset, refault, PSI를 본다.

## 5. cgroup은 process 집합의 자원 경계다

cgroup v2 core는 process를 하나의 hierarchy로 조직하고 controller가 CPU, memory, I/O 같은 자원을 계측·분배한다. 모든 process는 한 cgroup에 속하며 child의 제한은 ancestor 제한을 벗어나지 못한다.

CPU quota50,000µs/period100,000µs는 cgroup 전체 평균0.5 CPU 상한이다. **cpu.weight** 는 경쟁할 때의 상대 배분 비중이고 idle CPU가 충분하면 hard cap처럼 남는 CPU를 막지 않는다. quota와 weight는 다른 기작이다.

memory.current는 현재 charge gauge, memory.high는 reclaim과 throttling을 유도하는 경계, memory.max는 hard limit 성격의 경계다. memory.events는 high,max,oom,oom_kill 같은 누적 사건을 보여 준다. current<max라도 high 초과나 node pressure로 stall할 수 있다.

controller는 parent의 cgroup.subtree_control에서 child에 활성화한다. domain controller를 child에 분배하는 parent에는 no-internal-process constraint가 적용된다. **delegation** 은 subtree 조직 권한을 넘기되 parent가 정한 resource 제한을 벗어나지 못하게 하는 경계다. file permission 몇 개를 모두 넘기는 행위와 같지 않다.

## 6. PSI는 자원 부족이 만든 stall을 본다

Pressure Stall Information은 CPU, memory, I/O 경쟁이 task 생산성을 막은 시간을 /proc/pressure와 cgroup pressure file에 내보낸다. some은 적어도 일부 task가 stall된 시간 비중, full은 모든 non-idle task가 동시에 stall된 시간 비중이다.

avg10,avg60,avg300은 최근 경향의 백분율이고 total은 microsecond 누적값이다. total 두 시점 차이는 custom 관찰 창의 stall 증가를 계산하는 데 쓸 수 있다. avg10=20을 20ms latency로 읽지 않는다. PSI가 높다고 어느 device나 어느 allocation이 원인인지 자동으로 정해지지 않으므로 다음 계층 지표와 연결한다.

OOM kill은 pressure의 가능한 결과 중 하나다. reclaim stall이 길어도 kill이 없을 수 있고, 갑작스러운 큰 charge 실패로 긴 PSI 없이 cgroup OOM이 날 수도 있다. memory.events와 node log, current/high/max, PSI를 함께 본다.

## 7. file I/O가 지나가는 계층

process는 read/write system call이나 memory mapping으로 file을 다룬다. **VFS(Virtual File System)** 는 서로 다른 filesystem에 공통 file·inode·directory interface를 제공하는 kernel 층이다. ext4, XFS 같은 filesystem은 logical file offset을 block mapping과 metadata로 연결한다.

page cache hit이면 device I/O 없이 read가 끝날 수 있다. miss나 direct I/O는 block layer와 driver를 거쳐 storage device에 request를 보낼 수 있다. write는 page cache dirty 상태에서 나중 writeback되거나 동기화 요청의 경계까지 기다릴 수 있다.

**IOPS** 는 초당 operation 수, **throughput** 은 초당 byte, **latency** 는 한 operation의 제출부터 완료까지 시간이다. 작은 random I/O와 큰 sequential I/O는 같은 byte에서도 IOPS 요구가 다르다. queue depth를 늘리면 device parallelism과 throughput이 오를 수 있지만 service capacity보다 제출이 빠르면 pending과 tail latency가 커진다.

iowait는 per-process 정확한 disk wait 시간이 아니다. /proc/stat의 CPU accounting 문맥과 한계를 확인한다. process wall-CPU 차이를 그대로 iowait로 부르지 않는다.

## 8. io_uring의 요청과 completion

io_uring은 user space와 kernel이 shared ring 구조를 통해 비동기 I/O 요청과 완료를 교환하는 Linux interface다. SQ는 submission queue, SQE는 opcode, file, offset, buffer, user_data 등을 담는 요청 entry다. CQ는 completion queue, CQE는 user_data와 result를 담는 완료 entry다.

**비동기** 는 submit 함수가 I/O 완료 전에 반환될 수 있다는 뜻이다. 성공 여부와 byte 수는 나중 CQE에서 확인한다. SQE101 뒤102를 제출해도102가 먼저 끝날 수 있다. user_data로 pending request를 찾아야 한다.

buffer는 matching terminal completion까지 유효해야 한다. 먼저 free하거나 container 재할당으로 주소가 바뀌면 use-after-free가 된다. CQE result가 음수면 -errno 실패, 양수면 opcode별 byte 결과일 수 있다. read result0은 EOF, 요청4096에1200은 short read 성공일 수 있다.

cancel도 별도 request이며 대상 완료와 race한다. cancel CQE 하나만 보고 대상 buffer를 해제하지 않고 대상 state machine의 terminal 경로 하나가 final release를 소유하게 한다. io_uring setup이 EPERM이면 seccomp·policy·disabled 상태, EINVAL이면 flag·argument·opcode 지원, ENOSYS이면 syscall 경로를 구분한다.

## 9. network가 file I/O와 다른 대기 경로를 만든다

**socket** 은 process가 network endpoint와 byte/message를 주고받는 file-descriptor 형태의 kernel 객체다. TCP send는 application buffer에서 kernel socket buffer로 복사된 뒤 packet으로 나가며, send 호출 성공이 상대 application 처리 완료를 뜻하지 않는다. receive도 packet 도착, kernel queue, application read가 다른 경계다.

NIC는 network interface controller다. packet은 qdisc, driver ring, hardware queue를 거칠 수 있다. latency 증가는 DNS, connect, TLS, retransmission, receiver 처리, network queue 어디에서나 생긴다. local process가 D state라고 해서 항상 block storage만 기다리는 것도 아니다. kernel stack과 socket 지표를 구분한다.

TCP retransmission 증가는 loss 또는 심한 reordering 가설을 강화하지만 application latency의 유일 원인은 아니다. throughput, RTT, send/receive queue, drop, remote endpoint 상태를 같은 connection 신원과 시간으로 맞춘다.

## 10. container는 작은 VM이라는 한 문장으로 끝나지 않는다

container process도 host Linux kernel의 일반 process다. **namespace** 는 PID, mount, network, user 같은 자원 이름과 관점을 격리한다. cgroup은 resource accounting과 제한을 제공한다. filesystem image와 overlay mount는 root 경로 관점을 구성한다. security capability, seccomp와 LSM은 허용 operation을 제한한다.

container 안 PID1과 host PID는 다를 수 있고 /proc가 namespace 관점을 보여 줄 수 있다. cgroup path도 namespace root에서 상대적으로 보일 수 있다. 문제 해결 때 host와 container 어느 관점의 PID·mount·network·cgroup인지 적는다.

Kubernetes Pod는 하나 이상의 container가 network namespace 같은 일부 자원을 공유하도록 배치하는 API 객체다. kubelet과 container runtime이 host process와 cgroup을 만든다. request/limit은 scheduler와 runtime resource 설정으로 이어지지만 제품 version과 QoS 조건을 확인해야 한다. Pod가 Pending, container가 waiting, process가 runnable/throttled인 상태는 서로 다른 층이다.

readiness probe는 traffic을 받을 준비가 되었는지 판정하고, liveness probe는 반복 실패 시 container restart 같은 복구를 유도한다. 느린 storage 때문에 liveness가 실패하면 restart가 원인을 없애지 않고 cache와 recovery 비용을 더할 수 있다. probe 결과도 resource 증거와 연결한다.

## 11. GPU와 RAN workload도 같은 기반을 쓴다

GPU application은 user process가 driver와 runtime을 통해 device queue와 memory를 사용한다. CPU quota나 memory pressure가 host-side submission을 늦출 수 있으므로 GPU utilization0%를 GPU hardware 문제로 바로 해석하지 않는다. device plugin, DRA claim, container device permission, driver version과 process 상태를 따라간다.

AI-RAN workload는 network packet deadline, CPU scheduling, accelerator kernel, memory와 I/O를 함께 사용한다. 평균 throughput이 충분해도 p99 latency와 jitter가 radio timing budget을 깨뜨릴 수 있다. network와 accelerator 지표를 같은 frame/packet/work request 신원에 연결해야 한다.

## 12. 연구 관측으로 바꾸는 법

“container가 느리다”를 연구 질문으로 바꿀 때 대상 workload, resource 범위, 시간과 비교 조건을 정한다. 예를 들어 “cgroup CPU quota0.5와1.0에서 동일 입력의 p95 wall latency가 어떻게 달라지는가”라고 쓴다. 결과 checksum과 completed work가 같아야 한다.

**독립 변수** 는 quota, **종속 변수** 는 latency·throughput·cpu.stat delta, **통제 변수** 는 input, thread 수, affinity, memory, kernel, cache, 동시성이다. host background load는 교란 변수다. 순서를 randomize하고 원시 반복값을 남긴다.

상관과 인과를 구분한다. PSI와 latency가 함께 올랐다는 관측은 후보를 좁힌다. 격리 환경에서 다른 조건을 고정하고 resource pressure 하나를 바꿨을 때 예측한 지표와 결과가 함께 바뀌면 인과 설명이 강해진다. production에서 제한을 즉시 바꾸는 것은 별도 승인·복구 계획이 필요한 운영 행위다.

## 13. 종합 문제와 완전 풀이

### 문제 1. boot 지연의 위치

전원 후 login 가능까지60초이고 systemd service 하나가20초 걸렸다.

**풀이:** service20초가 전체 critical path에 포함됐는지 의존 graph와 timestamp를 확인한다. firmware와 kernel, initramfs 시간이 병렬·직렬로 더해질 수 있다. 60-20=40을 다른 한 원인으로 부르지 않는다.

### 문제 2. CPU time과 wall

4 thread가 각1 CPU초를 동시에 쓰고1초 wall에 끝났다.

**풀이:** process CPU time 합은 약4초, wall은 약1초일 수 있다. 여러 core 병렬 실행 때문이다. CPU time이 wall보다 크다고 계측 오류가 아니다.

### 문제 3. quota

cpu.max=50000 100000이고 thread 두 개가 각각30ms를 요구한다.

**풀이:** cgroup 합계 예산은50ms, share는0.5 CPU다. 교육 round-robin에서는 각각25ms 쓰고 총10ms demand가 다음 period로 남는다. thread마다0.5 CPU가 아니다.

### 문제 4. host idle 반례

host idle70%인데 service가100ms 주기로 멈춘다.

**풀이:** service cgroup quota나 affinity로 idle core를 못 쓸 수 있다. cpu.stat nr_throttled/throttled_usec delta와 cpu.max를 같은 시간에 확인한다. host 평균만으로 CPU 원인을 배제하지 않는다.

### 문제 5. virtual address

두 process가 모두0x400000을 읽는다.

**풀이:** 각 process page table이 다른 physical frame에 mapping할 수 있다. 같은 virtual 숫자가 같은 data를 뜻하지 않는다. shared mapping을 명시적으로 사용한 경우에는 같은 backing을 공유할 수 있다.

### 문제 6. major/minor fault

file page가 이미 page cache에 있지만 process page table mapping이 없다.

**풀이:** storage I/O 없이 mapping을 만들 수 있어 minor fault가 될 수 있다. fault라는 단어가 application 오류나 crash를 뜻하지 않는다. 실제 분류는 kernel 상황에 따른다.

### 문제 7. memory account

anonymous220,clean80,dirty40,other20MiB다.

**풀이:** current는360MiB다. high256보다 크고 max384보다 작다. high pressure 가능 구간이며 이 숫자만으로 즉시 OOM이라 하지 않는다.

### 문제 8. clean과 dirty reclaim

360에서 target240이다.

**풀이:** clean80을 회수하면280이다. dirty40은 writeback으로 clean이 되어도 합계는280이고, 그40을 추가 회수해야240이다. writeback과 reclaim을 같은 사건으로 세지 않는다.

### 문제 9. PSI

memory some total이60초에3,000,000µs 늘고 oom_kill은0이다.

**풀이:** 3초의 일부 task memory stall이 있었음을 나타낸다. OOM kill 없이 reclaim pressure가 있을 수 있다. 어떤 allocation과 page가 원인인지는 memory.events/stat/refault와 stack을 더 본다.

### 문제 10. I/O queue

초당100 request를 완료하고 평균 system 내 request가30이라는 안정 상태 가정이다.

**풀이:** Little의 법칙으로 평균 체류시간은30/100=0.3초다. 안정 상태와 같은 범위라는 조건이 깨지면 계산을 적용할 수 없다. p95는 평균에서 알 수 없다.

### 문제 11. short read

4096B read의 CQE result가1200이다.

**풀이:** 1200B 성공일 수 있다. buffer의0~1199만 유효하고, EOF 여부와 남은 byte를 다시 요청할지는 file/opcode 계약에 따라 결정한다. 자동으로 EIO가 아니다.

### 문제 12. out-of-order completion

101→buf-A,102→buf-B 뒤 CQE102가 먼저 왔다.

**풀이:** user_data102로 pending map을 찾아 buf-B 결과를 처리하고 B만 release한다. 배열 첫 buffer A를 해제하면 kernel이 아직 사용할 수 있어 use-after-free가 된다.

### 문제 13. errno 분리

ring setup이 EPERM이고 특정 opcode completion은 EINVAL이다.

**풀이:** EPERM은 policy, seccomp, privilege, disabled 설정 범주를 먼저 본다. EINVAL은 flag, field, opcode와 kernel 지원 조합을 본다. 둘을 모두 “kernel이 오래됨”으로 기록하지 않는다.

### 문제 14. TCP send 성공

send가4096을 반환했다.

**풀이:** local kernel이4096B를 받았다는 경계일 수 있다. 상대 application이 읽고 처리했다는 보장이 아니다. TCP ACK, receiver queue, application response는 이후 경계다.

### 문제 15. container OOM

Pod container 하나가 종료되고 해당 cgroup memory.events의 oom_kill delta가1, node 다른 workload는 정상이다.

**풀이:** 그 cgroup limit OOM 가설이 가장 가깝다. memory.current/max와 ancestor, kubelet/container status, kernel log를 확인한다. “node 전체 메모리 고갈”로 확대하지 않는다.

### 문제 16. liveness restart

storage latency 때 probe timeout으로 container가 반복 restart된다.

**풀이:** liveness는 process 재시작으로 회복 가능한 교착/고장을 다뤄야 한다. storage queue가 원인이면 restart가 cache를 버리고 부하를 더할 수 있다. readiness로 traffic을 빼고 resource 원인을 고치는 설계를 검토하되 실제 변경은 영향 시험이 필요하다.

### 문제 17. Spark/I/O evidence

Spark stage 정체60초에 CPU throttled0.2초, memory stall0.03초, io some stall18초, device active59초다.

**풀이:** storage path pressure 가설이 CPU quota·memory보다 강하다. device hardware 고장까지 증명한 것은 아니다. 다른 tenant, filesystem writeback, queue와 completion latency를 분리한다.

### 문제 18. 모델과 실측

Python memory model final이240MiB다.

**풀이:** 고정 입력에서 clean80과 dirty40을 모두 회수한 산술 결과다. 실제 Linux가 같은 시간과 순서로240에 도달한다는 예측이 아니다. swap, slab, refault, NUMA, writeback 실패가 생략됐다.

### 문제 19. counter reset

t0 counter1000,t1 counter20이다.

**풀이:** -980 사건이라고 계산하지 않는다. process/cgroup/device 재생성, boot 변경, field wrap를 확인한다. 동일 수명이라는 신원이 증명될 때만 단순 delta를 쓴다.

### 문제 20. 연구 설계

quota0.5와1.0의 latency를 비교하면서 thread 수도2에서8로 바꿨다.

**풀이:** 독립 변수가 두 개라 차이 원인을 분리할 수 없다. thread 수를 고정하고 quota만 바꾸거나 factorial design으로 두 요인의 조합을 반복한다. 결과량과 checksum도 같아야 한다.

## 14. 이름이 같은 객체를 구분한다

| 이름 | 실제 대상 | 위치와 수명 |
|---|---|---|
| task | Linux scheduler task | kernel이 thread 실행 수명 동안 관리 |
| Spark task | partition 계산 attempt | Spark stage 실행 동안 |
| page | virtual/physical memory 관리 단위 | mapping과 frame 수명 |
| file page | page cache의 file 내용 | reclaim 전까지 |
| SQE/CQE | io_uring ring entry | 제출·소비될 때까지 |
| queue | scheduler, block, NIC 등의 대기 구조 | 각 subsystem 실행 동안 |
| limit | cgroup controller 경계 | 설정이 유지되는 동안 |
| request | application 논리 작업 또는 kernel I/O | terminal 결과까지 |
| container | namespace/cgroup/image로 구성한 process 묶음 | runtime workload 수명 |
| evidence | 신원·시각·단위를 포함한 관측 묶음 | 조사와 재현 기록 수명 |

## 15. 문제 해결 순서

1. 증상을 시각, 범위, 숫자로 쓴다.
2. PID, cgroup, device, socket, container attempt 신원을 고정한다.
3. 최소 두 경쟁 가설과 예상 동반 관측을 적는다.
4. gauge, counter, average, limit를 분류한다.
5. 두 시점 counter의 delta를 계산하고 reset을 확인한다.
6. CPU, memory, I/O, network의 범위를 같은 시간축에 맞춘다.
7. application 결과와 kernel 자원 상태를 연결한다.
8. 가장 작은 read-only 추가 관측으로 가설을 줄인다.
9. 변경이 필요하면 격리 환경에서 한 변수만 바꾼다.
10. 결론 강도, 반대 증거와 남은 대안을 기록한다.

## 16. 공식 출처를 사용하는 법

Linux kernel 문서는 /proc, cgroup, PSI, io_uring과 I/O counter의 user-visible 계약을 확인하는 1차 자료다. systemd 문서는 unit과 resource-control mapping을 설명하고, Ubuntu 문서는 배포판 packaging과 지원 정책을 보완한다. Kubernetes 문서는 Pod와 probe API 계약을 확인한다. source code는 version별 구현 세부를 볼 수 있지만 현재 실행 kernel build와 config가 같은지 확인해야 한다.

blog의 tuning 숫자를 그대로 적용하지 않는다. kernel version, device, workload distribution, cache, concurrency와 결과 정확성이 다르면 효과가 바뀐다. 이 책의 모든 손 계산과 Python 출력은 교육용이며 현재 서버를 측정한 값이 아니다.

## 17. 주요 1차 자료

- [Linux kernel documentation](https://docs.kernel.org/)
- [Linux kernel: The kernel’s command-line parameters](https://docs.kernel.org/admin-guide/kernel-parameters.html)
- [Linux kernel: proc filesystem](https://docs.kernel.org/filesystems/proc.html)
- [Linux kernel: cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [Linux kernel: PSI](https://docs.kernel.org/accounting/psi.html)
- [Linux kernel: Memory Management](https://docs.kernel.org/admin-guide/mm/)
- [Linux kernel: I/O statistics fields](https://docs.kernel.org/admin-guide/iostats.html)
- [Linux kernel: io_uring](https://docs.kernel.org/io_uring/)
- [io_uring_setup(2)](https://man7.org/linux/man-pages/man2/io_uring_setup.2.html)
- [liburing](https://github.com/axboe/liburing)
- [systemd resource control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- [systemd unit documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html)
- [Kubernetes: Pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [Kubernetes: Resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)

새 용어는 실제 객체, 위치, 관리자, 수명, 관측 가능한 상태 전이로 연결해 설명한다.
