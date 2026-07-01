# Karmada 실험 진행표

이 디렉터리는 MiniX/kind Lab에서 Karmada 기능을 하나씩 검증하고, ScaleX-POD 설계에 필요한 근거를 남기는 공간이다.

## 실험 원칙

각 실험은 다음을 반드시 기록한다.

- 목적
- 가설
- 실행 명령
- 기대 결과
- 실제 결과
- 성공/실패 판단
- 문제/에러
- ScaleX-POD에 주는 의미
- 다음 액션

---

## 진행된 실험

| 번호 | 문서 | 주제 | 상태 | 핵심 결과 |
| --- | --- | --- | --- | --- |
| 00 | [`2026-06-25-00-kind-lab-plan.md`](./2026-06-25-00-kind-lab-plan.md) | kind 기반 Karmada Lab 구성 | 성공 | `tower/twinx/edgex/datax` 구성, Karmada Push 등록, demo-nginx 1:1:1 전파 성공 |
| 01 | [`2026-06-25-01-cluster-affinity-twinx-only.md`](./2026-06-25-01-cluster-affinity-twinx-only.md) | labelSelector로 twinx-only 배치 | 부분 성공 | Deployment/Service/Pod는 twinx에만 배치, namespace는 다른 member에도 생성됨 |
| 02 | [`2026-06-25-02-namespace-auto-propagation.md`](./2026-06-25-02-namespace-auto-propagation.md) | namespace 자동 생성 동작 확인 | 관찰 완료 | Namespace 정책 없이도 workload namespace가 모든 member에 자동 생성되는 현상 확인 |
| 03 | [`2026-06-25-03-weighted-replica-scheduling.md`](./2026-06-25-03-weighted-replica-scheduling.md) | weighted replica 분산 | 성공 | replicas=6, weight 4:1:1을 twinx=4/edgex=1/datax=1로 분산 |
| 04 | [`2026-06-25-04-override-policy-env.md`](./2026-06-25-04-override-policy-env.md) | OverridePolicy env 변경 | 성공 | 같은 Deployment를 twinx/edgex/datax에 배포하면서 cluster별 env를 다르게 적용 |
| 05 | [`2026-06-25-05-cluster-taint-failover.md`](./2026-06-25-05-cluster-taint-failover.md) | cluster taint/toleration/failover | 부분 성공 | 새 workload는 taint된 twinx를 회피, toleration workload는 twinx 허용, 기존 workload 자동 eviction은 미확인 |
| 06 | [`2026-06-25-06-actual-cluster-failover.md`](./2026-06-25-06-actual-cluster-failover.md) | 실제 member cluster 장애 | 부분 성공 | twinx 장애 감지/복구는 성공, 기존 workload 자동 failover는 현재 controller 옵션에서 미확인 |
| 07 | [`2026-06-26-07-failover-feature-gate.md`](./2026-06-26-07-failover-feature-gate.md) | Failover feature gate 재실험 | 부분 성공 | 옵션 활성화 후에도 실제 장애 자동 taint는 NoSchedule, 기존 workload 자동 이동은 미확인 |
| 08 | [`2026-06-26-08-noexecute-eviction.md`](./2026-06-26-08-noexecute-eviction.md) | 수동 NoExecute taint eviction | 성공/주의 필요 | NoExecute taint는 기존 twinx workload를 edgex/datax로 이동시킴, taint 제거 후 자동 재균형은 없음 |
| 09 | [`2026-06-26-09-workload-rebalancer-reschedule.md`](./2026-06-26-09-workload-rebalancer-reschedule.md) | WorkloadRebalancer 재균형 | 성공 | NoExecute 후 edgex/datax에 남은 workload를 twinx/edgex/datax=1:1:1로 재균형 |
| 10 | [`2026-06-26-10-noexecute-toleration-scope.md`](./2026-06-26-10-noexecute-toleration-scope.md) | NoExecute 영향 범위와 toleration | 성공/주의 필요 | toleration 없는 workload는 이동, matching toleration 있는 workload는 twinx 유지 |
| 11 | [`2026-06-26-11-multi-workload-rebalancer.md`](./2026-06-26-11-multi-workload-rebalancer.md) | 여러 workload batch 재균형 | 성공 | 하나의 WorkloadRebalancer로 세 Deployment를 모두 twinx/edgex/datax=1:1:1로 재균형 |
| 12 | [`2026-06-26-12-scalex-role-label-placement.md`](./2026-06-26-12-scalex-role-label-placement.md) | ScaleX-POD role label placement | 성공 | role/pool/location/workload label로 render=twinx3+edgex1, edge=edgex2, data=datax2 배치 |
| 13 | [`2026-06-26-13-resource-pool-placement.md`](./2026-06-26-13-resource-pool-placement.md) | Resource Pool placement | 성공 | poolx를 Karmada member로 추가하고 general=poolx2, render fallback=twinx3+edgex1+poolx1 배치 |
| 14 | [`2026-06-26-14-override-image-storageclass.md`](./2026-06-26-14-override-image-storageclass.md) | OverridePolicy image/storageClass | 성공 | cluster별 image tag와 PVC storageClassName을 다르게 override하고 모든 PVC Bound 확인 |
| 15 | [`2026-06-26-15-resource-pool-rebalance.md`](./2026-06-26-15-resource-pool-rebalance.md) | Resource Pool fallback 재균형 | 성공 | poolx=5 fallback skew를 WorkloadRebalancer로 twinx=3, edgex=1, poolx=1로 복구 |
| 16 | [`2026-06-27-16-scheduler-estimator.md`](./2026-06-27-16-scheduler-estimator.md) | scheduler-estimator 상태 정리 | 성공/설정 변경 | estimator 서비스 부재와 dial 실패 로그 확인, lab에서는 estimator 비활성화 후 weighted scheduling 정상 확인 |
| 17 | [`2026-06-27-17-spread-constraints.md`](./2026-06-27-17-spread-constraints.md) | spreadConstraints pool group 분산 | 성공/주의 필요 | `scalex.io/pool` 기준 spread 배치 성공, labelSelector weight는 매칭 cluster별 weight처럼 동작하고 minGroups hard fail은 미확인 |
| 18 | [`2026-06-27-18-argocd-to-karmada.md`](./2026-06-27-18-argocd-to-karmada.md) | ArgoCD -> Karmada API Server GitOps | 성공 | ArgoCD가 Karmada API Server를 destination으로 sync하고 self-heal로 replicas drift를 7에서 8로 복구 |
| 19 | [`2026-06-29-19-argocd-prune-rollback.md`](./2026-06-29-19-argocd-prune-rollback.md) | ArgoCD prune/delete/restore | 성공 | live Service 삭제 self-heal, Git Service 제거 prune, Git Service 복구 restore가 Karmada/member cluster까지 반영됨 |
| 20 | [`2026-06-29-20-pull-mode-member.md`](./2026-06-29-20-pull-mode-member.md) | Pull mode member cluster | 성공/주의 필요 | `pullx`를 Pull mode로 등록하고 agent 기반 workload 전파 성공, namespace 자동 생성과 broad label 매칭 주의점 확인 |
| 21 | [`2026-06-29-21-pull-mode-agent-recovery.md`](./2026-06-29-21-pull-mode-agent-recovery.md) | Pull mode agent 장애/복구 | 성공/주의 필요 | agent 중단 시 `pullx READY=Unknown`, 기존 workload 유지, 복구 후 밀린 replicas 변경 반영, status stale 주의점 확인 |
| 22 | [`2026-06-29-22-new-cluster-label-impact.md`](./2026-06-29-22-new-cluster-label-impact.md) | 신규 cluster label 영향 범위 | 성공/주의 필요 | `pullx` label이 기존 edge Service에 추가 매칭되는 현상을 정리하고 label 부여 전후 checklist 작성 |
| 23 | [`2026-06-29-23-pull-mode-workload-rebalancer.md`](./2026-06-29-23-pull-mode-workload-rebalancer.md) | Pull mode + WorkloadRebalancer | 성공 | 기존 edge Deployment를 `edgex=2`에서 `edgex=1,pullx=1`로 재균형, Push/Pull 혼합 재균형 확인 |
| 24 | [`2026-06-29-24-argocd-applicationset.md`](./2026-06-29-24-argocd-applicationset.md) | ArgoCD ApplicationSet -> Karmada | 성공/주의 필요 | ApplicationSet이 Karmada용 Application 2개를 생성하고 edge는 `edgex=1,pullx=1`, data는 `datax=2`로 전파됨 |
| 25 | [`2026-06-29-25-argocd-prune-safety.md`](./2026-06-29-25-argocd-prune-safety.md) | ArgoCD prune 운영 안전장치 | 성공 | prune 위험 모델, runbook, `karmada-guarded` AppProject 샘플을 정리하고 live ArgoCD 적용까지 확인 |
| 26 | [`2026-06-29-26-pull-mode-network-partition.md`](./2026-06-29-26-pull-mode-network-partition.md) | Pull mode 네트워크 단절/복구 | 성공/주의 필요 | agent Pod egress FORWARD 차단으로 `pullx READY=Unknown`, 기존 workload 유지, 복구 후 재수렴을 확인 |
| 27 | [`2026-06-29-27-kueue-datax-basic.md`](./2026-06-29-27-kueue-datax-basic.md) | Karmada + Kueue DataX Job admission | 성공/주의 필요 | Karmada가 Job을 datax로 전파하고, datax Kueue가 cpu=1 quota로 1개 admitted/1개 pending을 제어함 |
| 28 | [`2026-06-29-28-argocd-karmada-kueue.md`](./2026-06-29-28-argocd-karmada-kueue.md) | ArgoCD -> Karmada -> DataX -> Kueue | 성공/주의 필요 | ArgoCD sync, Karmada 전파, datax Kueue admission, self-heal 후 재입장까지 end-to-end 확인 |
| 29 | [`2026-06-29-29-kueue-observability.md`](./2026-06-29-29-kueue-observability.md) | Kueue 관측/알림 runbook | 성공 | ArgoCD/Karmada/Kueue 계층별 관측 명령과 pending/admitted 알림 기준 초안 작성 |
| 30 | [`2026-06-30-30-kueue-controller-recovery.md`](./2026-06-30-30-kueue-controller-recovery.md) | Kueue controller 장애/복구 | 성공/주의 필요 | controller/webhook 중단 시 Karmada FullyApplied=False, 복구 후 resource update로 빠른 재시도 수렴 확인 |
| 31 | [`2026-06-30-31-kueue-quota-change.md`](./2026-06-30-31-kueue-quota-change.md) | Kueue quota 변경 | 성공/주의 필요 | quota 증가는 pending Job을 admitted로 전환, quota 감소는 이미 running Job을 즉시 evict/suspend하지 않음 |
| 32 | [`2026-07-01-32-scheduler-estimator-install.md`](./2026-07-01-32-scheduler-estimator-install.md) | scheduler-estimator 설치형 실험 | 성공/주의 필요 | Push member별 estimator addon 설치, scheduler 연결, Aggregated scheduling 성공, kind 단일 노드 rollout 이슈 확인 후 원복 |

---

## 전체 리뷰

- [실험 coverage review](../notes/experiment-coverage-review.md)
- [ScaleX-POD 멀티클러스터 운영 모델](../notes/scalex-pod-operating-model.md)

---

## 실험 정리 판단

```text
ScaleX-POD 설계 판단에 필요한 핵심 기능 검증은 00~32에서 완료됐다.
아래 항목은 필수 검증이 아니라 운영 고도화 또는 실제 이전 준비 작업이다.
```

## 다음 실험 후보

| 우선순위 | 주제 | ScaleX-POD에서 의미 |
| --- | --- | --- |
| 1 | Kueue GitOps 배포 구조 | Kueue 설치/queue를 ArgoCD로 member cluster에 관리할지 검토 |
| 2 | ArgoCD AppProject migration | 기존 Application을 `default`에서 목적별 AppProject로 옮기는 절차 검증 |
| 3 | Kueue preemption/running Job 회수 | quota 감소만으로 running Job이 내려가지 않으므로 회수 정책 검토 |
| 4 | 실제 ScaleX-POD migration checklist | kind lab 결과를 실제 Tower/TwinX/EdgeX/DataX 이전 절차로 변환 |
| 5 | scheduler-estimator 운영 적용 판단 | 설치형 실험은 끝났고, 실제 capacity-aware scheduling 필요 시 운영화 여부 결정 |

---

## 현재 우선순위

```text
1. Kueue GitOps 배포 구조 검토
2. ArgoCD AppProject migration 실험
3. Kueue preemption/running Job 회수 정책 검토
4. 실제 ScaleX-POD migration checklist 작성
5. scheduler-estimator 운영 적용 여부 결정
```
