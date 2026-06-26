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

## 다음 정리 대상

- ScaleX-POD role label placement
- OverridePolicy image/storageClass
- scheduler-estimator
- ArgoCD -> Karmada API Server GitOps 흐름
- Pull mode
