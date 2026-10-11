"""RAN·AI를 직렬로 배치한 한 창의 시간 예산 모형.

단위는 ms. GPU 측정·실제 scheduler·최악 실행 시간 증명은 아니다.
겹치는 실행을 주장하려면 별도의 간섭·우선순위·preemption 모형이 필요하다.
"""


def decide(window_ms, ran_budget_ms, guard_ms, ai_budget_ms):
    slack_ms = window_ms - ran_budget_ms - guard_ms
    return slack_ms, ai_budget_ms <= slack_ms


if __name__ == "__main__":
    window = 1.0
    ran = 0.6
    guard = 0.1
    print("모형: 1.0 ms 창, RAN 예산 0.6 ms, 보호 여유 0.1 ms")
    for ai in (0.2, 0.5):
        slack, allowed = decide(window, ran, guard, ai)
        print(f"AI {ai:.1f} ms, 여유 {slack:.1f} ms: {'허용' if allowed else '거절'}")
    assert decide(window, ran, guard, 0.2)[1]
    assert not decide(window, ran, guard, 0.5)[1]
    print("평균 실행 시간만으로 최악 지연·deadline 보장을 증명할 수 없다.")
