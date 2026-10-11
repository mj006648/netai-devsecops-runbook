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
