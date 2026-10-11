# 04. 파이프라인·의존성·결과 전달

[← 이전](03-functions-abi-and-program-loading.md) · [목차](README.md) · [다음 →](05-branches-out-of-order-and-retirement.md)

**파이프라인**은 명령 처리를 여러 단계로 나누고 서로 다른 명령의 단계를 겹쳐 실행하는 구조다. 목적은 명령 하나의 결과를 무조건 빨리 만드는 것이 아니라 단위 시간에 더 많은 명령을 완료하는 것이다.

![pipeline](assets/pipeline.svg)

## 먼저 알아야 할 실행 단어

**PC(Program Counter, 프로그램 카운터)**는 CPU가 다음에 읽을 명령이 놓인 주소를 기억하는 프로그램 상태다. 여기서 주소는 메모리 안의 위치를 나타내는 숫자다. IF 단계는 PC를 입력으로 받아 그 위치의 명령 바이트를 읽고, 순차 실행이라면 명령 길이만큼 더한 다음 주소 후보도 만든다.

**opcode(연산 코드)**는 명령 바이트 안에서 “더하기, 읽기, 저장하기, 분기하기”처럼 할 일의 종류를 나타내는 부분이다. **operand(피연산자)**는 그 일이 사용할 값이나 값의 위치다. ADD x1,x2,x3에서 x2와 x3가 입력 피연산자이고 x1이 결과를 받을 목적지다.

**immediate(즉시값)**는 별도 register에서 읽지 않고 명령 바이트 안에 직접 들어 있는 작은 상수다. ADDI x1,x2,5의 5가 즉시값이다. decode 단계는 명령의 여러 bit 위치에서 immediate를 모으고 부호를 해석해 실행 단계가 쓸 값으로 만든다.

**control signal(제어 신호)**은 해독 결과를 실제 회로 행동으로 바꾸는 내부 지시다. “ALU는 덧셈을 선택한다”, “이 명령은 memory를 읽는다”, “마지막에 register를 쓴다” 같은 정보다. 잘못된 경로를 flush하거나 bubble을 넣을 때에는 이 신호를 꺼서 register와 memory가 바뀌지 않게 한다.

**ALU(산술논리장치)**는 정수 덧셈, 뺄셈, 비교, bit 논리를 수행하는 실행 회로다. 주소 계산도 덧셈이므로 EX 단계의 ALU나 별도 주소 생성 장치가 base address와 offset을 더할 수 있다.

**프로그램에 보이는 register 상태**는 instruction이 정상적으로 끝났을 때 다음 instruction과 debugger가 관찰하는 register 값이다. pipeline register 안의 중간값은 CPU 내부 구현 상태라 프로그램이 이름으로 직접 읽을 수 없다. 이 구분이 있어야 잘못 예측한 명령의 내부 계산을 버리면서도 프로그램 결과를 순차 실행과 같게 유지할 수 있다.

## 1. 교육용 5단계

| 단계 | 이름 | 입력 | 일 | 다음 단계 값 |
|---|---|---|---|---|
| IF | Instruction Fetch | PC | instruction byte와 순차 PC 후보 | instruction, PC |
| ID | Decode/Register Read | instruction | opcode·field 해독, register 읽기 | operand, immediate, control |
| EX | Execute | operand | ALU, branch 비교, 주소 계산 | 결과 또는 주소 |
| MEM | Memory Access | 주소·store data | data cache load/store | load value 또는 ALU result |
| WB | Write Back | 최종 결과 | 목적 register 기록 | 프로그램에 보이는 register 갱신 |

단계 사이 **pipeline register**는 한 cycle 결과를 잡아 다음 cycle 입력으로 준다. 실제 제품의 단계 수와 latch 내용은 다르다.

~~~mermaid
flowchart LR
 P[PC] --> IF[IF]
 IF --> A[IF/ID]
 A --> ID[ID]
 ID --> B[ID/EX]
 B --> EX[EX]
 EX --> C[EX/MEM]
 C --> MEM[MEM]
 MEM --> D[MEM/WB]
 D --> WB[WB]
~~~

## 2. latency와 throughput

서로 독립인 세 명령을 보자.

~~~text
I1: add x1, x2, x3
I2: sub x4, x5, x6
I3: and x7, x8, x9
~~~

| cycle | I1 | I2 | I3 |
|---:|---|---|---|
| 1 | IF |  |  |
| 2 | ID | IF |  |
| 3 | EX | ID | IF |
| 4 | MEM | EX | ID |
| 5 | WB | MEM | EX |
| 6 |  | WB | MEM |
| 7 |  |  | WB |

한 명령 latency는 5cycle이지만 채워진 뒤 throughput은 cycle당 한 명령이다. single-cycle CPU의 cycle이 0.9ns이고 pipeline cycle이 0.25ns라면 첫 명령 latency는 1.25ns로 더 길 수 있다. 그러나 100개 흐름은 pipeline이 약 104×0.25=26ns, single-cycle이 90ns다. fill, drain, stall, register overhead까지 비교해야 한다.

## 3. dependency와 hazard

**dependency**는 프로그램 의미상 값·순서 관계다. **hazard**는 현재 구현이 그대로 진행하면 정답을 보장하지 못하는 상황이다.

- RAW: 뒤 명령이 앞 write 결과를 읽는다. 참 data dependency다.
- WAR: 뒤 write가 앞 read보다 먼저 될 위험인 anti-dependency다.
- WAW: 같은 목적에 대한 write 순서가 뒤집힐 output dependency다.

in-order 5단계는 ID에서 순서대로 읽고 WB에서 순서대로 쓰므로 WAR와 WAW가 보통 생기지 않는다. RAW는 결과가 WB 전에 필요해 발생한다. 비순차 CPU는 WAR와 WAW를 피하려고 같은 프로그램 register 이름의 서로 다른 version에 별도 physical register를 할당하는 **register renaming**을 사용한다.

## 4. RAW가 틀린 값을 만드는 trace

~~~text
I1: add x1, x2, x3    # 7+5=12
I2: sub x4, x1, x5    # x5=2, 정답 10
~~~

forwarding과 stall이 없다면 I2는 cycle 3 ID에서 과거 x1을 읽는데 I1은 cycle 5 WB에서야 12를 기록한다.

| cycle | I1 | I2 | 결과 |
|---:|---|---|---|
| 1 | IF |  |  |
| 2 | ID | IF |  |
| 3 | EX, 12 | ID | I2가 과거 x1을 읽음 |
| 4 | MEM | EX | 잘못된 값 계산 |
| 5 | WB x1=12 | MEM | 이미 늦음 |
| 6 |  | WB | 잘못된 x4 |

원인은 SUB가 아니라 값 12가 준비된 위치와 소비 시점이 맞지 않는 것이다.

## 5. forwarding

**forwarding 또는 bypassing**은 결과를 register file에 WB하기 전에 소비 단계로 직접 보낸다. ADD 결과는 EX 끝의 EX/MEM에 있고 다음 cycle SUB의 EX 입력 multiplexer가 이를 선택한다.

| cycle | I1 | I2 | 경로 |
|---:|---|---|---|
| 1 | IF |  |  |
| 2 | ID | IF |  |
| 3 | EX, 12 | ID | I2 read 값은 오래될 수 있음 |
| 4 | MEM | EX | EX/MEM의 12를 ALU 입력으로 전달 |
| 5 | WB | MEM | SUB 결과 10 |
| 6 |  | WB | x4=10 |

forwarding unit은 원천 번호와 앞 명령의 목적 번호, register write enable, x0 여부를 검사한다. 더 최신 결과가 우선이다.

~~~text
I1: add x1, x2, x3     # x1=12
I2: add x1, x1, x4     # x4=1, x1=13
I3: sub x5, x1, x6     # x6=3, 정답 10
~~~

I3에 I1의 12를 주면 9로 틀린다. I2의 13을 선택해야 한다. forwarding은 wire 하나가 아니라 비교, valid, 우선순위 MUX로 구성된다.

## 6. load-use hazard

ALU 결과는 EX 끝에 나오지만 load data는 MEM 끝에 나온다.

~~~text
I1: lw  x1, 0(x2)      # memory 값 42
I2: add x3, x1, x4     # x4=5, 정답 47
~~~

I2가 바로 다음 cycle EX에 들어가면 그 cycle 시작에는 42가 없다. MEM 끝의 값을 같은 cycle EX 시작으로 시간을 거슬러 보낼 수 없어 한 bubble이 필요하다.

| cycle | I1 | I2 | 설명 |
|---:|---|---|---|
| 1 | IF |  |  |
| 2 | ID | IF |  |
| 3 | EX 주소 | ID | load-use 감지 |
| 4 | MEM, 42 도착 | ID 유지 | EX에 bubble, PC·IF/ID freeze |
| 5 | WB | EX | MEM/WB의 42 전달, 47 계산 |
| 6 |  | MEM |  |
| 7 |  | WB | x3=47 |

**stall**은 일부 pipeline register 값을 유지한다. **bubble**은 side effect 없는 빈 control을 다음 단계에 넣는다. 모든 CPU가 멈춘다는 뜻이 아니다. 이 1cycle은 제시한 5단계 모형의 결과지 모든 제품의 보장이 아니다.

compiler가 독립 명령을 사이에 배치하면 bubble을 숨길 수 있다.

~~~text
lw  x1, 0(x2)
add x8, x9, x10
add x3, x1, x4
~~~

## 7. store와 branch dependency

store는 목적 register가 없지만 주소 base와 저장 data가 필요하다.

~~~text
add x1, x2, x3
sw  x1, 0(x4)
~~~

주소는 EX에서 계산하고 store data는 MEM에서 쓴다면 ALU forwarding 외에 store-data 경로가 필요하다. 이를 빼면 memory에 과거 x1이 기록된다.

branch 비교도 operand에 의존한다. branch를 ID에서 비교하는 설계와 EX에서 비교하는 설계는 필요한 forwarding과 stall 수가 다르다. “5단계 pipeline의 branch penalty는 항상 2cycle”이라고 단정할 수 없다.

## 8. structural hazard와 control hazard

**structural hazard**는 같은 cycle에 여러 단계가 하나뿐인 자원을 요구할 때 생긴다. IF와 data load가 single-port memory를 공유하면 충돌한다. instruction cache와 data cache를 나누거나 port를 늘리면 특정 충돌을 줄이지만 면적, 전력, 배선 비용이 늘어난다.

**control hazard**는 branch의 다음 PC가 정해지기 전에 뒤 instruction을 가져올 때 생긴다.

~~~text
I1: beq x1, x2, target  # taken
I2: add x3, x4, x5      # 잘못된 경로
I3: sw  x6, 0(x7)       # 잘못된 경로
T : sub x8, x9, x10
~~~

I2의 내부 계산은 일어날 수 있지만 WB를 막고 I3의 store도 memory에 확정하지 않는다. 잘못된 경로의 valid를 지우고 target에서 다시 fetch한다. 내부 계산 결과는 임시 상태에만 두고 branch보다 앞선 명령부터 순서대로 안전성을 확인한 뒤 프로그램에 보이게 해야 한다.

## 9. CPI trace

base CPI=1, load 비율 20%, 그중 30%가 1cycle load-use stall, branch 15%, misprediction 10%, penalty 3cycle이라고 하자.

- load 추가 CPI=0.20×0.30×1=0.06
- branch 추가 CPI=0.15×0.10×3=0.045
- 총 CPI=1.105

1,000 instruction이면 약 1,105cycle이다. 2GHz의 0.5ns cycle이면 552.5ns다. 사건이 독립이고 다른 miss가 없다는 교육 모형이다. 실제 CPU에서는 penalty가 겹치고 wide issue에서는 IPC도 함께 본다.

## 10. 깊은 pipeline과 wide issue 연구

pipeline을 더 나누면 각 combinational path가 짧아져 높은 clock을 쓸 수 있다. 하지만 register overhead, bypass network, branch recovery, clock power가 늘어난다. dependency chain workload는 peak frequency보다 forwarding latency가 중요할 수 있다.

wide-issue CPU는 한 cycle에 여러 명령을 fetch·decode·issue·retire하려 한다. source와 destination 비교 수, bypass 배선, register-file port가 급격히 늘어난다. issue width를 두 배로 한다고 성능이 두 배가 되지 않는다. front end, dependency, cache bandwidth, execution port, retire width 중 하나가 병목이다.

최신 연구는 긴 latency 작업을 별도 queue로 분리하거나 compiler 정보와 dynamic scheduler를 결합하거나 chiplet 통신 지연을 숨긴다. 성능은 ISA 보장이 아니라 microarchitecture, workload, compiler, cache warm-up 조건의 측정이다.

## 11. examples/pipeline_model.py와 일치시키기

이 교재의 examples/pipeline_model.py는 이 장과 같은 IF·ID·EX·MEM·WB 5단계 교육 모형을 사용한다. 독립 instruction N개가 stall 없이 흐르면 첫 완료까지 5cycle, 전체 완료까지 N+4cycle이라는 표를 확인한다.

model의 핵심 입력은 각 instruction의 source와 destination register, load 여부다. load 바로 다음 instruction이 그 destination을 읽으면 한 cycle stall을 더한다. 예를 들어 LW x1 뒤 ADD x3,x1,x4라면 두 instruction의 이상적 N+4=6cycle에 load-use stall 1cycle을 더해 7cycle이다. 이는 앞의 cycle 표와 같다.

이 model은 실제 CPU timing simulator가 아니다. cache miss, branch prediction, 여러 instruction 동시 발행, variable latency를 생략한다. 목적은 “값이 MEM 끝에 나오는 load와 다음 EX 시작에서 필요한 consumer 사이에는 한 빈 cycle이 필요하다”는 규칙을 고정 입력으로 재현하는 것이다.


## 12. 하나의 C 식을 pipeline에서 끝까지 추적한다

~~~c
int f(const int *p, int b) {
    return *p + b;
}
~~~

03장의 ABI에 따라 p와 b가 register에 들어왔다고 하자. compiler는 교육용으로 LOAD와 ADD를 만든다. pipeline 관점에서 중요한 질문은 source 줄 수가 아니라 각 instruction의 결과가 어느 stage 끝에 준비되는가다.

LOAD의 EX에서는 p+0으로 effective address를 만든다. 이 주소는 아직 data 7이 아니다. MEM이 cache에 주소를 보내고 hit response를 받아야 7이 생긴다. ADD의 한 operand b=5는 일찍 준비되어도 다른 operand 7이 없으므로 EX에 보낼 수 없다. hazard unit은 목적 register 번호와 ADD source 번호를 비교해 정확히 한 cycle 기다리게 한다.

stall을 잘못 구현해 PC만 멈추고 IF/ID가 갱신되면 같은 instruction을 잃거나 중복 실행할 수 있다. 반대로 ID/EX에 기존 LOAD control을 그대로 유지하면 LOAD가 두 번 진행할 수 있다. 이 교육 모형에서는 PC와 IF/ID는 유지하고 ID/EX control을 side effect 없는 bubble로 만든다.

정상 흐름의 마지막 WB에서 ADD 결과 12가 목적 register에 기록된다. 실제 OOO CPU는 physical register와 ROB를 사용하지만, 프로그램에 보이는 결과와 exception 순서가 source 의미와 같아야 한다.

## 13. stall, flush, replay를 구분한다

**stall**은 필요한 조건이 올 때까지 일부 instruction의 진행을 멈춘다. load-use에서 ADD는 같은 경로의 올바른 instruction이며 operand만 기다린다.

**flush**는 잘못된 경로 또는 더 이상 유효하지 않은 younger instruction을 제거한다. branch misprediction에서 순차 경로 ADD와 STORE는 다시 실행할 대상이 아니라 올바른 target의 instruction으로 교체된다.

**replay**는 instruction이 speculative하게 실행됐지만 나중에 조건 위반이 발견되어 다시 실행하는 것이다. 예를 들어 OOO load가 older store와 주소가 다르다고 예측했는데 같음이 밝혀지면 load와 dependent chain을 replay할 수 있다.

세 경우 모두 cycle 표에 빈칸처럼 보일 수 있지만 원인과 control이 다르다. performance counter나 trace에서 frontend stall, backend dependency, branch recovery, replay를 분리해야 optimization 방향을 정할 수 있다.

## 14. pipeline register의 valid와 exception

pipeline register에는 data뿐 아니라 이 slot이 실제 instruction인지 나타내는 valid, register write와 memory write control, PC, exception 정보가 필요할 수 있다. bubble은 valid=0인 slot로 표현할 수 있다.

LOAD가 MEM에서 page fault를 발견했다고 하자. 뒤 ADD가 EX에서 내부 결과를 만들었더라도 faulting LOAD보다 뒤이므로 프로그램 상태에 남기면 안 된다. 단순 5단계 in-order pipeline은 뒤 stage control을 flush하고 fault PC를 보존해 handler로 간다. precise exception을 보장하려면 fault 앞 instruction은 반영되고 fault와 뒤 instruction은 반영되지 않아야 한다.

store의 memory write를 너무 이른 stage에서 되돌릴 수 없게 수행하면 older exception이나 branch misprediction 뒤 복구하기 어렵다. stage 표는 단순한 이름 목록이 아니라 side effect가 언제 확정되는지 설계하는 도구다.

## 15. performance 실험을 설계한다

forwarding 효과를 보려면 독립 instruction stream과 dependency chain을 나눈다. 같은 ADD 1억 개라도 서로 독립인 여러 accumulator를 쓰면 execution port throughput을 보고, 하나의 accumulator를 연속 갱신하면 ADD latency를 본다.

load-use 실험은 data가 L1에 있는 조건과 memory miss 조건을 분리한다. L1 hit인데 한 cycle dependency stall인 현상과 DRAM miss 수백 cycle을 섞으면 forwarding 개선을 관찰하기 어렵다. compiler가 loop를 제거하거나 vectorize하지 않았는지 최종 machine code도 확인한다.

측정한 cycle 수는 CPU model, clock, compiler, instruction alignment, cache와 predictor warm-up 조건에 속한다. ISA 명세가 특정 CPI를 보장하지 않는다.


## 16. 전체 문제 풀이

### 문제 1
5단계 pipeline에서 독립 instruction 20개를 완료하는 cycle 수는?

**풀이:** 첫 instruction 5cycle 뒤 매 cycle 하나씩 완료한다. 5+(20-1)=24cycle, 즉 N+4다.

### 문제 2
ADD x1,x2,x3 뒤 SUB x4,x1,x5에 EX/MEM→EX forwarding이 있으면 stall하는가?

**풀이:** ADD 결과는 EX 끝에 있고 다음 cycle SUB EX에서 쓸 수 있어 stall하지 않는다. 목적 x1과 원천 x1, write-enable을 확인해 forwarded 값을 선택한다.

### 문제 3
LW 바로 뒤 ADD가 forwarding이 있어도 stall하는 이유는?

**풀이:** load value는 MEM 끝, ADD operand는 같은 cycle EX 시작에 필요하다. 미래 값을 과거로 전달할 수 없어 1cycle bubble 뒤 MEM/WB→EX 전달한다.

### 문제 4
in-order 5단계에서 WAR와 WAW가 보통 hazard가 아닌 이유는?

**풀이:** read가 ID에서 순서대로, write가 WB에서 순서대로 일어나 뒤 write가 앞 read를 추월하거나 write 순서가 뒤집히지 않는다. 비순차 실행은 달라서 rename이 필요하다.

### 문제 5
load 25%, 그중 40%가 1cycle stall, branch 20%, misprediction 5%, penalty 4cycle이면 CPI는?

**풀이:** load 0.25×0.40=0.10, branch 0.20×0.05×4=0.04이므로 base 1과 합쳐 1.14다. 다른 miss와 중첩이 없다는 모형이다.

## 공식 자료

- [RISC-V Unprivileged ISA Manual](https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/)
- [RISC-V Ratified Specifications](https://docs.riscv.org/)

[← 이전](03-functions-abi-and-program-loading.md) · [목차](README.md) · [다음 →](05-branches-out-of-order-and-retirement.md)
