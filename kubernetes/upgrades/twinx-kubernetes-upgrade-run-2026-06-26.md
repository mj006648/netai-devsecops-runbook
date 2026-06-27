# TwinX Kubernetes Upgrade Run 2026-06-26

## Summary

TwinX Kubernetes upgrade run log for the 2026-06-26 UTC / 2026-06-27 KST maintenance window.

```text
start:   Kubernetes v1.34.3 for most nodes after the earlier v1.34 wave
target:  Kubernetes v1.35.4 with Kubespray v2.31.0
result:  main control-plane, GPU/storage workers, edgebox1, and edgebox2 upgraded to v1.35.4
hold:    edgebox3 and edgebox4 intentionally deferred because they remain NotReady
hubble:  not enabled in this run
otp:     temporary SSH OTP bypass remains enabled until the remaining edgebox3/4 decision is complete
```

Final node status captured after today's run:

| Node | Status | Version | Runtime | Decision |
| --- | --- | --- | --- | --- |
| `control1` | Ready | v1.35.4 | containerd 2.2.3 | upgraded |
| `control2` | Ready | v1.35.4 | containerd 2.2.3 | upgraded |
| `control3` | Ready | v1.35.4 | containerd 2.2.3 | upgraded |
| `sv4000-1` | Ready | v1.35.4 | containerd 2.2.3 | upgraded |
| `sv4000-2` | Ready | v1.35.4 | containerd 2.2.3 | upgraded |
| `l40s` | Ready | v1.35.4 | containerd 2.2.3 | upgraded |
| `rm352-1` | Ready | v1.35.4 | containerd 2.2.3 | upgraded |
| `rm352-2` | Ready | v1.35.4 | containerd 2.2.3 | upgraded |
| `edgebox1` | Ready,SchedulingDisabled | v1.35.4 | containerd 2.2.3 | upgraded with no-drain follow-up |
| `edgebox2` | Ready,SchedulingDisabled | v1.35.4 | containerd 2.2.3 | upgraded with no-drain follow-up |
| `edgebox3` | NotReady,SchedulingDisabled | v1.34.3 | containerd 2.2.1 | deferred; node/network issue |
| `edgebox4` | NotReady,SchedulingDisabled | v1.34.3 | containerd 2.2.1 | deferred; node/network issue |

## Important decisions

| Topic | Decision |
| --- | --- |
| Upgrade method | Use Kubespray v2.31.0 `upgrade-cluster.yml` for Kubernetes v1.35.4. |
| Drain policy | Use no-drain for the remaining storage/GPU worker upgrades because Rook-Ceph, Harbor, MinIO, and GPU workloads make normal drain risky. |
| Hubble | Do not enable Hubble in this run because Cilium is still managed through Kubespray rather than GitOps. |
| Edgebox | Upgrade edgebox1/2 one by one with no-drain after the main wave. Keep edgebox3/4 deferred because they remain NotReady and need node/network recovery first. |
| OTP bypass | Keep temporary SSH OTP bypass enabled until the remaining edgebox3/4 decision is complete, then run rollback. |
| Ceph `noout` | Temporarily used around Ceph-heavy node work, then unset. Final flags do not include `noout`. |

## Command pattern used

No-drain worker upgrade command shape:

```bash
cd /home/netai/chang/kubespray-v2.31
source /home/netai/ansible-venv-kubespray-2.31/bin/activate
ansible-playbook -i inventory/mycluster/inventory.ini upgrade-cluster.yml \
  -b -v \
  --limit <node> \
  -e '{"drain_nodes": false}'
```

Important: pass `drain_nodes` as JSON boolean. Do not use plain `-e drain_nodes=false`.

## Kubespray v2.31 no-drain patch

During the `l40s` run, Kubespray v2.31 still executed the worker drain task even though `-e '{"drain_nodes": false}'` was passed. The problematic path was:

```text
/home/netai/chang/kubespray-v2.31/roles/remove_node/pre_remove/tasks/main.yml
```

Local patch added `drain_nodes | default(true) | bool` conditions to the remove-node pre-remove tasks:

```text
Remove-node | Drain node except daemonsets resource
Remove-node | Wait until Volumes will be detached from the node
```

Validation after patch:

```text
ansible-playbook --syntax-check ... upgrade-cluster.yml: passed
rm352-1 and rm352-2: cordon happened, actual kubectl drain did not run, upgrade succeeded
```

Directive: if a fresh Kubespray checkout is used for the remaining edgebox work, re-check this patch before using `drain_nodes=false`.

## Backup and recovery material

Sensitive backup files are intentionally not committed.

Latest v1.35 backup path:

```text
/home/netai/chang/Git/twinx-upgrade-backups/20260626T162036Z-before-v135
```

Key backup evidence:

```text
etcd-snapshot-control1.db
sha256: 5e4f7ca25c25d6ccae15e55205cd9b044cc83dd75d00253e43903b31192a9cfd
```

Kubespray also created etcd snapshots on control-plane nodes:

```text
/var/backups/etcd-2026-06-26_16:36:32/snapshot.db
```

## OTP bypass state

Temporary SSH OTP bypass for the `netai` user was applied on control-plane nodes before the upgrade so Ansible would not block on interactive OTP.

```text
# BEGIN NETAI TEMP OTP BYPASS 2026-06-26
Match User netai
    AuthenticationMethods publickey
# END NETAI TEMP OTP BYPASS 2026-06-26
```

Current decision: do not rollback yet. Keep it until the remaining edgebox3/4 decision is complete.

Rollback command to run after the remaining edgebox3/4 decision:

```bash
/tmp/rollback_netai_otp_bypass.sh
```

Note: one rollback attempt was intentionally stopped/abandoned because the user decided to keep OTP bypass until edgebox completion. The first script attempt failed before changing remote files because `/bin/sh` did not support `set -o pipefail`.

## Work log

| Time | Action | Result |
| --- | --- | --- |
| pre-run | Preflight and backups | etcd/control-plane backups created; cluster risks identified. |
| pre-run | Prepared Kubespray v2.31.0 | inventory copied, Kubernetes target set to v1.35.4, validation passed. |
| v1.35 wave | `control1` | Upgraded to v1.35.4. Early command syntax caused a drain attempt; recovered and continued. |
| v1.35 wave | `control2` | Upgraded to v1.35.4 with no-drain JSON variable. |
| v1.35 wave | `control3` | Upgraded to v1.35.4 with no-drain JSON variable. |
| v1.35 wave | `sv4000-1` | Upgraded to v1.35.4. |
| v1.35 wave | `sv4000-2` | Upgraded to v1.35.4. |
| v1.35 wave | `l40s` first attempt | Kubespray v2.31 still executed worker drain despite `drain_nodes=false`; drain was interrupted and node uncordoned. |
| v1.35 wave | Kubespray patch | Patched local v2.31 remove-node pre-remove tasks to honor `drain_nodes=false`. |
| v1.35 wave | `l40s` retry | Upgraded to v1.35.4. Cilium/kube-proxy/Rook-Ceph pods Running after retry. |
| v1.35 wave | Ceph flag cleanup | `noout` unset after Ceph-heavy work. Final flags do not include `noout`. |
| v1.35 wave | `rm352-1` | Upgraded to v1.35.4. Play recap `failed=0`; actual drain skipped. |
| v1.35 wave | `rm352-2` | Upgraded to v1.35.4. Play recap `failed=0`; actual drain skipped. |
| main wave final check | Cluster verification | Main upgraded nodes Ready on v1.35.4; etcd healthy; edgebox1-4 still deferred at that moment. |
| edgebox follow-up | `edgebox1` | Upgraded to v1.35.4 with `drain_nodes=false`; play recap `failed=0`; no `kubectl drain edgebox1` process observed. |
| edgebox follow-up | `edgebox2` | Upgraded to v1.35.4 with `drain_nodes=false`; play recap `failed=0`; no `kubectl drain edgebox2` process observed. |
| edgebox follow-up | edgebox verification | edgebox1/2 Ready on v1.35.4; Cilium, kube-proxy, nginx-proxy Running; edgebox1/2 MinIO pods Running. |

## Final verification evidence

### rm352-2 post-upgrade

```text
rm352-2 Ready v1.35.4 containerd://2.2.3
Cilium: cilium-89hzl Running
kube-proxy: kube-proxy-sw6g2 Running
Rook-Ceph pods on rm352-2: Running
Non-running pods on rm352-2: none
```

### edgebox1/2 post-upgrade

```text
edgebox1 Ready,SchedulingDisabled v1.35.4 containerd://2.2.3
edgebox2 Ready,SchedulingDisabled v1.35.4 containerd://2.2.3
```

Core system pods on edgebox1/2:

```text
edgebox1: cilium, cilium-envoy, kube-proxy, nginx-proxy Running
edgebox2: cilium, cilium-envoy, kube-proxy, nginx-proxy Running
```

Workload check:

```text
edgebox1/2 non-running pods: none
minio-0 and minio-6 on edgebox1: Running
minio-1 and minio-3 on edgebox2: Running
```

### etcd health

```text
https://10.38.38.9:2379  healthy
https://10.38.38.17:2379 healthy
https://10.38.38.25:2379 healthy
```

### Ceph status after main wave

Ceph is operational but still in the pre-existing warning state.

```text
health: HEALTH_WARN
mon: 3 daemons, quorum e,f,h
mgr: a active, b standby
mds: 1/1 up, 1 hot standby
osd: 3 osds, 3 up, 3 in
pgs: 248 active+clean, 33 undersized+peered
flags: sortbitwise,recovery_deletes,purged_snapdirs,pglog_hardlimit
```

No `noout` flag remains.

### Known non-running pods after final check

```text
harbor/habor-harbor-jobservice-74c6fb9b97-s4g95   ContainerCreating on l40s
harbor/habor-harbor-registry-68df8bfb68-czpss     ContainerCreating on l40s
kube-system/kube-proxy-m7vxw                       Pending on edgebox4
kube-system/kube-proxy-stlt8                       Pending on edgebox3
minio/minio-2                                      Terminating on edgebox3
minio/minio-4                                      Terminating on edgebox4
minio/minio-5                                      Terminating on edgebox3
minio/minio-7                                      Terminating on edgebox4
```

Interpretation:

- Edgebox3/4-related Pending/Terminating pods are part of the remaining deferred edgebox work.
- Harbor pods on `l40s` are a separate RWO/Multi-Attach style cleanup item and were not treated as blocking the Kubernetes node upgrade.

## Remaining deferred edgebox work

Edgebox1/2 were completed in the follow-up run. Edgebox3/4 are intentionally not completed yet because both remain NotReady.

Current edgebox state:

```text
edgebox1: v1.35.4, Ready,SchedulingDisabled
edgebox2: v1.35.4, Ready,SchedulingDisabled
edgebox3: v1.34.3, NotReady,SchedulingDisabled
edgebox4: v1.34.3, NotReady,SchedulingDisabled
```

Before upgrading edgebox3/4:

1. Confirm power/link/reachability for `edgebox3` and `edgebox4`.
2. Decide whether edgebox MinIO pods can be cleaned up or need recovery first.
3. Re-check Kubespray no-drain patch if using a fresh checkout.
4. Upgrade remaining edgebox nodes one by one, not in parallel.
5. Verify kubelet/Cilium/kube-proxy after each node.
6. Only after the remaining edgebox decision is complete, rollback temporary OTP bypass.

## Remaining risks

| Risk | Status | Next action |
| --- | --- | --- |
| edgebox3/4 not upgraded | accepted temporary skew | recover node/network state before the next edgebox maintenance window |
| edgebox3/4 NotReady | unresolved | power/link/SSH/network check |
| Harbor registry/jobservice ContainerCreating | unresolved | inspect RWO volume attachments and old pod cleanup |
| Ceph HEALTH_WARN | baseline warning remains | monitor PGs, mon disk usage, scrub backlog, no-replica pools |
| OTP bypass still enabled | intentional temporary state | rollback after remaining edgebox3/4 decision |
| Hubble not enabled | intentional | enable later after Cilium GitOps/values plan |

## Stop conditions for next edgebox run

Stop before moving to the next edgebox node if any of the following happens:

```text
- etcd endpoint health fails
- current Ready upgraded nodes regress to NotReady
- Cilium on the target node does not become Ready
- kube-proxy on the target node does not become Running
- Ceph warning state worsens beyond the current baseline
- MinIO cleanup affects unrelated nodes unexpectedly
- Kubespray starts an actual drain when no-drain is intended
```
