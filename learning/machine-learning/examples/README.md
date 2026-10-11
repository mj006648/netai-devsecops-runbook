# 표준 라이브러리 계산 모델

세 파일은 Python 표준 라이브러리만 사용하며 파일, network, GPU에 접근하지 않는다.

- `linear_regression_step.py`: 회귀 loss, gradient, 한 번의 update
- `softmax_attention_model.py`: 안정화 softmax와 작은 attention
- `split_leakage_model.py`: validation 선택과 반복 test 선택의 누수

각 파일은 고정 입력과 `assert`를 포함한다. 이 결과는 계산 원리 검증이며 학습 성능이나 현장망 검증이 아니다.
