# Kubernetes Notes

Kubernetes-focused references and upgrade plans used while operating the TwinX and MiniX clusters.
These notes were migrated from [`kubernetes-study`](https://github.com/mj006648/kubernetes-study) so operational Kubernetes material can live with the rest of the NetAI runbook.

## Index

| Date | Topic | Document |
| --- | --- | --- |
| 2026-06-25 | TwinX Kubernetes 1.35.4 upgrade, Kubespray, Hubble, DRA, Ceph/Harbor/Partridge blockers | [TwinX Kubernetes 1.35 Upgrade Plan](twinx-kubernetes-1-35-upgrade-plan.md) |
| 2026-06-25 | Kubernetes ServiceAccount, token behavior, Role/ClusterRole, RBAC examples | [ServiceAccount and RBAC](serviceaccount-rbac.md) |
| 2026-06-25 | Gateway API, GatewayClass, Gateway, HTTPRoute, role separation | [Gateway API](gateway-api.md) |
| 2026-06-25 | PersistentVolume, PersistentVolumeClaim, StorageClass, dynamic provisioning | [Persistent Volumes and Claims](persistent-volumes.md) |
| 2026-06-25 | Dynamic Resource Allocation for GPUs and accelerators | [Dynamic Resource Allocation](dynamic-resource-allocation.md) |

## Groups

### Guides

- **[ServiceAccount and RBAC](serviceaccount-rbac.md)** — service identity, token handling, Role/ClusterRole, and practical RBAC examples.
- **[Gateway API](gateway-api.md)** — role-oriented service networking and HTTP routing patterns.
- **[Persistent Volumes and Claims](persistent-volumes.md)** — PV, PVC, StorageClass, dynamic provisioning, and operational storage examples.
- **[Dynamic Resource Allocation](dynamic-resource-allocation.md)** — DRA concepts for GPU and accelerator allocation.

### Upgrade plans

- **[TwinX Kubernetes 1.35 Upgrade Plan](twinx-kubernetes-1-35-upgrade-plan.md)** — Kubespray 1.35.4 path, Hubble, DRA, node-specific drain risks, Ceph/Harbor/Partridge blockers, and preflight checks.
