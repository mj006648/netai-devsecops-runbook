# Rook-Ceph full reinstall — staged bring-up runbook

## When to use this
- A storage node (e.g. `l40s`) has been rebooted in a way that lost
  OSD state, and partial recovery has been ruled out.
- Multiple "false" status apps depending on Ceph need to come back in
  the right order to avoid retriggering the failure chain.

## Pre-flight checklist
- [ ] Confirm the cluster has acknowledged the lost OSDs (`ceph osd tree`,
      `ceph -s`) — do **not** restart Rook while Ceph still expects them
      back.
- [ ] Snapshot any pool-level config you might need (`ceph osd pool ls
      detail`, CRUSH rules, RBD pool / RGW config).
- [ ] Quiesce dependent workloads (Trident Portal, Iceberg catalog, RGW
      consumers) — scale to zero, don't just disrupt.
- [ ] Confirm node networking is healthy first (see
      [`networking/mtu-cilium.md`](../networking/mtu-cilium.md) and
      [`networking/rm352-pod-comms.md`](../networking/rm352-pod-comms.md)).

## Phase 1 — wipe stale storage state on the affected node
Follow [`storage/lv-preparation.md`](lv-preparation.md) on the rebooted
node(s):
- Remove old LVs / VGs / PVs that Rook left behind.
- Zap GPT and Ceph signatures from each disk.
- Confirm `ceph-volume lvm list` is empty on that host.

## Phase 2 — bring the Rook operator and core mons back
```bash
# Scale operator up
kubectl -n rook-ceph scale deploy rook-ceph-operator --replicas=1

# Watch mons reach quorum
kubectl -n rook-ceph get pods -l app=rook-ceph-mon -w
ceph -s
```
Do **not** proceed until mon quorum is healthy and mgr is up.

## Phase 3 — re-prepare OSDs on the cleaned node
```bash
# Trigger the prepare job; the operator should re-create it automatically
kubectl -n rook-ceph delete job -l app=rook-ceph-osd-prepare,rook-ceph-osd-prepare-node=<node>

# Watch OSDs come up one by one
kubectl -n rook-ceph get pods -l app=rook-ceph-osd -o wide | grep <node>
ceph osd tree
```
Wait for backfill / recovery to settle before activating dependent apps.

## Phase 4 — reactivate dependent apps in dependency order
The "false status" apps that must be reactivated explicitly after a
reinstall (record actual list in lab memory `project_rook_ceph_reinstall`):

1. Object storage clients (RGW-backed services).
2. Block storage clients (RBD-backed PVCs).
3. Iceberg / catalog services that hold their metadata on Ceph.
4. Query / compute layers (Trino, Spark) that depend on the catalog.
5. Trident Portal and other user-facing apps last.

For each layer:
```bash
kubectl -n <ns> scale deploy <name> --replicas=<original>
kubectl -n <ns> rollout status deploy/<name>
```

## Phase 5 — verification
- `ceph -s` reports `HEALTH_OK` (or only expected warnings).
- All OSDs `up` and `in`.
- Backfill complete; no `degraded` or `misplaced` objects.
- Each reactivated app passes its smoke test.
- Run a controlled write/read against RGW and RBD to confirm.

## Prevention
- Keep the staged order above in this repo and update it after each
  reinstall.
- Avoid bringing all dependent apps back simultaneously — phased recovery
  surfaces issues incrementally and avoids retriggering cascades.

## References
- Lab memory: `project_rook_ceph_reinstall`
- Related: [`storage/lv-preparation.md`](lv-preparation.md),
  [`incidents/cluster-cascade.md`](../incidents/cluster-cascade.md)
