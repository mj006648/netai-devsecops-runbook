"""메모리 순서 교육 모형.

실제 CPU나 언어 메모리 모형을 검증하는 도구가 아니다. 첫 모형은 seq_cst에서
가능한 전역 사건 순서를 모두 만들고, 둘째 모형은 relaxed store buffering에서
store buffer 때문에 추가될 수 있는 결과를 명시한다. 셋째는 release/acquire
message passing에서 acquire load가 release store가 쓴 1을 실제로 읽은 경우만
동기화가 성립한다는 조건을 확인한다.
"""

from itertools import permutations


def preserves_program_order(order, before_after):
    """각 스레드의 사건 순서를 보존하는 전역 순서인지 검사한다."""
    position = {event: index for index, event in enumerate(order)}
    return all(position[before] < position[after] for before, after in before_after)


def run_seq_cst_store_buffering(order):
    """x=y=0에서 Sx;Ly와 Sy;Lx를 주어진 전역 순서로 실행한다."""
    memory = {"x": 0, "y": 0}
    reads = {}
    for event in order:
        if event == "Sx":
            memory["x"] = 1
        elif event == "Ly":
            reads["r1"] = memory["y"]
        elif event == "Sy":
            memory["y"] = 1
        elif event == "Lx":
            reads["r2"] = memory["x"]
        else:
            raise ValueError(event)
    return reads["r1"], reads["r2"]


def enumerate_seq_cst_outcomes():
    """프로그램 순서를 지키는 모든 seq_cst 전역 순서와 결과를 반환한다."""
    events = ("Sx", "Ly", "Sy", "Lx")
    program_order = (("Sx", "Ly"), ("Sy", "Lx"))
    traces = {}
    for order in permutations(events):
        if preserves_program_order(order, program_order):
            outcome = run_seq_cst_store_buffering(order)
            traces.setdefault(outcome, []).append(order)
    return traces


def relaxed_store_buffering_outcomes():
    """교육용 store-buffer 모형의 결과 집합.

    각 코어의 store가 자기 buffer에 머문 동안 뒤 load가 다른 주소의 공유
    메모리를 읽을 수 있다고 가정한다. 그래서 둘 다 초기 0을 읽는 실행이
    추가된다. 이는 모든 relaxed 구현의 완전한 형식 모형이라는 뜻이 아니다.
    """
    return {(0, 0), (0, 1), (1, 0), (1, 1)}


def message_passing(flag_read):
    """data=42 뒤 flag=1 release, 반대편의 acquire 관측을 단순화한다.

    flag_read가 1이면 그 값은 release store에서 왔다고 가정한다. 그때
    synchronizes-with와 happens-before가 이어져 data 42가 보여야 한다.
    flag_read가 0이면 동기화가 성립하지 않았으므로 data를 읽어도 된다는
    보장을 이 함수가 만들지 않는다.
    """
    published_data = 42
    if flag_read == 1:
        observed_data = published_data
        assert observed_data == 42
        return observed_data
    return None


def main():
    seq_cst = enumerate_seq_cst_outcomes()
    assert (0, 0) not in seq_cst
    assert set(seq_cst) == {(0, 1), (1, 0), (1, 1)}
    relaxed = relaxed_store_buffering_outcomes()
    assert (0, 0) in relaxed
    assert message_passing(1) == 42
    assert message_passing(0) is None
    print("seq_cst outcomes:", sorted(seq_cst))
    print("relaxed educational outcomes:", sorted(relaxed))
    print("message passing when acquire reads 1: data=42")


if __name__ == "__main__":
    main()
