# 03. Gradient와 최적화

[← 이전](02-linear-regression-and-loss.md) · [목차](README.md) · [다음 →](04-classification-and-probabilities.md)

Gradient는 parameter를 조금 바꿀 때 loss가 어느 방향으로 얼마나 변하는지 나타낸다.

미분은 순간 변화율을 계산하는 방법이다.

Optimizer는 gradient를 읽어 parameter를 실제로 갱신한다.

## 이 장의 목표

1. 새 용어와 수학 기호를 말로 설명한다.
2. 입력이 중간 숫자를 거쳐 결과가 되는 과정을 계산한다.
3. 계산 모형과 실제 성능 주장을 구분한다.

![03. Gradient와 최적화 도식](assets/regression-gradient.svg)

## 기본 단어와 기호

**slope**는 입력 변화 대비 출력 변화이다.

**derivative**는 한 점의 순간 변화율이다.

**partial derivative**는 다른 변수를 고정한 한 변수의 미분이다.

**gradient**는 모든 parameter 편미분의 vector이다.

**chain rule**는 연결된 변화율을 곱하는 규칙이다.

**learning rate**는 update 크기 계수이다.

**gradient descent**는 loss가 줄어드는 방향으로 이동이다.

**SGD**는 sample 또는 작은 batch 기반 gradient descent이다.

**momentum**는 이전 update 방향을 누적이다.

**Adam**는 gradient 평균과 제곱 평균을 쓰는 optimizer이다.

**step**는 한 번의 parameter 갱신이다.

**convergence**는 목표값 근처로 수렴하는 현상이다.

기호를 읽을 때 이름, shape, 단위, 생성 주체를 함께 적는다.

## 왜 필요한가

- Loss 값만 알아서는 parameter를 어느 방향으로 바꿀지 모른다.
- Learning rate가 너무 크면 최소점을 지나 흔들릴 수 있다.
- 너무 작으면 학습이 지나치게 느리다.
- Gradient 0은 전역 최솟값을 보장하지 않는다.

## 입력에서 결과까지

1. Forward가 현재 parameter의 loss를 만든다.
2. 미분 규칙이 local derivative를 구한다.
3. Chain rule이 경로의 derivative를 곱한다.
4. 여러 경로의 gradient를 더한다.
5. Optimizer가 gradient buffer를 읽는다.
6. Learning rate와 optimizer state를 적용한다.
7. Parameter를 새 값으로 쓴다.
8. 다음 step에서 새 loss를 관찰한다.

```mermaid
flowchart LR
    W[현재 가중치 w] --> L[손실 L(w)]
    L --> N[작은 변화로 수치 미분]
    L --> D[식으로 도함수 계산]
    N --> G[기울기 비교]
    D --> G
    G --> U[학습률을 곱해 새 w]
```

## 작은 숫자로 한 번 계산하기

L(w)=(w-3)²라고 하자.

Derivative dL/dw=2(w-3)이다.

w=1이면 gradient=2×(-2)=-4다.

Learning rate 0.25를 쓴다.

새 w=1-0.25×(-4)=2다.

처음 loss=(1-3)²=4다.

새 loss=(2-3)²=1이다.

Gradient가 음수였으므로 w를 키우는 update가 일어났다.

| 구분 | 값 또는 책임 |
|---|---|
| w | 1 |
| gradient | -4 |
| learning rate | 0.25 |
| new w | 2 |

## 수치 미분에서 도함수로 가기

미분을 처음 볼 때는 실제로 값을 조금 바꿔 보는 방법이 도움이 된다.

`L(w)=(w-3)²`, 현재 `w=1`이라고 하자.

작은 변화 `h=0.001`을 사용한다.

```text
L(1)=4
L(1.001)=(1.001-3)²=3.996001
앞쪽 차분=(3.996001-4)/0.001=-3.999
```

`h`를 충분히 작게 했을 때 변화율은 약 -4다.

식으로 미분한 도함수 `2(w-3)`에 w=1을 넣어도 -4다.

수치 미분은 구현의 gradient를 점검하는 데 유용하다.

하지만 h가 너무 크면 곡선의 한 점 기울기를 잘 근사하지 못한다.

h가 지나치게 작으면 floating point 반올림 오차가 커질 수 있다.

## 스칼라 미분에서 벡터 기울기로

Parameter가 `w1`, `w2` 두 개면 각각을 따로 조금 바꾼 변화율을 구한다.

```text
L(w1,w2)=(w1-1)²+(w2+2)²
∂L/∂w1=2(w1-1)
∂L/∂w2=2(w2+2)
```

`w1=0`, `w2=0`이면 gradient vector는 `[-2,4]`다.

학습률 0.1의 update는 다음과 같다.

```text
new w1=0-0.1×(-2)=0.2
new w2=0-0.1×4=-0.4
```

## 학습률이 너무 커 최소점을 지나치는 예

다시 `L(w)=(w-3)²`, w=1, gradient=-4를 사용한다.

학습률 0.25면 새 w=2이고 loss는 1로 줄어든다.

학습률 2면 새 w=1-2×(-4)=9다.

새 loss는 `(9-3)²=36`이다.

처음 loss 4보다 아홉 배 크다.

기울기 방향이 맞아도 이동 거리가 너무 크면 최소점 3을 지나 반대편 멀리 간다.

그래서 학습률 schedule, gradient clipping, loss curve 관찰이 필요하다.

## 미분, 편미분, 기울기를 구분하기

**미분(derivative)**은 입력 하나를 아주 조금 바꿀 때 출력이 얼마나 변하는지 나타내는 순간 변화율이다. 직선의 일정한 기울기와 달리 곡선은 위치마다 변화율이 달라서 “어느 점에서”를 함께 말해야 한다.

Parameter가 여러 개이면 한 숫자만 바꿔 보는 **편미분(partial derivative)**을 사용한다. `∂J/∂w`는 b를 고정하고 w만 바꿀 때 손실 J의 변화율, `∂J/∂b`는 w를 고정하고 b만 바꿀 때 변화율이다.

**기울기(gradient)**는 모든 편미분을 parameter와 같은 순서로 모은 벡터다.

```text
θ=[w,b]
∇J=[∂J/∂w, ∂J/∂b]
```

기울기는 현재 위치에서 손실이 가장 빠르게 증가하는 국소 방향을 가리킨다. 그래서 gradient descent는 반대 방향 `-∇J`로 이동한다. “국소”이므로 큰 폭으로 이동한 뒤에도 손실이 줄어든다는 보장은 없다.

**Step**은 gradient 계산과 parameter 갱신 한 번의 단위다. **학습률(learning rate)**은 gradient를 얼마만큼 parameter 변화로 바꿀지 정하는 계수다. Gradient 단위와 parameter 단위가 다르므로 학습률도 식 전체의 단위를 맞추는 역할을 한다.

## 같은 배송 데이터의 전체 gradient 유도

02장의 데이터와 목적함수를 그대로 쓴다.

```text
x=[1,2,3]
y=[2,4,5]
w=1, b=1
J=(1/(2n)) Σ(wx_i+b-y_i)²
n=3
```

현재 예측은 `[2,3,4]`, 오차 `e=ŷ-y=[0,-1,-1]`이다.

한 표본에서 w를 `Δw`만큼 바꾸면 예측은 `x_iΔw`만큼 바뀐다. Half squared error의 예측에 대한 변화율은 `e_i`다. 연쇄법칙을 적용하면 표본 i의 w 기여는 `e_ix_i`다.

평균 목적함수이므로 모든 표본 기여를 더해 n으로 나눈다.

```text
∂J/∂w = (1/n) Σ e_i x_i
       = [0×1 + (-1)×2 + (-1)×3] / 3
       = -5/3
       ≈ -1.6667
```

Bias b를 조금 바꾸면 모든 예측이 같은 양만큼 바뀌므로 `∂ŷ_i/∂b=1`이다.

```text
∂J/∂b = (1/n) Σ e_i
       = [0 + (-1) + (-1)] / 3
       = -2/3
       ≈ -0.6667
```

따라서 gradient는 `[-1.6667,-0.6667]`이다. 둘 다 음수이므로 작은 양의 학습률에서는 w와 b가 증가한다.

## 한 step 갱신과 새 평균 손실

학습률 `η=0.1`을 사용한다. 그리스 문자 eta를 학습률 기호로 자주 쓴다.

```text
new w = 1 - 0.1×(-5/3) = 7/6 ≈ 1.1667
new b = 1 - 0.1×(-2/3) = 16/15 ≈ 1.0667
```

새 parameter로 세 예측을 모두 다시 계산한다.

| x | y | 새 예측 | 새 오차 | 오차² |
|---:|---:|---:|---:|---:|
| 1 | 2 | 2.2333 | 0.2333 | 0.0544 |
| 2 | 4 | 3.4000 | -0.6000 | 0.3600 |
| 3 | 5 | 4.5667 | -0.4333 | 0.1878 |

제곱합은 약 `0.6022`다. 새 MSE는 `0.6022/3≈0.2007`, 새 J는 절반인 약 `0.1004`다. 이전 MSE `0.6667`, J `0.3333`보다 모두 줄었다.

이 한 step은 계산 원리의 확인이다. 실제 학습 성능이나 새 데이터 일반화의 증거가 아니다.

## 수치 미분으로 두 편미분 점검하기

Analytic 식이 맞는지 parameter 하나씩 `h=0.001` 바꿔 확인할 수 있다.

```text
w 방향 근사 = [J(w+h,b)-J(w,b)]/h
b 방향 근사 = [J(w,b+h)-J(w,b)]/h
```

각 계산에서 다른 parameter는 고정한다. 이 근사값이 각각 약 `-1.6667`, `-0.6667`에 가까워야 한다. 차이가 크면 평균 분모, 오차 부호, bias broadcast, 구현 indexing을 확인한다.

수치 미분은 느려서 큰 모델 학습에 직접 쓰지 않는다. 작은 모형의 gradient 검사에 사용한다.

## Batch, step, epoch의 위치

**Batch**는 한 번의 gradient 계산에 함께 쓰는 표본 묶음이다. 위 세 배송을 모두 쓰면 full batch다. 한 건씩 쓰면 각 gradient가 크게 흔들릴 수 있지만 계산이 가볍다.

**Step**은 batch 하나로 gradient를 계산해 parameter를 한 번 갱신하는 일이다. **Epoch**는 training 데이터 전체를 한 번 읽은 범위다. 표본 300개, batch size 30이면 drop 조건이 없을 때 epoch당 10 step이다.

Optimizer는 model parameter를 바꾸는 주체다. Backward 또는 미분 계산은 gradient를 만들 뿐이다. Gradient buffer를 읽기 전에 유한값 검사, clipping, 분산 평균이 끼어들 수 있다.

## 조건을 바꾼 반례: 특징 scale

거리를 km 대신 m로 입력하면 x는 천 배 커진다. 같은 물리 관계에서 w는 천 분의 일이 되어야 하지만 초기 w와 학습률을 그대로 쓰면 `e_ix_i` gradient가 매우 커질 수 있다.

따라서 feature 표준화나 feature별 scale을 고려한다. “같은 학습률 0.1”은 입력 표현이 달라져도 같은 이동을 뜻하지 않는다.

Momentum과 Adam은 이전 gradient 통계를 사용해 update를 바꾼다. 그래도 현재 gradient 계산, optimizer state, parameter update를 구분해야 한다. Optimizer 이름은 좋은 최솟값이나 일반화를 보장하지 않는다.

## 추가 문제 5개와 전체 해설

### 문제 1

`L(w)=(w-4)²`, w=2에서 도함수와 감소 방향을 구하라.

**해설:** `dL/dw=2(w-4)=-4`다. Gradient descent는 음의 gradient 반대인 양의 방향으로 w를 키운다.

### 문제 2

위 문제에서 학습률 0.5의 새 w와 loss는?

**해설:** `new w=2-0.5×(-4)=4`, 새 loss는 0이다. 이 단순 이차함수와 시작점에서 정확히 최소점에 도착한 경우다.

### 문제 3

`J(w,b)=(w-1)²+(b+1)²`, `(w,b)=(0,0)`의 gradient는?

**해설:** 편미분은 `2(w-1)=-2`, `2(b+1)=2`다. Gradient vector는 `[-2,2]`다.

### 문제 4

Gradient가 맞아도 학습률 때문에 loss가 커질 수 있는가?

**해설:** 가능하다. `L=(w-3)²`, w=1, gradient=-4에서 학습률 2면 w=9, loss=36으로 증가한다. 방향은 국소 정보이고 이동량이 너무 컸다.

### 문제 5

세 표본 중 한 표본 gradient만 사용해 loss가 줄었다. 전체 최적화 성공인가?

**해설:** 아니다. 다른 표본의 loss가 커질 수 있다. 전체 training 평균, validation, 독립 test를 단계별로 확인해야 한다.

## 계산을 거꾸로 점검하기

결과가 이상하면 마지막 값만 보지 않는다.

입력의 단위와 shape가 맞는지 먼저 확인한다.

중간값을 손으로 다시 계산한다.

Training 중 바뀌는 parameter와 고정된 data를 구별한다.

평가 data가 선택 과정에 들어갔는지 확인한다.

숫자의 분모와 평균 범위를 적는다.

## 실제 시스템으로 확장할 때

작은 예제는 원리를 고립시켜 보여 준다.

실제 system은 noise, queue, concurrency, finite precision을 포함한다.

Data 수집과 label 생성 지연도 성능에 포함한다.

Version, seed, split, metric 정의를 기록한다.

평균과 tail, subgroup 결과를 함께 본다.

실패와 timeout을 결과에서 지우지 않는다.

## 흔한 오해와 반례

- Gradient와 parameter update는 같은 연산이 아니다.
- Learning rate를 크게 하면 항상 빨리 수렴하지 않는다.
- Loss가 한 step 줄었다고 계속 줄어든다는 보장은 없다.
- Optimizer 이름만으로 좋은 결과가 보장되지 않는다.

## 확인 문제와 해설

### 문제 1

Gradient가 +5면 SGD는 어느 방향인가?

**해설:** 양의 learning rate에서 parameter를 줄이는 방향이다.

### 문제 2

Chain rule이 왜 필요한가?

**해설:** Parameter가 여러 중간 연산을 거쳐 loss에 영향을 주기 때문이다.

### 문제 3

Gradient 0의 가능한 의미는?

**해설:** 최솟값, 최댓값, 평평한 지점 등일 수 있어 추가 판단이 필요하다.

## 학습 체크리스트

- 모든 약어를 첫 등장에 풀어 썼는가?
- 수학 기호가 가리키는 값과 단위가 명확한가?
- 입력과 label의 시각 경계가 명확한가?
- Parameter를 바꾸는 주체를 설명했는가?
- Validation과 test의 책임을 나눴는가?
- Baseline과 실패 조건을 기록했는가?

## 공식 자료

- [ISLP 2023](https://www.statlearning.com/home)
- [Dive into Deep Learning: Generalization](https://d2l.ai/chapter_linear-regression/generalization.html)

공식 근거 확인일: **2026-10-11**.

[← 이전](02-linear-regression-and-loss.md) · [목차](README.md) · [다음 →](04-classification-and-probabilities.md)
