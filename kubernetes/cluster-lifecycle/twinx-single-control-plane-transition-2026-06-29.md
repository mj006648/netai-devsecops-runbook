# TwinX 단일 Control Plane 전환 계획 및 실행 로그 2026-06-29

## 요약

TwinX 클러스터의 control-plane을 3대 구조에서 `control1` 1대 구조로 줄이는 작업 계획과 실행 로그다.

현재 작업 방향은 다음과 같다.

- `control1`을 최종 단일 control-plane으로 남긴다.
- `control2`, `control3`는 Kubernetes control-plane과 etcd member에서 제거한다.
- edgebox3/4는 전원 이슈가 있으므로 이 작업의 직접 blocker로 보지 않고, 별도 복구/업그레이드 대상으로 분리한다.
- Cilium GitOps 전환, Hubble enable, KubeVirt 배포는 이 작업과 같은 maintenance window에서 진행하지 않는다.
- etcd snapshot과 health 확인 전에는 어떤 control-plane 제거도 진행하지 않는다.
- etcd snapshot 파일은 Kubernetes Secret과 인증 정보를 포함할 수 있으므로 GitHub에 올리지 않는다. GitHub에는 백업 위치와 검증 여부만 기록한다.
- 이번 전환은 Kubespray 전체 playbook을 기본 경로로 사용하지 않는다. worker/GPU 노드의 직접 Docker container에 영향을 주지 않기 위해 control-plane 대상 수동/외과적 제거를 우선한다.

## 현재 의도한 순서

```text
1. runbook 계획 기록
2. preflight 수집
3. control1 etcd snapshot 저장 및 snapshot status 확인
4. etcd member 상태 확인
5. control3 제거
6. 안정화 검증
7. control2 제거
8. 안정화 검증
9. Kubespray inventory / 운영 문서 정리
10. runbook에 실제 결과 기록
```

## 작업 대상

| 노드 | 현재 역할 | 최종 처리 |
| --- | --- | --- |
| control1 | control-plane, etcd | 유지 |
| control2 | control-plane, etcd | 제거 예정 |
| control3 | control-plane, etcd | 제거 예정 |


## 백업 보안 원칙

etcd snapshot은 GitHub에 올리지 않는다.

이유는 etcd snapshot 안에 다음 정보가 포함될 수 있기 때문이다.

- Kubernetes Secret
- ServiceAccount token
- OIDC/인증 관련 설정
- TLS 인증서/키에 연결되는 민감 정보
- ArgoCD, Harbor, OpenBao, External Secrets Operator 관련 secret
- 앱별 DB password, API key, registry credential

따라서 runbook에는 아래 정보만 남긴다.

| 항목 | 기록 여부 |
| --- | --- |
| snapshot 파일 내용 | 기록 금지 |
| snapshot 파일 GitHub 업로드 | 금지 |
| snapshot이 저장된 노드와 경로 | 기록 가능 |
| snapshot 생성 시각 | 기록 가능 |
| snapshot size/status 검증 결과 | 기록 가능 |
| snapshot 외부 백업 위치 | 민감하지 않은 범위에서 기록 가능 |

현재 snapshot 위치:

```text
control1:/root/etcd-snapshot-before-single-control-plane-2026-06-29-0701.db
```

검증 결과:

```text
etcdutl snapshot status 성공
revision: 231105727
size: 244 MB
file size: 233M
```

## Kubespray를 기본 제거 경로로 쓰지 않는 이유

TwinX는 Kubernetes workload뿐 아니라 사용자가 노드에 직접 접속해 Docker container를 실행하는 경우가 있다. Kubespray playbook이 넓은 범위로 실행되면 worker/GPU 노드의 container runtime, kubelet, CNI, iptables/ipvs, package 상태를 건드릴 수 있다.

이번 작업에서는 control2/control3가 직접 Docker workload를 거의 갖고 있지 않은 것으로 보지만, 그래도 worker/GPU 노드를 건드릴 이유가 없다. 따라서 기본 전략은 다음과 같다.

```text
Kubespray 전체 실행 금지
Kubespray remove-node 직접 실행 금지
필요 시 --list-hosts / --list-tasks 로 영향 범위만 확인
실제 제거는 control-plane 대상 수동/외과적 절차 우선
```

Kubespray는 나중에 inventory를 현실 상태에 맞게 정리하거나, 영향 범위가 control-plane으로만 제한되는지 확인된 경우에만 보조적으로 사용한다.

## 왜 edgebox보다 먼저 할 수 있는가

edgebox3/4는 현재 전원 또는 하드웨어 계층의 문제가 의심된다. 이 문제는 Kubernetes control-plane 축소와 직접적인 의존성이 낮다.

다만 edgebox3/4가 NotReady로 남아 있으면 전체 cluster 상태가 지저분해 보일 수 있으므로, control-plane 전환 검증에서는 다음을 분리해서 봐야 한다.

- control-plane/API/etcd 건강 상태
- Cilium이 살아 있는 노드에서 정상인지
- edgebox3/4 전원 문제로 인한 NotReady는 별도 known issue인지

## 절대 같이 하지 않을 작업

이번 작업에서는 아래를 하지 않는다.

- Cilium GitOps 전환
- Hubble 활성화
- Cilium version 변경
- kube-proxy replacement 전환
- KubeVirt 활성화
- edgebox3/4 강제 복구 또는 강제 reset
- Rook-Ceph 큰 구조 변경

## Preflight

작업 전 확인 명령이다.

```bash
kubectl get nodes -o wide
kubectl get pods -A | grep -v Running || true
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get pods | grep -E 'kube-apiserver|kube-controller|kube-scheduler|etcd' || true
kubectl -n kube-system get ds cilium -o wide
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
```

control1에서 etcd 상태를 확인한다.

```bash
sudo ETCDCTL_API=3 etcdctl member list --write-out=table
sudo ETCDCTL_API=3 etcdctl endpoint health --cluster
sudo ETCDCTL_API=3 etcdctl endpoint status --cluster --write-out=table
```

인증서 경로가 필요한 경우 Kubespray 기본 경로를 사용한다.

```bash
sudo ETCDCTL_API=3 etcdctl \
  --cacert=/etc/ssl/etcd/ssl/ca.pem \
  --cert=/etc/ssl/etcd/ssl/member-control1.pem \
  --key=/etc/ssl/etcd/ssl/member-control1-key.pem \
  member list --write-out=table
```

## Snapshot 필수 조건

control-plane 제거 전 반드시 etcd snapshot을 저장한다.

```bash
SNAPSHOT=/root/etcd-snapshot-before-single-control-plane-$(date +%F-%H%M).db
sudo ETCDCTL_API=3 etcdctl snapshot save "$SNAPSHOT"
sudo ETCDCTL_API=3 etcdctl snapshot status "$SNAPSHOT" --write-out=table
```

인증서가 필요한 경우:

```bash
SNAPSHOT=/root/etcd-snapshot-before-single-control-plane-$(date +%F-%H%M).db
sudo ETCDCTL_API=3 etcdctl \
  --cacert=/etc/ssl/etcd/ssl/ca.pem \
  --cert=/etc/ssl/etcd/ssl/member-control1.pem \
  --key=/etc/ssl/etcd/ssl/member-control1-key.pem \
  snapshot save "$SNAPSHOT"

sudo ETCDCTL_API=3 etcdctl snapshot status "$SNAPSHOT" --write-out=table
```

snapshot status 확인이 실패하면 제거 작업을 하지 않는다.

## 실행 계획

### 0단계 — 제거 대상 Docker 상태 확인

control2/control3에는 일반 사용자의 직접 Docker workload가 없을 가능성이 높지만, 제거 전 최소 확인은 수행한다.

```bash
ssh control2 'docker ps -a || sudo crictl ps -a || true'
ssh control3 'docker ps -a || sudo crictl ps -a || true'
```

사용자 Docker container가 발견되면 제거 작업을 중단하고 소유자/용도 확인 후 별도 백업한다.

2026-06-29 확인 결과 `docker` binary는 없고 Kubernetes/containerd pod만 있었다. 따라서 제거 당일에는 일반 pod를 안전하게 옮기기 위해 drain을 먼저 수행한다.

### 1단계 — control3 제거

먼저 `control3`부터 제거한다. 이유는 한 번에 두 member를 제거하지 않고, quorum과 API 동작을 단계별로 확인하기 위해서다.

예상 흐름:

```bash
# 1. Kubernetes 일반 pod 먼저 이동
kubectl drain control3   --ignore-daemonsets   --delete-emptydir-data   --force   --grace-period=60   --timeout=10m

# 2. drain 후 남은 pod 확인
kubectl get pods -A --field-selector spec.nodeName=control3 -o wide

# 3. member id 확인
sudo ETCDCTL_API=3 etcdctl member list --write-out=table

# 4. control3 etcd member remove
sudo ETCDCTL_API=3 etcdctl member remove c7b8a81e21db4ac9

# 5. control3에서 control-plane 프로세스가 다시 뜨지 않게 정지/비활성화
ssh control3 'sudo systemctl stop etcd kubelet'
ssh control3 'sudo systemctl disable etcd kubelet'

# 6. Kubernetes node 제거
kubectl delete node control3
```

`kubectl drain`은 Kubernetes pod만 대상으로 하며 직접 Docker container를 내리지는 않는다. 이번 확인에서 control3에는 일반 Docker container가 없었으므로 drain을 사용한다.

### 2단계 — control3 제거 후 검증

```bash
kubectl get nodes -o wide
kubectl get --raw='/readyz?verbose'
kubectl -n kube-system get pods -o wide | grep -E 'control1|control2|control3|etcd|kube-apiserver|kube-controller|kube-scheduler' || true
sudo ETCDCTL_API=3 etcdctl member list --write-out=table
sudo ETCDCTL_API=3 etcdctl endpoint health --cluster
```

### 3단계 — control2 제거

control3 제거 후 API와 etcd가 정상일 때만 `control2`를 제거한다.

```bash
# 1. control2 일반 pod 이동
kubectl drain control2   --ignore-daemonsets   --delete-emptydir-data   --force   --grace-period=60   --timeout=10m

# 2. drain 후 남은 pod 확인
kubectl get pods -A --field-selector spec.nodeName=control2 -o wide

# 3. control2 etcd member remove
sudo ETCDCTL_API=3 etcdctl member remove edff4a024be5bf5f

# 4. control2에서 control-plane 프로세스가 다시 뜨지 않게 정지/비활성화
ssh control2 'sudo systemctl stop etcd kubelet'
ssh control2 'sudo systemctl disable etcd kubelet'

# 5. Kubernetes node 제거
kubectl delete node control2
```

control2 제거 후에는 control1의 kube-apiserver static manifest에 남아 있는 `--etcd-servers`와 `--apiserver-count`를 control1 단일 구조로 정리해야 한다.

### 4단계 — 최종 검증

```bash
kubectl get nodes -o wide
kubectl get --raw='/readyz?verbose'
sudo ETCDCTL_API=3 etcdctl member list --write-out=table
sudo ETCDCTL_API=3 etcdctl endpoint health --cluster
sudo ETCDCTL_API=3 etcdctl endpoint status --cluster --write-out=table
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get ds cilium -o wide
kubectl -n rook-ceph get cephcluster,cephblockpool,cephfilesystem,cephobjectstore 2>/dev/null || true
```

## Kubespray inventory 정리 계획

실제 node 제거 후 Kubespray inventory에서도 control-plane과 etcd 그룹을 정리해야 한다.

확인 대상 후보:

```text
/home/netai/chang/kubespray-v2.31/inventory/mycluster/inventory.ini
/home/netai/chang/Git/TwinX/kubespray/inventory/mycluster/inventory.ini
```

정리 원칙:

- `kube_control_plane`에는 `control1`만 남긴다.
- `etcd`에는 `control1`만 남긴다.
- worker node 목록은 의도적으로 제거하지 않는다.
- edgebox3/4는 전원 이슈가 해결될 때까지 별도 known issue로 남긴다.

## 중단 기준

아래 중 하나라도 발생하면 즉시 중단한다.

- snapshot 저장 또는 status 확인 실패
- `control1` etcd health 실패
- control2/control3에서 예상하지 못한 사용자 Docker container 발견
- `kubectl get --raw='/readyz?verbose'` 실패
- control3 제거 후 API server가 불안정해짐
- control3 제거 후 etcd member list 또는 endpoint health가 불안정함
- Cilium DaemonSet이 예상보다 크게 흔들림
- Rook-Ceph, Harbor, ArgoCD, Keycloak 중 핵심 서비스가 동시에 장애를 보임

## Rollback 개념

etcd member 제거 후에는 단순히 node를 다시 켠다고 자동 복구되지 않을 수 있다. 문제가 발생하면 우선 다음을 확인한다.

```bash
kubectl get nodes -o wide
sudo ETCDCTL_API=3 etcdctl member list --write-out=table
sudo ETCDCTL_API=3 etcdctl endpoint health --cluster
```

심각한 etcd 장애가 발생하면 저장한 snapshot을 기준으로 etcd restore 절차를 검토한다. 이 절차는 별도 장애 복구 절차로 취급한다.

## 실행 로그

### 2026-06-29 최종 결과 — control1 단일 control-plane 전환 완료

상태: 완료.

TwinX Kubernetes control-plane은 `control1` 단일 구조로 전환됐다. `control2`, `control3`는 Kubernetes Node와 etcd member에서 제거했고, API server와 etcd는 `control1`만 바라보도록 정리했다.

최종 구조:

| 항목 | 최종 상태 |
| --- | --- |
| Kubernetes API server | `control1` |
| etcd member | `etcd1` / `10.38.38.9` only |
| kube-controller-manager | `control1` |
| kube-scheduler | `control1` |
| control2 | Kubernetes Node 삭제, etcd/kubelet 비활성화 |
| control3 | Kubernetes Node 삭제, etcd/kubelet 비활성화 |

최종 검증 결과:

```text
kubectl get --raw='/readyz?verbose' -> readyz check passed
etcd member list -> etcd1 only
etcd endpoint health -> https://10.38.38.9:2379 true
control1 -> Ready / v1.35.4
control2 -> node object removed
control3 -> node object removed
control2/control3에 bound 된 pod -> 없음
```

최종 노드 상태 요약:

| 노드 | 상태 | 비고 |
| --- | --- | --- |
| control1 | Ready | 단일 control-plane / etcd |
| sv4000-1 | Ready | GPU Operator, NFD master, DRA controller 배치 |
| sv4000-2 | Ready | Partridge 전용 taint 유지 |
| l40s | Ready | Prometheus server 동작 |
| rm352-1 | Ready | GPU worker |
| rm352-2 | Ready | GPU worker |
| edgebox1 | Ready,SchedulingDisabled | v1.35.4, 별도 cordon 유지 |
| edgebox2 | Ready,SchedulingDisabled | v1.35.4, 별도 cordon 유지 |
| edgebox3 | NotReady,SchedulingDisabled | 전원/하드웨어 이슈, v1.34.3 |
| edgebox4 | NotReady,SchedulingDisabled | 전원/하드웨어 이슈, v1.34.3 |

### 2026-06-29 control2 제거 실행 결과

상태: `control2` 제거 완료. `control1` 단일 control-plane + 단일 etcd 구조로 안정화 확인.

작업 전 추가 snapshot:

```text
control1:/root/etcd-snapshot-before-control2-remove-2026-06-29-0746.db
```

snapshot 검증:

```text
etcdutl snapshot status 성공
hash: b558cff2
revision: 231134668
total keys: 3851
total size: 244 MB
file size: 233M
```

주요 작업:

1. `control2` drain
   - 일반 pod 이동 완료
   - DaemonSet/static pod만 control2에 남는 상태 확인
2. control2 etcd member 제거
   - removed member: `edff4a024be5bf5f` / `etcd2` / `10.38.38.17`
   - 남은 member: `65971c18597cb2e7` / `etcd1` / `10.38.38.9`
3. control1 kube-apiserver manifest 단일화
   - 백업 위치: `control1:/root/kube-apiserver.yaml.before-control2-remove-2026-06-29-075555`
   - 최종 값:

```text
--etcd-servers=https://10.38.38.9:2379
--apiserver-count=1
```

4. control2 control-plane 비활성화
   - static pod manifest 이동 위치: `control2:/root/k8s-control-plane-disabled-2026-06-29-075555`
   - `etcd`, `kubelet` stop/disable 완료
   - 남아 있던 Kubernetes CRI container 정리 완료
5. Kubernetes Node 삭제
   - `kubectl delete node control2` 완료

control2 drain으로 이동한 주요 pod:

| Namespace | 기존 pod | 이동/대체 결과 |
| --- | --- | --- |
| gpu-operator | `gpu-operator-797b5df7dc-mrc4h` | 이후 GitOps 수정으로 `sv4000-1` 배치 |
| gpu-operator | `gpu-operator-node-feature-discovery-master-...` | 이후 GitOps 수정으로 `sv4000-1` 배치 |
| kube-system | `coredns-847b7d7cc7-tz545` | `l40s`에 새 replica Running |
| monitoring | `tx-gateway-collector-1` | `control1`에 재생성 Running |
| nvidia-dra-driver-gpu | `nvidia-dra-driver-gpu-controller-...` | 이후 GitOps 수정으로 `sv4000-1` 배치 |

control2 제거 후 일시 현상:

- control1이 kube-apiserver manifest 재시작 직후 잠시 `NotReady`로 표시됐다.
- 원인: kubelet status 갱신 지연으로 보이며, 곧 `Ready`로 회복됐다.
- API `/readyz`와 etcd health는 정상 확인됐다.

### 2026-06-29 control1 부담 감소를 위한 controller 재배치

control-plane 단일화 후 GPU/DRA 관련 controller가 control1로 몰리는 현상이 있었다. 단일 control-plane 안정성을 위해 GitOps values를 수정하여 GPU worker인 `sv4000-1`로 옮겼다.

변경한 TwinX-Ops commit:

| Commit | 내용 | 결과 |
| --- | --- | --- |
| `4962d7b` | `Move GPU operator off control1` | GPU Operator controller를 `sv4000-1`로 이동 |
| `1212bb1` | `Move DRA controller off control1` | DRA controller 이동 시도 |
| `7d2955f` | `Fix DRA controller affinity` | chart 기본 control-plane affinity 제거 후 `sv4000-1` 이동 성공 |

GPU Operator values 변경:

```yaml
operator:
  nodeSelector:
    kubernetes.io/hostname: sv4000-1
  tolerations: []
  affinity: {}

node-feature-discovery:
  master:
    nodeSelector:
      kubernetes.io/hostname: sv4000-1
    tolerations: []
    affinity: {}
```

DRA driver values 변경:

```yaml
controller:
  nodeSelector:
    kubernetes.io/hostname: sv4000-1
  tolerations: []
  affinity: null
```

`affinity: null`을 사용한 이유:

- NVIDIA DRA chart 기본값은 controller에 `node-role.kubernetes.io/control-plane` required affinity를 갖는다.
- `affinity: {}`는 Helm values merge 과정에서 기본 affinity를 제거하지 못했다.
- `affinity: null`로 렌더링했을 때 기본 control-plane affinity가 제거되는 것을 확인했다.

재배치 검증 결과:

```text
gpu-operator-64bf74d6dc-qhxxx -> sv4000-1 / 1/1 Running
gpu-operator-node-feature-discovery-master-6fd9cb8cf6-kk9z7 -> sv4000-1 / 1/1 Running
nvidia-dra-driver-gpu-controller-7cf68bfb65-v6bmg -> sv4000-1 / 1/1 Running
DRA controller log -> Kubernetes API 10.234.0.1:443 응답 200 OK, informer cache populated
```

### 2026-06-29 최종 known issue 및 남은 작업

이번 control-plane 단일화 작업에서 해결하지 않은 항목은 아래와 같다.

| 항목 | 상태 | 후속 작업 |
| --- | --- | --- |
| edgebox3/4 | `NotReady,SchedulingDisabled`, 전원/하드웨어 이슈 | 전원 복구 후 v1.35.4 업그레이드 재개 |
| MinIO 일부 pod | `Pending` 유지 | 기존 스토리지/스케줄링 이슈로 분리, 이번 작업에서 삭제/수정하지 않음 |
| Cilium operator live patch | 임시로 edgebox/control3 회피 | Cilium GitOps 전환 시 values로 영속화 필요 |
| `tx-gateway-collector-0/1` | 현재 control1에 Running | control1 부담을 더 줄일 때 monitoring values에서 별도 재배치 검토 |
| Kubespray inventory | control2/control3가 파일에 남아 있을 수 있음 | 실제 토폴로지에 맞게 control-plane/etcd 그룹 정리 필요 |

결론:

```text
TwinX control-plane 단일화는 완료됐다.
운영 기준 control-plane/etcd는 control1 하나만 사용한다.
GPU Operator, NFD master, DRA controller는 control1에서 sv4000-1로 이동 완료했다.
```






### 2026-06-29 control3 제거 실행 결과

상태: `control3` 제거 완료. `control1`/`control2` 2대 control-plane + 2대 etcd 구조로 안정화 확인.

실행한 주요 작업:

1. `control3` drain
   - `cilium-operator`, `prometheus-server-0`, `tx-gateway-collector-0` evict 완료
   - DaemonSet/static pod만 control3에 남는 상태 확인
2. Prometheus GitOps 원본 수정
   - TwinX-Ops commit: `0d0786c Relax Prometheus node pinning`
   - 파일: `argocd/monitoring/apps/prometheus/values.yaml`
   - 변경: `server.nodeSelector: {}`
   - 이유: `prometheus-server-0`가 `control3`에 고정되어 Pending이 되었기 때문
   - ArgoCD sync 후 `prometheus-server-0`는 `l40s`에서 `2/2 Running`
3. Cilium operator 임시 운영 조치
   - 기존 operator 1개가 `sv4000-2`에 있었고, 새 replica가 NotReady edgebox3/4로 계속 배정됨
   - 원인: Cilium operator의 넓은 `tolerations: [{operator: Exists}]`와 required podAntiAffinity
   - 임시 live patch로 `edgebox1`, `edgebox2`, `edgebox3`, `edgebox4`, `control3`를 피하도록 nodeAffinity 추가
   - 결과: operator 2개가 `rm352-2`, `l40s`에서 Running
   - 주의: Cilium은 아직 GitOps 관리가 아니므로 이 live patch는 향후 Helm/Kubespray 재적용 시 덮일 수 있다. Cilium GitOps 전환 때 정식 values에 반영해야 한다.
4. etcd member 제거
   - removed member: `c7b8a81e21db4ac9` / `etcd3` / `10.38.38.25`
   - 남은 member: `etcd1` `10.38.38.9`, `etcd2` `10.38.38.17`
5. control3 control-plane 비활성화
   - `/etc/kubernetes/manifests` 아래 static pod manifest 백업/이동
   - 백업 위치: `control3:/root/k8s-control-plane-disabled-2026-06-29-073847`
   - `etcd`, `kubelet` stop/disable 완료
   - orphan `kube-apiserver` container stop 완료
6. Kubernetes Node 삭제
   - `kubectl delete node control3` 완료
7. control1/control2 kube-apiserver manifest 정리
   - `--etcd-servers=https://10.38.38.9:2379,https://10.38.38.17:2379`
   - `--apiserver-count=2`
   - 백업 위치:
     - `control1:/root/kube-apiserver.yaml.before-control3-remove-2026-06-29-073847`
     - `control2:/root/kube-apiserver.yaml.before-control3-remove-2026-06-29-073847`

검증 결과:

```text
kubectl get --raw='/readyz?verbose' -> readyz check passed
etcd members -> etcd1, etcd2 only
etcd endpoint health -> control1/control2 healthy
control3 Kubernetes Node -> deleted
control3에 남은 Kubernetes pod -> 없음
kube-apiserver-control1 -> 1/1 Running
kube-apiserver-control2 -> 1/1 Running
prometheus-server-0 -> 2/2 Running on l40s
cilium-operator -> 2/2 Running on rm352-2, l40s
rook-ceph -> Ready / HEALTH_WARN 유지
```

남은 known issue:

- edgebox3/4는 기존처럼 `NotReady,SchedulingDisabled` 상태다.
- MinIO 일부 pod Pending은 기존 이슈로 유지된다.
- Cilium DaemonSet desired/ready는 edgebox3/4 때문에 `11 desired / 9 ready` 상태다.
- Cilium operator 임시 live affinity는 GitOps/Helm 영속 설정이 아니므로 Cilium GitOps 전환 시 정리 필요.
- control2 제거는 아직 진행하지 않았다.

다음 단계:

1. control3 제거 상태를 잠시 관찰한다.
2. 이상 없으면 같은 패턴으로 control2 제거를 진행한다.
3. control2 제거 후 control1의 kube-apiserver를 `--etcd-servers=https://10.38.38.9:2379`, `--apiserver-count=1`로 정리한다.
4. Kubespray inventory와 TwinX 운영 문서에서 control-plane/etcd 그룹을 최종 상태에 맞게 정리한다.

### 2026-06-29 제거 직전 영향 확인

- control2/control3에서 `docker` binary는 발견되지 않았다.
- control2/control3에는 일반 Docker container가 아니라 containerd가 관리하는 Kubernetes pod만 있었다.
- 따라서 직접 Docker container 보호 때문에 `kubectl drain`을 피할 필요는 낮다.
- 오히려 `prometheus-server-0`, `tx-gateway-collector`, `coredns`, `cilium-operator` 같은 일반 Kubernetes pod를 안전하게 옮기기 위해 제거 전 drain을 수행하는 편이 낫다.

control2에서 확인된 주요 non-DaemonSet pod:

| Namespace | Pod | Owner | 비고 |
| --- | --- | --- | --- |
| gpu-operator | `gpu-operator-797b5df7dc-mrc4h` | Deployment/ReplicaSet | 재스케줄 가능 |
| gpu-operator | `gpu-operator-node-feature-discovery-master-...` | Deployment/ReplicaSet | 재스케줄 가능 |
| kube-system | `coredns-847b7d7cc7-tz545` | Deployment/ReplicaSet | CoreDNS 2 replicas 중 1개 |
| monitoring | `tx-gateway-collector-1` | StatefulSet | PDB `maxUnavailable: 1` 존재 |
| nvidia-dra-driver-gpu | `nvidia-dra-driver-gpu-controller-...` | Deployment/ReplicaSet | 재스케줄 가능 |

control3에서 확인된 주요 non-DaemonSet pod:

| Namespace | Pod | Owner | 비고 |
| --- | --- | --- | --- |
| kube-system | `cilium-operator-56fb7bcb48-696qn` | Deployment/ReplicaSet | 2 replicas 중 1개 |
| monitoring | `prometheus-server-0` | StatefulSet | Rook-Ceph Block RWO PVC 사용 |
| monitoring | `tx-gateway-collector-0` | StatefulSet | PDB `maxUnavailable: 1` 존재 |

`prometheus-server-0`의 PVC:

```text
monitoring/storage-volume-prometheus-server-0
storageClass: rook-ceph-block
accessMode: RWO
size: 20Gi
```

이 PVC는 local PV가 아니라 Rook-Ceph block이므로 다른 노드로 재attach 가능하다. 다만 노드 제거 전에 drain으로 정상 detach/reattach 경로를 밟는 것이 안전하다.

확인 결과 저장 위치:

```text
/tmp/twinx-control-plane-final-check-2026-06-29-071725/check.txt
/tmp/twinx-control-plane-pod-impact-2026-06-29-071802/impact.txt
```

### 2026-06-29 계획 기록

- 상태: 계획 작성 완료
- 실제 control-plane 제거: 아직 진행하지 않음
- preflight: API readyz 통과, control1/control2/control3 Ready 확인
- known issue: edgebox3/4는 NotReady,SchedulingDisabled 상태이며 전원/하드웨어 문제로 별도 분리
- etcd health: control1/control2/control3 모두 healthy
- etcd leader: control1
- etcd snapshot: `control1:/root/etcd-snapshot-before-single-control-plane-2026-06-29-0701.db` 저장 완료
- snapshot 검증: `etcdutl snapshot status` 성공, revision `231105727`, size `244 MB`
- 보안 결정: snapshot 파일은 GitHub에 올리지 않고 위치와 검증 결과만 기록
- 실행 전략 결정: Kubespray 전체 실행은 피하고 control-plane 대상 수동/외과적 제거를 우선
- Docker/containerd 확인: control2/control3에는 일반 Docker container 없음, Kubernetes pod만 확인됨
- 영향 확인: control3에는 `prometheus-server-0` RWO Ceph PVC pod가 있어 drain 후 제거가 더 안전함
- control3 제거: 완료
- 현재 상태: control1/control2 2대 control-plane + 2대 etcd 구조
- 다음 단계: 안정화 관찰 후 control2 제거 여부 결정

