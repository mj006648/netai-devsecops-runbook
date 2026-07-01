# 실험 25. ArgoCD prune 운영 안전장치 정리

## 목적

실험 19에서 ArgoCD `prune=true`가 Karmada API Server와 member cluster까지 삭제/복구 흐름을 전파하는 것을 확인했다.
실험 24에서는 ApplicationSet이 생성한 Application에도 `prune=true`와 finalizer가 붙는 것을 확인했다.
이번 실험은 실제 ScaleX-POD 운영에서 prune으로 인한 대량 삭제를 줄이기 위한 안전장치를 runbook과 AppProject 샘플로 정리한다.

---

## 현재 lab 상태

```text
karmada-prune-rollback: prune=true, selfHeal=true
karmada-appset-edge   : prune=true, selfHeal=true, resources-finalizer 있음
karmada-appset-data   : prune=true, selfHeal=true, resources-finalizer 있음
karmada-spread-constraints: selfHeal=true, prune 미설정
```

확인 명령:

```bash
kubectl --context kind-tower -n argocd get applications -o jsonpath='{range .items[*]}{.metadata.name}{" prune="}{.spec.syncPolicy.automated.prune}{" selfHeal="}{.spec.syncPolicy.automated.selfHeal}{" finalizers="}{.metadata.finalizers}{"\n"}{end}'
```

---

## 위험 모델

```text
Git에서 manifest 삭제
  -> ArgoCD prune
    -> Karmada API Server resource 삭제
      -> ResourceBinding/Work 삭제
        -> member cluster resource 삭제
```

따라서 ArgoCD prune은 단일 cluster 삭제가 아니라 ScaleX-POD 전체 member cluster 삭제로 이어질 수 있다.

---

## 작성한 runbook

```text
kubernetes/multicluster/karmada/runbooks/argocd-prune-safety.md
```

핵심 내용:

```text
1. AppProject로 source/destination/resource 범위 제한
2. main branch protection과 review 필수화
3. sync window로 prune 가능 시간 제한
4. prune 전 ResourceBinding/Work/member 상태 preflight
5. ApplicationSet/Application 삭제와 manifest prune을 분리
6. 잘못 prune된 경우 Git 복구 -> ArgoCD refresh -> Karmada/member 확인
```

---

## 작성한 AppProject 샘플

```text
kubernetes/multicluster/karmada/argocd/projects/karmada-guarded-project.yaml
```

핵심 제한:

```text
sourceRepos:
- https://github.com/mj006648/netai-devsecops-runbook.git

destinations:
- server: https://karmada-apiserver.karmada-system.svc:5443
  namespace: demo-*

clusterResourceWhitelist:
- Namespace

namespaceResourceWhitelist:
- Service
- Deployment
- PropagationPolicy

orphanedResources.warn: true
syncWindows: karmada-guarded-* 대상 제한 window 예시
```

---

## live 검증

server dry-run:

```bash
kubectl --context kind-tower apply --dry-run=server \
  -f kubernetes/multicluster/karmada/argocd/projects/karmada-guarded-project.yaml
```

결과:

```text
appproject.argoproj.io/karmada-guarded created (server dry run)
```

live apply:

```bash
kubectl --context kind-tower apply \
  -f kubernetes/multicluster/karmada/argocd/projects/karmada-guarded-project.yaml
```

결과:

```text
appproject.argoproj.io/karmada-guarded created
```

확인:

```text
AppProject/karmada-guarded present
sourceRepos 제한 적용
destinations demo-* 제한 적용
resource whitelist 적용
orphanedResources.warn=true
syncWindows 적용
```

주의:

```text
기존 Application은 아직 default project에 남겨두었다.
이번 실험은 안전장치 샘플 검증이며, 기존 app project migration은 별도 작업으로 분리한다.
```

---

## 성공/실패 판단

```text
prune 위험 모델 정리: 성공
runbook 작성: 성공
AppProject 샘플 작성: 성공
AppProject server dry-run 검증: 성공
live ArgoCD에 AppProject 적용: 성공
기존 Application project 이동: 보류
```

---

## ScaleX-POD에 주는 의미

```text
1. 운영 app을 default project에 몰아넣지 않는다.
2. AppProject로 Karmada destination과 허용 resource 종류를 제한한다.
3. prune=true는 검증된 app에만 켠다.
4. ApplicationSet generator 변경은 고위험 변경으로 본다.
5. Pull/Edge cluster READY Unknown 상태에서는 prune을 금지한다.
6. Git 삭제 전 ResourceBinding/Work/member 상태 snapshot을 남긴다.
```
