# MiniX Kubespray 업그레이드 트러블슈팅 (2026-06-25)

## Summary
MiniX 클러스터를 Kubespray로 Kubernetes `v1.33.7`까지 올리는 과정에서
Cilium, CoreDNS, NodeLocalDNS, Rook-Ceph PDB, GPU 노드의 pod → API 서버
통신 문제가 연쇄적으로 드러났다.

최종적으로 업그레이드는 완료됐고, Karmada 실험을 진행해도 되는 상태까지
안정화했다.

## Final result
- Kubespray 작업 경로: `/home/chang/kubespray`
- Kubespray 버전: `v2.29.1`
- Inventory 경로: `/home/chang/kubespray/inventory/minix/inventory.ini`
- 목표 Kubernetes 버전: `v1.33.7`
- 모든 노드 `Ready`
- Cilium DaemonSet `5/5 Ready`
- CoreDNS Deployment `2/2 Ready`
- NodeLocalDNS DaemonSet `5/5 Ready`
- API 서버 `/readyz?verbose` 통과

최종 노드 상태:

| 노드 | 역할 | IP | OS | Kubernetes | Runtime |
| --- | --- | --- | --- | --- | --- |
| `master` | control-plane | `10.34.48.103` | Ubuntu 24.04.2 | `v1.33.7` | `containerd://2.1.5` |
| `com1` | worker | `10.34.48.100` | Ubuntu 24.04.2 | `v1.33.7` | `containerd://2.1.5` |
| `com2` | worker | `10.34.48.101` | Ubuntu 24.04.2 | `v1.33.7` | `containerd://2.1.5` |
| `com3` | worker | `10.34.48.102` | Ubuntu 24.04.2 | `v1.33.7` | `containerd://2.1.5` |
| `gpu` | gpu-worker | `10.30.0.139` | Ubuntu 24.04.4 | `v1.33.7` | `containerd://2.1.5` |

남아 있던 비정상 pod 중 아래는 이번 업그레이드/CNI/DNS 문제와 직접 관련 없는
앱 레벨 이슈로 분리했다.

```text
ollama/ollama-b8585f897-d6mhr       Pending
postgre/postgresql-0                Init:ImagePullBackOff
```

## 이슈 1 — Cilium init container가 `/hostbin/cilium-mount`를 못 씀

### Symptom
Cilium DaemonSet이 `3/5`에서 멈췄고, `master`, `com3`의 Cilium pod가
`Init:CrashLoopBackOff` 상태였다.

```text
cp: cannot create regular file '/hostbin/cilium-mount': Permission denied
```

`com3`에는 아래 taint도 남아 있었다.

```text
node.cilium.io/agent-not-ready
```

### Diagnosis
Kubespray preinstall 단계에서 `/opt/cni/bin`이 `kube:root`, `0755`로
만들어져 있었다.

Cilium의 `mount-cgroup` init container는 `/usr/bin/cilium-mount`를
host의 `/opt/cni/bin`으로 복사해야 한다. 그런데 init container가
`CAP_DAC_OVERRIDE`를 drop한 상태라서 container 안의 root라도 `kube`
소유 디렉터리에 쓸 수 없었다.

### Fix
즉시 복구는 모든 노드에서 CNI bin 디렉터리 소유자를 `root:root`로 되돌리고,
깨진 Cilium pod를 재생성했다.

```bash
cd /home/chang/kubespray

ansible -i inventory/minix/inventory.ini k8s_cluster -b -m file \
  -a 'path=/opt/cni/bin state=directory owner=root group=root mode=0755 recurse=false'

kubectl -n kube-system delete pod cilium-rjb8c cilium-df2sp --ignore-not-found=true
kubectl -n kube-system rollout status ds/cilium --timeout=180s
```

### Prevention
Kubespray 쪽에도 재발 방지 패치를 넣었다.

```yaml
# roles/kubernetes/preinstall/tasks/0050-create_directories.yml
owner: "{{ 'root' if item == '/opt/cni/bin' else kube_owner }}"
```

이유: Cilium init container가 `CAP_DAC_OVERRIDE` 없이 `/opt/cni/bin`에
파일을 써야 하므로, 해당 디렉터리는 `root:root`로 유지하는 것이 안전하다.

## 이슈 2 — kubeadm upgrade health-check job timeout

### Symptom
업그레이드 재실행 중 첫 control-plane upgrade 단계에서 kubeadm health check job이
15초 안에 완료되지 않아 실패했다.

```text
[ERROR CreateJob]: Job "upgrade-health-check-..." in namespace "kube-system" did not complete in 15s
```

### Root cause
kubeadm 자체 문제가 아니라, 위의 Cilium 장애 때문에 control-plane health check job이
정상적으로 완료되지 못한 것이었다.

### Fix
먼저 Cilium을 `5/5 Ready`로 복구한 뒤 다시 실행하니 control-plane upgrade 단계는
정상 통과했다.

```text
Kubeadm | Upgrade first control plane node to 1.33.7 changed: [master]
```

## 이슈 3 — Rook-Ceph PDB 때문에 worker drain이 막힘

### Symptom
Cilium 문제 해결 후에는 worker drain 단계에서 `com2`가 막혔다.
Rook-Ceph PDB가 disruption을 허용하지 않는 상태였다.

```text
rook-ceph-mon-pdb allowed disruptions: 0
rook-ceph-osd     allowed disruptions: 0
```

### Root cause
업그레이드 중 Kubespray가 노드를 drain하려 했지만, Rook-Ceph mon/osd pod가
PDB 때문에 eviction되지 않았다.

### 잘못 시도한 것
처음에는 아래처럼 넘겼지만, Ansible extra-vars에서 문자열 `"false"`가 truthy로
해석되어 drain이 계속 실행됐다.

```bash
ansible-playbook -i inventory/minix/inventory.ini upgrade-cluster.yml -b \
  -e drain_nodes=false
```

### Fix
JSON boolean으로 넘겨서 drain을 실제로 끄고, cordon/uncordon은 유지했다.

```bash
ansible-playbook -i inventory/minix/inventory.ini upgrade-cluster.yml -b \
  -e '{"drain_nodes": false, "upgrade_node_always_cordon": true}'
```

결과:

```text
PLAY RECAP: failed=0
duration: 18m04s
```

## 이슈 4 — CoreDNS `plugin/loop` CrashLoopBackOff

### Symptom
CoreDNS pod 하나가 `CrashLoopBackOff`였고, log에는 loop detection이 찍혔다.

```text
[FATAL] plugin/loop: Loop (...) detected for zone "."
```

### Diagnosis
CoreDNS ConfigMap이 node의 resolver를 그대로 참조하고 있었다.

```coredns
forward . /etc/resolv.conf
```

GPU 노드와 systemd-resolved/NodeLocalDNS 조합에서 node resolver 안에
`169.254.25.10` 같은 local/stub resolver가 들어가면서 CoreDNS ↔ NodeLocalDNS
forward loop가 만들어졌다.

### Fix
Kubespray inventory에 upstream DNS를 명시했다.

```yaml
# inventory/minix/group_vars/all/all.yml
upstream_dns_servers:
  - 8.8.8.8
  - 8.8.4.4
```

적용:

```bash
cd /home/chang/kubespray

ansible-playbook -i inventory/minix/inventory.ini cluster.yml -b --tags coredns
kubectl -n kube-system rollout restart deploy/coredns ds/nodelocaldns
```

적용 후 ConfigMap은 아래처럼 바뀌었다.

```text
coredns:      forward . 8.8.8.8 8.8.4.4
nodelocaldns: forward . 8.8.8.8 8.8.4.4
```

## 이슈 5 — GPU 노드 pod가 Kubernetes API 서버에 timeout

### Symptom
DNS loop를 고친 뒤 CoreDNS pod는 `Running`이 되었지만, GPU 노드 위 pod의
readiness check가 실패했다.

```text
failed to list *v1.Service:
Get "https://10.234.0.1:443/...": dial tcp 10.234.0.1:443: i/o timeout
```

GPU 노드의 테스트 pod에서도 처음에는 아래처럼 실패했다.

```text
api_backend:fail
api_service:fail
```

### Diagnosis
Cilium inventory에 아래 값이 들어가 있었다.

```yaml
cilium_native_routing_cidr: 10.34.48.0/24
```

MiniX는 터널 모드인데, 이 값 때문에 GPU pod → node/API 서버 대역 트래픽이
SNAT되지 않고 pod source IP로 나갔다. master/API 서버 쪽 return path 또는
`rp_filter`/host routing 문제로 응답이 돌아오지 않아 timeout이 발생했다.

임시로 GPU 노드에 SNAT rule을 넣었을 때 API 통신이 바로 살아나는 것으로 확인했다.

```bash
iptables -t nat -I CILIUM_POST_nat 1 \
  -s 10.234.69.0/24 -d 10.34.48.0/24 ! -o cilium_+ -j MASQUERADE
```

확인 결과:

```text
api_backend:ok
api_service:ok
```

### Fix
터널 모드에서는 pod → node/API 트래픽이 SNAT되도록
`cilium_native_routing_cidr`를 비웠다.

```yaml
# inventory/minix/group_vars/k8s_cluster/k8s-net-cilium.yml
cilium_native_routing_cidr: ""
```

적용:

```bash
cd /home/chang/kubespray

ansible-playbook -i inventory/minix/inventory.ini cluster.yml -b --tags cilium
kubectl -n kube-system rollout restart ds/cilium
```

### 잔여 iptables 정리
GPU 노드의 Cilium pod는 한 번 더 stale iptables chain 문제를 보였다.

```text
iptables rules full reconciliation failed...
OLD_CILIUM_POST_nat...
```

GPU 노드에서 참조되지 않는 old chain을 정리한 뒤 Cilium pod를 재생성했다.

```bash
for c in OLD_CILIUM_PRE_nat OLD_CILIUM_OUTPUT_nat OLD_CILIUM_POST_nat; do
  iptables -t nat -F "$c" || true
  iptables -t nat -X "$c" || true
done
```

최종적으로 GPU pod에서 API와 DNS 모두 정상 확인했다.

```text
api_backend:ok
api_service:ok
dns_kubernetes:10.234.0.1 kubernetes.default.svc.cluster.local
dns_external:3.33.186.135 kubernetes.io
```

## 최종 점검 명령

로컬 `kubectl` context가 다른 클러스터(`kind-twinx`)로 바뀌어 있을 수 있으므로,
MiniX 점검은 master의 admin.conf를 명시해서 보는 것이 안전하다.

```bash
ssh master 'sudo kubectl --kubeconfig /etc/kubernetes/admin.conf get nodes -o wide'
ssh master 'sudo kubectl --kubeconfig /etc/kubernetes/admin.conf -n kube-system get pods -o wide'
ssh master 'sudo kubectl --kubeconfig /etc/kubernetes/admin.conf get --raw /readyz?verbose'
```

핵심 체크:

```bash
kubectl -n kube-system rollout status ds/cilium
kubectl -n kube-system rollout status deploy/coredns
kubectl -n kube-system rollout status ds/nodelocaldns
kubectl get nodes
kubectl get pods -A --field-selector=status.phase!=Running
```

## 배운 점
1. Kubespray 재실행 전에 CNI부터 정상화해야 한다. CNI가 깨져 있으면 kubeadm
   health check job도 실패해서 원인이 헷갈린다.
2. Ansible extra-vars에서 boolean은 문자열로 넘기지 말고 JSON으로 넘긴다.
3. Rook-Ceph가 떠 있는 클러스터는 upgrade drain이 PDB에 막힐 수 있다.
   업그레이드 전략을 미리 정해야 한다.
4. CoreDNS가 `/etc/resolv.conf`를 그대로 forward하면 NodeLocalDNS/systemd-resolved와
   loop를 만들 수 있다. upstream DNS를 명시하는 편이 안전하다.
5. Cilium tunnel mode에서 `cilium_native_routing_cidr`를 잘못 잡으면 일부 node/API
   대역으로 SNAT이 빠져서 pod → API 통신이 timeout 날 수 있다.
