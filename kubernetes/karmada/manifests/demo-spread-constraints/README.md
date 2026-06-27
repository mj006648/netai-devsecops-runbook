# demo-spread-constraints

ScaleX-POD cluster label group을 기준으로 `spreadConstraints`를 검증하는 Karmada 실험 매니페스트다.

## pool group

```text
gpu     : twinx, edgex
data    : datax
general : poolx
```

## workload

```text
namespace : demo-spread-constraints
Deployment: demo-spread-pool-nginx
replicas  : 8
spread    : spreadByLabel=scalex.io/pool, minGroups=3, maxGroups=3
weight    : gpu=2, data=1, general=1
```

## 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-spread-constraints/
```

자세한 기록: `kubernetes/karmada/experiments/2026-06-27-17-spread-constraints.md`

## 실제 결과

```text
twinx=3
edgex=3
datax=1
poolx=1
```

주의: `scalex.io/pool=gpu` labelSelector는 `twinx`와 `edgex` 각각에 weight를 적용하는 형태로 관찰됐다.
