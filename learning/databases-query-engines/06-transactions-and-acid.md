# 06. Transaction과 ACID

[이 책 목차](README.md) · [이전: Query planning과 cost](05-query-planning-and-costs.md) · [다음: MVCC와 snapshot visibility](07-mvcc-and-snapshot-visibility.md)

은행 계좌 A에서 B로 100을 옮기려면 A를 줄이는 일과 B를 늘리는 일이 함께 성공해야 한다. 두 SQL 문장을 따로 실행하면 첫 문장만 성공한 상태가 남을 수 있다. 데이터베이스는 관련된 읽기와 쓰기를 하나의 논리 작업으로 묶어 완료와 실패의 경계를 만든다. 이 묶음이 transaction이다.

이 장의 계좌 값과 LSN은 상태 전이를 설명하는 교육용 숫자다. PostgreSQL 18의 transaction과 WAL 원리를 따르지만 실제 내부 log record 형식이나 flush 순서를 그대로 재현한 trace는 아니다.

## 1. transaction이라는 실제 대상

**transaction(트랜잭션)**은 데이터베이스가 함께 확정하거나 함께 중단할 SQL 작업의 논리 단위다. client connection을 처리하는 server backend는 현재 transaction 상태, snapshot, 만든 row version, 획득한 lock과 error 상태를 메모리에서 관리한다. 변경 record와 commit 여부는 WAL과 transaction status 같은 영구·복구 자료에도 연결된다.

transaction은 **BEGIN**으로 명시적 경계를 시작하고 **COMMIT**으로 성공 확정을 요청한다. **ROLLBACK**은 지금까지 한 database 변경을 취소하라는 요청이다. PostgreSQL은 transaction 밖에 보이는 각 SQL statement도 내부적으로 하나의 transaction 안에서 실행한다. client가 BEGIN을 보내지 않으면 성공한 statement마다 암묵적 commit이 일어나는 방식을 흔히 **autocommit**이라고 부른다.

transaction의 수명은 BEGIN부터 COMMIT 또는 ROLLBACK이 끝날 때까지다. error가 발생하면 transaction이 aborted state가 되어 ROLLBACK이나 savepoint 복구 전에는 다음 일반 statement를 실행할 수 없을 수 있다. connection의 수명과 transaction의 수명은 다르다. 한 connection에서 여러 transaction을 차례로 실행할 수 있다.

**operation(작업)**은 transaction 안의 SELECT, UPDATE, INSERT 같은 개별 행동이다. 여러 operation을 묶는 이유는 각각의 중간 상태보다 전체 업무 상태만 다른 session에 보이고 장애 뒤에도 그 단위로 복구되어야 하기 때문이다.

## 2. BEGIN, COMMIT, abort와 rollback을 구분한다

**BEGIN**은 backend에 새 transaction context를 만들고 이후 statement를 같은 경계에 넣는다. isolation level과 transaction 속성도 이 경계에서 정할 수 있다.

**COMMIT**은 “지금까지 오류가 없으니 변경을 성공 상태로 만들라”는 요청이다. DBMS는 constraint와 동시성 검사를 마치고 필요한 WAL durability 조건을 만족한 뒤 성공을 알린다. COMMIT 명령을 client가 보냈다는 사실과 성공 응답을 받았다는 사실은 다르다.

**abort(중단 상태)**는 transaction이 성공할 수 없게 된 상태 전이다. 명시적 ROLLBACK, statement error, deadlock victim 선택, serialization failure, connection 종료 등이 원인이 될 수 있다. abort된 transaction의 row version은 다른 정상 transaction에 committed data로 보이면 안 된다.

**rollback(되돌림 처리)**은 abort 결과로 transaction의 논리적 효과를 취소하는 과정과 명령을 가리킨다. MVCC engine에서는 수정한 data byte를 모두 즉시 과거 모양으로 덮어쓰는 것만이 rollback이 아니다. aborted transaction이 만든 tuple version을 invisible하게 판단하고 나중에 vacuum이 공간을 회수할 수 있다.

## 3. ACID 네 글자가 각각 보호하는 것

### Atomicity: 전부 또는 전무

**atomicity(원자성)**는 transaction의 database 변경이 모두 commit되거나 모두 abort되는 성질이다. 송금에서 A만 차감되거나 B만 입금된 committed 상태를 막는다.

원자성의 경계는 database transaction 안의 자원이다. transaction 중간에 HTTP 이메일 API를 호출했다면 ROLLBACK이 이미 전송된 이메일을 취소하지 않는다. 일반 파일, message broker와 다른 database도 자동 포함되지 않는다.

### Consistency: 정의한 유효 상태를 유지하는 목표

**consistency(일관성)**는 transaction이 업무와 schema가 정의한 invariant를 만족하는 유효 상태에서 다른 유효 상태로 이동해야 한다는 목표다. **invariant(불변식)**는 모든 committed 상태에서 참이어야 한다고 정한 조건이다.

NOT NULL, UNIQUE, FOREIGN KEY, CHECK처럼 DBMS에 선언한 **constraint(제약)**는 engine이 검사할 수 있다. “계좌 합계는 송금 전후 같아야 한다”, “하루 출금 총액은 고객 한도를 넘지 않는다” 같은 여러 row·서비스 규칙은 적절한 transaction, isolation, lock과 application 검사가 필요하다.

ACID의 consistency가 replica 간 값이 어느 시간에 같아지는지를 뜻하는 분산 시스템 consistency와 같은 용어는 아니다.

### Isolation: 동시에 실행돼도 허용된 상태만 관찰

**isolation(격리성)**은 concurrent transaction이 서로의 중간 변경을 관찰하고 영향을 주는 범위를 제한한다. isolation level에 따라 같은 transaction의 두 SELECT가 다른 committed 값을 볼 수 있거나, serialization anomaly를 막기 위해 transaction이 실패할 수 있다.

격리성이 모든 transaction을 물리적으로 한 번에 하나씩 실행한다는 뜻은 아니다. MVCC와 lock은 가능한 동시 실행을 허용하면서 결과 계약을 지킨다.

### Durability: 성공 응답 뒤 보존 범위

**durability(지속성)**는 commit 성공으로 알린 변경이 계약한 장애 뒤에도 복구된다는 성질이다. single-node storage crash, process crash, host loss, data-center loss는 서로 다른 장애 범위다.

로컬 WAL flush, synchronous replica의 write 또는 flush 확인, backup 완료는 다른 보장이다. COMMIT 성공 하나가 모든 replica와 backup에 반영되었다는 뜻은 아니다. synchronous_commit 같은 설정을 바꾸면 응답 latency와 특정 장애에서의 최근 transaction 손실 범위를 교환할 수 있다.

## 4. 두 계좌 송금의 논리 상태

초기 table은 다음과 같다.

| account | balance |
|---|---:|
| A | 500 |
| B | 300 |

불변식은 A+B=800이고 음수 잔액을 허용하지 않는다고 하자. 100 송금 transaction은 다음 순서다.

~~~sql
BEGIN;
SELECT balance FROM accounts WHERE id = 'A';
UPDATE accounts SET balance = balance - 100 WHERE id = 'A';
UPDATE accounts SET balance = balance + 100 WHERE id = 'B';
SELECT SUM(balance) FROM accounts WHERE id IN ('A','B');
COMMIT;
~~~

첫 SELECT에서 A가 500인지 확인하고 application은 100을 뺄 수 있다고 판단한다. 두 UPDATE 뒤 자기 transaction에서는 A=400, B=400을 볼 수 있다. 다른 transaction은 isolation 규칙에 따라 아직 committed되지 않은 두 변경을 보지 않는다.

| 시점 | A version | B version | transaction 상태 | 다른 reader |
|---:|---:|---:|---|---|
| t0 | 500 committed | 300 committed | 없음 | 500/300 |
| t1 | 500 | 300 | BEGIN, active | 500/300 |
| t2 | 400 uncommitted | 300 | active | 500/300 |
| t3 | 400 uncommitted | 400 uncommitted | active | 500/300 |
| t4 | 합계 800 검증 | 합계 800 검증 | commit 준비 | 500/300 |
| t5 | 400 committed | 400 committed | committed | 새 snapshot은 400/400 |

transaction이 t2 뒤 abort하면 A=400 version은 committed 결과가 되지 않고 다른 reader는 500을 계속 본다. t3 뒤 abort해도 두 변경 모두 최종 효과에서 제외된다.

동시에 다른 송금이 A를 바꾸면 row lock 대기나 isolation failure가 생길 수 있다. 잔액을 읽고 application에서 새 절대값을 계산한 뒤 blind write하면 lost update 위험이 있으므로 UPDATE balance = balance - 100 같은 원자적 SQL과 조건, 적절한 lock·isolation을 설계한다.

## 5. WAL과 LSN의 실제 역할

data page를 transaction마다 즉시 storage에 동기 기록하면 random I/O가 많아진다. **WAL(Write-Ahead Log, 선행 기록 로그)**은 data page 변경을 재현하는 정보를 먼저 순차 log에 기록해 recovery 가능하게 한다.

**log record**는 어느 page나 transaction에 무슨 변경이 있었는지 나타내는 binary record다. **LSN(Log Sequence Number)**은 WAL stream 안 위치를 나타내는 순서 식별자다. 시간 단위가 아니며 transaction ID와도 다르다.

**write-ahead rule**은 수정된 data page가 durable storage에 기록되기 전에 그 page 변경을 복구할 WAL이 먼저 필요한 수준까지 기록되어야 한다는 규칙이다. COMMIT 성공에 필요한 commit record도 durability 설정에 맞게 flush한다.

교육 trace에서 다음 LSN을 가정한다.

| LSN | 내용 |
|---:|---|
| 51 | A의 새 version 400 생성 정보 |
| 52 | B의 새 version 400 생성 정보 |
| 53 | transaction commit record |

backend memory와 buffer pool에는 새 tuple과 dirty data page가 있지만, WAL record가 먼저 생성된다. **dirty page**는 메모리 내용이 storage의 data file보다 새롭다는 page다. commit 시 모든 dirty data page를 즉시 flush할 필요는 없다. LSN 53까지 계약한 수준으로 durable하면 crash 뒤 WAL을 replay해 data page를 재구성할 수 있다.

~~~mermaid
flowchart LR
 I["BEGIN과 송금 입력"] --> A["A 차감 WAL 51·새 version"]
 A --> B["B 입금 WAL 52·새 version"]
 B --> V["합계와 constraint 검증"]
 V --> C["commit record WAL 53"]
 C --> D["요구 수준까지 WAL durable"]
 D --> R["client 성공 응답"]
 R --> F["data page는 이후 background flush 가능"]
~~~

## 6. 장애 시점을 여섯 경계로 나누기

같은 “서버가 죽었다”도 어느 경계인지에 따라 client와 recovery 의미가 다르다.

### 경계 1: BEGIN 직후

변경 record가 없다. transaction은 완료되지 않았고 계좌는 500/300이다.

### 경계 2: WAL 51 생성 뒤, B 입금 전

A의 uncommitted version과 WAL이 일부 존재할 수 있다. commit record가 없으므로 recovery는 이 transaction을 committed로 인정하지 않는다. 최종 visible 상태는 500/300이다.

### 경계 3: WAL 52 뒤, commit record 전

A와 B 변경 정보가 모두 있어도 commit decision이 없다. “두 UPDATE가 실행되었으니 성공”이 아니다. recovery 후 둘 다 committed 효과가 아니다.

### 경계 4: commit record가 memory에만 있고 durable 전

crash가 durable storage에 record를 남기지 않았다면 recovery는 commit을 보장할 수 없다. client에 성공을 아직 보내지 않아야 계약이 단순하다.

### 경계 5: LSN 53 durable, 성공 응답 전

database는 commit을 복구할 수 있지만 client는 network 단절로 결과를 모를 수 있다. 이것이 **ambiguous commit(커밋 결과 불명)** 상황이다. client가 같은 송금을 무조건 다시 실행하면 두 번 이체할 수 있다. 업무 request id를 UNIQUE하게 저장해 재시도를 idempotent하게 만든다.

### 경계 6: 성공 응답 뒤, data page flush 전

WAL로 redo할 수 있으므로 recovery 후 400/400이 남아야 한다. dirty data page가 옛 500/300 상태여도 WAL 51·52와 commit 53을 적용한다.

이 trace는 PostgreSQL이 aborted update를 일반적인 undo log로 과거 byte에 되돌린다고 단정하지 않는다. MVCC visibility와 WAL recovery, 나중 cleanup이 함께 committed 상태를 만든다.

## 7. checkpoint와 WAL 보존의 관계

**checkpoint(체크포인트)**는 recovery가 시작할 기준을 앞당기고 dirty buffer를 data file에 반영하도록 조정하는 지점이다. checkpoint가 있다고 이전 WAL을 즉시 전부 삭제할 수 있는 것은 아니다. replica, backup, archive와 recovery가 필요한 범위가 WAL 보존을 붙잡을 수 있다.

checkpoint를 너무 자주 하면 많은 write와 I/O burst가 생길 수 있고, 너무 드물면 crash recovery가 더 많은 WAL을 replay할 수 있다. transaction durability와 checkpoint 완료는 같은 사건이 아니다. commit은 필요한 WAL이 durable하면 data page flush를 기다리지 않을 수 있다.

## 8. rollback과 savepoint의 수명

**savepoint(저장점)**는 하나의 transaction 안에서 이후 작업 일부를 취소할 수 있는 이름 붙은 지점이다. 독립적으로 durable한 작은 transaction이 아니다.

~~~sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id='A';
SAVEPOINT credited_b;
UPDATE accounts SET balance = balance + 100 WHERE id='B';
ROLLBACK TO credited_b;
UPDATE accounts SET balance = balance + 100 WHERE id='C';
COMMIT;
~~~

ROLLBACK TO 뒤 B 입금 효과는 취소되지만 A 차감은 transaction 안에 남는다. C 입금 뒤 전체 COMMIT이 성공해야 A와 C 변경이 다른 session에 보인다. savepoint를 RELEASE해도 전체 commit 전에는 durability와 visibility가 독립 확정되지 않는다.

PostgreSQL에서는 statement error 뒤 전체 transaction이 aborted state가 될 수 있고, 적절한 savepoint로 돌아가야 계속할 수 있다. error를 무시하고 COMMIT만 보내는 코드는 의도한 상태를 만들지 못할 수 있다.

## 9. constraint와 업무 불변식

A와 B 합계 800은 두 row를 읽어야 하는 invariant다. CHECK(balance >= 0)는 각 row의 음수 방지에 도움을 주지만 합계를 자동 보장하지 않는다.

foreign key는 참조 대상 존재, unique는 중복 key 금지를 DBMS가 동시성 속에서 검사한다. application에서 먼저 SELECT한 뒤 INSERT하는 방식만 쓰면 concurrent transaction이 같은 값을 보고 둘 다 쓰려 할 수 있다. UNIQUE constraint를 최종 방어선으로 두고 conflict를 처리한다.

여러 table과 외부 service를 가로지르는 invariant는 한 database constraint로 표현되지 않을 수 있다. transaction outbox, idempotency, saga 또는 distributed commit 같은 별도 설계가 필요하다. ACID라는 이름만으로 경계 밖 상태가 자동 결합되지 않는다.

## 10. isolation이 consistency에 필요한 이유

두 transaction이 각각 시작과 끝에서 constraint를 만족해도 서로의 중간 읽기를 바탕으로 write skew 같은 anomaly를 만들 수 있다. “각 transaction 코드가 맞다”와 “동시에 실행해도 invariant가 유지된다”는 다른 주장이다.

적절한 isolation level, SELECT FOR UPDATE 같은 명시적 lock, unique/exclusion constraint, serializable retry 중 업무 조건에 맞는 방법을 선택한다. lock을 잡을 row가 아직 존재하지 않는 범위 조건은 predicate 전체를 보호해야 할 수 있다.

serialization failure나 deadlock victim으로 abort되면 마지막 statement나 COMMIT만 재시도하지 않는다. 이전 snapshot에서 읽고 판단한 값이 무효일 수 있으므로 BEGIN부터 읽기·검증·쓰기·COMMIT 전체를 새 transaction으로 수행한다.

## 11. 외부 side effect와 outbox

database transaction 안에서 주문 row를 INSERT한 뒤 email API를 호출하고 transaction이 abort하면 이메일은 이미 나갔다. 반대로 먼저 commit하고 프로세스가 죽으면 email을 호출하지 못할 수 있다.

**transactional outbox(트랜잭션 outbox)**는 주문 변경과 “이메일을 보내라”는 event row를 같은 database transaction에 기록한다. commit되면 별도 publisher가 outbox를 읽어 external system으로 전달하고 완료 상태를 기록한다.

전달자는 network timeout 때문에 같은 event를 여러 번 보낼 수 있다. **idempotency key(멱등 키)**는 같은 업무 request를 식별해 중복 요청이 한 번의 효과만 내도록 한다. 소비자는 처리한 event id를 저장하거나 external API가 idempotency를 지원하도록 한다.

outbox는 exactly-once network 전송을 마법처럼 만들지 않는다. database commit과 재시도 가능한 at-least-once 전달을 결합하고, 중복 효과를 제거하는 설계다.

## 12. replica와 backup이 넓히는 durability 범위

primary의 로컬 storage에 WAL이 durable한 것과 다른 host replica가 가진 것은 다르다. synchronous replication은 commit이 특정 standby의 응답을 기다리게 할 수 있지만 응답 단계가 receive, write, flush, replay 중 어디인지 설정에 따라 의미가 달라진다.

replica가 있다고 잘못된 DELETE에서 보호되는 것도 아니다. 논리 변경이 replica로 복제될 수 있다. backup과 point-in-time recovery는 운영자 오류와 장기 보존을 위한 별도 경계다.

durability 문서는 다음 질문에 답해야 한다.

- client 성공 전에 어느 node의 어느 storage 단계까지 완료되는가?
- primary process, host, disk, zone 손실 각각에서 무엇이 남는가?
- replica lag과 failover 시 허용 손실은 얼마인가?
- backup이 마지막으로 복구 검증된 시점은 언제인가?

## 13. 성공 응답과 재시도 계약

client가 COMMIT 성공을 받으면 request가 확정되었다고 처리할 수 있다. timeout이나 connection reset이면 commit 전 실패인지 commit 뒤 응답 손실인지 알 수 없을 수 있다.

송금 request에 transfer_id=abc-123을 사용하고 transfer table에 UNIQUE constraint를 둔다고 하자.

1. 새 transaction에서 transfer_id를 INSERT한다.
2. 이미 존재하면 이전 결과를 조회해 반환한다.
3. 처음이면 A와 B를 변경하고 같은 transaction에서 결과를 기록한다.
4. COMMIT 결과가 불명이어도 같은 id로 전체 request를 재시도한다.
5. 이미 commit된 경우 unique 충돌을 통해 중복 송금을 막고 기존 결과를 찾는다.

단순 HTTP retry와 database transaction retry를 연결하려면 업무 식별자가 필요하다.

## 14. 완전 풀이 문제

### 문제 1. autocommit 송금

A 차감과 B 입금을 두 autocommit UPDATE로 보내면 atomic한가?

**풀이:** 아니다. 첫 UPDATE가 독립 commit된 뒤 둘째가 실패할 수 있다. BEGIN으로 두 UPDATE와 검증을 한 transaction에 묶고 COMMIT 또는 ROLLBACK해야 한다.

### 문제 2. 합계 불변식

초기 A=500, B=300에서 100을 옮긴 뒤 값과 합계는?

**풀이:** A=400, B=400이고 합계는 800이다. A 차감 후 B 입금 전의 400/300은 transaction 내부 중간 상태이며 다른 transaction의 committed 결과로 남아서는 안 된다.

### 문제 3. commit과 dirty page

COMMIT 성공 뒤 data page가 아직 dirty일 수 있는가?

**풀이:** WAL system에서는 가능하다. 변경과 commit을 재현할 WAL이 요구 수준까지 durable하면 data page는 나중에 flush할 수 있다. crash recovery가 WAL을 redo해 committed 상태를 만든다.

### 문제 4. commit record 전 crash

A·B update WAL은 있지만 commit record가 durable하지 않은 채 crash했다. 성공 transaction으로 복구하는가?

**풀이:** 이 교육 trace에서는 아니다. 두 data 변경 정보가 있어도 commit decision이 durable하지 않으므로 committed visible 효과가 아니다. client 성공도 보내지 않은 경계여야 한다.

### 문제 5. ACK 전 crash

commit WAL은 durable하지만 client가 success를 받기 전에 connection이 끊겼다. client는 같은 송금을 다시 보내도 되는가?

**풀이:** 결과가 불명이라 blind retry하면 중복 송금할 수 있다. stable transfer_id와 UNIQUE constraint로 request를 멱등하게 만들고 같은 id로 전체 업무를 재시도해 기존 commit 여부를 판별한다.

### 문제 6. rollback과 이메일

transaction 중 email API를 호출한 뒤 ROLLBACK하면 이메일도 취소되는가?

**풀이:** 아니다. external API는 database atomicity 경계 밖이다. outbox row를 업무 변경과 함께 commit하고 publisher가 재시도하며 consumer가 idempotency key로 중복 효과를 막게 한다.

### 문제 7. savepoint

A 차감 뒤 savepoint, B 입금 뒤 ROLLBACK TO, C 입금 뒤 COMMIT이면 무엇이 남는가?

**풀이:** savepoint 이전 A 차감은 남고 B 입금은 취소되며 C 입금이 추가된다. 전체 COMMIT이 성공할 때 A와 C 변경이 함께 visible해진다. savepoint 자체는 독립 durable commit이 아니다.

### 문제 8. serialization failure

COMMIT에서 serialization failure가 났다. COMMIT만 다시 보내면 되는가?

**풀이:** 아니다. 이전 snapshot의 읽기와 업무 판단이 무효일 수 있다. transaction을 abort하고 BEGIN부터 모든 읽기·검증·쓰기를 새 snapshot에서 다시 수행한다. 외부 side effect는 성공 commit 뒤 outbox로 조정한다.

## 공식 자료

- [PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [PostgreSQL WAL](https://www.postgresql.org/docs/current/wal-intro.html)
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [PostgreSQL synchronous replication settings](https://www.postgresql.org/docs/current/runtime-config-replication.html)
