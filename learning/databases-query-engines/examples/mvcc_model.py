"""명시적 commit 집합을 쓰는 결정적 MVCC 교육 모델.

PostgreSQL 튜플 헤더의 상태 비트, XID wraparound, subtransaction을 구현하지
않는다. 진행 중이 아니라는 사실을 commit으로 간주하지 않는 것이 핵심이다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    committed: frozenset[int]
    self_xid: int


@dataclass(frozen=True)
class Version:
    value: int
    creator: int
    ended: int | None = None


def visible(version: Version, snapshot: Snapshot) -> bool:
    creator_visible = (
        version.creator == snapshot.self_xid
        or version.creator in snapshot.committed
    )
    if not creator_visible:
        return False

    if version.ended is None:
        return True

    ended_visible = (
        version.ended == snapshot.self_xid
        or version.ended in snapshot.committed
    )
    return not ended_visible


old = Version(value=100, creator=10, ended=30)
new = Version(value=80, creator=30)
old_snapshot = Snapshot(committed=frozenset({10}), self_xid=20)
new_snapshot = Snapshot(committed=frozenset({10, 30}), self_xid=40)

assert visible(old, old_snapshot)
assert not visible(new, old_snapshot)
assert not visible(old, new_snapshot)
assert visible(new, new_snapshot)
assert [v.value for v in (old, new) if visible(v, old_snapshot)] == [100]
assert [v.value for v in (old, new) if visible(v, new_snapshot)] == [80]

# XID 50은 진행 중 집합에서 사라졌더라도 committed에 없으면 aborted일 수 있다.
aborted = Version(value=999, creator=50)
assert not visible(aborted, new_snapshot)

# 자기 트랜잭션이 만든 미커밋 버전은 본인에게만 보인다.
self_version = Version(value=70, creator=40)
other_snapshot = Snapshot(committed=frozenset({10, 30}), self_xid=41)
assert visible(self_version, new_snapshot)
assert not visible(self_version, other_snapshot)

print("old snapshot:", [v.value for v in (old, new) if visible(v, old_snapshot)])
print("new snapshot:", [v.value for v in (old, new) if visible(v, new_snapshot)])
