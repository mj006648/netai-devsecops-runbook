# ArgoCD to Karmada API Server

이 디렉터리는 Tower의 ArgoCD가 Karmada API Server를 destination cluster로 사용하도록 검증하는 매니페스트를 보관한다.

## 구조

```text
GitHub repo
  -> ArgoCD on Tower
    -> Karmada API Server on Tower
      -> twinx / edgex / datax / poolx
```

## cluster secret

Karmada API Server cluster secret은 kubeconfig 인증서와 키를 포함하므로 레포에 저장하지 않는다.
실험에서는 live `argocd` namespace에만 `karmada-apiserver-cluster` secret을 생성했다.

## applications

- `applications/karmada-spread-constraints.yaml`
  - Git source: `kubernetes/karmada/manifests/demo-spread-constraints`
  - destination: Karmada API Server

## 실험 결과

실험 18에서 `karmada-spread-constraints` Application은 `Synced/Healthy` 상태가 됐고, Karmada API Server의 Deployment drift를 self-heal로 복구했다.

자세한 기록: `kubernetes/karmada/experiments/2026-06-27-18-argocd-to-karmada.md`
