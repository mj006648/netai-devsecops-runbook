# rm352 nodes: GPU Operator failure & kubelet disconnect — root cause & fix

**Status: RESOLVED (2026-06-05)**

---

## Symptoms (before fix)

- `rm352-1`, `rm352-2` nodes intermittently or permanently `NotReady`
- GPU Operator pods stuck in `Init:CrashLoopBackOff` — `nvidia.com/gpu` not registered
- `nginx-proxy` static pod CrashLoopBackOff → kubelet loses apiserver connectivity
- Pods on rm352 nodes fail hairpin / self-Service probes (cert-manager webhook, nfd-worker, etc.)
- `nvidia-container-cli: nvml error: insufficient permissions`

---

## Root Cause Chain

### 1. VirtualGL残재 — GPU device 권한 충돌 (rm352-2)

두 modprobe 파일이 같은 파라미터를 다르게 설정:

| 파일 | GID | Mode |
|------|-----|------|
| `/etc/modprobe.d/nvidia.conf` | 0 (root) | 0666 |
| `/etc/modprobe.d/virtualgl.conf` | 1002 (vglusers) | 0660 |

modprobe는 알파벳순으로 읽고 마지막 값이 승리 → `v` > `n` → virtualgl.conf 적용
→ `/dev/nvidia*` 권한이 `crw-rw---- root vglusers 0660`으로 잠김
→ GPU Operator validator NVML 권한 거부 → `nvidia.com/gpu` 미등록

추가로 `/etc/udev/rules.d/70-nvidia.rules`도 `MODE=0660 GROUP=video`로 이중 잠금.

### 2. 커널 업그레이드 후 nvidia 드라이버 모듈 미설치 (rm352-1)

재부팅 후 커널이 `6.8.0-94` → `6.8.0-124-generic`으로 업그레이드됐으나
`linux-modules-nvidia-580-open-6.8.0-124-generic` 패키지 미설치
→ `modprobe nvidia` 실패 → GPU 인식 불가

### 3. netplan T20 라우팅 테이블 로컬 경로 누락 (공통, 핵심)

`/etc/netplan/50-cloud-init.yaml`에 다음 policy가 적용되어 있음:

```yaml
routing-policy:
  - from: 10.38.38.105   # rm352-1의 메인 IP
    table: 20
    priority: 100
```

kubelet이 nginx-proxy liveness probe를 `http://10.38.38.105:8081/healthz`로 호출할 때
소스 IP가 `10.38.38.105`이므로 T20을 타는데, T20에 로컬 경로가 없음:

```
# T20 테이블 (수정 전)
default via 10.47.255.254 dev ens6f0np0
10.32.0.0/12 dev ens6f0np0 scope link
# local 10.38.38.105/32 없음!
```

→ `no route to host` → nginx-proxy liveness 실패 → CrashLoopBackOff back-off 5m
→ `127.0.0.1:6443` 단절 → kubelet heartbeat 불가 → `Kubelet stopped posting node status` → NotReady

### 4. Cilium BPF 상태 꼬임

장기간 위 문제들이 누적되어 Cilium BPF 상태가 꼬임
→ Pod→ClusterIP (`10.234.0.1:443`) 통신 불가 → nfd-worker 등 클러스터 내부 통신 실패
→ 재부팅으로 자동 회복

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

### rm352-1: 커널용 nvidia 모듈 패키지 설치

```bash
ssh rm352-1 'sudo apt install -y linux-modules-nvidia-580-open-$(uname -r)'
ssh rm352-1 'sudo modprobe nvidia && nvidia-smi -L'
```

### 공통: T20 로컬 경로 영구 추가

재부팅 후에도 유지되도록 systemd service로 등록:

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

back-off가 길어진 경우 컨테이너를 강제 삭제하면 kubelet이 즉시 재생성:

```bash
ssh rm352-1 'sudo crictl ps -a | grep nginx-proxy'
# Exited 상태의 컨테이너 ID 확인 후:
ssh rm352-1 'sudo crictl rm <container-id>'
```

---

## Verification

```bash
# 노드 Ready 확인
kubectl get node rm352-1 rm352-2

# GPU 리소스 등록 확인
kubectl get node rm352-1 rm352-2 -o custom-columns="NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu"

# GPU Operator Pod 확인
kubectl get pods -n gpu-operator -o wide | grep rm352

# Cilium 상태 확인
kubectl exec -n kube-system <cilium-pod-on-rm352-1> -- cilium-dbg status --brief
kubectl exec -n kube-system <cilium-pod-on-rm352-2> -- cilium-dbg status --brief
```

기대값:
- 두 노드 모두 `Ready`
- `nvidia.com/gpu: 2` 등록
- GPU Operator 전 Pod Running
- Cilium status: `OK`

---

## Cleanup (선택)

노드가 안정적으로 운영되는 것 확인 후, 기존에 적용한 nodeAffinity 회피책 제거:

```bash
# rm352- 로 검색해서 일괄 확인
grep -r "rm352-" argocd/twinx-infra/apps/
```

대상: cert-manager, Kyverno 등 `NotIn rm352-1/rm352-2` affinity 적용된 values.yaml

---

## Notes

- rm352 노드들은 과거 VirtualGL(원격 3D/VDI) 용으로 셋업된 이력이 있음
- k8s GPU 노드로 전환 시 VGL 설정 완전 제거 필요
- 커널 업그레이드 후 `linux-modules-nvidia-580-open-$(uname -r)` 패키지 설치 확인 필요
- netplan policy-based routing 사용 시 자기 자신 IP로의 loopback 경로를 해당 테이블에 명시적으로 추가해야 함
