"""실제 Linux reclaim을 예측하지 않는 memory account 계산 모형."""

from dataclasses import dataclass


@dataclass
class MemoryState:
    anonymous_mib: int
    clean_file_mib: int
    dirty_file_mib: int
    other_mib: int

    @property
    def current_mib(self):
        return (
            self.anonymous_mib
            + self.clean_file_mib
            + self.dirty_file_mib
            + self.other_mib
        )

    def reclaim_clean(self, amount_mib):
        reclaimed_mib = min(amount_mib, self.clean_file_mib)
        self.clean_file_mib -= reclaimed_mib
        return reclaimed_mib

    def writeback_dirty(self):
        written_mib = self.dirty_file_mib
        self.clean_file_mib += written_mib
        self.dirty_file_mib = 0
        return written_mib


def pressure_label(current_mib, high_mib, max_mib):
    if current_mib > max_mib:
        return "above-max"
    if current_mib > high_mib:
        return "above-high below-max"
    return "at-or-below-high"


def main():
    high_mib = 256
    max_mib = 384
    target_mib = 240
    state = MemoryState(220, 80, 40, 20)

    assert state.current_mib == 360
    assert pressure_label(state.current_mib, high_mib, max_mib) == "above-high below-max"
    print("current=360MiB high=256MiB max=384MiB")
    print("pressure=above-high below-max")

    clean_reclaimed = state.reclaim_clean(state.current_mib - target_mib)
    assert clean_reclaimed == 80
    assert state.current_mib == 280
    print("clean reclaimed=80MiB")

    dirty_written = state.writeback_dirty()
    assert dirty_written == 40
    assert state.dirty_file_mib == 0
    additional_reclaimed = state.reclaim_clean(state.current_mib - target_mib)
    assert additional_reclaimed == 40
    assert state.current_mib == target_mib
    print("dirty writeback then reclaimed=40MiB")
    print("modeled final=240MiB")
    print("model note: not an exact Linux reclaim prediction")


if __name__ == "__main__":
    main()
