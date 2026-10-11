# 00. 학습과 연구 지도

[← 이전](README.md) · [목차](README.md) · [다음 →](01-vectors-matrices-and-probability.md)

머신러닝은 data에서 규칙을 추정해 새 입력의 결과를 예측하는 방법이다.

이 장은 문제 정의에서 독립 평가까지의 전체 지도를 만든다.

작은 계산이 맞는 것과 실제 환경에서 유용한 것은 다른 주장이다.

## 이 장의 목표

1. 새 용어와 수학 기호를 말로 설명한다.
2. 입력이 중간 숫자를 거쳐 결과가 되는 과정을 계산한다.
3. 계산 모형과 실제 성능 주장을 구분한다.

![00. 학습과 연구 지도 도식](assets/learning-map.svg)

## 기본 단어와 기호

**data**는 관측하거나 만든 값의 모음이다.

**sample**는 데이터 한 행 또는 한 사례이다.

**feature**는 예측 입력으로 쓰는 값이다.

**label**는 맞히려는 정답이다.

**model**는 입력을 출력으로 바꾸는 함수이다.

**parameter**는 학습으로 바뀌는 모델 내부 숫자이다.

**loss**는 예측 오차를 하나의 숫자로 나타낸 값이다.

**training**는 loss를 줄이도록 parameter를 바꾸는 과정이다.

**inference**는 학습된 모델로 새 입력을 예측하는 과정이다.

**validation**는 모델과 설정을 고르는 평가이다.

**test**는 선택이 끝난 뒤 한 번 쓰는 독립 평가이다.

**baseline**는 비교 대상인 단순 규칙이나 기존 방법이다.

기호를 읽을 때 이름, shape, 단위, 생성 주체를 함께 적는다.

## 왜 필요한가

- 문제 문장을 입력과 결과로 바꾸지 않으면 모델이 무엇을 배워야 하는지 정할 수 없다.
- 정확도 하나만 보면 드문 위험 사례를 놓칠 수 있다.
- 데이터 생성 시각과 배포 시각이 다르면 미래 정보 누수가 생길 수 있다.
- 연구 질문은 바꾼 조건과 비교 기준을 함께 적어야 한다.

## 입력에서 결과까지

1. 사용자가 해결할 현상을 한 문장으로 정의한다.
2. 측정 주체가 원시 데이터를 수집한다.
3. 데이터 담당자가 feature와 label의 단위·시각을 고정한다.
4. 분할 담당자가 training, validation, test를 분리한다.
5. 학습 code가 training loss로 parameter를 바꾼다.
6. 연구자가 validation으로 후보를 선택한다.
7. 선택을 끝낸 뒤 test를 한 번 평가한다.
8. 운영자는 latency, power, QoS와 drift를 관측한다.

```mermaid
flowchart LR
 D[원시 데이터] --> S[학습·검증·시험 분할]
 S --> T[학습: 매개변수 변경]
 T --> V[검증: 후보 선택]
 V --> X[독립 시험: 최종 평가]
 X --> O[운영: 지연·전력·드리프트]
```

## 작은 숫자로 한 번 계산하기

기준 규칙은 10개 중 6개를 맞혔다.

후보 A는 validation 10개 중 8개를 맞혔다.

후보 B는 validation 10개 중 9개를 맞혔다.

Validation 선택은 후보 B다.

독립 test 20개에서 B는 15개를 맞혔다.

Test accuracy = 15/20 = 0.75 = 75%.

Validation 90%를 최종 성능으로 보고하면 선택 편향을 숨긴다.

표본 20개는 작으므로 uncertainty도 함께 적는다.

| 구분 | 값 또는 책임 |
|---|---|
| 입력 | 원시 sample 100개 |
| 중간 | train 60, validation 20, test 20 |
| 주체 | 학습 code와 평가자 |
| 결과 | 선택된 모델의 독립 test 결과 |

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

- Training loss가 낮다고 새 데이터 성능이 자동으로 좋지 않다.
- 모델이 복잡할수록 항상 우수하지 않다.
- Test를 반복해 고르면 test도 validation처럼 오염된다.
- 작은 Python 계산은 현장 성능 검증이 아니다.

## 확인 문제와 해설

### 문제 1

Feature와 label의 차이는?

**해설:** Feature는 예측 시 알 수 있는 입력이고 label은 맞히려는 목표다.

### 문제 2

Validation과 test를 왜 나누는가?

**해설:** Validation은 선택에 사용되어 그 선택에 적응한다. Test는 선택 뒤의 독립 평가를 위해 남긴다.

### 문제 3

Baseline이 필요한 이유는?

**해설:** 복잡한 모델의 추가 비용이 단순 규칙보다 실제로 나은지 확인하기 위해서다.

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

[← 이전](README.md) · [목차](README.md) · [다음 →](01-vectors-matrices-and-probability.md)
