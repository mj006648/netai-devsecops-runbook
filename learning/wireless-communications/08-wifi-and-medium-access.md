# 08. Wi‑Fi와 medium access

## 공유 공기에서 누가 먼저 말할지 정하는 문제

Wi-Fi UE와 AP는 같은 channel을 공유한다. 유선 switch처럼 동시에 송신하며 충돌을 직접 감지하기 어렵다. 자기 송신 전력이 수신하려는 약한 신호를 덮기 때문이다. 그래서 **CSMA/CA**는 송신 전에 channel을 듣고, 비어 있는 시간을 확인하고, 무작위 backoff를 사용해 충돌 가능성을 줄인다.

PHY는 bit를 RF symbol로 보내고 복호한다. MAC은 frame 주소, sequence, 재전송, medium access를 관리한다. RF 송신 성공은 상대 MAC 수신 성공이 아니며, MAC ACK는 애플리케이션 저장 성공이 아니다.

## 두 station backoff 전체 추적

A와 B가 동시에 frame을 준비하고 contention window 0~7 slot에서 각각 2와 5를 뽑았다고 하자. channel이 정해진 간격 동안 idle이면 둘 다 counter를 줄인다. A가 0이 되면 송신하고 B는 counter 3에서 멈춘다. ACK 뒤 channel이 다시 idle 조건을 만족하면 B가 3부터 재개한다.

| slot | channel | A counter | B counter | 사건 |
|---:|---|---:|---:|---|
| 0 | idle | 2 | 5 | 시작 |
| 1 | idle | 1 | 4 | 감소 |
| 2 | idle | 0 | 3 | A 송신 |
| 3~5 | busy | - | 3 | B freeze |
| 6 | ACK·idle 대기 | - | 3 | 재개 준비 |
| 9 | idle | - | 0 | B 송신 |

둘이 같은 숫자 2를 뽑으면 동시에 송신해 receiver에서 충돌할 수 있다. ACK가 없으면 contention window를 키우고 다시 시도한다. 충돌이 없어도 channel error나 ACK 유실로 재전송할 수 있다.

## hidden node 문제

A와 C는 서로 신호를 못 듣지만 둘 다 AP B에는 닿을 수 있다. A가 듣기에 channel이 비어 있고 C도 같아서 동시에 B에 보내면 B에서 충돌한다. carrier sense만으로 해결되지 않는 반례다.

RTS/CTS는 송신 예정과 수신 허가를 주변에 알려 hidden node 충돌을 줄일 수 있지만 짧은 frame에는 overhead가 더 클 수 있다. 모든 간섭원이 제어 frame을 듣는다는 보장도 없다.

## OFDM과 OFDMA 자원 배치

OFDM은 한 송신이 여러 subcarrier로 symbol을 보낸다. OFDMA는 AP가 한 전송 기회에서 서로 다른 resource unit을 여러 UE에 배정할 수 있게 한다. UE가 임의로 동시에 subcarrier를 고르는 것이 아니라 trigger와 scheduling·동기가 필요하다.

20 MHz 자원에서 교육용으로 UE A에 40%, B에 30%, pilot/control/guard에 30%를 쓴다고 하자. raw PHY가 100 Mbit/s 상당이라도 A 후보는 40, B는 30 Mbit/s이며 각자 MCS·재전송에 따라 goodput이 낮아진다.

## payload airtime과 goodput

payload 1,500 byte는 12,000 bit다. PHY payload rate 120 Mbit/s이면 순수 data 시간은 `12000/120M=100 μs`다. preamble 40 μs, contention 80 μs, ACK 관련 30 μs면 총 250 μs다. goodput 후보는 `12000/250 μs=48 Mbit/s`다.

재전송 한 번이 같은 250 μs를 더 쓰면 payload 12,000 bit에 500 μs로 24 Mbit/s가 된다. PHY 표기 rate와 애플리케이션 goodput이 다른 이유다.

| 요소 | 시간 |
|---|---:|
| contention | 80 μs |
| preamble | 40 μs |
| data | 100 μs |
| ACK | 30 μs |
| 합계 | 250 μs |

## 세대 이름과 band 조건

Wi-Fi 세대 이름은 지원 가능한 기능 묶음을 가리키며 실제 단말·AP·국가 규제·channel 폭·동시 사용자에 따라 결과가 달라진다. 6E는 6 GHz band 사용 가능성을 연결한 이름이지 모든 지역에서 같은 채널을 쓴다는 뜻이 아니다.

## AI medium access 연구 경계

AI가 contention, scheduling, MCS를 고를 때 traffic 분포와 hidden node, 이동 조건이 학습과 달라질 수 있다. simulation throughput 상승을 실제 혼잡 주택·기업망 보장으로 쓰지 않는다. 안전 fallback과 공정성, 다른 UE에 준 airtime을 함께 평가한다.

## 핵심 계산 복습: PHY와 MAC

PHY는 bit/symbol과 radio 파형을 연결한다.
MAC은 여러 station이 channel을 언제 쓰고 ACK를 어떻게 다룰지 정한다.

![Wi-Fi와 cellular](assets/wifi-cellular.svg)

## CSMA/CA

carrier sense로 channel을 듣는다.
idle 조건 뒤 random backoff를 센다.
0이면 전송하고 ACK를 기다린다.

```mermaid
stateDiagram-v2
    [*] --> Sense
    Sense --> Wait: busy
    Sense --> Backoff: idle
    Backoff --> Freeze: 다른 전송
    Freeze --> Backoff: 다시 idle
    Backoff --> TX: counter 0
    TX --> Done: ACK
    TX --> Retry: ACK 없음
    Retry --> Sense
```

무선은 송신 중 collision detection이 어렵다.
collision avoidance도 collision zero 보장이 아니다.

## backoff 추적

A=2slot, B=5slot을 뽑았다.

| idle slot | A | B | 사건 |
|---:|---:|---:|---|
| 시작 | 2 | 5 | 대기 |
| 1 | 1 | 4 | idle |
| 2 | 0 | 3 | A 전송 |
| A 송신 | - | 3 freeze | busy |
| 재개 | - | 2→1→0 | B 전송 |

B는 busy 동안 counter를 줄이지 않는다.
같은 값을 뽑으면 collision할 수 있다.

## ACK

ACK 없음은 data collision, fading, ACK loss 중 어느 것인지 바로 구분하지 못할 수 있다.
sender는 retry와 contention window를 조정한다.
MAC ACK는 application 처리나 저장 완료가 아니다.

## hidden node

A와 C가 서로 못 듣지만 둘 다 AP B에 도달하면 각각 idle로 판단할 수 있다.

```mermaid
flowchart LR
    A[A] --> B[AP B]
    C[C] --> B
    A -. 서로 감지 못함 .- C
```

B에서 신호가 겹친다.
RTS/CTS가 receiver 주변 예약에 도움을 줄 수 있다.
control overhead가 있어 항상 이득은 아니다.

## OFDM과 OFDMA

OFDM은 한 전송을 직교 subcarrier로 구성한다.
OFDMA는 subcarrier 묶음인 RU를 여러 user에게 할당한다.

| 항목 | OFDM | OFDMA |
|---|---|---|
| 질문 | 파형을 어떻게 나누나 | user에게 무엇을 주나 |
| 동시 user | 필수 아님 | 여러 user 가능 |
| 추가 상태 | FFT·CP·pilot | scheduler·RU·trigger |

OFDMA도 synchronization과 control overhead가 필요하다.

## 세대와 표준

| 이름 | IEEE 기반 | 상태/뜻 |
|---|---|---|
| Wi‑Fi 6 | 802.11ax-2021 | 2.4/5GHz 중심의 ax 기능군과 인증 |
| Wi‑Fi 6E | 802.11ax | Wi‑Fi 6의 6GHz 확장; 별도 PHY 규격이 아님 |
| Wi‑Fi 7 | 802.11be-2024 | be 기반 기능과 Alliance 인증 program |
| Wi‑Fi 8 | P802.11bn | 2026-10-11 현재 IEEE project/draft 단계 |

표준 publication, Wi‑Fi Alliance 인증 program, 제품 출시는 서로 다른 시점이다.
draft 기능을 완성 표준 보장처럼 쓰지 않는다.
6GHz 사용 가능 범위는 국가 규제와 device 인증에 달린다.

## 6E를 읽는 법

6E의 E는 802.11ax와 별개 PHY를 뜻하지 않는다.
Wi‑Fi 6(ax) 기능을 6GHz band로 확장한 생태계 이름이다.
AP가 6E여도 client와 지역 규제가 6GHz를 지원해야 한다.

## Wi‑Fi 7/8 경계

802.11be-2024와 Wi‑Fi 7 인증 program은 관련되지만 동일 문서가 아니다.
Wi‑Fi 8은 P802.11bn project의 draft 진행 상태다.
최종 기능과 인증 요구는 확정 문서를 확인한다.

## band와 세대

2.4GHz, 5GHz, 6GHz는 spectrum band다.
Wi‑Fi 6, 7, 8은 세대 이름이다.
숫자가 비슷해도 같은 축이 아니다.

## 상태표

| 주체 | 입력 | 상태 | 결과 |
|---|---|---|---|
| station | queued frame | carrier sense | busy/idle |
| backoff | random counter | freeze/count | TX 시점 |
| AP scheduler | queue/channel | RU allocation | OFDMA trigger |
| receiver | frame | CRC/FEC | ACK/무응답 |
| sender | ACK | retry state | 성공/재경쟁 |

## goodput

PHY rate에는 preamble, pilot, coding, MAC header, contention, ACK가 포함되지 않은 방식이 많다.
1Gbit/s PHY 표기가 1Gbit/s application goodput을 보장하지 않는다.
retry와 여러 station 경쟁이 airtime을 쓴다.

## 반례

RSSI가 강해도 hidden collision이 가능하다.
넓은 channel은 peak rate를 높여도 간섭 선택지를 줄일 수 있다.
OFDMA 지원 장치도 모든 frame에 OFDMA를 쓰지 않는다.
최신 세대 AP만 바꾸고 client가 옛 세대면 새 기능을 못 쓸 수 있다.

## Station, AP와 frame이 존재하는 위치

**Station(STA, 스테이션)**은 802.11 무선 LAN에 참여하는 장치다. 노트북과 전화뿐 아니라 AP도 station 기능을 가진다. **Access Point(AP)**는 infrastructure network에서 station을 연결하고 유선 distribution system으로 중계하는 역할을 한다.

Application packet은 OS network stack과 Wi-Fi driver를 지나 MAC frame이 되어 송신 station의 queue에 저장된다. Frame에는 송수신 주소, sequence, 제어 정보와 오류 검사용 FCS가 붙는다. Queue record는 성공 ACK, retry limit 초과, lifetime 만료 또는 연결 종료까지 산다.

**Airtime(공중 점유 시간)**은 preamble부터 frame·간격·ACK·재전송까지 channel을 사용하는 시간이다. Byte가 작은 관리 frame도 고정 preamble과 contention 비용을 낸다. PHY rate 숫자만으로 application goodput을 계산할 수 없는 이유다.

## CSMA/CA와 두 station backoff 전체 추적

**CSMA/CA**는 송신 전에 channel이 비었는지 듣고 충돌 가능성을 줄이는 Wi-Fi medium access 절차다. 유선 Ethernet처럼 송신 중 충돌을 확실히 검출하기 어려워 collision avoidance를 쓴다. **Carrier sense**는 receiver가 energy와 알려진 Wi-Fi 신호를 감지해 busy/idle을 정한다.

A와 B가 같은 AP에 frame을 갖고 있고 contention window에서 A=2, B=4 slot을 뽑았다고 하자. 둘 다 정해진 idle 간격 뒤 매 idle slot마다 counter를 1 줄인다.

| slot | channel 시작 | A counter | B counter | 사건 |
|---:|---|---:|---:|---|
| 0 | idle | 2→1 | 4→3 | 둘 다 대기 |
| 1 | idle | 1→0 | 3→2 | A 전송 자격 |
| 2..5 | busy | 0, 송신 | 2, freeze | A frame |
| 6 | ACK·간격 | 완료 | 2, freeze | B는 세지 않음 |
| 7 | idle | - | 2→1 | B 재개 |
| 8 | idle | - | 1→0 | B 전송 |
| 이후 | ACK | - | 완료 | queue 해제 |

**Backoff(무작위 후퇴)**는 충돌 뒤뿐 아니라 경쟁 시작에서 무작위 slot 수를 기다리는 상태다. Busy 중에는 counter를 새로 뽑지 않고 freeze했다가 적절한 idle 뒤 계속 센다. A와 B가 같은 숫자를 골라 함께 송신하면 AP에서 collision이 날 수 있다. ACK가 없으면 retry count와 contention window를 갱신해 재경쟁한다.

실제 표준은 frame 종류, access category와 PHY에 따라 간격·window·TXOP 규칙이 다르다. 위 표는 원리 모형이며 설치 장치의 정확한 microsecond 값을 만들지 않는다.

## ACK가 만드는 성공 조건과 시간 순서

송신 함수가 frame bytes를 driver에 넘겼다고 성공이 아니다. Receiver는 preamble로 동기를 잡고 header와 payload를 복호한 뒤 FCS가 맞을 때 ACK를 보낸다. Sender는 정해진 ACK 대기 timer 안에 응답을 받아야 성공으로 확정한다.

```text
queue → carrier sense → random backoff → DATA 전송
      → ACK 대기 → ACK 수신: buffer 해제
                 → timeout: retry count 증가, 재경쟁 또는 drop
```

ACK 자체가 다른 모든 station까지 data를 받았음을 뜻하지 않는다. 해당 unicast 교환의 receiver가 frame을 올바르게 받았다는 link-layer 확인이다. Broadcast·multicast와 block ACK에는 다른 계약이 있을 수 있다. 실측에서는 retry counter가 증가한 시각과 application 재전송을 구분한다.


## Hidden node와 RTS/CTS

Station A와 C가 서로 멀거나 가려져 상대 신호를 감지하지 못하지만 둘 다 가운데 AP B에 닿는다고 하자. A는 channel idle, C도 idle이라고 판단해 동시에 B로 보내 충돌한다. 이것이 **hidden node(숨은 노드)** 문제다. Carrier sense는 자신이 들을 수 있는 범위만 알기 때문에 생긴다.

**RTS(Request To Send)**와 **CTS(Clear To Send)**는 긴 data 전에 짧은 예약 frame을 교환하는 선택 절차다.

```text
A → B: RTS, 필요한 duration
B → 주변: CTS, duration
C: A의 RTS를 못 들어도 B의 CTS를 들으면 NAV 설정 후 대기
A → B: DATA
B → A: ACK
```

**NAV(Network Allocation Vector)**는 수신한 duration으로 medium이 예약됐다고 보는 가상 carrier-sense timer다. RTS/CTS도 airtime을 쓰며 CTS가 C에 들리지 않거나 매우 짧은 frame이면 이득보다 overhead가 클 수 있다. Hidden node를 항상 완전히 제거하는 마법이 아니다.

## OFDM, OFDMA와 MU-MIMO를 구분한다

**OFDM**은 한 전송 파형을 여러 직교 subcarrier로 구성한다. 한 사용자에게 전체 channel을 줄 수도 있다. **OFDMA**는 subcarrier 묶음인 **RU(Resource Unit)**를 같은 시간에 여러 사용자에게 할당하는 medium access 방법이다. AP scheduler가 어느 STA에 어느 RU와 MCS를 줄지 정하고, uplink에서는 trigger frame으로 동시 송신 시각과 자원을 알릴 수 있다.

20 MHz 교육 격자에서 data 가능한 tone 묶음을 A 106-tone, B 52-tone, C 26-tone으로 줬다고 하자. 각자 다른 modulation·code rate를 쓸 수 있다. 동시 종료를 맞추면 작은 packet 여러 개가 차례로 전체 channel을 경쟁하는 고정 비용을 줄일 수 있다. 그러나 trigger, pilot, padding과 scheduler overhead가 있고 모든 client가 같은 기능을 지원해야 한다.

**MU-MIMO**는 같은 time·frequency 자원에서 서로 구분 가능한 공간 channel을 이용해 여러 사용자 layer를 보낸다. OFDMA는 주파수 분할, MU-MIMO는 공간 분리를 중심으로 한다. 함께 쓸 수 있지만 동일 개념은 아니다. CSI가 낡거나 사용자 channel이 비슷하면 spatial separation이 실패할 수 있다.

## Airtime과 goodput 전체 계산

Payload 12,000 bit를 PHY 120 Mbit/s로 보내는 순수 payload 시간은 100 µs다. Preamble 40 µs, contention·간격 80 µs, MAC·PHY header 전송 20 µs, ACK 40 µs라면 성공 1회의 총 airtime은 280 µs다.

```text
application goodput = 12,000 bit / 280 µs
                    ≈ 42.86 Mbit/s
```

첫 시도가 충돌해 180 µs를 쓰고 두 번째 280 µs에 성공하면 같은 payload의 총 airtime은 460 µs, goodput은 약 26.09 Mbit/s다. PHY 120 Mbit/s는 payload 전송 구간의 modulation·coding rate이고 contention·실패를 포함하지 않는다.

여러 station의 fairness도 byte가 아니라 airtime으로 볼 필요가 있다. 느린 legacy station이 긴 airtime을 쓰면 빠른 station의 전송 기회도 줄 수 있다. Packet aggregation은 여러 payload를 한 전송에 묶어 preamble·ACK 고정 비용을 나누지만 한 번 실패할 때 영향과 지연이 커질 수 있다.

## Load, collision과 queue의 연결

도착률이 service 능력에 가까워지면 station queue가 길어지고 동시에 경쟁할 station 수도 늘어 collision과 backoff가 증가할 수 있다. 재전송이 airtime을 더 먹어 service가 더 느려지는 양의 feedback이 생긴다. 평균 PHY rate가 그대로여도 application latency p99가 급격히 나빠질 수 있다.

AP queue, station queue, driver queue와 application socket buffer는 다른 위치다. 한 queue 길이만 보고 전체 대기를 설명하지 않는다. Packet timestamp를 enqueue, first contention, transmit, ACK와 delivery에서 연결한다.

## AI medium access 연구의 경계

AI가 contention window, RU, user grouping이나 MCS를 고를 수 있다. Simulation에서는 perfect queue·CSI, 고정 traffic와 즉시 inference를 가정하기 쉽다. Testbed는 실제 chipset·driver와 제한된 방·client 조합을 포함한다. Field는 이웃 BSS, hidden node, legacy client, radar·규제, 이동과 시간대 변화를 포함한다.

연구 결과는 aggregate throughput만 보고하지 않는다. Per-station airtime, p50/p99 latency, packet drop, collision/retry, energy, inference deadline과 fallback을 본다. 학습 traffic과 평가 traffic을 분리하고 FIFO·표준 scheduler 같은 기준선을 같은 장치·load에서 비교한다. 정책 inference가 scheduling deadline보다 늦거나 관측에 없던 client에서 starvation을 만들면 평균 개선만으로 배포하지 않는다.

IEEE 802.11-2024는 WLAN MAC과 PHY 규격의 현재 revision이며, Wi-Fi Alliance 세대 인증 이름과 IEEE amendment 이름을 섞지 않는다. Draft 기능은 최종 표준·인증 지원처럼 단정하지 않는다.

## 종합 문제와 완전 해설

### 문제 1. Backoff freeze

Counter 4에서 idle 두 slot 뒤 busy가 되었다. 남은 값은?

**해설.** 2다. Busy 중 freeze하고 필요한 idle 간격 뒤 2부터 계속 센다. 새 값을 즉시 뽑지 않는다.

### 문제 2. 같은 backoff

두 station이 같은 counter 0에 도달하면 어떻게 되는가?

**해설.** 둘 다 송신해 receiver에서 collision할 수 있다. ACK가 없으면 retry와 더 넓은 contention window 정책으로 재경쟁한다.

### 문제 3. Hidden node

A와 C가 서로 못 듣고 AP B는 둘 다 듣는다. Carrier sense만으로 충돌을 막을 수 있는가?

**해설.** 없다. 각 station은 상대를 idle로 본다. B의 CTS를 둘 다 들을 수 있는 조건에서는 RTS/CTS가 예약 정보를 전달할 수 있다.

### 문제 4. Airtime goodput

12,000 bit를 성공 전달하는 전체 airtime이 300 µs면 goodput은?

**해설.** `12000/0.0003=40 Mbit/s`다. PHY rate와 다르다.

### 문제 5. Retry goodput

성공 airtime 280 µs 전에 실패 180 µs가 있었다. 12,000 bit goodput은?

**해설.** 총 460 µs라 `12000/0.00046≈26.09 Mbit/s`다.

### 문제 6. OFDM과 OFDMA

둘의 차이는?

**해설.** OFDM은 subcarrier로 파형을 구성하는 방식, OFDMA는 RU를 여러 사용자에게 배분하는 access 방식이다.

### 문제 7. OFDMA와 MU-MIMO

A와 B를 서로 다른 RU에 두는 것과 같은 RU에서 spatial layer로 나누는 것은?

**해설.** 전자는 주파수 자원 분할, 후자는 공간 channel 분리다. 후자는 충분히 다른 CSI와 rank가 필요하다.

### 문제 8. AI scheduler

Simulation 평균 throughput 20% 개선인데 한 station p99가 3배가 됐다. 성공인가?

**해설.** Fairness·latency SLO에 따라 실패일 수 있다. Per-station goodput·airtime·starvation과 field deadline을 포함해 판정한다.

## 공식 출처

- [IEEE 802.11 standard page](https://standards.ieee.org/ieee/802.11/10548/)
- [Wi‑Fi Alliance Wi‑Fi 7 announcement, 2024-01-08](https://www.wi-fi.org/news-events/newsroom/wi-fi-alliance-introduces-wi-fi-certified-7)
- [IEEE 802.11 Working Group](https://www.ieee802.org/11/)
- [IEEE 802.11-2024 standard page](https://standards.ieee.org/ieee/802.11/10548/)

[← 이전](07-antennas-mimo-and-beamforming.md) · [다음 →](09-cellular-generations-and-architecture.md)
