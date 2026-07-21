# C DGX Spark 4K 커널 Isaac Sim WebRTC 검증 런북 — 2026-07-21

> 범위: C 클러스터의 DGX Spark ARM64/GB10 노드에서 Isaac Sim 6.0.1 WebRTC가 64K page-size 커널 때문에 시작되지 않는 문제를, 설치되어 있는 4K NVIDIA 커널로 **한 번만 부팅해 검증**하는 절차다.
>
> 이 문서는 SmartX chart/preset 이관 설계를 반복하지 않는다. `eecs-k8s`/`c-k8s` 파일 경계는 `SMARTX_MIGRATION_PLAN.md`, 포털 기능 범위는 `ISAAC_UI_MVP_SCOPE.md`를 기준으로 한다.

---

## 1. 결론부터

현재 C 클러스터에서 WebRTC가 안 되는 직접 원인은 GPU, DRA claim, Isaac Sim Pod 실행 실패가 아니라 다음 오류다.

```text
libNvStreamServer.so: ELF load command address/offset not page-aligned
```

확인된 실행 환경은 다음과 같다.

```text
architecture: ARM64
GPU: NVIDIA GB10
kernel: 7.0.0-28-generic-64k
page size: 65536 bytes
Isaac Sim image: 10.34.25.18/omniverse/isaac-sim:6.0.1-arm64
```

DGX Spark 노드에는 별도의 4K NVIDIA 커널도 이미 설치되어 있다.

```text
6.17.0-1026-nvidia
```

따라서 다음 검증은 새 image를 다시 만드는 작업이 아니라, DGX Spark를 설치된 `6.17.0-1026-nvidia`로 **1회 부팅**한 뒤 같은 포털에서 Isaac Sim을 다시 생성하는 것이다.

### 4K 커널로 부팅하면 포털에서 그냥 Launch하면 되는가?

대체로 기존 사용 흐름을 그대로 쓴다.

```text
4K kernel 부팅
  -> node/GPU/DRA 정상 확인
  -> 기존 실패 instance 삭제
  -> isaac-twinx 포털에서 GB10 선택
  -> Launch
  -> 표시된 Stream IP로 WebRTC client 연결
```

그러나 **4K 커널만으로 WebRTC 접속까지 무조건 성공한다고 단정하지 않는다.**

4K 전환이 해결하는 것은 현재 확인된 `libNvStreamServer.so` ELF load 실패다. 플러그인이 정상 로드된 뒤에도 연결이 안 되면 TCP/UDP LoadBalancer 경로, advertised public IP, 또는 host-network 요구사항을 별도로 확인해야 한다.

판정은 다음처럼 분리한다.

| 결과 | 의미 | 다음 조치 |
| --- | --- | --- |
| ELF 오류가 사라지고 WebRTC 연결 성공 | 64K page size가 직접 원인이었고 현재 LB 방식도 유효 | 4K 운영 전환 여부 별도 결정 |
| ELF 오류는 사라졌지만 client 연결 실패 | 커널 문제는 해결, 네트워크 경로가 남음 | `49100/TCP`, `47998/UDP`, public IP, host network 검토 |
| 4K에서도 같은 ELF 오류 | image/library 자체 또는 다른 loader 문제 | image digest와 ARM64 binary 재검증 |
| GPU/DRA가 4K에서 사라짐 | target kernel의 NVIDIA module/runtime 문제 | 즉시 64K로 rollback |

---

## 2. 확인한 장애 증거

검증 Pod:

```text
namespace: omniverse
pod: isaac-test-654bc6c47c-wht95
node: d4dc6606-bfde-11d3-8000-4cbb472a16ef
image: 10.34.25.18/omniverse/isaac-sim:6.0.1-arm64
```

Isaac Sim 프로세스 자체는 시작했지만 WebRTC native library가 로드되지 않았다.

```text
libNvStreamServer.so: ELF load command address/offset not page-aligned
WebRTC plugin preload failed
WebRTC server factory unavailable
```

이는 다음 항목과 구분해야 한다.

- Pod scheduling 실패가 아니다.
- GB10 GPU allocation 실패가 아니다.
- ARM64 image pull 실패가 아니다.
- Nucleus 인증 실패가 아니다.
- WebRTC client 버전만의 문제가 아니다.
- 처음 로딩하는 1~2분을 기다리면 해결되는 상태가 아니다.

64K 커널은 ELF shared object를 64 KiB page 규칙으로 로드한다. 현재 image 안의 NVIDIA WebRTC library는 그 정렬 조건을 충족하지 못하므로, extension이 준비되기 전에 dynamic loader 단계에서 실패한다.

실행 중인 컨테이너에서 `patchelf`와 LIEF로 binary를 억지로 수정하는 방법도 임시 조사했으나, 기존 LOAD segment를 안전하게 재배치할 수 없었다. vendor binary를 변조한 image를 운영 해법으로 사용하지 않는다.

---

## 3. 공식 문서의 사실과 우리 환경의 결론

아래 내용을 구분해야 한다. NVIDIA 공식 문서가 직접 말하는 사실과, 그 사실을 현재 C 클러스터 로그에 대입해 내린 결론은 동일한 층위가 아니다.

### 3.1 NVIDIA 공식 문서가 명시한 사실

#### Isaac Sim 6.0.1의 aarch64 지원 대상

Isaac Sim 6.0.1 System Requirements는 aarch64 build를 현재 **DGX Spark에서만 지원**한다고 명시한다.

```text
Device: NVIDIA DGX Spark
OS: NVIDIA DGX OS 7
Driver: 580.159.03
```

현재 C의 DGX Spark driver도 `580.159.03`으로 확인했으므로, GPU 제품과 driver 조합은 공식 요구사항과 일치한다. 따라서 "GB10이라서 Isaac Sim 6.0.1 자체가 지원되지 않는다"가 현재 장애의 설명은 아니다.

#### Isaac Sim container의 multi-architecture 지원

Container Installation은 `nvcr.io/nvidia/isaac-sim:6.0.1` 동일 tag가 Linux `x86_64`와 `aarch64`를 지원한다고 설명한다. DGX Spark용 Docker build에서도 `--aarch64`를 사용하도록 명시한다.

우리 Harbor의 `isaac-sim:6.0.1-arm64`는 architecture를 구분하기 위한 내부 mirror/custom tag다. upstream 관점에서는 별개의 Isaac Sim 제품 버전이 아니라 6.0.1 aarch64 variant다.

#### DGX Spark의 공식 kernel 계열

DGX OS 7 Release Notes는 ARM64 제품별 kernel을 다음처럼 구분한다.

```text
ARM64 DGX GB200/GB300 -> *-nvidia-64k
ARM64 DGX Spark       -> *-nvidia
```

DGX OS 7.4.0 예시는 다음과 같다.

```text
DGX GBx00: 6.17.0-1008-nvidia-64k
DGX Spark: 6.17.0-1008-nvidia
```

DGX OS 7.5.0에서도 같은 구분이 유지된다.

```text
DGX GBx00: 6.17.0-1014-nvidia-64k
DGX Spark: 6.17.0-1014-nvidia
```

즉 `-64k`는 모든 ARM64 NVIDIA 시스템의 공통 기본이 아니다. DGX Spark 공식 제품 경로는 non-64K `-nvidia` 계열이다.

#### WebRTC container network 요구사항

Isaac Sim 6.0.1 Container Installation은 WebRTC livestreaming에서 host networking이 필요하다고 명시한다.

이유도 문서에 설명되어 있다.

```text
NVIDIA streaming SDK의 UDP media socket은 ISAACSIM_HOST 주소에 bind한다.
그 주소는 container 내부에서 실제 network interface에 존재해야 한다.
bridge network에서는 host IP가 container network namespace 안에 없을 수 있다.
signaling은 연결되어도 video stream은 나오지 않을 수 있다.
```

공식 기본 포트는 다음과 같다.

```text
49100/TCP = signaling
47998/UDP = media
```

공식 준비 완료 로그는 다음이다.

```text
Isaac Sim Full Streaming App is loaded.
```

### 3.2 공식 문서에 직접 쓰여 있지 않은 것

NVIDIA 문서가 다음 문장을 그대로 제공하는 것은 아니다.

```text
libNvStreamServer.so는 64K kernel에서 반드시 실패한다.
```

따라서 이 문장을 NVIDIA의 일반 공지처럼 표현하면 안 된다. 현재 결론은 **우리 환경의 실제 dynamic-loader 오류에 근거한 진단**이다.

### 3.3 우리 환경에서 확인한 직접 원인

Linux container는 host와 별도 kernel을 갖지 않는다. Kubernetes Pod 안의 process도 DGX Spark host kernel의 page size를 그대로 사용한다.

현재 host:

```text
kernel page size = 65536 bytes
```

현재 WebRTC library load:

```text
libNvStreamServer.so: ELF load command address/offset not page-aligned
```

ELF shared library에는 메모리에 매핑할 `PT_LOAD` segment들이 있다. Linux dynamic loader는 각 segment의 virtual address와 file offset이 host page boundary 조건을 만족해야 `mmap`할 수 있다.

현재 `libNvStreamServer.so`의 segment 배치는 64 KiB page mapping 조건을 만족하지 못한다. 그 결과 loader가 WebRTC code를 실행하기도 전에 library를 거부한다.

실행 흐름은 다음 지점에서 끊긴다.

```text
Isaac Sim process 시작
  -> WebRTC extension preload 시도
  -> libNvStreamServer.so dlopen
  -> 64K page alignment 검사 실패
  -> native streaming server factory 생성 실패
  -> signaling/media listener 준비 불가
  -> WebRTC client 연결 불가
```

이 때문에 Pod가 `Running`이고 GPU가 할당되어 있어도 WebRTC는 동작하지 않는다. Kubernetes readiness가 해당 native library의 실제 load 성공까지 검사하지 않으면 포털에는 실행 중처럼 보일 수도 있다.

### 3.4 왜 4K kernel이 해법 후보인가

4K kernel에서는 host page size가 `4096`이 된다. 현재 library의 segment가 4 KiB 경계 조건을 만족한다면 dynamic loader가 이를 정상 매핑할 수 있다.

```text
64K kernel: 65536-byte mapping 조건 -> 현재 library 거부
4K kernel:   4096-byte mapping 조건 -> library load 가능 예상
```

여기서 "예상"이라고 쓰는 이유는 kernel을 실제 전환해 아직 같은 image로 재시험하지 않았기 때문이다. 다만 다음 세 증거가 같은 방향을 가리킨다.

1. 실제 오류가 page alignment 오류다.
2. 현재 host가 64K page kernel이다.
3. NVIDIA가 DGX Spark 공식 kernel을 non-64K `-nvidia` 계열로 구분한다.

따라서 vendor library 변조보다 설치된 DGX Spark용 4K NVIDIA kernel로 한 번 부팅해 보는 것이 가장 작고 되돌릴 수 있는 검증이다.

### 3.5 image를 다시 build하는 것만으로 해결되지 않는 이유

일반적인 Docker image는 user space만 포함하고 host kernel을 공유한다.

```text
image 안의 Ubuntu/filesystem 변경 != host kernel page size 변경
```

같은 `libNvStreamServer.so`를 그대로 복사한 ARM64 image를 다시 build해도, 64K host에서 실행하면 같은 loader 조건을 만난다.

image rebuild로 해결하려면 NVIDIA가 해당 library를 64K-compatible ELF layout으로 다시 제공하거나, 지원되는 source/link option으로 library 자체를 다시 link해야 한다. 현재 파일은 proprietary vendor binary이므로 우리가 임의로 patch/relink하는 방법은 운영 해법으로 선택하지 않는다.

### 3.6 4K 전환 후에도 남을 수 있는 별도 문제

4K kernel은 **library load 문제**를 해결하는 시험이다. WebRTC 전체 연결에는 별도로 다음 조건이 필요하다.

- NVENC-capable GPU와 compatible driver
- `runheadless.sh` streaming app 정상 load
- `ISAACSIM_HOST` 또는 `primaryStream/publicIp`가 올바른 접속 주소
- `49100/TCP`와 `47998/UDP` 모두 통과
- client가 app의 완전한 초기화를 기다림
- container network에서 streaming SDK가 bind할 수 있는 실제 주소

공식 문서는 host network를 요구하므로, 4K에서 library가 로드된 뒤 현재 Kubernetes LoadBalancer 방식이 그대로 성공하는지는 실제 검증 대상이다. 기존 amd64 cluster에서 성공했더라도 DGX Spark/Isaac Sim 6.0.1의 결과를 미리 단정하지 않는다.

---

## 4. 왜 4K NVIDIA 커널을 시험하는가

NVIDIA DGX OS 문서는 ARM64 제품군의 커널을 구분한다.

```text
DGX GB200/GB300: *-nvidia-64k
DGX Spark:       *-nvidia
```

즉 DGX Spark에는 `-nvidia-64k`가 아닌 일반 `-nvidia` 커널이 공식 제품 구분과 맞는다.

현재 노드에도 다음 두 계열이 함께 설치되어 있어 새 package 설치 없이 부팅 선택 시험이 가능하다.

```text
linux-image-7.0.0-28-generic-64k
linux-image-6.17.0-1026-nvidia
```

이번 작업의 목적은 기존 64K 커널을 삭제하거나 영구 기본값을 바꾸는 것이 아니다.

```text
현재 기본 64K kernel 보존
  -> 4K NVIDIA kernel로 한 번만 부팅
  -> GPU/DRA/WebRTC 검증
  -> 결과에 따라 운영 kernel을 별도 결정
```

---

## 5. 변경되는 것과 유지되는 것

### 유지되는 것

커널 부팅 전환 자체로 다음 데이터가 삭제되지는 않는다.

- Git 저장소와 commit
- Harbor image
- Kubernetes API의 Deployment/Service 설정
- RBD PVC와 Nucleus 영구 데이터
- `eecs-k8s`/`c-k8s` GitOps source
- 포털 image와 Isaac Sim image
- 설치된 64K 커널 package

### 재시작 영향을 받는 것

DGX Spark 노드가 reboot되므로 다음 영향은 있다.

- 해당 노드의 Pod 재시작 또는 재스케줄
- 실행 중 Isaac Sim session 중단
- `emptyDir` 데이터 소실
- DRA allocation 재조정
- node Ready 상태의 일시적 해제
- GPU Operator와 DRA daemon 재기동

따라서 실행 중인 연구자의 workload를 확인하지 않고 reboot하지 않는다.

### 절대 하지 않는 것

- 64K kernel package 삭제
- 검증 전 `GRUB_DEFAULT` 영구 변경
- C Nucleus PVC/StatefulSet 삭제
- TwinX 외부 Nucleus `10.38.38.32` 변경
- 다른 연구자의 Isaac/Omniverse workload 삭제
- C preset의 Secret 원문 출력

---

## 6. 사전 안전 점검

이 단계는 read-only다.

### 6.1 노드와 workload 확인

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide --field-selector spec.nodeName=d4dc6606-bfde-11d3-8000-4cbb472a16ef
kubectl get resourceclaims -A
kubectl get resourceslices
```

다른 연구자의 장기 실행 Pod가 있으면 유지보수 시간을 먼저 잡는다.

### 6.2 현재 kernel/page size 기록

DGX Spark에서:

```bash
uname -a
uname -r
getconf PAGESIZE
cat /proc/cmdline
```

현재 기준 예상:

```text
uname -r       = 7.0.0-28-generic-64k
getconf PAGESIZE = 65536
```

### 6.3 target kernel과 module 확인

```bash
dpkg -l | grep -E 'linux-image|linux-modules' | grep -E 'nvidia|64k'
ls -ld /lib/modules/6.17.0-1026-nvidia
sudo test -f /boot/vmlinuz-6.17.0-1026-nvidia
sudo test -f /boot/initrd.img-6.17.0-1026-nvidia
modinfo -k 6.17.0-1026-nvidia nvidia | head
```

다음 중 하나라도 실패하면 reboot하지 않는다.

- target kernel image 없음
- initrd 없음
- `/lib/modules/<target>` 없음
- NVIDIA module 조회 실패
- 원격 console 또는 물리 console 복구 경로 없음

### 6.4 GRUB의 정확한 menu entry 확인

문서에 menu index를 하드코딩하지 않는다. 업데이트에 따라 순서가 달라질 수 있다.

```bash
sudo grep -nE "^submenu |^menuentry " /boot/grub/grub.cfg
sudo grep -n "6.17.0-1026-nvidia" /boot/grub/grub.cfg
```

`grub-reboot`에는 위 출력에서 확인한 **정확한 submenu/menuentry 문자열**만 사용한다.

---

## 7. 1회 4K 부팅 절차

> 이 절차는 노드 reboot를 포함한다. 다른 workload 영향과 복구 console이 확인된 유지보수 시간에만 실행한다.

### 7.1 현재 시험 instance 정리

가능하면 포털 Delete를 사용한다. Delete가 정상 동작하면 해당 instance의 다음 자원이 함께 사라지는지 확인한다.

```text
Deployment
LoadBalancer Service
ResourceClaim 또는 ResourceClaimTemplate
```

확인:

```bash
kubectl -n omniverse get deploy,svc,pod
kubectl -n omniverse get resourceclaims,resourceclaimtemplates
```

Nucleus와 포털 Deployment는 삭제 대상이 아니다.

### 7.2 노드 cordon

```bash
kubectl cordon d4dc6606-bfde-11d3-8000-4cbb472a16ef
```

`drain`은 DaemonSet, local storage, DRA workload 영향을 확인한 뒤에만 사용한다. 무조건적인 `--delete-emptydir-data`나 `--force`를 사용하지 않는다.

### 7.3 one-shot GRUB entry 설정

먼저 현재 GRUB 환경을 기록한다.

```bash
sudo grub-editenv list
```

그다음 6.4에서 확인한 정확한 문자열로 한 번만 부팅하도록 설정한다.

```bash
sudo grub-reboot '<확인한 6.17.0-1026-nvidia menu entry>'
sudo grub-editenv list
```

GRUB는 중첩 entry를 `상위 submenu>하위 entry` 형태로 식별한다. 실제 menu title이 아래와 정확히 같을 때의 실행 예시는 다음과 같다.

```bash
sudo grub-reboot 'Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-1026-nvidia'
sudo grub-editenv list | grep '^next_entry='
```

예상되는 형태:

```text
next_entry=Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-1026-nvidia
```

이 값은 다음 부팅 한 번에만 사용되고, GRUB가 entry를 사용하면 `next_entry`를 비운다. 따라서 영구 기본 kernel 변경과 다르다.

명령 예시의 title이 실제 `/boot/grub/grub.cfg` 출력과 한 글자라도 다르면 그대로 복사하지 않는다. 중첩 submenu의 문자열 해석이 불확실하면 `grub-reboot`를 추측해서 실행하지 않고 원격/물리 console의 GRUB 메뉴에서 직접 `6.17.0-1026-nvidia`를 한 번 선택한다.

영구 `GRUB_DEFAULT`는 아직 바꾸지 않는다.

### 7.4 reboot

```bash
sudo reboot
```

SSH가 끊긴 뒤 노드가 다시 올라올 때까지 기다린다.

---

## 8. 부팅 직후 host 검증

DGX Spark에 다시 접속한 뒤 다음을 순서대로 확인한다.

```bash
uname -r
getconf PAGESIZE
nvidia-smi
systemctl is-active containerd
systemctl is-active kubelet
```

성공 기준:

```text
uname -r         = 6.17.0-1026-nvidia
getconf PAGESIZE = 4096
nvidia-smi       = GB10과 driver 정상 표시
containerd       = active
kubelet          = active
```

`PAGESIZE=4096`이 아니면 이번 검증은 4K 부팅이 아니다.

NVIDIA module 또는 `nvidia-smi`가 실패하면 WebRTC 검증으로 넘어가지 않고 13장의 rollback을 수행한다.

---

## 9. Kubernetes/GPU/DRA 복구 확인

control plane에서:

```bash
kubectl get node d4dc6606-bfde-11d3-8000-4cbb472a16ef -o wide
kubectl describe node d4dc6606-bfde-11d3-8000-4cbb472a16ef
kubectl -n gpu-operator get pods -o wide
kubectl -n gpu-nvidia get pods -o wide
kubectl get deviceclass
kubectl get resourceslices
```

namespace는 실제 설치 상태에 맞춰 확인한다. GPU Operator와 DRA가 서로 다른 namespace일 수 있다.

검증할 항목:

- node `Ready=True`
- `nvidia.com/gpu` allocatable 존재
- GPU Operator daemon 정상
- DRA driver daemon/controller 정상
- `DeviceClass gpu.nvidia.com` 존재
- GB10 ResourceSlice/device가 portal inventory에 다시 표시

모두 정상일 때만:

```bash
kubectl uncordon d4dc6606-bfde-11d3-8000-4cbb472a16ef
```

---

## 10. 포털에서 다시 Launch

포털 자체는 별도 노드에서 계속 실행해도 된다. 포털은 Kubernetes API에서 GPU/DRA inventory를 읽고 선택한 장치에 Isaac Sim Deployment를 생성하는 controller이므로, DGX Spark kernel과 같은 노드에 있을 필요가 없다.

### 10.1 기존 instance를 재사용하지 않는 이유

kernel reboot 후 Pod가 자동 재생성될 수는 있지만, 검증 증거를 명확히 하고 DRA/Service를 깨끗하게 재생성하기 위해 기존 실패 instance는 삭제하고 새 instance를 만든다.

### 10.2 사용자 흐름

```text
isaac-twinx 웹 접속
  -> GPU Inventory에서 DGX Spark / GB10 확인
  -> + New instance
  -> user/instance 이름 입력
  -> GB10 선택
  -> Launch
  -> Initializing 상태에서 1~2분 대기
  -> Stream IP 확인
```

포털의 architecture별 image 선택 결과가 다음과 같은지 확인한다.

```text
arm64/GB10 -> 10.34.25.18/omniverse/isaac-sim:6.0.1-arm64
amd64      -> 기존 amd64 Isaac Sim image
```

검증 Pod:

```bash
kubectl -n omniverse get deploy,svc,pod -l group=dt-sim -o wide
kubectl -n omniverse describe pod -l group=dt-sim
```

---

## 11. WebRTC와 Nucleus 검증

### 11.1 가장 먼저 볼 로그

```bash
kubectl -n omniverse logs deploy/<새-instance-deployment> -c isaac-sim --tail=300
```

실패 문자열이 없어야 한다.

```text
ELF load command address/offset not page-aligned
WebRTC plugin preload failed
server factory unavailable
```

대신 WebRTC streaming app/extension이 정상 로드된 증거가 있어야 한다.

```bash
kubectl -n omniverse logs deploy/<새-instance-deployment> -c isaac-sim \
  | grep -Ei 'WebRTC|livestream|streaming|loaded|49100|47998'
```

### 11.2 Service와 endpoint

```bash
kubectl -n omniverse get svc <새-instance-stream-service> -o wide
kubectl -n omniverse get endpointslice -l kubernetes.io/service-name=<새-instance-stream-service>
```

필수 포트:

| Port | Protocol | 용도 |
| --- | --- | --- |
| `49100` | TCP | WebRTC signaling |
| `47998` | UDP | WebRTC media |

Isaac Sim에 전달된 `primaryStream/publicIp`가 포털에 표시된 LoadBalancer IP와 같아야 한다.

### 11.3 client 연결

Isaac Sim WebRTC Streaming Client 2.0.0에 포털의 Stream IP를 입력한다.

성공 기준:

- 영상 출력
- mouse/keyboard 입력
- 2분 이상 session 유지
- Pod restart 없음
- 선택한 GB10이 Allocated로 유지

### 11.4 Nucleus 연결

이번 C 검증의 Nucleus endpoint는 C preset이 주입한 값을 사용한다. image에 특정 MiniX/TwinX IP를 하드코딩하지 않는다.

확인:

```bash
kubectl -n omniverse get deploy <새-instance-deployment> -o yaml \
  | grep -E 'OMNI_SERVER|NUCLEUS_SECRET_NAME|OMNI_PROJECT_PATH'
```

Secret 원문은 출력하지 않는다.

Isaac Sim Content Browser에서 preset의 Nucleus connection이 보이고 asset browse/read가 되는지 확인한다. Nucleus 실패와 WebRTC 실패는 별도 판정한다.

---

## 12. 4K에서 플러그인은 로드되지만 연결이 안 될 때

NVIDIA Isaac Sim 6.0.1 공식 문서는 container livestreaming에 host networking을 요구하고, remote 연결에는 다음 값을 명시하도록 설명한다.

```text
primaryStream/publicIp=<접속할 IP>
primaryStream/signalPort=49100
primaryStream/streamPort=47998
```

현재 포털은 인스턴스별 LoadBalancer Service와 public IP argument를 사용한다. 이 방식은 MiniX/TwinX amd64에서 실제 성공했지만, NVIDIA 문서의 Docker 기준 `--network=host`와 완전히 같은 network topology는 아니다.

따라서 4K에서 ELF 오류가 사라진 뒤에도 연결되지 않으면 다음 순서로 확인한다.

1. Isaac Sim log에서 WebRTC app이 완전히 loaded인지 확인
2. `publicIp`가 실제 Stream IP와 같은지 확인
3. `49100/TCP`와 `47998/UDP`가 Service에 모두 있는지 확인
4. EndpointSlice가 Pod IP를 가리키는지 확인
5. MetalLB/firewall/ACL에서 두 protocol이 허용되는지 확인
6. packet capture로 signaling과 UDP media 도착 여부 확인
7. 마지막으로 Kubernetes `hostNetwork` 실험 설계를 별도 작성

`hostNetwork`를 바로 기본값으로 바꾸지 않는 이유:

- 한 노드에서 여러 instance가 같은 `49100/47998`을 사용할 수 없다.
- 인스턴스별 port allocator가 필요하다.
- Pod가 host port를 직접 점유한다.
- 기존 LoadBalancer/Service 설계가 바뀐다.

즉 **4K 부팅 검증과 host-network 설계 변경을 한 번에 섞지 않는다.** 먼저 현재 직접 원인인 ELF 문제를 제거한 뒤 네트워크 문제의 존재 여부를 판단한다.

---

## 13. Rollback

### 13.1 자동 one-shot rollback

`grub-reboot`로 한 번만 4K entry를 선택했다면 다음 reboot에서는 기존 기본 64K entry로 돌아가는 구성이 일반적이다. 실제 `GRUB_DEFAULT`와 saved entry를 확인한다.

```bash
grep '^GRUB_DEFAULT=' /etc/default/grub
sudo grub-editenv list
```

### 13.2 즉시 64K로 돌아가기

4K에서 GPU, kubelet, DRA 중 하나라도 복구되지 않으면:

```bash
sudo reboot
```

필요하면 GRUB console에서 기존 `7.0.0-28-generic-64k` entry를 선택한다.

복구 후:

```bash
uname -r
getconf PAGESIZE
nvidia-smi
kubectl get nodes
kubectl get resourceslices
```

예상:

```text
uname -r         = 7.0.0-28-generic-64k
getconf PAGESIZE = 65536
```

node가 안정화되면 cordon 상태를 확인하고 필요한 경우 uncordon한다.

```bash
kubectl get node d4dc6606-bfde-11d3-8000-4cbb472a16ef
kubectl uncordon d4dc6606-bfde-11d3-8000-4cbb472a16ef
```

---

## 14. 최종 합격 기준

### Kernel/GPU

- [x] `uname -r`가 `6.17.0-1026-nvidia`
- [x] `getconf PAGESIZE`가 `4096`
- [x] GB10 `nvidia-smi` 정상: NVIDIA GB10, driver 580.159.03
- [x] node Ready

### Kubernetes/DRA

- [x] GPU Operator 정상
- [x] NVIDIA DRA driver 정상
- [x] `gpu.nvidia.com` DeviceClass 존재
- [x] GB10 ResourceSlice 표시
- [x] portal에서 GB10 자동 발견
- [x] exact one-device allocation 성공

### Isaac Sim/WebRTC

- [x] ARM64 image 자동 선택
- [x] `libNvStreamServer.so` ELF 오류 없음
- [x] WebRTC extension/app load 성공
- [x] hostNetwork에서 `49100/TCP`, `47998/UDP` endpoint 정상
- [x] WebRTC Client 2.0.0 영상과 입력 성공
- [x] 이전 검증 instance Delete 후 Deployment/claim 삭제
- [x] GB10 반환 후 새 instance에 재할당 성공

### Nucleus

- [x] C preset의 Nucleus endpoint 사용
- [x] credential Secret 참조
- [x] Nucleus Authentication Service에서 `omniverse` 사용자 `status: OK`
- [ ] Content Browser connection 표시와 asset browse/read 사용자 확인
- [x] 기존 Nucleus StatefulSet, 데이터와 PVC 비변경

---

## 15. 결과 기록 템플릿

검증 후 이 절 아래에 실제 값만 추가한다. 비밀번호, token, Secret 원문은 기록하지 않는다.

```text
검증 일시:
작업자:
검증 전 kernel/page size:
검증 kernel/page size:
GPU/driver:
node Ready:
DRA DeviceClass/ResourceSlice:
portal image digest:
Isaac Sim image digest:
instance name:
Stream IP:
ELF 오류 제거:
WebRTC app loaded:
WebRTC 영상/입력:
Nucleus browse/read:
Delete/GPU 반환:
rollback 여부:
남은 문제:
```

### 15.1 실제 검증 결과 — 2026-07-21

```text
검증 일시: 2026-07-21
검증 전 kernel/page size: NVIDIA 64K kernel / 65536
검증 kernel/page size: 6.17.0-1026-nvidia / 4096
GPU/driver: NVIDIA GB10 / 580.159.03
node: d4dc6606-bfde-11d3-8000-4cbb472a16ef, Ready, arm64
DRA: gpu.nvidia.com DeviceClass와 GB10 ResourceSlice 정상
portal: 10.34.25.18/omniverse/isaac-twinx:0.2.2
Isaac Sim: 10.34.25.18/omniverse/isaac-sim:6.0.1-arm64
network: hostNetwork=true, dnsPolicy=ClusterFirstWithHostNet
Stream IP: 10.33.201.193
ELF 오류 제거: 완료
WebRTC app loaded: 완료
WebRTC 영상/입력: Client 2.0.0 사용자 확인 완료
Nucleus endpoint: omniverse://10.33.143.10/
Nucleus auth: omniverse 사용자 status OK
기존 Nucleus/PVC 변경: 없음
남은 수동 확인: 새 instance Content Browser의 asset browse/read
```

#### ARM64와 amd64 선택 경계

포털은 사용자가 architecture를 직접 고르게 하지 않는다. 선택한 DRA GPU가 있는 node의
`kubernetes.io/arch`를 읽어 실행 방식을 자동 결정한다.

```text
amd64 NVIDIA GPU
  -> isaac-sim:6.0
  -> 인스턴스별 LoadBalancer Service

arm64 DGX Spark GB10
  -> isaac-sim:6.0.1-arm64
  -> hostNetwork=true
  -> node InternalIP를 Stream IP로 사용
```

DGX Spark hostNetwork instance는 같은 node의 고정 WebRTC port를 사용한다. 따라서 같은 node에
두 번째 hostNetwork Isaac Sim을 동시에 만들지 않도록 포털에서 거절한다. 다른 node 또는 amd64의
LoadBalancer 방식은 이 제한과 별개다.

#### Nucleus 인증 장애와 해결

처음에는 `nucleus-cred`의 사용자 또는 비밀번호가 실제 Nucleus master credential과 일치하지 않아
Authentication Service가 `DENIED`를 반환했다. Isaac Sim log의 `Active user not found ... kiosk` 문구만
보면 client 설정 문제처럼 보이지만, Nucleus auth log에서는 전달된 사용자와 인증 결과를 직접 구분할
수 있었다.

해결은 다음과 같다.

1. `OMNI_USER`와 `OMNI_PASS`가 Pod에 존재하는지만 확인하고 원문은 출력하지 않았다.
2. `c-k8s/patches/omniverse-nucleus/values.yaml`에서 Nucleus 배포에 사용한 master credential을 값 노출
   없이 읽었다.
3. `nucleus-cred`를 `OMNI_USER=omniverse`와 해당 master credential로 다시 생성했다.
4. Isaac instance를 재시작한 뒤 Nucleus Authentication Service의 `status: OK`를 확인했다.
5. 원인 분리에 사용한 임시 authentication callback ConfigMap과 Deployment patch는 모두 제거했다.
6. 이후 포털에서 새로 만든 instance도 별도 patch 없이 같은 Secret을 참조해 `status: OK`가 재현됐다.

`eecs-k8s` chart와 `c-k8s` preset은 Secret 이름과 key만 참조하며 비밀번호를 렌더링하지 않는다.
현재 `nucleus-cred`는 cluster에 별도로 준비하는 Secret이므로 cluster 재구축 때 다시 생성하거나,
운영 전 External Secrets/OpenBao 같은 Secret backend로 이관해야 한다.

#### 실제 반영된 저장소 경계

```text
mj006648/isaac-twinx
  c70d125 fix: support Spark WebRTC
  - ARM64 image 자동 선택
  - DGX Spark hostNetwork와 node InternalIP
  - hostNetwork port 충돌 방지
  - 48 tests passed

SJoon99/eecs-k8s main
  6acbd67 fix: configure ARM64 WebRTC
  - 공통 chart에 isaacSimArm64HostNetwork 기본값과 env 전달

SJoon99/c-k8s main
  1ac1b9d fix: enable Spark WebRTC
  - portal 0.2.2
  - C의 ARM64 image, hostNetwork, Nucleus endpoint와 Secret 참조 override
```

`c-k8s`에는 확인된 `ops` remote branch가 없었으므로 이번 변경은 실제 Argo source가 사용하는
`main`에 반영했다.


### 15.2 NVIDIA 4K kernel 영구 기본값 고정 — 2026-07-21

WebRTC 검증이 끝난 뒤 DGX Spark가 다음 일반 재부팅에서도 64K generic kernel이 아니라 검증된
NVIDIA 4K kernel을 선택하도록 GRUB 기본값을 영구 고정했다. 이 작업 중에는 재부팅하지 않았으며,
Kubernetes node, 포털, 실행 중인 Isaac Sim과 Nucleus도 중단하지 않았다.

적용 상태:

```text
/etc/default/grub:
  GRUB_DEFAULT=saved

/boot/grub/grubenv:
  saved_entry=Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-1026-nvidia

current kernel: 6.17.0-1026-nvidia
current page size: 4096
backup: /etc/default/grub.bak-20260721-215758
```

실행한 핵심 명령:

```bash
sudo sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' /etc/default/grub
sudo update-grub
sudo grub-set-default \
  'Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-1026-nvidia'
sudo grub-editenv /boot/grub/grubenv unset next_entry
```

`grub-reboot`의 `next_entry`는 1회 부팅용이므로 제거하고, `saved_entry`만 유지했다. 또한 자동
`apt autoremove`가 검증된 kernel 구성요소를 정리하지 않도록 다음 versioned package를 manual로
표시했다.

```text
linux-image-6.17.0-1026-nvidia
linux-headers-6.17.0-1026-nvidia
linux-modules-6.17.0-1026-nvidia
linux-modules-nvidia-fs-6.17.0-1026-nvidia
linux-tools-6.17.0-1026-nvidia
```

이는 package를 무조건 `hold`한 것이 아니다. 동일 package의 보안/수정 업데이트는 막지 않으면서,
새 kernel이 설치되어도 GRUB은 위의 정확한 NVIDIA kernel entry를 기본으로 유지한다. 이 entry를
계속 사용하려면 `/boot/vmlinuz-6.17.0-1026-nvidia`와 initrd를 삭제하지 않아야 한다.

적용 직후 비재부팅 검증:

```text
DGX Spark node: Ready
portal deployment: 1/1
Isaac ARM64 deployment: 1/1
DRA claim: allocated,reserved
running kernel/page size: 변경 없음
```

의도적으로 원래 설정으로 되돌릴 때만 다음 rollback을 사용한다.

```bash
sudo cp -a /etc/default/grub.bak-20260721-215758 /etc/default/grub
sudo update-grub
sudo grub-editenv /boot/grub/grubenv unset saved_entry
```

rollback 명령도 즉시 reboot를 수행하지 않는다. 다음 reboot 전에 `GRUB_DEFAULT`, `saved_entry`,
`/boot`의 kernel/initrd 존재 여부를 다시 확인해야 한다.

---

## 16. 참고 문서

- NVIDIA Isaac Sim 6.0.1 Livestream Clients: <https://docs.isaacsim.omniverse.nvidia.com/6.0.1/installation/manual_livestream_clients.html>
- NVIDIA Isaac Sim 6.0.1 Container Installation: <https://docs.isaacsim.omniverse.nvidia.com/6.0.1/installation/install_container.html>
- NVIDIA DGX OS 7 Release Notes: <https://docs.nvidia.com/dgx/dgx-os-7-user-guide/release_notes.html>
- GNU GRUB Manual — one-shot `next_entry`와 submenu 식별: <https://www.gnu.org/software/grub/manual/grub/grub.html>
- 제품/기능 범위: [`ISAAC_UI_MVP_SCOPE.md`](./ISAAC_UI_MVP_SCOPE.md)
- eecs-k8s/c-k8s 파일 경계: [`SMARTX_MIGRATION_PLAN.md`](./SMARTX_MIGRATION_PLAN.md)
- amd64 실제 성공 기준: [`TWINX_ISAAC_SIM_E2E_2026-07-15.md`](./TWINX_ISAAC_SIM_E2E_2026-07-15.md)

---

## 17. 한 문장 결론

C DGX Spark의 Isaac Sim 6.0.1 ARM64 WebRTC 실패 원인은 64K kernel의 ELF page alignment였고, DGX Spark용 4K `6.17.0-1026-nvidia`, 포털의 ARM64 자동 image 선택, hostNetwork와 node IP 방식으로 DRA/WebRTC를 실제 검증했으며, Nucleus는 올바른 `nucleus-cred`를 사용한 새 instance에서 인증 `status: OK`까지 확인했다.
