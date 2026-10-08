# 12. 문제·해설·용어사전

[이 책의 목차](README.md) · [이전 장](11-streaming-security-and-operations.md)

암기보다 작은 상태를 계산하고 반례를 만드는 것으로 확인한다. 먼저 답을 가리고 종이에 파일·참조·행을 그린 뒤 해설과 비교한다. 모든 ID와 크기는 교육용이다.

## 1. 파일과 테이블 — 입문 문제

### 문제 1: 폴더를 직접 읽으면 무엇이 틀릴까

현재 snapshot S2는 A와 B를 참조한다. 저장소에는 A, B, 실패한 작업의 C, 이전 snapshot의 D가 있다. 사용자가 폴더의 모든 Parquet를 읽었다. 현재 테이블을 읽은 것인가?

**해설.** 아니다. C와 D가 섞일 수 있고 삭제 정보도 놓친다. catalog → metadata → 선택 snapshot → manifests의 참조를 따라야 한다. Parquet reader가 파일을 올바르게 해석해도 테이블의 현재 파일 집합을 올바르게 선택한 것은 아니다.

### 문제 2: 스키마 rename을 계산한다

Field 3은 `region=Seoul`이다. 그 이름을 `shipping_region`으로 바꾸고 새 field 7을 `region`으로 추가했다. 과거 파일에서 두 컬럼의 값은 무엇인가? 새 필드는 optional이며 initial default는 없다고 하자.

**해설.** `shipping_region=Seoul`, 새 `region=NULL`이다. Field 3의 의미를 이름이 아니라 ID로 유지한다. 실제 ID 할당은 테이블 상태에 따라 다르다.

### 문제 3: 통계로 알 수 있는 범위

A의 금액 min/max는 10000/20000, B는 30000/40000이다. `amount=15000` 조회에서 어느 파일을 제외할 수 있는가? A에 15000이 있다고 확정할 수 있는가?

**해설.** B는 제외할 수 있다. A는 후보지만 15000의 존재를 확정할 수 없다. A가 `[10000,20000]`뿐일 수 있다. “없음을 증명”하는 pruning과 “있음을 증명”하는 검색을 구별한다.

## 2. 삭제와 sequence — 중급 문제

### 문제 4: 위치 삭제와 값 삭제

데이터 파일 F는 다음 네 행이다. Position은 0부터 시작한다.

| Position | order_id | amount |
| --- | --- | --- |
| 0 | 101 | 10000 |
| 1 | 102 | 20000 |
| 2 | 103 | 15000 |
| 3 | 102 | 22000 |

F의 position 1 삭제와 `order_id=102` equality delete는 각각 무엇을 지우는가? 적용 partition·sequence 조건은 충족한다고 하자.

**해설.** Position은 두 번째 행 하나를 지운다. Equality는 ID 102인 두 행을 지운다. Equality delete는 행의 유일성을 보장하지 않으며 조건에 맞는 행이 여러 개면 모두 영향받을 수 있다.

### 문제 5: 같은 commit의 재삽입

F의 data sequence는 4다. Sequence 5에서 equality delete `id=102`와 금액 23000원의 새 id 102를 담은 G를 함께 추가했다. G의 data sequence는 5다. 삭제 조건만 보면 F와 G에 어떤 효과가 있는가?

**해설.** Equality 적용은 data sequence가 delete sequence보다 작아야 한다. F는 `4 < 5`라 삭제 대상, G는 `5 < 5`가 거짓이라 새 행이 남는다. Partition 조건과 equality key match까지 함께 충족해야 한다. Position/DV에는 `<=` 규칙이 있으므로 같은 비교를 그대로 사용하지 않는다.

### 문제 6: file sequence와 data sequence

이동·재작성 경로에서 파일 엔트리의 file sequence가 9, 보존된 data sequence가 4라고 하자. Equality delete sequence 7의 적용 판단에 어느 번호를 사용하는가?

**해설.** 논리적 내용의 나이인 data sequence 4를 사용한다. File sequence는 엔트리 추가 시점을 다루는 별도 번호다. 실제 rewrite가 data sequence를 어떻게 보존·부여하는지는 작업과 엔진 구현을 확인한다.

### 문제 7: v3 삭제 벡터를 합친다

F에 position `{1,3}`이 삭제된 DV가 있다. 다음 commit에서 position 2도 삭제한다. 같은 snapshot에 F를 대상으로 DV1 `{1,3}`과 DV2 `{2}`를 각각 두어도 되는가?

**해설.** 안 된다. 한 data file당 한 snapshot에 최대 한 DV다. 새 상태에서는 `{1,2,3}`을 나타내는 통합 DV로 유지해야 한다. 기존 v2 position deletes도 해당 파일에 DV를 만들 때 통합 규칙을 따른다.

### 문제 8: Row lineage가 추적하는 것

`_row_id=42`, `_last_updated_sequence_number=6`인 행을 값 변경 없이 compaction했다. 두 값이 새 commit sequence 10으로 모두 바뀌어야 하는가? Equality-delete 기반 교체에서 동일 row ID를 반드시 유지하는가?

**해설.** 물리 배치만 바꾼 unchanged row의 계보를 업무 update처럼 바꾸지 않는다. Equality-delete 기반 update는 기존 row ID를 읽지 않는 경로에서 삭제+새 행으로 처리되므로 새 ID가 할당된다. Row lineage는 모든 원천 시스템의 처리 lineage와 다른 개념이다.

## 3. 시간 여행과 유지보수 — 운영 문제

### 문제 9: 스냅샷 보존 용량

S1이 A 100 MiB를 참조한다. S2는 이를 B 90 MiB로 rewrite했다. S1이 tag로 보존된다. 현재 데이터 크기와 남아 있는 데이터 파일의 총 크기는 얼마인가? 메타데이터는 계산에서 제외한다.

**해설.** 현재는 90 MiB, 두 파일 합계는 190 MiB다. 현재 크기와 저장소 사용량은 다르다. S1을 보존하는 참조가 사라지고 지원되는 정리 절차가 수행되어야 A의 정리를 검토할 수 있다.

### 문제 10: 안전하지 않은 고아 판정

Writer가 2시간 동안 파일을 쓰고 마지막에 커밋한다. Cleaner가 생성 30분이 지났고 현재 참조가 없다는 이유로 파일을 지운다. 어떤 반례가 있는가?

**해설.** 아직 정상 진행 중인 writer의 파일이다. 유예 기간은 최장 실행·업로드·재시도·시계 오차를 고려해야 한다. 현재 snapshot의 참조만으로 orphan을 판정하면 과거 snapshot과 공유 테이블의 파일도 놓칠 수 있다.

### 문제 11: 커밋 timeout과 중복

서버 커밋 성공 직후 응답이 끊겼다. 사용자가 같은 100개 행을 새 작업으로 다시 append한다. 어떤 결과가 가능한가?

**해설.** 200개가 될 수 있다. 원자적 커밋은 최초 작업의 일부만 보이는 문제를 다루지만 사용자 재실행의 중복을 자동 제거하지 않는다. 성공 여부 확인과 작업 식별·멱등성 설계를 연결한다.

### 문제 12: 라이브러리와 포맷

2026-10-08 기준 Iceberg 1.12.0을 설치했다. 테이블을 v4로 올리면 되는가? 최신 Spark writer만 v3를 지원하면 공유 테이블을 올려도 되는가?

**해설.** 1.12.0은 v4 테이블 read/write를 지원하지 않고 v4는 개발 중이다. v3도 모든 reader·writer·maintenance·복구 도구를 확인해야 한다. 최신 writer 하나가 전체 환경을 대표하지 않는다.

## 4. 종합 설계 과제

### 과제 A: 센서 1000대의 적재 테이블

장치 1000대가 분당 한 이벤트를 보낸다. 이벤트는 `device_id`, `event_time`, `event_id`, `temperature_c`, `source_sequence`를 가진다. 3일 늦게 들어올 수 있고 재전송으로 중복될 수 있다. 대시보드는 하루별 장치 종류 평균, 연구는 특정 장치의 1주일 기록을 읽는다.

다음 항목을 문장과 그림으로 제출한다.

1. 원천 이벤트 테이블과 최신 상태/정제 테이블의 의미.
2. 사건 시각과 수신·커밋 시각의 기록 방식.
3. Partition과 sort 후보, 고카디널리티 작은 파일 반례.
4. 중복 이벤트 처리와 source 순서의 사용.
5. 스트리밍 checkpoint·snapshot 보존·reader 지연의 관계.
6. 연구 재현성에 필요한 snapshot·코드·단위·보존 기록.

**해설 방향.** 1일 이벤트 수는 `1000 × 60 × 24 = 1,440,000`이다. 행의 실제 바이트 크기를 측정하지 않고 저장 용량을 단정하지 않는다. 날짜 partition과 device 관련 bucket/sort 등을 후보로 두고 실제 쿼리·분포·파일 수로 비교한다. 이벤트 ID 중복 제거, 늦은 입력, 단위 변경을 schema 계약과 연결한다. 답은 한 구성으로 고정되지 않는다.

### 과제 B: v2에서 v3로 전환하는 팀

배치 writer는 최신, 스트리밍 writer는 구 버전, BI reader는 vendor connector, compactor는 독립 Spark 작업이다. v3 DV가 필요하다. 업그레이드 전 시험 계획을 작성한다.

**해설 방향.** 릴리스·engine·catalog·table format을 별도로 기록한다. Legacy equality/position files와 DV가 섞인 테스트를 만든다. 모든 reader에서 동일 결과를 검증하고 모든 writer와 compactor에서 sequence·lineage·default 보존을 확인한다. unsupported reader의 명확한 거절도 시험한다. 포맷 downgrade를 간단한 복구 수단으로 가정하지 않는다.

### 과제 C: 논리 삭제와 물리 제거

현재 테이블에서 한 사용자 행을 DELETE했다. 과거 snapshot과 S3 versioning, 백업이 있다. 삭제 목표를 “현재 검색 결과 제외”와 “전체 보관 위치의 바이트 제거”로 각각 정하고 필요한 작업과 증거를 적는다.

**해설 방향.** 두 요구는 다르다. Query 결과, 현재 파일의 삭제 방식, 과거 참조, 파일 rewrite, 만료·정리, 객체 버전·백업 정책을 연결한다. 실제 보존 요구와 조직 정책을 먼저 정한다. 테이블 포맷만으로 법적 준수를 판정하지 않는다.

## 5. 용어사전

| 용어 | 쉬운 뜻 | 자세히 볼 장 |
| --- | --- | --- |
| Row / Column | 한 기록 / 같은 의미의 값 자리 | 00 |
| Schema | 필드 이름·타입·필수 여부의 구조 약속 | 00·03 |
| File format | 파일 바이트를 저장·해석하는 규칙 | 00 |
| Table format | 여러 파일을 하나의 테이블로 관리하는 규칙 | 00·01 |
| Parquet | 컬럼 단위 저장과 읽기를 위한 파일 형식 | 00·02 |
| Avro | 스키마를 가진 레코드 파일 형식 | 01 |
| ORC | 분석용 컬럼 파일 형식의 하나 | 01 |
| Catalog | 테이블 이름 조회와 상태·커밋의 진입점 | 01·08 |
| Namespace | 이름을 묶는 공간 | 08 |
| FileIO | 파일 읽기·쓰기 구현 계층 | 08 |
| UUID | 대상을 구별하는 고유 식별자 | 01·08 |
| Metadata | 데이터를 설명하는 정보 | 01 |
| Snapshot | 특정 테이블 상태의 파일·참조 정보 | 01·04 |
| Manifest list | 스냅샷의 manifest 목록과 요약 | 01 |
| Manifest | 파일별 경로·상태·통계 등을 기록한 목록 | 01 |
| Commit | 새 테이블 상태를 확정·공개 | 02 |
| Optimistic concurrency | 변경을 준비한 뒤 커밋에서 충돌 확인 | 02 |
| CAS | 예상한 상태일 때만 새 상태로 교체하는 개념 | 02 |
| Idempotency | 요청 반복이 원하는 효과를 중복시키지 않음 | 02·11 |
| Pruning | 조건에 맞지 않을 후보를 미리 제외 | 02 |
| Predicate | 참·거짓을 판단하는 조건식 | 02 |
| Projection | 필요한 컬럼을 골라 읽기 | 02·03 |
| Partition | 정해진 값·변환으로 나눈 묶음 | 03 |
| Partition spec | partition의 source·transform 규칙 | 03 |
| Field ID | 이름·순서와 별개인 필드 식별 번호 | 03 |
| Hidden partitioning | 원래 컬럼 조건으로 파티션 계획 연결 | 03 |
| Bucket | 해시 계산 결과로 묶음을 나누는 변환 | 03 |
| Sort order | 파일에 쓸 행의 정렬 규칙 | 03·10 |
| Time travel | 보존된 과거 스냅샷을 선택해 조회 | 04 |
| Branch / Tag | 진행 가능한 참조 / 특정 상태의 이름 있는 참조 | 04 |
| WAP | 입력을 쓰고 검사한 뒤 공개하는 패턴 | 04 |
| COW | 변경이 있는 데이터 파일을 다시 쓰는 방식 | 05 |
| MOR | 읽을 때 데이터와 삭제 정보를 합쳐 반영 | 05 |
| Position delete | 파일 주소와 0부터 시작하는 위치로 삭제 | 05 |
| Equality delete | 지정 컬럼 값에 맞는 행을 삭제 | 05 |
| Data sequence number | 내용의 논리적 나이·삭제 적용 순서 | 05 |
| File sequence number | 파일 엔트리가 추가된 순서 | 05 |
| DV / Deletion vector | 삭제된 위치를 표시하는 bitmap | 06 |
| Puffin | DV·통계 등의 바이너리 blob 파일 형식 | 01·06 |
| Row lineage | 행 ID와 마지막 논리 변경 순서의 추적 | 06 |
| Initial / Write default | 기존 행 읽기 / 새 쓰기의 누락 값 기본값 | 06 |
| Variant | 반정형 값을 나타내는 확장 타입 | 06 |
| Nanosecond | 10억 분의 1초, ns | 06 |
| Geometry / Geography | 평면·공간 기하 / 지구 표면 관련 공간 타입 | 06 |
| Compaction | 파일을 합치거나 다시 배치하는 rewrite | 10 |
| Retention | 과거 상태를 보존할 기간·개수 정책 | 04·10 |
| Orphan | 유효한 참조가 없는 파일, 안전 기간 확인 필요 | 10 |
| CDC | 원천 삽입·수정·삭제를 이벤트로 전달 | 11 |
| Upsert | key가 있으면 수정, 없으면 삽입 | 11 |
| Checkpoint | 복구를 위한 입력 위치·처리 상태 | 11 |
| Event / Commit time | 사건 발생 / 테이블 확정 시각 | 04·11 |
| Credential vending | 제한된 파일 접근 자격증명 제공 | 08·11 |

## 6. 공식 자료를 찾는 지도

자료 확인일은 2026-10-08이다. `latest` 문서는 이후 달라질 수 있다. 운영 판단에는 사용 중인 릴리스의 문서·artifact·릴리스 노트를 함께 확인한다. 이 책의 그림·주문 값·계산 문제는 직접 만든 설명용 자료다.

| 자료 | 확인할 내용 |
| --- | --- |
| [Table specification](https://iceberg.apache.org/spec/) | 파일·metadata·sequence·삭제·타입의 규범적 계약 |
| [Puffin specification](https://iceberg.apache.org/puffin-spec/) | blob 구조와 deletion-vector-v1 |
| [REST catalog specification](https://iceberg.apache.org/rest-catalog-spec/) | 카탈로그 API·인증·커밋·지원 기능 |
| [Releases](https://iceberg.apache.org/releases/) | 공식 릴리스 날짜와 artifact |
| [1.12.0 release 발표](https://iceberg.apache.org/blog/apache-iceberg-1.12.0-release/) | 최신 기능과 v4 foundations의 실제 범위 |
| [1.11.0 release 발표](https://iceberg.apache.org/blog/apache-iceberg-1.11.0-release/) | REST protocol 등의 최근 변화 |
| [Multi-engine support](https://iceberg.apache.org/multi-engine-support/) | 엔진 integration 범위 |
| [Reliability](https://iceberg.apache.org/docs/latest/reliability/) | 일관된 읽기와 동시성 모델 |
| [Evolution](https://iceberg.apache.org/docs/latest/evolution/) | 스키마·파티션 변경 |
| [Partitioning](https://iceberg.apache.org/docs/latest/partitioning/) | 숨겨진 파티션과 변환 |
| [Spark DDL](https://iceberg.apache.org/docs/latest/spark-ddl/) | 테이블·컬럼·partition 변경 문법 |
| [Spark writes](https://iceberg.apache.org/docs/latest/spark-writes/) | INSERT·MERGE·UPDATE·DELETE |
| [Spark queries](https://iceberg.apache.org/docs/latest/spark-queries/) | 시간 여행과 metadata tables |
| [Branching](https://iceberg.apache.org/docs/latest/branching/) | branch·tag·WAP·보존 |
| [Spark procedures](https://iceberg.apache.org/docs/latest/spark-procedures/) | rewrite·rollback·expiration·orphan |
| [Maintenance](https://iceberg.apache.org/docs/latest/maintenance/) | 파일·snapshot의 수명주기 |
| [Configuration](https://iceberg.apache.org/docs/latest/configuration/) | mode·크기·통계·재시도·보존 설정 |
| [Spark streaming](https://iceberg.apache.org/docs/latest/spark-structured-streaming/) | streaming read/write와 제한 |
| [Flink writes](https://iceberg.apache.org/docs/latest/flink-writes/) | streaming upsert와 sink 지원 조건 |
| [Apache Spark 4.0 release](https://spark.apache.org/releases/spark-release-4-0-0.html) | Java·Scala·Python 실행 전제 |
| [Parquet overview](https://parquet.apache.org/docs/overview/) | 파일의 컬럼 저장 개념 |

## 7. 학습 완료 점검

다음 문장을 스스로 완성하면 이 책의 핵심을 연결한 것이다.

- “현재 테이블에 속한 파일은 ___을 따라 찾는다.”
- “새 파일 작성 성공과 테이블 커밋 성공은 ___ 때문에 다르다.”
- “v2 equality delete와 position delete의 sequence 비교는 각각 ___이다.”
- “v3 DV는 ___ 단위이며 같은 snapshot에서 ___개까지 존재한다.”
- “컬럼 rename 뒤 과거 값을 유지하는 식별자는 ___이다.”
- “파티션 명세 변경만으로 과거 파일의 물리 배치가 ___.”
- “Snapshot ID와 Iceberg 라이브러리 버전은 각각 ___을 나타낸다.”
- “현재 행을 DELETE한 것과 모든 보관 사본의 바이트 제거는 ___.”

정답은 차례대로 커밋된 metadata와 snapshot 참조, 작성과 공개 단계 분리, `<`와 `<=`, 단일 데이터 파일·최대 하나, field ID, 자동 바뀌지 않음, 상태 식별자·구현 릴리스, 서로 다른 작업이다. 실제 환경에서는 partition·파일 match·지원 버전 등 조건도 함께 설명한다.

[교재 처음으로](README.md) · [통합 learning 목차](../README.md)
