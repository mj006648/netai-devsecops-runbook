# 13. 버전과 마이그레이션: 엔진 하나가 아니라 호환성 행렬을 옮기는 일

[이전: 연구 워크플로](12-research-workflows.md) · [목차](README.md) · [다음: 문제·해설·개념 연결](14-exercises-and-glossary.md)

Spark를 업그레이드할 때 spark.version 숫자만 바꾸면 된다고 생각하기 쉽다. 실제 Application은 Spark Engine, Python Client, JDK, Scala Binary ABI, Connector Runtime JAR, Catalog, Storage Driver, Table Format Version, Streaming Checkpoint가 연결된 시스템이다. 한 축이 컴파일되거나 시작됐다는 사실은 다른 축의 호환성을 보장하지 않는다.

이 장의 기준일은 2026-10-11이다. Spark 4.2.0을 현재 Engine으로 설명하지만 Apache Iceberg 1.12.0의 공식 Release Page가 나열하는 Spark Runtime은 3.5, 4.0, 4.1이다. Spark 4.1용 Runtime JAR를 4.2에서 공식 지원된다고 확대 해석하지 않는다.

## 1. Version이라는 말이 가리키는 아홉 객체

**Spark Engine Version**은 Driver와 Executor에서 계획, Scheduler, SQL 연산자, Streaming Runtime을 실행하는 Spark 배포판의 버전이다. Application 전체 실행 동안 사용되며 운영자가 Cluster Image나 배포 Package로 관리한다.

**Python Version**은 PySpark Client 코드와 Python Worker가 실행되는 언어 Runtime 버전이다. Driver Python과 Executor Python이 다르면 직렬화 또는 Library Import 문제가 생길 수 있다. 운영자는 Image와 PYSPARK_PYTHON 같은 실행 설정으로 관리한다.

**JDK, Java Development Kit**는 JVM과 Java Class Library를 제공한다. Spark Driver와 Executor JVM이 시작될 때 필요하고 프로세스가 끝날 때까지 사용된다. Spark가 지원하는 JDK 범위 안에서도 Connector가 더 좁은 범위를 요구할 수 있다.

**Scala Binary ABI**의 ABI는 Application Binary Interface, 즉 이미 Compile된 Class가 Method 이름, 인자, Type 표현을 서로 맞춰 호출하는 약속이다. Artifact 이름의 _2.13은 Scala 2.13 Binary 계열용이라는 뜻이다. Source Code가 비슷해 보여도 2.12와 2.13용 JAR를 섞으면 Class 또는 Method를 찾지 못할 수 있다.

**Runtime JAR**는 특정 Spark 계열과 Scala ABI를 대상으로 빌드한 Connector 실행 코드 묶음이다. Driver와 Executor Classpath에 들어가 Application 동안 Catalog, Scan, Write, Commit 기능을 연결한다.

**Table Format Version**은 Iceberg Metadata와 Data/Delete File 의미를 Reader와 Writer가 해석하는 규격 번호다. Product Release 1.12.0과 다른 숫자 축이다. Table이 Format v3이라고 Iceberg Library Version이 3이라는 뜻이 아니다.

**Catalog**는 Table 이름을 현재 Metadata 위치와 연결하고 Commit의 경쟁을 조정하는 서비스 또는 구현이다. REST Catalog, Hive Metastore 기반, Hadoop Catalog 등 구현마다 인증과 원자적 Pointer 갱신 조건이 다르다.

**Storage Driver와 Bundle**은 S3, GCS, Azure, HDFS 같은 저장소에 실제로 연결하는 Client Library다. Credential Provider, Endpoint, TLS, Multipart Upload와 SDK Version을 관리한다. Iceberg Runtime JAR만 추가했다고 Cloud Storage 인증이 자동 완성되는 것은 아니다.

**Streaming Checkpoint**는 Source Offset, Commit Log, Query Metadata, Stateful Operator State를 지속 경로에 저장한 디렉터리다. 실행 중 Driver가 갱신하고 재시작한 Query가 읽는다. 코드보다 오래 살아남을 수 있으므로 Upgrade의 상태 객체로 취급한다.

## 2. 좌표 하나를 왼쪽부터 읽는다

다음 Artifact 좌표를 보자.

~~~text
org.apache.iceberg:
iceberg-spark-runtime-4.0_2.13:
1.12.0
~~~

각 부분의 뜻은 다음과 같다.

| 부분 | 의미 | 의미하지 않는 것 |
|---|---|---|
| iceberg-spark-runtime | Spark용 Iceberg Runtime 묶음 | Spark 자체 Engine |
| 4.0 | 대상으로 빌드된 Spark Integration 계열 | 4.x 전체 자동 호환 |
| _2.13 | Scala Binary ABI 계열 | Java 13 |
| 1.12.0 | Iceberg Product Release | Table Format v1.12 |

Spark 4.2 Application에 4.1용 Artifact를 넣어 Class Loading이 우연히 성공해도 공식 4.2 Integration 지원이 되는 것은 아니다. Scan 한 번 성공한 사실도 Write, Delete, Streaming, Catalog Commit의 전체 계약을 증명하지 않는다.

Apache Iceberg는 Runtime JAR와 Storage별 Bundle 외에 iceberg-core, iceberg-parquet 같은 내부 Module을 Uber JAR로 중복 포함하면 Dependency Conflict를 만들 수 있다고 공식 Multi-engine 문서에서 경고한다. Classpath에 같은 Class의 다른 Version이 둘 있으면 어떤 것이 먼저 Load되는지에 따라 환경별 오류가 달라질 수 있다.

## 3. 현재 공식 조합과 빈칸을 읽는 법

Apache Iceberg 1.12.0은 2026-09-29 발표되었다. 공식 Release Page는 다음 Spark Runtime을 나열한다.

| Spark Integration | Scala ABI | Iceberg 1.12.0 Runtime |
|---|---|---|
| 3.5 | 2.12, 2.13 | 제공 |
| 4.0 | 2.13 | 제공 |
| 4.1 | 2.13 | 제공 |
| 4.2 | 해당 Page에 없음 | 공식 Artifact로 단정하지 않음 |

표의 빈칸은 "절대 실행 불가능"을 수학적으로 증명하는 값이 아니다. 공식 Release가 해당 조합의 Runtime을 제공하지 않는다는 뜻이다. 운영 조합을 선택할 때는 지원되는 Engine으로 맞추거나, 4.2 Integration이 공식 Release에 추가될 때까지 기다리거나, Source Build와 자체 검증을 별도 책임으로 수행해야 한다. 4.1 JAR를 4.2에 넣는 것은 지원표 확인을 대체하지 않는다.

이 책의 Local 기준선인 PySpark 4.0.4, Java 21, Scala 2.13, Iceberg 1.12.0은 공식 Runtime 축이 존재한다. 그래도 Catalog, Storage Bundle, Python Package, Vendor Image를 포함한 실제 조합 검증은 필요하다.

## 4. Product Release와 Table Format을 분리한다

Iceberg Product 1.12.0은 Software Release다. Table Format v1, v2, v3는 Table Metadata와 Reader/Writer 행위의 규격이다.

| Format | 채택 상태 | 핵심 의미 |
|---|---|---|
| v1 | 완료·채택 | Immutable Data File 기반 분석 테이블 |
| v2 | 완료·채택 | Position/Equality Delete File을 포함한 Row-level Delete |
| v3 | 완료·채택 | Row Lineage, Binary Deletion Vector, 확장 Type 등 |
| v4 | 개발 중, 공식 채택 전 | Metadata 표현 변경 등을 논의·정의 중 |

현재 Spec Page는 v1·v2·v3를 Complete and Adopted로, v4를 Active Development이며 Formally Adopted되지 않았다고 명시한다. 문서에 v4 항목이 있다는 사실을 Production 채택 완료와 혼동하지 않는다.

Format Upgrade는 Metadata의 format-version을 올리는 쓰기다. 이전 Reader가 새 기능을 이해하지 못할 수 있으므로 모든 Engine의 Read/Write 지원을 확인한 뒤 활성화한다. 새 Writer가 v3 Deletion Vector를 썼는데 Rollback할 이전 Engine이 v3를 읽지 못하면 Package만 내리는 복구가 실패한다.

## 5. Engine·Python·JDK·Scala의 기본선

원문의 기준 표를 유지하되 실제 배포판 조건을 다시 확인해야 한다.

| Spark 계열 | JDK 기준 | Scala Binary | Python 기준 |
|---|---|---|---|
| 3.5 | 8·11·17 계열의 공식 조건 확인 | 2.12, 일부 배포 2.13 | 3.8 이상 계열 |
| 4.0 | 17·21 | 2.13 | 3.9 이상 |
| 4.1 | 17·21 | 2.13 | 3.10 이상 |
| 4.2 | 17·21·25 | 2.13 | 3.10 이상 |

Spark 4.0은 Java 8/11, Scala 2.12, Python 3.8 지원 제거가 포함된 큰 경계다. Python Script가 문법상 실행된다는 사실만 보면 부족하다. Pandas, PyArrow, NumPy, ML Library와 Python UDF가 새 Python ABI와 맞는지도 확인한다.

Driver Python 3.11과 Executor Python 3.10처럼 Minor Version이 다르면 CloudPickle, 사용자 Dependency, Native Extension에서 차이가 생길 수 있다. Driver와 Executor Image Digest를 Run Record에 남긴다.

## 6. SQL 의미가 바뀌면 성공 여부도 달라진다

Migration은 API 이름 존재 여부만의 문제가 아니다. ANSI Mode, Cast, Timestamp, Interval, Collation, NULL, Decimal Overflow처럼 같은 SQL의 결과 또는 오류가 달라질 수 있다.

원문 세 값은 다음과 같다.

~~~text
"12"
"12.5"
"unknown"
~~~

BIGINT로 변환할 때 이전 환경이 실패 값을 NULL로 만들었다면 결과는 12, NULL, NULL일 수 있다. 새 ANSI 정책이 Invalid Cast에서 예외를 내면 첫 실패 지점에서 Query 자체가 중단된다. try_cast를 명시하면 실패를 NULL로 선택할 수 있지만, failure_count=2와 원문을 기록해야 한다.

**Collation**은 문자열의 비교와 정렬 규칙이다. 대소문자, Accent, Unicode 동등성 규칙이 바뀌면 Group Key와 Join 결과가 달라질 수 있다. **Timezone**은 문자열을 Timestamp로 해석하고 날짜 경계를 자르는 기준이다. UTC 자정과 Asia/Seoul 자정은 다른 행을 같은 날짜로 묶을 수 있다.

Migration 검증은 전체 Row Count만 비교하지 않는다.

- 열별 NULL Count
- Parse Failure Count
- Key별 Aggregate
- Min/Max와 Decimal Scale
- 정렬과 Tie-breaker가 있는 대표 행
- 결과 Checksum
- 오류 Class와 실패 시점

## 7. Classic과 Connect의 경계

**Classic PySpark**는 Python Driver가 Py4J를 통해 Driver JVM과 가까이 상호작용하는 전통 경로다. **Spark Connect**는 Client가 논리 계획을 Protocol로 Server에 보내는 분리 모델이다. Client Process와 Server Driver의 위치와 수명이 다르다.

DataFrame API 이름이 같아도 df._jdf 같은 Private JVM Handle, SparkContext, RDD 기반 코드가 Connect에서 그대로 동작한다고 가정하지 않는다. API 문서의 Supports Spark Connect 표시, Client와 Server Version Compatibility, 사용자 Library의 실행 위치를 확인한다.

Connect Migration에서 Python Client만 Upgrade하고 Server를 그대로 두면 새 Client API가 Server에 없는 Plan Node를 보낼 수 있다. 반대로 Server만 Upgrade하면 기존 Client Protocol과 동작 차이를 확인해야 한다.

## 8. Catalog와 Storage까지 포함한 읽기 흐름

Spark SQL에서 SELECT가 성공하려면 다음 연결이 모두 성립해야 한다.

~~~mermaid
flowchart LR
    A["Spark SQL 계획"] --> B["Iceberg Runtime JAR"]
    B --> C["Catalog: 이름→Metadata 위치"]
    C --> D["Table Metadata와 Snapshot"]
    D --> E["Storage Driver·Credential"]
    E --> F["Manifest와 Data/Delete File"]
~~~

Catalog Plugin Class가 Load되어도 인증 Token Scope가 부족하면 Table을 찾지 못한다. Table Metadata를 읽어도 S3 Credential이 Data File Prefix를 허용하지 않으면 Scan Task가 Executor에서 실패한다. Driver만 Credential이 있고 Executor에는 없다면 Planning은 성공하고 실제 Read에서 실패할 수 있다.

Storage SDK Upgrade는 Endpoint, Retry, Checksum, TLS와 Credential Provider Chain을 바꿀 수 있다. Migration Test에는 목록 조회뿐 아니라 실제 Data File Read, Multipart Write, Commit 충돌, 실패 후 Retry를 포함한다.

## 9. Batch Migration의 단계별 기준선

현재 조합을 A, 목표 조합을 B라고 하자.

### 단계 1: Inventory 동결

Engine, Python, JDK, Scala ABI, 모든 JAR 좌표와 Hash, Catalog Type, Storage Bundle, Table UUID와 Format Version, Spark Config, Image Digest를 기록한다.

### 단계 2: 동일 입력 고정

Iceberg Snapshot ID 또는 Immutable Input 경로를 고정한다. Snapshot이 Test 기간 동안 만료되지 않도록 보존한다. 외부 Dimension Table도 같은 상태로 고정한다.

### 단계 3: 결과 의미 비교

A와 B에서 Schema, Row Count, NULL, 오류 행, Key Aggregate, Checksum을 비교한다. 12/12.5/unknown 같은 경계 입력을 별도 Fixture로 둔다.

### 단계 4: 계획과 자원 비교

Analyzed Logical Plan, 최종 AQE Physical Plan, File/Byte Scan, Join Strategy, Partition 수, Shuffle, Spill, Task Duration, Peak Memory를 비교한다. Plan이 달라도 결과와 성능이 허용 기준 안이면 성공할 수 있다. Plan 문자열 동일 자체를 목표로 하지 않는다.

### 단계 5: Write와 Commit 검증

격리 Table에서 Append, Overwrite, Merge/Delete가 실제 지원 경로로 Commit되는지 확인한다. 동시에 두 Writer를 실행해 Conflict 처리와 재시도를 관찰한다. Production Table에 바로 새 Format Feature를 쓰지 않는다.

### 단계 6: 장애와 Rollback Rehearsal

Task Failure, Executor Loss, Driver 종료, Commit 응답 유실을 시험한다. 새 조합으로 쓴 상태를 이전 조합이 읽을 수 있는지 확인한 뒤 전환한다.

## 10. Stateful Streaming Checkpoint의 내부 상태

**Stateful Operator**는 이전 Micro-batch의 값을 기억해야 다음 결과를 계산하는 연산이다. Window Aggregate, Streaming Deduplication, Stream-stream Join이 예다. 기억하는 Key와 Value의 자료형을 **State Schema**라고 한다.

Checkpoint에는 개념적으로 다음이 있다.

| 상태 | 역할 | 바뀌면 생길 수 있는 문제 |
|---|---|---|
| Query Metadata와 ID | 같은 Query의 연속성 식별 | Metadata 유실 시 중복 또는 시작 실패 |
| Offset Log | Source에서 어디까지 계획했는지 | 재독 또는 누락 |
| Commit Log | 어느 Batch 효과가 완료됐는지 | Sink 중복 판단 변화 |
| State Store | Key별 누적 상태 | Schema/Partition 불일치 |
| Operator ID와 Plan 관계 | 어떤 상태가 어느 연산 것인지 연결 | 연산 순서 변경 시 잘못된 상태 연결 |

Code가 Compile되어도 기존 Checkpoint를 새 Runtime이 읽을 수 없으면 Upgrade는 실패한다. Grouping Key, State Value Type, Stateful Operator 수와 순서, Shuffle Partition 수, Watermark 의미를 함부로 바꾸지 않는다.

Spark 4.2 Streaming Migration Guide는 Checkpoint Metadata File이 없는데 Offset 또는 Commit Log가 남은 경우 재시작을 실패시키는 검증을 설명한다. 이전처럼 새 Query ID를 조용히 만들면 Exactly-once Sink에서 중복 위험이 있기 때문이다. 설정으로 이전 동작을 되돌릴 수 있다는 사실은 위험이 사라진다는 뜻이 아니다.

## 11. Streaming 전환의 Blue/Green Rehearsal

Production Checkpoint를 복사해 두 Query가 동시에 같은 Sink에 쓰게 하면 중복과 경쟁을 만들 수 있다. 격리된 Source Replay와 별도 Sink Namespace를 사용한다.

1. 기존 Query A를 계속 운영하며 Input과 Output 기준을 기록한다.
2. 보존된 Source Range를 Test 환경에 재생한다.
3. Checkpoint 복사본은 Storage 수준 일관성과 권한을 확인해 격리 경로에 둔다.
4. 새 Runtime B가 Checkpoint를 읽고 다음 Batch로 진행하는지 본다.
5. State Row 수, Watermark, Offset, Output Checksum을 A와 비교한다.
6. 장애 후 같은 Checkpoint로 재시작해 중복과 누락을 검사한다.
7. Cutover 시각과 마지막 A Offset, 첫 B Offset을 기록한다.
8. Sink가 두 Query의 동시 Writer를 허용하지 않도록 Fence를 둔다.

**Fence**는 이전 Writer가 Cutover 뒤 Commit하지 못하게 막는 제어다. Application을 종료했다고 생각했지만 Network Partition 때문에 늦은 Writer가 살아 있을 수 있으므로 Catalog Lock, Lease, Writer Epoch 같은 실제 Sink 계약을 사용한다.

## 12. 새 Checkpoint가 필요한 경우

State Schema가 호환되지 않거나 Migration Guide가 기존 Checkpoint 재사용을 허용하지 않으면 새 Checkpoint로 시작해야 할 수 있다. 이것은 단순 디렉터리 이름 변경이 아니다.

새 시작 위치를 latest로 하면 과거 미처리 행을 놓칠 수 있다. earliest로 하면 기존 Sink 결과와 중복될 수 있다. 안전한 경로는 다음 중 시스템 계약에 맞게 고른다.

- 과거 Source를 새 격리 Sink로 전부 Replay한 뒤 검증하고 교체한다.
- 특정 Cutover Offset을 정해 이전 Query가 그 직전까지, 새 Query가 그 이후부터 처리한다.
- Sink Key와 Run ID를 이용해 Upsert 또는 Deduplicate한다.
- 전체 State를 Batch로 재구축하고 그 Snapshot 뒤부터 Streaming을 시작한다.

각 방법은 Source Retention과 Sink Idempotency를 요구한다. Checkpoint 삭제는 복구가 아니라 상태 연속성을 포기하는 선택이다.

## 13. Rollback은 쓰기 전부터 설계한다

Rollback 가능성을 지키려면 새 Writer가 이전 Reader가 모르는 상태를 만들지 않아야 한다. 다음을 사전에 금지하거나 격리한다.

- 이전 Engine이 읽지 못하는 Iceberg Format Upgrade
- 새 Type과 Collation으로 쓴 Schema
- 이전 Connector가 이해하지 못하는 Delete 표현
- 이전 Runtime이 읽지 못하는 Streaming State
- 되돌릴 수 없는 Catalog Migration
- Storage Layout이나 Encryption Key의 일괄 변경

전환 뒤 오류가 나면 실행 Binary만 A로 내리지 않는다. 마지막 공통 호환 Snapshot, Source Offset, Sink Commit, Checkpoint Backup, Catalog Pointer를 확인한다. B가 일부 Commit했다면 A가 그 상태를 읽을 수 있는지 검증한다.

Rollback Decision Tree는 다음과 같다.

1. B가 Write 전에 실패했는가? 입력과 외부 부작용을 확인하고 A 재실행을 고려한다.
2. B가 Table Snapshot을 Commit했는가? A Reader가 그 Snapshot과 Format Feature를 읽는지 본다.
3. B가 Streaming Sink에 Commit했는가? 마지막 Batch ID와 Offset을 기준으로 A의 재시작 위치를 정한다.
4. B가 State Schema를 변경했는가? A용 Checkpoint Backup 또는 State Rebuild 경로를 쓴다.
5. Catalog나 Storage Credential을 바꿨는가? Pointer와 권한 Rollback을 별도로 수행한다.

## 14. Migration 완료 조건

다음이 모두 충족되어야 완료로 판단한다.

- 지원 Matrix에 실제 Engine·Scala Runtime Artifact가 있다.
- Python, JDK, Native Dependency가 Driver와 Executor에서 같다.
- 동일 Input에서 Schema와 결과 값이 허용 기준 안에서 일치한다.
- 오류 정책과 Timezone, ANSI, Collation 차이가 기록됐다.
- Scan, Write, Delete, Commit Conflict가 격리 환경에서 통과했다.
- Stateful Query가 Checkpoint 재시작 또는 새 시작 계획을 통과했다.
- Rollback Rehearsal에서 이전 조합의 읽기와 Source/Sink 경계가 확인됐다.
- Runbook과 Artifact Lockfile, Image Digest가 저장됐다.

Dependency Resolver가 성공하고 Application이 시작된 것만으로 이 조건을 충족하지 않는다.

## 15. 종합 문제와 완전 풀이

### 문제 1
Iceberg 1.12.0의 4.1_2.13 Runtime JAR를 Spark 4.2에 넣으면 공식 지원인가?

**풀이:** 아니다. 4.1은 Integration Target, 2.13은 Scala ABI다. Release Page에 4.2 Artifact가 없으므로 4.2 공식 지원으로 단정하지 않는다.

### 문제 2
Table Format v3과 Iceberg 1.12.0은 같은 버전 번호 축인가?

**풀이:** 아니다. v3은 Table Metadata 규격이고 1.12.0은 Software Release다. Product가 여러 Format을 읽고 쓸 수 있다.

### 문제 3
Spark 4.2에서 v4 Spec 문서가 보이면 Production Table을 v4로 올려도 되는가?

**풀이:** 현재 공식 Spec은 v4를 개발 중이며 정식 채택 전이라고 명시한다. Engine과 Connector 지원, Rollback Reader를 확인하기 전 활성화하지 않는다.

### 문제 4
12, 12.5, unknown을 BIGINT로 바꾼 뒤 Row Count가 같으면 성공인가?

**풀이:** 부족하다. 값과 오류 정책이 달라질 수 있다. try_cast라면 NULL 2개와 failure_count=2를 확인하고 ANSI Cast라면 예외 발생 여부를 비교한다.

### 문제 5
Driver가 Catalog와 S3 Metadata를 읽었으니 Executor도 Data File을 읽을 수 있는가?

**풀이:** 보장되지 않는다. Executor Image의 Storage SDK, Credential과 Network 권한을 따로 확인한다.

### 문제 6
Checkpoint를 지우고 earliest로 시작하면 동일 Query Rollback인가?

**풀이:** 아니다. Source를 재독하는 새 시작이다. 기존 Sink 결과와 중복, State 재구축, Query ID와 Cutover Offset을 설계해야 한다.

### 문제 7
B Runtime이 Snapshot을 하나 Commit한 뒤 A로 Package만 내리면 되는가?

**풀이:** A가 새 Format Feature, Schema Type, Delete 표현을 읽는지 먼저 확인한다. 읽지 못하면 마지막 공통 호환 상태 또는 별도 변환이 필요하다.

### 문제 8
Logical Plan 문자열이 달라졌으므로 Migration 실패인가?

**풀이:** 반드시 그렇지 않다. Optimizer 변화로 Plan은 달라질 수 있다. 결과 의미, 오류, 성능, 자원, 복구 기준을 만족하는지 판단한다.

## 16. 공식 근거

Iceberg 1.12.0 Release 날짜와 Spark Runtime 목록은 [Apache Iceberg Releases](https://iceberg.apache.org/releases/)를 기준으로 했다. Artifact와 Classpath 원칙은 [Multi-engine Support](https://iceberg.apache.org/multi-engine-support/), Format v1·v2·v3 채택과 v4 개발 상태는 [Iceberg Table Spec](https://iceberg.apache.org/spec/)에 근거한다.

Spark Engine 변화는 [Spark 4.0 Release](https://spark.apache.org/releases/spark-release-4-0-0.html), [4.1 Release](https://spark.apache.org/releases/spark-release-4-1-0.html), [4.2 Release](https://spark.apache.org/releases/spark-release-4-2-0.html)를 구분해 사용했다. Stateful Checkpoint 경계는 [Spark 4.2 Structured Streaming Migration Guide](https://spark.apache.org/docs/4.2.0/streaming/ss-migration-guide.html)를 따른다.

[이전: 연구 워크플로](12-research-workflows.md) · [목차](README.md) · [다음: 문제·해설·개념 연결](14-exercises-and-glossary.md)
