# 실험 30. Kueue controller 장애/복구

## 목적

Karmada가 `datax`로 Job을 전파하는 중에 `datax`의 Kueue controller/webhook이 내려가면 어떤 계층에서 실패가 보이는지 확인한다.

확인할 것:

```text
1. Kueue controller가 0 replica일 때 Karmada Work 적용이 실패하는가?
2. Karmada ResourceBinding은 어떤 상태로 남는가?
3. controller를 복구하면 자동으로 수렴하는가?
4. 빠른 복구를 위해 어떤 재시도 트리거가 필요한가?
```

---

## 사전 상태

```text
Karmada cluster datax: READY=True
Kueue on datax: kueue-controller-manager 1/1 Running
demo namespace/queue/workload: 없음
```

확인 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get cluster datax -o wide
kubectl --context kind-datax -n kueue-system get deploy,pods -o wide
```

---

## 1. datax에 Kueue queue 준비

실험 27에서 만든 Kueue demo manifest를 재사용했다.

```bash
kubectl --context kind-datax apply \
  -f kubernetes/karmada/manifests/demo-kueue-datax/member/00-namespace.yaml

kubectl --context kind-datax apply \
  -f kubernetes/karmada/manifests/demo-kueue-datax/member/10-kueue-queues.yaml
```

결과:

```text
namespace/demo-kueue-datax created
resourceflavor.kueue.x-k8s.io/datax-default created
clusterqueue.kueue.x-k8s.io/datax-cpu-queue created
localqueue.kueue.x-k8s.io/datax-user-queue created
```

---

## 2. Kueue controller 중단

```bash
kubectl --context kind-datax -n kueue-system \
  scale deploy/kueue-controller-manager --replicas=0

kubectl --context kind-datax -n kueue-system get deploy
```

결과:

```text
kueue-controller-manager 0/0
```

의도:

```text
Kueue CRD와 webhook service object는 남아 있지만 controller/webhook endpoint가 없는 상태를 만든다.
```

---

## 3. Karmada API Server에 Job 제출

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-kueue-datax/karmada/00-namespace.yaml

kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-kueue-datax/karmada/01-cluster-propagation-policy-namespace.yaml \
  -f kubernetes/karmada/manifests/demo-kueue-datax/karmada/10-job-a.yaml \
  -f kubernetes/karmada/manifests/demo-kueue-datax/karmada/11-job-b.yaml \
  -f kubernetes/karmada/manifests/demo-kueue-datax/karmada/30-propagation-policy.yaml
```

Karmada API Server에는 Job과 policy가 생성됐다.

하지만 ResourceBinding은 다음 상태로 남았다.

```text
SCHEDULED=True
FULLYAPPLIED=False
```

DataX member cluster에는 Job/Pod/Workload가 생성되지 않았다.

---

## 4. 실패 원인 확인

Karmada Work 상세에서 member apply 실패 원인을 확인했다.

대표 메시지:

```text
Failed to apply all manifests (0/1):
failed calling webhook "mjob.kb.io":
failed to call webhook:
connect: connection refused
```

판단:

```text
Kueue controller/webhook 장애는 Kueue 내부 pending 상태가 아니라 Karmada member apply 실패로 드러난다.
즉 ArgoCD/Karmada가 만든 Job이 datax API Server admission 단계에서 거절되므로 ResourceBinding FullyApplied=False가 된다.
```

---

## 5. Kueue controller 복구

```bash
kubectl --context kind-datax -n kueue-system \
  scale deploy/kueue-controller-manager --replicas=1

kubectl --context kind-datax -n kueue-system \
  rollout status deploy/kueue-controller-manager --timeout=180s
```

결과:

```text
kueue-controller-manager 1/1 Running
```

복구 후 약 90초 동안 관찰했다.

관찰:

```text
ResourceBinding FullyApplied=False 유지
datax Job/Workload 없음
```

판단:

```text
controller/webhook이 살아나는 것만으로는 Karmada Work apply가 즉시 재시도되지 않았다.
운영에서 빠른 수렴이 필요하면 Karmada 쪽 resource update 또는 별도 재시도 트리거가 필요하다.
```

---

## 6. Karmada resource update로 재시도 유도

Karmada API Server의 Job에 annotation을 추가해 resourceVersion을 바꿨다.

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-kueue-datax annotate job demo-kueue-hold-a \
  scalex.io/retry-at="$stamp" --overwrite

kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-kueue-datax annotate job demo-kueue-hold-b \
  scalex.io/retry-at="$stamp" --overwrite
```

결과:

```text
ResourceBinding FullyApplied=True
datax Workload 1개 admitted
datax Workload 1개 pending
demo-kueue-hold-a Running
demo-kueue-hold-b Suspended
ClusterQueue pending=1 admitted=1
```

판단:

```text
Kueue controller 복구 후 Karmada resource update를 주면 Work가 다시 적용되고 정상적인 Kueue quota 상태로 들어간다.
```

---

## 7. cleanup

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete \
  -f kubernetes/karmada/manifests/demo-kueue-datax/karmada/ \
  --ignore-not-found

kubectl --context kind-datax delete \
  -f kubernetes/karmada/manifests/demo-kueue-datax/member/ \
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
Kueue controller down 상태 재현: 성공
Karmada member apply 실패 관찰: 성공
ResourceBinding FullyApplied=False 확인: 성공
controller 복구만으로 즉시 수렴하지 않는 현상 확인: 성공
Karmada resource update로 재시도/수렴 확인: 성공
cleanup: 성공
```

---

## ScaleX-POD에 주는 의미

```text
1. DataX/TwinX Kueue controller 장애는 Karmada FullyApplied=False로 보일 수 있다.
2. 이 상태는 단순 quota pending과 다르다.
3. 운영 알림은 Kueue controller unavailable과 Karmada member apply 실패를 같이 묶어 봐야 한다.
4. controller 복구 후에도 즉시 수렴하지 않을 수 있으므로 retry runbook이 필요하다.
5. ArgoCD가 Karmada API Server에 정상 sync했더라도 member admission webhook 장애로 실제 전파가 막힐 수 있다.
```

---

## 다음 액션

```text
1. Kueue quota 변경 시 pending/running Job 반응 확인
2. Kueue controller 장애 알림과 Karmada Work 실패 알림을 runbook에 반영
3. 운영에서는 controller 복구 후 Karmada resource 재적용 또는 annotation retry 절차를 준비
```
