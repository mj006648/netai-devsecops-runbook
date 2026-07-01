# 실험 31. Kueue quota 변경

## 목적

Kueue ClusterQueue quota를 운영 중에 변경했을 때 pending Job과 이미 admitted/running 중인 Job이 어떻게 반응하는지 확인한다.

확인할 것:

```text
1. quota를 늘리면 pending Job이 자동 admitted 되는가?
2. quota를 줄이면 이미 admitted/running 중인 Job이 즉시 evict/suspend 되는가?
3. ArgoCD/Karmada 관점과 Kueue 관점에서 어떤 상태를 봐야 하는가?
```

---

## 사전 상태

실험 30에서 복구 후 정상 수렴한 demo 상태를 사용했다.

```text
ClusterQueue datax-cpu-queue: pending=1 admitted=1
LocalQueue datax-user-queue: pending=1 admitted=1
demo-kueue-hold-a: Running
demo-kueue-hold-b: Suspended
nominalQuota: cpu=1
```

확인 명령:

```bash
kubectl --context kind-datax get clusterqueue datax-cpu-queue -o wide
kubectl --context kind-datax -n demo-kueue-datax get localqueue datax-user-queue -o wide
kubectl --context kind-datax -n demo-kueue-datax get workloads -o wide
kubectl --context kind-datax -n demo-kueue-datax get job,pods -o wide
```

---

## 1. quota를 1에서 2로 증가

```bash
kubectl --context kind-datax patch clusterqueue datax-cpu-queue \
  --type=json \
  -p='[{"op":"replace","path":"/spec/resourceGroups/0/flavors/0/resources/0/nominalQuota","value":"2"}]'
```

관찰 결과:

```text
ClusterQueue pending=0 admitted=2
LocalQueue pending=0 admitted=2
두 Workload 모두 ADMITTED=True
demo-kueue-hold-a Running
demo-kueue-hold-b Running
```

판단:

```text
quota를 늘리면 pending workload가 빠르게 admitted되고 Suspended Job이 Running으로 전환된다.
Karmada resource를 수정하지 않아도 member-local Kueue가 quota 변경만으로 재평가한다.
```

---

## 2. quota를 2에서 1로 감소

두 Job이 모두 Running인 상태에서 quota를 다시 낮췄다.

```bash
kubectl --context kind-datax patch clusterqueue datax-cpu-queue \
  --type=json \
  -p='[{"op":"replace","path":"/spec/resourceGroups/0/flavors/0/resources/0/nominalQuota","value":"1"}]'
```

20초 이상 관찰한 결과:

```text
ClusterQueue pending=0 admitted=2
LocalQueue pending=0 admitted=2
두 Workload 모두 ADMITTED=True 유지
demo-kueue-hold-a Running 유지
demo-kueue-hold-b Running 유지
spec nominalQuota는 cpu=1로 변경됨
```

판단:

```text
Kueue quota를 이미 사용량보다 낮게 줄여도, 이미 admitted/running 중인 Job을 즉시 evict하거나 suspend하지 않았다.
quota 감소는 새 admission을 제한하는 운영 조치로 봐야 하고, 실행 중 Job 회수 정책은 별도로 설계해야 한다.
```

---

## 3. cleanup

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete \
  -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/karmada/ \
  --ignore-not-found

kubectl --context kind-datax delete \
  -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/member/ \
  --ignore-not-found
```

최종 상태:

```text
Karmada demo namespace: NotFound
datax demo namespace/queue: NotFound
Kueue controller on datax: 1/1 Running
```

---

## 성공/실패 판단

```text
quota 증가 시 pending workload admission 확인: 성공
quota 증가 후 두 Job Running 확인: 성공
quota 감소 시 running Job 즉시 evict/suspend 없음 확인: 성공
cleanup: 성공
```

---

## ScaleX-POD에 주는 의미

```text
1. DataX/TwinX batch capacity를 늘릴 때 Kueue quota 증가는 즉시 pending 해소 수단이 된다.
2. quota 감소는 실행 중 workload를 강제로 내리는 장치가 아니다.
3. 긴급 회수가 필요하면 Job 중단, 우선순위/preemption 정책, 별도 운영 절차를 설계해야 한다.
4. 운영 dashboard는 quota spec 값과 admitted workload 수가 일시적으로 불일치할 수 있음을 보여줘야 한다.
```

---

## 다음 액션

```text
1. quota 변경 runbook에 증가/감소 의미를 분리해 적는다.
2. running Job 회수 정책이 필요하면 Kueue preemption 또는 Job 종료 절차를 별도 실험한다.
3. scheduler-estimator 설치형 capacity-aware scheduling을 확인한다.
```
