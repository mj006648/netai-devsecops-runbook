# 실험 20. Pull mode member cluster 등록과 workload 전파

## 목적

지금까지의 member cluster는 모두 Push mode였다.
이번 실험은 Pull mode member cluster를 새로 붙이고, Karmada API Server에 제출한 workload가 member cluster 내부의 `karmada-agent`를 통해 실제로 생성되는지 확인한다.

ScaleX-POD 기준으로는 다음 상황을 검증한다.

```text
Tower / Karmada control plane
  -> 직접 member API endpoint로 접근하기 어려운 Edge 계열 cluster
  -> member 내부 agent가 Karmada API Server로 접속해서 work를 가져감
```

특히 EdgeX처럼 NAT, 방화벽, 현장망 제약이 있는 cluster 후보에 Pull mode가 맞는지 판단하기 위한 기초 실험이다.

---

## 가설

```text
Pull mode로 등록된 cluster는 Cluster MODE가 Pull로 표시된다.
member cluster에는 karmada-agent Deployment가 생성된다.
Karmada API Server에 ResourceTemplate과 PropagationPolicy를 제출하면,
control plane이 member API로 직접 push하지 않아도 agent가 work를 가져가 workload를 생성한다.
```

---

## 사전 상태

기존 member cluster:

```text
NAME    MODE   READY   핵심 label
twinx   Push   True    scalex.io/role=gpu-render, scalex.io/pool=gpu
edgex   Push   True    scalex.io/role=edge-gpu, scalex.io/pool=gpu, scalex.io/location=edge
datax   Push   True    scalex.io/role=data, scalex.io/pool=data
poolx   Push   True    scalex.io/role=resource-pool, scalex.io/pool=general
```

Karmada CLI 확인:

```bash
kubectl karmada --help
kubectl karmada register --help
kubectl karmada token create --help
```

확인한 내용:

```text
join     : Push mode cluster 등록
register : Pull mode cluster 등록
unregister: Pull mode cluster 제거
token    : bootstrap token 생성
```

---

## 단계 1. Pull mode용 kind cluster 생성

새 member cluster 이름은 `pullx`로 잡았다.

```bash
kind create cluster --name pullx
```

결과:

```text
Creating cluster "pullx" ...
Set kubectl context to "kind-pullx"
```

주의:

```text
kind create cluster 실행 후 kubectl current-context가 kind-pullx로 바뀐다.
Karmada control plane 작업을 계속할 때는 context를 다시 확인해야 한다.
```

---

## 단계 2. Karmada API endpoint 확인

Karmada API Server kubeconfig의 server 값을 확인했다.

```bash
kubectl config view \
  --kubeconfig ~/.kube/karmada-apiserver.config \
  --minify \
  -o jsonpath='{.clusters[0].cluster.server}{"\n"}'
```

결과:

```text
https://172.18.0.2:32443
```

Pull mode register 명령에는 scheme을 빼고 다음 endpoint를 사용했다.

```text
172.18.0.2:32443
```

---

## 단계 3. bootstrap token 생성과 Pull mode 등록

bootstrap token은 출력과 문서에 남기지 않고 즉시 register에 사용했다.

```bash
register_cmd=$(kubectl karmada \
  --kubeconfig ~/.kube/karmada-apiserver.config \
  token create \
  --print-register-command)

# 문서화할 때 token/hash는 반드시 redaction 처리
# kubectl karmada register 172.18.0.2:32443 --token <redacted> --discovery-token-ca-cert-hash sha256:<redacted>

kubectl karmada register 172.18.0.2:32443 \
  --kubeconfig ~/.kube/config \
  --context kind-pullx \
  --cluster-name pullx \
  --token <redacted> \
  --discovery-token-ca-cert-hash sha256:<redacted>
```

결과:

```text
[preflight] Running pre-flight checks
[preflight] All pre-flight checks were passed
[karmada-agent-start] Waiting to perform the TLS Bootstrap
[karmada-agent-start] Waiting to check cluster exists
[karmada-agent-start] Assign the necessary RBAC permissions to the agent
[karmada-agent-start] Waiting to construct karmada-agent kubeconfig
[karmada-agent-start] Waiting the necessary secret and RBAC
[karmada-agent-start] Waiting karmada-agent Deployment

cluster(pullx) is joined successfully
```

---

## 단계 4. ScaleX-POD label 부여

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config label cluster pullx \
  scalex.io/role=pull-edge \
  scalex.io/pool=edge-pull \
  scalex.io/location=edge \
  scalex.io/connectivity=pull \
  --overwrite
```

결과:

```text
cluster.cluster.karmada.io/pullx labeled
```

Cluster 상태:

```text
NAME    VERSION   MODE   READY   API-ENDPOINT              LABELS
pullx   v1.34.0   Pull   True    https://127.0.0.1:37785   scalex.io/connectivity=pull,scalex.io/location=edge,scalex.io/pool=edge-pull,scalex.io/role=pull-edge
```

관찰:

```text
pullx의 API-ENDPOINT는 127.0.0.1 host port 형태로 보인다.
Tower 내부 control plane에서 이 endpoint로 직접 접근할 수 있는 구조가 아니어도,
Pull mode에서는 member 내부 agent가 Karmada API Server로 붙기 때문에 workload 전파가 가능했다.
```

---

## 단계 5. pullx 내부 agent 확인

```bash
kubectl --context kind-pullx -n karmada-system get deploy,pods,sa,secret
```

결과:

```text
NAME                            READY   UP-TO-DATE   AVAILABLE
deployment.apps/karmada-agent   1/1     1            1

NAME                                 READY   STATUS    RESTARTS
pod/karmada-agent-68457f4dd6-v65wl   1/1     Running   0

NAME                              SECRETS
serviceaccount/default            0
serviceaccount/karmada-agent-sa   0

NAME                        TYPE     DATA
secret/karmada-kubeconfig   Opaque   1
```

판단:

```text
Pull mode 등록은 member cluster 안에 karmada-agent와 kubeconfig secret을 만든다.
이 agent가 Karmada API Server에서 work를 가져가는 핵심 구성이다.
```

---

## 단계 6. Pull mode 전용 workload 적용

매니페스트 위치:

```text
kubernetes/karmada/manifests/demo-pull-mode/
  00-namespace.yaml
  01-cluster-propagation-policy-namespace.yaml
  10-deployment.yaml
  20-service.yaml
  30-propagation-policy.yaml
```

핵심 policy:

```yaml
placement:
  clusterAffinity:
    labelSelector:
      matchLabels:
        scalex.io/connectivity: pull
  replicaScheduling:
    replicaSchedulingType: Divided
    replicaDivisionPreference: Weighted
    weightPreference:
      staticWeightList:
        - targetCluster:
            labelSelector:
              matchLabels:
                scalex.io/role: pull-edge
          weight: 1
```

적용:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/karmada/manifests/demo-pull-mode/
```

결과:

```text
namespace/demo-pull-mode created
clusterpropagationpolicy.policy.karmada.io/demo-pull-mode-namespace-policy created
deployment.apps/demo-pull-mode-nginx created
service/demo-pull-mode-nginx created
propagationpolicy.policy.karmada.io/demo-pull-mode-nginx-policy created
```

---

## 단계 7. Karmada API Server 상태 확인

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-pull-mode get deploy,svc,propagationpolicy,rb -o wide
```

결과:

```text
Deployment/demo-pull-mode-nginx 2/2
Service/demo-pull-mode-nginx ClusterIP
PropagationPolicy/demo-pull-mode-nginx-policy
ResourceBinding/demo-pull-mode-nginx-deployment Scheduled=True FullyApplied=True
ResourceBinding/demo-pull-mode-nginx-service    Scheduled=True FullyApplied=True
```

Work 확인:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get work -A | grep pullx
```

관련 결과:

```text
karmada-es-pullx   demo-pull-mode-6cb4ff7484           Namespace    True
karmada-es-pullx   demo-pull-mode-nginx-76bdc864cc     Service      True
karmada-es-pullx   demo-pull-mode-nginx-7c6587574f     Deployment   True
```

---

## 단계 8. pullx 실제 workload 확인

```bash
kubectl --context kind-pullx -n demo-pull-mode get deploy,rs,pods,svc -o wide
```

결과:

```text
Deployment/demo-pull-mode-nginx 2/2
ReplicaSet/demo-pull-mode-nginx-6dbbdb6758 desired=2 current=2 ready=2
Pod/demo-pull-mode-nginx-6dbbdb6758-4r5hc Running Ready 1/1
Pod/demo-pull-mode-nginx-6dbbdb6758-7czvk Running Ready 1/1
Service/demo-pull-mode-nginx ClusterIP 80/TCP
```

다른 Push mode cluster 확인:

```bash
kubectl --context kind-twinx -n demo-pull-mode get all
kubectl --context kind-edgex -n demo-pull-mode get all
kubectl --context kind-datax -n demo-pull-mode get all
kubectl --context kind-poolx -n demo-pull-mode get all
```

결과:

```text
No resources found in demo-pull-mode namespace.
No resources found in demo-pull-mode namespace.
No resources found in demo-pull-mode namespace.
No resources found in demo-pull-mode namespace.
```

판단:

```text
demo-pull-mode workload는 Pull mode cluster인 pullx에만 생성됐다.
Karmada API Server에 제출한 resource가 Pull mode agent를 통해 member cluster에 반영되는 것을 확인했다.
```

---

## 추가 관찰 1. 새 cluster 등록 직후 기존 namespace가 많이 생성됨

`pullx`를 등록하자 기존 demo namespace들이 `pullx`에도 생성됐다.

예시:

```text
namespace/demo
namespace/demo-argocd-prune-rollback
namespace/demo-cluster-failover
namespace/demo-failover
namespace/demo-multi-rebalance
namespace/demo-scalex-role
namespace/demo-spread-constraints
namespace/demo-twinx
namespace/demo-weighted
...
```

Karmada API Server의 Work에도 namespace work가 다수 생성됐다.

```text
karmada-es-pullx   demo-6654f4c4f6                         Namespace   True
karmada-es-pullx   demo-argocd-prune-rollback-7d5b6f9cdc   Namespace   True
karmada-es-pullx   demo-scalex-role-8847cb496              Namespace   True
...
```

판단:

```text
이전 실험 01/02에서 확인했던 namespace 자동 전파 특성이 새 member cluster 등록 시점에도 다시 나타났다.
workload가 선택되지 않아도 namespace만 먼저 생길 수 있으므로, 운영에서는 namespace propagation 정책과 cleanup 기준을 따로 설계해야 한다.
```

---

## 추가 관찰 2. broad label이 기존 policy와 바로 매칭될 수 있음

`pullx`에 다음 label을 붙였다.

```text
scalex.io/location=edge
```

기존 `demo-scalex-edge-policy`는 같은 label을 selector로 사용하고 있었다.

```yaml
clusterAffinity:
  labelSelector:
    matchLabels:
      scalex.io/location: edge
```

그 결과 기존 edge demo Service가 `pullx`에도 전파됐다.

```text
kind-pullx / demo-scalex-role / service/demo-scalex-edge-nginx present
```

ResourceBinding 상태:

```text
Service binding clusters: edgex, pullx
Deployment binding clusters: edgex
```

해석:

```text
Service처럼 replica가 없는 resource는 새로 매칭된 cluster에 추가 전파됐다.
반면 기존 replica workload Deployment는 자동으로 재분산되지 않고 edgex에 남았다.
새 cluster를 추가하거나 label을 부여할 때 기존 labelSelector policy가 의도치 않게 확장될 수 있다.
replica workload까지 재균형하려면 WorkloadRebalancer 같은 별도 절차가 필요하다.
```

운영 의미:

```text
ScaleX-POD label은 너무 넓게 잡으면 신규 cluster가 기존 policy에 즉시 편입된다.
예: scalex.io/location=edge 하나만으로 운영 workload를 선택하지 말고,
scalex.io/pool, scalex.io/role, scalex.io/connectivity, workload tier label을 조합하는 편이 안전하다.
```

---

## 성공/실패 판단

```text
Pull mode cluster 등록: 성공
karmada-agent 생성/Running: 성공
Pull mode cluster label placement: 성공
Karmada API Server -> pullx workload 전파: 성공
다른 Push mode cluster로 demo-pull-mode workload가 새지 않음: 성공
기존 namespace 자동 생성 관찰: 주의 필요
broad label이 기존 policy에 매칭되는 현상 관찰: 주의 필요
```

---

## ScaleX-POD에 주는 의미

```text
1. Pull mode는 EdgeX처럼 inbound 접근이 어려운 cluster에 적합하다.
2. Tower의 ArgoCD/Karmada API Server에는 기존처럼 ResourceTemplate과 Policy를 제출하면 된다.
3. member 쪽에는 karmada-agent가 있어야 하고, agent가 Tower의 Karmada API endpoint로 나갈 수 있어야 한다.
4. 신규 cluster 등록 전 label 설계를 먼저 해야 한다.
5. broad label을 붙이면 기존 policy가 바로 확장될 수 있으므로 운영 label과 실험 label을 분리해야 한다.
6. 기존 replica workload의 자동 재분산은 기대하지 말고 WorkloadRebalancer 절차를 별도로 둔다.
```

---

## 다음 액션

```text
1. 신규 cluster 등록 후 기존 policy 영향 범위를 점검하는 checklist 작성
2. WorkloadRebalancer로 pullx까지 기존 edge replica workload를 재분산할 수 있는지 실험
3. Pull mode cluster의 agent 장애, network 단절, 복구 시 workload/status 변화 확인
4. ArgoCD ApplicationSet으로 여러 Karmada app을 묶어 관리하는 구조 실험
```
