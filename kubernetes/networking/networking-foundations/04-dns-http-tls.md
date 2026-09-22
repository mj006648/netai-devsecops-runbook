# 04. DNS, HTTP, TLS

범위: 이 장은 사용자가 URL을 입력했을 때 DNS, TCP/QUIC, TLS, HTTP가 어떻게 이어지는지 설명한다.
recursive/authoritative DNS, TTL, negative cache, URL parsing, certificate trust, SNI, ALPN, HTTP/1.1·2·3, proxy, L4/L7 load balancing, layered error를 다룬다.
실습 명령이나 packet capture는 포함하지 않는다.

## 1. URL은 주소 문자열이 아니라 여러 필드의 묶음이다

**URL(Uniform Resource Locator)**은 resource를 찾기 위한 문자열 표현이다.
예를 들어:

```text
https://www.example.com:443/docs/index.html?x=1#section2
```

쪼개면 다음과 같다.

| 부분 | 값 | 뜻 |
| --- | --- | --- |
| scheme | `https` | 사용할 protocol 또는 접근 방식 |
| host | `www.example.com` | 연결 대상 이름 |
| port | `443` | transport endpoint 번호 |
| path | `/docs/index.html` | origin server 안의 resource path |
| query | `x=1` | resource 선택에 쓰는 추가 문자열 |
| fragment | `section2` | client 쪽 문서 위치 표시 |

fragment는 HTTP request로 서버에 보내지지 않는다.
브라우저가 문서 안 위치를 찾는 데 주로 쓴다.

## 2. DNS는 이름을 주소와 여러 record로 바꾸는 분산 database다

**DNS(Domain Name System)**는 이름을 IP 주소 같은 resource record로 조회하는 분산 시스템이다.
처음에는 하나의 HOSTS.TXT 파일을 배포하는 방식이었지만, host 수와 변경 요구가 커지면서 계층적이고 분산된 DNS가 필요해졌다.
RFC 1034는 DNS의 등장 배경과 목표를 설명한다.
출처: [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034.html).

DNS는 단순히 “domain을 IP로 바꾸는 것”보다 넓다.
A record는 IPv4 주소, AAAA record는 IPv6 주소, MX는 mail exchanger, CNAME은 canonical name alias를 나타낸다.
서비스 discovery와 정책 record도 많다.

## 3. Resolver, recursive server, authoritative server

**stub resolver**는 애플리케이션이나 OS 쪽에서 DNS 질의를 시작하는 작은 resolver다.
보통 recursive resolver에게 물어본다.

**recursive resolver**는 client 대신 root, TLD, authoritative server를 따라가며 답을 찾고 cache한다.
ISP, 조직 내부 DNS, public resolver가 여기에 해당할 수 있다.

**authoritative name server**는 특정 zone에 대한 권위 있는 데이터를 가진 server다.
`example.com` zone의 A record를 최종적으로 대답할 수 있는 쪽이다.

RFC 1034는 name server, resolver, zone, authority 개념을 설명한다.
출처: [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034.html).

## 4. Recursive DNS journey

`www.example.com`의 A record를 조회한다고 하자.

```text
1. browser/application이 OS resolver에게 묻는다.
2. OS 또는 local stub resolver가 recursive resolver에게 묻는다.
3. recursive resolver cache에 없으면 root server에게 .com 담당을 묻는다.
4. root server는 .com TLD server 정보를 알려준다.
5. recursive resolver가 .com TLD server에게 example.com 담당을 묻는다.
6. TLD server는 example.com authoritative server를 알려준다.
7. recursive resolver가 authoritative server에게 www.example.com A를 묻는다.
8. authoritative server가 answer와 TTL을 준다.
9. recursive resolver는 cache하고 client에게 답한다.
```

실제 DNS에는 CNAME, DNSSEC, EDNS, TCP fallback, 여러 record, search domain, split-horizon, negative cache가 섞일 수 있다.
하지만 기본 journey는 “cache가 없으면 계층을 따라 권위자를 찾아간다”이다.

## 5. TTL은 cache가 믿을 수 있는 시간이다

**TTL(Time To Live)**은 DNS record를 cache할 수 있는 시간이다.
TTL이 300이면 resolver는 그 record를 최대 300초 정도 cache할 수 있다.
TTL이 짧으면 변경 반영은 빨라질 수 있지만 authoritative server 부하와 조회 latency가 늘 수 있다.
TTL이 길면 cache 효율은 좋지만 변경 전파가 늦다.

DNS는 강한 동시 일관성 database가 아니다.
RFC 1034도 DNS가 distributed database이고 caching과 refresh timeout을 사용한다고 설명한다.
출처: [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034.html).

## 6. Negative cache는 “없음”도 cache한다

DNS는 존재하는 record만 cache하지 않는다.
NXDOMAIN 같은 “이 이름은 없다”는 결과도 일정 시간 cache할 수 있다.
이를 **negative caching**이라고 한다.
RFC 2308은 DNS negative caching을 설명한다.
출처: [RFC 2308](https://www.rfc-editor.org/rfc/rfc2308.html).

운영 오개념:

| 오개념 | 바로잡기 |
| --- | --- |
| record를 만들면 모든 client가 즉시 본다 | resolver cache와 TTL 때문에 지연된다 |
| 없는 이름을 잠깐 조회한 것은 영향이 없다 | NXDOMAIN도 negative cache될 수 있다 |
| TTL 0이면 모든 문제가 사라진다 | resolver와 client 구현, 부하, 중간 cache를 고려해야 한다 |

## 7. DNS 답은 연결 성공을 보장하지 않는다

DNS가 IP를 줬다는 것은 “이 이름에 대해 이런 주소 record가 있다”는 뜻이다.
그 IP로 route가 되는지, TCP port가 열려 있는지, TLS certificate가 맞는지, HTTP route가 있는지는 별도 문제다.

계층별로 보면:

| 성공한 것 | 아직 모르는 것 |
| --- | --- |
| DNS A/AAAA 조회 성공 | network reachability |
| TCP connect 성공 | TLS trust |
| TLS handshake 성공 | HTTP resource 존재 |
| HTTP 200 | 업무 처리의 내부 commit |

## 8. HTTP는 resource에 대한 request/response protocol이다

**HTTP(Hypertext Transfer Protocol)**는 resource에 대한 request와 response 의미를 정의한다.
method, target, status code, field, content 같은 개념이 있다.
RFC 9110은 HTTP semantics를 정의한다.
출처: [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html).

HTTP는 transport가 아니다.
HTTP/1.1과 HTTP/2는 주로 TCP 위에서 쓰이고, HTTP/3은 QUIC 위에서 쓰인다.
HTTP가 “데이터를 안정적으로 보내는 기능”을 직접 제공하는 것이 아니라 아래 transport의 특성 위에서 message 의미를 정한다.

## 9. HTTP/1.1 message의 기본 감각

HTTP/1.1 request는 start-line, header fields, 빈 줄, optional content로 볼 수 있다.
RFC 9112가 HTTP/1.1 messaging을 정의한다.
출처: [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html).

```http
GET /docs/index.html HTTP/1.1
Host: www.example.com
User-Agent: example-client

```

POST body가 있으면 `Content-Length`나 chunked transfer coding 같은 message boundary 규칙이 필요하다.
TCP는 byte stream이므로 HTTP가 자기 message 경계를 정해야 한다.

## 10. TLS는 암호화만이 아니라 인증과 무결성을 포함한다

**TLS(Transport Layer Security)**는 통신 보안을 제공하는 protocol이다.
TLS 1.3은 기밀성, 무결성, endpoint 인증을 제공하도록 설계됐다.
RFC 8446이 TLS 1.3을 정의한다.
출처: [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html).

TLS에서 중요한 일:

- client와 server가 protocol version과 cipher suite를 협상한다.
- server가 certificate chain을 보낸다.
- client가 trust anchor와 hostname을 기준으로 certificate를 검증한다.
- key exchange를 통해 session key를 만든다.
- 이후 application data를 암호화하고 무결성을 검증한다.

TLS가 성공했다는 것은 대체로 “이름 검증과 certificate chain 검증을 통과하고 암호화된 채널이 열렸다”는 뜻이다.
HTTP 요청의 업무 성공을 뜻하지 않는다.

## 11. Certificate trust는 chain과 이름 검증이다

server certificate는 public key와 subject name 정보를 담는다.
client는 certificate chain이 신뢰하는 root CA까지 이어지는지 확인한다.
또 URL의 host name이 certificate의 SAN(Subject Alternative Name)에 맞는지 확인한다.

오개념:

| 오개념 | 바로잡기 |
| --- | --- |
| 암호화만 되면 안전하다 | 상대가 누구인지 certificate 검증이 필요하다 |
| certificate가 있으면 모든 domain에 유효하다 | hostname 검증 범위가 맞아야 한다 |
| expired certificate도 암호화는 되니 괜찮다 | trust 검증 실패로 연결이 거부될 수 있다 |

## 12. SNI는 TLS handshake에서 서버 이름을 알려준다

**SNI(Server Name Indication)**는 client가 TLS handshake 중 접속하려는 hostname을 알려주는 확장이다.
한 IP에서 여러 HTTPS site를 운영할 때 server가 적절한 certificate를 고르는 데 필요하다.

SNI는 ECH(Encrypted ClientHello)를 쓰지 않는 전통적 TLS 1.2/1.3 handshake에서 관측 가능한 metadata일 수 있다.
즉 HTTP payload와 TLS 1.3 server certificate가 암호화되어도, ClientHello의 hostname은 일부 환경에서 드러날 수 있다.
ECH는 이 metadata를 줄이기 위한 기술이지만, 운영 기초에서는 “TLS가 모든 metadata를 항상 숨기지는 않는다”를 기억한다.

## 13. ALPN은 HTTP 버전을 협상한다

**ALPN(Application-Layer Protocol Negotiation)**은 TLS handshake 안에서 어떤 application protocol을 쓸지 협상하는 확장이다.
예를 들어 client가 `h2`와 `http/1.1`을 제안하고 server가 하나를 고를 수 있다.

HTTP/2와 HTTP/1.1을 같은 443 port에서 제공할 수 있는 이유 중 하나가 ALPN이다.
HTTP/3은 QUIC 위에서 동작하며 TLS 사용 방식도 TCP+TLS와 다르다.

## 14. 암호화가 숨기는 것과 남기는 것

HTTPS가 숨기는 것:

- HTTP path.
- HTTP request/response header 대부분.
- HTTP body.
- cookie와 authorization header.

남을 수 있는 metadata:

- client/server IP.
- port.
- timing과 packet size pattern.
- DNS query가 별도 평문 경로라면 조회 이름.
- ECH가 없는 TLS ClientHello의 SNI hostname.
- TLS 1.2 이하에서는 server certificate chain. TLS 1.3에서는 server certificate가 handshake traffic key로 암호화된다.

따라서 “HTTPS니까 아무것도 안 보인다”는 틀렸다.
“내용 대부분은 보호되지만 TLS 버전과 ECH 사용 여부에 따라 남는 traffic metadata가 다르다”가 더 정확하다.

## 15. URL 입력부터 HTTP request까지의 전체 여정

`https://www.example.com/docs`를 입력했다고 하자.

```text
1. URL parser가 scheme=https, host=www.example.com, path=/docs를 분리한다.
2. port가 없으므로 https 기본 port 443을 선택한다.
3. DNS로 www.example.com의 A/AAAA record를 찾는다.
4. route lookup으로 next hop을 정한다.
5. ARP 또는 NDP로 next-hop link-layer address를 찾는다.
6. TCP 기반 HTTPS라면 TCP 3-way handshake를 한다.
7. TLS handshake를 한다.
8. certificate chain과 hostname을 검증한다.
9. ALPN으로 HTTP/2 또는 HTTP/1.1 등을 정한다.
10. HTTP request를 만든다.
11. TLS record로 암호화한다.
12. TCP는 byte stream을 segment로 보낸다.
13. server가 복호화하고 HTTP request를 해석한다.
14. server가 HTTP response를 보낸다.
```

HTTP/3이면 6번의 TCP handshake 대신 QUIC handshake가 오고, TLS 1.3이 QUIC에 통합된다.
출처: [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html), [RFC 9001](https://www.rfc-editor.org/rfc/rfc9001.html), [RFC 9114](https://www.rfc-editor.org/rfc/rfc9114.html).

## 16. HTTP/1.1, HTTP/2, HTTP/3 차이

| 버전 | 일반 transport | 핵심 특징 | 주의 |
| --- | --- | --- | --- |
| HTTP/1.1 | TCP | text 기반 message, keep-alive 가능 | 한 연결에서 pipeline은 제한적으로 쓰였고 head-of-line 문제가 있음 |
| HTTP/2 | TCP | binary framing, multiplexing, header compression | TCP packet loss가 모든 stream을 막을 수 있음 |
| HTTP/3 | QUIC/UDP | QUIC stream 위의 HTTP, TCP HoL 문제 감소 | UDP 차단, QUIC 운영 가시성, LB 지원 고려 |

RFC 9113은 HTTP/2를, RFC 9114는 HTTP/3을 정의한다.
출처: [RFC 9113](https://www.rfc-editor.org/rfc/rfc9113.html), [RFC 9114](https://www.rfc-editor.org/rfc/rfc9114.html).

## 17. Connection reuse와 multiplexing

HTTP/1.1 keep-alive는 같은 TCP connection을 여러 request에 재사용할 수 있게 한다.
매 request마다 TCP/TLS handshake를 새로 하지 않아도 되므로 latency와 CPU 비용을 줄인다.

HTTP/2는 하나의 TCP connection 안에서 여러 stream을 multiplexing한다.
여러 request/response가 frame 단위로 섞여 오갈 수 있다.

HTTP/3은 QUIC stream 위에서 multiplexing한다.
한 stream의 손실이 다른 stream 처리 전체를 막는 문제를 줄인다.

오개념:

| 오개념 | 바로잡기 |
| --- | --- |
| HTTP/2는 TCP를 안 쓴다 | HTTP/2는 일반적으로 TCP 위에서 쓴다 |
| HTTP/3은 암호화가 없다 | QUIC은 TLS 1.3을 사용한다 |
| multiplexing이면 무조건 빨라진다 | loss, server 처리, prioritization, CPU, congestion에 따라 다르다 |

## 18. Proxy는 대신 연결하고 대신 말하는 중간자다

**proxy**는 client와 server 사이에서 request/response를 중계하는 구성요소다.
forward proxy는 client 쪽 대리자에 가깝고, reverse proxy는 server 앞단 대리자에 가깝다.

reverse proxy의 역할:

- TLS termination.
- HTTP routing.
- compression.
- authentication 연동.
- rate limiting.
- backend load balancing.
- logging.

proxy가 있으면 client의 TCP/TLS 연결과 backend의 TCP/TLS 연결은 별개일 수 있다.
client가 본 source IP, server가 본 source IP, HTTP header의 `X-Forwarded-For` 또는 `Forwarded` 의미를 구분해야 한다.

## 19. L4 load balancing과 L7 load balancing

**L4 load balancing**은 TCP/UDP 5-tuple 같은 transport 계층 정보를 기준으로 흐름을 backend로 보낸다.
payload를 깊게 해석하지 않는다.
TLS를 종료하지 않는 TCP pass-through가 여기에 가까울 수 있다.

**L7 load balancing**은 HTTP host, path, header, method 같은 application 정보를 보고 backend를 고른다.
이 경우 load balancer 또는 ingress proxy가 HTTP를 해석해야 하며, HTTPS라면 보통 TLS termination이 필요하다.

비교:

| 항목 | L4 | L7 |
| --- | --- | --- |
| 주 기준 | IP/port/protocol | HTTP host/path/header |
| TLS 내부 보기 | 보통 못 봄 | termination 시 볼 수 있음 |
| 장점 | 단순하고 빠름 | 세밀한 routing |
| 주의 | app 의미 기반 분기 어려움 | 인증서, header, timeout, body size 정책 필요 |

## 20. Error를 계층별로 읽는다

하나의 “사이트가 안 열린다”도 여러 계층의 실패일 수 있다.

| 관측 | 가능한 계층 | 예 |
| --- | --- | --- |
| 이름 해석 실패 | DNS | NXDOMAIN, SERVFAIL, timeout |
| IP는 나왔지만 연결 실패 | routing/firewall/TCP | SYN timeout, RST |
| TLS alert 또는 certificate error | TLS | hostname mismatch, expired cert |
| HTTP 404 | HTTP routing/application | path 없음 |
| HTTP 502 | proxy/backend | upstream 연결 실패 |
| HTTP 503 | service availability | backend 없음, overload |
| HTTP 504 | timeout | upstream response 지연 |

중요한 태도는 가장 위의 오류 메시지만 보고 아래 계층 결론을 내리지 않는 것이다.
HTTP 502는 DNS 문제일 수도, upstream TCP 문제일 수도, TLS upstream 문제일 수도, backend process crash일 수도 있다.

## 21. DNS와 HTTP cache를 혼동하지 않는다

DNS TTL은 이름 record cache 시간이다.
HTTP cache는 response representation을 재사용하는 정책이다.
둘은 서로 다른 계층이다.

예를 들어 DNS TTL이 끝나도 browser HTTP cache에 문서가 남아 있을 수 있다.
반대로 DNS cache는 살아 있지만 HTTP cache가 만료되어 새 request를 보낼 수 있다.

HTTP caching semantics는 RFC 9110과 별도 HTTP caching 문서에서 다룬다.
이 장에서는 “DNS TTL과 HTTP cache header는 다르다”를 정확히 잡는다.

## 22. Host header와 TLS SNI는 다르다

HTTP/1.1의 `Host` field는 HTTP request 안에 있다.
TLS SNI는 TLS handshake 안에 있다.
둘 다 hostname과 관련되지만 계층과 시점이 다르다.

```text
TCP connect
TLS ClientHello with SNI
TLS certificate selection and handshake
encrypted HTTP request with Host header
```

SNI가 틀리면 server가 다른 certificate를 줄 수 있다.
Host header가 틀리면 HTTP virtual host routing이 다른 backend로 갈 수 있다.
둘이 항상 같은 값이어야 하는 것은 구성에 따라 다르지만, 일반 웹 요청에서는 맞춰야 기대한 site에 도달한다.

## 23. Kubernetes Ingress로 이어지는 감각

Kubernetes Ingress나 Gateway는 대체로 L7 routing을 제공한다.
client는 ingress controller의 IP로 연결한다.
TLS termination이 ingress에서 일어나면 backend pod는 평문 HTTP를 받을 수도 있고, 재암호화된 HTTPS를 받을 수도 있다.

문제를 볼 때 질문:

| 질문 | 계층 |
| --- | --- |
| DNS가 ingress IP를 가리키는가 | DNS |
| client가 ingress IP:port에 연결되는가 | L3/L4 |
| certificate가 hostname에 맞는가 | TLS |
| SNI와 Host가 기대한 값인가 | TLS/HTTP |
| ingress rule path가 맞는가 | HTTP routing |
| service endpoint가 있는가 | Kubernetes service discovery |
| backend app이 올바른 status를 주는가 | application |

이 장은 Kubernetes 설정을 다루지 않지만, 계층 질문을 분리하는 기준을 제공한다.

## 24. 자주 틀리는 오개념

| 오개념 | 바로잡기 |
| --- | --- |
| DNS 성공이면 접속도 된다 | routing, TCP/QUIC, TLS, HTTP는 별도다 |
| TTL을 낮추면 즉시 전 세계 반영된다 | cache와 resolver 동작 때문에 즉시는 아니다 |
| HTTPS는 metadata도 모두 숨긴다 | IP, port, timing, 크기, 일부 hostname 정보가 남을 수 있다 |
| SNI와 Host header는 같은 계층이다 | SNI는 TLS, Host는 HTTP다 |
| HTTP/2는 UDP다 | HTTP/2는 일반적으로 TCP 위에서 동작한다 |
| HTTP/3은 TCP를 빠르게 만든 것이다 | HTTP/3은 QUIC 위의 HTTP다 |
| L4 LB도 path routing이 가능하다 | path는 HTTP L7 정보다 |
| 502는 항상 backend app 버그다 | proxy에서 upstream 연결/TLS/DNS 실패도 502가 될 수 있다 |

## 25. 해설 문제

### 문제 1

`https://api.example.com/v1/users?limit=10#top`에서 DNS 조회에 쓰이는 host는 무엇인가?

해설:

`api.example.com`이다.
path, query, fragment는 DNS 조회 이름이 아니다.

### 문제 2

DNS A record TTL이 600초다.
record를 바꾼 직후 모든 client가 새 IP를 볼 수 있는가?

해설:

아니다.
기존 resolver cache는 TTL 동안 이전 값을 사용할 수 있다.

### 문제 3

TLS certificate는 통과했는데 HTTP 404가 나왔다.
어느 계층은 성공했고, 어느 계층을 봐야 하는가?

해설:

DNS, TCP, TLS는 대체로 성공했다.
HTTP host/path routing 또는 application resource 존재 여부를 봐야 한다.

### 문제 4

L7 load balancer가 `/api`와 `/static`을 다른 backend로 보내려면 어떤 정보를 봐야 하는가?

해설:

HTTP request target의 path를 봐야 한다.
HTTPS라면 LB가 TLS를 terminate하거나 HTTP를 해석할 수 있는 위치에 있어야 한다.

### 문제 5

SNI는 맞는데 HTTP Host header가 다른 값이면 어떤 일이 생길 수 있는가?

해설:

TLS certificate 선택은 기대대로 되었지만, HTTP virtual host routing은 다른 site나 backend로 갈 수 있다.
계층이 다르기 때문이다.

## 26. 1차 출처와 더 읽기

- DNS concepts, recursive/iterative, resolver, authoritative server, TTL/caching 개념: [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034.html)
- DNS implementation and message/resource record specification: [RFC 1035](https://www.rfc-editor.org/rfc/rfc1035.html)
- DNS negative caching: [RFC 2308](https://www.rfc-editor.org/rfc/rfc2308.html)
- TLS 1.3: [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html)
- QUIC transport: [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html)
- TLS for QUIC: [RFC 9001](https://www.rfc-editor.org/rfc/rfc9001.html)
- HTTP semantics: [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html)
- HTTP/1.1 messaging: [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html)
- HTTP/2: [RFC 9113](https://www.rfc-editor.org/rfc/rfc9113.html)
- HTTP/3: [RFC 9114](https://www.rfc-editor.org/rfc/rfc9114.html)
