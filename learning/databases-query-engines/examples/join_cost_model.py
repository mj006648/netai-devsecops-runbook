"""조인 비용의 크기 차이를 보이는 고정 입력 교육 모델."""
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class JoinEstimate:
    outer_rows: int
    inner_rows: int
    build_row_bytes: int
    memory_bytes: int

    @property
    def nested_loop_comparisons(self) -> int:
        return self.outer_rows * self.inner_rows

    @property
    def hash_key_operations(self) -> int:
        return self.outer_rows + self.inner_rows

    @property
    def hash_bytes(self) -> int:
        return self.inner_rows * self.build_row_bytes

    @property
    def hash_batches(self) -> int:
        return ceil(self.hash_bytes / self.memory_bytes)


case = JoinEstimate(outer_rows=10_000, inner_rows=100_000,
                    build_row_bytes=64, memory_bytes=2_000_000)
assert case.nested_loop_comparisons == 1_000_000_000
assert case.hash_key_operations == 110_000
assert case.hash_bytes == 6_400_000
assert case.hash_batches == 4
assert case.nested_loop_comparisons > case.hash_key_operations

print("nested-loop comparisons:", case.nested_loop_comparisons)
print("hash key operations:", case.hash_key_operations)
print("estimated hash batches:", case.hash_batches)
