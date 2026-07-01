# 실험 14. OverridePolicy로 cluster별 image/storageClass 변경

## 목적

실험 04에서는 `OverridePolicy`로 cluster별 env 값을 바꾸는 것을 확인했다.
이번 실험은 실제 운영 차이에 더 가까운 항목인 container image와 PVC `storageClassName`을 cluster별로 다르게 적용할 수 있는지 검증한다.

ScaleX-POD 기준 의미:

```text
같은 workload라도 TwinX / EdgeX / DataX / Resource Pool에서
사용하는 image registry/tag, storageClass가 다를 수 있다.
Karmada OverridePolicy로 이 차이를 중앙에서 관리할 수 있는지 확인한다.
```

---

## 가설

```text
Deployment image와 PVC storageClassName을 각각 별도 OverridePolicy로 지정하면,
member cluster마다 다른 image와 storageClass가 적용되고 PVC도 정상 Bound될 것이다.
```

---

## 사전 상태

member cluster:

```text
- twinx READY=True
- edgex READY=True
- datax READY=True
- poolx READY=True
```

각 member cluster에는 기본 StorageClass가 있다.

```text
standard (default)
provisioner: rancher.io/local-path
volumeBindingMode: WaitForFirstConsumer
```

이번 실험에서는 cluster별 이름 차이를 확인하기 위해 별도 StorageClass를 직접 생성했다.

---

## member cluster 사전 준비

StorageClass는 Karmada API가 아니라 각 member cluster에 직접 생성했다.

```bash
kubectl --context kind-twinx apply \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/member-storageclasses/twinx-storageclass.yaml

kubectl --context kind-edgex apply \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/member-storageclasses/edgex-storageclass.yaml

kubectl --context kind-datax apply \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/member-storageclasses/datax-storageclass.yaml

kubectl --context kind-poolx apply \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/member-storageclasses/poolx-storageclass.yaml
```

적용 시각:

```text
2026-06-26T04:53:59Z
```

결과:

```text
storageclass.storage.k8s.io/scalex-twinx-local created
storageclass.storage.k8s.io/scalex-edgex-local created
storageclass.storage.k8s.io/scalex-datax-local created
storageclass.storage.k8s.io/scalex-poolx-local created
```

최종 StorageClass:

```text
twinx:
- scalex-twinx-local
- standard (default)

edgex:
- scalex-edgex-local
- standard (default)

datax:
- scalex-datax-local
- standard (default)

poolx:
- scalex-poolx-local
- standard (default)
```

---

## 매니페스트

```text
kubernetes/multicluster/karmada/manifests/demo-override-platform/
  member-storageclasses/
    twinx-storageclass.yaml
    edgex-storageclass.yaml
    datax-storageclass.yaml
    poolx-storageclass.yaml
  00-namespace.yaml
  10-pvc.yaml
  20-deployment.yaml
  30-service.yaml
  40-override-image.yaml
  41-override-storageclass.yaml
  50-propagation-policy.yaml
```

workload:

```text
namespace : demo-override-platform
Deployment: demo-override-platform-nginx
PVC       : demo-override-platform-data
Service   : demo-override-platform-nginx
replicas  : 4
placement : twinx=1, edgex=1, datax=1, poolx=1
```

PVC base:

```yaml
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 64Mi
```

Deployment base image:

```yaml
image: nginx:1.27-alpine
```

---

## OverridePolicy: image

```yaml
apiVersion: policy.karmada.io/v1alpha1
kind: OverridePolicy
metadata:
  name: demo-override-platform-image
  namespace: demo-override-platform
spec:
  resourceSelectors:
    - apiVersion: apps/v1
      kind: Deployment
      name: demo-override-platform-nginx
  overrideRules:
    - targetCluster:
        clusterNames:
          - twinx
      overriders:
        plaintext:
          - path: /spec/template/spec/containers/0/image
            operator: replace
            value: nginx:1.27-alpine
    - targetCluster:
        clusterNames:
          - edgex
      overriders:
        plaintext:
          - path: /spec/template/spec/containers/0/image
            operator: replace
            value: nginx:1.26-alpine
    - targetCluster:
        clusterNames:
          - datax
      overriders:
        plaintext:
          - path: /spec/template/spec/containers/0/image
            operator: replace
            value: nginx:1.25-alpine
    - targetCluster:
        clusterNames:
          - poolx
      overriders:
        plaintext:
          - path: /spec/template/spec/containers/0/image
            operator: replace
            value: nginx:1.27-alpine
```

---

## OverridePolicy: storageClassName

```yaml
apiVersion: policy.karmada.io/v1alpha1
kind: OverridePolicy
metadata:
  name: demo-override-platform-storageclass
  namespace: demo-override-platform
spec:
  resourceSelectors:
    - apiVersion: v1
      kind: PersistentVolumeClaim
      name: demo-override-platform-data
  overrideRules:
    - targetCluster:
        clusterNames:
          - twinx
      overriders:
        plaintext:
          - path: /spec/storageClassName
            operator: replace
            value: scalex-twinx-local
    - targetCluster:
        clusterNames:
          - edgex
      overriders:
        plaintext:
          - path: /spec/storageClassName
            operator: replace
            value: scalex-edgex-local
    - targetCluster:
        clusterNames:
          - datax
      overriders:
        plaintext:
          - path: /spec/storageClassName
            operator: replace
            value: scalex-datax-local
    - targetCluster:
        clusterNames:
          - poolx
      overriders:
        plaintext:
          - path: /spec/storageClassName
            operator: replace
            value: scalex-poolx-local
```

---

## 실행 명령

client dry-run:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=client \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/00-namespace.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/10-pvc.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/20-deployment.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/30-service.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/40-override-image.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/41-override-storageclass.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/50-propagation-policy.yaml
```

적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/00-namespace.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/10-pvc.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/20-deployment.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/30-service.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/40-override-image.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/41-override-storageclass.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-override-platform/50-propagation-policy.yaml
```

적용 시각:

```text
2026-06-26T04:54:56Z
```

적용 결과:

```text
namespace/demo-override-platform created
persistentvolumeclaim/demo-override-platform-data created
deployment.apps/demo-override-platform-nginx created
service/demo-override-platform-nginx created
overridepolicy.policy.karmada.io/demo-override-platform-image created
overridepolicy.policy.karmada.io/demo-override-platform-storageclass created
propagationpolicy.policy.karmada.io/demo-override-platform-policy created
```

---

## 확인 명령

ResourceBinding:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb \
  -n demo-override-platform -o wide
```

cluster별 image/PVC:

```bash
for c in twinx edgex datax poolx; do
  echo "--- $c"
  kubectl --context kind-$c -n demo-override-platform get deploy \
    demo-override-platform-nginx \
    -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

  kubectl --context kind-$c -n demo-override-platform get pvc \
    demo-override-platform-data \
    -o jsonpath='{.spec.storageClassName}{" phase="}{.status.phase}{" volume="}{.spec.volumeName}{"\n"}'

  kubectl --context kind-$c -n demo-override-platform get pods
 done
```

---

## 기대 결과

| cluster | expected image | expected storageClass |
| --- | --- | --- |
| twinx | `nginx:1.27-alpine` | `scalex-twinx-local` |
| edgex | `nginx:1.26-alpine` | `scalex-edgex-local` |
| datax | `nginx:1.25-alpine` | `scalex-datax-local` |
| poolx | `nginx:1.27-alpine` | `scalex-poolx-local` |

---

## 실제 결과

### 1. ResourceBinding

관찰 시각:

```text
2026-06-26T04:55:24Z
```

결과:

```text
NAME                                                SCHEDULED   FULLYAPPLIED
demo-override-platform-data-persistentvolumeclaim   True        True
demo-override-platform-nginx-deployment             True        True
demo-override-platform-nginx-service                True        True
```

Deployment replica 배치:

```text
datax replicas=1
edgex replicas=1
poolx replicas=1
twinx replicas=1
```

### 2. cluster별 image와 PVC

`twinx`:

```text
image=nginx:1.27-alpine
deploy=1/1
pvc=scalex-twinx-local phase=Bound
pod=Running
```

`edgex`:

```text
image=nginx:1.26-alpine
deploy=1/1
pvc=scalex-edgex-local phase=Bound
pod=Running
```

`datax`:

```text
image=nginx:1.25-alpine
deploy=1/1
pvc=scalex-datax-local phase=Bound
pod=Running
```

`poolx`:

```text
image=nginx:1.27-alpine
deploy=1/1
pvc=scalex-poolx-local phase=Bound
pod=Running
```

두 번째, 세 번째 관찰에서도 동일했다.

```text
2026-06-26T04:55:40Z
2026-06-26T04:55:56Z
```

---

## 성공/실패 판단

| 검증 항목 | 기대 결과 | 실제 결과 | 판단 |
| --- | --- | --- | --- |
| image override | cluster별 image tag 변경 | twinx/edgex/datax/poolx 모두 다르게 반영 | 성공 |
| storageClass override | cluster별 storageClassName 변경 | 각 cluster 전용 storageClassName 반영 | 성공 |
| PVC binding | 모든 PVC Bound | 모두 Bound | 성공 |
| Pod 실행 | 모든 cluster에서 Running | 모두 Running | 성공 |
| ResourceBinding | FullyApplied=True | PVC/Deployment/Service 모두 True | 성공 |

---

## 문제/에러

이번 실험에서는 Karmada 기능 실패는 없었다.

주의할 점은 있다.

### 1. PVC storageClassName은 생성 후 변경이 어렵다

Kubernetes PVC의 `storageClassName`은 사실상 생성 시점에 결정되는 값이다.
따라서 OverridePolicy는 workload가 member cluster에 처음 적용되기 전에 준비되어 있어야 한다.

이번 실험은 다음 순서로 적용했다.

```text
1. Namespace/PVC/Deployment/Service 생성
2. OverridePolicy 생성
3. PropagationPolicy 생성
```

즉, propagation이 시작되기 전에 override가 준비되도록 했다.

### 2. member cluster StorageClass 사전 준비 필요

Karmada가 PVC를 전파하더라도, member cluster에 해당 `storageClassName`이 없으면 PVC가 Bound되지 않을 수 있다.
이번 실험에서는 각 member cluster에 StorageClass를 직접 준비했다.

운영에서는 다음 중 하나를 선택해야 한다.

```text
- 각 cluster bootstrap 과정에서 StorageClass 표준 생성
- Karmada로 StorageClass까지 전파/관리
- storageClassName contract를 문서화하고 admission/policy로 검증
```

### 3. image registry 차이도 cluster별 pull 가능성을 고려해야 한다

이번 실험에서는 Docker Hub의 nginx tag를 사용했다.
실제 운영에서는 Harbor, local registry, air-gapped registry 등 cluster별 pull 가능성이 다를 수 있다.

---

## ScaleX-POD에 주는 의미

이번 실험으로 확인한 점:

```text
1. 같은 Deployment라도 cluster별 image tag/registry를 다르게 줄 수 있다.
2. 같은 PVC라도 cluster별 storageClassName을 다르게 줄 수 있다.
3. OverridePolicy는 ScaleX-POD의 운영 차이를 Karmada control plane에서 표현하는 핵심 도구다.
```

ScaleX-POD 운영 후보:

```text
TwinX:
  image: GPU/render optimized image
  storageClass: fast local/NVMe 또는 Ceph profile

EdgeX:
  image: edge optimized image 또는 edge registry mirror
  storageClass: edge-local 또는 lightweight storage

DataX:
  image: data pipeline image
  storageClass: data-ssd 또는 Ceph/Rook data profile

Resource Pool:
  image: generic fallback image
  storageClass: general-local 또는 shared storage
```

운영 설계 포인트:

```text
- placement는 어디에 배치할지 결정한다.
- OverridePolicy는 배치된 cluster에서 어떤 차이를 적용할지 결정한다.
- 둘을 같이 써야 ScaleX-POD workload contract가 완성된다.
```

---

## 다음 액션

- Resource Pool fallback + WorkloadRebalancer 실험
- scheduler-estimator 정리
- spreadConstraints 실험
- ArgoCD -> Karmada API Server GitOps 흐름 검증
- Pull mode 후보 검토
