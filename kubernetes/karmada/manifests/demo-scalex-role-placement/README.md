# demo-scalex-role-placement

ScaleX-POD 역할 label을 기준으로 workload를 TwinX/EdgeX/DataX 후보에 배치하는 Karmada 실험 매니페스트다.

## 사용 label

```text
twinx: scalex.io/role=gpu-render, scalex.io/pool=gpu
edgex: scalex.io/role=edge-gpu, scalex.io/pool=gpu, scalex.io/location=edge
datax: scalex.io/role=data, scalex.io/storage=ssd, scalex.io/workload=data
```

## workload

```text
render: gpu pool 후보인 twinx/edgex에 3:1 배치
edge  : edge location인 edgex에만 배치
data  : data workload label이 있는 datax에만 배치
```

## 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-scalex-role-placement/
```

## 결과 요약

```text
render: twinx=3, edgex=1, datax=0
edge  : edgex=2
data  : datax=2
```

자세한 기록: `kubernetes/karmada/experiments/2026-06-26-12-scalex-role-label-placement.md`
