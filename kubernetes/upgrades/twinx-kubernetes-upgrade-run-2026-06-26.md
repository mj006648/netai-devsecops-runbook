# TwinX Kubernetes Upgrade Run 2026-06-26

## Summary

2026-06-26 13:00 KST 작업창에서 TwinX Kubernetes 업그레이드를 진행하기 위한 실행 로그와 당일 계획이다.
목표는 전체 노드를 무리하게 한 번에 끝내는 것이 아니라, preflight 결과를 보고 안전한 범위부터 단계적으로 진행하는 것이다.

```text
current: Kubernetes v1.33.3
target:  Kubernetes v1.35.4
path:    v1.33.3 -> v1.34.x -> v1.35.4
```

## What is preflight?

Preflight는 업그레이드 실행 전에 클러스터가 업그레이드를 받을 수 있는 상태인지 확인하는 사전 점검이다.
여기서 실패하면 업그레이드를 시작하지 않거나, 위험 노드를 제외하고 범위를 줄인다.

Preflight에서 보는 핵심은 다음과 같다.

- Ansible이 모든 대상 노드에 비대화형 SSH/sudo로 접속 가능한가
- etcd와 control-plane이 정상인가
- Rook-Ceph 상태가 악화되어 있지 않은가
- drain을 막을 PDB나 stateful workload가 어디에 있는가
- Cilium health가 전체 노드에서 정상인가
- Harbor registry PVC/RBD attachment가 꼬여 있지 않은가
- ArgoCD가 작업 중 민감한 앱을 자동으로 건드릴 가능성이 있는가

## Completed before upgrade

### 1. Control-plane OTP temporary bypass

Kubespray/Ansible은 control-plane 3대에 반복적으로 SSH 접속한다. Google OTP가 남아 있으면 playbook 중간에 멈출 수 있으므로, 작업 시간 동안 `netai` 계정의 SSH 공개키 접속만 OTP 없이 통과하도록 임시 설정했다.

적용 대상:

| Node | Result |
| --- | --- |
| `control1` | applied |
| `control2` | applied |
| `control3` | applied |

적용 방식:

```text
/etc/ssh/sshd_config

# BEGIN NETAI TEMP OTP BYPASS 2026-06-26
Match User netai
    AuthenticationMethods publickey
# END NETAI TEMP OTP BYPASS 2026-06-26
```

백업 파일:

| Node | Backup |
| --- | --- |
| `control1` | `/etc/ssh/sshd_config.netai-otp-bypass-20260626025816.bak` |
| `control2` | `/etc/ssh/sshd_config.netai-otp-bypass-20260626030319.bak` |
| `control3` | `/etc/ssh/sshd_config.netai-otp-bypass-20260626030319.bak` |

검증 결과:

```text
ansible kube_control_plane -m ping: success on control1/control2/control3
ansible kube_control_plane -m command -a 'sudo -n true': success on control1/control2/control3
ansible all -m ping: success on all nodes
ansible all -m command -a 'sudo -n true': success on all nodes
```

원복 명령:

```bash
/tmp/rollback_netai_otp_bypass.sh
```

작업 종료 후 반드시 실행한다.

## Preflight checklist

### Access / automation

- [x] `netai` account can SSH to `control1`, `control2`, `control3` without OTP during the work window
- [x] `ansible -i inventory/mycluster/inventory.ini kube_control_plane -m ping`
- [x] `ansible -i inventory/mycluster/inventory.ini kube_control_plane -m command -a 'sudo -n true'`
- [x] `ansible -i inventory/mycluster/inventory.ini all -m ping`
- [x] `ansible -i inventory/mycluster/inventory.ini all -m command -a 'sudo -n true'`

### Cluster state

- [ ] `kubectl get nodes -o wide`
- [ ] `kubectl get pods -A -o wide`
- [ ] `kubectl get pdb -A`
- [ ] `kubectl get apiservices`
- [ ] `kubectl get events -A --sort-by=.lastTimestamp`

### etcd / control-plane

- [ ] etcd endpoint health
- [ ] etcd snapshot
- [ ] `/etc/kubernetes` backup on control-plane nodes
- [ ] kube-apiserver, kube-controller-manager, kube-scheduler pod status check

### Cilium / networking

- [ ] Cilium agent pods status
- [ ] Cilium health `12/12 reachable`
- [ ] rm352-1 / rm352-2 Cilium health and pod-to-node/API connectivity check
- [ ] Decide whether Cilium version should be pinned during Kubernetes upgrade

### Rook-Ceph / storage

- [ ] `ceph status`
- [ ] `ceph health detail`
- [ ] Ceph MON quorum check
- [ ] OSD status check
- [ ] Confirm whether `l40s` and `sv4000-1` must be excluded from today's upgrade scope

### Harbor

- [ ] `kubectl -n harbor get pods,pvc -o wide`
- [ ] Harbor registry 500Gi RWO PVC attachment check
- [ ] Decide whether `rm352-1` is excluded until Harbor registry is stable

### Partridge

- [ ] `kubectl -n partridge get pods -o wide`
- [ ] Confirm `sv4000-2` downtime policy
- [ ] Keep `sv4000-2` out of the first upgrade wave unless downtime is accepted

### GitOps / ArgoCD

- [ ] `kubectl -n argocd get applications`
- [ ] Identify Degraded / OutOfSync apps
- [ ] Decide whether sensitive auto-syncs should be paused during upgrade

## Initial upgrade scope

Proceed only if preflight does not hit a stop condition.

Recommended first scope:

```text
1. control1 -> control2 -> control3
2. edgebox1 -> edgebox2 -> edgebox3 -> edgebox4
3. rm352-2
```

Hold by default:

| Node | Reason |
| --- | --- |
| `rm352-1` | Harbor registry RWO PVC was attached here during the 2026-06-25 audit |
| `sv4000-2` | Partridge dedicated node; pods cannot freely move elsewhere |
| `l40s` | all Ceph OSDs are on this node and runtime pod kill issues were observed |
| `sv4000-1` | Ceph MON/MDS/RGW/Rook-heavy node and Ubuntu 22.04 special case |

## Stop conditions

Stop before moving to the next node if any of the following happens.

```text
- etcd endpoint health fails
- two or more kube-apiserver instances are unhealthy
- Cilium health is not 12/12 reachable
- Ceph inactive/undersized PG count increases
- Harbor registry has zero Running pod
- RBD volume detach/attach is stuck
- drain is blocked by a PDB and the affected workload owner/impact is unclear
- Partridge pod unexpectedly becomes Pending or CrashLoopBackOff
```

## Work log

| Time | Action | Result | Next |
| --- | --- | --- | --- |
| 2026-06-26 before 13:00 KST | Temporarily bypassed SSH OTP for `netai` on control-plane nodes | Success. Ansible ping and `sudo -n true` succeeded on all nodes | Run full preflight |

## Next planned action

Run the remaining preflight checks, then decide whether the first upgrade wave can start.
