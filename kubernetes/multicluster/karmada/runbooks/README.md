# Karmada 운영 Runbook

이 디렉터리는 Karmada 실험 결과를 실제 ScaleX-POD 운영 절차로 바꾸기 위한 runbook 공간이다.

전체 운영 모델은 [`../notes/scalex-pod-operating-model.md`](../notes/scalex-pod-operating-model.md)를 기준으로 한다.

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

- [`../experiments/2026-06-26-08-noexecute-eviction.md`](../experiments/2026-06-26-08-noexecute-eviction.md)
- [`../experiments/2026-06-26-10-noexecute-toleration-scope.md`](../experiments/2026-06-26-10-noexecute-toleration-scope.md)

### 복구 후 재균형

```text
1. 대상 cluster 복구 확인
2. NoExecute taint 제거
3. 재균형 대상 workload 목록 작성
4. WorkloadRebalancer 생성
5. WorkloadRebalancer status와 ResourceBinding 확인
```

관련 실험:

- [`../experiments/2026-06-26-09-workload-rebalancer-reschedule.md`](../experiments/2026-06-26-09-workload-rebalancer-reschedule.md)
- [`../experiments/2026-06-26-11-multi-workload-rebalancer.md`](../experiments/2026-06-26-11-multi-workload-rebalancer.md)

### Pull mode cluster 포함 재균형

```text
1. 신규 Pull mode cluster가 placement selector에 매칭되는지 확인
2. ResourceBinding에서 기존 replica skew 확인
3. WorkloadRebalancer 생성
4. ResourceBinding이 Push/Pull cluster를 모두 포함하도록 재계산됐는지 확인
5. Push/Pull member cluster의 실제 Deployment/Pod 상태 확인
```

관련 실험:

- [`../experiments/2026-06-29-23-pull-mode-workload-rebalancer.md`](../experiments/2026-06-29-23-pull-mode-workload-rebalancer.md)

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

- [`new-cluster-label-impact-checklist.md`](./new-cluster-label-impact-checklist.md)
- [`../experiments/2026-06-29-22-new-cluster-label-impact.md`](../experiments/2026-06-29-22-new-cluster-label-impact.md)

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

- [`../experiments/2026-07-07-33-scalex-repo-split-poc.md`](../experiments/2026-07-07-33-scalex-repo-split-poc.md)

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

- [`argocd-prune-safety.md`](./argocd-prune-safety.md)
- [`../argocd/projects/karmada-guarded-project.yaml`](../argocd/projects/karmada-guarded-project.yaml)
- [`../experiments/2026-06-29-25-argocd-prune-safety.md`](../experiments/2026-06-29-25-argocd-prune-safety.md)

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

- [`kueue-observability.md`](./kueue-observability.md)
- [`../experiments/2026-06-29-27-kueue-datax-basic.md`](../experiments/2026-06-29-27-kueue-datax-basic.md)
- [`../experiments/2026-06-29-28-argocd-karmada-kueue.md`](../experiments/2026-06-29-28-argocd-karmada-kueue.md)
- [`../experiments/2026-06-29-29-kueue-observability.md`](../experiments/2026-06-29-29-kueue-observability.md)
- [`../experiments/2026-06-30-30-kueue-controller-recovery.md`](../experiments/2026-06-30-30-kueue-controller-recovery.md)
- [`../experiments/2026-06-30-31-kueue-quota-change.md`](../experiments/2026-06-30-31-kueue-quota-change.md)

### Pull mode 네트워크 단절/복구

```text
1. Pull mode cluster와 agent 상태 확인
2. 네트워크 차단 지점이 node OUTPUT인지 Pod egress/FORWARD인지 구분
3. 차단 중 Cluster READY, agent log, member workload 유지 여부 확인
4. 차단 중 desired state 변경이 member에 반영되지 않는지 확인
5. 복구 후 agent 재시작, Work sync, status reflect까지 확인
```

관련 실험:

- [`../experiments/2026-06-29-26-pull-mode-network-partition.md`](../experiments/2026-06-29-26-pull-mode-network-partition.md)

## 다음 정리 대상

- OverridePolicy image/storageClass
- scheduler-estimator 운영 적용 절차
- ArgoCD -> Karmada API Server GitOps 흐름
- 실제 tower-k8s/scalex-k8s/twinx-k8s/datax-k8s/edgex-k8s repo 생성 및 bootstrap
- 실제 ScaleX-POD 이전 checklist
- Kueue GitOps 배포 구조
- Kueue preemption/running Job 회수 정책
