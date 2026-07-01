# 실험 21. Pull mode karmada-agent 중단/복구

## 목적

실험 20에서 `pullx`를 Pull mode member cluster로 등록하고, `karmada-agent` 기반 workload 전파가 동작하는 것을 확인했다.
이번 실험은 Pull mode의 핵심 구성인 `karmada-agent`가 중단됐을 때 어떤 상태가 보이고, 복구 후 밀린 desired state가 실제 member cluster에 반영되는지 확인한다.

ScaleX-POD 기준으로는 다음 상황을 축소 검증한다.

```text
EdgeX 계열 cluster의 agent 장애
현장망 단절과 유사한 agent heartbeat 중단
agent 복구 후 Tower/Karmada desired state 재반영
```

---

## 가설

```text
1. pullx의 karmada-agent를 중단하면 일정 시간 뒤 Cluster READY가 Unknown으로 바뀐다.
2. agent가 중단돼도 이미 실행 중인 member workload는 계속 돈다.
3. agent 중단 중 Karmada API Server에서 desired state를 바꾸면 member cluster에는 즉시 반영되지 않는다.
4. agent를 복구하면 밀린 desired state가 pullx에 반영된다.
```

---

## 사용한 workload

새 manifest를 만들지 않고 실험 20의 `demo-pull-mode` workload를 재사용했다.

```text
namespace : demo-pull-mode
Deployment: demo-pull-mode-nginx
Service   : demo-pull-mode-nginx
기본 replicas: 2
대상 cluster: pullx, Pull mode
```

매니페스트 위치:

```text
kubernetes/multicluster/karmada/manifests/demo-pull-mode/
```

---

## 사전 상태

Repo 상태:

```text
main...origin/main clean
최근 커밋: c986d8d Add Karmada pull mode experiment
```

현재 context:

```text
kind-tower
```

`pullx` 상태:

```text
NAME    VERSION   MODE   READY   API-ENDPOINT              LABELS
pullx   v1.34.0   Pull   True    https://127.0.0.1:37785   scalex.io/connectivity=pull,scalex.io/location=edge,scalex.io/pool=edge-pull,scalex.io/role=pull-edge
```

`karmada-agent` 상태:

```text
deployment.apps/karmada-agent 1/1
pod/karmada-agent-68457f4dd6-v65wl Running
```

workload 상태:

```text
Karmada API Server Deployment/demo-pull-mode-nginx 2/2
pullx Deployment/demo-pull-mode-nginx 2/2
pullx Pod 2개 Running
ResourceBinding Scheduled=True FullyApplied=True
```

---

## 단계 1. karmada-agent 중단

```bash
kubectl --context kind-pullx -n karmada-system scale deployment karmada-agent --replicas=0
kubectl --context kind-pullx -n karmada-system rollout status deployment/karmada-agent --timeout=60s || true
```

결과:

```text
deployment.apps/karmada-agent scaled
deployment "karmada-agent" successfully rolled out
```

즉시 상태:

```text
deployment.apps/karmada-agent 0/0
pod/karmada-agent-... Terminating
pullx READY=True
Deployment/demo-pull-mode-nginx 2/2
Pod 2개 Running
```

15초 후:

```text
deployment.apps/karmada-agent 0/0
pullx READY=True
Deployment/demo-pull-mode-nginx 2/2
Pod 2개 Running
```

30초 후:

```text
pullx READY=Unknown
Ready=Unknown:ClusterStatusUnknown:Cluster status controller stopped posting cluster status.
Deployment/demo-pull-mode-nginx 2/2
Pod 2개 Running
```

60초 후:

```text
pullx READY=Unknown
Ready=Unknown:ClusterStatusUnknown:Cluster status controller stopped posting cluster status.
Deployment/demo-pull-mode-nginx 2/2
Pod 2개 Running
```

판단:

```text
agent 중단 후 약 30초 시점에 Karmada Cluster 상태가 Unknown으로 바뀌었다.
하지만 이미 pullx에 생성된 workload는 계속 Running 상태였다.
```

---

## 단계 2. agent 중단 중 desired state 변경

agent가 내려가 있는 상태에서 Karmada API Server의 Deployment replicas를 2에서 4로 늘렸다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config \
  -n demo-pull-mode scale deployment demo-pull-mode-nginx --replicas=4
```

결과:

```text
deployment.apps/demo-pull-mode-nginx scaled
```

즉시 상태:

```text
Karmada API Deployment/demo-pull-mode-nginx READY 2/4
ResourceBinding spec.replicas=4
ResourceBinding target pullx replicas=4
ResourceBinding Scheduled=True
ResourceBinding FullyApplied=True
Work Applied=True
pullx Deployment/demo-pull-mode-nginx 2/2
pullx Pod 2개 Running
```

20초 후:

```text
Karmada API Deployment/demo-pull-mode-nginx READY 2/4
ResourceBinding spec.replicas=4
ResourceBinding FullyApplied=True
Work Applied=True
pullx Deployment/demo-pull-mode-nginx 2/2
pullx Pod 2개 Running
```

40초 후:

```text
Karmada API Deployment/demo-pull-mode-nginx READY 2/4
ResourceBinding spec.replicas=4
ResourceBinding FullyApplied=True
Work Applied=True
pullx Deployment/demo-pull-mode-nginx 2/2
pullx Pod 2개 Running
```

중요 관찰:

```text
agent가 중단된 동안 Karmada API Server의 desired state는 replicas=4로 바뀌었다.
하지만 pullx 실제 Deployment는 계속 replicas=2였다.
이때 ResourceBinding FullyApplied=True와 Work Applied=True가 유지됐다.
따라서 agent 장애 상황에서는 FullyApplied/Applied만 보고 실제 member 반영 완료라고 판단하면 위험하다.
Cluster READY=Unknown, Karmada API aggregated status, member cluster 실제 상태를 같이 봐야 한다.
```

---

## 단계 3. karmada-agent 복구

```bash
kubectl --context kind-pullx -n karmada-system scale deployment karmada-agent --replicas=1
kubectl --context kind-pullx -n karmada-system rollout status deployment/karmada-agent --timeout=120s
```

결과:

```text
deployment.apps/karmada-agent scaled
deployment "karmada-agent" successfully rolled out
```

복구 직후:

```text
deployment.apps/karmada-agent 1/1
pod/karmada-agent-68457f4dd6-qvgq4 Running
pullx READY=Unknown
Karmada API Deployment/demo-pull-mode-nginx 2/4
pullx Deployment/demo-pull-mode-nginx 2/2
```

15초 후:

```text
pullx READY=Unknown
Karmada API Deployment/demo-pull-mode-nginx 2/4
pullx Deployment/demo-pull-mode-nginx 2/2
```

30초 후:

```text
pullx READY=True
Ready=True:ClusterReady:cluster is healthy and ready to accept workloads
Karmada API Deployment/demo-pull-mode-nginx 4/4
pullx Deployment/demo-pull-mode-nginx 4/4
pullx Pod 4개 Running
```

60초 후:

```text
pullx READY=True
Karmada API Deployment/demo-pull-mode-nginx 4/4
pullx Deployment/demo-pull-mode-nginx 4/4
pullx Pod 4개 Running
```

판단:

```text
agent 복구 후 약 30초 안에 pullx Cluster READY가 True로 돌아왔다.
agent 중단 중 변경한 replicas=4 desired state도 pullx에 반영됐다.
```

---

## 단계 4. repo manifest 기준으로 원복

실험 20의 repo manifest 기준 replicas는 2이므로 다시 적용했다.

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply \
  -f kubernetes/multicluster/karmada/manifests/demo-pull-mode/
```

결과:

```text
namespace/demo-pull-mode unchanged
clusterpropagationpolicy.policy.karmada.io/demo-pull-mode-namespace-policy unchanged
deployment.apps/demo-pull-mode-nginx configured
service/demo-pull-mode-nginx unchanged
propagationpolicy.policy.karmada.io/demo-pull-mode-nginx-policy configured
```

즉시 상태:

```text
Karmada API Deployment/demo-pull-mode-nginx 4/2
pullx Deployment/demo-pull-mode-nginx 2/2
추가 Pod 2개 Terminating
pullx READY=True
```

15초 후:

```text
Karmada API Deployment/demo-pull-mode-nginx 2/2
pullx Deployment/demo-pull-mode-nginx 2/2
Pod 2개 Running
pullx READY=True
```

최종 상태:

```text
ResourceBinding spec.replicas=2
ResourceBinding target pullx replicas=2
ResourceBinding Scheduled=True
ResourceBinding FullyApplied=True
Work Dispatching=True
Work Applied=True
pullx Deployment/demo-pull-mode-nginx 2/2
pullx Cluster READY=True
```

---

## agent 로그 관찰

복구 후 `karmada-agent` 로그에서 Work 동기화와 status 반영이 확인됐다.

```text
Sync work(karmada-es-pullx/demo-pull-mode-nginx-7c6587574f) to cluster(pullx) successful.
Successfully applied resource(demo-pull-mode/demo-pull-mode-nginx) to cluster pullx
Reflect status for object(Deployment/demo-pull-mode/demo-pull-mode-nginx) succeed.
Interpret health of object(Deployment/demo-pull-mode/demo-pull-mode-nginx) as healthy.
```

중간에 일시적인 update conflict도 있었다.

```text
Failed to update resource(kind=Deployment, demo-pull-mode/demo-pull-mode-nginx) in cluster pullx,
err: Operation cannot be fulfilled on deployments.apps "demo-pull-mode-nginx":
the object has been modified; please apply your changes to the latest version and try again.
```

판단:

```text
복구 중 Kubernetes object update conflict가 한 번 보였지만, 이후 재시도되어 최종 상태는 정상 Healthy가 됐다.
운영 문서에는 agent 복구 직후 일시적인 conflict/error 로그가 있을 수 있음을 남겨야 한다.
```

---

## 성공/실패 판단

```text
agent scale-down으로 Pull mode 장애 상황 만들기: 성공
약 30초 후 pullx READY=Unknown 관찰: 성공
agent 중단 중 기존 workload 유지 확인: 성공
agent 중단 중 desired state 변경이 member에 즉시 반영되지 않음 확인: 성공
agent 복구 후 desired state 반영 확인: 성공
repo manifest 기준 replicas=2 원복 확인: 성공
복구 중 일시적인 update conflict 로그 관찰: 주의 필요
```

---

## ScaleX-POD에 주는 의미

```text
1. Pull mode cluster는 agent가 끊기면 control plane 관점에서 Unknown이 된다.
2. 이미 실행 중인 member workload는 agent 장애만으로 바로 죽지 않는다.
3. agent 장애 중 Tower/Karmada API Server에 쌓인 desired state는 member에 즉시 반영되지 않는다.
4. agent가 복구되면 밀린 desired state를 다시 가져와 반영할 수 있다.
5. 장애 중에는 FullyApplied/Applied status가 stale하게 보일 수 있으므로 member 실제 상태와 Cluster READY를 함께 봐야 한다.
6. EdgeX 같은 현장 cluster에는 karmada-agent heartbeat/Ready Unknown 알림이 필요하다.
7. 복구 직후 일시적인 update conflict는 재시도 가능성이 있으므로 최종 Healthy 여부까지 확인해야 한다.
```

---

## 운영 checklist 초안

Pull mode cluster 운영 시 최소 확인 항목:

```text
1. Cluster READY가 True인지 확인
2. karmada-agent Deployment가 1/1인지 확인
3. Karmada API Server의 ResourceBinding/Work 상태 확인
4. member cluster의 실제 Deployment/Pod 상태 확인
5. READY=Unknown이면 desired state 변경이 지연될 수 있다고 판단
6. agent 복구 후 최소 30~60초 동안 상태 수렴 확인
7. 복구 후 agent 로그에서 반복 error가 남는지 확인
```

---

## 다음 액션

```text
1. 신규 cluster label 영향 범위 checklist 작성
2. Pull mode + WorkloadRebalancer 재균형 실험
3. 더 강한 장애 실험: agent scale-down이 아니라 네트워크 단절 또는 API endpoint 접근 실패 상황 검증
4. ArgoCD ApplicationSet으로 Pull/Push workload를 함께 관리하는 구조 실험
```
