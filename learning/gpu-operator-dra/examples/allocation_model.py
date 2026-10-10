"""Toy allocation model, not Kubernetes or NVIDIA driver implementation."""

from dataclasses import dataclass
from itertools import permutations


@dataclass(frozen=True)
class Device:
    node: str
    name: str
    memory_gib: int


@dataclass(frozen=True)
class Request:
    name: str
    min_memory_gib: int


def allocate(devices, requests, reserved):
    for node in sorted({device.node for device in devices}):
        available = [
            device for device in devices
            if device.node == node and device.name not in reserved
        ]
        for selected in permutations(available, len(requests)):
            if all(
                device.memory_gib >= request.min_memory_gib
                for request, device in zip(requests, selected)
            ):
                return node, dict(zip((request.name for request in requests), selected))
    return None


def describe(name, allocation):
    if allocation is None:
        print(f"{name}: unsatisfied")
        return
    node, assignments = allocation
    choices = " ".join(f"{request}={device.name}" for request, device in assignments.items())
    print(f"{name}: node={node} {choices}")


def main():
    devices = [
        Device("node-b", "demo-80", 80),
        Device("node-a", "demo-48", 48),
        Device("node-a", "demo-24", 24),
    ]
    requests = [Request("high", 40), Request("low", 20)]
    reserved = set()
    first = allocate(devices, requests, reserved)
    assert first is not None
    assert first[0] == "node-a"
    assert first[1]["high"].name == "demo-48"
    assert first[1]["low"].name == "demo-24"
    describe("case_1", first)
    impossible = allocate(devices, [Request("high", 40), Request("low", 40)], reserved)
    assert impossible is None
    describe("case_2", impossible)
    selected_names = {device.name for device in first[1].values()}
    reserved.update(selected_names)
    during_use = allocate(devices, requests, reserved)
    assert during_use is None
    describe("case_3", during_use)
    reserved.difference_update(selected_names)
    again = allocate(devices, requests, reserved)
    assert again == first
    describe("after_release", again)


if __name__ == '__main__':
    main()
