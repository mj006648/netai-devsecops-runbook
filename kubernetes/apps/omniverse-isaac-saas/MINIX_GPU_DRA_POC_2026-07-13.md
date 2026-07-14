# MiniX Kubernetes 1.34.3 + NVIDIA GPU DRA PoC 실행 기록

> 실행일: 2026-07-13  
> 목적: SmartX/eecs-k8s 구현 전에 MiniX RTX 3090으로 Kubernetes DRA 기반 GPU inventory와 특정 GPU 선택이 실제 동작하는지 검증한다.  
> 범위: 클러스터 업그레이드, 불필요 구성 제거, GPU Operator DRA 전환, 정확한 GPU 할당 smoke test. Isaac Sim과 Isaac UI 배포는 다음 단계다.

---

## 1. 결론

MiniX를 Kubernetes `v1.34.3`과 containerd `2.1.5`로 업그레이드했고, 기존 GPU Operator `v25.10.1`을 유지한 채 NVIDIA DRA driver `v25.12.0`을 설치했다.

RTX 3090 UUID를 지정한 `ResourceClaim`으로 다음 항목을 확인했다.

```text
ResourceClaim driver: gpu.nvidia.com
ResourceSlice pool: gpu
allocated device: gpu-0
scheduled node: gpu
GPU product: NVIDIA GeForce RTX 3090
GPU UUID: GPU-a4dda0d8-1036-c78c-127a-b910925061ce
driver: 580.159.03
memory: 24576 MiB
result: DRA_GPU_TEST=passed
```

따라서 MiniX에서는 다음 MVP 흐름을 구현할 기술 전제가 확인됐다.

```text
Isaac UI가 cluster GPU inventory 조회
  -> 사용자가 node/product/UUID 선택
  -> ResourceClaim 생성
  -> Kubernetes scheduler가 GPU 예약
  -> 선택 GPU 1개로 Isaac Sim Pod 실행
  -> LoadBalancer IP로 WebRTC 접속
```

---

## 2. 다른 문서와의 구분

이 문서는 설계 문서가 아니라 **실제 실행 기록과 검증 증거**다.

| 문서 | 역할 |
| --- | --- |
| `ISAAC_UI_MVP_SCOPE.md` | 최종 MVP 기능과 원본 대비 유지/제거/변경 설계 |
| `SMARTX_MIGRATION_PLAN.md` | 이전 문서 링크 호환용 안내 |
| `MINIX_GPU_DRA_POC_2026-07-13.md` | MiniX 업그레이드와 GPU DRA 실제 검증 결과 |

Isaac UI 화면, API, Nucleus, Extension, WebRTC 상세 설계는 `ISAAC_UI_MVP_SCOPE.md`에만 둔다.

---

## 3. 작업 전 상태

### 3.1 클러스터

```text
nodes: master, com1, com2, com3, gpu
Kubernetes: v1.33.3
GPU node: gpu
GPU node IP: 10.30.0.13
GPU: NVIDIA GeForce RTX 3090 1장
```

GPU 노드의 DHCP 주소 변경 때문에 Kubernetes node 상태가 불안정했던 이력이 있어 내부 IP를 `10.30.0.13`으로 고정한 뒤 작업했다.

### 3.2 GPU stack

```text
GPU Operator: v25.10.1
NVIDIA device plugin: v0.18.1
NVIDIA Container Toolkit: v1.18.1
host driver: 580.159.03
```

### 3.3 제거 대상

- KubeVirt CDI: 현재 사용하지 않음
- Kyverno: 현재 사용하지 않음
- Kubernetes Ollama: GPU 점유와 host port 충돌 방지를 위해 비활성화
- gpu 노드 systemd Ollama: GPU와 `11434` 포트 해제

KubeVirt CDI(Containerized Data Importer)와 NVIDIA CDI(Container Device Interface)는 이름만 같고 서로 다른 기술이다. KubeVirt CDI를 제거해도 NVIDIA GPU DRA에는 영향이 없다.

---

## 4. 사전 정리

### 4.1 CDI와 Kyverno

삭제 전에 다음 리소스가 없음을 확인했다.

```text
VirtualMachine / VirtualMachineInstance
DataVolume
Kyverno ClusterPolicy / Policy
```

그다음 namespace, CRD, webhook, APIService, RBAC를 제거하고 관련 리소스가 0개인지 확인했다.

백업 위치:

```text
/var/backups/minix-remove-cdi-kyverno-20260713-084030
```

### 4.2 Ollama

MiniX GitOps 설정에서 `applications.ollama.enabled`를 `false`로 바꾸고 push했다.

```text
repository: mj006648/MiniX
commit: a7b73ecd chore: disable ollama
```

Argo CD child Application에 resource finalizer를 추가한 뒤 cascade 삭제했고, `ollama` namespace가 사라진 것을 확인했다. gpu 노드의 `ollama.service`도 stop/disable하여 GPU와 포트를 비웠다.

---

## 5. Kubernetes 1.34.3 업그레이드

### 5.1 사용 버전

```text
Kubespray: v2.30.0
Kubernetes: v1.34.3
containerd: 2.1.5
Cilium: 1.18.4
CoreDNS: 1.12.1
etcd: 3.5.26
```

### 5.2 실행 방식

가용성과 원인 분리를 위해 node를 한 대씩 순차 업그레이드했다.

```text
master -> com1 -> com2 -> com3 -> gpu
```

Rook-Ceph PDB에 의한 drain 차단을 피하기 위해 이번 MiniX 실험에서는 다음 no-drain 값을 사용했다.

```yaml
drain_nodes: false
upgrade_node_always_cordon: true
```

이는 범용 운영 정책이 아니다. 운영 클러스터에서는 workload redundancy, PDB, storage 상태를 먼저 해결하고 정상 drain을 사용하는 것이 원칙이다.

### 5.3 Kubespray 보정

#### CNI binary 소유권

Kubespray가 `/opt/cni/bin` 소유자를 비-root로 바꾸면 Cilium init container가 `DAC_OVERRIDE` 없이 파일을 갱신하지 못했다. MiniX inventory에 다음을 고정했다.

```yaml
cni_bin_owner: root
```

#### no-drain 조건

Kubespray remove-node pre-task의 drain과 volume wait가 `drain_nodes` 값을 따르도록 로컬 role을 보정했다.

#### NVIDIA containerd drop-in import

containerd 2.1 설정이 재생성된 뒤 NVIDIA Container Toolkit이 만든 `/etc/containerd/conf.d/99-nvidia.toml`이 import되지 않았다. 그 결과 `RuntimeClass nvidia` Pod가 다음 오류로 시작하지 못했다.

```text
no runtime for "nvidia" is configured
```

재실행에도 유지되도록 Kubespray inventory에 다음을 추가했다.

```yaml
# inventory/minix/group_vars/all/containerd.yml
containerd_extra_args: 'imports = ["/etc/containerd/conf.d/*.toml"]'
```

gpu 노드 현재 설정에도 같은 import를 반영하고 TOML 검증 후 containerd를 재시작했다. 이후 NVIDIA validator와 `ClusterPolicy`가 모두 `ready`로 복구됐다.

### 5.4 실행 로그

```text
/home/chang/kubespray-v2.30/upgrade-master-20260713-101902.log
/home/chang/kubespray-v2.30/upgrade-com1-20260713-122056.log
/home/chang/kubespray-v2.30/upgrade-com2-20260713-122606.log
/home/chang/kubespray-v2.30/upgrade-com3-20260713-123056.log
/home/chang/kubespray-v2.30/upgrade-gpu-20260713-123555.log
```

모든 play recap은 `failed=0`이었다.

---

## 6. GPU Operator 판단과 DRA 전환

### 6.1 GPU Operator v25.10.1 유지 이유

MiniX PoC에서는 변수를 줄이기 위해 GPU Operator를 동시에 최신 계열로 올리지 않았다.

NVIDIA `25.10` support matrix의 다음 범위 안에 현재 조합이 들어간다.

```text
Kubernetes: 1.30-1.35
containerd: 1.7-2.1
NVIDIA driver: 580.159.03
```

현재 조합:

```text
Kubernetes: 1.34.3
containerd: 2.1.5
NVIDIA driver: 580.159.03
```

`25.10`은 장기 운영 기준 최신 계열이 아니므로 eecs/c-k8s 또는 TwinX 적용 전에는 당시 최신 GPU Operator와 DRA driver 호환성을 다시 확인한다.

참고:

- [GPU Operator 25.10 platform support](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/25.10/platform-support.html)
- [GPU Operator 25.10 DRA installation](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/25.10/dra-intro-install.html)

### 6.2 GPU Operator 변경

GPU Operator Helm release를 revision 3으로 갱신했다.

```yaml
cdi:
  enabled: true

devicePlugin:
  enabled: false
```

gpu node label:

```text
nvidia.com/dra-kubelet-plugin=true
```

전통 `nvidia-device-plugin` DaemonSet은 0개임을 확인했다. 이후 GPU 요청은 `resources.limits.nvidia.com/gpu`가 아니라 DRA claim을 기준으로 한다.

보호 백업:

```text
/var/backups/minix-gpu-dra-20260713-125215
```

### 6.3 NVIDIA DRA driver 설치

```text
Helm release: nvidia-dra-driver-gpu
chart: nvidia/nvidia-dra-driver-gpu
version: 25.12.0
namespace: nvidia-dra-driver-gpu
```

MiniX values:

```text
/home/chang/kubespray-v2.30/inventory/minix/dra-driver-nvidia-gpu-values.yaml
```

핵심 값:

```yaml
image:
  pullPolicy: IfNotPresent
kubeletPlugin:
  nodeSelector:
    nvidia.com/dra-kubelet-plugin: "true"
```

생성된 DeviceClass:

```text
gpu.nvidia.com
mig.nvidia.com
vfio.gpu.nvidia.com
```

---

## 7. UI가 클러스터 GPU를 파악하는 방식

### 7.1 source of truth

UI가 각 node에 SSH하거나 UI Pod에서 `nvidia-smi`를 실행하지 않는다. Kubernetes API의 다음 정보를 결합한다.

```text
ResourceSlice
  -> 실제 GPU 목록, node, pool, device, product, UUID, memory

모든 namespace의 ResourceClaim.status.allocation.devices.results
  -> 현재 DRA가 할당한 driver/pool/device

Node
  -> Ready, unschedulable, taint 상태

WebRTC capability policy
  -> NVENC 등 Isaac Sim streaming 호환 여부
```

장치의 고유 key는 다음 tuple로 처리한다.

```text
(driver, pool, device)
```

UUID만 key로 사용하지 않는 이유는 DRA의 실제 allocation 결과가 `driver/pool/device`로 반환되기 때문이다.

### 7.2 가용 상태 계산

UI API의 상태 계산 기준:

| 상태 | 기준 |
| --- | --- |
| `Available` | node Ready, schedulable, WebRTC 호환, allocation 결과에 없음 |
| `Allocated` | 어떤 ResourceClaim의 allocation 결과에 같은 driver/pool/device가 있음 |
| `NodeUnavailable` | node NotReady 또는 unschedulable |
| `Incompatible` | GPU는 존재하지만 WebRTC capability 정책에서 제외 |
| `Unknown` | ResourceSlice나 node 정보가 불완전함 |

예상 API 응답:

```json
{
  "node": "gpu",
  "driver": "gpu.nvidia.com",
  "pool": "gpu",
  "device": "gpu-0",
  "uuid": "GPU-a4dda0d8-1036-c78c-127a-b910925061ce",
  "product": "NVIDIA GeForce RTX 3090",
  "memory": "24Gi",
  "status": "Available",
  "compatibleWithWebRTC": true
}
```

UI에서 `Available`로 보인 직후 다른 사용자가 같은 GPU를 먼저 예약할 수 있다. 화면 표시는 안내이고, 생성 순간의 최종 판정은 scheduler와 DRA allocator가 한다.

### 7.3 선택 방식

```text
auto
  -> 호환 가능한 Available GPU 한 장

product
  -> 선택 제품과 일치하는 GPU 한 장

node
  -> 선택 node의 호환 가능한 GPU 한 장

device
  -> 선택 UUID와 일치하는 GPU 한 장
```

UI는 claim 생성 직전에 inventory를 다시 읽는다. 그래도 allocation 경쟁이 발생하면 `409 Conflict` 성격의 사용자 오류로 반환하고 목록 새로고침을 유도한다.

### 7.4 최소 read 권한

클러스터 전체 GPU 가용 상태를 정확히 표시하려면 다음 read-only 권한이 필요하다.

```text
nodes: get, list
deviceclasses: get, list
resourceslices: get, list
resourceclaims across namespaces: get, list
```

Isaac Sim 생성용 Pod, Service, Deployment, ResourceClaim의 create/delete 권한은 `omniverse` namespace에만 제한한다. Secret 원문 read 권한은 주지 않는다.

---

## 8. RTX 3090 ResourceSlice

NVIDIA DRA driver가 생성한 실제 inventory:

```text
ResourceSlice: gpu-gpu.nvidia.com-4r92w
node: gpu
driver: gpu.nvidia.com
pool: gpu
device: gpu-0
productName: NVIDIA GeForce RTX 3090
uuid: GPU-a4dda0d8-1036-c78c-127a-b910925061ce
PCI address: 0000:0a:00.0
architecture: Ampere
memory: 24 GiB
```

MVP GPU inventory API는 이 ResourceSlice를 읽어 화면을 구성한다. MiniX node 이름이나 UUID를 eecs chart에 하드코딩하지 않는다.

---

## 9. 정확한 GPU 선택 테스트

테스트 매니페스트:

```text
/home/chang/kubespray-v2.30/inventory/minix/dra-exact-rtx3090-test.yaml
```

### 9.1 ResourceClaim

```yaml
apiVersion: resource.k8s.io/v1
kind: ResourceClaim
metadata:
  name: exact-rtx3090
spec:
  devices:
    requests:
      - name: gpu
        exactly:
          deviceClassName: gpu.nvidia.com
          allocationMode: ExactCount
          count: 1
          selectors:
            - cel:
                expression: >-
                  device.attributes["gpu.nvidia.com"].uuid ==
                  "GPU-a4dda0d8-1036-c78c-127a-b910925061ce"
```

Pod는 legacy GPU limit 없이 claim만 소비했다.

```yaml
spec:
  resourceClaims:
    - name: selected-gpu
      resourceClaimName: exact-rtx3090
  containers:
    - name: gpu-check
      resources:
        claims:
          - name: selected-gpu
```

### 9.2 검증 결과

서버 dry-run:

```text
resourceclaim.resource.k8s.io/exact-rtx3090 created (server dry run)
pod/exact-rtx3090-check created (server dry run)
```

실시간 allocation:

```text
driver=gpu.nvidia.com,pool=gpu,device=gpu-0
```

Pod 결과:

```text
phase: Succeeded
node: gpu

DRA_GPU_TEST=started
NVIDIA GeForce RTX 3090, GPU-a4dda0d8-1036-c78c-127a-b910925061ce, 580.159.03, 24576 MiB
DRA_GPU_TEST=passed
```

테스트 namespace는 증거 확인 후 삭제하여 GPU를 반환했다. 매니페스트는 재현용으로 남겼다.

---

## 10. 최종 상태

```text
master  Ready  v1.34.3  containerd 2.1.5
com1    Ready  v1.34.3  containerd 2.1.5
com2    Ready  v1.34.3  containerd 2.1.5
com3    Ready  v1.34.3  containerd 2.1.5
gpu     Ready  v1.34.3  containerd 2.1.5

API /readyz: ok
Cilium: 5/5 Ready
Cilium Operator: 2/2 Ready
CoreDNS: 2/2 Ready
GPU ClusterPolicy: ready
NVIDIA DRA kubelet plugin: 1/1 Ready
traditional NVIDIA device plugin: absent
DeviceClass gpu.nvidia.com: present
RTX 3090 ResourceSlice: present
```

Rook-Ceph의 기존 low-space `HEALTH_WARN`은 이번 Kubernetes/GPU 작업에서 새로 발생한 문제가 아니다. 별도 storage capacity 작업으로 다룬다.

---

## 11. 이번 PoC에서 확정한 결정

1. Isaac UI는 `ResourceSlice`를 GPU inventory의 source of truth로 사용한다.
2. 전체 DRA claim allocation을 합쳐 사용 중인 GPU를 표시한다.
3. 특정 GPU 선택은 UUID CEL selector가 있는 `ResourceClaim`으로 구현한다.
4. 동시 요청 충돌은 UI가 아니라 scheduler/DRA allocator가 최종 판정한다.
5. Isaac Sim image는 GPU마다 다르게 만들지 않는다. 호환되는 공통 image를 쓰고 GPU 선택은 DRA가 담당한다.
6. RTX 3090은 WebRTC PoC 대상으로 사용한다.
7. `nvidia.com/gpu: 1` fallback은 image/runtime 초기 확인에만 쓰고 최종 MVP에서는 제거한다.

---

## 12. 다음 단계

MiniX에서 다음 순서로 진행한다.

1. 사용할 Isaac Sim image를 확인하거나 새로 build한다.
2. 같은 DRA claim으로 Isaac Sim Pod 한 개를 실행한다.
3. `/dev/shm`, WebRTC port, 인스턴스별 LoadBalancer Service를 검증한다.
4. Nucleus endpoint와 credential Secret을 주입하고 USD 접근을 확인한다.
5. 위 흐름이 성공하면 최소 Isaac UI에 GPU inventory와 `auto/product/node/device` 선택을 구현한다.
6. 마지막에 eecs-k8s 공통 chart와 c-k8s/TwinX preset으로 이관한다.

eecs 계열로 옮길 때는 MiniX GPU UUID나 node 이름을 복사하지 않는다. 각 대상 클러스터의 `ResourceSlice`를 실시간으로 읽고 selector를 생성한다.

---

## 13. 한 문장 요약

MiniX에서 Kubernetes 1.34.3과 NVIDIA DRA를 사용해 클러스터 GPU inventory를 읽고 RTX 3090 한 장을 UUID로 정확히 예약하는 것까지 검증했으므로, 다음 작업은 이 claim 위에 Isaac Sim과 WebRTC를 올리는 것이다.
