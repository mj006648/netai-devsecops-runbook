# 실험 26. Pull mode 네트워크 단절/복구

## 목적

실험 21에서는 `karmada-agent` Deployment를 scale down해서 agent 장애를 만들었다.
이번 실험은 agent process를 직접 내리지 않고, `pullx`에서 Karmada API Server로 가는 네트워크를 차단해 현장망 단절에 가까운 상황을 검증한다.

확인할 것:

```text
1. 네트워크 차단 시 pullx Cluster READY가 Unknown이 되는가?
2. 기존 workload는 유지되는가?
3. 차단 중 Karmada API Server의 desired state 변경이 member cluster에 반영되지 않는가?
4. 네트워크 복구 후 agent가 다시 수렴하는가?
5. 어떤 차단 방식이 kind/CNI 환경에서 실제로 유효한가?
```

---

## 사전 상태

```text
pullx MODE=Pull READY=True
karmada-agent 1/1 Running
agent Pod IP=10.244.0.8
Karmada API endpoint=172.18.0.2:32443
demo-pull-mode-nginx replicas=2
```

확인 명령:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get cluster pullx -o wide
kubectl --context kind-pullx -n karmada-system get deploy,pods -o wide
kubectl --context kind-pullx -n demo-pull-mode get deploy,pods -o wide
```

---

## 1차 시도. node OUTPUT 체인 차단

명령:

```bash
docker exec pullx-control-plane iptables -I OUTPUT 1 \
  -d 172.18.0.2 \
  -p tcp \
  --dport 32443 \
  -m comment \
  --comment karmada-api-block \
  -j REJECT
```

관찰:

```text
OUTPUT rule은 들어갔다.
하지만 pullx READY는 계속 True였다.
차단 중 Karmada API에서 replicas=2 -> 3 변경을 했더니 pullx 실제 Deployment도 3/3으로 올라갔다.
```

판단:

```text
1차 시도는 네트워크 단절 실험으로 실패했다.
kind/CNI 환경에서 agent Pod 트래픽은 node OUTPUT 체인이 아니라 FORWARD/CNI 경로를 타는 것으로 보인다.
이 실패는 운영 이슈 기록 가치가 있다.
```

원복:

```bash
docker exec pullx-control-plane iptables -D OUTPUT \
  -d 172.18.0.2 \
  -p tcp \
  --dport 32443 \
  -m comment \
  --comment karmada-api-block \
  -j REJECT

kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-pull-mode/
```

원복 결과:

```text
iptables rule 없음
demo-pull-mode-nginx 2/2
pullx READY=True
```

---

## 2차 시도. agent Pod IP 기준 FORWARD 체인 차단

agent Pod IP 확인:

```bash
kubectl --context kind-pullx -n karmada-system get pod \
  -l app=karmada-agent \
  -o jsonpath='{.items[0].status.podIP}'
```

결과:

```text
10.244.0.8
```

차단 명령:

```bash
docker exec pullx-control-plane iptables -I FORWARD 1 \
  -s 10.244.0.8 \
  -d 172.18.0.2 \
  -p tcp \
  --dport 32443 \
  -m comment \
  --comment karmada-api-block \
  -j REJECT
```

rule 확인:

```text
-A FORWARD -s 10.244.0.8/32 -d 172.18.0.2/32 -p tcp --dport 32443 -m comment --comment karmada-api-block -j REJECT
```

---

## 2차 시도 결과 1. READY Unknown

30초 후:

```text
pullx READY=True
agent log:
Get "https://172.18.0.2:32443/apis/cluster.karmada.io/v1alpha1/clusters": dial tcp 172.18.0.2:32443: connect: connection refused
```

60초 후:

```text
pullx READY=Unknown
Ready=Unknown:ClusterStatusUnknown:Cluster status controller stopped posting cluster status.

demo-pull-mode-nginx member Deployment 2/2 유지
```

판단:

```text
FORWARD 체인 차단은 agent의 Karmada API 접근을 실제로 막았다.
약 60초 후 Cluster READY가 Unknown으로 바뀌었다.
기존 member workload는 계속 Running이었다.
```

---

## 2차 시도 결과 2. 차단 중 desired state 변경

차단 상태에서 Karmada API Server의 replicas를 2에서 3으로 바꿨다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-pull-mode scale deployment demo-pull-mode-nginx --replicas=3
```

즉시 상태:

```text
Karmada API Deployment 2/3
ResourceBinding clusters=pullx:3
ResourceBinding FullyApplied=True
pullx member Deployment 2/2
```

30초 후:

```text
pullx READY=Unknown
Karmada API Deployment 2/3
pullx member Deployment 2/2
agent log connection refused
```

60초 후:

```text
pullx READY=Unknown
Karmada API Deployment 2/3
pullx member Deployment 2/2
```

판단:

```text
네트워크 차단 중 desired state는 Karmada API Server에서 바뀌지만 member cluster에는 반영되지 않았다.
이때 ResourceBinding FullyApplied=True가 유지되어 stale status 가능성이 다시 확인됐다.
```

---

## 2차 시도 결과 3. 네트워크 복구

rule 제거:

```bash
docker exec pullx-control-plane iptables -D FORWARD \
  -s 10.244.0.8 \
  -d 172.18.0.2 \
  -p tcp \
  --dport 32443 \
  -m comment \
  --comment karmada-api-block \
  -j REJECT
```

복구 직후~60초:

```text
rule 없음
pullx READY=Unknown 유지
member Deployment 2/2 유지
```

추가 확인 시점:

```text
pullx READY=True
karmada-agent 1/1 Running
agent Pod restart count=5
logs: Sync work ... successful, Reflect status ... succeed
```

해석:

```text
네트워크 복구 직후 바로 Ready가 True로 돌아오지는 않았다.
agent는 차단 중 여러 번 재시작했고, 복구 후 Work sync/status reflect를 다시 수행하면서 정상 상태로 돌아왔다.
```

---

## 최종 원복

repo manifest 기준 replicas=2로 원복했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-pull-mode/
```

최종 상태:

```text
iptables rule 없음
pullx READY=True
karmada-agent 1/1 Running
demo-pull-mode-nginx 2/2
ResourceBinding clusters=pullx:2
FullyApplied=True
```

---

## 성공/실패 판단

```text
OUTPUT 체인 차단 시도: 실패/관찰 가치 있음
FORWARD 체인 차단 시도: 성공
pullx READY Unknown 전환: 성공
agent log connection refused 확인: 성공
차단 중 desired state 미반영: 성공
기존 workload 유지: 성공
복구 후 READY True 회복: 성공
복구 중 agent restart 발생: 주의 필요
최종 replicas=2 원복: 성공
```

---

## ScaleX-POD에 주는 의미

```text
1. Pull mode 현장망 단절 시 기존 workload는 계속 실행될 수 있다.
2. 단절 중 Tower/Karmada desired state 변경은 member에 즉시 반영되지 않는다.
3. Cluster READY Unknown과 agent log를 함께 봐야 한다.
4. FullyApplied=True는 네트워크 단절 중 stale하게 보일 수 있다.
5. 복구 직후 바로 정상 수렴하지 않을 수 있고 agent restart가 발생할 수 있다.
6. kind/CNI 실험에서는 node OUTPUT이 아니라 Pod egress 경로(FORWARD)를 차단해야 했다.
7. 실제 ScaleX-POD에서는 방화벽/라우팅/프록시 위치별로 차단 지점이 다를 수 있다.
```

---

## 다음 액션

```text
1. Kueue 기초 실험
2. 실제 ScaleX-POD 이전 checklist 작성
3. ArgoCD AppProject migration 실험
4. scheduler-estimator 설치형 실험
```
