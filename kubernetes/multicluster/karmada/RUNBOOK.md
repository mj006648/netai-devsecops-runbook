# Karmada 운영 Runbook

이 디렉터리는 Karmada 실험 결과를 실제 ScaleX-POD 운영 절차로 바꾸기 위한 runbook 공간이다.

전체 운영 모델은 [`./OPERATING_MODEL.md`](./OPERATING_MODEL.md)를 기준으로 한다.

## 현재 검증된 흐름

### 장애/점검 시 workload 이동

```text
1. 대상 cluster 상태 확인
2. 이동 대상 workload와 유지 대상 workload 분리
3. 이동 대상에는 matching clusterTolerations를 두지 않음
4. 유지 대상에는 matching clusterTolerations 설정
5. 대상 cluster에 NoExecute taint 추가
6. ResourceBinding과 member cluster 상태 확인
```

관련 실험:

- [`./lab/experiments/2026-06-26-08-noexecute-eviction.md`](./lab/experiments/2026-06-26-08-noexecute-eviction.md)
- [`./lab/experiments/2026-06-26-10-noexecute-toleration-scope.md`](./lab/experiments/2026-06-26-10-noexecute-toleration-scope.md)

### 복구 후 재균형

```text
1. 대상 cluster 복구 확인
2. NoExecute taint 제거
3. 재균형 대상 workload 목록 작성
4. WorkloadRebalancer 생성
5. WorkloadRebalancer status와 ResourceBinding 확인
```

관련 실험:

- [`./lab/experiments/2026-06-26-09-workload-rebalancer-reschedule.md`](./lab/experiments/2026-06-26-09-workload-rebalancer-reschedule.md)
- [`./lab/experiments/2026-06-26-11-multi-workload-rebalancer.md`](./lab/experiments/2026-06-26-11-multi-workload-rebalancer.md)

### Pull mode cluster 포함 재균형

```text
1. 신규 Pull mode cluster가 placement selector에 매칭되는지 확인
2. ResourceBinding에서 기존 replica skew 확인
3. WorkloadRebalancer 생성
4. ResourceBinding이 Push/Pull cluster를 모두 포함하도록 재계산됐는지 확인
5. Push/Pull member cluster의 실제 Deployment/Pod 상태 확인
```

관련 실험:

- [`./lab/experiments/2026-06-29-23-pull-mode-workload-rebalancer.md`](./lab/experiments/2026-06-29-23-pull-mode-workload-rebalancer.md)

### 신규 member cluster label 영향 범위 점검

```text
1. 신규 cluster label 부여 전 기존 policy selector audit
2. ResourceBinding/ClusterResourceBinding snapshot 저장
3. label을 한 번에 하나씩 부여
4. label 부여 후 binding diff 확인
5. 예상하지 않은 binding이 생기면 label 또는 policy rollback
6. replica workload 재균형은 WorkloadRebalancer 절차로 분리
```

관련 문서:

- [신규 member cluster label 상세 checklist](#신규-member-cluster-label-영향-범위-점검-checklist)
- [`./lab/experiments/2026-06-29-22-new-cluster-label-impact.md`](./lab/experiments/2026-06-29-22-new-cluster-label-impact.md)

### ScaleX repo ownership 분리

```text
1. ArgoCD 서버는 TowerX에 하나만 둔다.
2. tower-k8s는 TowerX 제어 클러스터 repo로 둔다.
3. scalex-k8s는 Karmada 멀티클러스터 전용 repo로 둔다.
4. datax-k8s/twinx-k8s/edgex-k8s는 smartx-k8s preset 방식의 단일 클러스터 repo로 둔다.
5. 멀티클러스터 전파 resource와 PropagationPolicy/OverridePolicy는 scalex-k8s에 둔다.
6. CNI/CSI/storage/ingress/GPU operator/cluster-local app은 각 *-k8s에 둔다.
7. 같은 live resource를 scalex-k8s와 *-k8s에 동시에 선언하지 않는다.
8. Karmada로 전파한 resource는 member cluster local repo에서 다시 관리하지 않는다.
```

권장 흐름:

```text
tower-k8s  -> TowerX ArgoCD -> TowerX cluster

scalex-k8s -> TowerX ArgoCD -> Karmada API Server
                              -> EdgeX / DataX / TwinX / Resource Pool

twinx-k8s  -> TowerX ArgoCD -> TwinX cluster
datax-k8s  -> TowerX ArgoCD -> DataX cluster
edgex-k8s  -> TowerX ArgoCD -> EdgeX cluster
```

관련 실험:

- [`./lab/experiments/2026-07-07-33-scalex-repo-split-poc.md`](./lab/experiments/2026-07-07-33-scalex-repo-split-poc.md)

### ArgoCD prune 운영 안전장치

```text
1. ArgoCD Application의 prune/selfHeal/finalizer 상태 확인
2. AppProject로 source repo, destination namespace, resource 종류 제한
3. sync window와 reviewed sync 정책 준비
4. prune 전 ResourceBinding/Work/member cluster snapshot 저장
5. ApplicationSet/Application 삭제와 manifest prune을 분리
6. 잘못 prune된 경우 Git 복구 -> ArgoCD refresh -> Karmada/member 확인
```

관련 문서:

- [`argocd-prune-safety.md`](#argocd-prune-운영-안전장치-runbook)
- [`./lab/argocd/projects/karmada-guarded-project.yaml`](./lab/argocd/projects/karmada-guarded-project.yaml)
- [`./lab/experiments/2026-06-29-25-argocd-prune-safety.md`](./lab/experiments/2026-06-29-25-argocd-prune-safety.md)

### Karmada + Kueue 역할 분리

```text
1. Karmada는 member cluster placement를 담당
2. Kueue는 선택된 member cluster 내부의 Job admission과 quota를 담당
3. Kueue ResourceFlavor/ClusterQueue/LocalQueue는 Kueue가 설치된 member cluster에 적용
4. Karmada API Server에는 일반 Job과 PropagationPolicy를 적용
5. ArgoCD를 같이 쓸 때도 ArgoCD Synced와 Karmada FullyApplied만으로 Job 실행을 판단하지 않음
6. 상태 확인은 Karmada ResourceBinding과 member Kueue Workload/Queue를 함께 확인
7. Kueue controller/webhook 장애는 Karmada FullyApplied=False로 보일 수 있음
8. quota 증가는 pending 해소, quota 감소는 새 admission 제한으로 해석
```

관련 문서:

- [Kueue 관측/알림 상세 runbook](#kueue-관측알림-runbook)
- [`./lab/experiments/2026-06-29-27-kueue-datax-basic.md`](./lab/experiments/2026-06-29-27-kueue-datax-basic.md)
- [`./lab/experiments/2026-06-29-28-argocd-karmada-kueue.md`](./lab/experiments/2026-06-29-28-argocd-karmada-kueue.md)
- [`./lab/experiments/2026-06-29-29-kueue-observability.md`](./lab/experiments/2026-06-29-29-kueue-observability.md)
- [`./lab/experiments/2026-06-30-30-kueue-controller-recovery.md`](./lab/experiments/2026-06-30-30-kueue-controller-recovery.md)
- [`./lab/experiments/2026-06-30-31-kueue-quota-change.md`](./lab/experiments/2026-06-30-31-kueue-quota-change.md)

### Pull mode 네트워크 단절/복구

```text
1. Pull mode cluster와 agent 상태 확인
2. 네트워크 차단 지점이 node OUTPUT인지 Pod egress/FORWARD인지 구분
3. 차단 중 Cluster READY, agent log, member workload 유지 여부 확인
4. 차단 중 desired state 변경이 member에 반영되지 않는지 확인
5. 복구 후 agent 재시작, Work sync, status reflect까지 확인
```

관련 실험:

- [`./lab/experiments/2026-06-29-26-pull-mode-network-partition.md`](./lab/experiments/2026-06-29-26-pull-mode-network-partition.md)

## 다음 정리 대상

- OverridePolicy image/storageClass
- scheduler-estimator 운영 적용 절차
- ArgoCD -> Karmada API Server GitOps 흐름
- 실제 tower-k8s/scalex-k8s/twinx-k8s/datax-k8s/edgex-k8s repo 생성 및 bootstrap
- 실제 ScaleX-POD 이전 checklist
- Kueue GitOps 배포 구조
- Kueue preemption/running Job 회수 정책

---

## ArgoCD prune 운영 안전장치 runbook

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
kubernetes/multicluster/karmada/argocd/projects/karmada-guarded-project.yaml
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

---

## 신규 member cluster label 영향 범위 점검 checklist

## 목적

Karmada에서 member cluster label은 placement의 핵심 입력이다.
새 cluster를 등록한 뒤 label을 붙이면 기존 `PropagationPolicy` 또는 `ClusterPropagationPolicy`의 `labelSelector`에 바로 매칭될 수 있다.
이 문서는 ScaleX-POD에서 신규 Tower/TwinX/EdgeX/DataX/Resource Pool 계열 cluster를 붙이기 전후에 확인할 checklist를 정리한다.

---

## 기본 원칙

```text
1. 신규 cluster를 등록한 직후에는 label을 최소화한다.
2. placement에 쓰이는 label은 한 번에 여러 개 붙이지 않는다.
3. label을 붙이기 전 기존 policy selector를 먼저 감사한다.
4. label을 붙인 직후 ResourceBinding/ClusterResourceBinding 변화량을 확인한다.
5. 예상하지 않은 binding이 생기면 즉시 label 또는 policy를 되돌린다.
```

---

## label 분류

ScaleX-POD에서는 label을 다음처럼 나눠서 다룬다.

| 분류 | 예시 | placement 영향 | 운영 기준 |
| --- | --- | --- | --- |
| 역할 label | `scalex.io/role=edge-gpu` | 큼 | 실제 workload 배치 기준이므로 사전 검토 후 부여 |
| pool label | `scalex.io/pool=gpu` | 큼 | spread/fallback 정책에 바로 매칭될 수 있음 |
| 위치 label | `scalex.io/location=edge` | 큼 | 너무 넓게 쓰면 신규 Edge cluster가 기존 edge workload에 편입됨 |
| 연결 방식 label | `scalex.io/connectivity=pull` | 중간 | Pull mode 전용 policy에 매칭됨 |
| 기능 label | `scalex.io/storage=ssd` | 중간 | DataX/스토리지 workload에 영향 가능 |
| 임시 검증 label | `scalex.io/staging=true` | 낮음 | 운영 policy가 보지 않는 key를 사용 |

권장:

```text
운영 workload placement에는 scalex.io/location=edge 단독 사용을 피한다.
role + pool + connectivity + workload tier를 조합한다.
```

예시:

```yaml
clusterAffinity:
  labelSelector:
    matchLabels:
      scalex.io/location: edge
      scalex.io/role: edge-gpu
      scalex.io/connectivity: push
```

---

## 사전 점검 1. cluster label snapshot

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusters -o wide --show-labels
```

보관할 것:

```text
cluster name
MODE Push/Pull
READY 상태
기존 label 전체
```

---

## 사전 점검 2. policy selector audit

`clusterNames`를 직접 쓰는 policy는 신규 cluster label만으로 자동 확장되지 않는다.
반대로 `labelSelector`를 쓰는 policy는 신규 cluster label에 바로 반응할 수 있다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get propagationpolicy -A -o yaml

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusterpropagationpolicy -o yaml
```

확인할 항목:

```text
spec.placement.clusterAffinity.labelSelector
spec.placement.replicaScheduling.weightPreference.staticWeightList[].targetCluster.labelSelector
```

위험도가 높은 selector 예시:

```text
scalex.io/location=edge
scalex.io/pool In gpu,general
scalex.io/pool In gpu,data,general
scalex.io/role=gpu-render
scalex.io/role=resource-pool
scalex.io/workload=data
```

---

## 사전 점검 3. 현재 binding snapshot

label 부여 전 binding 상태를 저장한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get resourcebinding -A -o wide

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusterresourcebinding -o wide
```

특정 신규 cluster만 보고 싶으면 JSON에서 `spec.clusters[].name`을 기준으로 찾는다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get resourcebinding -A -o json

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusterresourcebinding -o json
```

---

## label 부여 절차

한 번에 하나씩 붙인다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config label cluster <cluster-name> \
  scalex.io/location=edge \
  --overwrite
```

바로 확인한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get cluster <cluster-name> \
  -o wide --show-labels

kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebinding -A -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusterresourcebinding -o wide
```

30~60초 후 다시 확인한다.

```bash
sleep 30
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebinding -A -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusterresourcebinding -o wide
```

---

## 예상하지 않은 binding이 생겼을 때

### 1. label을 되돌린다

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config label cluster <cluster-name> \
  scalex.io/location-
```

### 2. binding이 빠졌는지 확인한다

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebinding -A -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusterresourcebinding -o wide
```

### 3. member cluster 실제 resource를 확인한다

```bash
kubectl --context <member-context> -n <namespace> get all
```

주의:

```text
Service/ConfigMap처럼 replica가 없는 resource는 신규 cluster에 즉시 추가 전파될 수 있다.
Deployment처럼 replica가 있는 resource는 기존 배치가 자동으로 재분산되지 않을 수 있다.
재균형이 필요하면 WorkloadRebalancer 절차를 별도로 수행한다.
```

---

## ScaleX-POD 권장 label 설계

넓은 label:

```text
scalex.io/location=edge
```

이 label 하나만으로 운영 workload를 선택하지 않는다.

더 안전한 조합:

```text
scalex.io/location=edge
scalex.io/role=edge-gpu
scalex.io/pool=gpu
scalex.io/connectivity=push 또는 pull
scalex.io/workload=edge-runtime
```

Resource Pool은 별도 label로 분리한다.

```text
scalex.io/role=resource-pool
scalex.io/pool=general
scalex.io/fallback=true
```

Pull mode cluster는 연결 방식을 명시한다.

```text
scalex.io/connectivity=pull
```

---

## 운영 승인 기준

신규 cluster label을 운영에 반영하기 전 다음 조건을 만족해야 한다.

```text
1. 신규 cluster가 어떤 policy에 매칭되는지 목록화했다.
2. 예상 ResourceBinding 변화가 명확하다.
3. 예상하지 않은 Service/Deployment/Namespace 전파가 없다.
4. 변경 전후 binding snapshot을 남겼다.
5. rollback label 제거 명령을 준비했다.
6. 필요하면 WorkloadRebalancer 계획을 준비했다.
```

---

## Kueue 관측/알림 runbook

## 목적

ScaleX-POD에서 ArgoCD, Karmada, Kueue를 함께 쓰면 다음처럼 상태 계층이 나뉜다.

```text
ArgoCD: Git desired state가 Karmada API Server에 sync됐는지 확인
Karmada: Resource가 어떤 member cluster에 전파됐는지 확인
Kueue: 선택된 member cluster 안에서 Job이 admitted/running 가능한지 확인
```

따라서 다음 상태는 정상적으로 동시에 발생할 수 있다.

```text
ArgoCD Application = Synced
Karmada ResourceBinding = FullyApplied=True
DataX Kueue ClusterQueue = pending=1 admitted=1
Job = Suspended
```

이 문서는 위 상태를 배포 실패로 오해하지 않도록, 어느 계층에서 무엇을 봐야 하는지 정리한다.

---

## 핵심 원칙

```text
1. ArgoCD Synced는 Karmada API Server에 desired state가 적용됐다는 뜻이다.
2. Karmada FullyApplied는 member cluster에 resource가 전달됐다는 뜻이다.
3. Kueue admitted는 member cluster 안에서 Job 실행 허가가 났다는 뜻이다.
4. ArgoCD Synced + Karmada FullyApplied가 Job Running/Completed를 의미하지 않는다.
5. batch/AI workload 상태 판단은 Kueue Workload/ClusterQueue/LocalQueue까지 같이 봐야 한다.
```

---

## 1. ArgoCD 계층 확인

전체 Application 상태:

```bash
kubectl --context kind-tower -n argocd get applications -o wide
```

특정 Application 상태:

```bash
kubectl --context kind-tower -n argocd get application <app-name> -o wide
kubectl --context kind-tower -n argocd describe application <app-name>
```

판단 기준:

```text
Synced + Healthy: Git/Karmada API sync 계층은 정상
Synced + Progressing: sync는 됐지만 workload가 아직 완료/정상 상태로 판단되지 않음
OutOfSync: Git desired state와 Karmada API Server 상태가 다름
Degraded: ArgoCD 관점에서 target resource health 문제
Unknown: ArgoCD가 target 상태를 정상적으로 판단하지 못함
```

주의:

```text
Kueue가 Job을 Suspended로 잡고 있어도 ArgoCD는 Synced일 수 있다.
Synced를 Job 실행 완료로 해석하지 않는다.
```

---

## 2. Karmada 계층 확인

member cluster 상태:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusters -o wide
```

namespace별 resource와 binding:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n <namespace> get job,deploy,svc,propagationpolicy,rb -o wide
```

ResourceBinding 상세:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n <namespace> describe rb <resourcebinding-name>
```

판단 기준:

```text
Cluster READY=True: Karmada가 member cluster를 정상으로 보고 있음
ResourceBinding Scheduled=True: placement 결정 완료
ResourceBinding FullyApplied=True: Work가 member cluster에 적용됨
Scheduled=False: placement/scheduler 문제
FullyApplied=False: member 적용 실패 또는 Work 적용 지연
Cluster READY=False/Unknown: member cluster 연결/agent/API 문제
```

주의:

```text
ResourceBinding FullyApplied=True여도 member cluster 내부 Kueue admission은 별도다.
FullyApplied=True + Job Suspended는 Kueue quota 대기일 수 있다.
```

---

## 3. member Kueue 계층 확인

Kueue controller:

```bash
kubectl --context kind-datax -n kueue-system get deploy,pods -o wide
kubectl --context kind-datax -n kueue-system logs deploy/kueue-controller-manager --tail=200
```

Kueue API resource 확인:

```bash
kubectl --context kind-datax api-resources | grep -i 'kueue\|clusterqueue\|localqueue\|resourceflavor\|workload'
```

Queue 상태:

```bash
kubectl --context kind-datax get resourceflavor,clusterqueue
kubectl --context kind-datax get clusterqueue -o wide
kubectl --context kind-datax get localqueue -A -o wide
```

Workload/Job 상태:

```bash
kubectl --context kind-datax -n <namespace> get workloads -o wide
kubectl --context kind-datax -n <namespace> get job,pods -o wide
kubectl --context kind-datax -n <namespace> describe workload <workload-name>
```

판단 기준:

```text
ClusterQueue PENDING WORKLOADS > 0: quota/queue 대기 발생
ClusterQueue ADMITTED WORKLOADS > 0: 실행 허가된 workload 존재
Workload ADMITTED=True: Kueue가 해당 Job 실행을 허가
Workload RESERVED IN empty: 아직 cluster queue quota를 받지 못함
Job STATUS=Suspended: Kueue가 아직 실행을 허가하지 않음
Job STATUS=Running: Kueue admission 이후 Pod 실행 중
```

---

## 4. 계층별 장애/대기 구분

| 관찰 상태 | 의미 | 우선 확인 |
| --- | --- | --- |
| ArgoCD OutOfSync | Git sync 문제 | ArgoCD Application event, repo revision, path |
| ArgoCD Synced + Karmada RB 없음 | ArgoCD가 target에 만들지 못했거나 resource selector 문제 | ArgoCD details, Karmada namespace/resource |
| Karmada RB Scheduled=False | placement 실패 | PropagationPolicy, cluster label, cluster READY |
| Karmada RB FullyApplied=False | member 적용 실패/지연 | Work, member cluster 상태 |
| Karmada RB FullyApplied=False + Kueue webhook connection refused | member Kueue controller/webhook 장애로 admission 실패 | kueue-controller-manager, Work event, webhook service endpoint |
| Karmada RB FullyApplied=True + Kueue pending>0 | 배포는 됐지만 member-local quota 대기 | ClusterQueue/LocalQueue quota, Workload status |
| Kueue controller unavailable | admission controller 장애 | kueue-system Deployment/Pod/log |
| Job Suspended + Workload not admitted | Kueue 대기 | queue quota, running workload |
| Job Running + queue pending>0 | quota가 일부 workload만 허용 | 정상 backpressure 또는 quota 부족 |

---

## 5. 알림 기준 초안

### Critical

```text
1. kueue-controller-manager available replicas = 0
2. Kueue webhook connection refused로 Karmada ResourceBinding FullyApplied=False 지속
3. Karmada member cluster READY=False/Unknown이 지속됨
3. ArgoCD Application Degraded가 지속됨
4. 운영 batch namespace에서 LocalQueue pending이 장시간 증가만 함
```

### Warning

```text
1. ClusterQueue PENDING WORKLOADS > 0 이 10분 이상 지속
2. LocalQueue PENDING WORKLOADS > 0 이 10분 이상 지속
3. ArgoCD Synced + Karmada FullyApplied=True 이지만 Job Suspended가 10분 이상 지속
4. Kueue controller restart count 증가
5. quota 감소 후 admitted workload 수가 nominalQuota보다 큰 상태가 지속됨
```

### Info

```text
1. ClusterQueue PENDING WORKLOADS > 0 이지만 ADMITTED WORKLOADS도 존재
2. batch workload가 quota에 의해 정상적으로 backpressure 중
3. ArgoCD Application Health=Progressing이고 Job이 아직 실행/완료 중
```

운영에서는 namespace, workload 중요도, SLA에 따라 시간을 조정한다.

---

## 6. 장애 대응 순서

```text
1. ArgoCD Application이 Synced인지 확인
2. Karmada API Server에 Job/Policy가 존재하는지 확인
3. ResourceBinding이 어느 cluster로 배치됐는지 확인
4. 해당 member cluster의 Kueue controller가 Running인지 확인
5. ClusterQueue/LocalQueue pending/admitted 수 확인
6. Workload가 admitted됐는지 확인
7. Job이 Suspended인지 Running인지 확인
8. quota 부족이면 quota 조정, workload 우선순위, 대기, running Job 정리 중 하나를 선택
9. quota를 늘렸다면 pending workload가 admitted로 바뀌는지 확인
10. quota를 줄였다면 이미 running 중인 Job은 즉시 내려가지 않는다는 전제로 별도 회수 절차를 선택
11. Kueue controller 장애면 controller 복구 후 Workload 재수렴 확인
12. 복구 후 Karmada FullyApplied=False가 유지되면 Job annotation 등 resource update로 Work apply 재시도 유도
13. Karmada placement 문제면 PropagationPolicy/cluster label/cluster READY를 먼저 수정
```

---

## 7. 관측 snapshot 기록 템플릿

```text
시간:
Application:
  name:
  sync:
  health:
  revision:
Karmada:
  cluster READY:
  namespace:
  ResourceBinding:
    scheduled:
    fullyApplied:
    target clusters:
Kueue member cluster:
  cluster:
  controller ready:
  ClusterQueue pending/admitted:
  LocalQueue pending/admitted:
  Workload admitted:
  Job status:
판단:
  sync 문제 / placement 문제 / member apply 문제 / Kueue quota 대기 / Kueue controller 장애
조치:
```

---

## 8. Kueue quota 변경 해석

```text
quota 증가:
  pending Workload를 admitted로 전환할 수 있는 정상적인 capacity 확장 조치다.

quota 감소:
  이미 admitted/running 중인 Job을 즉시 evict/suspend하지 않는다.
  새 admission을 제한하는 조치로 보고, running Job 회수는 별도 절차로 처리한다.
```

운영자가 함께 봐야 할 값:

```bash
kubectl --context kind-datax get clusterqueue -o wide
kubectl --context kind-datax get localqueue -A -o wide
kubectl --context kind-datax get workloads -A -o wide
kubectl --context kind-datax -n <namespace> get job,pods -o wide
```

---

## 9. Kueue controller 복구 후 재시도

controller/webhook 장애로 Karmada Work apply가 실패하면 다음 순서로 확인한다.

```text
1. kueue-controller-manager 1/1 Running 복구
2. Karmada ResourceBinding FullyApplied 상태 확인
3. FullyApplied=False가 유지되면 Work event에서 webhook 실패가 계속 남는지 확인
4. 빠른 수렴이 필요하면 Karmada API Server의 Job에 annotation update를 주어 재시도 유도
```

예시:

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)

kubectl --kubeconfig ~/.kube/karmada-apiserver.config   -n <namespace> annotate job <job-name>   scalex.io/retry-at="$stamp" --overwrite
```

---

## 10. ScaleX-POD 권장 구조

```text
1. Tower ArgoCD dashboard만 보고 batch 상태를 끝내지 않는다.
2. Karmada ResourceBinding dashboard와 Kueue queue dashboard를 함께 둔다.
3. DataX/TwinX batch namespace별 LocalQueue pending/admitted를 기본 지표로 둔다.
4. Kueue pending은 항상 장애가 아니라 quota backpressure일 수 있음을 알림 메시지에 명시한다.
5. 운영 Job의 완료/지연 판단은 member cluster의 Kueue Workload와 Job 상태 기준으로 한다.
```
