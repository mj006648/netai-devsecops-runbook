"""Validation 선택과 반복 test 선택이 다른 이유를 보이는 계산 모델."""

candidates = {
    "simple": {"validation": 0.20, "test": 0.22},
    "medium": {"validation": 0.15, "test": 0.19},
    "complex": {"validation": 0.17, "test": 0.14},
}

selected = min(candidates, key=lambda name: candidates[name]["validation"])
reported_test = candidates[selected]["test"]
leaky_selection = min(candidates, key=lambda name: candidates[name]["test"])
leaky_test = candidates[leaky_selection]["test"]

assert selected == "medium"
assert reported_test == 0.19
assert leaky_selection == "complex"
assert leaky_test == 0.14
assert selected != leaky_selection

print(f"selected_by_validation={selected}")
print(f"independent_test_error={reported_test:.2f}")
print(f"selected_by_repeated_test={leaky_selection}")
print(f"optimistic_test_error={leaky_test:.2f}")
print("warning=test를 선택에 사용하면 더 이상 독립 평가가 아니다")
