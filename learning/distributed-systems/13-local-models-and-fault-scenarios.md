# 13. 로컬 모델과 장애 시나리오

## 모델에서 입력·상태·출력을 먼저 구분한다

이 장의 **모델**은 실제 제품을 축소 구현한 것이 아니라, 검토할 규칙을 Python 상태 전이로 표현한 실행 가능한 설명이다. 입력은 사건 목록·로그·함수 인자이고, 상태는 dataclass와 dict가 가진 값이다. 출력은 read history, commit index, 함수 반환값과 print이며, **불변식(invariant, 모든 허용 실행에서 지켜야 하는 조건)**은 assert가 검사한다.

`dataclass`는 관련 필드를 이름 붙여 한 객체로 묶는 Python 자료 구조다. 이 예제에서 `Replica(name, value, applied_index)`와 `Entry(index, term, command)`가 실제 상태 객체이며, 객체가 살아 있는 한 필드가 모델 상태를 이룬다. `dict`는 key로 값을 찾는 사전 자료 구조로, retry 모델의 `results[request_id]`가 이미 처리한 요청의 반환값을 기억한다. `return`은 함수가 호출자에게 계산 결과를 돌려주는 제어 지점이고, 그 뒤 문장은 실행되지 않는다. `assert 조건`은 조건이 거짓이면 즉시 `AssertionError`를 내어 그 trace가 기대 불변식을 어겼음을 표시한다. assert 통과는 적어 둔 조건이 이 실행에서 참이라는 뜻이며, 적지 않은 제품 속성까지 증명하지 않는다.

```mermaid
flowchart LR
 H[검토할 주장] --> M[작은 상태 모델]
 M --> F[정확한 위치에 장애 주입]
 F --> T[시간순 trace]
 T --> A[불변식 assert]
 A --> R[결과와 제외 범위]
```

같은 입력이 같은 trace를 내는 결정적 모델은 실패를 재현하고 수정 전후를 비교하기 쉽다. 난수를 쓰면 seed와 생성 규칙을 기록한다. 다만 seed는 실패 trace의 재현 주소이지 정확성 증거가 아니다. 논리 tick 5, 20, 25도 사건 순서일 뿐 실제 밀리초가 아니다.

세 예제는 Python 표준 라이브러리만 쓰는 교육용 모델이다. 실제 socket, 디스크, 프로세스 scheduler와 전체 Raft를 구현하지 않는다. 그러므로 결론은 “이 입력에서 이 상태 전이와 assert가 통과했다”까지로 제한한다.

## `replication_model.py`: 복제 전 stale read

실제 객체 `Replica`는 `name`, `value=1`, `applied_index=0`으로 시작한다. `apply(index, value)`는 새 index가 `applied_index+1`일 때만 value와 index를 바꾼다. 입력은 leader 쓰기, follower 읽기, follower 복제, 두 번째 읽기의 네 사건이다.

| tick | 입력 | 전 상태 | 조건·분기 | 후 상태 | 관측 |
|---:|---|---|---|---|---|
| 시작 | 없음 | L=(1,0), F=(1,0) | - | 동일 | `reads=[]` |
| 0 | `write,L,1,2` | L=(1,0) | `1=0+1` | L=(2,1) | 없음 |
| 5 | `read,F` | F=(1,0) | read | 변화 없음 | `(5,1,0)` |
| 20 | `replicate,F,1,2` | F=(1,0) | `1=0+1` | F=(2,1) | 없음 |
| 25 | `read,F` | F=(2,1) | read | 변화 없음 | `(25,2,1)` |

첫 assert는 `reads == [(5,1,0),(25,2,1)]`, 둘째는 leader와 follower의 값이 모두 2인지 검사한다. 출력은 두 read와 `converged:2`다. 이 모델이 계산하는 주장은 복제 전 follower 읽기는 오래될 수 있고, 복제 뒤에는 이 입력에서 수렴한다는 두 가지다.

전이를 코드 제어로 따라가면 첫 `write` 사건은 leader의 `apply(1,2)`를 호출한다. 조건 `index == applied_index + 1`은 `1 == 0+1`이라 참이므로 두 필드를 함께 `(2,1)`로 바꾼다. tick 5의 `read`는 follower 객체의 현재 필드를 tuple로 append할 뿐 상태를 바꾸지 않아 `(5,1,0)`을 남긴다. tick 20의 `replicate`가 같은 entry를 follower의 `apply`에 입력해 조건을 통과시키고, tick 25 read가 `(25,2,1)`을 반환한다. 실패 조건은 읽기 tuple 하나라도 다르거나 최종 두 value 중 하나가 2가 아닌 경우다. 따라서 중간 stale 관측과 최종 수렴을 서로 다른 assert로 잡는다.

모델의 경계도 구체적이다. index 2가 먼저 오면 `2 == 0+1`이 거짓이라 조용히 무시하며 buffer나 gap 재요청은 없다. term, 선거, WAL(write-ahead log, 적용 전 기록하는 내구 로그), fsync, 동시 thread와 restart도 없다. tick 20 사건을 지우면 reads는 `[(5,1,0),(25,1,0)]`이 되고 수렴 assert도 실패한다. 같은 index 1을 tick 30에 다시 보내도 값은 수렴하지만 내구성을 증명하지 않는다.

## `raft_commit_model.py`: 현재 term의 과반수

`Entry`는 바뀌지 않는 `index`, `term`, `command`를 가진다. A와 B의 log에는 `(1,term2,x=1)`, `(2,term4,y=1)`이 있고 C에는 index 1만 있다. `current_term=4`, node 수가 3이므로 majority는 `3//2+1=2`다.

함수는 후보 index `{1,2}`를 `[2,1]` 순서로 검사한다. index 2이면서 term 4인 사본은 A와 B에 있으므로 `copies=2`가 majority를 만족해 `commit_index=2`를 반환한다. A log에서 index 2 이하인 prefix의 command는 `x=1, y=1`이다.

| 검사 | A | B | C | copies | 판정 |
|---|---|---|---|---:|---|
| index2, term4 | 있음 | 있음 | 없음 | 2 | commit index2 |
| index1, term4 | 검사 종료로 생략 | 생략 | 생략 | - | prefix로 간접 포함 |

assert는 `commit_index==2`, command 목록 두 개, prefix 첫 항목의 term 2가 current term 4보다 작다는 사실을 검사한다. 과거 term 2 항목은 현재 term 4의 index 2가 commit될 때 prefix로 포함되는 모형이다.

함수 입력은 세 node의 log와 `current_term=4`다. 후보 index 2를 볼 때 각 log에 `index==2 and term==4`인 entry가 있는지 세어 A와 B에서 2를 얻는다. `copies >= majority`가 참이 되는 첫 후보에서 `return 2`가 실행되므로 index 1 검사로 내려가지 않는다. 이후 caller가 A log에서 `index <= commit_index`인 prefix를 골라 command 목록을 만든다. `return 2`는 상태 기계가 두 command를 적용했거나 client가 응답을 받았다는 뜻이 아니라 이 입력에서 commit index 산술이 2라는 출력일 뿐이다. A나 B 중 term 4 entry 하나를 제거하면 copies는 1이라 첫 분기가 실패하고, term 4 과반수가 다른 index에도 없으면 최종 반환은 0이다.

선거, RequestVote, AppendEntries, 충돌 rollback, leader 자격, `lastApplied`, 상태 기계 적용과 client 응답은 없다. A log를 권위 prefix로 쓰는 입력 가정도 있다. A와 B에 term 2의 index 1만 있고 current term이 4이면 term 4 사본은 0개이므로 결과는 0이다. 과거 term 항목이 과반수에 있다는 이유만으로 직접 commit하지 않는다.

같은 index에 충돌 log를 넣으려면 `prevLogTerm` 검사와 전이를 먼저 모델링해야 한다. 현재 함수의 단순 `any` 검사에 전제 밖 입력을 넣으면 실제 Raft보다 강한 잘못된 결론을 낼 수 있다.

## `retry_dedup_model.py`: 응답 유실 뒤 같은 ID 재시도

`AccountService`의 초기 상태는 `balance=1000`, `executions=0`, `results={}`다. 첫 `debit(R42,100)`은 ID가 없고 잔액이 충분한 분기를 지나 balance를 900, executions를 1, results를 `{R42:900}`으로 바꾸고 900을 반환한다. 응답이 유실되었다고 가정해 같은 호출을 다시 하면 ID 존재 분기에서 상태를 바꾸지 않고 900을 반환한다.

| 호출 | 전 상태 | 분기 | 후 상태 | 반환 |
|---|---|---|---|---:|
| 첫 `R42,100` | `1000,0,{}` | 새 ID·잔액 충분 | `900,1,{R42:900}` | 900 |
| 재시도 `R42,100` | `900,1,{R42:900}` | ID 존재 | 동일 | 900 |

네 assert는 두 반환값이 900인지, balance가 900인지, executions가 1인지, results dict가 기대와 같은지 검사한다. print는 `balance:900`, `executions:1`이다. 최종 balance만 보면 두 번 차감한 뒤 보상하는 잘못된 경로도 통과할 수 있어 실행 횟수와 결과표를 함께 검사한다.

첫 호출의 제어 흐름은 `request_id in results`가 거짓인지 확인하고, `amount <= balance`가 참인지 검사한 뒤 balance를 한 번 줄인다. executions를 증가시키고 새 balance를 results에 저장한 다음 `return 900`을 실행한다. 두 번째 호출은 첫 조건이 참이므로 `return results[R42]`에서 곧바로 끝나고 차감 분기에는 들어가지 않는다. 따라서 반환값이 같다는 사실뿐 아니라 후 상태가 바뀌지 않았다는 사실이 중복 제거의 핵심이다. 잔액보다 큰 amount를 처음 넣었을 때 어떤 오류를 반환하는지는 해당 코드 분기를 그대로 보고해야 하며, 성공 trace에서 임의로 추론하면 안 된다.

이 dict는 프로세스 메모리에만 있다. 같은 R42로 amount 500을 보내도 payload 비교 없이 기존 900을 반환하며, process restart면 results가 사라진다. 두 thread가 동시에 ID 없음 분기를 통과하는 race, DB transaction, 외부 결제와 TTL도 없다. 실제 중복 제거는 request ID와 payload hash를 영속 transaction에 함께 저장해야 한다.

## 세 모델을 요청 R42의 경계로 연결하기

클라이언트가 R42로 100 차감을 보낸다고 하자. leader는 명령을 term 4, index 2에 넣고 A와 B에 복제한다. Raft 모델은 현재 term 항목의 과반수를 보고 index 2 commit을 계산한다. 상태 기계가 debit을 적용해 balance 900과 `results[R42]=900`을 만든다. 응답이 유실되면 retry 모델처럼 같은 ID의 기존 결과를 반환해야 한다. follower C가 아직 index 1까지만 적용했다면 replication 모델처럼 오래된 읽기를 줄 수 있다.

| 경계 | 권위 상태 | 아직 보장하지 않는 것 |
|---|---|---|
| A에 index2 append | leader log | quorum commit |
| A·B에 term4 index2 | commit_index2 가능 | state machine apply |
| debit apply | balance900, result 저장 | client response 전달 |
| response 유실 | 내부 성공 | client 관측 |
| R42 retry | 기존900 반환 | 다른 ID의 중복 방지 |
| C 적용 전 read | C의 옛 상태 | 최신 읽기 |

세 Python 파일이 실제로 연결 실행되는 것은 아니다. Raft 모델의 `y=1` command를 debit으로 바꾸는 계층도 구현되어 있지 않다. 세 assert가 각각 통과했다는 사실로 전체 서비스의 원자성을 주장할 수 없다.

## 장애는 위치와 내구 상태로 쓴다

“중간에 crash”나 “timeout”만 적으면 허용 결과를 결정할 수 없다. 정상 시작 상태, 정확한 주입 위치, 각 주체가 마지막으로 본 message·term·offset, 복구 뒤 허용·금지 결과, 확인할 log·metric·assert를 기록한다.

| 이름 | 주입 위치 | 남은 상태 가정 | 기대 복구 |
|---|---|---|---|
| 요청 유실 | 함수 호출 전 | 변화 없음 | 같은 ID로 새 실행 |
| commit 전 crash | 원자 commit 전 | rollback | 새 실행 |
| 응답 유실 | balance와 result commit 뒤 | 효과 남음 | 기존 결과 반환 |
| 복제 전 read | leader apply 뒤 follower apply 전 | follower old | 읽기 계약에 따라 stale 허용 |
| current-term 복제 전 | index2가 한 노드에만 있음 | 과반수 아님 | 성공 응답 금지 |
| apply 뒤 응답 전 | commit·업무 효과 완료 | 결과 남음 | 조회나 dedup으로 확인 |

Python 예제에는 durable 저장소가 없지만, 코드 결과와 구분한 사고 실험으로 다음 표를 쓸 수 있다.

| 단계 | memory | durable | response | restart 후 |
|---|---|---|---|---|
| 시작 | `1000,{}` | `1000,{}` | 없음 | `1000,{}` |
| 계산 | `900,{R42:900}` | `1000,{}` | 없음 | crash면 1000 |
| 원자 commit | `900,{R42:900}` | `900,{R42:900}` | 없음 | crash면 900 |
| response send | 동일 | 동일 | 유실 가능 | retry는 900 |

commit 전 crash와 commit 뒤 응답 유실은 클라이언트에서 모두 timeout처럼 보일 수 있지만 복구 상태는 반대다. timeout을 한 종류로 합치면 재시도 규칙을 정할 수 없다.

## 모델이 실제로 검증하지 않는 경계

| 모델이 확인하는 것 | 모델이 확인하지 않는 것 |
|---|---|
| 고정 사건의 상태 계산 | 실제 socket 유실과 재정렬 |
| follower 적용 전후의 두 read | 전체 복제 protocol과 장애 복구 시간 |
| 현재 term 과반수 산술 | 선거, 상태 적용, client ack |
| 순차 호출의 중복 ID 분기 | 재시작 내구성, 동시 race, DB transaction |
| assert로 표현한 불변식 | 처리량, 보안과 제품 전체 정확성 |

사건 순열을 허용한다면 가능한 순서와 같은 tick의 tie-break 규칙을 정의한다. 그렇지 않으면 Python list 순서가 protocol 규칙처럼 보인다. 동시성 반례도 단순히 thread 두 개를 띄우기보다 ID 검사, balance 변경, results 기록을 사건으로 분해하고 고유 키·transaction의 역할을 모델링해야 한다.

random trace를 쓰면 seed, 생성 범위와 실패 trace를 저장한다. 한 seed에서 반례가 없다는 것은 그 trace에서 발견하지 못했다는 뜻뿐이다. 최소 반례를 찾으면 고정 회귀 입력으로 남긴다.

## 통합 문제와 해설

### 1. replication 모델에서 tick 20을 없애면?

입력 사건 목록에서 유일한 follower `apply`를 제거한 것이므로 tick 25에도 follower 상태는 `(1,0)`이다. reads는 `[(5,1,0),(25,1,0)]`이고 leader는 `(2,1)`, follower는 `(1,0)`이다. 첫 assert는 두 번째 tuple이 다르고, 수렴 assert도 value가 달라 실패한다. “시간이 25까지 지났으니 결국 복제된다”는 결론은 tick을 실제 시간과 혼동한 것이다. tick 30에 replicate 사건을 명시적으로 추가하면 그 뒤 read부터 2를 볼 수 있지만, 사건 없이 시간 숫자만 키워서는 상태가 바뀌지 않는다.

### 2. follower에 index 2를 먼저 적용하면?

`apply(2,value)`의 조건은 `2 == applied_index+1`, 즉 `2==1`이어서 거짓이다. 함수는 필드를 바꾸지 않고 끝나므로 후 상태도 `(1,0)`이다. “더 최신 index니까 바로 2가 된다”는 해석은 연속 적용 조건을 무시한다. 이후 index 1을 적용하면 `(value1,1)`이 되지만, 앞서 버린 index 2는 자동 재생되지 않는다. index 2를 다시 보내는 세 번째 사건이 있어야 `(value2,2)`가 된다. 실제 protocol이 out-of-order entry를 buffer하거나 gap을 요청하는지는 이 모델에 없으므로 그 동작을 주장하려면 상태와 사건을 추가해야 한다.

### 3. 최종 follower 값만 2이면 stale read를 검증한 것인가?

아니다. 최종값만 검사하면 follower가 시작부터 2로 잘못 초기화된 구현도 통과할 수 있다. 이 모델의 첫 주장은 tick 5에서 leader는 2지만 follower read는 `(1,0)`이라는 stale 관측이고, 둘째 주장은 replicate 뒤 둘 다 2라는 수렴이다. 그래서 reads 전체와 최종 value를 따로 assert한다. stale read를 허용하지 않는 선형화 읽기 모델로 조건을 바꾸면 기대 history부터 바뀌어야 하며 단순히 최종 assert만 유지해서는 읽기 계약을 검증할 수 없다.

### 4. A와 B에 term2 index1만 있고 current term4라면?

함수는 후보 index의 entry가 `current_term`과 같은 사본만 센다. A와 B에 index 1, term 2가 있어도 `term==4` 조건을 만족하는 사본은 0이므로 majority 2에 못 미치고 0을 반환한다. “두 노드에 있으니 commit 1”이라는 결론은 과반수와 현재 term 조건 중 앞부분만 적용한 것이다. 이후 term 4의 index 2가 A와 B에 복제되면 함수는 2를 반환하고 term 2의 index 1은 그 prefix에 포함될 수 있다.

### 5. commit_index 2 뒤 바로 client 성공을 출력해도 되는가?

`return 2`가 알려 주는 것은 현재 term 사본을 센 결과뿐이다. log commit 뒤 상태 기계가 `x=1,y=1`을 적용하는 사건, 결과를 durable dedup 표에 기록하는 사건, response를 client에 보내는 사건은 객체와 함수에 없다. 따라서 즉시 성공을 출력하면 모델에 없는 전이를 실행한 셈이다. 이 주장을 검증하려면 `commit_index`, `last_applied`, `response_sent`처럼 상태를 분리하고 crash를 각 경계에 넣어야 한다. 적용 뒤 응답 전 crash라면 재시도는 기존 결과를 찾아야 한다.

### 6. R42를 amount 500으로 다시 호출하면?

첫 호출 뒤 dict의 key는 R42이고 value는 900뿐이며 원래 amount 100은 저장하지 않는다. 두 번째 `debit(R42,500)`은 ID 존재 조건에서 곧바로 900을 반환하므로 500 요청을 실행하지도, 불일치로 알리지도 않는다. “잔액이 안전하니 올바르다”는 결론은 중복 ID 재사용 오류를 놓친다. 실제 경계를 모델링하려면 results 값에 payload hash와 반환값을 함께 저장하고, 같은 ID·같은 payload는 기존 결과를, 같은 ID·다른 payload는 충돌 오류를 반환하도록 해야 한다.

### 7. retry 모델을 재시작해도 `executions==1`인가?

프로세스를 새로 만들면 constructor 입력에 따라 `balance=1000`, `executions=0`, `results={}`로 돌아간다. 첫 실행의 900과 R42가 파일이나 DB에 쓰인 적이 없으므로 재시도는 새 요청 분기로 들어가 executions가 다시 1이 된다. 실제 세계에서 잔액만 별도 저장되고 results만 사라지면 900에서 다시 100을 빼 800이 되는 더 위험한 상태도 가능하다. balance와 request 결과를 같은 영속 transaction으로 commit하고 restart 때 함께 load하는 전이를 추가해야 재시작 후 exactly-once 성질을 시험할 수 있다.

### 8. tick 25를 25ms라고 보고하거나 assert 통과를 전원 장애 안전이라고 말해도 되는가?

tick 25는 event tuple의 정렬용 숫자이며 clock 읽기나 sleep이 없으므로 25ms 지연을 측정하지 않는다. dict 변경도 Python 프로세스 메모리 안에서만 일어나 WAL 기록이나 fsync 성공을 기다리지 않는다. 따라서 빠르다는 결론과 전원 장애 뒤 남는다는 결론 모두 모델 출력 범위를 벗어난다. 실제 latency는 clock과 반복 실험으로, 내구성은 durable commit과 restart load를 넣은 장애 시험으로 따로 검증한다.

### 9. seed 42에서 실패가 없으면 안전한가?

seed 42는 난수 생성기가 만든 한 사건 순서를 다시 얻는 입력이다. 그 순서에 race가 없었다고 다른 순서에도 없다고 일반화할 수 없다. seed 범위, 사건 수와 장애 생성 규칙을 기록하고 여러 경계 timing을 탐색한다. 실패가 나오면 긴 trace를 줄여 최소 반례로 만들고 고정 회귀 입력으로 남긴다. 생성 규칙 자체가 commit 뒤 응답 전 crash를 만들지 않는다면 seed를 아무리 늘려도 그 경계는 검사되지 않는다.

### 10. 출력 상수를 그대로 assert하면 충분한가?

예를 들어 코드가 결과를 계산하지 않고 항상 900을 반환하며 assert도 반환값 900만 검사하면 오류가 통과한다. 독립 기대는 첫 차감 뒤 balance 900, executions 1, results의 정확한 key·value, 재시도 뒤 무변화처럼 여러 관측으로 구성한다. replication에서도 최종 2뿐 아니라 중간 read를, Raft에서도 commit index뿐 아니라 prefix command와 term 조건을 검사한다. 그래도 코드와 assert가 같은 가정을 공유할 수 있으므로 표로 손 계산한 각 전이와 작은 실패 입력을 함께 대조하고, 모델에서 제외한 범위를 결론 바로 옆에 적는다.

## 보고 양식과 자료

보고서에는 초기 객체, 입력 전체 순서, 각 전이 뒤 상태, 실제 반환값과 print, assert, 제외 범위를 함께 적는다. 이 문서의 출력은 소스의 결정적 전이를 손으로 계산한 값이며 새 실행 측정치가 아니다. 코드가 바뀌면 입력, assert와 설명도 함께 다시 검증한다.

- [예제 안내](examples/README.md)
- [TLA+](https://lamport.azurewebsites.net/tla/tla.html)
- [Jepsen](https://jepsen.io/)

[← 이전](12-etcd-spark-iceberg-and-storage.md) · [목차](README.md) · [다음 →](14-experiments-and-research-methods.md)
