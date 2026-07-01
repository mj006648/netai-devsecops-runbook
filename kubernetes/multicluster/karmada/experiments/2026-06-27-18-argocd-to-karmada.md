# 실험 18. ArgoCD에서 Karmada API Server로 GitOps sync

## 목적

지금까지의 Karmada 실험은 대부분 `kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply` 방식으로 Karmada API Server에 직접 제출했다.
이번 실험은 Tower의 ArgoCD가 GitHub repo를 읽고, destination cluster를 Karmada API Server로 설정해 ResourceTemplate과 Karmada policy를 sync할 수 있는지 확인한다.

ScaleX-POD 기준 목표 구조:

```text
GitHub repo
  -> ArgoCD on Tower
    -> Karmada API Server on Tower
      -> TwinX / EdgeX / DataX / Resource Pool
```

---

## 가설

```text
ArgoCD에 Karmada API Server를 cluster destination으로 등록하면,
ArgoCD Application이 Git repo의 Kubernetes YAML과 Karmada policy를 Karmada API Server에 sync하고,
Karmada가 기존 PropagationPolicy에 따라 member cluster로 전파할 것이다.
```

---

## 사전 상태

Karmada lab:

```text
host: master
current context: kind-tower
Karmada API kubeconfig: ~/.kube/karmada-apiserver.config
member clusters: twinx, edgex, datax, poolx
member mode: Push
```

ArgoCD 설치 전 상태:

```text
argocd namespace: 없음
argocd CLI: /usr/local/bin/argocd
argocd CLI version: v3.0.6+db93798
helm: v4.2.2
```

Karmada API Server service:

```text
namespace: karmada-system
service  : karmada-apiserver
type     : NodePort
clusterIP: 10.96.112.23
ports    : 5443:32443/TCP
```

ArgoCD controller pod에서 접근할 destination server:

```text
https://karmada-apiserver.karmada-system.svc:5443
```

---

## ArgoCD 설치

CLI 버전에 맞춰 v3.0.6 manifest를 사용했다.

```bash
kubectl --context kind-tower create namespace argocd

kubectl --context kind-tower apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.0.6/manifests/install.yaml
```

적용 결과:

```text
namespace/argocd created
customresourcedefinition.apiextensions.k8s.io/applications.argoproj.io created
customresourcedefinition.apiextensions.k8s.io/applicationsets.argoproj.io created
customresourcedefinition.apiextensions.k8s.io/appprojects.argoproj.io created
...
deployment.apps/argocd-server created
statefulset.apps/argocd-application-controller created
```

Ready 확인:

```bash
kubectl --context kind-tower -n argocd rollout status deploy/argocd-redis --timeout=180s
kubectl --context kind-tower -n argocd rollout status deploy/argocd-repo-server --timeout=180s
kubectl --context kind-tower -n argocd rollout status deploy/argocd-server --timeout=180s
kubectl --context kind-tower -n argocd rollout status deploy/argocd-applicationset-controller --timeout=180s
kubectl --context kind-tower -n argocd rollout status deploy/argocd-dex-server --timeout=180s
kubectl --context kind-tower -n argocd rollout status statefulset/argocd-application-controller --timeout=180s
```

최종 pod 상태:

```text
argocd-application-controller-0                     1/1 Running
argocd-applicationset-controller-787f4cc5bf-zd645   1/1 Running
argocd-dex-server-67677d8f7b-tjzff                  1/1 Running
argocd-notifications-controller-586b4bf99b-5bjk6    1/1 Running
argocd-redis-dd46cfd64-n5gkh                        1/1 Running
argocd-repo-server-6494cbbfc6-mlj96                 1/1 Running
argocd-server-6687649b6c-jqnmj                      1/1 Running
```

---

## Karmada API Server를 ArgoCD destination으로 등록

ArgoCD cluster secret을 `argocd` namespace에 생성했다.
Karmada kubeconfig의 CA, client certificate, client key가 필요하므로 이 secret은 live cluster에만 만들고 repo에는 저장하지 않는다.

생성한 secret:

```text
namespace: argocd
name     : karmada-apiserver-cluster
label    : argocd.argoproj.io/secret-type=cluster
server   : https://karmada-apiserver.karmada-system.svc:5443
```

등록 확인:

```bash
kubectl --context kind-tower -n argocd get secrets \
  -l argocd.argoproj.io/secret-type=cluster
```

결과:

```text
karmada-apiserver-cluster
```

주의:

```text
실제 secret에는 client key가 들어간다.
따라서 레포에는 secret 본문을 저장하지 않는다.
```

---

## ArgoCD Application

레포에 추가한 Application 매니페스트:

```text
kubernetes/multicluster/karmada/argocd/applications/karmada-spread-constraints.yaml
```

내용:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: karmada-spread-constraints
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/mj006648/netai-devsecops-runbook.git
    targetRevision: main
    path: kubernetes/multicluster/karmada/manifests/demo-spread-constraints
  destination:
    server: https://karmada-apiserver.karmada-system.svc:5443
    namespace: demo-spread-constraints
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

이번 실험에서는 이미 main에 올라가 있는 실험 17 source path를 사용했다.

```text
source path: kubernetes/multicluster/karmada/manifests/demo-spread-constraints
```

이유:

```text
ArgoCD는 GitHub remote의 main을 읽기 때문에, 아직 push되지 않은 새 source path는 사용할 수 없다.
이미 main에 있는 매니페스트를 사용하면 ArgoCD sync 자체를 먼저 검증할 수 있다.
```

Application 적용:

```bash
kubectl --context kind-tower apply \
  -f kubernetes/multicluster/karmada/argocd/applications/karmada-spread-constraints.yaml
```

결과:

```text
application.argoproj.io/karmada-spread-constraints created
```

---

## ArgoCD sync 결과

확인 명령:

```bash
kubectl --context kind-tower -n argocd get application karmada-spread-constraints \
  -o jsonpath='sync={.status.sync.status}{" health="}{.status.health.status}{" phase="}{.status.operationState.phase}{" message="}{.status.operationState.message}{" revision="}{.status.sync.revision}{"\n"}'
```

결과:

```text
sync=Synced health=Healthy phase=Succeeded message=successfully synced (all tasks run) revision=3277b3dac3cd837232b5e600f17f17f9aa141f70
```

ArgoCD가 관리한 resource:

```text
Namespace/demo-spread-constraints status=Synced
Service/demo-spread-pool-nginx ns=demo-spread-constraints status=Synced
Deployment/demo-spread-pool-nginx ns=demo-spread-constraints status=Synced
PropagationPolicy/demo-spread-pool-policy ns=demo-spread-constraints status=Synced
```

Application controller 로그에서 확인된 destination:

```text
Comparing app state (cluster: https://karmada-apiserver.karmada-system.svc:5443, namespace: demo-spread-constraints)
```

판단:

```text
ArgoCD가 member cluster가 아니라 Karmada API Server를 destination으로 보고 sync했다.
```

---

## Karmada 전파 결과

Karmada API Server 리소스:

```text
namespace/demo-spread-constraints Active
Deployment/demo-spread-pool-nginx 8/8
Service/demo-spread-pool-nginx ClusterIP
PropagationPolicy/demo-spread-pool-policy
```

ResourceBinding:

```text
datax replicas=1
edgex replicas=3
poolx replicas=1
twinx replicas=3
lastScheduledTime=2026-06-27T10:59:12Z
conditions=Scheduled:True/Success FullyApplied:True/FullyAppliedSuccess
```

member cluster 상태:

```text
twinx: ready=3/3
edgex: ready=3/3
datax: ready=1/1
poolx: ready=1/1
```

판단:

```text
ArgoCD가 Karmada API Server에 sync한 리소스를 Karmada가 기존 PropagationPolicy에 따라 네 member cluster로 전파했다.
```

---

## self-heal 확인

ArgoCD가 Karmada API Server의 drift를 감지하고 Git 상태로 되돌리는지 확인했다.

drift 생성:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-spread-constraints patch deploy demo-spread-pool-nginx \
  --type=json \
  -p='[{"op":"replace","path":"/spec/replicas","value":7}]'
```

즉시 확인:

```text
afterPatchReplicas=7
```

ArgoCD refresh 요청:

```bash
kubectl --context kind-tower -n argocd annotate application karmada-spread-constraints \
  argocd.argoproj.io/refresh=hard \
  --overwrite
```

관찰:

```text
check=1 sync=OutOfSync health=Progressing phase=Running replicas=7
check=2 sync=Synced health=Healthy phase=Succeeded message=successfully synced (all tasks run) replicas=8
```

최종 Karmada Deployment:

```text
replicas=8
```

최종 ResourceBinding:

```text
datax replicas=1
edgex replicas=3
poolx replicas=1
twinx replicas=3
```

Application controller 로그:

```text
Updated sync status: Synced -> OutOfSync
Updated health status: Healthy -> Progressing
Initiated automated sync to '3277b3dac3cd837232b5e600f17f17f9aa141f70'
Applying resource Deployment/demo-spread-pool-nginx in cluster: https://karmada-apiserver.karmada-system.svc:5443, namespace: demo-spread-constraints
Partial sync operation to 3277b3dac3cd837232b5e600f17f17f9aa141f70 succeeded
Updated sync status: OutOfSync -> Synced
Updated health status: Progressing -> Healthy
```

판단:

```text
ArgoCD selfHeal이 Karmada API Server의 Deployment drift를 Git 상태로 되돌렸다.
그 후 Karmada가 다시 ResourceBinding을 갱신하고 member cluster replica 분산을 유지했다.
```

---

## 성공/실패 판단

```text
성공
```

성공 근거:

```text
1. ArgoCD가 kind-tower에 정상 설치됐다.
2. Karmada API Server를 ArgoCD destination cluster로 등록했다.
3. ArgoCD Application이 GitHub repo의 Karmada manifest path를 읽었다.
4. Destination이 member cluster가 아니라 Karmada API Server로 설정됐다.
5. Application이 Synced/Healthy/Succeeded 상태가 됐다.
6. Namespace, Deployment, Service, PropagationPolicy가 ArgoCD managed resource로 표시됐다.
7. Karmada ResourceBinding이 Scheduled=True, FullyApplied=True 상태를 유지했다.
8. member cluster에 twinx=3, edgex=3, datax=1, poolx=1로 전파됐다.
9. Karmada API에서 replicas를 7로 바꾸자 ArgoCD가 self-heal로 Git의 replicas=8로 되돌렸다.
```

---

## 문제/에러

이번 실험에서 기능 실패는 없었다.

주의할 점:

```text
1. ArgoCD cluster secret에는 Karmada client key가 들어가므로 repo에 저장하면 안 된다.
2. ArgoCD Application source는 GitHub remote에 이미 push된 path여야 한다.
3. 이번 실험은 prune=false로 진행했다.
4. delete/prune/rollback은 별도 실험으로 검증해야 한다.
5. Karmada member cluster를 ArgoCD destination으로 직접 등록하지 않았다. 의도적으로 Karmada API Server만 destination으로 사용했다.
```

---

## ScaleX-POD에 주는 의미

이번 실험으로 검증된 운영 흐름:

```text
GitHub repo
  -> ArgoCD on Tower
    -> Karmada API Server on Tower
      -> TwinX / EdgeX / DataX / Resource Pool
```

역할 분리가 명확해졌다.

```text
ArgoCD:
- Git repo 감시
- sync/diff/self-heal
- Karmada API Server에 ResourceTemplate + Policy 제출

Karmada:
- cluster placement
- replica 분산
- OverridePolicy 적용
- member cluster 전파
- WorkloadRebalancer/failover 계열 운영
```

ScaleX-POD 설계 반영:

```text
1. 멀티클러스터 앱은 ArgoCD가 member cluster에 직접 배포하지 않고 Karmada API Server에 제출한다.
2. member cluster 고유 인프라, 예를 들어 StorageClass/CNI/node-local 설정은 필요하면 별도 ArgoCD Application으로 member에 직접 관리할 수 있다.
3. Karmada policy와 workload YAML은 같은 Git source path에서 함께 관리할 수 있다.
4. ArgoCD self-heal은 Karmada API Server의 desired state를 복구하고, Karmada는 그 결과를 member cluster로 다시 전파한다.
```

---

## 다음 액션

```text
1. prune/delete/rollback 동작 검증
2. Pull mode member cluster 등록 실험
3. ArgoCD ApplicationSet으로 여러 Karmada app 관리 실험
4. Kueue와 Karmada 역할 분리 실험
```
