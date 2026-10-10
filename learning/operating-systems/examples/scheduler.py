"""작은 CPU scheduling 모형.

실제 Linux scheduler의 성능이나 정책을 재현하지 않는다.
"""

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    name: str
    arrival: int
    burst: int


JOBS = (Job("A", 0, 5), Job("B", 1, 2), Job("C", 2, 1))


def summarize(timeline: list[str], jobs: tuple[Job, ...]) -> None:
    finish: dict[str, int] = {}
    first: dict[str, int] = {}
    for tick, name in enumerate(timeline):
        if name == "-":
            continue
        first.setdefault(name, tick)
        finish[name] = tick + 1
    print("timeline:", " ".join(timeline))
    for job in jobs:
        turnaround = finish[job.name] - job.arrival
        response = first[job.name] - job.arrival
        waiting = turnaround - job.burst
        print(job.name, "turnaround", turnaround, "waiting", waiting, "response", response)


def nonpreemptive(key) -> list[str]:
    time = 0
    pending = list(JOBS)
    timeline: list[str] = []
    while pending:
        ready = [job for job in pending if job.arrival <= time]
        if not ready:
            timeline.append("-")
            time += 1
            continue
        job = min(ready, key=key)
        timeline.extend([job.name] * job.burst)
        time += job.burst
        pending.remove(job)
    return timeline


def round_robin(quantum: int) -> list[str]:
    if quantum <= 0:
        raise ValueError("quantum은 양의 정수여야 합니다")
    time = 0
    remaining = {job.name: job.burst for job in JOBS}
    ready: deque[Job] = deque()
    admitted: set[str] = set()
    timeline: list[str] = []
    while remaining:
        for job in JOBS:
            if job.arrival <= time and job.name not in admitted:
                ready.append(job)
                admitted.add(job.name)
        if not ready:
            timeline.append("-")
            time += 1
            continue
        job = ready.popleft()
        run = min(quantum, remaining[job.name])
        for _ in range(run):
            timeline.append(job.name)
            time += 1
            for candidate in JOBS:
                if candidate.arrival <= time and candidate.name not in admitted:
                    ready.append(candidate)
                    admitted.add(candidate.name)
        remaining[job.name] -= run
        if remaining[job.name]:
            ready.append(job)
        else:
            del remaining[job.name]
    return timeline


for title, result in (
    ("FCFS", nonpreemptive(lambda job: (job.arrival, job.name))),
    ("SJF", nonpreemptive(lambda job: (job.burst, job.arrival, job.name))),
    ("RR(q=2)", round_robin(2)),
):
    print("\n" + title)
    summarize(result, JOBS)
