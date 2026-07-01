# rm352 노드: GPU Operator 실패와 kubelet 단절 원인 및 해결

**상태: 해결됨 (2026-06-05)**

---

## Symptom (수정 전)

- `rm352-1`, `rm352-2` 노드가 간헐적 또는 지속적으로 `NotReady`
- GPU Operator pod가 `Init:CrashLoopBackOff`에 머물고 `nvidia.com/gpu`가 등록되지 않음
- `nginx-proxy` static pod가 CrashLoopBackOff → kubelet이 apiserver connectivity를 잃음
- rm352 노드 위 pod가 hairpin / self-Service probe에 실패함. 예: cert-manager webhook, nfd-worker
- `nvidia-container-cli: nvml error: insufficient permissions`

---

## Root-cause flow

### 1. VirtualGL 잔재 — GPU device 권한 충돌 (rm352-2)

두 modprobe 파일이 같은 파라미터를 다르게 설정하고 있었다.

| 파일 | GID | Mode |
|------|-----|------|
| `/etc/modprobe.d/nvidia.conf` | 0 (root) | 0666 |
| `/etc/modprobe.d/virtualgl.conf` | 1002 (vglusers) | 0660 |

modprobe는 알파벳순으로 읽고 마지막 값이 승리한다. `v`가 `n`보다 뒤라서 `virtualgl.conf`가 적용됐고,
`/dev/nvidia*` 권한이 `crw-rw---- root vglusers 0660`으로 잠겼다.
그 결과 GPU Operator validator가 NVML 권한 거부를 만나고 `nvidia.com/gpu`가 등록되지 않았다.

추가로 `/etc/udev/rules.d/70-nvidia.rules`도 `MODE=0660 GROUP=video`로 device 권한을 한 번 더 잠그고 있었다.

### 2. 커널 업그레이드 후 nvidia 드라이버 모듈 미설치 (rm352-1)

재부팅 후 커널이 `6.8.0-94` → `6.8.0-124-generic`으로 업그레이드됐지만
`linux-modules-nvidia-580-open-6.8.0-124-generic` 패키지가 설치되지 않았다.
그래서 `modprobe nvidia`가 실패했고 GPU가 인식되지 않았다.

### 3. netplan T20 routing table에 local route 누락 (공통, 핵심)

`/etc/netplan/50-cloud-init.yaml`에 아래 policy가 있었다.

```yaml
routing-policy:
  - from: 10.38.38.105   # rm352-1의 main IP
    table: 20
    priority: 100
```

kubelet이 nginx-proxy liveness probe를 `http://10.38.38.105:8081/healthz`로 호출할 때
source IP가 `10.38.38.105`라서 T20 table을 탄다. 그런데 T20에는 자기 자신 IP로 가는 local route가 없었다.

```text
# 수정 전 T20 table
default via 10.47.255.254 dev ens6f0np0
10.32.0.0/12 dev ens6f0np0 scope link
# local 10.38.38.105/32 없음
```

결과적으로 `no route to host` → nginx-proxy liveness 실패 → CrashLoopBackOff back-off 5분
→ `127.0.0.1:6443` 단절 → kubelet heartbeat 불가 → `Kubelet stopped posting node status` → `NotReady`로 이어졌다.

### 4. Cilium BPF 상태 꼬임

위 문제들이 오래 누적되면서 Cilium BPF 상태도 꼬였다.
Pod → ClusterIP (`10.234.0.1:443`) 통신이 실패했고, nfd-worker 같은 클러스터 내부 통신도 실패했다.
재부팅 후 자동 회복됐다.

---

## Fix

### rm352-2: VirtualGL 잔재 제거

```bash
ssh rm352-2 'sudo mv /etc/modprobe.d/virtualgl.conf /etc/modprobe.d/virtualgl.conf.disabled'
ssh rm352-2 'sudo mv /etc/udev/rules.d/70-nvidia.rules /etc/udev/rules.d/70-nvidia.rules.disabled'
ssh rm352-2 'sudo reboot'

# 재부팅 후 확인
ssh rm352-2 'ls -l /dev/nvidia*'
# 기대값: crw-rw-rw- root root (0666)
```

### rm352-1: 현재 커널용 nvidia module package 설치

```bash
ssh rm352-1 'sudo apt install -y linux-modules-nvidia-580-open-$(uname -r)'
ssh rm352-1 'sudo modprobe nvidia && nvidia-smi -L'
```

### 공통: T20 local route 영구 추가

재부팅 후에도 유지되도록 systemd service로 등록했다.

```bash
# rm352-1 (IP: 10.38.38.105)
cat << 'EOF' | ssh rm352-1 'sudo tee /etc/systemd/system/fix-local-route.service'
[Unit]
Description=Add local route to table 20 for hairpin traffic
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/sbin/ip route replace local 10.38.38.105/32 dev lo table 20
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
ssh rm352-1 'sudo systemctl daemon-reload && sudo systemctl enable --now fix-local-route.service'

# rm352-2 (IP: 10.38.38.49)
# 위와 동일하되 ExecStart의 IP를 10.38.38.49/32로 변경
```

검증:
```bash
ssh rm352-1 'curl -s http://10.38.38.105:8081/healthz && echo ok'
ssh rm352-2 'curl -s http://10.38.38.49:8081/healthz && echo ok'
```

### nginx-proxy CrashLoopBackOff back-off 즉시 해제

back-off가 길어진 경우 컨테이너를 강제로 삭제하면 kubelet이 즉시 재생성한다.

```bash
ssh rm352-1 'sudo crictl ps -a | grep nginx-proxy'
# Exited 상태의 container ID 확인 후:
ssh rm352-1 'sudo crictl rm <container-id>'
```

---

## 검증

```bash
# 노드 Ready 확인
kubectl get node rm352-1 rm352-2

# GPU resource 등록 확인
kubectl get node rm352-1 rm352-2 -o custom-columns="NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu"

# GPU Operator pod 확인
kubectl get pods -n gpu-operator -o wide | grep rm352

# Cilium 상태 확인
kubectl exec -n kube-system <cilium-pod-on-rm352-1> -- cilium-dbg status --brief
kubectl exec -n kube-system <cilium-pod-on-rm352-2> -- cilium-dbg status --brief
```

기대값:
- 두 노드 모두 `Ready`
- `nvidia.com/gpu: 2` 등록
- GPU Operator의 모든 pod가 `Running`
- Cilium status: `OK`

---

## 정리 (선택)

노드가 안정적으로 운영되는 것을 확인한 뒤 기존에 적용한 nodeAffinity 회피책을 제거한다.

```bash
# rm352- 로 검색해서 일괄 확인
grep -r "rm352-" argocd/twinx-infra/apps/
```

대상: cert-manager, Kyverno 등 `NotIn rm352-1/rm352-2` affinity가 적용된 values.yaml

---

## 메모

- rm352 노드들은 과거 VirtualGL(원격 3D/VDI)용으로 셋업된 이력이 있다.
- Kubernetes GPU 노드로 전환할 때는 VGL 설정을 완전히 제거해야 한다.
- 커널 업그레이드 후 `linux-modules-nvidia-580-open-$(uname -r)` 패키지가 설치됐는지 확인한다.
- netplan policy-based routing을 사용할 때는 자기 자신 IP로의 loopback route를 해당 table에 명시적으로 추가해야 한다.
