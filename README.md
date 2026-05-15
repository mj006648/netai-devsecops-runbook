# NetAI DevSecOps Runbook

Operational runbook for the **Trident** data lakehouse at [GIST NetAI Lab](https://netai.smartx.kr/).
Covers networking, storage, policy, observability, and incident notes accumulated while running the cluster in production.

> Primary audience is the lab itself — this is a working notebook, not a polished guide.
> It's public so that anyone hitting the same problems can benefit too.

## Sections

- **[networking/](networking/)** — netplan, Cilium, MTU, secondary IPs, node-level routing
- **[storage/](storage/)** — Rook-Ceph install, recovery, tuning, LVM prep
- **[policy/](policy/)** — Kyverno, cert-manager, webhook lifecycle
- **[observability/](observability/)** — Prometheus, Grafana, OpenTelemetry
- **[apps/](apps/)** — Trident Portal, catalog services, query engines
- **[incidents/](incidents/)** — timestamped incident write-ups

## Note format

Each note is written so it can be scanned at 3 AM:

- **Symptom** — what you observe
- **Diagnosis** — exact commands to confirm
- **Root cause** — why it happens
- **Fix** — step-by-step recovery
- **Prevention** — how to avoid it next time

## Discussions

[Discussions](https://github.com/mj006648/netai-devsecops-runbook/discussions) hold Q&A-style write-ups before they're promoted to full notes in this repo. Outside contributors welcome.

## License
MIT
