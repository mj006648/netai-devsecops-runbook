# TwinX Kubernetes Upgrade Run 2026-06-26

## Summary

2026-06-26 작업창에서 TwinX Kubernetes 업그레이드를 준비하기 위한 당일 실행 로그와 판단 기록이다.
현재 문서는 **preflight 결과 정리 문서**이며, 아직 업그레이드, drain, rollout, reboot는 시작하지 않았다.

```text
current: Kubernetes v1.33.3
target:  Kubernetes v1.35.4
path:    v1.33.3 -> v1.34.x -> v1.35.4
status:  preflight checked, upgrade not started
```

Preflight artifact:

```text
/tmp/twinx-upgrade-preflight-20260626030959
/tmp/twinx-upgrade-preflight-latest -> /tmp/twinx-upgrade-preflight-20260626030959
```

## Safety rule

업그레이드 실행은 사용자가 명시적으로 지시하기 전까지 시작하지 않는다.
아래 작업은 모두 금지한다.

```text
ansible-playbook upgrade-cluster.yml
ansible-playbook cluster.yml
kubectl drain / cordon / uncordon
kubectl rollout restart
pod delete
node reboot
Cilium / Hubble / DRA 설정 변경
ArgoCD auto-sync pause/resume
```

현재 허용된 범위는 read-only 점검과 문서 업데이트뿐이다.

## What is preflight?

Preflight는 업그레이드 실행 전에 클러스터가 업그레이드를 받을 수 있는 상태인지 확인하는 사전 점검이다.
여기서 문제가 크면 업그레이드를 시작하지 않거나, 위험 노드를 제외하고 범위를 줄인다.

Preflight에서 보는 핵심은 다음과 같다.

- Ansible이 모든 대상 노드에 비대화형 SSH/sudo로 접속 가능한가
- etcd와 control-plane이 정상인가
- Rook-Ceph 상태가 악화되어 있지 않은가
- drain을 막을 PDB나 stateful workload가 어디에 있는가
- Cilium health가 전체 노드에서 정상인가
- Harbor registry PVC/RBD attachment가 꼬여 있지 않은가
- ArgoCD가 작업 중 민감한 앱을 자동으로 건드릴 가능성이 있는가
- Kubespray checkout, inventory, removed vars가 목표 버전에 맞는가

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

### 2. Read-only preflight snapshot

다음 정보는 read-only로 수집했다.

```text
nodes-wide.txt
pods-wide.txt
pdb-wide.txt
apiservices.txt
events-sorted.txt
etcd-all-endpoint-health-status.txt
control-plane-pods.txt
cilium-health-all.txt
ceph-status.txt
ceph-health-detail.txt
harbor-wide.txt
volumeattachments.yaml
partridge-wide.txt
argocd-apps-summary.txt
kubespray-local-state.txt
preflight-derived-summary.txt
```

## Preflight result

### Good signs

| Area | Result | Evidence |
| --- | --- | --- |
| SSH / sudo | all nodes reachable | Ansible ping and `sudo -n true` succeeded on all nodes |
| Kubernetes version | all nodes are `v1.33.3` | `nodes-wide.txt` |
| APIService | no unavailable APIService found | `apiservices.txt` |
| etcd | all endpoints healthy | `etcd-all-endpoint-health-status.txt` |
| Cilium | agent health is `12/12 reachable` | `cilium-health-all.txt` |
| control-plane pods | all kube-apiserver/controller/scheduler pods Running | `control-plane-pods.txt` |

etcd status summary:

```text
10.38.38.9:2379   healthy, etcd 3.5.21, leader
10.38.38.17:2379  healthy, etcd 3.5.21
10.38.38.25:2379  healthy, etcd 3.5.21
RAFT term 7, index/applied 255448160
```

### Blockers / risks

| Area | Observation | Decision |
| --- | --- | --- |
| Rook-Ceph | `HEALTH_WARN`, 33 inactive/undersized PGs, 18 pools without replicas, all OSDs on `l40s` | `l40s` and `sv4000-1` hold |
| Harbor | new registry/jobservice pods are `ContainerCreating` on `rm352-2`, but registry/jobservice RWO volumes are still attached to `rm352-1` | `rm352-1` and `rm352-2` hold until Harbor is stable |
| Partridge | all worker pods are on `sv4000-2` and only `1/2` containers ready | `sv4000-2` hold unless downtime is accepted |
| PDB | `keycloak-db-primary`, `nessiedb-primary`, `opensearch` allowed disruptions are 0 | drain may block on nodes with these workloads |
| Runtime events | `l40s` has recent `FailedKillPod` / containerd timeout style warnings | do not drain `l40s` today without separate recovery plan |
| ArgoCD | `harbor` is Degraded, several apps are OutOfSync with auto-sync enabled | decide pause policy before mutation |
| Kubespray checkout | local checkout is `v2.28.0-123-g5e54fd4da`, not target `v2.31.0` | prepare Kubespray tag before upgrade |
| Inventory | `sv4000-1` has `ansible_hose=10.38.38.32` typo | fix before any playbook run involving `sv4000-1` |
| Removed vars | `deploy_netchecker: false` exists; `ingress_nginx_enabled: false` exists | validate against target Kubespray removed vars before upgrade |

Harbor-specific evidence:

```text
Running registry pod:     habor-harbor-registry-6b5988885d-wn8sx on rm352-1
New registry pod:         habor-harbor-registry-5497d49957-7x6cv on rm352-2, ContainerCreating
Running jobservice pod:   habor-harbor-jobservice-5ffb56cfb4-nzgsn on rm352-1
New jobservice pod:       habor-harbor-jobservice-7694979d84-bbjwp on rm352-2, ContainerCreating
Registry PVC:             habor-harbor-registry, 500Gi, RWO
Registry/jobservice PVs:  both attached to rm352-1
```

Ceph-specific evidence:

```text
health: HEALTH_WARN
mons d,e,f are using a lot of disk space
mon f is low on available space
Reduced data availability: 33 pgs inactive
Degraded data redundancy: 33 pgs undersized
osd: 3 osds: 3 up, 3 in
pgs: 248 active+clean, 33 undersized+peered
```

## Preflight checklist

### Access / automation

- [x] `netai` account can SSH to `control1`, `control2`, `control3` without OTP during the work window
- [x] `ansible -i inventory/mycluster/inventory.ini kube_control_plane -m ping`
- [x] `ansible -i inventory/mycluster/inventory.ini kube_control_plane -m command -a 'sudo -n true'`
- [x] `ansible -i inventory/mycluster/inventory.ini all -m ping`
- [x] `ansible -i inventory/mycluster/inventory.ini all -m command -a 'sudo -n true'`

### Cluster state

- [x] `kubectl get nodes -o wide`
- [x] `kubectl get pods -A -o wide`
- [x] `kubectl get pdb -A`
- [x] `kubectl get apiservices`
- [x] `kubectl get events -A --sort-by=.lastTimestamp`

### etcd / control-plane

- [x] etcd endpoint health
- [ ] etcd snapshot
- [ ] `/etc/kubernetes` backup on control-plane nodes
- [x] kube-apiserver, kube-controller-manager, kube-scheduler pod status check

### Cilium / networking

- [x] Cilium agent pods status
- [x] Cilium health `12/12 reachable`
- [x] rm352-1 / rm352-2 included in Cilium health result
- [ ] Decide whether Cilium version should be pinned during Kubernetes upgrade

### Rook-Ceph / storage

- [x] `ceph status`
- [x] `ceph health detail`
- [x] Ceph MON quorum check
- [x] OSD status check
- [x] Confirm whether `l40s` and `sv4000-1` must be excluded from today's upgrade scope

### Harbor

- [x] `kubectl -n harbor get pods,pvc -o wide`
- [x] Harbor registry 500Gi RWO PVC attachment check
- [x] Decide whether `rm352-1` is excluded until Harbor registry is stable
- [x] Decide whether `rm352-2` is excluded from first wave because new Harbor pods are stuck there

### Partridge

- [x] `kubectl -n partridge get pods -o wide`
- [x] Confirm `sv4000-2` downtime policy risk
- [x] Keep `sv4000-2` out of the first upgrade wave unless downtime is accepted

### GitOps / ArgoCD

- [x] `kubectl -n argocd get applications`
- [x] Identify Degraded / OutOfSync apps
- [ ] Decide whether sensitive auto-syncs should be paused during upgrade

### Kubespray readiness

- [x] Check local Kubespray checkout
- [x] Check inventory node entries
- [x] Check target-risk removed vars candidates
- [ ] Switch/prepare target Kubespray tag for Kubernetes 1.35.4
- [ ] Fix `sv4000-1 ansible_hose` inventory typo before any upgrade involving that node
- [ ] Validate inventory with target Kubespray before upgrade

## Revised upgrade scope

Do not proceed until the remaining gates are done.

Required gates before any upgrade playbook:

1. etcd snapshot
2. `/etc/kubernetes` backup on control-plane nodes
3. target Kubespray tag/branch prepared for Kubernetes `v1.35.4`
4. inventory typo and removed-var candidates reviewed
5. ArgoCD auto-sync policy decided for sensitive apps
6. user explicitly approves starting the upgrade

If those gates pass, the safest first wave is now limited to:

```text
1. control1 -> control2 -> control3
2. edgebox1 -> edgebox2 -> edgebox3 -> edgebox4
```

Hold by default:

| Node | Reason |
| --- | --- |
| `rm352-1` | Harbor registry/jobservice RWO volumes attached here |
| `rm352-2` | new Harbor registry/jobservice pods are stuck in `ContainerCreating` here |
| `sv4000-2` | Partridge dedicated node; pods cannot freely move elsewhere |
| `l40s` | all Ceph OSDs are on this node and runtime pod kill issues were observed |
| `sv4000-1` | Ceph MON/MDS/RGW/Rook-heavy node, Ubuntu 22.04 special case, inventory typo |



## Kubespray v2.30 staging

Intermediate Kubespray worktree was prepared for the `v1.33.3 -> v1.34.4` step. No upgrade playbook has been executed.

```text
source:      /home/netai/chang/kubespray
worktree:    /home/netai/chang/kubespray-v2.30
tag:         v2.30.0
kube target: v1.34.4
etcd target: 3.5.26 candidate from v2.30 checksums
ansible:     ansible 10.7.0 / ansible-core 2.17.x
```

Local prep performed only inside the v2.30 worktree:

- copied `inventory/mycluster` from the existing Kubespray checkout
- fixed the copied `sv4000-1 ansible_hose` typo to `ansible_host`
- added explicit `kube_version: v1.34.4` for the intermediate step
- verified `ansible-inventory --graph` parses the copied inventory

Cilium note:

```text
Kubespray v2.30 default cilium_version: 1.18.6
Current inventory cilium_version override: none
```

Therefore, running v2.30 as-is may also upgrade Cilium. Decide before execution whether to accept that or pin Cilium separately.

## OIDC / Keycloak preservation gate

OIDC is important and must be preserved through the Kubespray-rendered kube-apiserver manifest. The copied v2.30 inventory includes the required Kubespray OIDC variables in `inventory/mycluster/group_vars/k8s_cluster/k8s-cluster.yml`:

```text
kube_oidc_auth: true
kube_oidc_url: https://auth.mobilex.kr/realms/mobilex
kube_oidc_client_id: tenants
kube_oidc_username_claim: preferred_username
kube_oidc_username_prefix: oidc:
kube_oidc_groups_claim: groups
kube_oidc_groups_prefix: oidc:
```

Kubespray v2.30 templates still consume these variables and render the following kube-apiserver options:

```text
oidc-issuer-url
oidc-client-id
oidc-username-claim
oidc-username-prefix
oidc-groups-claim
oidc-groups-prefix
```

Current live check found an inconsistency that must be handled carefully:

| Check | control1 | control2 | control3 |
| --- | --- | --- | --- |
| host `/etc/kubernetes/manifests/kube-apiserver.yaml` contains OIDC | yes | yes | yes |
| Kubernetes mirror pod YAML contains OIDC | yes | no | no |
| running kube-apiserver process contains OIDC | yes | no | no |

Interpretation: OIDC is present in the inventory and static manifest files, but only `control1` is currently running with the OIDC arguments. During the control-plane upgrade, Kubespray should regenerate/restart kube-apiserver pods; after each control-plane node, verify OIDC args are present before continuing.

Existing OIDC RBAC subjects are present. `oidc-test-view` is not present, but current bindings include `oidc:twinx-login:partridge-view` and `partridge/oidc:twinx-login:partridge-admin` for `oidc:partridge`, `oidc:jinwang`, and `oidc:ich6648`.

Do not store client-side kubeconfig secrets or OIDC client secrets in this public runbook. Keep `tx-config` style client files local-only.

## If all nodes must be upgraded today

전 노드를 오늘 끝내는 방법은 있다. 단, 이 경우 목표는 **무중단 rolling upgrade**가 아니라 **maintenance window 안에서 Kubernetes version을 맞추는 작업**으로 잡아야 한다. Harbor, Partridge, 일부 GPU workload, Ceph-backed workload의 순간 중단 가능성을 받아들이는 전략이다.

### Required policy change

| Default safe plan | All-nodes-today plan |
| --- | --- |
| 위험 노드는 보류 | 위험 노드도 작업하되 downtime을 허용 |
| 가능한 곳은 drain | Ceph-heavy 노드는 drain 대신 no-drain 예외 검토 |
| Harbor/Partridge는 안정화 후 별도 처리 | Harbor/Partridge를 maintenance mode로 두고 처리 |
| Hubble/DRA는 업그레이드 후 별도 | 오늘은 Kubernetes version만 맞추고 Hubble/DRA는 하지 않음 |

### Practical same-day sequence

```text
0. Freeze
   - ArgoCD sensitive auto-sync pause 여부 결정
   - 새 GPU/HPC/HPDA 작업 투입 중지
   - Harbor/Partridge downtime 가능성 공지

1. Backup gates
   - etcd snapshot
   - control-plane /etc/kubernetes backup
   - Kubespray inventory backup
   - current Cilium config backup

2. Kubespray gates
   - Kubernetes 1.34 지원 Kubespray target 준비
   - Kubernetes 1.35.4 지원 Kubespray target 준비
   - sv4000-1 ansible_hose typo 수정
   - removed vars validation 통과

3. First minor upgrade: v1.33.3 -> v1.34.x
   - control1 -> control2 -> control3
   - edgebox1 -> edgebox2 -> edgebox3 -> edgebox4
   - Harbor maintenance 처리 후 rm352-1 / rm352-2
   - Partridge downtime 허용 후 sv4000-2
   - Ceph-heavy l40s / sv4000-1은 no-drain 예외 또는 별도 Ceph 조치 후 진행

4. Stability checkpoint
   - etcd health
   - Cilium 12/12 reachable
   - Ceph PG count가 악화되지 않았는지 확인
   - Harbor registry Running 확인
   - Partridge worker 회복 확인

5. Second minor upgrade: v1.34.x -> v1.35.4
   - 같은 순서 반복

6. Final recovery
   - 모든 node version 확인
   - ArgoCD sync policy 원복
   - OTP bypass 원복
   - Hubble/DRA는 별도 작업으로 남김
```

### Risk-node handling if completion is prioritized

| Node | Same-day handling | Risk |
| --- | --- | --- |
| `rm352-1` | Harbor registry/jobservice downtime을 허용하고 RWO volume 상태 확인 후 처리 | Harbor image push/pull 영향 |
| `rm352-2` | 현재 stuck Harbor pod를 먼저 정리하거나 Harbor maintenance mode로 두고 처리 | RBD attachment 충돌 가능 |
| `sv4000-2` | Partridge downtime을 허용하고 처리 | Partridge worker 중단 |
| `l40s` | Ceph OSD 전체가 있으므로 drain보다 no-drain 예외가 현실적 | kubelet/containerd 재시작 중 Ceph-backed workload 영향 |
| `sv4000-1` | MON 2개가 있어 가장 위험. 가능하면 mon 분산/정리 후 진행, 아니면 no-drain + 중단 감수 | Ceph quorum/data path 영향 가능 |

### Hard truth

오늘 전 노드 완료는 가능할 수 있지만, 현재 상태에서 안전한 전 노드 무중단 업그레이드는 아니다. 특히 `l40s`와 `sv4000-1`은 Ceph 구성상 일반 worker처럼 drain하면 안 된다. 전 노드 완료를 우선하면 `drain_nodes=false` 같은 예외와 workload downtime을 받아들이는 쪽으로 계획을 바꿔야 한다.

Decision needed before execution:

```text
오늘 목표를 "안전한 1차 wave"가 아니라
"downtime을 감수하고 전 노드 Kubernetes version 맞추기"로 변경할지 결정해야 한다.
```

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
- Kubespray validation reports removed vars or unsupported target version
```

## Work log

| Time | Action | Result | Next |
| --- | --- | --- | --- |
| 2026-06-26 before 13:00 KST | Temporarily bypassed SSH OTP for `netai` on control-plane nodes | Success. Ansible ping and `sudo -n true` succeeded on all nodes | Run full preflight |
| 2026-06-26 before 13:00 KST | Collected read-only cluster preflight snapshot | Success. Snapshot saved under `/tmp/twinx-upgrade-preflight-20260626030959` | Review blockers |
| 2026-06-26 before 13:00 KST | Checked etcd/control-plane/Cilium | etcd healthy, control-plane pods Running, Cilium `12/12 reachable` | Continue only after backup gates |
| 2026-06-26 before 13:00 KST | Checked Ceph/Harbor/Partridge/ArgoCD/Kubespray | Found multiple hold conditions: Ceph WARN, Harbor RWO attachment conflict, Partridge readiness, Kubespray not target tag | Do not start whole-cluster upgrade |
| 2026-06-26 before 13:00 KST | Revised first-wave scope | `rm352-2` removed from first wave; first candidate scope is control-plane and edgebox nodes only | Wait for explicit user approval before any upgrade |
| 2026-06-26 before upgrade | Prepared Kubespray v2.30.0 worktree | `/home/netai/chang/kubespray-v2.30`, copied inventory, fixed `sv4000-1` typo, set `kube_version: v1.34.4`, inventory parses | Do not execute until backup/OIDC/Cilium gates are decided |

## Next planned action

No upgrade is running.

Next safe actions before an actual upgrade are:

1. take etcd snapshot
2. back up `/etc/kubernetes` on control-plane nodes
3. prepare Kubespray target tag for Kubernetes `v1.35.4`
4. validate and clean inventory/removed vars
5. decide ArgoCD auto-sync handling
6. ask for explicit approval before starting the first upgrade wave
