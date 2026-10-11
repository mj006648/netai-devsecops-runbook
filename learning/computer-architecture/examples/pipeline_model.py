"""5단계의 상태를 갱신해 load-use 대기를 계산하는 교육 모형.

모든 단계는 한 주기, 메모리 적중을 가정한다. ALU 결과는 전달할 수 있고
LOAD 결과는 MEM 끝에 준비된다. 레지스터 값·실제 CPU 성능은 계산하지 않는다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Instruction:
    name: str
    kind: str
    destination: str
    sources: tuple[str, ...]


def simulate(program):
    stages = ("IF", "ID", "EX", "MEM", "WB")
    pipeline = dict.fromkeys(stages)
    pipeline["IF"] = program[0] if program else None
    next_instruction = 1
    timeline = {item.name: {stage: [] for stage in stages} for item in program}
    bubble_cycles = []
    cycle = 1
    while any(item is not None for item in pipeline.values()):
        for stage, instruction in pipeline.items():
            if instruction is not None:
                timeline[instruction.name][stage].append(cycle)
        producer, consumer = pipeline["EX"], pipeline["ID"]
        load_use = (producer is not None and consumer is not None
                    and producer.kind == "LOAD"
                    and producer.destination in consumer.sources)
        new_pipeline = {"WB": pipeline["MEM"], "MEM": pipeline["EX"]}
        if load_use:
            new_pipeline.update(EX=None, ID=pipeline["ID"], IF=pipeline["IF"])
            bubble_cycles.append(cycle + 1)
        else:
            fetched = program[next_instruction] if next_instruction < len(program) else None
            next_instruction += fetched is not None
            new_pipeline.update(EX=pipeline["ID"], ID=pipeline["IF"], IF=fetched)
        pipeline = new_pipeline
        cycle += 1
    return timeline, bubble_cycles


def main():
    program = [
        Instruction("LW x1,0(x2)", "LOAD", "x1", ("x2",)),
        Instruction("ADD x3,x1,x4", "ALU", "x3", ("x1", "x4")),
        Instruction("SUB x5,x3,x6", "ALU", "x5", ("x3", "x6")),
    ]
    timeline, bubbles = simulate(program)
    assert bubbles == [4]
    assert timeline[program[0].name]["MEM"] == [4]
    assert timeline[program[1].name]["ID"] == [3, 4]
    assert timeline[program[1].name]["EX"] == [5]
    assert timeline[program[2].name]["WB"] == [8]
    independent = [program[0], Instruction("ADD x3,x7,x4", "ALU", "x3", ("x7", "x4"))]
    assert simulate(independent)[1] == []
    print("한 주기 대기 때문에 생긴 EX 빈 주기:", bubbles)
    for name, trace in timeline.items():
        print(name, trace)


if __name__ == "__main__":
    main()
