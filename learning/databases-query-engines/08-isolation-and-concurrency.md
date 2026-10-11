# 08. Isolation과 concurrency

[이 책 목차](README.md) · [이전: MVCC와 snapshot visibility](07-mvcc-and-snapshot-visibility.md) · [다음: WAL, checkpoint와 recovery](09-wal-checkpoints-and-recovery.md)

여러 사용자가 같은 database를 동시에 쓰면 각 transaction 코드가 혼자 실행될 때는 맞아도 겹친 순서 때문에 잘못된 결과가 생길 수 있다. isolation level은 concurrent transaction이 어떤 중간 상태를 볼 수 있고, 어떤 실행을 기다리거나 실패시켜야 하는지 정하는 계약이다.

이 장은 SQL 표준이 isolation level에 요구하는 최소 계약과 PostgreSQL 18의 실제 보장을 분리한다. PostgreSQL의 Repeatable Read는 phantom read도 막는 더 강한 snapshot isolation이지만 Serializable과 같지 않다. write skew 같은 serialization anomaly는 남을 수 있다.

## 1. concurrent transaction과 serial execution

**concurrent transaction(동시 트랜잭션)**은 수명이 시간상 겹쳐 실행되는 transaction들이다. CPU가 정확히 같은 순간에 실행하지 않아도 BEGIN과 COMMIT 사이 operation이 교차하면 concurrent하다.

**serial execution(직렬 실행)**은 transaction 하나를 끝낸 뒤 다음 transaction을 시작하는 실행이다. TA 전체→TB 전체 또는 TB 전체→TA 전체처럼 operation이 섞이지 않는다. 이해하기 쉽지만 모든 작업을 물리적으로 직렬화하면 처리량과 latency가 나빠질 수 있다.

**serializable(직렬화 가능)**은 동시에 실행해 성공한 transaction들의 효과가 어떤 serial order로 실행한 것과 같다는 계약이다. 실제 내부 실행을 한 번에 하나로 제한할 필요는 없다. MVCC와 dependency 추적으로 동시 실행을 허용하고 직렬 순서로 설명할 수 없는 위험이 생기면 transaction 하나를 abort할 수 있다.

## 2. read와 write가 남기는 실제 상태

transaction이 table row를 읽을 때 backend는 snapshot과 tuple version을 사용한다. 일반 SELECT의 read가 row write lock을 항상 잡는 것은 아니다. PostgreSQL Serializable에서는 읽은 데이터 범위를 추적하는 SIReadLock 형태의 predicate lock 정보가 생길 수 있으며, 이는 일반 blocking lock과 목적이 다르다.

**lock(잠금)**은 동시에 수행하면 충돌하는 operation을 기다리거나 거부하기 위해 커널이 아니라 DBMS lock manager가 관리하는 상태다. table lock, row-level lock, advisory lock 등이 있다. owner transaction이 commit 또는 rollback하면 보통 해제된다.

**wait queue(대기열)**는 이미 lock을 가진 transaction 때문에 기다리는 요청을 관리한다. **wait-for graph(대기 그래프)**는 TA가 TB를 기다리는 방향을 edge로 나타낸다. cycle이 생기면 누구도 진행할 수 없는 deadlock이다.

**dependency(의존 관계)**는 한 transaction의 read나 write 결과가 다른 transaction operation에 영향을 받는 관계다. serializable 검사는 blocking lock만이 아니라 read-write dependency 조합도 추적할 수 있다.

## 3. SQL 표준의 네 현상

### Dirty read

**dirty read(더티 리드)**는 다른 transaction이 아직 commit하지 않은 data를 읽는 현상이다.

초기 x=10에서 T1이 x=20을 쓰고 아직 commit하지 않았다. T2가 20을 읽은 뒤 T1이 rollback하면 T2는 database에 존재한 적 없는 committed 값을 사용했다. PostgreSQL에서는 Read Uncommitted를 요청해도 Read Committed처럼 동작해 dirty read를 허용하지 않는다.

### Nonrepeatable read

**nonrepeatable read(반복 불가능 읽기)**는 한 transaction이 같은 row를 다시 읽었을 때 concurrent committed update 때문에 값이 달라지는 현상이다.

T1 Read Committed가 x=10을 읽고, T2가 x=20으로 commit한 뒤 T1의 다음 SELECT가 20을 볼 수 있다. 각 statement snapshot이 다르기 때문이다.

### Phantom read

**phantom read(팬텀 읽기)**는 같은 search predicate query를 다시 실행했을 때 concurrent commit으로 조건을 만족하는 row 집합이 달라지는 현상이다.

T1이 WHERE amount >= 100으로 order 5개를 읽는다. T2가 amount=150 order를 INSERT하고 commit한다. T1의 다음 query가 6개를 보면 새 row가 phantom이다.

SQL 표준은 Repeatable Read에서 phantom을 허용할 수 있는 최소 표를 정의하지만 PostgreSQL 18 Repeatable Read는 transaction snapshot을 유지하므로 phantom을 허용하지 않는다.

### Serialization anomaly

**serialization anomaly(직렬화 이상)**는 성공한 transaction 전체 결과를 가능한 어떤 serial order로도 설명할 수 없는 현상이다. 같은 row 반복 읽기와 phantom을 막아도 여러 row predicate를 각 transaction이 읽고 서로 다른 row를 쓰면 write skew가 생길 수 있다.

## 4. isolation level 표: 표준 최소와 PostgreSQL 보장

| 요청 level | SQL 표준이 금지해야 하는 최소 현상 | PostgreSQL 18 실제 핵심 |
|---|---|---|
| Read Uncommitted | 최소 금지 없음 | 내부적으로 Read Committed처럼 동작, dirty read 없음 |
| Read Committed | dirty read 금지 | statement 시작 snapshot, nonrepeatable·phantom·serialization anomaly 가능 |
| Repeatable Read | dirty·nonrepeatable 금지, phantom은 표준상 가능 | transaction snapshot, phantom도 없음, serialization anomaly 가능 |
| Serializable | 네 현상 모두 금지 | RR 기반 snapshot + SSI dependency 검사, 위험 시 serialization failure |

표준은 level이 최소보다 더 강한 보장을 제공하는 것을 허용한다. 그래서 PostgreSQL Repeatable Read가 phantom을 막아도 표준 위반이 아니다. 제품이 다르면 같은 이름의 내부 algorithm과 추가 보장이 다를 수 있다.

## 5. lost update 전체 trace

**lost update(갱신 분실)**는 두 transaction이 같은 old 값을 읽고 각각 새 값을 계산한 뒤, 나중 write가 앞 write 효과를 덮어 한 갱신이 사라지는 현상이다.

초기 counter=10이고 application이 “읽은 값에 1을 더한 절대값을 UPDATE”한다고 하자.

| 시각 | T1 | T2 | committed counter |
|---:|---|---|---:|
| t0 | BEGIN | BEGIN | 10 |
| t1 | SELECT→10 | | 10 |
| t2 | | SELECT→10 | 10 |
| t3 | UPDATE counter=11 | | 10 |
| t4 | COMMIT | waits 또는 이후 진행 | 11 |
| t5 | | UPDATE counter=11 | 11 |
| t6 | | COMMIT | 11 |

두 번 증가했지만 결과는 11이다. T2가 old application value 10으로 계산한 11을 썼기 때문이다.

다음 방법을 구분한다.

1. UPDATE counter = counter + 1처럼 database가 current row에 연산을 적용하게 한다. PostgreSQL Read Committed의 concurrent update 규칙에 따라 updated version과 predicate를 다시 다룰 수 있다.
2. SELECT FOR UPDATE로 row를 잠근 뒤 읽고 계산한다.
3. row에 version column을 두고 UPDATE ... WHERE version = old_version으로 optimistic validation을 한다.
4. Repeatable Read나 Serializable에서 conflict error를 받고 전체 transaction을 retry한다.

어느 방법도 외부 API와 자동 결합하지 않는다. 또한 여러 row predicate invariant는 한 row lost update 방지로 충분하지 않다.

## 6. dirty·nonrepeatable·phantom의 결과 비교

초기 products에는 price>=100 row가 P1 하나라고 하자.

| 시각 | T1 RC | T2 | T1 결과 |
|---:|---|---|---|
| t1 | SELECT predicate | - | {P1} |
| t2 | - | INSERT P2 price150, 미커밋 | - |
| t3 | SELECT 실행 중이라 가정 | 미커밋 | P2 dirty read 안 함 |
| t4 | - | COMMIT | - |
| t5 | 같은 SELECT 새 statement | committed | {P1,P2} |

t3에서 P2를 읽으면 dirty read지만 PostgreSQL RC는 읽지 않는다. t5에서 row 집합이 달라지는 것은 phantom이다. P1 자체 가격이 100에서 120으로 바뀌었다면 같은 row 값 변화는 nonrepeatable read다.

PostgreSQL RR의 T1이라면 t1 snapshot을 유지해 t5에서도 {P1}을 본다. 자기 transaction이 INSERT한 row는 self-visibility 규칙으로 볼 수 있으므로 “snapshot 뒤 모든 새 row가 절대 안 보인다”는 표현에는 자기 변경 예외가 있다.

## 7. 두 의사의 write skew 전체 상태

doctors table은 다음과 같다.

| doctor | on_call |
|---|---|
| A | true |
| B | true |

업무 invariant는 “A와 B 중 적어도 한 명은 on_call=true”다.

TA는 A가 퇴근하려는 transaction이고 TB는 B가 퇴근하려는 transaction이다. 각 transaction은 다른 의사가 당직인지 확인한 뒤 자기 row만 false로 바꾼다.

~~~sql
-- TA
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT on_call FROM doctors WHERE doctor='B'; -- true
UPDATE doctors SET on_call=false WHERE doctor='A';
COMMIT;

-- TB
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT on_call FROM doctors WHERE doctor='A'; -- true
UPDATE doctors SET on_call=false WHERE doctor='B';
COMMIT;
~~~

시간표:

| 시각 | TA | TB | committed 상태 |
|---:|---|---|---|
| t0 | BEGIN snapshot SA | BEGIN snapshot SB | A=true, B=true |
| t1 | B=true 읽음 | | 동일 |
| t2 | | A=true 읽음 | 동일 |
| t3 | A=false version 생성 | | 아직 둘 다 true가 committed |
| t4 | | B=false version 생성 | 동일 |
| t5 | COMMIT 성공 | | A=false, B=true |
| t6 | | COMMIT 성공 가능 | A=false, B=false |

서로 다른 row를 쓰므로 simple same-row writer conflict가 없다. 각 RR snapshot은 시작 때 둘 다 true였으므로 자기 판단은 snapshot 안에서 타당하다.

TA→TB serial order라면 TB는 A=false를 읽고 B를 끄면 안 된다. TB→TA라면 TA는 B=false를 읽고 A를 끄면 안 된다. 어느 serial order도 둘 다 false를 만들지 않으므로 결과는 serialization anomaly다.

~~~mermaid
flowchart LR
 RA[TA reads B=true] --> WA[TA writes A=false]
 RB[TB reads A=true] --> WB[TB writes B=false]
 WA -. TB의 읽은 조건을 무효화 .-> RB
 WB -. TA의 읽은 조건을 무효화 .-> RA
 C[read-write dependency cycle 위험] --> F[한 transaction serialization failure 가능]
 RA --> C
 RB --> C
~~~

## 8. explicit lock으로 write skew 막기

판단에 참여하는 A와 B row를 같은 순서로 잠근다고 하자.

1. TA가 SELECT ... WHERE doctor IN ('A','B') ORDER BY doctor FOR UPDATE로 A, B를 잠근다.
2. TB도 A부터 요청하지만 TA가 가진 lock 때문에 기다린다.
3. TA는 둘 다 true를 읽고 A=false를 쓰고 commit한다.
4. lock이 풀리면 TB가 A=false, B=true의 최신 상태를 확인한다.
5. invariant 때문에 TB는 B를 false로 바꾸지 않고 transaction을 끝낸다.

잠글 row가 현재 존재하는 두 의사로 고정되어 있다는 조건에서 동작한다. “특정 시간대에 당직자가 최소 한 명”처럼 아직 존재하지 않는 row INSERT도 조건을 바꿀 수 있다면 기존 row lock만으로 predicate 전체를 보호하기 어려울 수 있다. advisory lock, 별도 guard row, exclusion/unique constraint나 Serializable을 검토한다.

lock 순서를 일관되게 해야 deadlock 가능성을 줄인다. TA가 A→B, TB가 B→A 순서로 잠그면 각각 하나를 가진 채 상대 lock을 기다릴 수 있다.

## 9. deadlock의 실제 cycle

초기에는 lock이 없다.

| 시각 | TA | TB | wait-for edge |
|---:|---|---|---|
| d1 | A row lock 획득 | B row lock 획득 | 없음 |
| d2 | B lock 요청, 대기 | B 보유 | TA→TB |
| d3 | A 보유 | A lock 요청, 대기 | TB→TA |
| d4 | detector가 cycle 발견 | | TA↔TB |
| d5 | 한쪽을 victim으로 abort | 다른 쪽 진행 | cycle 제거 |

**deadlock(교착 상태)**은 기다림 cycle 때문에 외부 개입 없이 어느 transaction도 진행할 수 없는 상태다. DBMS deadlock detector는 graph를 검사해 victim 하나를 abort한다. PostgreSQL에서는 deadlock detected error의 SQLSTATE가 40P01일 수 있다.

lock timeout은 오래 기다린 요청을 끝낼 수 있지만 cycle의 논리적 원인을 없애지는 않는다. 일관된 lock order, 짧은 transaction, 필요한 row만 잠그는 설계로 빈도를 줄인다. victim application은 전체 transaction을 재시도할 수 있어야 한다.

deadlock과 serialization failure는 다르다. deadlock은 blocking lock wait cycle이고, serialization failure는 성공시키면 serial order로 설명할 수 없는 dependency 위험이다. 둘 다 abort와 retry가 필요할 수 있지만 관측과 해결 방향이 다르다.

## 10. MVCC, lock, OCC의 역할 차이

**MVCC(Multi-Version Concurrency Control)**는 여러 row version과 snapshot으로 reader가 적절한 version을 선택하게 한다. 일반 read와 write의 불필요한 blocking을 줄이지만 writer conflict와 write skew를 모두 자동 제거하지 않는다.

**pessimistic locking(비관적 잠금)**은 conflict 가능성이 있다고 보고 읽거나 쓰기 전에 lock을 얻는다. conflict가 잦고 기다린 뒤 성공하는 것이 유리할 때 적합할 수 있다. lock 범위가 넓거나 순서가 불규칙하면 blocking과 deadlock이 늘어난다.

**OCC(Optimistic Concurrency Control, 낙관적 동시성 제어)**는 먼저 작업하고 commit 전 validation에서 읽은 상태가 여전히 유효한지 검사한다. conflict가 드물다는 가정에서 blocking을 줄이지만 실패하면 계산을 버리고 retry한다.

application version-column OCC 예:

~~~sql
UPDATE accounts
SET balance = 400, version = version + 1
WHERE id='A' AND version=7;
~~~

affected rows가 1이면 version7을 성공적으로 갱신했다. 0이면 다른 transaction이 version을 바꿨을 수 있어 old read 기반 판단을 버리고 다시 읽는다. 0 row의 다른 원인도 query 조건에 따라 검토한다.

Serializable Snapshot Isolation도 optimistic 성격으로 dependency를 관측하다 위험한 execution을 abort할 수 있다. 단순 version-column OCC와 같은 구현은 아니다.

## 11. PostgreSQL SSI와 predicate lock

PostgreSQL Serializable은 Repeatable Read snapshot 동작에 **SSI(Serializable Snapshot Isolation)** 검사를 더한다. transaction들이 읽은 data와 concurrent write 사이의 read-write dependency를 추적해 serialization anomaly로 이어질 위험한 구조를 찾는다.

PostgreSQL 문서의 **predicate lock**은 앞선 query 결과에 영향을 줄 수 있었던 write를 탐지하기 위한 SIReadLock 상태다. 일반 exclusive lock처럼 writer를 block하지 않는다. 그래서 predicate lock 자체가 deadlock을 만들지는 않지만 dependency 정보와 memory overhead가 있다.

두 의사 예에서 TA가 B를 읽고 TB가 B를 쓰는 관계, TB가 A를 읽고 TA가 A를 쓰는 관계가 교차한다. 둘을 모두 commit하면 cycle 위험이 생겨 engine이 한 transaction을 serialization failure로 abort할 수 있다.

모든 rw dependency 하나가 즉시 abort라는 단순 규칙은 아니다. PostgreSQL은 dangerous structure와 commit 순서 조건을 판단한다. application 관점에서 중요한 계약은 Serializable transaction이 40001 오류로 실패할 수 있고 전체를 retry해야 한다는 것이다.

## 12. retry는 transaction 전체를 새 snapshot에서 수행한다

serialization failure가 COMMIT에서 발생했다고 하자. 이미 실행한 마지막 UPDATE만 다시 보내면 안 된다. 두 의사 예에서 “다른 의사가 true였다”는 판단이 old snapshot에서 나온 것이기 때문이다.

올바른 retry loop:

1. stable business input과 request id를 준비한다.
2. BEGIN과 isolation level을 설정한다.
3. 필요한 row와 predicate를 새 snapshot에서 다시 읽는다.
4. 업무 invariant를 다시 계산한다.
5. 허용되면 write한다.
6. COMMIT한다.
7. 40001 serialization failure 또는 retry 가능한 deadlock이면 ROLLBACK 후 backoff하고 2단계부터 반복한다.
8. 성공 commit 뒤에만 결과를 확정하고 external effect를 전달한다.

**backoff(재시도 간격 늘리기)**는 즉시 같은 경쟁을 반복하지 않도록 짧은 지연과 무작위 흔들림을 두는 방법이다. 무한 retry하지 않고 횟수·deadline을 제한하며 최종 실패를 client에 알린다.

transaction 중 읽은 값은 abort 뒤 유효한 업무 결과로 사용하지 않는다. PostgreSQL Serializable의 일반 read-only transaction도 성공 commit 전까지 결과 확정을 기다려야 한다. safe snapshot을 기다리는 deferrable read-only transaction은 별도 조건이 있다.

## 13. external side effect와 retry

transaction 안에서 email을 먼저 보내고 COMMIT에서 serialization failure가 나면 retry 때 이메일이 중복된다. database transaction이 abort해도 external API는 rollback되지 않는다.

outbox pattern은 database row 변경과 event row를 같은 transaction에 쓴다. 성공 commit 후 publisher가 event를 전달하고 consumer가 event id로 deduplicate한다. retry할 때 같은 business request id를 사용해 duplicate order나 payment도 막는다.

sequence 값은 transaction abort로 되돌아가지 않는 PostgreSQL object다. retry마다 nextval 결과가 건너뛸 수 있으므로 sequence를 gap 없는 업무 번호로 사용하면 안 된다. gap 없는 번호가 정말 필요하면 별도 serialization과 비용을 설계한다.

## 14. isolation level 선택 기준

Read Committed는 짧고 단순한 predetermined row update에 적합할 수 있다. 각 command snapshot이 달라질 수 있음을 application이 허용해야 한다.

Repeatable Read는 transaction 동안 안정된 snapshot이 필요한 분석과 read-modify-write에 유용하지만 concurrent changed row update는 serialization error가 날 수 있고 write skew를 자동 방지하지 않는다.

Serializable은 복잡한 여러 row invariant를 serial execution처럼 보호하기 쉽게 하지만 dependency 추적 overhead와 abort/retry를 application이 받아들여야 한다. 올바른 retry가 없으면 “높은 isolation을 설정했으니 안전”하지 않다.

명시적 lock은 conflict 대상을 정확히 알 때 단순하고 강한 방법이다. 너무 넓으면 concurrency를 줄이고, 빠뜨린 predicate나 새 row는 보호하지 못한다.

constraint는 가능한 invariant를 database가 직접 집행하는 가장 명확한 방어다. unique, foreign key, exclusion constraint로 표현할 수 있는 규칙은 application SELECT 검사만 두는 것보다 경쟁에 강하다.

## 15. anomaly 진단 시간표 작성법

문제가 생기면 각 transaction마다 다음을 적는다.

- isolation level과 snapshot 획득 시점
- read한 logical condition과 실제 row version
- write한 row와 lock
- commit 또는 abort 시점과 SQLSTATE
- wait-for 또는 read-write dependency edge
- external side effect 시점
- retry가 전체 transaction인지 일부 statement인지

최종 값만 보면 lost update와 정상 연속 update를 구분하기 어렵다. read 값을 포함한 시간표가 필요하다. same-row conflict와 multi-row predicate conflict를 분리한다.

## 16. 완전 풀이 문제

### 문제 1. dirty read

T1이 x=20을 미커밋 상태로 썼고 T2가 20을 읽은 뒤 T1이 abort했다. 현상은?

**풀이:** T2가 uncommitted data를 읽은 dirty read다. PostgreSQL은 Read Uncommitted 요청도 Read Committed로 동작하므로 일반 SELECT에서 이 현상을 허용하지 않는다.

### 문제 2. nonrepeatable read

PostgreSQL Read Committed transaction의 첫 SELECT가 x=10, concurrent commit 뒤 둘째 SELECT가 x=20이다. 왜 가능한가?

**풀이:** 각 command가 시작할 때 새 snapshot을 얻는다. 첫 SELECT 뒤 commit된 version을 둘째 snapshot이 볼 수 있다. 같은 statement 실행 중 view가 임의로 바뀐다는 뜻은 아니다.

### 문제 3. PostgreSQL RR phantom

SQL 표준 표에서 Repeatable Read가 phantom을 허용할 수 있으니 PostgreSQL RR도 반드시 허용하는가?

**풀이:** 아니다. 표준은 최소 금지 현상을 정하고 더 강한 보장을 허용한다. PostgreSQL 18 RR은 transaction snapshot을 유지해 phantom도 허용하지 않지만 serialization anomaly는 가능하다.

### 문제 4. lost update

counter 10을 T1과 T2가 읽어 각각 11을 절대값으로 쓰면 결과와 손실은?

**풀이:** 둘 다 commit할 수 있는 실행에서는 최종 11이 되어 증가 하나가 사라진다. UPDATE counter=counter+1, row lock, version validation 또는 conflict retry로 막는다. 선택한 isolation과 product 동작을 확인한다.

### 문제 5. write skew 직렬성

A와 B가 모두 true에서 TA는 B=true를 보고 A=false, TB는 A=true를 보고 B=false를 썼다. 왜 serial order가 없는가?

**풀이:** TA가 먼저면 TB는 A=false를 보고 B를 끄지 않아야 한다. TB가 먼저면 TA는 B=false를 보고 A를 끄지 않아야 한다. 어느 순서도 둘 다 false 결과를 만들지 않으므로 serialization anomaly다.

### 문제 6. lock deadlock

TA가 A lock 뒤 B를 기다리고 TB가 B lock 뒤 A를 기다린다. 해결과 예방은?

**풀이:** wait-for graph에 TA→TB와 TB→TA cycle이 생긴 deadlock이다. DBMS가 victim 하나를 abort해 cycle을 끊는다. 모든 transaction이 A→B 같은 일관된 순서로 lock하고 transaction을 짧게 유지해 가능성을 줄인다. victim은 전체 transaction을 retry한다.

### 문제 7. OCC affected rows 0

version=7 조건 UPDATE가 0 row를 바꿨다. 기존 계산을 그대로 다시 UPDATE해도 되는가?

**풀이:** 아니다. 다른 transaction이 version을 변경했을 수 있어 old read와 판단이 stale하다. 새 transaction에서 row와 관련 invariant를 다시 읽고 계산한 뒤 새 version 조건으로 시도한다.

### 문제 8. serialization retry

COMMIT에서 SQLSTATE 40001을 받았다. 무엇을 재시도하는가?

**풀이:** BEGIN, snapshot read, 업무 판단, write와 COMMIT 전체를 새 transaction에서 수행한다. 마지막 statement나 COMMIT만 반복하지 않는다. 성공 전 external effect를 보내지 않고 outbox와 idempotency key를 사용한다.

## 공식 자료

- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [PostgreSQL explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [PostgreSQL MVCC introduction](https://www.postgresql.org/docs/current/mvcc-intro.html)
- [PostgreSQL error codes](https://www.postgresql.org/docs/current/errcodes-appendix.html)
