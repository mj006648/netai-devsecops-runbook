# 12. Spark, Iceberg와 최적화

## snapshot 계획에서 분산 결과까지

Spark logical plan은 무엇을 계산할지 나타내는 driver 메모리 객체다. analyzed plan은 열 이름을 catalog schema와 연결하고 type을 확정한다. optimized logical plan은 의미를 보존하며 filter·projection·join을 변환한다. physical plan은 file scan, broadcast hash join, sort-merge join과 exchange를 고른다. stage와 task는 scheduler가 이를 cluster 작업으로 나눈 runtime 객체다.

Spark partition은 한 task가 처리하는 실행 입력 조각이다. Iceberg partition은 days(ts), bucket(16,id) 같은 transform 결과로 파일을 조직하는 지속 개념이다. Parquet row group은 파일 내부 행 범위다. owner, lifetime, 변경 주체가 모두 다르다.

Iceberg catalog는 이름을 current metadata JSON에 연결하고 snapshot은 manifest list를 가리킨다. manifest는 data/delete file별 경로와 통계를 담는다. Spark driver의 connector가 snapshot과 후보 파일을 고르고 executor가 Parquet를 읽는다. catalog가 SUM을 계산하지 않고 Iceberg가 shuffle을 실행하지 않는다.

## 전체 추적 1: SELECT

현재 snapshot 81에 manifest 20개, manifest마다 data file 50개가 있어 총 1,000파일이라고 하자. 파일 평균 128MiB라 전체 약 125GiB다. SQL은 특정 day의 region별 amount 합계다.

1. analyzer가 region, amount, day를 field ID와 type에 연결한다.
2. optimizer가 세 열만 projection하고 day filter를 scan에 전달한다.
3. connector가 snapshot 81을 고정한다.
4. manifest list summary로 20개 중 16개를 제외하고 200파일을 검사한다.
5. manifest file 통계로 160개를 더 제외해 40파일, 약 5GiB를 후보로 남긴다.
6. driver가 이를 80개 Spark input partition으로 만든다. 파일 수와 task 수는 같지 않다.
7. executor가 Parquet row group을 더 줄여 실제 800MiB를 decode한다.
8. 80 task가 KR,US,JP partial sum을 내면 최대 240개 중간 record다.
9. exchange가 같은 region을 모으고 final aggregate가 세 결과 행을 만든다.

snapshot 81을 고정한 뒤 82가 게시되어도 진행 query는 81의 파일 집합으로 끝난다. 파일 pruning 40개, decode 800MiB, 결과 3행은 서로 다른 단계의 수치다.

DataFrame transformation은 대개 action 전까지 lazy하지만 parsing, schema resolution, catalog·metadata 조회가 언제 일어나는지는 API와 connector에 따라 action 전에도 일어날 수 있다. collect, count, write 같은 action은 task 실행을 촉발한다. “모두 lazy”라는 문장으로 외부 I/O 시점을 단정하지 않는다.

## 전체 추적 2: write와 commit

80 writer task가 약 32MiB 파일을 하나씩 만들면 data file 80개, 총 2.5GiB가 저장소에 생긴다. task 성공은 upload 성공이지 table commit 성공이 아니다. driver가 manifest, snapshot 82, metadata v12 후보를 만들고 catalog pointer가 예상 v11일 때만 v12로 바꾼다.

다른 writer가 먼저 v12-other를 게시하면 compare-and-swap이 실패한다. append이고 논리 충돌이 없다면 최신 상태를 읽어 이미 쓴 80파일을 v13 후보에 재사용한다. overwrite가 겹치면 안전한 rebase가 아닐 수 있다. commit 전에 실패한 파일은 orphan 후보이며 실행 중 write와 보존 기간을 고려한 cleanup만 삭제해야 한다.

같은 100GiB를 10MiB 파일로 쓰면 약 10,240개, 256MiB 목표면 400개다. data byte는 같아도 manifest entry, object open, footer read, scheduling 비용이 다르다. compaction은 작은 파일을 읽어 큰 파일로 쓰고 새 snapshot에 게시하는 write다.

fact 100GiB와 dimension 40MiB를 broadcast join하면 executor 50개에 cluster 전체 약 2GiB가 전달될 수 있고 각 executor에 hash overhead가 생긴다. sort-merge join에서 hot key 하나가 20GiB면 한 reducer가 오래 남는다. 나머지 80GiB를 399개가 나누면 일반 partition 평균은 약 205MiB인데 hot task는 20GiB다. 전체 평균은 skew를 숨긴다.

## 연구 조건과 반례

QOaaS는 Calcite/Cascades 계열 optimizer를 여러 engine에 연결하는 prototype 방향이다. 바뀌는 객체는 property 표현, rule, cost와 engine capability 교환이며 Spark scheduler나 Iceberg manifest가 사라지지 않는다. 모든 Spark query에서 우위라는 보장이 아니다. planning time, unsupported operator와 execution time을 분리한다.

filtered-vector 접근에서는 Iceberg metadata pruning 뒤 Parquet filter와 ANN 탐색을 결합한다. SQL filter를 어긴 vector를 반환하면 빠르더라도 틀리다. exact filtered top-k, recall, file byte와 cold/warm latency를 함께 둔다.

- executor 수와 task 수는 다르다.
- object store의 file 존재는 snapshot 포함을 뜻하지 않는다.
- partition pruning은 row predicate를 대체하지 않는다.
- broadcast는 shuffle을 줄여도 memory·전송 비용이 있다.
- 최신 Spark 문서가 현재 cluster와 connector 지원을 보장하지 않는다.

## 완전 풀이 문제 5개

1. 100GiB를 256MiB로 나누면? **해설:** 102400/256=400개다.
2. 1,000파일에서 40개가 남으면 제거율은? **해설:** 후보 4%, 제거 96%다.
3. 80 task가 region 세 개 partial을 모두 내면? **해설:** 최대 240개다.
4. 80파일 upload 뒤 commit 실패면 행이 보이는가? **해설:** current snapshot에 없으므로 정상 reader에는 보이지 않는다.
5. hot 20GiB와 일반 평균 205MiB의 의미는? **해설:** 평균 task 크기만 보면 심한 skew와 straggler를 숨긴다.

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
