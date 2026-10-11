# 07. 읽기와 쓰기

## 저장 byte에서 원자적으로 공개된 결과까지

[이 책의 목차](README.md) · [이전 장](06-memory-and-performance.md)

Spark의 read는 “파일을 연다” 한 동작이 아니다. 저장소의 file을 찾고, schema를 정하고, footer와 row group 통계로 읽을 후보를 줄이고, read partition을 task에 배정한 뒤 row를 만든다. Write도 task가 파일을 쓴 순간 끝나지 않는다. 각 task output을 모아 job 또는 table commit이 성공해야 독자가 완성된 결과를 볼 수 있다.

## 1. 읽기 객체와 위치·수명

**File**은 저장소에 이름과 byte 내용으로 지속되는 객체다. HDFS나 로컬 파일시스템에서는 directory entry와 block으로 보이고, object store에서는 object name과 data로 관리된다. Spark executor가 사라져도 저장소의 file은 남는다.

**Schema**는 각 열의 이름, 자료형, null 허용 여부를 정의한 구조다. Driver의 논리 계획과 scan 계획에 있으며 executor는 이 schema로 byte를 row나 column batch로 해석한다. CSV처럼 자체 형 정보가 약한 원천은 명시적 schema가 특히 중요하다. 추론은 샘플이나 추가 scan 비용과 오판 위험을 만든다.

**Parquet row group**은 한 파일 내부에서 여러 행을 열별로 묶어 저장한 단위다. 각 column chunk에는 해당 row group의 한 열 값들이 있다. **Footer**는 파일 끝부분에 있는 metadata 영역으로 schema, row group 위치, column 통계 같은 정보를 담는다. Reader는 footer를 읽어 어느 byte 범위가 후보인지 계획할 수 있다. Footer와 통계가 있다고 모든 조건을 완전히 판단할 수 있는 것은 아니다.

**Read partition**, 또는 Spark input partition은 scan task 하나에 배정할 논리 입력 조각이다. File 하나가 커서 여러 split이 되면 여러 read partition이 생길 수 있고, 작은 file 여러 개를 한 read partition에 묶을 수도 있다. Read partition 객체는 Driver가 scan을 계획할 때 생성되고 stage가 끝나면 실행 계획 수명 뒤 사라진다.

**Row**는 executor가 byte를 해석해 만든 실행 중 값이다. 필요한 열만 읽으면 나머지 열의 row 값은 만들 필요가 줄어든다. Filter를 통과하지 못한 row는 downstream으로 전달되지 않고 batch 처리가 끝나면 회수 대상이 된다.

## 2. 세 파일의 전체 읽기 trace

원천에 다음 Parquet file 세 개가 있다고 하자. 한 행의 amount를 합산하며 amount>=20 조건을 적용한다.

| File | 저장 행 |
|---|---|
| A | (KR,10), (US,20), (KR,30) |
| B | (JP,40), (KR,50), (US,60) |
| C | (KR,70), (JP,80), (US,90) |

이 예에서는 우연히 A→P0, B→P1, C→P2로 file 하나와 read partition 하나가 대응한다고 가정한다. 일반 규칙은 아니다.

1. Driver가 경로 목록이나 table metadata에서 A, B, C를 발견한다.
2. 각 Parquet footer를 읽어 schema와 row group metadata를 확인한다.
3. Query가 region과 amount만 요구하므로 scan read schema도 두 열로 줄일 수 있다.
4. amount>=20 조건을 data source가 지원하면 Parquet filter pushdown 후보가 된다.
5. Driver가 P0, P1, P2 read partition을 만들고 stage task를 예약한다.
6. T0는 A의 필요한 column byte를 읽고 KR10을 제거해 US20, KR30을 낸다.
7. T1은 B 세 행을 모두 내고, T2도 C 세 행을 모두 낸다.
8. Filter 뒤 행은 2+3+3=8개다.
9. Region별 shuffle과 reduce 뒤 KR=30+50+70=150, US=20+60+90=170, JP=40+80=120이다.

| Task | 읽은 file | 조건 뒤 row | 지역 부분합 |
|---|---|---|---|
| T0/P0 | A | US20, KR30 | US20, KR30 |
| T1/P1 | B | JP40, KR50, US60 | JP40, KR50, US60 |
| T2/P2 | C | KR70, JP80, US90 | KR70, JP80, US90 |

File 세 개라 task 세 개인 것은 이 모형의 가정이다. A가 매우 크면 여러 split task가 읽을 수 있고 A,B,C가 작으면 한 task가 여러 file을 순차로 열 수 있다. Spark SQL의 file partition 설정과 source capability가 실제 배치를 정한다.

## 3. Pushdown과 pruning을 구분한다

**Pushdown**은 상위 Spark operator에서 할 일을 data source scan 가까이 내려 보내는 것이다. Column pruning은 필요한 열만 read schema에 포함하고, filter pushdown은 source가 조건을 사용해 불필요한 row group이나 record 처리를 줄이게 한다.

amount>=20이 scan의 PushedFilters에 보여도 저장소에서 정확히 10 한 행만 읽고 나머지는 전혀 읽지 않았다고 단정하지 않는다. Parquet row group 최소·최대 통계가 [10,30]이면 이 row group에는 통과 행이 있을 수 있어 column byte를 읽어 row 수준 조건을 적용해야 한다. Row group 전체 max가 10이면 amount>=20 조건으로 그 group을 건너뛸 수 있다.

**Partition pruning**은 저장 테이블의 partition 값으로 file 집합 자체를 줄이는 일이다. date=2026-10-11 폴더나 table partition metadata가 있을 때 다른 날짜 file을 scan 후보에서 제외한다. Row group 통계로 file 내부를 줄이는 것과 객체 위치가 다르다.

실제 확인 순서는 다음과 같다.

- Scan의 ReadSchema에 필요한 열만 있는가?
- PartitionFilters가 어느 저장 partition을 제외했는가?
- PushedFilters가 source에 전달되었는가?
- Runtime scan bytes와 row 수가 기대만큼 줄었는가?
- Spark 위쪽에 남은 Filter가 최종 정확성을 보장하는가?

Spark 4.2 Parquet 문서에서 spark.sql.parquet.filterPushdown 기본값은 true다. 그러나 조건 종류, 통계 유무와 정확성, 암호화나 source 구현에 따라 skip 범위가 달라진다.

## 4. Schema를 잘못 읽는 실패

CSV의 amount 열에 문자열 error가 섞였다고 하자. Schema를 amount integer로 정했을 때 source 옵션은 parse 실패, NULL 변환, corrupt record 격리처럼 다른 동작을 낼 수 있다. 조용히 row를 버리면 합계 340이 나온 이유를 찾기 어렵다.

Schema 계약에는 다음을 포함한다.

| 항목 | 예 |
|---|---|
| 열 이름과 형 | region string, amount long |
| null 허용 | region은 non-null |
| 시간 해석 | UTC, 형식 yyyy-MM-dd HH:mm:ss |
| 오류 정책 | 잘못된 amount는 격리하고 count 기록 |
| 진화 규칙 | 새 nullable 열 허용, 형 축소 금지 |

Parquet part-file들의 schema가 다를 때 mergeSchema는 파일별 schema를 수집·병합하는 추가 비용과 충돌 판단을 만든다. Spark 공식 Parquet 문서에서 schema merging은 기본적으로 꺼져 있으며 필요할 때 옵션으로 켠다. “같은 확장자”를 “같은 계약”으로 보지 않는다.

## 5. 저장 partition과 실행 partition

| 객체 | 실제 위치 | 생성 주체 | 목적 |
|---|---|---|---|
| Spark read partition | Driver 실행 계획 | file source | scan task 입력 |
| Shuffle partition | shuffle block과 다음 stage 계획 | partitioner/AQE | 같은 key 재분배 |
| Table partition | directory 또는 table metadata 값 | writer/table spec | 저장 배치·pruning |
| Parquet row group | file 내부 byte 구간 | Parquet writer | column I/O·통계 |
| Output file | 저장소 | writer task | 지속 결과 byte |

repartition(4)는 DataFrame 실행 분포를 shuffle로 바꾼다. partitionBy("date")는 file writer가 date 값별 저장 경로를 나누는 규칙이다. 같은 task가 여러 date 값을 받으면 date별로 여러 writer를 열어 여러 file을 만들 수 있다. 빈 task는 file을 만들지 않을 수도 있다. 따라서 repartition(4).write.partitionBy("date")가 정확히 네 file을 보장하지 않는다.

Iceberg hidden partitioning은 table metadata의 partition transform과 writer distribution을 사용한다. 일반 Parquet directory partitionBy와 같은 API나 공개 규칙이라고 가정하지 않는다.

## 6. 쓰기 전에 만들어지는 실행 상태

위 집계 결과 세 행 KR150, US170, JP120을 저장한다고 하자. Writer stage의 논리 output partition이 세 개이고 task T0, T1, T2가 각각 한 행을 맡는 단순 모형을 쓴다.

**Task output**은 한 task attempt가 만든 file과 그 metadata다. T0는 F0, T1은 F1, T2는 F2를 작성한다. File byte는 object store나 filesystem에 지속될 수 있지만, commit 전에는 완성 dataset의 유효 파일이라고 볼 수 없다.

Writer task 내부에는 encoder, column buffer, compression 상태, Parquet row group builder가 executor memory에 생긴다. Row group이 닫히면 compressed column pages가 file로 기록되고 footer가 마지막에 완성된다. Task가 성공 보고를 마치면 이 memory 상태는 소멸한다.

| 시점 | 저장소에 보일 수 있는 것 | Coordinator 상태 | Reader가 믿을 수 있는 것 |
|---|---|---|---|
| T0 완료 | F0 또는 임시 F0 | T0 성공 | 아직 없음 |
| T1 완료 | F0,F1 | T0,T1 성공 | 아직 없음 |
| T2 실패 | F0,F1, 실패 시도 조각 | 전체 미완료 | 완성 dataset 아님 |
| T2 retry 완료 | F0,F1,F2b | 세 논리 task 성공 | commit 전 미확정 |
| Job commit 성공 | 유효 file 집합 | 성공 표지/metadata | 새 결과 공개 |

File이 존재한다는 사실과 dataset이 commit되었다는 사실은 다르다. 경로 glob이 F0,F1만 읽으면 부분 결과를 정상 데이터로 오해할 수 있다.

## 7. Commit과 atomic publish

**Commit**은 성공한 task output 중 어느 file 집합이 새 결과인지 확정하는 절차다. Task commit은 한 attempt의 결과를 채택하고, job commit은 모든 필수 task 성공 뒤 dataset을 공개한다. DataSource V2나 table format은 writer message를 Driver coordinator로 모아 최종 commit 또는 abort를 호출할 수 있다.

**Atomic publish**는 독자가 이전 완성 상태 또는 새 완성 상태 중 하나를 보고 중간 혼합은 보지 않게 공개하는 성질이다. 모든 저장소와 file writer가 자동으로 이 성질을 제공하는 것은 아니다.

Iceberg table은 새 data file과 metadata를 준비한 뒤 새 snapshot을 가리키도록 table state를 교체한다. Commit 성공 전 file은 저장소에 있어도 current snapshot이 참조하지 않을 수 있다. Commit 충돌로 실패한 file도 orphan으로 남을 수 있어 별도 안전한 정리 절차가 필요하다. Reader는 catalog의 current metadata와 snapshot, manifest, delete 정보를 따라 유효 file을 고른다.

일반 Parquet 경로 glob은 이런 table snapshot을 적용하지 않는다. 폴더에 보이는 과거 file, 실패 attempt file, Iceberg가 더는 참조하지 않는 file까지 섞을 수 있다. File format과 table format을 구분하는 이유다.

~~~mermaid
sequenceDiagram
    participant E as Executor tasks
    participant O as Object store
    participant C as Commit coordinator/catalog
    participant R as Reader
    E->>O: F0, F1, F2 작성
    E-->>C: task output metadata 보고
    C->>C: 전체 성공·충돌 조건 검증
    C-->>R: commit 뒤 새 파일 집합 공개
~~~

## 8. Partial failure 전체 추적

T0와 T1이 성공해 F0, F1을 썼고 T2가 network timeout으로 실패했다고 하자.

1. 저장소에는 F0와 F1이 보일 수 있다.
2. Coordinator는 T2 성공 message가 없으므로 job을 commit하지 않는다.
3. Scheduler가 T2를 재시도한다.
4. 새 attempt는 이름 충돌을 피하는 F2b 또는 별도 attempt 경로에 쓴다.
5. T2b 성공 message를 coordinator가 받는다.
6. Coordinator는 T0, T1, T2b를 유효 output으로 선택하고 job/table commit을 수행한다.
7. 실패한 T2의 임시 조각은 abort나 후속 cleanup 대상이다.
8. 독자는 commit 뒤 F0,F1,F2b에 해당하는 완성 집합을 읽는다.

이때 task attempt가 최종 이름 F2에 직접 덮어쓰고 두 attempt가 경주하면 늦게 끝난 실패 attempt가 성공 결과를 덮을 수 있다. Commit protocol은 attempt별 격리와 최종 선택을 제공해야 한다.

Commit은 성공했지만 Driver가 성공 응답을 받기 전에 끊길 수도 있다. 호출자는 결과를 unknown으로 보아야 한다. 상태 조회 없이 append 전체를 다시 실행하면 같은 세 행을 중복 추가할 수 있다. Query ID, batch ID, snapshot summary나 멱등 key로 이미 commit되었는지 확인한 뒤 재시도를 결정한다.

## 9. Object store는 파일시스템과 다르다

**Object store**는 object-name→data 형태의 원격 저장소다. Directory는 이름 prefix로 흉내 내며, rename이 metadata pointer 한 번 변경이 아니라 copy와 delete로 구현될 수 있다. Spark 4.2 cloud integration 문서는 object store를 고전 filesystem의 직접 대체로 보지 말라고 하며, rename이 느리고 실패 시 상태가 불명확할 수 있다고 설명한다.

따라서 “임시 directory 전체를 원자적으로 rename하면 publish 완료”라는 로컬 filesystem 가정을 S3 같은 대상에 그대로 옮기지 않는다. Connector와 committer가 제공하는 보장을 확인한다. S3A 계열의 zero-rename committer는 multipart upload의 최종 공개를 job commit까지 미루는 방식처럼 object store에 맞춘 경로를 쓸 수 있다. GCS나 Azure 대상에서도 manifest committer 지원과 Hadoop 버전 조건이 다르다.

Object 하나는 완성되어 보여도 여러 object를 묶은 dataset 전체 공개가 자동 atomic인 것은 아니다. Atomic publish가 필요하면 table metadata commit, manifest pointer, 대상에 맞는 commit protocol을 사용한다. 정확한 지원은 Spark 버전만이 아니라 Hadoop connector, cloud service, committer 설정까지 포함한다.

## 10. Append와 overwrite 범위

**Append**는 기존 유효 결과에 새 행/file을 추가하는 쓰기 의미다. **Overwrite**는 정한 범위를 새 결과로 교체한다. 범위가 전체 table인지, 조건에 맞는 row/file인지, 새 데이터가 닿은 partition인지 구분해야 한다.

| 표현 의도 | 교체 범위 | 위험 |
|---|---|---|
| 전체 path overwrite | 대상 path 전체 | 실패 중 빈 상태·다른 writer 충돌 |
| static partition overwrite | 명시 partition | 조건 실수로 넓은 삭제 |
| dynamic partition overwrite | 새 row가 쓰인 partition | partition spec 변경 시 의미 변화 |
| overwrite by filter | filter가 가리킨 범위 | source 지원·충돌 검증 필요 |
| Iceberg overwrite/merge | snapshot에 기록된 file 변화 | concurrent commit 조건 필요 |

“먼저 폴더를 지우고 새 file을 쓴다”는 절차는 원자적 publish가 아니다. 삭제 뒤 task 일부가 실패하면 독자는 빈 결과나 부분 결과를 볼 수 있다. 동시 writer A와 B가 같은 path를 overwrite하면 서로의 file 삭제와 publish가 교차할 수 있다.

Iceberg 공식 Spark write 문서는 DataFrameWriterV2의 명시적 overwrite와 table commit을 사용하며, MERGE가 영향을 받는 data file만 교체할 수 있어 partition 변화에 민감한 dynamic overwrite보다 권장되는 경우를 설명한다. 지원에는 catalog 구성과 Iceberg Spark extension, Spark 버전 조건이 따를 수 있다.

## 11. 이름 충돌과 동시 writer 반례

Writer A와 B가 동시에 output/part-000.parquet를 쓰는 나쁜 설계를 보자.

1. A가 임시 내용을 쓰기 시작한다.
2. B도 같은 최종 이름을 선택한다.
3. A가 commit 성공했다고 기록한다.
4. B가 늦게 같은 object를 덮어쓴다.
5. A의 metadata는 자기 checksum을 기대하지만 path 내용은 B의 것이 된다.

Attempt ID, job UUID, table data file UUID처럼 충돌하지 않는 이름을 생성하고 metadata commit이 유효 file을 가리키게 해야 한다. “Task 번호가 다르니 안전”도 충분하지 않다. 다른 job은 같은 task 번호를 쓸 수 있다.

Iceberg 같은 optimistic commit에서는 두 writer가 같은 base snapshot에서 시작할 수 있다. 먼저 한 writer가 current metadata를 바꾸면 다음 writer는 충돌 조건을 다시 검증하고 재시도하거나 실패해야 한다. 마지막 writer가 무조건 pointer를 덮으면 첫 변경을 잃는다.

## 12. 작은 file과 output 병렬성

1 GiB를 한 번에 처리해 적절한 크기의 몇 file로 쓰는 것과 1 MiB씩 1,024번 별도 commit하는 것은 총 byte가 같아도 file listing, footer read, open request, task planning 비용이 다르다. 작은 file은 저장 byte보다 metadata와 요청 수가 병목이 될 수 있다.

coalesce(1)은 output task를 하나로 줄여 file 수를 줄이는 후보지만 큰 결과를 한 task에 몰아 병렬성을 잃는다. Repartition은 실행 분포를 바꾸지만 정확한 file 수 계약은 아니다. Writer의 maxRecordsPerFile, table partition 수, 한 task가 연 writer 수, empty partition, retry와 commit protocol이 file 수에 영향을 준다.

파일 수를 맞추는 것보다 목표 file byte 범위, task max 시간, 저장 partition별 file 분포와 downstream scan 비용을 함께 본다. Iceberg에서는 rewrite/compaction이 작은 file을 나중에 합칠 수 있지만 별도 I/O와 commit 비용이 든다.

## 13. JDBC 경계

JDBC는 JVM 프로그램이 관계형 database와 통신하는 API다. JDBC read partition을 네 개 만들면 executor가 서로 다른 조건의 query와 connection을 원천 DB에 동시에 열 수 있다. Spark input partition은 DB의 물리 partition과 같은 객체가 아니다.

lowerBound와 upperBound는 partition stride를 계산하는 데 쓰이며 항상 전체 row를 거르는 filter와 같다고 단정하지 않는다. NULL partition column 처리, 각 query가 같은 snapshot을 보는지, connection 제한을 확인한다. 빠르게 읽으려고 수백 connection을 열면 운영 DB를 압박한다.

JDBC write도 task마다 transaction이 생길 수 있다. Spark job 전체가 database의 단일 transaction이 된다고 가정하지 않는다. Task 재시도로 insert가 반복될 수 있으므로 유일 key, upsert, staging table과 최종 transaction 같은 멱등 설계가 필요하다.

## 14. 완전 풀이 1: 필터부터 합계까지

**문제.** A,B,C의 아홉 행에서 amount>=20을 적용한 행 수와 region 합계를 구하라.

**풀이.** KR10 한 행만 제거되어 8행이다. KR은 30+50+70=150, US는 20+60+90=170, JP는 40+80=120이다. T0은 두 행, T1과 T2는 각 세 행을 낸다.

**조건 변화.** amount>20이면 US20도 빠져 7행이고 US 합은 150이다. 경계 연산자 하나가 출력과 pushdown 조건을 모두 바꾼다.

## 15. 완전 풀이 2: Row group skip

**문제.** Row group G0 amount min/max가 1/10, G1이 10/30일 때 amount>=20 조건으로 무엇을 건너뛰는가?

**풀이.** G0의 max 10은 20보다 작으므로 통계를 신뢰할 수 있는 지원 조건에서 G0 전체를 건너뛸 수 있다. G1은 범위가 조건 양쪽에 걸쳐 있어 읽고 row 수준으로 판단해야 한다.

**조건 변화.** 통계가 없거나 잘린 문자열 통계가 조건 판단에 충분하지 않으면 skip하지 못한다. PushedFilters 표기만 보고 실제 scan byte 감소를 확정하지 않는다.

## 16. 완전 풀이 3: File 수와 task 수

**문제.** Parquet file 세 개면 read task도 세 개인가?

**풀이.** 모형에서는 그렇지만 일반적으로 아니다. 큰 file은 여러 split, 작은 file들은 한 partition으로 묶일 수 있다. Driver가 만든 read partition 수가 stage의 scan task 수와 연결된다.

**조건 변화.** 압축 codec이 split을 지원하지 않거나 source가 특정 단위를 요구하면 분할 방식이 달라진다. 실제 scan plan과 UI task 수를 본다.

## 17. 완전 풀이 4: Partial output

**문제.** F0,F1이 저장소에 있고 F2 task가 실패했다. 독자가 F0,F1을 새 dataset으로 읽어도 되는가?

**풀이.** 안 된다. Job/table commit 전이면 전체 논리 output이 확정되지 않았다. F0,F1은 성공 task output일 뿐 완성 dataset이 아니다. Coordinator가 T2 재시도 결과까지 채택해 commit한 뒤 공개한다.

**조건 변화.** 외부 manifest가 atomic하게 공개되고 그 manifest가 F0,F1만을 의도한 완성 집합으로 가리킨다면 그때는 계약이 다르다. 공개 기준은 파일 존재가 아니라 protocol이다.

## 18. 완전 풀이 5: 성공 응답 유실

**문제.** Append commit 뒤 client가 timeout을 받았다. 전체 job을 즉시 다시 실행해도 되는가?

**풀이.** Commit은 성공했지만 응답만 유실되었을 수 있어 결과가 unknown이다. Snapshot, query/batch ID, destination metadata로 이미 반영됐는지 조회한다. 확인 없이 재실행하면 중복 append가 생긴다.

**조건 변화.** 쓰기가 유일한 operation ID로 멱등이고 duplicate를 destination이 거부한다면 안전한 재시도 근거가 생긴다. 이를 실제 source 보장으로 검증한다.

## 19. 완전 풀이 6: Overwrite 충돌

**문제.** 두 writer가 같은 path에 “삭제 후 쓰기” overwrite를 동시에 수행하면?

**풀이.** A가 기존 file을 지운 뒤 B도 빈 경로를 보고 쓰고, A와 B task가 섞여 file을 만들 수 있다. 늦은 삭제가 다른 writer의 새 file까지 없앨 수도 있다. 독자는 빈 상태나 혼합 상태를 본다.

**조건 변화.** Table metadata의 compare-and-swap commit과 conflict validation을 쓰면 한 writer가 먼저 성공한 뒤 다른 writer는 base 변화로 실패하거나 재검토한다. 어떤 충돌을 검출하는지는 isolation 설정에 따른다.

## 20. 완전 풀이 7: repartition과 partitionBy

**문제.** repartition(2).write.partitionBy("date")이면 file 두 개인가?

**풀이.** 아니다. 실행 partition 두 개가 여러 date를 포함하면 task마다 date별 writer를 열어 두 개보다 많은 file을 만들 수 있다. Empty task는 만들지 않을 수 있고 file size 제한은 추가 file을 만든다.

**조건 변화.** Date가 하나이고 두 task가 모두 data를 가지며 writer가 task당 file 하나만 만든다는 추가 조건에서 두 개가 나올 수 있지만 보편 계약은 아니다.

## 21. 완전 풀이 8: Table read와 glob

**문제.** Iceberg table의 data directory를 Parquet glob으로 읽으면 table query와 같은가?

**풀이.** 같지 않을 수 있다. Glob은 path에 보이는 Parquet file을 읽지만 table query는 current snapshot과 manifest를 따라 유효 data file을 고르고 관련 delete 정보를 적용한다. 과거 snapshot file과 실패 write orphan이 directory에 남을 수 있다.

**조건 변화.** 순수 Parquet dataset이고 commit protocol이 유효 file만 path에 남긴다는 별도 계약이 있으면 glob이 그 dataset 인터페이스일 수 있다. Table format에는 catalog/table 이름을 사용한다.

## 22. 읽기·쓰기 검증표

| 단계 | 확인할 객체와 수치 |
|---|---|
| Discovery | file 목록 또는 snapshot ID, 총 file 수 |
| Schema | 열 형·null·timezone·오류 정책 |
| Planning | read partition 수, file/split 배치 |
| Pushdown | ReadSchema, PartitionFilters, PushedFilters |
| Runtime read | bytes, rows, skipped 후보, task max |
| Task write | attempt ID, output file, row/byte, footer 완료 |
| Commit | 채택된 task message, manifest/snapshot, 성공 ID |
| Failure | 남은 임시·orphan, unknown commit 조회 |
| Overwrite | 교체 범위, base version, 동시 writer 충돌 |
| Publish | 독자가 보는 이전/새 상태 경계 |

읽기 성능을 file 수 하나로, 쓰기 성공을 file 존재 하나로 설명하면 실제 경계를 놓친다. Footer와 row group은 file 내부 후보를 줄이고, read partition은 task 실행을 나누며, commit은 여러 task output 가운데 유효 집합을 공개한다. Object store와 table format에서는 rename 가정 대신 connector와 metadata protocol의 지원 조건으로 원자성을 판단한다.

## 공식 자료

[SQL data sources](https://spark.apache.org/docs/4.2.0/sql-data-sources.html), [Parquet](https://spark.apache.org/docs/4.2.0/sql-data-sources-parquet.html), [CSV](https://spark.apache.org/docs/4.2.0/sql-data-sources-csv.html), [JDBC](https://spark.apache.org/docs/4.2.0/sql-data-sources-jdbc.html), [Spark cloud integration](https://spark.apache.org/docs/4.2.0/cloud-integration.html), [Iceberg Spark writes](https://iceberg.apache.org/docs/latest/spark-writes/)를 사용한 장이다.

[다음: 08. Structured Streaming](08-structured-streaming.md)
