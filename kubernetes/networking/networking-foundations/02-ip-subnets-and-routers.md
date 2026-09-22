# 02. IP, Subnet, Router

범위: 이 장은 IPv4/IPv6 주소, CIDR, subnet, longest prefix match, ARP/NDP, routing, TTL, ICMP, PMTUD, NAT를 설명한다.
명령 실행이나 호스트 설정 없이 손계산과 packet journey로 이해한다.

## 1. IP 주소는 host가 아니라 interface에 붙는 네트워크 계층 주소다

**IP(Internet Protocol)**는 여러 network를 이어 packet을 목적지 쪽으로 보내기 위한 network-layer protocol이다.
IPv4는 32 bit 주소를 사용한다.
IPv6는 128 bit 주소를 사용한다.

초보자가 자주 하는 실수는 “서버 하나 = IP 하나”라고 외우는 것이다.
운영에서는 하나의 host가 여러 NIC, VLAN subinterface, loopback, pod interface, service VIP를 가질 수 있다.
따라서 IP는 보통 host 전체보다 interface 또는 논리 endpoint에 붙은 주소로 이해하는 편이 안전하다.

RFC 791은 IPv4가 source와 destination을 fixed length address로 식별하고 datagram을 전달한다고 설명한다.
출처: [RFC 791](https://www.rfc-editor.org/rfc/rfc791.html).

## 2. IPv4 주소는 32 bit 숫자다

`192.168.10.25`는 사람이 읽기 쉽게 8 bit씩 끊어 10진수로 쓴 것이다.

```text
192      .168      .10       .25
11000000 10101000 00001010 00011001
```

각 octet은 0부터 255까지다.
IP 주소 계산은 결국 32 bit 숫자에 mask를 AND하는 일이다.

## 3. CIDR은 prefix 길이를 명시한다

**CIDR(Classless Inter-Domain Routing)**는 옛 Class A/B/C 방식 대신 prefix 길이를 명시하는 주소 표현이다.
`192.168.10.0/24`에서 `/24`는 앞 24 bit가 network prefix라는 뜻이다.
RFC 4632는 CIDR notation이 IPv4 주소 뒤에 slash와 0~32 사이 숫자로 significant bits를 나타낸다고 설명한다.
출처: [RFC 4632](https://www.rfc-editor.org/rfc/rfc4632.html).

```text
/24 mask = 11111111.11111111.11111111.00000000
         = 255.255.255.0

/26 mask = 11111111.11111111.11111111.11000000
         = 255.255.255.192
```

## 4. Network address는 IP AND mask로 구한다

예: `192.168.10.77/26`

```text
IP      192.168.10.77
binary  11000000.10101000.00001010.01001101

mask    255.255.255.192
binary  11111111.11111111.11111111.11000000

AND     11000000.10101000.00001010.01000000
        192.168.10.64
```

따라서 `192.168.10.77/26`은 `192.168.10.64/26` subnet에 속한다.

## 5. /26 host count 손계산

IPv4는 32 bit다.
`/26`이면 host bit는 `32 - 26 = 6`개다.
가능한 조합은 `2^6 = 64`개다.

전통적인 broadcast subnet에서는 all-zero host 부분은 network address, all-one host 부분은 directed broadcast address로 쓰므로 일반 host 수는 `64 - 2 = 62`다.

```text
192.168.10.64/26

network address:   192.168.10.64
first usable:      192.168.10.65
last usable:       192.168.10.126
broadcast address: 192.168.10.127
usable count:      62
```

오개념: “모든 subnet은 무조건 2개를 뺀다”는 말은 예외가 있다.

## 6. /31과 /32 예외

`/32`는 host bit가 0개다.
주소 하나만 정확히 가리킨다.
loopback address, host route, routing table의 정확한 destination에 자주 쓴다.

`/31`은 point-to-point 링크에서 두 주소를 모두 endpoint 주소로 쓰는 방식이 있다.
전통적인 network/broadcast 예약을 그대로 적용하면 주소가 하나도 남지 않지만, point-to-point에서는 broadcast가 필요 없기 때문이다.
운영 문서에서는 장비와 OS가 `/31`을 지원하는지 확인해야 한다.

초보 단계에서는 이렇게 기억한다.

| prefix | 일반적 의미 |
| --- | --- |
| /24 | 256개 주소, 전통적 usable 254 |
| /26 | 64개 주소, 전통적 usable 62 |
| /31 | point-to-point에서 2 endpoint용 가능 |
| /32 | 정확히 한 IPv4 주소 |

## 7. Longest Prefix Match는 가장 구체적인 route를 고른다

router는 routing table에서 destination IP와 맞는 route를 찾고, 그중 prefix 길이가 가장 긴 항목을 선택한다.
이를 **Longest Prefix Match(LPM)**라고 한다.

예:

```text
0.0.0.0/0          -> GW A
10.0.0.0/8         -> GW B
10.20.0.0/16       -> GW C
10.20.30.0/24      -> GW D
```

destination `10.20.30.77`은 네 route 모두에 들어간다.
가장 긴 `/24`가 이기므로 GW D가 선택된다.

destination `10.20.44.9`는 `/24`에는 안 들어가고 `/16`에 들어간다.
GW C가 선택된다.

destination `8.8.8.8`은 `0.0.0.0/0`만 맞는다.
GW A가 선택된다.

## 8. Data plane과 control plane을 나눈다

**data plane**은 실제 packet을 빠르게 forwarding하는 경로다.
destination IP를 보고 next hop과 egress interface를 고른다.

**control plane**은 routing table을 만들고 유지하는 논리다.
static route, OSPF, BGP 같은 protocol이 control plane에 속한다.

비유하면 data plane은 택배 분류기의 현재 규칙이고, control plane은 그 규칙표를 만드는 회의와 업데이트 시스템이다.
비유의 한계는 실제 router는 하드웨어 ASIC, kernel FIB, userspace routing daemon, policy routing이 섞일 수 있다는 점이다.

## 9. Static route, OSPF, BGP의 등장 동기

**static route**는 관리자가 직접 넣는 route다.
작고 단순한 환경에서는 명확하지만, 장애와 topology 변경에 자동 반응하지 않는다.

**OSPF(Open Shortest Path First)**는 하나의 관리 도메인 내부에서 link-state 정보를 나누고 최단 경로를 계산하는 IGP다.
RFC 2328은 OSPFv2를 IPv4 routing protocol로 정의한다.
출처: [RFC 2328](https://www.rfc-editor.org/rfc/rfc2328.html).

**BGP(Border Gateway Protocol)**는 AS(Autonomous System) 사이의 reachability 정보를 교환하는 path-vector protocol이다.
인터넷과 대규모 data center edge에서 중요하다.
RFC 4271은 BGP-4를 정의한다.
출처: [RFC 4271](https://www.rfc-editor.org/rfc/rfc4271.html).

초보자가 기억할 구분:

| 방식 | 주 사용처 | 장점 | 주의 |
| --- | --- | --- | --- |
| static | 작은 고정 경로 | 단순함 | 장애 자동 우회 약함 |
| OSPF | 한 조직 내부 | topology 변화 반영 | area/design 필요 |
| BGP | 조직 간, 대규모 정책 routing | policy와 확장성 | 설정 실수 영향 큼 |

## 10. ARP는 IPv4 주소를 MAC 주소로 묻는다

같은 Ethernet/VLAN 안에서 IPv4 packet을 frame에 싣기 위해서는 next-hop MAC이 필요하다.
**ARP(Address Resolution Protocol)**는 IPv4 주소에 해당하는 hardware address를 찾기 위해 생겼다.
RFC 826은 Ethernet address와 protocol address 사이의 변환 문제를 다룬다.
출처: [RFC 826](https://www.rfc-editor.org/rfc/rfc826.html).

예:

```text
A: 10.0.1.10/24, MAC aa
GW: 10.0.1.1/24, MAC gg
S: 10.0.9.20/24
```

A가 S로 보내려면 S가 같은 subnet이 아니므로 next hop은 GW다.
A는 `10.0.1.1의 MAC이 누구인가?`를 ARP로 묻는다.
답은 `gg`다.

그 뒤 frame은 이렇게 된다.

```text
Ethernet dst MAC = gg
Ethernet src MAC = aa
IPv4 dst IP      = 10.0.9.20
IPv4 src IP      = 10.0.1.10
```

중요: ARP는 최종 목적지 S의 MAC을 묻지 않는다.
현재 링크에서 다음 hop인 GW의 MAC을 묻는다.

## 11. ARP cache는 학습 결과를 잠시 저장한다

ARP 요청을 매 packet마다 보내면 비효율적이다.
그래서 host는 ARP 결과를 cache한다.

```text
ARP cache 예:
10.0.1.1 -> gg:gg:gg:gg:gg:gg, reachable
10.0.1.20 -> bb:bb:bb:bb:bb:bb, stale
```

cache entry는 시간이 지나면 stale이 되거나 다시 확인된다.
운영에서 “첫 packet만 느림”은 ARP/NDP resolution 때문일 수 있다.
하지만 여기서 명령으로 확인하지는 않는다.

## 12. IPv6는 ARP를 쓰지 않고 NDP를 쓴다

IPv6에는 ARP가 없다.
대신 **NDP(Neighbor Discovery Protocol)**가 ICMPv6 위에서 동작한다.
NDP는 neighbor의 link-layer address를 찾고, router를 발견하고, prefix 정보를 얻는 데 쓰인다.
RFC 4861은 IPv6 Neighbor Discovery를 정의한다.
출처: [RFC 4861](https://www.rfc-editor.org/rfc/rfc4861.html).

초보자가 기억할 차이:

| IPv4 | IPv6 |
| --- | --- |
| ARP로 IPv4 -> MAC 매핑 | NDP로 IPv6 neighbor discovery |
| broadcast ARP request | multicast 기반 neighbor solicitation |
| IPv4 broadcast 개념 있음 | IPv6에는 IPv4식 broadcast 없음 |

## 13. TTL과 hop limit은 packet 수명을 제한한다

IPv4의 **TTL(Time To Live)**은 packet이 routing loop에서 영원히 돌지 않도록 줄어드는 값이다.
router는 packet을 처리할 때 TTL을 감소시키고, 0이 되면 폐기한다.
RFC 791은 TTL이 datagram lifetime의 upper bound이며 route 상에서 감소한다고 설명한다.
출처: [RFC 791](https://www.rfc-editor.org/rfc/rfc791.html).

IPv6에서는 비슷한 역할을 **Hop Limit**이 한다.
TTL이 “초”처럼 보이지만 현대 운영 감각에서는 router hop마다 줄어드는 limit으로 이해하는 것이 좋다.

## 14. ICMP는 IP의 오류와 진단 신호를 전달한다

**ICMP(Internet Control Message Protocol)**는 IP 처리 중 생긴 오류나 제어 정보를 전달하는 protocol이다.
예를 들어 destination unreachable, time exceeded 같은 메시지가 있다.
RFC 792가 ICMP를 정의한다.
출처: [RFC 792](https://www.rfc-editor.org/rfc/rfc792.html).

ICMP는 “ping만 하는 protocol”이 아니다.
PMTUD, TTL exceeded, unreachable 같은 네트워크 동작에 중요하다.
무조건 ICMP를 막으면 문제를 숨기거나 PMTUD를 깨뜨릴 수 있다.

## 15. PMTUD는 경로의 MTU를 찾는다

**PMTUD(Path MTU Discovery)**는 출발지에서 목적지까지 가는 경로 중 가장 작은 MTU를 알아내려는 절차다.
IPv4에서는 DF(Don't Fragment) bit를 세우고, 중간 router가 더 작은 MTU 때문에 forwarding할 수 없으면 ICMP fragmentation needed를 보내는 방식이 쓰인다.
RFC 1191이 IPv4 Path MTU Discovery를 설명한다.
출처: [RFC 1191](https://www.rfc-editor.org/rfc/rfc1191.html).

문제는 ICMP가 중간에서 막히면 sender가 작은 MTU를 알지 못하는 blackhole이 생길 수 있다는 점이다.
overlay tunnel이 있는 Kubernetes 환경에서는 inner packet에 outer header가 더해져 실제 underlay MTU 여유가 줄어든다.

손계산:

```text
underlay MTU = 1500
tunnel outer overhead = 50 bytes라고 가정
inner packet 최대 = 1500 - 50 = 1450 bytes
```

overhead 값은 tunnel 종류와 옵션에 따라 달라진다.
운영 문서에서는 실제 encapsulation을 확인해야 한다.

## 16. NAT는 주소를 바꾸고 상태를 기억한다

**NAT(Network Address Translation)**는 packet의 IP 주소, 때로는 port까지 바꾸는 기능이다.
RFC 3022는 traditional NAT가 private realm과 external realm 사이의 주소를 변환한다고 설명한다.
출처: [RFC 3022](https://www.rfc-editor.org/rfc/rfc3022.html).

**SNAT(Source NAT)**는 source 주소를 바꾼다.
내부 client가 외부로 나갈 때 내부 source IP를 gateway의 public IP로 바꾸는 경우가 대표적이다.

**DNAT(Destination NAT)**는 destination 주소를 바꾼다.
외부에서 public IP:port로 들어온 packet을 내부 서버 IP:port로 보내는 port forwarding이 대표적이다.

## 17. NAT state와 reverse path

NAT는 돌아오는 packet을 원래 흐름에 맞게 되돌리기 위해 상태를 저장한다.

```text
내부 client: 10.0.1.10:50000
외부 server: 203.0.113.7:443
NAT public: 198.51.100.9

나가는 packet 변환:
10.0.1.10:50000 -> 203.0.113.7:443
198.51.100.9:40001 -> 203.0.113.7:443

NAT table:
198.51.100.9:40001 <-> 10.0.1.10:50000

돌아오는 packet:
203.0.113.7:443 -> 198.51.100.9:40001
NAT 후:
203.0.113.7:443 -> 10.0.1.10:50000
```

reverse path가 같은 NAT 장비를 지나지 않으면 상태를 찾을 수 없어 연결이 깨질 수 있다.
그래서 active-active firewall/NAT, asymmetric routing, Kubernetes egress gateway 설계에서 state 동기화와 경로 대칭성이 중요하다.

## 18. Packet journey: subnet 밖으로 가는 IPv4 packet

```text
1. 애플리케이션이 서버 10.0.9.20:443에 연결하려 한다.
2. host는 route lookup을 한다.
3. 10.0.9.20이 local subnet 밖이므로 default gateway 10.0.1.1을 next hop으로 고른다.
4. ARP cache에 10.0.1.1 MAC이 없으면 ARP request를 보낸다.
5. gateway MAC을 알면 Ethernet frame dst MAC을 gateway로 설정한다.
6. IPv4 packet dst IP는 여전히 10.0.9.20이다.
7. switch는 dst MAC을 보고 gateway port로 frame을 보낸다.
8. router는 frame을 벗기고 IP dst 10.0.9.20으로 LPM route lookup을 한다.
9. router는 TTL을 줄이고 다음 link의 Ethernet header를 새로 붙인다.
10. 목적지 subnet에 도착하면 마지막 router가 목적지 host MAC을 ARP로 알아내 frame을 보낸다.
```

각 hop에서 바뀌는 것:

| 필드 | 같은 subnet switch 통과 | router 통과 |
| --- | --- | --- |
| Ethernet src/dst MAC | 유지되거나 switch 내부 처리 | 새 링크에 맞게 변경 |
| IPv4 src/dst IP | 유지 | 일반 routing에서는 유지. NAT 장비라면 바뀔 수 있음 |
| TTL | 유지 | 1 감소 |
| IPv4 header checksum | 유지 | TTL 변경에 맞춰 갱신. IPv6에는 header checksum 없음 |
| FCS | 유지 | router가 새 링크로 내보내는 frame에 맞게 재계산 |

## 19. 자주 틀리는 오개념

| 오개념 | 바로잡기 |
| --- | --- |
| `/24`는 항상 Class C다 | CIDR에서는 class보다 prefix 길이가 중요하다 |
| subnet host 수는 항상 `2^hostbits - 2`다 | `/31`, `/32` 같은 예외가 있다 |
| ARP는 최종 목적지 MAC을 찾는다 | 같은 링크의 next-hop MAC을 찾는다 |
| IPv6도 ARP를 쓴다 | IPv6는 NDP를 쓴다 |
| ICMP는 ping이라 막아도 된다 | 오류 전달과 PMTUD에 필요하다 |
| NAT는 주소만 바꾸고 끝이다 | port와 상태, reverse path가 중요하다 |
| default route가 있으면 최적 경로다 | 더 구체적인 route가 있으면 LPM으로 그쪽이 선택된다 |

## 20. 해설 문제

### 문제 1

`10.10.5.130/26`의 network address, broadcast address, 일반 usable 범위는?

해설:

```text
/26 block size = 64
10.10.5.0, .64, .128, .192 경계
130은 .128 block에 속함

network = 10.10.5.128
broadcast = 10.10.5.191
usable = 10.10.5.129 .. 10.10.5.190
```

### 문제 2

route table에 `0.0.0.0/0`, `10.0.0.0/8`, `10.2.0.0/16`이 있다.
destination `10.2.9.1`은 어느 prefix가 이기는가?

해설:

`10.2.0.0/16`이 가장 길게 일치한다.

### 문제 3

host A가 다른 subnet의 host B에게 packet을 보낸다.
첫 Ethernet frame의 destination MAC은 누구인가?

해설:

default gateway 또는 선택된 next-hop router의 MAC이다.
IP destination은 host B지만 L2 destination은 next hop이다.

### 문제 4

NAT 장비가 나가는 packet의 source를 `10.0.1.10:50000`에서 `198.51.100.9:40001`로 바꿨다.
돌아오는 packet을 원래 client에게 보내려면 무엇이 필요한가?

해설:

NAT state table에 외부 tuple과 내부 tuple의 매핑이 있어야 하고, 돌아오는 packet이 그 NAT 장비를 지나야 한다.

## 21. 1차 출처와 더 읽기

- IPv4 datagram, TTL, routing, checksum, IP의 비신뢰성: [RFC 791](https://www.rfc-editor.org/rfc/rfc791.html)
- CIDR prefix notation과 등장 배경: [RFC 4632](https://www.rfc-editor.org/rfc/rfc4632.html)
- ARP: [RFC 826](https://www.rfc-editor.org/rfc/rfc826.html)
- IPv6 Neighbor Discovery: [RFC 4861](https://www.rfc-editor.org/rfc/rfc4861.html)
- ICMP: [RFC 792](https://www.rfc-editor.org/rfc/rfc792.html)
- IPv4 Path MTU Discovery: [RFC 1191](https://www.rfc-editor.org/rfc/rfc1191.html)
- Traditional NAT: [RFC 3022](https://www.rfc-editor.org/rfc/rfc3022.html)
- OSPFv2: [RFC 2328](https://www.rfc-editor.org/rfc/rfc2328.html)
- BGP-4: [RFC 4271](https://www.rfc-editor.org/rfc/rfc4271.html)
