# 분산 시스템: 실패를 전제로 상태를 지키는 법

분산 시스템은 여러 컴퓨터가 네트워크로 협력해 하나의 서비스를 제공하는 시스템이다.
이 책은 서버, 프로세스, 요청, 복제본, 로그라는 말을 처음 접하는 독자를 대상으로 한다.
목표는 용어 암기보다 “누가 어떤 상태를 언제 바꾸었는가”를 시간순으로 추적하는 능력이다.

## 선수 지식

- **프로세스**: 실행 중인 프로그램 한 개다.
- **서버**: 요청을 받아 처리하는 프로세스 또는 그 프로세스가 실행되는 컴퓨터다.
- **네트워크**: 서로 떨어진 컴퓨터 사이에 바이트를 전달하는 통로다.
- **상태**: 프로그램이 다음 행동을 결정하기 위해 기억하는 값이다.
- **장애**: 기대한 시간과 방식으로 동작하지 않는 사건이다.

## 읽는 순서

1. [왜 분산 시스템인가](00-why-distributed-systems.md)
2. [RPC와 메시지 전달](01-rpc-and-message-delivery.md)
3. [시간, 사건, 순서](02-time-events-and-ordering.md)
4. [복제와 일관성](03-replication-and-consistency.md)
5. [리더, 쿼럼, 파티션](04-leaders-quorums-and-partitions.md)
6. [Raft 로그와 커밋](05-raft-logs-and-commit.md)
7. [합의 장애와 스냅샷](06-consensus-failures-and-snapshots.md)
8. [트랜잭션과 2단계 커밋](07-transactions-and-two-phase-commit.md)
9. [샤딩과 재구성](08-sharding-and-reconfiguration.md)
10. [재시도, 멱등성, 중복 제거](09-retries-idempotency-and-deduplication.md)
11. [스트림, 체크포인트, 복구](10-streams-checkpoints-and-recovery.md)
12. [멤버십, 장애 감지, 리스](11-membership-failure-detection-and-leases.md)
13. [etcd, Spark, Iceberg와 저장소](12-etcd-spark-iceberg-and-storage.md)
14. [로컬 모델과 장애 시나리오](13-local-models-and-fault-scenarios.md)
15. [실험과 연구 방법](14-experiments-and-research-methods.md)
16. [종합 문제, 용어, 출처](15-exercises-glossary-and-sources.md)

## 함께 보는 자료

- [그림 자료](assets/README.md)
- [작은 실행 모델](examples/README.md)
- [Apache Spark 학습서](../apache-spark/README.md)

각 장의 숫자는 원리 설명을 위한 교육용 모형이다.
제품의 지연 시간이나 장애 허용 보장을 뜻하지 않는다.

[다음 장 →](00-why-distributed-systems.md)
