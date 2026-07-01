# 실험 32. scheduler-estimator 설치형 실험

## 목적

실험 16에서는 scheduler-estimator 서비스가 없는 상태에서 Karmada scheduler가 반복적으로 dial 실패를 내는 것을 확인하고, lab에서는 estimator를 비활성화했다.

이번 실험은 공식 addon 방식으로 scheduler-estimator를 실제 설치한 뒤 `Divided + Aggregated` scheduling이 정상 동작하는지 확인한다.

확인할 것:

```text
1. Karmada v1.18.0 scheduler-estimator addon을 member cluster별로 설치할 수 있는가?
2. Karmada scheduler가 estimator service와 연결되는가?
3. Aggregated scheduling workload가 정상 배치되는가?
4. kind 단일 노드 lab에서 rollout 이슈가 있는가?
5. 실험 후 원래 비활성화 상태로 안전하게 원복할 수 있는가?
```

---

## 사전 상태

```text
Karmada version: v1.18.0
Karmada scheduler image: docker.io/karmada/karmada-scheduler:v1.18.0
Karmada scheduler-estimator resources: 없음
Karmada scheduler option: --enable-scheduler-estimator=false
member clusters: twinx/edgex/datax/poolx READY=True, pullx READY=True Pull mode
```

확인 명령:

```bash
kubectl --context kind-tower -n karmada-system get deploy karmada-scheduler -o yaml
kubectl --context kind-tower -n karmada-system get deploy,svc,secret | grep scheduler-estimator || true
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusters -o wide
```

---

## 1. 공식 addon 방식 확인

Karmada v1.18.0 CLI help에서 scheduler-estimator addon이 제공됨을 확인했다.

```bash
kubectl-karmada addons enable --help
```

핵심 옵션:

```text
addons enable karmada-scheduler-estimator
-C, --cluster
--member-kubeconfig
--member-context
--karmada-scheduler-estimator-image docker.io/karmada/karmada-scheduler-estimator:v1.18.0
```

공식 manifest template도 확인했다.

```text
Deployment name: karmada-scheduler-estimator-<cluster>
Service name: karmada-scheduler-estimator-<cluster>
Service port: 10352
member kubeconfig secret: <cluster>-kubeconfig
```

주의:

```text
member kubeconfig에는 인증 정보가 들어가므로 repo에 저장하지 않는다.
이번 실험에서는 /tmp에 임시 kubeconfig를 만들고 addon 설치 직후 삭제했다.
```

---

## 2. datax estimator 먼저 설치

`kind-datax` kubeconfig의 server 주소는 local loopback일 수 있으므로, estimator Pod에서 접근 가능한 member API endpoint로 임시 kubeconfig를 바꿔 사용했다.

```bash
tmpcfg=$(mktemp /tmp/datax-estimator.XXXXXX.config)

kubectl config view --raw --minify --context kind-datax > "$tmpcfg"
kubectl --kubeconfig "$tmpcfg" config set-cluster kind-datax \
  --server=https://172.18.0.5:6443

kubectl-karmada addons enable karmada-scheduler-estimator \
  --kubeconfig ~/.kube/config \
  --context kind-tower \
  --karmada-kubeconfig ~/.kube/karmada-apiserver.config \
  -C datax \
  --member-kubeconfig "$tmpcfg" \
  --member-context kind-datax \
  --namespace karmada-system

rm -f "$tmpcfg"
```

결과:

```text
karmada-scheduler-estimator-datax Deployment 1/1
karmada-scheduler-estimator-datax Service 10352/TCP
```

---

## 3. scheduler estimator 활성화

`karmada-scheduler` command를 임시로 변경했다.

```text
--enable-scheduler-estimator=false
```

에서:

```text
--enable-scheduler-estimator=true
--disable-scheduler-estimator-in-pull-mode=true
```

로 변경했다.

Pull mode cluster인 `pullx`에는 estimator를 설치하지 않았으므로 Pull mode estimator 사용은 끄고 Push mode cluster만 대상으로 했다.

---

## 4. kind 단일 노드 rollout 이슈

처음 rollout은 지연됐다.

관찰:

```text
0 out of 1 new replicas have been updated
1 old replica pending termination
new scheduler pod Pending
old scheduler pod Running
```

원인:

```text
karmada-scheduler Deployment는 required podAntiAffinity가 있다.
kind-tower는 단일 노드라 RollingUpdate의 surge pod가 같은 노드에 올라오지 못했다.
```

해결:

```bash
kubectl --context kind-tower -n karmada-system patch deploy karmada-scheduler \
  --type=merge \
  -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":1,"maxSurge":0}}}}'

kubectl --context kind-tower -n karmada-system rollout status \
  deploy/karmada-scheduler --timeout=180s
```

결과:

```text
karmada-scheduler rollout 성공
```

판단:

```text
이 문제는 scheduler-estimator 기능 문제가 아니라 kind 단일 노드 lab과 hard podAntiAffinity 조합의 rollout 문제다.
실제 multi-node Tower에서는 다르게 보일 수 있지만, lab에서는 rollout 전략을 임시 조정해야 했다.
```

---

## 5. twinx/edgex/poolx estimator 추가 설치

기존 `demo-scheduler-estimator` 시나리오가 `twinx/edgex/datax/poolx`를 후보로 쓰기 때문에 Push mode cluster 4개에 estimator를 설치했다.

```bash
for item in \
  twinx=https://172.18.0.3:6443 \
  edgex=https://172.18.0.4:6443 \
  poolx=https://172.18.0.6:6443
do
  cluster=${item%%=*}
  server=${item#*=}
  tmpcfg=$(mktemp "/tmp/${cluster}-estimator.XXXXXX.config")

  kubectl config view --raw --minify --context "kind-${cluster}" > "$tmpcfg"
  kubectl --kubeconfig "$tmpcfg" config set-cluster "kind-${cluster}" \
    --server="$server"

  kubectl-karmada addons enable karmada-scheduler-estimator \
    --kubeconfig ~/.kube/config \
    --context kind-tower \
    --karmada-kubeconfig ~/.kube/karmada-apiserver.config \
    -C "$cluster" \
    --member-kubeconfig "$tmpcfg" \
    --member-context "kind-${cluster}" \
    --namespace karmada-system

  rm -f "$tmpcfg"
done
```

결과:

```text
karmada-scheduler-estimator-twinx 1/1
karmada-scheduler-estimator-edgex 1/1
karmada-scheduler-estimator-datax 1/1
karmada-scheduler-estimator-poolx 1/1
각 Service 10352/TCP 생성
```

---

## 6. scheduler와 estimator 연결 확인

scheduler log에서 estimator service 연결을 확인했다.

대표 결과:

```text
Connection with estimator server karmada-scheduler-estimator-datax ... has been established.
Connection with estimator server karmada-scheduler-estimator-edgex ... has been established.
Connection with estimator server karmada-scheduler-estimator-poolx ... has been established.
Connection with estimator server karmada-scheduler-estimator-twinx ... has been established.
```

설치 전에는 twinx/edgex/poolx estimator service가 없어서 dial 실패가 반복됐고, 설치 후 연결이 성공했다.

---

## 7. Aggregated scheduling 검증

임시 namespace와 Deployment/Service/PropagationPolicy를 적용했다.

테스트 조건:

```text
namespace: demo-scheduler-estimator-install
Deployment: demo-estimator-installed-nginx
replicas: 4
requests: cpu=10m, memory=32Mi
candidate clusters: twinx, edgex, datax, poolx
replicaScheduling: Divided + Aggregated
```

결과:

```text
ResourceBinding Scheduled=True
ResourceBinding FullyApplied=True
Deployment placement result: poolx=4
poolx member Deployment: 4/4 Running
```

Karmada scheduler event:

```text
ScheduleBindingSucceed
Result: {poolx:4}
```

판단:

```text
scheduler-estimator service가 실제로 설치된 상태에서 Aggregated scheduling이 정상 수행됐다.
이번 lab의 균등한 kind cluster 조건에서는 scheduler가 poolx에 4개 replica를 모았다.
중요한 검증 지점은 특정 cluster 선택값보다 estimator 연결 실패 없이 scheduling과 Work 적용이 완료됐다는 점이다.
```

---

## 8. cleanup과 원복

임시 workload 삭제:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config delete \
  -f /tmp/demo-scheduler-estimator-install.yaml \
  --ignore-not-found
```

`karmada-scheduler` 원복:

```text
--enable-scheduler-estimator=false
--disable-scheduler-estimator-in-pull-mode flag 제거
RollingUpdate maxUnavailable/maxSurge 25%로 원복
```

estimator addon 삭제:

```bash
for cluster in twinx edgex datax poolx; do
  kubectl-karmada addons disable karmada-scheduler-estimator \
    --kubeconfig ~/.kube/config \
    --context kind-tower \
    --karmada-kubeconfig ~/.kube/karmada-apiserver.config \
    -C "$cluster" \
    --namespace karmada-system \
    --force
done
```

최종 상태:

```text
karmada-scheduler 1/1
--enable-scheduler-estimator=false
scheduler-estimator Deployment/Service/Secret 없음
demo-scheduler-estimator-install namespace 삭제 완료
```

---

## 성공/실패 판단

```text
공식 addon으로 estimator 설치: 성공
member kubeconfig를 repo에 남기지 않는 방식 확인: 성공
scheduler estimator 연결 확인: 성공
Aggregated scheduling 정상 배치 확인: 성공
kind 단일 노드 scheduler rollout 이슈 발견/해결: 성공
실험 후 estimator 비활성화와 addon 삭제 원복: 성공
```

---

## ScaleX-POD에 주는 의미

```text
1. scheduler-estimator는 Karmada placement를 capacity-aware에 가깝게 만들 때 쓸 수 있다.
2. Push mode member cluster마다 estimator Deployment/Service와 member kubeconfig secret이 필요하다.
3. Pull mode member에는 별도 전략이 필요하므로 우선 --disable-scheduler-estimator-in-pull-mode=true가 안전하다.
4. scheduler-estimator는 설치/인증/rollout 복잡도가 있으므로 기본 운영 필수 요소로 두기보다는 capacity-aware scheduling이 필요한 시점에 켠다.
5. Tower가 단일 노드면 Karmada scheduler hard anti-affinity 때문에 rollout이 막힐 수 있다.
```

---

## 다음 액션

```text
1. 실제 ScaleX-POD에서 estimator를 쓸지 여부는 capacity-aware scheduling 요구가 확정된 뒤 결정한다.
2. 사용한다면 member kubeconfig secret 생성/회전/권한 범위를 운영 runbook으로 만든다.
3. 단일 노드 Tower lab에서는 scheduler rollout 전략 또는 anti-affinity 예외 절차를 문서화한다.
4. Kueue GitOps 배포 구조와 ArgoCD AppProject migration은 별도 후속 작업으로 남긴다.
```
