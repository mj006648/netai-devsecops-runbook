# 13. 로컬 계산 모델

[← 이전](12-ai-ran-and-operational-evaluation.md) · [목차](README.md) · [다음 →](14-experiments-and-research.md)

이 장은 표준 Python 계산 모델 세 개로 손계산을 다시 확인한다.

고정 입력과 assert는 계산 결과의 퇴행을 잡는다.

이 실행은 학습 성능, GPU 성능, 현장망 검증이 아니다.

## 이 장의 목표

1. 처음 나오는 단어와 기호를 설명한다.
2. 작은 입력의 모든 중간값을 계산한다.
3. 계산 결과와 실제 system 주장을 구분한다.

![13. 로컬 계산 모델 도식](assets/learning-map.svg)

## 기본 단어와 기호

**standard library**는 Python에 기본 포함된 library이다.

**deterministic**는 같은 입력에서 같은 결과이다.

**assert**는 조건이 틀리면 실행을 실패시키는 검사이다.

**regression step**는 회귀 parameter 한 번 갱신이다.

**stable softmax**는 최댓값을 빼 overflow를 줄인 softmax이다.

**attention model**는 Q K V 가중합 계산이다.

**split model**는 validation과 test 책임 모형이다.

**expected output**는 고정 입력의 예상 결과이다.

**tolerance**는 floating point 비교 허용 오차이다.

**unit test**는 작은 동작을 자동 확인이다.

**simulation**는 현상을 단순화한 모형이다.

**empirical evidence**는 실제 관측으로 얻은 증거이다.

## 왜 필요한가

- 손계산과 code가 같아야 설명을 신뢰할 수 있다.
- Assert는 조용히 틀린 숫자를 출력하는 것을 막는다.
- Floating point는 정확한 십진 표현이 아닐 수 있어 tolerance를 쓴다.
- 작은 모형을 실제 model benchmark로 확대하면 안 된다.

## 입력에서 결과까지

1. README에서 각 파일의 목적을 읽는다.
2. 고정 입력과 식을 손으로 계산한다.
3. Code에서 같은 중간값을 찾는다.
4. Assert가 어떤 불변조건을 검사하는지 읽는다.
5. 출력의 반올림 자리와 내부 값을 구분한다.
6. 입력 하나만 바꿔 결과를 예측한다.
7. 실행 결과와 예측을 비교한다.
8. 현장 검증에 필요한 누락 요소를 적는다.

```mermaid
flowchart LR
 H[손계산] --> P[표준 Python 모델]
 P --> A[assert 불변조건]
 A --> O[고정 출력]
 O --> C[설명과 대조]
 C --> B[현장 검증과 경계 표시]
```

## 작은 숫자로 한 번 계산하기

회귀 예제 처음 prediction=2.00이다.

처음 loss=4.50이다.

Gradient는 w=-6, b=-3이다.

새 w=1.6, b=0.3이다.

새 loss=1.125로 줄었다.

Attention weight 합은 1이다.

Split 예제는 validation으로 medium을 선택한다.

Medium 독립 test error는 0.19다.

Test로 다시 고른 0.14는 낙관적 선택 결과다.

| 구분 | 값 또는 책임 |
|---|---|
| 회귀 파일 | loss와 update |
| attention 파일 | 안정화 softmax |
| split 파일 | test 누수 |
| 외부 I/O | 없음 |

## Shape·단위·시각 점검

입력 shape를 적는다.

각 축이 sample, channel, sequence 중 무엇인지 적는다.

숫자의 단위가 dB, ms, byte, 무차원 중 무엇인지 적는다.

Model이 값을 읽는 시각에 실제로 알 수 있었는지 확인한다.

평균의 분모가 sample인지 token인지 요청인지 적는다.

Parameter와 관측값을 구분한다.

## 구현에서 달라지는 것

Library는 여러 연산을 합쳐 실행할 수 있다.

Memory allocator와 queue가 추가 지연을 만든다.

Finite precision 때문에 손계산과 마지막 자리에서 다를 수 있다.

Version이 바뀌면 API 기본값이 달라질 수 있다.

따라서 식, code, 실행 환경을 함께 기록한다.

## 흔한 오해와 반례

- Assert 통과는 algorithm 전체 정확성 증명이 아니다.
- 고정 입력 성공은 일반화 성능이 아니다.
- Stdlib 예제는 accelerator benchmark가 아니다.
- Test 선택 예제의 0.14를 최종 성능으로 보고하지 않는다.

## 확인 문제와 해설

### 문제 1

Assert의 역할은?

**해설:** 예상 조건이 깨지면 즉시 실패시켜 계산 회귀를 드러낸다.

### 문제 2

Tolerance가 필요한 이유는?

**해설:** Floating point 반올림으로 수학적으로 같은 값도 bit 수준에서 다를 수 있기 때문이다.

### 문제 3

로컬 예제가 증명하지 못하는 것은?

**해설:** 실제 data 일반화, GPU 성능, 현장 RAN QoS다.

## 실행 파일

- [선형회귀 한 step](examples/linear_regression_step.py)
- [안정화 softmax와 attention](examples/softmax_attention_model.py)
- [분할과 test 누수](examples/split_leakage_model.py)

## 학습 체크리스트

- 용어를 자신의 말로 설명할 수 있는가?
- 중간 숫자를 계산할 수 있는가?
- 누가 값을 바꾸는지 말할 수 있는가?
- 반례와 실패 조건을 말할 수 있는가?
- 독립 test와 운영 평가를 구분하는가?

## 공식 자료

- [ISLP 2023](https://www.statlearning.com/home)
- [Dive into Deep Learning](https://d2l.ai/)

공식 근거 확인일: **2026-10-11**.

[← 이전](12-ai-ran-and-operational-evaluation.md) · [목차](README.md) · [다음 →](14-experiments-and-research.md)
