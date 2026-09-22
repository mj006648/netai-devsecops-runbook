# 01. Ethernet, Switch, VLAN

범위: 이 장은 같은 LAN 안에서 frame이 어떻게 움직이는지 설명한다.
핵심은 MAC 주소, Ethernet frame, switch의 FDB 학습, broadcast domain, VLAN tag, loop 방지다.
호스트 설정이나 네트워크 진단 명령 실습은 하지 않는다.

## 1. MAC 주소는 링크 계층의 주소다

**MAC(Media Access Control) 주소**는 링크 계층에서 장비 인터페이스를 식별하는 주소다.
Ethernet에서 흔히 48 bit, 즉 6 byte로 표현한다.
사람이 읽을 때는 `aa:bb:cc:dd:ee:ff`처럼 16진수 6묶음으로 쓴다.

**IP 주소**는 네트워크 계층 주소다.
IP는 여러 링크와 router를 지나 목적지 network까지 packet을 보내기 위해 필요하다.
MAC은 현재 링크에서 다음 수신자를 찾기 위해 필요하다.

둘을 우편 비유로 보면 IP는 최종 도시·건물 주소이고, MAC은 지금 물류센터 안에서 다음 컨베이어 벨트의 번호에 가깝다.
비유의 한계는 IP도 NAT과 tunnel 때문에 바뀔 수 있고, MAC도 가상 NIC와 bridge 때문에 물리 카드와 1:1이 아닐 수 있다는 점이다.

## 2. IP는 목적지를, MAC은 다음 hop을 본다

같은 subnet 안에서 A가 B로 보낼 때 목적지 IP는 B이고 목적지 MAC도 B일 수 있다.
다른 subnet으로 보낼 때는 목적지 IP는 원격 서버지만 목적지 MAC은 default gateway의 MAC이다.

```text
A: 10.0.1.10/24, MAC aa:aa
GW: 10.0.1.1/24, MAC gg:gg
S: 10.0.9.20/24, MAC ss:ss

A가 S에게 보내는 IPv4 packet:
  IP src = 10.0.1.10
  IP dst = 10.0.9.20

A가 첫 링크에 싣는 Ethernet frame:
  MAC src = aa:aa
  MAC dst = gg:gg
```

router는 frame을 받아 Ethernet header를 벗기고 IP destination을 본다.
다음 링크로 보낼 때 새 Ethernet header를 붙인다.
IP 목적지는 유지되지만 MAC 주소는 hop마다 바뀐다.

## 3. Ethernet frame의 기본 필드

운영자가 자주 보는 기본 Ethernet II frame은 다음처럼 가르칠 수 있다.

```text
Destination MAC  6 bytes
Source MAC       6 bytes
EtherType        2 bytes
Payload         46..1500 bytes
FCS              4 bytes
```

RFC 894는 IPv4 datagram을 Ethernet frame의 data field에 싣고 EtherType `0x0800`을 사용한다고 설명한다.
또 data field는 최소 46 octets이며 필요하면 padding하고, IPv4 datagram 최대는 1500 octets라고 설명한다.
출처: [RFC 894](https://www.rfc-editor.org/rfc/rfc894.html).

여기서 “payload 1500”은 frame 전체가 1500이라는 뜻이 아니다.
VLAN tag가 없는 기본 frame에서 MAC header 14 byte와 FCS 4 byte를 더하면 1518 byte가 된다.

```text
MAC header 14 + payload 1500 + FCS 4 = 1518 bytes
```

실제 선로에는 preamble, SFD, inter-frame gap도 고려된다.
이들은 IP MTU나 Ethernet payload 안에 들어가지 않는다.
운영 계산에서 “애플리케이션 payload”, “IP packet”, “Ethernet frame”, “wire cost”를 구분해야 한다.

## 4. Preamble, SFD, FCS, IFG는 왜 나왔는가

**Preamble**은 수신기가 bit 타이밍을 맞추도록 돕는 앞부분 신호다.
**SFD(Start Frame Delimiter)**는 이제 frame 내용이 시작된다는 경계 표시다.
**FCS(Frame Check Sequence)**는 frame 손상 여부를 찾는 검사값이다.
**IFG(Inter-Frame Gap)**는 frame과 frame 사이의 간격이다.

초보자가 볼 수 있는 packet capture에는 FCS나 preamble이 보이지 않을 수 있다.
NIC가 이미 처리했기 때문이다.
그래서 capture 길이와 실제 wire cost는 다를 수 있다.

중요한 태도는 “MTU 1500” 하나로 모든 byte 비용을 설명하지 않는 것이다.
MTU는 IP packet 크기 계산에 주로 쓰고, 링크 효율 계산에는 링크 계층 오버헤드를 따로 더한다.

## 5. Switch는 frame의 destination MAC을 보고 넘긴다

**switch**는 Ethernet frame을 받아 destination MAC 주소를 보고 어느 port로 내보낼지 결정하는 장비다.
router처럼 IP routing table을 먼저 보는 장비가 아니다.
일반 L2 switch의 기본 동작은 MAC learning, filtering, forwarding, flooding이다.

**FDB(Forwarding Database)** 또는 MAC address table은 “어느 MAC이 어느 port 뒤에 있는가”를 담는다.
switch는 frame의 source MAC을 보고 학습한다.
destination MAC이 table에 있으면 해당 port로만 보낸다.
없으면 같은 VLAN의 다른 port로 flood한다.

## 6. FDB learning trace

다음 topology를 보자.

```text
Host A MAC aa:aa -- port 1
Host B MAC bb:bb -- port 2
Host C MAC cc:cc -- port 3
Switch S
```

초기 FDB는 비어 있다.

| 시점 | 들어온 port | src MAC | dst MAC | switch가 배운 것 | 동작 |
| --- | --- | --- | --- | --- | --- |
| T0 | - | - | - | 없음 | FDB empty |
| T1 | 1 | aa:aa | bb:bb | aa:aa -> port 1 | bb:bb를 몰라 port 2,3으로 flood |
| T2 | 2 | bb:bb | aa:aa | bb:bb -> port 2 | aa:aa를 아니까 port 1로만 forward |
| T3 | 3 | cc:cc | aa:aa | cc:cc -> port 3 | aa:aa를 아니까 port 1로만 forward |

switch는 source MAC으로 배운다.
destination MAC으로 배우지 않는다.
이 차이가 중요하다.

## 7. Flood, broadcast, unknown unicast를 구분한다

**broadcast**는 destination MAC이 `ff:ff:ff:ff:ff:ff`인 frame이다.
같은 broadcast domain의 모든 host가 받아야 한다.
ARP request가 대표적이다.
RFC 894도 IPv4 broadcast address가 Ethernet broadcast address로 mapping될 수 있다고 설명한다.
출처: [RFC 894](https://www.rfc-editor.org/rfc/rfc894.html).

**unknown unicast flooding**은 destination MAC이 unicast인데 switch table에 없어서 flood하는 동작이다.
이때 frame은 broadcast 주소가 아니지만 여러 port로 복제된다.

**multicast**는 여러 수신자를 대상으로 하는 주소 범위다.
초보 단계에서는 broadcast와 multicast를 “여러 곳으로 간다”는 점만 묶고, 제어 방식은 다르다고 기억한다.

## 8. Broadcast domain은 flood가 닿는 범위다

**broadcast domain**은 broadcast frame이 전달되는 범위다.
VLAN이 없고 하나의 switch에 host들이 붙어 있으면 대체로 같은 broadcast domain이다.
router는 일반적으로 L2 broadcast를 다른 subnet으로 넘기지 않는다.

왜 broadcast domain을 줄여야 할까?
broadcast가 너무 넓으면 ARP, discovery, 잘못된 flood, loop 사고의 영향 범위가 커진다.
운영에서는 장애 blast radius를 줄이기 위해 VLAN과 routing boundary를 둔다.

비유하면 broadcast domain은 같은 강당이다.
한 사람이 확성기로 외치면 강당 안 사람은 다 듣는다.
다른 강당까지 자동으로 들리지는 않는다.

## 9. VLAN은 하나의 물리 switch를 여러 논리 LAN처럼 나누는 방법이다

**VLAN(Virtual LAN)**은 같은 물리 장비 위에서 L2 broadcast domain을 논리적으로 나누는 기술이다.
VLAN 10과 VLAN 20은 같은 switch에 있어도 서로 다른 LAN처럼 취급된다.
서로 통신하려면 router 또는 L3 switch 같은 L3 경계가 필요하다.

VLAN의 등장 동기는 단순하다.
케이블과 switch를 부서별로 완전히 따로 두면 비용과 운영이 어렵다.
VLAN은 물리 인프라를 공유하면서 L2 범위를 나눈다.

비유하면 한 건물의 엘리베이터를 쓰지만 출입 카드 권한으로 층을 나누는 것과 비슷하다.
비유의 한계는 VLAN은 보안 기능 하나만이 아니라 forwarding 범위와 tagging 규칙이며, 설정 오류 하나로 분리가 깨질 수 있다는 점이다.

## 10. Access port와 trunk port

**access port**는 보통 하나의 VLAN에 속한 endpoint용 port다.
host가 tag 없는 frame을 보내면 switch는 그 port의 access VLAN으로 분류한다.
host로 내보낼 때도 보통 tag 없는 frame으로 내보낸다.

**trunk port**는 여러 VLAN의 frame을 한 링크로 운반하는 port다.
trunk에서는 frame에 VLAN tag를 붙여 VLAN ID를 표시한다.
switch와 switch 사이, switch와 hypervisor host 사이, switch와 router-on-a-stick 사이에서 쓴다.

```text
Access port:
  Host frame: [Ethernet][IP]
  Switch 내부 분류: VLAN 10

Trunk port:
  Wire frame: [Ethernet][802.1Q tag VLAN 10][IP]
```

## 11. VLAN tag와 PVID

**VLAN tag**는 frame이 어느 VLAN에 속하는지 표시하는 tag다.
교육 모델에서는 Ethernet header 안에 4 byte tag가 끼어든다고 보면 된다.
tag에는 VLAN ID와 priority 관련 정보가 들어간다.

**PVID(Port VLAN ID)**는 tag 없는 ingress frame을 어느 VLAN으로 분류할지 정하는 port의 기본 VLAN이다.
access port의 PVID는 보통 access VLAN과 같다.
trunk port에도 native/untagged VLAN 같은 개념이 있을 수 있지만, 장비마다 명칭과 기본값이 다르다.

운영에서 위험한 지점은 “tag 없음”이 “VLAN 없음”이 아니라는 점이다.
tag 없는 frame도 port 규칙에 따라 특정 VLAN으로 들어간다.

## 12. VLAN forwarding trace

topology:

```text
port 1: Host A, access VLAN 10, MAC aa
port 2: Host B, access VLAN 20, MAC bb
port 3: Host C, access VLAN 10, MAC cc
port 4: uplink trunk VLAN 10,20
```

FDB는 VLAN별로 분리해 생각한다.

| 시점 | ingress | VLAN | src | dst | 학습 | 동작 |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | port1 untagged | 10 | aa | cc | VLAN10 aa->p1 | cc unknown, VLAN10 port3/port4로 flood |
| T2 | port3 untagged | 10 | cc | aa | VLAN10 cc->p3 | aa known, port1로만 forward |
| T3 | port2 untagged | 20 | bb | aa | VLAN20 bb->p2 | VLAN20에서 aa unknown, port4로 flood 가능 |

VLAN10의 `aa`를 배웠다고 VLAN20에서도 `aa`를 안다고 보면 안 된다.
FDB key는 보통 VLAN과 MAC의 조합으로 이해해야 한다.

## 13. Loop는 왜 위험한가

L2 Ethernet frame에는 IP TTL 같은 hop limit이 없다.
switch 사이에 loop가 생기면 broadcast와 unknown unicast가 계속 복제되어 돌아다닐 수 있다.
FDB도 출처 port가 계속 바뀌어 흔들린다.
이를 MAC flapping이라고 부른다.

loop 사고의 전형적 증상은 broadcast storm, CPU 상승, 관리 접속 불가, packet loss, FDB flapping이다.
그래서 L2에서는 loop를 막는 별도 제어가 필요하다.

## 14. STP는 loop를 막기 위해 일부 port를 막는다

**STP(Spanning Tree Protocol)** 계열은 switch들이 논리 tree를 만들고 loop가 되는 port를 blocking 상태로 두는 방식이다.
목표는 모든 switch가 연결되지만 loop는 없는 topology를 만드는 것이다.

비유하면 도로망에 여러 우회도로가 있어도 평상시에는 일부 차단기를 내려 한 방향 tree처럼 쓰는 것이다.
장애가 나면 차단기를 다시 열어 우회한다.
비유의 한계는 실제 STP는 BPDU, root bridge, port role, state transition 같은 절차를 가진다는 점이다.

운영 오개념:

| 오개념 | 바로잡기 |
| --- | --- |
| STP가 있으면 loop 사고가 불가능하다 | BPDU filter, 잘못된 edge 설정, 장비 버그, 장애 전환 중에는 사고가 날 수 있다 |
| STP는 모든 링크를 active-active로 쓴다 | 기본 목적은 loop 제거라 일부 경로를 막을 수 있다 |
| 서버 bond를 아무 switch 두 대에 꽂으면 된다 | MLAG/vPC/stack 같은 장비 기능과 정책이 맞아야 한다 |

## 15. LACP는 여러 물리 링크를 하나의 논리 링크처럼 묶는다

**LACP(Link Aggregation Control Protocol)**는 여러 물리 port를 하나의 link aggregation group으로 묶기 위한 제어 프로토콜이다.
목적은 대역폭 집계와 링크 장애 대응이다.

하지만 한 flow가 항상 모든 링크에 나뉘어 흐른다고 생각하면 안 된다.
많은 장비는 source/destination MAC, IP, port 같은 hash로 flow를 특정 member link에 배정한다.
따라서 단일 TCP flow 하나의 처리량은 member link 하나의 한계를 넘지 못할 수 있다.

```text
4 x 25 Gb/s LAG

여러 flow 전체 합: 최대 100 Gb/s에 가까울 수 있음
단일 flow 하나: 해시 결과가 탄 member 하나, 대략 25 Gb/s 한계 가능
```

## 16. MLAG는 두 switch를 하나처럼 보이게 하지만 만능이 아니다

**MLAG(Multi-Chassis Link Aggregation)**는 서로 다른 두 물리 switch에 걸쳐 LAG를 구성하게 해 주는 장비 기능군이다.
벤더마다 vPC, MC-LAG, MLAG 등 이름과 동작이 다르다.
목적은 switch 하나 장애에도 서버 uplink를 유지하는 것이다.

한계도 있다.
두 switch 사이 peer link와 keepalive 설계가 필요하다.
split-brain, inconsistent VLAN, orphan port, STP interaction, MAC sync 문제가 생길 수 있다.
MLAG는 “두 장비가 완전히 하나의 switch가 된다”는 뜻이 아니라, 특정 L2/LAG 동작을 조정해 endpoint에 하나처럼 보이게 하는 설계다.

## 17. Ethernet에서 Kubernetes까지 이어지는 감각

Kubernetes node도 결국 NIC를 통해 frame을 주고받는다.
pod network가 overlay를 쓰면 원래 packet이 VXLAN, Geneve 같은 tunnel 안에 다시 encapsulation될 수 있다.
underlay switch는 outer Ethernet/IP header를 보고 전달한다.
pod의 inner IP는 underlay switch가 직접 routing하지 않을 수 있다.

그래서 네트워크 장애를 볼 때는 질문을 나눠야 한다.

| 질문 | 보는 계층 |
| --- | --- |
| link가 up인가 | 물리/link |
| switch가 MAC을 어느 port에서 배웠나 | L2/FDB |
| VLAN이 맞나 | L2 segmentation |
| gateway MAC을 알아냈나 | ARP/NDP |
| 목적지 IP route가 있나 | L3 routing |
| MTU와 tunnel overhead가 맞나 | L2/L3/overlay |

## 18. 자주 틀리는 오개념

| 오개념 | 바로잡기 |
| --- | --- |
| MAC 주소는 인터넷 전체에서 목적지를 찾는다 | MAC은 현재 L2 domain 안에서 다음 수신자를 찾는다 |
| switch는 IP routing table로 forwarding한다 | 일반 L2 switch는 destination MAC과 VLAN을 본다 |
| broadcast와 unknown unicast flood는 같다 | 결과적으로 여러 port로 가지만 주소 의미가 다르다 |
| VLAN은 보안 장벽으로 충분하다 | 분리 도구지만 trunk/native VLAN 오류와 L3 정책 부재를 조심해야 한다 |
| trunk는 tag 없는 frame이 없다 | native/untagged VLAN 정책이 있을 수 있다 |
| LACP 4개 링크면 단일 flow도 4배 빨라진다 | flow hashing 때문에 단일 flow는 member 하나에 묶일 수 있다 |
| MLAG는 두 switch를 완전한 한 장비로 만든다 | 제한된 동기화와 장애 모델을 가진 설계다 |

## 19. 해설 문제

### 문제 1

MAC `aa`가 port 1에서 들어온 frame의 source로 보였다.
switch는 무엇을 학습하는가?

해설:

```text
aa -> port 1
```

switch는 source MAC으로 위치를 학습한다.

### 문제 2

Host A가 다른 subnet의 서버 S로 보낼 때 destination IP와 destination MAC은 누구인가?

해설:

```text
destination IP = 서버 S의 IP
destination MAC = default gateway의 MAC
```

### 문제 3

VLAN tag 없는 frame이 trunk로 들어왔다.
이 frame은 VLAN이 없는가?

해설:

아니다.
해당 port의 PVID/native VLAN 정책에 따라 특정 VLAN으로 분류될 수 있다.
장비 기본값을 확인하지 않으면 장애가 생긴다.

### 문제 4

VLAN 10에서 `aa -> port1`을 배웠다.
VLAN 20에서도 `aa`가 port1이라고 단정할 수 있는가?

해설:

단정하면 안 된다.
FDB는 VLAN별로 분리해 이해해야 한다.

## 20. 1차 출처와 더 읽기

- IP over Ethernet, Ethernet data field, padding, IPv4 EtherType, Ethernet broadcast mapping: [RFC 894](https://www.rfc-editor.org/rfc/rfc894.html)
- ARP가 Ethernet과 IPv4 주소를 매핑하는 동기: [RFC 826](https://www.rfc-editor.org/rfc/rfc826.html)
- IPv4가 local network protocol 위에 datagram을 싣는 모델: [RFC 791](https://www.rfc-editor.org/rfc/rfc791.html)
