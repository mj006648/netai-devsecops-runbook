# 실험 19. ArgoCD prune/delete/restore와 Karmada 전파

## 목적

실험 18에서는 ArgoCD가 Karmada API Server를 destination으로 사용해 GitOps sync와 self-heal을 수행할 수 있음을 확인했다.
이번 실험은 운영에서 더 중요한 delete/prune/restore 흐름을 검증한다.

ScaleX-POD 기준 목표 흐름:

```text
GitHub repo
  -> ArgoCD on Tower
    -> Karmada API Server on Tower
      -> TwinX / EdgeX / DataX / Resource Pool
```

확인할 것:

```text
1. Karmada API에서 live resource를 직접 삭제하면 ArgoCD self-heal로 복구되는가?
2. Git에서 manifest를 제거하면 ArgoCD prune으로 Karmada API와 member cluster에서 삭제되는가?
3. Git에서 manifest를 복구하면 ArgoCD sync로 Karmada API와 member cluster에 다시 생성되는가?
```

---

## 가설

```text
ArgoCD Application에 prune=true, selfHeal=true를 설정하면,
Karmada API Server에 생성된 resource도 일반 Kubernetes cluster처럼 Git desired state 기준으로 관리된다.
따라서 live delete는 self-heal되고, Git 삭제는 prune되며, Git 복구는 member cluster까지 재전파될 것이다.
```

---

## 사전 상태

ArgoCD:

```text
namespace: argocd
application controller: Running
Karmada API Server cluster secret: karmada-apiserver-cluster
```

Karmada:

```text
member clusters:
- twinx Push Ready
- edgex Push Ready
- datax Push Ready
- poolx Push Ready
```

기존 Application:

```text
karmada-spread-constraints: Synced/Healthy
```

---

## 전용 demo app

이번 실험은 기존 workload를 건드리지 않기 위해 전용 namespace와 Application을 만들었다.

```text
namespace : demo-argocd-prune-rollback
Deployment: demo-argocd-prune-rollback-nginx
Service   : demo-argocd-prune-rollback-nginx
replicas  : 4
placement : twinx=1, edgex=1, datax=1, poolx=1
```

매니페스트 위치:

```text
kubernetes/karmada/manifests/demo-argocd-prune-rollback/
  00-namespace.yaml
  10-deployment.yaml
  20-service.yaml
  30-propagation-policy.yaml
```

ArgoCD Application:

```text
kubernetes/karmada/argocd/applications/karmada-prune-rollback.yaml
```

Application 핵심:

```yaml
spec:
  source:
    repoURL: https://github.com/mj006648/netai-devsecops-runbook.git
    targetRevision: main
    path: kubernetes/karmada/manifests/demo-argocd-prune-rollback
  destination:
    server: https://karmada-apiserver.karmada-system.svc:5443
    namespace: demo-argocd-prune-rollback
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## 단계 1. 초기 source 추가와 push

초기 demo source와 Application을 main에 올렸다.

커밋:

```text
ffcad7e Add Karmada ArgoCD prune rollback demo
```

적용:

```bash
kubectl --context kind-tower apply \
  -f kubernetes/karmada/argocd/applications/karmada-prune-rollback.yaml

kubectl --context kind-tower -n argocd annotate application karmada-prune-rollback \
  argocd.argoproj.io/refresh=hard \
  --overwrite
```

초기 ArgoCD 상태:

```text
sync=Synced health=Healthy phase=Succeeded message=successfully synced (all tasks run)
revision=ffcad7eec12e22fac0e1df31b8657cf86f67aa50
```

ArgoCD managed resources:

```text
Namespace/demo-argocd-prune-rollback status=Synced
Service/demo-argocd-prune-rollback-nginx status=Synced
Deployment/demo-argocd-prune-rollback-nginx status=Synced
PropagationPolicy/demo-argocd-prune-rollback-policy status=Synced
```

Karmada API Server:

```text
Deployment/demo-argocd-prune-rollback-nginx 4/4
Service/demo-argocd-prune-rollback-nginx ClusterIP
PropagationPolicy/demo-argocd-prune-rollback-policy
```

ResourceBinding:

```text
demo-argocd-prune-rollback-nginx-deployment Scheduled=True FullyApplied=True
demo-argocd-prune-rollback-nginx-service    Scheduled=True FullyApplied=True
```

member cluster:

```text
twinx: Deployment 1/1, Service present
edgex: Deployment 1/1, Service present
datax: Deployment 1/1, Service present
poolx: Deployment 1/1, Service present
```

---

## 단계 2. live delete self-heal

Karmada API Server에서 Service를 직접 삭제했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-argocd-prune-rollback delete svc demo-argocd-prune-rollback-nginx
```

결과:

```text
service "demo-argocd-prune-rollback-nginx" deleted
```

삭제 직후:

```text
Error from server (NotFound): services "demo-argocd-prune-rollback-nginx" not found
```

ArgoCD refresh:

```bash
kubectl --context kind-tower -n argocd annotate application karmada-prune-rollback \
  argocd.argoproj.io/refresh=hard \
  --overwrite
```

관찰:

```text
check=1 sync=OutOfSync health=Missing phase=Running svc=present ip=10.99.233.86
check=2 sync=Synced health=Healthy phase=Succeeded message=successfully synced (all tasks run) svc=present ip=10.99.233.86
```

복구 후:

```text
Karmada API Service present
Service ResourceBinding present
member cluster Service present on twinx/edgex/datax/poolx
```

판단:

```text
Karmada API Server의 live delete는 ArgoCD self-heal로 복구됐다.
Karmada는 복구된 Service를 다시 member cluster로 전파했다.
```

---

## 단계 3. Git 삭제 prune

Git source에서 Service manifest를 제거했다.

```bash
git rm kubernetes/karmada/manifests/demo-argocd-prune-rollback/20-service.yaml
git commit -m "Remove prune rollback demo service"
git push origin main
```

커밋:

```text
06c8d76 Remove prune rollback demo service
```

ArgoCD refresh 후 관찰:

```text
check=1 sync=Synced health=Healthy revision=ffcad7e... service/demo-argocd-prune-rollback-nginx resourcebinding.work.karmada.io/demo-argocd-prune-rollback-nginx-service
check=2 sync=Synced health=Healthy revision=06c8d76... svc=missing serviceRB=missing
```

ArgoCD managed resources에서 Service가 사라졌다.

```text
Namespace/demo-argocd-prune-rollback status=Synced
Deployment/demo-argocd-prune-rollback-nginx status=Synced
PropagationPolicy/demo-argocd-prune-rollback-policy status=Synced
```

Karmada API Server:

```text
Deployment present
PropagationPolicy present
Service missing
Service ResourceBinding missing
```

member cluster:

```text
twinx: service not found
edgex: service not found
datax: service not found
poolx: service not found
```

판단:

```text
Git에서 Service manifest를 제거하면 ArgoCD prune이 Karmada API Server의 Service를 삭제했다.
Karmada는 Service ResourceBinding을 제거하고 member cluster의 Service도 삭제했다.
```

---

## 단계 4. Git 복구 restore

Service manifest를 다시 추가했다.

```bash
git add kubernetes/karmada/manifests/demo-argocd-prune-rollback/20-service.yaml
git commit -m "Restore prune rollback demo service"
git push origin main
```

커밋:

```text
55845e8 Restore prune rollback demo service
```

ArgoCD refresh 후 관찰:

```text
check=1 sync=Synced health=Healthy revision=06c8d76... svc=missing serviceRB=missing
check=2 sync=Synced health=Healthy revision=55845e8... svc=present ip=10.111.178.70 resourcebinding.work.karmada.io/demo-argocd-prune-rollback-nginx-service
```

ArgoCD managed resources:

```text
Namespace/demo-argocd-prune-rollback status=Synced
Service/demo-argocd-prune-rollback-nginx status=Synced
Deployment/demo-argocd-prune-rollback-nginx status=Synced
PropagationPolicy/demo-argocd-prune-rollback-policy status=Synced
```

Karmada API Server:

```text
Deployment/demo-argocd-prune-rollback-nginx 4/4
Service/demo-argocd-prune-rollback-nginx ClusterIP 10.111.178.70
PropagationPolicy/demo-argocd-prune-rollback-policy
```

ResourceBinding:

```text
Deployment RB:
- datax replicas=1
- edgex replicas=1
- poolx replicas=1
- twinx replicas=1
- Scheduled=True
- FullyApplied=True

Service RB:
- datax
- edgex
- poolx
- twinx
- Scheduled=True
- FullyApplied=True
```

member cluster 최종 상태:

```text
twinx: Deployment 1/1, Service present
edgex: Deployment 1/1, Service present
datax: Deployment 1/1, Service present
poolx: Deployment 1/1, Service present
```

판단:

```text
Git에서 Service manifest를 복구하면 ArgoCD가 Karmada API Server에 Service를 다시 생성하고,
Karmada가 member cluster로 재전파했다.
```

---

## 최종 상태

Git:

```text
55845e8 Restore prune rollback demo service
06c8d76 Remove prune rollback demo service
ffcad7e Add Karmada ArgoCD prune rollback demo
```

ArgoCD:

```text
sync=Synced health=Healthy phase=Succeeded
revision=55845e83aa73a2737d910fae95360c07099abac6
```

Karmada:

```text
Deployment RB: Scheduled=True FullyApplied=True
Service RB   : Scheduled=True FullyApplied=True
```

member cluster:

```text
twinx=1
edgex=1
datax=1
poolx=1
Service present on all four member clusters
```

---

## 성공/실패 판단

```text
성공
```

성공 근거:

```text
1. ArgoCD Application이 Karmada API Server를 destination으로 정상 sync했다.
2. Karmada API의 live Service 삭제는 ArgoCD self-heal로 복구됐다.
3. Git에서 Service manifest 제거 시 ArgoCD prune으로 Karmada API Service가 삭제됐다.
4. Karmada는 Service ResourceBinding과 member cluster Service를 삭제했다.
5. Git에서 Service manifest 복구 시 ArgoCD가 Service를 다시 생성했다.
6. Karmada는 Service를 twinx/edgex/datax/poolx로 다시 전파했다.
```

---

## 문제/에러

### 1. push rejected: 원격 main 선행 커밋

초기 demo commit push 시 원격 main에 새 커밋이 있어 push가 거절됐다.

```text
! [rejected] main -> main (fetch first)
```

처리:

```bash
git fetch origin main
git rebase origin/main
git push origin main
```

결과:

```text
rebase 후 push 성공
```

### 2. 삭제 파일 grep 검사

Service manifest 삭제 커밋 검사 중 삭제된 파일 경로에 대해 `grep`이 `No such file or directory`를 출력했다.

의미:

```text
삭제된 파일을 직접 grep 대상으로 넘겼기 때문이다.
삭제 커밋 검사에서는 --diff-filter=ACM 등으로 존재하는 파일만 검사하는 방식이 더 적합하다.
```

기능 영향:

```text
없음
```

---

## ScaleX-POD에 주는 의미

검증된 운영 패턴:

```text
Git desired state 삭제
  -> ArgoCD prune
    -> Karmada API resource 삭제
      -> ResourceBinding 삭제
        -> member cluster resource 삭제

Git desired state 복구
  -> ArgoCD sync
    -> Karmada API resource 생성
      -> ResourceBinding 생성
        -> member cluster resource 생성
```

ScaleX-POD 운영 설계에 반영할 점:

```text
1. 멀티클러스터 app의 delete/restore도 GitOps로 관리할 수 있다.
2. ArgoCD prune=true는 Karmada API와 member cluster까지 영향을 주므로 신중하게 사용해야 한다.
3. 운영 app에는 AppProject, sync window, branch protection, review flow 같은 안전장치가 필요하다.
4. Service, Deployment, PropagationPolicy를 같은 Application에서 관리하면 prune 영향 범위가 명확하다.
5. Karmada member cluster를 ArgoCD가 직접 관리하지 않아도, Karmada 전파 삭제/복구까지 이어진다.
```

---

## 다음 액션

```text
1. Pull mode member cluster 등록 실험
2. ApplicationSet으로 여러 Karmada Application 관리 실험
3. ArgoCD prune=true 운영 안전장치 정리
4. Kueue와 Karmada 역할 분리 실험
```
