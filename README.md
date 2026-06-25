# NetAI Operations Runbook

Operational runbook for the **TwinX** and **MiniX** clusters at [GIST NetAI Lab](https://netai.smartx.kr/).
It captures production notes for networking, storage, policy, observability, applications, Kubernetes operations, and incident response.

> The primary audience is the lab operations team.
> This is a living working notebook, not a polished product manual.
> The repository is public so people facing similar problems can reuse the diagnosis and recovery notes.

## Quick map

| Area | Where | Last noted | What is there |
| --- | --- | --- | --- |
| Kubernetes | [kubernetes/](kubernetes/) | 2026-06-25 | Kubernetes object guides, Kubespray upgrade plans, DRA, Hubble notes |
| Networking | [networking/](networking/) | ongoing | Cilium, MTU, netplan, secondary IPs, node/pod connectivity |
| Storage | [storage/](storage/) | ongoing | Rook-Ceph, LVM preparation, storage recovery notes |
| Policy | [policy/](policy/) | ongoing | Kyverno, cert-manager, webhook lifecycle |
| Observability | [observability/](observability/) | planned | Prometheus, Grafana, OpenTelemetry notes |
| Apps | [apps/](apps/) | planned | TwinX/MiniX application operation notes |
| Incidents | [incidents/](incidents/) | 2026-06-25 | Timestamped incident response and postmortem notes |

## Sections

- **[networking/](networking/)** — netplan, Cilium, MTU, secondary IPs, node-level routing
- **[storage/](storage/)** — Rook-Ceph install, recovery, tuning, LVM preparation
- **[policy/](policy/)** — Kyverno, cert-manager, webhook lifecycle
- **[observability/](observability/)** — Prometheus, Grafana, OpenTelemetry
- **[apps/](apps/)** — TwinX/MiniX applications, portals, catalog services, query engines
- **[kubernetes/](kubernetes/)** — Kubernetes object guides, Kubespray upgrade plans, DRA, Hubble notes
- **[incidents/](incidents/)** — timestamped incident response notes and postmortems

## Note format

Each note should be readable at 3 AM and follow this flow.

- **Symptom** — 실제로 관측되는 현상
- **Diagnosis** — 확인에 사용한 정확한 명령
- **Root cause** — 왜 발생했는지
- **Fix** — 복구 절차
- **Prevention** — 다음에 같은 문제를 피하는 방법

## Discussions

Use [Discussions](https://github.com/mj006648/netai-devsecops-runbook/discussions) for questions or rough notes before promoting them to committed runbook entries.

## License

MIT
