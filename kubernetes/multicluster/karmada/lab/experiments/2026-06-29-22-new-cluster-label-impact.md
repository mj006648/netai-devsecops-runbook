# 실험 22. 신규 cluster label 영향 범위 점검

## 목적

실험 20에서 Pull mode cluster `pullx`를 새로 등록하고 다음 label을 붙였다.

```text
scalex.io/role=pull-edge
scalex.io/pool=edge-pull
scalex.io/location=edge
scalex.io/connectivity=pull
```

이후 `demo-pull-mode` workload는 의도대로 `pullx`에 배치됐다.
하지만 추가로 기존 `demo-scalex-edge-policy`의 Service도 `pullx`에 전파됐다.
이번 실험은 신규 cluster에 label을 붙일 때 기존 policy가 어디까지 영향을 받는지 점검하고, ScaleX-POD 운영 checklist로 정리하는 것이 목적이다.

---

## 가설

```text
1. clusterNames를 직접 쓰는 policy는 신규 cluster label만으로 자동 확장되지 않는다.
2. labelSelector를 쓰는 policy는 신규 cluster label에 바로 매칭될 수 있다.
3. Service처럼 replica가 없는 resource는 새로 매칭된 cluster에 추가 전파될 수 있다.
4. Deployment처럼 replica가 있는 resource는 새 cluster가 selector에 매칭되어도 기존 replica 배치가 자동 재분산되지 않을 수 있다.
5. 따라서 신규 cluster label 부여 전 policy selector audit이 필요하다.
```

---

## 사전 상태

현재 member cluster label:

```text
NAME    MODE   READY   LABELS
twinx   Push   True    scalex.io/pool=gpu,scalex.io/role=gpu-render
edgex   Push   True    scalex.io/location=edge,scalex.io/pool=gpu,scalex.io/role=edge-gpu
datax   Push   True    scalex.io/pool=data,scalex.io/role=data,scalex.io/storage=ssd,scalex.io/workload=data
poolx   Push   True    scalex.io/fallback=true,scalex.io/pool=general,scalex.io/role=resource-pool,scalex.io/workload=general
pullx   Pull   True    scalex.io/connectivity=pull,scalex.io/location=edge,scalex.io/pool=edge-pull,scalex.io/role=pull-edge
```

확인 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusters -o wide --show-labels
```

---

## 단계 1. policy selector audit

확인 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get propagationpolicy -A -o json

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusterpropagationpolicy -o json
```

분류 결과:

### clusterNames 기반 policy

다음 계열은 `clusterNames`를 직접 사용하므로, 신규 cluster에 label을 붙여도 자동으로 `pullx`를 포함하지 않는다.

```text
demo-nginx
demo-weighted
demo-cluster-failover
demo-failover
demo-failover-enabled
demo-noexecute-eviction
demo-noexecute-toleration-scope
demo-multi-workload-rebalance
demo-override-platform
demo-scheduler-estimator
demo-argocd-prune-rollback
```

### labelSelector 기반 policy

다음 계열은 신규 cluster label과 매칭될 수 있다.

| selector | 관련 policy | 신규 cluster 영향 |
| --- | --- | --- |
| `scalex.io/connectivity=pull` | `demo-pull-mode-nginx-policy`, `demo-pull-mode-namespace-policy` | `pullx` 의도 매칭 |
| `scalex.io/location=edge` | `demo-scalex-edge-policy` | `pullx`가 기존 edge Service에 추가 매칭됨 |
| `scalex.io/pool=gpu` | `demo-scalex-render-policy` | 신규 cluster가 gpu pool이면 render workload 후보가 됨 |
| `scalex.io/pool In gpu,general` | resource pool fallback/rebalance policy | 신규 cluster가 gpu/general이면 fallback 후보가 됨 |
| `scalex.io/pool In gpu,data,general` | spread constraints policy | 신규 cluster가 기존 pool이면 spread 후보가 됨 |
| `scalex.io/role=gpu-render` | twinx-only 계열 policy | 신규 cluster가 같은 role이면 twinx-only 실험 workload 후보가 됨 |
| `scalex.io/role=resource-pool` | resource pool general policy | 신규 cluster가 resource-pool이면 general workload 후보가 됨 |
| `scalex.io/workload=data` | data workload policy | 신규 cluster가 data workload label을 가지면 DataX workload 후보가 됨 |

판단:

```text
운영 label 중 scalex.io/location=edge는 너무 넓다.
Edge 계열 cluster 전체를 뜻하는 label로는 유용하지만, workload placement selector로 단독 사용하면 신규 cluster가 의도치 않게 편입될 수 있다.
```

---

## 단계 2. pullx에 실제 매칭된 binding 확인

확인 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get resourcebinding -A -o json

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusterresourcebinding -o json
```

`pullx`가 포함된 ResourceBinding:

```text
demo-pull-mode/demo-pull-mode-nginx-deployment
  resource=Deployment/demo-pull-mode-nginx
  policy=demo-pull-mode-nginx-policy
  clusters=pullx:2
  판단=의도한 Pull mode workload

demo-pull-mode/demo-pull-mode-nginx-service
  resource=Service/demo-pull-mode-nginx
  policy=demo-pull-mode-nginx-policy
  clusters=pullx
  판단=의도한 Pull mode Service

demo-scalex-role/demo-scalex-edge-nginx-service
  resource=Service/demo-scalex-edge-nginx
  policy=demo-scalex-edge-policy
  clusters=edgex,pullx
  판단=scalex.io/location=edge 때문에 추가 매칭된 기존 Service
```

`pullx`가 포함된 ClusterResourceBinding:

```text
demo-pull-mode-namespace
  resource=Namespace/demo-pull-mode
  policy=demo-pull-mode-namespace-policy
  clusters=pullx
  판단=의도한 Pull mode namespace
```

---

## 단계 3. 기존 edge policy 영향 확인

기존 policy:

```yaml
clusterAffinity:
  labelSelector:
    matchLabels:
      scalex.io/location: edge
```

`pullx`에도 같은 label이 있다.

```text
scalex.io/location=edge
```

실제 확인:

```bash
kubectl --context kind-pullx -n demo-scalex-role get deploy,rs,pods,svc -o wide
```

결과:

```text
service/demo-scalex-edge-nginx present
Deployment 없음
Pod 없음
```

ResourceBinding:

```text
Service binding clusters: edgex,pullx
Deployment binding clusters: edgex
```

해석:

```text
Service는 replica 개념이 없기 때문에 신규로 매칭된 pullx에 추가 전파됐다.
Deployment는 기존 replicas=2가 edgex에 유지됐고, pullx로 자동 재분산되지는 않았다.
따라서 신규 cluster label 추가 후에는 resource 종류별로 영향이 다르게 나타날 수 있다.
```

---

## 단계 4. checklist 문서화

운영 절차로 다음 runbook을 추가했다.

```text
kubernetes/multicluster/karmada/RUNBOOK.md#신규-member-cluster-label-영향-범위-점검-checklist
```

핵심 checklist:

```text
1. 신규 cluster label을 최소화한다.
2. label 부여 전 policy selector audit을 한다.
3. label 부여 전 ResourceBinding/ClusterResourceBinding snapshot을 남긴다.
4. label은 한 번에 하나씩 붙인다.
5. label 부여 후 30~60초 동안 binding 변화를 본다.
6. 예상하지 않은 binding이 생기면 label을 제거하거나 policy selector를 좁힌다.
7. replica workload 재분산은 자동으로 기대하지 않고 WorkloadRebalancer 계획을 별도로 둔다.
```

---

## 성공/실패 판단

```text
기존 policy selector audit: 성공
pullx에 실제 매칭된 ResourceBinding 확인: 성공
broad label로 기존 Service가 추가 전파된 현상 정리: 성공
Deployment 자동 재분산 미발생 정리: 성공
운영 checklist 문서화: 성공
```

---

## ScaleX-POD에 주는 의미

```text
1. 신규 cluster를 붙일 때 label은 단순 metadata가 아니라 scheduling input이다.
2. scalex.io/location=edge 같은 broad label은 단독 placement selector로 쓰면 위험하다.
3. EdgeX/TwinX/DataX/Resource Pool label은 role, pool, connectivity, workload tier를 조합해서 좁혀야 한다.
4. 신규 cluster 등록 절차에는 반드시 policy selector audit과 binding diff가 들어가야 한다.
5. 신규 cluster를 추가했다고 기존 replica workload가 자동으로 균형 있게 재배치되지는 않는다.
6. 재균형은 WorkloadRebalancer 실험/운영 절차로 분리해야 한다.
```

---

## 다음 액션

```text
1. Pull mode + WorkloadRebalancer 재균형 실험
2. Pull mode 네트워크 단절/복구 실험
3. ApplicationSet으로 Push/Pull workload를 함께 관리하는 GitOps 구조 실험
4. ArgoCD prune 운영 안전장치 정리
```
