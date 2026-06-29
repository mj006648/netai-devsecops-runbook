# demo-pull-rebalance 실험

이 manifest는 기존 edge workload가 새 Pull mode cluster `pullx`까지 재균형되는지 확인하기 위한 WorkloadRebalancer다.

## 대상

```text
Deployment: demo-scalex-role/demo-scalex-edge-nginx
현재 policy: scalex.io/location=edge
대상 cluster: edgex, pullx
기대 replica: edgex=1, pullx=1
```

## 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-pull-rebalance/10-workload-rebalancer.yaml
```

## 확인

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get workloadrebalancer demo-pull-edge-rebalance-run -o yaml

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-scalex-role get rb demo-scalex-edge-nginx-deployment -o yaml

kubectl --context kind-edgex -n demo-scalex-role get deploy,pods -o wide
kubectl --context kind-pullx -n demo-scalex-role get deploy,pods -o wide
```
