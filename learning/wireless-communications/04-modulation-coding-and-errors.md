# 04. 변조·부호화·오류

[← 이전](03-sampling-iq-and-radio-chain.md) · [다음 →](05-channel-noise-and-capacity.md)

## 1. 변조는 bit를 파형 선택으로 바꾸는 규칙이다

**변조(modulation)**는 coded bit 묶음을 channel에 보낼 진폭·위상·주파수 선택으로 매핑한다. **Symbol(심볼)**은 한 symbol interval 동안 선택한 상태이고, **constellation(성상도)**은 가능한 I/Q(In-phase/Quadrature, 동상·직교) 점의 모음이다.

**BPSK(Binary Phase Shift Keying, 이진 위상 편이 변조)**는 두 점으로 1 coded bit, **QPSK(Quadrature Phase Shift Keying, 직교 위상 편이 변조)**는 네 점으로 2 bit를 나타낸다. **QAM(Quadrature Amplitude Modulation, 직교 진폭 변조)**의 16-QAM은 16점으로 4 bit, 64-QAM은 64점으로 6 bit를 나타낼 수 있다. 점 수가 많으면 같은 symbol rate의 raw bit rate가 높지만 이웃 점 간 거리가 가까워져 같은 noise에서 오판 가능성이 커진다.

평균 전력을 맞춘 constellation에서 64-QAM이 QPSK보다 “신호가 강해서 빠른” 것이 아니다. 더 촘촘한 점을 구별할 SNR과 channel 추정 정확도가 필요하다.

QPSK(Quadrature Phase Shift Keying, 직교 위상 편이 변조)의 한 교육용 Gray mapping은 다음처럼 쓸 수 있다. 실제 구현은 축 정규화와 mapping 약속을 확인한다.

```text
00 → (+1,+1)
01 → (-1,+1)
11 → (-1,-1)
10 → (+1,-1)
```

입력 `00 10 11`은 세 symbol이 된다. 두 번째 수신점 `(0.8,-0.7)`은 `(+1,-1)`과 가까워 `10`으로 판단할 수 있지만 경계 `(0.02,0.01)` 부근은 작은 noise에도 판단이 바뀐다.

```mermaid
flowchart LR
    B["정보 bit"] --> E["FEC encoder"]
    E --> M["constellation mapper"]
    M --> C["channel"]
    C --> L["LLR detector"]
    L --> D["FEC decoder"]
    D --> R["CRC"]
    R --> O["accept 또는 retransmit"]
```

## 2. FEC는 여분 구조로 오류를 추정한다

**FEC(Forward Error Correction, 순방향 오류 정정)**는 정보 bit에 구조화된 여분을 더해 수신기가 일부 오류를 고치게 한다. code rate `R=K/N`은 K information bit를 N coded bit로 만든 비율이다. rate 1/2는 1,000 information bit를 2,000 coded bit로 만든다.

반복 부호 `1→111`에서 관측 101은 다수결로 1을 복구하지만 100은 0으로 잘못 복구한다. 실제 cellular·Wi-Fi code는 훨씬 복잡하지만, 여분이 무한 오류 정정을 뜻하지 않는다는 점은 같다.

**interleaver**는 인접 coded bit를 시간·주파수에 흩어 burst error가 한 code 부분에 몰리는 것을 줄인다. channel이 전체 block을 깊은 fade로 지우면 강한 FEC도 정보가 부족할 수 있다.

## 3. Detector, LLR, decoder와 CRC

detector는 보정된 I/Q 관측이 각 bit 가설과 얼마나 맞는지 soft value를 만든다. **LLR(Log-Likelihood Ratio, 로그 가능도비)**은 두 bit 가설의 가능성 비율을 로그로 나타낸다. 부호 convention은 구현마다 확인한다. 절댓값이 크면 한 가설에 대한 확신이 크고 0 근처면 불확실하다.

Decoder는 여러 LLR과 code 제약을 함께 사용해 information bit 후보를 찾는다. **CRC(Cyclic Redundancy Check, 순환 중복 검사)**는 복호된 frame이 송신자가 붙인 다항식 검사 관계를 만족하는지 본다. FEC는 정정을 시도하고 CRC는 남은 오류를 주로 검출한다.

| 단계 | 입력 | 중간 상태 | 출력 |
|---|---|---|---|
| FEC encoder | information bit | code block | coded bit |
| mapper | coded bit | constellation | I/Q symbol |
| detector | I/Q·noise 추정 | 거리·LLR | soft bit |
| decoder | LLR | code constraint | 정보 후보 |
| CRC | frame bit | remainder | pass/fail |

CRC pass도 오류 확률 0을 뜻하지 않는다. 검사 길이와 오류 패턴에 따라 미검출 가능성이 작게 남는다.

Hard decision은 각 bit를 0 또는 1 하나로 확정하지만 soft decision은 어느 쪽을 얼마나 믿는지도 전달한다. 예를 들어 구현 convention에서 양수가 0의 증거라면 LLR `+8`은 0을 강하게, `+0.2`는 0을 약하게, `-6`은 1을 강하게 지지한다. 부호 convention은 반대일 수 있다. 반복 관측 LLR `-4, -3, +1`을 단순 합하면 `-6`이므로 하나의 반대 관측이 있어도 전체는 1 쪽 증거가 강하다.

## 4. ARQ와 HARQ를 시간 방향으로 본다

**ARQ(Automatic Repeat reQuest, 자동 재전송 요청)**는 실패한 block을 다시 요청한다. **HARQ(Hybrid ARQ, 혼합 자동 재전송 요청)**는 이전 수신의 soft information을 buffer에 보존하고 재전송 관측과 결합한다. chase combining은 같은 coded 정보를 다시 관측할 수 있고 incremental redundancy는 다른 parity를 추가할 수 있다.

| 시각 | 송신기 | 수신기 |
|---:|---|---|
| 0 ms | block 7 전송 | I/Q 수신 |
| 1 ms | feedback 대기 | LLR·FEC·CRC 실패 |
| 2 ms | NACK 수신 | soft buffer 보존 |
| 3 ms | 추가 parity 전송 | 이전 LLR과 결합 |
| 4 ms | ACK 수신 | CRC pass·상위 전달 |

재전송이 성공률을 높이지만 airtime과 latency를 사용한다. 높은 MCS로 첫 전송이 자주 실패하면 raw rate가 높아도 goodput은 낮을 수 있다.

## 5. 전체 block 수치 추적

payload 1,000 bit, header와 CRC 200 bit면 information block은 1,200 bit다. code rate 1/2이면 2,400 coded bit다. 16-QAM은 4 coded bit/symbol이므로 600 symbol이다. symbol rate 100 ksymbol/s라면 data symbol 시간은 6 ms다.

첫 전송 실패 후 같은 크기 자원을 한 번 더 쓰면 data symbol airtime은 12 ms다. ACK/NACK, preamble, scheduling은 별도다. payload 기준 첫 전송 coding·header 효율은 `1000/2400≈41.7%`다. 한 번 재전송하면 사용 coded bit는 4,800으로 `1000/4800≈20.8%`다.

둘째 예는 64-QAM, code rate 3/4다. 1,200 information bit는 `1200/(3/4)=1600 coded bit`다. symbol당 6 bit이므로 `1600/6≈266.7`이라 padding을 고려해 최소 267 symbol이 필요하다. 모든 resource element가 data는 아니므로 실제 resource 수는 더 크다.

## 6. Channel 조건과 MCS 선택

**MCS(Modulation and Coding Scheme, 변조·부호화 조합)**는 변조 차수와 code rate 등 전송 강도를 묶은 선택이다. receiver의 channel quality feedback, 최근 error, 목표 block error rate를 보고 scheduler가 고른다.

channel이 빠르게 바뀌면 측정 시점과 실제 전송 사이 정보가 낡는다. 고속 이동 Doppler, 간섭 변화, beam 변경이 원인이다. 보수적 MCS는 성공률을 높일 수 있지만 더 많은 airtime을 쓴다. 공격적 MCS는 첫 전송 raw rate가 높지만 HARQ가 늘 수 있다.

| MCS 모형 | coded bit/symbol | code rate | 첫 전송 성공률 | 기대 payload 경향 |
|---|---:|---:|---:|---|
| QPSK robust | 2 | 1/2 | 높음 | 낮은 raw rate |
| 16-QAM middle | 4 | 3/4 | 중간 | 균형 |
| 64-QAM aggressive | 6 | 5/6 | 낮을 수 있음 | 좋은 channel에서 유리 |

수치는 특정 표준 MCS 표가 아니라 관계를 설명하는 교육 모형이다.

## 7. BER, BLER와 오류 모양

**BER(Bit Error Rate, 비트 오류율)**은 비교한 전체 bit 가운데 잘못 판정한 bit의 비율이다. **BLER(Block Error Rate, 블록 오류율)**은 전송 block 가운데 복호·CRC 검사에 실패한 block의 비율이다. 예를 들어 100개 block 중 5개가 실패하면 BLER는 5%다. 전체 100,000 bit를 기준으로 120 bit가 잘못됐다면 BER는 0.12%다. 같은 BLER라도 실패 block 안 오류 수는 다를 수 있고, 같은 평균 BER라도 오류가 block에 몰리는 방식은 다를 수 있다.

100 coded bit 중 흩어진 오류 10개와 연속 10 bit burst는 BER 10%로 같다. 그러나 code와 interleaver 구조에 따라 복호 결과가 다르다.

| 전송 | 오류 모양 | 복호 조건 |
|---|---|---|
| A | 여러 위치에 분산 | code 제약에 분산 |
| B | 40~49 연속 | 한 부분 집중 |
| C | block 전체 deep fade | soft 정보 모두 약함 |

interleaver는 burst를 여러 code 위치로 흩지만 지연·메모리를 쓰고 fade가 interleaver 범위보다 길면 한계가 있다. 평균 BER 하나만으로 frame 성공률을 결정할 수 없다.

HARQ buffer가 유실되면 재전송이 와도 이전 LLR과 결합하지 못한다. 송신 재전송 절차와 수신 buffer 수명은 함께 맞아야 한다.

## 8. AI-RAN 연구의 평가 경계

AI가 MCS나 decoder 관련 값을 예측할 때 metric은 raw accuracy만이 아니다. block error, goodput, latency, 재전송, 안전 fallback을 함께 본다. 한 channel·속도에서 학습한 모델이 다른 환경에서 성능을 잃을 수 있다.

2024 multi-task learning 연구는 네 simulation task와 partial federation 조건에서 공동 학습을 평가하며 negative transfer 가능성을 다룬다. [원문](https://arxiv.org/abs/2404.15197)의 task·dataset·metric을 실제 표준 MCS 성능 보장으로 바꾸지 않는다.

## 9. 통합 문제와 완전 해설

### 9.1 256-QAM은 이상적으로 symbol당 몇 coded bit인가?
점 256개는 `log2(256)=8`이므로 8 bit다.

### 9.2 1,500 information bit, rate 3/5의 coded bit는?
`1500/(3/5)=2500 bit`다.

### 9.3 2,400 coded bit를 64-QAM으로 보내는 symbol 수는?
`2400/6=400 symbol`이다.

### 9.4 첫 전송 600 symbol과 재전송 300 symbol을 썼다면 총 data symbol은?
900 symbol이다. incremental redundancy가 절반 크기라는 교육용 조건이다.

### 9.5 높은 MCS가 goodput을 낮출 수 있는 이유는?
channel이 점 간격과 code rate를 감당하지 못하면 CRC 실패와 HARQ 재전송이 늘어 실제 성공 payload/time이 줄기 때문이다.

### 9.6 64-QAM 100 symbol은 몇 coded bit를 나타내는가?

`100×6=600 bit`다.

### 9.7 1,200 coded bit를 rate 1/2로 부호화했다면 information bit는?

Code rate가 information/coded이므로 `1,200×1/2=600 bit`다.

### 9.8 LLR, FEC, CRC와 HARQ를 한 frame에서 구분하라.

LLR은 detector가 만든 bit 가설의 soft evidence다. FEC decoder는 여러 LLR과 code 제약으로 information bit 후보를 복원한다. CRC는 복원 frame 전체의 검사 관계를 확인한다. CRC 실패 시 HARQ controller는 soft buffer 수명 안에서 이전 LLR을 보존하고 재전송 또는 추가 parity와 결합한다. 즉 LLR은 입력 증거, FEC는 정정 절차, CRC는 최종 검출, HARQ는 시간에 걸친 재전송 절차다.

## 10. 공식 출처

- [MIT 6.451 hard/soft decoding](https://ocw.mit.edu/courses/6-451-principles-of-digital-communication-ii-spring-2005/download/)
- [MIT 6.02 coding readings](https://ocw.mit.edu/courses/6-02-introduction-to-eecs-ii-digital-communication-systems-fall-2012/pages/readings/)

[← 이전](03-sampling-iq-and-radio-chain.md) · [다음 →](05-channel-noise-and-capacity.md)
