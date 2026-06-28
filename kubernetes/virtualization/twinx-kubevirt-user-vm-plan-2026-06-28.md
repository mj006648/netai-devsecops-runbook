# TwinX KubeVirt User VM Plan — 2026-06-28

## Summary

TwinX 클러스터에는 Kubernetes를 직접 사용하는 사용자와 물리 노드에 SSH로 접속해 Docker 컨테이너를 직접 띄우는 사용자가 함께 있다. 이 방식은 노드 오염, 리소스 추적 어려움, 업그레이드 시 drain/blocker 증가, 사용자별 격리 부족 문제가 있다.

본 계획은 **Kubernetes를 인프라 레이어로 숨기고, Kubernetes를 모르는 사용자에게는 사용자별 KubeVirt VM을 제공**하는 것을 목표로 한다. GitOps에는 KubeVirt 공식 `v1.8.4` 매니페스트를 준비하되, ArgoCD 자동 동기화로 즉시 배포되지 않도록 현재는 Application을 비활성화 상태로 유지한다.

## Goal

- 사용자별로 `vm-<user>` 형태의 VM을 제공한다.
- 사용자는 기존처럼 SSH로 접속하고 VM 내부에서 Docker, Docker Compose, Python, TwinX 작업을 수행한다.
- 운영자는 Kubernetes 리소스로 CPU, Memory, Storage, GPU, 네트워크 접근을 추적하고 제한한다.
- 물리 노드 SSH 직접 사용을 줄이고, 사용자 작업을 VM/namespace 단위로 격리한다.

## Why this design

### Why KubeVirt VM instead of direct node SSH

기존 방식:

```text
user -> physical node SSH -> docker run / docker compose / local changes
```

문제:

- 물리 노드에 사용자 변경이 직접 남는다.
- 누가 어떤 컨테이너와 포트를 쓰는지 추적하기 어렵다.
- CPU/RAM/GPU 사용량을 사용자별로 제한하기 어렵다.
- 노드 업그레이드, 재부팅, drain 작업 때 사용자 컨테이너가 blocker가 된다.
- Docker socket, host path, root 권한 사용이 운영 리스크가 된다.

KubeVirt 방식:

```text
user -> vm-<user> SSH -> docker run / docker compose / TwinX work
```

장점:

- 사용자는 서버 하나를 받은 것처럼 쓴다.
- 관리자는 Kubernetes에서 VM, PVC, Service, Quota, RBAC을 추적한다.
- VM 단위로 정지, 백업, 삭제, 리소스 조정이 가능하다.
- Docker-in-Docker privileged Pod보다 VM 안 Docker가 더 안전하다.

### Why not only Pod workspaces

Pod workspace는 Jupyter, code-server, batch job에는 효율적이다. 그러나 현재 사용자는 Kubernetes를 잘 모르고, Docker Compose/systemd/root 권한이 필요한 작업도 있다. 따라서 기본 전환 경로는 VM이 더 자연스럽다.

권장 분리:

| Use case | Default runtime |
| --- | --- |
| 일반 개발, Docker Compose, root 권한 필요 | KubeVirt VM |
| 짧은 GPU batch, Kubernetes-native job | Pod/Job |
| A100 MIG 공유 GPU 실험 | Pod/Job 우선 |
| 전용 GPU가 필요한 장기 개발 | 별도 GPU passthrough VM 검토 |

## Target architecture

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
    ├── Ceph/RBD or NFS-backed PVC
    ├── Keycloak/OIDC-backed access policy
    ├── MetalLB/Gateway exposure if needed
    └── Nucleus or other TwinX services through Service/Endpoint/DNS
```

## Resource model

A VM is scheduled onto **one Kubernetes node**. It cannot combine CPU from one node, memory from another node, and GPU from a third node.

Possible:

```text
vm-user-a on l40s
- CPU from l40s
- Memory from l40s
- GPU from l40s, if passthrough is configured
- Storage from Ceph/NFS PVC
```

Not possible:

```text
single VM
- GPU from l40s
- CPU from sv4000-1
- Memory from rm352-1
```

For multi-node compute, use several VMs/Pods and a distributed framework such as Ray, Spark, Slurm, MPI, or Kubernetes Jobs.

## Network model

KubeVirt VMs can access other cluster or node services if routing and policy allow it. For example, if a Nucleus local DB is running on another node and listens on a routable address, a VM can connect to it by node IP or a stable DNS name.

Preferred approach:

- Do not make users remember physical node IPs.
- Wrap node-local shared services with Kubernetes Service/Endpoint or stable internal DNS.
- Use NetworkPolicy to explicitly allow needed service access from user namespaces.

## Version decision

### Current repository state before this change

- GitOps app: `argocd/twinx-infra/values.yaml`
- Application entry: `kubevirt-operator`
- Previous state: `enabled: false`
- Existing manifest version: `v1.7.0`
- Current cluster deployment: no active `kubevirt` namespace, `virt-operator`, or KubeVirt CR observed during pre-check.

### Selected version

Use **KubeVirt `v1.8.4`**.

Reason:

- `v1.8.4` is the KubeVirt official stable release checked from the upstream stable release endpoint on 2026-06-28.
- TwinX is now on Kubernetes `v1.35.4`; using a newer KubeVirt stable is safer than keeping the older `v1.7.0` manifest.
- The change only prepares GitOps manifests. It does not deploy KubeVirt until the Application is enabled and synced.

## What changed in GitOps

Repository: `TwinX`

Updated:

- `argocd/twinx-infra/apps/kubevirt-operator/kubevirt-operator.yaml`
  - replaced with official KubeVirt `v1.8.4` manifest
- `argocd/twinx-infra/values.yaml`
  - added a safety note above the disabled KubeVirt Application entry
  - kept `enabled: false`

Intentionally unchanged:

- `argocd/twinx-infra/apps/kubevirt-operator/kubevirt-cr.yaml`
  - official `v1.8.4` CR shape is effectively the same as the existing CR
- `kubevirt-operator.enabled`
  - remains `false` to avoid immediate ArgoCD automated deployment

## Why `enabled: false` remains

The `argocd/twinx-infra/templates/applications.yaml` template gives enabled applications an automated sync policy:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Therefore flipping `kubevirt-operator.enabled` to `true` and pushing can cause ArgoCD to create and reconcile KubeVirt resources automatically. KubeVirt installs cluster-wide CRDs, webhooks, controllers, and a `virt-handler` DaemonSet. That should be treated as a planned cluster change, not a passive manifest update.

## Deployment preflight

Run these before enabling the app:

```bash
# Current cluster and node state
kubectl get nodes -o wide
kubectl get nodes -l kubevirt.io/schedulable=true

# Confirm KubeVirt is not partially installed
kubectl get ns kubevirt || true
kubectl get crd kubevirts.kubevirt.io || true
kubectl get kubevirt -A || true
kubectl get pods -n kubevirt || true

# Storage prerequisites for VM disks
kubectl get storageclass
kubectl get pvc -A | grep -Ei 'cdi|kubevirt|vm' || true

# ArgoCD app status
kubectl -n argocd get applications | grep -Ei 'twinx-infra|kubevirt' || true
```

Notes:

- Old labels such as `kubevirt.io/schedulable=true` can remain from an earlier experiment. They are not proof that KubeVirt is currently installed.
- CDI should be planned separately if VM disk images need DataVolume/import workflows.
- Start with CPU-only VM smoke tests before GPU passthrough.

## Enable and sync procedure

1. Change the app flag in `TwinX/argocd/twinx-infra/values.yaml`:

```yaml
kubevirt-operator:
  enabled: true
```

2. Commit and push.
3. Sync the parent `twinx-infra` app or the generated `kubevirt-operator` app.
4. Watch KubeVirt:

```bash
kubectl get ns kubevirt
kubectl get pods -n kubevirt -o wide
kubectl get kubevirt -n kubevirt
kubectl -n kubevirt wait kv kubevirt --for=condition=Available --timeout=10m
kubectl get daemonset -n kubevirt virt-handler -o wide
```

Expected result:

- `virt-operator` runs.
- KubeVirt CR reaches `Available`.
- `virt-handler` is running on schedulable nodes.
- KubeVirt CRDs are present.

## Smoke test plan

After KubeVirt is available, create only a small CPU VM first.

Smoke test checks:

```bash
kubectl get vm -A
kubectl get vmi -A
kubectl get pods -A | grep virt-launcher
kubectl describe vmi <test-vmi> -n <test-namespace>
```

Success criteria:

- VM starts.
- VM gets an IP or expected network attachment.
- SSH or console access works.
- VM disk persists after stop/start.
- No unexpected impact to Cilium, Rook-Ceph, GPU Operator, Harbor, or Keycloak.

## User VM template direction

Default namespace and resource naming:

```text
namespace: user-<id>
vm:        vm-<id>
root pvc:  vm-<id>-root
home pvc:  vm-<id>-data
ssh svc:   ssh-vm-<id>
```

Default VM profiles:

| Profile | Use case | Example quota |
| --- | --- | --- |
| `cpu-small` | light TwinX development | 4 vCPU / 16Gi RAM / 100Gi disk |
| `cpu-medium` | normal Docker Compose work | 8 vCPU / 32Gi RAM / 200Gi disk |
| `cpu-large` | heavy build/test | 16 vCPU / 64Gi RAM / 500Gi disk |
| `gpu-dedicated` | GPU passthrough experiment | node-pinned, separate approval |

Policy defaults:

- Use `ResourceQuota` per user namespace.
- Use `LimitRange` for default CPU/memory requests.
- Use `NetworkPolicy` to allow only required internal services.
- Avoid hostPath and host Docker socket mounts.
- Use VM-internal Docker instead of privileged Docker-in-Docker Pods.

## GPU plan

Do not start with GPU passthrough.

Recommended order:

1. CPU-only VM smoke test.
2. Persistent disk test.
3. Internal service access test, including Nucleus if needed.
4. CDI/image workflow test.
5. Only then evaluate GPU passthrough for a dedicated test node.

Reason:

- GPU passthrough usually pins the VM to the node with the physical GPU.
- It may interact with GPU Operator, device plugin, MIG manager, and DRA plans.
- For shared A100 MIG workloads, Kubernetes Pod/Job allocation remains the safer first path.

## Stop / rollback criteria

Stop the rollout if any of these occur:

- KubeVirt webhooks block unrelated Kubernetes resource creation.
- `virt-handler` causes node instability.
- Cilium, Rook-Ceph, GPU Operator, Harbor, or Keycloak pods regress.
- KubeVirt CR does not become `Available` within the planned window.

Rollback approach:

1. Do not create user VMs until the KubeVirt control plane is healthy.
2. If only KubeVirt control plane was installed, set `kubevirt-operator.enabled: false` and sync after confirming no production VMs exist.
3. If VMs exist, stop and export/backup VM disks before allowing prune/delete actions.

## Current result

As of this runbook entry:

- KubeVirt deployment has **not** been enabled.
- ArgoCD sync has **not** been triggered for KubeVirt.
- GitOps manifests are prepared for KubeVirt `v1.8.4`.
- The next action is a planned preflight and explicit enable/sync window.
