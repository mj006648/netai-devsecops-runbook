"""검색과 안정 병합 정렬의 작은 정확성 예제.

이 assert들은 선택한 입력만 확인한다. 성능 측정이나 모든 입력에 대한
증명이 아니다.
"""


def binary_search(keys, target):
    """포함 경계를 사용해 (위치 또는 None, 추적값)을 반환한다."""
    lo, hi = 0, len(keys) - 1
    trace = []
    while lo <= hi:
        mid = (lo + hi) // 2
        trace.append((lo, mid, hi))
        if keys[mid] == target:
            return mid, trace
        if keys[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return None, trace


def stable_merge(left, right):
    """Key가 같으면 왼쪽 record를 골라 안정적으로 병합한다."""
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i][0] <= right[j][0]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def merge_sort(records):
    if len(records) <= 1:
        return list(records)
    mid = len(records) // 2
    return stable_merge(merge_sort(records[:mid]), merge_sort(records[mid:]))


def run_examples():
    keys = [3, 8, 12, 20, 31, 44, 57, 91]
    index, trace = binary_search(keys, 44)
    assert index == 5
    assert trace == [(0, 3, 7), (4, 5, 7)]

    missing, missing_trace = binary_search(keys, 43)
    assert missing is None
    assert missing_trace == [(0, 3, 7), (4, 5, 7), (4, 4, 4)]
    assert binary_search([], 1) == (None, [])

    records = [(3, "A"), (1, "B"), (3, "C"), (2, "D")]
    assert merge_sort(records) == [(1, "B"), (2, "D"), (3, "A"), (3, "C")]
    assert merge_sort([]) == []


if __name__ == "__main__":
    run_examples()
    print("search_sort_lab: 선택한 정확성 예제가 통과했습니다")
