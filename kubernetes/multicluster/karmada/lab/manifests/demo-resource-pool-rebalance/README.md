# demo-resource-pool-rebalance

ScaleX-POD의 Resource Pool fallback workload가 poolx에 몰린 뒤, `WorkloadRebalancer`로 원래 placement weight 기준까지 돌아오는지 확인하는 Karmada 실험 매니페스트다.

## workload

```text
namespace : demo-resource-pool-rebalance
Deployment: demo-pool-fallback-rebalance-nginx
replicas  : 5
후보      : scalex.io/pool in (gpu, general)
weight    : gpu-render=3, edge-gpu=1, resource-pool=1
기대      : twinx=3, edgex=1, poolx=1
```

## 적용

baseline 리소스만 먼저 적용한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/00-namespace.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/10-deployment.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/20-service.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/30-propagation-policy.yaml
```

lab-only skew를 만든 뒤 재균형한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/40-workload-rebalancer.yaml
```

자세한 기록: `kubernetes/multicluster/karmada/experiments/2026-06-26-15-resource-pool-rebalance.md`
