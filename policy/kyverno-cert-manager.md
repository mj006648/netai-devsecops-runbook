# Kyverno + cert-manager integration causes infinite cert ping-pong (chart v3.7.x)

## Symptom
- After enabling cert-manager integration in the Kyverno Helm chart, the
  admission controller pods restart every few minutes with `SIGTERM`.
- Admission requests flap; validation/mutation policies become unreliable.
- The webhook TLS secret keeps changing owners: at one moment it carries
  cert-manager–issued material, at the next it has Kyverno's self-signed.

## Diagnosis
```bash
kubectl -n kyverno get pods -w
kubectl -n kyverno get secret kyverno-svc.kyverno.svc.kyverno-tls-pair -o yaml | grep -E 'owner|managed-by'
kubectl -n kyverno logs deploy/kyverno-admission-controller | grep -i cert
```

You'll see the secret's annotations alternate between cert-manager and
Kyverno, with frequent admission controller restarts.

## Root cause
In Kyverno Helm chart **v3.7.x** the cert-manager handoff is only
partially implemented:

- The chart can create a `Certificate` resource pointing at the right
  Issuer.
- The Kyverno admission controller still runs its **own** certificate
  reconciliation loop, expecting to fully own the webhook secret.
- When it sees a secret it didn't generate (the cert-manager–issued one),
  it overwrites it with self-signed material and restarts.
- cert-manager's controller observes drift and reconciles the secret back
  to its issued cert.
- Loop continues indefinitely.

There is no flag in v3.7.x that fully disables Kyverno's internal cert
loop while keeping the webhooks functional — the two managers cannot
coexist in this chart version.

## Fix — let Kyverno manage its own certs
```yaml
# values.yaml
certManager:
  create: false
admissionController:
  # remove any cert-manager–specific extraArgs
```

Clean up leftovers after redeploying:
```bash
kubectl -n kyverno delete certificate,issuer -l app.kubernetes.io/instance=kyverno
kubectl -n kyverno delete secret \
  kyverno-svc.kyverno.svc.kyverno-tls-pair \
  kyverno-cleanup-controller.kyverno.svc.kyverno-tls-pair \
  --ignore-not-found
```

Kyverno regenerates its self-signed material on next start and stops
flapping.

## Why this is acceptable in practice
- Webhook certs are scoped to in-cluster admission only.
- Kyverno auto-rotates them before expiry.
- The CA bundle is injected into the `ValidatingWebhookConfiguration` /
  `MutatingWebhookConfiguration` automatically.
- The trust boundary is the apiserver-to-webhook hop; there is no
  meaningful security gain from cert-manager involvement here.

## Prevention
- Pin `certManager.create: false` in the values file so a future operator
  doesn't re-enable it.
- Alert on admission controller restart count; a sustained increase often
  re-surfaces this issue.

## References
- Lab memory: `feedback_kyverno_certmanager_chart_bug`
- Discussion: [#2](https://github.com/mj006648/netai-devsecops-runbook/discussions/2)
