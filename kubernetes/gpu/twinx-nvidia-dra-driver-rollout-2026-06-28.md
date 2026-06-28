# TwinX NVIDIA DRA Driver Rollout (2026-06-28)

## Summary
TwinX 클러스터에 NVIDIA GPU Operator `v25.3.4`가 이미 운영 중인 상태에서
Kubernetes Dynamic Resource Allocation(DRA)을 사용하기 위해 NVIDIA DRA Driver for GPUs를
별도 Argo CD Application으로 추가했다.

최종 상태는 다음과 같다.

- `nvidia-dra-driver-gpu` Argo CD Application: `Synced / Healthy`
- DRA driver chart: `nvidia/nvidia-dra-driver-gpu` `25.3.2`
- GPU Operator chart: `nvidia/gpu-operator` `v25.3.4`
- 생성된 DeviceClass:
  - `gpu.nvidia.com`
  - `mig.nvidia.com`
  - `compute-domain-daemon.nvidia.com`
  - `compute-domain-default-channel.nvidia.com`
- 생성된 ResourceSlice driver:
  - `gpu.nvidia.com` x 5
  - `compute-domain.nvidia.com` x 5

## Why
기존 GPU Operator만으로는 Kubernetes DRA의 `DeviceClass`, `ResourceSlice`,
`ResourceClaim` 기반 GPU 할당 모델이 활성화되지 않았다.

확인 결과 GPU Operator `v25.3.4` chart values에는 DRA를 켜는 별도 values 키가 없었다.
따라서 `gpu-operator/values.yaml`에 추정 키를 넣는 방식은 Argo CD sync가 성공하더라도
실제 리소스가 생성되지 않을 수 있다. NVIDIA DRA Driver chart를 별도 Application으로
배포하는 방식으로 정리했다.

## Existing GPU Operator state
TwinX-Ops 저장소의 기존 GPU Operator values 파일:

```text
argocd/twinx-infra/apps/gpu-operator/values.yaml
```

주요 설정:

```yaml
mig:
  strategy: mixed

driver:
  enabled: false

daemonsets:
  tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"
  - key: "twinx.dreamai.kr/dedicated-node"
    operator: "Equal"
    value: "partridge"
    effect: "NoSchedule"

devicePlugin:
  enabled: true
  nodeSelector: { NodeGroup: gpu }

migManager:
  enabled: true
  nodeSelector: { NodeGroup: gpu }
```

해석:

- `driver.enabled=false`: NVIDIA driver는 GPU Operator container driver가 아니라 host에 설치된 driver를 사용한다.
- `mig.strategy=mixed`: MIG 사용 노드와 full GPU 사용 노드를 함께 운용할 수 있다.
- `NodeGroup=gpu`와 GPU taint toleration을 GPU 관련 DaemonSet에 적용한다.

## Chart key verification
GPU Operator chart에서 DRA 관련 values 키가 있는지 먼저 확인했다.

```bash
helm show values nvidia/gpu-operator --version v25.3.4 \
  | grep -niE 'dra|resourceDriver|gpuResources|nvidiaDra' -A12 -B4
```

결과적으로 `driver`/`drain` 같은 문자열만 잡혔고 DRA enable block은 확인되지 않았다.

NVIDIA DRA Driver chart values는 다음처럼 확인했다.

```bash
helm show values nvidia/nvidia-dra-driver-gpu --version 25.3.2 \
  | grep -niE 'gpuResourcesEnabledOverride|gpus:|computeDomains:|enabled' -A3 -B2
```

중요한 점은 `resources.gpus.enabled=true`만 설정하면 chart validation이 실패한다는 것이다.

```text
The default value of 'resources.gpus.enabled=true' is not yet supported.
Until then, please explicitly set 'resources.gpus.enabled=false' when installing this chart.
If you truly want to force 'resources.gpus.enabled=true' to apply,
you must also set 'gpuResourcesEnabledOverride=true'.
```

따라서 GPU/MIG DRA까지 활성화하려면 다음 두 값을 함께 설정해야 한다.

```yaml
gpuResourcesEnabledOverride: true

resources:
  gpus:
    enabled: true
  computeDomains:
    enabled: true
```

## GitOps changes
TwinX-Ops 저장소 `main`에 두 번의 커밋으로 반영했다.

```text
640ca41 Add NVIDIA DRA driver app
9fa7418 Enable NVIDIA GPU DRA resources
```

### 1. Argo CD Application 추가

파일:

```text
argocd/twinx-infra/values.yaml
```

추가된 Application 정의:

```yaml
nvidia-dra-driver-gpu:
  enabled: true
  namespace: nvidia-dra-driver-gpu
  syncWave: "4"
  project: twinx-infra
  source:
    type: helm
    repoURL: https://helm.ngc.nvidia.com/nvidia
    chart: nvidia-dra-driver-gpu
    targetRevision: "25.3.2"
    helm:
      releaseName: nvidia-dra-driver-gpu
      valueFiles:
        - "argocd/twinx-infra/apps/nvidia-dra-driver-gpu/values.yaml"
```

### 2. DRA driver values 추가

파일:

```text
argocd/twinx-infra/apps/nvidia-dra-driver-gpu/values.yaml
```

최종 values:

```yaml
nvidiaDriverRoot: /

gpuResourcesEnabledOverride: true

resources:
  gpus:
    enabled: true
  computeDomains:
    enabled: true

kubeletPlugin:
  nodeSelector:
    NodeGroup: gpu
  tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"
  - key: "twinx.dreamai.kr/dedicated-node"
    operator: "Equal"
    value: "partridge"
    effect: "NoSchedule"
```

설정 이유:

- `nvidiaDriverRoot: /`: GPU Operator가 host-installed driver를 사용하므로 driver root는 host root이다.
- `gpuResourcesEnabledOverride: true`: chart `25.3.2`에서 GPU/MIG DeviceClass 렌더링을 강제로 허용한다.
- `resources.gpus.enabled=true`: `gpu.nvidia.com`, `mig.nvidia.com` DeviceClass와 GPU ResourceSlice를 생성한다.
- `resources.computeDomains.enabled=true`: ComputeDomain DRA 리소스를 생성한다.
- `kubeletPlugin.nodeSelector`: DRA kubelet plugin을 GPU 노드에만 배치한다.
- `kubeletPlugin.tolerations`: GPU 전용 taint가 있는 노드에도 plugin Pod가 스케줄링되게 한다.

## Render verification before sync
Argo CD sync 전에 Helm 렌더링으로 검증했다.

```bash
helm template nvidia-dra-driver-gpu nvidia/nvidia-dra-driver-gpu \
  --version 25.3.2 \
  --namespace nvidia-dra-driver-gpu \
  -f argocd/twinx-infra/apps/nvidia-dra-driver-gpu/values.yaml
```

렌더링에서 확인된 DeviceClass:

```text
compute-domain-daemon.nvidia.com
compute-domain-default-channel.nvidia.com
gpu.nvidia.com
mig.nvidia.com
```

또한 DaemonSet에 GPU node scheduling 설정이 들어간 것을 확인했다.

```yaml
nodeSelector:
  NodeGroup: gpu
tolerations:
- key: nvidia.com/gpu
  operator: Exists
  effect: NoSchedule
- key: twinx.dreamai.kr/dedicated-node
  operator: Equal
  value: partridge
  effect: NoSchedule
```

## Post-sync verification
Argo CD sync 후 상태 확인:

```bash
kubectl -n argocd get app nvidia-dra-driver-gpu gpu-operator -o wide
```

결과:

```text
NAME                    SYNC STATUS   HEALTH STATUS   PROJECT
nvidia-dra-driver-gpu   Synced        Healthy         twinx-infra
gpu-operator            OutOfSync     Healthy         twinx-infra
```

`gpu-operator`의 `OutOfSync`는 DRA driver Application 문제가 아니라 기존
`nvidia.com/ClusterPolicy cluster-policy` drift로 분리했다.

### DeviceClass

```bash
kubectl get deviceclass gpu.nvidia.com \
  mig.nvidia.com \
  compute-domain-daemon.nvidia.com \
  compute-domain-default-channel.nvidia.com
```

결과:

```text
gpu.nvidia.com
mig.nvidia.com
compute-domain-daemon.nvidia.com
compute-domain-default-channel.nvidia.com
```

### ResourceSlice driver

```bash
kubectl get resourceslices.resource.k8s.io \
  -o jsonpath='{range .items[*]}{.spec.driver}{"\n"}{end}' \
  | sort | uniq -c
```

결과:

```text
5 compute-domain.nvidia.com
5 gpu.nvidia.com
```

### DRA driver Pods

```bash
kubectl -n nvidia-dra-driver-gpu get pods -o wide
```

결과 요약:

```text
nvidia-dra-driver-gpu-controller      1/1 Running
nvidia-dra-driver-gpu-kubelet-plugin  2/2 Running on l40s
nvidia-dra-driver-gpu-kubelet-plugin  2/2 Running on rm352-1
nvidia-dra-driver-gpu-kubelet-plugin  2/2 Running on rm352-2
nvidia-dra-driver-gpu-kubelet-plugin  2/2 Running on sv4000-1
nvidia-dra-driver-gpu-kubelet-plugin  2/2 Running on sv4000-2
```

GPU resource를 켠 뒤 kubelet plugin Pod는 `compute-domains`와 `gpus` 두 컨테이너로
동작하므로 `2/2 Running`이 정상이다.

### GPU inventory from ResourceSlice

`ResourceSlice`의 device attribute에서 `productName`, `type`, `memory`를 확인했다.

```bash
kubectl get resourceslices.resource.k8s.io -o json > /tmp/resourceslices.json
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path('/tmp/resourceslices.json').read_text())
for s in data.get('items', []):
    spec = s.get('spec', {})
    if spec.get('driver') != 'gpu.nvidia.com':
        continue
    node = spec.get('nodeName') or '-'
    for dev in spec.get('devices', []):
        attrs = dev.get('attributes', {}) or {}
        product = attrs.get('productName', {}).get('string')
        typ = attrs.get('type', {}).get('string')
        mem = dev.get('capacity', {}).get('memory', {}).get('value')
        print(f'{node}	{dev.get("name")}	{typ}	{product}	{mem}')
PY
```

관측 결과:

```text
l40s      NVIDIA L40S x8                         46068Mi each
rm352-1   NVIDIA A10, Quadro RTX 6000            23028Mi / 24Gi
rm352-2   Quadro RTX 6000, NVIDIA A10            24Gi / 23028Mi
sv4000-1  NVIDIA RTX A6000 x2, A100-PCIE-40GB    49140Mi / 40Gi
sv4000-2  NVIDIA L40 x2, A100-PCIE-40GB, MIG     46068Mi / 40Gi / 4864Mi slices
```

전체 `gpu.nvidia.com` ResourceSlice device는 25개로 확인됐다. 여기에는 full GPU와
MIG slice가 함께 포함된다.

## What this enables
이번 변경으로 TwinX에서는 다음을 할 수 있다.

1. **GPU DRA 할당**
   - `gpu.nvidia.com` DeviceClass 기반으로 ResourceClaim/ResourceClaimTemplate을 작성할 수 있다.
   - 기존 `limits: nvidia.com/gpu: 1` 모델보다 더 명시적으로 장치 할당 상태를 추적할 수 있다.

2. **MIG DRA 할당**
   - `mig.nvidia.com` DeviceClass가 생성되어 MIG slice도 DRA 장치로 노출된다.

3. **ComputeDomain DRA**
   - `compute-domain-daemon.nvidia.com`, `compute-domain-default-channel.nvidia.com` DeviceClass가 생성되어
     ComputeDomain 기반 워크로드 실험을 진행할 수 있다.

4. **장치 속성 기반 관측**
   - ResourceSlice에 `productName`, `architecture`, `cudaComputeCapability`, `driverVersion`,
     `memory`, `uuid`, `pcieBusID`, `type` 같은 속성이 들어온다.
   - 스케줄링/할당 정책을 설계할 때 현재 클러스터 GPU 구성을 Kubernetes API로 확인할 수 있다.

5. **GitOps 재현성**
   - DRA driver 설치가 수동 Helm install이 아니라 Argo CD Application으로 관리된다.
   - values 파일만 보면 host driver 사용, GPU/MIG 활성화, GPU 노드 배치 조건을 재현할 수 있다.

## Useful commands

### Application 상태

```bash
kubectl -n argocd get app nvidia-dra-driver-gpu -o wide
kubectl -n argocd get app nvidia-dra-driver-gpu \
  -o jsonpath='sync={.status.sync.status}{" health="}{.status.health.status}{" op="}{.status.operationState.phase}{" msg="}{.status.operationState.message}{"\n"}'
```

### DRA API와 리소스

```bash
kubectl api-resources --api-group=resource.k8s.io
kubectl get deviceclasses.resource.k8s.io
kubectl get resourceslices.resource.k8s.io -A -o wide
```

### driver별 ResourceSlice 개수

```bash
kubectl get resourceslices.resource.k8s.io \
  -o jsonpath='{range .items[*]}{.spec.driver}{"\n"}{end}' \
  | sort | uniq -c
```

### DRA Pod 로그 에러 확인

```bash
kubectl -n nvidia-dra-driver-gpu logs deploy/nvidia-dra-driver-gpu-controller \
  --all-containers=true --since=5m | grep -Ei 'error|warn|fail|panic|timeout' || true

kubectl -n nvidia-dra-driver-gpu logs \
  -l nvidia-dra-driver-gpu-component=kubelet-plugin \
  --all-containers=true --since=5m --prefix \
  | grep -Ei 'error|warn|fail|panic|timeout' || true
```

## Troubleshooting

### `gpu.nvidia.com` DeviceClass가 없다

가능성:

- `resources.gpus.enabled`가 `false`이다.
- `resources.gpus.enabled=true`만 넣고 `gpuResourcesEnabledOverride=true`를 빠뜨렸다.
- Argo CD가 아직 sync되지 않았다.

확인:

```bash
kubectl -n argocd get app nvidia-dra-driver-gpu -o wide
kubectl get deviceclasses.resource.k8s.io
helm template nvidia-dra-driver-gpu nvidia/nvidia-dra-driver-gpu \
  --version 25.3.2 \
  --namespace nvidia-dra-driver-gpu \
  -f argocd/twinx-infra/apps/nvidia-dra-driver-gpu/values.yaml
```

### ComputeDomain만 있고 GPU ResourceSlice가 없다

`resources.gpus.enabled=false` 상태일 가능성이 높다. 이 경우 아래처럼 driver 개수를 보면
`compute-domain.nvidia.com`만 나온다.

```bash
kubectl get resourceslices.resource.k8s.io \
  -o jsonpath='{range .items[*]}{.spec.driver}{"\n"}{end}' \
  | sort | uniq -c
```

### kubelet plugin Pod가 GPU 노드에 안 뜬다

`NodeGroup=gpu` 라벨과 taint/toleration을 확인한다.

```bash
kubectl get nodes -l NodeGroup=gpu
kubectl describe node <gpu-node> | grep -A5 -i taints
kubectl -n nvidia-dra-driver-gpu get ds nvidia-dra-driver-gpu-kubelet-plugin -o yaml
```

### productName 조회 스크립트가 빈 값을 출력한다

DRA ResourceSlice의 구조는 `dev.basic.attributes.productName`이 아니라
`dev.attributes.productName.string`이다. 아래 경로를 사용한다.

```python
attrs = dev.get('attributes', {}) or {}
product = attrs.get('productName', {}).get('string')
```

### `gpu-operator`가 OutOfSync이다

이번 DRA Application과 별개로 기존 GPU Operator의 `ClusterPolicy` drift일 수 있다.
DRA가 정상인지 판단할 때는 `nvidia-dra-driver-gpu` Application, DeviceClass, ResourceSlice,
DRA Pod 상태를 따로 본다.

```bash
kubectl -n argocd get app gpu-operator -o jsonpath='{range .status.resources[?(@.status=="OutOfSync")]}{.group}{"/"}{.kind}{"	"}{.namespace}{"	"}{.name}{"	"}{.status}{"\n"}{end}'
```

## Rollback

GPU/MIG DRA만 끄고 ComputeDomain만 남기려면 values를 다음처럼 되돌린다.

```yaml
# gpuResourcesEnabledOverride 제거 또는 false
resources:
  gpus:
    enabled: false
  computeDomains:
    enabled: true
```

DRA driver 전체를 제거하려면 `argocd/twinx-infra/values.yaml`에서
`nvidia-dra-driver-gpu.enabled=false`로 변경하거나 Application을 제거한 뒤 Argo CD sync한다.
운영 중 ResourceClaim 워크로드가 생긴 뒤에는 먼저 해당 워크로드를 정리해야 한다.

## References

- NVIDIA GPU Operator DRA documentation: <https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/25.3.4/dra-intro-install.html>
- Kubernetes Dynamic Resource Allocation: <https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/>
