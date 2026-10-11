# 14. 종합 문제와 개념 연결: 파일 한 줄에서 Commit과 복구까지

[이전: 버전과 마이그레이션](13-versions-and-migration.md) · [목차](README.md)

이 장은 용어를 한 줄씩 외우는 사전이 아니다. 같은 실행에서 Source File, Input Partition, Task, Stage, Executor, Shuffle Block, Output File, Table Snapshot이 어디에 존재하고 누가 관리하며 언제 사라지는지를 연결한다. 이어지는 15개 문제는 답 한 줄로 끝내지 않고 입력 상태, 계산 과정, 실패 반례와 실제 확인 대상을 모두 풀이한다.

## 1. 하나의 Spark Application 안에 있는 실행 객체

**Application**은 사용자가 제출한 Spark 프로그램 한 번의 전체 실행이다. Driver가 시작될 때 만들어지고 Driver가 정상 종료하거나 실패할 때 끝난다. Cluster Manager는 Application에 CPU와 Memory 자원을 배정하지만 SQL의 의미를 결정하지 않는다.

**Driver**는 사용자 코드와 SparkSession, 논리·물리 계획, Job·Stage·Task 상태를 가진 중심 Process다. **Executor**는 Cluster Worker 또는 Pod에서 Task를 실행하고 Cache와 Shuffle Block을 보관하는 Process다. Driver가 "무엇을 어떤 순서로 계산할지" 관리한다면 Executor는 할당된 Partition의 행을 실제로 읽고 변환한다.

**Job**은 Action이 결과를 요구할 때 만들어지는 실행 묶음이다. show 한 번이 언제나 Job 하나라는 계약은 아니다. Broadcast 준비나 내부 실행 때문에 여러 Job이 보일 수 있다. **Stage**는 Shuffle 같은 데이터 재분배 경계 사이의 Task 집합이다. **Task**는 Stage의 Partition 하나를 처리하는 실행 단위다. 동일 논리 Task가 실패하거나 Speculation으로 복제되면 여러 Attempt가 생길 수 있다.

이 관계를 객체 수명으로 그리면 다음과 같다.

~~~mermaid
flowchart TD
    A["Application: Driver 수명"] --> J1["Job 1: count Action"]
    A --> J2["Job 2: write Action"]
    J2 --> S0["Stage 0: scan/filter/partial"]
    J2 --> S1["Stage 1: shuffle 뒤 aggregate"]
    S0 --> T0["Task P0 attempt 0"]
    S0 --> T1["Task P1 attempt 0"]
    S0 --> T2["Task P2 attempt 0"]
    T2 -. 실패 .-> T2R["Task P2 attempt 1"]
~~~

Task와 Thread, Core도 같은 객체가 아니다. Task는 논리 실행 단위이고 Thread가 Task 코드를 실행하며 Core는 그 Thread에 CPU 시간을 제공한다.

## 2. 데이터가 존재하는 네 장소

**Source File**은 실행 전 Storage에 있는 입력 Byte다. Parquet라면 Row Group, Column Chunk와 Footer Metadata를 가진다. Spark가 File Listing과 Split 계획을 거쳐 **Input Partition**을 만든다. File 하나가 Partition 하나라는 고정 관계는 없다.

**Shuffle Block**은 앞 Stage Task가 만든 중간 결과 Byte다. 같은 Key를 모으기 위해 뒤 Stage가 Network로 가져간다. Executor Local Disk에만 있던 Block은 Executor Loss로 사라질 수 있으며 Lineage가 있으면 이전 Task를 다시 실행해 만든다.

**Cache Block**은 반복 계산을 줄이려고 Executor Memory나 Disk에 임시 보관한 Partition 결과다. DataFrame 변수를 Python 변수에 넣는 것만으로 Cache되지 않는다. cache 또는 persist 표시 뒤 Action이 계산해야 실제 Block이 생긴다. Eviction이나 Executor Loss 뒤에는 다시 계산될 수 있다.

**Output File**은 Writer Task가 Sink에 만든 Data File이다. File 존재는 전체 Job Commit 또는 Iceberg Snapshot Commit과 다르다. Task File이 모두 성공해도 Driver가 최종 Commit 전에 실패할 수 있다.

## 3. 계획 객체와 저장 상태를 연결한다

**DataFrame**은 이름과 Type이 있는 Column 연산의 분산 계획을 가리킨다. Driver의 DataFrame 변수 안에 모든 행이 들어 있는 것이 아니다. **Logical Plan**은 무엇을 계산할지를 Filter, Join, Aggregate 같은 관계 연산으로 표현한다. **Physical Plan**은 Scan 구현, Hash Aggregate, Sort Merge Join, Exchange처럼 어떻게 실행할지를 정한다.

**Catalyst**는 Spark SQL의 Expression과 Plan을 분석하고 변환하는 기반이다. Schema와 내장 함수 의미가 보이므로 Column Pruning, Predicate Pushdown, 부분 집계 같은 선택을 할 수 있다. Python UDF 내부 의미는 같은 수준으로 보이지 않을 수 있다.

**DAG**는 방향이 있고 순환하지 않는 계산 의존 Graph다. **Lineage**는 결과 Partition이 어떤 입력과 변환에서 왔는지 나타내는 재계산 경로다. DAG가 계획의 전체 의존 관계라면 Lineage는 잃어버린 조각을 다시 만드는 데 쓰이는 계보라는 관점이 중요하다.

**Checkpoint**는 특히 Streaming에서 Source Offset, Commit Log, State를 지속 Storage에 기록한 복구 상태다. Lineage를 짧게 자르는 Batch Checkpoint와 Stateful Streaming Checkpoint는 맥락과 내용이 다르다. 이름만 같다고 동일 Directory 의미로 취급하지 않는다.

## 4. Structured Streaming 객체의 연결

**Micro-batch**는 일정 구간의 새 입력을 작은 Batch Job처럼 반복 처리하는 방식이다. **Event Time**은 사건이 원천에서 발생한 시각이고 **Processing Time**은 Spark가 처리한 시각이다. Network 지연 때문에 Event Time이 오래된 행이 나중에 도착할 수 있다.

**Watermark**는 Event Time 진행과 허용 지연을 바탕으로 오래된 State를 언제 정리할 수 있는지 판단하는 경계다. "이 시각보다 늦은 행은 항상 버린다"는 단일 문장으로 모든 Operator 동작을 설명할 수 없다. Output Mode와 Window, Join, Deduplication 연산의 조건을 함께 봐야 한다.

**State**는 다음 Micro-batch 계산에 필요한 누적 값이다. Window별 Count, 이미 본 Event ID, Stream-stream Join의 아직 짝을 기다리는 행이 예다. Executor Memory만의 임시 Cache와 달리 재시작 복구를 위해 State Store와 Checkpoint에 연결된다.

**Exactly-once**라는 표현은 범위를 붙여야 한다. Source Offset과 Sink Commit의 조합이 한 Query의 처리 효과를 중복시키지 않더라도, 같은 업무 event_id가 서로 다른 Offset으로 두 번 들어오면 업무 중복은 남는다.

## 5. Iceberg 객체와 Spark 실행을 연결한다

**Table Format**은 Data File 집합을 Table 상태로 관리하는 Metadata 규칙이다. Iceberg에서 **Catalog**는 Table 이름과 현재 Metadata 위치를 연결하고 Commit 경쟁을 조정한다. **Snapshot**은 성공한 Commit 뒤 유효한 File과 상태를 가리킨다.

**COW, Copy-on-Write**는 Row 변경을 반영한 새 Data File을 쓰는 방식이고 **MOR, Merge-on-Read**는 기존 Data File과 Delete 정보를 읽을 때 합칠 수 있는 방식이다. SQL DELETE 조건이 어떤 물리 표현을 만드는지는 Engine, Table Property, Format Version과 지원 경로에 달려 있다. 사용자가 equality delete라는 단어를 SQL에 쓰지 않았다고 Engine이 임의로 업무 의미를 추측하는 것은 아니다.

Iceberg Format v1·v2·v3는 Table 규격이고 Iceberg 1.12.0은 Software Release다. v4는 현재 개발 중이며 공식 채택 전이다. Spark 4.2 Engine과 Iceberg 4.1 Runtime JAR 숫자도 서로 다른 축이다.

## 6. 종합 사례의 모든 행

Source File 세 개가 다음 Input Partition P0~P2로 계획되었다고 하자.

| Partition | 입력 행 |
|---|---|
| P0 | KR 10, US 20, KR 30 |
| P1 | JP 40, KR 50, US 60 |
| P2 | KR 70, JP 80, US 90 |

연산은 amount >= 20 Filter, region별 Sum, 결과 Write다. P0에서는 KR10이 제거되어 KR30과 US20이 남는다. P1과 P2의 모든 행은 남는다.

Shuffle 전 부분 상태를 Key별로 합치면 다음과 같다.

| Partition | 부분 상태 |
|---|---|
| P0 | KR=30, US=20 |
| P1 | JP=40, KR=50, US=60 |
| P2 | KR=70, JP=80, US=90 |

Exchange 뒤 같은 Key의 상태를 합치면 KR=30+50+70=150, US=20+60+90=170, JP=40+80=120이다. 최종 행은 세 개다.

Writer가 이 세 행을 F0과 F1 두 File에 나누어 쓸 수 있다. File 두 개는 Executor 두 개라는 뜻이 아니다. 하나의 Executor가 순서대로 두 Writer Task를 실행할 수도 있고 여러 Executor가 만든 결과가 Commit Protocol에서 두 File로 공개될 수도 있다.

P2 Shuffle Block이 Executor Loss로 사라지면 P2 Source가 남아 있을 때 P2의 이전 Stage Task를 새 Attempt로 다시 실행해 부분 상태를 만든다. Task 안에서 외부 결제 API를 호출했다면 그 API 효과까지 Spark Lineage가 되돌리지 않는다.

## 7. 문제 1 — 평균의 평균

Partition A에는 값 10 하나, B에는 값 20 세 개가 있다. 부분 평균의 평균과 전체 평균을 구하고 왜 다른지 설명하라.

**풀이:** A의 평균은 10, B의 평균은 20이므로 단순 평균은 (10+20)/2=15다. 그러나 실제 행은 10,20,20,20 네 개이므로 전체 평균은 70/4=17.5다. 단순 평균은 두 Partition에 같은 가중치를 줬지만 실제로 B에는 세 배의 행이 있다.

정확히 합치려면 A=(sum 10,count 1), B=(sum 60,count 3)을 보낸다. 최종 상태는 (sum 70,count 4)이고 70/4=17.5다. Partition별 평균만 남기면 원래 Count 정보를 잃어 일반적으로 복구할 수 없다.

## 8. 문제 2 — NULL과 0

온도 20, 22, NULL에 COUNT(*), COUNT(temperature), AVG(temperature)를 적용하고 NULL을 0으로 채운 뒤 평균 변화를 설명하라.

**풀이:** COUNT(*)는 행을 세므로 3이다. COUNT(temperature)는 NULL이 아닌 값만 세므로 2다. AVG도 NULL을 제외해 (20+22)/2=21이다. NULL을 0으로 채우면 알려지지 않은 값을 실제 0도로 바꾸므로 (20+22+0)/3=14다.

14는 계산 오류가 아니라 다른 데이터 의미의 결과다. 결측을 0으로 바꾸려면 센서 고장이 실제 0도를 뜻한다는 업무 근거가 있어야 한다. 품질 분석에서는 전체 행 3, 유효 측정 2, 결측 1을 함께 기록한다.

## 9. 문제 3 — 지연 실행과 물질화

clean=raw.filter(...), summary=clean.groupBy(...).agg(...)를 실행했다. 결과 File과 Cache가 이미 만들어졌는가?

**풀이:** 두 문장은 Transformation Plan을 Driver에 만든다. 일반적으로 전체 입력을 읽는 Job이나 Output File Write는 아직 시작되지 않는다. 결과를 실제 Byte로 만드는 것을 물질화라고 하며 count, collect, write 같은 Action이 필요하다.

cache를 호출했더라도 표시만 Lazy할 수 있다. 뒤 Action이 Partition을 계산하면서 Cache Block을 채운다. File Listing이나 Schema 추론 같은 Metadata 접근은 Action 전에도 생길 수 있으므로 "아무 I/O도 없다"로 과장하지 않는다.

## 10. 문제 4 — Task 동시성과 실행 차수

Executor 3개, 각 4 Core, Task당 CPU 1개, 다른 제한이 없을 때 120 Task의 최대 동시 실행 수와 최소 단순 차수는?

**풀이:** 총 Core는 3×4=12이므로 약 12 Task가 동시에 실행된다. 모든 Task 시간이 같고 Scheduling Overhead가 없으면 120/12=10차수다.

Task당 CPU 2개를 요청하면 동시성은 약 6이고 20차수가 된다. 실제로는 Memory, Locality, Dynamic Allocation, Skew, 실패 재시도가 있어 차수가 달라진다. Slot은 독립 Process가 아니라 이 동시성을 설명하는 편의적 표현이다.

## 11. 문제 5 — Action 하나와 Job 수

show 하나를 호출했으니 Spark UI에 Job이 반드시 하나여야 하는가?

**풀이:** 보장할 수 없다. show는 하나의 Action이지만 Broadcast 관계를 준비하거나 내부 Subquery를 계산하는 과정, AQE 경로 때문에 여러 Job이 보일 수 있다. 반대로 좁은 Transformation 여러 개는 하나의 Job과 Stage 안에서 Pipeline될 수 있다.

검증할 때 Action 수를 Job 수의 고정 공식으로 쓰지 않는다. Spark UI와 Event Log에서 Job이 어떤 SQL Execution과 Stage에 연결됐는지 확인한다.

## 12. 문제 6 — Join Cardinality

Events에는 S1 두 행, S2 한 행이 있고 Devices에는 S1 두 행, S2 한 행이 있다. device_id Inner Join의 행 수를 계산하고 품질 검사를 설계하라.

**풀이:** S1은 왼쪽 2×오른쪽 2=4행, S2는 1×1=1행이므로 총 5행이다. Join은 같은 Key의 가능한 행 조합을 만든다.

Devices가 장치당 한 행이어야 한다면 S1 중복은 기준 데이터 오류다. Join 전에 device_id별 Count가 1인지 검사하고, Join 뒤 Events의 고유 Event ID가 몇 번 나타났는지 확인한다. SQL 성공 여부는 업무 Cardinality가 맞다는 증거가 아니다.

## 13. 문제 7 — Repartition과 File 수

DataFrame을 repartition(4)하고 두 날짜 값으로 partitionBy("date")해 저장했다. File이 반드시 네 개인가?

**풀이:** 아니다. repartition(4)은 Write 앞 실행 Partition을 네 개로 재분배하는 Plan이다. partitionBy는 저장 경로를 날짜 값별 디렉터리 또는 Table Partition으로 나누는 규칙이다. 한 Task가 여러 날짜를 가지면 날짜별 File을 만들 수 있고, AQE와 Writer 정책도 File 수에 영향을 준다.

기존 원본 File도 repartition 호출만으로 바뀌지 않는다. Write Action과 Commit이 성공해야 새 File이 공개된다. 확인 항목은 실제 File 수, File별 Row와 Byte, Table Metadata다.

## 14. 문제 8 — Driver OOM

Executor Memory를 두 배로 늘렸지만 toPandas에서 Driver가 죽었다. 원인과 수정 방향은?

**풀이:** toPandas는 분산 결과를 Driver Process로 모아 단일 Pandas DataFrame을 만든다. Executor Memory 증가는 각 Task 계산 공간을 넓히지만 Driver가 전체 결과를 담는 요구를 없애지 않는다.

수정은 전체 결과를 분산 File로 쓰거나, 필요한 Aggregate만 가져오거나, 명시적 Limit와 표본을 사용하는 식으로 요구를 바꾸는 것이다. Driver Heap만 계속 키우면 Network 전송과 단일 Process 한계가 남는다.

## 15. 문제 9 — 평균이 숨기는 Skew

Partition 10개 중 9개가 10MiB, 하나가 910MiB다. 평균을 구하고 실행에 미치는 영향을 설명하라.

**풀이:** 합계는 9×10+910=1,000MiB, 평균은 100MiB다. 평균만 보면 균등한 100MiB 10개처럼 보이지만 실제 마지막 Task는 다른 Task보다 약 91배 큰 입력을 처리한다.

큰 Partition의 Task가 Stage 완료 시간을 지배하고 Memory Spill 또는 OOM을 일으킬 수 있다. Median, Max, p95 Task Duration과 Partition Byte를 보고, Key Skew라면 Salt, AQE Skew Join, 사전 집계 등 의미에 맞는 방법을 검토한다.

## 16. 문제 10 — 변수와 Cache

DataFrame을 변수에 넣고 count 다음 write를 호출했다. 입력은 반드시 한 번만 읽는가?

**풀이:** 변수 할당은 Plan 손잡이를 저장할 뿐 Cache가 아니다. count Job이 계산한 중간 결과가 자동으로 write Job 전체에 영구 보존되지 않으므로 다시 읽을 수 있다.

cache 또는 persist를 표시하고 첫 Action으로 물질화하면 두 번째 Action이 재사용할 수 있다. 그래도 Executor Loss, Eviction, Storage Level과 Plan 동일성에 따라 일부를 다시 계산할 수 있다. UI의 Storage와 Physical Plan에서 실제 재사용을 확인한다.

## 17. 문제 11 — Offset Exactly-once와 업무 중복

같은 event_id가 Kafka의 서로 다른 Offset 두 개에 있다. 각 Offset을 정확히 한 번 처리하면 결과 사건은 하나인가?

**풀이:** 아니다. Source 처리 관점에서는 두 위치가 서로 다른 입력이므로 둘 다 한 번씩 처리된다. 업무 관점에서는 같은 사건이 재전송된 중복일 수 있다.

event_id, Producer Sequence, Event Time 등으로 중복 정의를 만들고 대표 행 선택 규칙과 State Retention을 정한다. 무한히 중복을 기억할 수 없으므로 Watermark와 업무 지연 상한도 필요하다.

## 18. 문제 12 — Checkpoint 삭제

Streaming Checkpoint를 지우고 startingOffsets=earliest로 다시 시작했다. 이전 Query의 복구인가?

**풀이:** 아니다. Offset, Commit Log, State와 Query Metadata를 잃은 새 시작이다. earliest는 보존된 과거 입력을 다시 읽으므로 기존 Sink 결과와 중복될 수 있다.

복구하려면 원래 Checkpoint를 보존하고 호환되는 Runtime과 Plan으로 재시작한다. 새 Checkpoint가 필요하면 Cutover Offset, 격리 Sink, Upsert Key와 State 재구축을 설계한다.

## 19. 문제 13 — SQL DELETE와 물리 Delete 표현

DELETE WHERE device_id='S2'를 실행하면 반드시 Equality Delete File이 생기는가?

**풀이:** 아니다. SQL은 제거할 논리 행 조건이다. Engine은 Table Property, COW/MOR Mode, Iceberg Format Version, 지원 구현에 따라 Data File Rewrite, Position Delete, Equality Delete 또는 다른 지원 표현을 선택할 수 있다.

v3 Deletion Vector 지원 여부도 Runtime과 Engine 통합에 달려 있다. 결과 Snapshot의 Manifest와 File Content Type을 확인해야 실제 표현을 안다. 논리 결과와 물리 전략을 구분한다.

## 20. 문제 14 — 최신 Version 조합

Spark 최신 안정 Release와 Iceberg 최신 Release를 각각 설치하면 자동 호환되는가?

**풀이:** 아니다. Iceberg 1.12.0 Release Page는 Spark 3.5, 4.0, 4.1 Runtime을 나열한다. Spark 4.2가 현재 Engine이어도 4.1 Runtime JAR를 공식 4.2 지원으로 간주하지 않는다.

Spark Integration Suffix, Scala ABI, JDK, Python, Catalog, Storage Bundle까지 Matrix로 확인한다. Table Format v1/v2/v3 채택과 v4 개발 상태는 Product Release와 별도 축이다.

## 21. 문제 15 — Classic 코드와 Spark Connect

Spark Connect에서 df._jdf와 RDD를 사용하는 Classic 코드를 그대로 실행할 수 있는가?

**풀이:** Connect Client는 논리 Plan을 원격 Server에 전달한다. Client Process에 Driver JVM Private Object가 있다는 가정을 할 수 없다. _jdf는 공개 호환 API가 아니며 SparkContext와 RDD 경로도 Classic과 다르다.

DataFrame API 문서의 Connect 지원 표시를 확인하고, 사용자 함수가 Client와 Server 중 어디서 실행되는지, Dependency를 어디에 설치할지 정한다. 같은 메서드 이름이 보여도 Private JVM 접근까지 호환된다는 뜻은 아니다.

## 22. 세 문제를 한 번에 연결하는 최종 추적

P2 Executor가 KR70, JP80, US90의 Shuffle Block을 만든 뒤 사라졌다고 하자. Stage 1은 P2 Block Fetch에 실패한다. Driver는 P2의 Source Partition과 Filter·부분 집계 Lineage를 이용해 다른 Executor에 새 Attempt를 보낸다.

재실행 결과는 KR70, JP80, US90이어야 한다. 현재 연산은 결정적이므로 최종 KR150, US170, JP120은 같다. 그러나 Task 안에 "API 호출 횟수 증가"가 있었다면 두 Attempt가 모두 외부 효과를 만들 수 있다. Spark가 최종 Shuffle 결과 하나를 채택해도 외부 API 상태를 되돌리지는 않는다.

Writer가 F0, F1을 만든 뒤 Driver가 Commit 응답을 잃었다면 File 목록만 보고 전체 재실행하지 않는다. Sink의 Commit ID 또는 Iceberg Snapshot을 확인한다. 성공 Snapshot이 있으면 재실행은 중복 데이터를 만들 수 있고, 실패했다면 Orphan File 정리와 재시도 경로가 필요하다.

작은 최종 세 행 collect는 Driver에 안전하지만 Source 전체 9행이라는 이유가 아니라 결과 크기가 작기 때문이다. Production에서 Group Key가 수억 개면 같은 코드는 위험하다.

## 23. 개념을 질문으로 기억하기

용어를 만났을 때 다음 다섯 질문을 답하면 서로 섞이지 않는다.

1. 이것은 Process, Plan, Data Byte, Metadata, 실행 시도 중 무엇인가?
2. Driver, Executor, Cluster Manager, Catalog, Storage 중 누가 관리하는가?
3. Application, Job, Stage, Task, Snapshot, Retention 중 어느 수명을 갖는가?
4. 실패하면 재계산하는가, 지속 상태에서 복구하는가, Commit 여부를 조회하는가?
5. 행 결과의 의미와 성능 중 무엇을 바꾸는가?

Partition은 Task의 실행 조각일 수도 있고 Table의 저장 분류일 수도 있다. Checkpoint는 지속 복구 상태이며 Cache는 재계산 가능한 임시 Block이다. Snapshot은 Commit된 Table 상태이고 Source File은 그 상태가 참조하는 Byte 중 하나다. 같은 단어를 외우는 대신 이 관계를 추적해야 실제 장애에서 다음 확인 위치를 찾을 수 있다.

## 24. 공식 자료

Driver·Executor·Task 관계는 [Spark Cluster Overview](https://spark.apache.org/docs/4.2.0/cluster-overview.html), 계획과 SQL은 [Spark SQL Guide](https://spark.apache.org/docs/4.2.0/sql-programming-guide.html), Shuffle·Memory는 [Spark Tuning Guide](https://spark.apache.org/docs/4.2.0/tuning.html), Streaming 상태는 [Structured Streaming Guide](https://spark.apache.org/docs/4.2.0/streaming/index.html)를 기준으로 했다.

Iceberg Runtime 호환성은 [Multi-engine Support](https://iceberg.apache.org/multi-engine-support/), Format 상태는 [Iceberg Spec](https://iceberg.apache.org/spec/)에 근거한다.

[교재 처음으로](README.md) · [통합 Learning 목차](../README.md)
