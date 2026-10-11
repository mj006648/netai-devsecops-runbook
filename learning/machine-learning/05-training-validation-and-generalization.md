# 05. 학습·검증·일반화

## 모집단에서 표본을 뽑아 새 사례를 예측한다는 뜻

**모집단(population)**은 관심 있는 모든 가능한 사례다. 앞으로 들어올 모든 배송, 모든 cell의 미래 traffic처럼 실제로 전부 볼 수 없는 대상이다. **표본(sample)**은 그중 관측해 데이터로 가진 일부다. 학습 목표는 표본을 암기하는 것이 아니라 같은 목적의 모집단에서 새로 온 사례에 유용한 예측을 하는 **일반화(generalization)**다.

Training set은 parameter를 바꾸고, validation set은 모델 구조·학습률·epoch 같은 선택에 쓰며, test set은 선택을 끝낸 뒤 최종 추정에 쓴다. Test를 보고 설정을 바꾸면 그 test도 선택에 사용됐으므로 독립 test가 아니다.

100일 데이터를 다음처럼 나눈다고 하자.

```text
day 1~60   training: parameter 학습
day 61~80  validation: 후보 A/B와 threshold 선택
day 81~100 test: 선택을 고정한 뒤 한 번 평가
```

시간 예측에서 행을 무작위로 섞으면 day 90과 거의 같은 day 89가 training에 들어갈 수 있다. 미래 분포를 예측하려면 과거→미래 방향을 보존한다.

사용자나 cell도 경계다. 같은 cell A의 연속 window가 train/test 양쪽에 있으면 cell 고유 패턴을 외운 성능이 “새 cell 일반화”처럼 보일 수 있다. 시간 일반화와 대상 일반화를 각각 평가한다.

**교차검증(cross-validation)**은 training 영역을 여러 fold로 나눠 번갈아 validation으로 쓰는 방법이다. 5-fold에서 각 표본은 네 번 학습, 한 번 validation에 쓰인다. 후보 선택 안정성을 보는 데 유용하지만 최종 test를 대체한다고 자동 결론 내리지 않는다.

```text
fold1 validate, fold2~5 train
fold2 validate, 나머지 train
...
5개 validation score 평균
```

시간 series는 일반 K-fold보다 rolling split이 자연스럽다. `train day1~30→validate31~40`, `train1~40→validate41~50`처럼 항상 과거로 미래를 평가한다.

**데이터 누수**는 예측 시점에 알 수 없는 정보가 feature·전처리·선택에 들어가는 일이다. 전체 100일의 평균과 표준편차로 먼저 정규화한 뒤 split하면 test 분포가 training 변환에 들어간다. Training에서 변환 parameter를 fit하고 validation/test에는 그대로 적용한다.

후보 20개를 validation에서 고르면 최고 score에는 우연한 이득도 섞인다. 최종 test는 이 선택 전체의 일반화를 평가한다. Test를 반복 확인하며 후보를 바꾸면 새로운 독립 holdout이나 nested 평가가 필요하다.

## 수치 시간표

후보 A/B의 validation error가 0.18/0.15여서 B를 고정했다. Test 200건에서 34건 오류면 test error는 17%다. Validation 15%를 최종 성능으로 보고하지 않는다. Test 17%도 유한 표본 추정이며 모집단의 정확한 상수가 아니다.

반례로 random split 90% 성능, 시간 split 70%라면 모델이 미래 변화에 약하다는 증거다. 편한 split만 선택하지 않는다.

## 유도 문제 5개

1. Validation으로 parameter를 직접 학습하면? **해설:** 선택 경계가 흐려져 validation 성능이 낙관적이 된다.
2. Test를 세 번 보고 모델을 바꾸면? **해설:** Test가 선택 data가 됐다. 새 독립 평가가 필요하다.
3. 같은 환자의 행이 양쪽 split에 있으면? **해설:** 개인 패턴 누수로 새 환자 성능이 부풀 수 있다.
4. 시간 series에 random K-fold가 위험한 이유는? **해설:** 미래 정보와 인접 window가 과거 학습에 들어갈 수 있다.
5. Population과 sample 차이는? **해설:** 모집단은 결론을 내리고 싶은 전체, 표본은 실제 관측한 일부다.

[← 이전](04-classification-and-probabilities.md) · [목차](README.md) · [다음 →](06-regularization-and-data-quality.md)

일반화는 training에서 보지 않은 data에도 유용한 예측을 하는 능력이다.

Validation은 선택에 쓰고 test는 선택이 끝난 뒤 쓴다.

시간과 대상이 겹치면 data leakage가 생길 수 있다.

## 이 장의 목표

1. 새 용어와 수학 기호를 말로 설명한다.
2. 입력이 중간 숫자를 거쳐 결과가 되는 과정을 계산한다.
3. 계산 모형과 실제 성능 주장을 구분한다.

![05. 학습·검증·일반화 도식](assets/classification-split.svg)

## 기본 단어와 기호

**generalization**는 새 data에서의 성능이다.

**training set**는 parameter 학습용 data이다.

**validation set**는 모델·설정 선택용 data이다.

**test set**는 최종 독립 평가용 data이다.

**hyperparameter**는 학습 전에 고르는 설정이다.

**epoch**는 training data를 한 번 도는 단위이다.

**overfitting**는 training에는 맞지만 새 data에 약한 상태이다.

**underfitting**는 training 관계도 충분히 못 배운 상태이다.

**leakage**는 예측 때 모를 정보가 학습·선택에 들어감이다.

**distribution shift**는 운영 분포가 평가 분포와 다름이다.

**cross-validation**는 여러 fold로 선택 안정성을 보는 방법이다.

**early stopping**는 validation 악화 전에 학습을 멈추는 방법이다.

기호를 읽을 때 이름, shape, 단위, 생성 주체를 함께 적는다.

## 왜 필요한가

- 같은 data로 학습과 평가를 하면 암기를 실력으로 착각한다.
- Validation을 여러 번 보며 설정을 고르면 validation에도 적응한다.
- Test를 반복 선택에 쓰면 독립성이 사라진다.
- 시간 series와 cell data는 무작위 행 분할이 누수를 만들 수 있다.

## 입력에서 결과까지

1. 전체 data의 생성 단위와 시간을 확인한다.
2. 같은 사람·cell·시간 window가 split을 넘지 않게 묶는다.
3. Training으로 parameter를 학습한다.
4. Validation으로 model과 hyperparameter를 선택한다.
5. 선택 기록을 고정한다.
6. Test를 한 번 실행한다.
7. Confidence interval과 subgroup 결과를 계산한다.
8. 운영 drift를 별도로 관측한다.

```mermaid
flowchart LR
 D[전체 데이터] --> T[학습 집합]
 D --> V[검증 집합]
 D --> X[독립 시험 집합]
 T --> M[후보 모델 학습]
 M --> V
 V --> S[모델 선택 고정]
 S --> X
```

## 작은 숫자로 한 번 계산하기

후보 simple의 validation error=0.20이다.

Medium은 0.15다.

Complex는 0.17이다.

Validation 선택은 medium이다.

Medium의 독립 test error=0.19다.

Complex test error=0.14를 보고 complex로 바꾸면 test를 선택에 쓴 것이다.

그 뒤 0.14는 독립 평가가 아니다.

새 test나 nested 절차가 필요하다.

| 구분 | 값 또는 책임 |
|---|---|
| Training | parameter 변경 |
| Validation | 후보 선택 |
| Test | 최종 보고 |
| 운영 | drift와 실제 비용 |

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

- Data가 많아도 중복이면 독립 표본이 아니다.
- Cross-validation 뒤에도 최종 test가 필요할 수 있다.
- Test 점수가 가장 좋은 후보를 고르는 것은 test 누수다.
- Random split이 모든 data에 안전하지 않다.

## 확인 문제와 해설

### 문제 1

Validation을 왜 학습에 직접 쓰지 않는가?

**해설:** 선택 기준으로 남겨 새 설정의 비교에 사용하기 위해서다.

### 문제 2

같은 사용자의 행이 train/test에 섞이면?

**해설:** 개인 고유 패턴을 외워 성능이 부풀 수 있다.

### 문제 3

독립 test의 사용 시점은?

**해설:** 모든 모델·설정 선택을 끝내고 고정한 뒤다.

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

[← 이전](04-classification-and-probabilities.md) · [목차](README.md) · [다음 →](06-regularization-and-data-quality.md)
