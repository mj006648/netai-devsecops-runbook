# 05. 분기·비순차 실행·결과 확정

[← 이전](04-pipelines-hazards-and-forwarding.md) · [목차](README.md) · [다음 →](06-cache-addresses-and-locality.md)

**PC(프로그램 카운터)**는 다음에 가져올 명령의 주소를 나타내는 프로그램 상태다. **fetch(명령 가져오기)**는 PC가 가리키는 위치에서 명령 바이트를 읽는 일이다. **decode(명령 해독)**는 그 바이트를 할 일의 종류인 opcode, 값을 담은 register 번호, 명령 안의 작은 상수인 immediate로 나누어 무엇을 실행할지 알아내는 일이다. **operand(피연산자)**는 ADD가 더할 값이나 LOAD가 주소를 만들 때 쓸 base처럼 실행 장치의 실제 입력이다.

순서가 앞선 LOAD가 먼 memory를 기다리는 동안, 그 값과 관계없는 뒤 ADD는 두 operand가 이미 준비되어 있을 수 있다. 무조건 앞 명령을 기다리면 실행 장치가 논다. **비순차 실행(out-of-order execution)**은 fetch와 decode 순서는 기록해 두되 operand와 실행 장치가 준비된 명령을 먼저 계산해 기다리는 시간을 숨기는 방법이다.

그러나 뒤 ADD 결과를 즉시 프로그램 register에 확정하면 문제가 생긴다. 오래 기다리던 앞 LOAD에서 page fault가 발견되거나 앞 branch 예측이 틀리면 순차 프로그램에서는 뒤 ADD가 아직 존재하지 않았어야 한다. 먼저 계산한 결과와 exception을 임시로 보관하고, 앞 명령부터 안전 여부를 확인해 프로그램에 보여 주는 기록 구조가 필요하다.

이 순서 기록 구조를 교육 모형에서 **ROB(Reorder Buffer, 재정렬 버퍼)**라고 부른다. decode한 명령을 프로그램 순서대로 넣고 완료 결과와 exception을 붙인다. 가장 오래된 항목부터 결과를 확정하는 일을 **retire(은퇴 또는 확정)**라고 한다. 실행 장치에서 계산이 끝난 completion과 프로그램이 결과를 관찰하는 retire는 다른 시점이다.

**추측 실행(speculation)**은 branch 방향이나 memory 주소 충돌처럼 아직 확인되지 않은 조건을 예측하고 맞다고 가정해 실행하는 방법이다. 예측이 맞으면 시간을 절약하고 틀리면 임시 결과를 버린다.

## 1. branch를 기다리면 front end가 빈다

branch는 조건에 따라 다음 PC를 바꾼다. 조건을 EX에서 계산하는 동안 fetch가 멈추면 branch마다 빈 cycle이 생긴다. **branch prediction**은 방향과 target을 추측해 instruction 공급을 이어 간다.

- **direction predictor**: taken인지 not-taken인지 예측한다.
- **BTB(Branch Target Buffer)**: branch PC를 key로 taken target을 기억한다.
- **RAS(Return Address Stack)**: 함수 call의 return address를 stack처럼 기억해 return target을 예측한다.
- **BHT 또는 PHT**: branch history를 이용해 방향 상태를 찾는 table이다.

2-bit saturating counter는 strongly not-taken, weakly not-taken, weakly taken, strongly taken 네 상태를 쓴다. 실제 결과가 taken이면 한 단계 taken 쪽, 아니면 반대로 이동한다. 한 번의 예외 결과로 강한 상태가 즉시 뒤집히지 않는다.

loop branch 결과가 T,T,T,N을 반복하고 초기 strongly taken이라고 하자. 앞 세 번은 맞고 exit N에서 한 번 틀린다. 다음 loop 첫 T에서는 weakly taken이라 다시 맞는다. 단순 predictor도 반복 loop에 높은 정확도를 보일 수 있지만 irregular data-dependent branch는 어렵다.

~~~mermaid
flowchart LR
  PC[fetch PC] --> B[BTB·방향 predictor]
  B --> NP[예측 next PC]
  NP --> F[추측 경로 fetch]
  F --> E[branch 실제 실행]
  E --> C{예측과 실제 일치?}
  C -->|예| K[계속]
  C -->|아니오| X[젊은 명령 flush]
  X --> R[올바른 PC로 복구]
~~~

## 2. misprediction 전체 trace

~~~text
I1: beq x1, x2, T      # 실제 taken, predictor는 not-taken
I2: add x3, x4, x5     # 잘못된 경로
I3: sw  x6, 0(x7)      # 잘못된 경로
T : sub x8, x9, x10
~~~

| cycle | front end·실행 | speculative 상태 | 건축적 상태 |
|---:|---|---|---|
| 1 | I1 fetch, not-taken 예측 | next=I2 | 변화 없음 |
| 2 | I2 fetch·decode | I2 ROB 할당 | 변화 없음 |
| 3 | I3 fetch, I1 비교 | I1 실제 taken 확인 | 변화 없음 |
| 4 | I2·I3 flush, PC=T | 임시 결과·store 제거 | 변화 없음 |
| 5 | T fetch | 새 올바른 경로 | 변화 없음 |
| 이후 | T 실행·retire | 정상 결과 | x8 갱신 |

I2가 ALU에서 결과를 만들었더라도 retire하지 않는다. I3의 store도 data cache나 memory에 되돌릴 수 없는 형태로 확정하면 안 된다. store data와 address를 store queue에 임시 보관하고 해당 store가 retire할 수 있을 때 coherence-visible write를 허용하는 교육 모형을 사용한다.

## 3. 왜 in-order issue만으로는 latency를 숨기기 어려운가

~~~text
I1: load x1, 0(x2)      # cache miss, 20cycle
I2: add  x3, x4, x5     # I1과 독립
I3: mul  x6, x7, x8     # I1과 독립
I4: add  x9, x1, x10    # I1에 의존
~~~

in-order issue가 I1 다음에서 멈추면 I2와 I3의 준비된 실행 장치를 사용하지 못한다. 비순차 scheduler는 I2와 I3를 먼저 보내고 I4만 x1을 기다리게 한다. 프로그램 순서를 없앤 것이 아니라 내부 실행 순서와 보이는 retire 순서를 분리한 것이다.

## 4. rename은 WAR와 WAW를 실제 storage에서 분리한다

ISA가 프로그램에 보여 주는 x1 같은 **논리 register 이름**은 수가 제한되어 있다. CPU 내부에는 더 많은 **physical register(물리 register)**가 있을 수 있다. **rename map**은 현재 프로그램 register 이름이 어느 physical register의 최신 version인지 기록한다.

~~~text
I1: add x1, x2, x3
I2: sub x4, x1, x5
I3: mul x1, x6, x7
I4: add x8, x1, x9
~~~

초기 x1→P1이라고 하자.

- I1 decode: 새 P10을 할당, source x2/x3 mapping을 읽고 x1→P10으로 갱신
- I2 decode: source x1은 P10이므로 I1에 RAW 의존
- I3 decode: 새 P11을 할당하고 x1→P11로 갱신. I1과 I3의 WAW 이름 충돌 제거
- I4 decode: source x1은 P11이므로 I3 결과를 기다림

I3가 P11에 먼저 결과를 써도 I1의 P10을 덮지 않는다. I2는 P10, I4는 P11을 읽는다. physical register는 이전 version이 더 이상 recovery와 older instruction에 필요 없을 때 free list로 돌아간다. 너무 일찍 재사용하면 misprediction 복구가 깨진다.

## 5. reservation station과 wakeup/select

**reservation station 또는 issue queue**는 실행을 기다리는 operation과 source 준비 상태를 보관한다. source가 준비되면 result tag broadcast나 dependency tracking으로 wakeup된다. **select** logic은 준비된 operation 중 실행 port에 보낼 것을 고른다.

항목에는 operation, source physical register 또는 ready value, destination tag, age 같은 정보가 들어갈 수 있다. 실제 제품 구조는 다르다. 모든 instruction이 하나의 거대한 station에 들어갈 수도, integer·floating·load/store queue로 나뉠 수도 있다.

I1 load가 기다리는 동안 I2 ADD의 source 둘이 ready이면 integer port로 issue된다. I4는 P10이 not-ready라 대기한다. load 결과가 P10 tag와 함께 나오면 I4가 wakeup된다. 이것이 source code 순서와 실행 순서가 달라지는 기작이다.

## 6. ROB와 in-order retire

ROB는 decode 순서대로 entry를 할당하는 원형 queue로 설명할 수 있다. entry에는 destination architectural register, 새 physical register, 이전 mapping, 완료, exception, branch recovery 정보가 있을 수 있다.

~~~text
I1: load x1, [A]        # 8cycle
I2: add  x2, x3, x4     # 1cycle
I3: div  x5, x6, x0     # divide-by-zero exception
I4: add  x7, x8, x9
~~~

| 시점 | I1 | I2 | I3 | I4 | 보이는 상태 |
|---:|---|---|---|---|---|
| 1 | ROB0 미완료 | ROB1 | ROB2 | ROB3 | 변화 없음 |
| 2 | memory 대기 | 결과 17 완료 | 실행 중 | 결과 완료 | 변화 없음 |
| 3 | 대기 | 완료 | exception 기록 | 완료 | 변화 없음 |
| 8 | load 9 완료 | 완료 | exception | 완료 | 변화 없음 |
| 9 | retire x1=9 | 완료 | exception | 완료 | I1만 확정 |
| 10 | 제거 | retire x2=17 | exception | 완료 | I2 확정 |
| 11 | 제거 | 제거 | head에서 exception | flush | I3 앞까지만 보임 |

**완료(completion)**는 실행 장치가 result 또는 exception을 CPU 내부 임시 상태에 기록했다는 뜻이다. **retire**는 ROB의 가장 오래된 항목부터 프로그램 순서로 결과를 되돌릴 수 없게 인정하는 단계다. I2가 먼저 끝나도 I1보다 먼저 retire하지 않는다.

## 7. precise exception

exception 발견 즉시 handler로 가면 더 오래된 명령의 상태가 불분명하다. faulting instruction이 ROB head가 될 때까지 기다리면 그보다 older instruction은 retire했고 younger instruction은 폐기할 수 있다. handler가 보는 상태는 순차 프로그램에서 faulting instruction 직전 상태와 같다. 이를 **precise exception**이라고 한다.

page fault가 해결 가능한 경우에는 faulting PC와 필요한 상태를 보존하고 page table을 고친 뒤 instruction을 재시작할 수 있다. divide-by-zero처럼 software에 signal을 전달할 수도 있다. exception 종류와 처리 방식은 ISA와 OS 계약이다.

## 8. load/store queue와 memory dependency

register dependency만 rename해서는 충분하지 않다. load와 store address는 실행 전까지 모를 수 있다.

~~~text
I1: store [x1+0], x2
I2: load  x3, [x4+0]
~~~

두 effective address가 다르면 load를 먼저 실행해도 결과가 같을 수 있다. 같다면 older store data를 memory로 보내기 전 load가 그 값을 받아야 한다. **store-to-load forwarding**은 store queue의 같은 주소에서 최신 older store data를 load에 전달한다.

CPU가 주소가 다를 것이라 예측해 load를 먼저 실행했는데 나중에 같은 주소임이 밝혀지면 **memory ordering violation**으로 load와 dependent instruction을 replay해야 한다. store가 두 개면 프로그램 순서상 load보다 앞선 같은 주소 store 중 가장 젊은 값을 골라야 한다.

## 9. speculative side effect와 보안 경계

예측이 틀린 경로의 instruction은 프로그램에 보이는 register와 memory state를 남기지 않아야 한다. 그러나 cache line 채움, TLB, predictor 같은 **CPU 내부 상태**는 바뀔 수 있다. 이런 흔적의 timing을 관찰해 speculative path의 secret을 추론하는 것이 Spectre 계열 문제의 핵심 원리다.

“retire하지 않았으므로 아무 side effect도 없다”는 문장은 건축적 상태에만 맞고 timing-visible microstate에는 틀릴 수 있다. fence, speculation barrier, index masking, predictor isolation 같은 mitigation은 threat model과 CPU·compiler 지침에 따라 적용한다. mitigation 비용도 workload와 구현 조건에서 측정한다.

I/O register write처럼 외부 장치에 되돌리기 어려운 operation은 speculative로 마음대로 실행하면 안 된다. memory type과 ordering rule, privilege check, retire 경계를 따라 side effect를 제어한다.


## 10. rename 복구 checkpoint

branch를 예측해 rename map을 계속 갱신하다가 misprediction이 나면 올바른 경로가 시작될 당시의 mapping으로 돌아가야 한다. 단순히 younger ROB entry를 버리는 것만으로는 x1이 어느 physical register를 가리켜야 하는지 복원되지 않는다.

한 방법은 branch마다 rename map checkpoint를 저장하는 것이다. branch B 전 x1→P10, B 뒤 잘못된 경로에서 x1→P14로 바뀌었다고 하자. B가 틀리면 P14 mapping과 그 이후 할당을 폐기하고 checkpoint의 x1→P10을 복원한다. 다른 방법은 ROB에 이전 mapping을 기록하고 역순으로 되돌리는 것이다. checkpoint 수, recovery latency, storage는 구현 trade-off다.

free list도 함께 복구해야 한다. 잘못된 경로가 받은 P14를 다시 free로 돌리되 올바른 경로에서 아직 사용하는 physical register를 중복 할당하면 안 된다. rename은 단순 이름 바꾸기가 아니라 version의 수명과 recovery를 관리하는 기작이다.

## 11. retire 시점에 무엇을 확정하는가

physical register에 결과가 기록되어도 프로그램에 보이는 register 대응을 retire state로 확정하는 방식은 구현마다 다를 수 있다. ROB head가 정상 완료되면 이전 physical register가 더 이상 precise recovery에 필요 없는지 판단해 반환한다.

store는 register result와 달리 memory hierarchy에 외부 관찰 효과를 낸다. store queue entry에는 address, data, byte mask, exception 여부를 임시로 둔다. store가 ROB head를 지나 정상 retire한 뒤 cache ownership을 얻어 visible write를 진행하는 모형을 생각할 수 있다. 정확한 queue와 timing은 제품마다 다르지만 wrong-path store가 남아서는 안 된다는 건축적 조건은 같다.

memory-mapped I/O처럼 read 자체가 device 상태를 바꾸거나 write가 외부 packet을 보내는 영역은 일반 cacheable memory보다 speculation 제약이 강하다. page attribute와 ordering rule을 따라야 한다.

## 12. quantitative window 예제

ROB 192entry, 평균 IPC 4인 core가 60cycle L3 miss를 만났다고 하자. 완벽한 독립 instruction이 충분하면 miss 동안 60×4=240 instruction을 진행할 여지가 필요하지만 ROB가 192entry라 window가 먼저 찰 수 있다. 실제로는 branch, dependency, issue queue와 physical register가 더 일찍 제한할 수 있다.

ROB를 384entry로 늘리면 latency hiding 기회는 늘지만 모든 workload가 빨라지지 않는다. pointer chasing처럼 다음 load 주소가 이전 load 결과에 의존하면 window 안에 실행 가능한 독립 일이 없다. entry access energy와 wakeup network 비용도 늘어난다.

연구 비교에서는 ROB 크기만 바꾼 결과인지, predictor·cache·frequency도 함께 바뀌었는지 확인한다. IPC 평균뿐 아니라 power와 area, branch recovery, workload별 distribution을 보고 “큰 window가 항상 좋다”는 일반화를 피한다.


## 13. predictor와 OOO 성능을 공정하게 측정하기

branch predictor 정확도만으로 성능을 결론 내릴 수 없다. misprediction penalty, branch 빈도, front-end 폭, target miss, instruction cache miss를 함께 본다.

1,000 instruction 중 branch 200개, misprediction 10개, penalty 15cycle이면 추가 150cycle이다. base CPI 0.5인 2-wide 이상화 core라면 base 500cycle에서 650cycle이 되어 CPI 0.65다. predictor 정확도는 95%지만 실행시간 증가는 base 대비 30%다. 높은 정확도라는 표현만으로 비용이 작다고 말할 수 없다.

OOO window가 커지면 long-latency miss 뒤의 독립 일을 더 찾을 수 있지만 physical register, ROB, issue queue, wakeup/select 전력과 timing 비용이 커진다. 최신 연구는 neural branch predictor, value prediction, larger window를 효율적으로 표현하는 방법을 다룬다. 결과는 trace, compiler, history warm-up, power budget에 의존하며 ISA 보장이 아니다.

## 14. 전체 문제 풀이

### 문제 1
2-bit counter가 strongly taken이고 실제 결과가 T,T,N,N,N이면 상태와 misprediction 수는?

**풀이:** 첫 T 두 번은 strongly taken 유지로 맞는다. 첫 N은 예측 T라 틀리고 weakly taken, 둘째 N도 T 예측이라 틀리고 weakly not-taken, 셋째 N은 N 예측으로 맞고 strongly not-taken이다. 총 2회다.

### 문제 2
I1이 x1에 쓰고 I3도 x1에 쓰며 I2는 I1의 x1, I4는 I3의 x1을 읽는다. rename의 역할은?

**풀이:** I1 목적에 P10, I3 목적에 P11을 주고 map을 version별 갱신한다. I2는 P10, I4는 P11을 source로 잡는다. WAW와 WAR 이름 충돌을 없애지만 I1→I2와 I3→I4의 실제 RAW는 유지한다.

### 문제 3
I2가 I1보다 먼저 완료했는데 왜 retire하지 못하는가?

**풀이:** older I1에서 exception이나 branch recovery가 필요할 수 있다. I2를 먼저 보이면 precise state를 만들 수 없다. ROB head부터 순서대로 retire해 완료 순서와 관찰 순서를 분리한다.

### 문제 4
older store와 younger load 주소가 같고 store가 아직 cache에 쓰지 않았다. load는 무엇을 읽어야 하는가?

**풀이:** 프로그램 순서상 자신보다 앞선 같은 주소 store 중 가장 젊은 값을 store queue에서 전달받아야 한다. memory의 오래된 값을 읽으면 틀린다.

### 문제 5
speculative instruction이 flush되면 cache effect도 반드시 사라지는가?

**풀이:** 아니다. architectural register와 memory write는 확정되지 않아야 하지만 speculative load가 cache와 predictor 같은 microstate를 바꿀 수 있다. timing side channel을 막으려면 threat model에 맞는 별도 mitigation이 필요하다.

## 공식 자료

- [RISC-V Unprivileged ISA Manual](https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/)
- [RISC-V Ratified Specifications](https://docs.riscv.org/)

[← 이전](04-pipelines-hazards-and-forwarding.md) · [목차](README.md) · [다음 →](06-cache-addresses-and-locality.md)
