# demo-multi-workload-rebalance

여러 Deployment를 하나의 `WorkloadRebalancer`로 한 번에 재균형하는 절차를 확인하기 위한 Karmada 실험 매니페스트다.

## 구성

```text
namespace: demo-multi-rebalance
workloads:
  - demo-multi-render-nginx
  - demo-multi-edge-nginx
  - demo-multi-data-nginx
```

각 Deployment는 `replicas: 3`이고 기본 policy는 `twinx`, `edgex`, `datax`에 1:1:1로 분산한다.

## 적용 순서

먼저 namespace/workload/policy만 적용한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/00-namespace.yaml \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/10-render-deployment.yaml \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/11-edge-deployment.yaml \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/12-data-deployment.yaml \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/20-render-service.yaml \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/21-edge-service.yaml \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/22-data-service.yaml \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/30-propagation-policy.yaml
```

그 다음 실험에서 skew를 만든 뒤 rebalancer를 적용한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-multi-workload-rebalance/40-workload-rebalancer.yaml
```

## 결과 요약

lab-only skew:

```text
render: edgex=2, datax=1, twinx=0
edge  : edgex=1, datax=2, twinx=0
data  : datax=3, twinx=0
```

WorkloadRebalancer 후:

```text
render: twinx=1, edgex=1, datax=1
edge  : twinx=1, edgex=1, datax=1
data  : twinx=1, edgex=1, datax=1
```

자세한 기록: `kubernetes/karmada/experiments/2026-06-26-11-multi-workload-rebalancer.md`
