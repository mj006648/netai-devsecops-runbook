# 실험 24. ArgoCD ApplicationSet으로 여러 Karmada app 생성

## 목적

실험 18~19에서는 ArgoCD `Application` 하나가 Karmada API Server를 destination으로 사용할 수 있고, self-heal/prune/restore 흐름도 동작함을 확인했다.
이번 실험은 ArgoCD `ApplicationSet`을 사용해 여러 Karmada Application을 한 번에 생성하고, 각 Application이 Karmada API Server로 sync되어 member cluster까지 전파되는지 확인한다.

ScaleX-POD 기준 목표:

```text
GitHub repo
  -> ArgoCD ApplicationSet on Tower
    -> 여러 ArgoCD Application 생성
      -> Karmada API Server
        -> EdgeX / Pull Edge / DataX 등 member cluster 전파
```

---

## 가설

```text
1. ArgoCD ApplicationSet controller가 설치되어 있으면 하나의 ApplicationSet으로 여러 Application을 생성할 수 있다.
2. 생성된 Application의 destination을 Karmada API Server로 지정하면 일반 Application과 동일하게 sync된다.
3. Karmada policy에 따라 edge workload는 edgex/pullx로, data workload는 datax로 전파된다.
4. ApplicationSet이 생성한 Application에는 ownerReference가 붙어 운영 단위가 ApplicationSet으로 묶인다.
```

---

## 사전 상태

ArgoCD CRD/controller:

```text
applicationsets.argoproj.io present
applications.argoproj.io present
appprojects.argoproj.io present
argocd-applicationset-controller 1/1 Running
```

기존 Application:

```text
karmada-spread-constraints Synced/Healthy
karmada-prune-rollback     Synced/Healthy
```

기존 ApplicationSet:

```text
없음
```

---

## 단계 1. ApplicationSet용 demo source 작성

기존 Application과 리소스 충돌을 피하기 위해 전용 demo manifest를 새로 만들었다.

```text
kubernetes/multicluster/karmada/manifests/demo-appset-edge/
  00-namespace.yaml
  10-deployment.yaml
  20-service.yaml
  30-propagation-policy.yaml

kubernetes/multicluster/karmada/manifests/demo-appset-data/
  00-namespace.yaml
  10-deployment.yaml
  20-service.yaml
  30-propagation-policy.yaml
```

### edge app

```text
namespace : demo-appset-edge
Deployment: demo-appset-edge-nginx
replicas  : 2
selector  : scalex.io/location=edge
expected  : edgex=1, pullx=1
```

`pullx`는 Pull mode cluster이므로, 이 app은 ApplicationSet -> Karmada -> Push/Pull 혼합 전파를 확인한다.

### data app

```text
namespace : demo-appset-data
Deployment: demo-appset-data-nginx
replicas  : 2
selector  : scalex.io/workload=data
expected  : datax=2
```

---

## 단계 2. ApplicationSet 작성

매니페스트 위치:

```text
kubernetes/multicluster/karmada/argocd/applicationsets/karmada-demo-appset.yaml
```

핵심 구조:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: karmada-demo-appset
  namespace: argocd
spec:
  generators:
    - list:
        elements:
          - name: edge
            namespace: demo-appset-edge
            path: kubernetes/multicluster/karmada/manifests/demo-appset-edge
          - name: data
            namespace: demo-appset-data
            path: kubernetes/multicluster/karmada/manifests/demo-appset-data
  template:
    metadata:
      name: 'karmada-appset-{{name}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/mj006648/netai-devsecops-runbook.git
        targetRevision: main
        path: '{{path}}'
      destination:
        server: https://karmada-apiserver.karmada-system.svc:5443
        namespace: '{{namespace}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

생성될 Application:

```text
karmada-appset-edge
karmada-appset-data
```

---

## 단계 3. dry-run 검증

처음에는 Karmada API Server에 server dry-run을 시도했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  --dry-run=server \
  -f kubernetes/multicluster/karmada/manifests/demo-appset-edge/
```

결과:

```text
namespace/demo-appset-edge created (server dry run)
Error from server (NotFound): namespaces "demo-appset-edge" not found
```

해석:

```text
server dry-run에서는 Namespace가 실제로 생성되지 않으므로,
같은 디렉터리의 namespaced Deployment/Service/PropagationPolicy 검증이 namespace not found로 실패했다.
실제 apply는 ArgoCD가 sync wave 없이도 순서대로 처리해 성공했지만,
검증 단계에서는 client dry-run 또는 namespace 선생성 후 server dry-run이 필요하다.
```

대체 검증:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  --dry-run=client \
  -f kubernetes/multicluster/karmada/manifests/demo-appset-edge/

kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  --dry-run=client \
  -f kubernetes/multicluster/karmada/manifests/demo-appset-data/

kubectl --context kind-tower apply \
  --dry-run=server \
  -f kubernetes/multicluster/karmada/argocd/applicationsets/karmada-demo-appset.yaml
```

결과:

```text
namespace/demo-appset-edge created (dry run)
deployment.apps/demo-appset-edge-nginx created (dry run)
service/demo-appset-edge-nginx created (dry run)
propagationpolicy.policy.karmada.io/demo-appset-edge-policy created (dry run)

namespace/demo-appset-data created (dry run)
deployment.apps/demo-appset-data-nginx created (dry run)
service/demo-appset-data-nginx created (dry run)
propagationpolicy.policy.karmada.io/demo-appset-data-policy created (dry run)

applicationset.argoproj.io/karmada-demo-appset created (server dry run)
```

---

## 단계 4. source를 main에 먼저 push

ArgoCD는 GitHub `main`에서 manifest를 읽으므로, ApplicationSet 적용 전에 source를 먼저 push했다.

```text
커밋: d713be8 Add Karmada ApplicationSet demo
```

이 순서를 지키지 않으면 ApplicationSet이 생성한 Application이 아직 remote에 없는 path를 읽게 된다.

---

## 단계 5. ApplicationSet 적용

```bash
kubectl --context kind-tower apply \
  -f kubernetes/multicluster/karmada/argocd/applicationsets/karmada-demo-appset.yaml
```

결과:

```text
applicationset.argoproj.io/karmada-demo-appset created
```

10초 후 ApplicationSet 상태:

```text
condition=ErrorOccurred:False:ApplicationSetUpToDate:Successfully generated parameters for all Applications
condition=ParametersGenerated:True:ParametersGenerated:Successfully generated parameters for all Applications
condition=ResourcesUpToDate:True:ApplicationSetUpToDate:ApplicationSet up to date
```

생성된 Application:

```text
karmada-appset-edge Synced Healthy revision=d713be8d64a42eb9bc1fc24be2353c30c0c16e90
karmada-appset-data Synced Healthy revision=d713be8d64a42eb9bc1fc24be2353c30c0c16e90
```

90초 후에도 동일하게 유지됐다.

---

## 단계 6. Karmada API Server 상태 확인

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-appset-edge get deploy,svc,propagationpolicy,rb -o wide

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-appset-data get deploy,svc,propagationpolicy,rb -o wide
```

결과:

```text
demo-appset-edge:
  Deployment/demo-appset-edge-nginx 2/2
  Service/demo-appset-edge-nginx present
  PropagationPolicy/demo-appset-edge-policy present
  ResourceBinding Deployment Scheduled=True FullyApplied=True
  ResourceBinding Service    Scheduled=True FullyApplied=True

demo-appset-data:
  Deployment/demo-appset-data-nginx 2/2
  Service/demo-appset-data-nginx present
  PropagationPolicy/demo-appset-data-policy present
  ResourceBinding Deployment Scheduled=True FullyApplied=True
  ResourceBinding Service    Scheduled=True FullyApplied=True
```

ResourceBinding placement:

```text
edge clusters=edgex:1 pullx:1
edge aggregated=edgex:true:Healthy:1/1 pullx:true:Healthy:1/1

data clusters=datax:2
data aggregated=datax:true:Healthy:2/2
```

---

## 단계 7. member cluster 상태 확인

### edge app

```text
edgex:
  Deployment/demo-appset-edge-nginx 1/1
  Pod 1개 Running
  Service present

pullx:
  Deployment/demo-appset-edge-nginx 1/1
  Pod 1개 Running
  Service present

datax/twinx/poolx:
  demo-appset-edge workload 없음
```

### data app

```text
datax:
  Deployment/demo-appset-data-nginx 2/2
  Pod 2개 Running
  Service present

edgex/pullx/twinx/poolx:
  demo-appset-data workload 없음
```

판단:

```text
ApplicationSet이 생성한 두 Application이 Karmada API Server에 sync됐고,
Karmada가 policy에 따라 Push/Pull member cluster로 전파했다.
```

---

## 단계 8. ApplicationSet ownerReference 확인

생성된 Application에는 ApplicationSet ownerReference가 붙었다.

```yaml
ownerReferences:
  - apiVersion: argoproj.io/v1alpha1
    kind: ApplicationSet
    name: karmada-demo-appset
    controller: true
```

주의:

```text
생성된 Application에는 resources-finalizer.argocd.argoproj.io finalizer도 붙어 있었다.
따라서 Application 삭제/재생성 테스트는 target resource prune까지 일으킬 수 있어 이번 실험에서는 수행하지 않았다.
ApplicationSet 삭제/수정 실험은 prune 영향 범위를 별도 실험으로 분리하는 것이 안전하다.
```

---

## 성공/실패 판단

```text
ApplicationSet CRD/controller 확인: 성공
list generator로 Application 2개 생성: 성공
생성 Application 2개 Synced/Healthy: 성공
Application destination을 Karmada API Server로 지정: 성공
edge workload edgex/pullx 전파: 성공
data workload datax 전파: 성공
ApplicationSet ownerReference 확인: 성공
Application 삭제 재생성 테스트는 finalizer/prune 위험 때문에 생략: 의도적 보류
```

---

## ScaleX-POD에 주는 의미

```text
1. 여러 Karmada app을 개별 Application으로 직접 만들지 않고 ApplicationSet으로 묶을 수 있다.
2. Tower의 ArgoCD는 ApplicationSet으로 TwinX/EdgeX/DataX 계열 app 묶음을 생성하고, 각 app은 Karmada API Server에 제출할 수 있다.
3. Push/Pull member가 섞여 있어도 Karmada placement가 실제 배치를 결정한다.
4. ApplicationSet은 app 묶음 생성/관리 계층이고, cluster 배치 로직은 Karmada 정책에 남는다.
5. ApplicationSet이 생성한 Application 삭제/변경은 prune 영향이 있을 수 있으므로 운영 안전장치가 필요하다.
```

---

## 다음 액션

```text
1. ArgoCD prune 운영 안전장치(AppProject, sync window, branch protection) 정리
2. Pull mode 네트워크 단절/복구 실험
3. 실제 ScaleX-POD 이전 checklist 작성
4. Kueue 조합 검토
5. scheduler-estimator 설치형 실험
```
