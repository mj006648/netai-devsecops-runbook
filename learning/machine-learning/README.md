# 머신러닝·딥러닝 원리 교재

이 교재는 수학과 프로그래밍을 처음 접하는 독자가 작은 숫자를 손으로 따라가며 머신러닝과 딥러닝의 원리를 이해하도록 구성한다.

## 읽는 순서

00장부터 15장까지 순서대로 읽는다. 각 장은 단어와 기호, 작은 계산, 운영 반례, 연습문제와 해설을 포함한다.

**자료 확인 기준일: 2026-10-11.** 여기서 모델(model)은 입력으로부터 예측을 계산하는 규칙과 수치의 묶음이다. 가중치(weight)는 그 계산에 쓰는 조절 가능한 값이며, 학습(training)은 데이터로 정한 목적에 맞추어 값을 바꾸는 과정이다. GPU 설치나 실제 망 접근 없이 작은 계산부터 시작한다.

| 장 | 처음 던지는 질문 | 직접 따라갈 일 |
| --- | --- | --- |
| [00. 학습과 연구의 지도](00-learning-and-research-map.md) | 예측·학습·평가는 누가 무엇을 바꾸는가? | 입력·정답·모델·평가의 경계를 그리기 |
| [01. 벡터·행렬·확률](01-vectors-matrices-and-probability.md) | 배열의 숫자와 확률은 어떤 뜻인가? | 행·열과 내적, 조건부 확률을 계산 |
| [02. 선형회귀와 손실](02-linear-regression-and-loss.md) | 예측의 오차를 어떤 값으로 비교할까? | 여러 관측의 오차·MSE·가중치 한 번 갱신 |
| [03. 기울기와 최적화](03-gradients-and-optimization.md) | 어느 값으로 얼마나 이동해야 할까? | 작은 변화량·미분·학습률·과도한 갱신의 반례 |
| [04. 분류와 확률](04-classification-and-probabilities.md) | 숫자 점수를 분류 확률로 어떻게 바꿀까? | 로짓·softmax·손실·임계값을 구별 |
| [05. 학습·검증·일반화](05-training-validation-and-generalization.md) | 본 적 없는 입력에서 잘하는지 어떻게 알까? | 모델 선택용 검증과 독립 시험의 사용 순서 |
| [06. 규제와 데이터 품질](06-regularization-and-data-quality.md) | 데이터에 너무 맞춘 규칙을 어떻게 다룰까? | 복잡도·누수·이상치·데이터 수집 조건의 반례 |
| [07. 계산 그래프와 자동미분](07-computation-graphs-and-autograd.md) | 손실에서 각 가중치로 변화율이 어떻게 전해질까? | 연산별 중간값과 역방향 기울기를 추적 |
| [08. 신경망과 활성화](08-neural-networks-and-activations.md) | 여러 층과 비선형 함수는 왜 필요한가? | 작은 층의 입력·가중합·출력·기울기를 연결 |
| [09. 합성곱과 순서 데이터](09-convolutions-and-sequence-models.md) | 이미지의 이웃과 시간 순서를 어떻게 활용할까? | 필터 위치와 순서별 상태를 따라가기 |
| [10. Attention과 Transformer](10-attention-and-transformers.md) | 입력끼리 관련된 정보를 어떻게 섞을까? | Q·K·V 행렬곱→점수→softmax→가중합 |
| [11. 학습 시스템과 숫자 정밀도](11-training-systems-and-numerical-precision.md) | 학습 모드와 숫자 표현이 무엇을 바꿀까? | dropout·정규화·역전파·FP16/BF16 조건 구별 |
| [12. AI-RAN과 운영 평가](12-ai-ran-and-operational-evaluation.md) | 예측 개선이 무선망의 개선으로 이어질까? | 시점별 데이터·추론 지연·전력·QoS 비교 |
| [13. 로컬 계산 모델](13-local-models.md) | 손 계산을 코드로 어디까지 확인할까? | 회귀·attention·평가 데이터 누수의 모형 실행 |
| [14. 실험과 연구](14-experiments-and-research.md) | 개선의 이유를 어떤 비교로 보여 줄까? | 기준군·반복·품질·실패·재현 조건 설계 |
| [15. 종합 문제·용어·출처](15-exercises-glossary-and-sources.md) | 용어를 실제 계산과 판단에 쓸 수 있는가? | 해설 문제를 풀고 모르는 단어를 본문과 연결 |

첫 경로는 **00→01→02→03→04→05**다. 손실이 왜 줄었는지 설명할 수 있으면 **07→08→09→10**에서 계산 구조를 확장한다. 연구에서는 **06·11·12·14**로 데이터와 실제 운영 조건을 다시 점검한다. 문제 해설은 직접 답을 적은 뒤 읽는다.

## 중요한 경계

- 계산 모형의 성공은 실제 학습 성능이나 현장망 성능의 증거가 아니다.
- Validation은 모델 선택에 쓰고 독립 test는 마지막 평가에 쓴다.
- Logit은 확률이 아니며 softmax 같은 변환과 해석 조건이 필요하다.
- 자동미분은 gradient를 계산하고 optimizer가 parameter를 갱신한다.
- AI-RAN 평가는 정확도뿐 아니라 지연, 전력, QoS와 안전한 fallback을 본다.

## 보조 자료

- [도식](assets/README.md)
- [표준 라이브러리 계산 모델](examples/README.md)

| 계산 모델 | 확인하는 예 | 별도로 남는 질문 |
| --- | --- | --- |
| [선형회귀 한 단계](examples/linear_regression_step.py) | 예측·손실·기울기·갱신 후 손실 계산 | 새 데이터에서 품질이 좋아지는가? |
| [Softmax attention](examples/softmax_attention_model.py) | 점수·행별 가중치·값의 합·큰 점수의 안정화 | 학습된 Transformer가 어떤 과제에서 좋은가? |
| [평가 데이터 누수](examples/split_leakage_model.py) | 검증으로 선택하는 경우와 시험으로 선택하는 경우 | 실제 표본에서 선택 편향의 크기는 얼마인가? |

이 계산 모형은 고정된 교육용 입력을 쓴다. 출력이 맞는다는 사실과 실제 데이터·GPU·현장망에서 좋은 성능을 얻었다는 사실은 다른 증거가 필요하다.

모델 실행을 서비스로 연결하려면 [AI 인프라](../../ai/learning/ai-infrastructure/README.md), GPU의 스레드·메모리·동기화는 [GPU 병렬 프로그래밍](../gpu-programming/README.md), 무선망의 자원과 제어는 [무선통신·AI-RAN](../wireless-communications/README.md)으로 이어간다.

[통합 교재 목차](../README.md) · [첫 장 읽기](00-learning-and-research-map.md)
