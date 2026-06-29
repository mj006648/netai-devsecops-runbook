# Kueue 관측/알림 runbook

## 목적

ScaleX-POD에서 ArgoCD, Karmada, Kueue를 함께 쓰면 다음처럼 상태 계층이 나뉜다.

```text
ArgoCD: Git desired state가 Karmada API Server에 sync됐는지 확인
Karmada: Resource가 어떤 member cluster에 전파됐는지 확인
Kueue: 선택된 member cluster 안에서 Job이 admitted/running 가능한지 확인
```

따라서 다음 상태는 정상적으로 동시에 발생할 수 있다.

```text
ArgoCD Application = Synced
Karmada ResourceBinding = FullyApplied=True
DataX Kueue ClusterQueue = pending=1 admitted=1
Job = Suspended
```

이 문서는 위 상태를 배포 실패로 오해하지 않도록, 어느 계층에서 무엇을 봐야 하는지 정리한다.

---

## 핵심 원칙

```text
1. ArgoCD Synced는 Karmada API Server에 desired state가 적용됐다는 뜻이다.
2. Karmada FullyApplied는 member cluster에 resource가 전달됐다는 뜻이다.
3. Kueue admitted는 member cluster 안에서 Job 실행 허가가 났다는 뜻이다.
4. ArgoCD Synced + Karmada FullyApplied가 Job Running/Completed를 의미하지 않는다.
5. batch/AI workload 상태 판단은 Kueue Workload/ClusterQueue/LocalQueue까지 같이 봐야 한다.
```

---

## 1. ArgoCD 계층 확인

전체 Application 상태:

```bash
kubectl --context kind-tower -n argocd get applications -o wide
```

특정 Application 상태:

```bash
kubectl --context kind-tower -n argocd get application <app-name> -o wide
kubectl --context kind-tower -n argocd describe application <app-name>
```

판단 기준:

```text
Synced + Healthy: Git/Karmada API sync 계층은 정상
Synced + Progressing: sync는 됐지만 workload가 아직 완료/정상 상태로 판단되지 않음
OutOfSync: Git desired state와 Karmada API Server 상태가 다름
Degraded: ArgoCD 관점에서 target resource health 문제
Unknown: ArgoCD가 target 상태를 정상적으로 판단하지 못함
```

주의:

```text
Kueue가 Job을 Suspended로 잡고 있어도 ArgoCD는 Synced일 수 있다.
Synced를 Job 실행 완료로 해석하지 않는다.
```

---

## 2. Karmada 계층 확인

member cluster 상태:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusters -o wide
```

namespace별 resource와 binding:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n <namespace> get job,deploy,svc,propagationpolicy,rb -o wide
```

ResourceBinding 상세:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n <namespace> describe rb <resourcebinding-name>
```

판단 기준:

```text
Cluster READY=True: Karmada가 member cluster를 정상으로 보고 있음
ResourceBinding Scheduled=True: placement 결정 완료
ResourceBinding FullyApplied=True: Work가 member cluster에 적용됨
Scheduled=False: placement/scheduler 문제
FullyApplied=False: member 적용 실패 또는 Work 적용 지연
Cluster READY=False/Unknown: member cluster 연결/agent/API 문제
```

주의:

```text
ResourceBinding FullyApplied=True여도 member cluster 내부 Kueue admission은 별도다.
FullyApplied=True + Job Suspended는 Kueue quota 대기일 수 있다.
```

---

## 3. member Kueue 계층 확인

Kueue controller:

```bash
kubectl --context kind-datax -n kueue-system get deploy,pods -o wide
kubectl --context kind-datax -n kueue-system logs deploy/kueue-controller-manager --tail=200
```

Kueue API resource 확인:

```bash
kubectl --context kind-datax api-resources | grep -i 'kueue\|clusterqueue\|localqueue\|resourceflavor\|workload'
```

Queue 상태:

```bash
kubectl --context kind-datax get resourceflavor,clusterqueue
kubectl --context kind-datax get clusterqueue -o wide
kubectl --context kind-datax get localqueue -A -o wide
```

Workload/Job 상태:

```bash
kubectl --context kind-datax -n <namespace> get workloads -o wide
kubectl --context kind-datax -n <namespace> get job,pods -o wide
kubectl --context kind-datax -n <namespace> describe workload <workload-name>
```

판단 기준:

```text
ClusterQueue PENDING WORKLOADS > 0: quota/queue 대기 발생
ClusterQueue ADMITTED WORKLOADS > 0: 실행 허가된 workload 존재
Workload ADMITTED=True: Kueue가 해당 Job 실행을 허가
Workload RESERVED IN empty: 아직 cluster queue quota를 받지 못함
Job STATUS=Suspended: Kueue가 아직 실행을 허가하지 않음
Job STATUS=Running: Kueue admission 이후 Pod 실행 중
```

---

## 4. 계층별 장애/대기 구분

| 관찰 상태 | 의미 | 우선 확인 |
| --- | --- | --- |
| ArgoCD OutOfSync | Git sync 문제 | ArgoCD Application event, repo revision, path |
| ArgoCD Synced + Karmada RB 없음 | ArgoCD가 target에 만들지 못했거나 resource selector 문제 | ArgoCD details, Karmada namespace/resource |
| Karmada RB Scheduled=False | placement 실패 | PropagationPolicy, cluster label, cluster READY |
| Karmada RB FullyApplied=False | member 적용 실패/지연 | Work, member cluster 상태 |
| Karmada RB FullyApplied=True + Kueue pending>0 | 배포는 됐지만 member-local quota 대기 | ClusterQueue/LocalQueue quota, Workload status |
| Kueue controller unavailable | admission controller 장애 | kueue-system Deployment/Pod/log |
| Job Suspended + Workload not admitted | Kueue 대기 | queue quota, running workload |
| Job Running + queue pending>0 | quota가 일부 workload만 허용 | 정상 backpressure 또는 quota 부족 |

---

## 5. 알림 기준 초안

### Critical

```text
1. kueue-controller-manager available replicas = 0
2. Karmada member cluster READY=False/Unknown이 지속됨
3. ArgoCD Application Degraded가 지속됨
4. 운영 batch namespace에서 LocalQueue pending이 장시간 증가만 함
```

### Warning

```text
1. ClusterQueue PENDING WORKLOADS > 0 이 10분 이상 지속
2. LocalQueue PENDING WORKLOADS > 0 이 10분 이상 지속
3. ArgoCD Synced + Karmada FullyApplied=True 이지만 Job Suspended가 10분 이상 지속
4. Kueue controller restart count 증가
```

### Info

```text
1. ClusterQueue PENDING WORKLOADS > 0 이지만 ADMITTED WORKLOADS도 존재
2. batch workload가 quota에 의해 정상적으로 backpressure 중
3. ArgoCD Application Health=Progressing이고 Job이 아직 실행/완료 중
```

운영에서는 namespace, workload 중요도, SLA에 따라 시간을 조정한다.

---

## 6. 장애 대응 순서

```text
1. ArgoCD Application이 Synced인지 확인
2. Karmada API Server에 Job/Policy가 존재하는지 확인
3. ResourceBinding이 어느 cluster로 배치됐는지 확인
4. 해당 member cluster의 Kueue controller가 Running인지 확인
5. ClusterQueue/LocalQueue pending/admitted 수 확인
6. Workload가 admitted됐는지 확인
7. Job이 Suspended인지 Running인지 확인
8. quota 부족이면 quota 조정, workload 우선순위, 대기, running Job 정리 중 하나를 선택
9. Kueue controller 장애면 controller 복구 후 Workload 재수렴 확인
10. Karmada placement 문제면 PropagationPolicy/cluster label/cluster READY를 먼저 수정
```

---

## 7. 관측 snapshot 기록 템플릿

```text
시간:
Application:
  name:
  sync:
  health:
  revision:
Karmada:
  cluster READY:
  namespace:
  ResourceBinding:
    scheduled:
    fullyApplied:
    target clusters:
Kueue member cluster:
  cluster:
  controller ready:
  ClusterQueue pending/admitted:
  LocalQueue pending/admitted:
  Workload admitted:
  Job status:
판단:
  sync 문제 / placement 문제 / member apply 문제 / Kueue quota 대기 / Kueue controller 장애
조치:
```

---

## 8. ScaleX-POD 권장 구조

```text
1. Tower ArgoCD dashboard만 보고 batch 상태를 끝내지 않는다.
2. Karmada ResourceBinding dashboard와 Kueue queue dashboard를 함께 둔다.
3. DataX/TwinX batch namespace별 LocalQueue pending/admitted를 기본 지표로 둔다.
4. Kueue pending은 항상 장애가 아니라 quota backpressure일 수 있음을 알림 메시지에 명시한다.
5. 운영 Job의 완료/지연 판단은 member cluster의 Kueue Workload와 Job 상태 기준으로 한다.
```
