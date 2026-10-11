"""교육용 Raft 커밋 판정 모델. 선거·RPC를 포함한 전체 Raft가 아니다."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    index: int
    term: int
    command: str


logs = {
    "A": [Entry(1, 2, "x=1"), Entry(2, 4, "y=1")],
    "B": [Entry(1, 2, "x=1"), Entry(2, 4, "y=1")],
    "C": [Entry(1, 2, "x=1")],
}
current_term = 4
majority = len(logs) // 2 + 1


def committed_index() -> int:
    candidates = sorted({e.index for log in logs.values() for e in log}, reverse=True)
    for index in candidates:
        copies = sum(any(e.index == index and e.term == current_term for e in log) for log in logs.values())
        if copies >= majority:
            return index
    return 0


commit_index = committed_index()
committed_prefix = [entry for entry in logs["A"] if entry.index <= commit_index]
assert commit_index == 2
assert [e.command for e in committed_prefix] == ["x=1", "y=1"]
assert committed_prefix[0].term < current_term  # 과거 항목은 현재 term 항목과 함께 간접 커밋
print("commit_index:", commit_index)
print("committed:", [e.command for e in committed_prefix])
