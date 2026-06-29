# 실험 28. ArgoCD -> Karmada -> DataX -> Kueue end-to-end

## 목적

실험 18~19, 24~25에서는 ArgoCD가 Karmada API Server를 destination으로 사용할 수 있음을 확인했다.
실험 27에서는 Karmada가 datax로 보낸 Job을 datax 내부 Kueue가 quota/admission으로 제어하는 것을 확인했다.

이번 실험은 두 흐름을 합쳐서 다음 end-to-end 구조를 검증한다.

```text
GitHub main
  -> ArgoCD on Tower
    -> Karmada API Server on Tower
      -> datax member cluster
        -> Kueue admission/queue
```

확인할 것:

```text
1. ArgoCD가 GitHub main의 Karmada Job/Policy manifest를 Karmada API Server로 sync하는가?
2. Karmada가 Job을 datax로 전파하는가?
3. datax의 Kueue가 cpu quota 기준으로 하나만 admitted하고 하나는 Suspended/Pending으로 두는가?
4. ArgoCD/Karmada 관점의 성공 상태와 Kueue admission 상태가 다르게 보이는가?
5. Karmada API Server에서 Job을 삭제하면 ArgoCD self-heal과 Kueue 재입장이 함께 동작하는가?
```

---

## 사전 상태

```text
ArgoCD registered cluster: Karmada API Server만 등록
datax 직접 등록: 없음
Kueue on datax: kueue-controller-manager 1/1 Running
Kueue image: registry.k8s.io/kueue/kueue:v0.18.2
demo namespace/queue: 없음
datax Karmada Cluster READY=True
```

확인 명령:

```bash
kubectl --context kind-tower -n argocd get applications -o wide
kubectl --context kind-tower -n argocd get secrets -l argocd.argoproj.io/secret-type=cluster -o custom-columns=NAME:.metadata.name --no-headers
kubectl --context kind-datax -n kueue-system get deploy,pods -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get cluster datax -o wide
```

---

## manifest 구성

작성 위치:

```text
kubernetes/karmada/manifests/demo-argocd-kueue-datax/
kubernetes/karmada/argocd/applications/karmada-kueue-datax.yaml
```

구성:

```text
member/
  00-namespace.yaml
  10-kueue-queues.yaml

karmada/
  00-namespace.yaml
  01-cluster-propagation-policy-namespace.yaml
  10-job-a.yaml
  11-job-b.yaml
  30-propagation-policy.yaml
```

분리 이유:

```text
Kueue CRD는 datax member cluster에만 설치되어 있다.
따라서 ResourceFlavor/ClusterQueue/LocalQueue는 datax에 직접 적용한다.
ArgoCD Application은 Karmada API Server에 Namespace/Job/PropagationPolicy만 sync한다.
```

ArgoCD Application:

```text
name: karmada-kueue-datax
source path: kubernetes/karmada/manifests/demo-argocd-kueue-datax/karmada
destination: Karmada API Server
syncPolicy: prune=true, selfHeal=true
```

manifest를 GitHub main에 먼저 올렸다.

```text
commit: f4075b8 Add ArgoCD Kueue DataX demo
```

---

## 1. datax에 Kueue queue 준비

명령:

```bash
kubectl --context kind-datax apply -f kubernetes/karmada/manifests/demo-argocd-kueue-datax/member/00-namespace.yaml

kubectl --context kind-datax apply --dry-run=server -f kubernetes/karmada/manifests/demo-argocd-kueue-datax/member/10-kueue-queues.yaml

kubectl --context kind-datax apply -f kubernetes/karmada/manifests/demo-argocd-kueue-datax/member/10-kueue-queues.yaml
```

결과:

```text
namespace/demo-argocd-kueue-datax created
resourceflavor.kueue.x-k8s.io/argocd-datax-default created
clusterqueue.kueue.x-k8s.io/argocd-datax-cpu-queue created
localqueue.kueue.x-k8s.io/argocd-datax-user-queue created
```

Queue 설정:

```text
ClusterQueue: argocd-datax-cpu-queue
LocalQueue: argocd-datax-user-queue
nominalQuota: cpu=1, memory=256Mi
```

---

## 2. ArgoCD Application 적용

명령:

```bash
kubectl --context kind-tower apply -f kubernetes/karmada/argocd/applications/karmada-kueue-datax.yaml

kubectl --context kind-tower -n argocd annotate application karmada-kueue-datax argocd.argoproj.io/refresh=hard --overwrite
```

결과:

```text
application.argoproj.io/karmada-kueue-datax created
application.argoproj.io/karmada-kueue-datax annotated
```

ArgoCD 상태:

```text
NAME                  SYNC STATUS   HEALTH STATUS   REVISION
karmada-kueue-datax   Synced        Progressing     f4075b81e37318eef0ef0182c33b9d4e352301ba
```

판단:

```text
ArgoCD sync는 성공했다.
Job이 아직 완료되지 않은 상태라 Application health는 Progressing으로 보였다.
```

---

## 3. Karmada 전파 결과

Karmada API Server 확인:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n demo-argocd-kueue-datax get job,propagationpolicy,rb -o wide
```

결과:

```text
job.batch/demo-argocd-kueue-hold-a   Running
job.batch/demo-argocd-kueue-hold-b   Running
propagationpolicy/demo-argocd-kueue-datax-jobs-policy present
resourcebinding/demo-argocd-kueue-hold-a-job SCHEDULED=True FULLYAPPLIED=True
resourcebinding/demo-argocd-kueue-hold-b-job SCHEDULED=True FULLYAPPLIED=True
```

판단:

```text
ArgoCD는 Karmada API Server에 원하는 resource를 만들었고,
Karmada는 두 Job 모두 datax로 전파했다고 판단했다.
```

---

## 4. datax Kueue admission 결과

DataX Kueue Workload 확인:

```bash
kubectl --context kind-datax -n demo-argocd-kueue-datax get workloads -o wide
```

초기 결과:

```text
job-demo-argocd-kueue-hold-a-b6d6b   argocd-datax-user-queue
job-demo-argocd-kueue-hold-b-94242   argocd-datax-user-queue   argocd-datax-cpu-queue   True
```

DataX Job/Pod 확인:

```bash
kubectl --context kind-datax -n demo-argocd-kueue-datax get job,pods -o wide
```

초기 결과:

```text
job.batch/demo-argocd-kueue-hold-a   Suspended
job.batch/demo-argocd-kueue-hold-b   Running
pod/demo-argocd-kueue-hold-b-*       Running
```

Queue 확인:

```text
ClusterQueue PENDING WORKLOADS=1 ADMITTED WORKLOADS=1
LocalQueue   PENDING WORKLOADS=1 ADMITTED WORKLOADS=1
```

판단:

```text
Kueue가 cpu=1 quota 때문에 두 Job 중 하나만 admitted했다.
어느 Job이 먼저 admitted되는지는 이름 순서가 아니라 queue 처리 시점에 따라 달라질 수 있다.
이번 run에서는 Job B가 먼저 admitted되고 Job A가 Suspended/Pending이었다.
```

중요 관찰:

```text
ArgoCD: Synced
Karmada ResourceBinding: FullyApplied=True
DataX Kueue: pending=1, admitted=1
```

즉 ArgoCD/Karmada만 보면 배포 성공처럼 보이지만, 실제 member cluster에서는 Kueue quota 때문에 하나의 Job이 아직 실행되지 않고 있었다.

---

## 5. admitted Job 삭제 후 self-heal + Kueue 재입장

초기 admitted Job은 `demo-argocd-kueue-hold-b`였다.
Karmada API Server에서 해당 Job을 삭제했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n demo-argocd-kueue-datax delete job demo-argocd-kueue-hold-b
```

관찰 중 issue:

```text
처음 작성한 관찰 loop에서 custom-columns 표현식의 괄호가 shell에서 깨져 syntax error가 발생했다.
Job 삭제 자체는 이미 성공했으므로, 단순 get -o wide 기반 loop로 다시 관찰했다.
```

삭제 후 관찰 결과:

```text
ArgoCD app: Synced / Progressing 유지
Karmada API: demo-argocd-kueue-hold-b가 다시 생성됨
ResourceBinding: hold-a/hold-b 모두 SCHEDULED=True FULLYAPPLIED=True
```

DataX Kueue 결과:

```text
job-demo-argocd-kueue-hold-a-b6d6b   argocd-datax-user-queue   argocd-datax-cpu-queue   True
job-demo-argocd-kueue-hold-b-6bdd6   argocd-datax-user-queue

job.batch/demo-argocd-kueue-hold-a   Running
job.batch/demo-argocd-kueue-hold-b   Suspended
```

판단:

```text
ArgoCD selfHeal이 Karmada API Server에서 삭제된 Job B를 복구했다.
그 사이 quota가 반환되면서 기존 pending Job A가 admitted됐다.
복구된 새 Job B는 queue에 다시 들어갔지만 cpu=1 quota 때문에 Suspended/Pending 상태로 남았다.
```

---

## 6. cleanup

demo Job이 계속 남아 다음 실험에 영향을 주지 않도록 live 리소스는 정리했다.
manifest와 Application YAML은 repo에 남겨 재실행 가능하게 했다.

정리 순서:

```bash
kubectl --context kind-tower -n argocd delete application karmada-kueue-datax --ignore-not-found

kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete -f kubernetes/karmada/manifests/demo-argocd-kueue-datax/karmada/ --ignore-not-found

kubectl --context kind-datax delete -f kubernetes/karmada/manifests/demo-argocd-kueue-datax/member/ --ignore-not-found
```

최종 확인:

```text
ArgoCD Application karmada-kueue-datax: NotFound
Karmada demo namespace/resource: NotFound
DataX demo namespace/queue/resource: NotFound
Kueue controller on datax: Running 유지
```

---

## 성공/실패 판단

```text
ArgoCD Application manifest 작성/Push: 성공
ArgoCD -> Karmada API Server sync: 성공
Karmada -> datax Job 전파: 성공
DataX Kueue quota admission: 성공
ArgoCD/Karmada 성공 상태와 Kueue pending 상태 차이 확인: 성공
Karmada API Job 삭제 후 ArgoCD self-heal: 성공
self-heal 후 Kueue 재입장/재대기 확인: 성공
cleanup: 성공
```

---

## ScaleX-POD에 주는 의미

```text
1. ArgoCD, Karmada, Kueue는 함께 쓸 수 있다.
2. ArgoCD는 Git의 desired state를 Karmada API Server에 제출한다.
3. Karmada는 ScaleX-POD member cluster 중 어디로 보낼지 결정한다.
4. Kueue는 선택된 member cluster 내부에서 Job 실행 허용 여부를 결정한다.
5. ArgoCD Synced와 Karmada FullyApplied가 곧 Job 실행 완료를 의미하지는 않는다.
6. DataX/TwinX batch/AI workload 운영에서는 Kueue Workload/ClusterQueue/LocalQueue 상태까지 같이 봐야 한다.
7. Kueue queue resource를 어디에서 GitOps로 관리할지는 별도 설계가 필요하다.
```

---

## 다음 액션

```text
1. Kueue 관측/알림 runbook 작성
2. Kueue queue/resourceflavor를 ArgoCD로 member cluster에 배포하는 구조 검토
3. Kueue controller 장애/복구 실험
4. Kueue quota 변경 실험
5. ArgoCD AppProject migration 실험
```
