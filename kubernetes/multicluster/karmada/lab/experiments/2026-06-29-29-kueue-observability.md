# 실험 29. Kueue 관측/알림 runbook 검증

## 목적

실험 28에서 ArgoCD/Karmada는 성공 상태인데 Kueue에서는 일부 Job이 pending/Suspended일 수 있음을 확인했다.
이번 실험은 이 차이를 운영자가 놓치지 않도록 Kueue 관측/알림 runbook을 작성하고, 실제 demo 상태에서 runbook 명령이 필요한 정보를 보여주는지 검증한다.

작성한 runbook:

```text
kubernetes/multicluster/karmada/RUNBOOK.md#kueue-관측알림-runbook
```

---

## 사전 상태

```text
git status: clean
ArgoCD existing Applications: Synced/Healthy
Karmada clusters: twinx/edgex/datax/poolx/pullx READY=True
Kueue on datax: kueue-controller-manager 1/1 Running
Current Kueue queues/workloads on datax: 없음
```

확인 명령:

```bash
git status -sb
kubectl --context kind-tower -n argocd get applications -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusters -o wide
kubectl --context kind-datax -n kueue-system get deploy,pods -o wide
kubectl --context kind-datax get resourceflavor,clusterqueue 2>/dev/null || true
kubectl --context kind-datax get localqueue -A 2>/dev/null || true
kubectl --context kind-datax get workloads -A 2>/dev/null || true
```

결과 요약:

```text
ArgoCD 기존 app은 Synced/Healthy
Karmada member cluster는 모두 READY=True
Kueue controller는 datax에서 Running
실험 demo queue/workload는 cleanup된 상태
```

---

## 1. 관측 demo 재실행

실험 28에서 만든 demo를 짧게 다시 실행했다.

```bash
kubectl --context kind-datax apply -f kubernetes/multicluster/karmada/manifests/demo-argocd-kueue-datax/member/00-namespace.yaml
kubectl --context kind-datax apply -f kubernetes/multicluster/karmada/manifests/demo-argocd-kueue-datax/member/10-kueue-queues.yaml

kubectl --context kind-tower apply -f kubernetes/multicluster/karmada/argocd/applications/karmada-kueue-datax.yaml
kubectl --context kind-tower -n argocd annotate application karmada-kueue-datax argocd.argoproj.io/refresh=hard --overwrite
```

결과:

```text
namespace/demo-argocd-kueue-datax created
ResourceFlavor/ClusterQueue/LocalQueue created
Application/karmada-kueue-datax created
```

---

## 2. 관측 snapshot

ArgoCD:

```text
NAME                  SYNC STATUS   HEALTH STATUS   REVISION
karmada-kueue-datax   Synced        Progressing     eaa0df5712cc56e9f6f2072d21e4ec5c297600e9
```

Karmada:

```text
job.batch/demo-argocd-kueue-hold-a   Running
job.batch/demo-argocd-kueue-hold-b   Running
resourcebinding/demo-argocd-kueue-hold-a-job SCHEDULED=True FULLYAPPLIED=True
resourcebinding/demo-argocd-kueue-hold-b-job SCHEDULED=True FULLYAPPLIED=True
```

Kueue/DataX:

```text
ClusterQueue argocd-datax-cpu-queue PENDING WORKLOADS=1 ADMITTED WORKLOADS=1
LocalQueue   argocd-datax-user-queue PENDING WORKLOADS=1 ADMITTED WORKLOADS=1
```

Workload:

```text
job-demo-argocd-kueue-hold-a-53939   argocd-datax-user-queue   argocd-datax-cpu-queue   True
job-demo-argocd-kueue-hold-b-7c50f   argocd-datax-user-queue
```

Job/Pod:

```text
job.batch/demo-argocd-kueue-hold-a   Running
job.batch/demo-argocd-kueue-hold-b   Suspended
pod/demo-argocd-kueue-hold-a-*       Running
```

판단:

```text
ArgoCD: sync 성공
Karmada: placement/apply 성공
Kueue: quota로 1개 admitted, 1개 pending
member Job: admitted Job만 Running, pending Job은 Suspended
```

---

## 3. runbook에서 정리한 알림 해석

위 상태는 다음처럼 해석한다.

```text
장애가 아니라 Kueue quota backpressure 상태다.
ArgoCD/Karmada 배포 실패가 아니다.
운영 알림은 "배포 실패"가 아니라 "Kueue queue pending 발생"으로 분리해야 한다.
```

알림 후보:

```text
Info: ClusterQueue pending=1 admitted=1
Warning: pending이 10분 이상 지속되면 queue 지연 알림
Critical: kueue-controller-manager unavailable 또는 member cluster READY Unknown
```

---

## 4. cleanup

관측 demo 리소스는 정리하고, Kueue 설치만 유지했다.

```bash
kubectl --context kind-tower -n argocd delete application karmada-kueue-datax --ignore-not-found
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete -f kubernetes/multicluster/karmada/manifests/demo-argocd-kueue-datax/karmada/ --ignore-not-found
kubectl --context kind-datax delete -f kubernetes/multicluster/karmada/manifests/demo-argocd-kueue-datax/member/ --ignore-not-found
```

최종 상태:

```text
Application/karmada-kueue-datax: NotFound
Karmada demo namespace: NotFound
DataX demo namespace/queue: NotFound
Kueue controller on datax: 1/1 Running 유지
```

---

## 성공/실패 판단

```text
Kueue 관측 runbook 작성: 성공
ArgoCD/Karmada/Kueue 계층별 관측 명령 정리: 성공
pending/admitted snapshot 재현: 성공
Synced/FullyApplied와 Kueue pending 차이 해석 정리: 성공
알림 severity 초안 작성: 성공
cleanup: 성공
```

---

## ScaleX-POD에 주는 의미

```text
1. Tower ArgoCD 화면만으로 DataX/TwinX batch 상태를 판단하면 안 된다.
2. Karmada ResourceBinding과 member Kueue queue 상태를 함께 봐야 한다.
3. pending은 장애가 아니라 quota backpressure일 수 있다.
4. 알림은 GitOps 실패, placement 실패, member apply 실패, Kueue quota 대기, Kueue controller 장애로 분리한다.
5. 실제 ScaleX-POD dashboard는 ArgoCD/Karmada/Kueue 3계층을 같이 보여줘야 한다.
```

---

## 다음 액션

```text
1. Kueue queue/resourceflavor GitOps 배포 구조 검토
2. Kueue controller 장애/복구 실험
3. Kueue quota 변경 실험
4. ArgoCD AppProject migration 실험
```
