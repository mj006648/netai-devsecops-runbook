# 06. OFDM·시간·주파수·자원

## 넓은 대역 전송을 여러 좁은 subcarrier로 나누는 이유

넓은 대역의 단일 carrier에서 짧고 빠른 symbol을 보내면 multipath의 지연된 복사본이 다음 symbol과 쉽게 겹치고, 주파수에 따라 달라지는 channel을 긴 equalizer로 처리해야 할 수 있다. **OFDM(직교 주파수 분할 다중화)**은 대역을 서로 직교하는 여러 좁은 **subcarrier(부반송파)**로 나누고 각 subcarrier에는 더 긴 symbol을 보낸다. 각 좁은 대역 안에서는 channel이 거의 flat하다고 보고 subcarrier별 복소 곱으로 보정할 수 있기 때문에 필요하다.

**직교성**은 한 유효 OFDM symbol 구간에서 서로 다른 subcarrier를 내적하면 0이 되어 분리되는 성질이다. Subcarrier가 단지 떨어져 있다는 뜻이 아니다. 간격 `Δf`와 유효 symbol 시간 `T_u`가 `Δf=1/T_u`를 만족하고 timing과 주파수가 맞아야 한다. Spectrum이 겹쳐 보여도 FFT bin에서 구별되는 이유다.

```text
Δf=15 kHz → Tu≈66.67 µs
Δf=30 kHz → Tu≈33.33 µs
Δf=60 kHz → Tu≈16.67 µs
```

실제 전송 symbol에는 뒤에서 설명할 cyclic prefix 시간이 더해진다.

### 네 복소 sample로 직교를 확인한다

복소수 `e^{jθ}=cosθ+j sinθ`는 크기 1인 회전을 나타낸다. 4-point OFDM에서 subcarrier `k`의 `n`번째 sample은 `e^{j2πkn/4}` 꼴이다. `k=0`은 `[1,1,1,1]`, `k=1`은 `[1,j,-1,-j]`다.

한 파와 다른 파의 **켤레복소수**를 곱해 더하는 내적을 본다. 켤레복소수는 `a+jb`의 허수 부호를 바꾼 `a-jb`이며, 성분의 위상 차이를 비교하는 데 필요하다. `k=0`과 `k=1`의 합은 `1+j-1-j=0`이므로 두 파는 이 구간에서 직교한다.

## IFFT로 합성하고 FFT로 분리한다

송신기는 각 subcarrier에 QAM symbol `X[k]`를 놓는다. **IFFT(역 고속 푸리에 변환)**는 이 주파수 bin 목록을 한 묶음의 시간 sample `x[n]`으로 합성한다. DAC와 RF chain은 그 시간 파형을 보낸다. 수신기는 symbol 경계를 맞추고 CP를 제거한 뒤 **FFT(고속 푸리에 변환)**로 subcarrier별 관측 `Y[k]`를 되찾는다. FFT는 channel과 noise를 없애지 않으므로 pilot 기반 channel 추정과 equalization이 뒤따른다.

```mermaid
flowchart LR
    S[subcarrier별 QAM symbol] --> IFFT[IFFT: 시간 sample 합성]
    IFFT --> CP[CP 붙이기]
    CP --> CH[channel]
    CH --> RCP[CP 제거]
    RCP --> FFT[FFT: bin별 분리]
    FFT --> EQ[pilot 기반 equalization]
```

| 단계 | 입력 | 주체·상태 | 출력 |
|---|---|---|---|
| mapping | coded bit | modulation | subcarrier I/Q `X[k]` |
| resource mapping | data·pilot | grid 위치 | grid |
| IFFT | grid 한 열 | phase 합 | 시간 sample `x[n]` |
| CP 삽입 | `x[n]` 끝부분 | 앞에 복사 | CP+`x[n]` |
| channel | 시간 파형 | 지연 경로 합 | 수신 sample |
| CP 제거·FFT | 수신 유효 구간 | 직교 분해 | subcarrier 관측 `Y[k]` |
| equalization | `Y[k]`, pilot | channel estimate `H[k]` | `X[k]` 추정 |

8-point toy에서 bin 1과 3에 symbol을 두면 IFFT가 8개 시간 sample을 만든다. 이상 channel과 정확한 동기에서는 FFT가 다시 bin 1과 3을 분리한다. IFFT는 여덟 radio를 만드는 것이 아니라 하나의 합성 시간 파형을 계산한다.

4-point에서 주파수 bin을 `X=[1,1,0,0]`으로 두고 IFFT 정규화를 `1/N`으로 하면 다음과 같다.

| n | k=0 성분 | k=1 성분 | `x[n]=(합)/4` |
|---:|---|---|---|
| 0 | 1 | 1 | 0.5 |
| 1 | 1 | j | 0.25+j0.25 |
| 2 | 1 | -1 | 0 |
| 3 | 1 | -j | 0.25-j0.25 |

이 네 복소 sample이 DAC와 RF chain을 거쳐 시간 파형이 된다. 이상 channel과 정확한 timing에서 FFT하면 bin 0과 1에서 다시 1을 얻는다.

## Cyclic prefix가 지연 경로를 다루는 조건

**Cyclic prefix(CP, 순환 접두부)**는 유효 OFDM symbol의 끝부분을 앞에 복사한 guard 구간이다. 최대 의미 있는 channel 지연이 CP보다 짧고 FFT window가 맞으면 이전 symbol의 꼬리가 CP 안에 머문다. 이 조건은 선형 convolution을 유효 구간에서 circular convolution처럼 만들어 FFT가 subcarrier별 곱셈으로 다룰 수 있게 한다. CP가 channel 자체를 없애는 것은 아니다.

```text
유효 sample 8개: [a b c d e f g h]
CP 길이 2:       [g h | a b c d e f g h]
```

전체 10 sample 가운데 새 유효 sample은 8개이므로 CP overhead는 `2/10=20%`다. CP를 길게 하면 더 긴 지연을 보호하지만 효율은 낮아진다.

유효 sample `x=[1,2,3,4]`, CP 길이 1이면 `[4|1,2,3,4]`를 전송한다. Channel을 현재 sample과 한 sample 지연 복사본의 합 `h=[1,0.5]`라고 하자.

| 유효 위치 | 현재 | 직전(CP 포함) | 관측 |
|---:|---:|---:|---:|
| 0 | 1 | 4 | 3 |
| 1 | 2 | 1 | 2.5 |
| 2 | 3 | 2 | 4 |
| 3 | 4 | 3 | 5.5 |

첫 위치가 이전 OFDM symbol의 알 수 없는 꼬리 대신 현재 symbol 끝 4를 사용한다. 지연이 CP 1 sample보다 길면 이전 symbol 성분이 유효 구간에 들어와 이 구조가 깨진다.

시간 단위의 별도 예에서 유효 symbol이 66.67 µs이고 CP가 4.7 µs이면 유효 시간 비율은 `66.67/(66.67+4.7)≈93.4%`다.

| 경로 | 지연 | CP 4.7 µs 안? | 결과 |
|---|---:|---|---|
| 직접 | 0 | 예 | 기준 |
| 반사 A | 2 µs | 예 | subcarrier별 `H[k]`로 보정 |
| 반사 B | 7 µs | 아니오 | 이전·다음 symbol 침범 가능 |

두 예제는 조건이 다르다. 첫 예제는 sample 단위로 circular convolution을 보이고, 둘째는 실제 시간에서 delay spread와 효율의 trade-off를 보인다.

## Resource grid와 numerology로 시간·주파수 자원을 계산한다

![OFDM 자원격자](assets/ofdm-grid.svg)

**Resource grid(자원 격자)**는 세로축 subcarrier, 가로축 OFDM symbol인 논리 표다. **Resource element(RE, 자원 요소)**는 그 교차점 한 칸으로 data, pilot, control, guard 가운데 한 역할을 맡는다. **Resource block(RB, 자원 블록)**은 NR에서 주파수 방향 12 subcarrier를 묶어 스케줄링하기 위한 단위다. 표준마다 resource unit·block의 이름과 크기가 다르므로 아래 toy grid를 실제 Wi-Fi나 5G 배치로 읽지 않는다.

### 8-subcarrier toy grid

| time\\subcarrier | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---:|---|---|---|---|---|---|---|---|
| 0 | guard | data | data | pilot | data | data | data | guard |
| 1 | guard | data | data | pilot | data | data | data | guard |
| 2 | guard | data | data | pilot | data | data | data | guard |
| 3 | guard | data | data | pilot | data | data | data | guard |

한 time에 data subcarrier는 5개다. QPSK는 subcarrier당 2 coded bit이므로 OFDM symbol당 10 coded bit, 4개 time이면 40 coded bit다. Coding rate 1/2이면 이상적 information bit는 20 bit다. Guard와 pilot은 payload를 직접 싣지 않지만 spectrum edge 보호와 channel 추정에 필요하다.

### NR 교육 조건의 전체 계산

3GPP NR의 세부 배치는 TS 38.211 버전별로 확인한다. 여기서는 normal CP 한 slot이 14 OFDM symbol이고 RB당 12 subcarrier라는 교육 조건을 쓴다.

5 RB의 raw RE는 `5×12×14=840`이다. Pilot·control 140 RE를 빼면 data RE는 700이다. QPSK 2 coded bit/RE, code rate 1/2이면 `700×2×0.5=700 information bit` 후보다. 실제 transport block은 CRC, rate matching, reserved RE와 규격 절차 때문에 달라진다.

별도 10 RB 조건에서는 raw RE가 1,680개다. Pilot·control 280 RE를 빼면 data RE는 1,400개이고, 16-QAM 4 coded bit/RE와 code rate 3/4를 쓰면 `1400×4×0.75=4200 bit`, 약 525 byte 후보다. 두 독립 layer가 가능하면 이상 후보는 두 배지만 channel rank·power·overhead 조건이 필요하다. 두 계산은 RB 수와 modulation 조건이 다른 예제다.

**Numerology(뉴머롤로지)**는 subcarrier spacing과 symbol·slot 시간 구조를 함께 선택하는 체계다. NR의 기본 관계는 `Δf=15×2^μ kHz`로 읽을 수 있다. `μ=0,1,2`는 각각 15, 30, 60 kHz이고 유효 symbol 시간은 대략 66.67, 33.33, 16.67 µs다. 실제 CP와 slot 경계는 규격 표를 따른다.

Spacing이 커지면 symbol이 짧아져 빠른 시간 변화와 큰 Doppler에 유리할 수 있지만, 같은 절대 delay가 symbol에서 차지하는 비율이 커질 수 있다. 좁은 spacing은 symbol이 길어 multipath의 상대 영향이 줄 수 있으나 slot 시간과 phase noise도 함께 봐야 한다. 하나의 numerology가 모든 delay·속도·carrier에 최적이지 않다.

FFT size `N`과 sample rate `F_s`가 정해지면 bin 간격은 `F_s/N`이고 유효 symbol 시간은 `N/F_s`다. `N=8`, `F_s=1 MHz`이면 bin 간격은 125 kHz, 유효 시간은 8 µs로 `Δf=1/T_u`와 같다. 모든 bin이 payload는 아니다. DC 근처, band edge guard, pilot·control을 제외해야 하므로 N을 두 배로 늘렸다고 payload가 자동으로 두 배가 되지 않는다.

## Pilot, offset과 ICI가 직교성을 지키는 범위

**Pilot(기준 신호)**은 송수신자가 값을 아는 symbol이며 channel 추정에 필요하다. 보낸 값이 `x`, 받은 값이 `y`이면 `h≈y/x`로 channel을 추정한다. `x=1+j0`, `y=0.8+j0.2`라면 `h≈0.8+j0.2`다. Pilot 사이에서 channel이 너무 빨리 바뀌면 interpolation이 틀릴 수 있다.

송수신 oscillator 차이와 Doppler가 만드는 carrier frequency offset이 크면 FFT가 기대한 정수 회전수에서 벗어난다. 한 bin의 energy가 이웃으로 새는 **ICI(반송파 간 간섭)**가 생긴다. `Δf=15 kHz`에서 offset 1.5 kHz는 간격의 10%다. Preamble과 pilot로 offset·phase를 추정하고 보정하지만 residual error가 남을 수 있다.

Timing도 CP 안에서 맞아야 한다. FFT window가 이전 symbol을 포함하면 CP가 충분해도 ISI가 생길 수 있다. Receiver는 frame detection, timing, frequency correction, CP 제거, FFT, pilot channel estimation, equalization, detection, decoding 순으로 상태를 갱신한다. N개보다 하나 적거나 많은 sample을 FFT에 넣는 일도 symbol timing 계약을 바꾸므로 sample clock, windowing, overlap과 hardware buffer 경계를 관리한다.

## PAPR가 전력 효율을 제한한다

**PAPR(Peak-to-Average Power Ratio, 첨두 대 평균 전력비)**은 시간 파형의 peak power를 평균 power로 나눈 값이다. 여러 subcarrier가 같은 위상으로 더해지는 순간 peak가 커지므로 PA의 선형 범위와 backoff를 정할 때 필요하다.

진폭 1인 네 subcarrier가 같은 위상에서 합쳐지면 순간 진폭은 4, peak power는 16이다. 평균 power를 4로 정규화한 단순 조건에서 PAPR은 `16/4=4`, 즉 약 6.02 dB다. PA가 peak를 감당하지 못하면 clipping, constellation 왜곡과 대역 밖 spectral regrowth가 생긴다. Backoff는 선형성을 확보하지만 송신 전력 효율을 낮춘다. PAPR 저감 기법은 error, spectrum과 계산 복잡도를 함께 평가한다.

Subcarrier가 많다고 처리량이나 전력 효율이 자동으로 좋아지지 않는다. FFT size, CP, pilot, guard, sampling 조건이 함께 바뀌며 OFDM은 narrowband interference도 없애지 않는다.

## 두 사용자의 자원 할당과 실제 전달량

한 slot에 data 가능한 RE가 700개이고 user A·B가 각각 420·280개를 받는다고 하자. A는 16-QAM 4 bit/RE, code rate 3/4이고 B는 QPSK 2 bit/RE, rate 1/2다.

```text
A information 후보 = 420 × 4 × 3/4 = 1,260 bit
B information 후보 = 280 × 2 × 1/2 =   280 bit
합                  = 1,540 bit/slot
```

A가 높은 modulation을 쓰는 이유는 더 좋은 SINR이라는 scheduler 가정 때문이다. 오래된 CSI 때문에 실제 channel이 나빠져 codeword가 실패하면 1,260 bit를 성공 payload로 세면 안 된다. HARQ 재전송은 이후 slot airtime을 소비한다. 할당표에는 RE뿐 아니라 MCS, 성공 여부, 재전송과 delivered bit를 붙인다.

한 slot이 0.5 ms라는 별도 가정에서 모두 성공하면 gross information 후보 rate는 `1540/0.0005=3.08 Mbit/s`다. 이 수치는 두 사용자 합이며 application goodput에는 MAC·transport header와 queue 시간이 빠져 있다.

## AI-RAN 자원 연구에서 주장할 수 있는 범위

AI scheduler가 CSI·queue를 입력으로 RB와 MCS를 고를 때 CSI가 오래됐거나 pilot 오염이 있으면 계산상 높은 rate 배치가 HARQ 실패를 만들 수 있다. 정확한 선택도 slot 시작보다 늦으면 사용할 수 없다.

보고서는 증거 단계를 구분한다.

- simulation: grid·channel seed·traffic·baseline·training/test split과 추론 지연 모형
- testbed: 실제 waveform·RF front-end·clock·제한된 방과 단말·측정 반복
- field: 장소·시간·사용자 이동·간섭 변화·규격 준수·안전 fallback

Simulation의 평균 throughput 개선을 모든 cell의 p99 latency 개선으로 확대하지 않는다. 전통 scheduler 기준선, outage·HARQ, control overhead, model update 비용과 deadline miss를 함께 본다.

## 종합 문제와 완전 해설

### 문제 1. Spacing과 유효시간

`Δf=60 kHz`이면 유효 symbol 시간은?

**해설.** `1/60000≈16.67 µs`다. CP가 더해진 실제 전송 symbol은 더 길다.

### 문제 2. 직교 내적

네 sample에서 `k=0` `[1,1,1,1]`과 `k=1` `[1,j,-1,-j]`의 합은?

**해설.** `1+j-1-j=0`이다. 정확한 window와 frequency에서 서로의 FFT 관측에 남지 않는다.

### 문제 3. Grid bit

5 RB×12 subcarrier×14 symbol에서 140 RE overhead, QPSK, rate 1/2이면?

**해설.** Raw 840, data 700 RE이고 `700×2×0.5=700 information bit` 후보다.

### 문제 4. CP overhead

유효 12 sample, CP 3 sample이면 CP 비율은?

**해설.** 전체 15 중 3이라 20%이고 유효시간 효율은 80%다.

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
