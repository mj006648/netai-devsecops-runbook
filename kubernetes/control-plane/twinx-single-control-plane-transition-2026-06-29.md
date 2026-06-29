# TwinX 단일 Control Plane 전환 계획 및 실행 로그 2026-06-29

## 요약

TwinX 클러스터의 control-plane을 3대 구조에서 `control1` 1대 구조로 줄이는 작업 계획과 실행 로그다.

현재 작업 방향은 다음과 같다.

- `control1`을 최종 단일 control-plane으로 남긴다.
- `control2`, `control3`는 Kubernetes control-plane과 etcd member에서 제거한다.
- edgebox3/4는 전원 이슈가 있으므로 이 작업의 직접 blocker로 보지 않고, 별도 복구/업그레이드 대상으로 분리한다.
- Cilium GitOps 전환, Hubble enable, KubeVirt 배포는 이 작업과 같은 maintenance window에서 진행하지 않는다.
- etcd snapshot과 health 확인 전에는 어떤 control-plane 제거도 진행하지 않는다.

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

### 1단계 — control3 제거

먼저 `control3`부터 제거한다. 이유는 한 번에 두 member를 제거하지 않고, quorum과 API 동작을 단계별로 확인하기 위해서다.

예상 흐름:

```bash
# member id 확인
sudo ETCDCTL_API=3 etcdctl member list --write-out=table

# control3 member remove
sudo ETCDCTL_API=3 etcdctl member remove <CONTROL3_MEMBER_ID>

# Kubernetes node 제거
kubectl drain control3 --ignore-daemonsets --delete-emptydir-data --force --grace-period=30 --timeout=5m || true
kubectl delete node control3
```

실제 drain이 불필요하거나 node가 이미 NotReady면 `kubectl delete node control3`만 수행할 수 있다. 단, etcd member 제거가 먼저다.

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
kubectl drain control2 --ignore-daemonsets --delete-emptydir-data --force --grace-period=30 --timeout=5m || true
kubectl delete node control2
```

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
- etcd snapshot: 아직 진행하지 않음
- 다음 단계: preflight 및 snapshot 수행

