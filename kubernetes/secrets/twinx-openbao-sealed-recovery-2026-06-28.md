# TwinX OpenBao Sealed 복구 기록 2026-06-28

## 요약

TwinX Argo CD에서 `external-secrets-resources`, `trident-portal`, `trident-spark`, `trident-twin-hub`가 `Degraded`로 보였습니다.

직접 원인은 OpenBao가 `Sealed=true` 상태였고, External Secrets Operator가 `openbao-cluster-store`를 통해 OpenBao Kubernetes auth login을 할 수 없었던 것입니다.

2026-06-28 복구 결과:

- OpenBao: `Initialized=true`, `Sealed=false`
- `ClusterSecretStore/openbao-cluster-store`: `Valid`, `Ready=True`
- Trident ExternalSecrets: `SecretSynced`, `Ready=True`
- Argo CD health:
  - `external-secrets-resources`: `Synced / Healthy`
  - `trident-portal`: `Healthy`
  - `trident-spark`: `Healthy`
  - `trident-twin-hub`: `Healthy`

> 공개 runbook 규칙: unseal key와 root token 값은 절대 이 문서에 쓰지 않습니다.

## 증상

Argo CD에서 아래 health 문제가 보였습니다.

```text
external-secrets-resources   Synced     Degraded
trident-portal               OutOfSync  Degraded
trident-spark                OutOfSync  Degraded
trident-twin-hub             OutOfSync  Degraded
```

Kubernetes 쪽 증상 확인 명령:

```bash
kubectl get clustersecretstore openbao-cluster-store
kubectl get externalsecret -n trident
kubectl get externalsecret -n spark-operator
```

관측된 형태:

```text
openbao-cluster-store  InvalidProviderConfig  Ready=False
trident-*              SecretSyncedError      Ready=False
```

External Secrets Operator 로그에는 아래 내용이 있었습니다.

```text
unable to log in with Kubernetes auth
URL: PUT http://openbao.openbao.svc.cluster.local:8200/v1/auth/kubernetes/login
Code: 503
* Vault is sealed
```

## 진단

OpenBao pod 내부에서 상태를 확인했습니다.

```bash
kubectl -n openbao exec openbao-0 -- sh -lc '
  export BAO_ADDR=http://127.0.0.1:8200
  bao status
'
```

문제 상태:

```text
Initialized        true
Sealed             true
Seal Type          shamir
Threshold          3
Unseal Progress    0/3
Storage Type       file
HA Enabled         false
```

해석:

- `Initialized=true`이므로 **`bao operator init`을 다시 실행하면 안 됩니다**.
- `Sealed=true`는 데이터는 남아 있지만 OpenBao가 secret/auth 요청을 처리하지 않는 상태라는 뜻입니다.
- `Threshold=3`이므로 기존 unseal key 5개 중 아무 3개가 필요합니다.

ESO가 이 OpenBao store를 사용 중인지 확인했습니다.

```bash
kubectl get clustersecretstore openbao-cluster-store -o yaml
```

예상되는 store 형태:

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

## 원인

OpenBao는 standalone Shamir seal 방식으로 배포되어 있었습니다.

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

Shamir seal 방식에서는 pod가 재시작되어도 seal 상태가 자동으로 복구되지 않습니다.

PVC의 file storage는 OpenBao 데이터, policy, role, KV 내용을 보존하지만, 프로세스는 sealed 상태로 시작합니다. 따라서 pod restart, node maintenance, reschedule 이후 OpenBao가 `Initialized=true`, `Sealed=true` 상태로 올라올 수 있습니다.

이 문제는 Argo CD에서 바로 드러나지 않았습니다. chart values에서 sealed 상태의 OpenBao도 probe를 통과하도록 설정되어 있었기 때문입니다.

```yaml
readinessProbe:
  path: "/v1/sys/health?standbyok=true&sealedcode=204&uninitcode=204"
livenessProbe:
  path: "/v1/sys/health?standbyok=true&sealedcode=204&uninitcode=204"
```

이 설정 때문에 OpenBao pod는 sealed 상태에서도 `Ready`로 보일 수 있습니다. 하지만 ESO는 `/v1/auth/kubernetes/login`에 인증할 수 없으므로 OpenBao에 의존하는 ExternalSecret들이 모두 실패합니다.

## 복구 절차

### 1. 다시 초기화하지 않기

`Initialized=true`라면 아래 명령은 실행하면 안 됩니다.

```bash
bao operator init -key-shares=5 -key-threshold=3
```

`operator init`은 완전히 새로운 OpenBao data directory에서만 사용하는 명령입니다. 이미 초기화된 인스턴스는 기존 unseal key로 unseal해야 합니다.

### 2. 기존 unseal key 3개로 unseal

key가 shell history나 process args에 남지 않도록 interactive TTY로 입력합니다.

```bash
kubectl -n openbao exec -it openbao-0 -- sh -lc '
  export BAO_ADDR=http://127.0.0.1:8200
  bao operator unseal
'
```

프롬프트가 뜨면 unseal key 하나를 입력합니다. threshold를 만족할 때까지 같은 명령을 반복합니다.

```bash
# key 1
kubectl -n openbao exec -it openbao-0 -- sh -lc 'export BAO_ADDR=http://127.0.0.1:8200; bao operator unseal'

# key 2
kubectl -n openbao exec -it openbao-0 -- sh -lc 'export BAO_ADDR=http://127.0.0.1:8200; bao operator unseal'

# key 3
kubectl -n openbao exec -it openbao-0 -- sh -lc 'export BAO_ADDR=http://127.0.0.1:8200; bao operator unseal'
```

최종 기대 상태:

```text
Initialized     true
Sealed          false
Storage Type    file
HA Enabled      false
```

### 3. ESO 상태가 오래 남아 있으면 reconcile 유도

ESO는 보통 다음 reconcile interval에 자동 복구됩니다. 즉시 안전하게 reconcile을 유도하려면 store와 영향을 받은 ExternalSecret에 임시 annotation을 찍습니다.

```bash
stamp=$(date +%s)
kubectl annotate clustersecretstore openbao-cluster-store force-sync="$stamp" --overwrite
kubectl -n trident annotate externalsecret --all force-sync="$stamp" --overwrite
kubectl -n spark-operator annotate externalsecret --all force-sync="$stamp" --overwrite
```

리소스가 `Ready=True`가 되면 GitOps drift를 피하기 위해 임시 annotation을 제거합니다.

```bash
kubectl annotate clustersecretstore openbao-cluster-store force-sync- --overwrite
kubectl -n trident annotate externalsecret --all force-sync- --overwrite
kubectl -n spark-operator annotate externalsecret --all force-sync- --overwrite
```

## 검증

OpenBao 상태:

```bash
kubectl -n openbao exec openbao-0 -- sh -lc '
  export BAO_ADDR=http://127.0.0.1:8200
  bao status
'
```

필수 상태:

```text
Initialized     true
Sealed          false
```

ESO store:

```bash
kubectl get clustersecretstore openbao-cluster-store
```

필수 상태:

```text
NAME                    STATUS   CAPABILITIES   READY
openbao-cluster-store   Valid    ReadWrite      True
```

Trident ExternalSecrets:

```bash
kubectl get externalsecret -n trident
kubectl get externalsecret -n spark-operator
```

필수 형태:

```text
STATUS         READY
SecretSynced   True
```

Argo CD health:

```bash
kubectl get applications.argoproj.io -n argocd external-secrets-resources trident-portal trident-spark trident-twin-hub
```

필수 상태:

```text
external-secrets-resources   Healthy
trident-portal               Healthy
trident-spark                Healthy
trident-twin-hub             Healthy
```

메모: `trident-*` app은 ExternalSecret CRD default field나 controller-owned metadata 차이 때문에 `OutOfSync`가 남을 수 있습니다. OpenBao 장애 종료 기준은 health 복구와 `SecretSynced=True`로 보고, 남은 diff는 별도 GitOps drift 정리로 처리합니다.

## 재발 방지

1. unseal key는 승인된 secret manager에 보관하고, 이 문서에는 값이 아니라 조회 경로만 남깁니다.
2. `bao status` 또는 `/v1/sys/seal-status` 기준 `sealed=true` 알림을 추가합니다.
3. sealed 상태가 운영상 바로 보이도록 OpenBao health probe를 조정하거나, sealed 상태에서 실패하는 별도 synthetic check를 추가합니다.
4. 안전한 KMS/HSM 기반 seal backend를 사용할 수 있다면 auto-unseal 도입을 검토합니다.
5. 계획된 node maintenance 또는 OpenBao pod restart 이후에는 아래를 명시적으로 확인합니다.

   ```bash
   kubectl -n openbao exec openbao-0 -- bao status
   kubectl get clustersecretstore openbao-cluster-store
   kubectl get externalsecret -n trident
   ```

## 관련 TwinX-Ops 경로

```text
argocd/twinx-infra/apps/openbao/values.yaml
argocd/twinx-infra/apps/openbao-resources/
argocd/twinx-infra/apps/external-secrets/values.yaml
argocd/twinx-infra/apps/external-secrets-resources/01-cluster-secret-store.yaml
argocd/trident/apps/trident-portal/*externalsecret.yaml
argocd/trident/apps/trident-spark/01-rbac-secret.yaml
argocd/trident/apps/trident-twin-hub/keycloak-externalsecret.yaml
```
