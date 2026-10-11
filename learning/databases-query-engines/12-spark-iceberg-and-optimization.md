# 12. Spark, Iceberg와 최적화

[이 책 목차](README.md) · [이전: Columnar·vectorized query engine](11-columnar-vectorized-query-engines.md) · [다음: 로컬 교육 모델](13-local-models.md)

Spark와 Iceberg를 함께 쓸 때 한 SQL은 세 종류의 시스템을 지난다. Spark는 여러 프로세스에 계산을 나누는 실행 엔진이고, Iceberg는 어느 파일들이 테이블의 현재 버전을 이루는지 기록하는 테이블 형식이며, Parquet는 각 데이터 파일 안의 열 바이트를 배치하는 파일 형식이다. 느린 질의를 고치려면 Spark 작업 조각, Iceberg 파티션, Parquet 행 그룹을 같은 “partition”으로 부르지 않고 실제 객체와 수명을 구분해야 한다.

## 1. Spark application의 실제 주체

**application** 은 사용자가 제출한 하나의 Spark 프로그램 실행이다. 그 안에서 **driver** 는 SQL을 해석하고 실행 계획을 만들며 작업을 조정하는 프로세스다. **executor** 는 cluster의 worker 노드에서 task를 실행하고 메모리·로컬 디스크를 사용하는 프로세스다. executor 수명은 application 설정과 동적 자원 할당에 따라 달라질 수 있고, task 하나가 끝나도 executor는 다음 task를 수행할 수 있다.

**logical plan, 논리 계획** 은 “어떤 결과를 계산할지”를 나타내는 driver 메모리의 연산자 나무다. unresolved plan의 문자열 열 이름은 **analyzer** 가 catalog schema의 field와 type에 연결한다. 그 결과인 analyzed plan을 **optimizer** 가 의미를 보존하는 범위에서 filter 밀어넣기, projection 축소, 상수 단순화처럼 바꾼다. **physical plan, 물리 계획** 은 실제 file scan, broadcast hash join, sort-merge join, aggregate 같은 실행 연산자를 고른다.

DataFrame transformation은 보통 action 전까지 task 실행을 만들지 않는 lazy 특성이 있다. 그러나 parsing, schema resolution, catalog와 table metadata 조회가 정확히 언제 일어나는지는 API와 connector에 따라 action 전일 수 있다. collect, count, write 같은 action이 분산 task 실행을 촉발한다는 원리와 “어떤 외부 I/O도 action 전에는 절대 없다”는 과도한 주장을 구분한다.

## 2. stage, task, Spark partition

**task** 는 한 executor가 한 입력 조각에 대해 실행하는 최소 scheduling 단위다. **Spark partition** 은 그 task가 처리할 논리적 데이터 조각이다. 파일 하나가 task 하나라는 보장은 없다. 작은 파일 여러 개를 한 partition으로 묶거나 큰 파일의 여러 범위를 여러 task로 나눌 수 있다.

**stage** 는 서로 직접 파이프라인으로 실행할 수 있는 task들의 집합이다. key가 같은 레코드를 다른 worker로 모아야 하면 경계가 생긴다. 이 네트워크 재분배를 **shuffle** 이라 한다. map 쪽 task가 shuffle block을 로컬 디스크나 메모리에 만들고, reduce 쪽 task가 필요한 block을 네트워크로 가져온다. shuffle은 전송 바이트뿐 아니라 직렬화, 임시 파일, fetch 재시도, executor 메모리와 수명을 가진 실제 중간 자료다.

Spark partition은 실행마다 optimizer와 scheduler가 만드는 일시 객체다. 다음 실행에서 수와 경계가 달라질 수 있다.

## 3. Iceberg partition과 snapshot

**Iceberg partition** 은 days(ts), bucket(16,id) 같은 transform 결과로 데이터를 조직하는 지속적인 테이블 metadata 개념이다. directory 문자열을 직접 해석하는 규칙이 아니며 partition spec과 field ID가 뜻을 정한다. 테이블이 partition evolution을 거치면 서로 다른 spec으로 쓴 파일이 같은 snapshot에 있을 수 있다. connector가 각 spec을 이해해 필터를 변환해야 한다.

**snapshot** 은 특정 커밋에서 유효한 파일 집합을 가리키는 테이블 버전이다. 독자가 snapshot 81을 선택하면 질의 도중 snapshot 82가 current가 되어도 원칙적으로 81이 가리키는 일관된 파일 집합을 계속 읽는다. snapshot은 데이터 바이트 복사본이 아니라 metadata graph의 한 지점이다.

Parquet **row group** 은 한 파일 안의 행 범위이고, 그 안에 열별 column chunk가 있다. 정리하면 Spark partition은 한 실행의 task 입력, Iceberg partition은 테이블 조직 규칙, Parquet row group은 파일 내부 배치다. 이름이 비슷해도 소유자·위치·수명이 모두 다르다.

## 4. catalog에서 data file까지의 포인터 사슬

**catalog** 는 prod.sales.orders 같은 테이블 이름을 현재 metadata JSON 위치에 연결하는 서비스 또는 metadata store다. metadata JSON은 현재 snapshot ID, snapshot 목록, schema, partition spec과 속성을 담는다. snapshot은 **manifest list** 를 가리키고, manifest list는 여러 **manifest file** 의 경로와 partition summary를 기록한다. 각 manifest는 data file과 delete file의 경로, 행 수, partition 값, 열 통계 같은 entry를 담는다.

~~~text
catalog table name
  → current metadata JSON
    → snapshot 81
      → manifest list
        → manifest files
          → data files / delete files
            → Parquet row groups and column chunks
~~~

catalog가 SUM을 계산하지 않고, Iceberg manifest가 shuffle을 실행하지 않는다. Spark driver의 Iceberg connector가 metadata를 읽어 후보 파일을 계획하고 executor가 Parquet 바이트를 읽어 계산한다. 어느 계층이 느린지를 object-store GET, metadata planning, task execution, shuffle로 나눠야 한다.

## 5. 전체 읽기 추적: 125GiB에서 세 행까지

다음 수치는 실제 측정값이 아니라 단계 구분을 위한 교육용 모형이다. current snapshot 81에 manifest 20개, manifest마다 data file 50개가 있어 총 1,000파일이라고 하자. 파일 평균은 128MiB이므로 전체 약 125GiB다. 질의는 특정 day의 region별 amount 합계다.

~~~sql
SELECT region, SUM(amount)
FROM prod.sales.orders
WHERE order_day = DATE '2026-10-10'
GROUP BY region;
~~~

| 단계 | 주체 | 입력 | 출력 |
|---|---|---|---|
| 분석 | driver analyzer | 이름 region, amount, order_day | field ID와 type이 연결된 계획 |
| 논리 최적화 | driver optimizer | analyzed plan | 세 열 projection과 day filter |
| snapshot 고정 | Iceberg connector | current metadata | snapshot 81 |
| manifest-list pruning | connector | manifest 20개 | 4개, 파일 후보 200개 |
| manifest pruning | connector | 200 file entry | 40파일, 약 5GiB |
| split 계획 | driver | 40파일과 범위 | Spark input partition 80개 |
| Parquet pruning/decode | executors | 약 5GiB 후보 | 실제 decode 800MiB |
| 부분 집계 | 80 tasks | 선택된 행 | task당 KR/US/JP 최대 3개 |
| exchange와 최종 집계 | Spark | 최대 240 record | 결과 3행 |

manifest list summary가 20개 중 16개를 제외해도 data file을 읽은 것은 아니다. manifest가 160파일을 더 제외해 후보가 40개가 되어도 아직 5GiB 모두 decode한 것은 아니다. Parquet row-group 통계와 열 projection 뒤 실제 800MiB가 decode된다. 최종 결과 세 행과 읽은 바이트를 같은 수치로 섞지 않는다.

filter를 Iceberg connector가 안전하게 변환할 수 있어야 metadata pruning이 일어난다. 사용자 정의 함수이나 transform과 맞지 않는 조건은 Spark가 scan 뒤에 적용할 수 있다. 계획에 Filter가 보인다는 사실만으로 data source까지 pushdown되었다고 결론 내리지 않고 scan의 pushed filters와 실제 파일·바이트 지표를 본다.

## 6. delete file을 읽는 경로

Iceberg row-level delete는 원본 data file을 즉시 다시 쓰지 않고 별도 삭제 표현으로 남을 수 있다. **position delete** 는 data file 경로와 그 파일 안의 행 위치를 기록한다. 예를 들어 (data-A.parquet, position 4)는 다른 파일의 position 4에 적용되지 않는다. **equality delete** 는 customer_id=7처럼 field ID로 식별한 값과 일치하는 행을 삭제 대상으로 삼는다. partition과 data sequence 조건을 만족하는 data file에만 적용된다.

v2에서 position delete는 position delete file로, equality delete는 equality delete file로 표현된다. v3 이상에서는 position delete를 deletion vector로 표현할 수 있다. “v3이면 모든 delete file을 읽지 않는다”는 뜻이 아니다. equality delete file은 여전히 별도 형식이고, 테이블에 남은 옛 delete file과 엔진 지원 조건을 reader가 처리해야 한다.

snapshot 81이 data-A 1,000행과 position delete 10개, equality delete customer_id=7을 가리킨다고 하자. Spark scan은 data-A만 읽어 1,000행을 반환하면 틀린다. connector는 적용 가능한 delete metadata를 계획하고 executor reader는 위치 마스크와 equality 조건을 합쳐 제거한 뒤 Spark filter와 aggregate에 넘긴다. 파일 통계상 1,000 records와 최종 reader가 내는 live rows는 다를 수 있다.

sequence number는 성공한 commit의 상대 순서를 나타낸다. 일반적으로 delete는 같은 partition의 더 오래된 data에 적용되며, equality delete는 data file data sequence가 delete보다 엄격히 작아야 하는 등의 규칙이 있다. 파일 이름 시간이나 object-store 수정 시각으로 적용 순서를 추측하지 않는다. 정확한 규칙은 table format version과 spec에 따른다.

## 7. 전체 쓰기 추적: 파일 생성과 table commit

80 writer task가 각각 약 32MiB data file 하나를 만든다고 하자. 저장소에는 80파일, 총 2.5GiB가 생긴다. 이 시점은 task upload 성공이지 table commit 성공이 아니다. current metadata가 v11일 때 driver는 새 manifest, snapshot 82, metadata v12 후보를 만든다. 마지막에는 catalog pointer를 “여전히 v11일 때만 v12로 변경”하는 compare-and-swap을 수행한다.

| 경계 | 실제 존재 | 정상 reader에게 보이는가 |
|---|---|---|
| task 40개 upload | data file 40개 | 아니오 |
| task 80개 upload | data file 80개 | 아니오 |
| manifest와 metadata v12 작성 | 후보 metadata | current pointer가 v11이면 아니오 |
| catalog CAS v11→v12 성공 | snapshot 82가 current | 새 질의에 보임 |
| client ACK | application이 성공 관찰 | 이미 commit된 뒤 응답 |

다른 writer가 먼저 v12-other를 게시하면 예상 v11 조건이 맞지 않아 CAS가 실패한다. 단순 append이고 논리 충돌이 없다면 writer는 최신 metadata를 읽고 이미 만든 80 data file을 v13 후보에 재사용해 commit을 다시 시도할 수 있다. 같은 partition 범위를 덮어쓰는 overwrite라면 다른 writer의 변경을 지울 수 있어 단순 rebase가 안전하지 않을 수 있다. connector의 충돌 검증과 isolation 조건이 결정한다.

catalog commit 성공 직후 driver 응답이 유실될 수도 있다. 무조건 같은 overwrite를 새 작업으로 반복하면 다른 결과가 생길 수 있으므로 commit 상태와 snapshot summary를 먼저 확인한다. 분산 task retry가 동일 논리 출력을 여러 임시 파일로 만들 수도 있다. metadata에 포함된 파일만 table reader에게 보이며, 포함되지 않은 것은 orphan 후보다.

## 8. orphan 정리와 snapshot expiration

**orphan file** 은 저장소에는 있지만 어떤 유효 table metadata에서도 참조되지 않는 파일이다. 실패한 task, 실패한 commit, speculative execution 때문에 생길 수 있다. object store에 존재한다는 사실만으로 테이블 데이터가 아니다.

orphan cleanup을 “현재 snapshot에 없으면 즉시 삭제”로 구현하면 과거 snapshot이나 진행 중인 writer가 사용할 파일을 지울 수 있다. 안전한 보존 기간, 진행 중 write의 최대 시간, 모든 metadata 경로를 고려해야 한다. 경로의 문자열 표현이 다르면 동일 object 판정도 주의해야 한다.

**snapshot expiration** 은 오래된 snapshot과 더 이상 필요한 참조가 없는 파일을 정리할 수 있게 하는 metadata 유지 작업이다. compaction이 옛 파일을 현재 snapshot에서 제거해도 time travel snapshot이 참조하면 즉시 물리 삭제할 수 없다. orphan removal과 snapshot expiration은 대상 판정이 다른 maintenance다.

## 9. small files와 compaction

같은 100GiB를 평균 10MiB로 쓰면 약 10,240파일이다. 256MiB 목표면 단순 계산으로 약 400파일이다. 총 데이터 바이트는 같지만 파일마다 manifest entry, object open, footer range read, task scheduling 비용이 생긴다. 너무 큰 파일도 병렬성이 줄고 rewrite 범위가 커질 수 있다.

**compaction** 은 작은 파일을 읽어 더 큰 파일로 다시 쓰고 새 snapshot에 게시하는 쓰기 작업이다. 저장소에서 파일을 이어 붙이는 단순 rename이 아니다. 예를 들어 1,024개의 10MiB 파일을 읽어 40개의 256MiB 안팎 파일로 만들 수 있다. 새 파일 upload와 commit 사이에 동시 writer 충돌이 있으며, commit 뒤에도 옛 snapshot이 구파일을 참조할 수 있다.

writer task는 Spark partition 하나와 Iceberg partition 경계를 넘어 파일 하나를 만들 수 없다는 제약을 고려해야 한다. 입력 Spark partition이 지나치게 작으면 목표 file size 설정만 크게 해도 작은 파일이 남는다. 분배와 정렬, task 크기, 압축률을 함께 조정한다.

## 10. optimizer와 실제 통계

Spark optimizer는 각 plan node의 출력 행 수와 바이트 추정치를 이용해 join 순서와 전략을 고른다. 통계는 catalog, data source, runtime에서 올 수 있다. 통계가 없거나 오래되면 40MiB dimension을 4GiB로 오판해 불필요한 sort-merge join을 고르거나, 반대로 큰 쪽을 broadcast해 executor 메모리를 소진할 수 있다.

**AQE(Adaptive Query Execution, 적응형 실행)** 는 실행 중 얻은 shuffle 통계로 후속 physical plan 일부를 다시 고르는 기능이다. Spark의 해당 버전과 설정에서 활성화되어야 하며 모든 잘못된 계획을 자동 수정하는 보장은 없다. 이미 비효율적으로 읽은 파일 바이트를 되돌릴 수도 없다. explain의 최초 계획, runtime statistics, 최종 adaptive plan을 따로 본다.

hint는 optimizer에 우선 전략을 요청하지만 join type과 engine capability 때문에 적용되지 않을 수 있다. hint가 있다는 이유만으로 실제 physical operator가 바뀌었다고 가정하지 않는다.

## 11. broadcast join 숫자 추적

fact가 100GiB, dimension이 40MiB라고 하자. **broadcast join** 은 작은 dimension을 각 executor로 보내 hash table을 만들고, 큰 fact의 각 partition을 로컬에서 probe한다. executor 50개면 원시 전송·보관량만 단순히 약 2,000MiB, 즉 약 2GiB가 cluster 전체에 생긴다. serialization과 hash table overhead는 별도다.

broadcast는 큰 fact를 key로 shuffle하지 않아도 되는 이점이 있다. 그러나 executor 하나당 dimension 사본을 담을 메모리가 필요하고, driver 수집이나 broadcast timeout이 문제가 될 수 있다. Spark 공식 기본 auto broadcast threshold 같은 값은 버전과 설정에 따라 확인해야 하며, 40MiB가 자동 broadcast된다는 보장은 없다. 실제 통계, threshold, hint, join type을 함께 본다.

## 12. sort-merge join과 skew

두 큰 입력을 join key로 shuffle하고 각 partition을 정렬·병합하는 방식을 생각하자. fact 100GiB 중 hot key 하나가 20GiB이고 나머지 80GiB가 399 partition에 고르게 간다면 일반 partition 평균은 약 205MiB이지만 hot task 하나는 20GiB다. 대부분 task가 끝난 뒤 그 하나가 오래 남는 **straggler** 가 된다.

평균 100GiB/400=256MiB만 보면 이 쏠림을 숨긴다. task size 분포, 최대값, key 빈도, spill과 fetch 시간을 본다. AQE skew join 분할은 설정과 조건이 맞을 때 큰 shuffle partition을 나눌 수 있지만, join 상대 데이터를 복제하는 추가 비용이 생길 수 있다. key에 임의 salt를 붙이는 방법도 정답 중복·재집계와 join 양쪽 변환을 정확히 설계해야 한다.

## 13. 장애와 재시도를 객체별로 읽는다

executor가 task 출력 data file을 upload한 뒤 죽으면 scheduler는 task를 다시 실행할 수 있다. 두 시도의 파일이 모두 저장소에 있어도 driver commit이 선택한 파일만 snapshot에 들어간다. driver가 metadata 후보를 쓴 뒤 catalog CAS 전에 죽으면 파일과 metadata는 존재하지만 current table은 이전 snapshot이다. CAS 성공 뒤 ACK 전에 죽으면 commit은 성공했으나 application은 실패로 볼 수 있다.

따라서 다음 네 질문을 순서대로 한다.

1. 어떤 application, stage, task attempt인가?
2. 어느 data/delete/manifest/metadata 파일이 생성됐는가?
3. catalog current pointer가 어느 metadata를 가리키는가?
4. reader가 고정한 snapshot과 실제 반환 행은 무엇인가?

파일 목록만 보고 commit을 추론하거나 Spark UI 성공만 보고 catalog publication을 추론하지 않는다.

## 14. 전체 검증 실험 설계

같은 snapshot ID에서 explain plan, 계획된 data/delete file 수, manifest 읽기 수, object-store bytes, Parquet row group 수, scan output rows를 기록한다. Spark 쪽은 stage/task 수, shuffle read/write, spill, 최대 task 시간과 최종 adaptive plan을 기록한다. cold run과 cache가 남은 warm run을 섞지 않는다.

최적화 전후 결과는 region별 SUM과 행 수를 먼저 비교한다. delete file을 의도적으로 포함한 작은 fixture에서 삭제된 행이 다시 나타나지 않는지 확인한다. writer 장애 시험은 upload 뒤 commit 전, CAS conflict, CAS 성공 뒤 ACK 유실을 나눠 current snapshot과 orphan을 검사한다. 여기의 모든 용량과 시간 수치는 교육용이며 실제 cluster 실험 결과가 아니다.

## 15. 완전 풀이 문제

### 문제 1. 100GiB의 파일 수

100GiB를 256MiB 목표로 단순 분할한다.

**풀이:** 100GiB=102,400MiB이고 102,400/256=400파일이다. 실제 파일 수는 Iceberg partition 경계, Spark task 크기, 압축률과 writer 분배 때문에 달라질 수 있다.

### 문제 2. pruning 비율

1,000파일에서 40파일이 후보로 남았다.

**풀이:** 후보 비율은 40/1,000=4%, 제거 비율은 96%다. 40파일 전체를 decode했다는 뜻은 아니다. Parquet row-group pruning 뒤 실제 bytes를 별도로 본다.

### 문제 3. 부분 집계 레코드

80 task가 KR, US, JP 세 region을 모두 가진다.

**풀이:** 각 task가 region당 부분 합 하나를 내면 최대 80×3=240 record다. exchange 뒤 region별로 합치면 최종 세 행이다. 원본 선택 행 수와 중간 record 수가 다르다.

### 문제 4. upload 성공 뒤 commit 실패

80 data file이 저장소에 있지만 catalog pointer는 여전히 v11이다.

**풀이:** 정상 Iceberg reader는 v11 graph에 없는 80파일을 읽지 않는다. 재시도 가능한 append면 새 후보에서 재사용할 수 있고, 끝내 참조되지 않으면 보존 정책 뒤 orphan cleanup 대상이다. 즉시 삭제하면 진행 중 retry를 깨뜨릴 수 있다.

### 문제 5. position delete 적용

delete record가 (A.parquet, 4)이고 B.parquet의 position 4도 같은 order_id다.

**풀이:** position delete는 파일 경로와 행 위치 쌍이다. A의 position 4만 제거한다. B까지 지우려면 B를 가리키는 position delete나 적용 가능한 equality delete가 필요하다.

### 문제 6. snapshot 고정

질의가 snapshot 81을 고정한 뒤 82가 commit됐다.

**풀이:** 진행 질의는 81의 manifest와 파일 집합으로 끝나야 일관된 읽기가 된다. 새로 시작한 질의는 current 82를 고를 수 있다. object store에서 82 파일을 우연히 발견해 진행 중 계획에 섞으면 안 된다.

### 문제 7. broadcast 총량

40MiB dimension을 50 executor가 각각 보관한다.

**풀이:** 원시 크기만 약 2,000MiB, 약 2GiB다. executor별 hash table overhead와 직렬화 사본이 추가될 수 있다. “shuffle이 없다”와 “전송·메모리 비용이 없다”는 다르다.

### 문제 8. hot partition

hot key 20GiB, 나머지 80GiB를 399개가 나눈다.

**풀이:** 일반 partition 평균은 80×1024/399≈205MiB다. hot task는 일반의 약 100배라 마지막 straggler가 된다. 평균 partition 크기 대신 최대값과 분포를 보고 AQE skew 처리, key 분할, 사전 집계를 검토한다.

## 16. 지원 조건을 확인하는 순서

Spark와 Iceberg의 기능 이름만으로 현재 환경 지원을 단정하지 않는다. Spark major/minor, Iceberg runtime artifact, catalog 종류, table format version, Spark SQL extensions, DataSource V2 경로를 기록한다. Iceberg 공식 Spark 쓰기 표에서 DELETE, UPDATE, MERGE가 extensions를 요구하는 경우가 있고 DataFrame API 지원도 Spark 버전에 따라 다르다. 실행 전에 현재 조합의 공식 호환성과 실제 explain을 확인한다.

## 근거와 더 읽을 자료

- [Apache Spark SQL Performance Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
- [Apache Iceberg Specification](https://iceberg.apache.org/spec/)
- [Apache Iceberg Spark Writes](https://iceberg.apache.org/docs/latest/spark-writes/)
- [Apache Iceberg Maintenance](https://iceberg.apache.org/docs/latest/maintenance/)
- [Apache Parquet File Format](https://parquet.apache.org/docs/file-format/)
