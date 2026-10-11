"""교육용 비동기 복제 모델. 실제 저장소 구현이 아니다."""

from dataclasses import dataclass


@dataclass
class Replica:
    name: str
    value: int = 1
    applied_index: int = 0

    def apply(self, index: int, value: int) -> None:
        if index == self.applied_index + 1:
            self.value = value
            self.applied_index = index


leader = Replica("leader")
follower = Replica("follower")

events = [
    (0, "write", leader, 1, 2),
    (5, "read", follower, None, None),
    (20, "replicate", follower, 1, 2),
    (25, "read", follower, None, None),
]

reads: list[tuple[int, int, int]] = []
for tick, kind, replica, index, value in events:
    if kind in {"write", "replicate"}:
        replica.apply(index, value)
    else:
        reads.append((tick, replica.value, replica.applied_index))

assert reads == [(5, 1, 0), (25, 2, 1)]
assert leader.value == follower.value == 2
print("reads:", reads)
print("converged:", leader.value)
