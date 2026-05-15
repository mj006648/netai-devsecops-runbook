# Rook-Ceph full reinstall — staged bring-up runbook

## When to use this
- A storage node (e.g. `l40s`) has been rebooted in a way that lost OSD
  state, and partial recovery has been ruled out.
- Multiple apps depending on Ceph need to come back in the right order
  to avoid retriggering the failure chain.

## Pre-flight checklist
- [ ] Confirm the cluster has acknowledged the lost OSDs (`ceph osd tree`,
      `ceph -s`) — do **not** restart Rook while Ceph still expects them
      back.
- [ ] Snapshot pool-level config you might need (`ceph osd pool ls
      detail`, CRUSH rules, RBD pool / RGW config).
- [ ] Quiesce dependent workloads (scale to zero, don't just disrupt).
- [ ] Confirm node networking is healthy first
      ([`networking/mtu-cilium.md`](../networking/mtu-cilium.md),
      [`networking/rm352-pod-comms.md`](../networking/rm352-pod-comms.md)).

## Phase 1 — wipe stale storage state on the affected node
Follow [`storage/lv-preparation.md`](lv-preparation.md):
- Remove old LVs / VGs / PVs Rook left behind.
- Zap GPT and Ceph signatures from each disk.
- Confirm `ceph-volume lvm list` is empty on that host.

> Real-world note: zombie GPT/LVM metadata has blocked LV creation on
> rebuild in this cluster before — `sgdisk --zap-all` + `wipefs -a`
> before `pvremove` is the safer order.

## Phase 2 — bring the Rook operator and core mons back
```bash
kubectl -n rook-ceph scale deploy rook-ceph-operator --replicas=1
kubectl -n rook-ceph get pods -l app=rook-ceph-mon -w
ceph -s
```
Do **not** proceed until mon quorum is healthy and mgr is up.

## Phase 3 — re-prepare OSDs on the cleaned node
```bash
kubectl -n rook-ceph delete job -l app=rook-ceph-osd-prepare,rook-ceph-osd-prepare-node=<node>
kubectl -n rook-ceph get pods -l app=rook-ceph-osd -o wide | grep <node>
ceph osd tree
```
Wait for backfill / recovery to settle before activating dependent apps.

## Phase 4 — reactivate dependent apps in dependency order
The ArgoCD apps that need explicit re-enable after a reinstall in this
cluster, in roughly this order:

1. **cnpg (pg-resources)** — Postgres operator + cluster instances
   (catalog backends sit on top of this).
2. **nessie** — Iceberg catalog. Depends on its Postgres being up.
3. **trino** — query engine. Depends on catalog and on object storage.
4. **trident-infra** — supporting services for the lakehouse.
5. **trident-spark** — compute. Depends on catalog + object storage.
6. **superset** — BI / dashboards. User-facing, comes last.

For each:
```bash
# In ArgoCD-managed setup
kubectl -n argocd patch app <name> --type=merge -p '{"spec":{"syncPolicy":{"automated":{}}}}'
# Or scale workloads back to original replicas
kubectl -n <ns> scale deploy <name> --replicas=<original>
kubectl -n <ns> rollout status deploy/<name>
```

## Phase 5 — verification
- `ceph -s` reports `HEALTH_OK` (or only expected warnings).
- All OSDs `up` and `in`.
- Backfill complete; no `degraded` or `misplaced` objects.
- Each reactivated app passes its smoke test.
- Controlled write/read against RGW and RBD succeeds.

## Prevention
- Keep the staged order above in this repo and update after each
  reinstall.
- Avoid bringing all dependent apps back simultaneously — phased recovery
  surfaces issues incrementally and avoids retriggering cascades.

## References
- Lab memory: `project_rook_ceph_reinstall`
- TwinX commits 2026-05-01: `c65c4de`..`2ed16e8` (full Rook-Ceph rebuild)
- Related: [`storage/lv-preparation.md`](lv-preparation.md),
  [`incidents/cluster-cascade.md`](../incidents/cluster-cascade.md)
