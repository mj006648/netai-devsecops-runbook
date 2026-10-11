"""같은 키 식별자 아래 nonce 중복을 거부하는 교육 모형."""

from dataclasses import dataclass, field


@dataclass
class NonceRegistry:
    used: dict[str, set[int]] = field(default_factory=dict)

    def reserve(self, key_id: str, nonce: int) -> bool:
        """처음 본 (키, nonce)이면 기록하고 True를 반환한다."""
        if nonce < 0:
            raise ValueError("nonce는 음수가 될 수 없습니다")
        key_nonces = self.used.setdefault(key_id, set())
        if nonce in key_nonces:
            return False
        key_nonces.add(nonce)
        return True


def main() -> None:
    registry = NonceRegistry()
    events = [("key-A", 0), ("key-A", 1), ("key-B", 0), ("key-A", 0)]
    results = [registry.reserve(key, nonce) for key, nonce in events]
    assert results == [True, True, True, False]
    assert registry.used == {"key-A": {0, 1}, "key-B": {0}}
    for event, result in zip(events, results):
        print(f"{event} -> {'예약 성공' if result else '중복 거부'}")


if __name__ == "__main__":
    main()
