# demo-resource-pool-placement

ScaleX-POD의 Resource Pool 역할을 `poolx` member cluster로 추가한 뒤, general workload와 render fallback workload를 label 기반으로 배치하는 Karmada 실험 매니페스트다.

## 사용 label

```text
poolx:
  scalex.io/role=resource-pool
  scalex.io/pool=general
  scalex.io/workload=general
  scalex.io/fallback=true
```

## workload

```text
general:
  replicas=2
  후보: scalex.io/role=resource-pool
  결과: poolx=2

render fallback:
  replicas=5
  후보: scalex.io/pool in (gpu, general)
  weight: gpu-render=3, edge-gpu=1, resource-pool=1
  결과: twinx=3, edgex=1, poolx=1
```

## 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-placement/
```

자세한 기록: `kubernetes/multicluster/karmada/experiments/2026-06-26-13-resource-pool-placement.md`
