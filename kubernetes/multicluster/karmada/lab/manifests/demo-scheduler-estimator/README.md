# demo-scheduler-estimator

Karmada scheduler의 `--enable-scheduler-estimator=true` 상태에서 실제 scheduler-estimator 서비스가 없을 때 스케줄링이 막히는지 확인하는 실험 매니페스트다.

## workload

```text
namespace : demo-scheduler-estimator
Deployment: demo-estimator-aggregated-nginx
replicas  : 4
requests  : cpu=10m, memory=32Mi
policy    : Divided + Aggregated
candidate : twinx, edgex, datax, poolx

disabled-check workload:
  Deployment: demo-estimator-disabled-weighted-nginx
  replicas  : 4
  policy    : Divided + Weighted, 1:1:1:1
```

## 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-scheduler-estimator/
```

자세한 기록: `kubernetes/multicluster/karmada/experiments/2026-06-27-16-scheduler-estimator.md`
