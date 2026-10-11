# 06. 정규화와 데이터 품질

[← 이전](05-training-validation-and-generalization.md) · [목차](README.md) · [다음 →](07-computation-graphs-and-autograd.md)

정규화는 모델이 training data의 우연한 세부에 과도하게 맞는 것을 줄이는 방법이다.

데이터 품질 문제는 모델 기법만으로 고칠 수 없다.

결측, 중복, label 오류, 표본 편향을 먼저 조사한다.

## 이 장의 목표

1. 새 용어와 수학 기호를 말로 설명한다.
2. 입력이 중간 숫자를 거쳐 결과가 되는 과정을 계산한다.
3. 계산 모형과 실제 성능 주장을 구분한다.

![06. 정규화와 데이터 품질 도식](assets/classification-split.svg)

## 기본 단어와 기호

**regularization**는 복잡도나 parameter 크기를 제한하는 방법이다.

**L1**는 절댓값 penalty이다.

**L2**는 제곱 penalty이다.

**weight decay**는 parameter를 0 쪽으로 줄이는 update이다.

**dropout**는 training 중 activation 일부를 확률적으로 0으로 함이다.

**augmentation**는 의미를 보존하는 data 변형이다.

**missing value**는 관측되지 않은 값이다.

**outlier**는 일반 범위에서 크게 벗어난 값이다.

**duplicate**는 같거나 매우 유사한 반복 sample이다.

**label noise**는 잘못되거나 애매한 정답이다.

**class imbalance**는 class 빈도 차이가 큰 상태이다.

**data provenance**는 data 출처와 처리 이력이다.

기호를 읽을 때 이름, shape, 단위, 생성 주체를 함께 적는다.

## 왜 필요한가

- 복잡한 모델은 noise까지 외울 수 있다.
- L1과 L2는 같은 penalty가 아니다.
- Dropout은 training과 evaluation 동작이 다르다.
- 나쁜 label을 더 오래 학습하면 오류를 더 잘 외울 수 있다.

## 입력에서 결과까지

1. Data source와 consent를 기록한다.
2. 중복 단위를 정의해 train/test 중복을 찾는다.
3. 결측값의 원인과 비율을 조사한다.
4. Label 작성 기준과 disagreement를 측정한다.
5. Baseline과 regularized 후보를 만든다.
6. Validation으로 penalty 강도를 고른다.
7. Evaluation에서 dropout을 끄고 일관된 동작을 쓴다.
8. Subgroup와 rare class 오류를 보고한다.

```mermaid
flowchart LR
 D[원시 데이터] --> Q[결측·중복·정답 검사]
 Q --> T[학습 데이터]
 T --> M[기본 손실]
 W[가중치 크기] --> P[L1·L2 벌점]
 M --> O[전체 목적함수]
 P --> O
 O --> V[검증으로 강도 선택]
```

## 작은 숫자로 한 번 계산하기

Training loss=0.20인 모델의 weight가 [3,4]다.

L2 penalty 계수 λ=0.01이다.

제곱합=3²+4²=25다.

Penalty=0.01×25=0.25다.

전체 목적함수=0.20+0.25=0.45다.

Weight [0,5]도 제곱합 25라 L2 penalty는 같다.

L1은 [3,4]에서 0.01×7=0.07이다.

Penalty의 단위와 평균 기준을 구현과 맞춘다.

| 구분 | 값 또는 책임 |
|---|---|
| 문제 | 첫 확인 |
| 결측 | 발생 주체·비율 |
| 중복 | split 간 identity |
| label 오류 | 작성 기준·합의도 |

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

- Regularization은 data 오류를 자동 수정하지 않는다.
- Dropout을 evaluation에서도 무작위로 켜면 결과가 흔들린다.
- Class weight는 새 minority sample을 만들지 않는다.
- Outlier를 무조건 삭제하면 중요한 rare event를 잃을 수 있다.

## 확인 문제와 해설

### 문제 1

L2가 큰 weight에 더 큰 벌을 주는 이유는?

**해설:** 제곱하므로 크기가 커질수록 penalty가 빠르게 증가한다.

### 문제 2

Dropout의 train/eval 차이는?

**해설:** Training은 일부 activation을 무작위로 끄고 evaluation은 보통 모두 사용하도록 동작을 전환한다.

### 문제 3

Provenance가 필요한 이유는?

**해설:** 오류·권한·변경 원인을 추적하고 재현하기 위해서다.

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

[← 이전](05-training-validation-and-generalization.md) · [목차](README.md) · [다음 →](07-computation-graphs-and-autograd.md)
