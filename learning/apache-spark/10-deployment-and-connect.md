# 10. Spark 배포와 Spark Connect: Client 요청이 Cluster 실행과 응답이 되는 과정

[이전: Spark와 Iceberg](09-iceberg-integration.md) · [목차](README.md) · [다음: 로컬 실습](11-local-labs.md)

같은 DataFrame 코드라도 Driver가 노트북 안에 있는지, YARN Container나 Kubernetes Pod에 있는지에 따라 Network와 장애 경계가 달라진다. Spark Connect를 사용하면 사용자의 Python Process와 Driver Server까지 분리된다. 이 장은 Client가 실행을 요청한 순간부터 Cluster Manager가 자원을 만들고, Driver가 Plan을 분석하고, Executor가 Task를 실행하고, 결과가 돌아오거나 장애 후 재접속하는 전체 흐름을 설명한다.

예시 명령과 수치는 구조를 설명하기 위한 교육용 모델이다. 완성된 운영 Manifest나 특정 조직의 보안 설정이 아니다.

![Spark driver, executor, cluster manager의 관계](assets/architecture.svg)

## 1. Client, Driver, Executor, Cluster Manager

**Client**는 Application 제출 또는 Spark Connect 요청을 시작하는 프로그램이다. spark-submit Process, Notebook Python Kernel, IDE 안의 Connect Library가 될 수 있다. Client의 수명은 제출이 끝날 때까지일 수도 있고 Interactive Session 동안 계속될 수도 있다.

**Driver**는 사용자 Main Program, SparkSession, 분석된 Plan, Scheduler 상태를 가진 중심 Process다. Driver Memory에는 모든 원본 행이 아니라 Plan, File·Task Metadata, Driver로 Collect한 결과가 있다. Application 시작부터 종료까지 살아 있으며 Driver가 복구되지 않으면 Application이 끝날 수 있다.

**Executor**는 Driver가 보낸 Task를 실행하는 Process다. 입력 File을 읽고 Filter, Join, Aggregate를 실행하며 Cache와 Shuffle Block을 Memory·Disk에 둔다. Executor는 Application 전용으로 할당되는 것이 일반적이며 Dynamic Allocation에서는 실행 중 늘거나 줄 수 있다.

**Cluster Manager**는 CPU, Memory와 실행 위치를 배정한다. Spark Standalone Master, YARN ResourceManager, Kubernetes API와 Scheduler가 예다. Cluster Manager는 어느 Node/Container에 Process를 둘지 결정하지만 Catalyst Join 순서나 Predicate Pushdown을 정하지 않는다.

~~~mermaid
flowchart LR
    C["Client: 제출·요청"] --> D["Driver: Plan·Scheduler"]
    D --> M["Cluster Manager: CPU·Memory 배치"]
    M --> E1["Executor 1: Task·Cache·Shuffle"]
    M --> E2["Executor 2"]
    D <--> E1
    D <--> E2
    E1 --> S["Storage·Catalog"]
    E2 --> S
~~~

## 2. master와 deploy mode는 다른 질문이다

**Master URL**은 어떤 자원 관리자 또는 실행 환경을 사용할지 선택한다. local[4], spark://..., yarn, k8s://...가 예다.

**Deploy Mode**는 Driver를 Client Process 쪽에 둘지 Cluster 안에 둘지 정한다.

| 질문 | 선택 예 |
|---|---|
| 누가 자원을 배치하는가? | Local, Standalone, YARN, Kubernetes |
| Driver가 어디에 사는가? | Client Mode, Cluster Mode |
| 사용자 API가 Driver와 어떻게 통신하는가? | Classic 또는 Spark Connect |

Kubernetes를 쓴다고 반드시 Connect를 쓰는 것이 아니며, Connect를 쓴다고 반드시 Kubernetes Cluster Mode인 것도 아니다. 자원 관리자, Driver 위치, Client Protocol은 독립 축이다.

## 3. Local Mode의 생성부터 종료까지

~~~text
spark-submit --master "local[4]" app.py
~~~

local[4]는 한 Machine 안에서 최대 네 Task Thread를 쓰는 설정이다. 서버 네 대나 Executor Process 네 개를 뜻하지 않는다. Driver와 실행 Thread가 같은 Machine의 CPU, Memory, Disk와 Credential을 공유한다.

1. spark-submit이 Python Application과 Spark JVM을 시작한다.
2. SparkSession과 Driver 상태가 같은 Machine에 생긴다.
3. local Scheduler가 최대 네 Task Thread를 사용한다.
4. Task는 같은 Machine의 File과 Network 경로를 사용한다.
5. Driver Process가 끝나면 Application도 끝난다.

Local 성공은 별도 Executor JVM Loss, Node 간 Network, Kubernetes ServiceAccount, Remote Object Storage Credential 배포를 검증하지 않는다. 교육, 작은 재현, Debugger에는 적합하지만 분산 장애 실험의 대체가 아니다.

## 4. Client Mode와 Cluster Mode

**Client Mode**에서는 Driver가 spark-submit을 실행한 Client Machine에 있다. Executor가 Driver의 Host와 Port로 연결할 수 있어야 한다. 노트북 Wi-Fi, NAT, Firewall, Client Process 종료가 Application에 직접 영향을 줄 수 있다.

**Cluster Mode**에서는 Cluster Manager가 Cluster 안의 Worker 또는 Container에서 Driver를 시작한다. 제출 Client는 Application 생성 요청 뒤 종료해도 Driver가 계속 실행될 수 있다. 하지만 Driver Pod나 Container 자체가 죽었을 때 자동 복구되는지는 Cluster Manager와 Supervision 설정, Application 종류에 달려 있다.

두 Mode 모두 Executor Task를 지시하는 주체는 Driver다. Client가 Executor에 Task를 직접 보내지 않는다.

## 5. Spark Standalone의 Process 흐름

Spark Standalone은 Spark 자체 Master와 Worker Daemon이 자원을 관리한다.

1. Client가 spark://master:7077에 Application을 제출한다.
2. Client Mode이면 Client Process가 Driver다.
3. Cluster Mode이면 Worker가 Driver Process를 시작한다.
4. Master가 Worker 자원을 Executor에 배정한다.
5. Driver가 Executor와 직접 통신하며 Task를 실행한다.

~~~text
spark-submit \
  --master spark://spark-master.example:7077 \
  --deploy-mode client \
  --executor-memory 4g \
  --executor-cores 2 \
  app.py
~~~

공식 Spark 4.2 제출 문서는 Standalone Cluster Mode가 Python Application을 지원하지 않는다고 명시한다. PySpark .py를 Standalone Cluster Mode로 제출할 수 있다고 일반화하지 않는다. Standalone의 --supervise는 Cluster Mode Driver가 비정상 종료될 때 재시작을 시도하는 기능이지만 외부 Side Effect와 Streaming State를 자동 Rollback하지 않는다.

## 6. YARN의 Client·ApplicationMaster·Container

YARN은 Hadoop 생태계의 Resource Manager다. **ApplicationMaster, AM**은 한 YARN Application의 자원 요청과 생애주기를 조정하는 Container 역할이다.

Client Mode에서는 Driver가 제출 Machine에 있고 AM은 Executor Container 자원을 요청한다. Cluster Mode에서는 Driver가 AM Process 안에서 실행된다.

~~~text
spark-submit \
  --master yarn \
  --deploy-mode cluster \
  --driver-memory 2g \
  --executor-memory 8g \
  --executor-cores 4 \
  --num-executors 6 \
  app.py
~~~

Cluster Mode에서 Client Local Path의 JAR나 Python File이 Driver Node에 자동 존재한다고 가정하지 않는다. --jars, --py-files, Archive와 Distributed Cache 경로로 배포한다. Hadoop Configuration과 Credential이 AM·Driver·Executor Container에 필요한 범위로 전달되어야 한다.

YARN이 실패 Executor를 새 Container로 보충해도 Task 안에서 실행한 외부 Database Insert를 되돌리지 않는다. Spark Task Retry와 End-to-end Transaction은 별도다.

## 7. Kubernetes에서 Pod가 생기는 전체 순서

Kubernetes Cluster Mode를 예로 든다.

1. spark-submit Client가 Kubernetes API Server에 Driver Pod 생성을 요청한다.
2. Kubernetes Scheduler가 Node를 선택하고 Kubelet이 Image를 시작한다.
3. Driver Pod 안에서 Spark Driver Process가 SparkSession과 Scheduler를 만든다.
4. Driver의 ServiceAccount Credential로 Executor Pod 생성을 요청한다.
5. Executor Pod가 시작되어 Driver 주소로 등록한다.
6. Driver가 Stage별 Task를 Executor에 보낸다.
7. Executor가 Storage와 Catalog에 접근해 입력을 읽고 결과를 쓴다.
8. Executor가 Task 상태와 결과 Metadata를 Driver에 보고한다.
9. Driver가 Job 결과와 Application 상태를 기록하고 Executor를 종료한다.

~~~mermaid
sequenceDiagram
    participant C as spark-submit Client
    participant K as Kubernetes API
    participant D as Driver Pod
    participant E as Executor Pods
    participant S as Storage/Catalog
    C->>K: Driver Pod 생성
    K-->>D: Schedule·Start
    D->>K: Executor Pod 요청
    K-->>E: Schedule·Start
    E->>D: Executor 등록
    D->>E: Task 할당
    E->>S: Data read/write
    E-->>D: Task status/result
    D-->>C: 제출 상태 또는 로그 경로
~~~

다음 설정은 제출 조각이며 완성 Manifest가 아니다.

~~~text
spark-submit \
  --master k8s://https://kubernetes.default.svc \
  --deploy-mode cluster \
  --name event-etl \
  --conf spark.kubernetes.container.image=registry.example/spark:4.0.4 \
  --conf spark.executor.instances=5 \
  --conf spark.executor.cores=2 \
  --conf spark.executor.memory=6g \
  --conf spark.executor.memoryOverhead=1g \
  local:///opt/spark/jobs/app.py
~~~

Image 안의 local:///opt/...는 Client Laptop 경로가 아니라 Driver·Executor Image 내부 경로다.

## 8. Pod, Executor, Core, Task 숫자를 계산한다

Executor 5개, Executor당 2 Core, Task당 CPU 1개라고 하자.

~~~text
Spark Pod 수 = Driver 1 + Executor 5 = 6
동시 Task 후보 = 5 × 2 = 약 10
100 Tasks의 단순 최소 Wave = 100 / 10 = 10
~~~

Sidecar Container가 각 Pod에 있어도 Pod 수는 6이고 Container 수가 늘어난다. Spark Operator Pod, Admission Controller, Monitoring Agent는 Application Pod 단순 계산 밖이다.

## 9. Heap과 Container Memory를 구분한다

spark.executor.memory=6g는 Executor JVM Heap 기준이다. Container Limit에는 Heap 밖의 여러 Memory가 포함된다.

| 영역 | 실제 사용 주체 |
|---|---|
| JVM Heap | Spark Row Object, Hash State, Java/Scala 객체 |
| JVM Non-heap | Class Metadata, Code Cache |
| Direct/Native Buffer | Network, Compression, Arrow, Library |
| Python Worker | PySpark UDF와 Python 객체 |
| Off-heap Spark Memory | 명시적으로 활성화한 실행·저장 영역 |
| Sidecar Memory | 같은 Pod의 별도 Container면 별도 Limit/Request |

개념적으로 Executor Container 요청은 Heap 6GiB + Overhead 1GiB 등 설정된 항목을 반영한다. 정확한 계산과 기본 Factor는 Spark Version과 Language에 따라 다르다. Heap이 6GiB라고 Pod Memory Limit을 6GiB로 두면 Native 또는 Python 사용 때문에 OOMKilled될 수 있다.

spark.executor.cores=4인데 Kubernetes CPU Limit이 1이면 Driver는 동시에 네 Task를 배치하려 해도 Container는 CPU Throttling으로 약 1 Core 수준만 사용할 수 있다. Spark Slot과 Kubernetes Scheduler Request/Limit을 함께 설계한다.

## 10. Credential은 Process마다 필요한 범위가 다르다

**Credential, 자격 증명**은 Identity를 증명하고 Resource 접근 권한을 얻는 Secret, Token, Role 연결이다. 한곳에 넣은 Credential이 모든 Process에 자동 전파된다고 가정하지 않는다.

| Process | 필요한 대표 권한 |
|---|---|
| 제출 Client | Kubernetes Driver Pod 생성 또는 YARN 제출 |
| Driver | Executor 생성, Catalog Metadata 조회·Commit, 일부 Storage Planning |
| Executor | Data/Delete File Read, Output File Write, Shuffle Network |
| Connect Client | Connect Endpoint 인증과 Session 권한 |
| Connect Server | Spark Session, Catalog, Executor 자원 요청 |
| Catalog | Table Name/Metadata Pointer 관리와 Backend Storage 접근 |

Kubernetes에서는 Driver ServiceAccount가 Executor Pod 생성 권한을 가진다. Executor가 같은 ServiceAccount를 쓰는지 별도 ServiceAccount를 쓰는지 확인한다. Object Storage Credential은 Workload Identity, Secret Mount, SDK Provider Chain 등 실제 방법으로 Driver와 Executor에 전달한다.

Secret 값을 spark-submit Argument나 Log에 평문으로 남기면 History Server와 Process 목록에 노출될 수 있다. Network Policy와 TLS는 Credential 전송 경계를 보호한다.

## 11. Driver와 Executor의 장애 전파

Executor가 죽으면 Driver는 Heartbeat Timeout 또는 Task Failure로 감지한다. 손실 Executor의 Cache와 Shuffle Block이 사라질 수 있다. Source와 Lineage가 남아 있으면 Task를 다른 Executor에서 재실행한다.

Driver가 죽으면 Scheduler State와 Session이 사라질 수 있다. Kubernetes가 Pod를 다시 시작한다는 사실만으로 동일 Spark Application 상태가 복구되는 것은 아니다. Batch Input을 다시 실행할지, Streaming Checkpoint로 새 Driver가 이어갈지, Table Commit Outcome을 확인할지 Workload별로 다르다.

Task가 외부 REST API에 Write한 뒤 Executor가 응답 전에 죽으면 새 Attempt가 같은 Write를 반복할 수 있다. Idempotency Key, Unique Constraint, Transactional Sink 또는 검증된 Commit Protocol이 필요하다.

## 12. Spark Connect의 Client·Server 객체

**Spark Connect Client**는 DataFrame API 호출을 Unresolved Logical Plan으로 만드는 가벼운 Library다. 사용자 Notebook이나 Service Process 안에 있으며 Remote Server 주소와 Session 정보를 관리한다.

**Unresolved Logical Plan**은 Table과 Column 이름이 실제 Catalog·Schema 객체에 아직 연결되지 않은 연산 Tree다. Client는 prod.events라는 문자열을 넣지만 그 Table 존재와 Column Type은 Server가 분석한다.

**Protocol Buffers**는 이 Plan을 언어 중립적인 Message Byte로 표현하는 규격이다. **gRPC**는 HTTP/2 위에서 Method 요청과 Streaming 응답을 주고받는 RPC Framework다. Connect는 gRPC로 Plan과 Operation을 전송한다.

**Spark Connect Server**는 Spark Driver에 Endpoint를 제공한다. Plan을 Spark Logical Operator로 바꾸고 Analyzer, Catalyst, Physical Planner와 Scheduler를 사용한다. Executor가 실제 Task를 실행한다.

**Apache Arrow Batch**는 열 형태의 결과를 언어 간에 전달하기 위한 Memory 표현이다. Server는 결과를 Arrow로 Encoding해 gRPC Stream으로 Client에 보낼 수 있다. Client가 Executor와 직접 연결되는 것은 아니다.

## 13. Connect 요청의 생성부터 응답까지

~~~python
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .remote("sc://spark-connect.example:15002")
    .getOrCreate()
)

result = (
    spark.read.table("prod.analytics.events")
    .where("event_date >= DATE '2026-10-01'")
    .groupBy("event_type")
    .count()
)

result.show()
~~~

흐름은 다음과 같다.

1. getOrCreate가 Client Session을 만들고 Server Endpoint와 연결한다.
2. read.table, where, groupBy, count는 Client 안에 Unresolved Plan Node를 쌓는다.
3. Transformation만 쌓는 동안 Server가 Table을 분석하지 않을 수 있다.
4. show 또는 Schema 접근처럼 분석·실행이 필요한 Operation이 Plan을 Protocol Buffer로 Encoding한다.
5. Client가 Session ID와 Operation을 gRPC로 Server에 보낸다.
6. Server가 Table을 Catalog에서 찾고 Column과 Function을 분석한다.
7. Catalyst가 Logical Plan을 최적화하고 Physical Plan을 선택한다.
8. Driver Scheduler가 Executor에 Task를 보낸다.
9. Executor가 Partition 결과를 Server Driver로 전달한다.
10. Server가 필요한 결과 Batch와 Status를 gRPC로 Client에 Streaming한다.
11. Client가 Arrow Batch를 Python Row 또는 표시 Table로 변환한다.

없는 Column c를 Filter에 쓴 경우 Classic과 Connect는 Error 시점이 다를 수 있다. Connect Client가 Unresolved Plan만 만든 동안에는 Error가 없고, Server Analysis가 필요한 columns, explain, persist 또는 Action에서 Error가 돌아올 수 있다.

## 14. Classic PySpark와 Connect 차이

Classic PySpark의 Python Driver는 Py4J를 통해 같은 Application의 Driver JVM과 가깝게 통신한다. Connect Client는 Driver Process와 분리되며 Py4J Private Handle을 노출하지 않는다.

| 기능 | Classic | Connect |
|---|---|---|
| DataFrame/SQL | 지원 | 지원 범위 내에서 Plan 전송 |
| df._jdf, spark._jvm | Private JVM 접근 가능할 수 있음 | 제공하지 않음 |
| SparkContext/RDD | 사용 가능 | Protocol의 핵심 지원 대상 아님 |
| Static Spark Config 변경 | Driver 권한에 따라 | 공유 Server 환경이라 제한 |
| Client Local File | Driver와 같은 Host일 수 있음 | Server Local File과 다름 |
| Dependency | Driver/Executor 배포 | Server/Executor 위치에 배포 |

Client의 /home/user/data.csv를 Server가 같은 경로로 읽는다고 가정하지 않는다. Connect Plan의 File Path는 Server와 Executor가 접근할 Storage URI여야 한다. 사용자 정의 Code와 Package도 실제 실행 위치에 설치하거나 지원되는 전송 방식을 사용한다.

## 15. Connect Session, 장애와 재접속

Connect는 Session 기반이다. Temporary View, SQL Config, Cache 참조와 진행 중 Operation은 Server Session에 연결될 수 있다. Client Network가 잠시 끊겼다고 Server Operation이 반드시 취소되거나 반드시 계속된다고 하나로 단정하지 않는다. Operation 상태, Reattach 지원과 Timeout 설정을 사용 중인 Version 계약으로 확인한다.

장애를 나누어 본다.

1. **Client Process 종료:** Server Session과 Operation이 일정 기간 남을 수 있지만 영구 보존을 보장하지 않는다.
2. **gRPC Network 단절:** Client는 응답을 못 받아 결과가 불명확할 수 있다. Write Operation을 무조건 재요청하면 중복 가능성이 있다.
3. **Connect Server/Driver 종료:** In-memory Session, Temporary View, Cache와 Scheduler State가 사라질 수 있다. 새 Server는 같은 Session이라고 가정하지 않는다.
4. **Executor Loss:** Driver가 Task를 재시도하고 Connect Operation은 계속될 수 있다.
5. **Catalog Commit 뒤 응답 유실:** Table Snapshot을 확인해 성공 여부를 판단한다.

재접속 절차는 Session Identifier와 Operation Identifier가 Server에 아직 유효한지 확인하고, Reattach 가능한 Operation이면 결과 Stream을 다시 잇는다. Server State가 사라졌다면 새 Session을 만들고 Permanent Table과 Checkpoint 같은 지속 상태에서 계산을 다시 구성한다. Client DataFrame 변수만으로 Server Session을 복원할 수는 없다.

## 16. Connect 보안 경계

gRPC Endpoint는 Network Service다. HTTP/2와 인증 Proxy를 사용할 수 있지만 Spark가 모든 조직 인증 정책을 자동 제공한다고 가정하지 않는다.

- TLS로 Client와 Endpoint 사이 전송을 보호한다.
- 인증 Proxy 또는 Gateway가 사용자 Identity를 검증한다.
- Server가 Identity를 Catalog와 Storage 권한에 연결한다.
- Session 간 Temporary View와 Artifact를 격리한다.
- Query, Error, Plan Log에 Secret이 남지 않게 한다.
- 큰 결과와 장시간 Operation에 Quota와 Timeout을 둔다.

Connect Client Credential과 Server의 Storage Credential은 다르다. 사용자가 Server 접속 권한이 있어도 모든 Table을 읽을 권한이 자동 생기면 안 된다.

## 17. Streaming Checkpoint와 Driver 재시작

Structured Streaming Checkpoint는 Driver Pod의 emptyDir이나 Container Writable Layer에만 두면 Pod 교체와 함께 사라진다. Shared Durable Storage에 두고 Source Offset, State Store, Commit Log를 보존한다.

~~~python
query = (
    events.writeStream
    .format("parquet")
    .option("path", "s3a://lake/output/events")
    .option("checkpointLocation", "s3a://lake/checkpoints/events-v1")
    .start()
)
~~~

새 Driver가 같은 Checkpoint를 사용한다고 임의 Plan 변경이 모두 허용되는 것은 아니다. Stateful Operator, State Schema, Partition 수, Source와 Sink 계약을 확인한다. Checkpoint가 없으면 earliest 재시작은 같은 Application 복구가 아니라 과거 입력을 재독하는 새 시작일 수 있다.

Connect를 통해 Streaming Query를 시작했더라도 Client Session, Server Driver, Streaming Checkpoint의 수명은 다르다. Client가 닫힌 뒤 Query 관리가 어떻게 되는지는 Server와 API 계약을 확인한다.

## 18. 8개 종합 문제와 완전 풀이

### 문제 1
Kubernetes에서 Driver 1개와 Executor 5개를 고정했다. 기본 Spark Pod 수와 2 Core씩의 동시 Task 후보는?

**풀이:** Pod는 1+5=6개다. Task당 CPU 1이면 동시 Task 후보는 5×2=10개다. 100 Task는 이상적으로 10 Wave지만 Task 시간과 실패 때문에 실제는 달라진다.

### 문제 2
local[4]는 Executor 네 개 또는 서버 네 대인가?

**풀이:** 아니다. 한 Machine에서 최대 네 Task Thread를 쓰는 Local Scheduler 설정이다. 별도 Node Network와 Executor Process Loss를 재현하지 않는다.

### 문제 3
Client Mode Driver를 Laptop에서 실행했는데 Executor가 Driver에 연결하지 못한다. 왜 가능한가?

**풀이:** Executor는 Laptop Driver의 Host와 Port에 Network로 도달해야 한다. NAT, Firewall, DNS, Wi-Fi 변경이 막을 수 있다. Cluster Mode로 Driver를 Cluster Network 안에 두거나 올바른 Driver Address와 Network 정책을 구성한다.

### 문제 4
Executor Heap 6GiB, Overhead 1GiB인데 Pod Limit을 6GiB로 두면 안전한가?

**풀이:** 아니다. Container에는 Heap 밖의 JVM, Direct Buffer, Python/Native Memory가 들어간다. Limit 6GiB는 Heap이 차지한 뒤 추가 사용을 수용하지 못해 OOMKilled될 수 있다.

### 문제 5
Standalone Cluster Mode로 PySpark .py를 제출하려 한다. 현재 공식 제한은?

**풀이:** Spark 4.2 공식 제출 문서는 Standalone Cluster Mode가 Python Application을 지원하지 않는다고 명시한다. Client Mode나 다른 Cluster Manager를 선택하고 실제 Version 문서를 확인한다.

### 문제 6
Connect Client가 result DataFrame을 만들었으니 없는 Column 오류가 즉시 나야 하는가?

**풀이:** Client는 Unresolved Plan을 쌓을 수 있다. Server Analysis가 필요한 Schema 접근, explain, persist 또는 Action에서 Plan이 전송될 때 오류가 날 수 있다.

### 문제 7
Connect gRPC 응답이 끊겼다. Write를 바로 다시 보내도 되는가?

**풀이:** Server에서 Operation 또는 Catalog Commit이 성공했을 수 있다. Session·Operation 상태와 실제 Sink Snapshot을 확인한 뒤 Reattach 또는 재시도를 결정한다. 무조건 재전송하면 중복될 수 있다.

### 문제 8
Driver Pod가 재시작됐으니 Streaming Session과 Temporary View가 자동 복구되는가?

**풀이:** 아니다. Temporary View와 Cache는 Driver Memory Session 상태일 수 있다. Streaming은 호환되는 Durable Checkpoint에서 복구할 수 있지만 Plan과 Sink 계약을 확인해야 한다. 새 Driver가 이전 Connect Session을 자동 상속한다고 가정하지 않는다.

## 19. 공식 근거와 버전 경계

Driver·Executor·Deploy Mode는 [Spark 4.2 Submitting Applications](https://spark.apache.org/docs/4.2.0/submitting-applications.html), [Standalone](https://spark.apache.org/docs/4.2.0/spark-standalone.html), [YARN](https://spark.apache.org/docs/4.2.0/running-on-yarn.html), [Kubernetes](https://spark.apache.org/docs/4.2.0/running-on-kubernetes.html)을 기준으로 했다.

Unresolved Plan, Protocol Buffers, gRPC, Arrow 응답과 Classic 차이는 [Spark Connect Overview](https://spark.apache.org/docs/4.2.0/spark-connect-overview.html)에 근거한다. Spark 4.2 Engine의 배포 기능 설명과 Iceberg 1.12.0의 공식 Spark Runtime 지원 Matrix는 별개다. Iceberg 공식 Runtime은 3.5, 4.0, 4.1 축을 나열하므로 4.2 Engine에 4.1 JAR를 공식 조합으로 단정하지 않는다.

[이전: Spark와 Iceberg](09-iceberg-integration.md) · [목차](README.md) · [다음: 로컬 실습](11-local-labs.md)
