# Cluster cascade failure — OTel → Cilium hostNetwork → Rook-Ceph rebuild

## Summary
A correlated chain of failures across observability (OpenTelemetry),
CNI / host networking (Cilium), and storage (Rook-Ceph) over three days
that culminated in a full Rook-Ceph reinstall.

## Timeline (TwinX git log, 2026-04-29 → 2026-05-01)

**2026-04-29 — API server overload**
- otel-operator generated enough custom resource churn / webhook traffic
  to push the API server into overload.
- Mitigation: **disable otel-operator** in ArgoCD to stop the bleeding.

**2026-04-30 — host networking + otel collector update**
- `hostNetwork: true` enabled on the otel collector path so its traffic
  stops flowing through the overloaded CNI/admission path.
- otelcol version/config updated alongside.

**2026-05-01 — full Rook-Ceph rebuild**
- Commits `c65c4de` … `2ed16e8`.
- Storage state had drifted (likely from earlier reboots + zombie LVM /
  GPT metadata blocking fresh OSD prepare).
- Sequence applied:
  1. Disable all dependent apps in ArgoCD.
  2. Cleanup (wipe LV / VG / PV, zap signatures).
  3. Reinstall Rook-Ceph operator.
  4. Enable operator → enable cluster → wait for OSDs.
  5. Re-enable dependent apps in dependency order.

## Order of recovery (lessons learned)
1. **Stabilize the network first.** Until pod-to-pod traffic and webhook
   reachability are reliable, restarting Ceph or rolling apps will keep
   failing in confusing ways.
   - Verify Cilium MTU vs host MTU
     ([`networking/mtu-cilium.md`](../networking/mtu-cilium.md)).
   - Apply `NotIn rm352-*` affinity on any new webhook-bearing
     controller ([`networking/rm352-pod-comms.md`](../networking/rm352-pod-comms.md)).
2. **Reduce API/webhook pressure.** Disabling otel-operator and moving
   collectors to `hostNetwork` was load-shedding, not root-cause repair —
   it bought time for the storage rebuild.
3. **Then storage.** Use the staged
   [`storage/rook-ceph-reinstall.md`](../storage/rook-ceph-reinstall.md)
   procedure; wipe stale LVM with
   [`storage/lv-preparation.md`](../storage/lv-preparation.md) **before**
   reinstalling.
4. **Then observability and apps.** Bring otel back after storage is
   healthy; roll apps in their documented dependency order
   (cnpg → nessie → trino → trident-infra → trident-spark → superset).

## Diagnostic shortcuts used during the incident
```bash
# Quick triage trio
kubectl get nodes -o wide
kubectl -n rook-ceph get pods -o wide | grep -E 'osd|mon|mgr'
ceph -s

# Is the API server actually overloaded
kubectl -n kube-system top pod -l component=kube-apiserver
kubectl get --raw /metrics | grep apiserver_request_duration_seconds_count | head

# Is webhook traffic itself causing the load
kubectl get validatingwebhookconfiguration,mutatingwebhookconfiguration

# Cilium identity / endpoint health
kubectl -n kube-system exec ds/cilium -- cilium status --brief
```

## Prevention
- Maintain a single authoritative bring-up / bring-down order for the
  cluster in this repo. Update after every incident.
- Alert **early** on leading indicators: API server p99 latency, webhook
  call counts, OSD restart rate, Cilium identity churn — rather than
  late on user-visible symptoms.
- Be deliberate about which controllers run admission webhooks. Each one
  is a multiplier on API server load during incidents.

## References
- Lab memory: `project_cluster_issues`, `project_rook_ceph_reinstall`
- TwinX commits 2026-04-29 (otel-operator disable), 2026-04-30
  (hostNetwork on, otelcol update), 2026-05-01 (`c65c4de`..`2ed16e8`,
  Rook-Ceph rebuild)
