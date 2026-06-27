# 실험 17. spreadConstraints로 pool group 분산 배치

## 목적

지금까지 실험은 주로 `clusterAffinity`, role label, weighted replica scheduling으로 특정 cluster 또는 cluster set에 workload를 배치했다.
이번 실험은 Karmada `spreadConstraints`를 사용해 cluster를 label group으로 묶고, workload가 여러 group에 걸쳐 배치되는지 확인한다.

ScaleX-POD 기준 의미:

```text
TwinX / EdgeX / DataX / Resource Pool이 늘어나면 단순 cluster name이나 role weight만으로는 운영이 어려워진다.
cluster를 pool, zone, provider, role group으로 묶고, workload를 group 간에 분산하는 정책이 필요하다.
```

---

## 가설

```text
Cluster label `scalex.io/pool`을 기준으로 spreadConstraints를 설정하면,
Karmada는 gpu/data/general group을 모두 고려해 workload를 분산할 것이다.
```

---

## 사전 상태

Karmada scheduler-estimator는 실험 16에서 비활성화했다.

```text
karmada-scheduler: --enable-scheduler-estimator=false
```

기존 cluster label:

```text
twinx: scalex.io/pool=gpu, scalex.io/role=gpu-render
edgex: scalex.io/pool=gpu, scalex.io/role=edge-gpu
poolx: scalex.io/pool=general, scalex.io/role=resource-pool
datax: scalex.io/role=data, scalex.io/storage=ssd, scalex.io/workload=data
```

이번 실험에서 `datax`도 pool group에 포함하기 위해 label을 추가했다.

실행 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config label cluster datax \
  scalex.io/pool=data \
  --overwrite
```

결과:

```text
cluster.cluster.karmada.io/datax labeled
```

최종 pool group:

```text
gpu     : twinx, edgex
data    : datax
general : poolx
```

최종 cluster label:

```text
datax: scalex.io/pool=data, scalex.io/role=data, scalex.io/storage=ssd, scalex.io/workload=data
edgex: scalex.io/location=edge, scalex.io/pool=gpu, scalex.io/role=edge-gpu
poolx: scalex.io/fallback=true, scalex.io/pool=general, scalex.io/role=resource-pool, scalex.io/workload=general
twinx: scalex.io/pool=gpu, scalex.io/role=gpu-render
```

---

## API 확인

확인 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config explain \
  propagationpolicy.spec.placement.spreadConstraints \
  --api-version=policy.karmada.io/v1alpha1
```

핵심 필드:

```text
spreadByField:
- cluster
- region
- zone
- provider

spreadByLabel:
- label key로 cluster group 생성

minGroups:
- 선택할 최소 group 수

maxGroups:
- 선택할 최대 group 수
```

주의:

```text
spreadByField와 spreadByLabel은 같이 쓰면 안 된다.
둘 다 비어 있으면 기본값은 spreadByField=cluster다.
```

---

## 매니페스트

```text
kubernetes/karmada/manifests/demo-spread-constraints/
  00-namespace.yaml
  10-pool-spread-deployment.yaml
  20-pool-spread-service.yaml
  30-pool-spread-propagation-policy.yaml
```

workload:

```text
namespace : demo-spread-constraints
Deployment: demo-spread-pool-nginx
Service   : demo-spread-pool-nginx
replicas  : 8
requests  : cpu=10m, memory=32Mi
```

placement:

```text
clusterAffinity:
- scalex.io/pool in (gpu, data, general)

spreadConstraints:
- spreadByLabel: scalex.io/pool
- minGroups: 3
- maxGroups: 3

replicaScheduling:
- Divided + Weighted
- gpu weight=2
- data weight=1
- general weight=1
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
            - data
            - general
  spreadConstraints:
    - spreadByLabel: scalex.io/pool
      minGroups: 3
      maxGroups: 3
  replicaScheduling:
    replicaSchedulingType: Divided
    replicaDivisionPreference: Weighted
    weightPreference:
      staticWeightList:
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/pool: gpu
          weight: 2
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/pool: data
          weight: 1
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/pool: general
          weight: 1
```

---

## 실행 명령

client dry-run:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=client \
  -f kubernetes/karmada/manifests/demo-spread-constraints/
```

결과:

```text
namespace/demo-spread-constraints created (dry run)
deployment.apps/demo-spread-pool-nginx created (dry run)
service/demo-spread-pool-nginx created (dry run)
propagationpolicy.policy.karmada.io/demo-spread-pool-policy created (dry run)
```

적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-spread-constraints/
```

적용 시각:

```text
2026-06-27T07:19:18Z
```

결과:

```text
namespace/demo-spread-constraints created
deployment.apps/demo-spread-pool-nginx created
service/demo-spread-pool-nginx created
propagationpolicy.policy.karmada.io/demo-spread-pool-policy created
```

---

## 확인 명령

ResourceBinding:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb \
  -n demo-spread-constraints demo-spread-pool-nginx-deployment \
  -o jsonpath='{range .spec.clusters[*]}{.name}{" replicas="}{.replicas}{"\n"}{end}{"lastScheduledTime="}{.status.lastScheduledTime}{"\n"}{"schedulerObservedGeneration="}{.status.schedulerObservedGeneration}{"\n"}{"conditions="}{range .status.conditions[*]}{.type}{":"}{.status}{"/"}{.reason}{" "}{end}{"\n"}'
```

member cluster:

```bash
for c in twinx edgex datax poolx; do
  echo "--- $c"
  kubectl --context kind-$c -n demo-spread-constraints get deploy,pods -o wide
done
```

scheduler log:

```bash
kubectl --context kind-tower -n karmada-system logs deploy/karmada-scheduler --since=2m \
  | grep -Ei 'demo-spread|spread|ScheduleBindingSucceed|failed|error'
```

---

## 실제 결과

### 1. ResourceBinding

```text
datax replicas=1
edgex replicas=3
poolx replicas=1
twinx replicas=3
lastScheduledTime=2026-06-27T07:19:19Z
schedulerObservedGeneration=2
conditions=Scheduled:True/Success FullyApplied:True/FullyAppliedSuccess
```

### 2. member cluster

```text
twinx: Deployment 3/3, Pod Running 3개
edgex: Deployment 3/3, Pod Running 3개
datax: Deployment 1/1, Pod Running 1개
poolx: Deployment 1/1, Pod Running 1개
```

최종 확인:

```text
twinx: ready=3/3 image=nginx:1.27-alpine
edgex: ready=3/3 image=nginx:1.27-alpine
datax: ready=1/1 image=nginx:1.27-alpine
poolx: ready=1/1 image=nginx:1.27-alpine
```

### 3. scheduler log

```text
Binding has been scheduled successfully. Result: {datax:1, edgex:3, poolx:1, twinx:3}
```

---

## 관찰: weight labelSelector 해석

처음 기대했던 group 비율은 다음처럼 생각할 수 있었다.

```text
gpu group weight=2
data group weight=1
general group weight=1
replicas=8

단순 group aggregate로 보면:
- gpu group 전체 = 4
- data group = 2
- general group = 2
```

하지만 실제 결과는 다음이었다.

```text
twinx=3
edgex=3
datax=1
poolx=1
```

해석:

```text
weightPreference.staticWeightList에서 labelSelector가 여러 cluster를 매칭하면,
weight는 group 전체에 한 번 적용되는 것이 아니라 매칭된 각 cluster에 적용되는 것으로 보인다.
```

이번 실험에서는 다음처럼 해석할 수 있다.

```text
twinx: pool=gpu     -> weight 2
edgex: pool=gpu     -> weight 2
datax: pool=data    -> weight 1
poolx: pool=general -> weight 1

total weight = 2 + 2 + 1 + 1 = 6
replicas=8 -> 대략 3, 3, 1, 1
```

ScaleX-POD 정책 작성 시 의미:

```text
pool 단위 전체 weight를 의도했다면 labelSelector 하나가 여러 cluster를 매칭할 때의 분배 방식을 주의해야 한다.
정확한 cluster별 비율이 필요하면 clusterNames 기반 staticWeightList가 더 명시적이다.
```

---

## negative probe: minGroups 기대와 실제

`minGroups`가 hard fail처럼 동작하는지 확인하기 위해 임시 리소스로 `minGroups=4`, `maxGroups=4`를 적용했다.
실제 pool group은 `gpu`, `data`, `general` 세 개뿐이므로, 단순히 생각하면 scheduling 실패를 기대할 수 있다.

임시 정책 핵심:

```yaml
spreadConstraints:
  - spreadByLabel: scalex.io/pool
    minGroups: 4
    maxGroups: 4
```

실제 결과:

```text
Scheduled=True
FullyApplied=True
Result: {edgex:1, poolx:1, twinx:1}
```

ResourceBinding 일부:

```text
spec.clusters:
- edgex replicas=1
- poolx replicas=1
- twinx replicas=1
```

관찰:

```text
이번 lab 조건에서는 minGroups=4가 즉시 hard scheduling failure로 이어지지 않았다.
또한 datax가 pool=data label을 갖고 있어도 임시 workload는 edgex/poolx/twinx로만 배치됐다.
```

처리:

```text
임시 negative probe 리소스는 결과 수집 후 삭제했다.
최종 live namespace에는 demo-spread-pool-nginx 리소스만 남겼다.
```

정리 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete pp \
  -n demo-spread-constraints demo-spread-unsatisfied-policy --ignore-not-found

kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete deploy \
  -n demo-spread-constraints demo-spread-unsatisfied-nginx --ignore-not-found

kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete svc \
  -n demo-spread-constraints demo-spread-unsatisfied-nginx --ignore-not-found
```

주의:

```text
spreadConstraints의 minGroups/maxGroups 동작은 운영에서 hard guarantee로 단정하지 말고,
실제 Karmada 버전과 replica 수, candidate cluster 수, scoring 결과를 함께 검증해야 한다.
```

---

## 성공/실패 판단

```text
성공/주의 필요
```

성공 근거:

```text
1. spreadByLabel=scalex.io/pool 정책이 schema상 정상 적용됐다.
2. gpu/data/general pool label을 가진 cluster들이 모두 후보로 선택됐다.
3. 최종 workload가 twinx/edgex/datax/poolx에 모두 전파됐다.
4. ResourceBinding은 Scheduled=True, FullyApplied=True가 됐다.
5. member cluster의 pod가 모두 Running 상태가 됐다.
```

주의 필요 근거:

```text
1. labelSelector weight는 group 전체 weight가 아니라 매칭 cluster 각각의 weight처럼 동작했다.
2. minGroups=4 negative probe가 hard failure로 이어지지 않았다.
3. spreadConstraints는 운영 배치 보조 정책으로 쓰되, 중요한 보장 조건은 별도 실험으로 확인해야 한다.
```

---

## ScaleX-POD에 주는 의미

사용 가능한 패턴:

```text
pool label 기반 분산:
- gpu pool: TwinX/EdgeX
- data pool: DataX
- general pool: Resource Pool
```

추천 사용 방식:

```text
1. 큰 그룹 구분은 spreadConstraints로 표현한다.
2. 정확한 replica 비율은 clusterNames 또는 명확한 role label weight로 표현한다.
3. pool label처럼 여러 cluster를 매칭하는 weight는 per-cluster weight처럼 해석될 수 있음을 문서화한다.
4. minGroups/maxGroups를 장애 방지용 hard rule로 쓰기 전 별도 실패 실험이 필요하다.
```

ScaleX-POD 예시:

```text
render workload:
  spreadByLabel=scalex.io/pool
  gpu/general pool에 걸쳐 배치

analytics workload:
  spreadByLabel=scalex.io/pool
  data/general pool에 걸쳐 배치

platform workload:
  spreadByField=zone 또는 spreadByLabel=scalex.io/zone
  Tower/Resource Pool 장애 도메인 분산
```

---

## 다음 액션

```text
1. ArgoCD -> Karmada API Server GitOps 실험
2. Pull mode member cluster 등록 실험
3. prune/delete/rollback 동작 검증
4. scheduler-estimator 설치형 capacity-aware scheduling 실험
```
