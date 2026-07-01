# Kubernetes Security

OpenBao, External Secrets Operator, Kyverno, cert-manager, RBAC/OIDC, and webhook lifecycle runbooks.

## Quick map

| Last update | Topic | Document | Contents |
| --- | --- | --- | --- |
| 2026-06-28 | OpenBao / ESO | [TwinX OpenBao Sealed Recovery](twinx-openbao-sealed-recovery-2026-06-28.md) | OpenBao sealed 상태로 ESO/ExternalSecret이 Degraded 된 장애 복구 |
| 2026-06-25 | Kyverno / cert-manager | [Kyverno + cert-manager](kyverno-cert-manager.md) | Kyverno chart v3.7.x 인증서 ping-pong 문제 |
| 2026-06-25 | Webhook TLS | [Webhook Cert SIGTERM](webhook-cert-sigterm.md) | webhook controller가 인증서 owner 충돌로 주기적 SIGTERM 재시작되는 문제 |
