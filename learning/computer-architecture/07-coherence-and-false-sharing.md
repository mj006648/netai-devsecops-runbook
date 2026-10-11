# 07. 캐시 일관성과 false sharing

[← 이전](06-cache-addresses-and-locality.md) · [목차](README.md) · [다음 →](08-memory-ordering-and-atomics.md)

코어가 하나라면 06장의 cache는 memory data의 가까운 복사본을 두는 문제로 시작할 수 있다. 코어가 둘이면 같은 physical address의 line이 두 L1 cache에 동시에 존재할 수 있다. 한 코어가 값을 바꿨는데 다른 코어가 오래된 copy를 계속 읽으면 프로그램이 기대한 communication이 깨진다. 여러 copy의 읽기와 쓰기 권한을 조정하는 규칙이 **cache coherence(캐시 일관성)**다.

![coherence](assets/coherence.svg)

## 메시지를 보내는 실제 주체

각 core의 cache 옆에는 **cache controller(캐시 제어기)**가 있다. 이 제어 회로는 CPU의 load와 store 주소를 받아 tag와 상태를 확인하고, local hit이면 data를 돌려준다. 다른 cache와 협의가 필요하면 coherence request를 만든다. “CPU0이 invalidate를 보낸다”라는 표현은 실제로 CPU0 쪽 cache controller와 coherence 장치가 protocol message를 보낸다는 뜻이다.

여러 cache controller와 마지막 단계 cache 또는 memory controller를 연결해 request와 data가 이동하는 통신 경로를 **interconnect(상호연결망)**라고 한다. 한 개 bus일 수도 있고 ring, mesh, point-to-point network일 수도 있다. **medium(전송 매체)**은 message가 지나가는 공유 bus나 link 같은 물리·논리 경로를 일반적으로 부르는 말이다. core 수가 많으면 한 공유 bus만으로 모든 message를 방송하기 어려워 network와 directory를 사용한다.

한 cache가 line을 수정하려면 다른 cache가 오래된 copy를 계속 사용하지 못하도록 배타적인 쓰기 권한이 필요하다. 이 권한을 **ownership(소유권)**이라고 부른다. data라는 물체를 영원히 소유한다는 뜻이 아니라, 지금 이 line의 최신 값을 수정할 protocol 권한을 가진다는 뜻이다.

다른 cache의 copy를 더 이상 읽을 수 없게 상태 I로 바꾸라는 message가 **invalidate(무효화 요청)**다. invalidate를 받은 controller는 진행 중인 access와 순서를 맞춘 뒤 line을 I로 만들고, 처리가 끝났다는 **acknowledgement 또는 ack(확인 응답)**를 돌려준다. writer는 필요한 ack를 모아 오래된 readable copy가 남지 않았음을 확인한 뒤 ownership을 사용할 수 있다.

누가 line copy를 가지고 있는지 기록한 표를 **directory(디렉터리)**라고 한다. directory entry에는 owner와 sharer 집합이 들어갈 수 있다. write request가 오면 directory가 invalidate를 보낼 대상을 정한다. 반대로 **snooping(엿보기 방식)**은 공유 bus 같은 경로에 흐르는 coherence request를 각 cache controller가 관찰하고 자신이 가진 line과 관련되면 응답하는 방식이다. directory와 snooping은 같은 일을 구현하는 서로 다른 조직이며 실제 system은 계층적으로 섞을 수도 있다.

## 1. line 단위로 권한을 관리하는 이유

cache는 byte 하나가 아니라 보통 64B **cache line**을 data 이동과 tag 관리 단위로 쓴다. coherence도 대개 line 단위로 어느 cache가 읽을 수 있고 누가 쓸 권한을 가지는지 추적한다.

주소 0x1000의 8B counter를 CPU0과 CPU1이 모두 읽었다고 하자. 두 L1에는 0x1000~0x103f line copy가 있을 수 있다. CPU0이 counter를 1로 쓰려면 CPU1의 오래된 copy가 이후 read에 사용되지 않게 해야 한다.

이를 위해 interconnect와 cache controller는 read request, ownership request, invalidate, acknowledgement, data response 같은 message를 교환한다. directory 기반 system은 어느 cache가 copy를 가진지 기록할 수 있고 snooping system은 공유 medium의 request를 cache들이 관찰할 수 있다. ISA가 message 이름과 exact protocol을 강제하지 않는다.

## 2. MESI 상태를 필요한 질문에서 도출한다

각 cache line entry에는 data와 tag 외에 “이 copy를 읽어도 되는가”, “다른 cache가 copy를 가질 수 있는가”, “memory보다 최신인가”를 나타낼 상태가 필요하다. 교육용 MESI는 네 상태로 답한다.

- **I(Invalid, 무효)**: 이 entry의 data를 해당 address의 유효 copy로 사용할 수 없다.
- **S(Shared, 공유)**: 여러 cache가 가질 수 있는 깨끗한 read-only copy다. memory와 같은 값이라고 보는 교육 모형이다.
- **E(Exclusive, 단독)**: 이 cache만 가진 깨끗한 copy다. memory와 같은 값이지만 다른 sharer가 없으므로 local write 때 message 없이 M으로 갈 수 있다.
- **M(Modified, 수정)**: 이 cache가 최신 data와 write ownership을 가진다. 아래 memory는 오래될 수 있으며 다른 cache가 읽으려면 최신 data를 받아야 한다.

MESI는 공통 원리를 설명하는 모형이다. 실제 CPU는 Owned, Forward 같은 상태와 transient state를 더 쓰고 directory, inclusive cache 정책에 따라 전이가 다르다. 제품이 “MESI 계열”이라는 말만으로 exact message와 latency를 알 수 없다.

~~~mermaid
sequenceDiagram
  participant C0 as CPU0 L1
  participant H as coherence 경로
  participant C1 as CPU1 L1
  C0->>H: line L read
  H-->>C0: data, 유일 copy라 E 가능
  C1->>H: 같은 L read
  H->>C0: 다른 reader 통지
  H-->>C1: data
  Note over C0,C1: 둘 다 S
  C0->>H: write ownership 요청
  H->>C1: invalidate L
  C1-->>H: acknowledgement, I
  H-->>C0: write 허가
  Note over C0: C0는 M으로 수정
~~~

## 3. 한 line의 전체 상태 trace

line L의 memory 값은 0이고 두 L1 상태는 I라고 하자.

| 단계 | 사건 | CPU0 상태·값 | CPU1 상태·값 | 아래 memory | 이유 |
|---:|---|---|---|---:|---|
| 0 | 초기 | I | I | 0 | copy 없음 |
| 1 | CPU0 read L | E, 0 | I | 0 | 유일한 깨끗한 copy |
| 2 | CPU0 write 1 | M, 1 | I | 0 | E→M은 다른 sharer 없어 조용히 가능 |
| 3 | CPU1 read L | S, 1 | S, 1 | 1 | pure MESI 모형에서 M owner가 data를 제공하고 하위 memory도 최신화 |
| 4 | CPU1 write 2 요청 | I | M, 2 | 1 | CPU0 copy invalidate 뒤 ownership, memory는 아직 이전값 |
| 5 | CPU0 read L | S, 2 | S, 2 | 2 | M owner가 data를 제공하고 하위 memory도 최신화 |
| 6 | 다른 line이 CPU1 entry 교체 | S, 2 | I | 2 | clean shared eviction은 조용할 수 있음 |

이 표는 Owned 상태가 없는 **순수 MESI 교육 모형**을 가정한다. 따라서 M line을 다른 reader와 공유해 양쪽이 S가 되는 단계 3과 5에서는 dirty data가 하위 memory에도 반영되어 S의 “깨끗한 공유 copy” 조건을 유지한다. 실제 MOESI 계열은 owner가 dirty shared data를 유지할 수 있어 memory update 시점이 다르다. 어떤 모형을 쓰는지 밝히지 않고 두 동작을 섞으면 안 된다.

**ownership**은 line을 수정할 수 있는 배타적 권한이다. data가 register에 있다는 사실과 line write ownership은 다르다. CPU가 store instruction을 실행했어도 ownership request와 invalidate acknowledgement를 기다리면 store가 coherence-visible해지는 시점이 늦을 수 있다.

## 4. invalidate와 update

write가 생길 때 다른 copy를 **invalidate**하는 protocol은 상대 cache 상태를 I로 만든다. 다음 read는 miss를 내고 최신 data를 다시 받는다. **update protocol**은 새 값을 다른 sharer에 보내 copy를 갱신한다.

invalidate는 한 core가 같은 line을 여러 번 쓸 때 traffic을 줄일 수 있다. update는 여러 core가 번갈아 읽는 경우 next read miss를 줄일 수 있지만 write마다 data traffic이 크다. 현대 general-purpose cache coherence에서 invalidate 계열이 흔하지만 모든 system의 절대 규칙은 아니다.

invalidate request를 보낸 순간 곧바로 자유롭게 쓸 수 있다고 단정하면 안 된다. 필요한 sharer의 acknowledgement를 모아 이전 copy가 더 이상 사용되지 않음을 확인하는 과정이 있을 수 있다. 이 대기가 store latency와 contention을 만든다.

## 5. true sharing과 false sharing

**true sharing**은 여러 thread가 논리적으로 같은 변수나 data structure를 읽고 쓰는 상황이다. synchronization이 없다면 data race가 될 수 있다. coherence는 최신 copy와 ownership을 조정하지만 source language의 atomicity와 happens-before를 자동 제공하지 않는다.

**false sharing**은 thread들이 서로 다른 변수를 쓰지만 그 변수들이 같은 cache line에 있어 line ownership을 경쟁하는 현상이다. 값 의존성은 없지만 hardware 관리 단위가 더 커서 “거짓으로 공유하는 것처럼” traffic이 생긴다.

~~~c
struct Counters {
    long cpu0_count;  // offset 0
    long cpu1_count;  // offset 8
};
~~~

64B line 시작에 이 struct가 있고 CPU0은 cpu0_count만, CPU1은 cpu1_count만 증가한다고 하자. 두 8B 변수는 다르지만 같은 line이다.

| 반복 단계 | CPU0 | CPU1 | coherence 사건 |
|---:|---|---|---|
| 1 | line E→M, A 증가 | I | CPU0 ownership |
| 2 | I로 전이 | ownership 받아 B 증가, M | line data와 권한 CPU1로 이동 |
| 3 | ownership 받아 A 증가, M | I | 다시 CPU0로 이동 |
| 4 | I | ownership 받아 B 증가, M | 다시 CPU1로 이동 |

이를 line ping-pong이라고 부른다. 한 번 increment의 ALU 연산은 짧지만 ownership 왕복과 interconnect queue가 병목이 된다. core 수를 늘릴수록 느려질 수도 있다.

## 6. false sharing을 고치는 방법과 반례

가장 직접적인 방법은 자주 쓰는 per-thread counter를 서로 다른 line에 놓는 것이다. padding 또는 alignment를 사용하거나 thread별 array element stride를 line size 이상으로 둔다. 그러나 무조건 64B padding이 정답은 아니다.

- 실제 coherence line 크기가 다를 수 있다.
- allocator가 object 시작을 충분히 align하지 않으면 경계를 걸칠 수 있다.
- padding은 memory footprint와 cache·TLB pressure를 늘린다.
- read-mostly data까지 멀리 떼면 spatial locality가 나빠질 수 있다.
- compiler와 language layout rule을 확인해야 한다.

더 좋은 algorithm은 hot counter를 thread-local로 누적한 뒤 낮은 빈도로 합치는 것이다. 매 increment의 shared write를 없애고 reduction 시점만 synchronize한다. 이 방법은 결과가 즉시 전역에 보여야 하는 요구와 trade-off가 있다.

수정 전 8 thread가 하나의 line 안 8개 counter를 초당 각 1억 번 쓴다고 하자. ownership이 thread 사이를 계속 이동한다. 수정 후 각 counter를 별도 line에 두면 coherence traffic은 줄지만 working set은 64B에서 512B로 늘어난다. performance counter와 wall time으로 실제 이득을 확인해야 한다.

## 7. coherence와 memory consistency는 다르다

**coherence**는 보통 한 memory location의 copy와 write 순서를 다룬다. **memory consistency model**은 서로 다른 location에 대한 load와 store가 다른 hart에 어떤 순서로 관찰될 수 있는지 정한다.

CPU0:
~~~text
data = 42
flag = 1
~~~

CPU1:
~~~text
if (flag == 1)
    print(data)
~~~

data와 flag가 각각 coherence를 지켜도 CPU1이 flag=1을 본 뒤 data=0을 볼 수 있는지는 memory model, compiler reorder, cache와 store buffer, synchronization에 달렸다. coherence만으로 “source 순서대로 모두 보인다”고 결론 내리면 안 된다.

**release store**는 그 store보다 앞선 이 thread의 memory 작업이 release 뒤로 밀려 다른 thread에 늦게 보이는 것을 제한한다. CPU0이 data=42를 일반 store한 뒤 flag=1을 release로 저장한다고 하자. **acquire load**는 flag에서 1을 읽은 뒤의 작업이 acquire 앞으로 당겨지는 것을 제한한다. CPU1이 flag를 acquire로 읽어 release가 쓴 1을 관찰하면 두 operation 사이에 동기화 관계가 생겨 뒤의 data read가 42를 관찰하도록 language와 ISA 규칙을 구성할 수 있다. 정확한 code는 사용하는 언어의 atomic API와 memory order를 따라야 한다.

**atomic operation**도 coherence와 같지 않다. coherence protocol은 atomic read-modify-write가 line ownership을 얻는 기반이 될 수 있지만 ISA가 operation의 indivisibility와 ordering을 별도로 정의해야 한다. 일반 load 다음 일반 store로 counter++를 구현하면 각 access가 coherent여도 두 thread가 같은 old value를 읽어 update 하나를 잃을 수 있다.

## 8. lost update 전체 trace

counter=0이고 CPU0과 CPU1이 일반 load/add/store로 증가시킨다.

| 순서 | CPU0 | CPU1 | memory/coherence 결과 |
|---:|---|---|---|
| 1 | load counter→0 |  | CPU0 copy 0 |
| 2 |  | load counter→0 | 두 core가 0 관찰 |
| 3 | register에서 1 계산 |  | memory 변화 없음 |
| 4 |  | register에서 1 계산 | memory 변화 없음 |
| 5 | store 1, ownership |  | counter=1 |
| 6 |  | store 1, ownership 이동 | counter=1 |

두 번 증가했지만 결과는 1이다. coherence가 깨진 것이 아니다. 두 store의 순서는 정해졌고 마지막 값 1이 모두에게 보인다. 문제는 load와 store 사이 전체가 atomic하지 않았다는 것이다.

atomic fetch-add를 사용하면 ownership을 가진 cache controller와 execution unit이 read-modify-write를 다른 hart의 같은 atomic operation과 중간에 섞이지 않는 하나의 단위로 수행하도록 ISA가 약속한다. 한 thread는 old 0을 받아 1, 다른 thread는 old 1을 받아 2를 만든다. 어떤 순서인지는 달라도 최종 2다. 다만 같은 위치의 원자성만 요청한 relaxed operation인지, 앞뒤 다른 memory 작업의 순서까지 묶는 acquire·release인지 API argument로 구분해야 한다.

## 9. lock과 line contention

spinlock의 lock word 하나를 모든 thread가 계속 write하려 하면 ownership ping-pong이 생긴다. test-and-test-and-set은 먼저 read-only로 기다리고 값이 풀릴 때만 atomic write를 시도해 write traffic을 줄인다. queue lock은 각 waiter가 다른 node나 line을 기다리게 해 확장성을 높일 수 있다.

lock을 썼다는 사실만으로 false sharing이 사라지지 않는다. lock과 보호 data가 같은 line인지, 서로 다른 lock들이 한 line에 모였는지, critical section 밖의 counter가 같은 line인지 layout을 본다.

NUMA system에서는 line owner가 다른 socket에 있으면 coherence message가 socket interconnect를 건너 latency와 bandwidth 비용이 커진다. thread pinning과 first-touch allocation, data partitioning을 함께 측정한다.

## 10. DMA와 device coherence

CPU 외의 device도 memory를 읽고 쓸 수 있다. **coherent DMA** platform은 device와 CPU cache 사이 visibility를 hardware와 platform protocol이 관리할 수 있다. non-coherent device에서는 driver가 cache clean, invalidate, DMA mapping API를 올바른 순서로 사용해야 한다.

device가 memory를 썼는데 CPU가 stale line을 계속 읽거나, CPU dirty line이 device가 쓴 memory를 나중에 덮으면 data corruption이 난다. “cache coherence가 있는 CPU”라는 사실만으로 모든 peripheral이 자동 coherent라고 가정하지 않는다. platform와 driver API 계약을 확인한다.

## 11. 관측과 연구 연결

false sharing은 source만 보고 확정하기 어렵다. object address, line size, thread placement, write frequency를 확인한다. wall time과 함께 cache-to-cache transfer, HITM, invalidation 관련 PMU event를 보되 event 이름과 정확한 의미는 CPU vendor 문서를 따른다.

실험은 single-thread baseline, thread 수 변화, padding 전후, thread pinning, NUMA 위치를 통제한다. 평균뿐 아니라 tail과 run-to-run 변동을 본다. padding 후 빨라져도 원인이 오직 false sharing이라고 결론 내리기 전에 working set과 allocator layout 변화를 확인한다.

최신 연구는 directory storage를 줄이는 sparse coherence, chiplet·CXL device coherence, heterogeneous CPU-GPU shared memory, coherence side channel을 다룬다. protocol guarantee와 prototype 측정값을 분리한다. 특정 workload에서 traffic이 몇 % 감소했다는 결과는 core 수, line size, topology, baseline에서만 해석한다.

## 12. 전체 문제 풀이

### 문제 1
CPU0이 line을 E로 가진 뒤 local write하면 반드시 invalidate message가 필요한가?

**풀이:** 교육용 MESI에서 E는 다른 sharer 없는 깨끗한 단독 copy다. CPU0은 외부 invalidate 없이 E→M으로 바꿔 쓸 수 있다. 실제 protocol의 transient 조건은 구현에 따라 다르다.

### 문제 2
CPU0과 CPU1이 S인 line에 CPU0이 쓰려면 어떤 일이 필요한가?

**풀이:** CPU0이 ownership을 요청하고 CPU1 copy를 invalidate해 I로 만든다. 필요한 acknowledgement 뒤 CPU0이 M 권한으로 수정한다. CPU1 다음 read는 miss로 최신 data를 받아야 한다.

### 문제 3
서로 다른 두 counter를 쓰는데 왜 느릴 수 있는가?

**풀이:** 두 변수가 같은 64B line이면 coherence는 변수 아닌 line 단위 ownership을 이동시킨다. 각 core write 때 상대 copy를 invalidate해 line이 ping-pong한다. 별도 line 배치나 thread-local aggregation을 검토한다.

### 문제 4
coherence가 있으면 일반 counter++가 atomic한가?

**풀이:** 아니다. 각 load와 store는 coherent해도 두 core가 모두 old 0을 읽고 각각 1을 저장해 update 하나를 잃을 수 있다. atomic fetch-add나 lock으로 read-modify-write 전체를 보호해야 한다.

### 문제 5
data와 flag 각각이 coherent하면 flag=1을 본 CPU가 항상 최신 data를 보는가?

**풀이:** coherence만으로 서로 다른 location의 관찰 순서를 보장하지 않는다. language와 ISA memory model에 맞는 release/acquire 또는 lock이 필요하다. flag의 release store와 이를 읽은 acquire load가 동기화 관계를 만들면 release 앞 data write를 acquire 뒤에서 관찰하도록 순서를 세울 수 있다.

## 공식 자료

- [RISC-V Unprivileged ISA Memory Models](https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/#memory-models)
- [RISC-V Ratified Specifications](https://docs.riscv.org/)

[← 이전](06-cache-addresses-and-locality.md) · [목차](README.md) · [다음 →](08-memory-ordering-and-atomics.md)
