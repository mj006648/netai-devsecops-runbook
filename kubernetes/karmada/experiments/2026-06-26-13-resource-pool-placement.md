# 실험 13. Resource Pool member cluster와 fallback placement

## 목적

실험 12에서는 `twinx`, `edgex`, `datax`의 role label을 기준으로 render/edge/data workload를 배치했다.
이번 실험은 ScaleX-POD의 `Resource Pool` 역할을 `poolx` kind member cluster로 추가하고, general workload와 fallback workload를 label 기반으로 배치할 수 있는지 확인한다.

ScaleX-POD 기준 의미:

```text
TwinX / EdgeX / DataX 외에 범용 fallback pool을 두고,
일반 workload 또는 overflow/fallback workload를 Resource Pool로 보낼 수 있는지 검증한다.
```

---

## 가설

```text
Resource Pool member cluster에 scalex.io/role=resource-pool, scalex.io/pool=general label을 부여하면,
Karmada placement에서 general workload는 poolx에만 배치하고,
render fallback workload는 TwinX/EdgeX/Resource Pool에 weight 기반으로 분산할 수 있다.
```

---

## poolx member cluster 생성

기존 lab member:

```text
- twinx
- edgex
- datax
```

추가 member:

```text
- poolx
```

### 실행 명령

kind cluster 생성:

```bash
kind create cluster --name poolx
```

결과:

```text
Creating cluster "poolx" ...
✓ Ensuring node image (kindest/node:v1.34.0)
✓ Preparing nodes
✓ Writing configuration
✓ Starting control-plane
✓ Installing CNI
✓ Installing StorageClass
Set kubectl context to "kind-poolx"
```

주의:

```text
kind create cluster는 current-context를 새 cluster인 kind-poolx로 바꾼다.
이전 실험에서 context 혼동 문제가 있었으므로, 등록 후 current-context를 kind-tower로 되돌렸다.
```

poolx Docker IP 확인:

```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' poolx-control-plane
```

결과:

```text
172.18.0.6
```

Karmada Push mode 등록용 kubeconfig 생성:

```bash
mkdir -p /tmp/karmada-kind-kubeconfigs
kind get kubeconfig --name poolx > /tmp/karmada-kind-kubeconfigs/poolx.kubeconfig

kubectl --kubeconfig /tmp/karmada-kind-kubeconfigs/poolx.kubeconfig \
  config set-cluster kind-poolx \
  --server=https://172.18.0.6:6443 \
  --tls-server-name=poolx-control-plane
```

host에서 kubeconfig 확인:

```bash
kubectl --kubeconfig /tmp/karmada-kind-kubeconfigs/poolx.kubeconfig \
  --context kind-poolx get nodes -o wide
```

결과:

```text
NAME                  STATUS   ROLES           VERSION   INTERNAL-IP
poolx-control-plane   Ready    control-plane   v1.34.0   172.18.0.6
```

Karmada join:

```bash
kubectl karmada --kubeconfig ~/.kube/karmada-apiserver.config join poolx \
  --cluster-kubeconfig /tmp/karmada-kind-kubeconfigs/poolx.kubeconfig \
  --cluster-context kind-poolx
```

결과:

```text
cluster(poolx) is joined successfully
```

current-context 복구:

```bash
kubectl config use-context kind-tower
```

---

## poolx label

실행 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config label cluster poolx \
  scalex.io/role=resource-pool \
  scalex.io/pool=general \
  scalex.io/workload=general \
  scalex.io/fallback=true \
  --overwrite
```

최종 label:

```text
poolx:
- scalex.io/role=resource-pool
- scalex.io/pool=general
- scalex.io/workload=general
- scalex.io/fallback=true
```

Karmada cluster 상태:

```text
NAME    VERSION   MODE   READY
poolx   v1.34.0   Push   True
```

---

## 전체 cluster label

```text
twinx:
- scalex.io/role=gpu-render
- scalex.io/pool=gpu

edgex:
- scalex.io/role=edge-gpu
- scalex.io/pool=gpu
- scalex.io/location=edge

datax:
- scalex.io/role=data
- scalex.io/storage=ssd
- scalex.io/workload=data

poolx:
- scalex.io/role=resource-pool
- scalex.io/pool=general
- scalex.io/workload=general
- scalex.io/fallback=true
```

---

## 매니페스트

```text
kubernetes/karmada/manifests/demo-resource-pool-placement/
  00-namespace.yaml
  10-general-deployment.yaml
  11-render-fallback-deployment.yaml
  20-general-service.yaml
  21-render-fallback-service.yaml
  30-general-propagation-policy.yaml
  31-render-fallback-propagation-policy.yaml
```

workload:

```text
general:
  Deployment: demo-pool-general-nginx
  replicas: 2
  후보: scalex.io/role=resource-pool
  기대: poolx=2

render fallback:
  Deployment: demo-pool-render-fallback-nginx
  replicas: 5
  후보: scalex.io/pool in (gpu, general)
  weight: gpu-render=3, edge-gpu=1, resource-pool=1
  기대: twinx=3, edgex=1, poolx=1
```

---

## 핵심 policy

### general workload

```yaml
placement:
  clusterAffinity:
    labelSelector:
      matchLabels:
        scalex.io/role: resource-pool
  replicaScheduling:
    replicaSchedulingType: Divided
    replicaDivisionPreference: Weighted
    weightPreference:
      staticWeightList:
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/role: resource-pool
          weight: 1
```

### render fallback workload

```yaml
placement:
  clusterAffinity:
    labelSelector:
      matchExpressions:
        - key: scalex.io/pool
          operator: In
          values:
            - gpu
            - general
  replicaScheduling:
    replicaSchedulingType: Divided
    replicaDivisionPreference: Weighted
    weightPreference:
      staticWeightList:
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/role: gpu-render
          weight: 3
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/role: edge-gpu
          weight: 1
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/role: resource-pool
          weight: 1
```

---

## 실행 명령

client dry-run:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=client \
  -f kubernetes/karmada/manifests/demo-resource-pool-placement/
```

적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-resource-pool-placement/
```

적용 시각:

```text
2026-06-26T04:37:00Z
```

적용 결과:

```text
namespace/demo-resource-pool created
deployment.apps/demo-pool-general-nginx created
deployment.apps/demo-pool-render-fallback-nginx created
service/demo-pool-general-nginx created
service/demo-pool-render-fallback-nginx created
propagationpolicy.policy.karmada.io/demo-pool-general-policy created
propagationpolicy.policy.karmada.io/demo-pool-render-fallback-policy created
```

---

## 확인 명령

ResourceBinding 확인:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb -n demo-resource-pool -o wide

for name in demo-pool-general-nginx demo-pool-render-fallback-nginx; do
  echo "### $name"
  kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb \
    -n demo-resource-pool ${name}-deployment \
    -o jsonpath='{range .spec.clusters[*]}{.name}{" replicas="}{.replicas}{"\n"}{end}{"lastScheduledTime="}{.status.lastScheduledTime}{"\n"}{"gracefulEvictionTasks="}{.spec.gracefulEvictionTasks}{"\n"}'
done
```

member cluster 확인:

```bash
for c in twinx edgex datax poolx; do
  echo "--- $c"
  kubectl --context kind-$c get deploy,pods,svc -n demo-resource-pool -o wide
 done
```

---

## 기대 결과

| workload | 기대 배치 |
| --- | --- |
| general | `poolx=2` |
| render fallback | `twinx=3`, `edgex=1`, `poolx=1`, `datax=0` |

---

## 실제 결과

### 1. ResourceBinding

최종 ResourceBinding은 모두 `SCHEDULED=True`, `FULLYAPPLIED=True`가 되었다.

```text
NAME                                         SCHEDULED   FULLYAPPLIED
demo-pool-general-nginx-deployment           True        True
demo-pool-general-nginx-service              True        True
demo-pool-render-fallback-nginx-deployment   True        True
demo-pool-render-fallback-nginx-service      True        True
```

Deployment replica 배치:

```text
general:
- poolx replicas=2

render fallback:
- edgex replicas=1
- poolx replicas=1
- twinx replicas=3
```

`gracefulEvictionTasks`는 모두 비어 있었다.

### 2. member cluster 상태

`twinx`:

```text
demo-pool-render-fallback-nginx 3/3
```

`edgex`:

```text
demo-pool-render-fallback-nginx 1/1
```

`datax`:

```text
No resources in demo-resource-pool namespace
```

`poolx`:

```text
demo-pool-general-nginx           2/2
demo-pool-render-fallback-nginx   1/1
```

### 3. Service 전파

Service도 workload placement와 같은 cluster에만 생성되었다.

`twinx`:

```text
demo-pool-render-fallback-nginx
```

`edgex`:

```text
demo-pool-render-fallback-nginx
```

`poolx`:

```text
demo-pool-general-nginx
demo-pool-render-fallback-nginx
```

---

## 성공/실패 판단

| 검증 항목 | 기대 결과 | 실제 결과 | 판단 |
| --- | --- | --- | --- |
| poolx 생성 | kind cluster 생성 | 생성 완료 | 성공 |
| poolx join | Karmada Push member 등록 | 등록 완료 | 성공 |
| poolx label | resource-pool/general/fallback label | 적용 완료 | 성공 |
| general placement | poolx=2 | poolx=2 | 성공 |
| render fallback placement | twinx=3, edgex=1, poolx=1 | twinx=3, edgex=1, poolx=1 | 성공 |
| datax 제외 | render fallback에서 datax 제외 | datax 리소스 없음 | 성공 |
| current-context 복구 | kind-tower | kind-tower | 성공 |

---

## 문제/에러

이번 실험에서 Karmada 기능 실패는 없었다.

주의할 점은 있다.

### 1. kind create cluster가 current-context를 바꾼다

`kind create cluster --name poolx` 실행 후 current-context가 `kind-poolx`로 바뀌었다.

```text
current-context before restore: kind-poolx
current-context after restore : kind-tower
```

이전 실험에서 current context 혼동이 있었으므로, 앞으로 kind cluster를 새로 만들면 반드시 current-context를 다시 확인한다.

### 2. Push mode API endpoint는 Docker network IP로 맞춰야 한다

Karmada Push mode에서 `poolx` API endpoint는 다음으로 등록했다.

```text
https://172.18.0.6:6443
```

host/karmada control plane 접근성을 모두 고려해야 한다.

### 3. Resource Pool은 실제 운영에서 별도 capacity 정책이 필요하다

이번 실험은 placement label만 검증했다.
실제 운영에서는 다음이 추가로 필요하다.

```text
- Resource Pool 노드 capacity
- GPU/CPU/Memory quota
- fallback workload 우선순위
- noisy neighbor 방지
- clusterTolerations / taint 정책
```

---

## ScaleX-POD에 주는 의미

이번 실험으로 확인한 점:

```text
1. Resource Pool을 독립 member cluster로 추가할 수 있다.
2. general workload는 Resource Pool 전용으로 보낼 수 있다.
3. render workload도 TwinX/EdgeX 우선 + Resource Pool fallback 형태로 분산할 수 있다.
4. DataX는 data 전용 label만 유지하면 render/general fallback에서 제외할 수 있다.
```

ScaleX-POD placement 후보:

```text
render/gpu workload:
  후보: scalex.io/pool in (gpu, general)
  우선: gpu-render weight 높게
  fallback: edge-gpu/resource-pool weight 낮게

general workload:
  후보: scalex.io/role=resource-pool

data workload:
  후보: scalex.io/workload=data
```

운영 설계 포인트:

```text
Resource Pool은 단순한 나머지 cluster가 아니라,
명시적인 role/pool/fallback label을 가진 운영 대상이어야 한다.
```

---

## 다음 액션

- OverridePolicy image/storageClass 실험
- Resource Pool fallback 상태에서 WorkloadRebalancer 동작 확인
- scheduler-estimator 정리
- spreadConstraints 실험
- ArgoCD -> Karmada API Server GitOps 흐름 검증
