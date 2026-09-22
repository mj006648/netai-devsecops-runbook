# 06. eBPF·XDP·TC: 커널 안에서 안전하게 작은 프로그램을 실행하기

[이전: Linux 패킷 경로](05-linux-packet-path.md) · 다음: [Kubernetes CNI와 Cilium](07-kubernetes-cni-cilium.md)

근거 확인일: **2026-09-22**.

범위: 이 장은 eBPF를 처음 보는 독자가 "커널 모듈보다 제한된 작은 프로그램", "packet path의 여러 hook", "Cilium datapath의 재료"를 구분하도록 만든다. 실제 eBPF program을 attach하지 않는다. 모든 예시는 읽기용 pseudo code, 상태 추적, 산술 예시다.

## 1. BPF는 무엇에서 출발했는가

BPF는 역사적으로 Berkeley Packet Filter에서 출발했다.
처음 목적은 packet capture 도구가 모든 packet을 user space로 복사하지 않고, kernel 쪽에서 필요한 packet만 고르게 하는 것이었다.
예를 들어 `tcp port 80` 같은 filter를 kernel에서 먼저 평가하면, 필요 없는 packet을 user space로 올리지 않아도 된다.
이 초기 형태를 cBPF(classic BPF, 고전 BPF)라고 부른다.

현대 Linux 문서에서는 eBPF를 그냥 BPF라고도 부른다.
공식 BPF ISA 문서는 BPF가 packet filtering을 넘어섰기 때문에 현재는 약어 풀이보다 독립된 이름처럼 쓰인다고 설명한다.
eBPF(extended BPF, 확장 BPF)는 작은 명령어 집합, verifier, helper, map, attach point를 조합해 kernel 안의 정해진 위치에서 짧은 program을 실행한다.

여기서 "kernel 안에서 실행"이라는 말은 위험하다.
eBPF는 kernel module처럼 아무 kernel C 코드를 넣는 구조가 아니다.
program type마다 볼 수 있는 context가 다르고, 호출 가능한 helper가 다르며, verifier가 받아들이는 memory access와 control flow 안에서만 동작한다.
이 제한 때문에 운영 도구, 네트워크 정책, tracing, CNI datapath에 널리 쓰일 수 있다.

## 2. eBPF의 기본 부품을 한국어로 풀기

| 부품 | 풀네임·쉬운 뜻 | 왜 필요한가 |
|---|---|---|
| bytecode | 바이트코드. CPU 기계어가 아니라 BPF VM이 이해하는 작은 명령 | verifier가 검사하고 JIT가 native instruction으로 바꿀 수 있게 한다 |
| register | 레지스터. program이 계산할 때 쓰는 작은 작업 칸 | packet pointer, map value pointer, scalar 값을 추적한다 |
| helper | 헬퍼 함수. kernel이 허용한 내장 함수 | 시간 조회, map 접근, redirect, packet 조정 같은 기능을 제한된 방식으로 제공한다 |
| map | 맵. kernel과 user space가 공유하는 key-value 저장소 | policy, counter, connection state, 설정값을 저장한다 |
| verifier | 검증기. load 전에 program 상태를 따라가며 안전성을 검사하는 kernel 구성 | 잘못된 pointer, 검증 불가능한 control flow, helper 인자 오류를 막는다 |
| JIT | Just-In-Time compiler. 확인된 bytecode를 CPU native instruction으로 바꾸는 단계 | 매 packet마다 interpreter 비용을 줄인다 |
| BTF | BPF Type Format. type/debug metadata | CO-RE, verifier log, pretty print, kernel type 접근을 돕는다 |
| CO-RE | Compile Once - Run Everywhere. 한 번 compile한 object가 여러 kernel layout에 맞도록 relocation하는 방식 | kernel 구조체 field offset 차이를 일부 흡수한다 |
| loader | 적재기. object를 읽고 map 생성, relocation, load, attach를 수행하는 user space 프로그램 | source와 kernel 사이의 조립 담당자다 |

비유하면 eBPF program은 출입증에 적힌 방과 도구만 쓰는 작은 출장 직원이고, map은 운영자와 공유하는 장부이며, verifier는 출장 전 동선과 도구 사용법을 검사하는 보안팀이다. 비유의 한계는 verifier가 사람처럼 의도를 읽지 않고 register type, range, branch 상태를 기계적으로 추적한다는 점이다.

## 3. 개발·실행 lifecycle: source에서 cleanup까지

실제 eBPF 시스템은 program 하나만으로 끝나지 않는다.
다음 순서를 한 번에 그려야 운영 사고를 피한다.

```text
source C/Rust front-end 생각
  → LLVM BPF backend가 BPF bytecode가 든 ELF object 생성
  → object 안에 program section, map definition, BTF, .BTF.ext CO-RE relocation 포함 가능
  → loader가 object를 열고 map을 만들거나 기존 pin map을 찾음
  → loader가 target kernel BTF를 읽어 CO-RE relocation 적용
  → loader가 BPF_PROG_LOAD로 verifier에게 program을 제출
  → verifier가 모든 path의 register·stack·pointer·helper 인자를 검사
  → 통과하면 kernel이 program fd를 돌려주고, JIT가 켜진 환경에서는 native code 생성 가능
  → loader가 attach point에 program을 붙이고 bpf_link fd 또는 legacy attach 상태를 얻음
  → program은 packet/event마다 실행되고 map·ringbuf·perf buffer로 state와 event를 남김
  → 운영자는 map snapshot, event stream, bpffs pin 상태, link 상태를 관찰
  → detach, unlink pin, fd close가 모두 정리되어야 object reference가 사라짐
```

source는 사람이 읽는 입력이다.
object는 kernel에 바로 넣을 수 있는 재료지만, 아직 실행 중인 program이 아니다.
loader는 object를 target kernel에 맞게 조정하고 `bpf()` syscall을 호출한다.
`BPF_PROG_LOAD`는 eBPF program을 verify하고 load해서 fd를 돌려주는 명령이다.
`BPF_MAP_CREATE`는 map fd를 만든다.
`BPF_LINK_CREATE`는 program을 어떤 hook에 붙이고 link fd를 돌려준다.

중요한 점은 map 생성과 program load와 attach가 서로 다른 단계라는 것이다.
map은 만들어졌지만 program load가 실패할 수 있다.
program load는 성공했지만 attach가 실패할 수 있다.
attach는 성공했지만 event reader가 늦어서 event가 유실될 수 있다.
그래서 문제를 볼 때 "eBPF가 안 된다"라고 뭉뚱그리지 말고 어느 단계인지 먼저 나눈다.

## 4. bytecode register: pointer와 scalar는 다르다

BPF ABI 문서는 BPF가 64-bit general purpose register 10개와 read-only frame pointer register를 갖는다고 설명한다.
R0는 helper return value와 program exit value에 쓰인다.
R1부터 R5는 helper 인자다.
R6부터 R9는 helper 호출 뒤에도 보존되는 callee-saved register다.
R10은 stack 접근에 쓰는 read-only frame pointer다.

verifier에게 register 값은 단순 숫자가 아니다.
어떤 register는 scalar value(스칼라 값, 일반 숫자)이고, 어떤 register는 pointer다.
pointer도 종류가 있다.
`PTR_TO_CTX`는 context pointer, `PTR_TO_PACKET`은 packet data pointer, `PTR_TO_PACKET_END`는 packet 끝 pointer, `PTR_TO_MAP_VALUE_OR_NULL`은 map lookup 결과처럼 null일 수도 있는 pointer다.

이 구분이 왜 중요할까.
숫자끼리 더하면 숫자다.
하지만 pointer 둘을 더하면 의미 있는 주소가 아니다.
verifier는 이런 연산을 pointer로 인정하지 않는다.
map lookup 결과도 null check를 하기 전에는 map value pointer로 바로 읽을 수 없다.
packet pointer는 data_end와 비교해 안전한 범위를 증명해야 한다.

```text
좋은 직관: R3=data, R4=data_end, R5=R3+14, if R5>R4 then too_short.
fall-through에서는 R3에서 14 bytes 접근 가능하다고 증명된다.
나쁜 직관: R3이 packet 시작처럼 보이니 그냥 R3+12에서 2 bytes 읽자.
verifier에게는 아직 14 bytes가 있다는 증명이 없다.
```

verifier는 사람의 의도를 믿지 않는다.
명령어와 branch 조건이 만드는 register state만 믿는다.
그래서 eBPF 개발자는 "사람에게 안전한 코드"보다 "verifier가 증명할 수 있는 코드"를 써야 한다.

## 5. verifier control-flow toy: packet 길이 12와 14

Ethernet header는 14 bytes다.
처음 두 MAC 주소 12 bytes와 EtherType 2 bytes를 합친 크기다.
`eth->h_proto`를 읽으려면 offset 12와 13, 즉 2 bytes를 읽어야 하므로 packet 시작부터 최소 14 bytes가 필요하다.

다음은 실행 가능한 C가 아니라 verifier 사고방식을 설명하는 pseudo state다.

```text
초기:
R3 = data       // PTR_TO_PACKET, 안전 범위 r=0
R4 = data_end   // PTR_TO_PACKET_END
R5 = R3
R5 += 14
if R5 > R4 goto too_short
fall-through에서만 R3의 안전 범위 r=14로 인정
load16 R0 = *(u16 *)(R3 + 12)
```

packet 길이가 12 bytes라면 `data + 14 > data_end`가 참이다.
program은 `too_short` branch로 가야 하고 `R3 + 12`에서 2 bytes를 읽으면 안 된다.
offset 12의 첫 byte조차 packet 끝과 같거나 밖일 수 있다.

packet 길이가 14 bytes라면 `data + 14 > data_end`가 거짓이다.
fall-through에서는 `[data, data+14)`가 안전 범위다.
`R3 + 12`에서 2 bytes를 읽으면 `[data+12, data+14)`이므로 안전하다.
이때 `data+14` 자체는 마지막 byte가 아니라 끝 경계다.
C의 half-open interval처럼 시작은 포함하고 끝은 포함하지 않는다고 보면 된다.

| packet 길이 | `data+14 > data_end` | EtherType 읽기 | 이유 |
|---:|---|---|---|
| 12 | 참 | 불가 | 14 bytes 증명 실패 |
| 13 | 참 | 불가 | offset 13 byte가 없음 |
| 14 | 거짓 | 가능 | bytes 12와 13이 범위 안 |
| 60 | 거짓 | 가능 | Ethernet 최소 frame 수준에서도 14 bytes는 있음 |

이 작은 예제가 eBPF verifier의 핵심이다.
검증은 runtime packet 하나를 미리 아는 것이 아니라, 가능한 branch마다 register state를 좁혀 간다.
조건문 뒤에서 verifier가 아는 정보가 달라진다.

## 6. helper 호출 뒤 pointer 증명은 사라질 수 있다

일부 helper는 packet buffer를 바꿀 수 있다.
예를 들어 `bpf_xdp_adjust_head()`는 XDP packet의 data pointer를 앞뒤로 움직여 header를 제거하거나 추가하는 데 쓰인다.
이런 helper 뒤에는 이전에 증명한 packet pointer 범위를 다시 써서는 안 된다.
packet 시작과 끝이 바뀌었을 수 있기 때문이다.

```text
1. data, data_end를 읽는다.
2. data + 14 <= data_end를 확인한다.
3. eth pointer로 Ethernet header를 읽는다.
4. bpf_xdp_adjust_head(ctx, 4) 같은 packet 변경 helper를 호출한다.
5. 이전 eth pointer와 이전 data_end 증명은 폐기해야 한다.
6. ctx에서 data, data_end를 다시 읽고 bounds check를 다시 한다.
```

이 규칙은 초보자에게 까다롭다.
사람 눈에는 "방금 확인했는데 왜 또 확인하지?"처럼 보인다.
하지만 verifier 관점에서는 helper가 packet buffer를 옮겼을 수 있으므로, 과거 pointer state는 더 이상 현재 packet을 증명하지 못한다.

이 원리는 TC 쪽 helper에도 비슷하게 나타난다.
skb data를 바꾸거나 linearize할 수 있는 helper 뒤에는 이전 direct packet access 증명을 다시 세워야 한다.
정확한 helper별 규칙은 program type과 helper 정의를 확인한다.

## 7. XDP와 TC attach point

attach point는 program이 붙는 위치다.
같은 eBPF instruction이라도 어디에 붙느냐에 따라 context, helper, return code, 성능 의미가 달라진다.

| attach point | 위치 | 장점 | 한계 |
|---|---|---|---|
| XDP native | driver RX path의 매우 이른 지점 | skb 생성 전 early drop/redirect에 유리 | driver 지원과 context 제약이 큼 |
| XDP generic | native 미지원 때 stack에서 XDP 동작을 흉내 | 개발·호환성 확인에 유용 | native XDP 성능·driver 의미와 다름 |
| XDP offload | NIC hardware가 지원하면 NIC 쪽 실행 | host CPU 이전 처리 가능 | NIC·driver·program 기능 제약이 큼 |
| TC ingress | skb가 만들어진 뒤 netdevice ingress qdisc 근처 | skb metadata와 Linux network stack 문맥 활용 | XDP보다 늦은 지점 |
| TC egress | netdevice egress 쪽 | outbound policy, mark, redirect | qdisc, offload, driver와 함께 해석해야 함 |
| tracepoint | kernel에 미리 정의된 trace 위치 | 관찰 지점이 비교적 안정적 | enforcement보다 관찰에 적합 |
| kprobe/kretprobe | kernel function 진입·반환 | 깊은 디버깅 | kernel symbol과 구현 변화에 취약 |
| uprobe/uretprobe | user-space function 진입·반환 | app/library tracing | binary, symbol, ASLR, version 영향을 받음 |

XDP가 항상 좋은 것은 아니다.
XDP는 빠르지만 packet이 아직 skb로 올라오기 전이라 Linux stack의 풍부한 문맥을 덜 본다.
TC는 늦지만 skb 기반 정보와 qdisc 경로를 활용할 수 있다.
policy가 L7 proxy, conntrack, socket 의미론에 기대면 XDP만으로 충분하지 않을 수 있다.

## 8. XDP return code의 실제 의미

XDP program은 return code로 packet 운명을 말한다.
이 값은 단순 enum이 아니라 driver와 XDP core가 해석하는 행동이다.

| return | 쉬운 뜻 | 실제 의미 |
|---|---|---|
| `XDP_PASS` | 통과 | packet을 일반 kernel networking stack으로 넘긴다 |
| `XDP_DROP` | 폐기 | packet을 버린다. 상위 stack에는 보이지 않는다 |
| `XDP_TX` | 되돌려 보내기 | 받은 같은 interface로 다시 전송하려고 한다 |
| `XDP_REDIRECT` | 다른 대상으로 넘기기 | helper가 미리 지정한 devmap/cpumap/xskmap 등 대상으로 enqueue한다 |
| `XDP_ABORTED` | 비정상 종료 | program 오류 성격의 action이며 보통 exception tracepoint 관찰 대상이다 |

`XDP_REDIRECT`는 자동 L3 routing이 아니다.
program이 `bpf_redirect()` 또는 `bpf_redirect_map()` 같은 helper로 redirect target 정보를 설정하고, return code로 `XDP_REDIRECT`를 돌려줘야 한다.
그 뒤 driver 쪽 `xdp_do_redirect()`와 NAPI poll loop 끝의 flush 과정이 redirect를 완성한다.
즉 redirect는 "목적지 IP를 보고 Linux routing table이 알아서 처리"라는 의미가 아니다.
service policy, L2 rewrite, map target, device support, non-linear frame 지원 여부를 별도로 봐야 한다.

`XDP_TX`도 "라우터처럼 반대편으로 전달"이 아니다.
받은 interface로 다시 내보내는 동작이다.
load balancer나 echo 같은 특수 경우에는 유용하지만, 일반 routing과 같은 의미로 외우면 안 된다.

## 9. map lifetime, fd, pin, link, cleanup

BPF object는 file descriptor(fd, 파일 디스크립터)와 reference로 살아 있다.
`BPF_MAP_CREATE`로 map을 만들면 map fd가 생긴다.
`BPF_PROG_LOAD`로 program을 load하면 program fd가 생긴다.
fd를 닫으면 reference 하나가 줄어든다.
하지만 fd를 닫았다고 항상 object가 즉시 사라지는 것은 아니다.

```text
map fd 생성
  → program instruction이 map을 참조하도록 load됨
  → loader가 map fd를 닫음
  → loaded program이 map reference를 잡고 있으면 map은 계속 존재
  → program detach/unload, pin 제거, 남은 fd close 뒤에야 해제 가능
```

bpffs pin은 filesystem path가 object reference를 잡게 하는 방식이다.
`BPF_OBJ_PIN`으로 pin하면 process가 종료되어도 object가 남을 수 있다.
`BPF_OBJ_GET`으로 다시 fd를 열 수 있다.
편리하지만 stale map이나 stale program이 남아 새 agent와 충돌할 수 있다.

bpf_link는 attach 자체를 fd로 관리하는 방식이다.
`BPF_LINK_CREATE`는 program을 target hook에 붙이고 link fd를 돌려준다.
link fd를 close하거나 pin하지 않은 link가 사라지면 attach도 해제될 수 있다.
`BPF_LINK_DETACH`는 link fd가 가리키는 attachment를 강제로 detach한다.
legacy attach 방식은 attach point마다 detach 방식이 다를 수 있으므로, 운영 문서에는 "이 object를 누가 붙잡고 있는가"를 program, map, link, pin으로 나눠 기록한다.

정리할 때는 loader process fd, bpffs pin, bpf_link fd 또는 legacy attach, loaded program의 map reference, 다른 process가 `dup`·fork·unix socket으로 받은 fd를 모두 확인한다.

## 10. map concurrency: N=2 CPU counter 예시

map은 kernel과 user space가 공유하는 저장소지만, 자동으로 모든 race를 해결하지 않는다.
두 CPU가 같은 hash map value의 counter를 read-modify-write하면 lost update가 생길 수 있다.

```text
초기 counter = 0
CPU0: value를 읽음 → 0
CPU1: value를 읽음 → 0
CPU0: 0 + 1을 씀 → 1
CPU1: 0 + 1을 씀 → 1
기대한 값: 2
실제 값: 1
```

이 문제를 피하는 대표 방법은 세 가지다.
첫째, atomic add를 사용한다.
둘째, per-CPU map을 사용해 CPU마다 별도 counter를 두고 user space에서 합산한다.
셋째, value 안의 spin lock 같은 동기화 수단을 쓴다.
어느 쪽이 맞는지는 update 빈도, read 빈도, 정확도 요구, CPU 수에 따라 달라진다.

per-CPU counter snapshot도 완벽한 한 시점의 사진은 아니다.
user space가 CPU0 값을 읽고 CPU1 값을 읽는 사이에도 packet은 들어온다.
그래서 "대략적인 누적 통계"에는 좋지만, 과금이나 보안 판정처럼 정확한 transaction 경계가 필요한 곳에는 설계를 더 세밀하게 해야 한다.

```text
per-CPU map 예시 snapshot:
CPU0 counter = 10
CPU1 counter = 7
user space 합계 = 17

그 직후 CPU1에 packet 3개가 들어오면 kernel 상태는 20이지만,
방금 출력한 snapshot은 17이다.
```

## 11. ordinary hash와 LRU hash의 capacity 의미

ordinary hash map은 `max_entries`가 꽉 찬 상태에서 새 key를 추가하려 하면 update가 실패할 수 있다.
공식 syscall 문서는 `BPF_MAP_UPDATE_ELEM`이 `E2BIG`을 낼 수 있고, 그 뜻을 map element 수가 creation 때 지정한 `max_entries` 한계에 도달한 것이라고 설명한다.
이미 존재하는 key를 업데이트하는 것과 새 key를 추가하는 것은 다르다.

LRU hash map은 capacity에 도달했을 때 오래된 entry를 evict하려고 시도할 수 있다.
따라서 "hash update failure or eviction"처럼 뭉뚱그리면 틀릴 수 있다.
ordinary hash의 새 key 추가는 실패가 핵심이고, LRU hash는 eviction 정책이 핵심이다.
물론 LRU map도 메모리 부족, flag, lock contention, 구현 세부 조건 때문에 update가 항상 성공한다고 보장하지 않는다.

| map type | capacity 도달 시 일반적 해석 | 운영상 질문 |
|---|---|---|
| ordinary hash | 새 key 추가가 `E2BIG` 등으로 실패할 수 있음 | cardinality 제한을 넘었는가 |
| LRU hash | 오래된 entry eviction을 시도할 수 있음 | 사라져도 되는 state인가 |
| per-CPU hash | CPU별 value 저장으로 memory 사용이 커짐 | CPU 수 × value size × entries가 감당 가능한가 |
| array | key 범위가 index로 고정됨 | sparse key에 맞는 구조인가 |
| ringbuf | lookup/update/delete map이 아니라 event buffer 성격 | reader가 늦을 때 event loss를 어떻게 볼 것인가 |

connection state를 LRU map에 넣으면 capacity pressure 때 오래된 connection이 사라질 수 있다.
그것이 괜찮은 cache인지, 사라지면 policy가 흔들리는 state인지 구분해야 한다.
보안 정책의 allow/deny 핵심 상태라면 eviction이 곧 정책 변화가 될 수 있다.

## 12. BTF와 CO-RE: field offset 숫자 예시

BTF(BPF Type Format)는 type 정보를 담는다.
CO-RE(Compile Once - Run Everywhere)는 BPF object 안의 relocation 정보와 target kernel의 BTF를 비교해 field offset 같은 값을 load time에 고친다.
libbpf 문서는 running kernel의 BTF와 object의 BTF relocation 정보를 맞춰 필요한 offset을 조정한다고 설명한다.

가상의 구조체 layout을 보자.

```text
버전 A의 task_like:
offset 0: state     8 bytes
offset 8: pid       4 bytes
offset 12: padding  4 bytes

a->pid offset = 8

버전 B의 task_like:
offset 0: state      8 bytes
offset 8: namespace  8 bytes
offset 16: pid       4 bytes

b->pid offset = 16
```

CO-RE 없이 object가 `pid`를 offset 8에서 읽도록 박혀 있으면 버전 B에서 namespace 일부를 pid처럼 읽을 수 있다.
CO-RE relocation이 있으면 loader는 target BTF를 보고 `pid` field가 offset 16에 있음을 찾아 instruction의 offset field를 고칠 수 있다.

하지만 CO-RE는 의미가 바뀐 field를 고쳐 주지 않는다.
field 이름은 같지만 단위가 바뀌었거나, helper의 return 의미가 바뀌었거나, program type에서 필요한 helper가 target kernel에 없으면 offset만 고쳐도 맞는 program이 되지 않는다.
field가 사라졌거나 권한·program type·helper availability가 맞지 않아도 실패할 수 있다.
CO-RE는 구조체 배치 차이를 줄이는 도구이지, 모든 kernel version 차이를 없애는 마법이 아니다.

## 13. tracing event lifecycle: clock, dropped event, latency

tracing eBPF는 관찰용 program을 hook에 붙이고 event를 user space로 보낸다.
흔한 경로는 tracepoint/kprobe/uprobe에서 event record를 만들고, perf event buffer나 BPF ring buffer에 넣고, user space reader가 epoll 또는 polling으로 읽는 구조다.
ring buffer 문서는 variable-length record, 공간 부족 시 reservation 실패, memory-mappable data area, epoll notification 같은 특성을 설명한다.

```text
kernel event 발생
  → eBPF tracing program 실행
  → timestamp와 key fields를 record에 기록
  → ringbuf/perf buffer에 submit
  → user space reader가 read/poll
  → decoder가 span, pid, cpu, comm, latency로 출력
```

clock 선택도 중요하다.
`bpf_ktime_get_ns()` 계열 시간은 보통 boot 이후 monotonic 성격의 nanosecond timestamp로 latency 계산에 쓰인다.
wall clock과 직접 섞으면 NTP 조정, timezone, clock source 차이 때문에 해석이 꼬일 수 있다.
latency는 같은 clock domain에서 시작과 끝을 빼야 한다.

두 hook으로 syscall latency를 잰다고 하자.

```text
tracepoint/syscalls/sys_enter_read:
  key = pid/tid
  start_ns[key] = now_ns

tracepoint/syscalls/sys_exit_read:
  end = now_ns
  start = start_ns[key]
  latency = end - start
  event(latency, return_value)를 ringbuf로 submit
  start_ns[key] 삭제
```

sample 숫자:

```text
enter timestamp = 1,000,000,000 ns
exit timestamp  = 1,003,500,000 ns
latency         = 3,500,000 ns = 3.5 ms
```

event가 없다는 것은 사건이 없었다는 뜻이 아니다.
start event는 기록됐지만 exit event 전에 process가 사라졌을 수 있다.
map entry가 evict됐을 수 있다.
ringbuf reserve가 실패했을 수 있다.
reader가 늦어서 perf buffer lost event가 생겼을 수 있다.
attach scope 밖의 CPU, cgroup, namespace, binary version에서 사건이 일어났을 수도 있다.
관찰 도구는 event count와 함께 lost event count, reader health, map pressure, attach scope를 보여줘야 한다.

## 14. eBPF policy 안전성 test matrix

네트워크 policy program은 happy path만 보면 안 된다.
특히 XDP/TC parser는 packet이 항상 예쁜 Ethernet/IPv4/TCP라고 가정하면 안 된다.
다음 matrix는 실제 attach 없이 설계 리뷰와 test case 설계에 쓰는 표다.

| case | 넣어야 할 packet 모양 | 확인할 것 |
|---|---|---|
| truncated Ethernet | 0~13 bytes | Ethernet header 읽기 전에 drop/pass branch가 나는가 |
| VLAN 1개 | Ethernet + 802.1Q tag | EtherType 위치를 14로 고정하지 않는가 |
| VLAN 2개 QinQ | outer/inner VLAN | 지원하지 않으면 안전하게 pass/drop하는가 |
| IPv4 IHL=5 | options 없는 기본 IPv4 | L4 header offset이 20 bytes로 계산되는가 |
| IPv4 IHL>5 | IP options 있음 | IHL × 4 계산과 bounds check가 있는가 |
| IPv4 fragment | non-first fragment | L4 port가 없을 수 있음을 처리하는가 |
| IPv6 기본 | extension header 없음 | IPv4와 header 길이를 섞지 않는가 |
| IPv6 extension headers | hop-by-hop, routing, fragment | bounded loop 또는 제한된 parse depth가 있는가 |
| non-linear skb | skb fragment 포함 | TC에서 direct access 가능한 headlen만 믿지 않는가 |
| XDP non-linear frame | driver 지원 차이 | redirect/transmit 지원 여부를 확인하는가 |
| checksum/offload | NIC offload 상태 | program이 수정한 header의 checksum 책임을 아는가 |
| GRO/GSO 영향 | 큰 skb 또는 합쳐진 skb | TC hook에서 packet 단위 해석이 기대와 맞는가 |
| unknown EtherType | ARP/LLDP/기타 | 기본 action이 정책 의도와 맞는가 |
| map full | ordinary hash capacity 초과 | 새 key 실패와 fallback action이 정의됐는가 |
| event buffer full | reader 정지 | event loss를 metric으로 드러내는가 |

safe policy의 기본은 "모르면 통과" 또는 "모르면 차단" 중 하나를 명확히 고르는 것이다.
보안 정책은 fail closed를 원할 수 있고, 관찰 program은 fail open을 원할 수 있다.
둘을 섞으면 장애 때 왜 packet이 사라졌는지 설명하기 어렵다.

## 15. observe, enforcement, 권한을 분리한다

관찰(observe)은 counter 증가, latency event, stack trace처럼 무엇이 일어났는지 보는 일이다. 집행(enforcement)은 `XDP_DROP`, TC redirect, cgroup connect deny처럼 실제 트래픽을 허용·차단·redirect·rewrite하는 일이다. 관찰 실패는 데이터 누락과 오해로 끝날 수 있지만, 집행 실패는 실제 장애가 된다. Hubble이나 tracing event는 datapath의 한 지점에서 본 사실이므로 hook 위치, sampling, event loss, map pressure, user space reader 상태를 같이 본다.

이 표준화된 제한 모델 덕분에 eBPF는 kernel module보다 운영하기 쉬운 경우가 많지만, 절대 안전을 뜻하지는 않는다. verifier는 많은 memory safety 문제를 줄이지만 kernel bug, JIT bug, helper bug, 권한 오남용, 잘못된 정책, 과도한 map memory 사용까지 모두 없애지는 않는다. 누가 load했는지, 어떤 object와 kernel·driver 조합에서 검증했는지, rollback이 있는지 기록해야 한다.

BPF 작업은 강한 권한이 필요하다. Linux 배포판과 kernel 설정에 따라 `CAP_BPF`, `CAP_PERFMON`, `CAP_NET_ADMIN`, `CAP_SYS_ADMIN`, locked memory limit, LSM policy가 영향을 준다. 권한 오류는 program 논리 오류와 다르다.

## 16. Cilium eBPF는 마법이 아니라 구성된 정책과 map이다

Cilium은 eBPF를 사용해 service load balancing, policy enforcement, routing, masquerading, observability를 구현할 수 있다. 하지만 Cilium이 있다고 모든 packet이 자동으로 최적 경로를 타거나 모든 장애 원인이 eBPF map 하나로 보이는 것은 아니다. Cilium 동작은 agent 설정, Kubernetes Service/EndpointSlice/Pod/Node 정보, NetworkPolicy, BPF service/backend/policy/conntrack maps, kernel version, hook 선택, kube-proxy replacement 여부, NIC driver와 XDP mode, map capacity, event reader 상태가 함께 만든다.

Cilium 장애를 볼 때도 lifecycle을 나눈다. object가 load됐는가, attach됐는가, map state가 의도와 맞는가, packet이 해당 hook을 지나가는가, event가 유실되지 않는가, redirect target이 driver에서 지원되는가를 따로 확인한다.

## 17. 깊게 풀어보는 문제

**문제 1.** Ethernet header의 EtherType을 읽고 싶다. packet 길이가 13 bytes일 때 `data + 14 <= data_end` check 없이 `*(u16 *)(data + 12)`를 읽어도 되는가?
**해설:** 안 된다. 2 bytes load는 offset 12와 13을 모두 읽는다. 길이 13이면 유효 byte는 0부터 12까지라서 offset 13은 packet 밖이다. verifier는 `data + 14 <= data_end` 같은 증명이 없는 direct packet access를 거절해야 한다. 길이 14부터 `[data+12, data+14)` 범위가 안전하다.

**문제 2.** native XDP와 generic XDP가 모두 `XDP_DROP`을 돌려줄 수 있다면 성능 의미도 같다고 봐도 되는가?
**해설:** 아니다. native XDP는 driver RX path의 이른 지점에서 실행될 수 있고, generic XDP는 native 미지원 때 stack 쪽에서 XDP 의미를 흉내 내는 경로다. 같은 return code라도 실행 위치와 비용이 다르다. generic mode에서 기능 논리를 개발할 수는 있지만, native XDP의 PPS, CPU 사용량, driver redirect 동작을 그대로 증명하지는 못한다.

**문제 3.** ordinary hash map의 `max_entries=2`이고 key A, B가 이미 있다. 새 key C를 `BPF_ANY`로 넣으면 무엇을 예상해야 하는가? LRU hash라면 무엇이 달라지는가?
**해설:** ordinary hash에서는 새 element 수가 `max_entries`를 넘으므로 update가 `E2BIG` 같은 오류로 실패할 수 있다. 기존 key A를 update하는 것과 새 key C를 추가하는 것은 다르다. LRU hash라면 capacity 도달 시 오래된 entry를 evict하려고 시도할 수 있다. 따라서 ordinary hash는 failure path를, LRU hash는 eviction되어도 되는 state인지를 설계해야 한다.

**문제 4.** 두 CPU가 같은 map value counter를 atomic 없이 증가한다. 초기값 0에서 두 packet이 동시에 들어오면 왜 결과가 1이 될 수 있는가?
**해설:** CPU0과 CPU1이 모두 0을 읽고, 각각 1을 계산한 뒤, 둘 다 1을 저장하면 마지막 저장 값이 1이다. 두 번 증가했지만 read-modify-write가 서로 덮어쓴 것이다. atomic add는 이 세 단계를 하나의 원자적 갱신으로 만들고, per-CPU map은 CPU별 counter를 나눠 contention을 줄인다. per-CPU 방식은 user space 합산 시 snapshot 경계를 별도로 해석해야 한다.

**문제 5.** CO-RE가 `pid` field offset을 버전 A의 8에서 버전 B의 16으로 고쳐 줄 수 있다. 그렇다면 field 의미가 바뀌어도 안전한가?
**해설:** 안전하다고 단정할 수 없다. CO-RE는 BTF와 relocation 정보로 field offset, size, existence 같은 구조적 차이를 다룬다. field 이름은 같지만 의미나 단위가 바뀌었거나, helper의 의미가 달라졌거나, program type에서 필요한 helper가 target kernel에 없으면 offset만 맞아도 정책은 틀릴 수 있다. CO-RE는 portability 도구이지 semantic compatibility 보증서가 아니다.

**문제 6.** syscall latency tracing에서 enter event는 기록했는데 exit event가 없다. syscall이 끝나지 않았다고 결론 내도 되는가?
**해설:** 바로 결론 내면 안 된다. exit hook이 attach scope 밖이었을 수 있고, process가 사라졌거나, start map entry가 evict됐거나, ringbuf/perf buffer가 가득 차 event가 drop됐을 수 있다. user space reader가 늦었거나 decoder가 실패했을 수도 있다. latency 도구는 start map 잔여 수, lost event count, reader lag, attach 대상, clock domain을 함께 보여줘야 한다.

## 18. 확인한 1차 자료

- Linux kernel BPF 문서: [overview](https://docs.kernel.org/bpf/index.html), [verifier](https://docs.kernel.org/bpf/verifier.html), [maps](https://docs.kernel.org/bpf/maps.html), [BTF](https://docs.kernel.org/bpf/btf.html), [syscall](https://docs.kernel.org/userspace-api/ebpf/syscall.html)
- Linux kernel BPF ABI/ISA와 CO-RE: [ABI register convention](https://docs.kernel.org/bpf/standardization/abi.html), [BPF instruction set](https://docs.kernel.org/bpf/standardization/instruction-set.html), [libbpf overview](https://docs.kernel.org/bpf/libbpf/libbpf_overview.html), [LLVM BPF relocations](https://docs.kernel.org/bpf/llvm_reloc.html)
- Linux kernel XDP/event 자료: [BPF redirect](https://docs.kernel.org/bpf/redirect.html), [BPF program run](https://docs.kernel.org/bpf/bpf_prog_run.html), [BPF ring buffer](https://docs.kernel.org/bpf/ringbuf.html)
- Cilium: [eBPF introduction](https://docs.cilium.io/en/stable/network/ebpf/intro/), [kube-proxy replacement](https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/)
