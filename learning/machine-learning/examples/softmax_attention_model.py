"""안정화 softmax와 query-key-value attention 계산 모델."""

import math


def stable_softmax(values):
    maximum = max(values)
    shifted = [value - maximum for value in values]
    exponentials = [math.exp(value) for value in shifted]
    total = sum(exponentials)
    return [value / total for value in exponentials]


query = [1.0, 0.0]
keys = [[1.0, 0.0], [0.0, 1.0]]
values = [[10.0, 0.0], [0.0, 20.0]]
scale = math.sqrt(2.0)
scores = [sum(q * k for q, k in zip(query, key)) / scale for key in keys]
weights = stable_softmax(scores)
output = [
    sum(weights[index] * values[index][axis] for index in range(2))
    for axis in range(2)
]

assert abs(sum(weights) - 1.0) < 1e-12
assert weights[0] > weights[1]
assert abs(output[0] - 6.697615493266566) < 1e-12
assert abs(output[1] - 6.604769013466869) < 1e-12
assert stable_softmax([1000.0, 1000.0]) == [0.5, 0.5]

print("scores=" + ",".join(f"{value:.6f}" for value in scores))
print("weights=" + ",".join(f"{value:.6f}" for value in weights))
print("output=" + ",".join(f"{value:.6f}" for value in output))
