# rook-ceph-runbook

Battle-tested operational runbook for running [Rook-Ceph](https://rook.io/) on production Kubernetes clusters.
Written from real incidents at [GIST NetAI Lab](https://netai.smartx.kr/) while operating the **Trident** data lakehouse.

## Who this is for
- SREs running Rook-Ceph in production
- Researchers building data platforms on Kubernetes
- Anyone who hit a Ceph error message at 3 AM

## Recipe index

### 01 — Installation
- LV preparation after node reboot
- Node affinity quirks (avoiding problematic nodes)
- Fresh install checklist

### 02 — Networking
- MTU mismatch symptoms and recovery
- Cilium interop pitfalls
- Secondary IP routing (netplan `/32 from`-route fix)

### 03 — Recovery
- Full reinstall runbook
- OSD down / mon quorum lost
- PG stuck states

### 04 — Tuning
- CRUSH rules for NVMe-only pools
- BlueStore cache sizing
- RGW throughput

### 05 — Integration
- cert-manager + webhook controller pitfalls
- Kyverno policy interactions
- Prometheus / Grafana dashboards

## Recipe format
Every recipe in this repo follows the same structure so you can scan fast at 3 AM:

- **Symptom** — what you observe
- **Diagnosis** — exact commands to confirm
- **Root cause** — why it happens
- **Fix** — step-by-step recovery
- **Prevention** — how to avoid it next time

## Contributing
Found a new failure mode? [Open a discussion](https://github.com/mj006648/rook-ceph-runbook/discussions) or send a PR.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the recipe template.

## License
MIT
