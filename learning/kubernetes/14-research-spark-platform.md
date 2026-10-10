# 14. 연구용 Spark on Kubernetes 플랫폼

[이 책 목차](README.md) · [이전: 로컬 실습](13-local-labs.md) · [다음: 버전과 확장](15-versions-and-extensions.md)

Spark를 Kubernetes에서 실행하면 driver와 executor가 Pod가 된다. Kubernetes는 Pod 배치와 재시작 기반을 제공하지만 Spark job의 commit, streaming source·sink correctness, Iceberg catalog 계약을 대신하지 않는다.

![Spark driver와 executor가 Kubernetes에서 실행되는 구조](assets/architecture.svg)

## 1. Process 배치

```mermaid
flowchart TB
    C["spark-submit client"] --> API["Kubernetes API"]
    API --> D["Spark driver Pod"]
    D --> API
    D --> E1["Executor Pod 1"]
    D --> E2["Executor Pod 2"]
    D --> E3["Executor Pod 3"]
    D --> CAT["Iceberg catalog"]
    E1 --> OBJ["Object storage"]
    E2 --> OBJ
    E3 --> OBJ
```

Cluster deploy mode에서 제출 client가 driver Pod 생성을 요청하고 driver가 executor Pod를 생성·관찰한다. Executor는 task를 수행하고 driver에 상태와 결과를 보낸다. 공식 [Spark on Kubernetes](https://spark.apache.org/docs/4.0.4/running-on-kubernetes.html)를 기준으로 한다.

## 2. ServiceAccount와 API 권한

Driver는 자기 namespace에서 executor Pod와 관련 resource를 만들고 감시·삭제할 권한이 필요하다. 전용 ServiceAccount와 namespace Role을 사용하고 `cluster-admin`을 주지 않는다.

```text
spark.kubernetes.authenticate.driver.serviceAccountName=spark-driver
spark.kubernetes.namespace=spark-lab
```

필요 verb는 Spark version, executor allocation, Service·ConfigMap 사용에 따라 달라진다. [10장](10-security-rbac.md)의 baseline을 실제 API audit와 공식 문서로 보정한다. Executor application code가 Kubernetes API를 쓸 필요가 없다면 token automount를 제한한다.

## 3. Executor 수와 Pod 수

정적 allocation에서 executor 4개라면 기본 Spark application Pod는 driver 1개와 executor 4개로 약 5개다.

```text
spark.executor.instances=4
spark.executor.cores=2
→ executor task slot 기준 약 8개
```

Dynamic allocation을 사용하면 executor Pod 수가 변한다. Pod 수와 CPU slot, 실제 parallelism은 input partition, shuffle partition, scheduler backlog의 영향을 함께 받는다.

## 4. JVM heap와 container memory

```mermaid
flowchart TD
    LIM["Executor container memory limit"] --> H["JVM heap: spark.executor.memory"]
    LIM --> O["memoryOverhead: native, off-heap, container process"]
    LIM --> P["PySpark worker memory"]
    LIM --> X["명시한 offHeap memory"]
```

`spark.executor.memory=6g`는 container 전체 limit 6Gi와 같은 뜻이 아니다. 대략 heap + overhead + off-heap + PySpark memory를 담을 공간이 필요하다.

```text
--conf spark.executor.memory=6g
--conf spark.executor.memoryOverhead=1g
--conf spark.executor.cores=2
--conf spark.kubernetes.executor.limit.cores=2
```

이 설정 조각은 `lab13/spark-lab` 격리 실습 예시이며 제출하지 않았다. CPU limit이 task slot보다 너무 낮으면 throttling되고 memory overhead가 작으면 heap 밖 사용 때문에 OOMKilled될 수 있다.

## 5. 실행 가능한 제출 형태

```text
spark-submit \
  --master k8s://https://kubernetes.default.svc \
  --deploy-mode cluster \
  --name research-etl \
  --conf spark.kubernetes.namespace=spark-lab \
  --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark-driver \
  --conf spark.kubernetes.container.image=registry.example/spark:4.0.4 \
  --conf spark.executor.instances=4 \
  local:///opt/spark/jobs/etl.py
```

문법 예시일 뿐 image와 job은 실제 존재하지 않으며 이 문서에서는 실행하지 않는다. External production cluster에는 적용하지 않는다.

## 6. Streaming checkpoint

Driver Pod filesystem이나 `emptyDir`에 checkpoint를 두면 Pod 교체 때 잃을 수 있다. 여러 재시작에서 같은 URI를 읽을 수 있는 지속 storage를 사용한다.

```text
checkpointLocation=s3a://research-lake/checkpoints/events-v1
```

Checkpoint 지속성만으로 exactly-once가 완성되지 않는다. Source offset semantics, sink commit/idempotency, query 변경 호환성, credential과 object-store consistency를 함께 검증한다. Pod 재시작은 외부 sink의 중복 write를 자동 취소하지 않는다. [Structured Streaming recovery semantics](https://spark.apache.org/docs/4.0.4/streaming/apis-on-dataframes-and-datasets.html#recovery-semantics-after-changes-in-a-streaming-query)를 참고한다.

```mermaid
sequenceDiagram
    participant D as "Driver Pod A"
    participant C as "Durable checkpoint"
    participant S as "Source"
    participant O as "Sink"
    D->>S: "offset 이후 batch 읽기"
    D->>O: "sink commit 시도"
    D->>C: "progress 기록"
    D--xD: "Pod 종료"
    C-->>D: "새 Driver Pod가 progress 복구"
```

Sink commit 성공 뒤 checkpoint 응답을 잃은 구간 같은 failure를 실제 connector 계약으로 시험한다.

## 7. Iceberg catalog와 object storage

개발 laptop의 local filesystem HadoopCatalog 성공은 Kubernetes 다중 writer 계약을 검증하지 않는다. Driver와 executor가 서로 다른 node에서 같은 local path를 본다고 가정할 수 없다.

연구 cluster에서는 다음을 분리한다.

- Catalog: table 이름과 current metadata commit 경계
- Object storage: data, manifest, metadata file byte 저장
- Spark integration: SQL plan, reader/writer와 Iceberg runtime
- IAM: driver·executor의 catalog/storage 권한

Object storage가 있다고 atomic Iceberg catalog commit이 생기는 것도 아니며, catalog가 있다고 모든 executor의 object access가 보장되는 것도 아니다. [Iceberg 통합 장](../apache-spark/09-iceberg-integration.md)을 함께 본다.

## 8. 읽기 전용 진단

```text
kubectl get pods -n spark-lab -l spark-app-name=research-etl
kubectl logs -n spark-lab <driver-pod> --tail=200
kubectl get events -n spark-lab --sort-by=.metadata.creationTimestamp
kubectl auth can-i create pods --as=system:serviceaccount:spark-lab:spark-driver -n spark-lab
```

위 명령은 `lab13/spark-lab` 예시이며 실행하지 않았다. Driver log, executor log, Spark UI event, object-store/catalog log를 application ID와 시간으로 연결한다.

## 9. Driver와 executor 실패를 Kubernetes retry로만 읽지 않는다

Kubernetes가 executor Pod를 다시 만들 수 있는지와 Spark가 stage task를 재시도할 수 있는지는 서로 다른 control loop다. Driver가 살아 있으면 잃은 executor를 감지해 새 executor를 요청하고 task를 다시 schedule할 수 있다. Driver가 사라지면 application 전체 복구는 submit 방식, restart policy, operator, checkpoint에 따라 달라진다.

```mermaid
sequenceDiagram
    participant D as "Spark driver"
    participant A as "Kubernetes API"
    participant E1 as "executor Pod e1"
    participant S as "external sink"
    participant E2 as "replacement executor e2"
    D->>A: "executor e1 Pod 요청"
    A-->>E1: "Pod 실행"
    D->>E1: "partition 42 task"
    E1->>S: "output 일부 write"
    E1--xD: "OOMKilled"
    D->>A: "replacement executor 요청"
    A-->>E2: "새 Pod UID 실행"
    D->>E2: "partition 42 재시도"
    E2->>S: "같은 output 다시 write 가능"
```

Spark의 task retry가 output commit protocol과 함께 안전한지 확인해야 한다. 단순 REST 호출, email, 임의 database insert를 task 안에서 수행하면 speculative execution이나 retry로 중복될 수 있다. Partition ID와 application attempt를 idempotency key로 쓰거나 transaction·commit protocol이 있는 sink를 사용한다.

## 10. 한 application의 자원 계산

Driver request 1 CPU/2Gi, executor 4개가 각각 2 CPU/8Gi를 요청하면 scheduler가 보는 합은 대략 9 CPU/34Gi다. Executor memory 설정만 더한 값이 아니다.

```text
driver:    1 × (1 CPU, 2Gi) = 1 CPU, 2Gi
executors: 4 × (2 CPU, 8Gi) = 8 CPU, 32Gi
합계 request                 = 9 CPU, 34Gi
```

세 node에 각각 남은 자원이 4 CPU/12Gi라면 합계는 충분해 보여도 executor 하나가 들어갈 node별 연속 공간과 driver placement를 순서대로 봐야 한다. Pod anti-affinity, taint, zone-bound PVC가 있으면 후보는 더 줄어든다. Dynamic allocation의 최대 executor를 기준으로 namespace quota와 downstream connection 한도도 계산한다.

## 11. 실패 시간표를 여러 log로 맞추기

```text
11:00:00 Spark UI: stage 8, task partition=42 시작
11:00:18 executor log: native allocation 1.2Gi
11:00:20 Pod status: lastState.reason=OOMKilled, exitCode=137
11:00:21 Kubernetes event: BackOff 또는 executor Pod 종료 관찰
11:00:23 driver log: executor lost, task 42 재시도
11:00:40 sink log: partition 42 write request 두 번 관찰
```

Driver log만 보면 “executor lost”이고 Kubernetes status만 보면 “OOMKilled”이며 sink log만 보면 “duplicate write”다. Application ID, stage/task attempt, Pod UID, executor ID, output partition을 함께 남겨야 하나의 사건으로 연결된다. Executor limit만 올리기 전에 skew된 partition, heap 밖 memory, Python worker, shuffle fetch와 retry side effect를 구분한다.

## 12. 문제와 해설

1. Executor 4개면 기본 Pod 수는? **Driver 포함 약 5개**다.
2. `executor.memory=6g`면 container limit도 6Gi인가? **아니다.** overhead 등을 포함해야 한다.
3. Durable checkpoint만 있으면 임의 sink가 exactly-once인가? **아니다.** source·sink 계약이 필요하다.
4. Local HadoopCatalog 성공이 다중 node object storage commit을 증명하는가? **아니다.** 서로 다른 storage·catalog 계약이다.

다음 장에서는 Kubernetes version, API lifecycle, feature gate와 extension의 성숙도를 읽는다.
