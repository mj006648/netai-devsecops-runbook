# TwinX OpenBao Sealed Recovery (2026-06-28)

## Summary

TwinX Argo CD에서 `external-secrets-resources`, `trident-portal`,
`trident-spark`, `trident-twin-hub`가 `Degraded`로 보였다.
직접 원인은 OpenBao가 `Sealed=true` 상태였고, ESO가
`openbao-cluster-store`로 OpenBao Kubernetes auth login을 할 수 없었던 것이다.

2026-06-28 복구 결과:

- OpenBao: `Initialized=true`, `Sealed=false`
- `ClusterSecretStore/openbao-cluster-store`: `Valid`, `Ready=True`
- Trident ExternalSecrets: `SecretSynced`, `Ready=True`
- Argo CD health:
  - `external-secrets-resources`: `Synced / Healthy`
  - `trident-portal`: `Healthy`
  - `trident-spark`: `Healthy`
  - `trident-twin-hub`: `Healthy`

> Public runbook rule: unseal keys and root tokens must never be written here.

## Symptom

Argo CD showed the following health failures:

```text
external-secrets-resources   Synced     Degraded
trident-portal               OutOfSync  Degraded
trident-spark                OutOfSync  Degraded
trident-twin-hub             OutOfSync  Degraded
```

Kubernetes-side symptoms:

```bash
kubectl get clustersecretstore openbao-cluster-store
kubectl get externalsecret -n trident
kubectl get externalsecret -n spark-operator
```

Observed shape:

```text
openbao-cluster-store  InvalidProviderConfig  Ready=False
trident-*              SecretSyncedError      Ready=False
```

ESO log contained:

```text
unable to log in with Kubernetes auth
URL: PUT http://openbao.openbao.svc.cluster.local:8200/v1/auth/kubernetes/login
Code: 503
* Vault is sealed
```

## Diagnosis

Check OpenBao status from inside the pod:

```bash
kubectl -n openbao exec openbao-0 -- sh -lc '
  export BAO_ADDR=http://127.0.0.1:8200
  bao status
'
```

Problem state:

```text
Initialized        true
Sealed             true
Seal Type          shamir
Threshold          3
Unseal Progress    0/3
Storage Type       file
HA Enabled         false
```

Important interpretation:

- `Initialized=true` means **do not run `bao operator init` again**.
- `Sealed=true` means the data exists but OpenBao will not serve secret/auth requests
  until enough unseal keys are supplied.
- `Threshold=3` means any 3 of the 5 existing unseal keys are required.

Confirm ESO is using this OpenBao store:

```bash
kubectl get clustersecretstore openbao-cluster-store -o yaml
```

Expected store shape:

```yaml
spec:
  provider:
    vault:
      server: http://openbao.openbao.svc.cluster.local:8200
      path: secret
      version: v2
      auth:
        kubernetes:
          mountPath: kubernetes
          role: eso-trident
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

## Root cause

OpenBao was deployed as standalone Shamir-sealed OpenBao:

```yaml
server:
  ha:
    enabled: false
  standalone:
    enabled: true
    config: |
      storage "file" {
        path = "/openbao/data"
      }
```

With Shamir seal, the seal state is not automatically restored after a pod restart.
The file storage/PVC preserves OpenBao data, policies, roles, and KV contents, but
the process still starts sealed. A pod restart, node maintenance, or reschedule can
therefore bring OpenBao back as `Initialized=true` and `Sealed=true`.

This was hidden from Argo CD because the chart values intentionally allowed sealed
OpenBao to pass probes:

```yaml
readinessProbe:
  path: "/v1/sys/health?standbyok=true&sealedcode=204&uninitcode=204"
livenessProbe:
  path: "/v1/sys/health?standbyok=true&sealedcode=204&uninitcode=204"
```

That setting keeps the OpenBao pod `Ready` while sealed, but ESO cannot authenticate
against `/v1/auth/kubernetes/login`, so all ExternalSecrets backed by OpenBao fail.

## Fix

### 1. Do not initialize again

Do **not** run this if `Initialized=true`:

```bash
bao operator init -key-shares=5 -key-threshold=3
```

`operator init` is only for a brand-new, uninitialized OpenBao data directory. For
an already initialized instance, use the existing unseal keys.

### 2. Unseal with 3 existing keys

Use an interactive TTY so keys are not recorded in shell history or process args:

```bash
kubectl -n openbao exec -it openbao-0 -- sh -lc '
  export BAO_ADDR=http://127.0.0.1:8200
  bao operator unseal
'
```

Enter one unseal key when prompted. Repeat the same command until threshold is met:

```bash
# key 1
kubectl -n openbao exec -it openbao-0 -- sh -lc 'export BAO_ADDR=http://127.0.0.1:8200; bao operator unseal'

# key 2
kubectl -n openbao exec -it openbao-0 -- sh -lc 'export BAO_ADDR=http://127.0.0.1:8200; bao operator unseal'

# key 3
kubectl -n openbao exec -it openbao-0 -- sh -lc 'export BAO_ADDR=http://127.0.0.1:8200; bao operator unseal'
```

Expected final status:

```text
Initialized     true
Sealed          false
Storage Type    file
HA Enabled      false
```

### 3. Trigger ESO reconciliation if status is stale

ESO normally recovers on the next reconcile interval. To force a safe immediate
reconcile, annotate the store and affected ExternalSecrets with a throwaway stamp:

```bash
stamp=$(date +%s)
kubectl annotate clustersecretstore openbao-cluster-store force-sync="$stamp" --overwrite
kubectl -n trident annotate externalsecret --all force-sync="$stamp" --overwrite
kubectl -n spark-operator annotate externalsecret --all force-sync="$stamp" --overwrite
```

After the resources become `Ready=True`, remove the temporary annotations to avoid
GitOps drift:

```bash
kubectl annotate clustersecretstore openbao-cluster-store force-sync- --overwrite
kubectl -n trident annotate externalsecret --all force-sync- --overwrite
kubectl -n spark-operator annotate externalsecret --all force-sync- --overwrite
```

## Verification

OpenBao:

```bash
kubectl -n openbao exec openbao-0 -- sh -lc '
  export BAO_ADDR=http://127.0.0.1:8200
  bao status
'
```

Required:

```text
Initialized     true
Sealed          false
```

ESO store:

```bash
kubectl get clustersecretstore openbao-cluster-store
```

Required:

```text
NAME                    STATUS   CAPABILITIES   READY
openbao-cluster-store   Valid    ReadWrite      True
```

Trident ExternalSecrets:

```bash
kubectl get externalsecret -n trident
kubectl get externalsecret -n spark-operator
```

Required shape:

```text
STATUS         READY
SecretSynced   True
```

Argo CD health:

```bash
kubectl get applications.argoproj.io -n argocd   external-secrets-resources trident-portal trident-spark trident-twin-hub
```

Required:

```text
external-secrets-resources   Healthy
trident-portal               Healthy
trident-spark                Healthy
trident-twin-hub             Healthy
```

Note: `trident-*` apps can remain `OutOfSync` if ExternalSecret CRDs default fields
or controller-owned metadata differ from the Git-rendered manifest. Treat health
recovery and `SecretSynced=True` as the OpenBao incident closure signal; handle
remaining diff as a separate GitOps drift cleanup.

## Prevention

1. Keep unseal keys in an approved secret manager and document only the retrieval
   path, never the values.
2. Add an alert on `bao status` / `/v1/sys/seal-status` for `sealed=true`.
3. Consider changing OpenBao health probes so sealed state is visible operationally,
   or add a separate synthetic check that fails when sealed.
4. Consider auto-unseal if the environment has a safe KMS/HSM-backed seal backend.
5. After planned node maintenance or OpenBao pod restart, explicitly check:

   ```bash
   kubectl -n openbao exec openbao-0 -- bao status
   kubectl get clustersecretstore openbao-cluster-store
   kubectl get externalsecret -n trident
   ```

## Related TwinX-Ops paths

```text
argocd/twinx-infra/apps/openbao/values.yaml
argocd/twinx-infra/apps/openbao-resources/
argocd/twinx-infra/apps/external-secrets/values.yaml
argocd/twinx-infra/apps/external-secrets-resources/01-cluster-secret-store.yaml
argocd/trident/apps/trident-portal/*externalsecret.yaml
argocd/trident/apps/trident-spark/01-rbac-secret.yaml
argocd/trident/apps/trident-twin-hub/keycloak-externalsecret.yaml
```
