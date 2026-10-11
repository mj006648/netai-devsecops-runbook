#!/usr/bin/env python3
"""Deterministic interleaving models; not a CPU or C++ memory-model simulator."""

from collections import Counter
from itertools import combinations


def schedules(steps_per_thread):
    """All order-preserving merges for two threads, A and B."""
    size = 2 * steps_per_thread
    for a_slots in combinations(range(size), steps_per_thread):
        a_slots = set(a_slots)
        yield tuple("A" if slot in a_slots else "B" for slot in range(size))


def simulate(schedule, kind):
    value = 0
    local = {"A": None, "B": None}
    progress = {"A": 0, "B": 0}
    trace = []
    for actor in schedule:
        step = progress[actor]
        before = value
        if kind == "split_three":
            if step == 0:
                local[actor] = value
                operation = "read"
            elif step == 1:
                local[actor] += 1
                operation = "add"
            else:
                value = local[actor]
                operation = "write"
        elif kind == "atomic_load_store":
            if step == 0:
                local[actor] = value
                operation = "atomic_load"
            else:
                value = local[actor] + 1
                operation = "atomic_store"
        elif kind in ("atomic_rmw", "mutex_whole_increment"):
            # The entire increment is one indivisible step in these models.
            value += 1
            operation = kind
        else:
            raise ValueError(kind)
        progress[actor] += 1
        trace.append((actor, operation, before, value, local[actor]))
    return value, trace


def run_model(kind, steps, expected):
    outcomes = Counter()
    losing_trace = None
    for order in schedules(steps):
        result, trace = simulate(order, kind)
        outcomes[result] += 1
        if result == 1 and losing_trace is None:
            losing_trace = trace
    assert dict(outcomes) == expected, (kind, outcomes, expected)
    print(f"{kind}: schedules={sum(outcomes.values())}, outcomes={dict(sorted(outcomes.items()))}")
    return losing_trace


def main():
    trace = run_model("split_three", 3, {1: 18, 2: 2})
    run_model("atomic_load_store", 2, {1: 4, 2: 2})
    run_model("atomic_rmw", 1, {2: 2})
    run_model("mutex_whole_increment", 1, {2: 2})
    print("\nOne losing split-three trace (actor op before after local):")
    for row in trace:
        print(*row)
    print("\nSchedule counts are not real-world probabilities.")
    print("This model does not execute an undefined C++ data race.")


if __name__ == "__main__":
    main()
