# 실험 27. Karmada + Kueue DataX 기초 실험

## 목적

Karmada와 Kueue를 같이 쓸 때 역할이 겹치는지, 아니면 분리되는지 확인한다.

이번 실험의 관점:

```text
Karmada: ScaleX-POD member cluster 중 datax로 Job을 전파한다.
Kueue: datax cluster 안에서 Job admission과 quota를 제어한다.
```

참고한 공식 문서:

- Kueue installation: https://kueue.sigs.k8s.io/docs/getting-started/installation/
- Kueue quick start: https://kueue.sigs.k8s.io/docs/getting-started/quick-start/

---

## 사전 상태

```text
datax Kueue API resources: 없음
kueue-system namespace: 없음
datax Karmada cluster READY=True
```

확인 명령:

```bash
kubectl --context kind-datax api-resources | grep -i kueue || true
kubectl --context kind-datax get ns kueue-system || true
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get cluster datax -o wide
```

결과:

```text
Kueue CRD/namespace는 아직 설치되지 않음
datax MODE=Push READY=True
```

---

## 1. Kueue 설치 위치 결정

Kueue는 member cluster 내부의 Job admission을 제어해야 하므로 이번 실험에서는 `kind-datax`에 설치했다.

```bash
kubectl --context kind-datax apply --server-side   -f https://github.com/kubernetes-sigs/kueue/releases/download/v0.18.2/manifests.yaml

kubectl --context kind-datax wait deploy/kueue-controller-manager   -n kueue-system   --for=condition=available   --timeout=5m
```

결과:

```text
kueue-controller-manager 1/1 Available
image: registry.k8s.io/kueue/kueue:v0.18.2
Kueue CRD 생성 확인:
- resourceflavors.kueue.x-k8s.io
- clusterqueues.kueue.x-k8s.io
- localqueues.kueue.x-k8s.io
- workloads.kueue.x-k8s.io
```

설치 중 관찰:

```text
Warning: unrecognized format "int64"
Warning: unrecognized format "int32"
```

판단:

```text
경고는 있었지만 CRD와 controller는 정상 설치됐다.
실제 운영 이슈로 분리할 정도는 아니고, 설치 로그 관찰 사항으로 기록한다.
```

---

## 2. manifest 구성

작성 위치:

```text
kubernetes/multicluster/karmada/manifests/demo-kueue-datax/
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
Kueue CRD는 이번 실험에서 datax에만 설치했다.
따라서 ResourceFlavor/ClusterQueue/LocalQueue는 Karmada API Server가 아니라 datax에 직접 적용한다.
Karmada API Server에는 일반 Kubernetes Job과 PropagationPolicy만 적용한다.
```

---

## 3. dry-run 이슈

처음에는 디렉터리 전체를 `server dry-run`으로 검증했다.

```bash
kubectl --context kind-datax apply --dry-run=server   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/member/
```

결과:

```text
namespace/demo-kueue-datax created (server dry run)
resourceflavor.kueue.x-k8s.io/datax-default created (server dry run)
clusterqueue.kueue.x-k8s.io/datax-cpu-queue created (server dry run)
Error from server (NotFound): namespaces "demo-kueue-datax" not found
```

Karmada 쪽도 namespace와 namespaced Job/Policy를 한 번에 server dry-run하면 같은 문제가 생겼다.

판단:

```text
manifest 문제가 아니라 server dry-run이 앞선 Namespace 생성 결과를 실제 저장하지 않기 때문에 생긴 순서 문제다.
검증/적용은 Namespace를 먼저 만들고 나머지 namespaced resource를 적용하는 방식으로 진행한다.
```

---

## 4. datax에 Kueue queue 생성

명령:

```bash
kubectl --context kind-datax apply   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/member/00-namespace.yaml

kubectl --context kind-datax apply --dry-run=server   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/member/10-kueue-queues.yaml

kubectl --context kind-datax apply   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/member/10-kueue-queues.yaml
```

결과:

```text
resourceflavor.kueue.x-k8s.io/datax-default created
clusterqueue.kueue.x-k8s.io/datax-cpu-queue created
localqueue.kueue.x-k8s.io/datax-user-queue created
```

Queue 설정:

```text
ClusterQueue: datax-cpu-queue
LocalQueue: datax-user-queue
nominalQuota: cpu=1, memory=256Mi
```

---

## 5. Karmada로 Job 2개를 datax에 전파

Karmada API Server에 Namespace를 먼저 만든 뒤 나머지를 적용했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/karmada/00-namespace.yaml

kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/karmada/01-cluster-propagation-policy-namespace.yaml   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/karmada/10-job-a.yaml   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/karmada/11-job-b.yaml   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/karmada/30-propagation-policy.yaml
```

Job 설정:

```text
demo-kueue-hold-a: cpu=1, memory=64Mi, sleep 600
demo-kueue-hold-b: cpu=1, memory=64Mi, sleep 600
queue label: kueue.x-k8s.io/queue-name=datax-user-queue
```

PropagationPolicy:

```text
clusterNames: datax
```

---

## 6. 결과 1. Karmada는 둘 다 datax로 전파

Karmada API Server 확인:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config   -n demo-kueue-datax get job,propagationpolicy,rb -o wide
```

결과:

```text
job.batch/demo-kueue-hold-a Running
job.batch/demo-kueue-hold-b Running
resourcebinding demo-kueue-hold-a-job SCHEDULED=True FULLYAPPLIED=True
resourcebinding demo-kueue-hold-b-job SCHEDULED=True FULLYAPPLIED=True
```

판단:

```text
Karmada 관점에서는 두 Job 모두 datax에 전파됐다.
다만 이 상태만 보면 Kueue 때문에 Job B가 member에서 Suspended 상태인지는 바로 보이지 않는다.
```

---

## 7. 결과 2. datax의 Kueue가 quota로 하나만 admitted

DataX에서 Kueue Workload 확인:

```bash
kubectl --context kind-datax -n demo-kueue-datax get workloads -o wide
```

결과:

```text
job-demo-kueue-hold-a-4e404   datax-user-queue   datax-cpu-queue   True
job-demo-kueue-hold-b-dbaa4   datax-user-queue
```

DataX Job/Pod 확인:

```bash
kubectl --context kind-datax -n demo-kueue-datax get job,pods -o wide
```

결과:

```text
job.batch/demo-kueue-hold-a   Running
job.batch/demo-kueue-hold-b   Suspended
pod/demo-kueue-hold-a-*       Running
```

Queue 확인:

```bash
kubectl --context kind-datax get clusterqueue datax-cpu-queue -o wide
kubectl --context kind-datax -n demo-kueue-datax get localqueue datax-user-queue -o wide
```

결과:

```text
PENDING WORKLOADS=1
ADMITTED WORKLOADS=1
```

판단:

```text
Kueue가 datax 내부 quota cpu=1을 기준으로 Job A만 admitted했고, Job B는 pending/Suspended 상태로 유지했다.
즉 Karmada placement와 Kueue admission은 분리되어 동작한다.
```

---

## 8. 결과 3. admitted Job 삭제 후 pending Job admitted

Job A를 Karmada API Server에서 삭제했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config   -n demo-kueue-datax delete job demo-kueue-hold-a
```

15초 후 결과:

```text
DataX Kueue workloads:
job-demo-kueue-hold-b-dbaa4   datax-user-queue   datax-cpu-queue   True

DataX jobs:
job.batch/demo-kueue-hold-b   Running

DataX queues:
PENDING WORKLOADS=0
ADMITTED WORKLOADS=1
```

판단:

```text
Job A가 삭제되어 quota가 반환되자 Job B가 admitted 됐다.
Kueue queue가 정상적으로 pending -> admitted 전환을 수행했다.
```

---

## 9. 정리

실험 Job과 queue 리소스는 삭제하고, Kueue 설치만 datax에 남겼다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/karmada/   --ignore-not-found

kubectl --context kind-datax delete   -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/member/   --ignore-not-found
```

최종 상태:

```text
Karmada demo namespace/resource: 삭제됨
DataX demo namespace/queue/resource: 삭제됨
Kueue controller on datax: Running 유지
```

---

## 성공/실패 판단

```text
Kueue v0.18.2 datax 설치: 성공
Kueue queue 생성: 성공
Karmada Job -> datax 전파: 성공
Kueue quota로 1개 admitted / 1개 pending: 성공
admitted Job 삭제 후 pending Job admitted: 성공
Karmada API만 보면 member Kueue pending 상태가 숨겨지는 관찰: 중요
server dry-run namespace 순서 이슈: 관찰/기록 완료
실험 리소스 cleanup: 성공
```

---

## ScaleX-POD에 주는 의미

```text
1. Karmada와 Kueue는 같은 일을 하는 도구가 아니다.
2. Karmada는 어느 cluster에 보낼지 결정한다.
3. Kueue는 선택된 cluster 내부에서 Job admission, quota, pending 순서를 제어한다.
4. DataX/TwinX에서 AI/batch Job이 많아질수록 Kueue가 필요하다.
5. Karmada API Server의 Job/ResourceBinding 상태만 보면 Kueue pending/Suspended 상태를 놓칠 수 있다.
6. 운영 관측은 Karmada ResourceBinding + member Kueue Workload/ClusterQueue/LocalQueue를 같이 봐야 한다.
7. 처음부터 Kueue MultiKueue와 Karmada를 겹치게 쓰지 말고, local Kueue부터 검증한다.
```

---

## 다음 액션

```text
1. ScaleX-POD 이전 checklist 작성
2. Kueue 관측/알림 항목 정리
3. Kueue를 ArgoCD로 member cluster에 배포하는 GitOps 구조 검토
4. 필요 시 Kueue MultiKueue와 Karmada 역할 충돌 여부 별도 실험
```
