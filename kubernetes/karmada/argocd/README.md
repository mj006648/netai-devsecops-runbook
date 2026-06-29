# ArgoCD to Karmada API Server

이 디렉터리는 Tower의 ArgoCD가 Karmada API Server를 destination cluster로 사용하도록 검증하는 매니페스트를 보관한다.

## 구조

```text
GitHub repo
  -> ArgoCD on Tower
    -> Karmada API Server on Tower
      -> twinx / edgex / datax / poolx / pullx
```

## cluster secret

Karmada API Server cluster secret은 kubeconfig 인증서와 키를 포함하므로 레포에 저장하지 않는다.
실험에서는 live `argocd` namespace에만 `karmada-apiserver-cluster` secret을 생성했다.

## applications

- `applications/karmada-spread-constraints.yaml`
  - Git source: `kubernetes/karmada/manifests/demo-spread-constraints`
  - destination: Karmada API Server
- `applications/karmada-prune-rollback.yaml`
  - Git source: `kubernetes/karmada/manifests/demo-argocd-prune-rollback`
  - destination: Karmada API Server
  - prune/self-heal 검증용

## applicationsets

- `applicationsets/karmada-demo-appset.yaml`
  - list generator로 `karmada-appset-edge`, `karmada-appset-data` Application 생성
  - destination: Karmada API Server
  - edge app: `edgex=1`, `pullx=1`
  - data app: `datax=2`

## projects

- `projects/karmada-guarded-project.yaml`
  - Karmada destination을 `demo-*` namespace로 제한하는 AppProject 샘플
  - source repo와 허용 resource 종류를 제한
  - `orphanedResources.warn=true`와 sync window 예시 포함
  - 기존 Application을 바로 이동하지 않고, prune 안전장치 샘플로 먼저 검증

관련 runbook:

- [`../runbooks/argocd-prune-safety.md`](../runbooks/argocd-prune-safety.md)

## 실험 결과

실험 18에서 `karmada-spread-constraints` Application은 `Synced/Healthy` 상태가 됐고, Karmada API Server의 Deployment drift를 self-heal로 복구했다.

자세한 기록: `kubernetes/karmada/experiments/2026-06-27-18-argocd-to-karmada.md`

실험 19에서 `karmada-prune-rollback` Application은 live delete self-heal, Git prune, Git restore 흐름을 모두 성공했다.

자세한 기록: `kubernetes/karmada/experiments/2026-06-29-19-argocd-prune-rollback.md`

실험 24에서 `karmada-demo-appset` ApplicationSet은 두 Application을 생성했고, 둘 다 `Synced/Healthy` 상태가 됐다. Karmada는 edge app을 `edgex=1,pullx=1`, data app을 `datax=2`로 전파했다.

자세한 기록: `kubernetes/karmada/experiments/2026-06-29-24-argocd-applicationset.md`

실험 25에서 ArgoCD prune 위험 모델을 정리하고 `karmada-guarded` AppProject 샘플을 live ArgoCD에 적용했다. 기존 Application은 아직 `default` project에 남겨두고, 실제 migration은 별도 실험으로 분리했다.

자세한 기록: `kubernetes/karmada/experiments/2026-06-29-25-argocd-prune-safety.md`
