# demo-argocd-prune-rollback

ArgoCD가 Karmada API Server를 destination으로 사용할 때 delete, prune, restore 동작이 Karmada member cluster까지 전파되는지 확인하는 실험 매니페스트다.

## workload

```text
namespace : demo-argocd-prune-rollback
Deployment: demo-argocd-prune-rollback-nginx
Service   : demo-argocd-prune-rollback-nginx
replicas  : 4
placement : twinx=1, edgex=1, datax=1, poolx=1
```

## 실험 포인트

```text
1. live Service 삭제 -> ArgoCD self-heal로 복구되는지 확인
2. Git에서 Service manifest 제거 -> ArgoCD prune으로 Karmada API와 member cluster에서 삭제되는지 확인
3. Git에서 Service manifest 복구 -> ArgoCD sync로 Karmada API와 member cluster에 재생성되는지 확인
```

자세한 기록: `kubernetes/multicluster/karmada/experiments/2026-06-29-19-argocd-prune-rollback.md`

## 실제 결과

```text
self-heal: live Service 삭제 후 ArgoCD가 복구
prune    : Git에서 Service 제거 후 Karmada API/member Service 삭제
restore  : Git에서 Service 복구 후 Karmada API/member Service 재생성
```
