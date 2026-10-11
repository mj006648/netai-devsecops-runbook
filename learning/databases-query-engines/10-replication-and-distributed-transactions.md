# 10. Replication과 distributed transaction

[이 책 목차](README.md) · [이전: WAL, checkpoint와 recovery](09-wal-checkpoints-and-recovery.md) · [다음: Columnar·vectorized query engine](11-columnar-vectorized-query-engines.md)

Replication은 한 node의 변경을 다른 node에 전달해 availability와 read scale을 높일 수 있다. Distributed transaction은 여러 participant의 commit 결정을 맞추지만 latency, blocking과 failure state를 추가한다.

모든 출력과 수치는 교육용이며 실제 PostgreSQL·Spark·Iceberg 실행 결과가 아니다.

## 복제 진행 위치와 읽기 의미

primary가 LSN 1000까지 만들고 replica가 received=980, written=970, flushed=960, replayed=900이라고 하자. receive는 네트워크 도착, write는 OS에 전달, flush는 지속 저장 계약 완료, replay는 데이터 페이지와 논리 상태에 적용한 위치다. primary와 replay 차이 100 LSN unit은 byte 또는 시간과 자동으로 같지 않다. 처리량이 변하므로 시간 lag를 알려면 특정 commit의 timestamp와 replay 시점을 연결한다.

비동기 복제에서 primary는 replica flush를 기다리지 않고 ACK할 수 있다. 장애와 failover가 LSN 960 replica에서 일어나면 961~1000의 최근 ACK 변경을 잃을 가능성을 계약에 포함해야 한다. 동기 복제는 정한 quorum의 특정 단계 ACK를 기다려 범위를 강화하지만 지연과 가용성 비용이 있다. quorum 2-of-3은 어느 두 replica인지, flush인지 replay인지, 장애 시 정책이 어떻게 바뀌는지까지 정의해야 한다.

read-after-write가 필요한 요청을 replay 900 replica로 즉시 보내면 방금 쓴 LSN 1000 결과를 보지 못한다. primary로 라우팅하거나, replica가 세션의 최소 LSN까지 replay하기를 기다리거나, stale 허용을 사용자 계약으로 둔다. lag=0이라는 한 시점 관측도 다음 요청까지 최신임을 영구 보장하지 않는다.

## 2PC와 shard 경계

주문은 shard A, 재고는 shard B에 있다고 하자. coordinator가 각 participant에 local 변경을 실행시키고 prepare를 요청한다. A와 B가 모두 prepare하면 각자는 잠금과 복구 정보를 durable하게 유지한다. coordinator가 commit 결정을 기록한 뒤 두 곳에 알린다. B가 commit 메시지를 받기 전에 네트워크가 끊기면 B는 마음대로 abort할 수 없는 in-doubt 상태로 결정을 조회한다. 이 동안 잠금이 다른 작업을 막을 수 있다.

| 단계 | shard A | shard B | coordinator |
|---|---|---|---|
| 실행 | 주문 준비 | 재고 차감 준비 | transaction id 배정 |
| prepare | YES, resource 유지 | YES, resource 유지 | 응답 수집 |
| 결정 | 대기 | 대기 | COMMIT durable 기록 |
| 전파 장애 | commit 수신 | in-doubt | 재전송 필요 |

shard key를 잘 고르면 많은 트랜잭션을 한 shard 안에 가둘 수 있어 2PC 경계를 줄인다. 그러나 사용자별 shard에 있는 두 사용자의 송금처럼 업무 경계가 shard 경계를 넘으면 분산 조정이 다시 필요하다. Saga의 보상은 이미 일어난 외부 효과를 의미상 상쇄하는 새 작업이며 데이터베이스 rollback처럼 과거를 지우지 않는다.

failover에서는 옛 primary를 **fencing**해 더는 write를 받지 못하게 해야 한다. 새 primary와 옛 primary가 동시에 권위를 주장하면 split brain이 되고 서로 다른 로그가 생긴다. client retry도 첫 요청이 commit되었지만 응답만 잃은 경우를 고려해 idempotency key로 중복 효과를 막는다.

### 문제 5개

1. flushed 960, replayed 900의 뜻은? **해설:** 로그는 960까지 durable하지만 질의 상태 적용은 900까지만 끝났다.
2. 2-of-3 quorum이면 모든 replica 완료인가? **해설:** 아니다. 정한 두 응답 단계만 충족하며 세 번째는 뒤처질 수 있다.
3. prepare 뒤 coordinator 장애 시 왜 block하는가? **해설:** participant가 durable한 최종 결정을 몰라 resource를 임의 해제할 수 없다.
4. replication이 exactly-once를 주는가? **해설:** client가 ACK를 잃고 재시도하면 중복될 수 있어 idempotency가 별도다.
5. shard를 늘리면 항상 확장되는가? **해설:** cross-shard transaction, 재분배, hot shard와 fan-out query 비용이 늘 수 있다.

## 1. 단어와 위치

| 용어 | 뜻 |
| --- | --- |
| Primary | Write를 받아 authoritative log를 생성하는 node role |
| Replica | Primary log를 받아 replay하는 copy |
| Replication lag | Primary progress와 replica replay progress의 차이 |
| Synchronous replication | 정한 replica acknowledgment를 commit 조건에 포함하는 방식 |
| Asynchronous replication | Local commit 뒤 replica가 나중에 따라오는 방식 |
| Failover | 새 primary role로 service를 전환하는 절차 |
| Split brain | 둘 이상의 node가 동시에 primary라고 행동하는 위험 |
| 2PC | Two-Phase Commit, prepare와 commit/abort 두 단계 protocol |
| Coordinator | Distributed transaction 결정을 모으고 알리는 주체 |
| Participant | Local resource를 prepare하고 결정에 따르는 node |

## 2. 실제 객체

- Primary WAL position

- Replica receive/write/flush/replay positions

- Consensus 또는 fencing metadata

- Coordinator transaction record

- Participant prepared transaction

- Client retry/idempotency key

## 3. 입력에서 결과까지

```mermaid
flowchart LR
 I["입력"] --> X["실행 주체"]
 X --> S["중간 상태"]
 S --> O["결과 또는 오류"]
```

1. Client write가 primary transaction을 시작한다.

2. Primary가 WAL과 commit decision을 만든다.

3. Log sender가 replica로 bytes를 전송한다.

4. Replica가 receive·write·flush·replay 단계를 진행한다.

5. Sync policy가 요구한 acknowledgment를 primary가 기다린다.

6. Client가 commit success를 받는다.

7. 2PC에서는 coordinator가 participants에 prepare를 요청한다.

8. 모두 prepare이면 durable commit decision을 기록한다.

9. Coordinator가 commit을 전파한다.

10. Recovery는 in-doubt participant가 결정을 다시 확인하게 한다.

## 4. 숫자 시간표

- primary LSN 1,000

- replica received 980, flushed 960, replayed 900

- replay lag = 100 LSN units

- read-after-write를 replica에서 즉시 하면 old value 가능

- 2PC 3 participants 중 1개 unreachable이면 prepared lock이 남을 수 있음

## 5. 조건과 경계

Async replica는 primary crash에서 acknowledged transaction 일부를 잃을 수 있다.

Sync replica도 application-level exactly-once를 만들지 않는다.

Replica read는 stale할 수 있어 consistency routing이 필요하다.

Failover에는 old primary fencing이 중요하다.

2PC prepare는 local resource를 잠근 채 coordinator 결정을 기다릴 수 있다.

Saga는 compensating action을 쓰지만 원래 side effect가 사라지는 rollback과 다르다.

## 6. 실패를 읽는 순서

1. 어느 transaction·snapshot·LSN·stage인지 identity를 적는다.

2. Client 성공과 storage·replica 완료를 구분한다.

3. Estimate와 actual을 분리한다.

4. Retry가 전체 operation인지 일부 request인지 확인한다.

5. External side effect와 orphan object를 찾는다.

6. Version별 공식 보장을 확인한다.

## 7. 오해와 반례

- Replica가 둘이면 data loss가 불가능하다.

- Replication lag는 network latency 하나다.

- Read replica는 항상 read-your-writes를 제공한다.

- 2PC는 failure에도 절대 block하지 않는다.

- Compensation은 database rollback과 같다.

## 8. 문제

1. Flushed 960, replayed 900의 차이는?

2. Failover 때 fencing이 필요한 이유는?

3. 2PC participant가 prepare 뒤 coordinator를 잃으면?

## 9. 해설

1. Log는 durable하지만 data state 적용은 900까지일 수 있다.

2. Old primary가 계속 write해 split brain을 만드는 것을 막기 위해서다.

3. 결정을 알 수 없는 in-doubt 상태로 lock/resource를 유지할 수 있다.

## 10. 공식 자료

- [공식 문서](https://www.postgresql.org/docs/current/warm-standby.html)

- [공식 문서](https://www.postgresql.org/docs/current/two-phase.html)

- [CMU 15-445/645 Fall 2024](https://15445.courses.cs.cmu.edu/fall2024/syllabus.html)

다음 장에서는 이 계약을 더 큰 execution 또는 재현 모델에 연결한다.


## 보강: primary LSN에서 replica 적용까지

Replication은 primary의 변경 기록을 replica가 받아 사본에 재생하는 과정이다. primary가 WAL LSN 9000까지 만들고 replica receiver가 8900까지 수신했지만 replay process가 8700까지만 적용했다면 send lag는 없더라도 replay lag가 200 LSN만큼 남는다. replica SELECT는 적용된 8700 상태까지만 볼 수 있다. 네트워크 수신 완료와 질의에 보이는 적용 완료를 구별해야 한다.

2PC(Two-Phase Commit)는 coordinator가 참여자에게 prepare를 요청하고 모두 준비되면 commit 결정을 알리는 프로토콜이다. Prepared state는 참여자가 필요한 잠금과 복구 정보를 보관해 최종 결정을 기다리는 상태다. coordinator 장애 시 참여자가 결정을 모르면 오래 대기할 수 있으므로 2PC가 가용성을 자동 해결하지는 않는다.
