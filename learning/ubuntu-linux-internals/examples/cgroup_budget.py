"""CPU cgroup quota를 순수 계산으로 설명하는 작은 모형."""

from dataclasses import dataclass


@dataclass
class ThreadDemand:
    name: str
    demand_ms: int
    used_ms: int = 0

    @property
    def remaining_ms(self):
        return self.demand_ms - self.used_ms


def run_period(quota_us, period_us, demands, quantum_ms=5):
    """한 period의 공유 CPU 예산을 round-robin 계산으로 나눈다."""
    budget_ms = quota_us // 1000
    trace = []
    while budget_ms > 0 and any(item.remaining_ms > 0 for item in demands):
        progressed = False
        for item in demands:
            if budget_ms == 0:
                break
            use_ms = min(quantum_ms, item.remaining_ms, budget_ms)
            if use_ms == 0:
                continue
            before_ms = budget_ms
            item.used_ms += use_ms
            budget_ms -= use_ms
            progressed = True
            trace.append((item.name, before_ms, use_ms, budget_ms))
        if not progressed:
            break
    remaining_ms = sum(item.remaining_ms for item in demands)
    return {
        "cpu_share": quota_us / period_us,
        "budget_left_ms": budget_ms,
        "remaining_demand_ms": remaining_ms,
        "trace": trace,
    }


def main():
    threads = [ThreadDemand("A", 30), ThreadDemand("B", 30)]
    first = run_period(50_000, 100_000, threads)

    assert first["cpu_share"] == 0.5
    assert first["budget_left_ms"] == 0
    assert first["remaining_demand_ms"] == 10
    assert [item.used_ms for item in threads] == [25, 25]
    assert sum(step[2] for step in first["trace"]) == 50

    print(f"quota/period = {first['cpu_share']:.2f} CPU")
    print("period 1: A=25ms B=25ms throttled-demand=10ms")

    second = run_period(50_000, 100_000, threads)
    assert second["remaining_demand_ms"] == 0
    assert [item.used_ms for item in threads] == [30, 30]
    print("period 2: remaining demand completed")
    print("model note: calculation only; no cgroup was read or changed")


if __name__ == "__main__":
    main()
