# 00a. 객체가 바이트와 패킷이 되는 과정

[학습 목차](README.md) · 이전: [계층 지도와 기초 용어](00-map-and-vocabulary.md) · 다음: [Linux 읽기·쓰기](01-linux-read-write.md)

범위: 회원 한 명을 등록하는 **교육용 HTTP/1.1 평문·TCP·IPv4·Ethernet 경로**다.
이 장의 중첩 그림은 IP 단편화·VLAN 태그·터널을 생략한다. 실제 서비스는 HTTPS, 다른 HTTP 버전, 프록시, 다른 링크 기술을 쓸 수 있다.
핵심 질문은 “지금 말하는 바이트와 완료가 **어느 계층의 것인가?**”다.
OSI 7계층 이름을 먼저 외우기보다, 이 예에서 실제로 이어지는 표현과 단위를 따라가자.

## 1. 먼저 다섯 단어를 분리한다

| 단어 | 뜻 | 이 장의 예 |
| --- | --- | --- |
| data | 해석할 대상 전체를 가리키는 넓은 말 | 회원 이름, 전송 중인 바이트, 저장된 행 모두 문맥에 따라 data |
| object | 프로그램이 다루는 값과 구조 | Python `dict` 한 개 |
| record | 같은 종류의 항목 한 건이라는 논리적 단위 | 회원 한 명의 정보 |
| schema | 필드 이름·타입·필수 여부 등의 해석 규칙 | `member_id`는 문자열, `note`는 문자열 |
| byte | 파일·네트워크 API가 다루는 8비트 단위 | UTF-8로 인코딩된 JSON의 한 옥텟 |

`object`와 `record`는 반드시 하나의 네트워크 패킷에 들어가야 하는 단위가 아니다.
회원 객체 하나를 여러 바이트 조각으로 보낼 수도 있고, 한 TCP 연결에서 여러 회원 요청을 보낼 수도 있다.
반대로 JSON을 해석해 얻은 `dict`에도 필드가 있다는 사실만으로 `member_id`의 타입과 중복 허용 정책까지 검증한 것은 아니다.

## 2. header·body·payload·metadata는 기준을 붙여 말한다

**Header**는 해당 형식의 내용을 해석할 단서, **body**는 그 형식에서 헤더와 구분되는 본문이다.
**Payload**는 한 계층이 상위 계층에서 받아 실어 나르는 내용이다.
**Metadata**는 내용의 의미·위치·형식·상태를 설명하는 정보다.
이 말들은 전 세계에서 딱 한 범위를 가리키는 고유명사가 아니다.

~~~text
Ethernet frame
├─ Ethernet header: 다음 목적지 MAC 주소 등
├─ Ethernet data field: IPv4 packet을 담음(필요 시 뒤에 padding)
│  ├─ IPv4 header: 출발지·목적지 IP 주소 등
│  └─ IPv4 payload = TCP segment 전체
│     ├─ TCP header: 포트·sequence number 등
│     └─ TCP payload = HTTP/1.1 메시지 바이트의 일부 또는 전부
│        ├─ HTTP start-line + headers: 메서드·경로·Content-Type 등
│        └─ HTTP body: JSON을 UTF-8로 인코딩한 바이트
└─ Ethernet trailer: FCS(프레임 오류 검사 값)
~~~

따라서 **HTTP 헤더도 IP payload 안에 있다**. IP 관점에서는 HTTP 헤더와 body를 모두 TCP 안의 데이터로 실어 나르기 때문이다.
그림의 `TCP payload = HTTP 메시지 일부 또는 전부`도 중요하다. HTTP 메시지 하나가 segment 하나에 딱 맞아야 한다는 규칙은 없다.
파일 전송이라면 HTTP body가 JSON 대신 파일 바이트일 수 있다. 이때 **파일도 HTTP payload**라고 부를 수 있다.
파일을 디스크에 저장한 뒤에는 같은 바이트가 저장 객체의 내용이며, 파일 이름·크기·생성 시각 등은 그 저장 계층의 metadata다.
`Content-Type`은 HTTP metadata인 반면 `member_id`는 이 예의 업무 데이터다. [HTTP 메시지 형식](https://www.rfc-editor.org/rfc/rfc9112.html#section-2.1), [HTTP content](https://www.rfc-editor.org/rfc/rfc9110.html#section-6.4)

## 3. Python 객체에서 JSON 바이트로

**직렬화**는 프로그램 객체를 교환·저장할 수 있는 형식으로 표현하는 작업이다.
JSON을 택하면 키 이름, 따옴표, 중괄호가 들어간 **텍스트**가 나온다.
**문자 인코딩**은 그 텍스트의 문자를 UTF-8 같은 규칙으로 **바이트**로 바꾼다.
다른 시스템의 수신자는 바이트를 UTF-8로 해석하고, JSON을 파싱하고, 필요한 schema·업무 규칙을 검증한다.
폐쇄된 환경에 한정되지 않는 시스템 간 JSON 교환에서는 UTF-8을 사용하도록 표준이 정한다. [JSON RFC 8259 §8.1](https://www.rfc-editor.org/rfc/rfc8259.html#section-8.1)

아래 예제는 네트워크나 파일에 접근하지 않는다. Python 3 표준 라이브러리만 사용한다.

~~~python
import json

member = {"member_id": "m7", "note": "안녕"}
json_text = json.dumps(member, ensure_ascii=False, separators=(",", ":"))
body = json_text.encode("utf-8")

print(json_text)
print(len("안녕"), len("안녕".encode("utf-8")))
print(len(json_text), len(body))
print(json.loads(body.decode("utf-8")) == member)
~~~

~~~text
{"member_id":"m7","note":"안녕"}
2 6
30 34
True
~~~

`안녕`은 Python 문자열 길이로 2지만, UTF-8로는 6바이트다.
JSON 전체도 30문자와 34바이트로 다르다. 따라서 HTTP의 `Content-Length`를 문자 수 30으로 적으면 본문이 중간에서 끊긴다.
이 예에서는 본문이 전송할 UTF-8 바이트 그대로이므로 `Content-Length: 34`다.
HTTP/1.1에서 `Content-Length`가 적용되는 경우 그 값은 **본문의 옥텟 수**이며, chunked 전송 등 다른 메시지 경계 규칙도 있다. [HTTP/1.1 메시지 경계](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.2)

### 직렬화, 인코딩, 압축, 암호화를 헷갈리지 않는다

| 작업 | 입력 → 출력 | 왜 하는가? | 되돌리는 데 필요한 것 |
| --- | --- | --- | --- |
| 직렬화 | 객체 → JSON 같은 교환 표현 | 객체의 구조를 전달 | 해당 형식 파서·의미 규칙 |
| 문자 인코딩 | 텍스트 → UTF-8 바이트 | 문자를 바이트로 전달 | 같은 인코딩 규칙 |
| 압축 | 바이트 → 보통 더 짧은 바이트 | 크기·전송 비용 감소 | 압축 해제 알고리즘 |
| 암호화 | 평문 바이트 → 암호문 바이트 | 허가되지 않은 읽기 방지 | 키와 알고리즘, 해당 방식의 검증 절차 |

압축이 항상 더 작은 결과를 만든다는 보장은 없다. 아주 짧거나 이미 압축된 입력은 오히려 커질 수 있다.
암호화는 **기밀성**에 관한 말이다. 바이트 변조 탐지나 상대 신원 확인까지 주장하려면 인증된 암호화 방식과 키·인증서 검증이 어떻게 쓰였는지 확인해야 한다. [TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html)

**Base64는 암호화도 압축도 아니다.** 임의의 바이트를 제한된 문자 집합으로 표현하는 인코딩이다.
3바이트를 4문자로 바꾸므로 긴 입력은 대체로 원본의 4/3 크기가 되고, 끝의 남은 바이트에는 보통 `=` padding이 붙는다.
짧은 입력은 반올림 효과 때문에 비율이 더 크다. 예를 들어 `b"hi"` 2바이트는 `aGk=` 4문자다. 누구나 다시 디코딩할 수 있다. [Base64 RFC 4648 §4](https://www.rfc-editor.org/rfc/rfc4648.html#section-4)

## 4. JSON 바이트를 HTTP/1.1 메시지에 넣는다

아래는 앞의 `body`를 넣은 **HTTP/1.1 평문 요청의 읽기 쉬운 표기**다.
실제 줄 끝은 `CRLF`(`\r\n`)이며 빈 줄도 `CRLF` 한 번으로 나타낸다.
표시된 줄바꿈 자체를 실제 전송 바이트라고 가정하면 안 된다.
이 예는 요청 형식과 경계를 보여 주며 서버에 보내는 실행 명령은 아니다.

~~~http
POST /members HTTP/1.1
Host: example.test
Content-Type: application/json
Content-Length: 34

{"member_id":"m7","note":"안녕"}
~~~

시작 줄의 `POST`는 동작, `/members`는 대상 경로다.
`Host`는 대상 호스트, `Content-Type`은 본문 표현을 해석할 미디어 타입이다.
헤더 뒤의 빈 줄부터 body가 시작한다. 이 body는 위의 JSON 바이트 34개다.
HTTP 성공 응답은 서버가 정한 HTTP 수준의 결과일 뿐, 원격 DB의 영속 commit까지 자동으로 증명하지 않는다. [HTTP 메시지](https://www.rfc-editor.org/rfc/rfc9112.html#section-2), [미디어 타입](https://www.rfc-editor.org/rfc/rfc9110.html#section-8.3)

`Content-Length: 34`는 **HTTP body** 길이다. HTTP 시작 줄·헤더·TCP/IP/Ethernet 헤더를 포함하지 않는다.
압축된 body를 전송하면 전송된 표현의 바이트 수를 세어야 하고, `Transfer-Encoding: chunked`처럼 경계 규칙이 달라진 HTTP/1.1 메시지에는 이 단순 예를 그대로 옮길 수 없다. [RFC 9110 Content-Length](https://www.rfc-editor.org/rfc/rfc9110.html#section-8.6), [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html#section-6)

## 5. TCP는 메시지 상자가 아니라 바이트 흐름이다

HTTP/1.1 평문 요청을 TCP에 쓰면 TCP는 **순서 있는 바이트 스트림**을 제공한다.
TCP는 그 스트림을 네트워크 상황에 맞게 segment로 나누어 IP에 맡긴다.
상대 TCP는 sequence number를 이용해 순서를 맞추고 손실된 데이터의 재전송을 처리한다.
연결이 정상적으로 데이터를 전달할 때의 보장은 **그 연결의 바이트 순서와 손실 복구**에 관한 것이다. 연결 실패 뒤의 전달 완료나 서버의 업무 처리·DB commit까지 보장하지 않는다. [TCP RFC 9293 §3.4](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.4)

~~~text
애플리케이션의 write/send 한 번: [HTTP 요청 바이트 100개]
송신 TCP의 segment 예:         [40개] [60개]
수신 애플리케이션의 recv 예:    [13개] [87개]
~~~

숫자는 가능한 **개념 예시**일 뿐 실제 분할을 예측한 값이 아니다.
`send` 한 번 = TCP segment 한 개 = IP packet 한 개 = `recv` 한 번이라는 등식은 성립하지 않는다. `send` 자체도 요청한 바이트를 일부만 받아들일 수 있으므로 반환된 바이트 수를 확인해야 한다.
`recv(n)`의 `n`은 **한 번에 받을 최대 바이트 수**다. TCP 소켓에서 양수 크기 `n`을 요청해도 그보다 적게 반환할 수 있다. 이 조건에서 빈 바이트열은 남은 수신 데이터를 다 읽은 뒤 상대의 정상적인 송신 종료를 만났음을 나타낸다.
`recv(0)`의 빈 결과는 송신 종료 판별에 쓰지 않는다.
그러므로 본문 34바이트를 읽으려면 프로토콜이 정한 경계를 알고 모자란 부분을 계속 읽어야 한다. [Python `socket.recv`](https://docs.python.org/3/library/socket.html#socket.socket.recv)

다음은 순수 메모리에서 **길이 1바이트 + payload**라는 장난감 framing 규칙을 시험한다.
HTTP의 framing이 아니다. 네트워크를 열지 않고 “읽은 조각”의 경계가 메시지 경계와 다르다는 점만 보여 준다.

~~~python
messages = [b"hi", "안녕".encode("utf-8")]
wire = b"".join(bytes([len(item)]) + item for item in messages)
chunks = [wire[:1], wire[1:4], wire[4:6], wire[6:]]

buffer = bytearray()
decoded = []
for chunk in chunks:
    buffer.extend(chunk)
    while buffer and len(buffer) >= 1 + buffer[0]:
        size = buffer[0]
        decoded.append(bytes(buffer[1:1 + size]))
        del buffer[:1 + size]

print([part.decode("utf-8") for part in decoded])
print(len(wire), len(chunks), len(buffer))
~~~

~~~text
['hi', '안녕']
10 4 0
~~~

`wire`는 1+2+1+6 = 10바이트이고 네 조각으로 공급했다.
첫 조각은 길이만 있으므로 메시지가 완성되지 않는다. 두 번째 조각에서 첫 메시지를 얻고, 남은 바이트를 다음 메시지의 시작으로 보관한다.
실제 HTTP/1.1은 이 장난감 길이 접두사 대신 자신의 시작 줄·헤더·본문 경계 규칙을 사용한다. [HTTP/1.1 RFC 9112 §6](https://www.rfc-editor.org/rfc/rfc9112.html#section-6)

TCP ACK는 상대 TCP가 **연결의 바이트를 받아들였다는 신호**다.
그 바이트가 HTTP로 파싱됐는지, 회원 레코드가 DB에 commit됐는지, 디스크에 `fsync`됐는지는 말해 주지 않는다.
애플리케이션 응답, DB commit 응답, 영속화 보장은 각각 별도 계약으로 확인한다. [TCP ACK 의미](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.4), [Linux 쓰기·동기화](01-linux-read-write.md)

## 6. TCP segment가 IP packet과 Ethernet frame에 실린다

| 이름 | 이 예에서 주요 역할 | 단위의 경계 |
| --- | --- | --- |
| TCP segment | 포트·순서·재전송 상태와 스트림의 바이트 조각 | TCP header + TCP data |
| IPv4 packet | 출발지·목적지 IP 주소를 이용한 라우팅 | IPv4 header + IP payload |
| Ethernet frame | 한 링크에서 다음 장비로 전달 | Ethernet header + payload + FCS trailer |

이 이름은 서로 바꿔 쓰지 않는다. IPv4 packet의 payload에 TCP segment가 들어가고, Ethernet frame의 payload에 IPv4 packet이 들어간다.
IP 주소는 목적지 호스트 쪽으로 가는 경로, Ethernet MAC 주소는 해당 링크에서 다음 수신 대상을 가리킨다.
라우터를 지나면 링크별 Ethernet frame은 새로 만들어질 수 있다. 원래 frame 하나가 종단 간 그대로 이동하는 그림은 아니다. [IPv4 packet 구조](https://www.rfc-editor.org/rfc/rfc791.html#section-3.1), [IP over Ethernet](https://www.rfc-editor.org/rfc/rfc894.html), [IEEE 802.3 프레임 도식](https://www.ieee802.org/3/by/public/May15/sun_3by_01_0515.pdf)

**MTU 1500 bytes**라고 할 때 일반적인 Ethernet의 1500은 frame 전체가 아니라 그 링크가 담는 **IP packet 크기**의 상한으로 이해해야 한다.
예를 들어 IPv4 헤더가 20바이트, TCP 헤더가 20바이트이고 옵션·확장 헤더가 없으면 `1500 - 20 - 20 = 1460`바이트가 한 segment의 TCP data에 들어갈 수 있다.
여기서 1460은 **TCP data의 상한을 계산한 예**이지 HTTP body 크기나 요청 하나의 제한이 아니다.
TCP data에 HTTP 헤더와 body가 함께 섞일 수도 있다. 앞의 회원 요청은 body가 34바이트라도 HTTP 시작 줄·헤더까지 더해 TCP에 전달한다. [IPv4 헤더 길이](https://www.rfc-editor.org/rfc/rfc791.html#section-3.1), [TCP 헤더](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.1), [Ethernet 1500바이트](https://www.rfc-editor.org/rfc/rfc894.html)

IP MTU 밖의 비용도 따로 세어야 한다. 다음은 **VLAN 태그 없는 Ethernet II**의 기본 계산이다.

| 범위 | 크기·뜻 |
| --- | --- |
| Ethernet MAC 헤더 | 목적지 MAC 6 + 출발지 MAC 6 + EtherType 2 = 14바이트 |
| IP packet | 이 예의 상한 1500바이트; 내부에 IP·TCP 헤더가 포함됨 |
| Ethernet FCS | 4바이트; 위 1500바이트 밖에 위치 |
| 기본 MAC frame 전체 | IP packet이 1500바이트라면 14 + 1500 + 4 = 1518바이트 |
| Preamble + SFD / 프레임 사이 간격 | 앞쪽 동기화 8바이트와 별도의 전송 간격; IP MTU에 포함하지 않음 |

짧은 IP packet은 Ethernet 최소 크기를 맞추는 padding이 뒤에 붙을 수 있다. padding은 IP packet 자체의 내용이 아니다. 따라서 앞의 중첩 그림은 padding을 생략한 구조 설명이다. 일반적인 OS 캡처에서는 NIC가 처리한 FCS나 preamble이 보이지 않을 수 있어 캡처 길이와 선로 비용도 구분한다. [IEEE 802.3 작업반의 프레임 도식, 4쪽](https://www.ieee802.org/3/by/public/May15/sun_3by_01_0515.pdf#page=4)

이 계산은 조건이 바뀌면 달라진다.

- IPv6 기본 헤더는 40바이트라 같은 경로 MTU에서도 계산이 달라진다. IPv6 확장 헤더가 있으면 더 줄 수 있다. [IPv6 RFC 8200](https://www.rfc-editor.org/rfc/rfc8200.html#section-3)
- TCP 옵션, 터널, TLS의 암호화 레코드 오버헤드가 있다면 애플리케이션의 평문 바이트 수와 각 계층의 실제 바이트 수가 달라진다.
- Jumbo frame을 허용한 링크는 보통의 1500-byte 예와 다르다. 경로 전체가 같은 크기를 지원하는지도 봐야 한다.
- NIC의 segmentation offload 때문에 송신 호스트의 패킷 캡처에 MTU보다 큰 “packet”이 보일 수 있다. 그 캡처만으로 실제 선로에 같은 크기의 frame이 나갔다고 결론 내리면 안 된다. [Linux segmentation offload](https://docs.kernel.org/networking/segmentation-offloads.html)

Ethernet의 FCS는 링크에서 frame 손상을 검사하는 **CRC 계열 값**이다.
IPv4의 header checksum은 IP 헤더를, TCP checksum은 segment의 헤더·데이터를 검사한다. 이들 역시 우발적 전송 손상을 찾는 장치이며, 콘텐츠를 누가 만들었는지 또는 업무 값이 맞는지 증명하지 않는다. [IPv4 checksum](https://www.rfc-editor.org/rfc/rfc791.html#section-3.1), [TCP checksum](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.1)
암호학적 hash는 다른 목적과 성질을 갖지만 **hash만 계산해서 전송한 것**도 공격자에 대한 출처 인증이 되지 않는다. 출처·변조에 대한 보장은 MAC·디지털 서명·인증된 암호화처럼 키와 검증 절차까지 봐야 한다.
애플리케이션은 `member_id`가 존재하는지, 허용된 형식인지, 이미 등록됐는지도 따로 검증한다. [Ethernet FCS](https://www.ieee802.org/3/by/public/May15/sun_3by_01_0515.pdf), [TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html)

## 7. HTTPS와 다른 HTTP 버전에서는 보이는 것이 달라진다

이 장의 HTTP/1.1 **평문** 모형에서는 TCP payload를 볼 수 있는 지점이라면 HTTP 시작 줄·헤더·JSON도 읽을 수 있다.
HTTPS를 사용하면 HTTP 메시지 바이트가 TLS로 보호되어 전송된다. 중간의 일반적인 packet capture에서는 IP 주소·포트·전송 길이와 TLS의 일부 메타데이터는 볼 수 있어도, 복호화 권한 없이 HTTP 헤더와 JSON body를 그대로 읽을 수 없다.
TLS의 기밀성·무결성·피어 인증은 실제 버전·인증 방식·인증서 검증이 올바른지에 달려 있다. [TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html), [HTTP/1.1과 TLS](https://www.rfc-editor.org/rfc/rfc9112.html#section-9.7)

| 버전 | 메시지가 실리는 대표 경로 | 이 장의 평문 줄 예와 다른 점 |
| --- | --- | --- |
| HTTP/1.1 | 평문 TCP 또는 TLS 위 TCP | 평문 예는 시작 줄·헤더·빈 줄·body를 직접 볼 수 있음 |
| HTTP/2 | frame과 stream을 TCP 위에서 사용; HTTPS에서는 TLS | HEADERS·DATA frame 등으로 메시지를 실음 |
| HTTP/3 | QUIC 위에 HTTP frame; QUIC은 UDP datagram 사용 | TCP segment가 아니라 QUIC packet·stream을 거침 |

따라서 **모든 HTTP가 TCP를 쓴다**는 말은 틀리다. HTTP/3은 QUIC/UDP 경로다.
또 `frame`이라는 말도 HTTP/2 frame과 Ethernet frame에서 서로 다른 계층의 단위다. [HTTP/2 RFC 9113](https://www.rfc-editor.org/rfc/rfc9113.html#section-4), [QUIC RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html#section-12), [HTTP/3 RFC 9114](https://www.rfc-editor.org/rfc/rfc9114.html)

## 8. 상대편에서 재조립해도 업무 완료는 별개다

~~~text
수신 Ethernet frame 검사
  → IP packet 해석
  → TCP가 연결의 바이트 순서 복원
  → HTTP/1.1이 요청 경계와 헤더·body 해석
  → JSON UTF-8 디코딩·파싱
  → schema·업무 규칙 검사
  → DB 저장·commit 또는 오류 응답
~~~

이 화살표는 책임의 순서다. 실제 구현에서는 버퍼링·병렬 처리·프록시 때문에 시간적으로 한 줄의 단순 파이프라인만 있는 것은 아니다.
수신자가 JSON을 정상 파싱해도 `member_id`가 중복이면 회원 생성은 실패할 수 있다.
HTTP body 34바이트가 DB의 34바이트 한 블록으로 저장된다는 뜻도 아니다.
DB는 인덱스·WAL·페이지에 다른 형태로 기록할 수 있고, 파일시스템은 다시 block·page cache·장치 요청으로 나눈다. [DB 페이지·WAL](05-database-pages-wal-indexes.md), [Linux 읽기·쓰기](01-linux-read-write.md)

### 응답을 잃어버린 뒤 재시도하면?

~~~text
1. 클라이언트가 request_id=R7로 POST /members를 보냄
2. 서버가 회원을 DB에 commit함
3. 성공 응답이 클라이언트에 도착하지 않음
4. 클라이언트가 같은 작업을 다시 보냄
~~~

TCP sequence number는 **한 연결의 바이트 순서**를 식별한다.
`request_id`는 **업무 요청의 식별자**이며 애플리케이션이 만들고 해석한다.
새 연결에서 재시도한 요청에 같은 `request_id`를 써도 TCP sequence number는 그 요청의 중복 여부를 판단하지 않는다.
서버가 이미 처리한 `request_id`와 결과를 원자적으로 기록하거나, `member_id`에 고유 제약을 두고 중복 요청을 같은 결과로 해석하는 등의 **idempotency 설계**가 필요하다.
그 규칙이 없으면 응답 손실 뒤 재시도로 중복 insert가 생길 수 있다.
네트워크가 제공하는 보편적인 “정확히 한 번의 업무 실행”을 가정하지 않는다. HTTP의 idempotent 메서드 의미도 실제 서버의 저장·부수효과 설계를 대신하지 않는다. [HTTP 메서드의 멱등성](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2), [TCP sequence number](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.4)

## 9. 스스로 확인하기

1. JSON의 `안녕`은 2글자인데 왜 `Content-Length` 계산에서 6바이트인가? → UTF-8 인코딩 결과를 세기 때문이다.
2. HTTP 헤더는 IP payload 밖에 있는가? → 아니다. IP payload 안의 TCP 데이터에 포함된다.
3. `recv(100)`이 100바이트를 보장하는가? → 아니다. 최대 100바이트이며 더 적을 수 있다.
4. TCP ACK를 받았으면 DB commit과 `fsync`도 끝났는가? → 그 사실만으로 알 수 없다.
5. MTU 1500이면 HTTP body 최대 크기가 1500인가? → 아니다. IP packet 크기의 예이며 HTTP 메시지는 여러 segment에 나뉠 수 있다.
6. Base64로 바꾸면 개인정보가 숨겨지는가? → 아니다. 누구나 디코딩할 수 있다.
7. 재시도 요청의 중복을 TCP sequence number로 판정할 수 있는가? → 아니다. 업무 ID와 저장 규칙이 필요하다.

다음 [Linux 읽기·쓰기](01-linux-read-write.md)에서는 이렇게 얻은 바이트가 로컬 파일 API에 전달된 뒤 어디까지 처리됐는지 추적한다.
