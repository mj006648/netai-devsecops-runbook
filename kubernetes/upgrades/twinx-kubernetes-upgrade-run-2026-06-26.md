# TwinX Kubernetes 업그레이드 작업 기록 2026-06-26

## 요약

2026-06-26 UTC / 2026-06-27 KST 유지보수 시간에 수행한 TwinX Kubernetes v1.35.4 업그레이드 기록입니다.

```text
시작 상태: 이전 v1.34 업그레이드 이후 대부분 노드는 Kubernetes v1.34.3 상태
목표:      Kubespray v2.31.0 기반 Kubernetes v1.35.4 업그레이드
결과:      control-plane, 주요 GPU/스토리지 worker, edgebox1, edgebox2를 v1.35.4로 업그레이드
보류:      edgebox3, edgebox4는 이전 v1.34 업그레이드 이후 NotReady 상태였기 때문에 이번 v1.35 작업에서 제외
Hubble:    이번 작업에서는 활성화하지 않음
OTP:       edgebox3/4 후속 판단 전까지 control-plane의 임시 SSH OTP 우회 설정 유지
```

중요한 구분:

- `edgebox3/4`는 과거 `v1.33 -> v1.34` 업그레이드 이후 NotReady가 된 것으로 보이며, 해당 원인은 별도 조사 대상입니다.
- 이번 `v1.35.4` 업그레이드 wave에서는 `edgebox3/4`에 Kubespray 업그레이드를 실행하지 않았습니다.
- 이번 작업 중 `edgebox3/4`에 대해 확인되는 직접 조치는 `cordon`, 상태 확인, ping/BMC reachability 확인 수준입니다.

작업 후 기록한 최종 노드 상태:

| 노드 | 상태 | 버전 | 런타임 | 판단 |
| --- | --- | --- | --- | --- |
| `control1` | Ready | v1.35.4 | containerd 2.2.3 | 업그레이드 완료 |
| `control2` | Ready | v1.35.4 | containerd 2.2.3 | 업그레이드 완료 |
| `control3` | Ready | v1.35.4 | containerd 2.2.3 | 업그레이드 완료 |
| `sv4000-1` | Ready | v1.35.4 | containerd 2.2.3 | 업그레이드 완료 |
| `sv4000-2` | Ready | v1.35.4 | containerd 2.2.3 | 업그레이드 완료 |
| `l40s` | Ready | v1.35.4 | containerd 2.2.3 | 업그레이드 완료 |
| `rm352-1` | Ready | v1.35.4 | containerd 2.2.3 | 업그레이드 완료 |
| `rm352-2` | Ready | v1.35.4 | containerd 2.2.3 | 업그레이드 완료 |
| `edgebox1` | Ready,SchedulingDisabled | v1.35.4 | containerd 2.2.3 | no-drain 후속 작업으로 업그레이드 완료 |
| `edgebox2` | Ready,SchedulingDisabled | v1.35.4 | containerd 2.2.3 | no-drain 후속 작업으로 업그레이드 완료 |
| `edgebox3` | NotReady,SchedulingDisabled | v1.34.3 | containerd 2.2.1 | 이번 v1.35 작업 제외; 기존 node/network 문제 |
| `edgebox4` | NotReady,SchedulingDisabled | v1.34.3 | containerd 2.2.1 | 이번 v1.35 작업 제외; 기존 node/network 문제 |

## 주요 결정

| 항목 | 결정 |
| --- | --- |
| 업그레이드 방식 | Kubespray v2.31.0의 `upgrade-cluster.yml`로 Kubernetes v1.35.4 업그레이드 |
| drain 정책 | Rook-Ceph, Harbor, MinIO, GPU workload 때문에 일반 drain은 위험하므로 storage/GPU worker는 no-drain으로 진행 |
| Hubble | Cilium이 아직 GitOps가 아니라 Kubespray 관리 상태이므로 이번 작업에서는 Hubble 미활성화 |
| Edgebox | 메인 wave 이후 `edgebox1/2`만 하나씩 no-drain으로 업그레이드. `edgebox3/4`는 NotReady 상태라 power/link/network 복구 전까지 보류 |
| OTP 우회 | edgebox3/4 후속 판단 전까지 control-plane의 임시 SSH OTP 우회 유지. 이후 rollback 필요 |
| Ceph `noout` | Ceph-heavy 노드 작업 중 임시 사용 후 해제. 최종 flag에는 `noout` 없음 |

## 사용한 명령 패턴

worker 노드 no-drain 업그레이드 명령 형태:

```bash
cd /home/netai/chang/kubespray-v2.31
source /home/netai/ansible-venv-kubespray-2.31/bin/activate
ansible-playbook -i inventory/mycluster/inventory.ini upgrade-cluster.yml \
  -b -v \
  --limit <node> \
  -e '{"drain_nodes": false}'
```

중요: `drain_nodes`는 JSON boolean으로 넘겨야 합니다. `-e drain_nodes=false`처럼 문자열로 넘기면 의도와 다르게 동작할 수 있습니다.

## Kubespray v2.31 no-drain 패치

`l40s` 작업 중 `-e '{"drain_nodes": false}'`를 넘겼는데도 Kubespray v2.31이 worker drain task를 실행하려고 했습니다. 문제가 된 경로:

```text
/home/netai/chang/kubespray-v2.31/roles/remove_node/pre_remove/tasks/main.yml
```

로컬 Kubespray checkout에 아래 remove-node pre-remove task들이 `drain_nodes | default(true) | bool` 조건을 보도록 패치했습니다.

```text
Remove-node | Drain node except daemonsets resource
Remove-node | Wait until Volumes will be detached from the node
```

패치 후 검증:

```text
ansible-playbook --syntax-check ... upgrade-cluster.yml: 통과
rm352-1, rm352-2: cordon은 발생했지만 실제 kubectl drain은 실행되지 않았고 업그레이드 성공
```

주의: 남은 edgebox 작업에 새로운 Kubespray checkout을 사용하면 `drain_nodes=false`를 쓰기 전에 이 패치가 들어가 있는지 다시 확인해야 합니다.

## 백업 및 복구 자료

민감한 백업 파일은 repository에 커밋하지 않습니다.

최신 v1.35 작업 전 백업 경로:

```text
/home/netai/chang/Git/twinx-upgrade-backups/20260626T162036Z-before-v135
```

주요 백업 근거:

```text
etcd-snapshot-control1.db
sha256: 5e4f7ca25c25d6ccae15e55205cd9b044cc83dd75d00253e43903b31192a9cfd
```

Kubespray도 control-plane 노드에 etcd snapshot을 생성했습니다.

```text
/var/backups/etcd-2026-06-26_16:36:32/snapshot.db
```

## OTP 우회 상태

Ansible이 대화형 OTP에서 막히지 않도록 업그레이드 전에 control-plane 노드의 `netai` 사용자에 대해 임시 SSH OTP 우회를 적용했습니다.

```text
# BEGIN NETAI TEMP OTP BYPASS 2026-06-26
Match User netai
    AuthenticationMethods publickey
# END NETAI TEMP OTP BYPASS 2026-06-26
```

현재 결정: 아직 rollback하지 않습니다. `edgebox3/4` 후속 판단이 끝날 때까지 유지합니다.

edgebox3/4 후속 판단이 끝난 뒤 실행할 rollback 명령:

```bash
/tmp/rollback_netai_otp_bypass.sh
```

메모: 한 번 rollback을 시도하려다 사용자가 edgebox 완료 전까지 유지하기로 결정해 중단했습니다. 첫 스크립트 시도는 원격 파일을 바꾸기 전에 실패했으며, 원인은 `/bin/sh`가 `set -o pipefail`을 지원하지 않았기 때문입니다.

## 작업 로그

| 시점 | 작업 | 결과 |
| --- | --- | --- |
| 사전 작업 | Preflight 및 백업 | etcd/control-plane 백업 생성, cluster risk 확인 |
| 사전 작업 | Kubespray v2.31.0 준비 | inventory 복사, Kubernetes target v1.35.4 설정, validation 통과 |
| v1.35 wave | `control1` | v1.35.4 업그레이드 완료. 초기 명령 문법 때문에 drain 시도가 있었으나 복구 후 계속 진행 |
| v1.35 wave | `control2` | no-drain JSON variable로 v1.35.4 업그레이드 완료 |
| v1.35 wave | `control3` | no-drain JSON variable로 v1.35.4 업그레이드 완료 |
| v1.35 wave | `sv4000-1` | v1.35.4 업그레이드 완료 |
| v1.35 wave | `sv4000-2` | v1.35.4 업그레이드 완료 |
| v1.35 wave | `l40s` 1차 시도 | `drain_nodes=false`에도 Kubespray v2.31이 worker drain을 실행하려 해 중단 후 uncordon |
| v1.35 wave | Kubespray 패치 | 로컬 v2.31 remove-node pre-remove task가 `drain_nodes=false`를 존중하도록 패치 |
| v1.35 wave | `l40s` 재시도 | v1.35.4 업그레이드 완료. 이후 Cilium/kube-proxy/Rook-Ceph pod Running 확인 |
| v1.35 wave | Ceph flag 정리 | Ceph-heavy 작업 후 `noout` 해제. 최종 flag에 `noout` 없음 |
| v1.35 wave | `rm352-1` | v1.35.4 업그레이드 완료. play recap `failed=0`, 실제 drain skip |
| v1.35 wave | `rm352-2` | v1.35.4 업그레이드 완료. play recap `failed=0`, 실제 drain skip |
| 메인 wave 최종 확인 | Cluster 검증 | 주요 업그레이드 노드 Ready on v1.35.4, etcd healthy, edgebox1-4는 당시 보류 상태 |
| edgebox 후속 작업 | `edgebox1` | `drain_nodes=false`로 v1.35.4 업그레이드 완료. play recap `failed=0`, `kubectl drain edgebox1` 프로세스 미관측 |
| edgebox 후속 작업 | `edgebox2` | `drain_nodes=false`로 v1.35.4 업그레이드 완료. play recap `failed=0`, `kubectl drain edgebox2` 프로세스 미관측 |
| edgebox 후속 검증 | edgebox 상태 확인 | edgebox1/2 Ready on v1.35.4, Cilium/kube-proxy/nginx-proxy Running, edgebox1/2 MinIO pod Running |
| edgebox 보류 | `edgebox3/4` | 이번 v1.35 업그레이드는 실행하지 않음. v1.34.3 NotReady 상태로 남김 |

## 최종 검증 근거

### rm352-2 업그레이드 후

```text
rm352-2 Ready v1.35.4 containerd://2.2.3
Cilium: cilium-89hzl Running
kube-proxy: kube-proxy-sw6g2 Running
Rook-Ceph pods on rm352-2: Running
Non-running pods on rm352-2: none
```

### edgebox1/2 업그레이드 후

```text
edgebox1 Ready,SchedulingDisabled v1.35.4 containerd://2.2.3
edgebox2 Ready,SchedulingDisabled v1.35.4 containerd://2.2.3
```

edgebox1/2의 core system pod:

```text
edgebox1: cilium, cilium-envoy, kube-proxy, nginx-proxy Running
edgebox2: cilium, cilium-envoy, kube-proxy, nginx-proxy Running
```

workload 확인:

```text
edgebox1/2 non-running pods: none
minio-0 and minio-6 on edgebox1: Running
minio-1 and minio-3 on edgebox2: Running
```

### etcd 상태

```text
https://10.38.38.9:2379  healthy
https://10.38.38.17:2379 healthy
https://10.38.38.25:2379 healthy
```

### 메인 wave 이후 Ceph 상태

Ceph는 동작 중이지만, 기존 warning 상태가 남아 있습니다.

```text
health: HEALTH_WARN
mon: 3 daemons, quorum e,f,h
mgr: a active, b standby
mds: 1/1 up, 1 hot standby
osd: 3 osds, 3 up, 3 in
pgs: 248 active+clean, 33 undersized+peered
flags: sortbitwise,recovery_deletes,purged_snapdirs,pglog_hardlimit
```

`noout` flag는 남아 있지 않습니다.

### 최종 확인 시점의 known non-running pod

```text
harbor/habor-harbor-jobservice-74c6fb9b97-s4g95   ContainerCreating on l40s
harbor/habor-harbor-registry-68df8bfb68-czpss     ContainerCreating on l40s
kube-system/kube-proxy-m7vxw                       Pending on edgebox4
kube-system/kube-proxy-stlt8                       Pending on edgebox3
minio/minio-2                                      Terminating on edgebox3
minio/minio-4                                      Terminating on edgebox4
minio/minio-5                                      Terminating on edgebox3
minio/minio-7                                      Terminating on edgebox4
```

해석:

- edgebox3/4 관련 Pending/Terminating pod는 남은 edgebox 보류 작업에 속합니다.
- `l40s`의 Harbor pod는 별도의 RWO/Multi-Attach 계열 정리 항목이며 Kubernetes 노드 업그레이드 blocking 이슈로 보지는 않았습니다.

## 남은 edgebox 작업

edgebox1/2는 후속 작업으로 완료했습니다. edgebox3/4는 둘 다 NotReady 상태였기 때문에 의도적으로 완료하지 않았습니다.

현재 edgebox 상태:

```text
edgebox1: v1.35.4, Ready,SchedulingDisabled
edgebox2: v1.35.4, Ready,SchedulingDisabled
edgebox3: v1.34.3, NotReady,SchedulingDisabled
edgebox4: v1.34.3, NotReady,SchedulingDisabled
```

edgebox3/4 업그레이드 전 확인할 것:

1. `edgebox3`, `edgebox4`의 전원, 링크, BMC, SSH reachability를 먼저 확인합니다.
2. edgebox MinIO pod를 정리할 수 있는지, 먼저 복구가 필요한지 결정합니다.
3. fresh Kubespray checkout을 사용한다면 no-drain 패치가 있는지 다시 확인합니다.
4. 남은 edgebox 노드는 병렬이 아니라 하나씩 업그레이드합니다.
5. 각 노드 작업 후 kubelet, Cilium, kube-proxy를 확인합니다.
6. 남은 edgebox 판단이 끝난 뒤에만 임시 OTP 우회를 rollback합니다.

## 2026-06-29 edgebox3/4 전원 이슈 메모

2026-06-29 확인 시점에 `edgebox3/4`는 Kubernetes/BMC 네트워크 모두 reachability가 없었고, 현장 확인 결과 전원 자체가 들어오지 않는 상태로 보고되었습니다.

확인된 점:

- 이번 v1.35 작업에서는 `edgebox3/4`에 Kubespray 업그레이드를 실행하지 않았습니다.
- runbook과 shell history 기준 `edgebox3/4`에 대해 확인되는 직접 작업은 `kubectl cordon`, ping/BMC reachability 확인 수준입니다.
- `shutdown`, `reboot`, `poweroff`, `ipmitool power off` 같은 전원 관련 명령 흔적은 확인되지 않았습니다.
- BMC까지 응답하지 않는 경우는 Kubernetes/Kubespray보다 DC power, PDU, PSU, 배선, 랙 전원 경로 문제를 우선 의심해야 합니다.

전원 복구 후 확인할 명령:

```bash
last -x | head -50
uptime
journalctl --since "2026-06-28 05:30" --until "2026-06-28 07:00" --no-pager | tail -200
journalctl -u kubelet -u containerd --since "2 hours ago" --no-pager
ip addr
ip route
systemctl status kubelet containerd --no-pager
```

## 남은 리스크

| 리스크 | 상태 | 다음 조치 |
| --- | --- | --- |
| edgebox3/4 v1.35 미적용 | 임시 skew 허용 | 전원/link/SSH 복구 후 다음 maintenance window에서 처리 |
| edgebox3/4 NotReady | 미해결 | power/link/BMC/SSH/network 확인 |
| edgebox3/4 물리 전원 이슈 | 2026-06-29 현장 확인 필요 | DC power, PDU, PSU, 배선 확인 후 OS 로그 확인 |
| Harbor registry/jobservice ContainerCreating | 미해결 | RWO volume attachment와 old pod 정리 확인 |
| Ceph HEALTH_WARN | baseline warning 유지 | PG, mon disk usage, scrub backlog, no-replica pool 모니터링 |
| OTP 우회 유지 중 | 의도적 임시 상태 | edgebox3/4 판단 완료 후 rollback |
| Hubble 미활성화 | 의도적 | Cilium GitOps/values 계획 후 별도 활성화 |

## 다음 edgebox 작업 중단 조건

아래 상황이 하나라도 발생하면 다음 edgebox 노드로 넘어가지 않습니다.

```text
- etcd endpoint health 실패
- 현재 Ready인 업그레이드 완료 노드가 NotReady로 회귀
- 대상 노드의 Cilium이 Ready가 되지 않음
- 대상 노드의 kube-proxy가 Running이 되지 않음
- Ceph warning 상태가 현재 baseline보다 악화
- MinIO 정리가 다른 노드에 예상치 못한 영향을 줌
- no-drain 의도와 다르게 Kubespray가 실제 drain을 시작
```
