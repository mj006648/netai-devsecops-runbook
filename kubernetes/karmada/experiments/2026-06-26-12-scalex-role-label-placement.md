# 실험 12. ScaleX-POD role label 기반 placement

## 목적

지금까지 실험은 주로 `clusterNames`를 직접 지정해서 workload를 배치했다.
이번 실험은 ScaleX-POD 구조에 맞게 Karmada `Cluster` label을 사용해 workload 종류별 후보 cluster를 선택하는 방식을 검증한다.

ScaleX-POD 기준 의미:

```text
TwinX / EdgeX / DataX / Resource Pool을 직접 이름으로 고정하기보다,
cluster role label을 기준으로 workload가 적절한 cluster pool에 배치되도록 만든다.
```

---

## 현재 cluster label

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
```

현재 kind lab에는 별도 `Resource Pool` member cluster가 없다.
이번 실험은 `twinx`, `edgex`, `datax` 3개 member로 ScaleX-POD role placement를 축소 검증한다.

---

## 가설

```text
Karmada PropagationPolicy의 clusterAffinity.labelSelector와 replicaScheduling targetCluster.labelSelector를 조합하면,
workload 목적별로 TwinX/EdgeX/DataX 후보 cluster를 label 기반으로 선택할 수 있다.
```

---

## 매니페스트

```text
kubernetes/karmada/manifests/demo-scalex-role-placement/
  00-namespace.yaml
  10-render-deployment.yaml
  11-edge-deployment.yaml
  12-data-deployment.yaml
  20-render-service.yaml
  21-edge-service.yaml
  22-data-service.yaml
  30-render-propagation-policy.yaml
  31-edge-propagation-policy.yaml
  32-data-propagation-policy.yaml
```

workload:

```text
render:
  Deployment: demo-scalex-render-nginx
  replicas: 4
  후보: scalex.io/pool=gpu
  weight: gpu-render=3, edge-gpu=1

edge:
  Deployment: demo-scalex-edge-nginx
  replicas: 2
  후보: scalex.io/location=edge
  weight: edge=1

data:
  Deployment: demo-scalex-data-nginx
  replicas: 2
  후보: scalex.io/workload=data
  weight: data=1
```

---

## 핵심 policy

### render workload

```yaml
placement:
  clusterAffinity:
    labelSelector:
      matchLabels:
        scalex.io/pool: gpu
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
```

의미:

```text
gpu pool에 속한 cluster만 후보로 보고,
그중 TwinX 역할 cluster에 더 큰 weight를 준다.
```

### edge workload

```yaml
placement:
  clusterAffinity:
    labelSelector:
      matchLabels:
        scalex.io/location: edge
```

의미:

```text
EdgeX처럼 edge location label이 있는 cluster에만 배치한다.
```

### data workload

```yaml
placement:
  clusterAffinity:
    labelSelector:
      matchLabels:
        scalex.io/workload: data
```

의미:

```text
DataX처럼 data workload label이 있는 cluster에만 배치한다.
```

---

## 실행 명령

client dry-run:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=client \
  -f kubernetes/karmada/manifests/demo-scalex-role-placement/
```

적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-scalex-role-placement/
```

적용 시각:

```text
2026-06-26T04:22:30Z
```

적용 결과:

```text
namespace/demo-scalex-role created
deployment.apps/demo-scalex-render-nginx created
deployment.apps/demo-scalex-edge-nginx created
deployment.apps/demo-scalex-data-nginx created
service/demo-scalex-render-nginx created
service/demo-scalex-edge-nginx created
service/demo-scalex-data-nginx created
propagationpolicy.policy.karmada.io/demo-scalex-render-policy created
propagationpolicy.policy.karmada.io/demo-scalex-edge-policy created
propagationpolicy.policy.karmada.io/demo-scalex-data-policy created
```

---

## 확인 명령

ResourceBinding 확인:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb -n demo-scalex-role -o wide

for name in demo-scalex-render-nginx demo-scalex-edge-nginx demo-scalex-data-nginx; do
  echo "### $name"
  kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb \
    -n demo-scalex-role ${name}-deployment \
    -o jsonpath='{range .spec.clusters[*]}{.name}{" replicas="}{.replicas}{"\n"}{end}{"lastScheduledTime="}{.status.lastScheduledTime}{"\n"}{"gracefulEvictionTasks="}{.spec.gracefulEvictionTasks}{"\n"}'
done
```

member cluster 확인:

```bash
for c in twinx edgex datax; do
  echo "--- $c"
  kubectl --context kind-$c get deploy,pods,svc -n demo-scalex-role -o wide
 done
```

---

## 기대 결과

| workload | 기대 배치 |
| --- | --- |
| render | `twinx=3`, `edgex=1`, `datax=0` |
| edge | `edgex=2` |
| data | `datax=2` |

---

## 실제 결과

### 1. ResourceBinding

최종 ResourceBinding은 모두 `SCHEDULED=True`, `FULLYAPPLIED=True`가 되었다.

```text
NAME                                  SCHEDULED   FULLYAPPLIED
demo-scalex-data-nginx-deployment     True        True
demo-scalex-data-nginx-service        True        True
demo-scalex-edge-nginx-deployment     True        True
demo-scalex-edge-nginx-service        True        True
demo-scalex-render-nginx-deployment   True        True
demo-scalex-render-nginx-service      True        True
```

Deployment replica 배치:

```text
render:
- edgex replicas=1
- twinx replicas=3

edge:
- edgex replicas=2

data:
- datax replicas=2
```

`gracefulEvictionTasks`는 모두 비어 있었다.

### 2. member cluster 상태

`twinx`:

```text
demo-scalex-render-nginx 3/3
```

`edgex`:

```text
demo-scalex-render-nginx 1/1
demo-scalex-edge-nginx   2/2
```

`datax`:

```text
demo-scalex-data-nginx   2/2
```

### 3. Service 전파

Service도 workload placement와 같은 cluster에만 생성되었다.

`twinx`:

```text
demo-scalex-render-nginx
```

`edgex`:

```text
demo-scalex-render-nginx
demo-scalex-edge-nginx
```

`datax`:

```text
demo-scalex-data-nginx
```

---

## 성공/실패 판단

| 검증 항목 | 기대 결과 | 실제 결과 | 판단 |
| --- | --- | --- | --- |
| render 후보 | gpu pool만 선택 | twinx/edgex 선택 | 성공 |
| render weight | twinx=3, edgex=1 | twinx=3, edgex=1 | 성공 |
| edge 후보 | edge label cluster만 선택 | edgex=2 | 성공 |
| data 후보 | data workload label cluster만 선택 | datax=2 | 성공 |
| Service 전파 | workload와 같은 cluster | 동일하게 전파 | 성공 |
| ResourceBinding | FullyApplied=True | 모두 True | 성공 |

---

## 문제/에러

이번 실험에서는 Karmada 기능 실패는 없었다.

주의할 점:

```text
현재 kind lab에는 Resource Pool 역할 member cluster가 없다.
따라서 실제 ScaleX-POD의 Resource Pool fallback 배치는 다음 실험에서 별도 member cluster 또는 label로 추가 검증해야 한다.
```

---

## ScaleX-POD에 주는 의미

이번 실험으로 확인한 점:

```text
1. workload가 cluster 이름을 직접 몰라도 role label 기반으로 배치될 수 있다.
2. TwinX/EdgeX처럼 같은 gpu pool에 속한 cluster도 weight로 우선순위를 줄 수 있다.
3. EdgeX/DataX 전용 workload는 location/workload label로 명확하게 제한할 수 있다.
4. Service도 Deployment와 같은 placement 정책에 따라 필요한 cluster에만 생성된다.
```

ScaleX-POD placement 후보:

```text
render/gpu workload:
  후보: scalex.io/pool=gpu
  우선: scalex.io/role=gpu-render weight 높게
  fallback: scalex.io/role=edge-gpu weight 낮게

edge workload:
  후보: scalex.io/location=edge

data workload:
  후보: scalex.io/workload=data 또는 scalex.io/storage=ssd
```

운영 설계 포인트:

```text
cluster 이름보다 label contract가 중요하다.
TwinX/EdgeX/DataX/Resource Pool마다 label 표준을 먼저 정해야 한다.
```

---

## 다음 액션

- Resource Pool 역할 label 추가 실험
- OverridePolicy image/storageClass 실험
- scheduler-estimator 정리
- spreadConstraints 실험
- ArgoCD -> Karmada API Server GitOps 흐름 검증
