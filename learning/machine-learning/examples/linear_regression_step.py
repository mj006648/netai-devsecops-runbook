"""한 점의 선형회귀 SGD 한 step을 확인하는 계산 모델."""

x = 2.0
target = 5.0
weight = 1.0
bias = 0.0
learning_rate = 0.1

prediction = weight * x + bias
error = prediction - target
loss = 0.5 * error**2
grad_weight = error * x
grad_bias = error
new_weight = weight - learning_rate * grad_weight
new_bias = bias - learning_rate * grad_bias
new_prediction = new_weight * x + new_bias
new_loss = 0.5 * (new_prediction - target) ** 2

assert prediction == 2.0
assert loss == 4.5
assert grad_weight == -6.0
assert grad_bias == -3.0
assert abs(new_weight - 1.6) < 1e-12
assert abs(new_bias - 0.3) < 1e-12
assert new_loss < loss

print(f"prediction={prediction:.2f}")
print(f"loss={loss:.2f}")
print(f"grad_weight={grad_weight:.2f}, grad_bias={grad_bias:.2f}")
print(f"new_weight={new_weight:.2f}, new_bias={new_bias:.2f}")
print(f"new_loss={new_loss:.3f}")
