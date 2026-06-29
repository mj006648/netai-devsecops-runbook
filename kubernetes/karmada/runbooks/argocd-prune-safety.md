# ArgoCD prune 운영 안전장치 runbook

## 목적

ArgoCD가 Karmada API Server를 destination으로 사용할 때 `prune=true`는 단순히 Tower의 리소스만 지우는 것이 아니다.
Karmada API Server에서 리소스가 삭제되면 Karmada가 member cluster의 Work도 정리하므로, 결과적으로 TwinX/EdgeX/DataX/Resource Pool/Pull Edge workload까지 삭제될 수 있다.

이 문서는 ScaleX-POD에서 ArgoCD prune을 운영할 때 필요한 안전장치를 정리한다.

---

## 위험 모델

```text
Git에서 manifest 삭제
  -> ArgoCD prune
    -> Karmada API Server resource 삭제
      -> ResourceBinding/Work 삭제
        -> member cluster resource 삭제
```

주의할 resource:

```text
Namespace
Deployment
Service
PropagationPolicy
OverridePolicy
WorkloadRebalancer
ApplicationSet이 생성한 Application
```

---

## 현재 lab에서 확인된 prune 관련 상태

```text
karmada-prune-rollback: prune=true, selfHeal=true
karmada-appset-edge   : prune=true, selfHeal=true, resources-finalizer 있음
karmada-appset-data   : prune=true, selfHeal=true, resources-finalizer 있음
karmada-spread-constraints: selfHeal=true, prune 미설정
```

ApplicationSet이 생성한 Application에는 다음 finalizer가 붙을 수 있다.

```text
resources-finalizer.argocd.argoproj.io
```

이 finalizer가 있는 Application을 삭제하면 target resource prune까지 이어질 수 있으므로, Application 삭제 테스트는 별도 안전 실험으로 분리한다.

---

## 안전장치 1. AppProject로 범위 제한

샘플 manifest:

```text
kubernetes/karmada/argocd/projects/karmada-guarded-project.yaml
```

핵심 제한:

```text
sourceRepos: netai-devsecops-runbook만 허용
destinations: Karmada API Server의 demo-* namespace만 허용
clusterResourceWhitelist: Namespace만 허용
namespaceResourceWhitelist: Service, Deployment, PropagationPolicy만 허용
orphanedResources.warn: true
syncWindows: karmada-guarded-* app에 제한적 sync window 예시
```

운영에서는 기존 `default` project에 모든 Karmada app을 두지 말고, 목적별 AppProject를 분리한다.

---

## 안전장치 2. branch protection과 reviewed sync

ArgoCD가 `main`을 바라보면 main 변경이 곧 운영 desired state 변경이다.
따라서 운영 repo에서는 다음을 적용한다.

```text
1. main 직접 push 제한
2. pull request review 필수
3. CODEOWNERS로 Karmada/ArgoCD path owner 지정
4. destructive change checklist 필수
5. ApplicationSet generator 변경은 별도 리뷰
```

현재 lab에서는 빠른 실험을 위해 main 직접 push를 사용하지만, 실제 ScaleX-POD에서는 보호 branch가 필요하다.

---

## 안전장치 3. sync window

운영 prune은 정해진 시간대에만 허용한다.

예시:

```yaml
syncWindows:
  - kind: allow
    schedule: "0 0 * * *"
    duration: 1h
    applications:
      - karmada-guarded-*
    manualSync: true
```

의미:

```text
자동 sync/prune 가능 시간을 제한한다.
manualSync는 허용해서 긴급 복구 여지를 둔다.
```

실제 운영에서는 업무 시간, 점검 시간, edge 현장망 상태를 고려해 window를 정한다.

---

## 안전장치 4. prune 전 preflight

prune이 예상되는 Git 변경 전에는 다음을 확인한다.

```bash
kubectl --context kind-tower -n argocd get applications -o wide
kubectl --context kind-tower -n argocd get applications -o jsonpath='{range .items[*]}{.metadata.name}{" prune="}{.spec.syncPolicy.automated.prune}{" finalizers="}{.metadata.finalizers}{"\n"}{end}'

kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebinding -A -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusterresourcebinding -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get work -A
```

확인할 것:

```text
1. 삭제될 resource가 어떤 ResourceBinding/Work와 연결되는지
2. member cluster 어디에 실제 resource가 있는지
3. ApplicationSet이 생성한 Application인지
4. finalizer가 붙어 있는지
5. rollback commit 또는 manifest 복구 경로가 있는지
```

---

## 안전장치 5. deletion cascade 분리

ApplicationSet 또는 Application 삭제는 manifest prune보다 위험할 수 있다.

운영 원칙:

```text
1. Git manifest 삭제와 Application 삭제를 같은 작업에 묶지 않는다.
2. ApplicationSet 삭제 전 생성된 Application 목록을 백업한다.
3. Application finalizer 유무를 확인한다.
4. prune 영향이 불명확하면 automated prune을 먼저 끄고 관찰한다.
```

---

## rollback 절차

잘못 prune된 경우:

```text
1. Git에서 삭제된 manifest를 즉시 복구한다.
2. ArgoCD Application refresh/sync를 실행한다.
3. Karmada API Server에서 resource 복구를 확인한다.
4. ResourceBinding/Work가 다시 생성됐는지 확인한다.
5. member cluster 실제 Pod/Service를 확인한다.
```

명령 예시:

```bash
kubectl --context kind-tower -n argocd annotate application <app-name> \
  argocd.argoproj.io/refresh=hard \
  --overwrite

kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n <namespace> get deploy,svc,propagationpolicy,rb -o wide
```

---

## ScaleX-POD 운영 권장안

```text
1. 실험 app과 운영 app의 AppProject 분리
2. 운영 app은 prune=false로 시작하고, 검증된 app만 prune=true 전환
3. ApplicationSet generator 변경은 고위험 변경으로 분류
4. Karmada policy/resource 삭제는 member cluster 영향까지 리뷰
5. ResourceBinding/Work snapshot을 변경 기록에 첨부
6. Edge/Pull cluster READY Unknown 상태에서는 prune 금지
```
