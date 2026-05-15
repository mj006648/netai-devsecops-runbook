# Webhook controller restarts on a periodic SIGTERM cycle

## Symptom
- A webhook-related controller (e.g. an admission webhook for a CRD or a
  cluster add-on) is restarted by Kubernetes with `SIGTERM` on a regular
  interval — often every few minutes to an hour.
- The pod looks healthy otherwise: no OOM, no panic, no readiness failures
  immediately before the restart.
- Restart frequency roughly matches the controller's internal certificate
  rotation cadence.

## Diagnosis
```bash
kubectl -n <ns> get pods -l <selector> -o wide
kubectl -n <ns> describe pod <pod>     # check last termination reason
kubectl -n <ns> logs <pod> --previous | tail -50
kubectl -n <ns> get events --sort-by=.lastTimestamp | tail -30

# Inspect the TLS secret backing the webhook
kubectl -n <ns> get secret <webhook-secret> -o yaml | grep -E 'annotations|managed-by|owner'
```

If the controller log shows certificate regeneration / "rotating webhook
cert" entries right before each restart, and the secret carries
annotations from multiple managers (the controller itself **and**
cert-manager, or the controller and a Helm hook), the cycle is almost
certainly a certificate ownership conflict.

## Root cause
Two things are simultaneously claiming the webhook TLS secret:

1. The controller's built-in certificate manager — it regenerates the
   secret on startup and on a timer, then restarts the pod to load the
   "correct" material.
2. An external cert source — often cert-manager via a `Certificate`
   resource, or a Helm `post-install` hook that re-writes the secret.

Each reconciliation triggers the other. The controller process gets
`SIGTERM`'d every cycle so it can pick up "its" cert again, which is
immediately overwritten by the external source, and so on.

## Fix — pick exactly one cert owner
**Option A — let the controller manage its own certs** (usually the safer
choice for in-cluster webhooks):

- Disable any external cert-manager `Certificate` for this webhook.
- Remove Helm values like `certManager.create: true` /
  `useCertManagerCerts: true`.
- Delete the externally-issued secret so the controller regenerates a
  fresh self-signed pair on next start.

**Option B — fully delegate to cert-manager** (only if the controller
supports a real `--disable-internal-cert-manager` flag):

- Confirm the flag exists in the controller version you run.
- Set it via Helm values or deployment args.
- Let cert-manager own the secret end-to-end.

If neither side cleanly disables, go with Option A. The mixed mode is
what causes the SIGTERM cycle.

## Verification
```bash
# Restart count stabilizes
kubectl -n <ns> get pods -l <selector>

# Webhook secret stops oscillating
kubectl -n <ns> get secret <webhook-secret> -o yaml | grep annotations
```

## Prevention
- For every webhook-bearing controller, document in this runbook which
  cert manager owns its TLS secret.
- Alert on `kube_pod_container_status_restarts_total` for known webhook
  controllers — a slow drip of restarts here is almost always a cert
  ownership issue, not a crash bug.

## References
- Lab memory: `feedback_webhook_self_cert_diagnosis`
- Related: [`policy/kyverno-cert-manager.md`](kyverno-cert-manager.md)
