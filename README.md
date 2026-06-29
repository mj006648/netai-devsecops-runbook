# NetAI Operations Runbook

[GIST NetAI Lab](https://netai.smartx.kr/)에서 **TwinX**와 **MiniX** 클러스터를 운영하며 쌓은 운영 런북입니다.
네트워킹, 스토리지, 정책, 관측, 애플리케이션, Kubernetes 운영, 장애 대응 기록을 한 곳에 정리합니다.

> 주 대상은 랩 내부 운영자입니다.
> 완성된 매뉴얼이라기보다 운영 중 계속 갱신하는 작업 노트에 가깝습니다.
> 공개 저장소로 두는 이유는 비슷한 문제를 만난 사람이 그대로 참고할 수 있게 하기 위해서입니다.

## Quick map

최근 또는 중요한 운영 이슈를 바로 찾기 위한 표입니다. `Last update`는 해당 문서의 최근 반영일입니다.

| Last update | Area | Issue / note | Contents |
| --- | --- | --- | --- |
| 2026-06-29 | Networking / Cilium | [TwinX Cilium GitOps 및 Hubble 전환 계획](networking/twinx-cilium-gitops-hubble-plan-2026-06-29.md) | Kubespray가 설치한 Cilium을 ArgoCD GitOps 관리로 넘기기 위한 DataX 비교, 현재 TwinX 값, Hubble 단계, 중단 기준 |
| 2026-06-29 | Kubernetes / Registry | [TwinX Harbor RWO PVC Rollout Deadlock](kubernetes/registry/twinx-harbor-rwo-pvc-rollout-deadlock-2026-06-29.md) | Harbor registry/jobservice가 RWO PVC와 RollingUpdate 조합으로 ContainerCreating에 걸린 원인, 잘못된 Recreate 시도, PR #209 node pinning fix와 검증 |
| 2026-06-28 | Kubernetes / Secrets | [TwinX OpenBao Sealed Recovery](kubernetes/secrets/twinx-openbao-sealed-recovery-2026-06-28.md) | OpenBao sealed 상태로 ESO와 Trident ExternalSecret이 Degraded 된 장애 복구, `operator init` 금지 조건, unseal 및 검증 절차 |
| 2026-06-28 | Kubernetes / GPU | [TwinX NVIDIA DRA Driver Rollout](kubernetes/gpu/twinx-nvidia-dra-driver-rollout-2026-06-28.md) | GPU Operator v25.3.4 환경에서 NVIDIA DRA driver chart 25.3.2를 GitOps로 추가하고 GPU/MIG/ComputeDomain DeviceClass와 ResourceSlice 검증 |
| 2026-06-28 | Kubernetes / Virtualization | [TwinX KubeVirt User VM Plan](kubernetes/virtualization/twinx-kubevirt-user-vm-plan-2026-06-28.md) | 사용자별 KubeVirt VM 제공 설계, v1.8.4 선택 이유, GitOps 준비 결과, 배포 전 preflight와 중단 기준 |
| 2026-06-26 | Kubernetes / Karmada | [Karmada ScaleX-POD Lab](kubernetes/karmada/) | MiniX kind 기반 Karmada 실험 00~14, OverridePolicy image/storageClass, Resource Pool fallback, NoExecute failover, WorkloadRebalancer 재균형 |
| 2026-06-26 | Kubernetes / Upgrade | [TwinX Kubernetes Upgrade Run 2026-06-26](kubernetes/upgrades/twinx-kubernetes-upgrade-run-2026-06-26.md) | 당일 preflight 결과, OTP 임시 해제, Harbor/Ceph/Partridge/Kubespray blocker, 축소된 1차 wave |
| 2026-06-25 | Kubernetes / Upgrade | [TwinX Kubernetes 1.35 Upgrade Plan](kubernetes/upgrades/twinx-kubernetes-1-35-upgrade-plan.md) | TwinX Kubespray `1.33 -> 1.35.4` 계획, Ceph/Harbor/Partridge/l40s blocker, Hubble/DRA 적용 순서 |
| 2026-06-25 | Incident | [MiniX Kubespray Upgrade Troubleshooting](incidents/minix-kubespray-upgrade-2026-06-25.md) | Cilium 권한, kubeadm health-check timeout, Rook-Ceph PDB drain block, CoreDNS loop, GPU node API timeout |
| 2026-06-25 | Incident | [Cluster Cascade](incidents/cluster-cascade.md) | OTel, Cilium hostNetwork, Rook-Ceph 재구축으로 이어진 연쇄 장애 정리 |
| 2026-06-25 | Networking | [rm352 Pod Communication](networking/rm352-pod-comms.md) | rm352 GPU Operator 실패, kubelet 단절, pod-to-node/API 통신 문제 원인과 해결 |
| 2026-06-25 | Networking | [MTU / Cilium Instability](networking/mtu-cilium.md) | MTU 불일치로 인한 OSD flapping과 클러스터 불안정 |
| 2026-06-25 | Networking | [Netplan Secondary IP](networking/netplan-secondary-ip.md) | secondary IP 추가 후 노드가 NotReady 되는 문제 |
| 2026-06-25 | Storage | [Rook-Ceph Reinstall](storage/rook-ceph-reinstall.md) | Rook-Ceph 전체 재설치와 단계별 bring-up 절차 |
| 2026-06-25 | Storage | [LV Preparation](storage/lv-preparation.md) | 재부팅 후 Ceph OSD가 올라오지 않는 stale LVM PV 문제 |
| 2026-06-25 | Policy | [Kyverno + cert-manager](policy/kyverno-cert-manager.md) | Kyverno chart v3.7.x에서 인증서 ping-pong이 반복되는 문제 |
| 2026-06-25 | Policy | [Webhook Cert SIGTERM](policy/webhook-cert-sigterm.md) | webhook controller가 인증서 owner 충돌로 주기적 SIGTERM 재시작되는 문제 |

## Sections

- **[kubernetes/](kubernetes/)** — Kubernetes 운영 계획과 공부 문서
  - **[kubernetes/karmada/](kubernetes/karmada/)** — ScaleX-POD Karmada 멀티클러스터 실험과 운영 runbook
  - **[kubernetes/gpu/](kubernetes/gpu/)** — GPU Operator, NVIDIA DRA, MIG, GPU node 운영
  - **[kubernetes/secrets/](kubernetes/secrets/)** — OpenBao, External Secrets Operator, GitOps secret delivery 운영
  - **[kubernetes/registry/](kubernetes/registry/)** — Harbor registry, image storage, RWO PVC rollout 운영
  - **[kubernetes/upgrades/](kubernetes/upgrades/)** — Kubespray 업그레이드, Hubble, DRA 적용 계획
  - **[kubernetes/virtualization/](kubernetes/virtualization/)** — KubeVirt 기반 사용자별 VM 제공 계획과 운영 절차
- **[networking/](networking/)** — netplan, Cilium, MTU, secondary IP, 노드 라우팅
- **[storage/](storage/)** — Rook-Ceph 설치·복구·튜닝, LVM 준비
- **[policy/](policy/)** — Kyverno, cert-manager, webhook lifecycle
- **[observability/](observability/)** — Prometheus, Grafana, OpenTelemetry
- **[apps/](apps/)** — TwinX/MiniX 앱, 포털, 카탈로그 서비스, 쿼리 엔진
- **[incidents/](incidents/)** — 장애 대응 기록과 postmortem

## Note format

각 노트는 아래 형식을 기준으로 작성합니다.

- **Symptom** — 실제로 관측되는 현상
- **Diagnosis** — 확인에 사용한 정확한 명령
- **Root cause** — 왜 발생했는지
- **Fix** — 복구 절차
- **Prevention** — 다음에 같은 문제를 피하는 방법

## Discussions

정식 문서로 정리하기 전의 질문이나 메모는 [Discussions](https://github.com/mj006648/netai-devsecops-runbook/discussions)에 남깁니다.

## License

This repository is licensed under the [MIT License](LICENSE).
