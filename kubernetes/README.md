# Kubernetes Notes

TwinX와 MiniX 클러스터를 운영하면서 필요한 Kubernetes 참고 문서와 업그레이드 계획을 모아둔 공간입니다.
기존 [`kubernetes-study`](https://github.com/mj006648/kubernetes-study)에 있던 문서를 이 런북으로 옮겼습니다.
앞으로 Kubernetes 운영 문서는 이 디렉터리에 추가합니다.

## Index

| Date | Topic | Document |
| --- | --- | --- |
| 2026-06-25 | TwinX Kubernetes 1.35.4 업그레이드, Kubespray, Hubble, DRA, Ceph/Harbor/Partridge blocker | [TwinX Kubernetes 1.35 Upgrade Plan](twinx-kubernetes-1-35-upgrade-plan.md) |
| 2026-06-25 | ServiceAccount, token 동작, Role/ClusterRole, RBAC 예시 | [ServiceAccount and RBAC](serviceaccount-rbac.md) |
| 2026-06-25 | Gateway API, GatewayClass, Gateway, HTTPRoute, 역할 분리 | [Gateway API](gateway-api.md) |
| 2026-06-25 | PersistentVolume, PersistentVolumeClaim, StorageClass, 동적 프로비저닝 | [Persistent Volumes and Claims](persistent-volumes.md) |
| 2026-06-25 | GPU와 accelerator를 위한 Dynamic Resource Allocation | [Dynamic Resource Allocation](dynamic-resource-allocation.md) |

## Groups

### Guides

- **[ServiceAccount and RBAC](serviceaccount-rbac.md)** — 파드 신원, 토큰 처리, Role/ClusterRole, 실무 RBAC 예시
- **[Gateway API](gateway-api.md)** — 역할 기반 서비스 네트워킹과 HTTP routing 패턴
- **[Persistent Volumes and Claims](persistent-volumes.md)** — PV, PVC, StorageClass, 동적 프로비저닝, 운영 스토리지 예시
- **[Dynamic Resource Allocation](dynamic-resource-allocation.md)** — GPU와 accelerator 할당을 위한 DRA 개념

### Upgrade plans

- **[TwinX Kubernetes 1.35 Upgrade Plan](twinx-kubernetes-1-35-upgrade-plan.md)** — Kubespray 1.35.4 경로, Hubble, DRA, 노드별 drain 리스크, Ceph/Harbor/Partridge blocker, preflight 체크
