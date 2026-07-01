# 실험 23. Pull mode cluster 포함 WorkloadRebalancer 재균형

## 목적

실험 20~22에서 `pullx`를 Pull mode member cluster로 등록했고, `scalex.io/location=edge` label 때문에 기존 edge Service가 `pullx`에도 전파되는 것을 확인했다.
하지만 기존 edge Deployment는 여전히 `edgex=2`, `pullx=0` 상태였다.

이번 실험은 새로 추가된 Pull mode cluster까지 기존 edge replica workload를 `WorkloadRebalancer`로 재균형할 수 있는지 확인한다.

ScaleX-POD 기준 의미:

```text
EdgeX 계열 신규 cluster 또는 Pull mode cluster를 추가한 뒤,
기존 edge workload를 새 cluster까지 의도적으로 재분산할 수 있는지 검증한다.
```

---

## 가설

```text
1. 기존 ResourceBinding은 새 cluster가 policy selector에 매칭되어도 replica workload를 자동 재분산하지 않을 수 있다.
2. WorkloadRebalancer를 실행하면 현재 policy placement를 기준으로 ResourceBinding이 다시 계산된다.
3. `scalex.io/location=edge`를 가진 edgex와 pullx가 동일 weight로 매칭되므로 replicas=2는 edgex=1, pullx=1로 재균형될 것이다.
4. Pull mode cluster인 pullx에도 karmada-agent를 통해 Deployment/Pod가 생성될 것이다.
```

---

## 대상 workload

기존 실험 12의 edge workload를 재사용했다.

```text
namespace : demo-scalex-role
Deployment: demo-scalex-edge-nginx
Service   : demo-scalex-edge-nginx
replicas  : 2
policy    : demo-scalex-edge-policy
selector  : scalex.io/location=edge
```

현재 매칭 cluster:

```text
edgex: scalex.io/location=edge, Push mode
pullx: scalex.io/location=edge, Pull mode
```

---

## 사전 상태

WorkloadRebalancer 기존 리소스:

```text
demo-multi-workload-rebalance-batch
demo-noexecute-eviction-rebalance
demo-pool-fallback-rebalance-run
```

ResourceBinding before:

```text
demo-scalex-edge-nginx-deployment
  clusters=edgex:2
  Scheduled=True
  FullyApplied=True

demo-scalex-edge-nginx-service
  clusters=edgex,pullx
  Scheduled=True
  FullyApplied=True
```

member cluster before:

```text
edgex:
  Deployment/demo-scalex-edge-nginx 2/2
  Pod 2개 Running
  Service present

pullx:
  Deployment 없음
  Pod 없음
  Service/demo-scalex-edge-nginx present
```

해석:

```text
실험 22에서 확인한 것처럼 Service는 pullx에 추가 전파됐지만,
Deployment replica는 기존 edgex=2 상태로 남아 있었다.
```

---

## 단계 1. WorkloadRebalancer manifest 작성

매니페스트 위치:

```text
kubernetes/multicluster/karmada/manifests/demo-pull-rebalance/10-workload-rebalancer.yaml
```

내용:

```yaml
apiVersion: apps.karmada.io/v1alpha1
kind: WorkloadRebalancer
metadata:
  name: demo-pull-edge-rebalance-run
spec:
  workloads:
    - apiVersion: apps/v1
      kind: Deployment
      namespace: demo-scalex-role
      name: demo-scalex-edge-nginx
```

적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-pull-rebalance/10-workload-rebalancer.yaml
```

결과:

```text
workloadrebalancer.apps.karmada.io/demo-pull-edge-rebalance-run created
```

---

## 단계 2. WorkloadRebalancer status 확인

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get workloadrebalancer demo-pull-edge-rebalance-run -o yaml
```

결과:

```text
status:
  finishTime: "2026-06-29T03:52:38Z"
  observedGeneration: 1
  observedWorkloads:
  - result: Successful
    workload:
      apiVersion: apps/v1
      kind: Deployment
      name: demo-scalex-edge-nginx
      namespace: demo-scalex-role
```

판단:

```text
WorkloadRebalancer 자체는 즉시 Successful로 완료됐다.
```

---

## 단계 3. ResourceBinding 재균형 확인

확인 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-scalex-role get rb demo-scalex-edge-nginx-deployment -o jsonpath='...'
```

결과:

```text
clusters=edgex:1 pullx:1
conditions=Scheduled:True:Success FullyApplied:True:FullyAppliedSuccess
aggregated=edgex:true:Healthy:1/1 pullx:true:Healthy:1/1
```

판단:

```text
기존 edgex=2 skew가 edgex=1, pullx=1로 재균형됐다.
```

---

## 단계 4. member cluster 실제 상태 확인

### edgex

```bash
kubectl --context kind-edgex -n demo-scalex-role \
  get deploy,pods -l app=demo-scalex-edge-nginx -o wide
```

결과:

```text
Deployment/demo-scalex-edge-nginx 1/1
Pod/demo-scalex-edge-nginx-648fb94657-jd69r Running
```

### pullx

```bash
kubectl --context kind-pullx -n demo-scalex-role \
  get deploy,pods -l app=demo-scalex-edge-nginx -o wide
```

결과:

```text
Deployment/demo-scalex-edge-nginx 1/1
Pod/demo-scalex-edge-nginx-648fb94657-n6bgv Running
```

60초 후에도 상태 유지:

```text
edgex Deployment 1/1
pullx Deployment 1/1
ResourceBinding edgex:1 pullx:1
FullyApplied=True
```

---

## 성공/실패 판단

```text
Pull mode cluster까지 WorkloadRebalancer 재균형: 성공
ResourceBinding edgex=2 -> edgex=1,pullx=1 변경: 성공
pullx에 Deployment/Pod 생성: 성공
edgex 기존 Deployment replica 감소: 성공
Service는 기존처럼 edgex,pullx 유지: 성공
```

---

## 기존 WorkloadRebalancer 실험과의 차이

기존 실험과 겹치는지 확인했다.

```text
실험 09: 단일 workload를 Push cluster twinx/edgex/datax 사이에서 재균형
실험 11: 여러 workload를 Push cluster 사이에서 batch 재균형
실험 15: Resource Pool fallback skew를 Push cluster twinx/edgex/poolx 사이에서 재균형
실험 23: 새로 추가된 Pull mode cluster pullx까지 기존 edge workload를 재균형
```

판단:

```text
WorkloadRebalancer라는 기능은 같지만 검증 시나리오가 다르다.
실험 23은 Push/Pull 혼합 cluster와 신규 cluster 편입 후 재균형을 검증하므로 중복이 아니다.
```

---

## ScaleX-POD에 주는 의미

```text
1. 신규 Pull mode Edge cluster를 붙인 뒤 기존 edge workload를 의도적으로 재분산할 수 있다.
2. Service 같은 non-replica resource는 label 매칭 시 먼저 추가 전파될 수 있다.
3. Deployment replica는 자동 재균형을 기대하지 말고 WorkloadRebalancer 절차를 실행해야 한다.
4. Push cluster와 Pull cluster가 같은 placement selector에 들어와도 WorkloadRebalancer가 재계산할 수 있다.
5. 신규 EdgeX/Pull Edge 확장 시 운영 절차는 label audit -> binding 확인 -> WorkloadRebalancer 순서가 적절하다.
```

---

## 주의점

```text
이 실험 이후 live lab의 demo-scalex-edge-nginx 상태는 실험 12 당시의 edgex=2가 아니라 edgex=1,pullx=1이다.
실험 12 문서는 당시 결과이고, 현재 live state는 실험 23에 의해 진화한 상태다.
```

---

## 다음 액션

```text
1. Pull mode 네트워크 단절/복구 실험
2. ApplicationSet으로 Push/Pull workload를 함께 관리하는 GitOps 구조 실험
3. ArgoCD prune 운영 안전장치 정리
4. Kueue 조합 검토
5. scheduler-estimator 설치형 실험
```
