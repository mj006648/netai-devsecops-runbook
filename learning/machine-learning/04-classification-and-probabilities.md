# 04. 분류와 확률

[← 이전](03-gradients-and-optimization.md) · [목차](README.md) · [다음 →](05-training-validation-and-generalization.md)

분류는 입력을 category로 나누는 문제다.

모델은 먼저 logit이라는 제한 없는 score를 만들 수 있다.

Softmax나 sigmoid가 score를 확률 모양으로 바꾼다.

## 이 장의 목표

1. 새 용어와 수학 기호를 말로 설명한다.
2. 입력이 중간 숫자를 거쳐 결과가 되는 과정을 계산한다.
3. 계산 모형과 실제 성능 주장을 구분한다.

![04. 분류와 확률 도식](assets/classification-split.svg)

## 기본 단어와 기호

**class**는 예측할 범주이다.

**binary classification**는 두 class 분류이다.

**multiclass**는 셋 이상 class 분류이다.

**logit**는 확률 변환 전의 실수 score이다.

**sigmoid**는 한 logit을 0~1로 변환이다.

**softmax**는 여러 score를 합 1인 값으로 변환이다.

**cross-entropy**는 정답 확률의 음의 log 손실이다.

**threshold**는 class 결정을 가르는 기준이다.

**precision**는 양성 예측 중 실제 양성 비율이다.

**recall**는 실제 양성 중 찾아낸 비율이다.

**confusion matrix**는 예측과 정답 조합 표이다.

**calibration**는 예측 확률과 실제 빈도의 일치이다.

기호를 읽을 때 이름, shape, 단위, 생성 주체를 함께 적는다.

## 왜 필요한가

- Logit은 음수나 1보다 큰 값도 가능하므로 확률이 아니다.
- Softmax는 상대 score를 비교해 합이 1인 값을 만든다.
- Log는 작은 정답 확률을 큰 손실로 벌준다.
- Threshold는 false positive와 false negative의 비용에 맞춘다.

## 입력에서 결과까지

1. Model이 class별 logit을 계산한다.
2. 수치 안정화를 위해 최댓값을 뺀다.
3. Exponential을 계산한다.
4. 합으로 나눠 softmax 확률을 만든다.
5. 정답 class 확률의 -log를 loss로 쓴다.
6. Training이 logit parameter를 갱신한다.
7. Validation에서 threshold를 고른다.
8. Test에서 precision, recall, calibration을 평가한다.

```mermaid
flowchart LR
 X[특징 벡터] --> Z[클래스별 로짓]
 Z --> H[최댓값 빼기]
 H --> E[지수 계산]
 E --> P[합으로 나눠 확률]
 P --> C[임계값·클래스 결정]
 P --> L[교차엔트로피]
```

## 작은 숫자로 한 번 계산하기

Logit=[2,1]이라고 하자.

안정화를 위해 max 2를 빼 [0,-1]로 만든다.

exp 값은 [1,0.3679]다.

합은 1.3679다.

확률은 [0.7311,0.2689]다.

정답이 첫 class면 loss=-log(0.7311)≈0.3133이다.

Logit 2 자체는 200% 확률이 아니다.

두 확률의 합은 1이다.

| 구분 | 값 또는 책임 |
|---|---|
| 실제 양성·예측 양성 | TP |
| 실제 음성·예측 양성 | FP |
| 실제 양성·예측 음성 | FN |
| 실제 음성·예측 음성 | TN |

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

- 가장 큰 logit은 확률값이 아니다.
- Softmax 0.9가 항상 90% calibration을 뜻하지 않는다.
- Accuracy는 불균형 data에서 오해를 부를 수 있다.
- Threshold 0.5가 모든 비용 구조에 최적은 아니다.

## 확인 문제와 해설

### 문제 1

Logit [-1,3]의 합이 1이어야 하는가?

**해설:** 아니다. Logit은 제한 없는 score다.

### 문제 2

Precision 식은?

**해설:** TP/(TP+FP)다.

### 문제 3

Recall을 높이면 어떤 trade-off가 가능한가?

**해설:** Threshold를 낮추면 더 많이 찾지만 false positive가 늘 수 있다.

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

[← 이전](03-gradients-and-optimization.md) · [목차](README.md) · [다음 →](05-training-validation-and-generalization.md)
