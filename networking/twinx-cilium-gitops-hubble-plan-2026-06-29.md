# TwinX Cilium GitOps 및 Hubble 운영 기록 2026-06-29

## 현재 상태 2026-07-01

현재 운영 기준 결론은 다음과 같다.

- TwinX Cilium은 ArgoCD child `Application/cilium`으로 GitOps ownership을 넘겼다.
- Hubble relay와 Hubble metrics는 활성화됐다.
- `hubble-relay`는 `1/1 Running`이며, Cilium agent peer 연결도 성공했다.
- Cilium `1.17.3` chart가 relay `hostNetwork` 값을 직접 렌더링하지 않아, live `hubble-relay` Deployment에 `hostNetwork=true`, `dnsPolicy=ClusterFirstWithHostNet`를 패치했다.
- TwinX-Ops PR #224로 ArgoCD가 위 hostNetwork/dnsPolicy 패치를 되돌리지 않도록 `ignoreDifferences`와 `RespectIgnoreDifferences=true`를 추가했다.
- Hubble UI, 외부 LoadBalancer, Ingress/Gateway 노출은 아직 하지 않았다.
- `Application/cilium`은 edgebox3/4 전원 장애 때문에 `OutOfSync/Progressing`처럼 보일 수 있지만, Hubble relay 자체는 정상이다.

## 문서 읽는 법

- 급하게 현재 상태만 보려면 **현재 상태 2026-07-01**과 **2026-07-01 Hubble live sync 및 relay 복구 결과**를 먼저 본다.
- `작업 기록`은 실제로 어떤 순서로 변경했는지 남긴 기록이다.
- `참고: 배경과 원래 계획` 아래 내용은 왜 이런 방향을 택했는지 설명하는 설계/계획 자료다. 최신 상태와 다를 수 있는 과거 계획은 별도로 표시했다.

## 문서 목적

이 문서는 TwinX 클러스터의 Cilium을 Kubespray 설치 상태에서 ArgoCD GitOps 관리로 넘기고, Hubble relay/metrics를 활성화한 과정을 기록한다.

처음에는 전환 계획서로 시작했지만, 2026-07-01 작업 후에는 아래 내용을 함께 담는 운영 기록이 됐다.

- DataX-Ops와 TwinX Cilium 설정 차이
- Cilium GitOps ownership 전환 기준
- Hubble relay/metrics 활성화 절차
- `hubble-relay`가 `NOT_SERVING`이 된 원인과 복구 방법
- ArgoCD가 relay `hostNetwork/dnsPolicy` 패치를 되돌리지 않도록 한 설정
- edgebox3/4 전원 장애로 인해 Cilium Application health가 `Progressing`으로 보일 수 있는 known exception

앞으로 Cilium version upgrade, Hubble UI 노출, LoadBalancer/Ingress 노출은 이 문서의 후속 작업을 기준으로 별도 문서나 별도 작업 기록에서 진행한다.

## 작업 기록

### 2026-07-01 결정 사항

edgebox3/4는 Kubernetes 설정 문제가 아니라 SYS-210P-FRDN6T DC 전원 공급 계통 문제로 판단된다. 따라서 Cilium 계획은 edgebox 전원 복구를 기다리되, 복구 전에도 안전한 준비 작업은 진행할 수 있다.

오늘 기준 방향은 다음과 같다.

1. Kubespray로 Cilium/Hubble을 변경하지 않는다.
   - 현재 Kubespray v2.31 기본 Cilium 값은 `1.19.3`이다.
   - live Cilium은 `1.17.3`이므로, Kubespray를 실행하면 Hubble enable과 Cilium version upgrade가 섞일 위험이 있다.

2. TwinX-Ops `argocd/twinx-infra` 아래에 Cilium app과 `values.yaml`을 준비한다.
   - 처음에는 `enabled: false`로 둔다.
   - chart `targetRevision`은 live와 같은 `1.17.3`으로 고정한다.
   - values는 현재 Helm release의 동작을 유지하도록 작성한다.
   - Hubble은 아직 disabled로 둔다.
   - `syncPolicy.automated: false`를 지원하도록 app template을 보완해, Cilium을 나중에 enabled로 전환해도 자동 sync/prune/selfHeal이 걸리지 않게 한다.

3. ArgoCD ownership 전환은 기능 변경 없이 별도 승인 후 진행한다.
   - 전환 시점에는 ArgoCD diff를 먼저 확인한다.
   - sync 전후에 Cilium DaemonSet, operator, CoreDNS, Kubernetes service 접근을 확인한다.
   - edgebox3/4가 계속 전원 장애 상태라면 `10 desired / 8 ready` 같은 Cilium DaemonSet 상태를 known exception으로 기록하고, 살아 있는 노드 기준 검증 명령을 별도로 사용한다.

4. Hubble은 GitOps ownership 전환이 안정화된 뒤 별도 커밋/승인으로 켠다.
   - 1차 Hubble 범위는 relay와 metrics만이다.
   - UI, Gateway API, L2 announcement, native routing, kube-proxy replacement는 별도 계획으로 분리한다.

5. Cilium version upgrade는 Hubble enable과 분리한다.
   - 필요하면 ArgoCD에서 chart `targetRevision`만 단계적으로 올린다.
   - 권장 순서는 `1.17.3` 유지 → Hubble 안정화 → `1.18.x` → `1.19.x` 검토다.

### 2026-07-01 진행 결과

오늘은 실제 Cilium 리소스를 건드리지 않고, TwinX-Ops와 runbook에 GitOps 전환 준비만 반영했다.

- TwinX-Ops PR #219에서 live Cilium `1.17.3` Helm values를 기준으로 `argocd/twinx-infra/apps/cilium/values.yaml`을 추가하고, Cilium app scaffold를 `enabled: false`로 넣었다.
- TwinX-Ops PR #220에서 `argocd/twinx-infra` Application template이 `syncPolicy.automated: false`를 지원하도록 바꿨다. 이 값이 있으면 child Application에는 `automated` sync가 렌더링되지 않는다.
- TwinX-Ops PR #221에서 `applications.cilium.enabled`를 `true`로 바꿨다. 다만 root app인 `twinx-infra-root-app` 자체가 manual sync 상태이므로, merge만으로 live cluster에 `Application/cilium`은 생성되지 않았다.
- merge 후 확인 결과 root app `twinx-infra-root-app`은 최신 revision `f72ee1e`를 보고 `OutOfSync/Healthy` 상태다.
- live `argocd` namespace에는 아직 `Application/cilium`이 없고, 기존 Cilium Helm release는 계속 `1.17.3`으로 동작 중이다.
- Cilium DaemonSet은 `10 desired / 8 ready / 8 available` 상태이며, 부족한 2개는 edgebox3/4 전원 장애에 따른 known exception이다.

따라서 다음 실제 단계는 `twinx-infra-root-app` 수동 sync다. 이 sync의 목표는 **manual child `Application/cilium`을 생성하는 것**이며, child Cilium app sync나 Hubble enable은 아직 진행하지 않는다. 이 단계도 작업 전 상태 보고와 명시 승인을 받은 뒤에만 진행한다.

### 2026-07-01 실제 반영 결과

사용자 승인 후 `Application/cilium` 생성 단계만 진행했다. 작업 서버에 `argocd` CLI가 없어 root app 전체 sync 대신 TwinX-Ops `argocd/twinx-infra` chart를 로컬에서 렌더링하고, 생성된 `Application/cilium` manifest만 `kubectl apply`로 적용했다. 이 방식은 root app sync가 만들 대상 중 Cilium child Application 하나만 생성하므로 적용 범위를 더 좁게 제한한다.

적용 결과는 다음과 같다.

- `Application/cilium`이 `argocd` namespace에 생성됐다.
- child app `spec.syncPolicy.automated`는 비어 있고, syncOptions만 있다.
- child app operation은 비어 있어 실제 Cilium sync는 수행되지 않았다.
- child app 상태는 `OutOfSync/Progressing`이다. 이는 Cilium chart 리소스가 아직 child app에 의해 sync되지 않았기 때문에 정상적인 대기 상태다.
- root app `twinx-infra-root-app`은 `OutOfSync/Healthy`이며, out-of-sync resource는 child `Application/cilium`이다.
- live Cilium Helm release는 기존 `1.17.3`, revision `11` 그대로다.
- live Cilium DaemonSet은 `10 desired / 8 ready / 8 available` 그대로이며, edgebox3/4 전원 장애는 known exception이다.

다음 단계는 child `Application/cilium` diff 확인이다. 실제 child app sync, Cilium Helm 적용, Hubble enable은 별도 상태 보고와 명시 승인을 받은 뒤에만 진행한다.

### 2026-07-01 diff 확인 및 보정 결과

child `Application/cilium` 생성 후 diff를 확인했다. live Helm values와 Git values는 `COMPUTED VALUES:` 헤더를 제외하면 동일했지만, chart render 결과가 live manifest와 일부 달랐다.

처음 확인된 차이는 다음과 같다.

- `k8sServiceHost` / `k8sServicePort`가 Git values에서는 `auto`로 렌더링되어 live의 `10.38.38.9:6443`과 달랐다.
- Cilium agent DaemonSet의 기존 수동 rollout annotation `kubectl.kubernetes.io/restartedAt: "2026-04-08T03:27:35Z"`가 Git render에는 없어 pod template diff가 발생했다.

이 차이는 child app sync 시 불필요한 Cilium rollout을 만들 수 있으므로, TwinX-Ops PR #222에서 live manifest와 맞도록 values를 보정했다.

- `k8sServiceHost: 10.38.38.9`
- `k8sServicePort: 6443`
- root-level `podAnnotations`에 기존 `kubectl.kubernetes.io/restartedAt` 보존

보정 후 검증 결과는 다음과 같다.

- `helm template cilium cilium/cilium --version 1.17.3` 렌더링 성공
- `kubectl diff --server-side=false -f <rendered>` 결과 `rc=0`
- `kubectl apply --dry-run=server -f <rendered>` 결과 conflict 없음
- child `Application/cilium`은 최신 TwinX-Ops revision `2605673`을 보고 있다.
- child app은 여전히 manual sync 상태이며 실제 sync는 수행하지 않았다.
- live Cilium Helm release는 `1.17.3`, revision `11` 그대로다.

다음 실제 단계는 child `Application/cilium` sync 여부 결정이다. diff가 0이므로 예상되는 spec 변경은 없지만, ArgoCD/Helm ownership metadata와 last-applied annotation이 붙을 수 있으므로 작업 전 상태 보고와 명시 승인을 먼저 받아야 한다.

### 2026-07-01 Cilium ownership sync 결과

사용자 승인 후 child `Application/cilium`만 수동 sync했다. `argocd` CLI가 없는 환경이라 Application CR의 `operation.sync`를 사용했다. Hubble enable, Cilium chart version upgrade, Kubespray 실행은 하지 않았다.

작업 전 백업 위치는 다음과 같다.

- `/home/netai/chang/Git/cilium-backup-20260701-063130`

sync 요청은 현재 child app이 보고 있던 multi-source revision을 고정해 수행했다.

- Cilium chart revision: `1.17.3`
- values repo revision: `2605673449e2e798c672419a6ed0f6033b062941`
- prune: `false`
- sync options: `CreateNamespace=true`, `ServerSideApply=true`, `Validate=false`

결과는 다음과 같다.

- `Application/cilium` sync status: `Synced`
- operation phase: `Succeeded`
- operation message: `successfully synced (all tasks run)`
- `Application/cilium` operation field: empty
- `Application/cilium` resource list: all `Synced`
- live Cilium Helm release: `1.17.3`, revision `11` 유지
- post-sync `kubectl diff --server-side=false -f <rendered>` 결과 `rc=0`
- Cilium DaemonSet: generation `6`, observed `6`, `10 desired / 8 ready / 8 available`
- Cilium Envoy DaemonSet: generation `3`, observed `3`, `10 desired / 8 ready / 8 available`
- Cilium Operator Deployment: generation `5`, observed `5`, `2 replicas / 2 ready`
- Cilium agent pod ages/restarts는 작업 직후 새 rollout을 보이지 않았다.

`Application/cilium` health는 `Progressing`으로 남아 있다. 이는 Cilium 또는 Envoy DaemonSet이 edgebox3/4 전원 장애 때문에 전체 10개 중 8개만 available인 known exception과 연결해서 해석한다. 실제 sync status와 리소스 sync status는 `Synced`다.

`Application/cilium`은 GitOps ownership을 갖게 되었으므로, 이후 Cilium 변경은 TwinX-Ops values 변경과 ArgoCD child app sync로 진행한다. Hubble 활성화는 별도 커밋과 별도 승인 후 진행한다.

### 2026-07-01 Hubble 준비 PR 결과

TwinX-Ops PR #223에서 Hubble 활성화 준비를 Git에 반영했다. 아직 child `Application/cilium` sync는 하지 않았다.

반영 내용은 다음과 같다.

- `hubble.enabled: true`
- `hubble.eventQueueSize: "8191"`
- `hubble.relay.enabled: true`
- `hubble.metrics.enabled`: `drop`, `tcp`, `flow`, `icmp`, `httpV2:exemplars=true`
- `hubble.metrics.enableOpenMetrics: true`
- `hubble.metrics.port: 9965`
- `hubble.metrics.tls.enabled: false` 유지
- `hubble.ui.enabled: false` 유지
- Cilium chart version은 `1.17.3` 유지
- Hubble relay image도 chart `1.17.3` 기본값인 `quay.io/cilium/hubble-relay:v1.17.3` 유지

DataX 예시는 `1.17.5` 기준이므로 relay image tag/digest를 그대로 복사하지 않았다. TwinX는 현재 Cilium `1.17.3`이므로 relay도 `1.17.3`으로 맞췄다.

TLS는 `hubble.tls.auto.method: cronJob`으로 설정했다. `helm` 방식은 ArgoCD 렌더링 때 Hubble 인증서 Secret이 매번 달라져 계속 diff가 생길 수 있기 때문이다. `cronJob` 방식은 렌더 결과가 반복 실행해도 동일했다.

검증 결과는 다음과 같다.

- `helm template cilium cilium/cilium --version 1.17.3` 반복 렌더 SHA 동일
- client-side `kubectl diff`에서 예상된 Hubble 리소스 추가와 Cilium agent DaemonSet template 변경 확인
- `kubectl apply --dry-run=server --validate=false` 결과 `rc=0`
- Cilium child Application 렌더 결과 `ServerSideApply=true` 제거 확인

`ServerSideApply=true`를 제거한 이유는 Hubble enable 시 `cilium-config.data.enable-hubble` 필드가 Cilium agent manager와 충돌하기 때문이다. Force conflict는 피하고, Cilium app만 client-side apply 방식으로 sync하도록 `syncOptionsOverride`를 추가했다. 다른 앱의 기본 `ServerSideApply=true` 동작은 유지된다.

PR merge 후 child `Application/cilium`을 hard refresh한 결과는 다음과 같다.

- child app revisions: `1.17.3`, `0e51fd008c6431fbf35eb4ed686622be714f3808`
- child app sync: `OutOfSync`
- child app health: `Missing`
- live Hubble resource는 아직 없음

`Missing`은 Hubble relay/certgen/metrics 리소스가 Git에는 추가됐지만 아직 sync하지 않아 live에 없기 때문에 예상되는 상태다. 다음 단계는 작업 전 백업과 상태 보고 후 child `Application/cilium` sync를 수행하는 것이다. 이 sync는 Cilium agent DaemonSet template 변경을 포함하므로 Cilium agent rollout 가능성이 있다.


### 2026-07-01 Hubble live sync 및 relay 복구 결과

사용자 승인 후 child `Application/cilium`을 수동 sync해 Hubble relay와 metrics를 활성화했다. Cilium chart version upgrade, Kubespray 실행, Hubble UI, Gateway API/L2 기능은 진행하지 않았다.

작업 전 백업 위치는 다음과 같다.

- `/home/netai/chang/Git/cilium-hubble-backup-20260701-065401`

sync 요청은 다음 revision을 고정해 수행했다.

- Cilium chart revision: `1.17.3`
- values repo revision: `0e51fd008c6431fbf35eb4ed686622be714f3808`
- prune: `false`
- sync options: `CreateNamespace=true`, `Validate=false`

sync 후 Hubble 관련 리소스가 생성됐다.

- `Deployment/hubble-relay`
- `Service/hubble-relay`
- `Service/hubble-peer`
- `Service/hubble-metrics`
- `CronJob/hubble-generate-certs`
- `ServiceAccount/hubble-relay`
- `ServiceAccount/hubble-generate-certs`
- `ConfigMap/hubble-relay-config`

처음에는 `hubble-relay-client-certs` Secret이 없어 relay Pod가 뜨지 못했다. `hubble.tls.auto.method: cronJob` 방식에서는 CronJob이 Secret을 만들기 전까지 relay가 대기할 수 있으므로, 수동으로 1회 Job을 생성해 인증서를 만들었다.

```bash
kubectl -n kube-system create job hubble-generate-certs-manual-070042 \
  --from=cronjob/hubble-generate-certs
```

생성 확인한 Secret은 다음과 같다.

- `hubble-server-certs`
- `hubble-relay-client-certs`
- `cilium-ca`

이후 relay는 실행됐지만 `hubble-peer.kube-system.svc.cluster.local.:443` 연결 timeout으로 `NOT_SERVING` 상태가 됐다. 원인은 Hubble 설정이 반영된 Cilium DaemonSet template과 기존 Cilium Pod spec이 달라, 살아 있는 노드의 Cilium Pod들을 새 template으로 재생성해야 했기 때문이다.

edgebox3/4는 전원 장애로 `Terminating` 상태라 건드리지 않았고, 살아 있는 노드의 Cilium Pod만 하나씩 직접 삭제해 재생성했다.

| 노드 | 새 Cilium Pod | 결과 |
| --- | --- | --- |
| l40s | `cilium-vht8d` | `1/1 Running` |
| control1 | `cilium-vtfqv` | `1/1 Running` |
| rm352-1 | `cilium-csdxp` | `1/1 Running` |
| rm352-2 | `cilium-jcf97` | `1/1 Running` |
| sv4000-1 | `cilium-xsnnx` | `1/1 Running` |
| sv4000-2 | `cilium-d7pm8` | `1/1 Running` |
| edgebox1 | `cilium-k77xv` | `1/1 Running` |
| edgebox2 | `cilium-tvzjh` | `1/1 Running` |

그래도 relay가 계속 timeout을 냈다. 추가 확인 결과는 다음과 같다.

- l40s의 Cilium agent는 `Hubble: Ok` 상태였다.
- l40s Cilium agent는 `*:4244`를 listen 중이었다.
- 일반 Pod network에서 `10.38.38.97:4244`와 `hubble-peer` ClusterIP는 timeout이었다.
- `hostNetwork: true` 임시 Pod에서는 `10.38.38.97:4244`와 `hubble-peer` ClusterIP 모두 접속됐다.

따라서 원인은 relay 자체 문제가 아니라 **일반 Pod network에서 Cilium agent Hubble peer port 4244로 들어가는 경로가 막히는 것**으로 판단했다. Hubble relay만 `hostNetwork: true`, `dnsPolicy: ClusterFirstWithHostNet`로 패치하자 즉시 정상화됐다.

```bash
kubectl -n kube-system patch deploy hubble-relay --type=json -p='[
  {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
  {"op":"add","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}
]'
```

최종 확인 결과는 다음과 같다.

- `Deployment/hubble-relay`: `1/1`
- `hubble-relay` Pod IP: `10.38.38.97`
- relay 로그에서 `control1`, `l40s`, `rm352-1`, `rm352-2`, `sv4000-1`, `sv4000-2`, `edgebox1`, `edgebox2` peer 연결 성공
- edgebox3/4 peer도 endpoint에는 남아 있지만, 해당 노드는 전원 장애 known exception이다.

Cilium `1.17.3` chart는 `hubble.relay.hostNetwork` 값을 Deployment에 렌더링하지 않는다. 따라서 TwinX-Ops PR #224에서 ArgoCD가 검증된 live patch를 되돌리지 않도록 child Application에 아래 설정을 추가했다.

- `ignoreDifferences`: `Deployment/hubble-relay`의 `/spec/template/spec/hostNetwork`, `/spec/template/spec/dnsPolicy`
- `syncOptions`: `RespectIgnoreDifferences=true`

PR #224 merge 후 확인 결과는 다음과 같다.

- TwinX-Ops main revision: `91d89ec`
- live `Application/cilium.spec.syncPolicy.syncOptions`: `CreateNamespace=true`, `Validate=false`, `RespectIgnoreDifferences=true`
- live `Application/cilium.spec.ignoreDifferences`: `hubble-relay`의 `hostNetwork`, `dnsPolicy`
- live `Deployment/hubble-relay`: `hostNetwork=true`, `dnsPolicy=ClusterFirstWithHostNet`, `ready=1/1`

`Application/cilium`은 여전히 `OutOfSync/Progressing`으로 보일 수 있다. 현재 해석은 다음과 같다.

- Cilium DaemonSet은 edgebox3/4 전원 장애 때문에 `10 desired / 8 available`이다.
- Hubble relay 자체는 정상이다.
- 나중에 `twinx-infra` parent app을 sync해도 PR #224 설정이 반영되어 ArgoCD가 relay의 `hostNetwork/dnsPolicy`를 되돌리지 않아야 한다.

향후 정리할 점은 다음과 같다.

- Cilium chart upgrade 시 `hubble.relay.hostNetwork`를 공식 values로 지원하는지 다시 확인한다.
- 공식 지원이 없으면 Cilium chart wrapper 또는 ArgoCD post-render/patch 구조를 별도 설계한다.
- Hubble relay 외부 노출은 아직 하지 않는다. 현재 relay server TLS는 꺼져 있으므로, LoadBalancer나 Ingress로 열려면 내부망 제한, TLS, 인증 방식을 먼저 정해야 한다.

## 참고: 배경과 원래 계획

### 배경

TwinX는 현재 Kubespray로 Cilium을 설치하고 있다. 이 방식은 Kubernetes 설치와 업그레이드에는 편하지만, 운영 중 Cilium values를 추적하거나 Hubble 같은 관측 기능을 단계적으로 켜기에는 불편하다.

MobileX/DataX 쪽은 Cilium을 직접 GitOps로 관리하고 있고, Hubble도 사용하고 있다. TwinX도 장기적으로는 Cilium chart와 values를 Git에 두고 ArgoCD로 관리하는 편이 운영 추적성과 재현성이 좋다.

다만 Cilium은 단순 addon이 아니라 pod network, service routing, kube-proxy 연동, CNI 설정을 담당한다. 따라서 **Kubespray와 ArgoCD가 동시에 Cilium을 장기간 관리하는 상태**가 되면 위험하다.

### 현재 TwinX Cilium 상태

2026-06-29 기준 확인한 상태다.

| 항목 | 현재 값 |
| --- | --- |
| 설치 주체 | Kubespray가 실행한 Helm release |
| Helm release | `cilium` |
| Namespace | `kube-system` |
| Cilium version | `1.17.3` |
| Image | `quay.io/cilium/cilium:v1.17.3` |
| Release status | `deployed` |
| Helm revision | `11` |
| Hubble | disabled |
| kube-proxy replacement | false |
| routing mode | tunnel |
| tunnel protocol | vxlan |
| datapath mode | veth |
| IPAM | cluster-pool |
| Pod CIDR | `10.234.64.0/18` |
| MTU | 1500 |
| Gateway API | disabled |
| L2 announcements | disabled |
| CNI exclusive | true |

확인에 사용한 주요 명령은 아래와 같다.

```bash
helm -n kube-system status cilium
helm -n kube-system get values cilium --all
kubectl -n kube-system get cm cilium-config -o yaml
kubectl -n kube-system get ds cilium -o wide
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
```

현재 `cilium-config`에는 `enable-hubble: false`, `kube-proxy-replacement: false`, `routing-mode: tunnel`, `tunnel-protocol: vxlan`, `datapath-mode: veth`가 반영되어 있다. 즉 TwinX는 DataX처럼 native routing, netkit, kube-proxy replacement를 사용하는 형태가 아니다.

### DataX-Ops 참고 구조

DataX-Ops에서는 Cilium을 ArgoCD Helm app으로 관리한다.

| 항목 | DataX 참고 값 |
| --- | --- |
| Cilium app path | `gitops-apps/datax/core/apps/cilium/values.yaml` |
| ArgoCD values | `gitops-apps/datax/core/values.yaml` |
| Chart repo | `https://helm.cilium.io/` |
| Chart | `cilium` |
| Target revision | `1.17.5` |
| Namespace | `kube-system` |
| sync wave | `1` |
| cilium-resources sync wave | `5` |

DataX는 Cilium chart와 별도로 Cilium 리소스도 GitOps로 관리한다.

- Cilium L2AnnouncementPolicy
- Cilium LoadBalancerIPPool
- Gateway API resource
- CiliumNetworkPolicy

DataX values의 특징은 고성능 네트워크 설정에 가깝다.

- `routingMode: native`
- `devices: bond0`
- `kubeProxyReplacement: true`
- `bpf.datapathMode: netkit`
- `enableIPv4BIGTCP: true`
- `gatewayAPI.enabled: true`
- `l2announcements.enabled: true`
- `hubble.enabled: true`
- `hubble.relay.enabled: true`
- `hubble.ui.enabled: true`

### DataX 값을 TwinX에 그대로 복사하면 안 되는 이유

TwinX와 DataX는 현재 네트워크 설계가 다르다.

| 구분 | TwinX 현재 | DataX 참고 |
| --- | --- | --- |
| routing | VXLAN tunnel | native routing |
| datapath | veth | netkit |
| kube-proxy | 사용 중 | replacement |
| Hubble | disabled | enabled |
| Gateway API | disabled | enabled |
| L2 announcement | disabled | enabled |
| device 지정 | 없음 | `bond0` |
| BIG TCP | disabled | enabled |

특히 아래 값들은 단순히 복사하면 장애 가능성이 크다.

- `kubeProxyReplacement: true`
- `routingMode: native`
- `bpf.datapathMode: netkit`
- `enableIPv4BIGTCP: true`
- `devices: bond0`
- `gatewayAPI.enabled: true`
- `l2announcements.enabled: true`

TwinX는 rm352, sv4000, l40s, edgebox 등 노드 종류와 NIC 구성이 섞여 있고, 과거 rm352 pod 통신 문제와 MTU/Cilium 불안정도 있었다. 따라서 먼저 현재 값을 보존한 상태로 GitOps ownership만 정리해야 한다.

### 전환 원칙

1. **한 번에 하나만 바꾼다.**
   - Cilium ownership 전환, Cilium version upgrade, Hubble enable, routing mode 변경을 한 번에 묶지 않는다.

2. **처음 GitOps values는 현재 Helm values를 기준으로 만든다.**
   - DataX values는 구조 참고용이다.
   - TwinX의 현재 tunnel/veth/kube-proxy 사용 상태를 먼저 유지한다.

3. **Kubespray와 ArgoCD의 장기 이중 관리를 피한다.**
   - 전환 전에는 Kubespray inventory에서 Cilium 관련 값을 계속 추적한다.
   - 전환 후에는 Cilium 변경을 ArgoCD 쪽에서만 수행하도록 운영 규칙을 정한다.

4. **Hubble은 전환 안정화 후 별도 단계로 켠다.**
   - 먼저 relay와 metrics만 켠다.
   - UI 노출, 인증, Gateway 연동은 나중에 결정한다.

5. **edgebox3/4 전원 문제는 known exception으로 다룬다.**
   - 전원 장애가 복구되기 전에는 GitOps 준비 작업만 수행한다.
   - 실제 Cilium ownership 전환이나 Hubble enable을 진행하려면 작업 직전 상태 보고와 명시 승인을 먼저 받는다.
   - 전원 장애 노드 때문에 Cilium DaemonSet 전체 rollout 검증이 완료되지 않을 수 있으므로, 살아 있는 노드 기준 검증 결과와 known exception을 함께 기록한다.

6. **Kubespray는 Cilium 변경 경로에서 제외한다.**
   - Kubernetes 설치/업그레이드에는 Kubespray를 계속 사용할 수 있다.
   - Cilium 운영 변경, Hubble enable, Cilium chart version 변경은 ArgoCD/TwinX-Ops를 source of truth로 삼는다.

### 권장 디렉터리 설계

TwinX-Ops 쪽에는 아래와 같은 구조를 권장한다.

```text
argocd/twinx-infra/apps/
└── cilium/
    ├── Chart.yaml 또는 ArgoCD Helm source 설정
    └── values.yaml

argocd/twinx-infra/apps/
└── cilium-resources/
    ├── README.md
    └── *.yaml
```

ArgoCD app 목록은 먼저 `enabled: false`로 추가했고, manual sync guard 검증 후 `enabled: true`로 전환했다.
root app이 manual sync이므로 이 변경은 merge만으로 live cluster에 반영되지 않는다.

```yaml
cilium:
  enabled: true
  namespace: kube-system
  syncWave: "1"
  project: twinx-infra
  syncPolicy:
    automated: false
  source:
    type: helm
    repoURL: https://helm.cilium.io/
    chart: cilium
    targetRevision: 1.17.3
    helm:
      releaseName: cilium
      valueFiles:
        - "argocd/twinx-infra/apps/cilium/values.yaml"

cilium-resources:
  enabled: false
  namespace: kube-system
  syncWave: "5"
  project: twinx-infra
  source:
    path: "argocd/twinx-infra/apps/cilium-resources"
```

처음에는 `targetRevision: 1.17.3`으로 현재 버전을 맞춘다. Cilium upgrade와 GitOps ownership 전환을 동시에 하지 않기 위해서다.

### 단계별 계획

#### 0단계 — 현재 상태 백업

작업 전 현재 Helm values와 ConfigMap을 저장한다.

```bash
BACKUP_DIR=~/cilium-backup-$(date +%F)
mkdir -p "$BACKUP_DIR"
helm -n kube-system get values cilium --all > "$BACKUP_DIR/cilium-values-all.yaml"
helm -n kube-system status cilium > "$BACKUP_DIR/cilium-helm-status.txt"
kubectl -n kube-system get cm cilium-config -o yaml > "$BACKUP_DIR/cilium-config.yaml"
kubectl -n kube-system get ds cilium -o yaml > "$BACKUP_DIR/cilium-ds.yaml"
kubectl -n kube-system get deploy cilium-operator -o yaml > "$BACKUP_DIR/cilium-operator.yaml"
```

#### 1단계 — TwinX-Ops에 Cilium app과 values 추가

목표는 배포가 아니라 Git에 구조와 values를 먼저 넣는 것이다. 이 단계는 클러스터 변경이 아니라 문서/형상 준비 작업이다.

- 처음에는 `enabled: false`로 추가했다.
- chart version은 현재와 같은 `1.17.3`으로 고정했다.
- values는 현재 `helm get values --all`에서 출발했다.
- Hubble은 아직 disabled다.
- routing, kube-proxy, datapath, IPAM은 현재 값 유지다.
- `argocd/twinx-infra/apps/cilium/values.yaml`을 생성했다.
- 앱 디렉터리별 README는 만들지 않고, 운영 의사결정과 절차는 이 runbook에 기록한다.
- `cilium-resources`는 현재 TwinX에서 관리할 Cilium custom resource가 없으므로 만들지 않는다. L2 announcement, LoadBalancer IPAM, CiliumNetworkPolicy 등을 도입할 때 별도 추가한다.
- manual sync guard 검증 뒤 `enabled: true`로 바꿨지만, root app sync는 아직 하지 않았다.

이 단계에서는 ArgoCD sync를 하지 않았다.

#### 2단계 — values diff 검토

Git에 들어간 values와 현재 cluster values가 의미적으로 같은지 비교한다.

```bash
helm -n kube-system get values cilium --all > /tmp/twinx-cilium-current.yaml
diff -u /tmp/twinx-cilium-current.yaml argocd/twinx-infra/apps/cilium/values.yaml
```

완전히 같은 YAML 모양일 필요는 없지만 아래 기능 값은 반드시 같아야 한다.

- `kubeProxyReplacement`
- `routingMode`
- `tunnelProtocol`
- `ipam`
- `clusterPoolIPv4PodCIDRList`
- `bpf.datapathMode`
- `hubble.enabled`
- `gatewayAPI.enabled`
- `l2announcements.enabled`
- `operator.replicas`

#### 3단계 — maintenance window에서 ownership 전환

이 단계는 실제 변경 단계이므로 별도 작업 승인 후 진행한다.

권장 흐름은 다음과 같다.

1. edgebox3/4 상태와 control-plane 상태 확인
2. Cilium 백업 재수행
3. `twinx-infra-root-app` sync로 child `Application/cilium`만 생성
4. child `Application/cilium`이 manual sync인지 확인
5. child Application diff 확인
6. 별도 승인 후 child `Application/cilium` sync
7. Cilium DaemonSet과 operator rollout 확인
8. pod-to-pod, pod-to-service, pod-to-node, external service 접근 확인

여기서 기능 변경은 하지 않는다.  
성공 기준은 **Cilium을 GitOps가 관리하게 되었지만 네트워크 동작은 이전과 같은 상태**다.

#### 4단계 — Hubble relay와 metrics 활성화

GitOps 전환 후 별도 maintenance window에서 Hubble을 켠다.

처음에는 UI 없이 relay와 metrics만 활성화한다.

```yaml
hubble:
  enabled: true
  relay:
    enabled: true
  ui:
    enabled: false
  metrics:
    enabled:
      - drop
      - tcp
      - flow
      - icmp
    enableOpenMetrics: true
    port: 9965
    tls:
      enabled: false
```

`httpV2` metrics는 유용하지만 트래픽 양과 label cardinality를 확인한 뒤 추가한다.

#### 5단계 — Hubble UI와 고급 기능 검토

아래 기능은 Cilium GitOps 전환과 Hubble relay가 안정화된 뒤 별도 계획으로 다룬다.

- Hubble UI
- Gateway API
- L2 announcement
- LoadBalancer IPAM
- native routing
- kube-proxy replacement
- netkit
- BIG TCP

이 기능들은 DataX에서는 이미 쓰고 있지만, TwinX에서는 노드별 NIC, MTU, 기존 서비스 노출 방식, kube-proxy 의존성을 다시 확인해야 한다.

### Preflight

작업 전 반드시 아래 상태를 확인한다.

```bash
kubectl get nodes -o wide
kubectl -n kube-system get ds cilium -o wide
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
kubectl -n kube-system get pods -l name=cilium-operator -o wide
kubectl -n kube-system get cm cilium-config -o yaml
helm -n kube-system status cilium
helm -n kube-system get values cilium --all
kubectl get svc -A
kubectl get endpoints kubernetes -n default
kubectl get crd | grep -i cilium
```

특히 아래 조건이면 당일 작업하지 않는다.

- edgebox3/4 전원 또는 kubelet 상태가 불명확함
- control-plane 정리 작업과 같은 날임
- Rook-Ceph, Harbor, Keycloak, ArgoCD 중 하나라도 불안정함
- `kubectl get nodes`에서 예상하지 못한 NotReady가 있음
- Cilium pod가 이미 재시작을 반복 중임

### 검증 기준

GitOps ownership 전환 후 확인할 것:

```bash
kubectl -n kube-system rollout status ds/cilium --timeout=10m
kubectl -n kube-system rollout status deploy/cilium-operator --timeout=10m
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
kubectl -n kube-system get pods -l name=cilium-operator -o wide
kubectl get nodes
kubectl get pods -A | grep -v Running
```

Hubble 활성화 후 확인할 것:

```bash
kubectl -n kube-system get svc hubble-relay
kubectl -n kube-system get pods | grep hubble
kubectl -n kube-system get cm cilium-config -o yaml | grep -i hubble
```

가능하면 Cilium CLI가 있는 환경에서 아래도 확인한다.

```bash
cilium status
cilium connectivity test
```

### 중단 기준

아래 중 하나라도 발생하면 즉시 중단하고 rollback 또는 이전 values 복구를 우선한다.

- Cilium DaemonSet이 10분 이상 Ready로 돌아오지 않음
- `kubernetes.default` endpoint 접근이 깨짐
- CoreDNS가 API 서버에 접근하지 못함
- 다수 노드가 NotReady로 변함
- pod-to-service 통신이 깨짐
- Rook-Ceph, Harbor, Keycloak, ArgoCD가 동시에 네트워크 장애를 보임
- ArgoCD가 Cilium 리소스를 계속 prune/recreate하려고 함

### Rollback 개념

전환 직후 문제가 생기면 먼저 GitOps sync를 멈추고, 백업한 values로 Helm rollback 또는 upgrade를 검토한다.

```bash
helm -n kube-system history cilium
helm -n kube-system rollback cilium <REVISION>
```

또는 백업 values로 다시 적용한다.

```bash
helm -n kube-system upgrade cilium cilium/cilium \
  --version 1.17.3 \
  -f ~/cilium-backup-YYYY-MM-DD/cilium-values-all.yaml
```

정확한 rollback 방식은 당시 ArgoCD ownership 전환 방식에 따라 달라지므로, 실제 작업 문서에는 사용한 sync 방식과 revision을 반드시 남긴다.

### 2026-07-01 최종 반영 요약

오늘 최종 상태는 다음과 같다.

- TwinX-Ops PR #219~#224를 통해 Cilium child Application, manual sync guard, Hubble relay/metrics enable, hostNetwork drift 방지 설정을 반영했다.
- child `Application/cilium` sync를 통해 Hubble relay/metrics 리소스를 live cluster에 생성했다.
- Hubble certgen Job을 수동 1회 실행해 `hubble-server-certs`, `hubble-relay-client-certs`, `cilium-ca` Secret을 생성했다.
- 살아 있는 노드의 Cilium Pod를 하나씩 재생성해 Hubble agent 설정을 반영했다.
- `hubble-relay`는 일반 Pod network에서 Cilium agent 4244로 접근하지 못해 `NOT_SERVING`이었고, `hostNetwork=true` 패치 후 정상화됐다.
- runbook 기록 기준 live `hubble-relay`는 `ready=1/1`이다.

### 남은 후속 작업

1. edgebox3/4 전원 복구 후 Cilium DaemonSet이 `10/10`으로 돌아오는지 확인한다.
2. Cilium chart를 `1.18.x` 또는 `1.19.x`로 올릴 때 relay hostNetwork를 공식 values로 처리할 수 있는지 다시 확인한다.
3. 필요하면 Cilium chart wrapper, ArgoCD patch/post-render 구조, 또는 Cilium chart upgrade 중 하나로 hostNetwork 처리를 더 깔끔하게 정리한다.
4. Hubble UI나 LoadBalancer 노출은 별도 보안 설계 후 진행한다. 현재 relay server TLS는 꺼져 있으므로 외부 노출은 하지 않는다.
5. Cilium version upgrade는 Hubble 활성화와 분리해 별도 작업으로 진행한다.
