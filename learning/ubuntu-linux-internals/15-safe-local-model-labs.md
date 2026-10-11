# 15. 안전한 로컬 모형 실습

[이전: 14. 문제 해결과 증거 수집](14-troubleshooting-and-evidence.md) · [목차](README.md) · [다음: 16. 문제·용어·출처](16-exercises-glossary-and-sources.md)

![Kernel workload 경로와 이 장의 순수 계산 모형 경계](assets/kernel-workload-path.svg)

이 장의 세 Python 프로그램은 실제 cgroup, sysfs, systemd 설정을 바꾸지 않고 io_uring syscall도 호출하지 않는다. 정수와 작은 상태 객체로 CPU 예산, request-buffer 수명, memory reclaim 순서를 손으로 검산한다. 모형이 답하는 제한된 질문과 실제 Linux에서 생략한 조건을 함께 읽어야 한다.

**입력** 은 계산 전에 고정한 숫자와 객체다. **상태** 는 계산 도중 변하는 field들의 현재 조합이다. **출력** 은 사람이 trace를 확인하도록 보여 주는 text다. **assert** 는 특정 입력에서 반드시 참이어야 한다고 코드가 정한 조건이며, 거짓이면 실행을 중단한다. assert 통과는 이 작은 모델의 불변식을 확인할 뿐 kernel scheduler, memory reclaim, io_uring 구현을 검증하지 않는다.

~~~mermaid
flowchart TD
    I["고정된 교육 입력"] --> M["Python 상태 전이"]
    M --> T["중간 trace"]
    T --> A["assert로 불변식 확인"]
    A --> B["실제 kernel 보장과 경계 구분"]
~~~

## 1. 세 파일의 질문과 수명

| 파일 | 질문 | 주요 상태 | 결과 |
|---|---|---|---|
| cgroup_budget.py | 공유 quota를 두 thread demand에 어떻게 나누는가 | ThreadDemand.used_ms, budget_ms | 남은 demand와 trace |
| ring_lifetime_model.py | out-of-order CQE에서 어느 buffer를 언제 해제하는가 | pending map, Request.state, released | request별 result 종류와 release log |
| memory_pressure_model.py | clean/dirty file page를 어떤 순서로 회수하는가 | MemoryState 네 account | pressure label과 최종 240MiB |

ThreadDemand와 Request, MemoryState는 Python process 안에서 script 실행 동안만 존재한다. 실제 kernel task, cgroup, ring, physical page가 아니다. 단위가 같은 이름을 가졌어도 객체 소유자와 수명이 다르다.

Repository root에서 기존 예제는 다음처럼 직접 실행하도록 구성되어 있다.

~~~text
python3 -B learning/ubuntu-linux-internals/examples/cgroup_budget.py
python3 -B learning/ubuntu-linux-internals/examples/ring_lifetime_model.py
python3 -B learning/ubuntu-linux-internals/examples/memory_pressure_model.py
~~~

-B는 .pyc bytecode cache 파일을 만들지 않게 한다. 외부 package는 사용하지 않는다.

## 2. CPU 모형이 표현하는 실제 개념

**cgroup CPU quota** 는 process/thread 집합이 한 **period** 안에 소비할 수 있는 CPU 실행 시간 상한이다. quota 50,000µs, period 100,000µs이면 50ms/100ms=0.5 CPU다. 이는 물리 core 절반을 분리했다는 뜻이 아니라 여러 period에서 한 core의 절반에 해당하는 평균 실행 예산이다.

**CPU time** 은 thread가 CPU 위에서 실행한 시간이고 **wall time** 은 사람이 본 경과 시간이다. thread가 30ms CPU를 요구해도 throttling과 다른 task 경쟁이 있으면 완료 wall time은 30ms보다 길 수 있다. 이 모형의 demand_ms는 필요한 CPU time이다.

**quantum** 은 모델이 한 차례에 배분하는 5ms 계산 조각이다. 실제 Linux scheduler time slice가 항상 5ms라는 뜻이 아니다. round-robin, 즉 A 다음 B를 반복하는 손 계산을 드러내려고 고른 값이다.

## 3. ThreadDemand 객체

ThreadDemand에는 name, demand_ms, used_ms가 있다. name은 trace에서 A와 B를 구별하는 문자열이다. demand_ms는 전체 CPU 요구량이고 used_ms는 지금까지 받은 양이다. remaining_ms property는 demand_ms-used_ms를 매번 계산한다.

~~~python
@dataclass
class ThreadDemand:
    name: str
    demand_ms: int
    used_ms: int = 0

    @property
    def remaining_ms(self):
        return self.demand_ms - self.used_ms
~~~

객체는 frozen이 아니므로 run_period가 used_ms를 누적 변경한다. 같은 threads 목록을 두 번째 period에 다시 전달하면 첫 period의 25ms 사용 상태에서 이어진다. 새 목록을 만들면 상태가 reset되므로 결과가 달라진다.

## 4. run_period 입력과 반환값

run_period(quota_us,period_us,demands,quantum_ms=5)는 quota를 1,000으로 정수 나눠 budget_ms를 만든다. 50,000µs는50ms다. period_us는 cpu_share=quota_us/period_us 계산에 쓰이며 loop 예산 자체는 quota가 정한다.

while 조건은 budget이 남고 어느 demand라도 remaining>0일 때다. for loop가 A,B 순서로 각자 min(quantum,remaining,budget)을 사용한다. trace 항목은 (thread 이름, 사용 전 예산, 이번 사용량, 사용 후 예산)이다. progressed가 False면 더 쓸 demand가 없거나 사용량이0인 상태에서 무한 loop를 피한다.

반환 dictionary의 네 field는 다음 뜻이다.

- cpu_share: quota/period 비율 0.5다.
- budget_left_ms: 이번 period에 쓰지 않은 quota다.
- remaining_demand_ms: 모든 thread의 남은 CPU demand 합이다.
- trace: 각 배분 단계의 전후 상태다.

cpu_share가 0.5라는 값은 실제 사용률이 반드시 50%라는 뜻이 아니다. runnable demand가 적으면 budget_left가 남는다.

## 5. 첫 period 전체 추적

입력은 A demand30ms, B demand30ms, quota50ms, quantum5ms다.

| step | thread | 전 budget | 사용 | 후 budget | A used | B used |
|---:|---|---:|---:|---:|---:|---:|
| 1 | A | 50 | 5 | 45 | 5 | 0 |
| 2 | B | 45 | 5 | 40 | 5 | 5 |
| 3 | A | 40 | 5 | 35 | 10 | 5 |
| 4 | B | 35 | 5 | 30 | 10 | 10 |
| 5 | A | 30 | 5 | 25 | 15 | 10 |
| 6 | B | 25 | 5 | 20 | 15 | 15 |
| 7 | A | 20 | 5 | 15 | 20 | 15 |
| 8 | B | 15 | 5 | 10 | 20 | 20 |
| 9 | A | 10 | 5 | 5 | 25 | 20 |
| 10 | B | 5 | 5 | 0 | 25 | 25 |

합 demand60ms 중50ms를 썼으므로 remaining은 A5+B5=10ms다. “throttled-demand”는 model이 예산 밖에 남은 요구를 부른 설명 표현이다. 실제 cpu.stat throttled_usec를 예측한 값이 아니다.

## 6. CPU assert와 두 번째 period

첫 결과는 다음을 검사한다.

- cpu_share==0.5
- budget_left_ms==0
- remaining_demand_ms==10
- A,B used_ms가 각각25
- trace의 use_ms 합이50

두 번째 run_period는 같은 mutable threads를 받는다. 각자 remaining5ms이므로 A5,B5만 쓰고 완료한다. budget40ms가 남지만 반환 검사는 remaining=0과 used=[30,30]을 확인한다. 출력은 다음과 같다.

~~~text
quota/period = 0.50 CPU
period 1: A=25ms B=25ms throttled-demand=10ms
period 2: remaining demand completed
model note: calculation only; no cgroup was read or changed
~~~

모형은 fairness를 입력 목록 순서와 quantum으로 고정했다. 실제 kernel의 CFS/EEVDF scheduling, 여러 CPU, migration, burst, weight, affinity, accounting rounding은 생략한다. quota가 50,500µs처럼 1ms 배수가 아니면 //1000이 remainder를 버리는 것도 모델 한계다.

## 7. CPU 조건 변경 반례

quota를60,000µs로 바꾸면 budget60ms라 첫 period에 두 demand가 모두 끝난다. thread C를 목록 앞에 추가하면 round-robin 분배가 달라진다. quantum을7ms로 바꾸면 마지막 step이 1~몇 ms가 될 수 있지만 총 사용은 budget과 remaining의 최소값이어야 한다.

실제 cgroup CPU 결과로 일반화하려면 cpu.max, cpu.stat delta, runnable thread, affinity와 ancestor quota를 읽어야 한다. 모델의 A/B used가 같다는 이유로 kernel fairness를 증명하지 않는다.

## 8. io_uring 모델의 객체

![SQE 제출부터 CQE matching과 buffer 해제까지의 수명주기](assets/io-uring-lifecycle.svg)

io_uring에서 **SQE** 는 read 같은 요청 한 건을 기술하는 submission queue entry이고, **CQE** 는 끝난 요청의 user_data와 result를 돌려주는 completion queue entry다. 요청을 제출한 순서와 완료 순서는 다를 수 있다. buffer는 kernel이 접근할 수 있는 동안 유효한 주소와 내용을 유지해야 한다.

이 Python 파일은 ring memory와 syscall을 만들지 않는다. Request 객체로 application이 관리해야 할 상태만 표현한다.

~~~python
class State(Enum):
    SUBMITTED = auto()
    COMPLETED = auto()
    CANCELLED = auto()
~~~

SUBMITTED는 terminal completion을 아직 처리하지 않은 상태다. COMPLETED와 CANCELLED는 더 진행되지 않는 terminal state다.

Request의 request_id는 실제 model에서 user_data 역할을 하는 정수, buffer_name은 소유권을 설명할 문자열, requested_bytes는 요청 크기다. state는 처음 SUBMITTED, released는 False다. requested_bytes는 현재 finish에서 short read 검증에 사용하지 않는다. 이는 명시적 생략이다.

## 9. finish와 release_once의 불변식

finish(result)는 state가 SUBMITTED가 아니면 RuntimeError를 낸다. 같은 request에 terminal completion을 두 번 붙이지 못하게 한다. result==-125일 때 CANCELLED, 그 밖에는 COMPLETED로 둔다. Linux errno 125가 ECANCELED인 일반 환경을 교육 값으로 사용한 것이다. 실제 liburing opcode의 result 계약을 확인해야 한다.

finish 반환은 result<0이면 문자열 errno, 0 이상이면 bytes다. 따라서 -22는 22byte 성공이 아니다. 반대로 result=0도 bytes 종류로 분류하며 read 문맥에서는 EOF일 수 있다.

release_once는 released가 이미 True면 double release RuntimeError를 낸다. state가 여전히 SUBMITTED이면 matching completion 전 release RuntimeError를 낸다. terminal state에서 처음 부르면 released=True가 된다.

이 코드는 실제 free 함수를 호출하지 않는다. “buffer 수명을 끝냈다”는 application state만 표시한다.

## 10. RingModel pending map

RingModel.pending은 request_id에서 Request로 가는 dictionary다. submit은 ID가 이미 있으면 ValueError를 내 중복 correlation을 막는다. complete는 ID가 없으면 KeyError를 내 unknown CQE를 다른 request에 붙이지 않는다.

complete가 올바른 ID를 찾으면 pending에서 pop한다. 그 뒤 finish로 result를 분류하고 release_once를 호출하며 buffer_name을 release_log에 추가한다. 요청은 pending 수명에서 사라지지만 반환된 Request 객체는 Python 변수로 남아 assert에서 state와 released를 검사할 수 있다.

pending에서 먼저 pop한 뒤 finish가 예외를 내면 모델 상태가 일부 변경될 수 있다는 점도 실제 production state machine과 다른 단순화다. 실제 코드는 오류 경로의 atomicity와 recovery를 더 엄격히 설계해야 한다.

## 11. out-of-order completion 전체 trace

요청101은 buf-A에4096B, 요청102는 buf-B에2048B를 요구한다. submit 순서는101,102다. completion은102 result2048이 먼저, 101 result-22가 나중이다.

| 사건 | pending key | release log | 결과 |
|---|---|---|---|
| submit101 | [101] | [] | buf-A alive |
| submit102 | [101,102] | [] | 둘 다 alive |
| complete102,2048 | [101] | [buf-B] | bytes, B released |
| complete101,-22 | [] | [buf-B,buf-A] | errno, A released |

CQE가 먼저 왔다는 이유로 배열 첫 request101을 해제하면 use-after-free 또는 잘못된 buffer 결과가 된다. ID102로 map을 찾아 buf-B만 끝낸다.

출력과 assert는 다음 계약을 고정한다.

~~~text
submitted ids: [101, 102]
completion 102: bytes=2048 release=buf-B
completion 101: errno=EINVAL release=buf-A
cancel race: target terminal state owns final release
model note: this is not a real io_uring call
~~~

kind102는 bytes이고 released=True, kind101은 errno이고 released=True다. release_log 순서는 [buf-B,buf-A], pending은 비어야 한다.

## 12. cancel race 모형의 정확한 한계

![io_uring polling·interrupt·cancel 경로의 서로 다른 mode](assets/io-uring-modes.svg)

illustrate_cancel_race는 boolean 하나로 두 문장을 반환한다. target_already_completed=True이면 대상 completion이 final release를 소유한다. False이면 cancelled target completion이 final release를 소유한다. cancel request 자체의 CQE, target CQE result, multi-shot request와 partial completion을 구현하지 않는다.

핵심 불변식은 “cancel CQE를 봤다는 이유만으로 buffer를 해제하지 않고 대상 request의 terminal 경로 하나만 final release를 소유한다”이다. 두 반환 문자열 assert가 이 설명을 고정한다. 실제 race의 event ordering을 재현하거나 memory ordering을 검증하지 않는다.

## 13. ring 모델이 생략한 현실

실제 io_uring에는 ring setup flag, opcode 지원, SQ/CQ head-tail memory ordering, registered buffer와 fixed file, linked request, timeout, partial read, signal, seccomp/LSM 정책이 있다. request마다 별도 buffer를 썼다는 model 가정도 실제 application이 pool을 사용할 때 달라진다.

user_data가 64-bit application 값이라고 해서 kernel이 buffer ownership을 자동 관리하는 것은 아니다. ID reuse는 이전 request CQE가 모두 소비된 뒤 세대까지 구분해야 안전하다. Python의 buffer_name 문자열은 실제 주소 안정성을 증명하지 않는다.

별도 uring_read.c는 실제 liburing API 모양을 보여 주는 선택 예제지만 liburing header/library, 실행 kernel, seccomp와 policy 조건이 필요하다. header에서 compile된다는 사실은 kernel이 모든 flag/opcode를 실행한다는 보장이 아니다.

## 14. memory 모형의 객체와 단위

MemoryState는 anonymous_mib, clean_file_mib, dirty_file_mib, other_mib 네 정수를 가진 mutable 객체다. MiB는1,048,576B다.

**anonymous memory** 는 heap과 stack처럼 파일 내용으로 다시 읽을 수 없는 page를 단순 대표한다. **clean file page** 는 backing storage와 같은 file cache라 다시 읽을 수 있어 reclaim 후보로 둔다. **dirty file page** 는 memory 변경을 storage에 writeback해야 clean으로 바뀐다고 단순화한다. other는 모델에서 회수하지 않는20MiB다.

현실 memory.current accounting은 slab, socket, page table, shared page, swap charge와 kernel version 조건을 포함한다. 이 네 field가 실제 cgroup memory.stat을 완전 분할한 것이 아니다.

current_mib property는 네 field 합이다. 시작 상태220+80+40+20=360MiB다. high256, max384, target240이다.

## 15. pressure_label은 사건 예측이 아니다

pressure_label은 current>max이면 above-max, 아니고 current>high이면 above-high below-max, 아니면 at-or-below-high를 반환한다. strict greater-than을 쓰므로 current==max는 above-max가 아니고 current==high는 at-or-below-high다. 실제 memory.max에서 charge·reclaim·OOM의 세부 동작을 예측하는 함수가 아니다.

시작360은256보다 크고384보다 작아 above-high below-max다. 이는 pressure 가능 구간 표시다. 즉시 OOM kill이 난다는 뜻이 아니다. memory.high가 reclaim/throttling을 유도할 수 있고 memory.max는 hard limit 성격이지만 실제 결과는 회수 가능 page, swap, ancestor, 동시 allocation에 달렸다.

## 16. reclaim_clean과 writeback_dirty

reclaim_clean(amount)는 요청량과 현재 clean_file 중 작은 값을 reclaimed로 잡고 clean field에서 뺀다. clean80에120을 요청해도 min(120,80)=80만 회수하고 성공량80을 반환한다. 회수 가능량보다 큰 목표를 성공으로 보고하지 않는 규칙이다.

writeback_dirty는 dirty 전체를 written으로 잡고 같은 양을 clean에 더한 뒤 dirty를0으로 만든다. 실제 storage 오류, 부분 writeback, 재오염, writeback latency를 생략한 원자적 상태 전이다. 반환값은 written MiB다.

## 17. memory 전체 상태 변화

목표는 current360에서240으로120MiB 줄이는 것이다.

| 단계 | anon | clean | dirty | other | current | 사건 |
|---|---:|---:|---:|---:|---:|---|
| 시작 | 220 | 80 | 40 | 20 | 360 | high 초과, max 미만 |
| clean reclaim | 220 | 0 | 40 | 20 | 280 | 80 회수 |
| dirty writeback | 220 | 40 | 0 | 20 | 280 | 분류만 변경 |
| 추가 reclaim | 220 | 0 | 0 | 20 | 240 | 40 회수 |

첫 reclaim 요청량은 current-target=120이지만 clean80만 회수한다. writeback은 dirty40을 clean40으로 옮겨 current 총합을 바꾸지 않는다. 그 clean40을 추가 회수해야240이 된다. writeback 자체를 reclaim으로 세면280에서 바로240이 되었다고 잘못 기록한다.

출력은 다음과 같다.

~~~text
current=360MiB high=256MiB max=384MiB
pressure=above-high below-max
clean reclaimed=80MiB
dirty writeback then reclaimed=40MiB
modeled final=240MiB
model note: not an exact Linux reclaim prediction
~~~

## 18. memory assert가 고정하는 계약

시작 current=360, label=above-high below-max, 첫 clean reclaim=80과 current=280을 확인한다. writeback=40과 dirty=0, 추가 reclaim=40과 final current=target240을 확인한다.

anonymous220과 other20은 전체 실행에서 변하지 않는다. swap, anonymous reclaim이나 OOM으로 목표를 맞추지 않는다. clean+dirty file120이 정확히 목표 감소량120이라 성공하는 입력이다.

clean을20으로 줄이고 dirty를40으로 유지하면 file reclaim 최대60이므로 시작 current300에서 target240에는 닿지만, other 조건을 바꾸면 못 닿을 수 있다. 모델은 일반적인 “목표 미달” status를 반환하지 않으므로 새 입력을 넣을 때 final assert를 무조건 유지하면 실패 이유를 해석해야 한다.

## 19. watermark라는 이름의 경계

target240을 watermark라고 설명하지만 실제 Linux zone watermark가 아니다. kernel의 low/high/min watermark, LRU generation, reclaim priority를 모델링하지 않는다. cgroup memory.high와도 다른 교육 목표다. 이름이 같거나 비슷해도 실제 객체를 명시해야 한다.

real reclaim에서는 recently used file page가 refault하고, dirty writeback이 device를 막고, anonymous를 swap할 수 있으며 NUMA node별 free memory가 다르다. direct reclaim 중 application thread가 stall할 수 있어 PSI가 오른다. 이 model의 즉시 숫자 변화에서 latency를 추론하지 않는다.

## 20. 세 모델의 공통 검산법

첫째, 단위를 확인한다. quota_us를 ms budget으로 바꿀 때1,000으로 나누고 memory는 MiB다. 둘째, mutable object의 이전 실행 상태가 다음 호출에 남는지 확인한다. 셋째, 출력 text보다 assert 조건을 읽는다. 넷째, 모델이 일부러 실패시키는 중복 ID, unknown completion, double release 경계를 확인한다. 다섯째, 생략 조건을 현실 보장으로 채워 넣지 않는다.

## 21. 완전 풀이 문제

### 문제 1. quota 비율

50,000µs/100,000µs는 얼마인가?

**풀이:** 0.5 CPU 평균 상한이다. 두 thread가 각각0.5가 아니라 합계가0.5다. runnable demand가 없으면 실제 사용은 더 적다.

### 문제 2. first period remaining

A,B가 각각30ms demand이고 budget50ms다.

**풀이:** round-robin5ms 가정에서 각각25ms 사용하고5ms씩 남아 합10ms다. trace use 합은50이다.

### 문제 3. second period budget

같은 mutable thread를 두 번째50ms period에 넣는다.

**풀이:** A5+B5만 더 쓰면 demand가 끝나고 budget40ms가 남는다. assert는 remaining0과 used=[30,30]을 확인한다.

### 문제 4. out-of-order CQE

102 completion이 먼저 왔다.

**풀이:** pending[102]의 buf-B를 처리·release한다. 제출 첫 항목 buf-A를 해제하지 않는다. release log 첫 원소는 buf-B다.

### 문제 5. result -22

**풀이:** model은 result<0을 errno 종류로 분류하고 Request는 COMPLETED terminal 상태가 된다. 출력에서 EINVAL로 설명한다. 22byte 성공이 아니다.

### 문제 6. cancel과 release

cancel CQE를 받았다.

**풀이:** cancel request 결과만으로 대상 buffer를 해제하지 않는다. 대상 request의 terminal completion 경로가 final release를 한 번 소유한다. model은 두 possible ordering을 문자열로 단순화한다.

### 문제 7. duplicate ID

101이 pending인데 새 request101을 submit한다.

**풀이:** ValueError로 거부한다. 같은 ID를 허용하면 CQE101이 어느 buffer에 속하는지 모호해진다. 실제 장기 시스템은 generation까지 고려한다.

### 문제 8. clean reclaim

360에서 target240, clean80이다.

**풀이:** 필요한120 중 min(120,80)=80만 회수해 current280이다. dirty40은 writeback 뒤 clean으로 전환해야 추가 회수한다.

### 문제 9. writeback 후 합계

dirty40을 clean40으로 옮겼다.

**풀이:** current 총합은280으로 같다. writeback은 저장 상태를 바꾸지만 page를 memory에서 없애지 않았다. 그 뒤 reclaim40으로240이 된다.

### 문제 10. pressure label

current384,high256,max384다.

**풀이:** 함수가 strict greater-than을 쓰므로 above-high below-max를 반환한다. 이 label만으로 실제 charge 성공이나 OOM을 예측하지 않는다. current385면 above-max다.

## 22. 공식 근거와 모델 경계

- [Linux kernel: cgroup v2 CPU·memory controllers](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [Linux kernel: io_uring](https://docs.kernel.org/io_uring/)
- [liburing source and examples](https://github.com/axboe/liburing)
- [systemd resource control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)

세 script의 assert는 안전한 계산 실습을 반복 가능하게 한다. 실제 kernel behavior를 주장하려면 해당 kernel version의 interface를 읽고, 별도 격리 환경에서 원시 관측과 결과를 검증해야 한다.
