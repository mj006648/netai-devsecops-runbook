# 실험 15. Resource Pool fallback 후 WorkloadRebalancer 재균형

## 목적

실험 13에서는 `poolx`를 Resource Pool member cluster로 추가하고, render fallback workload를 `twinx=3`, `edgex=1`, `poolx=1`로 배치했다.
실험 09와 11에서는 `WorkloadRebalancer`로 skew 상태의 workload를 policy 기준으로 재균형할 수 있음을 확인했다.

이번 실험은 두 흐름을 합쳐서, ScaleX-POD의 fallback pool에 몰린 workload를 다시 정상 placement weight 기준으로 복구할 수 있는지 확인한다.

ScaleX-POD 기준 의미:

```text
TwinX/EdgeX 쪽 장애, 점검, 일시적 우회 운영으로 render workload가 Resource Pool에 몰린 뒤,
복구 시 WorkloadRebalancer로 TwinX/EdgeX/Resource Pool의 원래 비율까지 되돌리는 절차를 검증한다.
```

---

## 가설

```text
Resource Pool fallback workload가 poolx=5로 몰려 있어도,
WorkloadRebalancer를 실행하면 기존 PropagationPolicy의 label/weight 기준을 다시 평가해서
원래 목표인 twinx=3, edgex=1, poolx=1로 재균형될 것이다.
```

---

## 사전 상태

member cluster:

```text
- twinx READY=True, scalex.io/role=gpu-render, scalex.io/pool=gpu
- edgex READY=True, scalex.io/role=edge-gpu, scalex.io/pool=gpu
- datax READY=True, scalex.io/role=data
- poolx READY=True, scalex.io/role=resource-pool, scalex.io/pool=general
```

Karmada member mode:

```text
전부 Push mode
```

---

## 매니페스트

```text
kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/
  00-namespace.yaml
  10-deployment.yaml
  20-service.yaml
  30-propagation-policy.yaml
  40-workload-rebalancer.yaml
```

workload:

```text
namespace : demo-resource-pool-rebalance
Deployment: demo-pool-fallback-rebalance-nginx
Service   : demo-pool-fallback-rebalance-nginx
replicas  : 5
```

placement:

```text
후보 cluster:
- scalex.io/pool in (gpu, general)

weight:
- scalex.io/role=gpu-render    -> 3
- scalex.io/role=edge-gpu      -> 1
- scalex.io/role=resource-pool -> 1

기대 결과:
- twinx=3
- edgex=1
- poolx=1
- datax=0
```

---

## PropagationPolicy 핵심

```yaml
placement:
  clusterAffinity:
    labelSelector:
      matchExpressions:
        - key: scalex.io/pool
          operator: In
          values:
            - gpu
            - general
  replicaScheduling:
    replicaSchedulingType: Divided
    replicaDivisionPreference: Weighted
    weightPreference:
      staticWeightList:
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/role: gpu-render
          weight: 3
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/role: edge-gpu
          weight: 1
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/role: resource-pool
          weight: 1
```

---

## WorkloadRebalancer 핵심

```yaml
apiVersion: apps.karmada.io/v1alpha1
kind: WorkloadRebalancer
metadata:
  name: demo-pool-fallback-rebalance-run
spec:
  workloads:
    - apiVersion: apps/v1
      kind: Deployment
      namespace: demo-resource-pool-rebalance
      name: demo-pool-fallback-rebalance-nginx
```

주의:

```text
ttlSecondsAfterFinished를 넣지 않았다.
그래서 실험 후 status를 계속 확인할 수 있다.
같은 이름으로 반복 실행하려면 기존 WorkloadRebalancer를 삭제하거나 새 이름을 사용한다.
```

---

## 실행 명령

client dry-run:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=client \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/
```

baseline 적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/00-namespace.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/10-deployment.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/20-service.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/30-propagation-policy.yaml
```

lab-only fallback skew 생성:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config patch rb \
  -n demo-resource-pool-rebalance demo-pool-fallback-rebalance-nginx-deployment \
  --type=merge \
  -p '{"spec":{"clusters":[{"name":"poolx","replicas":5}]}}'
```

주의:

```text
ResourceBinding 직접 patch는 운영 절차가 아니라 실험용 skew 생성 방법이다.
실제 운영에서는 장애, NoExecute taint, 정책 변경, 수동 우회 운영 등으로 비슷한 skew가 생길 수 있다.
```

WorkloadRebalancer 적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-resource-pool-rebalance/40-workload-rebalancer.yaml
```

---

## 확인 명령

ResourceBinding:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb \
  -n demo-resource-pool-rebalance demo-pool-fallback-rebalance-nginx-deployment \
  -o jsonpath='{range .spec.clusters[*]}{.name}{" replicas="}{.replicas}{"\n"}{end}{"lastScheduledTime="}{.status.lastScheduledTime}{"\n"}{"schedulerObservedGeneration="}{.status.schedulerObservedGeneration}{"\n"}{"gracefulEvictionTasks="}{.spec.gracefulEvictionTasks}{"\n"}'
```

WorkloadRebalancer:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get workloadrebalancer \
  demo-pool-fallback-rebalance-run \
  -o jsonpath='{.status.finishTime}{" observed="}{.status.observedGeneration}{" results="}{range .status.observedWorkloads[*]}{.workload.name}{":"}{.result}{" reason="}{.reason}{" "}{end}{"\n"}'
```

member cluster:

```bash
for c in twinx edgex poolx datax; do
  echo "--- $c"
  kubectl --context kind-$c -n demo-resource-pool-rebalance get deploy,pods -o wide
done
```

---

## 기대 결과

| 단계 | 기대 결과 |
| --- | --- |
| baseline | `twinx=3`, `edgex=1`, `poolx=1` |
| lab-only fallback skew | `poolx=5`, `twinx=0`, `edgex=0` |
| WorkloadRebalancer | `Successful` |
| 재균형 | `twinx=3`, `edgex=1`, `poolx=1` |
| datax | 후보 label에 없으므로 배치되지 않음 |

---

## 실제 결과

### 1. dry-run

결과:

```text
namespace/demo-resource-pool-rebalance created (dry run)
deployment.apps/demo-pool-fallback-rebalance-nginx created (dry run)
service/demo-pool-fallback-rebalance-nginx created (dry run)
propagationpolicy.policy.karmada.io/demo-pool-fallback-rebalance-policy created (dry run)
workloadrebalancer.apps.karmada.io/demo-pool-fallback-rebalance-run created (dry run)
```

판단:

```text
매니페스트 schema 문제 없음.
```

### 2. baseline 적용

적용 시각:

```text
2026-06-26T05:32:21Z
```

적용 결과:

```text
namespace/demo-resource-pool-rebalance created
deployment.apps/demo-pool-fallback-rebalance-nginx created
service/demo-pool-fallback-rebalance-nginx created
propagationpolicy.policy.karmada.io/demo-pool-fallback-rebalance-policy created
```

ResourceBinding:

```text
edgex replicas=1
poolx replicas=1
twinx replicas=3
lastScheduledTime=2026-06-26T05:32:21Z
schedulerObservedGeneration=2
```

member cluster:

```text
twinx: Deployment 3/3, Pod Running 3개
edgex: Deployment 1/1, Pod Running 1개
poolx: Deployment 1/1, Pod Running 1개
datax: No resources found
```

판단:

```text
baseline placement는 기대한 twinx=3, edgex=1, poolx=1과 일치한다.
```

### 3. lab-only fallback skew 생성

실행 결과:

```text
resourcebinding.work.karmada.io/demo-pool-fallback-rebalance-nginx-deployment patched
```

ResourceBinding:

```text
poolx replicas=5
lastScheduledTime=2026-06-26T05:32:21Z
schedulerObservedGeneration=3
gracefulEvictionTasks=
```

member cluster:

```text
twinx: No resources found
edgex: No resources found
poolx: Deployment 5/5, Pod Running 5개
datax: No resources found
```

판단:

```text
Resource Pool fallback 상태를 의도적으로 만들 수 있었다.
이 상태는 운영 절차가 아니라 WorkloadRebalancer 검증용 skew 상태다.
```

### 4. WorkloadRebalancer 적용

적용 시각:

```text
2026-06-26T05:38:39Z
```

적용 결과:

```text
workloadrebalancer.apps.karmada.io/demo-pool-fallback-rebalance-run created
```

상태:

```text
2026-06-26T05:38:39Z observed=1 results=demo-pool-fallback-rebalance-nginx:Successful reason=
```

ResourceBinding:

```text
edgex replicas=1
poolx replicas=1
twinx replicas=3
lastScheduledTime=2026-06-26T05:38:39Z
schedulerObservedGeneration=5
gracefulEvictionTasks=
```

`rescheduleTriggeredAt`도 WorkloadRebalancer 실행 시각으로 기록되었다.

```text
rescheduleTriggeredAt=2026-06-26T05:38:39Z
```

member cluster:

```text
twinx: Deployment 3/3, Pod Running 3개
edgex: Deployment 1/1, Pod Running 1개
poolx: Deployment 1/1, Pod Running 1개
datax: No resources found
```

판단:

```text
poolx=5 fallback 상태에서 WorkloadRebalancer 실행 후 원래 weight 기준인 twinx=3, edgex=1, poolx=1로 복구됐다.
```

---

## 성공/실패 판단

```text
성공
```

성공 근거:

```text
1. baseline placement가 twinx=3, edgex=1, poolx=1로 배치됐다.
2. lab-only patch로 poolx=5 fallback skew를 만들었다.
3. WorkloadRebalancer가 Successful 상태가 됐다.
4. ResourceBinding.lastScheduledTime과 rescheduleTriggeredAt이 WorkloadRebalancer 실행 시각으로 갱신됐다.
5. 최종 배치가 다시 twinx=3, edgex=1, poolx=1로 돌아왔다.
```

---

## 문제/에러

이번 실험에서 기능 실패는 없었다.

주의할 점:

```text
ResourceBinding 직접 patch는 실험용이다.
운영에서는 fallback 상태를 만드는 원인을 명확히 해야 한다.
```

이전 실험과 연결되는 운영상 주의:

```text
실제 member cluster down에서 Karmada가 자동으로 붙인 taint는 NoSchedule이었다.
기존 workload 자동 이동은 확인되지 않았다.
기존 workload를 강제로 이동하려면 NoExecute taint 또는 별도 운영 절차가 필요했다.
```

따라서 Resource Pool fallback 운영을 만들려면 다음 중 하나를 선택해야 한다.

```text
1. 장애/점검 시 NoExecute 기반 eviction runbook 사용
2. 운영자가 policy/RB 상태를 바꾼 뒤 WorkloadRebalancer로 복구
3. Karmada failover/eviction 설정을 더 깊게 검증
4. ArgoCD와 결합해 선언형 정책 변경으로 fallback/복구 절차 관리
```

---

## ScaleX-POD에 주는 의미

이번 실험으로 확인한 운영 패턴:

```text
정상 상태:
  render workload -> TwinX 중심 + EdgeX/Resource Pool 일부 분산

우회 상태:
  render workload -> Resource Pool에 집중

복구 상태:
  WorkloadRebalancer -> 원래 placement weight 기준으로 재균형
```

ScaleX-POD 설계에 반영할 수 있는 점:

```text
1. Resource Pool은 단순 spare cluster가 아니라 fallback workload 수용 지점으로 쓸 수 있다.
2. fallback 후 자동 복귀가 항상 일어나는 것은 아니므로 WorkloadRebalancer runbook이 필요하다.
3. workload별 정상 weight를 PropagationPolicy에 명확히 남겨야 복구 시 기준점이 생긴다.
4. ArgoCD를 붙이면 fallback/restore 정책 변경과 WorkloadRebalancer 실행 매니페스트를 Git으로 추적할 수 있다.
```

---

## 다음 액션

우선순위 후보:

```text
1. scheduler-estimator 로그/필요성 정리
2. spreadConstraints로 role/zone/provider 분산 배치 검증
3. ArgoCD -> Karmada API Server GitOps 실험
4. Pull mode member cluster 등록 실험
5. Kueue와 Karmada 역할 분리 실험
```
