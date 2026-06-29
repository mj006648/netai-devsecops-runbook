# TwinX KubeVirt 사용자 VM 계획 2026-06-28

## 요약

TwinX 클러스터에는 Kubernetes를 직접 사용하는 사용자와 물리 노드에 SSH로 접속해 Docker 컨테이너를 직접 띄우는 사용자가 함께 있습니다. 이 방식은 노드 오염, 리소스 추적 어려움, 업그레이드 시 drain/blocker 증가, 사용자별 격리 부족 문제를 만듭니다.

이 계획의 목표는 **Kubernetes를 인프라 레이어로 숨기고, Kubernetes를 모르는 사용자에게 사용자별 KubeVirt VM을 제공**하는 것입니다. GitOps에는 KubeVirt 공식 `v1.8.4` 매니페스트를 준비하되, ArgoCD 자동 동기화로 즉시 배포되지 않도록 현재 Application은 비활성화 상태로 유지합니다.

## 목표

- 사용자별로 `vm-<user>` 형태의 VM을 제공합니다.
- 사용자는 기존처럼 SSH로 접속하고 VM 내부에서 Docker, Docker Compose, Python, TwinX 작업을 수행합니다.
- 운영자는 Kubernetes 리소스로 CPU, Memory, Storage, GPU, 네트워크 접근을 추적하고 제한합니다.
- 물리 노드 SSH 직접 사용을 줄이고, 사용자 작업을 VM/namespace 단위로 격리합니다.

## 설계 이유

### 물리 노드 SSH 대신 KubeVirt VM을 쓰는 이유

기존 방식:

```text
user -> physical node SSH -> docker run / docker compose / local changes
```

문제:

- 물리 노드에 사용자 변경이 직접 남습니다.
- 누가 어떤 컨테이너와 포트를 쓰는지 추적하기 어렵습니다.
- CPU/RAM/GPU 사용량을 사용자별로 제한하기 어렵습니다.
- 노드 업그레이드, 재부팅, drain 작업 때 사용자 컨테이너가 blocker가 됩니다.
- Docker socket, hostPath, root 권한 사용이 운영 리스크가 됩니다.

KubeVirt 방식:

```text
user -> vm-<user> SSH -> docker run / docker compose / TwinX work
```

장점:

- 사용자는 서버 하나를 받은 것처럼 사용할 수 있습니다.
- 관리자는 Kubernetes에서 VM, PVC, Service, Quota, RBAC을 추적할 수 있습니다.
- VM 단위로 정지, 백업, 삭제, 리소스 조정이 가능합니다.
- privileged Docker-in-Docker Pod보다 VM 내부 Docker 사용이 더 안전합니다.

### Pod workspace만 쓰지 않는 이유

Pod workspace는 Jupyter, code-server, batch job에는 효율적입니다. 그러나 현재 사용자 중에는 Kubernetes를 잘 모르고, Docker Compose, systemd, root 권한이 필요한 작업을 하는 경우가 있습니다. 따라서 기존 물리 노드 SSH 사용자를 흡수하는 기본 전환 경로는 VM이 더 자연스럽습니다.

권장 분리:

| 사용 사례 | 기본 실행 방식 |
| --- | --- |
| 일반 개발, Docker Compose, root 권한 필요 | KubeVirt VM |
| 짧은 GPU batch, Kubernetes-native job | Pod/Job |
| A100 MIG 공유 GPU 실험 | Pod/Job 우선 |
| 전용 GPU가 필요한 장기 개발 | 별도 GPU passthrough VM 검토 |

## 목표 아키텍처

```text
TwinX Kubernetes Cluster
├── kubevirt namespace
│   ├── virt-operator
│   ├── virt-api
│   ├── virt-controller
│   └── virt-handler DaemonSet
│
├── user-<id> namespace
│   ├── VM: vm-<id>
│   ├── PVC: vm-<id>-root
│   ├── PVC: vm-<id>-data
│   ├── Service: ssh-vm-<id>
│   ├── ResourceQuota / LimitRange
│   └── RoleBinding / NetworkPolicy
│
└── shared services
    ├── Ceph/RBD 또는 NFS-backed PVC
    ├── Keycloak/OIDC 기반 접근 정책
    ├── 필요 시 MetalLB/Gateway 노출
    └── Nucleus 또는 다른 TwinX 서비스를 Service/Endpoint/DNS로 제공
```

## 리소스 모델

VM 하나는 **하나의 Kubernetes 노드**에 스케줄됩니다. 한 VM이 어떤 노드의 CPU, 다른 노드의 메모리, 또 다른 노드의 GPU를 조합해서 사용할 수는 없습니다.

가능한 형태:

```text
vm-user-a on l40s
- CPU from l40s
- Memory from l40s
- GPU from l40s, if passthrough is configured
- Storage from Ceph/NFS PVC
```

불가능한 형태:

```text
single VM
- GPU from l40s
- CPU from sv4000-1
- Memory from rm352-1
```

여러 노드 자원을 함께 쓰려면 VM 하나가 아니라 여러 VM/Pod와 Ray, Spark, Slurm, MPI, Kubernetes Job 같은 분산 실행 구조를 사용해야 합니다.

## 네트워크 모델

KubeVirt VM은 라우팅과 정책이 허용되면 다른 cluster 서비스나 node-local 서비스에 접근할 수 있습니다. 예를 들어 Nucleus local DB가 다른 노드에서 routable address로 listen 중이면 VM에서 node IP 또는 안정적인 DNS 이름으로 접속할 수 있습니다.

권장 방식:

- 사용자가 물리 node IP를 외우게 하지 않습니다.
- node-local 공유 서비스는 Kubernetes Service/Endpoint 또는 안정적인 내부 DNS로 감쌉니다.
- 사용자 namespace에서 필요한 서비스만 접근할 수 있도록 NetworkPolicy를 명시합니다.

## 버전 결정

### 변경 전 repository 상태

- GitOps app: `argocd/twinx-infra/values.yaml`
- Application entry: `kubevirt-operator`
- 이전 상태: `enabled: false`
- 기존 manifest 버전: `v1.7.0`
- 현재 cluster 배포 상태: pre-check 중 활성 `kubevirt` namespace, `virt-operator`, KubeVirt CR은 관측되지 않음

### 선택한 버전

**KubeVirt `v1.8.4`**를 사용합니다.

이유:

- `v1.8.4`는 2026-06-28 기준 upstream stable release endpoint에서 확인한 KubeVirt 공식 stable release입니다.
- TwinX는 현재 Kubernetes `v1.35.4`이므로 오래된 `v1.7.0` manifest를 유지하는 것보다 최신 stable KubeVirt를 준비하는 것이 낫습니다.
- 이번 변경은 GitOps manifest 준비까지만 수행합니다. Application을 enable하고 sync하기 전까지 KubeVirt는 배포되지 않습니다.

## GitOps 변경 내용

저장소: `TwinX`

수정한 파일:

- `argocd/twinx-infra/apps/kubevirt-operator/kubevirt-operator.yaml`
  - KubeVirt 공식 `v1.8.4` manifest로 교체
- `argocd/twinx-infra/values.yaml`
  - disabled 상태의 KubeVirt Application entry 위에 안전 주석 추가
  - `enabled: false` 유지

의도적으로 유지한 것:

- `argocd/twinx-infra/apps/kubevirt-operator/kubevirt-cr.yaml`
  - 공식 `v1.8.4` CR 형태가 기존 CR과 사실상 동일함
- `kubevirt-operator.enabled`
  - 즉시 ArgoCD 자동 배포가 일어나지 않도록 `false` 유지

## `enabled: false`를 유지하는 이유

`argocd/twinx-infra/templates/applications.yaml` 템플릿은 enabled application에 자동 sync policy를 붙입니다.

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

따라서 `kubevirt-operator.enabled`를 `true`로 바꾸고 push하면 ArgoCD가 KubeVirt resource를 자동으로 생성하고 reconcile할 수 있습니다. KubeVirt는 cluster-wide CRD, webhook, controller, `virt-handler` DaemonSet을 설치하므로 단순 manifest 준비가 아니라 계획된 cluster 변경으로 다뤄야 합니다.

## 배포 전 점검

Application을 enable하기 전에 아래를 확인합니다.

```bash
# 현재 cluster와 node 상태
kubectl get nodes -o wide
kubectl get nodes -l kubevirt.io/schedulable=true

# KubeVirt가 부분 설치된 상태가 아닌지 확인
kubectl get ns kubevirt || true
kubectl get crd kubevirts.kubevirt.io || true
kubectl get kubevirt -A || true
kubectl get pods -n kubevirt || true

# VM disk를 위한 storage 사전 조건 확인
kubectl get storageclass
kubectl get pvc -A | grep -Ei 'cdi|kubevirt|vm' || true

# ArgoCD app 상태
kubectl -n argocd get applications | grep -Ei 'twinx-infra|kubevirt' || true
```

메모:

- `kubevirt.io/schedulable=true` 같은 오래된 label은 이전 실험에서 남아 있을 수 있습니다. 이 label만으로 현재 KubeVirt가 설치되어 있다고 판단하면 안 됩니다.
- VM disk image import에 DataVolume workflow가 필요하면 CDI는 별도로 계획해야 합니다.
- GPU passthrough보다 CPU-only VM smoke test를 먼저 진행합니다.

## enable 및 sync 절차

1. `TwinX/argocd/twinx-infra/values.yaml`에서 app flag를 변경합니다.

```yaml
kubevirt-operator:
  enabled: true
```

2. commit 후 push합니다.
3. parent `twinx-infra` app 또는 생성된 `kubevirt-operator` app을 sync합니다.
4. KubeVirt 상태를 확인합니다.

```bash
kubectl get ns kubevirt
kubectl get pods -n kubevirt -o wide
kubectl get kubevirt -n kubevirt
kubectl -n kubevirt wait kv kubevirt --for=condition=Available --timeout=10m
kubectl get daemonset -n kubevirt virt-handler -o wide
```

기대 결과:

- `virt-operator`가 Running 상태입니다.
- KubeVirt CR이 `Available` 상태가 됩니다.
- schedulable node에서 `virt-handler`가 Running 상태입니다.
- KubeVirt CRD가 생성되어 있습니다.

## 기본 동작 테스트 계획

KubeVirt가 Available 상태가 된 뒤에는 작은 CPU VM 하나만 먼저 생성합니다.

기본 동작 테스트 확인 명령:

```bash
kubectl get vm -A
kubectl get vmi -A
kubectl get pods -A | grep virt-launcher
kubectl describe vmi <test-vmi> -n <test-namespace>
```

성공 기준:

- VM이 시작됩니다.
- VM이 IP 또는 기대한 network attachment를 받습니다.
- SSH 또는 console 접속이 됩니다.
- VM disk가 stop/start 이후에도 유지됩니다.
- Cilium, Rook-Ceph, GPU Operator, Harbor, Keycloak에 예상치 못한 영향이 없습니다.

## 사용자 VM 템플릿 방향

기본 namespace와 resource 이름:

```text
namespace: user-<id>
vm:        vm-<id>
root pvc:  vm-<id>-root
home pvc:  vm-<id>-data
ssh svc:   ssh-vm-<id>
```

기본 VM profile:

| Profile | 사용 사례 | 예시 quota |
| --- | --- | --- |
| `cpu-small` | 가벼운 TwinX 개발 | 4 vCPU / 16Gi RAM / 100Gi disk |
| `cpu-medium` | 일반 Docker Compose 작업 | 8 vCPU / 32Gi RAM / 200Gi disk |
| `cpu-large` | 무거운 build/test | 16 vCPU / 64Gi RAM / 500Gi disk |
| `gpu-dedicated` | GPU passthrough 실험 | node 고정, 별도 승인 필요 |

기본 policy:

- 사용자 namespace마다 `ResourceQuota`를 적용합니다.
- 기본 CPU/memory request를 위해 `LimitRange`를 사용합니다.
- 필요한 내부 서비스만 접근할 수 있도록 `NetworkPolicy`를 사용합니다.
- hostPath와 host Docker socket mount는 피합니다.
- privileged Docker-in-Docker Pod 대신 VM 내부 Docker를 사용합니다.

## GPU 계획

처음부터 GPU passthrough로 시작하지 않습니다.

권장 순서:

1. CPU-only VM smoke test
2. persistent disk test
3. Nucleus 등 내부 서비스 접근 test
4. CDI/image workflow test
5. 이후 dedicated test node에서 GPU passthrough 평가

이유:

- GPU passthrough는 보통 물리 GPU가 있는 노드에 VM을 고정합니다.
- GPU Operator, device plugin, MIG manager, DRA 계획과 상호작용할 수 있습니다.
- 공유 A100 MIG workload는 당분간 Kubernetes Pod/Job allocation 방식이 더 안전합니다.

## 중단 및 rollback 기준

아래 중 하나라도 발생하면 rollout을 중단합니다.

- KubeVirt webhook이 무관한 Kubernetes resource 생성을 막습니다.
- `virt-handler`가 node instability를 유발합니다.
- Cilium, Rook-Ceph, GPU Operator, Harbor, Keycloak pod가 회귀합니다.
- 계획한 시간 안에 KubeVirt CR이 `Available` 상태가 되지 않습니다.

Rollback 접근:

1. KubeVirt control plane이 정상인지 확인하기 전에는 사용자 VM을 만들지 않습니다.
2. KubeVirt control plane만 설치된 상태라면, production VM이 없는 것을 확인한 뒤 `kubevirt-operator.enabled: false`로 되돌리고 sync합니다.
3. VM이 이미 존재한다면 prune/delete를 허용하기 전에 VM을 중지하고 VM disk를 export/backup합니다.

## 현재 결과

이 runbook 작성 시점 기준:

- KubeVirt 배포는 **활성화하지 않았습니다**.
- KubeVirt 대상 ArgoCD sync는 **실행하지 않았습니다**.
- GitOps manifest만 KubeVirt `v1.8.4` 기준으로 준비했습니다.
- 다음 작업은 계획된 preflight와 명시적인 enable/sync window입니다.
