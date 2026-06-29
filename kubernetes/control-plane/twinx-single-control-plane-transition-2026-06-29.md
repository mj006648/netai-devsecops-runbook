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

### 1단계 — control3 제거

먼저 `control3`부터 제거한다. 이유는 한 번에 두 member를 제거하지 않고, quorum과 API 동작을 단계별로 확인하기 위해서다.

예상 흐름:

```bash
# member id 확인
sudo ETCDCTL_API=3 etcdctl member list --write-out=table

# control3 member remove
sudo ETCDCTL_API=3 etcdctl member remove <CONTROL3_MEMBER_ID>

# control3에서 control-plane 프로세스가 다시 뜨지 않게 정지/비활성화
ssh control3 'sudo systemctl stop etcd kubelet'
ssh control3 'sudo systemctl disable etcd kubelet'

# Kubernetes node 제거
kubectl delete node control3
```

`kubectl drain`은 Kubernetes pod만 대상으로 하며 직접 Docker container를 내리지는 않는다. 하지만 control-plane 제거 목적에서는 static pod와 etcd/kubelet 정리가 더 중요하므로, drain은 필수 경로로 보지 않는다.

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
sudo ETCDCTL_API=3 etcdctl member remove <CONTROL2_MEMBER_ID>
ssh control2 'sudo systemctl stop etcd kubelet'
ssh control2 'sudo systemctl disable etcd kubelet'
kubectl delete node control2
```

control2 제거 후에는 control1의 kube-apiserver static manifest에 남아 있는 `--etcd-servers`와 `--apiserver-count` 정리가 필요한지 확인한다.

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
- 다음 단계: control2/control3 Docker 상태 확인 후 control3부터 제거 여부 결정

