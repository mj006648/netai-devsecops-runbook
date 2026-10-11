# 12. Spark, Iceberg와 최적화

[이 책 목차](README.md) · [이전: Columnar·vectorized query engine](11-columnar-vectorized-query-engines.md) · [다음: 로컬 교육 모델](13-local-models.md)

Spark는 distributed execution engine이고 Iceberg는 table metadata·snapshot·file 집합을 관리하는 open table format이다. 둘을 함께 써도 partition skew, shuffle, small files와 catalog commit을 별도로 이해해야 한다.

모든 출력과 수치는 교육용이며 실제 PostgreSQL·Spark·Iceberg 실행 결과가 아니다.

## 1. 단어와 위치

| 용어 | 뜻 |
| --- | --- |
| Driver | Spark application plan과 task scheduling을 조정하는 process |
| Executor | Partition task를 실행하고 shuffle data를 읽고 쓰는 process |
| Partition | 한 task가 처리하는 logical data 조각 |
| Stage | Shuffle boundary로 나뉜 task 집합 |
| Shuffle | Partition key에 따라 data를 worker 사이로 재분배 |
| Iceberg snapshot | 특정 시점 table metadata와 file 집합을 가리키는 commit |
| Manifest | Data file metadata entry를 모은 Iceberg metadata file |
| Catalog | Table 이름과 current metadata pointer를 관리하는 service |
| Partition pruning | Metadata로 불필요 partition/file을 제외 |
| Small-file problem | 작은 file이 많아 metadata·open·scheduling 비용이 커지는 상태 |

## 2. 실제 객체

- Spark logical/physical plan

- Driver의 stage/task state

- Executor shuffle blocks

- Iceberg metadata.json과 manifest list

- Manifest files와 data files

- Catalog current pointer와 commit conflict

## 3. 입력에서 결과까지

```mermaid
flowchart LR
 I["입력"] --> X["실행 주체"]
 X --> S["중간 상태"]
 S --> O["결과 또는 오류"]
```

1. Spark가 SQL/DataFrame logical plan을 만든다.

2. Optimizer가 filter·projection과 join strategy를 정한다.

3. Iceberg connector가 current snapshot metadata를 읽는다.

4. Manifest statistics로 candidate data file을 고른다.

5. Driver가 file split을 task partition으로 계획한다.

6. Executor가 columnar data를 scan한다.

7. Join/aggregate shuffle이 key별 data를 재분배한다.

8. Writer task가 새 data files를 만든다.

9. Driver commit이 새 metadata를 작성한다.

10. Catalog가 expected old pointer 조건으로 current snapshot을 교체한다.

## 4. 숫자 시간표

- 100 files × 1GB = 100GB

- 1,000 executors가 아니라 400 tasks로 split될 수 있음

- 한 hot key가 20GB면 한 partition에 skew 가능

- 10MB small file 10,000개도 100GB지만 open/metadata cost 큼

- 256MB target file이면 약 400 files가 단순 목표

## 5. 조건과 경계

Spark executor 수와 data partition 수는 다르다.

Shuffle은 network, serialization, disk spill과 fetch retry 비용을 만든다.

Iceberg partition spec은 directory 문자열만이 아니라 metadata transform이다.

Snapshot commit은 새 file 집합 pointer를 atomic하게 publish하려는 protocol이다.

Data file upload 성공만으로 table commit 성공이 아니다.

Compaction은 file 수를 줄이지만 rewrite I/O와 concurrent commit conflict를 만든다.

## 6. 실패를 읽는 순서

1. 어느 transaction·snapshot·LSN·stage인지 identity를 적는다.

2. Client 성공과 storage·replica 완료를 구분한다.

3. Estimate와 actual을 분리한다.

4. Retry가 전체 operation인지 일부 request인지 확인한다.

5. External side effect와 orphan object를 찾는다.

6. Version별 공식 보장을 확인한다.

## 7. 오해와 반례

- Spark partition은 Iceberg partition과 같은 object다.

- Executor 하나가 file 하나를 항상 처리한다.

- Iceberg catalog가 data bytes를 저장한다.

- Object storage put 성공이면 table commit 완료다.

- Small files는 총 byte가 같으므로 성능 영향이 없다.

## 8. 문제

1. 100GB를 256MB file로 단순 나누면 몇 개인가?

2. Spark shuffle partition과 Iceberg partition 차이는?

3. Commit conflict 뒤 이미 쓴 data file은?

## 9. 해설

1. 약 400개다.

2. 전자는 한 execution의 task data 조각이고 후자는 table metadata의 data organization이다.

3. Current snapshot에 포함되지 않은 orphan 후보가 될 수 있어 안전한 cleanup policy가 필요하다.

## 10. 공식 자료

- [공식 문서](https://spark.apache.org/docs/latest/sql-performance-tuning.html)

- [공식 문서](https://iceberg.apache.org/spec/)

- [공식 문서](https://iceberg.apache.org/docs/latest/performance/)

- [CMU 15-445/645 Fall 2024](https://15445.courses.cs.cmu.edu/fall2024/syllabus.html)

다음 장에서는 이 계약을 더 큰 execution 또는 재현 모델에 연결한다.


## 보강: metadata 계획과 분산 task 실행

Iceberg table은 단일 데이터 파일이 아니라 metadata file, snapshot, manifest list, manifest, data file을 연결한 논리 객체다. Planner는 선택한 snapshot에서 manifest 통계를 읽고 조건과 겹치지 않는 partition과 file을 제외한다. 남은 파일 경로가 Spark scan task 입력이 되고 executor process가 column chunk를 읽어 filter·join·aggregate를 수행한다. Metadata pruning은 읽을 후보를 줄이는 단계이지 결과 행을 이미 계산한 것이 아니다.

Spark의 shuffle은 upstream task가 key별 중간 block을 쓰고 downstream task가 여러 executor에서 그 block을 가져오는 재분배다. `groupBy(customer_id)`에서 같은 key를 한 partition으로 모으는 데 필요하지만 네트워크, 직렬화, 디스크 spill을 만든다. 작은 테이블 broadcast join은 shuffle을 줄일 수 있으나 각 executor 메모리에 사본을 둘 수 있을 때만 안전하다.
