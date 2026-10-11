# 04. 변조·부호화·오류

## 변조는 bit를 “파형 선택”으로 바꾸는 규칙이다

**변조**는 coded bit 묶음을 channel에 보낼 진폭·위상·주파수 선택으로 매핑한다. **symbol**은 한 symbol interval 동안 선택한 상태이고, **constellation**은 가능한 I/Q 점의 모음이다.

BPSK는 두 점으로 1 coded bit, QPSK는 네 점으로 2 bit, 16-QAM은 16점으로 4 bit, 64-QAM은 64점으로 6 bit를 나타낼 수 있다. 점 수가 많으면 같은 symbol rate의 raw bit rate가 높지만 이웃 점 간 거리가 가까워져 같은 noise에서 오판 가능성이 커진다.

평균 전력을 맞춘 constellation에서 64-QAM이 QPSK보다 “신호가 강해서 빠른” 것이 아니다. 더 촘촘한 점을 구별할 SNR과 channel 추정 정확도가 필요하다.

## FEC는 여분 구조로 오류를 추정한다

**FEC(Forward Error Correction)** 는 정보 bit에 구조화된 여분을 더해 수신기가 일부 오류를 고치게 한다. code rate `R=K/N`은 K information bit를 N coded bit로 만든 비율이다. rate 1/2는 1,000 information bit를 2,000 coded bit로 만든다.

반복 부호 `1→111`에서 관측 101은 다수결로 1을 복구하지만 100은 0으로 잘못 복구한다. 실제 cellular·Wi-Fi code는 훨씬 복잡하지만, 여분이 무한 오류 정정을 뜻하지 않는다는 점은 같다.

**interleaver**는 인접 coded bit를 시간·주파수에 흩어 burst error가 한 code 부분에 몰리는 것을 줄인다. channel이 전체 block을 깊은 fade로 지우면 강한 FEC도 정보가 부족할 수 있다.

## detector, LLR, decoder, CRC의 역할

detector는 보정된 I/Q 관측이 각 bit 가설과 얼마나 맞는지 soft value를 만든다. **LLR**은 두 bit 가설의 가능성 비율을 로그로 나타낸다. 부호 convention은 구현마다 확인한다. 절댓값이 크면 한 가설에 대한 확신이 크고 0 근처면 불확실하다.

decoder는 여러 LLR과 code 제약을 함께 사용해 information bit 후보를 찾는다. **CRC**는 복호된 frame이 송신자가 붙인 다항식 검사 관계를 만족하는지 본다. FEC는 정정을 시도하고 CRC는 남은 오류를 주로 검출한다.

| 단계 | 입력 | 중간 상태 | 출력 |
|---|---|---|---|
| FEC encoder | information bit | code block | coded bit |
| mapper | coded bit | constellation | I/Q symbol |
| detector | I/Q·noise 추정 | 거리·LLR | soft bit |
| decoder | LLR | code constraint | 정보 후보 |
| CRC | frame bit | remainder | pass/fail |

CRC pass도 오류 확률 0을 뜻하지 않는다. 검사 길이와 오류 패턴에 따라 미검출 가능성이 작게 남는다.

## ARQ와 HARQ를 시간 방향으로 본다

**ARQ**는 실패한 block을 다시 요청한다. **HARQ**는 이전 수신의 soft information을 buffer에 보존하고 재전송 관측과 결합한다. chase combining은 같은 coded 정보를 다시 관측할 수 있고 incremental redundancy는 다른 parity를 추가할 수 있다.

| 시각 | 송신기 | 수신기 |
|---:|---|---|
| 0 ms | block 7 전송 | I/Q 수신 |
| 1 ms | feedback 대기 | LLR·FEC·CRC 실패 |
| 2 ms | NACK 수신 | soft buffer 보존 |
| 3 ms | 추가 parity 전송 | 이전 LLR과 결합 |
| 4 ms | ACK 수신 | CRC pass·상위 전달 |

재전송이 성공률을 높이지만 airtime과 latency를 사용한다. 높은 MCS로 첫 전송이 자주 실패하면 raw rate가 높아도 goodput은 낮을 수 있다.

## 전체 block 수치 추적

payload 1,000 bit, header와 CRC 200 bit면 information block은 1,200 bit다. code rate 1/2이면 2,400 coded bit다. 16-QAM은 4 coded bit/symbol이므로 600 symbol이다. symbol rate 100 ksymbol/s라면 data symbol 시간은 6 ms다.

첫 전송 실패 후 같은 크기 자원을 한 번 더 쓰면 data symbol airtime은 12 ms다. ACK/NACK, preamble, scheduling은 별도다. payload 기준 첫 전송 coding·header 효율은 `1000/2400≈41.7%`다. 한 번 재전송하면 사용 coded bit는 4,800으로 `1000/4800≈20.8%`다.

둘째 예는 64-QAM, code rate 3/4다. 1,200 information bit는 `1200/(3/4)=1600 coded bit`다. symbol당 6 bit이므로 `1600/6≈266.7`이라 padding을 고려해 최소 267 symbol이 필요하다. 모든 resource element가 data는 아니므로 실제 resource 수는 더 크다.

## channel 조건과 MCS 선택

**MCS(Modulation and Coding Scheme)** 는 변조 차수와 code rate 등 전송 강도를 묶은 선택이다. receiver의 channel quality feedback, 최근 error, 목표 block error rate를 보고 scheduler가 고른다.

channel이 빠르게 바뀌면 측정 시점과 실제 전송 사이 정보가 낡는다. 고속 이동 Doppler, 간섭 변화, beam 변경이 원인이다. 보수적 MCS는 성공률을 높일 수 있지만 더 많은 airtime을 쓴다. 공격적 MCS는 첫 전송 raw rate가 높지만 HARQ가 늘 수 있다.

| MCS 모형 | coded bit/symbol | code rate | 첫 전송 성공률 | 기대 payload 경향 |
|---|---:|---:|---:|---|
| QPSK robust | 2 | 1/2 | 높음 | 낮은 raw rate |
| 16-QAM middle | 4 | 3/4 | 중간 | 균형 |
| 64-QAM aggressive | 6 | 5/6 | 낮을 수 있음 | 좋은 channel에서 유리 |

수치는 특정 표준 MCS 표가 아니라 관계를 설명하는 교육 모형이다.

## AI-RAN 평가와 negative transfer

AI가 MCS나 decoder 관련 값을 예측할 때 metric은 raw accuracy만이 아니다. block error, goodput, latency, 재전송, 안전 fallback을 함께 본다. 한 channel·속도에서 학습한 모델이 다른 환경에서 성능을 잃을 수 있다.

2024 multi-task learning 연구는 네 simulation task와 partial federation 조건에서 공동 학습을 평가하며 negative transfer 가능성을 다룬다. [원문](https://arxiv.org/abs/2404.15197)의 task·dataset·metric을 실제 표준 MCS 성능 보장으로 바꾸지 않는다.

## 오류 개수와 오류 모양

100 coded bit 중 흩어진 오류 10개와 연속 10 bit burst는 BER 10%로 같다. 그러나 code와 interleaver 구조에 따라 복호 결과가 다르다.

| 전송 | 오류 모양 | 복호 조건 |
|---|---|---|
| A | 여러 위치에 분산 | code 제약에 분산 |
| B | 40~49 연속 | 한 부분 집중 |
| C | block 전체 deep fade | soft 정보 모두 약함 |

interleaver는 burst를 여러 code 위치로 흩지만 지연·메모리를 쓰고 fade가 interleaver 범위보다 길면 한계가 있다. 평균 BER 하나만으로 frame 성공률을 결정할 수 없다.

HARQ buffer가 유실되면 재전송이 와도 이전 LLR과 결합하지 못한다. 송신 재전송 절차와 수신 buffer 수명은 함께 맞아야 한다.

## 추가 문제와 완전 해설

### 1. 256-QAM은 이상적으로 symbol당 몇 coded bit인가?
점 256개는 `log2(256)=8`이므로 8 bit다.

### 2. 1,500 information bit, rate 3/5의 coded bit는?
`1500/(3/5)=2500 bit`다.

### 3. 2,400 coded bit를 64-QAM으로 보내는 symbol 수는?
`2400/6=400 symbol`이다.

### 4. 첫 전송 600 symbol과 재전송 300 symbol을 썼다면 총 data symbol은?
900 symbol이다. incremental redundancy가 절반 크기라는 교육용 조건이다.

### 5. 높은 MCS가 goodput을 낮출 수 있는 이유는?
channel이 점 간격과 code rate를 감당하지 못하면 CRC 실패와 HARQ 재전송이 늘어 실제 성공 payload/time이 줄기 때문이다.

[이 책 목차](README.md)

[← 이전](03-sampling-iq-and-radio-chain.md) · [다음 →](05-channel-noise-and-capacity.md)

## 핵심 계산 복습: 변조와 symbol

변조는 bit를 channel에 보낼 파형 선택으로 바꾸는 규칙이다.
symbol은 한 번의 선택이다.
constellation은 가능한 I/Q 점의 모음이다.

| 방식 | 점 | coded bit/symbol |
|---|---:|---:|
| BPSK | 2 | 1 |
| QPSK | 4 | 2 |
| 16-QAM | 16 | 4 |
| 64-QAM | 64 | 6 |

점이 많으면 같은 symbol rate에서 더 많은 bit를 보낸다.
점 간격이 가까워져 noise에 더 민감할 수 있다.

## QPSK 예

```text
00 → (+1,+1)
01 → (-1,+1)
11 → (-1,-1)
10 → (+1,-1)
```

입력 `00 10 11`은 세 symbol이 된다.
두 번째 수신점 `(0.8,-0.7)`은 `(1,-1)`과 가까워 `10`으로 판단할 수 있다.
경계 `(0.02,0.01)`은 작은 noise에도 판단이 바뀐다.

```mermaid
flowchart LR
    B[정보 bit] --> E[FEC encoder]
    E --> M[mapper]
    M --> C[channel]
    C --> L[LLR detector]
    L --> D[FEC decoder]
    D --> CRC[CRC]
    CRC --> O[accept 또는 retransmit]
```

## FEC와 code rate

FEC는 구조화된 여분 bit로 receiver가 오류 정정을 시도하게 한다.
code rate는 `정보 bit/coded bit`다.

1,000bit를 rate 1/2로 부호화하면 2,000coded bit다.
900bit를 rate 3/4로 부호화하면 1,200coded bit다.
낮은 rate는 여분이 많고 airtime도 늘어난다.

## 반복 부호 예

bit 1을 `111`로 보낸다.
관측이 `101`이면 다수결로 1을 복구한다.
`100`이면 0으로 잘못 복구한다.
실제 Wi‑Fi 부호가 아니라 정정 원리 모형이다.

## hard와 soft

hard decision은 0/1 하나만 낸다.
soft decision은 어느 쪽을 얼마나 믿는지 준다.
LLR은 두 bit 가설의 가능성 비율을 로그로 나타낸다.

```text
LLR +8: convention상 0을 강하게 믿음
LLR +0.2: 0 쪽이지만 약함
LLR -6: 1을 강하게 믿음
```

부호 convention은 구현에 따라 반대일 수 있다.

## soft 결합

반복 관측 LLR이 `-4,-3,+1`이면 합은 -6이다.
하나가 반대여도 전체는 1 쪽 증거가 강하다.
decoder는 code 구조와 여러 soft evidence를 함께 쓴다.

## CRC

CRC는 주로 오류 검출용이다.
FEC는 오류 정정 시도용이다.
FEC 복호 뒤 CRC 실패면 frame을 폐기하거나 재전송한다.
CRC 통과도 오류 확률 0은 아니다.

## ARQ와 HARQ

ARQ는 실패 frame을 재전송한다.
HARQ는 재전송 관측과 FEC 정보를 결합한다.

| 순서 | 송신 | 수신 |
|---:|---|---|
| 1 | coded block | decode+CRC |
| 2 | ACK 대기 | 실패면 NACK |
| 3 | 재전송/추가 parity | 이전 soft 정보와 결합 |
| 4 | ACK | 상위 전달 |

incremental redundancy는 같은 bit 반복이 아니라 추가 parity를 보낼 수 있다.

## 효율 계산

payload 1,000, header+CRC 200, rate 1/2:

```text
정보 block = 1200bit
coded = 2400bit
16-QAM = 4bit/symbol
필요 symbol = 600
payload/coded 효율 = 41.7%
```

재전송 한 번이면 같은 payload의 air resource가 더 든다.

## 상태표

| 주체 | 입력 | 상태 | 결과 |
|---|---|---|---|
| encoder | information bit | code block | coded bit |
| mapper | coded bit | constellation | I/Q |
| detector | I/Q·channel | 거리·noise | LLR |
| decoder | LLR | code constraint | bit 후보 |
| CRC | frame | remainder | pass/fail |
| HARQ | fail+buffer | combining | retry 결과 |

## link adaptation

receiver feedback와 error history로 MCS를 고른다.
높은 MCS는 고차 modulation/높은 code rate를 사용할 수 있다.
channel이 바뀌면 과거 측정이 오래될 수 있다.
보수적 MCS는 robust하지만 airtime이 늘어난다.

## 반례

64-QAM이 QPSK보다 항상 빠르지 않다.
재전송이 많으면 goodput이 낮아진다.
강한 FEC도 deep fade의 모든 오류를 고치지 못한다.
LLR scale이 틀리면 decoder가 잘못된 확신을 받을 수 있다.

## 문제

## LLR·FEC·CRC·HARQ를 한 frame에서 구분하기

detector는 각 coded bit가 0/1 중 어느 쪽인지와 확신도를 LLR로 만든다.
FEC decoder는 여러 LLR을 code 제약과 함께 처리해 원래 information bit 후보를 복원한다.
CRC는 복원된 frame 전체가 송신자가 붙인 검사 관계를 만족하는지 확인한다.
CRC 실패면 receiver는 그 frame을 상위에 전달하지 않는다.
HARQ controller는 실패한 전송의 soft buffer를 보관하고 송신자에게 재전송을 요구한다.
다음 redundancy가 오면 이전 LLR과 결합해 FEC decoder를 다시 실행한다.
LLR은 입력 증거, FEC는 정정 알고리즘, CRC는 최종 검출, HARQ는 시간에 걸친 재전송 절차다.

1. 64-QAM 100symbol의 coded bit는?
2. 1,200coded bit를 rate 1/2로 썼다면 information bit는?
3. CRC와 FEC 차이는?

## 해설

1. `100×6=600bit`다.
2. `1,200×1/2=600bit`다.
3. CRC는 주로 검출, FEC는 여분 구조로 정정을 시도한다.

## 공식 출처

- [MIT 6.451 hard/soft decoding](https://ocw.mit.edu/courses/6-451-principles-of-digital-communication-ii-spring-2005/download/)
- [MIT 6.02 coding readings](https://ocw.mit.edu/courses/6-02-introduction-to-eecs-ii-digital-communication-systems-fall-2012/pages/readings/)

[← 이전](03-sampling-iq-and-radio-chain.md) · [다음 →](05-channel-noise-and-capacity.md)
