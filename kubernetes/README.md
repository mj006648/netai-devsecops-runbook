# Kubernetes Notes

TwinX와 MiniX 클러스터를 운영하면서 필요한 Kubernetes 참고 문서와 업그레이드 계획을 모아둔 공간입니다.
기존 [`kubernetes-study-archive`](https://github.com/mj006648/kubernetes-study-archive)에 있던 문서를 이 런북으로 옮겼습니다.
앞으로 Kubernetes 운영 문서는 이 디렉터리에 추가합니다.

## Index

| Last update | Type | Topic | Document |
| --- | --- | --- | --- |
| 2026-06-29 | Cluster lifecycle | TwinX control1 단일 control-plane 전환 완료, control2/control3 제거, GPU Operator/NFD/DRA controller sv4000-1 이동 | [TwinX Single Control Plane Transition](cluster-lifecycle/twinx-single-control-plane-transition-2026-06-29.md) |
| 2026-06-29 | Registry / Harbor | Harbor registry/jobservice RWO PVC rollout deadlock, chart Recreate 렌더링 실패, rm352-1 node pinning fix | [TwinX Harbor RWO PVC Rollout Deadlock](registry/twinx-harbor-rwo-pvc-rollout-deadlock-2026-06-29.md) |
| 2026-06-28 | Secrets / OpenBao | OpenBao sealed 상태로 ESO와 Trident ExternalSecret이 Degraded 된 장애 복구, unseal 절차, 재발 방지 | [TwinX OpenBao Sealed Recovery](secrets/twinx-openbao-sealed-recovery-2026-06-28.md) |
| 2026-06-28 | GPU | TwinX GPU Operator v25.3.4, NVIDIA DRA driver 25.3.2, GPU/MIG/ComputeDomain DeviceClass와 ResourceSlice 검증 | [TwinX NVIDIA DRA Driver Rollout](gpu/twinx-nvidia-dra-driver-rollout-2026-06-28.md) |
| 2026-06-28 | Virtualization | 사용자별 KubeVirt VM 제공, v1.8.4 GitOps 준비, preflight, smoke test, rollback 기준 | [TwinX KubeVirt User VM Plan](virtualization/twinx-kubevirt-user-vm-plan-2026-06-28.md) |
| 2026-06-26 | Karmada | ScaleX-POD 멀티클러스터 실험, OverridePolicy image/storageClass, Resource Pool fallback, role label placement, WorkloadRebalancer | [Karmada ScaleX-POD Lab](karmada/) |
| 2026-06-27 | Upgrade run | TwinX v1.35.4 업그레이드 완료 노드, edgebox1/2 완료, edgebox3/4 보류, Kubespray no-drain 패치, Ceph/Harbor/OTP 남은 작업 | [TwinX Kubernetes Upgrade Run 2026-06-26](cluster-lifecycle/twinx-kubernetes-upgrade-run-2026-06-26.md) |
| 2026-06-25 | Upgrade | TwinX Kubernetes 1.35.4 업그레이드, Kubespray, Hubble, DRA, Ceph/Harbor/Partridge blocker | [TwinX Kubernetes 1.35 Upgrade Plan](cluster-lifecycle/twinx-kubernetes-1-35-upgrade-plan.md) |

## Directories

- **[karmada/](karmada/)** — ScaleX-POD Karmada 멀티클러스터 실험과 운영 runbook
- **[gpu/](gpu/)** — GPU Operator, NVIDIA DRA, MIG, GPU node 운영
- **[secrets/](secrets/)** — OpenBao, External Secrets Operator, GitOps secret delivery 운영
- **[registry/](registry/)** — Harbor registry, image storage, RWO PVC rollout 운영
- **[cluster-lifecycle/](cluster-lifecycle/)** — Kubernetes version upgrade, control-plane/etcd topology 변경, node 제거, maintenance window 계획
- **[virtualization/](virtualization/)** — KubeVirt 기반 사용자별 VM 계획과 운영 runbook
