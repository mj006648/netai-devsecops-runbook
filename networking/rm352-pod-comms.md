# rm352 nodes have broken intra-pod networking (hairpin / livez fails)

## Symptom
- Pods scheduled on `rm352-1` or `rm352-2` fail webhook-style health probes
  that depend on **pod talking to itself or back through its own Service**
  (hairpin traffic), e.g. cert-manager / Kyverno admission webhook
  startup `livez` checks.
- Affected controllers crash-loop or never become Ready on those nodes;
  the same workload moved elsewhere works fine.
- DNS / outbound from those pods may still appear partially functional —
  the failure is specific to the hairpin / loopback-through-Service path.

## Diagnosis
```bash
# Where is the misbehaving pod scheduled
kubectl -n <ns> get pods -o wide | grep <controller>

# From a debug pod on rm352-*, try hairpin
kubectl debug node/rm352-1 -it --image=nicolaka/netshoot
# inside:
curl -kv https://<self-service>.<ns>.svc:<port>/livez

# Compare the same probe from a pod on a healthy node — it should succeed.
```

## Root cause
Hairpin / self-Service traffic on `rm352-1` and `rm352-2` does not
complete reliably. The exact CNI / kernel interaction has not been fully
root-caused, but the symptom is consistent and node-specific: any
workload whose readiness depends on calling itself through a Service
(notably webhook controllers running their own `livez`) will fail
exclusively on these two nodes.

## Fix — exclude rm352-* via nodeAffinity for affected workloads
Apply this affinity (already in use in TwinX `argocd/twinx-infra/apps/*`
for cert-manager and Kyverno controllers):

```yaml
spec:
  template:
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: kubernetes.io/hostname
                    operator: NotIn
                    values:
                      - rm352-1
                      - rm352-2
```

Confirmed deployments using this pattern in this cluster:
- cert-manager: controller, cainjector, startupapicheck
- Kyverno: admissionController, reportsController

## Prevention
- Any new workload that runs an in-pod webhook / hairpin `livez` should
  inherit the same `NotIn rm352-*` affinity until the root cause is
  resolved.
- Re-test hairpin from rm352-* after every Cilium / kernel upgrade — the
  issue may resolve incidentally and the affinity can be relaxed.

## References
- Lab memory: `project_twinx_node_issues`
- TwinX values: `argocd/twinx-infra/apps/cert-manager/values.yaml`,
  `argocd/twinx-infra/apps/kyverno/values.yaml`
