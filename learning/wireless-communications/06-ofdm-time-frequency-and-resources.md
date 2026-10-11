# 06. OFDM·시간·주파수·자원

[이 책 목차](README.md)

[← 이전: channel과 noise](05-channel-noise-and-capacity.md) · [다음: antenna·MIMO·beamforming →](07-antennas-mimo-and-beamforming.md)

## 왜 여러 작은 subcarrier로 나누는가

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

## 문제

## FFT bin과 실제 subcarrier

수신기는 CP를 버린 뒤 정확히 유효 symbol 길이만큼 sample을 고른다.
FFT의 각 출력 bin은 그 구간에서 특정 회전수를 가진 파형과 얼마나 닮았는지 계산한 결과다.
timing이 한참 밀리면 이전 symbol이 섞이고, carrier offset이 있으면 energy가 이웃 bin으로 샌다.
pilot bin은 receiver가 이 회전·gain 오차를 추정할 기준을 제공한다.
equalizer는 bin마다 추정 channel로 data 관측을 보정한다.
FFT 출력 자체가 곧 bit는 아니며 detector와 decoder가 뒤따른다.

## 한 subcarrier deep fade 배치

8개 중 data subcarrier 1~6을 쓰고 index 3이 deep fade라고 하자.
uncoded이면 index 3의 bit가 집중적으로 틀릴 수 있다.
interleaver가 coded bit를 여러 subcarrier/time에 흩으면 한 codeword에 burst 오류가 분산된다.

| subcarrier | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| SNR | 20 | 18 | 2 | 19 | 17 | 20 dB |

receiver는 pilot/channel estimate로 index 3의 LLR 확신을 낮출 수 있다.
FEC decoder가 다른 강한 관측과 결합한다.
반례로 fade가 너무 넓거나 오래 지속되면 interleaving/FEC 능력을 넘는다.

1. Tu=4µs이면 Δf는?
2. 유효 12 sample, CP 3 sample의 CP overhead는?
3. data subcarrier 6개, 16-QAM, rate 3/4이면 한 OFDM symbol의 information bit 모형은?

## 해설

1. `1/4µs=250kHz`다.
2. 전체 15 중 3이므로 20%다.
3. `6×4×3/4=18bit`다.

## 공식 출처

- [MIT 6.450 signal space and modulation notes](https://ocw.mit.edu/courses/6-450-principles-of-digital-communication-i-fall-2009/pages/lecture-notes/)
- [3GPP specifications portal](https://www.3gpp.org/specifications-technologies/specifications-by-series)

[← 이전: channel과 noise](05-channel-noise-and-capacity.md) · [다음: antenna·MIMO·beamforming →](07-antennas-mimo-and-beamforming.md)
