# 데이터베이스와 쿼리 엔진 입문

이 교재는 SQL 문장만 외우지 않고 데이터가 page에 놓이고, optimizer가 plan을 고르고, transaction·WAL·replication이 실패를 견디며, columnar engine과 Spark·Iceberg가 큰 데이터를 처리하는 경로를 설명한다.

모든 숫자와 출력은 교육용 모델이다. 실제 PostgreSQL·Spark·Iceberg cluster에서 실행한 결과라고 주장하지 않는다.

## 학습 순서

1. [데이터베이스와 쿼리 전체 지도](00-database-and-query-map.md)
2. [관계, SQL과 NULL](01-relations-sql-and-null.md)
3. [Page, record와 buffer pool](02-pages-records-and-buffer-pools.md)
4. [B-tree와 LSM index](03-btree-and-lsm-indexes.md)
5. [Scan, filter와 join](04-scans-filters-and-joins.md)
6. [Query planning과 cost](05-query-planning-and-costs.md)
7. [Transaction과 ACID](06-transactions-and-acid.md)
8. [MVCC와 snapshot visibility](07-mvcc-and-snapshot-visibility.md)
9. [Isolation과 concurrency](08-isolation-and-concurrency.md)
10. [WAL, checkpoint와 recovery](09-wal-checkpoints-and-recovery.md)
11. [Replication과 distributed transaction](10-replication-and-distributed-transactions.md)
12. [Columnar·vectorized query engine](11-columnar-vectorized-query-engines.md)
13. [Spark, Iceberg와 최적화](12-spark-iceberg-and-optimization.md)
14. [로컬 교육 모델](13-local-models.md)
15. [실험과 연구 설계](14-experiments-and-research.md)
16. [종합 문제, 용어집과 출처](15-exercises-glossary-and-sources.md)

## 부속 자료

- [그림 설명](assets/README.md)
- [재현 가능한 Python 교육 모델](examples/README.md)

## 읽는 방법

각 장에서 먼저 객체가 어디에 존재하는지 찾는다.

그 다음 입력, 실행 주체, 중간 상태, 결과를 시간순서로 읽는다.

숫자 예제는 공식 구현의 모든 세부사항을 복제하지 않는 교육용 단순화다.

PostgreSQL에만 해당하는 동작과 SQL 표준 또는 일반 데이터베이스 개념을 구분한다.

실제 시스템에서는 version, configuration, storage, workload 분포를 다시 확인한다.
