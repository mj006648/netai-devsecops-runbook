# 실험 16. scheduler-estimator 상태와 비활성화 판단

## 목적

이전 실험 중 `karmada-scheduler` 로그에 scheduler-estimator 연결 실패가 반복적으로 보였다.
이번 실험은 현재 MiniX/kind Karmada lab에서 scheduler-estimator가 실제로 필요한지, 없을 때 스케줄링이 막히는지, lab에서는 비활성화해도 되는지 확인한다.

ScaleX-POD 기준 의미:

```text
Karmada scheduler-estimator는 member cluster의 실제 여유 리소스를 고려해 replica 조정을 더 정확히 하기 위한 보조 컴포넌트다.
하지만 ScaleX-POD 초기 검증이 label/weight/override/failover 중심이라면, estimator 없이도 기본 placement 검증은 가능해야 한다.
```

---

## 가설

```text
현재 lab에는 scheduler-estimator 서비스가 없기 때문에 scheduler 로그에 dial 실패가 반복된다.
하지만 label/weight 기반 Karmada placement 자체는 estimator 없이도 동작한다.
따라서 현재 kind lab에서는 estimator를 끄고, 나중에 resource-aware scheduling이 필요할 때 별도 설치 실험으로 분리하는 것이 낫다.
```

---

## 사전 상태

Karmada control plane:

```text
context: kind-tower
Karmada version image: docker.io/karmada/karmada-scheduler:v1.18.0
```

member cluster:

```text
- twinx Push Ready
- edgex Push Ready
- datax Push Ready
- poolx Push Ready
```

실험 전 scheduler command:

```text
/bin/karmada-scheduler
--kubeconfig=/etc/karmada/config/karmada.config
--metrics-bind-address=$(POD_IP):8080
--health-probe-bind-address=$(POD_IP):10351
--enable-scheduler-estimator=true
--leader-elect=true
--scheduler-estimator-ca-file=/etc/karmada/pki/ca.crt
--scheduler-estimator-cert-file=/etc/karmada/pki/karmada.crt
--scheduler-estimator-key-file=/etc/karmada/pki/karmada.key
--leader-elect-resource-namespace=karmada-system
--v=2
```

---

## estimator 서비스 존재 여부

확인 명령:

```bash
kubectl --context kind-tower -n karmada-system get svc | grep estimator
kubectl --context kind-tower -n karmada-system get endpoints | grep estimator

for c in tower twinx edgex datax poolx; do
  echo "--- kind-$c"
  kubectl --context kind-$c get deploy,ds,svc,pods -A | grep -i estimator || true
done
```

결과:

```text
karmada-scheduler-estimator-* 서비스 없음
karmada-scheduler-estimator-* endpoint 없음
모든 kind cluster에서 estimator pod/deployment/service 없음
```

판단:

```text
scheduler는 estimator 사용이 켜져 있지만, 실제 estimator 컴포넌트는 설치되어 있지 않다.
```

---

## scheduler 로그 이슈

확인 명령:

```bash
kubectl --context kind-tower -n karmada-system logs deploy/karmada-scheduler --tail=300 \
  | grep -Ei 'estimat|Failed to dial|does not exist in estimator cache'
```

대표 로그:

```text
Start dialing estimator server(karmada-scheduler-estimator-twinx.karmada-system.svc.cluster.local:10352,...)
Failed to dial cluster(twinx): timeout waiting for connection to karmada-scheduler-estimator-twinx.karmada-system.svc.cluster.local:10352

Start dialing estimator server(karmada-scheduler-estimator-edgex.karmada-system.svc.cluster.local:10352,...)
Failed to dial cluster(edgex): timeout waiting for connection to karmada-scheduler-estimator-edgex.karmada-system.svc.cluster.local:10352

Start dialing estimator server(karmada-scheduler-estimator-datax.karmada-system.svc.cluster.local:10352,...)
Failed to dial cluster(datax): timeout waiting for connection to karmada-scheduler-estimator-datax.karmada-system.svc.cluster.local:10352

Start dialing estimator server(karmada-scheduler-estimator-poolx.karmada-system.svc.cluster.local:10352,...)
Failed to dial cluster(poolx): timeout waiting for connection to karmada-scheduler-estimator-poolx.karmada-system.svc.cluster.local:10352
```

판단:

```text
기능이 바로 실패하지는 않지만, 없는 estimator를 주기적으로 찾으면서 로그 noise가 계속 발생한다.
```

---

## API/flag 확인

`replicaScheduling` 설명:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config explain \
  propagationpolicy.spec.placement.replicaScheduling \
  --api-version=policy.karmada.io/v1alpha1
```

핵심 내용:

```text
replicaSchedulingType:
- Duplicated
- Divided

replicaDivisionPreference:
- Aggregated: 가능한 적은 cluster에 replica를 모으되, cluster resource availability를 고려
- Weighted: WeightPreference에 따라 replica 분산
```

scheduler help에서 estimator 관련 flag:

```bash
kubectl --context kind-tower -n karmada-system exec deploy/karmada-scheduler -- \
  /bin/karmada-scheduler --help | grep -Ei 'estimator|resource'
```

핵심 flag:

```text
--enable-scheduler-estimator
  Enable calling cluster scheduler estimator for adjusting replicas.

--scheduler-estimator-service-prefix
  default: karmada-scheduler-estimator

--scheduler-estimator-service-namespace
  default: karmada-system

--scheduler-estimator-port
  default: 10352
```

---

## 매니페스트

```text
kubernetes/karmada/manifests/demo-scheduler-estimator/
  00-namespace.yaml
  10-aggregated-deployment.yaml
  20-aggregated-service.yaml
  30-aggregated-propagation-policy.yaml
  11-disabled-weighted-deployment.yaml
  21-disabled-weighted-service.yaml
  31-disabled-weighted-propagation-policy.yaml
```

### workload 1: estimator enabled 상태에서 Aggregated scheduling

```text
Deployment: demo-estimator-aggregated-nginx
replicas  : 4
requests  : cpu=10m, memory=32Mi
policy    : Divided + Aggregated
candidate : twinx, edgex, datax, poolx
```

목적:

```text
estimator가 켜져 있지만 실제 estimator cache가 없는 상태에서 Aggregated scheduling이 막히는지 확인한다.
```

### workload 2: estimator disabled 상태에서 Weighted scheduling

```text
Deployment: demo-estimator-disabled-weighted-nginx
replicas  : 4
requests  : cpu=10m, memory=32Mi
policy    : Divided + Weighted, twinx:edgex:datax:poolx = 1:1:1:1
```

목적:

```text
scheduler-estimator를 비활성화해도 일반 weight 기반 scheduling이 정상 동작하는지 확인한다.
```

---

## 실행 명령

### 1. dry-run

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply --dry-run=client \
  -f kubernetes/karmada/manifests/demo-scheduler-estimator/
```

결과:

```text
namespace/demo-scheduler-estimator created (dry run)
deployment.apps/demo-estimator-aggregated-nginx created (dry run)
service/demo-estimator-aggregated-nginx created (dry run)
propagationpolicy.policy.karmada.io/demo-estimator-aggregated-policy created (dry run)
```

### 2. estimator enabled 상태에서 Aggregated workload 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-scheduler-estimator/
```

실제 적용한 시각:

```text
2026-06-27T06:33:45Z
```

### 3. ResourceBinding 확인

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb \
  -n demo-scheduler-estimator demo-estimator-aggregated-nginx-deployment \
  -o jsonpath='{range .spec.clusters[*]}{.name}{" replicas="}{.replicas}{"\n"}{end}{"lastScheduledTime="}{.status.lastScheduledTime}{"\n"}{"schedulerObservedGeneration="}{.status.schedulerObservedGeneration}{"\n"}{"conditions="}{range .status.conditions[*]}{.type}{":"}{.status}{"/"}{.reason}{" "}{end}{"\n"}'
```

결과:

```text
poolx replicas=4
lastScheduledTime=2026-06-27T06:33:46Z
schedulerObservedGeneration=2
conditions=Scheduled:True/Success FullyApplied:True/FullyAppliedSuccess
```

member cluster:

```text
twinx: No resources found
edgex: No resources found
datax: No resources found
poolx: Deployment 4/4, Pod Running 4개
```

scheduler 로그:

```text
Max cluster available replicas error: [cluster poolx does not exist in estimator cache, cluster datax does not exist in estimator cache, cluster twinx does not exist in estimator cache, cluster edgex does not exist in estimator cache]
Binding has been scheduled successfully. Result: {poolx:4}
```

판단:

```text
estimator cache가 없어도 scheduling 자체는 실패하지 않았다.
다만 Aggregated + resource availability 판단은 estimator 없는 상태에서 정확한 리소스 기반 판단이라고 보기는 어렵다.
```

---

## scheduler-estimator 비활성화

현재 lab에는 estimator 서비스가 없으므로, 반복 dial 실패 로그를 줄이기 위해 scheduler flag를 비활성화했다.

실행 명령:

```bash
kubectl --context kind-tower -n karmada-system patch deploy karmada-scheduler --type=json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/command/4","value":"--enable-scheduler-estimator=false"}]'

kubectl --context kind-tower -n karmada-system rollout status deploy/karmada-scheduler --timeout=120s
```

### rollout 이슈

단일 노드 kind cluster라 새 scheduler pod가 Pending에 걸렸다.

원인:

```text
0/1 nodes are available: 1 node(s) didn't match pod anti-affinity rules.
```

상태:

```text
기존 pod: karmada-scheduler-55cfc54d66-fwlz4 Running
새 pod  : karmada-scheduler-67c6887679-cqtrd Pending
```

처리:

```bash
kubectl --context kind-tower -n karmada-system delete pod karmada-scheduler-55cfc54d66-fwlz4
kubectl --context kind-tower -n karmada-system rollout status deploy/karmada-scheduler --timeout=120s
```

결과:

```text
pod "karmada-scheduler-55cfc54d66-fwlz4" deleted
deployment "karmada-scheduler" successfully rolled out
karmada-scheduler-67c6887679-cqtrd  1/1 Running
```

최종 scheduler command:

```text
--enable-scheduler-estimator=false
```

주의:

```text
이 변경은 live kind lab에 적용한 설정이다.
운영 환경에서는 estimator를 설치할지, 끌지, Pull mode에서는 어떻게 다룰지 별도 설계가 필요하다.
```

---

## estimator disabled 상태에서 Weighted workload 적용

실행 시각:

```text
2026-06-27T06:45:50Z
```

적용 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-scheduler-estimator/11-disabled-weighted-deployment.yaml \
  -f kubernetes/karmada/manifests/demo-scheduler-estimator/21-disabled-weighted-service.yaml \
  -f kubernetes/karmada/manifests/demo-scheduler-estimator/31-disabled-weighted-propagation-policy.yaml
```

결과:

```text
deployment.apps/demo-estimator-disabled-weighted-nginx created
service/demo-estimator-disabled-weighted-nginx created
propagationpolicy.policy.karmada.io/demo-estimator-disabled-weighted-policy created
```

ResourceBinding:

```text
datax replicas=1
edgex replicas=1
poolx replicas=1
twinx replicas=1
lastScheduledTime=2026-06-27T06:45:51Z
schedulerObservedGeneration=2
conditions=Scheduled:True/Success FullyApplied:True/FullyAppliedSuccess
```

member cluster:

```text
twinx: Deployment 1/1
edgex: Deployment 1/1
datax: Deployment 1/1
poolx: Deployment 1/1
```

scheduler 로그:

```text
Binding has been scheduled successfully. Result: {datax:1, edgex:1, poolx:1, twinx:1}
```

비활성화 후 새 scheduler pod 로그에는 `Failed to dial estimator` 유형의 반복 에러가 보이지 않았다.

---

## 성공/실패 판단

```text
성공
```

근거:

```text
1. 현재 lab에 scheduler-estimator 서비스/파드가 없음을 확인했다.
2. estimator enabled 상태에서는 scheduler가 없는 estimator service를 계속 찾으며 dial 실패 로그를 남겼다.
3. estimator cache가 없어도 Aggregated workload는 Scheduled=True, FullyApplied=True가 됐다.
4. estimator disabled 후에도 Weighted workload는 twinx/edgex/datax/poolx=1:1:1:1로 정상 분산됐다.
5. 단일 노드 kind에서 scheduler rollout 시 anti-affinity Pending 이슈를 재확인하고 해결 절차를 기록했다.
```

---

## 문제/에러

### 1. estimator service 없음

증상:

```text
Failed to dial cluster(...): timeout waiting for connection to karmada-scheduler-estimator-...
```

의미:

```text
scheduler는 estimator를 사용하도록 설정되어 있지만, 해당 서비스가 없어서 연결 실패 로그가 반복된다.
```

### 2. Aggregated scheduling의 resource-aware 정확도 한계

증상:

```text
cluster ... does not exist in estimator cache
```

의미:

```text
Aggregated는 resource availability를 고려한다고 설명되어 있지만,
estimator cache가 없으면 실제 member cluster 여유 리소스 기반 판단의 신뢰도가 낮다.
```

### 3. 단일 노드 kind의 anti-affinity rollout 이슈

증상:

```text
0/1 nodes are available: 1 node(s) didn't match pod anti-affinity rules.
```

처리:

```text
기존 scheduler pod를 삭제해 새 pod가 같은 단일 노드에 올라오도록 했다.
```

---

## ScaleX-POD에 주는 의미

현재 단계 결론:

```text
MiniX/kind 기반 Karmada 기능 검증에서는 scheduler-estimator 없이도 진행 가능하다.
label placement, weighted replica scheduling, OverridePolicy, WorkloadRebalancer 실험은 estimator 없이도 검증됐다.
```

ScaleX-POD에서 estimator가 필요한 경우:

```text
1. cluster별 실제 CPU/Memory 여유량을 보고 replica 수를 조정해야 할 때
2. TwinX/EdgeX/DataX/Resource Pool 간 capacity 차이가 크고, 단순 weight로 부족할 때
3. GPU/스토리지/노드 상태까지 고려한 resource-aware placement가 필요할 때
4. Aggregated scheduling을 실제 운영 의미로 사용하려 할 때
```

현재 권장:

```text
1. lab에서는 --enable-scheduler-estimator=false 유지
2. ScaleX-POD 초기 설계는 label + weight + override + failover runbook 중심으로 진행
3. 실제 capacity-aware placement가 필요해지는 시점에 scheduler-estimator 설치 실험을 별도로 수행
4. scheduler-estimator 설치 전에는 Aggregated scheduling 결과를 resource-aware 판단으로 과신하지 않기
```

---

## 다음 액션

```text
1. spreadConstraints로 role/zone/provider 분산 배치 검증
2. ArgoCD -> Karmada API Server GitOps 실험
3. Pull mode member cluster 등록 실험
4. scheduler-estimator 설치형 실험은 나중에 capacity-aware scheduling 단계에서 분리
```
