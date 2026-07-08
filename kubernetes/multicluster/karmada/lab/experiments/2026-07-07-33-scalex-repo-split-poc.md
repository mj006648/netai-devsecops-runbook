# 실험 33. ScaleX repo split PoC: `scalex-federation` federation + `*-k8s` cluster-local

## 목적

ScaleX-POD 운영 구조를 다음처럼 나눌 수 있는지 kind lab에서 임시 repo로 검증한다.

```text
TowerX(tower-k8s)
  -> TowerX ArgoCD
    ├─ scalex-federation -> Karmada API Server -> EdgeX / DataX / TwinX
    ├─ twinx-k8s  -> TwinX cluster
    ├─ datax-k8s  -> DataX cluster
    └─ edgex-k8s  -> EdgeX cluster
```

이번 실험의 핵심 질문은 다음이다.

```text
1. scalex-federation는 멀티클러스터에 전파할 resource + Karmada policy repo로 둘 수 있는가?
2. twinx-k8s/datax-k8s/edgex-k8s는 mobilex-k8s와 같은 cluster-local repo로 둘 수 있는가?
3. federation 리소스와 cluster-local 리소스를 분리하면 소유권 충돌 없이 공존하는가?
```

---

## 설계 철학

### TowerX / `tower-k8s` / `scalex-federation`

TowerX는 ScaleX-POD의 단일 GitOps 제어 계층이다.

```text
TowerX
  - ArgoCD 1개
  - Karmada Control Plane
```

`tower-k8s`는 TowerX 제어 클러스터 자체를 담당한다.

```text
- TowerX ArgoCD
- Karmada 설치 기반
- AppProject
- root Application
- repo/cluster destination 연결
```

`scalex-federation`는 다음을 담당한다.

```text
- 전체 멀티클러스터에 공통으로 전파해야 하는 리소스
- 멀티클러스터 workload
- Karmada PropagationPolicy / ClusterPropagationPolicy
- Karmada OverridePolicy / ClusterOverridePolicy
- WorkloadRebalancer
- cluster placement / label convention
```

정의:

```text
scalex-federation = 어떤 리소스를 어느 클러스터들에 전파할 것인가?
```

### EdgeX/DataX/TwinX / `*-k8s`

각 member cluster는 자기 내부 전용 GitOps repo를 가진다.
ArgoCD 서버는 각 member cluster에 따로 두지 않고 TowerX의 단일 ArgoCD를 사용한다.

```text
EdgeX(edgex-k8s) -> TowerX ArgoCD -> EdgeX cluster
DataX(datax-k8s) -> TowerX ArgoCD -> DataX cluster
TwinX(twinx-k8s) -> TowerX ArgoCD -> TwinX cluster
```

각 `*-k8s`는 다음을 담당한다.

```text
- 해당 클러스터 안에서만 쓰는 앱
- CNI / CSI / StorageClass / Ingress / GPU Operator 같은 cluster-local platform
- cluster-local namespace / RBAC / values / patches
```

정의:

```text
cluster-k8s = 이 클러스터에 어떤 앱을 설치할 것인가?
```


### 배포 위치 분리 기준

이번 구조에서 가장 중요한 운영 규칙은 앱을 “전체/공통”, “cluster-local”로 먼저 나누는 것이다.

| 리소스 성격 | 위치 | 이유 |
| --- | --- | --- |
| 전체 공통 리소스 | `scalex-federation` | Karmada가 여러 member cluster로 전파해야 함 |
| TwinX+EdgeX 같이 여러 cluster를 같이 쓰는 workload | `scalex-federation` | replica weight, placement, override가 필요함 |
| EdgeX에서만 뜰 앱 | `edgex-k8s` | Karmada 없이 EdgeX destination에 직접 sync하면 충분함 |
| MobileX에서만 뜰 앱 | `mobilex-k8s` | 기존 MobileX preset처럼 MobileX 전용 설정/patch로 관리 |
| TwinX에서만 뜰 앱 | `twinx-k8s` | TwinX 전용 앱은 cluster-local 소유가 명확함 |
| DataX에서만 뜰 앱 | `datax-k8s` | DataX data/batch/analytics 앱은 DataX repo가 소유 |

따라서 `scalex-federation`는 “모든 앱을 모으는 repo”가 아니라, Karmada가 필요한 리소스만 담는 federation repo다.

### 단일 소유권 원칙

같은 live resource를 Karmada 전파 경로와 TowerX ArgoCD의 직접 cluster destination 경로가 동시에 관리하면 안 된다.

```text
금지 예시:
TowerX ArgoCD -> Karmada API Server -> TwinX에 GPU Operator 전파
TowerX ArgoCD -> TwinX cluster 직접 destination -> 같은 GPU Operator 설치
```

이 경우 두 controller가 같은 resource를 reconcile하면서 충돌할 수 있다.

운영 원칙:

```text
1. 멀티클러스터 전파 리소스는 scalex-federation만 관리한다.
2. cluster-local 리소스는 해당 *-k8s만 관리한다.
3. 같은 namespace/name/kind를 두 계층에 중복 선언하지 않는다.
4. Karmada로 전파한 리소스는 member cluster local repo에 다시 넣지 않는다.
```

---

## 실험 환경

실행 위치:

```text
host: master
kind clusters: tower, twinx, edgex, datax, poolx, pullx
Karmada API kubeconfig: ~/.kube/karmada-apiserver.config
```

Karmada member label 중 이번 실험에 사용한 것:

```text
twinx: scalex.io/pool=gpu, scalex.io/role=gpu-render
edgex: scalex.io/pool=gpu, scalex.io/role=edge-gpu
datax: scalex.io/pool=data, scalex.io/role=data
```

주의:

```text
poolx/pullx는 이번 repo split 판단에는 필수 요소가 아니므로 사용하지 않았다.
```

---

## 임시 repo 생성

실제 GitHub repo를 만들지 않고 `/tmp`에 임시 Git repo 4개를 생성했다.

```text
/tmp/scalex-temp-repos/scalex-federation
/tmp/scalex-temp-repos/twinx-k8s
/tmp/scalex-temp-repos/datax-k8s
/tmp/scalex-temp-repos/edgex-k8s
```

각 repo는 `git init`과 최초 commit까지 수행했다.

```text
scalex-federation 8318d9f
twinx-k8s  e82bfb3
datax-k8s  974d1cc
edgex-k8s  3bf4221
```

---

## 임시 repo 구조

### `scalex-federation`

```text
scalex-federation/
  manifest.yaml
  federation/
    clusters.yaml
    placements.yaml
    kustomization.yaml
    00-namespaces/
      namespaces.yaml
      namespace-policies.yaml
    10-apps/
      render-demo/app.yaml
      data-demo/app.yaml
  docs/
    ownership.md
```

`scalex-federation/federation` 렌더링 결과:

```text
2 ClusterPropagationPolicy
2 Namespace
2 PropagationPolicy
1 Deployment
1 Service
1 Job
```

### `twinx-k8s`, `datax-k8s`, `edgex-k8s`

각 repo는 cluster-local demo resource만 가진다.

```text
twinx-k8s/apps/local-demo/
datax-k8s/apps/local-demo/
edgex-k8s/apps/local-demo/
```

각 repo는 해당 cluster에만 적용되는 ConfigMap을 생성한다.

---

## 실행 절차

### 1. 기존 임시 resource 정리

`tmp-*` 이름을 가진 이전 실험 리소스만 정리했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete propagationpolicy -n tmp-fed-render tmp-render-demo-gpu-placement --ignore-not-found=true
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete propagationpolicy -n tmp-fed-data tmp-data-demo-datax-only --ignore-not-found=true
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete deploy,svc -n tmp-fed-render --all --ignore-not-found=true
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete job -n tmp-fed-data --all --ignore-not-found=true
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete clusterpropagationpolicy tmp-fed-render-namespace tmp-fed-data-namespace --ignore-not-found=true
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete ns tmp-fed-render tmp-fed-data --ignore-not-found=true
```

### 2. `scalex-federation` namespace phase 적용

Karmada API Server에도 namespaced resource를 만들 namespace가 먼저 필요하다.
따라서 namespace는 별도 phase로 먼저 적용했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  apply -f /tmp/scalex-temp-repos/scalex-federation/federation/00-namespaces/namespaces.yaml
```

결과:

```text
namespace/tmp-fed-render created
namespace/tmp-fed-data created
```

### 3. `scalex-federation` policy/app dry-run

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=server \
  -f /tmp/scalex-temp-repos/scalex-federation/federation/00-namespaces/namespace-policies.yaml
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=server \
  -f /tmp/scalex-temp-repos/scalex-federation/federation/10-apps/render-demo/app.yaml
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=server \
  -f /tmp/scalex-temp-repos/scalex-federation/federation/10-apps/data-demo/app.yaml
```

결과:

```text
clusterpropagationpolicy.policy.karmada.io/tmp-fed-render-namespace created (server dry run)
clusterpropagationpolicy.policy.karmada.io/tmp-fed-data-namespace created (server dry run)
deployment.apps/tmp-render-demo created (server dry run)
service/tmp-render-demo created (server dry run)
propagationpolicy.policy.karmada.io/tmp-render-demo-gpu-placement created (server dry run)
job.batch/tmp-data-demo created (server dry run)
propagationpolicy.policy.karmada.io/tmp-data-demo-datax-only created (server dry run)
```

### 4. `scalex-federation` federation 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f /tmp/scalex-temp-repos/scalex-federation/federation/00-namespaces/namespace-policies.yaml
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f /tmp/scalex-temp-repos/scalex-federation/federation/10-apps/render-demo/app.yaml
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f /tmp/scalex-temp-repos/scalex-federation/federation/10-apps/data-demo/app.yaml
```

### 5. cluster-local repo 적용

이번 실험에서는 TowerX ArgoCD가 각 member cluster destination으로 직접 sync하는 경로를 `kubectl apply -k`로 대체했다.
이는 repo/ownership split 검증이 목적이기 때문이다.

```bash
kubectl --context kind-twinx apply -k /tmp/scalex-temp-repos/twinx-k8s/apps/local-demo
kubectl --context kind-datax apply -k /tmp/scalex-temp-repos/datax-k8s/apps/local-demo
kubectl --context kind-edgex apply -k /tmp/scalex-temp-repos/edgex-k8s/apps/local-demo
```

---

## 결과 1. `scalex-federation` federation 전파

### render-demo

`tmp-render-demo`는 GPU pool에 배치하고, weight를 `gpu-render:edge-gpu = 3:1`로 설정했다.

ResourceBinding 결과:

```text
tmp-render-demo-deployment  edgex,twinx  FullyApplied=True
tmp-render-demo-service     edgex,twinx  FullyApplied=True
```

member cluster 결과:

```text
TwinX: tmp-render-demo replicas 3/3 Running
EdgeX: tmp-render-demo replicas 1/1 Running
DataX: 없음
```

이는 `scalex-federation`가 멀티클러스터 placement repo로 동작할 수 있음을 보여준다.

### data-demo

`tmp-data-demo` Job은 `clusterNames: [datax]`로 지정했다.

ResourceBinding 결과:

```text
tmp-data-demo-job  datax  FullyApplied=True
```

member cluster 결과:

```text
DataX: tmp-data-demo Job Running, Pod Running
TwinX/EdgeX: 없음
```

---

## 결과 2. `*-k8s` cluster-local 적용

각 cluster-local repo가 자기 cluster에만 리소스를 만들었다.

```text
TwinX:
  namespace: kube-system
  configmap: tmp-twinx-local
  owner: twinx-k8s

DataX:
  namespace: datax-platform
  configmap: tmp-datax-local
  owner: datax-k8s

EdgeX:
  namespace: edgex-runtime
  configmap: tmp-edgex-local
  owner: edgex-k8s
```

확인 결과:

```text
twinx-local owner=twinx-k8s
datax-local owner=datax-k8s
edgex-local owner=edgex-k8s
```

---

## 결과 3. node scheduling

Karmada는 member cluster 선택까지만 담당했고, 각 member cluster 내부에서는 기본 Kubernetes scheduler가 node를 선택했다.

```text
TwinX pod -> twinx-control-plane
EdgeX pod -> edgex-control-plane
DataX pod -> datax-control-plane
```

따라서 기본 흐름은 다음처럼 검증됐다.

```text
scalex-federation
  -> Karmada API Server
    -> TwinX / EdgeX / DataX
      -> kube-scheduler
        -> kubelet
```

Kueue는 이번 실험에 넣지 않았다.
Kueue는 Job/GPU/batch workload가 많아지고 queue/admission/quota가 필요할 때 별도 optional layer로 도입한다.

---

## 확인된 보정점

### Namespace phase 분리 필요

Karmada API Server에 namespaced resource를 만들려면 Karmada API Server 쪽 namespace도 먼저 있어야 한다.
따라서 `scalex-federation`는 다음 구조가 안전하다.

```text
scalex-federation/
  federation/
    00-namespaces/
    10-apps/
    20-policies/
    30-overrides/
```

또는 ArgoCD sync wave를 사용한다.

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-10" # Namespace
```

### Resource ownership label 권장

운영 시 다음 label을 모든 리소스에 붙이는 것이 좋다.

```yaml
scalex.io/management-plane: federation
```

cluster-local 리소스에는 다음처럼 붙인다.

```yaml
scalex.io/management-plane: twinx-local
scalex.io/management-plane: datax-local
scalex.io/management-plane: edgex-local
```

---

## 성공 판단

성공.

```text
1. scalex-federation는 멀티클러스터 전파 resource + Karmada policy repo로 동작 가능하다.
2. twinx-k8s/datax-k8s/edgex-k8s는 cluster-local repo로 분리 가능하다.
3. federation 리소스와 cluster-local 리소스를 분리하면 소유권 충돌 없이 공존한다.
4. Karmada는 cluster placement까지만 담당하고, node placement는 member cluster kube-scheduler가 담당한다.
5. Kueue 없이도 기본 멀티클러스터 전파와 node scheduling 흐름은 동작한다.
```

---

## ScaleX-POD에 주는 의미

최종 repo 전략은 다음처럼 잡는다.

```text
SmartX-Team/tower-k8s
  = TowerX 제어 클러스터 repo
  = TowerX ArgoCD, Karmada 설치 기반, AppProject, root Application, repo/cluster 연결 관리

SmartX-Team/scalex-federation
  = Karmada 멀티클러스터 전용 repo
  = 멀티클러스터에 전파할 resource + PropagationPolicy/OverridePolicy 관리

SmartX-Team/twinx-k8s
SmartX-Team/datax-k8s
SmartX-Team/edgex-k8s
  = TowerX 단일 ArgoCD가 각 member cluster destination으로 sync하는 단일 클러스터 repo
  = 이 클러스터에 어떤 앱을 설치할 것인가 관리
```

운영 원칙:

```text
TowerX(tower-k8s): 제어 클러스터와 단일 ArgoCD bootstrap 담당
ScaleX(scalex-federation): 전체 멀티클러스터에 공통으로 전파해야 하는 리소스나 멀티클러스터 workload 전파 담당
EdgeX/DataX/TwinX(*-k8s): 각 클러스터 내부 전용 리소스 담당
같은 리소스는 Karmada 전파 경로와 직접 cluster destination 경로가 동시에 관리하지 않음
```

---

## 남은 확인 사항

이번 실험은 repo split과 Karmada/member 동작을 검증했다.
다만 다음은 실제 운영 전 별도 bootstrap 작업으로 남긴다.

```text
1. 실제 GitHub repo 생성: tower-k8s, scalex-federation, twinx-k8s, datax-k8s, edgex-k8s
2. TowerX 단일 ArgoCD root Application이 tower-k8s를 바라보도록 설정
3. TowerX ArgoCD child Application이 scalex-federation는 Karmada API Server destination으로 sync하도록 설정
4. TowerX ArgoCD child Application이 twinx/datax/edgex-k8s는 각 member cluster destination으로 sync하도록 설정
5. AppProject/source/destination/resource whitelist 적용
6. prune=false에서 시작 후 app별로 prune=true 승격
```

기능 관점에서는 추가 핵심 검증은 필요하지 않다.
남은 작업은 실제 repo/bootstrap/운영 안전장치 적용이다.
