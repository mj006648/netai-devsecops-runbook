# 09. 패킷을 끝까지 따라가는 종합 문제와 용어 사전

[학습 목차](README.md) · 이전: [진단·실습](08-troubleshooting-and-labs.md)

모든 주소·시간·장치 이름은 교육용이다. 문제를 먼저 풀고 해설을 읽는다. 외워서 맞힌 용어보다 **계산 과정, 패킷의 방향, 현재 관측 지점, 남아 있는 가정**을 더 중요하게 평가한다. 문서용 IPv4 주소의 용도는 [RFC 5737](https://www.rfc-editor.org/rfc/rfc5737.html)을 참고한다.

## 1. 같은 네트워크에 있는지 비트로 판정한다

**조건:** A는 `192.0.2.10/26`, B는 `192.0.2.50/26`, C는 `192.0.2.70/26`이다. 일반적인 broadcast 가능한 IPv4 subnet을 가정한다. 세 장치의 mask, network, broadcast, 일반적인 host 범위를 구하고 A가 B/C에 보낼 때 필요한 다음 홉을 설명하라.

**해설:** `/26`은 앞의 26비트가 네트워크 부분이라는 뜻이다. 32비트 중 host 부분은 6비트이므로 주소는 `2^6=64`개다. mask는 `255.255.255.192`이며 마지막 8비트는 `11000000`이다.

~~~text
A의 마지막 바이트: 10 = 00001010
mask 마지막 바이트:     11000000
AND 결과:               00000000 = 0

C의 마지막 바이트: 70 = 01000110
mask 마지막 바이트:     11000000
AND 결과:               01000000 = 64
~~~

따라서 A와 B는 `192.0.2.0/26`, C는 `192.0.2.64/26`이다. 첫 범위는 `.0`부터 `.63`, 일반 host 주소는 `.1`부터 `.62`, broadcast는 `.63`이다. 두 번째 범위는 `.64`부터 `.127`이며 일반 host 범위는 `.65`부터 `.126`이다.

A가 B에게 보낼 때 같은 on-link 네트워크라면 B의 MAC을 구한다. C에게 보낼 때는 라우팅 표가 선택한 gateway의 MAC을 구한다. 실제로 어떤 경로가 선택되는지는 단순 subnet 계산뿐 아니라 설치된 routing table·policy에 달려 있다. `/31`, `/32`, IPv6에 `전체 주소 수 - 2` 공식을 무조건 적용하지 않는다. 예외는 [IP 장](02-ip-subnets-and-routers.md)을 다시 읽는다.

## 2. 라우터 한 홉을 통과하며 바뀌는 것을 적는다

**조건:** A=`192.0.2.10`, gateway=`192.0.2.1`, 서버 B=`198.51.100.20`. A가 B의 TCP 443번 포트에 접속한다. A의 임시 출발 포트는 교육용으로 50000이다. NAT·터널·proxy가 없는 정상 전달 경로를 가정한다.

| 관측 지점 | Ethernet 목적지 | IP 출발지→목적지 | TCP 출발→목적 포트 |
| --- | --- | --- | --- |
| A가 내보내는 링크 | 라우터의 A쪽 MAC | A→B | 50000→443 |
| 라우터가 B쪽으로 내보내는 링크 | B 또는 다음 라우터의 MAC | A→B | 50000→443 |
| B의 응답 경로 | 응답 링크의 다음 홉 MAC | B→A | 443→50000 |

라우터는 입력 Ethernet 프레임을 그대로 다른 링크에 복사하는 것이 아니라 IP 패킷을 전달하면서 출력 링크에 맞는 프레임을 만든다. IPv4 TTL은 전달 과정에서 감소하고 이에 따라 IPv4 header checksum도 갱신한다. 종단 IP와 포트는 이 가정에서는 유지된다. NAT가 있으면 그 변환을 별도로 추적해야 한다.

이 문제를 틀리는 대표 이유는 **최종 목적지의 IP를 다음 홉 MAC으로 바꾼다**고 생각하는 것이다. 두 주소는 다른 계층의 역할이다. 다음 홉 MAC을 알아도 최종 목적지 IP는 필요하다.

## 3. 스위치는 모르는 목적지를 어디로 보낼까?

**조건:** VLAN 10에서 A는 port1, B는 port2, C는 port3에 있다. forwarding database(FDB)는 비어 있다. 정상적인 loop 없는 스위치이며 특수 보안 정책은 없다. A가 B에게 unicast frame을 보내고 B가 답한다고 하자.

**해설:** 처음 수신한 프레임의 **source MAC A**와 입력 port1을 연결해 배운다. destination B가 아직 테이블에 없으므로 해당 VLAN의 허용된 다른 포트로 unknown-unicast flooding을 할 수 있다. 일반적인 이 모형에서는 port2와 port3이다. B의 응답이 port2로 오면 source B→port2를 배운다. destination A는 이미 있으므로 응답은 port1로 전달한다.

| 사건 | 새로 학습한 항목 | 전달 판단 |
| --- | --- | --- |
| A→B 처음 수신 | VLAN10, A→port1 | B 미학습: VLAN10의 다른 허용 포트로 flood |
| B→A 응답 수신 | VLAN10, B→port2 | A 학습됨: port1 |
| A→B 재전송 | A→port1 갱신 가능 | B 학습됨: port2 |

배우는 주소는 source이고 찾는 주소는 destination이다. 이 테이블은 IP routing table이나 ARP cache와 다르다. FDB aging, topology change, port security, EVPN 등 실제 기능은 이 단순 모델에 조건을 추가한다. [스위치 장](01-ethernet-switches-vlans.md)

## 4. 가장 구체적인 IP 경로를 고른다

**조건:** 라우팅 표에 다음 경로가 있다. 동일 prefix에 대한 추가 정책·우선순위 문제는 없다고 하자.

~~~text
0.0.0.0/0          → gateway A
198.51.100.0/24     → gateway B
198.51.100.128/25   → gateway C
~~~

목적지 `198.51.100.140`은 세 경로에 모두 해당하지만 `/25`가 가장 긴 prefix이므로 C가 선택된다. `198.51.100.20`은 `/25`에는 속하지 않으므로 `/24`의 B를 선택한다. `203.0.113.9`는 제시된 표에서는 default route A를 선택한다.

이것이 **longest prefix match**다. 위에서 먼저 적힌 줄을 무조건 선택하는 규칙이 아니다. 실제 policy routing은 사용할 table 선택 등의 단계를 더할 수 있으므로 [02장](02-ip-subnets-and-routers.md)의 적용 범위를 함께 본다.

## 5. 빠른 링크인데 한 연결의 처리량이 낮은 이유

**조건:** 링크는 10 Gbit/s, 왕복 지연(RTT)은 40 ms다. 이 경로를 가득 활용하려면 대략 어느 정도의 바이트가 처리 중이어야 하는가? 손실과 다른 제약은 우선 무시한다.

~~~text
10 Gbit/s ÷ 8 = 1.25 GB/s
40 ms = 0.040 s
BDP = 1.25 GB/s × 0.040 s = 0.050 GB = 50 MB
~~~

**BDP(Bandwidth-Delay Product)**는 대역폭과 왕복 시간의 곱이다. 약 50 MB가 비행 중인 규모가 된다. TCP에서는 송신량이 receive window와 congestion window 등으로 제한된다. 교육용으로 허용된 비행 중 데이터가 1 MB에 불과하면, 단순 상한은 `1 MB / 0.040 s = 25 MB/s = 200 Mbit/s` 수준이다.

이 계산은 곧바로 socket buffer를 50 MB로 바꾸라는 명령이 아니다. 실제 병목, window scaling, congestion control, CPU, 앱이 데이터를 생산하는 속도, 양방향 경로를 확인해야 한다. 단위를 맞춘 후 메커니즘을 따져야 한다. [TCP 장](03-transport-tcp-udp-quic.md)

## 6. 터널을 씌우면 MTU가 왜 줄어드는가?

**조건:** underlay의 IP MTU가 1500 B다. IPv4/UDP/VXLAN으로 내부 Ethernet frame을 운반하며 기본 outer IPv4 header 20 B, UDP 8 B, VXLAN 8 B, inner Ethernet header 14 B만 고려한다. 추가 VLAN tag·IP 옵션·암호화는 없고 inner FCS는 운반하지 않는 모형이다.

~~~text
1500 - 20 - 8 - 8 - 14 = 1450 B
~~~

따라서 내부 IP 패킷에 사용할 수 있는 크기는 이 가정에서 1450 B다. outer Ethernet header를 또 빼지 않은 이유는 주어진 1500이 이미 **outer IP MTU**이기 때문이다. 서로 다른 계층의 길이를 섞으면 이중 계산한다.

내부 IPv4와 TCP의 기본 header를 각각 20 B로 두면 기본 payload 계산은 `1450 - 20 - 20 = 1410 B`다. 실제 options, 경로 MTU, IPv6, 다른 캡슐화에 따라 달라진다. 작은 ping만 된다고 큰 데이터 전송까지 정상이라는 증거는 없다. PMTUD와 ICMP 전달 조건은 [02장](02-ip-subnets-and-routers.md), Kubernetes의 실제 구성 차이는 [07장](07-kubernetes-cni-cilium.md)을 참고한다.

## 7. eBPF verifier 통과는 무엇을 증명하는가?

**조건:** 프로그램이 verifier를 통과하고 정상 부착되었지만 의도한 서비스 패킷을 모두 차단한다. “verifier가 있으니 프로그램은 올바르다”라는 설명을 평가하라.

**해설:** verifier는 해당 프로그램 유형·커널의 규칙 안에서 메모리 접근과 실행 등에 관한 안전 조건을 검사한다. 작성자가 원한 업무 정책을 대신 이해하지 않는다. 안전하게 잘못된 패킷을 버리는 프로그램도 가능하다. 올바른 hook 선택, header/byte order, IPv4·IPv6·fragment·VLAN·길이 검사, map 값, 정책 우선순위, 반환 동작을 별도로 검증해야 한다.

또한 XDP에서 본 패킷 수와 앱의 요청 수를 같은 숫자로 비교하면 안 된다. 재전송·패킷 분할·집계·관측 hook·sampling·event 유실로 관계가 달라진다. **관측 프로그램이 본 사건**과 **전체 시스템에서 일어난 사건**을 구별한다. [eBPF 장](06-ebpf-xdp-tc.md)

## 8. 장애를 계층별로 좁히는 문제

**조건:** 사용자는 “웹 사이트에 접속 안 됨”이라고 말한다. 아래 네 관측 각각에서 무엇이 확인됐으며 무엇을 아직 모르는지 설명하라.

| 관측 | 확인된 것 | 다음 질문 |
| --- | --- | --- |
| DNS 응답에 주소가 있음 | 어떤 resolver가 이름 조회 결과를 반환 | 그 주소가 의도한 endpoint인가, 연결·권한은 정상인가? |
| TCP handshake 성공 | 해당 흐름에서 TCP 연결 성립 | TLS·HTTP·backend 준비는 정상인가? |
| TLS 인증서 검증 실패 | 보호된 연결 설정 단계에서 조건 불만족 | 신뢰 체인·이름·유효기간·시각·중간 인증서 중 무엇인가? |
| HTTP 503 수신 | HTTP 응답 주체가 서비스 불가를 보고 | proxy/backend 중 누가 응답했고 어떤 readiness/의존성 문제인가? |

DNS 성공이 TCP 성공을 보장하지 않고, TCP 성공이 업무 요청 성공을 보장하지 않는다. 실패를 관측한 층과 원인이 있는 층이 항상 같지도 않다. 예를 들어 backend 네트워크 문제가 gateway의 503으로 나타날 수 있다. [DNS·HTTP·TLS 장](04-dns-http-tls.md)

## 9. 작은 설계 과제: 관측 가능한 서비스 경로

**요구:** 두 노드에 Pod가 있고 Service 이름으로 서로 호출한다. 일부 큰 요청만 timeout이 발생한다. 서비스 재배포나 방화벽 전체 해제 없이 원인 후보를 구별하는 계획을 작성하라.

해설의 핵심은 정답 제품 이름이 아니다. 다음을 빠뜨리지 않았는지 확인한다.

1. 같은 노드와 다른 노드, 작은 요청과 큰 요청을 구분해 현상 범위를 정한다.
2. DNS 결과, 실제 연결 대상, Service→backend 변환, 요청과 응답 경로를 각각 그린다.
3. overlay/direct routing 및 실제 MTU를 확인할 자료를 정한다. “큰 것만 실패”는 MTU 가설을 지지하지만 증명하지는 않는다.
4. packet loss/retransmission, 애플리케이션 제한·timeout, backend 부하라는 대안 가설도 적는다.
5. 각 관측 도구가 보는 지점과 권한을 정한다. Hubble이나 캡처 결과가 모든 hook의 모든 drop을 보여준다고 가정하지 않는다.
6. 의심 원인을 하나씩 구별할 격리 실험을 설계한다. 운영에 실제 주입하는 것은 별도의 실행 절차다.

**자체 평가:** 경로와 방향 1점, 가설 두 개 이상 1점, 구별 관측·예측 1점, 변경 없이 먼저 확인할 근거 1점, 관측 한계 1점. “MTU 바꾸면 된다”만 쓰면 원인 후보를 확정한 근거가 없으므로 통과하지 못한다.

## 10. 처음 보는 약어를 풀어 읽는 사전

사전은 본문을 대체하지 않는다. 처음 단어를 만났을 때 뜻을 찾고 연결 장으로 돌아간다. 문맥에 따라 같은 단어가 다른 단위를 뜻할 수 있다.

| 단어·풀네임 | 쉬운 뜻 | 혼동할 대상 | 본문 |
| --- | --- | --- | --- |
| bit / symbol | 이진 정보의 자리 / 물리 신호의 구별 상태 | 한 symbol이 언제나 한 bit는 아님 | [00](00-signals-frames-and-packets.md) |
| bandwidth / throughput | 경로가 수용하는 이동량 / 실제 유용 작업 완료량 | 광고 속도와 실제 앱 속도 | [00](00-signals-frames-and-packets.md) |
| latency / jitter | 걸린 시간 / 지연의 변동 | 평균 하나로 분포 설명 | [00](00-signals-frames-and-packets.md) |
| frame / packet / segment | 링크 / IP / TCP 계층의 전달 단위 | 앱 메시지와 같지 않음 | [00](00-signals-frames-and-packets.md) |
| encapsulation | 위 계층 바이트를 아래 계층의 내용으로 감싸기 | 암호화와 다름 | [00](00-signals-frames-and-packets.md) |
| MAC, Media Access Control | 링크 계층의 접근·주소 체계 문맥 | IP 주소와 다름 | [01](01-ethernet-switches-vlans.md) |
| FDB, Forwarding Database | 스위치의 MAC/VLAN→출력 위치 표 | ARP cache·IP 경로표 | [01](01-ethernet-switches-vlans.md) |
| VLAN, Virtual LAN | 하나의 물리 스위칭 환경 안에서 논리 LAN 분리 | IP subnet과 일대일 필수 관계 아님 | [01](01-ethernet-switches-vlans.md) |
| STP, Spanning Tree Protocol | L2 루프를 피하도록 전달 경로 조정 | 라우팅 프로토콜과 다름 | [01](01-ethernet-switches-vlans.md) |
| LACP, Link Aggregation Control Protocol | 링크 묶음의 구성 협상 | 한 흐름 속도의 단순 합산 보장 아님 | [01](01-ethernet-switches-vlans.md) |
| IP, Internet Protocol | 네트워크 사이에 주소로 패킷을 전달하는 규칙 | 신뢰성 있는 앱 전달 보장 아님 | [02](02-ip-subnets-and-routers.md) |
| CIDR, Classless Inter-Domain Routing | prefix 길이로 주소 범위를 다루는 방식 | 예전 class A/B/C 고정 구분 | [02](02-ip-subnets-and-routers.md) |
| ARP, Address Resolution Protocol | IPv4 링크에서 다음 홉 주소에 대응하는 MAC 찾기 | DNS 이름 조회 | [02](02-ip-subnets-and-routers.md) |
| NDP, Neighbor Discovery Protocol | IPv6 이웃·라우터 발견 등의 기능 | 단순 ARP 이름 변경이 아님 | [02](02-ip-subnets-and-routers.md) |
| TTL, Time To Live | IP 전달 홉 제한 또는 DNS cache 유지 시간 문맥 | 두 TTL의 단위와 대상은 다름 | [02](02-ip-subnets-and-routers.md), [04](04-dns-http-tls.md) |
| ICMP, Internet Control Message Protocol | IP 관련 오류·진단 등의 메시지 | 모든 메시지가 ping인 것은 아님 | [02](02-ip-subnets-and-routers.md) |
| MTU, Maximum Transmission Unit | 해당 링크/경로에서 다루는 전송 크기 한도 | TCP payload 크기인 MSS | [02](02-ip-subnets-and-routers.md) |
| PMTUD, Path MTU Discovery | 경로에서 통과할 크기를 알아내는 절차 | 로컬 NIC MTU만 보는 것 | [02](02-ip-subnets-and-routers.md) |
| NAT, Network Address Translation | 주소·필요시 포트를 변환하는 처리 | 암호화·완전한 보안 경계 | [02](02-ip-subnets-and-routers.md) |
| TCP, Transmission Control Protocol | 순서 있는 신뢰성 바이트 스트림 | 요청 한 건의 경계·업무 commit | [03](03-transport-tcp-udp-quic.md) |
| UDP, User Datagram Protocol | datagram 단위의 전송 인터페이스 | 전달·순서·중복 방지 자동 보장 | [03](03-transport-tcp-udp-quic.md) |
| socket / port | 프로그램의 통신 인터페이스 / 끝점 구별 번호 | 스위치의 물리 포트 | [03](03-transport-tcp-udp-quic.md) |
| ACK, Acknowledgment | 특정 계층에서 받은 것에 대한 확인 | 디스크 영속성·업무 성공 | [03](03-transport-tcp-udp-quic.md) |
| RTT, Round-Trip Time | 왕복 경과 시간 | 편도 지연과 다름 | [03](03-transport-tcp-udp-quic.md) |
| MSS, Maximum Segment Size | TCP가 다루는 payload 크기 관련 값 | Ethernet frame 전체 크기 | [03](03-transport-tcp-udp-quic.md) |
| cwnd / rwnd | 혼잡 창 / 수신 창 | 서로 다른 제어 목적 | [03](03-transport-tcp-udp-quic.md) |
| QUIC | UDP 위에서 연결·보호·스트림 등을 제공하는 전송 프로토콜 | UDP 자체가 TCP 보장을 갖는다는 뜻 아님 | [03](03-transport-tcp-udp-quic.md) |
| DNS, Domain Name System | 이름과 관련된 레코드를 조회하는 분산 체계 | 모든 이름 결과가 IP 하나인 것은 아님 | [04](04-dns-http-tls.md) |
| TLS, Transport Layer Security | 통신 보호와 상대 인증을 위한 프로토콜 | 목적지·시각 등 모든 metadata 은닉 | [04](04-dns-http-tls.md) |
| SNI, Server Name Indication | TLS 연결에서 의도한 서버 이름 전달 | DNS 조회나 인증서 검증 자체 | [04](04-dns-http-tls.md) |
| ALPN, Application-Layer Protocol Negotiation | 연결에서 사용할 앱 프로토콜 협상 | 서버 주소 선택 | [04](04-dns-http-tls.md) |
| HTTP, Hypertext Transfer Protocol | 요청·응답 의미와 웹 메시지 규칙 | 특정 TCP packet 하나 | [04](04-dns-http-tls.md) |
| proxy / load balancer | 요청 중계 / 대상 사이 부하 분배 역할 | 모두 같은 L4/L7 동작을 하는 것은 아님 | [04](04-dns-http-tls.md) |
| qdisc, queueing discipline | Linux 송신 큐의 처리 규칙 | NIC hardware queue 자체 | [05](05-linux-packet-path.md) |
| NAPI | Linux 수신 처리의 polling·interrupt 협업 인터페이스 | 모든 작업을 CPU 없이 처리하는 기능 | [05](05-linux-packet-path.md) |
| GRO / GSO | 수신 패킷 집계 / 송신 분할 관련 offload | wire상 실제 frame 크기 | [05](05-linux-packet-path.md) |
| veth, virtual Ethernet | 양 끝이 연결된 가상 네트워크 장치 쌍 | 물리 케이블이나 독립 커널 | [05](05-linux-packet-path.md) |
| conntrack | 흐름 상태를 추적하는 기능 | 모든 앱 세션의 의미를 이해하는 기능 | [05](05-linux-packet-path.md) |
| BPF / eBPF | Berkeley Packet Filter에서 발전한 커널 내 프로그램 실행 체계 | 커널 전체를 자유롭게 수정하는 모듈 | [06](06-ebpf-xdp-tc.md) |
| verifier / helper / map | 검사기 / 제공 함수 / 프로그램과 사용자 공간이 쓰는 상태 구조 | 정책 정확성을 자동 증명하는 기능 | [06](06-ebpf-xdp-tc.md) |
| XDP, eXpress Data Path | 이른 패킷 처리 지점·프레임워크 | 모든 네트워크 hook의 총칭 | [06](06-ebpf-xdp-tc.md) |
| TC, Traffic Control | Linux 트래픽 제어 및 관련 hook | XDP와 동일 위치 | [06](06-ebpf-xdp-tc.md) |
| BTF, BPF Type Format | 형식·타입 정보를 표현하는 metadata | 프로그램의 모든 호환성 보장 | [06](06-ebpf-xdp-tc.md) |
| CO-RE, Compile Once – Run Everywhere | 타입·필드 차이에 맞춘 BPF 재배치 접근 | 모든 커널·helper·설정에 무조건 실행 | [06](06-ebpf-xdp-tc.md) |
| JIT, Just-In-Time compilation | 실행 대상 기계어로 변환하는 컴파일 방식 | 업무 정책 검증 | [06](06-ebpf-xdp-tc.md) |
| CNI, Container Network Interface | 컨테이너 네트워크 설정 인터페이스·규격 | Kubernetes 모든 네트워크 기능 자체 | [07](07-kubernetes-cni-cilium.md) |
| IPAM, IP Address Management | IP 주소 할당·관리 | 패킷 전달 경로 자체 | [07](07-kubernetes-cni-cilium.md) |
| VXLAN, Virtual eXtensible LAN | IP/UDP 경로 위에 L2 frame을 운반하는 터널 | 암호화 자동 제공 | [07](07-kubernetes-cni-cilium.md) |
| Service / EndpointSlice | 서비스 접근 추상화 / backend 정보 객체 | 반드시 물리 NIC에 부여된 IP | [07](07-kubernetes-cni-cilium.md) |
| NetworkPolicy | Pod 통신 허용 조건을 표현하는 API | 모든 구현에서 동일한 기능·L7 보장 | [07](07-kubernetes-cni-cilium.md) |
| Cilium / Hubble | 네트워크·정책 구현 / 관련 관측 기능 | eBPF 자체 또는 전 구간 완전 관측 | [07](07-kubernetes-cni-cilium.md) |

새로운 기술을 만나면 이 사전에 단어를 추가하는 것으로 끝내지 않는다. **어느 계층의 어떤 문제를 해결하며, packet path의 어디를 바꾸고, 무엇을 검증해야 하는지** 본문과 연결해서 설명한다.
