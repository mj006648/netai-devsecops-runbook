# 02. 전력·dB·링크 버짓

## 전력이 실제로 존재하는 위치부터 찾는다

**전력**은 단위 시간에 전달되는 에너지 비율이며 단위는 watt다. 송신기의 power amplifier 출력, cable을 지나는 RF, 안테나 급전점, 공간을 지나 수신 안테나에 들어온 신호는 모두 전력으로 표현할 수 있지만 측정 위치가 다르다. “송신 전력 100 mW”와 “수신 전력 100 mW”는 같은 숫자여도 전혀 다른 지점이다.

UE baseband가 만든 I/Q sample은 DAC와 mixer를 지나 작은 RF 전압이 된다. power amplifier가 이를 키우고, cable·connector를 지나 안테나에 공급한다. 안테나는 에너지를 새로 만들지 않고 방향별 방사 패턴으로 분포시킨다. 공간에서는 거리 확산, 벽 흡수, 회절, 반사로 특정 수신 안테나에 결합되는 전력이 줄어든다.

| 위치 | 물리 대상 | 담당 주체 | 다음 단계 |
|---|---|---|---|
| PA 출력 | RF 전압·전류 | 송신 radio | cable |
| antenna 입력 | cable 손실 뒤 RF | 송신 antenna | 공간 field |
| receiver 입력 | 수신 antenna가 얻은 RF | LNA | filter·mixer |
| ADC 입력 | 낮춰진 analog I/Q | ADC | digital sample |

## dB와 dBm을 계산 도구로 이해한다

**dB**는 두 전력의 비율을 로그로 나타낸 값이다. `G_dB=10log10(P2/P1)`이다. 10배는 +10 dB, 100배는 +20 dB, 절반은 약 -3 dB다. 비율이므로 기준 없이 “3 dB의 절대 전력”이라고 말하지 않는다.

**dBm**은 1 mW를 기준으로 한 절대 전력이다. `P_dBm=10log10(P_mW/1mW)`다. 0 dBm=1 mW, 20 dBm=100 mW다. -60 dBm은 `10^(-60/10) mW=10^-6 mW=10^-9 W`, 즉 1 nW다.

두 20 dBm 신호를 더할 때 dBm 숫자를 더하면 안 된다. 각각 100 mW이므로 합은 200 mW다. `10log10(200)=약 23 dBm`이다. 같은 전력 두 개 합은 +3 dB가 된다.

## link budget은 위치별 이득과 손실 장부다

**링크 버짓**은 송신기에서 수신기까지 각 구간의 이득과 손실을 dB로 더하고 빼는 장부다. 입력은 송신 출력, cable loss, antenna gain, path loss다. 결과는 예상 수신 전력이다.

송신기 20 dBm, 송신 cable -2 dB, 송신 antenna +5 dBi, path -80 dB, 수신 antenna +2 dBi, 수신 cable -1 dB라면 다음과 같다.

`20-2+5-80+2-1=-56 dBm`

| 단계 | 누적 전력 |
|---|---:|
| PA 출력 | 20 dBm |
| 송신 cable 뒤 | 18 dBm |
| 송신 antenna 방향 등가 | 23 dBm EIRP |
| path 뒤 | -57 dBm |
| 수신 antenna 뒤 | -55 dBm |
| 수신 cable 뒤 | -56 dBm |

**dBi**는 이상적인 등방성 안테나와 비교한 특정 방향 이득이다. 안테나 전체 에너지를 증가시키지 않는다. 한 방향으로 집중하면 다른 방향의 방사는 줄어든다. antenna 방향이 틀리면 명목 gain이 높아도 링크에는 도움이 되지 않는다.

## FSPL과 실제 channel loss를 구별한다

자유공간 경로 손실은 장애물과 반사가 없는 far-field 확산 모형이다.

`FSPL(dB)=32.44+20log10(d_km)+20log10(f_MHz)`

2 GHz, 0.1 km이면 `32.44-20+20log10(2000)`이다. `20log10(2000)≈66.02`이므로 약 78.46 dB다. 거리를 0.2 km로 두 배 늘리면 `20log10(2)≈6.02 dB`가 추가되어 약 84.48 dB다.

이 계산은 km와 MHz 단위에 맞춘 상수를 썼다. m와 GHz를 그대로 넣으면 단위 오류다. 실내 벽, 지면 반사, 회절, foliage, 비, antenna polarization mismatch는 별도다.

## noise, interference, SNR, SINR

**noise**는 receiver thermal noise와 내부 회로 잡음처럼 원하는 전송과 무관한 성분이다. **interference**는 다른 송신기의 구조 있는 RF가 같은 수신 대역에 들어온 것이다. **SNR**은 원하는 신호와 noise의 비, **SINR**은 noise와 interference를 함께 분모에 둔 비다.

원하는 신호 -56 dBm, noise -96 dBm이면 SNR은 40 dB다. 간섭이 -60 dBm이면 noise보다 간섭이 훨씬 크므로 단순 SNR만 보고 성공을 예측하면 틀린다. 정확한 SINR은 noise와 interference를 linear power로 합친 뒤 신호와 비교한다.

noise -96 dBm은 약 `2.51×10^-10 mW`, interference -60 dBm은 `10^-6 mW`라 후자가 지배한다. 합은 거의 -60 dBm이고 SINR은 약 `-56-(-60)=4 dB`다.

대역폭을 넓히면 같은 noise spectral density에서 총 noise power가 증가한다. 20 MHz에서 40 MHz로 두 배면 이상 모형상 약 +3 dB noise가 늘 수 있다. 더 넓은 대역이 늘 더 높은 SNR을 주는 것은 아니다.

## sensitivity와 margin의 조건

**receiver sensitivity**는 특정 대역폭, modulation, code rate, 목표 error rate에서 필요한 입력 전력 기준이다. 안테나가 물리적으로 감지할 수 있는 영원한 단일 숫자가 아니다. 높은 MCS는 보통 더 높은 SINR을 요구하고, 강한 FEC와 낮은 rate는 더 약한 신호에서 동작할 수 있다.

예상 수신 -56 dBm, 해당 조건 sensitivity -70 dBm이면 margin은 14 dB다. fading 8 dB와 구현 오차 3 dB를 동시에 가정하면 남은 단순 margin은 `14-8-3=3 dB`다. 간섭이 새로 생기면 이 장부 밖의 추가 손실이 된다.

## 두 전체 수치 추적

첫째, 거리 변화다. 100 m에서 path loss 78.5 dB였던 2 GHz 자유공간 모형은 200 m에서 약 84.5 dB다. 다른 항목이 같으면 수신 -56 dBm은 -62 dBm으로 6 dB 낮아진다. sensitivity -70 dBm에 대한 margin은 14 dB에서 8 dB로 준다.

둘째, 대역폭 변화다. 20 MHz noise -96 dBm, signal -66 dBm이면 SNR 30 dB다. 같은 noise density에서 40 MHz로 넓혀 noise가 -93 dBm이 되고 signal power가 같다고 단순 가정하면 SNR은 27 dB다. 대신 더 많은 subcarrier·resource로 총 rate가 늘 여지는 있다. rate와 reliability를 같이 본다.

## AI-RAN 모델 평가와 링크 버짓의 관계

AI 모델이 beam, MCS, power를 추천해도 입력 RSSI·SINR의 측정 위치와 대역폭을 알아야 한다. simulation에서 path loss와 fading 분포를 만든 결과는 실제 도시·실내 환경 전체 보장이 아니다. 2024 multi-task learning 연구의 네 simulation task와 partial federation, negative transfer 조건은 [원문](https://arxiv.org/abs/2404.15197)의 실험 경계 안에서 읽는다.

## 시간에 따라 변하는 fading 추적

평균 수신 -66 dBm, sensitivity -75 dBm이면 평균 margin은 9 dB다. 사람이 지나갈 때 20 ms 동안 12 dB deep fade가 생기면 순간 수신은 -78 dBm으로 기준보다 3 dB 낮다.

| 시각 | fading | 수신 | margin |
|---:|---:|---:|---:|
| 0 ms | 0 dB | -66 dBm | 9 dB |
| 10 ms | -6 dB | -72 dBm | 3 dB |
| 20 ms | -12 dB | -78 dBm | -3 dB |
| 40 ms | -2 dB | -68 dBm | 7 dB |

평균 RSSI만 보면 짧은 packet 실패를 놓친다. FEC, HARQ, antenna diversity는 서로 다른 시간·공간 정보를 쓰며 임의로 긴 fade의 성공을 보장하지 않는다.

## 추가 문제와 완전 해설

### 1. 50 mW는 몇 dBm인가?
`10log10(50)≈16.99 dBm`, 약 17 dBm이다.

### 2. -70 dBm 신호와 -90 dBm noise의 SNR은?
20 dB다. 같은 측정 대역이라는 조건이 필요하다.

### 3. 3개의 같은 -90 dBm noise를 합치면?
각 1 pW이므로 3 pW다. `10log10(3)≈4.77 dB` 증가해 약 -85.2 dBm이다.

### 4. 2 GHz에서 거리를 네 배로 하면 FSPL 증가는?
`20log10(4)=약12.04 dB`다. 자유공간 조건의 값이다.

### 5. margin 10 dB면 연결이 보장되는가?
아니다. fading·간섭·방향·구현 오차와 sensitivity 조건이 바뀔 수 있다.

[이 책 목차](README.md)

[← 이전](01-waves-frequency-and-spectrum.md) · [다음 →](03-sampling-iq-and-radio-chain.md)

## 핵심 계산 복습: 전력과 단위

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
