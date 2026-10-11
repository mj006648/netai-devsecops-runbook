"""교육용 재시도·중복 제거 모델. 실제 결제 시스템이 아니다."""

from dataclasses import dataclass, field


@dataclass
class AccountService:
    balance: int = 1_000
    executions: int = 0
    results: dict[str, int] = field(default_factory=dict)

    def debit(self, request_id: str, amount: int) -> int:
        if request_id in self.results:
            return self.results[request_id]
        if amount > self.balance:
            raise ValueError("insufficient balance")
        self.balance -= amount
        self.executions += 1
        self.results[request_id] = self.balance
        return self.balance


service = AccountService()
first_result = service.debit("R42", 100)
# 성공 응답이 유실됐다고 가정하고 같은 ID로 다시 호출한다.
retry_result = service.debit("R42", 100)

assert first_result == retry_result == 900
assert service.balance == 900
assert service.executions == 1
assert service.results == {"R42": 900}
print("balance:", service.balance)
print("executions:", service.executions)
