# Kubernetes Notes

TwinX와 MiniX 클러스터를 운영하면서 필요한 Kubernetes 참고 문서와 업그레이드 계획을 모아둔 공간입니다.
기존 [`kubernetes-study-archive`](https://github.com/mj006648/kubernetes-study-archive)에 있던 문서를 이 런북으로 옮겼습니다.
앞으로 Kubernetes 운영 문서는 이 디렉터리에 추가합니다.

## Index

| Last update | Type | Topic | Document |
| --- | --- | --- | --- |
| 2026-06-28 | Virtualization | 사용자별 KubeVirt VM 제공, v1.8.4 GitOps 준비, preflight, smoke test, rollback 기준 | [TwinX KubeVirt User VM Plan](virtualization/twinx-kubevirt-user-vm-plan-2026-06-28.md) |
| 2026-06-26 | Karmada | ScaleX-POD 멀티클러스터 실험, OverridePolicy image/storageClass, Resource Pool fallback, role label placement, WorkloadRebalancer | [Karmada ScaleX-POD Lab](karmada/) |
| 2026-06-27 | Upgrade run | TwinX v1.35.4 업그레이드 완료 노드, edgebox1/2 완료, edgebox3/4 보류, Kubespray no-drain 패치, Ceph/Harbor/OTP 남은 작업 | [TwinX Kubernetes Upgrade Run 2026-06-26](upgrades/twinx-kubernetes-upgrade-run-2026-06-26.md) |
| 2026-06-25 | Upgrade | TwinX Kubernetes 1.35.4 업그레이드, Kubespray, Hubble, DRA, Ceph/Harbor/Partridge blocker | [TwinX Kubernetes 1.35 Upgrade Plan](upgrades/twinx-kubernetes-1-35-upgrade-plan.md) |
| 2026-06-25 | Study | ServiceAccount, token 동작, Role/ClusterRole, RBAC 예시 | [ServiceAccount and RBAC](study/serviceaccount-rbac.md) |
| 2026-06-25 | Study | Gateway API, GatewayClass, Gateway, HTTPRoute, 역할 분리 | [Gateway API](study/gateway-api.md) |
| 2026-06-25 | Study | PersistentVolume, PersistentVolumeClaim, StorageClass, 동적 프로비저닝 | [Persistent Volumes and Claims](study/persistent-volumes.md) |
| 2026-06-25 | Study | GPU와 accelerator를 위한 Dynamic Resource Allocation | [Dynamic Resource Allocation](study/dynamic-resource-allocation.md) |

## Directories

- **[karmada/](karmada/)** — ScaleX-POD Karmada 멀티클러스터 실험과 운영 runbook
- **[upgrades/](upgrades/)** — 운영 업그레이드 계획과 preflight/runbook
- **[virtualization/](virtualization/)** — KubeVirt 기반 사용자별 VM 계획과 운영 runbook
- **[study/](study/)** — Kubernetes 개념 공부와 참고용 정리
