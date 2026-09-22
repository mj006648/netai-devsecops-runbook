# 00. 신호에서 프레임과 패킷까지

범위: 이 장은 네트워크를 처음 보는 사람이 “정보가 어떻게 전기·빛·무선 신호가 되고, 다시 bit, frame, packet으로 해석되는가”를 잡기 위한 바닥 장이다.
Kubernetes, Cilium, DNS, TLS를 보기 전에 필요한 가장 낮은 단위를 다룬다.
실제 PHY 칩, 광모듈, 무선 변조, Ethernet 표준의 모든 세부 구현은 훨씬 복잡하다.
여기서는 운영자가 패킷 경로와 MTU, latency, encapsulation을 이해하는 데 필요한 모델을 세운다.

## 1. 정보는 의미이고, 신호는 물리 현상이다

**정보(information)**는 불확실성을 줄이는 내용이다.
“서버 A의 IP는 10.0.1.7이다”라는 문장은 사람이 읽는 정보다.
컴퓨터는 그 문장을 문자 코드와 byte로 표현하고, 네트워크 장치는 byte를 신호로 바꾼다.

**신호(signal)**는 정보를 싣기 위해 의도적으로 바꾼 물리량이다.
구리선에서는 전압과 전류가 바뀐다.
광섬유에서는 빛의 세기와 위상이 바뀐다.
무선에서는 전자기파의 진폭, 주파수, 위상 같은 성질이 바뀐다.

비유하면 정보는 편지의 내용이고, 신호는 편지를 싣는 트럭이다.
비유의 한계는 명확하다.
네트워크 신호는 트럭처럼 독립 물체가 도로를 달리는 것이 아니라, 매질과 회로 안에서 전자기적 변화가 전파되는 현상이다.

## 2. bit, byte, symbol을 분리한다

**bit(binary digit)**는 0 또는 1 중 하나의 값을 갖는 정보 단위다.
**byte**는 오늘날 보통 8 bit다.
**symbol**은 물리 계층이 한 번의 신호 상태로 구분해 보내는 단위다.

중요한 점은 `1 symbol = 1 bit`가 항상 아니라는 것이다.
어떤 방식은 symbol 하나에 1 bit만 담고, 어떤 방식은 symbol 하나에 여러 bit를 담는다.
더 많은 bit를 한 symbol에 담으려면 수신기가 더 미세한 차이를 구분해야 하므로 잡음에 더 민감해진다.

```text
예: 4단계 신호

전압 상태 0 -> bit 00
전압 상태 1 -> bit 01
전압 상태 2 -> bit 10
전압 상태 3 -> bit 11

symbol 1개가 2 bit를 표현한다.
```

이 예는 교육용이다.
실제 고속 Ethernet은 단순한 네 단계 전압표만으로 설명되지 않는다.
하지만 “bit는 정보 단위, symbol은 물리 신호 단위”라는 구분은 그대로 유효하다.

## 3. bit rate와 baud rate는 다르다

**bit rate**는 초당 몇 bit를 전달하는가다.
단위는 bit/s, b/s, bps로 쓴다.
**baud rate**는 초당 몇 symbol을 보내는가다.
단위는 baud다.

```text
symbol rate = 25 Gbaud
symbol 하나가 2 bit를 담음

bit rate = 25 Gsymbol/s x 2 bit/symbol = 50 Gbit/s
```

초보자가 자주 하는 실수는 100 Gb/s를 100 GB/s로 읽는 것이다.
작은 b는 bit, 큰 B는 byte다.
오버헤드를 무시해도 `100 Gb/s / 8 = 12.5 GB/s`다.
실제 애플리케이션 payload 처리량은 preamble, frame header, FCS, inter-frame gap, IP/TCP/TLS/HTTP header, 재전송, 혼잡 제어 때문에 더 작다.

## 4. clock은 “언제 읽을지”를 맞추는 약속이다

수신기는 선 위의 값을 아무 때나 읽으면 안 된다.
신호가 바뀌는 중간을 읽으면 0인지 1인지 애매할 수 있다.
그래서 송신과 수신은 bit나 symbol의 경계에 대한 시간 감각을 맞춰야 한다.

**clock**은 그 시간 기준이다.
동기식 링크는 별도의 clock을 보내거나 데이터 안에서 clock을 복구할 수 있게 encoding한다.
수신기는 clock recovery로 “지금이 symbol의 중앙쯤이니 읽기 좋다”는 시점을 찾는다.

비유하면 빠르게 지나가는 기차 창문 안의 글자를 읽을 때, 글자가 창 중앙에 왔을 때 읽어야 한다.
창틀 사이에서 읽으면 글자가 섞인다.
비유의 한계는 실제 링크에서는 지터, 위상 잡음, equalization, clock drift까지 고려해야 한다는 점이다.

## 5. encoding은 bit를 선로에 맞는 모양으로 바꾸는 일이다

**encoding**은 bit열을 물리 링크가 안정적으로 보낼 수 있는 신호열로 바꾸는 규칙이다.
왜 필요할까?
긴 0만 계속 보내면 수신기가 clock을 잃을 수 있다.
직류 성분이 너무 많으면 회로와 매질에 문제가 생길 수 있다.
오류 검출이나 제어 문자를 섞어야 할 수도 있다.

예를 들어 단순 NRZ 모델은 1을 높은 전압, 0을 낮은 전압으로 표현한다고 가르칠 수 있다.
하지만 긴 `00000000`은 변화가 없어서 clock recovery에 불리하다.
그래서 실제 링크는 scrambling, block coding, line coding 같은 방식을 쓴다.

운영자가 기억할 핵심은 이렇다.
애플리케이션 byte가 선로에 그대로 “ASCII 글자 모양”으로 흐르는 것이 아니다.
byte는 링크 장치 안에서 물리 전송에 맞는 symbol과 신호 패턴으로 바뀐다.

## 6. 오류는 사라지는 것이 아니라 발견하고 줄이는 것이다

신호는 잡음, 감쇠, 반사, 간섭, 불량 케이블, 불량 광모듈, 장비 queue overflow의 영향을 받는다.
네트워크는 오류 가능성을 0으로 만들지 않는다.
대신 여러 계층에서 오류를 줄이고, 발견하고, 재전송하거나 버린다.

**CRC(Cyclic Redundancy Check)**는 bit열을 다항식 나눗셈처럼 계산해 얻은 검사값이다.
Ethernet frame에는 FCS(Frame Check Sequence)가 붙고, FCS는 수신 측이 frame 손상을 발견하는 데 쓴다.
CRC는 암호학적 인증이 아니다.
공격자가 내용을 바꾸지 않았다는 보증이나 상대 신원 확인을 제공하지 않는다.

오류 처리의 계층을 나누면 이해가 쉽다.

| 계층 | 예 | 오류를 다루는 방식 |
| --- | --- | --- |
| 물리 계층 | 신호 품질, encoding | 신호 복구, 오류율 감소 |
| 링크 계층 | Ethernet FCS | 손상 frame 폐기 |
| 네트워크 계층 | IPv4 header checksum | IPv4 header 손상 검사, 실패 시 폐기 |
| 전송 계층 | TCP checksum, 재전송 | 손실·순서·중복 처리 |
| 응용 계층 | TLS 인증, HTTP status, 업무 검증 | 상대 인증, 변조 탐지, 의미 검증 |

IPv4는 header checksum을 갖지만 payload 신뢰성을 제공하지 않는다.
RFC 791은 IP가 end-to-end 신뢰성, 순서, 흐름 제어를 제공하지 않는다고 설명한다.
출처: [RFC 791](https://www.rfc-editor.org/rfc/rfc791.html).

## 7. frame은 한 링크에서 전달되는 상자다

**frame**은 링크 계층의 전송 단위다.
Ethernet에서 frame은 한 링크에서 다음 장비까지 전달된다.
frame의 목적지 MAC 주소는 “이 링크에서 누가 받아야 하는가”를 나타낸다.

**packet**은 보통 네트워크 계층 단위로 말한다.
IPv4에서는 IP datagram 또는 packet이 출발지 IP와 목적지 IP를 담고 여러 router를 거쳐 목적지 쪽으로 이동한다.
RFC 791은 IP가 packet-switched network 사이에서 datagram을 source에서 destination으로 보내는 기능을 제공한다고 설명한다.
출처: [RFC 791](https://www.rfc-editor.org/rfc/rfc791.html).

비유하면 packet은 목적지 도시 주소가 붙은 택배이고, frame은 현재 구간의 트럭 운송장이다.
router를 지나면 다음 도로 구간의 트럭 운송장이 새로 붙는다.
비유의 한계는 실제 packet은 물리 물체가 아니라 각 장비의 메모리와 포트 사이에서 다시 캡슐화되는 byte열이라는 점이다.

## 8. encapsulation은 “상위 단위를 하위 단위의 payload로 넣는 일”이다

**encapsulation**은 한 계층의 데이터를 아래 계층의 payload에 넣고, 아래 계층 header를 붙이는 작업이다.
반대 방향에서 header를 벗기며 해석하는 작업은 decapsulation이다.

```text
HTTP message
  -> TCP segment payload
     -> IPv4 packet payload
        -> Ethernet frame payload
           -> symbol과 신호
```

각 계층의 header는 관심사가 다르다.
HTTP header는 메서드, 경로, host, content type 같은 응용 의미를 담는다.
TCP header는 port, sequence number, ACK number 같은 연결 상태를 담는다.
IP header는 source/destination IP와 TTL 같은 라우팅 정보를 담는다.
Ethernet header는 source/destination MAC과 EtherType을 담는다.

RFC 894는 IP datagram이 Ethernet frame 안에 실릴 때 Ethernet type field가 IPv4를 나타내고, data field가 IP header 뒤에 IP data를 담는다고 설명한다.
출처: [RFC 894](https://www.rfc-editor.org/rfc/rfc894.html).

## 9. circuit switching과 packet switching은 자원 배정 방식이 다르다

**circuit switching**은 통신 전에 고정된 회선 또는 자원 경로를 예약하는 방식이다.
전화망을 떠올리면 된다.
연결이 유지되는 동안 일정한 자원이 묶여 있어 예측이 쉽지만, 말이 없는 순간에도 자원이 비효율적으로 묶일 수 있다.

**packet switching**은 데이터를 작은 packet으로 나누고, packet마다 network가 forwarding한다.
인터넷의 기본 감각은 packet switching이다.
여러 흐름이 같은 링크와 router queue를 공유하므로 자원을 효율적으로 쓸 수 있지만, 지연과 손실은 상황에 따라 달라진다.

초보자가 주의할 점은 “TCP connection”이라는 말 때문에 실제 물리 회선이 전용으로 예약된다고 오해하는 것이다.
TCP connection은 양 끝 host의 상태와 packet 교환 규칙이지, 인터넷 전체 경로에 전용선을 깔았다는 뜻이 아니다.
IPv4 자체는 datagram을 독립 entity로 다룬다.
출처: [RFC 791](https://www.rfc-editor.org/rfc/rfc791.html).

## 10. latency는 하나의 숫자가 아니라 여러 지연의 합이다

**latency**는 요청한 사건이 관측될 때까지 걸리는 시간이다.
네트워크에서는 최소한 네 종류를 나눈다.

| 이름 | 뜻 | 손계산 |
| --- | --- | --- |
| serialization delay | bit를 링크에 밀어 넣는 시간 | frame bit 수 / link bit rate |
| propagation delay | 신호가 매질을 지나가는 시간 | 거리 / 전파 속도 |
| queueing delay | 장비 queue에서 기다리는 시간 | 혼잡에 따라 변함 |
| processing delay | 장비가 header를 보고 처리하는 시간 | 장비 구현에 따라 변함 |

손계산을 해 보자.

```text
조건:
VLAN tag 없는 최대 Ethernet MAC frame = 1518 bytes
  = MAC header 14 + payload 1500 + FCS 4
wire에서 추가로 차지하는 preamble+SFD = 8 bytes
inter-frame gap(IFG) = 12 byte-times
link rate = 1 Gb/s

MAC frame만 계산:
1518 x 8 = 12144 bit
serialization delay = 12144 / 1,000,000,000 s
                    = 12.144 us

wire cost까지 계산:
(1518 + 8 + 12) x 8 = 12304 bit
wire-time = 12304 / 1,000,000,000 s
          = 12.304 us
```

10 Gb/s라면 같은 MAC frame을 미는 시간은 약 1.2144 us이고, preamble/SFD/IFG까지 포함한 wire-time은 약 1.2304 us다.
하지만 왕복 latency가 1/10로 줄었다고 단정하면 안 된다.
거리 전파 지연, switch/router queue, TCP handshake, TLS handshake, server processing은 따로 남는다.

전파 지연도 계산해 보자.

```text
조건:
광섬유 안 신호 속도 = 대략 200,000 km/s로 가정
거리 = 100 km

one-way propagation delay = 100 / 200,000 s
                          = 0.0005 s
                          = 0.5 ms
```

이는 교육용 근사다.
실제 경로는 직선이 아니며, 광장비와 router 처리, queue가 더해진다.

## 11. MTU는 한 번에 담을 수 있는 네트워크 계층 payload 상한이다

**MTU(Maximum Transmission Unit)**는 한 링크가 한 번에 싣는 network-layer packet 크기의 상한으로 많이 말한다.
일반 Ethernet에서 IPv4 datagram의 최대 크기를 1500 octets로 다루는 전통적 기준은 RFC 894에 나온다.
출처: [RFC 894](https://www.rfc-editor.org/rfc/rfc894.html).

MTU 1500에서 IPv4 header 20 byte, TCP header 20 byte, option 없음이라고 하면 TCP payload는 이렇게 계산한다.

```text
TCP payload 최대 = 1500 - 20 - 20 = 1460 bytes
```

이 1460은 HTTP body 최대값이 아니다.
TCP payload 안에는 HTTP header와 body 일부가 들어갈 수 있다.
HTTP message 하나가 TCP segment 하나에 딱 들어가야 하는 규칙도 없다.

## 12. OSI와 TCP/IP 모델은 학습 도구이지 구현 도면이 아니다

**OSI 7계층**은 물리, 데이터링크, 네트워크, 전송, 세션, 표현, 응용 계층으로 나누는 교육 모델이다.
**TCP/IP 모델**은 link, internet, transport, application처럼 인터넷 프로토콜 묶음을 더 직접적으로 설명한다.

둘 다 유용하지만 실제 구현을 정확히 자르는 칼은 아니다.
TLS는 전송 위에서 암호화된 record를 만들지만 HTTP/3에서는 QUIC과 결합된다.
NIC offload는 TCP/IP 처리 일부를 NIC가 돕는다.
VLAN, VXLAN, IPsec, tunnel, proxy는 계층 그림을 더 복잡하게 만든다.

그러므로 계층을 외우는 목적은 “어느 header가 어느 문제를 해결하는가”를 묻기 위해서다.
계층표 자체를 현실 구현과 1:1로 맞추려 하면 오히려 헷갈린다.

## 13. packet journey: 같은 byte가 이름을 바꿔 간다

브라우저가 HTTP 요청 byte를 만든다고 하자.

```text
1. 애플리케이션은 HTTP 요청 line, header, body를 만든다.
2. 전송 계층은 TCP segment 또는 QUIC packet으로 나눈다.
3. IP 계층은 source IP와 destination IP를 붙인다.
4. 링크 계층은 다음 hop의 MAC 주소를 붙여 Ethernet frame을 만든다.
5. PHY는 frame bit를 encoding하고 symbol로 보내며 신호로 전파한다.
6. switch는 frame의 MAC 주소를 보고 같은 LAN 안에서 전달한다.
7. router는 Ethernet header를 벗기고 IP header를 보고 다음 hop으로 보낸다.
8. 다음 링크에서는 새 Ethernet header가 붙는다.
9. 목적지 host는 역순으로 해석해 애플리케이션 byte를 복원한다.
```

여기서 IP destination은 최종 목적지를 가리키지만, Ethernet destination MAC은 현재 링크의 다음 수신자를 가리킨다.
router를 넘을 때 MAC 주소가 바뀌는 이유가 이것이다.

## 14. 자주 틀리는 오개념

| 오개념 | 바로잡기 |
| --- | --- |
| 전기 신호가 곧 0과 1이다 | 신호를 정해진 threshold, clock, encoding 규칙으로 해석해야 bit가 된다 |
| 1 baud는 항상 1 bit/s다 | symbol 하나가 여러 bit를 담을 수 있다 |
| packet과 frame은 같은 말이다 | packet은 보통 IP 계층, frame은 링크 계층 단위다 |
| TCP 연결은 전용 회선이다 | TCP는 end host 상태와 packet 교환 규칙이지 물리 회선 예약이 아니다 |
| MTU 1500이면 HTTP body가 1500 byte다 | IP/TCP/TLS/HTTP header와 segmentation을 따로 봐야 한다 |
| CRC가 있으니 보안상 안전하다 | CRC는 우발적 손상 검출용이지 인증이나 암호화가 아니다 |
| OSI 7계층은 실제 커널 코드 구조와 같다 | 좋은 학습 모델이지만 구현은 더 섞여 있다 |

## 15. 해설 문제

### 문제 1

25 Gbaud 링크가 symbol 하나에 2 bit를 담는다고 하자.
raw bit rate는 얼마인가?

해설:

```text
25 Gsymbol/s x 2 bit/symbol = 50 Gbit/s
```

### 문제 2

1 Gb/s 링크에서 1500 byte IP packet을 선로에 넣는 데 걸리는 serialization delay를 Ethernet header/FCS 없이 계산하라.

해설:

```text
1500 x 8 = 12000 bit
12000 / 1,000,000,000 = 0.000012 s = 12 us
```

### 문제 3

MTU 1500, IPv4 header 20 byte, TCP header 20 byte, TCP option 없음일 때 TCP payload 상한은?

해설:

```text
1500 - 20 - 20 = 1460 bytes
```

### 문제 4

router를 지나면 source/destination IP와 source/destination MAC은 각각 어떻게 되는가?

해설:

IP source/destination은 일반 forwarding에서는 최종 통신 당사자를 유지한다.
TTL 같은 IP header 일부는 바뀔 수 있다.
Ethernet source/destination MAC은 링크마다 새로 붙으므로 hop마다 바뀐다.

## 16. 1차 출처와 더 읽기

- IPv4 datagram, routing, TTL, checksum, IP의 비신뢰성: [RFC 791](https://www.rfc-editor.org/rfc/rfc791.html)
- IP over Ethernet, Ethernet data field, padding, IPv4 EtherType, 1500 octet IP datagram: [RFC 894](https://www.rfc-editor.org/rfc/rfc894.html)
- TCP segment와 byte stream의 기초: [RFC 9293](https://www.rfc-editor.org/rfc/rfc9293.html)
- UDP datagram 형식: [RFC 768](https://www.rfc-editor.org/rfc/rfc768.html)
- QUIC packet과 UDP 기반 transport: [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html)
