# 10. Replication과 distributed transaction

[이 책 목차](README.md) · [이전: WAL, checkpoint와 recovery](09-wal-checkpoints-and-recovery.md) · [다음: Columnar·vectorized query engine](11-columnar-vectorized-query-engines.md)

Replication은 한 node의 변경을 다른 node에 전달해 availability와 read scale을 높일 수 있다. Distributed transaction은 여러 participant의 commit 결정을 맞추지만 latency, blocking과 failure state를 추가한다.

모든 출력과 수치는 교육용이며 실제 PostgreSQL·Spark·Iceberg 실행 결과가 아니다.

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
