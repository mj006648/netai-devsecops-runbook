# Kubernetes Networking

Cilium, Hubble, MTU, Pod communication, and Kubernetes-related node routing runbooks.

## Quick map

| Last update | Topic | Document | Contents |
| --- | --- | --- | --- |
| 2026-07-01 | Cilium / Hubble | [TwinX Cilium GitOps 및 Hubble 운영 기록](twinx-cilium-hubble-gitops-2026-07-01.md) | Cilium GitOps ownership 전환, Hubble relay/metrics 활성화, certgen Job, relay hostNetwork 복구 |
| 2026-06-25 | Cilium / MTU | [MTU / Cilium Instability](mtu-cilium.md) | MTU 불일치로 인한 OSD flapping과 클러스터 불안정 |
| 2026-06-25 | Pod communication | [rm352 Pod Communication](rm352-pod-comms.md) | rm352 GPU Operator 실패, kubelet 단절, pod-to-node/API 통신 문제 |
| 2026-06-25 | Netplan | [Netplan Secondary IP](netplan-secondary-ip.md) | secondary IP 추가 후 노드 NotReady 문제 |
