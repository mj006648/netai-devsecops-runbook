# 02. 전력·dB·링크 버짓

## 전력이 실제로 존재하는 위치

**전력(power)**은 단위 시간에 전달되는 에너지의 비율이며 단위는 watt(W)다. 송신기의 전력 증폭기 출력, cable을 지나는 고주파 신호, 안테나 급전점, 공간을 지나 수신 안테나에 들어온 신호는 모두 전력으로 표현할 수 있지만 측정 위치가 다르다. “송신 전력 100 mW”와 “수신 전력 100 mW”는 같은 숫자여도 전혀 다른 지점을 가리킨다.

단말의 베이스밴드가 만든 **I/Q(In-phase/Quadrature, 동상/직교 성분)** 표본은 **DAC(Digital-to-Analog Converter, 디지털-아날로그 변환기)**와 믹서를 지나 작은 **RF(Radio Frequency, 무선 주파수)** 전압이 된다. **PA(Power Amplifier, 전력 증폭기)**가 이를 키우고 cable과 connector를 지나 안테나에 공급한다. 안테나는 에너지를 새로 만들지 않고 방향별 방사 패턴으로 분포시킨다. 공간에서는 거리 확산, 벽 흡수, 회절, 반사 때문에 특정 수신 안테나에 결합되는 전력이 줄어든다.

| 위치 | 물리 대상 | 담당 주체 | 다음 단계 |
|---|---|---|---|
| PA 출력 | RF 전압·전류 | 송신 radio | cable |
| antenna 입력 | cable 손실 뒤 RF | 송신 antenna | 공간 field |
| receiver 입력 | 수신 antenna가 얻은 RF | LNA | filter·mixer |
| ADC 입력 | 낮춰진 analog I/Q | ADC | digital sample |

여기서 **LNA(Low-Noise Amplifier, 저잡음 증폭기)**는 수신 신호에 잡음을 적게 더하면서 증폭하고, **ADC(Analog-to-Digital Converter, 아날로그-디지털 변환기)**는 연속 전압을 디지털 표본으로 바꾼다. 같은 “전력”이라도 어느 표의 위치에서 측정했는지를 빠뜨리면 링크 계산을 이어 갈 수 없다.

## W·mW·dB·dBm

작은 수신 전력을 W나 mW로만 쓰면 0이 많은 숫자가 된다. 무선에서는 전력비를 더하고 빼기 쉽게 로그 단위를 사용한다.

**dB(decibel, 데시벨)**는 두 전력의 비율을 로그로 나타낸 값이다.

`G_dB=10log10(P2/P1)`

| 전력비 | dB |
|---:|---:|
| 1배 | 0 dB |
| 2배 | 약 +3 dB |
| 10배 | +10 dB |
| 100배 | +20 dB |
| 1/2 | 약 -3 dB |
| 1/10 | -10 dB |

dB는 비율이므로 기준 없이 “3 dB의 절대 전력”이라고 말하지 않는다.

**dBm(decibel-milliwatt, 1 mW 기준 데시벨 전력)**은 1 mW를 기준으로 한 절대 전력이다.

`P_dBm=10log10(P_mW/1mW)`

| dBm | 전력 |
|---:|---:|
| -10 dBm | 0.1 mW |
| 0 dBm | 1 mW |
| 10 dBm | 10 mW |
| 20 dBm | 100 mW |
| 30 dBm | 1 W |

-60 dBm은 `10^(-60/10) mW=10^-6 mW=10^-9 W`, 즉 1 nW다. 두 20 dBm 신호를 더할 때 dBm 숫자를 더해서 40 dBm이라고 하면 안 된다. 각각 100 mW이므로 합은 200 mW이고 `10log10(200)≈23 dBm`이다. 같은 전력 두 개의 합은 원래 하나보다 약 +3 dB다. 서로 독립적인 -90 dBm 잡음원 두 개도 각각 1 pW이므로 합은 2 pW, 약 -87 dBm이다. 로그값을 합하기 전에 선형 전력으로 바꿔야 한다.

## 링크 버짓과 EIRP

**링크 버짓(link budget)**은 송신기에서 수신기까지 각 구간의 이득과 손실을 dB로 더하고 빼는 장부다. 입력은 송신 출력, cable loss, antenna gain, path loss이고 결과는 예상 수신 전력이다.

```mermaid
flowchart LR
    T[TX 20dBm] -->|cable -2dB| A1[antenna +5dBi]
    A1 -->|path -80dB| A2[antenna +2dBi]
    A2 -->|cable -1dB| R[RX -56dBm]
```

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

**dBi(decibel-isotropic, 등방성 안테나 대비 데시벨 이득)**는 이상적인 등방성 안테나와 비교한 특정 방향의 이득이다. 안테나가 전체 에너지를 증가시키는 값이 아니다. 한 방향으로 집중하면 다른 방향의 방사는 줄어들며, 안테나 방향이 틀리면 명목 gain이 높아도 링크에 도움이 되지 않는다.

**EIRP(Equivalent Isotropically Radiated Power, 등가 등방 방사 전력)**는 실제 안테나가 특정 방향으로 방사하는 효과를 등방성 안테나의 출력으로 환산한 값이다. 위 예에서는 송신 출력에서 송신 cable loss를 빼고 antenna gain을 더한 `20-2+5=23 dBm`이다. 실제 규제 판단은 지역, 주파수 대역, 장치 조건에 해당하는 공식 규정을 따라야 한다.

| 주체 | 입력 | 중간 상태 | 결과 |
|---|---|---|---|
| transmitter | digital sample | gain·PA | RF 출력 |
| cable | RF | insertion loss | antenna 입력 |
| antenna | RF | 방향 pattern | 방사 field |
| channel | field | path·fading | 수신 field |
| receiver | field | noise figure·filter | detector sample |

## 거리·FSPL·실제 채널 손실

**FSPL(Free-Space Path Loss, 자유공간 경로 손실)**은 장애물과 반사가 없는 원거리장(far-field)에서 전파가 퍼지는 손실 모형이다.

`FSPL(dB)=32.44+20log10(d_km)+20log10(f_MHz)`

2 GHz, 0.1 km이면 `32.44-20+20log10(2000)`이다. `20log10(2000)≈66.02`이므로 약 78.46 dB다. 거리를 0.2 km로 두 배 늘리면 `20log10(2)≈6.02 dB`가 추가되어 약 84.48 dB다.

원문의 별도 2.4 GHz 예에서는 0.1 km일 때 다음과 같다.

```text
32.44 + 20log10(0.1) + 20log10(2400)
≈ 32.44 - 20 + 67.60
≈ 80.04 dB
```

같은 주파수에서 거리를 두 배로 하면 자유공간 모형의 손실은 약 6 dB 증가한다. 따라서 2 GHz의 100 m 손실 78.5 dB는 200 m에서 약 84.5 dB가 되고, 2.4 GHz의 100 m 손실 80 dB는 200 m에서 약 86 dB가 된다. 두 예의 시작값이 다른 이유는 주파수가 각각 2 GHz와 2.4 GHz이기 때문이다.

FSPL 식의 상수 32.44는 거리를 km, 주파수를 MHz로 넣을 때 맞는다. m와 GHz를 그대로 대입하면 단위 오류다. 또한 실내 벽, 지면 반사, 회절, 나뭇잎, 비, 안테나 편파 불일치는 별도다. 실내에서는 거리 두 배가 정확히 6 dB 증가를 만들지 않을 수 있다.

**페이딩(fading)**은 반사·회절·이동 등으로 수신 전력이 시간과 위치에 따라 변하는 현상이다. 평균 수신 전력만 보면 짧고 깊은 fade를 놓칠 수 있다. 평균 수신 -66 dBm, sensitivity -75 dBm인 링크에 사람이 지나가며 다음 변화가 생겼다고 하자.

| 시각 | fading | 수신 | margin |
|---:|---:|---:|---:|
| 0 ms | 0 dB | -66 dBm | 9 dB |
| 10 ms | -6 dB | -72 dBm | 3 dB |
| 20 ms | -12 dB | -78 dBm | -3 dB |
| 40 ms | -2 dB | -68 dBm | 7 dB |

20 ms 동안 수신 전력이 기준보다 3 dB 낮으므로 그 구간의 패킷은 실패할 수 있다. **FEC(Forward Error Correction, 순방향 오류 정정)**, **HARQ(Hybrid Automatic Repeat reQuest, 오류 정정과 재전송을 결합한 방식)**, 안테나 diversity는 서로 다른 시간·공간 정보를 활용하지만 임의로 긴 fade에서 성공을 보장하지 않는다.

## 잡음·간섭·SNR·SINR

**잡음(noise)**은 수신기의 열잡음과 내부 회로 잡음처럼 원하는 전송과 무관한 성분이다. **간섭(interference)**은 다른 송신기의 구조 있는 RF가 같은 수신 대역에 들어온 것이다. **SNR(Signal-to-Noise Ratio, 신호 대 잡음비)**은 원하는 신호와 잡음의 비다. **SINR(Signal-to-Interference-plus-Noise Ratio, 신호 대 간섭 및 잡음비)**은 잡음과 간섭을 함께 분모에 둔다.

원하는 신호 -56 dBm, 잡음 -96 dBm이면 같은 측정 대역에서 SNR은 `-56-(-96)=40 dB`다. 간섭이 -60 dBm이면 잡음보다 훨씬 크므로 SNR만 보고 성공을 예측하면 틀린다. 정확한 SINR은 잡음과 간섭을 선형 전력으로 합친 뒤 신호와 비교한다. -96 dBm은 약 `2.51×10^-10 mW`, -60 dBm은 `10^-6 mW`이므로 간섭이 지배한다. 합은 거의 -60 dBm이고 SINR은 약 `-56-(-60)=4 dB`다.

**RSSI(Received Signal Strength Indicator, 수신 신호 강도 지표)**는 구현에 따라 수신 대역의 총 전력을 나타낼 수 있다. 원하는 신호 -60 dBm, 잡음 -90 dBm이면 SNR은 30 dB지만, 간섭이 -62 dBm이면 RSSI가 강하게 보여도 복호가 어려울 수 있다. RSSI와 SNR·SINR은 같은 지표가 아니다.

같은 잡음 전력 밀도에서 대역폭을 20 MHz에서 40 MHz로 두 배 넓히면 이상 모형상 총 잡음 전력이 약 +3 dB 늘 수 있다. 20 MHz에서 signal -66 dBm, noise -96 dBm이면 SNR은 30 dB다. signal power가 같다는 단순 조건에서 40 MHz로 넓혀 noise가 -93 dBm이 되면 SNR은 27 dB다. 대신 더 많은 subcarrier와 resource로 총 rate가 늘 여지가 있으므로 전송률과 신뢰성을 함께 본다.

## 수신 감도와 링크 여유

**수신 감도(receiver sensitivity)**는 특정 대역폭, 변조, 부호율(code rate), 목표 오류율에서 복호에 필요한 수신기 입력 전력 기준이다. 안테나가 물리적으로 감지할 수 있는 영원한 단일 최솟값이 아니다.

대역폭은 잡음 전력을 정하고, 수신기 잡음 지수(noise figure)는 내부 잡음을 더한다. 변조와 code rate는 필요한 SINR을 정하며, 목표 패킷 오류율이 합격선을 정한다. 같은 radio라도 좁은 대역폭과 강한 FEC에서는 더 약한 신호를 복호할 수 있고, 높은 **MCS(Modulation and Coding Scheme, 변조 및 부호화 방식)**에서는 더 강한 신호와 낮은 간섭이 필요하다.

예상 수신 -56 dBm, 해당 조건의 sensitivity -70 dBm이면 링크 여유(margin)는 `-56-(-70)=14 dB`다. fading 8 dB와 구현 오차 3 dB를 동시에 가정하면 남은 단순 margin은 `14-8-3=3 dB`다. 간섭이 새로 생기면 이 장부 밖의 추가 저하가 된다. 출력 증가도 언제나 해결책은 아니다. 수신기 전단이 포화되면 오히려 성능이 나빠질 수 있다.

거리 변화까지 이어 보면, 2 GHz 자유공간 모형에서 100 m의 수신 전력이 -56 dBm이었다면 200 m에서는 약 6 dB 낮은 -62 dBm이 된다. sensitivity -70 dBm에 대한 margin은 14 dB에서 8 dB로 줄어든다. 이 결과는 다른 링크 항목이 모두 같다는 조건에서만 성립한다.

## 연구·계획값을 읽는 조건

링크 버짓은 계획값이다. 실제 cable loss와 antenna pattern은 주파수에 따라 다르고, sensitivity는 modulation, coding, bandwidth, 오류 기준에 따라 달라진다. RF 모형값은 현장 측정값이 아니다. antenna gain이 높아도 방향이 틀리면 약하고, FSPL이 낮아도 같은 channel 간섭이 강하면 실패하며, 대역폭을 넓히면 잡음 전력도 늘 수 있다.

**AI-RAN(Artificial Intelligence for Radio Access Network, 무선 접속망에 인공지능을 적용하는 접근)** 모델이 beam, MCS, power를 추천하더라도 입력 RSSI·SINR의 측정 위치와 대역폭을 알아야 한다. simulation에서 path loss와 fading 분포를 만들어 얻은 결과는 실제 도시·실내 환경 전체의 보장이 아니다. 2024 multi-task learning 연구의 네 simulation task, partial federation, negative transfer 조건은 [원문](https://arxiv.org/abs/2404.15197)의 실험 경계 안에서 읽어야 한다.

## 문제와 해설

### 1. 50 mW와 100 mW는 각각 몇 dBm인가?

50 mW는 `10log10(50)≈16.99 dBm`, 즉 약 17 dBm이다. 100 mW는 1 mW의 100배이므로 `10log10(100)=20 dBm`이다.

### 2. -70 dBm 신호와 -90 dBm 잡음의 SNR은 얼마인가?

같은 위치와 측정 대역이라는 조건에서 `-70-(-90)=20 dB`다. 측정 대역이 다르면 두 값을 바로 뺄 수 없다.

### 3. 같은 -90 dBm 잡음원 3개의 전력을 합치면 얼마인가?

각각 1 pW이므로 합은 3 pW다. 같은 전력 세 개를 합치면 `10log10(3)≈4.77 dB` 증가하므로 약 -85.2 dBm이다. dBm 숫자 세 개를 산술로 더하지 않는다.

### 4. 2 GHz에서 거리를 네 배로 하면 FSPL은 얼마나 증가하는가?

주파수가 같고 자유공간 조건이라면 `20log10(4)≈12.04 dB` 증가한다. 벽·반사·회절이 있는 실제 환경의 보편 법칙은 아니다.

### 5. margin이 10 dB이면 연결이 보장되는가?

보장되지 않는다. margin은 명시한 sensitivity 조건과 계획값에 대한 여유다. 시간에 따른 fading, 간섭, 안테나 방향, 구현 오차, 대역폭이나 MCS 변경으로 실제 여유가 줄 수 있다.

### 6. 송신기 15 dBm, cable loss 1 dB, antenna gain 4 dBi의 EIRP는 얼마인가?

`15-1+4=18 dBm`이다. 이는 해당 안테나 방향의 등가 등방 방사 전력이며 실제 허용 여부는 적용 규정을 확인해야 한다.

### 7. 수신 전력 -65 dBm, 필요한 수신 전력 -72 dBm의 margin은 얼마인가?

`-65-(-72)=7 dB`다. 두 값은 같은 수신기 입력 위치와 동일한 bandwidth·modulation·coding·오류 기준에 대응해야 한다.

## 공식 출처

- [MIT 6.450 wireless notes](https://ocw.mit.edu/courses/6-450-principles-of-digital-communications-i-fall-2006/pages/lecture-notes/)
- [FCC RF resources](https://www.fcc.gov/engineering-technology)

[이 책 목차](README.md)

[← 이전](01-waves-frequency-and-spectrum.md) · [다음 →](03-sampling-iq-and-radio-chain.md)
