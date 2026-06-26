# demo-override-platform

Karmada `OverridePolicy`로 cluster별 container image와 PVC `storageClassName`을 다르게 적용하는 실험 매니페스트다.

## member cluster 사전 준비

각 member cluster에 실험용 StorageClass를 직접 생성한다.

```bash
kubectl --context kind-twinx apply -f member-storageclasses/twinx-storageclass.yaml
kubectl --context kind-edgex apply -f member-storageclasses/edgex-storageclass.yaml
kubectl --context kind-datax apply -f member-storageclasses/datax-storageclass.yaml
kubectl --context kind-poolx apply -f member-storageclasses/poolx-storageclass.yaml
```

## Karmada 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f 00-namespace.yaml \
  -f 10-pvc.yaml \
  -f 20-deployment.yaml \
  -f 30-service.yaml \
  -f 40-override-image.yaml \
  -f 41-override-storageclass.yaml \
  -f 50-propagation-policy.yaml
```

## 결과 요약

```text
twinx: image=nginx:1.27-alpine, storageClass=scalex-twinx-local, PVC Bound
edgex: image=nginx:1.26-alpine, storageClass=scalex-edgex-local, PVC Bound
datax: image=nginx:1.25-alpine, storageClass=scalex-datax-local, PVC Bound
poolx: image=nginx:1.27-alpine, storageClass=scalex-poolx-local, PVC Bound
```

자세한 기록: `kubernetes/karmada/experiments/2026-06-26-14-override-image-storageclass.md`
