# 07. 트랜잭션과 2단계 커밋

[← 이전](06-consensus-failures-and-snapshots.md) · [목차](README.md) · [다음 →](08-sharding-and-reconfiguration.md)

## 원자성과 2PC

트랜잭션의 **원자성**은 여러 변경이 모두 적용되거나 모두 취소되는 성질이다.
2PC(Two-Phase Commit)는 coordinator와 participant가 분산 원자 결정을 맞추는 프로토콜이다.

```mermaid
sequenceDiagram
 participant C as Coordinator
 participant A as 계좌 shard A
 participant B as 계좌 shard B
 C->>A: PREPARE T9
 C->>B: PREPARE T9
 A-->>C: YES, 잠금+로그
 B-->>C: YES, 잠금+로그
 C->>C: COMMIT T9 영속 기록
 C->>A: COMMIT
 C->>B: COMMIT
```

입력은 거래 ID와 참여자별 변경이다.
prepare 단계에서 참여자는 검사하고 잠금과 준비 로그를 영속화한다.
YES 뒤에는 혼자 abort할 수 없는 중간 상태가 된다.
모두 YES면 coordinator가 COMMIT을 영속 기록한다.
하나라도 NO면 ABORT를 기록한다.
두 번째 단계에서 결정을 참여자에게 보낸다.

## blocking

참여자 A가 YES를 보낸 직후 coordinator와 통신이 끊겼다고 하자.
A는 다른 참여자의 표와 coordinator 결정을 모른다.
임의 commit은 원자성을 깰 수 있고 임의 abort도 이미 기록된 commit과 충돌할 수 있다.
따라서 결정을 배울 때까지 잠금과 prepared 상태를 유지할 수 있다.
이것이 2PC의 blocking 성질이다.
coordinator 로그를 복제하거나 합의 프로토콜을 결합하면 단일 장애를 줄이지만 프로토콜 조건은 더 복잡해진다.

### participant 내부 상태를 따라가기

participant는 단순히 YES 문자열만 돌려주지 않는다.
거래 T9가 바꿀 행, 잡은 잠금, undo/redo 정보, 현재 단계가 로컬 저장소에 남는다.

| 상태 | 디스크에 남은 정보 | 허용 행동 |
|---|---|---|
| INIT | 거래 ID와 작업 시작 | prepare 검사 |
| PREPARED | 변경 재현 정보와 YES 사실 | 전역 결정 대기 |
| COMMITTED | commit 결정과 적용 결과 | 잠금 해제, 결과 반환 |
| ABORTED | abort 결정과 복구 결과 | 잠금 해제 |

t=0에 coordinator가 A와 B에 PREPARE T9를 보낸다.
t=10에 A가 행 잠금과 PREPARED를 디스크에 쓰고 YES를 보낸다.
t=15에 B도 같은 절차를 마친다.
t=20에 coordinator가 COMMIT을 디스크에 쓴다.
t=21에 coordinator가 멈춰 결정 메시지가 전달되지 않는다.
A와 B는 timeout을 보지만 PREPARED를 지우면 안 된다.
복구된 coordinator나 결정 기록의 복제본에서 COMMIT을 배운 뒤 적용한다.

NO를 보낸 participant는 prepare 조건을 충족하지 못한 것이다.
YES를 보낸 participant와 달리 전역 commit에 참여할 준비가 끝나지 않았다.
coordinator는 하나라도 NO이면 ABORT를 선택한다.
그러나 메시지 유실 때문에 참여자별 관측 시각은 다를 수 있다.

### 2PC와 로컬 데이터베이스 경계

coordinator 메모리에만 참여자 목록을 두면 재시작 뒤 누구에게 결정을 재전송할지 모른다.
결정은 참여자 통지 전에 영속화해야 한다.
참여자는 결정 적용 후 확인을 보내고, coordinator는 모든 정리 조건을 만족한 뒤 기록을 수거한다.
준비 거래가 오래 남으면 잠금이 정상 요청을 막으므로 운영자는 임의 삭제보다 결정 복구 경로를 먼저 사용해야 한다.

## 수치 추적

prepare 왕복 20 ms, 결정 영속화 5 ms, commit 왕복 20 ms인 교육 모형은 최소 약 45 ms다.
한 참여자가 200 ms 지연되면 전체 결정이 그 지연을 기다릴 수 있다.
timeout으로 기다림을 끝내도 prepared 결과는 자동 abort가 아니다.

## 반례

2PC는 Raft와 같은 합의 알고리즘 자체가 아니다.
2PC participant가 YES 뒤 독립적으로 결정을 만들 수 없기 때문이다.
데이터베이스 내부 원자 커밋과 외부 이메일 발송을 한 트랜잭션으로 묶지 못하면 outbox 같은 경계 설계가 필요하다.

## 문제와 해설

### 1. YES 전에 무엇을 영속화하는가?
commit 명령을 나중에 수행할 수 있는 변경과 prepared 상태다.

### 2. coordinator 장애 때 왜 막히는가?
참여자가 전역 결정을 모르며 어느 쪽 추측도 원자성을 깰 수 있다.

### 3. timeout은 abort 증거인가?
아니다. 결정 메시지 유실일 수 있어 결과 조회와 복구가 필요하다.

## 공식 자료

- [PostgreSQL PREPARE TRANSACTION](https://www.postgresql.org/docs/current/sql-prepare-transaction.html)

[← 이전](06-consensus-failures-and-snapshots.md) · [목차](README.md) · [다음 →](08-sharding-and-reconfiguration.md)
## 상세 추적: crash 위치별 복구

participant는 YES 전에 거래 ID, 변경 재현 정보, 잠금, PREPARED 상태를 영속화한다. YES 뒤에는 혼자 abort할 수 없다.

| crash 지점 | coordinator 기록 | participant 상태 | 복구 |
|---|---|---|---|
| PREPARE 전 | 없음 | INIT | abort 가능 |
| 일부 YES 뒤 | 결정 없음 | 일부 PREPARED | abort 통지 |
| COMMIT 기록 뒤 | COMMIT | PREPARED | commit 재전송 |
| 적용 뒤 ack 전 | COMMIT | COMMITTED | 중복 commit 멱등 처리 |

t=0 PREPARE 전송, t=10 A가 PREPARED+YES, t=15 B가 PREPARED+YES, t=20 coordinator가 COMMIT 영속화, t=21 coordinator crash라고 하자. timeout은 abort 증거가 아니다. 복구된 coordinator가 COMMIT을 읽어 재전송한다.

coordinator가 COMMIT을 메모리에만 두고 통지하면 참여자별 결정이 갈릴 수 있다. 결정은 통지 전에 영속화해야 한다. participant도 PREPARED 기록보다 YES를 먼저 보내면 재시작 뒤 commit을 수행할 정보를 잃을 수 있다.

2PC는 원자 결정을 맞추며 직렬화 격리를 자동 제공하지 않는다. 보상 가능한 업무의 saga도 과거를 지우는 rollback이 아니라 새 업무다. 이미 보낸 이메일은 완전히 되돌릴 수 없는 반례다.
