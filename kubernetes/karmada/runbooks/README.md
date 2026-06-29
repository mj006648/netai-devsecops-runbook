# Karmada 운영 Runbook

이 디렉터리는 Karmada 실험 결과를 실제 ScaleX-POD 운영 절차로 바꾸기 위한 runbook 공간이다.

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

## 다음 정리 대상

- OverridePolicy image/storageClass
- scheduler-estimator
- ArgoCD -> Karmada API Server GitOps 흐름
