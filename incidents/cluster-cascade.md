# Cluster cascade failure across OTel, Cilium, Ceph

## Summary
A correlated chain of failures across observability (OpenTelemetry),
CNI (Cilium), and storage (Rook-Ceph) that surfaced together as the
cluster appeared "fully down" but actually had distinct underlying
causes that had to be unwound in order.

## Timeline (sketch)
- T0 — Users report query latencies and dashboards going stale.
- T+m — OTel collectors back-pressure; logs/traces stop flowing.
- T+m — Cilium identity churn and pod-to-pod connectivity issues on
  affected nodes (intersects with MTU and rm352 issues).
- T+m — Ceph OSDs flap; PGs become inactive; RGW / RBD calls hang.
- T+m — Apps that rely on object storage (Trident Portal data flows,
  Iceberg catalog, etc.) start failing in turn.

## Order of recovery (lessons learned)
1. **Stabilize the network first.** Until pod-to-pod traffic is reliable,
   restarting Ceph or rolling apps will keep failing in confusing ways.
   - Verify Cilium MTU vs host MTU (see
     [`networking/mtu-cilium.md`](../networking/mtu-cilium.md)).
   - Drain `rm352-1` / `rm352-2` if they're in the path (see
     [`networking/rm352-pod-comms.md`](../networking/rm352-pod-comms.md)).
2. **Bring storage back next.** Without healthy Ceph, every downstream
   service stays half-broken.
   - Check OSDs for flapping vs genuinely down.
   - Use the staged activation order from
     [`storage/rook-ceph-reinstall.md`](../storage/rook-ceph-reinstall.md)
     when a full reinstall is needed.
3. **Then unblock observability.** OTel/Prometheus failing during the
   incident is loud but rarely root cause; restoring it last avoids
   chasing red herrings.
4. **Finally roll apps.** Trident Portal, catalogs, query engines —
   restart in their documented dependency order, not all at once.

## Diagnostic shortcuts
```bash
# Quick triage trio
kubectl get nodes -o wide
kubectl -n rook-ceph get pods -o wide | grep -E 'osd|mon|mgr'
ceph -s

# Cilium identity / endpoint health
kubectl -n kube-system exec ds/cilium -- cilium status --brief
kubectl -n kube-system exec ds/cilium -- cilium endpoint list | head

# Where is OTel back-pressuring
kubectl -n observability logs -l app=otel-collector --tail=200 | grep -iE 'refused|backoff|drop'
```

## Prevention
- Maintain a single authoritative bring-up / bring-down order for the
  cluster in this repo. Update it after every incident.
- Add alerts that fire **early** on the leading indicators (MTU drops,
  OSD restart rate, Cilium identity churn) rather than late on user-
  visible symptoms.
- After each cascade, capture which signals fired in what order in this
  `incidents/` folder so the next on-call has a precedent.

## References
- Lab memory: `project_cluster_issues`
