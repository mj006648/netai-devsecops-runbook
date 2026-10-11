# 12. 관찰성과 문제 해결

[이 책 목차](README.md) · [이전: Helm, Kustomize와 GitOps](11-delivery-helm-gitops.md) · [다음: 로컬 실습](13-local-labs.md)
## 한 장애를 네 신호로 연결한다

이 장의 수치와 출력은 교육용 예상 관찰이며 실제 클러스터 측정 결과가 아니다. 월요일 10:00에 API p99 latency가 200ms에서 2.4s로 올랐고 error rate가 0.2%에서 8%가 됐다고 하자.

**Metric**은 시간에 따른 숫자 표본이다. Counter는 요청 총수처럼 증가하고, gauge는 현재 queue 길이처럼 오르내리며, histogram은 latency를 bucket별 누적 count와 sum으로 집계한다. **Log**는 process가 사건과 문맥을 기록한 record다. **Trace**는 한 요청을 여러 service·database span으로 연결한다. **Kubernetes status/event**는 control plane과 kubelet이 본 객체 상태다.

```mermaid
flowchart LR
    U["사용자 GET /orders<br/>trace_id=t9"] --> G["Gateway span 40ms"]
    G --> A["API Pod span 2100ms"]
    A --> D["DB query span 1900ms"]
    M["Histogram p99=2.4s<br/>error=8%"] --> I["Incident 시작"]
    E["Event: OOMKilled<br/>restartCount 증가"] --> I
    L["Log trace_id=t9<br/>pool timeout"] --> A
    T["Trace t9"] --> D
```

Metric→incident는 이상을 넓게 발견한다. Event는 container 수명 변화를 설명한다. Log와 trace ID는 특정 요청의 application·DB 시간을 연결한다. 어느 하나만으로 모든 원인을 증명하지 않는다.

## Cardinality는 왜 비용과 신뢰성을 해치는가

Metric label 조합 하나가 time series를 만든다. `method` 5개 × `route` 40개 × `status` 6개 × `pod` 100개면 최대 120,000 series다. 여기에 `user_id` 백만 개를 label로 넣으면 폭증한다. User·request ID는 log/trace field에 두고 metric label은 제한된 집합을 사용한다.

Pod name label은 rollout마다 새 값이 생겨 series churn을 만든다. Service-level SLO에는 stable workload·route label로 집계하고, Pod별 진단 metric은 보존 기간과 목적을 분리한다.

## Histogram과 p99 손계산의 한계

10,000개 요청 중 latency bucket 누적 count가 다음과 같다고 하자.

| le bucket | 누적 count |
|---:|---:|
| 0.1s | 8,000 |
| 0.25s | 9,500 |
| 0.5s | 9,850 |
| 1s | 9,930 |
| 2.5s | 9,995 |
| +Inf | 10,000 |

p99 위치는 9,900번째다. 0.5s bucket에는 9,850개뿐이고 1s bucket에 9,930개이므로 p99는 0.5~1s 구간으로 추정된다. Histogram query는 bucket 안 분포를 보간할 수 있지만 실제 9,900번째 raw latency를 저장한 것은 아니다. Bucket 경계를 SLO 근처에 두는 이유다.

Instance별 quantile summary를 평균내는 것은 전체 p99가 아니다. Histogram bucket은 여러 replica를 합산할 수 있지만 scrape 누락, reset, rate window를 고려한다.

## SLI, SLO, error budget, alert

SLI(Service Level Indicator)는 성공률·latency처럼 측정한 지표다. SLO는 “28일 동안 유효 요청 99.9% 성공” 같은 목표다. 99.9%이면 error budget은 0.1%다. 1,000,000 요청 기간이면 허용 실패는 1,000개다.

5분에 100,000 요청 중 2,000개가 실패하면 실패율 2%이고 budget 소비 속도는 목표 허용률 0.1%의 20배다. 짧은 window만 alert하면 순간 noise가 많고 긴 window만 쓰면 늦다. 빠른 burn과 지속 burn을 함께 보는 multi-window alert를 설계한다.

SLO alert는 원인 진단이 아니다. Alert annotation에 dashboard, log query, runbook을 연결하고 실제 traffic·maintenance 조건을 기록한다.

## 완전 수치 시간표

| 시각 | 사용자/SLI | Kubernetes 상태 | App/DB 증거 | 판단 |
|---:|---|---|---|---|
| 09:55 | p99 0.2s, error 0.2% | Ready 4/4 | DB pool 40% | 정상 기준 |
| 10:00 | p99 1.2s | Ready 4/4 | DB query p99 0.9s | Process는 Ready지만 느림 |
| 10:02 | p99 2.4s, error 8% | Pod p2 OOMKilled | pool wait·cache 증가 | Memory spike와 DB 지연 병존 |
| 10:03 | Ready 3/4 | Endpoint p2 제외 | 기존 keep-alive 일부 error | Readiness 전파 |
| 10:05 | 새 Pod Pending | FailedScheduling memory | available 3 | Request/allocatable 확인 |
| 10:10 | DB p99 정상 | 새 Pod Ready | app p99 0.3s | 회복 후보 |
| 10:20 | error budget burn 하락 | Ready 4/4 | trace 정상 | Incident 종료 조건 검토 |

OOMKilled 하나를 root cause로 즉시 확정하지 않는다. DB 지연이 queue와 memory를 키웠을 수도 있고 memory leak가 DB connection을 고갈시켰을 수도 있다. Timeline과 trace, heap/profile 등 후속 증거로 인과 방향을 검증한다.

## 로그와 이전 container

Kubelet이 같은 Pod 안 container를 재시작하면 현재 log와 이전 instance log가 다르다. `--previous` 개념으로 이전 종료 직전 stack trace를 찾는다. Pod가 삭제되면 node-local log가 사라질 수 있어 중앙 수집과 retention이 필요하다.

Log에는 timestamp, severity, service, operation, trace ID를 구조화해 남긴다. Password·token·개인정보를 넣지 않는다. Sampling은 volume을 줄이지만 rare error를 잃을 수 있어 error log 정책을 분리한다.

## Trace sampling과 인과관계

Head sampling은 요청 시작 때 보존 여부를 고르고, tail sampling은 완료 후 latency/error를 보고 결정할 수 있다. Sampling되지 않은 요청이 없었다는 뜻은 아니다. Trace context propagation이 끊기면 gateway와 DB span이 다른 trace로 보인다.

Trace의 긴 DB span은 그 요청에서 시간이 소비된 위치를 보여 주지만 DB가 최초 원인임을 단독 증명하지 않는다. App가 잘못된 query를 생성했거나 lock holder가 다른 workload일 수 있다. Query fingerprint, lock wait, database metric으로 이어간다.

## 문제와 유도 해설 보강

1. Running Pod면 SLO 정상인가? **아니다.** Phase는 process 수명 요약이고 latency/error SLI는 별도다.
2. User ID를 metric label로 넣으면 왜 위험한가? **Series cardinality가 사용자 수만큼 늘어 memory·query 비용과 수집 안정성을 해친다.**
3. Histogram p99가 0.8s이면 정확한 raw 99번째 값인가? **Bucket 누적값에서 보간한 추정일 수 있다.** Bucket 설계를 본다.
4. 99.9% SLO에서 1,000,000 요청의 budget은? **실패 1,000개**다.
5. OOMKilled event 하나로 root cause를 확정할 수 있는가? **아니다.** 원인 또는 결과일 수 있어 timeline·resource·trace·application 증거를 연결한다.

문제 해결은 명령을 많이 실행하는 일이 아니라 증상을 어느 계층에서 관찰했는지 구분하는 일이다. Kubernetes object status, event, container log, metric, application trace를 같은 시간축으로 연결한다.

## 1. 네 가지 신호

| 신호 | 답하는 질문 | 한계 |
| --- | --- | --- |
| Status·condition | Control plane이 어떤 상태를 관찰했나? | 업무 성공을 직접 증명하지 않음 |
| Event | 최근 어떤 결정·실패 이유가 있었나? | 보존 기간이 짧고 중복 집계 가능 |
| Log | Process가 무엇을 기록했나? | 기록하지 않은 사실은 알 수 없음 |
| Metric·trace | 시간이 지나며 얼마나, 어디서 느린가? | 수집·label·sampling 설계 필요 |

```mermaid
flowchart LR
    S["사용자 오류"] --> I["Ingress/Service"]
    I --> P["Pod readiness와 restart"]
    P --> A["Application log와 metric"]
    A --> D["Database/object storage"]
    E["Kubernetes events"] --> P
```

## 2. Pod phase와 Ready

Pod phase는 `Pending`, `Running`, `Succeeded`, `Failed`, `Unknown`의 큰 수명 상태다. `Running`은 적어도 하나의 container가 실행 중이거나 시작·재시작 중이라는 뜻이며 모든 container가 Ready이거나 application이 정상이라는 뜻이 아니다.

```text
PHASE=Running
Ready condition=False
ContainersReady=False
→ process는 있지만 새 traffic을 받지 못할 수 있음
```

`CrashLoopBackOff`는 `kubectl`이 container가 반복 실패하고 backoff 중임을 보여 주는 status/reason 표현이지 Pod phase 이름이 아니다. 실제 Pod phase는 `Running`일 수 있다. [Pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)을 참고한다.

## 3. 읽기 전용 첫 절차

다음은 `lab13` context와 `observe-lab` namespace 전용 읽기 예시다. 여기서는 실행하지 않았다.

```text
1. kubectl config current-context
   예상: lab13
2. kubectl get pods -n observe-lab -o wide
3. kubectl describe pod api-abc -n observe-lab
4. kubectl get events -n observe-lab --sort-by=.metadata.creationTimestamp
5. kubectl logs api-abc -n observe-lab -c api --tail=200 --timestamps
6. kubectl logs api-abc -n observe-lab -c api --previous --tail=200 --timestamps
```

`--previous`는 같은 Pod의 해당 container에서 바로 전에 종료된 instance log를 요청한다. 새 Pod로 교체되었거나 node log가 사라졌다면 중앙 log storage가 필요하다. 공식 [kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/)를 본다.

## 4. 증상별 순서

```mermaid
flowchart TD
    X["Pod가 정상 아님"] --> P{"Pending?"}
    P -->|"예"| PE["Events: resource, affinity, taint, PVC"]
    P -->|"아니오"| R{"Restart 증가?"}
    R -->|"예"| L["logs --previous, exitCode, OOMKilled, probe"]
    R -->|"아니오"| RD{"Ready false?"}
    RD -->|"예"| PR["Readiness endpoint와 dependency"]
    RD -->|"아니오"| NET["Service, EndpointSlice, DNS, policy"]
```

### Pending

Scheduler event의 `Insufficient cpu`, untolerated taint, affinity mismatch를 본다. PVC Pending이면 provisioner·StorageClass event를 본다.

### ImagePullBackOff

Image 이름과 digest, registry DNS/TLS, pull secret, node egress를 확인한다. Backoff는 원인보다 재시도 상태다.

### OOMKilled

`lastState.terminated.reason`, exit code, memory limit, application heap/native 사용을 본다. Limit만 올리기 전에 leak과 request/limit 관계를 측정한다.

### Ready false

Probe path·port·timeout, startup 시간, dependency 상태를 본다. Liveness를 느슨하게 바꾸어 장애를 숨기지 않는다.

## 5. Event의 성격

Event는 scheduler, kubelet, controller가 남기는 관찰 기록이다. 동일 event는 count로 합쳐질 수 있고 영구 audit log가 아니다.

```text
Warning  FailedScheduling  0/3 nodes available: 3 Insufficient cpu
Warning  BackOff           Back-off restarting failed container api
Normal   Pulled            Container image already present on machine
```

Message 문자열 parsing을 장기 API 계약처럼 사용하지 않는다. Alert는 metric·condition과 함께 설계한다. [Events](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/)를 참고한다.

## 6. Log 안전성

- Credential, token, Authorization header를 출력하지 않는다.
- Request ID, Pod name, application version을 구조화 field로 남긴다.
- High-cardinality 사용자 값을 metric label에 넣지 않는다.
- Node-local log rotation과 중앙 수집 보존 기간을 구분한다.
- 여러 replica의 clock과 timezone을 맞춘다.

`kubectl logs`는 시작점이며 여러 Pod·과거 Pod·장기 추세에는 중앙 수집이 필요하다.

## 7. Metric과 trace

Resource metric은 CPU·memory 사용을, application metric은 request rate·latency·error를 보여 준다. Distributed trace는 Service 경계를 지난 한 요청 경로를 연결한다. Metric이 정상인데 사용자가 느리면 sampling되지 않은 dependency나 queue 대기를 trace와 log로 좁힌다.

```mermaid
flowchart LR
    REQ["request_id=7f3"] --> W["web span 120ms"]
    W --> API["api span 95ms"]
    API --> DB["db span 80ms"]
    M["p95 latency 증가"] --> REQ
    L["같은 request_id log"] --> API
```

## 8. OOMKilled와 CrashLoopBackOff를 한 사건으로 진단하기

다음 사례는 실제 cluster 실행 기록이 아니라 각 관찰이 어떻게 연결되는지를 보여 주는 완전한 예상 진단 이야기다. 교육용 Pod `api-7d9f`의 memory request는 256Mi, limit은 512Mi라고 가정한다.

```text
09:14:00 새 image rollout, Pod api-7d9f 시작
09:16:21 traffic 증가, container RSS 505Mi
09:16:24 kernel/cgroup이 process 종료
09:16:25 kubelet status: lastState.terminated.reason=OOMKilled, exitCode=137
09:16:26 restartCount=1, 새 container 시작
09:16:40 같은 입력을 읽고 다시 memory 증가
09:17:10 반복 실패 뒤 restart backoff 증가
09:17:11 kubectl get 표시: Running, 0/1, CrashLoopBackOff
```

여기에는 서로 다른 상태 표현이 동시에 참일 수 있다.

| 관찰 위치 | 값 | 뜻 |
| --- | --- | --- |
| Pod `status.phase` | `Running` | Pod가 node에 bind되어 container를 실행·재시작하는 큰 수명 단계 |
| 현재 container state | `waiting.reason=CrashLoopBackOff` | 지금은 반복 실패 뒤 다음 재시작을 기다림 |
| 직전 container state | `terminated.reason=OOMKilled` | 바로 전 process가 memory 관련 kill로 종료됨 |
| `restartCount` | 증가 | 같은 Pod UID 안에서 container instance가 교체됨 |
| kubectl `STATUS` 열 | `CrashLoopBackOff` | 사람이 보기 쉽게 고른 container 상태 요약이며 Pod phase가 아님 |

따라서 `STATUS=CrashLoopBackOff`만 보고 application exception이라고 단정하지 않고 `lastState`의 reason·exitCode와 event를 확인한다. 반대로 `phase=Running`만 보고 건강하다고 결론 내리지 않는다.

## 9. 같은 사례의 읽기 순서와 예상 증거

다음 명령은 `lab13/observe-lab`의 읽기 전용 교육 절차이며 여기서는 실행하지 않았다.

```text
kubectl get pod api-7d9f -n observe-lab -o wide
kubectl get pod api-7d9f -n observe-lab \
  -o jsonpath='{.status.phase}{"\n"}{.status.containerStatuses[0].state}{"\n"}{.status.containerStatuses[0].lastState}{"\n"}'
kubectl describe pod api-7d9f -n observe-lab
kubectl logs api-7d9f -n observe-lab -c api --previous --timestamps --tail=200
kubectl logs api-7d9f -n observe-lab -c api --timestamps --tail=200
kubectl get events -n observe-lab --sort-by=.metadata.creationTimestamp
```

예상되는 핵심 증거는 다음과 같다.

```text
phase: Running
state.waiting.reason: CrashLoopBackOff
lastState.terminated.reason: OOMKilled
lastState.terminated.exitCode: 137
restartCount: 4
event: Back-off restarting failed container api
previous log: loading partition=2026-10-10, estimated rows=4800000
```

Event의 `BackOff`는 재시작을 늦추고 있다는 결과이지 memory 원인 자체가 아니다. `--previous` log는 죽은 instance가 마지막으로 무엇을 하던 중이었는지 보여 준다. 현재 log만 보면 막 시작한 process의 banner만 있어 원인을 놓칠 수 있다.

## 10. OOM이라고 limit만 올리지 않는 이유

`OOMKilled` 뒤에는 여러 다른 원인이 있다.

- Container cgroup limit보다 heap+native+page cache 사용이 커졌다.
- Application leak 때문에 시간에 따라 계속 증가한다.
- 한 요청이나 partition 크기가 정상 범위를 벗어났다.
- Sidecar와 app의 limit을 혼동해 다른 container를 보고 있다.
- Node 전체 memory pressure에서 eviction과 kernel OOM이 관여했다.

먼저 container 이름, limit, working set/RSS 추세, application heap, native allocation, input cardinality를 같은 시간축으로 본다. Limit을 512Mi에서 2Gi로 올려 잠시 정상화되더라도 leak이면 실패 시간만 늦춘다. 반대로 정상 peak가 700Mi이고 node에 충분한 여유가 있으며 application을 줄일 수 없다면 측정 근거로 request와 limit을 함께 조정할 수 있다.

Memory request를 그대로 256Mi로 두고 limit만 2Gi로 올리면 scheduler는 여전히 256Mi만 예약한다. Replica 여러 개가 동시에 2Gi에 가까워지면 node pressure가 커진다. 안정적인 사용 percentile을 바탕으로 request도 다시 산정한다.

## 11. Probe 실패가 CrashLoop을 만든 반례

`lastState.terminated.reason=Error`, exit code가 애플리케이션의 자연 종료 값이 아니고 event에 `Liveness probe failed`와 `Killing`이 이어지면 memory가 아니라 kubelet이 container를 재시작했을 수 있다.

```mermaid
flowchart TD
    C["CrashLoopBackOff 표시"] --> LS{"lastState reason"}
    LS -->|"OOMKilled"| M["limit·heap·native·node pressure"]
    LS -->|"Error/Completed"| E["exitCode와 previous log"]
    E --> EV{"Event에 probe failed + Killing?"}
    EV -->|"예"| P["probe path·timeout·dependency·startup"]
    EV -->|"아니오"| A["application exit 또는 command 오류"]
```

Database가 잠깐 느려져 liveness endpoint가 timeout되고 kubelet이 정상 process를 죽이는 경우, heap을 늘려도 해결되지 않는다. `describe` event와 probe 설정, application access log를 같은 timestamp로 맞춰야 한다.

## 12. 새 Pod와 같은 Pod의 재시작을 구분하기

Deployment rollout이나 eviction으로 Pod가 교체되면 새 UID가 생긴다. 이때 새 Pod에서 `kubectl logs --previous`를 실행해도 옛 Pod의 container log를 얻지 못한다. 중앙 log에서 Pod UID, owner revision, container restart index를 함께 저장해야 한다.

```text
api-7d9f UID=aaa restartCount=4  ← 같은 Pod 안 재시작
api-b62c UID=bbb restartCount=0  ← rollout로 생긴 새 Pod
```

Pod 이름 prefix가 같다고 동일 instance가 아니다. ReplicaSet hash가 다르면 image·config template revision도 다를 수 있다. 장애가 rollout 직후 시작했다면 두 ReplicaSet별 error rate와 image digest를 비교한다.

## 13. 진단이 완료되는 조건

원인을 찾았다는 말은 `CrashLoopBackOff` 표시가 사라졌다는 뜻만이 아니다. 이 사례의 완료 조건은 다음과 같다.

1. 이전 container의 OOMKilled와 memory 증가가 timestamp로 연결된다.
2. Leak, 정상 peak, 비정상 input 중 재현 가능한 원인이 좁혀진다.
3. 격리 환경에서 수정 뒤 같은 input과 부하를 실행해 restart가 늘지 않는다.
4. Request·limit과 node allocatable에서 replica 전체가 감당 가능한지 다시 계산한다.
5. Ready replica, error rate, latency가 관찰 기간 동안 회복된다.

단순히 Pod를 삭제하면 controller가 새 Pod를 만들고 잠시 초록색이 될 수 있지만 같은 input에서 다시 OOM이 난다. 재생성은 진단도 수정도 아니다.

## 14. 문제와 해설

1. Pod phase가 Running이면 Ready인가? **아니다.** Condition을 별도로 본다.
2. CrashLoopBackOff는 Pod phase인가? **아니다.** 반복 실패와 backoff를 보여 주는 표시다.
3. 이전 container instance log는? **`kubectl logs --previous`**로 시도한다.
4. Event가 영구 audit 기록인가? **아니다.** 보존과 집계가 제한된 진단 신호다.

다음 장의 격리 실습에서는 이 읽기 순서를 실제 object에 적용한다.
