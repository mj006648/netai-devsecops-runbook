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

[← 이전](12-etcd-spark-iceberg-and-storage.md) · [목차](README.md) · [다음 →](14-experiments-and-research-methods.md)
