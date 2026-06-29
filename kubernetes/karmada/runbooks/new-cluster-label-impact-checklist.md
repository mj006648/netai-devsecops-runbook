# 신규 member cluster label 영향 범위 점검 checklist

## 목적

Karmada에서 member cluster label은 placement의 핵심 입력이다.
새 cluster를 등록한 뒤 label을 붙이면 기존 `PropagationPolicy` 또는 `ClusterPropagationPolicy`의 `labelSelector`에 바로 매칭될 수 있다.
이 문서는 ScaleX-POD에서 신규 Tower/TwinX/EdgeX/DataX/Resource Pool 계열 cluster를 붙이기 전후에 확인할 checklist를 정리한다.

---

## 기본 원칙

```text
1. 신규 cluster를 등록한 직후에는 label을 최소화한다.
2. placement에 쓰이는 label은 한 번에 여러 개 붙이지 않는다.
3. label을 붙이기 전 기존 policy selector를 먼저 감사한다.
4. label을 붙인 직후 ResourceBinding/ClusterResourceBinding 변화량을 확인한다.
5. 예상하지 않은 binding이 생기면 즉시 label 또는 policy를 되돌린다.
```

---

## label 분류

ScaleX-POD에서는 label을 다음처럼 나눠서 다룬다.

| 분류 | 예시 | placement 영향 | 운영 기준 |
| --- | --- | --- | --- |
| 역할 label | `scalex.io/role=edge-gpu` | 큼 | 실제 workload 배치 기준이므로 사전 검토 후 부여 |
| pool label | `scalex.io/pool=gpu` | 큼 | spread/fallback 정책에 바로 매칭될 수 있음 |
| 위치 label | `scalex.io/location=edge` | 큼 | 너무 넓게 쓰면 신규 Edge cluster가 기존 edge workload에 편입됨 |
| 연결 방식 label | `scalex.io/connectivity=pull` | 중간 | Pull mode 전용 policy에 매칭됨 |
| 기능 label | `scalex.io/storage=ssd` | 중간 | DataX/스토리지 workload에 영향 가능 |
| 임시 검증 label | `scalex.io/staging=true` | 낮음 | 운영 policy가 보지 않는 key를 사용 |

권장:

```text
운영 workload placement에는 scalex.io/location=edge 단독 사용을 피한다.
role + pool + connectivity + workload tier를 조합한다.
```

예시:

```yaml
clusterAffinity:
  labelSelector:
    matchLabels:
      scalex.io/location: edge
      scalex.io/role: edge-gpu
      scalex.io/connectivity: push
```

---

## 사전 점검 1. cluster label snapshot

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusters -o wide --show-labels
```

보관할 것:

```text
cluster name
MODE Push/Pull
READY 상태
기존 label 전체
```

---

## 사전 점검 2. policy selector audit

`clusterNames`를 직접 쓰는 policy는 신규 cluster label만으로 자동 확장되지 않는다.
반대로 `labelSelector`를 쓰는 policy는 신규 cluster label에 바로 반응할 수 있다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get propagationpolicy -A -o yaml

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusterpropagationpolicy -o yaml
```

확인할 항목:

```text
spec.placement.clusterAffinity.labelSelector
spec.placement.replicaScheduling.weightPreference.staticWeightList[].targetCluster.labelSelector
```

위험도가 높은 selector 예시:

```text
scalex.io/location=edge
scalex.io/pool In gpu,general
scalex.io/pool In gpu,data,general
scalex.io/role=gpu-render
scalex.io/role=resource-pool
scalex.io/workload=data
```

---

## 사전 점검 3. 현재 binding snapshot

label 부여 전 binding 상태를 저장한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get resourcebinding -A -o wide

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusterresourcebinding -o wide
```

특정 신규 cluster만 보고 싶으면 JSON에서 `spec.clusters[].name`을 기준으로 찾는다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get resourcebinding -A -o json

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  get clusterresourcebinding -o json
```

---

## label 부여 절차

한 번에 하나씩 붙인다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config label cluster <cluster-name> \
  scalex.io/location=edge \
  --overwrite
```

바로 확인한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get cluster <cluster-name> \
  -o wide --show-labels

kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebinding -A -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusterresourcebinding -o wide
```

30~60초 후 다시 확인한다.

```bash
sleep 30
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebinding -A -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusterresourcebinding -o wide
```

---

## 예상하지 않은 binding이 생겼을 때

### 1. label을 되돌린다

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config label cluster <cluster-name> \
  scalex.io/location-
```

### 2. binding이 빠졌는지 확인한다

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebinding -A -o wide
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusterresourcebinding -o wide
```

### 3. member cluster 실제 resource를 확인한다

```bash
kubectl --context <member-context> -n <namespace> get all
```

주의:

```text
Service/ConfigMap처럼 replica가 없는 resource는 신규 cluster에 즉시 추가 전파될 수 있다.
Deployment처럼 replica가 있는 resource는 기존 배치가 자동으로 재분산되지 않을 수 있다.
재균형이 필요하면 WorkloadRebalancer 절차를 별도로 수행한다.
```

---

## ScaleX-POD 권장 label 설계

넓은 label:

```text
scalex.io/location=edge
```

이 label 하나만으로 운영 workload를 선택하지 않는다.

더 안전한 조합:

```text
scalex.io/location=edge
scalex.io/role=edge-gpu
scalex.io/pool=gpu
scalex.io/connectivity=push 또는 pull
scalex.io/workload=edge-runtime
```

Resource Pool은 별도 label로 분리한다.

```text
scalex.io/role=resource-pool
scalex.io/pool=general
scalex.io/fallback=true
```

Pull mode cluster는 연결 방식을 명시한다.

```text
scalex.io/connectivity=pull
```

---

## 운영 승인 기준

신규 cluster label을 운영에 반영하기 전 다음 조건을 만족해야 한다.

```text
1. 신규 cluster가 어떤 policy에 매칭되는지 목록화했다.
2. 예상 ResourceBinding 변화가 명확하다.
3. 예상하지 않은 Service/Deployment/Namespace 전파가 없다.
4. 변경 전후 binding snapshot을 남겼다.
5. rollback label 제거 명령을 준비했다.
6. 필요하면 WorkloadRebalancer 계획을 준비했다.
```
