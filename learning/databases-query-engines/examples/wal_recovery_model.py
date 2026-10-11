"""WAL redo 순서를 설명하는 메모리 전용 교육 모델."""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Page:
    value: int
    page_lsn: int


@dataclass(frozen=True)
class WalRecord:
    txid: int
    lsn: int
    value: int


def recover(page: Page, records: tuple[WalRecord, ...],
            committed: frozenset[int]) -> Page:
    result = page
    for record in sorted(records, key=lambda item: item.lsn):
        if record.txid in committed and record.lsn > result.page_lsn:
            result = replace(result, value=record.value, page_lsn=record.lsn)
    return result


disk_page = Page(value=50, page_lsn=10)
wal = (WalRecord(1, 11, 60), WalRecord(2, 12, 70))
recovered = recover(disk_page, wal, committed=frozenset({1}))

assert disk_page == Page(50, 10)
assert recovered == Page(60, 11)
assert recover(recovered, wal, frozenset({1})) == recovered
print("recovered page:", recovered)
