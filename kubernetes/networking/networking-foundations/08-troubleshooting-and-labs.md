# 08. 트러블슈팅과 안전한 실습: 증거를 한 계층씩 좁히기

[이전: Kubernetes CNI와 Cilium](07-kubernetes-cni-cilium.md)

근거 확인일: **2026-09-22**.

범위: 이 장은 네트워크 장애를 안전하게 분해하는 방법과 로컬 Python 표준 라이브러리 실습을 제공한다. 실습은 sudo, network namespace 생성, 원격 접속, packet capture, BPF attach, Kubernetes cluster 변경을 하지 않는다. 운영 명령은 실행 절차가 아니라 출력 해석을 배우기 위한 synthetic 예시다.

## 1. 트러블슈팅의 첫 원칙: 계층을 건너뛰지 않는다

"접속이 안 된다"는 말은 너무 넓다. DNS가 틀렸는지, route가 없는지, SYN이 막혔는지, TLS 인증서가 틀렸는지, HTTP application이 500을 내는지 모두 다르다.

```text
name → address → route/neighbor → packet delivery → TCP/UDP/QUIC → TLS → HTTP/application
```

각 단계에서 질문을 하나만 한다.

| 단계 | 질문 | 통과 증거 | 실패 증거 |
| --- | --- | --- | --- |
| DNS | 이름이 기대 IP로 풀리는가 | A/AAAA/CNAME 응답 | NXDOMAIN, timeout, 잘못된 IP |
| route | 목적지로 나갈 interface/next-hop이 있는가 | route lookup 결과 | no route, 잘못된 table/rule |
| neighbor | next-hop MAC을 아는가 | REACHABLE/STALE entry | INCOMPLETE/FAILED |
| MTU | packet 크기가 경로 MTU를 넘지 않는가 | 작은 요청 성공, PMTUD 정상 | 큰 요청 timeout, frag needed 손실 |
| TCP | handshake가 되는가 | SYN/SYN-ACK/ACK | SYN retry, RST, timeout |
| TLS | 인증서와 protocol 협상이 되는가 | handshake complete | unknown CA, SNI mismatch, protocol alert |
| HTTP | application이 정상 응답하는가 | 2xx/3xx 또는 기대 status | 4xx/5xx, timeout, wrong Host |

## 2. synthetic 출력 읽기: route와 neighbor

아래 출력은 실제 장비가 아니라 교육용 synthetic 예시다.

```text
$ ip route get 203.0.113.10
203.0.113.10 via 192.0.2.1 dev eth0 src 192.0.2.10 uid 1000
    cache
```

해석:

- 목적지 `203.0.113.10`으로 가려면 next-hop `192.0.2.1`을 쓴다.
- 나가는 device는 `eth0`다.
- source address는 `192.0.2.10`으로 선택됐다.
- 이 결과는 packet이 실제로 도착했다는 증거가 아니라 local route decision의 증거다.

```text
$ ip neigh show dev eth0
192.0.2.1 lladdr 00:11:22:33:44:55 REACHABLE
192.0.2.99 INCOMPLETE
```

해석:

- gateway `192.0.2.1`의 L2 address는 알려져 있고 최근 reachable했다.
- `192.0.2.99`는 ARP/NDP 해석이 끝나지 않았다.
- neighbor가 REACHABLE이어도 remote service가 열려 있다는 뜻은 아니다.

## 3. synthetic 출력 읽기: socket과 packet

```text
$ ss -tin dst 198.51.100.20
ESTAB 0 0 10.244.1.5:45678 198.51.100.20:443
     cubic wscale:7,7 rto:204 rtt:12.4/1.1 ato:40 mss:1448 cwnd:10 bytes_sent:1200 bytes_acked:1200
```

해석:

- TCP state는 ESTABLISHED다.
- RTT 추정은 12.4ms 근처다.
- MSS 1448은 path와 option 때문에 1460보다 작을 수 있다.
- application이 성공했다는 뜻은 아니다. TLS/HTTP는 그 위 계층이다.

```text
synthetic tcpdump-like view
10.244.1.5.45678 > 198.51.100.20.443: Flags [S], seq 1000, win 64240, options [mss 1448,sackOK]
198.51.100.20.443 > 10.244.1.5.45678: Flags [S.], seq 7000, ack 1001, win 65535, options [mss 1448,sackOK]
10.244.1.5.45678 > 198.51.100.20.443: Flags [.], ack 7001
```

해석:

- TCP 3-way handshake는 됐다.
- 그 다음 TLS ClientHello가 보이지 않는다면 application이 아직 쓰지 않았거나, capture 위치/필터가 틀렸거나, offload/GRO 때문에 다르게 보일 수 있다.

## 4. DNS/TCP/TLS/HTTP failure tree

```text
1. 이름이 안 풀림
   → DNS 서버 주소, search suffix, CoreDNS health, NetworkPolicy egress 53 확인

2. 이름은 풀리지만 route 없음
   → route table, policy routing, Pod CIDR route, CNI route 확인

3. SYN을 보내지만 SYN-ACK 없음
   → firewall, NetworkPolicy, service backend, SNAT, return route, MTU blackhole 확인

4. TCP는 되지만 TLS 실패
   → SNI, certificate CN/SAN, CA trust, protocol version, mTLS identity 확인

5. TLS는 되지만 HTTP 404/503/500
   → Host header, path, ingress/gateway route, backend readiness, application log 확인
```

이 트리는 원인을 찍어 맞추는 표가 아니다. 어떤 계층까지 성공했는지를 좁히는 순서다.

## 5. MTU blackhole을 의심하는 법

MTU blackhole은 작은 packet은 지나가지만 큰 packet이 사라지는 현상이다. overlay, VPN, tunnel, firewall의 ICMP 차단, PMTUD 실패에서 자주 보인다.

증상:

1. DNS나 TCP handshake는 된다.
2. 작은 HTTP 응답은 된다.
3. 큰 응답이나 TLS handshake 일부가 timeout난다.
4. retransmission이 늘고, ICMP Fragmentation Needed가 보이지 않는다.

Path MTU Discovery는 IPv4에서 DF bit와 ICMP 오류를 이용해 경로 MTU를 찾는 방식이다. [RFC 1191](https://datatracker.ietf.org/doc/html/rfc1191). IPv6는 router fragmentation이 없고 source가 packet size를 맞춰야 하며, IPv6 기본 동작은 RFC 8200을 따른다. [RFC 8200](https://datatracker.ietf.org/doc/html/rfc8200).

운영에서 MTU를 검증할 때는 승인된 유지보수 절차 안에서 ping size, tracepath, capture, CNI MTU 설정, tunnel overhead를 함께 본다. 이 교재는 그런 명령을 실행하지 않는다.

## 6. packet loss와 congestion을 구분한다

packet loss는 packet이 사라지는 사건이다. congestion은 경로의 queue와 capacity가 부족해 delay, drop, ECN mark가 생기는 상태다. 모든 loss가 congestion 때문은 아니다. policy drop, checksum error, MTU blackhole, NIC ring overflow, eBPF policy drop도 loss처럼 보일 수 있다.

| 관측 | 가능한 의미 | 추가 질문 |
| --- | --- | --- |
| TCP retransmission | loss 또는 reorder 또는 delayed ACK | 어느 방향 packet이 사라졌는가 |
| RTT 급증 | queueing delay 가능 | 같은 시간 throughput도 증가했는가 |
| RST | 상대 application/kernel이 연결 거부/종료 | 누가 RST를 보냈는가 |
| ICMP unreachable | network layer 오류 보고 | type/code가 무엇인가 |
| Cilium drop event | datapath policy/drop reason | 같은 flow의 route와 endpoint state는? |
| no Hubble event | 관측 누락 가능 | agent health, event loss, attachment scope는? |

## 7. eBPF map/agent health와 인과관계의 거리

Cilium에서 service map, policy map, conntrack map, ipcache 같은 상태가 이상하면 통신 장애가 생길 수 있다. 하지만 map entry 하나가 보인다고 바로 원인이 확정되는 것은 아니다.

```text
증거 거리 예:
Cilium agent restart count 증가
  → agent가 불안정할 수 있음
  → map update가 지연됐을 수 있음
  → 특정 flow가 실패했을 수 있음
  → application timeout의 원인일 수 있음
```

각 화살표에는 별도 증거가 필요하다. 시간 상관관계, 해당 endpoint identity, policy revision, service backend, conntrack entry, drop event, application log를 맞춰야 한다. 관찰 도구를 원인으로 바꾸는 순간 분석이 위험해진다.

## 8. 안전 실습 1: CIDR과 route longest-prefix match

아래 Python은 로컬 계산만 한다. network를 변경하지 않는다.

```python
import ipaddress

routes = [
    (ipaddress.ip_network("0.0.0.0/0"), "gw-default"),
    (ipaddress.ip_network("10.244.0.0/16"), "cni0"),
    (ipaddress.ip_network("10.244.2.0/24"), "vxlan.calico"),
    (ipaddress.ip_network("10.244.2.128/25"), "special-node"),
]

def lookup(dst):
    ip = ipaddress.ip_address(dst)
    matches = [(net.prefixlen, net, via) for net, via in routes if ip in net]
    matches.sort(reverse=True)
    return matches[0][1], matches[0][2]

for dst in ["10.244.2.9", "10.244.2.200", "10.244.3.7", "203.0.113.10"]:
    net, via = lookup(dst)
    print(f"{dst} -> {net} via {via}")
```

검증한 출력:

```text
10.244.2.9 -> 10.244.2.0/24 via vxlan.calico
10.244.2.200 -> 10.244.2.128/25 via special-node
10.244.3.7 -> 10.244.0.0/16 via cni0
203.0.113.10 -> 0.0.0.0/0 via gw-default
```

해설: route lookup은 더 긴 prefix를 우선한다. 같은 Pod CIDR 안에서도 더 구체적인 route가 있으면 그것이 이긴다. Linux policy routing은 table과 rule까지 보므로 실제 시스템은 이 예제보다 복잡할 수 있다.

## 9. 안전 실습 2: socketpair로 stream 경계 확인

`socket.socketpair()`는 같은 host process 안에 연결된 socket 두 개를 만든다. 원격 네트워크를 쓰지 않는다.

```python
import socket

a, b = socket.socketpair()
a.settimeout(2)
b.settimeout(2)
try:
    a.sendall(b"hello")
    a.sendall(b"world")
    print(b.recv(3))
    print(b.recv(1024))
finally:
    a.close()
    b.close()
```

검증한 출력:

```text
b'hel'
b'loworld'
```

해설: stream socket은 message boundary를 보존하지 않는다. sender가 두 번 보냈지만 receiver는 3 bytes와 나머지 7 bytes로 읽었다. TCP도 byte stream이므로 application protocol이 length prefix, delimiter, framing을 직접 정해야 한다.

## 10. 안전 실습 3: synthetic IPv4/TCP header parser

아래 Python은 hard-coded IPv4 + TCP header bytes를 해석한다. packet capture를 하지 않고, raw socket도 열지 않으며, 외부 network를 사용하지 않는다. 예제 parser는 교육용이므로 IPv4 header checksum과 TCP checksum은 검증하지 않는다. endpoint 도달성이나 wire 위 실제 packet을 주장하지 않고, byte 배열 안의 header 형식만 검사한다.

```python
import struct
import ipaddress

IPV4_MIN_HEADER = 20
TCP_MIN_HEADER = 20
IP_PROTO_TCP = 6
IP_MF_FLAG = 0x1


def parse_ipv4_tcp(packet):
    if len(packet) < IPV4_MIN_HEADER:
        raise ValueError("truncated IPv4 header")

    version_ihl = packet[0]
    version = version_ihl >> 4
    ihl = (version_ihl & 0x0F) * 4
    if version != 4:
        raise ValueError("not IPv4")
    if ihl < IPV4_MIN_HEADER:
        raise ValueError("invalid IPv4 IHL")
    if len(packet) < ihl:
        raise ValueError("truncated IPv4 options")

    fields = struct.unpack("!BBHHHBBHII", packet[:IPV4_MIN_HEADER])
    _, tos, total_len, ident, flags_frag, ttl, proto, ip_checksum, src, dst = fields
    if total_len < ihl:
        raise ValueError("IPv4 total length smaller than header")
    if len(packet) < total_len:
        raise ValueError("truncated IPv4 packet")
    if proto != IP_PROTO_TCP:
        raise ValueError("not TCP")

    flags = flags_frag >> 13
    frag_offset = flags_frag & 0x1FFF
    if (flags & IP_MF_FLAG) or frag_offset != 0:
        raise ValueError("fragmented IPv4 packet not supported")

    tcp_start = ihl
    tcp_end_min = tcp_start + TCP_MIN_HEADER
    if total_len < tcp_end_min:
        raise ValueError("truncated TCP header")

    tcp = packet[tcp_start:tcp_end_min]
    src_port, dst_port, seq, ack, offset_flags, window, tcp_checksum, urg = struct.unpack("!HHIIHHHH", tcp)
    data_offset = ((offset_flags >> 12) & 0xF) * 4
    tcp_flags = offset_flags & 0x01FF
    if data_offset < TCP_MIN_HEADER:
        raise ValueError("invalid TCP data offset")
    if total_len < tcp_start + data_offset:
        raise ValueError("truncated TCP options")

    return {
        "version": version,
        "ihl": ihl,
        "total_len": total_len,
        "ttl": ttl,
        "proto": proto,
        "src": str(ipaddress.ip_address(src)),
        "dst": str(ipaddress.ip_address(dst)),
        "src_port": src_port,
        "dst_port": dst_port,
        "tcp_data_offset": data_offset,
        "tcp_flags": tcp_flags,
        "payload_len": total_len - tcp_start - data_offset,
    }


packet = bytes.fromhex(
    "45 00 00 28 12 34 40 00 40 06 00 00 c0 00 02 0a c6 33 64 14"
    "04 d2 01 bb 00 00 00 01 00 00 00 00 50 02 20 00 00 00 00 00"
)

info = parse_ipv4_tcp(packet)
print(info["version"], info["ihl"], info["total_len"], info["ttl"], info["proto"])
print(info["src"], info["src_port"], "->", info["dst"], info["dst_port"])
print("tcp_header", info["tcp_data_offset"], "flags", hex(info["tcp_flags"]), "payload", info["payload_len"])

malformed_cases = {
    "truncated_ip": packet[:10],
    "bad_version": bytes([0x65]) + packet[1:],
    "bad_ihl": bytes([0x44]) + packet[1:],
    "bad_total_len": packet[:2] + b"\x00\x10" + packet[4:],
    "not_tcp": packet[:9] + b"\x11" + packet[10:],
    "fragmented": packet[:6] + b"\x20\x01" + packet[8:],
    "short_tcp": packet[:2] + b"\x00\x1c" + packet[4:28],
    "bad_tcp_offset": packet[:32] + b"\x40\x02" + packet[34:],
}

for name, sample in malformed_cases.items():
    try:
        parse_ipv4_tcp(sample)
        print(name, "accepted")
    except ValueError as exc:
        print(name, "rejected:", exc)
```

검증한 출력:

```text
4 20 40 64 6
192.0.2.10 1234 -> 198.51.100.20 443
tcp_header 20 flags 0x2 payload 0
truncated_ip rejected: truncated IPv4 header
bad_version rejected: not IPv4
bad_ihl rejected: invalid IPv4 IHL
bad_total_len rejected: IPv4 total length smaller than header
not_tcp rejected: not TCP
fragmented rejected: fragmented IPv4 packet not supported
short_tcp rejected: truncated TCP header
bad_tcp_offset rejected: invalid TCP data offset
```

해설: protocol 6은 TCP다. TCP flags `0x2`는 SYN bit가 선 상태를 뜻한다. 이 parser는 fragment를 재조립하지 않으므로 fragmented IPv4 packet은 명확히 거부한다. TCP header는 port 4바이트만 읽고 끝내지 않고 최소 20바이트 전체를 읽은 뒤 data offset이 20바이트 이상인지 확인한다. `192.0.2.0/24`와 `198.51.100.0/24`는 문서용 TEST-NET 주소 범위라 실제 운영 대상을 가리키지 않는다.

## 11. 안전 실습 4: MTU overhead 산수

```python
def pod_mtu(underlay_mtu, overheads):
    return underlay_mtu - sum(overheads.values())

vxlan_ipv4 = {
    "outer_ipv4": 20,
    "udp": 8,
    "vxlan": 8,
    "inner_ethernet": 14,
}

wireguard_extra = {
    "outer_ipv4": 20,
    "udp": 8,
    "wireguard_approx": 32,
}

print(pod_mtu(1500, vxlan_ipv4))
print(pod_mtu(1500, wireguard_extra))
```

검증한 출력:

```text
1450
1440
```

해설: 숫자는 교육용 근사다. 실제 overhead는 IPv6, VLAN, tunnel option, encryption, CNI 구현에 따라 달라진다. 중요한 것은 overlay를 쓰면 inner packet에 허용되는 MTU가 줄어든다는 점이다.

## 12. 안전 실습 5: DNS 실패와 TCP 실패를 분리하는 사고 실험

아래 코드는 외부 DNS나 원격 network를 쓰지 않는다. `socket.getaddrinfo` 대신 주어진 synthetic resolver 결과를 분석한다.

```python
cases = {
    "dns_nxdomain": [],
    "dns_ok_tcp_timeout": ["203.0.113.10"],
    "dns_wrong_ip": ["192.0.2.55"],
}

expected = "203.0.113.10"

for name, answers in cases.items():
    if not answers:
        verdict = "DNS layer failed"
    elif expected not in answers:
        verdict = "DNS returned unexpected address"
    else:
        verdict = "DNS layer passed; test route/TCP/TLS next"
    print(name, "=>", verdict)
```

검증한 출력:

```text
dns_nxdomain => DNS layer failed
dns_ok_tcp_timeout => DNS layer passed; test route/TCP/TLS next
dns_wrong_ip => DNS returned unexpected address
```

해설: DNS가 성공했다는 것은 다음 계층을 볼 자격이 생겼다는 뜻이지, TCP나 TLS가 성공했다는 뜻이 아니다.

## 13. 종합 연습

1. 작은 HTTP 요청은 성공하고 큰 파일 다운로드만 멈춘다. 가장 먼저 떠올릴 네트워크 가설 두 가지는?
2. `ss`에는 ESTAB가 보이지만 HTTP 503이다. 어느 계층까지는 통과했는가?
3. Hubble drop event가 없다. policy 문제가 아니라고 확정할 수 있는가?
4. `ip route get` 결과가 올바르다. packet이 remote application에 도착했다고 말할 수 있는가?
5. stream socket에서 sender가 `sendall(b"hello")`, `sendall(b"world")`를 호출했다. receiver의 첫 `recv(3)` 결과는 왜 `b'hel'`일 수 있는가?

**답:** ① MTU blackhole, congestion/loss, TLS record 또는 proxy body size 같은 상위 계층도 후보에 둔다. ② DNS, route, TCP handshake는 적어도 일부 통과했을 가능성이 높고, HTTP application 또는 upstream/backend 계층을 봐야 한다. ③ 없다. 관측 범위, event loss, agent 상태, 다른 enforcement 지점을 확인해야 한다. ④ 없다. local route decision일 뿐이다. ⑤ TCP/stream socket은 message boundary를 보존하지 않고 byte stream만 제공하기 때문이다.

## 14. 확인한 1차 자료

- IETF: [IPv4 RFC 791](https://datatracker.ietf.org/doc/html/rfc791), [IPv6 RFC 8200](https://datatracker.ietf.org/doc/html/rfc8200), [TCP RFC 9293](https://datatracker.ietf.org/doc/html/rfc9293), [Path MTU Discovery RFC 1191](https://datatracker.ietf.org/doc/html/rfc1191), [QUIC RFC 9000](https://datatracker.ietf.org/doc/html/rfc9000)
- Linux kernel: [NAPI](https://docs.kernel.org/networking/napi.html), [sk_buff](https://docs.kernel.org/networking/skbuff.html), [BPF verifier](https://docs.kernel.org/bpf/verifier.html)
- Cilium: [routing](https://docs.cilium.io/en/stable/network/concepts/routing/), [masquerading](https://docs.cilium.io/en/stable/network/concepts/masquerading/), [kube-proxy replacement](https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/)
