# 06. OFDM·시간·주파수·자원

## 긴 wideband symbol의 문제를 여러 좁은 subcarrier로 나눈다

넓은 대역 단일 carrier는 multipath 때문에 긴 equalizer가 필요할 수 있다. **OFDM**은 대역을 많은 좁은 subcarrier로 나누고 각 subcarrier에는 긴 symbol을 보낸다. 각 좁은 대역 안에서 channel이 거의 flat하다고 보고 간단한 복소 곱으로 보정한다.

**subcarrier**는 서로 다른 중심 주파수의 sinusoid 성분이다. 간격 Δf와 유효 symbol 시간 T가 `Δf=1/T` 관계를 가지면 한 symbol 구간 적분에서 다른 subcarrier가 0이 되는 **직교성**을 얻는다. spectrum이 겹쳐 보여도 FFT bin에서 구별된다.

Δf=15 kHz이면 유효 symbol 시간은 `1/15000≈66.67 μs`다. 30 kHz이면 약 33.33 μs다. 실제 symbol에는 cyclic prefix 시간이 추가된다.

## IFFT와 FFT가 하는 일

송신기는 각 subcarrier에 QAM symbol X[k]를 놓는다. IFFT는 이 주파수 bin 목록을 N개의 시간 sample x[n]으로 바꾼다. DAC와 RF chain이 시간 파형을 보낸다. 수신기는 symbol 경계를 맞춘 뒤 FFT로 다시 subcarrier별 Y[k]를 얻는다.

| 단계 | 입력 | 주체 | 출력 |
|---|---|---|---|
| mapping | coded bit | mapper | X[k] QAM 점 |
| IFFT | 주파수 bin | baseband | x[n] 시간 sample |
| CP 삽입 | x[n] 끝부분 | baseband | CP+x[n] |
| channel | 시간 파형 | 공간 | 지연 경로 합 |
| CP 제거·FFT | 수신 sample | receiver | Y[k] |
| equalization | Y[k], H[k] | receiver | X 추정 |

8-point toy에서 bin 1과 3에 symbol을 두고 IFFT하면 8개 시간이 생성된다. 수신 FFT는 동기가 맞고 channel이 이상적일 때 다시 bin 1과 3을 분리한다. IFFT는 여덟 radio를 만드는 것이 아니라 하나의 합성 시간 파형을 계산한다.

## cyclic prefix가 지연 경로를 흡수하는 조건

**CP**는 유효 OFDM symbol 끝부분을 앞에 복사한 guard 구간이다. 최대 의미 있는 channel 지연이 CP보다 짧고 FFT window가 맞으면 이전 symbol의 꼬리가 CP 안에 머물러 유효 구간을 보호한다. 선형 convolution을 FFT가 다루기 쉬운 circular convolution처럼 보이게 한다.

유효 symbol 66.67 μs, CP 4.7 μs라고 하자. 지연 spread 2 μs는 CP 안이지만 7 μs 경로는 유효 구간을 침범해 ISI와 직교성 손상을 만든다.

| 경로 | 지연 | CP 4.7 μs 안? | 결과 |
|---|---:|---|---|
| 직접 | 0 | 예 | 기준 |
| 반사 A | 2 μs | 예 | subcarrier별 H[k]로 보정 |
| 반사 B | 7 μs | 아니오 | 다음 symbol 침범 가능 |

CP는 매 symbol 반복되는 overhead다. `66.67/(66.67+4.7)≈93.4%`가 유효 시간 비율이다.

## resource grid와 payload 계산

**resource element(RE)** 는 한 subcarrier와 한 OFDM symbol의 교차 칸이다. **resource block(RB)** 은 주파수 방향 12 subcarrier 묶음이다. NR normal CP 조건의 한 slot에 14 OFDM symbol이 있다는 모형을 쓰면 한 RB의 raw RE는 `12×14=168`개다.

10 RB를 할당하면 1,680 RE다. 그중 pilot·control 280 RE를 빼면 data RE는 1,400개다. 16-QAM 4 coded bit/RE, code rate 3/4라면 information 후보는 `1400×4×0.75=4200 bit`, 약 525 byte다. layer 2개가 독립 전송 가능하면 이상 후보는 두 배지만 rank·power·overhead 조건이 필요하다.

## numerology와 시간 선택

subcarrier spacing을 키우면 symbol은 짧아져 빠른 시간 변화와 큰 Doppler에 유리할 수 있지만 같은 절대 CP 시간·overhead와 delay spread 조건이 달라진다. 좁은 spacing은 긴 symbol로 multipath 상대 영향이 줄 수 있으나 slot 시간과 phase noise 조건을 함께 본다.

frequency offset이 Δf의 큰 비율이면 FFT bin 사이 leakage가 생겨 직교성이 깨진다. timing, carrier recovery, phase noise가 OFDM에서 중요한 이유다.

## PAPR 반례와 AI-RAN 연결

여러 subcarrier가 같은 위상으로 더해지는 순간 peak가 커져 PAPR이 높다. PA backoff를 두지 않으면 clipping과 spectral regrowth가 생긴다. subcarrier 수가 많다는 사실만으로 전력 효율이 좋아지지 않는다.

AI scheduler가 RB를 할당할 때 입력 CSI가 오래됐거나 pilot 오염이 있으면 계산상 높은 rate 배치가 HARQ 실패를 만들 수 있다. 논문 simulation의 grid·channel·traffic 가정을 운영 보장으로 확대하지 않는다.

## 핵심 계산 복습: 왜 여러 작은 subcarrier로 나누는가

넓은 대역 하나에서 빠른 symbol을 보내면 multipath delay가 symbol 사이를 쉽게 겹치게 한다.
OFDM은 bandwidth를 서로 직교하는 여러 좁은 subcarrier로 나눈다.
각 subcarrier는 더 느린 symbol을 보낸다.
주파수별 channel 차이를 작은 단위로 보정하기 쉬워진다.

![OFDM 자원격자](assets/ofdm-grid.svg)

## 직교의 뜻

직교는 한 OFDM symbol 구간에서 subcarrier들을 정해진 방식으로 관측하면 서로의 성분이 0으로 분리되는 성질이다.
주파수가 떨어져 있어야 한다는 말만으로 충분하지 않다.
subcarrier 간격과 symbol 유효시간이 맞아야 한다.

```text
유효 symbol 시간 Tu = 8µs
subcarrier 간격 Δf = 1/Tu = 125kHz
```

각 파는 구간 안에서 정수 번 회전해 다른 파와 내적하면 상쇄된다.
timing/frequency offset이 크면 직교성이 깨져 ICI가 생긴다.

## IFFT와 FFT

송신기는 subcarrier별 I/Q symbol들을 IFFT에 넣어 시간 sample 묶음을 만든다.
수신기는 FFT로 시간 sample을 subcarrier별 관측으로 되돌린다.

```mermaid
flowchart LR
    S[8개 subcarrier symbol] --> IFFT[8-point IFFT]
    IFFT --> CP[CP 붙이기]
    CP --> CH[channel]
    CH --> RCP[CP 제거]
    RCP --> FFT[8-point FFT]
    FFT --> Y[8개 관측]
```

FFT가 channel과 noise를 없애는 것은 아니다.
주파수별 관측으로 나누고 pilot 기반 equalization이 뒤따른다.

## 8-subcarrier toy grid

subcarrier index 0~7, OFDM symbol time 0~3을 쓰자.

| time\\subcarrier | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---:|---|---|---|---|---|---|---|---|
| 0 | guard | data | data | pilot | data | data | data | guard |
| 1 | guard | data | data | pilot | data | data | data | guard |
| 2 | guard | data | data | pilot | data | data | data | guard |
| 3 | guard | data | data | pilot | data | data | data | guard |

한 time에 data subcarrier는 5개다.
QPSK면 subcarrier당 2coded bit이므로 OFDM symbol당 10coded bit다.
4개 time이면 40coded bit다.
coding rate 1/2면 이상적 information bit는 20bit다.

guard와 pilot은 payload bit를 직접 싣지 않는다.
그래도 spectrum edge 보호와 channel 추정에 필요하다.

## CP

cyclic prefix(CP)는 OFDM symbol 끝 일부를 앞에 복사한 guard interval이다.
delay spread가 CP 안에 들어오고 동기가 맞으면 이전 symbol 영향이 FFT 유효 구간에 덜 들어오게 한다.
linear convolution을 subcarrier별 곱셈처럼 다루는 조건을 만든다.

```text
유효 sample 8개: [a b c d e f g h]
CP 길이 2:       [g h | a b c d e f g h]
```

전체 시간은 10 sample이고 payload 계산에 쓰는 새 유효 sample은 8개다.
CP overhead는 `2/10=20%`다.

CP가 delay spread보다 짧으면 ISI/ICI가 남을 수 있다.
CP를 무한히 길게 하면 보호는 늘지만 효율이 떨어진다.

## resource element와 resource unit

resource element는 특정 time과 subcarrier의 한 칸으로 생각할 수 있다.
여러 칸을 묶어 user나 signal에 할당한다.
표준마다 resource unit/block 이름과 크기가 다르다.
이 toy grid를 실제 Wi‑Fi/5G 숫자로 읽지 않는다.

## pilot

송신자와 수신자가 알고 있는 symbol을 pilot으로 보낸다.
수신기는 보낸 값 `x`와 받은 값 `y`를 비교해 channel `h≈y/x`를 추정한다.

pilot `x=1+j0`, 수신 `y=0.8+j0.2`이면 추정 `h≈0.8+j0.2`다.
data 관측을 이 channel로 보정한다.
pilot 사이에서 channel이 너무 빨리 바뀌면 interpolation이 틀릴 수 있다.

## PAPR

여러 subcarrier 파가 같은 순간 같은 방향으로 더해지면 peak가 커질 수 있다.
평균 대비 peak 비율을 PAPR로 본다.
power amplifier가 peak를 못 받으면 clipping과 spectrum regrowth가 생긴다.
출력 back-off는 선형성을 돕지만 전력 효율을 낮출 수 있다.

## 상태 추적

| 단계 | 입력 | 상태 | 출력 |
|---|---|---|---|
| mapper | coded bit | modulation | subcarrier I/Q |
| resource mapper | data/pilot | grid 위치 | grid |
| IFFT | grid 한 열 | phase 합 | time samples |
| CP | tail samples | 앞에 복사 | 전송 symbol |
| FFT | 수신 유효 구간 | 직교 분해 | subcarrier 관측 |
| equalizer | 관측+pilot | channel estimate | 보정 symbol |

## 반례

subcarrier 수가 많다고 항상 처리량이 증가하지 않는다.
FFT size, CP, pilot, guard, sampling 조건이 함께 바뀐다.
OFDM은 narrowband interference를 사라지게 하지 않는다.
frequency offset이 크면 인접 subcarrier 간섭이 생긴다.

## 복소수 회전과 직교를 네 sample로 확인하기

복소수 `e^{jθ}=cosθ+j sinθ`는 크기 1인 회전을 나타낸다. 4-point OFDM에서 subcarrier k의 n번째 sample은 `e^{j2πkn/4}` 꼴이다. k=0은 `[1,1,1,1]`, k=1은 `[1,j,-1,-j]`다.

두 파가 직교하는지 보려면 한 symbol 구간에서 하나와 다른 하나의 **켤레복소수**를 곱해 더하는 내적을 본다. 켤레는 `a+jb`의 허수 부호를 바꾼 `a-jb`다. k=0과 k=1의 합은 `1+j-1-j=0`이다. Spectrum이 겹쳐 보여도 정확한 시간창·간격·주파수에서 FFT가 분리할 수 있는 이유다.

주파수 bin을 `X=[1,1,0,0]`으로 두고 정규화를 `1/N`으로 하는 IFFT를 손으로 계산하면 두 subcarrier가 합쳐진다.

| n | k=0 성분 | k=1 성분 | `x[n]=(합)/4` |
|---:|---|---|---|
| 0 | 1 | 1 | 0.5 |
| 1 | 1 | j | 0.25+j0.25 |
| 2 | 1 | -1 | 0 |
| 3 | 1 | -j | 0.25-j0.25 |

이 네 복소 sample이 DAC와 RF chain으로 시간 파형이 된다. 이상 channel과 정확한 timing에서 FFT를 하면 bin 0과 1에서 다시 1을 얻는다. IFFT가 네 개의 물리 송신기를 만드는 것이 아니다.

## CP가 convolution을 다루는 전체 작은 예

유효 sample `x=[1,2,3,4]`, CP 길이 1이면 마지막 sample 4를 앞에 복사해 `[4|1,2,3,4]`를 전송한다. Channel을 현재 sample과 한 sample 지연 복사본의 합 `h=[1,0.5]`라고 하자.

수신 유효 구간에서 각 출력은 현재 값과 직전 값의 절반이다.

| 유효 위치 | 현재 | 직전(CP 포함) | 관측 |
|---:|---:|---:|---:|
| 0 | 1 | 4 | 3 |
| 1 | 2 | 1 | 2.5 |
| 2 | 3 | 2 | 4 |
| 3 | 4 | 3 | 5.5 |

첫 위치가 이전 OFDM symbol의 알 수 없는 꼬리 대신 현재 symbol 끝 4를 사용한다. 유효 구간 안에서 circular convolution이 되어 FFT bin별 곱으로 표현할 수 있다. 지연이 CP 1 sample보다 길면 이전 symbol 성분이 유효 구간에 들어와 이 조건이 깨진다. CP는 channel을 없애지 않고 FFT가 다루기 쉬운 구조를 보존한다.

## Resource grid와 numerology의 전체 계산

**Resource grid(자원 격자)**는 세로축 subcarrier, 가로축 OFDM symbol인 논리 표다. 한 칸인 RE는 data, pilot, control, guard 가운데 한 역할을 갖는다. 3GPP NR의 세부 배치는 TS 38.211 버전에 따라 확인하며, 여기서는 normal CP 한 slot 14 symbol과 RB당 12 subcarrier라는 교육 조건을 쓴다.

5 RB라면 raw RE는 `5×12×14=840`이다. Pilot·control이 140이면 data RE는 700이다. QPSK는 RE당 2 coded bit, code rate 1/2이면 `700×2×0.5=700 information bit` 후보가 된다. 실제 transport block은 CRC, rate matching, reserved RE와 규격 절차로 달라진다.

**Numerology(뉴머롤로지)**는 subcarrier spacing과 symbol·slot 시간 구조의 선택 묶음이다. NR에서 기본 관계를 `Δf=15×2^μ kHz`로 읽을 수 있다. μ=0은 15 kHz, μ=1은 30, μ=2는 60 kHz다. 유효 symbol 시간은 대략 역수라 각각 66.67, 33.33, 16.67 µs다. 실제 CP와 slot 경계는 규격 표를 따른다.

Spacing이 커지면 symbol이 짧아져 같은 절대 delay가 차지하는 비율이 커질 수 있다. 반면 Doppler와 phase 변화에 대한 상대 조건은 달라진다. Numerology 하나가 모든 delay·속도·carrier에 최적이라는 뜻은 아니다.

## 주파수 offset과 ICI

송수신기 oscillator 차이와 Doppler 때문에 carrier frequency offset이 생긴다. Δf=15 kHz인데 offset이 1.5 kHz면 subcarrier 간격의 10%다. FFT가 기대한 정수 회전수에서 벗어나 한 bin energy가 이웃으로 새는 **ICI(반송파 간 간섭)**가 생긴다. Preamble과 pilot로 offset·phase를 추정하고 보정하지만 residual error가 남는다.

Timing도 CP 안에서 적절히 잡아야 한다. FFT window가 이전 symbol을 포함하면 CP가 충분해도 ISI가 생길 수 있다. OFDM receiver는 frame detection, timing, frequency correction, CP 제거, FFT, pilot channel estimation, equalization, detection, decoding 순으로 상태를 갱신한다.

## PAPR의 수치 반례

**PAPR(Peak-to-Average Power Ratio)**은 시간 파형 peak power를 평균 power로 나눈 비다. 여러 subcarrier 위상이 우연히 맞으면 진폭이 더해진다. 네 subcarrier가 각 진폭 1로 같은 위상에서 합쳐지면 순간 진폭 4, power는 16이다. 평균 power를 4로 정규화한 단순 경우 PAPR은 4, 즉 6.02 dB다.

Power amplifier가 peak를 감당하지 못해 clipping하면 constellation 왜곡과 대역 밖 방사가 생긴다. Backoff는 선형 영역을 확보하지만 송신 전력 효율을 낮춘다. PAPR 저감 기법은 error, spectrum, 계산 복잡도와 함께 평가한다.

## Sample rate, FFT size와 실제 subcarrier 위치

FFT size N과 sample rate `F_s`가 정해지면 FFT bin 간격은 `F_s/N`이다. N=8, sample rate 1 MHz이면 bin 간격은 125 kHz이고 유효 symbol 시간은 `N/F_s=8 µs`다. 두 식은 같은 `Δf=1/T_u` 관계를 다른 단위로 본다.

모든 FFT bin이 payload subcarrier는 아니다. DC 근처를 비우거나 band edge에 guard를 두고, 일부를 pilot·control에 쓴다. N을 두 배로 늘려도 sample rate와 점유 bandwidth, guard 정책이 어떻게 바뀌는지 모르면 payload가 두 배라고 결론 낼 수 없다.

Receiver가 CP를 제거한 뒤 N개 sample보다 하나 적거나 많은 구간을 FFT에 넣는 것은 단순한 크기 오류를 넘어 symbol timing 계약을 바꾼다. 실제 구현은 sample clock, windowing, overlap과 hardware buffer 경계를 관리한다.

## 두 사용자의 자원 할당 시간표

한 slot에 data 가능한 RE가 700개이고 user A·B가 각각 420·280개를 받는다고 하자. A는 16-QAM 4 bit/RE, code rate 3/4이고 B는 QPSK 2 bit/RE, rate 1/2다.

```text
A information 후보 = 420 × 4 × 3/4 = 1,260 bit
B information 후보 = 280 × 2 × 1/2 =   280 bit
합                  = 1,540 bit/slot
```

A가 높은 modulation을 쓰는 이유는 더 좋은 SINR이라는 scheduler 가정 때문이다. 실제 A의 channel이 오래된 CSI 때문에 나빠져 codeword가 실패하면 1,260 bit를 성공 payload로 세면 안 된다. HARQ 재전송은 이후 slot airtime을 소비한다. Resource allocation 표에는 할당 RE뿐 아니라 MCS, 성공 여부, 재전송과 실제 delivered bit를 붙인다.

한 slot이 0.5 ms라는 별도 가정을 두고 모두 성공하면 gross information 후보 rate는 `1540/0.0005=3.08 Mbit/s`다. 이 숫자는 두 사용자 합이며 application goodput에는 MAC·transport header와 queue 시간이 빠져 있다.


## AI-RAN 자원 연구의 경계

AI scheduler가 CSI·queue를 입력으로 RB와 MCS를 고른다고 하자. Simulation은 14-symbol slot, 정한 mobility와 perfect 또는 noisy CSI, 추론시간 0이라는 가정을 둘 수 있다. 실제 decision이 slot 시작보다 늦으면 정확한 선택도 사용할 수 없다.

보고서는 다음을 분리한다.

- simulation: channel seed, traffic, baseline, training/test split과 추론 지연 모형
- testbed: 실제 waveform, RF front-end, clock, 제한된 방·단말과 측정 반복
- field: 장소·시간·사용자 이동·간섭 변화, 안전 fallback과 규격 준수

AI-RAN 연구의 평균 throughput 개선을 모든 cell의 p99 latency 개선으로 바꾸어 말하지 않는다. 전통 scheduler 기준선, outage·HARQ, control overhead, model update 비용과 deadline miss를 함께 본다.

## 종합 문제와 완전 해설

### 문제 1. Spacing과 유효시간

Δf=60 kHz이면 유효 symbol 시간은?

**해설.** `1/60000≈16.67 µs`다. CP가 더해진 실제 전송 symbol은 더 길다.

### 문제 2. 직교 내적

네 sample에서 k=0 `[1,1,1,1]`과 k=1 `[1,j,-1,-j]`의 합은?

**해설.** `1+j-1-j=0`이다. 정확한 window와 frequency에서 서로의 FFT 관측에 남지 않는다는 작은 예다.

### 문제 3. Grid bit

5 RB×12 subcarrier×14 symbol에서 140 RE overhead, QPSK, rate 1/2이면?

**해설.** Raw 840, data 700 RE다. `700×2×0.5=700 information bit` 후보다.

### 문제 4. CP overhead

유효 12 sample, CP 3 sample이면 CP 비율은?

**해설.** 전체 15 중 3이라 20%다. 유효시간 효율은 80%다.

### 문제 5. CP 실패

CP 4 µs인데 유의미한 지연이 6 µs면?

**해설.** 2 µs가 보호 구간을 넘어 이전 symbol이 유효 FFT 구간에 들어올 수 있어 ISI·ICI가 생긴다.

### 문제 6. Deep fade

Data subcarrier 하나의 SNR이 2 dB이고 이웃은 18 dB라면 평균만 보고 같은 LLR을 줘도 되는가?

**해설.** 안 된다. Channel·noise 추정으로 약한 bin의 신뢰도를 낮추고 FEC·interleaving이 다른 관측과 결합하게 한다.

### 문제 7. PAPR

같은 위상 진폭 1의 subcarrier 네 개가 합쳐지고 평균 power가 4라면 PAPR은?

**해설.** Peak 진폭 4, peak power 16이므로 `16/4=4`, 약 6.02 dB다.

### 문제 8. AI scheduler

Simulation throughput 15% 개선, inference deadline miss 8%라면 현장 15% 개선을 주장할 수 있는가?

**해설.** 없다. 늦은 결정의 fallback 성능, control overhead, field channel과 간섭에서 goodput·outage를 다시 측정해야 한다.

## 공식 출처

- [MIT 6.450 signal space and modulation notes](https://ocw.mit.edu/courses/6-450-principles-of-digital-communication-i-fall-2009/pages/lecture-notes/)
- [3GPP specifications portal](https://www.3gpp.org/specifications-technologies/specifications-by-series)
- [3GPP TS 38.211 공식 archive](https://www.3gpp.org/ftp/specs/archive/38_series/38.211/)
- [AI-RAN Alliance Vision and Mission White Paper](https://ai-ran.org/wp-content/uploads/2024/12/AI-RAN_Alliance_Whitepaper.pdf)

[← 이전: channel과 noise](05-channel-noise-and-capacity.md) · [다음: antenna·MIMO·beamforming →](07-antennas-mimo-and-beamforming.md)
