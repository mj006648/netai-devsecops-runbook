# 실험 11. 여러 workload를 하나의 WorkloadRebalancer로 재균형

## 목적

실험 09에서는 하나의 Deployment를 `WorkloadRebalancer`로 재균형했다.
실험 10 cleanup에서는 여러 workload를 한 번에 재균형하는 패턴을 임시로 사용했다.

이번 실험은 여러 workload를 하나의 `WorkloadRebalancer.spec.workloads`에 넣어 batch 재균형하는 절차를 별도 실험으로 정리한다.

ScaleX-POD 기준 의미:

```text
TwinX 장애/점검 후 여러 서비스가 EdgeX/DataX로 이동한 상태에서,
TwinX 복구 후 여러 workload를 한 번에 원래 policy 기준으로 재분산하는 runbook을 검증한다.
```

---

## 가설

```text
여러 Deployment를 하나의 WorkloadRebalancer에 넣으면,
각 Deployment의 ResourceBinding이 모두 다시 scheduling되고,
각각의 policy에 맞게 twinx/edgex/datax로 재균형될 것이다.
```

---

## 실험 방식

이번 실험에서는 기존 cluster 전체에 영향을 주는 `NoExecute` taint를 다시 쓰지 않았다.
대신 전용 실험 workload의 `ResourceBinding.spec.clusters`만 lab-only 방식으로 직접 patch해서 skew 상태를 만들었다.

주의:

```text
ResourceBinding 직접 patch는 운영 절차가 아니라 실험용 skew 생성 방법이다.
운영에서 실제 skew는 장애, taint eviction, policy 변경, 수동 운영 등으로 발생할 수 있다.
```

---

## 매니페스트

```text
kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/
  00-namespace.yaml
  10-render-deployment.yaml
  11-edge-deployment.yaml
  12-data-deployment.yaml
  20-render-service.yaml
  21-edge-service.yaml
  22-data-service.yaml
  30-propagation-policy.yaml
  40-workload-rebalancer.yaml
```

대상 workload:

```text
namespace: demo-multi-rebalance
- Deployment/demo-multi-render-nginx
- Deployment/demo-multi-edge-nginx
- Deployment/demo-multi-data-nginx
```

각 Deployment:

```text
replicas: 3
```

기본 policy:

```text
twinx: 1
edgex: 1
datax: 1
```

---

## WorkloadRebalancer 매니페스트

```yaml
apiVersion: apps.karmada.io/v1alpha1
kind: WorkloadRebalancer
metadata:
  name: demo-multi-workload-rebalance-batch
spec:
  workloads:
    - apiVersion: apps/v1
      kind: Deployment
      namespace: demo-multi-rebalance
      name: demo-multi-render-nginx
    - apiVersion: apps/v1
      kind: Deployment
      namespace: demo-multi-rebalance
      name: demo-multi-edge-nginx
    - apiVersion: apps/v1
      kind: Deployment
      namespace: demo-multi-rebalance
      name: demo-multi-data-nginx
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
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/
```

결과:

```text
namespace/demo-multi-rebalance created (dry run)
deployment.apps/demo-multi-render-nginx created (dry run)
deployment.apps/demo-multi-edge-nginx created (dry run)
deployment.apps/demo-multi-data-nginx created (dry run)
service/demo-multi-render-nginx created (dry run)
service/demo-multi-edge-nginx created (dry run)
service/demo-multi-data-nginx created (dry run)
propagationpolicy.policy.karmada.io/demo-multi-rebalance-policy created (dry run)
workloadrebalancer.apps.karmada.io/demo-multi-workload-rebalance-batch created (dry run)
```

baseline 적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/00-namespace.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/10-render-deployment.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/11-edge-deployment.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/12-data-deployment.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/20-render-service.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/21-edge-service.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/22-data-service.yaml \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/30-propagation-policy.yaml
```

lab-only skew 생성:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config patch rb \
  -n demo-multi-rebalance demo-multi-render-nginx-deployment \
  --type=merge \
  -p '{"spec":{"clusters":[{"name":"edgex","replicas":2},{"name":"datax","replicas":1}]}}'

kubectl --kubeconfig ~/.kube/karmada-apiserver.config patch rb \
  -n demo-multi-rebalance demo-multi-edge-nginx-deployment \
  --type=merge \
  -p '{"spec":{"clusters":[{"name":"edgex","replicas":1},{"name":"datax","replicas":2}]}}'

kubectl --kubeconfig ~/.kube/karmada-apiserver.config patch rb \
  -n demo-multi-rebalance demo-multi-data-nginx-deployment \
  --type=merge \
  -p '{"spec":{"clusters":[{"name":"datax","replicas":3}]}}'
```

batch WorkloadRebalancer 적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-multi-workload-rebalance/40-workload-rebalancer.yaml
```

---

## 확인 명령

WorkloadRebalancer 상태:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get workloadrebalancer \
  demo-multi-workload-rebalance-batch \
  -o jsonpath='{.status.finishTime}{" observed="}{.status.observedGeneration}{" results="}{range .status.observedWorkloads[*]}{.workload.name}{":"}{.result}{" "}{end}{"\n"}'
```

ResourceBinding 확인:

```bash
for name in demo-multi-render-nginx demo-multi-edge-nginx demo-multi-data-nginx; do
  echo "### $name"
  kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb \
    -n demo-multi-rebalance ${name}-deployment \
    -o jsonpath='{range .spec.clusters[*]}{.name}{" replicas="}{.replicas}{"\n"}{end}{"lastScheduledTime="}{.status.lastScheduledTime}{"\n"}{"schedulerObservedGeneration="}{.status.schedulerObservedGeneration}{"\n"}{"gracefulEvictionTasks="}{.spec.gracefulEvictionTasks}{"\n"}'
done
```

member cluster 확인:

```bash
for c in twinx edgex datax; do
  echo "--- $c"
  kubectl --context kind-$c get deploy -n demo-multi-rebalance
 done
```

---

## 기대 결과

| 단계 | 기대 결과 |
| --- | --- |
| baseline | 세 workload 모두 twinx=1, edgex=1, datax=1 |
| lab-only skew | twinx에서 세 workload 제거, edgex/datax에 몰림 |
| WorkloadRebalancer | 세 workload 모두 Successful |
| 재균형 | 세 workload 모두 twinx=1, edgex=1, datax=1 |

---

## 실제 결과

### 1. baseline 적용

적용 시각:

```text
2026-06-26T03:51:32Z
```

적용 결과:

```text
namespace/demo-multi-rebalance created
deployment.apps/demo-multi-render-nginx created
deployment.apps/demo-multi-edge-nginx created
deployment.apps/demo-multi-data-nginx created
service/demo-multi-render-nginx created
service/demo-multi-edge-nginx created
service/demo-multi-data-nginx created
propagationpolicy.policy.karmada.io/demo-multi-rebalance-policy created
```

baseline ResourceBinding:

```text
demo-multi-render-nginx:
- datax replicas=1
- edgex replicas=1
- twinx replicas=1

demo-multi-edge-nginx:
- datax replicas=1
- edgex replicas=1
- twinx replicas=1

demo-multi-data-nginx:
- datax replicas=1
- edgex replicas=1
- twinx replicas=1
```

baseline member 상태:

```text
twinx:
- demo-multi-render-nginx 1/1
- demo-multi-edge-nginx   1/1
- demo-multi-data-nginx   1/1

edgex:
- demo-multi-render-nginx 1/1
- demo-multi-edge-nginx   1/1
- demo-multi-data-nginx   1/1

datax:
- demo-multi-render-nginx 1/1
- demo-multi-edge-nginx   1/1
- demo-multi-data-nginx   1/1
```

### 2. lab-only skew 생성

실행 시각:

```text
2026-06-26T03:53:03Z
```

patch 결과:

```text
resourcebinding.work.karmada.io/demo-multi-render-nginx-deployment patched
resourcebinding.work.karmada.io/demo-multi-edge-nginx-deployment patched
resourcebinding.work.karmada.io/demo-multi-data-nginx-deployment patched
```

skew ResourceBinding:

```text
demo-multi-render-nginx:
- edgex replicas=2
- datax replicas=1

demo-multi-edge-nginx:
- edgex replicas=1
- datax replicas=2

demo-multi-data-nginx:
- datax replicas=3
```

skew member 상태:

```text
twinx:
- workload 없음

edgex:
- demo-multi-render-nginx 2/2
- demo-multi-edge-nginx   1/1

datax:
- demo-multi-render-nginx 1/1
- demo-multi-edge-nginx   2/2
- demo-multi-data-nginx   3/3
```

### 3. batch WorkloadRebalancer 적용

적용 시각:

```text
2026-06-26T03:55:31Z
```

결과:

```text
workloadrebalancer.apps.karmada.io/demo-multi-workload-rebalance-batch created
```

status:

```text
finishTime=2026-06-26T03:55:31Z
observedGeneration=1

demo-multi-data-nginx: Successful
demo-multi-edge-nginx: Successful
demo-multi-render-nginx: Successful
```

### 4. 재균형 결과

관찰 시각:

```text
2026-06-26T03:55:53Z
2026-06-26T03:56:04Z
2026-06-26T03:56:14Z
2026-06-26T03:56:25Z
```

세 ResourceBinding 모두 다음 상태로 돌아왔다.

```text
datax replicas=1
edgex replicas=1
twinx replicas=1
lastScheduledTime=2026-06-26T03:55:31Z
schedulerObservedGeneration=5
gracefulEvictionTasks=
```

member 상태:

```text
twinx:
- demo-multi-render-nginx 1/1
- demo-multi-edge-nginx   1/1
- demo-multi-data-nginx   1/1

edgex:
- demo-multi-render-nginx 1/1
- demo-multi-edge-nginx   1/1
- demo-multi-data-nginx   1/1

datax:
- demo-multi-render-nginx 1/1
- demo-multi-edge-nginx   1/1
- demo-multi-data-nginx   1/1
```

---

## 성공/실패 판단

| 검증 항목 | 기대 결과 | 실제 결과 | 판단 |
| --- | --- | --- | --- |
| baseline | 세 workload 1:1:1 | 모두 1:1:1 | 성공 |
| skew 생성 | twinx 제거, edgex/datax 집중 | twinx workload 없음, edgex/datax 집중 | 성공 |
| batch WLR status | 세 workload Successful | 세 workload Successful | 성공 |
| 재균형 | 세 workload 모두 1:1:1 | 모두 1:1:1 | 성공 |
| gracefulEvictionTasks | 비어 있음 | 비어 있음 | 성공 |

---

## 문제/에러

이번 실험 자체에서는 Karmada 기능 실패는 없었다.

주의할 점은 있다.

### 1. ResourceBinding 직접 patch는 실험용이다

이번 skew 생성은 cluster 전체 taint를 다시 사용하지 않기 위한 lab-only 방법이다.
운영에서 ResourceBinding을 직접 patch하는 방식은 기본 runbook으로 삼지 않는다.

운영 skew 원인 후보:

```text
- NoExecute taint eviction
- 실제 장애 후 운영자 개입
- policy 변경
- 수동 migration
```

### 2. WorkloadRebalancer는 one-shot object다

같은 이름의 `WorkloadRebalancer`가 이미 `Successful`이면, 같은 이름으로 다시 apply하는 것을 반복 실행으로 보면 안 된다.

반복 실행 방식:

```text
1. 기존 WorkloadRebalancer 삭제 후 같은 이름 재생성
2. timestamp가 들어간 새 이름 사용
3. ttlSecondsAfterFinished를 넣어 완료 후 자동 정리
```

---

## ScaleX-POD에 주는 의미

이번 실험으로 확인한 점:

```text
1. WorkloadRebalancer 하나로 여러 workload를 한 번에 재균형할 수 있다.
2. 각 workload는 자신의 PropagationPolicy placement 기준으로 다시 scheduling된다.
3. 장애/점검 복구 runbook에서 workload 목록을 묶어 batch 재균형할 수 있다.
```

ScaleX-POD 운영 후보 흐름:

```text
TwinX 장애/점검
  -> NoExecute taint로 이동 대상 workload를 EdgeX/DataX/Resource Pool로 이동
  -> TwinX 복구
  -> taint 제거
  -> 재균형 대상 workload 목록 생성
  -> WorkloadRebalancer 생성
  -> 각 workload가 policy 기준으로 TwinX/EdgeX/DataX에 재분산
```

운영 runbook에서 필요한 입력:

```text
- 대상 namespace 목록
- 대상 workload 목록
- 재균형 제외 workload 목록
- WorkloadRebalancer 이름 규칙
- TTL 사용 여부
- 완료 후 status 확인 명령
```

---

## 다음 액션

- ScaleX-POD role label 기반 placement 고도화
- OverridePolicy image/storageClass 실험
- scheduler-estimator 정리
- ArgoCD -> Karmada API Server GitOps 흐름 검증
- Pull mode 후보 검토
