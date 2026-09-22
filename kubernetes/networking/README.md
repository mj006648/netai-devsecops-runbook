# Kubernetes Networking

Cilium, Hubble, MTU, Pod communication, and Kubernetes-related node routing runbooks.

## 처음 배우는 네트워크

[신호·스위치·라우터·패킷에서 Linux·eBPF·Cilium까지](networking-foundations/README.md): 기초 용어, 등장 이유, 손으로 추적하는 패킷 경로, 서브넷·MTU·BDP 계산, 안전한 로컬 실습과 해설 문제를 순서대로 읽는 독립 교재입니다. Kubernetes 사전 지식은 앞부분에 필요하지 않습니다.

## Quick map

| Last update | Topic | Document | Contents |
| --- | --- | --- | --- |
| 2026-07-01 | Cilium / Hubble | [TwinX Cilium GitOps 및 Hubble 운영 기록](twinx-cilium-hubble-gitops-2026-07-01.md) | Cilium GitOps ownership 전환, Hubble relay/metrics 활성화, certgen Job, relay hostNetwork 복구 |
| 2026-06-25 | Cilium / MTU | [MTU / Cilium Instability](mtu-cilium.md) | MTU 불일치로 인한 OSD flapping과 클러스터 불안정 |
| 2026-06-25 | Pod communication | [rm352 Pod Communication](rm352-pod-comms.md) | rm352 GPU Operator 실패, kubelet 단절, pod-to-node/API 통신 문제 |
| 2026-06-25 | Netplan | [Netplan Secondary IP](netplan-secondary-ip.md) | secondary IP 추가 후 노드 NotReady 문제 |
