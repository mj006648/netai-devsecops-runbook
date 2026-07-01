# TwinX Cilium GitOps 및 Hubble 전환 계획 2026-06-29

## 요약

TwinX 클러스터의 Cilium은 현재 Kubespray가 설치한 Helm release로 동작하고 있다.  
이 문서는 Cilium을 바로 변경하기 위한 작업 문서가 아니라, **Kubespray 관리 상태에서 ArgoCD GitOps 관리 상태로 안전하게 넘기고 이후 Hubble을 단계적으로 켜기 위한 계획서**다.

현재 결론은 다음과 같다.

- Cilium은 클러스터 네트워크 자체이므로 Kubernetes upgrade, control-plane 정리, edgebox 복구, KubeVirt 작업과 같은 날에 같이 진행하지 않는다.
- DataX-Ops의 Cilium GitOps 구조는 참고하되, TwinX에 그대로 복사하지 않는다.
- 1차 목표는 기능 변경이 아니라 **현재 TwinX Cilium 값을 거의 그대로 GitOps에 옮겨 ownership만 정리하는 것**이다.
- Hubble은 Cilium GitOps 전환이 안정화된 뒤 `relay`와 metrics부터 켜고, UI와 Gateway API/L2 기능은 별도 단계로 분리한다.
- 2026-07-01 기준으로는 edgebox3/4 전원 장애가 길어질 수 있으므로, 먼저 **클러스터에 영향 없는 GitOps 준비 작업**만 진행한다.
- 실제 적용 작업(`ArgoCD sync`, `Helm upgrade`, `Kubespray 실행`, `Hubble enable`, `Cilium rollout`)은 작업 전 상태 보고와 명시 승인을 받은 뒤에만 진행한다.

## 2026-07-01 결정 사항

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

## 배경

TwinX는 현재 Kubespray로 Cilium을 설치하고 있다. 이 방식은 Kubernetes 설치와 업그레이드에는 편하지만, 운영 중 Cilium values를 추적하거나 Hubble 같은 관측 기능을 단계적으로 켜기에는 불편하다.

MobileX/DataX 쪽은 Cilium을 직접 GitOps로 관리하고 있고, Hubble도 사용하고 있다. TwinX도 장기적으로는 Cilium chart와 values를 Git에 두고 ArgoCD로 관리하는 편이 운영 추적성과 재현성이 좋다.

다만 Cilium은 단순 addon이 아니라 pod network, service routing, kube-proxy 연동, CNI 설정을 담당한다. 따라서 **Kubespray와 ArgoCD가 동시에 Cilium을 장기간 관리하는 상태**가 되면 위험하다.

## 현재 TwinX Cilium 상태

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

## DataX-Ops 참고 구조

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

## DataX 값을 TwinX에 그대로 복사하면 안 되는 이유

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

## 전환 원칙

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

## 권장 디렉터리 설계

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

ArgoCD app 목록에서는 처음에 `enabled: false`로 추가하는 것이 안전하다.

```yaml
cilium:
  enabled: false
  namespace: kube-system
  syncWave: "1"
  project: twinx-infra
  source:
    type: helm
    repoURL: https://helm.cilium.io/
    chart: cilium
    targetRevision: 1.17.3
    helm:
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

## 단계별 계획

### 0단계 — 현재 상태 백업

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

### 1단계 — TwinX-Ops에 disabled 상태로 Cilium app 추가

목표는 배포가 아니라 Git에 구조와 values를 먼저 넣는 것이다. 이 단계는 클러스터 변경이 아니라 문서/형상 준비 작업이다.

- `enabled: false`
- chart version은 현재와 같은 `1.17.3`
- values는 현재 `helm get values --all`에서 출발
- Hubble은 아직 disabled
- routing, kube-proxy, datapath, IPAM은 현재 값 유지
- `argocd/twinx-infra/apps/cilium/values.yaml` 생성
- 앱 디렉터리별 README는 만들지 않고, 운영 의사결정과 절차는 이 runbook에 기록한다.
- `cilium-resources`는 현재 TwinX에서 관리할 Cilium custom resource가 없으므로 만들지 않는다. L2 announcement, LoadBalancer IPAM, CiliumNetworkPolicy 등을 도입할 때 별도 추가한다.

이 단계에서는 ArgoCD sync를 하지 않는다.

### 2단계 — values diff 검토

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

### 3단계 — maintenance window에서 ownership 전환

이 단계는 실제 변경 단계이므로 별도 작업 승인 후 진행한다.

권장 흐름은 다음과 같다.

1. edgebox3/4 상태와 control-plane 상태 확인
2. Cilium 백업 재수행
3. ArgoCD app을 enabled로 바꾸되 values는 현재와 동일하게 유지
4. ArgoCD diff 확인
5. ArgoCD sync
6. Cilium DaemonSet과 operator rollout 확인
7. pod-to-pod, pod-to-service, pod-to-node, external service 접근 확인

여기서 기능 변경은 하지 않는다.  
성공 기준은 **Cilium을 GitOps가 관리하게 되었지만 네트워크 동작은 이전과 같은 상태**다.

### 4단계 — Hubble relay와 metrics 활성화

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

### 5단계 — Hubble UI와 고급 기능 검토

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

## Preflight

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

## 검증 기준

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

## 중단 기준

아래 중 하나라도 발생하면 즉시 중단하고 rollback 또는 이전 values 복구를 우선한다.

- Cilium DaemonSet이 10분 이상 Ready로 돌아오지 않음
- `kubernetes.default` endpoint 접근이 깨짐
- CoreDNS가 API 서버에 접근하지 못함
- 다수 노드가 NotReady로 변함
- pod-to-service 통신이 깨짐
- Rook-Ceph, Harbor, Keycloak, ArgoCD가 동시에 네트워크 장애를 보임
- ArgoCD가 Cilium 리소스를 계속 prune/recreate하려고 함

## Rollback 개념

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

## 오늘까지 한 것

- DataX-Ops의 Cilium GitOps 구조를 확인했다.
- TwinX의 현재 Cilium Helm release와 주요 values를 확인했다.
- DataX values를 TwinX에 그대로 복사하면 안 되는 차이를 정리했다.
- Cilium GitOps 전환과 Hubble 활성화는 실제 적용하지 않았다.
- TwinX-Ops에는 아직 Cilium app과 values를 추가하지 않았다.
- ArgoCD sync는 하지 않았다.

## 다음 작업

1. TwinX-Ops에 `enabled: false` 상태의 Cilium app과 values를 추가한다.
2. 현재 Helm values와 Git values의 기능 차이가 없는지 검토한다.
3. edgebox3/4 전원 장애는 별도 하드웨어 이슈로 추적하고, Cilium 적용 단계에서는 known exception으로 남긴다.
4. 실제 ArgoCD ownership 전환 전에는 현재 상태, diff, rollback 계획을 먼저 보고하고 승인을 받는다.
5. 별도 maintenance window에서 Cilium ownership 전환만 수행한다.
6. ownership 전환 안정화 후 Hubble relay와 metrics를 별도 커밋/승인으로 활성화한다.
7. Cilium version upgrade는 Hubble과 분리해 ArgoCD chart revision 변경으로 단계적으로 진행한다.
