# 05. Linux 패킷 경로: socket에서 NIC와 다시 socket까지

[이전: TCP·UDP·QUIC·DNS·TLS 기초](04-dns-http-tls.md) · 다음: [eBPF·XDP·TC](06-ebpf-xdp-tc.md)

근거 확인일: **2026-09-22**.

범위: 이 장은 Linux 노드 한 대 안에서 패킷이 어떻게 움직이는지 설명한다. Kubernetes Pod, Cilium, eBPF는 뒤 장에서 다루며, 여기서는 먼저 Linux kernel의 일반 네트워크 데이터 경로를 잡는다. 실제 커널 버전, NIC 드라이버, offload 설정, namespace, netfilter/nftables ruleset, CNI 구현에 따라 세부 순서와 관측 위치는 달라질 수 있다.

핵심 질문은 하나다. **프로그램이 `send()`를 호출하면 byte가 어떤 kernel 객체와 queue를 지나 NIC로 나가고, 들어온 packet은 어떤 CPU 경로를 거쳐 `recv()`로 보이는가?**

## 1. 먼저 단어를 만든다

| 단어 | 뜻 | 왜 필요한가 |
| --- | --- | --- |
| socket | process가 네트워크 통신을 위해 여는 endpoint | 파일 fd처럼 `read/write/send/recv` API로 네트워크를 다루기 위해 |
| syscall | user space가 kernel에 요청하는 진입점 | 일반 프로그램이 NIC register와 kernel memory를 직접 만지지 못하게 하기 위해 |
| protocol stack | TCP, UDP, IP, routing, neighbor, qdisc 같은 계층 묶음 | 각 계층이 자기 책임만 처리하게 하기 위해 |
| skb, `struct sk_buff` | Linux 네트워크 stack에서 packet을 표현하는 metadata 구조 | packet data, header 위치, offload 상태, device 정보를 함께 운반하기 위해 |
| qdisc | queuing discipline. 송신 packet을 어떤 순서와 속도로 내보낼지 정하는 queue 계층 | shaping, scheduling, drop 정책을 적용하기 위해 |
| driver TX/RX ring | NIC와 driver가 descriptor를 주고받는 ring buffer | kernel memory와 NIC DMA 작업을 효율적으로 연결하기 위해 |
| DMA | Direct Memory Access. 장치가 CPU 대신 memory와 장치 사이 데이터를 옮기는 기능 | CPU가 모든 byte를 직접 복사하지 않게 하기 위해 |
| IRQ | interrupt request. 장치가 CPU에게 일이 생겼다고 알리는 신호 | packet 도착이나 송신 완료를 kernel이 알기 위해 |
| NAPI | Linux 네트워크 event 처리 방식. interrupt와 polling을 섞어 packet을 batch 처리한다 | 고속 packet에서 interrupt 폭주를 줄이기 위해 |

Linux kernel 문서는 `sk_buff`가 packet을 대표하는 주요 구조이며, 구조 자체는 metadata이고 packet data는 연결된 buffer에 있다고 설명한다. NAPI 문서는 장치가 interrupt로 host에 event를 알리고, 이후 NAPI poll이 packet을 처리하는 구조를 설명한다. [Linux skbuff 문서](https://docs.kernel.org/networking/skbuff.html), [Linux NAPI 문서](https://docs.kernel.org/networking/napi.html).

## 2. 송신 경로: `send()`에서 wire까지

가장 단순한 TCP 송신을 먼저 보자.

```text
user process
  → socket fd에 send()/write()
  → syscall 진입
  → TCP가 byte stream을 segment로 나눔
  → IP가 source/destination address와 route를 결정
  → neighbor/ARP 또는 NDP가 next-hop L2 address를 찾음
  → qdisc가 packet을 queue/schedule
  → NIC driver가 TX descriptor를 TX ring에 둠
  → NIC가 DMA로 packet data를 읽음
  → NIC가 frame을 wire로 전송
  → TX completion이 올라오고 skb 자원을 회수
```

`send()`가 반환했다고 해서 packet이 이미 wire에 올라갔다는 뜻은 아니다. 보통은 kernel이 socket buffer에 데이터를 받아들였거나 일부를 처리했다는 의미다. TCP는 byte stream이므로 application이 한 번 `send()`한 경계가 상대방 `recv()` 경계와 같다고 보장하지 않는다. TCP 표준은 TCP를 reliable ordered byte stream으로 정의한다. [RFC 9293](https://datatracker.ietf.org/doc/html/rfc9293).

UDP는 다르다. UDP는 datagram 단위이고, TCP처럼 stream 순서와 재전송을 제공하지 않는다. UDP header에는 source port, destination port, length, checksum이 있다. [RFC 768](https://datatracker.ietf.org/doc/html/rfc768). 하지만 UDP 위의 QUIC처럼 상위 계층이 reliability와 encryption을 구현할 수 있으므로 "UDP = 항상 단순하고 무책임"이라고 외우면 안 된다. [RFC 9000](https://datatracker.ietf.org/doc/html/rfc9000).

## 3. 수신 경로: wire에서 `recv()`까지

수신은 송신의 단순한 반대가 아니다. NIC가 먼저 packet을 memory에 넣고, CPU가 batch로 처리하는 경로가 중요하다.

```text
wire
  → NIC가 frame 수신
  → NIC가 RX ring descriptor를 보고 DMA로 memory buffer에 packet 저장
  → NIC가 IRQ 또는 interrupt moderation으로 CPU에 event 알림
  → driver interrupt handler가 NAPI poll을 schedule
  → NAPI poll이 RX ring에서 packet batch를 꺼냄
  → native XDP가 지원되는 driver라면 skb 생성 전에 xdp_buff에서 실행될 수 있음
  → XDP_PASS 또는 XDP 미사용이면 driver/kernel이 skb를 만들거나 buffer를 skb로 연결
  → generic XDP(XDP_SKB)는 driver native XDP가 아니라 skb 기반 receive path의 fallback으로 실행됨
  → TC ingress는 skb가 생긴 뒤 netdevice ingress 지점에서 실행될 수 있음
  → GRO, checksum 검증 상태, netfilter, routing 등이 적용될 수 있음
  → IP/TCP/UDP stack이 socket을 찾음
  → socket receive queue에 data가 들어감
  → user process가 recv()/read()로 data를 가져감
```

NAPI의 핵심은 packet마다 hard interrupt로 깊은 stack을 다 처리하지 않는다는 점이다. interrupt는 "일이 있다"고 알리고, NAPI poll이 budget 안에서 여러 packet을 처리한다. budget은 한 번에 처리할 RX packet 수를 제한해 한 NIC가 CPU를 끝없이 붙잡지 않게 한다. Linux NAPI 문서는 poll method가 budget만큼 RX packet을 처리하고, 완료되면 NAPI ownership을 반환한다고 설명한다.

XDP와 TC의 위치는 반드시 나누어 말해야 한다. **native XDP**는 driver RX path의 이른 지점에서 `skb` 생성 전에 실행될 수 있다. **generic XDP**, 또는 **XDP_SKB**는 driver native 지원이 없거나 명시적으로 선택했을 때 skb 기반 generic receive path에서 동작하는 fallback이다. **TC ingress**는 `skb`가 있는 netdevice ingress 경로에서 동작하므로 native XDP보다 늦은 관측 지점이다. 따라서 XDP drop counter, TC drop counter, tcpdump, socket receive queue는 같은 packet path의 서로 다른 지점을 본다.

CPU 관점에서 packet path를 보면 다음 세 비용이 크다.

1. packet을 memory에 두고 skb metadata를 만드는 비용
2. cache miss와 CPU core 이동 비용
3. interrupt, softirq, NAPI poll, socket wakeup 비용

그래서 NIC queue, RSS, interrupt affinity, NAPI, GRO/GSO 같은 기능은 성능 튜닝에서 함께 나온다. 단일 packet diagram만 보면 네트워크가 선과 NIC 문제처럼 보이지만, 실제 고속 네트워크 병목은 CPU scheduling과 memory locality에서 생길 수 있다.

## 4. skb는 packet 자체가 아니라 packet을 가리키는 작업표다

`skb`를 택배 상자라고 비유하면 절반만 맞다. packet data는 buffer에 있고, `skb`는 그 data가 어디부터 Ethernet header인지, 어디부터 IP header인지, checksum이 이미 계산됐는지, 어떤 device에서 왔는지 같은 metadata를 들고 다닌다.

```text
skb metadata
  ├─ data buffer 위치
  ├─ MAC/IP/TCP header offset
  ├─ packet length
  ├─ ingress/egress device
  ├─ checksum offload 상태
  ├─ segmentation offload 상태
  └─ qdisc, netfilter, routing에서 쓰는 부가 정보
```

캡처 도구가 보는 것은 이 경로 중 한 지점의 모습이다. 그래서 `tcpdump`에서 보이는 packet 크기나 checksum 상태가 wire 위의 최종 frame과 다를 수 있다. 특히 offload가 켜져 있으면 kernel은 "아직 NIC가 나중에 처리할 큰 packet"을 볼 수 있고, capture는 그 중간 상태를 찍을 수 있다.

## 5. GRO, GSO, checksum offload와 캡처 오해

| 기능 | 방향 | 하는 일 | 캡처에서 생기는 오해 |
| --- | --- | --- | --- |
| checksum offload | TX/RX | checksum 계산 또는 검증을 NIC에 맡김 | 송신 전 capture에서 checksum이 틀린 것처럼 보일 수 있음 |
| TSO/GSO | TX | 큰 TCP payload를 kernel/NIC가 나중에 MSS 단위로 나눔 | capture에 MTU보다 큰 packet처럼 보일 수 있음 |
| LRO/GRO | RX | 여러 작은 segment를 큰 skb로 합쳐 stack 비용을 줄임 | capture 위치에 따라 실제 wire packet보다 큰 덩어리로 보일 수 있음 |

Linux segmentation offload 문서는 TCP Segmentation Offload와 Generic Segmentation Offload처럼 큰 packet을 나중에 segment로 나누는 기능을 설명한다. [Linux segmentation offloads](https://docs.kernel.org/networking/segmentation-offloads.html).

중요한 운영 결론은 이렇다. **한 지점의 capture만 보고 MTU 위반, checksum 오류, 애플리케이션 message 크기를 단정하지 않는다.** sender host의 pre-offload capture, receiver host의 post-GRO capture, switch SPAN, NIC hardware capture는 서로 다른 사실을 보여 준다.

## 6. qdisc와 driver TX ring은 둘 다 queue지만 위치가 다르다

qdisc는 Linux network stack의 송신 queue 계층이다. traffic control, shaping, priority, drop 같은 정책이 이 근처에서 적용된다. driver TX ring은 NIC에게 줄 DMA descriptor queue다. qdisc는 "어떤 packet을 언제 driver로 줄까"를 다루고, TX ring은 "NIC가 어떤 memory buffer를 읽어 wire로 보낼까"를 다룬다.

```text
TCP/IP stack → qdisc → driver TX ring → NIC DMA → wire
```

qdisc가 비어 있어도 TX ring이나 NIC가 막힐 수 있고, TX ring이 여유 있어도 qdisc 정책이 packet을 지연시킬 수 있다. container traffic shaping, TC eBPF, rate limit, queue backlog를 볼 때 이 구분이 중요하다.

## 7. namespace, veth, bridge: 한 노드 안의 작은 네트워크

network namespace는 network device, route table, iptables/nftables ruleset 일부, socket namespace를 분리하는 Linux 기능이다. Pod는 보통 자기 network namespace를 가진다. veth pair는 양끝이 연결된 가상 Ethernet cable처럼 동작한다. 한쪽 끝을 Pod namespace에 두고, 다른 쪽 끝을 host namespace의 bridge나 CNI datapath에 연결할 수 있다.

```text
Pod netns                         host netns
  eth0 ── veth pair ── vethXYZ ── bridge/cni datapath ── host NIC
  route table                     route table, netfilter, qdisc, driver
```

bridge는 L2 switch처럼 MAC learning과 forwarding을 할 수 있다. 하지만 Kubernetes CNI가 항상 Linux bridge를 쓰는 것은 아니다. Cilium처럼 eBPF datapath를 쓰는 구현, routing 기반 구현, overlay 기반 구현이 있을 수 있다. 이 장의 bridge 그림은 기초 모델이다.

## 8. netfilter, conntrack, SNAT, DNAT trace

netfilter는 Linux packet filtering/NAT hook framework다. nftables는 ruleset을 표현하고 적용하는 현대적인 user-facing framework다. iptables를 쓰는 시스템도 있고, nftables backend를 쓰는 시스템도 있다. Kubernetes kube-proxy, CNI, cloud agent, admin rules가 어떤 방식으로 rules를 만들었는지는 실제 노드에서 확인해야 한다.

conntrack은 connection tracking이다. TCP connection, UDP flow 같은 통신 상태를 기억해 reply packet을 원래 translation과 연결한다. NAT에는 대표적으로 두 방향이 있다.

| NAT | 바뀌는 주소 | 예 |
| --- | --- | --- |
| DNAT | destination address/port | ClusterIP `10.96.0.10:53`을 실제 backend Pod IP로 바꿈 |
| SNAT | source address/port | Pod 사설 IP를 node IP로 바꿔 외부망으로 나감 |

synthetic request/reply를 trace해 보자.

```text
가정:
client Pod: 10.244.1.5:40000
Service ClusterIP: 10.96.0.80:80
backend Pod: 10.244.2.9:8080
node egress IP: 192.0.2.10
```

| 단계 | packet 5-tuple | 변화 |
| --- | --- | --- |
| 1. client가 보냄 | `10.244.1.5:40000 → 10.96.0.80:80 TCP` | Service IP로 요청 |
| 2. DNAT | `10.244.1.5:40000 → 10.244.2.9:8080 TCP` | destination이 backend로 바뀜 |
| 3. backend가 reply | `10.244.2.9:8080 → 10.244.1.5:40000 TCP` | conntrack은 원래 Service flow를 기억 |
| 4. reverse NAT | `10.96.0.80:80 → 10.244.1.5:40000 TCP` | client는 Service가 답한 것처럼 봄 |

외부 egress는 SNAT가 들어갈 수 있다.

| 단계 | packet 5-tuple | 변화 |
| --- | --- | --- |
| 1. Pod가 외부로 보냄 | `10.244.1.5:40000 → 198.51.100.20:443 TCP` | Pod source 유지 |
| 2. SNAT | `192.0.2.10:53001 → 198.51.100.20:443 TCP` | source가 node IP와 새 port로 바뀜 |
| 3. 외부 reply | `198.51.100.20:443 → 192.0.2.10:53001 TCP` | node로 돌아옴 |
| 4. reverse SNAT | `198.51.100.20:443 → 10.244.1.5:40000 TCP` | Pod socket이 받음 |

routing policy와 actual implementation은 다를 수 있다. 운영 문서에 "Pod CIDR은 routable"이라고 써 있어도 CNI가 overlay를 쓰거나, eBPF NAT를 쓰거나, cloud route table을 쓰거나, nftables SNAT를 쓸 수 있다. 설계 의도와 노드 datapath 증거를 분리해 기록한다.

## 9. 읽기 전용 관측 명령은 무엇을 답하는가

아래 명령은 운영 노드에서 실행하라는 절차가 아니다. 읽기 전용으로 어떤 질문에 답하는지 배우기 위한 목록이다. 권한, 보안 정책, 운영 시간, 개인정보 노출을 고려해야 한다.

```text
ss -tinp                  # socket 상태, TCP 정보
ip route                  # route lookup에 쓰이는 route table 요약
ip neigh                  # ARP/NDP neighbor cache
ip link                   # device, MTU, qdisc hint, state
nft list ruleset          # nftables ruleset. 민감 정보가 있을 수 있음
tc qdisc show dev eth0    # qdisc 상태
tc filter show dev eth0 ingress  # TC filter. eBPF attachment가 보일 수 있음
ethtool -k eth0           # offload feature 상태
tcpdump -i eth0 -nn       # packet capture. 운영망에서는 승인 필요
```

읽기 전용이어도 출력에는 IP, port, process, policy, service 이름이 들어갈 수 있다. 교재나 이슈에 붙일 때는 필요한 필드만 남긴다.

## 10. 연습 문제

1. `send()`가 반환하면 packet이 wire에 올라갔다고 말할 수 있는가?
2. RX packet 처리에서 NAPI가 필요한 이유는 무엇인가?
3. tcpdump에서 MTU보다 큰 TCP packet이 보였다. 실제 wire에 그렇게 나갔다고 단정할 수 있는가?
4. DNAT와 SNAT의 차이는 무엇인가?
5. 같은 Pod-to-Service 요청이라도 iptables, nftables, eBPF Cilium 구현에서 trace 위치가 달라질 수 있는 이유는 무엇인가?

**답:** ① 없다. kernel socket buffer나 stack 처리 성공일 수 있다. ② packet마다 interrupt로 끝까지 처리하면 고속 수신에서 CPU가 interrupt 처리에 압도되므로 polling/batching이 필요하다. ③ 없다. GSO/TSO/GRO/offload와 capture 위치를 확인해야 한다. ④ DNAT는 destination을, SNAT는 source를 바꾼다. ⑤ service translation과 policy enforcement가 어떤 hook/device/map에서 구현되는지 CNI와 설정마다 다르기 때문이다.

## 11. 확인한 1차 자료

- Linux kernel networking: [NAPI](https://docs.kernel.org/networking/napi.html), [sk_buff](https://docs.kernel.org/networking/skbuff.html), [segmentation offloads](https://docs.kernel.org/networking/segmentation-offloads.html)
- IETF: [IPv4 RFC 791](https://datatracker.ietf.org/doc/html/rfc791), [TCP RFC 9293](https://datatracker.ietf.org/doc/html/rfc9293), [UDP RFC 768](https://datatracker.ietf.org/doc/html/rfc768), [QUIC RFC 9000](https://datatracker.ietf.org/doc/html/rfc9000)
