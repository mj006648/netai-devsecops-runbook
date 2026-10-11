# 02. 전력·dB·링크 버짓

[이 책 목차](README.md)

[← 이전](01-waves-frequency-and-spectrum.md) · [다음 →](03-sampling-iq-and-radio-chain.md)

## 전력과 단위

전력은 단위 시간에 전달되는 energy 비율이며 단위는 W다.
무선 수신 전력은 작아 mW와 dBm을 많이 쓴다.

## dB 비율표

| 비율 | dB |
|---:|---:|
| 1배 | 0 |
| 2배 | 약 +3 |
| 10배 | +10 |
| 1/2 | 약 -3 |
| 1/10 | -10 |
| 100배 | +20 |

전력비의 정확한 식은 `10log10(P2/P1)`이다.
dB는 기준 없는 절대 전력이 아니라 비율이다.

## dBm

dBm은 1mW를 기준으로 한 절대 전력이다.

| dBm | 전력 |
|---:|---:|
| 0 | 1mW |
| 10 | 10mW |
| 20 | 100mW |
| 30 | 1W |
| -10 | 0.1mW |

두 20dBm 송신기의 전력을 더하면 40dBm이 아니다.
100mW+100mW=200mW, 약 23dBm이다.

## link budget

```mermaid
flowchart LR
    T[TX 20dBm] -->|cable -2dB| A1[antenna +5dBi]
    A1 -->|path -80dB| A2[antenna +2dBi]
    A2 -->|cable -1dB| R[RX -56dBm]
```

```text
20 - 2 + 5 - 80 + 2 - 1 = -56dBm
```

dBi는 이상적인 등방성 안테나 대비 특정 방향 gain이다.
안테나는 energy를 만들지 않고 방향별 분포를 바꾼다.

## EIRP

송신 출력에서 송신 cable loss를 빼고 antenna gain을 더한다.
위 예의 EIRP는 `20-2+5=23dBm`이다.
실제 규제 판단은 지역·band·장치 조건의 공식 규정을 따른다.

## margin

필요 수신 전력이 -70dBm이면 margin은 `-56-(-70)=14dB`다.
이는 단순 budget 여유다.
fading, 간섭, 구현 오차가 시간과 위치에 따라 바뀐다.
14dB가 연결을 보장하지 않는다.

## FSPL

FSPL은 장애물과 반사가 없는 자유공간 spreading loss 모형이다.

```text
FSPL(dB) ≈ 32.44 + 20log10(d_km) + 20log10(f_MHz)
```

2.4GHz, 0.1km:

```text
32.44 + 20log10(0.1) + 20log10(2400)
≈ 32.44 - 20 + 67.60
≈ 80.04dB
```

단위가 km와 MHz일 때의 상수다.
m와 GHz를 그대로 넣으면 틀린다.
far-field 자유공간 조건이며 벽·비·회절·multipath 측정값이 아니다.

## 거리 두 배

같은 주파수에서 거리를 두 배로 하면 FSPL은 `20log10(2)≈6dB` 증가한다.
100m에서 80dB였다면 200m 자유공간 모형은 약 86dB다.
실내에서는 반사와 차폐 때문에 정확히 6dB가 아닐 수 있다.

## 주체와 상태

| 주체 | 입력 | 중간 상태 | 결과 |
|---|---|---|---|
| transmitter | digital sample | gain·PA | RF 출력 |
| cable | RF | insertion loss | antenna 입력 |
| antenna | RF | 방향 pattern | 방사 field |
| channel | field | path·fading | 수신 field |
| receiver | field | noise figure·filter | detector sample |

## SNR과 RSSI

RSSI는 받은 총 power의 구현 지표일 수 있다.
SNR은 원하는 signal과 noise의 비율이다.
signal -60dBm, noise -90dBm이면 SNR 30dB다.
interference가 -62dBm이면 RSSI는 강해 보여도 decode가 어려울 수 있다.

## 합산 예

서로 독립적인 -90dBm noise source 두 개의 power를 더한다.
각각 1pW라면 합은 2pW다.
따라서 약 -87dBm으로 3dB 증가한다.
dBm 숫자를 산술로 더하지 않고 linear power로 합친다.

## 관측 경계

link budget은 계획값이다.
실제 cable loss와 antenna pattern은 주파수에 따라 다르다.
receiver sensitivity는 modulation, coding, bandwidth, error 기준에 따라 다르다.
RF 모형값은 현장 측정이 아니다.

## 반례

출력을 높여도 receiver front-end가 포화되면 나빠질 수 있다.
antenna gain이 높아도 방향이 틀리면 약하다.
FSPL이 낮아도 같은 channel 간섭이 강하면 실패한다.
대역폭을 넓히면 noise power도 늘 수 있다.

## 문제

## sensitivity가 만들어지는 과정

receiver sensitivity는 안테나가 감지할 수 있는 절대 최솟값 하나가 아니다.
선택한 bandwidth가 noise power를 정하고, receiver noise figure가 내부 noise를 더한다.
modulation과 code rate가 필요한 SINR을 정하고, 목표 packet error rate가 합격선을 정한다.
설계자는 이 조건에서 필요한 입력 power를 sensitivity로 기록한다.
같은 radio라도 좁은 bandwidth와 강한 FEC에서는 더 약한 signal을 복호할 수 있다.
반대로 높은 MCS에서는 더 강한 signal·낮은 interference가 필요하다.

1. 100mW는 몇 dBm인가?
2. 15dBm, cable -1dB, antenna +4dBi의 EIRP는?
3. 수신 -65dBm, 필요 -72dBm의 margin은?

## 해설

1. 1mW의 100배이므로 20dBm이다.
2. `15-1+4=18dBm`이다.
3. `-65-(-72)=7dB`다.

## 공식 출처

- [MIT 6.450 wireless notes](https://ocw.mit.edu/courses/6-450-principles-of-digital-communications-i-fall-2006/pages/lecture-notes/)
- [FCC RF resources](https://www.fcc.gov/engineering-technology)

[← 이전](01-waves-frequency-and-spectrum.md) · [다음 →](03-sampling-iq-and-radio-chain.md)
