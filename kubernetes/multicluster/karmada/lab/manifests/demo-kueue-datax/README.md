# demo-kueue-datax

이 예제는 Karmada와 Kueue의 역할을 분리해서 확인한다.

```text
Karmada: Job을 datax member cluster로 보낸다.
Kueue on datax: datax 안에서 Job admission과 CPU/memory quota를 제어한다.
```

## 적용 순서

Kueue CRD는 현재 `datax` member cluster에만 설치한다. 따라서 Kueue queue 리소스는 Karmada API Server가 아니라 `kind-datax`에 직접 적용한다.

```bash
kubectl --context kind-datax apply -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/member/
```

Karmada가 전파할 Namespace/Job/PropagationPolicy는 Karmada API Server에 적용한다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-kueue-datax/karmada/
```

## 기대 결과

```text
1. 두 Job은 Karmada를 통해 datax에만 생성된다.
2. datax의 Kueue ClusterQueue quota는 cpu=1 이다.
3. Job A/B는 각각 cpu=1을 요청한다.
4. 따라서 동시에 하나만 admitted/running 되고, 다른 하나는 pending 상태가 된다.
5. running Job을 삭제하면 pending Job이 admitted 된다.
```

## ScaleX-POD 의미

```text
Karmada는 ScaleX-POD 전체에서 어느 member cluster로 보낼지 결정한다.
Kueue는 DataX/TwinX 같은 member cluster 내부에서 batch/AI 작업의 입장 순서와 quota를 제어한다.
처음부터 Kueue MultiKueue와 Karmada를 겹치게 쓰지 말고, local queue 역할부터 분리해서 검증한다.
```
