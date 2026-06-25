# Kyverno + cert-manager 연동 시 인증서 ping-pong이 무한 반복됨 (chart v3.7.x)

## Symptom
- Kyverno Helm chart에서 cert-manager integration을 켠 뒤 admission controller pod가 몇 분마다 `SIGTERM`으로 재시작된다.
- Admission request가 흔들리고 validation/mutation policy가 불안정해진다.
- webhook TLS secret의 owner가 계속 바뀐다. 어느 순간에는 cert-manager가 발급한 material이고,
  다음 순간에는 Kyverno self-signed material로 바뀐다.

## Diagnosis
```bash
kubectl -n kyverno get pods -w
kubectl -n kyverno get secret kyverno-svc.kyverno.svc.kyverno-tls-pair -o yaml | grep -E 'owner|managed-by|annotations'
kubectl -n kyverno logs deploy/kyverno-admission-controller | grep -i cert
```

Secret annotation이 cert-manager와 Kyverno 사이에서 번갈아 바뀌고,
admission controller가 자주 재시작되는 것을 볼 수 있다.

## Root cause
Kyverno Helm chart **v3.7.x**에서는 cert-manager handoff가 반쪽만 구현되어 있다.

- Chart는 올바른 Issuer를 바라보는 `Certificate` resource를 만들 수 있다.
- 하지만 Kyverno admission controller는 여전히 **자체 certificate reconciliation loop**를 실행하고,
  webhook secret을 완전히 소유한다고 가정한다.
- Controller가 자신이 만든 것이 아닌 secret, 즉 cert-manager가 발급한 secret을 보면
  self-signed material로 덮어쓰고 재시작한다.
- cert-manager는 drift를 감지하고 secret을 다시 발급본으로 되돌린다.
- 이 loop가 끝없이 반복된다.

v3.7.x에는 webhook 기능을 유지하면서 Kyverno internal cert loop만 완전히 끄는 flag가 없다.
이 chart version에서는 두 manager가 동시에 공존할 수 없다.

## Fix — Kyverno가 자체 인증서를 관리하게 둔다

현재 TwinX에서는 아래 설정을 사용한다.
`argocd/twinx-infra/apps/kyverno/values.yaml`:

```yaml
certManager:
  enabled: false
```

재배포 후 남은 resource를 정리한다.

```bash
kubectl -n kyverno delete certificate,issuer -l app.kubernetes.io/instance=kyverno
kubectl -n kyverno delete secret   kyverno-svc.kyverno.svc.kyverno-tls-pair   kyverno-cleanup-controller.kyverno.svc.kyverno-tls-pair   --ignore-not-found
```

다음 시작 시 Kyverno가 self-signed material을 다시 만들고 flapping이 멈춘다.

## 운영상 괜찮은 이유
- Webhook certificate는 cluster 내부 admission에만 사용된다.
- Kyverno가 만료 전에 자동으로 rotate한다.
- CA bundle은 `ValidatingWebhookConfiguration` / `MutatingWebhookConfiguration`에 자동 주입된다.
- 신뢰 경계는 apiserver → webhook 구간이다. 여기서 cert-manager를 개입시켜 얻는 보안 이득은 크지 않다.

## Prevention
- 이후 운영자가 “cert-manager를 켜면 더 좋아 보인다”고 다시 켜지 않도록 values file에
  `certManager.enabled: false`를 명시적으로 고정한다.
- Admission controller restart count에 alert를 건다. 지속적인 restart 증가는 이 이슈가 다시 나타난 신호일 수 있다.

## 참고
- TwinX values: `argocd/twinx-infra/apps/kyverno/values.yaml`
- Discussion: [#2](https://github.com/mj006648/netai-devsecops-runbook/discussions/2)
