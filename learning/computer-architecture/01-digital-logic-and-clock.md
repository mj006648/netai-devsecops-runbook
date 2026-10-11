# 01. 디지털 논리와 클록

[← 이전](00-architecture-and-execution-map.md) · [목차](README.md) · [다음 →](02-instructions-registers-and-isa.md)

00장에서는 LOAD와 ADD가 fetch, decode, execute, retire를 지나간다고 설명했다. 이번 장은 그 상자 안을 한 단계 더 연다. 비트가 전압으로 표현되고, 게이트가 비트를 계산하며, 플립플롭이 한 시점의 결과를 다음 시점까지 기억하는 과정을 연결한다. CPU는 “0과 1을 아는 기계”가 아니라 연속적인 전기 신호를 정해진 규칙으로 두 논리 상태처럼 다루는 회로다.

## 1. 전압과 비트는 같은 말이 아니다

**전압(voltage)**은 두 지점 사이의 전기적 위치 에너지 차이다. 회로에서는 도선의 전압 범위를 논리 0과 1로 해석한다. **비트(bit)**는 두 상태 중 하나를 나타내는 정보 단위다. 비트 0이 자연에 별도 물체로 존재하는 것이 아니라, 회로가 어떤 전압 범위를 0으로 해석한다.

교육용 입력 규칙이 0~0.8V를 0, 2.0~3.3V를 1로 본다고 하자. 1.4V는 “0.5라는 비트”가 아니라 입력 규격이 어느 논리값도 보장하지 않는 범위다. 실제 임계값과 전원 전압은 공정, 회로 계열, 제품 규격에 따라 다르므로 이 숫자를 모든 CPU에 적용하면 안 된다.

출력 회로가 0을 보장하는 최대 전압과 다음 입력 회로가 0으로 인정하는 최대 전압 사이에는 **잡음 여유(noise margin)**가 필요하다. 배선에서 작은 잡음이 섞여도 논리값이 뒤집히지 않게 하기 위해서다. 디지털이라는 말은 전압이 즉시 완벽한 사각형이라는 뜻이 아니다. 신호는 상승·하강하는 데 시간이 걸리고 배선과 트랜지스터는 지연과 에너지를 가진다.

**트랜지스터(transistor)**는 전기 신호로 다른 전류 경로를 제어하는 소자다. 현대 디지털 회로에서는 많은 트랜지스터를 조합해 논리 게이트와 저장 소자를 만든다. 이 장은 트랜지스터의 반도체 물리보다 게이트 수준의 관찰에 집중한다.

## 2. 논리 게이트와 진리표

**논리 게이트(logic gate)**는 입력 논리값을 규칙에 따라 출력 논리값으로 바꾸는 회로다. **진리표(truth table)**는 가능한 모든 입력 조합과 출력을 적은 표다.

| A | B | AND | OR | XOR |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 | 1 |
| 1 | 1 | 1 | 1 | 0 |

**AND**는 두 입력이 모두 1일 때만 1이다. **OR**은 하나 이상이 1이면 1이다. **XOR(exclusive OR, 배타적 논리합)**은 두 입력이 서로 다를 때 1이다. **NOT**은 입력 하나를 뒤집는다. NAND는 AND 뒤에 NOT을 붙인 규칙이고 NOR는 OR 뒤에 NOT을 붙인 규칙이다.

게이트의 출력은 입력이 바뀐 순간 수학적으로 즉시 바뀌지 않는다. 입력 전환이 출력에 안정된 값으로 나타나기까지의 시간을 **전파 지연(propagation delay)**이라고 한다. 여러 게이트가 직렬로 이어지면 경로 지연이 누적된다. 순간적으로 서로 다른 경로의 신호 도착 시간이 달라 잘못된 중간 출력인 **glitch**가 생길 수도 있다.

## 3. 조합 논리: 현재 입력으로 현재 출력을 만든다

**조합 논리(combinational logic)**는 현재 입력 조합이 같으면 안정된 뒤 같은 출력을 낸다. 과거 값을 기억하는 상태는 없다. decoder, multiplexer, 비교기, 가산기가 대표적이다.

**multiplexer 또는 MUX(다중 선택기)**는 여러 입력 중 선택 신호가 지정한 하나를 출력한다. CPU의 다음 PC가 순차 주소인지 분기 목표인지 고를 때 이런 선택 논리를 사용할 수 있다. 2:1 MUX에서 선택 S=0이면 입력 X, S=1이면 입력 Y를 출력한다고 하자. 논리식은 NOT S AND X, 또는 S AND Y의 OR로 만들 수 있다.

**decoder(해독기)**는 입력 비트 패턴을 여러 선택선 중 하나로 펼친다. 2비트 입력 10이면 네 출력 중 번호 2만 활성화하는 식이다. 명령 decoder라는 말은 단순한 한 게이트가 아니라 opcode와 필드를 해석해 여러 제어 신호를 만드는 회로 블록을 가리킬 수 있다.

~~~mermaid
flowchart LR
  A[A] --> X[XOR]
  B[B] --> X
  A --> N[AND]
  B --> N
  X --> S[합 비트 Sum]
  N --> C[자리올림 Carry]
~~~

### 3.1 반가산기와 전가산기

**반가산기(half adder)**는 두 1비트 A와 B를 더한다. sum은 A XOR B, carry는 A AND B다. 1+1에서는 sum=0, carry=1이므로 두 비트 결과는 10₂다.

**전가산기(full adder)**는 A, B뿐 아니라 아래 자리에서 올라온 carry-in도 더한다. A=1, B=0, Cin=1이면 총합은 2이므로 현재 자리 sum=0, 위 자리 carry-out=1이다.

4비트 0111₂와 0011₂를 오른쪽부터 더한다.

| 자리 | A | B | Cin | 합계 | Sum | Cout |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 1 | 0 | 2 | 0 | 1 |
| 1 | 1 | 1 | 1 | 3 | 1 | 1 |
| 2 | 1 | 0 | 1 | 2 | 0 | 1 |
| 3 | 0 | 0 | 1 | 1 | 1 | 0 |

결과는 1010₂, 즉 10이다. 단순 **ripple-carry adder**는 각 자리 carry가 다음 자리 입력이므로 폭이 커질수록 최악 지연이 길어진다. **carry-lookahead** 같은 구조는 여러 자리의 carry 조건을 병렬로 계산해 지연을 줄이지만 회로 면적과 배선이 늘 수 있다. ISA가 ADD의 결과를 정의해도 가산기 내부 구조까지 강제하지는 않는다.

### 3.2 부호 없는 carry와 signed overflow

4비트 unsigned 1111₂+0001₂는 1 0000₂다. 결과 레지스터가 4비트라면 아래 0000만 남고 바깥 carry-out은 1이다. unsigned 범위 0~15를 넘었다.

같은 4비트를 2의 보수 signed로 해석하면 0111₂는 7이고 0001₂는 1이다. 합의 1000₂는 -8로 해석된다. 양수 둘을 더해 음수 결과가 되었으므로 signed overflow다. carry-out과 signed overflow는 같은 조건이 아니다. 1111₂(-1)+0001₂(1)=0000₂는 carry-out이 있어도 signed 결과 0은 정상이다.

## 4. 순차 논리: 과거 상태를 기억한다

프로그램 실행에는 이전 PC, 레지스터 값처럼 과거 상태가 필요하다. **순차 논리(sequential logic)**는 현재 입력뿐 아니라 저장된 상태에 따라 출력과 다음 상태가 달라진다.

**래치(latch)**는 enable 조건이 활성인 동안 입력 변화가 출력으로 통과할 수 있는 level-sensitive 저장 소자다. **플립플롭(flip-flop)**은 보통 상승 edge나 하강 edge 같은 특정 순간에 입력을 받아 다음 edge까지 보관하는 edge-triggered 모형으로 설명한다. 둘을 무조건 같은 말로 쓰면 timing 분석에서 혼동된다.

D flip-flop의 D는 다음에 저장할 데이터 입력이고 Q는 현재 저장 출력이다. 상승 edge에서 D=1이면 작은 clock-to-Q 지연 뒤 Q=1이 된다. edge 사이에 D가 바뀌어도 다음 edge 전까지 Q는 유지된다.

| 시점 | D | 상승 edge | Q |
|---:|---:|---|---:|
| 0.1 ns | 0 | 없음 | 이전값 0 |
| 0.3 ns | 1 | 없음 | 0 유지 |
| 0.4 ns | 1 | 있음 | 지연 뒤 1 |
| 0.6 ns | 0 | 없음 | 1 유지 |
| 0.8 ns | 0 | 있음 | 지연 뒤 0 |

여러 flip-flop을 묶으면 한 번에 여러 비트를 저장하는 **레지스터**를 만들 수 있다. read port와 write port를 가진 많은 저장 위치를 배열하고 선택 회로를 붙이면 레지스터 파일이 된다. 실제 고성능 레지스터 파일은 단순한 flip-flop 묶음보다 면적과 포트 지연을 줄이는 구현을 쓸 수 있다.

## 5. 클록은 시간을 나누는 계약이다

**클록(clock)**은 동기식 회로의 상태 갱신 시점을 맞추는 반복 신호다. **주기(period 또는 cycle time)**는 반복 한 번의 시간이고 **주파수(frequency)**는 초당 반복 횟수인 Hz다.

1 GHz는 초당 10⁹주기이므로 한 주기는 1ns다. 2.5 GHz의 한 주기는 1/(2.5×10⁹)s=0.4ns다. 4 GHz면 0.25ns다. 이 값은 상태 갱신 간격이지 명령 한 개가 반드시 그 시간 안에 완료된다는 뜻이 아니다. 한 명령은 여러 pipeline stage와 여러 cycle을 사용할 수 있다.

한 레지스터의 출력이 조합 논리를 지나 다음 레지스터 입력으로 들어가는 경로를 생각한다. 다음 edge 전에 신호가 안정되어야 한다. 단순화한 최소 주기는 다음 합보다 길어야 한다.

- 출발 flip-flop의 clock-to-Q 지연
- 조합 논리의 최악 전파 지연
- 도착 flip-flop의 setup time
- clock skew와 설계 여유

clock-to-Q=0.08ns, 조합 지연=0.31ns, setup=0.06ns, 여유=0.05ns라면 최소 주기는 0.50ns이고 최대 이론 주파수는 2GHz다. 2.5GHz의 0.4ns 주기를 강제로 사용하면 최악 경로가 다음 edge 전 안정되지 않아 올바른 값을 보장할 수 없다.

**critical path(임계 경로)**는 한 clock domain에서 주기를 제한하는 가장 긴 조합 경로다. 주파수를 높이려면 논리를 최적화하거나 pipeline register를 추가해 경로를 나눌 수 있다. register 추가는 각 stage 지연을 줄일 수 있지만 명령이 지나야 할 stage 수, branch 오예측 비용, 전력과 면적을 바꾼다.

## 6. setup, hold, skew, jitter

**setup time**은 clock edge 전에 D가 안정되어 있어야 하는 최소 시간이다. **hold time**은 edge 뒤에도 D가 유지되어야 하는 최소 시간이다. 둘 중 하나를 어기면 flip-flop이 즉시 안정된 0이나 1로 결정되지 못하는 **metastability(준안정 상태)**에 들어갈 수 있다.

metastability는 논리값 0.5를 저장한다는 단순 개념이 아니다. 내부 전압이 불안정한 상태에서 어느 쪽으로 결정될지, 안정되기까지 얼마나 걸릴지 정해진 디지털 시간 안에 보장하기 어려운 현상이다. 확률을 아주 낮출 수는 있어도 비동기 입력에서 수학적으로 완전히 제거한다고 말하면 안 된다.

**clock skew**는 같은 clock edge가 서로 다른 레지스터에 도착하는 시간 차이다. **jitter**는 clock edge 위치가 시간에 따라 흔들리는 현상이다. skew는 setup 여유뿐 아니라 너무 짧은 경로의 hold 조건에도 영향을 준다. 주파수 숫자만 보고 timing이 맞는지 판단할 수 없는 이유다.

## 7. clock domain crossing

서로 다른 주파수나 위상으로 움직이는 회로 영역을 **clock domain**이라고 한다. 외부 네트워크 신호, 장치 interrupt, 다른 PLL의 clock에서 오는 신호는 현재 domain의 edge와 무관하게 바뀔 수 있다.

한 비트 상태 신호를 다른 domain으로 넘길 때 흔히 두 단계 synchronizer를 사용한다. 첫 flip-flop이 metastable해져도 두 번째가 읽기 전 안정될 시간을 더 준다. 이는 실패 확률을 줄이는 구조이지 모든 데이터 전달 문제를 해결하는 마법은 아니다. 짧은 pulse는 놓칠 수 있고 여러 비트를 각각 동기화하면 서로 다른 시점 값이 섞일 수 있다.

여러 비트 데이터와 생산자·소비자 속도가 다르면 **asynchronous FIFO**를 사용할 수 있다. write pointer와 read pointer를 각 clock domain에서 관리하고 Gray code처럼 한 번에 한 비트만 바뀌는 표현을 이용해 pointer 동기화 위험을 낮춘다. 데이터 자체, pointer, full/empty 판정의 역할을 구분해야 한다.

~~~mermaid
flowchart LR
  A["비동기 입력 또는 Domain A"] --> F1["첫 동기화 flip-flop"]
  F1 --> F2["둘째 동기화 flip-flop"]
  F2 --> B["Domain B 논리"]
  N["주의: pulse·다중 비트에는 별도 protocol 필요"] -.-> F2
~~~

## 8. reset과 전원·온도 조건

**reset**은 회로 상태를 알려진 초기값으로 보내는 기능이다. reset을 assertion하는 방식과 해제하는 방식이 동기인지 비동기인지 구분한다. 비동기 reset을 clock과 무관하게 걸 수 있어도 해제 시점이 edge 근처면 recovery/removal timing 문제가 생길 수 있어 domain별 동기화가 필요하다.

게이트 지연은 고정 상수가 아니다. 제조 공정 편차, 공급 전압, 온도에 따라 변한다. 이를 **PVT(process, voltage, temperature) corner**라고 묶어 분석한다. 전압을 낮추면 동적 에너지를 줄일 수 있지만 지연이 늘고 timing 여유가 감소할 수 있다. 온도가 올라가면 누설과 지연 특성도 바뀐다.

**DVFS(Dynamic Voltage and Frequency Scaling)**는 부하와 전력·열 조건에 따라 전압과 주파수를 조절하는 기법이다. 주파수를 낮추면 단위 시간 처리량이 줄 수 있지만 전력과 열 제한 안에서 더 오래 안정적으로 실행할 수 있다. 최신 CPU와 가속기 연구에서는 최고 주파수 하나보다 성능, 에너지, 온도, 오류율을 함께 최적화한다.

칩렛과 대규모 가속기는 모든 영역에 하나의 완벽한 clock을 배포하기 어렵다. 여러 domain을 두고 경계에서 protocol로 연결하는 **GALS(Globally Asynchronous, Locally Synchronous)** 방식과 저전력 clock gating도 중요하다. clock gating은 유휴 block의 clock 전환을 멈춰 동적 전력을 줄이지만, enable 신호가 glitch 없이 timing 규칙을 만족해야 한다.

## 9. 00장의 ADD와 연결하기

00장의 교육용 ADD가 r1=7, r2=5를 더한다고 하자. 레지스터 파일의 read 회로가 두 값을 내보내고 가산기의 각 자리 전가산기가 sum과 carry를 계산한다. 결과 12의 비트 패턴이 목적 레지스터 입력에 도착한다. clock edge 전 setup 시간을 만족하면 다음 상태로 저장된다.

그러나 실제 비순차 CPU에서 “ADD 결과 저장”은 건축적 r3를 즉시 바꾸는 단순 edge 하나가 아닐 수 있다. 결과가 물리 레지스터와 ROB에 들어가고 나중에 retire한다. 디지털 논리는 그 구현을 만드는 재료이고, ISA가 프로그램에 보이는 최종 결과를 정한다. gate 수준 timing과 ISA 수준 상태 전이를 섞지 않아야 한다.


## 10. 논리 회로를 어떻게 검증하는가

진리표가 작은 gate의 기능을 완전히 나열할 수 있어도 CPU 규모 회로의 모든 입력 조합을 직접 시험하는 것은 불가능하다. 그래서 설계자는 여러 수준의 검증을 함께 사용한다.

**simulation(시뮬레이션)**은 입력 파형을 넣고 시간에 따른 출력을 계산한다. 기능 simulation은 논리값이 맞는지 보고 timing simulation은 gate와 배선 지연을 포함할 수 있다. simulation에서 통과한 입력만 맞다는 증거이므로 test가 빠뜨린 경우가 남는다.

**formal verification(형식 검증)**은 수학적으로 표현한 property가 가능한 상태와 입력에서 성립하는지 증명하거나 반례 trace를 찾는다. 예를 들어 “reset 뒤 valid=0”, “request를 받으면 제한된 cycle 안에 response 또는 error” 같은 property를 적는다. property 자체가 요구사항을 잘못 표현하면 증명이 되어도 원하는 제품이 아닐 수 있다.

**equivalence checking(등가성 검사)**은 RTL을 최적화하거나 gate netlist로 합성한 뒤 두 표현의 관찰 결과가 같은지 확인한다. source RTL과 synthesized circuit이 같다는 검사는 ISA 구현이 전체적으로 맞다는 증명과 범위가 다르다.

**static timing analysis**는 특정 data pattern을 하나씩 simulation하지 않고 timing graph의 경로를 분석해 setup과 hold 조건을 검사한다. “기능 결과가 맞다”와 “목표 clock에서 제시간에 도착한다”는 별도 검증 항목이다.

교육용 4비트 adder를 검증한다면 16×16=256개 A,B 조합과 carry-in 두 값을 모두 검사할 수 있다. 결과의 아래 4비트가 수학적 합 modulo 16과 같고 carry-out이 16 이상 여부와 같은지 비교한다. signed overflow property는 carry-out 대신 “같은 부호 두 입력의 결과 부호가 바뀌었는가”를 검사한다.

## 11. 성능뿐 아니라 전력과 열을 읽는다

CMOS 회로의 동적 전력은 단순 모델에서 switching activity, capacitance, 전압의 제곱, 주파수에 비례한다. 모든 node가 매 cycle 전환하지 않으므로 **switching activity**를 포함한다. 전압을 조금 낮추면 동적 에너지는 크게 줄 수 있지만 gate가 느려져 timing 실패 위험이 커진다.

**정적 전력 또는 leakage power**는 논리값이 바뀌지 않아도 흐르는 누설 전류에서 생긴다. 공정과 온도에 민감하다. clock tree는 많은 저장 소자에 매 cycle 신호를 보내므로 실제 data 계산이 없어도 큰 switching 비용을 만들 수 있다. **clock gating**은 유휴 block의 clock 전환을 멈추지만 enable을 안전하게 만들고 다시 시작할 때 상태 일관성을 지켜야 한다.

CPU가 높은 주파수에서 잠시 빨라졌다가 온도·전력 제한으로 낮아지는 **thermal throttling**을 생각하자. 5GHz라는 최고 수치와 10분 workload의 지속 주파수는 다르다. 같은 명령과 입력이어도 냉각, 전력 제한, 동시 활성 core 수가 실행시간을 바꿀 수 있다. benchmark에는 주파수, 온도, warm-up, 반복 조건을 함께 기록한다.

최신 연구에서는 timing 여유를 크게 잡아 모든 최악 조건을 피하는 대신, 실제 critical path의 오류를 감지하고 재실행하거나 workload에 맞춰 전압을 조정하는 방법도 연구한다. 그러나 오류 검출기가 놓치는 silent data corruption과 recovery 비용까지 평가해야 한다. “전압을 낮추면 전력 절약”만으로 안전성을 결론 내릴 수 없다.

## 12. 두 번째 timing trace

두 pipeline register 사이에 세 논리 block A, B, C가 있고 지연이 각각 0.10ns, 0.18ns, 0.12ns라고 하자. clock-to-Q=0.06ns, setup=0.05ns, skew와 jitter 여유=0.04ns다.

전체를 한 stage로 두면 최소 주기는 0.06+0.10+0.18+0.12+0.05+0.04=0.55ns이고 최대 주파수는 약 1.82GHz다. B와 C 사이에 register를 하나 추가하면 앞 stage 경로는 0.06+0.10+0.18+0.05+0.04=0.43ns, 뒤 stage는 0.06+0.12+0.05+0.04=0.27ns다. 새 최대 주파수는 긴 쪽인 0.43ns 기준 약 2.33GHz다.

주파수는 높아졌지만 한 data item은 register stage를 하나 더 지나므로 latency cycle 수가 증가한다. 새 register의 clock load와 area도 늘어난다. 실제 설계는 두 stage의 지연을 더 균등하게 나누고 branch와 forwarding 경로까지 함께 고려한다.


## 13. 문제와 전체 풀이

### 문제 1. 게이트와 가산기

A=1, B=1, Cin=1인 전가산기의 sum과 carry-out을 구하라.

**풀이:** 세 입력의 산술 합은 3이고 이진수로 11₂다. 현재 자리에는 아래 비트 1이 남으므로 sum=1, 다음 자리로 위 비트 1을 보내므로 carry-out=1이다. AND(1,1)만 계산하는 반가산기와 달리 Cin도 포함해야 한다.

### 문제 2. unsigned carry와 signed overflow

4비트에서 0111+0001과 1111+0001을 계산하고 carry-out과 signed overflow를 구분하라.

**풀이:** 0111+0001=1000이다. 바깥 carry-out은 0이지만 signed로 7+1이 -8이 되어 overflow다. 1111+0001=1 0000이므로 4비트 결과 0000과 carry-out 1이다. signed로는 -1+1=0이므로 overflow가 아니다. carry와 signed overflow는 같은 플래그가 아니다.

### 문제 3. 최대 clock

clock-to-Q=0.07ns, 최악 조합 지연=0.28ns, setup=0.05ns, skew와 여유 합=0.05ns다. 최소 주기와 최대 주파수는?

**풀이:** 최소 주기는 0.07+0.28+0.05+0.05=0.45ns다. 주파수는 1/0.45ns≈2.22GHz다. 이는 단순 교육 계산이며 실제 sign-off는 여러 PVT corner, jitter, 변동과 hold 검사를 포함한다.

### 문제 4. metastability

외부 버튼 신호를 한 flip-flop으로 바로 받아도 “대부분 동작하므로” 안전한가?

**풀이:** 안전하다고 보장할 수 없다. 버튼 전환이 clock edge의 setup/hold 창과 겹치면 첫 flip-flop이 metastable해지고 다음 논리가 정해진 시간 안에 안정값을 못 받을 수 있다. 한 비트 level 신호에는 보통 두 단계 synchronizer로 결정 시간을 늘리고, 버튼 bouncing도 별도 debounce한다. pulse와 다중 비트에는 handshake나 asynchronous FIFO 같은 protocol이 필요하다.

### 문제 5. pipeline의 이득과 비용

0.8ns 조합 경로를 가운데 register로 두 개의 0.4ns 경로로 나누면 명령이 무조건 두 배 빨라지는가?

**풀이:** 아니다. 각 stage에는 새 register의 clock-to-Q와 setup, skew 비용이 추가된다. 한 작업이 지나야 할 stage 수가 늘어 latency가 증가할 수 있다. 충분한 독립 작업에서는 처리량이 높아질 수 있지만 branch 오예측 시 버릴 stage도 늘 수 있다. 주파수, latency, throughput, 전력, 정확성을 함께 비교해야 한다.

## 14. 공식 자료와 다음 장 연결

RISC-V ISA 명세는 ADD 같은 명령의 프로그램에 보이는 결과를 정의한다. 특정 RISC-V CPU가 ripple-carry인지, 몇 단계 pipeline인지, 어떤 clock distribution을 쓰는지는 ISA가 정하지 않는다. 다음 장에서는 이 경계를 유지한 채 명령 바이트의 field를 실제 숫자로 해독한다.

- [RISC-V Ratified Specifications](https://docs.riscv.org/)
- [RISC-V Unprivileged ISA Manual](https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/)

[← 이전](00-architecture-and-execution-map.md) · [목차](README.md) · [다음 →](02-instructions-registers-and-isa.md)
