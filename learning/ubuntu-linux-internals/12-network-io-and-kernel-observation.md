# 12. Network I/O와 kernel 관찰

[이 책 목차](README.md) · [이전: io_uring ordering, error와 fsync](11-io-uring-ordering-errors-and-fsync.md) · [다음: Container, Kubernetes, GPU와 RAN](13-containers-kubernetes-gpu-and-ran.md)

네트워크 서버의 recv()와 send()만 보면 패킷이 NIC queue, kernel packet object, socket queue와 application buffer를 지나는 동안 어느 CPU에서 복사·전환·대기가 생겼는지 놓친다. 이 장의 packet trace와 수치는 실행 결과가 아닌 교육용 가상 모형이다. eBPF program을 attach하거나 network·kernel 설정을 바꾸지 않았다.

## socket은 process가 network endpoint를 다루는 kernel object다

**socket(소켓)**은 TCP·UDP 같은 통신 endpoint의 상태를 kernel이 보관하는 객체다. process는 fd로 socket을 참조한다. local·remote address, protocol state, receive/send queue는 kernel memory에 있고 close와 reference 종료 뒤 해제된다. application이 byte stream을 읽고 쓰려면 hardware packet과 process buffer 사이의 경계가 필요해 socket이 존재한다.

NIC(Network Interface Controller)는 frame을 송수신하는 hardware다. RX는 receive, TX는 transmit이다. NIC의 RX descriptor ring은 driver가 제공한 host memory buffer와 hardware ownership을 기록하는 원형 queue다. packet이 오면 NIC는 **DMA(Direct Memory Access)**로 CPU가 byte마다 복사하지 않고 host memory에 frame을 기록한다.

driver는 NIC register, queue, interrupt와 DMA buffer를 다루는 kernel software다. NIC가 새 일이 있음을 CPU에 알리는 signal이 interrupt다. packet마다 interrupt하면 전환 비용이 커지므로 Linux는 **NAPI**라는 network event 처리 mechanism으로 interrupt와 polling을 조합한다. 현재 공식 문서에서 NAPI라는 이름은 특정 영어 구절을 풀어 쓴 약어로 취급하지 않는다. driver가 NAPI instance를 schedule하면 poll method가 budget 수만큼 RX packet을 처리하고 TX completion도 회수한다.

packet을 kernel network stack이 전달할 때 대표적으로 **skb(socket buffer 또는 struct sk_buff)**라는 metadata 객체를 사용한다. skb는 packet data 자체와 항상 한 덩어리 복사본인 것이 아니라 header, 길이, protocol, fragment 참조와 queue 연결 정보를 가진다. kernel이 할당·수정·해제하고 socket delivery나 drop 뒤 수명이 끝난다.

~~~mermaid
flowchart LR
 N[NIC RX queue] -->|DMA| B[driver buffer]
 B -->|interrupt then poll| P[NAPI]
 P --> S[skb와 network stack]
 S --> Q[socket receive queue]
 Q -->|recv copy 또는 지원 경로| U[application buffer]
 U --> A[protocol parser]
~~~

### 문제 1: receive 경로의 copy와 context를 구분하기

frame 1500바이트가 도착해 일반 TCP recv로 사용자 buffer에 전달됐다. DMA와 CPU copy, 실행 context를 설명하라.

NIC는 DMA로 driver가 준비한 host buffer에 frame을 기록한다. interrupt는 처리할 일이 있음을 알리고 NAPI poll은 보통 softirq context에서 descriptor를 회수한다. kernel stack은 skb metadata로 Ethernet/IP/TCP를 처리하고 payload를 socket receive queue에 연결한다. recv가 진행되면 payload byte가 application buffer로 copy될 수 있다. DMA가 있었으므로 전체가 zero-copy라는 결론은 틀리다. 조건을 바꾸어 page fragment, GRO, XDP, io_uring zero-copy 지원 경로를 쓰면 copy 위치가 달라질 수 있어 측정과 feature 조건이 필요하다.

## RSS와 RPS는 서로 다른 시점에 CPU를 고른다

**RSS(Receive Side Scaling)**는 multi-queue NIC가 packet header hash와 indirection table로 hardware RX queue를 선택하는 기능이다. queue별 IRQ affinity를 통해 어느 CPU가 초기 receive 처리를 맡을지 분산한다. NIC와 driver가 관리하며 장치가 multi-queue와 RSS를 지원해야 한다.

**RPS(Receive Packet Steering)**는 hardware queue 이후 Linux software가 flow hash로 protocol 처리를 수행할 CPU를 고르는 기능이다. 선택한 CPU backlog에 skb를 넣고 필요하면 inter-processor interrupt로 깨운다. CONFIG_RPS가 필요하고 queue별 rps_cpus가 0이면 기본적으로 비활성이다. RSS는 hardware queue와 interrupt CPU를, RPS는 이후 stack CPU를 고른다는 위치 차이가 있다.

**per-CPU data(퍼CPU 데이터)**는 각 logical CPU가 자기 복사본이나 queue를 갖게 해 공유 lock과 cache-line 경쟁을 줄이는 kernel 구조다. network backlog와 통계가 per-CPU일 수 있다. 합계를 얻으려면 CPU별 값을 안전하게 모아야 하며 thread가 CPU를 이동하면 locality가 달라진다.

### 문제 2: RSS와 RPS가 만든 두 번의 CPU 이동

RSS가 flow를 RX queue 2, IRQ CPU 2로 보냈고 RPS가 CPU 6을 선택했다. 어떤 일이 추가되고 언제 유리한가?

NIC DMA completion과 초기 interrupt/NAPI는 CPU 2와 연결된다. RPS는 skb를 CPU 6 backlog에 enqueue하고 CPU 6을 깨워 상위 protocol 처리를 이어가게 한다. CPU 사이 queueing과 IPI, cache 이동 비용이 추가된다. CPU 2가 포화됐거나 application이 CPU 6 근처에서 실행돼 locality가 좋아지면 이득일 수 있다. 조건을 바꾸어 queue 수와 CPU mapping이 이미 균형 잡힌 RSS라면 RPS가 중복 비용만 만들 수 있다. packet rate, queue drop, CPU load와 NUMA locality로 판단한다.

## XDP와 tc는 packet path의 서로 다른 hook이다

**XDP(eXpress Data Path)**는 지원 driver의 receive 경로에서 skb를 만들기 전 이른 시점에 BPF program을 실행해 PASS, DROP, TX, REDIRECT 같은 결정을 내리는 hook이다. NIC driver와 kernel이 program을 실행하며 mode는 native·generic·offload 등 지원 조건이 다르다. XDP가 있다는 말만으로 hardware offload나 zero-copy를 보장하지 않는다.

**tc(traffic control)**는 Linux qdisc와 ingress·egress hook에서 packet 분류, shaping, policing과 BPF action을 적용하는 subsystem이다. tc BPF는 일반적으로 XDP보다 stack의 뒤쪽에서 skb를 볼 수 있다. 둘은 “빠른 packet program”이라는 이유로 교환 가능한 한 지점이 아니다.

**eBPF(extended Berkeley Packet Filter)**는 verifier가 검사한 bytecode program을 kernel hook에서 실행하고 map으로 상태를 공유하는 기술이다. program과 map은 fd·pin/reference가 유지되는 동안 kernel에 존재한다. attach는 관찰 목적이어도 kernel runtime state를 바꾸며 권한, verifier, overhead, payload privacy 검토가 필요하다.

### 문제 3: XDP drop과 socket drop을 구별하기

XDP program이 packet 100개를 DROP했다. socket receive queue drop과 application recv count에는 어떻게 보일 수 있는가?

XDP_DROP은 skb 생성과 socket lookup 이전의 이른 경로에서 packet을 버릴 수 있어 socket queue까지 도달하지 않는다. application recv byte에는 나타나지 않고 socket drop counter도 해당 지점을 세지 않을 수 있다. XDP program·driver 통계가 필요하다. 조건을 바꾸어 tc ingress나 socket queue에서 drop되면 skb는 이미 만들어졌고 다른 counter가 증가할 수 있다. “packet이 사라졌다”만으로 drop hook을 정하지 않는다.

## TCP byte stream과 readiness·completion을 분리한다

epoll은 fd에서 blocking 없이 read·write를 시도할 준비가 되었음을 알리는 **readiness(준비 상태)** 모델이다. EPOLLIN 뒤 application이 recv를 호출해 실제 byte 수, EOF, EAGAIN을 받는다. 다른 thread가 먼저 읽거나 edge-triggered loop가 queue를 끝까지 비우지 않으면 event 해석이 달라진다.

io_uring은 제출한 receive operation의 결과가 CQE로 오는 **completion(완료)** 모델이다.

~~~text
RECV SQE len=8192, user_data=connection_42
CQE res=1460  → 1460 bytes 수신
CQE res=0     → TCP peer orderly shutdown 가능
CQE res=-11   → -EAGAIN, mode·flag에 따라 처리
~~~

TCP는 message가 아니라 순서 있는 byte stream을 제공한다. 32 KiB body가 CQE 여러 개로 나뉘거나 header와 다음 message 일부가 한 recv에 들어올 수 있다. parser가 length와 누적 byte로 경계를 복원한다.

### 문제 4: CQE 1000바이트의 의미

4 KiB message를 기다리는데 receive CQE가 1000을 반환했다. message 완료인가? 다음 상태를 계산하라.

4 KiB는 4096바이트이므로 1000만으로 완료가 아니다. header가 선언한 길이가 4096이라면 remaining은 \(4096-1000=3096\)바이트다. buffer offset을 1000 전진해 다음 receive를 제출하고 EOF·error·timeout을 처리한다. 조건을 바꾸어 1000바이트 안에 길이 400짜리 message 두 개와 다음 header 200바이트가 들어왔다면 parser는 두 message를 꺼내고 200을 보존한다. CQE 경계를 protocol 경계로 쓰지 않는다.

## buffer lifetime과 multishot을 terminal까지 본다

provided buffer ring은 kernel이 등록된 group에서 receive buffer ID를 골라 CQE flag로 돌려주는 방식이다. application은 선택된 ID의 res 길이만 parse하고 모든 consumer가 끝난 뒤 pool로 반환한다. 먼저 recycle하면 다음 packet이 아직 참조 중인 memory를 덮는다.

multishot accept·receive는 SQE 하나가 CQE 여러 개를 만든다. IORING_CQE_F_MORE가 더 결과가 올 수 있음을 알린다. MORE가 없는 terminal CQE 전 request context를 해제하지 않는다. 지원 opcode와 kernel version, flags는 probe해야 한다.

send CQE full bytes는 sender kernel socket buffer가 byte를 받아들였다는 뜻일 수 있다. NIC 전송, remote TCP stack 수신, remote application read, database commit은 이후 단계다. TCP ACK도 remote kernel transport 신호다.

**zero-copy(무복사)**는 특정 경계에서 CPU data copy를 줄이는 기법이다. 모든 경계에서 byte가 한 번도 복사되지 않는다는 절대 표현이 아니다. send zero-copy는 kernel이 user page 참조를 끝냈다는 notification까지 buffer를 유지해야 하며 fallback 가능성도 처리한다. remote 처리 완료 신호가 아니다.

### 문제 5: send 성공과 buffer 재사용

8 KiB SEND_ZC 요청의 data CQE가 8192였지만 notification이 아직 없다. buffer를 덮어도 되는가? remote commit을 알 수 있는가?

full data CQE는 요청 byte가 send 경로에 받아들여졌음을 나타내지만 zero-copy reference 해제 notification 전에는 buffer를 재사용하지 않는다. remote application commit은 별도 protocol response와 transaction ID로 확인해야 한다. 조건을 바꾸어 kernel이 copy fallback을 했다면 notification semantics가 달라질 수 있으므로 CQE flags와 API 계약을 처리한다. io_uring 사용, registered buffer, zero-copy는 같은 조건이 아니다.

## queue 증가와 backpressure를 수치로 본다

**backpressure(역압)**는 consumer가 느릴 때 queue 증가가 window 축소나 producer 대기로 전달되어 생산 속도를 제한하는 현상이다. TCP는 receive window와 send buffer를 통해 속도가 전달될 수 있지만 UDP에는 같은 reliable stream backpressure가 없어 drop이 직접 나타날 수 있다.

client 1000개가 각 100 KiB/s를 보내면 ingress는 약 100 MiB/s다. parser 처리량이 60 MiB/s면 잠재 차이는 40 MiB/s이고 5초면 200 MiB다. 실제 queue는 socket limit과 TCP window 때문에 무한히 늘지 않는다. 대신 sender 지연, drop, retransmission이 나타날 수 있다. socket memory는 cgroup memory에 포함될 수 있어 network burst가 memory.high, reclaim, OOM과 연결된다.

### 문제 6: queue와 deadline 계산

ingress 80 MiB/s, 처리 50 MiB/s가 4초 지속된다. 잠재 queue 증가량과 64 MiB 여유를 소진하는 시간을 구하라.

차이는 30 MiB/s, 4초 누적은 \(30×4=120\) MiB다. 64 MiB 여유는 \(64/30≈2.13\)초에 소진된다. 실제 TCP backpressure가 먼저 sender를 늦출 수 있으므로 120 MiB가 실제 메모리에 모두 쌓인다는 예측은 아니다. 조건을 바꾸어 UDP라면 receive queue가 차면 drop이 늘 수 있고 송신자는 자동으로 동일한 속도 제한을 받지 않는다.

## deadline은 단계별 timeout 합이 아니다

전체 request budget 100 ms를 header 10, body 20, work 45, response 15, reserve 10으로 나눴다고 하자. **deadline**은 작업이 끝나야 하는 절대 시각이고 timeout은 한 operation을 감시하는 mechanism이다. 각 단계에 100 ms relative timeout을 주면 최악 합계가 전체 budget을 넘는다.

시작+100 ms를 absolute deadline으로 두고 매 단계 monotonic clock으로 remaining을 계산한다. header 완료가 18 ms면 82 ms가 남고 DB budget은 min(45, remaining-reserve)로 정한다. timeout CQE와 대상 CQE가 race하므로 둘의 terminal 결과 전 buffer와 connection context를 free하지 않는다.

### 문제 7: 단계 지연 뒤 남은 예산

100 ms deadline에서 header 18 ms, body 27 ms를 썼고 reserve 10 ms가 필요하다. work와 send에 쓸 수 있는 합계와 원래 work 45+send 15 계획의 가능성을 계산하라.

elapsed는 45 ms, remaining은 55 ms다. reserve를 빼면 45 ms만 work+send에 쓸 수 있다. 원래 계획 60 ms는 15 ms 초과하므로 그대로 실행하면 deadline 위험이 있다. work budget 축소, 조기 실패, 품질 저하 같은 정책이 필요하다. 조건을 바꾸어 timeout cancellation이 즉시 device work를 멈추지 않는다면 deadline 뒤에도 resource가 소비될 수 있어 late completion을 정리해야 한다.

## PMU, tracepoint와 per-CPU 관찰의 경계

**PMU(Performance Monitoring Unit, 성능 감시 장치)**는 CPU hardware counter로 cycle, instruction, cache miss 같은 event를 센다. kernel perf subsystem이 예약·multiplex하고 process·CPU 범위로 읽는다. counter는 packet 의미를 모르며 multiplex·sampling overhead와 hardware 지원 차이가 있다.

**tracepoint(추적 지점)**는 kernel 개발자가 정의한 event hook과 형식이다. function address에 직접 기대는 kprobe보다 안정적인 관찰 지점이 될 수 있지만 tracepoint 존재와 field는 kernel에서 확인한다. tracepoint event는 per-CPU ring buffer에 기록될 수 있고 consumer가 느리면 overwrite·lost event가 생길 수 있다.

eBPF는 tracepoint, XDP, tc 등 서로 다른 hook에 attach할 수 있다. BPF map이 per-CPU 형식이면 update 경쟁을 줄이지만 userspace가 CPU별 counter를 합쳐야 전체값이 된다. flow·IP·payload 같은 high-cardinality와 민감 data를 무제한 수집하지 않는다.

### 문제 8: PMU와 tracepoint가 답하는 질문

packet 지연이 늘었을 때 PMU cache-miss 상승과 net tracepoint queue event가 각각 무엇을 말하며 무엇을 못 말하는가?

PMU는 관측 CPU에서 cache miss가 늘었다는 hardware 실행 특성을 보여 주지만 어느 connection packet인지 직접 말하지 않는다. tracepoint는 정의된 network event와 skb·device·queue 단서를 줄 수 있지만 trace buffer loss와 attach overhead가 있고 application request ID가 없을 수 있다. 두 값을 같은 timestamp·CPU·cgroup과 application trace에 연결한다. 조건을 바꾸어 PMU가 multiplex됐다면 scaled count의 오차를 고려하고, tracepoint가 없는 kernel이면 지원되는 다른 stable hook을 선택한다.

## packet 한 개를 TX까지 시간 순서로 연결한다

RX frame은 NIC queue에 도착해 DMA로 host buffer에 기록된다. interrupt가 NAPI를 schedule하고 poll이 descriptor를 회수한다. RSS가 hardware queue를, 설정됐다면 RPS가 상위 처리 CPU를 고른다. XDP hook이 있으면 skb 전 결정을 내리고, 통과한 packet은 skb와 Ethernet/IP/TCP stack을 지나 socket receive queue로 간다. epoll readiness 뒤 recv copy 또는 io_uring completion으로 application buffer에 도착한다. parser가 message를 복원하고 handler가 결과를 만든다.

TX에서는 send가 socket send queue에 byte를 넣고 TCP가 segment와 skb를 만든다. qdisc와 tc egress를 지나 driver TX queue와 NIC로 제출된다. TX completion은 DMA buffer를 반환할 수 있고 transport ACK는 remote kernel 수신을 반영한다. 이 경로에서 data copy, CPU context 이동, queue wait를 따로 잰다.

Linux 공식 문서에 따르면 RSS/RPS/XPS는 지원·설정 조건이 있고 RPS는 compile돼 있어도 rps_cpus가 0이면 비활성이다. XDP mode, zero-copy, multishot, BPF hook도 kernel·driver·NIC·권한에 따라 달라진다. 기능 이름을 보았다는 이유로 활성·offload·무복사를 주장하지 않는다.


## 지연을 copy·전환·queue 대기로 분해한다

교육용 packet 한 개의 RX 지연이 90 µs라고 하자. DMA 8, NAPI가 실행되기 전 CPU backlog 대기 20, driver·stack 처리 22, socket queue에서 application이 읽을 때까지 30, userspace copy 10 µs라면 합은 \(8+20+22+30+10=90\)이다. 이 중 DMA는 device 전송, 20과 30은 queue wait, 22는 kernel CPU 실행, 10은 copy CPU 작업이다. 총합만 줄이면 어느 resource를 바꿀지 알 수 없다.

NAPI budget이 소진돼 다음 poll로 밀렸다면 CPU 사용률이 높지 않아도 packet은 queue에서 기다릴 수 있다. 반대로 userspace copy가 크면 PMU cycle·cache miss와 memory bandwidth가 늘 수 있다. RPS로 CPU를 옮기면 source CPU backlog는 줄지만 IPI와 cache 이동이 추가된다. 각 최적화는 다른 항을 바꾼다.

### 추가 풀이: queue counter와 application latency 연결

RX queue 0에서 1초 동안 packet 100,000개가 도착하고 NAPI가 98,000개를 처리했으며 drop 2,000개가 증가했다. application p99도 같은 초에 2 ms에서 20 ms로 올랐다. 처리율 차이와 관측 한계를 설명하라.

도착과 처리 차이는 2,000 packet/s이고 drop 증가와 수치가 맞아 queue capacity 초과 가설을 지지한다. 그러나 application p99 상승 전체가 그 drop 때문이라는 증명은 아니다. retransmission, 다른 queue, CPU migration, cgroup pressure를 함께 본다. 조건을 바꾸어 drop은 queue 0인데 application flow는 RSS로 queue 3에만 있었다면 직접 귀속이 약하다. flow hash, queue, IRQ CPU와 socket을 연결해야 한다.

### 추가 풀이: per-CPU counter를 그대로 비교하면 생기는 오류

CPU 0의 BPF per-CPU map 값 900, CPU 1의 값 100을 보고 CPU 0이 전체 packet의 90%를 처리했다고 하자. 두 값의 시작 시각과 online CPU 집합이 같고 event 정의가 동일할 때만 합 1000 중 90%라는 계산이 성립한다. CPU hotplug, map reset, lost event, RPS 이동이 있으면 기간을 맞춰야 한다. 조건을 바꾸어 sample 기반 PMU 값이라면 packet count가 아니라 sampled hardware event이므로 같은 비율 해석을 적용하지 않는다.

## feature 이름과 실제 활성 상태를 세 단계로 확인한다

첫째 kernel build와 version이 interface를 제공하는지, 둘째 NIC·driver가 mode를 지원하는지, 셋째 현재 설정과 program attach가 실제 활성인지 나눈다. RPS는 CONFIG_RPS가 있어도 rps_cpus가 0이면 비활성이고, XDP는 generic과 native·offload의 비용 경계가 다르며, zero-copy는 opcode와 memory registration·notification 조건이 맞아야 한다. 관찰 결과에는 interface 존재, 설정값, packet counter라는 서로 다른 증거를 적는다.

## 공식 근거

- [Linux NAPI](https://docs.kernel.org/networking/napi.html)
- [Linux networking scaling: RSS, RPS, RFS, XPS](https://docs.kernel.org/networking/scaling.html)
- [Linux BPF documentation](https://docs.kernel.org/bpf/index.html)
- [Linux tracepoints](https://docs.kernel.org/trace/tracepoints.html)
- [Linux perf ring buffer](https://docs.kernel.org/userspace-api/perf_ring_buffer.html)
- [epoll(7)](https://man7.org/linux/man-pages/man7/epoll.7.html)

[이 책 목차](README.md) · [이전: io_uring ordering, error와 fsync](11-io-uring-ordering-errors-and-fsync.md) · [다음: Container, Kubernetes, GPU와 RAN](13-containers-kubernetes-gpu-and-ran.md)
