# NetAI Operations Runbook

[GIST NetAI Lab](https://netai.smartx.kr/)에서 **TwinX**와 **MiniX** 클러스터를 운영하며 쌓은 운영 런북입니다.
네트워킹, 스토리지, 정책, 관측, 애플리케이션, Kubernetes 운영, 장애 대응 기록을 한 곳에 정리합니다.

> 주 대상은 랩 내부 운영자입니다.
> 완성된 매뉴얼이라기보다 운영 중 계속 갱신하는 작업 노트에 가깝습니다.
> 공개 저장소로 두는 이유는 비슷한 문제를 만난 사람이 그대로 참고할 수 있게 하기 위해서입니다.

## Quick map

| Area | Where | Last updated | Contents |
| --- | --- | --- | --- |
| Kubernetes | [kubernetes/](kubernetes/) | 2026-06-25 | Kubernetes 오브젝트 가이드, Kubespray 업그레이드 계획, DRA, Hubble 메모 |
| Networking | [networking/](networking/) | ongoing | Cilium, MTU, netplan, secondary IP, 노드·파드 통신 문제 |
| Storage | [storage/](storage/) | ongoing | Rook-Ceph, LVM 준비, 스토리지 복구 절차 |
| Policy | [policy/](policy/) | ongoing | Kyverno, cert-manager, webhook lifecycle |
| Observability | [observability/](observability/) | planned | Prometheus, Grafana, OpenTelemetry 운영 메모 |
| Apps | [apps/](apps/) | planned | TwinX/MiniX 애플리케이션 운영 메모 |
| Incidents | [incidents/](incidents/) | 2026-06-25 | 시간순 장애 대응 기록과 사후 정리 |

## Sections

- **[networking/](networking/)** — netplan, Cilium, MTU, secondary IP, 노드 라우팅
- **[storage/](storage/)** — Rook-Ceph 설치·복구·튜닝, LVM 준비
- **[policy/](policy/)** — Kyverno, cert-manager, webhook lifecycle
- **[observability/](observability/)** — Prometheus, Grafana, OpenTelemetry
- **[apps/](apps/)** — TwinX/MiniX 앱, 포털, 카탈로그 서비스, 쿼리 엔진
- **[kubernetes/](kubernetes/)** — Kubernetes 오브젝트 가이드, Kubespray 업그레이드, DRA, Hubble
- **[incidents/](incidents/)** — 장애 대응 기록과 postmortem

## Note format

각 노트는 새벽 3시에 봐도 바로 따라갈 수 있도록 아래 흐름으로 작성합니다.

- **Symptom** — 실제로 관측되는 현상
- **Diagnosis** — 확인에 사용한 정확한 명령
- **Root cause** — 왜 발생했는지
- **Fix** — 복구 절차
- **Prevention** — 다음에 같은 문제를 피하는 방법

## Discussions

정식 문서로 정리하기 전의 질문이나 메모는 [Discussions](https://github.com/mj006648/netai-devsecops-runbook/discussions)에 남깁니다.

## License

MIT
