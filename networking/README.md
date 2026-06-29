# Networking Runbooks

TwinX와 MiniX에서 겪은 네트워크 운영 이슈와 계획을 정리한다.  
각 문서는 증상, 진단 명령, 원인, 해결 또는 전환 계획, 재발 방지 관점으로 작성한다.

## Quick map

| Last update | Topic | Note | Contents |
| --- | --- | --- | --- |
| 2026-06-29 | Cilium / Hubble | [TwinX Cilium GitOps 및 Hubble 전환 계획](twinx-cilium-gitops-hubble-plan-2026-06-29.md) | Kubespray가 설치한 Cilium을 ArgoCD GitOps 관리로 넘기기 위한 DataX 비교, 현재 TwinX 값, Hubble 단계, 중단 기준 |
| 2026-06-25 | Cilium / MTU | [MTU / Cilium Instability](mtu-cilium.md) | MTU 불일치로 인한 OSD flapping과 클러스터 불안정 |
| 2026-06-25 | Node routing | [rm352 Pod Communication](rm352-pod-comms.md) | rm352 GPU Operator 실패, kubelet 단절, pod-to-node/API 통신 문제 원인과 해결 |
| 2026-06-25 | Netplan | [Netplan Secondary IP](netplan-secondary-ip.md) | secondary IP 추가 후 노드가 NotReady 되는 문제 |
