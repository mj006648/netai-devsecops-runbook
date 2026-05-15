# MTU mismatch causes OSD flapping and cluster-wide instability

## Symptom
- Ceph OSDs flap up/down repeatedly without disk errors.
- `ceph -s` shows slow ops, PGs stuck `peering` or `inactive`.
- Some pod-to-pod traffic works for small packets but hangs for larger ones
  (e.g. `curl` of small JSON works, image pulls / streaming queries hang).
- `dmesg` may show `fragmentation needed` / `packet too big` warnings.

## Diagnosis
```bash
# Compare MTU on host NIC vs pod interface
ip link show <host-iface>
kubectl exec -n rook-ceph <osd-pod> -- ip link show

# Probe with don't-fragment to find the actual working size
ping -M do -s 8900 <other-node-IP>
# Decrease -s until ping succeeds; that's the effective MTU minus 28
```

If host MTU is `9000` but Cilium tunnel overhead pushes effective pod MTU
to `8950` or less while the OSD config still assumes `9000`, OSDs will
fail heartbeats on jumbo replication traffic.

## Root cause
Cilium (VXLAN/Geneve tunneling) consumes ~50 bytes per packet. When the
host NIC and the pod network MTU are set without accounting for tunnel
overhead, large packets — especially Ceph replication / scrub — get
silently dropped instead of fragmented, because Path MTU Discovery does
not always propagate inside the overlay.

## Fix
1. Decide on a coherent MTU stack, e.g. host `9000`, Cilium tunnel `8950`,
   pod MTU `8950`.
2. Patch Cilium config:
   ```yaml
   spec:
     mtu: 8950
   ```
3. Roll Cilium daemonset, then drain/uncordon nodes so pods pick up the
   new MTU.
4. Verify OSDs stop flapping; PGs should return to `active+clean`.

## Prevention
- Never change host MTU without simultaneously updating Cilium config.
- Add a smoke test in cluster bring-up: `ping -M do -s <effective>` between
  two pods on different nodes.
- Alert on Ceph OSD restart rate; a sustained increase often re-surfaces
  this class of issue after a network or CNI upgrade.

## References
- Lab memory: `project_cluster_issues`
