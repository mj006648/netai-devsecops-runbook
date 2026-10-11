"""실제 io_uring 호출 없이 요청과 buffer 수명을 설명하는 모형."""

from dataclasses import dataclass
from enum import Enum, auto


class State(Enum):
    SUBMITTED = auto()
    COMPLETED = auto()
    CANCELLED = auto()


@dataclass
class Request:
    request_id: int
    buffer_name: str
    requested_bytes: int
    state: State = State.SUBMITTED
    released: bool = False

    def finish(self, result):
        if self.state is not State.SUBMITTED:
            raise RuntimeError("요청이 이미 terminal 상태입니다")
        self.state = State.CANCELLED if result == -125 else State.COMPLETED
        return "errno" if result < 0 else "bytes"

    def release_once(self):
        if self.released:
            raise RuntimeError("buffer를 두 번 해제할 수 없습니다")
        if self.state is State.SUBMITTED:
            raise RuntimeError("matching completion 전에 해제할 수 없습니다")
        self.released = True


class RingModel:
    def __init__(self):
        self.pending = {}
        self.release_log = []

    def submit(self, request):
        if request.request_id in self.pending:
            raise ValueError("request ID가 중복되었습니다")
        self.pending[request.request_id] = request

    def complete(self, request_id, result):
        if request_id not in self.pending:
            raise KeyError("알 수 없는 completion ID입니다")
        request = self.pending.pop(request_id)
        result_kind = request.finish(result)
        request.release_once()
        self.release_log.append(request.buffer_name)
        return request, result_kind


def illustrate_cancel_race(target_already_completed):
    """Cancel 요청과 대상 완료의 두 순서를 terminal state로 단순화한다."""
    if target_already_completed:
        return "target completion owns final release"
    return "cancelled target completion owns final release"


def main():
    ring = RingModel()
    ring.submit(Request(101, "buf-A", 4096))
    ring.submit(Request(102, "buf-B", 2048))
    print("submitted ids: [101, 102]")

    request_102, kind_102 = ring.complete(102, 2048)
    assert kind_102 == "bytes"
    assert request_102.released
    print("completion 102: bytes=2048 release=buf-B")

    request_101, kind_101 = ring.complete(101, -22)
    assert kind_101 == "errno"
    assert request_101.released
    assert ring.release_log == ["buf-B", "buf-A"]
    assert not ring.pending
    print("completion 101: errno=EINVAL release=buf-A")

    assert illustrate_cancel_race(True) == "target completion owns final release"
    assert illustrate_cancel_race(False) == "cancelled target completion owns final release"
    print("cancel race: target terminal state owns final release")
    print("model note: this is not a real io_uring call")


if __name__ == "__main__":
    main()
