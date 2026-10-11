# 13. 로컬 모델과 장애 시나리오

## 입력에서 결과까지 계산하는 모델

toy model은 제품 축소판이 아니라 한 규칙의 결과를 드러내는 실행 가능한 설명이다. 입력, 상태 전이 함수, 관측 결과, 불변식을 분리한다.

복제 모델 입력을 `write(index=1,value=2)`, `read(follower)`, `replicate`, `read(follower)`로 두자. 시작 상태는 leader와 follower 모두 `(value=1, applied=0)`이다.

| 사건 | leader | follower | 관측 |
|---|---|---|---|
| write | (2,1) | (1,0) | 없음 |
| read | (2,1) | (1,0) | 1 |
| replicate | (2,1) | (2,1) | 없음 |
| read | (2,1) | (2,1) | 2 |

모델은 “복제 전 follower 읽기는 오래될 수 있다”를 계산한다. 실제 네트워크, 디스크 reorder, 동시 스레드는 모델에 없다. assert가 통과해도 실제 저장소 정확성을 증명하지 않는다.

재시도 모델은 시작 balance=1000, executions=0, results={}를 입력으로 둔다. R42 debit 100을 실행하면 balance=900, executions=1, results[R42]=900이다. 같은 R42를 다시 넣으면 results를 읽고 실행 수는 1로 남아야 한다.

## 장애 위치와 미검증 조건

장애를 “중간에 발생”이라고 쓰지 않고 커밋 전, 커밋 후 응답 전처럼 정확히 둔다. 모델이 메모리 dict만 사용하면 재시작 내구성을 검증하지 않는다. 논리 tick은 실제 밀리초가 아니다.

| 모델이 확인 | 모델이 확인하지 않음 |
|---|---|
| 고정 사건의 상태 계산 | 실제 socket 유실 |
| 중복 ID 분기 | 디스크 fsync |
| 현재 term 커밋 산술 | 전체 Raft 선거 |
| assert 불변식 | 성능·보안 |

## 추가 문제와 해설

### 1. 출력 상수를 쓰고 같은 상수를 assert하면 왜 부족한가?
입력 사건에서 상태를 계산하지 않아 잘못된 전이도 발견하지 못한다.

### 2. seed를 고정하는 이유는?
실패 trace를 재현해 원인과 수정 전후를 비교하기 위해서다.

### 3. crash를 커밋 전과 후로 나누는 이유는?
같은 timeout이어도 영속 업무 결과가 반대이기 때문이다.

### 4. 모델에서 제외한 조건은 어디에 쓰는가?
결론 바로 옆의 한계로 명시해 제품 보장으로 일반화하지 않게 한다.

### 5. 불변식 예는?
같은 request ID를 여러 번 넣어도 `executions==1`이고 잔액은 한 번만 감소해야 한다.

## 작은 모델을 장애 주장으로 바꾸지 않는 법

로컬 모델은 복제, Raft commit, retry dedup의 상태 전이를 고정 입력으로 확인한다. 실제 network, disk, process scheduler를 재현하지 않으므로 운영 성능 증거가 아니다.

`replication_model.py`에서는 primary 값 10이 replica 두 개에 전달된다고 하자. 한 replica 전달 실패 뒤 retry하면 최종 `[10,10]`이 될 수 있다. 이 결과는 protocol 산술을 보일 뿐 실제 packet loss율이나 복구 시간을 측정하지 않는다.

`raft_commit_model.py`에서 3 node 중 2개가 log index 7을 저장하면 다수결 2를 만족한다. 그러나 application state 적용, client response, leader 교체까지 같은 시각에 끝났다는 뜻은 아니다.

`retry_dedup_model.py`에서 같은 request ID 두 번의 counter 증가가 한 번만 적용되도록 assert할 수 있다. Process memory 집합이면 재시작 내구성은 검증하지 못한다.

장애 시나리오는 다음 다섯 칸으로 쓴다.

1. 정상 시작 상태와 durable state.
2. 정확한 장애 주입 시점.
3. 각 주체가 마지막으로 본 message·term·offset.
4. 복구 뒤 허용되는 결과와 금지되는 결과.
5. 관측할 log·metric·assert.

예: “응답 유실”은 server 업무 commit 뒤 response 전달 전에 끊는다. “요청 유실”과 결과가 다르므로 timeout 한 단어로 합치지 않는다.

### 완전 해설 문제

1. Assert 통과가 실제 cluster 복구를 증명하는가? **해설:** 아니다. Model에 포함한 상태 전이만 확인한다.
2. Raft 다수 저장과 client 성공은 같은가? **해설:** Commit, state machine 적용, response 전달 경계가 남는다.
3. 결정적 모델의 장점은? **해설:** 같은 상태와 event 순서에서 같은 결과를 만들어 regression을 찾기 쉽다.

[← 이전](12-etcd-spark-iceberg-and-storage.md) · [목차](README.md) · [다음 →](14-experiments-and-research-methods.md)

## 모델의 목적

작은 모델은 제품 구현이 아니라 규칙의 결과를 손으로 확인하는 도구다.
이 책의 [예제](examples/README.md)는 고정된 작은 입력만 사용한다.
복제 지연, Raft 커밋 판정, 중복 제거 경계를 각각 분리한다.

```mermaid
flowchart LR
 H[가설] --> M[작은 상태 모델]
 M --> F[장애 주입]
 F --> T[시간순 trace]
 T --> A[불변식 assert]
 A --> R[해석과 한계]
```

## 장애 시나리오 작성법

먼저 정상 상태를 적는다.
그다음 입력과 주체를 적는다.
중간 상태를 노드별로 적는다.
정확한 한 지점에 메시지 유실, 지연, 재시작을 넣는다.
마지막으로 기대 불변식을 적는다.

예: R9 요청이 서버에서 커밋됐지만 응답만 유실된다.
클라이언트는 같은 R9로 재시도한다.
서버의 영속 dedup table에는 R9 결과가 있다.
잔액은 한 번만 바뀌고 같은 결과가 돌아와야 한다.
assert balance == 900과 assert executions == 1을 둔다.

## 결정적 모델

결정적 모델은 같은 입력에 같은 trace를 낸다.
난수를 쓰면 seed와 생성 규칙을 기록한다.
논리 tick 1,2,3을 쓰면 실제 ms 성능으로 해석하지 않는다.
상태 공간을 줄이면 제외한 조건을 문서화한다.

## 세 모델

`replication_model.py`는 비동기 팔로워가 오래된 읽기를 내는 상황을 보인다.
`raft_commit_model.py`는 현재 term 과반수 규칙을 검사한다.
`retry_dedup_model.py`는 응답 유실 뒤 같은 ID 재시도를 검사한다.
모두 Python 표준 라이브러리만 쓰는 교육용 toy다.
실제 네트워크, 디스크, 전체 Raft를 구현하지 않는다.

## 반례

단위 모델 assert 통과는 실제 제품 정확성 증명이 아니다.
모델에서 제외한 디스크 write reorder나 동시성 오류가 제품에 있을 수 있다.
벽시계 sleep 기반 시험은 느린 머신에서 불안정해질 수 있다.

## 문제와 해설

### 1. 실패를 어디에 넣는가?
불변식 의미가 달라지는 구체 경계, 예를 들어 커밋 후 응답 전에 넣는다.

### 2. 고정 입력의 장점은?
trace 재현과 원인 비교가 쉽다.

### 3. 모델 한계를 왜 쓰는가?
독자가 교육 결과를 제품 보장으로 일반화하지 않게 한다.

## 공식 자료

- [TLA+](https://lamport.azurewebsites.net/tla/tla.html)
- [Jepsen](https://jepsen.io/)



## 실제 Python 객체의 뜻과 수명

**모델**은 실제 시스템에서 검토할 규칙만 Python 상태 전이로 줄인 실행 객체다. 파일의 dataclass, dict, event list와 함수가 실제 대상이며 한 프로세스 실행 동안 산다. **입력**은 events, logs와 debit 인자, **상태**는 value·applied_index·log·balance·executions·results, **출력**은 reads·commit_index·반환값과 print다. **불변식**은 모든 허용 실행에서 지켜야 할 조건이며 이 예제에서는 assert가 검사한다. 실제 socket이나 디스크를 재현하지 않고도 잘못된 규칙의 작은 반례를 찾기 위해 필요하다.

## replication_model.py 전체 실행

Replica는 name, value=1, applied_index=0으로 시작한다. apply는 새 index가 applied_index+1일 때만 value와 index를 바꾼다.

| tick | 입력 | 전 상태 | 조건/분기 | 후 상태 | 관측 |
|---:|---|---|---|---|---|
| 시작 | 없음 | L=(1,0), F=(1,0) | - | 동일 | reads=[] |
| 0 | write,L,1,2 | L=(1,0) | 1=0+1 | L=(2,1) | 없음 |
| 5 | read,F | F=(1,0) | read | 변화 없음 | (5,1,0) |
| 20 | replicate,F,1,2 | F=(1,0) | 1=0+1 | F=(2,1) | 없음 |
| 25 | read,F | F=(2,1) | read | 변화 없음 | (25,2,1) |

첫 assert는 reads가 [(5,1,0),(25,2,1)]인지 확인한다. 둘째는 leader.value와 follower.value가 모두 2인지 확인한다. 출력은 두 reads와 converged:2다. 복제 전 follower 읽기는 낡고, replicate 뒤 수렴한다는 두 주장만 검사한다.

생략 범위도 코드에서 읽어야 한다. index2가 먼저 오면 조용히 무시하며 buffer·재요청이 없다. term, 선거, WAL, fsync, concurrent thread와 restart가 없다. tick 5·20·25는 실제 ms가 아니라 순서다. tick20 사건을 삭제하면 두 번째 read가 (25,1,0)이 되어 두 assert가 실패한다. tick30에 같은 index1 replicate를 넣으면 다시 수렴하지만 내구성을 증명하지 않는다.

## raft_commit_model.py 전체 실행

Entry는 immutable한 index, term, command다. A와 B log에는 (1,term2,x=1),(2,term4,y=1), C에는 index1만 있다. current_term=4, node3이므로 majority=3//2+1=2다.

함수는 후보 index 집합 {1,2}를 내림차순 [2,1]로 돈다. index2이면서 term4인 사본은 A와 B 두 개다. copies=2가 majority2 이상이므로 commit_index=2를 즉시 반환한다. A log에서 index<=2인 prefix는 x=1,y=1이다.

| 검사 | A | B | C | copies | 판정 |
|---|---|---|---|---:|---|
| index2,term4 | 있음 | 있음 | 없음 | 2 | commit index2 |
| index1,term4 | 실행 안 함 | 실행 안 함 | 실행 안 함 | - | prefix로 포함 |

assert는 commit_index==2, command 목록 두 개, prefix 첫 항목 term2<current_term4를 검사한다. 과거 term2 항목은 현재 term4 index2가 commit될 때 prefix로 간접 commit된다는 모형이다.

선거·RequestVote·AppendEntries·충돌 rollback·leader 여부·lastApplied·client 응답은 없다. A log를 권위 prefix로 쓰는 입력 가정도 있다. A와 B에 term2 index1만 있고 current_term4라면 term4 copies=0이라 결과 0이다. term2가 과반수라는 이유만으로 직접 commit하지 않는다.

## retry_dedup_model.py 전체 실행

AccountService 초기값은 balance=1000, executions=0, results={}다. 첫 debit(R42,100)은 ID 없음, 100<=1000 조건을 통과해 balance900, executions1, results={R42:900}을 만들고 900을 반환한다. 응답 유실을 가정한 같은 호출은 ID 존재 분기에서 상태를 바꾸지 않고 900을 반환한다.

| 호출 | 전 상태 | 분기 | 후 상태 | 반환 |
|---|---|---|---|---:|
| 첫 R42,100 | 1000,0,{} | 새 ID·잔액 충분 | 900,1,{R42:900} | 900 |
| 재시도 R42,100 | 900,1,{R42:900} | ID 존재 | 동일 | 900 |

assert 네 개는 두 반환값 900, balance900, executions1, results dict를 확인한다. print는 balance:900, executions:1이다. 같은 입력의 재시도 효과가 한 번이라는 규칙을 보인다.

같은 R42로 amount500을 보내도 payload 비교 없이 900을 반환한다. process restart면 dict가 사라진다. 두 thread가 동시에 ID 없음 분기를 통과하는 race, DB transaction, 외부 결제, TTL이 없다. 실제 dedup은 ID와 payload hash를 영속 transaction에 저장해야 한다.

## 장애 위치를 경계로 쓴다

| 이름 | 주입 위치 | 남은 상태 가정 | 기대 복구 |
|---|---|---|---|
| 요청 유실 | 함수 호출 전 | 변화 없음 | 같은 ID 새 실행 |
| commit 전 crash | 원자 commit 전 | rollback | 새 실행 |
| 응답 유실 | balance+result commit 뒤 | 효과 남음 | 기존 결과 반환 |
| 복제 전 read | leader apply 뒤 follower 전 | follower old | 계약에 따라 stale 허용 |
| current-term 복제 전 | index2 한 노드만 | 과반수 아님 | 성공 응답 금지 |
| apply 뒤 응답 전 | commit·업무 효과 뒤 | 결과 남음 | 조회·dedup |

“중간 crash”라는 한 줄은 부족하다. 요청 전인지 commit 후인지에 따라 허용 결과가 반대다. 논리 tick, 마지막 durable 상태와 응답 전달 여부를 따로 적는다.

## 모델 확장 원칙과 한계

제품 검사기를 구현해 분량을 늘리지 않는다. 한 주장에 필요한 최소 상태를 더한다. gap 적용을 보려면 index2 먼저, index1, index2 재전송의 세 사건이면 된다. 실제 TCP는 필요 없다. random trace를 쓰면 seed와 생성 범위, 실패 trace를 기록한다. seed는 재현 주소이지 정확성 증거가 아니다.

assert가 통과해도 모델 밖의 오류는 남는다. Python dict는 fsync하지 않고 process crash를 견디지 않는다. 사건 loop는 thread interleaving이 없다. 메모리 쓰기 순서와 디스크 reorder도 없다. 결과 문장은 “이 고정 입력에서 이 assert가 통과했다”로 제한한다.

## 추가 완전 풀이

### 문제 6. replication 모델에서 tick20을 없애면?

**풀이:** reads는 [(5,1,0),(25,1,0)]이 되어 기대 assert와 다르고 leader2, follower1이라 수렴 assert도 실패한다. 복제 사건 없이는 follower가 자동 갱신되지 않는다.

### 문제 7. follower에 index2를 먼저 적용하면?

**풀이:** 초기 applied_index0이므로 2==1 조건이 거짓이고 변화가 없다. 실제 protocol의 gap 요청이나 buffer는 이 모델에 없다.

### 문제 8. A와 B에 term2 index1만 있고 current_term4라면?

**풀이:** index1의 term4 copies는 0이라 commit_index0이다. 과거 term 항목의 과반수 존재만으로 직접 commit하지 않는 규칙이다.

### 문제 9. R42,500을 재호출하면?

**풀이:** 기존 ID 분기에서 900을 반환해 입력 불일치를 숨긴다. 실제 시스템은 payload hash를 비교해 충돌로 거부해야 한다.

### 문제 10. assert 통과가 전원 장애 안전을 뜻하는가?

**풀이:** 아니다. 모델은 process memory만 쓴다. WAL, fsync, restart load를 표현하지 않는다.

### 문제 11. tick25를 25ms라고 보고해도 되는가?

**풀이:** 안 된다. sleep이나 clock 측정이 없으며 tick은 사건 순서다. 실제 latency는 별도 실험으로 측정한다.

### 문제 12. seed42에서 실패가 없으면 안전한가?

**풀이:** 한 trace에 반례가 없다는 뜻이다. 경계값과 여러 생성 범위를 탐색하고 발견한 최소 반례를 고정 회귀 사례로 남긴다.



## 세 모델을 하나의 요청으로 연결하기

클라이언트 R42가 100 차감을 보냈다고 가정한다. leader는 명령을 term4 index2에 넣고 A·B에 복제한다. raft 모델은 index2 commit을 계산한다. 상태 기계가 debit을 실행해 balance900과 results R42=900을 만든다. 응답이 유실되면 retry 모델은 같은 ID 결과를 반환한다. follower C가 아직 index1이면 replication 모델처럼 오래된 읽기를 줄 수 있다.

| 경계 | 권위 상태 | 아직 보장하지 않는 것 |
|---|---|---|
| A에 index2 append | leader log | quorum commit |
| A·B에 term4 index2 | commit_index2 가능 | state apply |
| debit apply | balance900, result 저장 | client response 전달 |
| response 유실 | 내부 성공 | client 관측 |
| R42 retry | 기존900 반환 | 다른 ID 중복 방지 |
| C 적용 전 read | C의 old state | 최신 읽기 |

이 연결은 각 모델의 출력이 다음 모델 입력이 될 수 있음을 보여 주지만 실제 코드 세 파일이 함께 실행되는 것은 아니다. Raft 모델의 command 문자열 y=1과 retry 모델 debit 사이 변환도 구현돼 있지 않다. 따라서 “세 assert가 각각 통과했으니 전체 서비스가 원자적”이라고 결론 내리면 안 된다.

## 상태 공간과 반례 선택

replication 모델의 두 replica와 네 사건은 가능한 실제 실행 중 하나만 고른다. 사건을 순열로 바꾸면 read가 replicate 뒤 올 수도 있고 두 번 모두 앞에 올 수도 있다. 모델이 허용하는 순서를 먼저 정의하고, 같은 tick의 tie-break 규칙도 정한다. 그렇지 않으면 우연한 list 순서가 protocol 규칙처럼 보인다.

Raft 모델은 각 node가 같은 index에 하나의 entry만 가진다고 가정한다. 충돌 반례를 보려면 B index2 term3 z=9, leader A index2 term4 y=1 같은 상태와 prevLogTerm 검사를 모델에 추가해야 한다. 단순 committed_index 함수에 충돌 log를 넣으면 any 검사만 통과해 실제 Raft보다 잘못된 결론을 낼 수 있다. 모델 전제에 맞지 않는 입력은 전이를 보강한 뒤 사용한다.

retry 모델은 순차 호출만 있다. 동시성 반례는 두 호출이 ID 검사, balance 변경, results 기록의 어느 단계에서 교차하는지 사건으로 분해해야 한다. 고유 키와 DB transaction을 추가하지 않은 채 thread 두 개만 돌리면 스케줄에 따라 비결정적이고 원인 설명이 약해진다.

## crash와 durable state를 분리한 종이 모델

실제 코드를 바꾸지 않고도 durable 열을 표에 추가할 수 있다. 첫 R42 처리에서 메모리 balance를 900으로 만든 뒤 durable commit 전 crash하면 복구 balance1000, results{}다. durable transaction 뒤 response 전 crash면 복구 balance900, results{R42:900}다. 이 두 상태를 섞으면 재시도 기대를 정할 수 없다.

| 단계 | memory | durable | response | restart 후 |
|---|---|---|---|---|
| 시작 | 1000,{} | 1000,{} | 없음 | 1000,{} |
| 계산 | 900,{R42:900} | 1000,{} | 없음 | crash면 1000 |
| 원자 commit | 900,{R42:900} | 900,{R42:900} | 없음 | crash면 900 |
| response send | 동일 | 동일 | 유실 가능 | retry는 900 |

Python 예제에는 durable 열이 실제로 없으므로 이 표는 확장 가정이다. 문서에서 코드 실행 결과와 사고 실험을 구분해 표시한다.

## assert 설계의 양방향 검사

최종 balance900만 검사하면 두 번 100 차감한 뒤 100을 보상해도 통과할 수 있다. executions==1과 results dict를 함께 검사해 경로를 제한한다. replication도 최종 값2만 보면 follower가 처음부터2였던 잘못된 초기화가 통과할 수 있어 중간 reads를 검사한다. Raft도 commit_index2만 보면 잘못된 command가 들어갈 수 있어 prefix command 목록과 과거 term 조건을 확인한다.

assert는 구현을 그대로 반복하는 상수 비교가 아니라 독립 불변식에 가까워야 한다. 그래도 같은 잘못된 가정을 코드와 assert가 공유할 수 있다. 표로 손 계산한 기대, 작은 반례와 코드 출력을 대조한다.

## 추가 풀이

### 문제 13. 최종 follower 값만 2이면 stale read 모델이 검증됐는가?

**풀이:** 아니다. 중간 tick5 read가 1이었는지 확인해야 복제 전 stale 관측을 검증한다. 최종 수렴 assert와 중간 history assert는 서로 다른 주장이다.

### 문제 14. commit_index2 뒤 바로 client 성공을 출력해도 되는가?

**풀이:** 모델에는 state machine apply와 response 전송이 없다. commit, apply, client ack 경계를 추가하기 전에는 성공 시점을 주장할 수 없다.

### 문제 15. retry 모델을 재시작해도 executions1인가?

**풀이:** 새 AccountService는 초기값으로 돌아가 results를 잃는다. 영속 DB에서 balance와 result를 원자 복원하는 코드를 넣지 않았으므로 재시작 내구성은 검증 밖이다.

또한 예제 실행은 Python 표준 라이브러리만 사용하지만 이 문서에서는 명령 실행 결과를 새로 측정하지 않았다. 출력은 소스의 결정적 전이를 손으로 전수 계산한 값이다. 코드가 바뀌면 입력 목록, assert와 이 설명을 함께 다시 검증해야 한다. 모델 파일의 docstring처럼 세 예제는 교육용이며 실제 저장소·Raft·결제 구현이 아니다.

특히 실제 클러스터의 처리량, 장애 확률과 복구 시간은 이 세 파일에서 관측하지 않았으므로 어떤 숫자도 운영 성능으로 인용하지 않는다.

제외한 조건은 실패가 아니라 모델 적용 범위의 경계다.

## 보고 양식

초기 객체, 입력 전체 순서, 각 전이 후 상태, 최종 출력, assert와 제외 범위를 함께 기록한다. 가상 숫자는 실행 규칙 설명이며 제품 성능 결과가 아니다.


[← 이전](12-etcd-spark-iceberg-and-storage.md) · [목차](README.md) · [다음 →](14-experiments-and-research-methods.md)
