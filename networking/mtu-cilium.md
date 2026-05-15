# MTU mismatch causes OSD flapping and cluster-wide instability

## Symptom
- Ceph OSDs flap up/down repeatedly without disk errors.
- `ceph -s` shows slow ops, PGs stuck `peering` or `inactive`.
- Some pod-to-pod traffic works for small packets but hangs for larger
  ones (e.g. small JSON `curl` works, image pulls / streaming queries
  hang).
- `dmesg` may show `fragmentation needed` / `packet too big` warnings.

## Diagnosis
```bash
# Compare MTU on host NIC vs pod interface
ip link show <host-iface>
kubectl exec -n rook-ceph <osd-pod> -- ip link show

# Probe with don't-fragment to find the actual working size
ping -M do -s 8900 <other-node-IP>
# Decrease -s until ping succeeds; that's effective MTU minus 28
```

If the host's working size is much smaller than `kubectl exec` reports
inside the pod, traffic that fills the pod-advertised MTU will be
silently dropped on the wire.

## Root cause
Cilium VXLAN/Geneve tunneling consumes ~50 bytes per packet. When the
host NIC and pod MTU are set independently — or when Cilium is left on
auto-detect and the host MTU is changed later — large packets, notably
Ceph replication / scrub, get silently dropped instead of fragmented,
because Path MTU Discovery does not reliably propagate inside the
overlay.

## Current cluster config (TwinX)
```yaml
# kubespray roles/network_plugin/cilium/defaults/main.yml
cilium_mtu: "0"      # auto-detect from host
```

Auto-detect works correctly **only if every node's primary interface
already carries the intended MTU at the time Cilium starts**. Changing
host MTU after Cilium is up does not re-trigger detection — Cilium must
be rolled.

## Fix
1. Decide on a coherent MTU stack — e.g. host `9000`, effective Cilium
   `8950`. Apply host MTU to every node first.
2. Either:
   - Keep `cilium_mtu: "0"` and **roll Cilium** so it re-detects:
     ```bash
     kubectl -n kube-system rollout restart ds/cilium
     ```
   - Or pin Cilium MTU explicitly:
     ```yaml
     cilium_mtu: "8950"
     ```
3. Drain/uncordon affected nodes so pods pick up the new MTU.
4. Verify OSDs stop flapping; PGs return to `active+clean`.

## Prevention
- Never change host MTU on a Kubernetes node without immediately rolling
  the CNI to re-detect.
- Add a smoke test in cluster bring-up:
  `ping -M do -s <effective> <other-pod-IP>` between two pods on
  different nodes.
- Alert on Ceph OSD restart rate; a sustained increase often re-surfaces
  this class of issue after a network or CNI upgrade.

## References
- Lab memory: `project_cluster_issues`
- TwinX: `kubespray/roles/network_plugin/cilium/defaults/main.yml`
