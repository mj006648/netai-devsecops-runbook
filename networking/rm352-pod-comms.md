# rm352 nodes have broken intra-pod networking

## Symptom
- New workloads scheduled on `rm352-1` or `rm352-2` cannot reach other pods
  in the same cluster (DNS lookups time out, service ClusterIPs unreachable).
- The same workload deployed elsewhere works fine.
- Existing long-running pods on `rm352-*` appear fine; only **newly created**
  pods exhibit the issue.

## Diagnosis
```bash
# From a pod on rm352-* try reaching CoreDNS / another pod
kubectl exec -it <pod-on-rm352> -- nslookup kubernetes.default
kubectl exec -it <pod-on-rm352> -- curl -v <other-pod-IP>:<port>

# Compare with the same probe from a pod on a healthy node
```
Outbound to the internet may still work; only **pod-to-pod** is broken,
which points at the CNI datapath on those nodes specifically.

## Root cause
A node-local CNI/kernel issue on the `rm352-*` machines that we have not
fully root-caused. The symptom is consistent and reproducible on those
two nodes only.

## Fix — avoid scheduling new workloads onto rm352-* via nodeAffinity
Until the underlying issue is fixed, exclude `rm352-1` and `rm352-2` from
new deployments:

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

Or label the nodes with a taint and tolerate it only for known-safe workloads.

## Prevention
- New chart values / Kustomize overlays in this cluster should default to
  the affinity rule above until the rm352 issue is resolved.
- Re-test pod-to-pod connectivity from rm352-* after every Cilium / kernel
  upgrade — the issue may resolve incidentally.

## References
- Lab memory: `project_twinx_node_issues`
