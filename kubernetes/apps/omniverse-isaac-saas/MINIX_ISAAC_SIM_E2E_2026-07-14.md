# MiniX Isaac Sim Harbor + DRA + WebRTC E2E 실행 기록

> 실행일: 2026-07-14
> 대상: MiniX Kubernetes `v1.34.3`, NVIDIA RTX 3090 GPU 노드
> 목적: SmartX/eecs-k8s 이관 전에 개인 `isaac-twinx` 저장소와 MiniX에서 Isaac Sim self-service 최소 흐름을 실제로 끝까지 검증한다.
> 보안: 이 문서에는 Harbor robot secret, Nucleus 비밀번호, GHCR token, SSH 비밀번호를 기록하지 않는다.

---

## 1. 결론

다음 흐름을 MiniX에서 실제로 검증했다.

```text
Isaac TwinX 내부 포털
  -> Kubernetes ResourceSlice에서 GPU inventory 조회
  -> gpu 노드 RTX 3090 UUID 선택
  -> resource.k8s.io/v1 ResourceClaim 생성
  -> NVIDIA DRA가 정확한 GPU 1개 할당
  -> Harbor private registry에서 Isaac Sim 6.0 이미지 pull
  -> Isaac Sim Kit 실행
  -> 인스턴스별 LoadBalancer Service 생성
  -> WebRTC TCP 49100 / UDP 47998 노출
  -> 포털 API에 사용자, 노드, GPU, Stream IP, Running 상태 표시
```

최종 확인값은 다음과 같다.

```text
Kubernetes: v1.34.3
GPU node: gpu
GPU node IP: 10.30.0.13
GPU: NVIDIA GeForce RTX 3090 24Gi
GPU UUID: GPU-a4dda0d8-1036-c78c-127a-b910925061ce
DRA driver: gpu.nvidia.com
DRA device: gpu/gpu-0

Harbor: http://10.34.48.223
Nucleus: omniverse://10.34.48.221/
Portal: http://10.34.48.222
Isaac Sim Stream IP: 10.34.48.224
WebRTC signaling: TCP 49100 reachable
WebRTC media: UDP 47998 endpoint registered

Instance: minix-e2e
Created by: chang
Pod: Running 1/1
ResourceClaim: allocated,reserved
GPU process: /isaac-sim/kit/kit
```

최신 Nucleus mounted-server 보정 Isaac Sim 이미지:

```text
repository: 10.34.48.223/omniverse/isaac-sim
tag: 6.0-netai-f2606b4-r5
digest: sha256:cbd29a70ce7d743430ed6794db4aa673cd31fe1141783025f014c2092a9cda68
source revision: 30dc739bde3b29ea507600acb0371a6efae7805e
```

사용자 WebRTC 시험에 사용한 `minix-e2e` instance는 r3 digest였으며, 2026-07-15 포털 Delete/GPU 반환 검증 후 삭제했다. 현재 사용자가 시험 중인 `test1`은 r4 digest를 유지하고, 새 instance부터 r5 digest를 사용한다.

---

## 2. 다른 문서와의 구분

이 문서는 설계 문서가 아니라 **Harbor 설치부터 실제 Isaac Sim WebRTC 실행까지의 실행 기록과 검증 증거**다.

| 문서 | 역할 |
| --- | --- |
| `ISAAC_UI_MVP_SCOPE.md` | 원본 대비 유지/변경/제거 범위와 목표 MVP 설계 |
| `MINIX_GPU_DRA_POC_2026-07-13.md` | Kubernetes 1.34.3 업그레이드와 NVIDIA DRA 사전 검증 |
| `MINIX_ISAAC_SIM_E2E_2026-07-14.md` | Harbor, 이미지, 포털, DRA, Nucleus, WebRTC 실제 통합 실행 기록 |
| `SMARTX_MIGRATION_PLAN.md` | 이전 링크 호환용 안내 |

UI 기능 정의나 SmartX chart 설계를 이 문서에 다시 반복하지 않는다. 이 문서는 “실제로 무엇을 실행했고 어떤 결과가 나왔는가”만 기록한다.

---

## 3. 작업 저장소와 변경 경계

### 3.1 개인 구현 저장소

```text
repository: https://github.com/mj006648/isaac-twinx
local: /home/chang/git/isaac-twinx
branch: main
```

관련 커밋:

```text
0631c6e feat: add isaac sim image
333c1a8 fix: start isaac sim
```

`isaac-twinx`에 포함된 범위:

```text
FastAPI 기반 최소 포털
GPU inventory와 DRA claim 생성
인스턴스 Deployment/Service 생성 및 삭제
사용자 이름 annotation
WebRTC Stream IP 표시
Isaac Sim 6.0 이미지 Dockerfile
SmartX Omniverse extension 고정 lock
MiniX 읽기 전용 배포 예제
테스트
```

### 3.2 MiniX GitOps 저장소

```text
repository: https://github.com/mj006648/MiniX
local: /home/chang/git/MiniX
branch: main
```

Harbor 관련 커밋:

```text
9428a255 feat: add minix harbor
b21e1b97 fix: order harbor sync
```

### 3.3 이번 단계에서 수정하지 않은 저장소

다음 저장소에는 아직 Isaac SaaS 구현을 push하지 않았다.

```text
SJoon99/eecs-k8s
SJoon99/c-k8s
SJoon99/twinx-k8s
```

Standalone MiniX E2E가 끝난 뒤 SmartX feature graph와 preset 구조로 옮기는 순서를 유지한다.

---

## 4. Harbor 설치

### 4.1 참조한 원본

Harbor 설치 값은 다음 private 운영 저장소를 기준으로 확인했다.

```text
repository: SmartX-Team/TwinX-Ops
commit: 91d89ecf06124c077216df95790e99f1b396aaf5
source values: argocd/twinx-infra/apps/harbor/values.yaml
```

원본의 주요 조건:

```text
Harbor Helm chart: 1.19.1
Harbor application: 2.15.1
Rook-Ceph block storage
LoadBalancer exposure
Trivy enabled
```

### 4.2 MiniX에 맞춘 변경

| 항목 | TwinX 원본 | MiniX 적용 |
| --- | --- | --- |
| LoadBalancer IP | `10.38.38.210` | `10.34.48.223` |
| MetalLB pool | TwinX pool | `primary-pool` |
| TLS | false | false, 실험 단계 HTTP |
| StorageClass | `rook-ceph-block` | `rook-ceph-block` |
| registry PVC | 500Gi | 100Gi |
| jobservice PVC | 원본 기준 | 5Gi |
| database PVC | 원본 기준 | 5Gi |
| redis PVC | 원본 기준 | 1Gi |
| trivy PVC | 원본 기준 | 10Gi |
| node pinning | `rm352-1` | 제거 |
| admin password | values 직접 값 | `harbor-admin` Secret 참조 |

Harbor admin 비밀번호는 Git에 넣지 않고 다음 Secret으로 생성했다.

```text
namespace: harbor
secret: harbor-admin
key: HARBOR_ADMIN_PASSWORD
```

### 4.3 Argo CD 동기화

MiniX root app-of-apps는 기존 Progressing application의 sync wave 때문에 전체 operation이 대기했다. Harbor 설정은 Git에 먼저 push한 뒤, 동일 Git source로 렌더링한 Harbor child `Application`을 직접 적용했다.

최종 상태:

```text
Application: harbor
Sync: Synced
Health: Healthy
Portal HTTP: 200
API ping: 200
Registry /v2/: 401 without authentication, expected
```

Harbor workload 확인 결과:

```text
harbor-core: 1/1
harbor-jobservice: 1/1
harbor-nginx: 1/1
harbor-portal: 1/1
harbor-registry: 1/1
harbor-database: 1/1
harbor-redis: 1/1
harbor-trivy: 1/1
```

PVC는 모두 `Bound` 상태를 확인했다.

---

## 5. Harbor project와 최소 권한 계정

### 5.1 project

```text
project: omniverse
visibility: private
```

### 5.2 robot 계정 분리

빌드와 runtime 권한을 분리했다.

| 용도 | 권한 | Kubernetes Secret |
| --- | --- | --- |
| Isaac image builder | repository pull, push | `harbor/isaac-builder-regcred` |
| Kubernetes runtime | repository pull only | `omniverse/harbor-regcred` |

두 계정 모두 Harbor `/v2/` 인증 HTTP 200을 확인했다. Secret 원문은 출력하거나 Git에 저장하지 않았다.

Harbor robot secret은 생성 시 한 번만 안전하게 받아 Kubernetes `kubernetes.io/dockerconfigjson` Secret으로 저장했다. 인증 오류를 수정하는 과정에서 secret을 즉시 rotate했고, 잘못 저장된 첫 값은 덮어썼다.

### 5.3 GPU 노드 containerd

Harbor가 실험 단계 HTTP이므로 GPU node containerd에 registry host를 등록했다.

```text
/etc/containerd/certs.d/10.34.48.223/hosts.toml
```

설정 개념:

```toml
server = "http://10.34.48.223"

[host."http://10.34.48.223"]
  capabilities = ["pull", "resolve"]
  skip_verify = true
```

운영 전에는 Harbor TLS를 적용하고 HTTP insecure registry 설정을 제거해야 한다.

---

## 6. Isaac Sim 이미지 구성

### 6.1 최종 파일 구조

개인 저장소의 이미지 정의:

```text
images/isaac-sim/
├── Dockerfile
├── README.md
├── entrypoint.sh
├── extensions.lock.json
├── experiment/
│   ├── set_4k.py
│   └── wander.py
└── overrides/
    ├── gist.netai.video.extension.toml
    ├── gist.streamer.extension.py
    └── gist.timetravel.extension.py

scripts/prepare_isaac_extensions.py
tests/test_isaac_image.py
```

생성된 extension payload는 `.gitignore`로 제외한다.

```text
images/isaac-sim/extensions/
```

이미지 build 전에 `prepare_isaac_extensions.py`가 lock 파일과 upstream commit을 기준으로 payload를 재생성한다.

### 6.2 base image 고정

```text
nvcr.io/nvidia/isaac-sim:6.0.0
base digest: sha256:68735a60b6c15c85e0dd0098570c6d2cc79e928f2d068ce2790aa43284ac165d
```

태그 변조나 재게시 영향을 줄이기 위해 Dockerfile에서 digest까지 고정했다.

### 6.3 Extension source 고정

```text
repository: https://github.com/SmartX-Team/Omniverse.git
commit: f2606b43c437d1e3b70e16edb011fc3b237bb2e4
selected extensions: 9
```

포함된 extension:

```text
gist.husky.isaacsim_ros
gist.netai.falcon
gist.netai.time_travel_summarization
gist.netai.uwb
gist.netai.video
gist.streamer
gist.timetravel
netai.cesium.digitaltwin
netai.smart.factory
```

Deprecated extension은 제외했다.

`gist.netai.video` 원본 TOML에는 중복 `[python.pipapi]` section이 있어 TOML parser가 실패했다. 의미를 유지한 단일 section override를 이미지 build에 적용했다.

### 6.4 이미지에 넣은 것

```text
Isaac Sim 6.0 official container
ROS Jazzy packages
선정한 NetAI extensions 9개
Xvfb와 기본 그래픽 runtime library
Nucleus config 생성 로직
선택형 startup USD/camera 로직
WebRTC launcher 연결
```

### 6.5 이미지에서 뺀 것

```text
code-server / VSCode sidecar
Prometheus / OTel / node-exporter
stage reporter callback
runtime git pull
모든 extension 자동 enable
사용자별 workspace PVC
Scenes / GPU bans / Metrics UI
```

Extension은 이미지에 포함하고 Kit extension folder에 등록하지만, 모두 강제로 자동 enable하지 않는다. Scene이나 사용 기능이 요구할 때 enable하는 방식으로 유지한다.

### 6.6 Nucleus 연결

Nucleus server 자체는 Isaac Sim 이미지에 포함하지 않는다.

Pod runtime 환경:

```text
OMNI_SERVER
OMNI_PROJECT_PATH
OMNI_USER
OMNI_PASS
```

MiniX endpoint:

```text
omniverse://10.34.48.221/
```

credential Secret:

```text
namespace: omniverse
secret: nucleus-cred
keys:
  OMNI_USER
  OMNI_PASS
```

`OMNI_PASS`는 기존 `nucleus-passwords/master-password`를 출력하지 않고 복사했다. 사용자 이름은 MiniX Nucleus 기본 관리자 계정에 맞췄다.

entrypoint는 Python JSON quoting을 사용해 TOML 문자열 escaping 문제를 막고 `/root/.nvidia-omniverse/config/omniverse.toml`을 생성한다.

---

## 7. 이미지 registry 선택

### 7.1 GHCR push 실패 원인

첫 build는 성공했지만 GHCR push는 구조적으로 사용할 수 없었다.

```text
largest NVIDIA base layer: 약 10.59GB
GHCR maximum layer size: 10GB
```

따라서 source와 portal image는 GitHub/GHCR에 두고, 대형 Isaac Sim runtime image는 MiniX Harbor에 저장하는 구조로 분리했다.

참고:

- GitHub Container registry: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry

### 7.2 Harbor artifact

```text
latest: 10.34.48.223/omniverse/isaac-sim:6.0-netai-f2606b4-r4
latest digest: sha256:70399e7db9883341bae8539c8485ac5b17702cdb3a15ea218c687ccc1780c50f
deleted minix-e2e digest (historical): sha256:5be32513c96b71a0b7224c87bd59b119f2e52b4461dd950dce14518acdcc0049
```

Kubernetes manifest는 tag가 아니라 digest를 사용한다.

---

## 8. 이미지 build 과정

### 8.1 BuildKit

공식 BuildKit `v0.30.0` binary를 GitHub release asset digest로 검증한 뒤 GPU node에서 임시 daemon으로 사용했다.

```text
release: moby/buildkit v0.30.0
worker: containerd/overlayfs
platform: linux/amd64
```

최초 전체 build는 NVIDIA base layer, Ubuntu package, ROS Jazzy package를 포함했다. Harbor push가 끝난 뒤 임시 BuildKit root와 registry 인증 파일은 삭제했다.

실행 중 발견한 entrypoint 문제는 containerd에 이미 내려받은 11GB 이미지를 base로 사용해 작은 patch layer만 r1, r2, r3로 다시 push했다. Nucleus runtime path 보정도 검증된 r3 digest를 정확한 base로 고정하고 entrypoint와 두 Extension override만 교체해 r4로 push했다.

### 8.2 중간 수정 이력

| 이미지 | 결과 | 원인/수정 |
| --- | --- | --- |
| initial | CrashLoop | `set -u` 상태에서 ROS generated setup script가 optional variable 참조 |
| r1 | CrashLoop | system ROS를 미리 source하면 official Isaac launcher 환경과 충돌 가능 |
| r2 | CrashLoop | `STARTUP_USD_STAGE`가 비어 있을 때 helper가 상태 1 반환, `set -e`가 종료 |
| r3 | Running | ROS source는 official launcher에 맡기고 빈 startup stage를 `return 0` 처리 |
| r4 | Harbor push/runtime pull 확인 | Nucleus Content Browser path와 두 Extension의 과거 고정 URI를 runtime `OMNI_SERVER`/`OMNI_PROJECT_PATH`로 교체 |

최종 entrypoint 원칙:

```text
1. Xvfb 시작
2. 9개 extension symlink 등록
3. Nucleus config 생성
4. optional startup stage 준비
5. official Isaac Sim streaming launcher 실행
```

---

## 9. 디스크 문제와 정리

### 9.1 최초 실패

Isaac Sim image pull 중 GPU node가 kubelet ephemeral-storage eviction threshold 아래로 내려가 Pod가 Evicted됐다.

```text
kubelet threshold: 약 69.5GB available
image compressed size: 약 11GB
image unpack과 containerd snapshot으로 추가 공간 필요
```

증상:

```text
ContainerCreating
Evicted: low on resource: ephemeral-storage
DiskPressure=True
```

### 9.2 안전하게 정리한 항목

먼저 cache와 로그만 정리했다.

```text
~/.cache/ov
~/.cache/pip
~/.cache/uv
~/.cache/packman/chk
~/.local/share/Trash
~/isaac-sim/temp
systemd journal: 약 3.9GB -> 약 471MB
```

그다음 `~/isaac-sim/project`가 기존 차량/도시/traffic light/Worker 자율주행 실험 데이터임을 디렉터리와 ZIP 목록으로 확인했다. 사용자 확인 후 다음을 삭제했다.

```text
~/isaac-sim/project
~/isaac-sim/temp.zip
isaac-sim-standalone-5.1.0-linux-x86_64.zip
isaac-sim-assets-robots_and_sensors-5.1.0.zip
isaac-sim-assets-materials_and_props-5.1.0.zip
isaac-sim-assets-environments-5.1.0.zip
```

보존한 항목:

```text
실제 로컬 Isaac Sim 설치본
~/isaac-sim/Assets
~/isaac-sim/exts
~/isaac-sim/extscache
~/isaac-sim/myassets
~/nuscenes
```

정리 결과:

```text
free disk: 94GB -> 150GB
local ~/isaac-sim: 약 103GB -> 약 47GB
image pull 후 free disk: 약 126GB
DiskPressure=False
```

---

## 10. 최소 포털 배포

### 10.1 외부 포털

```text
Service: isaac-twinx
External IP: 10.34.48.222
Mode: WRITE_ENABLED=false
```

Keycloak 또는 다른 서버 측 인증·인가가 붙기 전에는 외부 포털의 create/delete를 열지 않는다.

### 10.2 내부 E2E 포털

실제 create/delete 검증은 외부에 노출되지 않는 별도 ClusterIP portal로 수행했다.

```text
Deployment: isaac-twinx-e2e
Service: isaac-twinx-e2e
Exposure: ClusterIP only
WRITE_ENABLED: true
AUTH_DISPLAY_NAME: chang
```

내부 포털에 설정한 runtime 값:

```text
ISAAC_SIM_IMAGE=<final immutable Harbor digest>
IMAGE_PULL_SECRETS=harbor-regcred
DRA_API_VERSION=resource.k8s.io/v1
DRA_DRIVER=gpu.nvidia.com
DRA_DEVICE_CLASS=gpu.nvidia.com
OMNI_SERVER=omniverse://10.34.48.221/
OMNI_PROJECT_PATH=Projects/demonstration
NUCLEUS_SECRET_NAME=nucleus-cred
```

외부 포털은 같은 managed resource label을 조회하므로 내부 포털이 생성한 실제 인스턴스를 읽기 전용 화면에서 볼 수 있다.

---

## 11. 실제 GPU 선택과 인스턴스 생성

### 11.1 GPU inventory

내부 포털 `/api/gpus`가 다음 정보를 확인했다.

```text
node: gpu
product: NVIDIA GeForce RTX 3090
memory: 24Gi
architecture: Ampere
status: Available
compatibleWithWebRTC: true
```

Source of truth:

```text
ResourceSlice
ResourceClaim allocation results
Node Ready/unschedulable 상태
```

SSH나 `nvidia-smi`를 UI가 직접 호출하지 않는다.

### 11.2 create request

```json
{
  "name": "minix-e2e",
  "gpuUUID": "GPU-a4dda0d8-1036-c78c-127a-b910925061ce"
}
```

생성 응답 요약:

```text
name: minix-e2e
user: chang
node: gpu
GPU: NVIDIA GeForce RTX 3090
Stream IP: 10.34.48.224
initial status: Pending
```

### 11.3 생성된 리소스

```text
ResourceClaim: isaac-minix-e2e-gpu
Service: isaac-minix-e2e-stream
Deployment: isaac-minix-e2e
Pod: isaac-minix-e2e-*
```

ResourceClaim selector는 UUID를 정확히 비교한다.

```text
device.driver == "gpu.nvidia.com"
device.attributes["gpu.nvidia.com"].uuid == selected UUID
allocationMode: ExactCount
count: 1
```

최종 claim 상태:

```text
allocated,reserved
pool: gpu
device: gpu-0
node: gpu
```

---

## 12. 실제 WebRTC와 GPU 검증

### 12.1 Kubernetes 상태

```text
Deployment: 1/1 Available
Pod: 1/1 Running
Node: gpu
Restart: 0 on final r3 Pod
```

### 12.2 Service와 EndpointSlice

```text
LoadBalancer IP: 10.34.48.224
TCP signaling: 49100
UDP media: 47998
Endpoint Pod IP: 10.234.69.80
```

TCP 확인:

```text
10.34.48.224:49100 reachable
```

사용자는 Isaac Sim WebRTC Streaming Client에 Stream IP `10.34.48.224`를 입력한다.

### 12.3 Isaac Sim Kit

로그에서 다음을 확인했다.

```text
Isaac Sim Full Streaming Version: 6.0.0-rc.59
omni.kit.livestream.core startup
omni.kit.livestream.webrtc startup
omni.kit.livestream.app startup
isaacsim.exp.full.streaming startup
```

GPU node `nvidia-smi` 확인:

```text
GPU UUID: GPU-a4dda0d8-1036-c78c-127a-b910925061ce
process: /isaac-sim/kit/kit
initial observed memory: 432 MiB
```

### 12.4 포털 상태

`/api/instances` 응답에서 다음을 확인했다.

```text
name: minix-e2e
user: chang
status: Running
ready: true
node: gpu
GPU product: NVIDIA GeForce RTX 3090
GPU status: Allocated
allocatedBy: omniverse/isaac-minix-e2e-gpu
streamIP: 10.34.48.224
```

---

## 13. Nucleus 상태와 경고

entrypoint에서 다음 로그를 확인했다.

```text
Nucleus endpoint configured
```

Isaac Sim Kit의 Nucleus 관련 extension도 startup했다.

```text
omni.kit.widget.nucleus_connector
omni.kit.widget.nucleus_info
```

초기 r3/r4 검증 당시 OmniHub helper가 root container 환경에서 config file을 만들지 못하고 재연결하는 warning이 반복됐다.

```text
Hub failed to launch
```

이 warning은 현재 Isaac Sim Kit와 WebRTC 실행을 막지 않았다. 다음 검증은 별도로 남아 있다.

```text
Nucleus 경로 browse
USD open
Nucleus write/save
credential 권한 확인
OmniHub warning 제거 또는 비활성화 필요성 판단
```

이 절은 당시 검증 경계를 기록한 역사 구간이다. 후속 asset read/write는 13.2에서, OmniHub 비활성화와 자동 연결은 13.3에서 완료했다.


### 13.1 2026-07-15 Nucleus/Extension 연결 정책 보정

실행 중인 Pod와 개인 저장소를 다시 확인해 다음을 구분했다.

~~~text
Extension source 9개 image 포함: 확인
/isaac-sim/exts symlink 등록: 9개 확인
custom Extension 자동 startup: 0개
Nucleus config/credential 주입: 확인
Isaac Pod에서 Nucleus 주요 TCP port 도달: 확인
Nucleus Content Browser read/write: 당시 미검증, 13.2/13.3에서 완료
~~~

자동 startup 0개는 오류가 아니라 확정 정책이다. Extension은 검색 가능하게 등록만 하고 사용자가 필요한 것만 Extension Manager에서 활성화한다.

원본 Extension 중 다음 두 개에는 과거 Nucleus URI가 하드코딩되어 있었다.

~~~text
gist.streamer
gist.timetravel
~~~

개인 isaac-twinx 소스에서는 이를 제거하고 다음 런타임 값으로 조합하도록 변경했다.

~~~text
OMNI_SERVER=omniverse://<cluster-nucleus>/
OMNI_PROJECT_PATH=Projects/demonstration
~~~

Extension payload는 Git에 직접 커밋하지 않으므로, 두 Python override를 images/isaac-sim/overrides에 두고 prepare_isaac_extensions.py가 고정 upstream commit을 materialize할 때 다시 적용하도록 했다.

entrypoint는 다음 동작을 수행한다.

1. OMNI_SERVER를 정규화한다.
2. credential을 0600 Nucleus client config에 기록한다.
3. Nucleus root와 project URL을 Isaac Sim 6.0 Content Browser folder에 추가한다.
4. Isaac asset root를 cluster Nucleus 경로로 전달한다.
5. custom Extension을 자동 활성화하지 않는다.

이 소스 수정은 기존 실행 중인 r3 digest에 자동 반영되지 않는다. 다음 r4 image를 빌드해 Harbor에 immutable digest로 push하고 Kubernetes runtime pull까지 확인했다.

~~~text
tag: 10.34.48.223/omniverse/isaac-sim:6.0-netai-f2606b4-r4
digest: sha256:70399e7db9883341bae8539c8485ac5b17702cdb3a15ea218c687ccc1780c50f
image revision label: c171142a33d6e5fd2daee018338e4d7adde99168
~~~

r4는 검증된 r3 digest를 base로 entrypoint와 `gist.streamer`/`gist.timetravel` override만 교체했다. BuildKit의 최초 push는 로컬 pull-only config 때문에 HTTP 401이었고, `harbor/isaac-builder-regcred`를 임시 Docker config로 사용해 push했다. Secret 값은 출력하지 않았고 build 종료 후 임시 builder root, context, push/pull 인증 디렉터리를 삭제했다. 실제 Pod가 사용하는 `omniverse/harbor-regcred`로 r4를 다시 pull해 manifest digest와 revision label도 확인했다.

새 인스턴스로 다음 GUI 동작은 아직 사용자가 확인해야 한다.

~~~text
Content Browser에서 Nucleus root/project 표시
Nucleus folder 목록 조회
USD open
USD save/write
gist.streamer 또는 gist.timetravel 수동 enable 후 새 OMNI_SERVER 사용
~~~

WebRTC는 Isaac Sim WebRTC Streaming Client 2.0.0으로 10.34.48.224에 접속해 영상과 입력이 정상 동작하는 것을 사용자가 확인했다.

개인 GitHub 반영:

~~~text
mj006648/isaac-twinx main: c171142
GitHub Actions Build portal image: success
mj006648/smartx-k8s main: 31f3682
mj006648/twinx-k8s default: 4565d2c
~~~

개인 SmartX chart에는 nucleus.projectPath를 추가해 OMNI_PROJECT_PATH로 포털에 전달하고, TwinX preset에는 Projects/demonstration을 설정했다. master의 Helm 4.2.3에서 chart lint, app render, SmartX root render와 Kubernetes server dry-run이 모두 성공했다.

새 GHCR portal image와 Nucleus entrypoint/Extension override가 들어간 r4 Isaac Sim runtime image를 각각 GHCR와 Harbor에 반영했다.

MiniX live portal 적용 결과:

~~~text
portal: http://10.34.48.222
image: ghcr.io/mj006648/isaac-twinx:sha-c171142a33d6e5fd2daee018338e4d7adde99168
WRITE_ENABLED=true
OMNI_PROJECT_PATH=Projects/demonstration
ISAAC_SIM_IMAGE=10.34.48.223/omniverse/isaac-sim@sha256:70399e7db9883341bae8539c8485ac5b17702cdb3a15ea218c687ccc1780c50f
Deployment rollout: success
/api/config writeEnabled: true
/healthz: ok
~~~

이 활성화는 사용자의 create/delete 및 GPU 반환 실험을 위한 임시 설정이다. AUTH_ENABLED=false이므로 외부 운영 환경에는 그대로 사용하지 않는다.

기존 `minix-e2e` Deployment는 r3 digest로 WebRTC를 검증한 뒤 2026-07-15 사용자가 포털에서 삭제했다. 포털 설정 변경은 기존 Deployment를 자동 교체하지 않으므로 새로 생성하는 instance부터 r4를 사용한다.

### 13.2 2026-07-15 Nucleus 실데이터 확인과 r5 분리

`test1` Pod에서 실제 런타임과 같은 `OMNI_USER`/`OMNI_PASS`를 사용해 Omniverse Client API를 호출했다. Secret 원문은 출력하지 않았다.

```text
Nucleus root list: Result.OK, 4 entries
NVIDIA/Assets/Isaac/6.0/Isaac/Robots: Result.OK, 50 entries
NVIDIA/Assets/Isaac/6.0/Isaac/Environments: Result.OK, 13 entries
Projects/demonstration create: Result.OK
netai_connection_test.usda write/stat/list: Result.OK
```

따라서 Content Browser의 자물쇠는 asset 부재나 인증 실패가 아니라 Isaac Sim curated collection의 read-only 표시다. r4는 Nucleus root와 project까지 이 read-only `Isaac Sim` collection에 섞어 넣은 UI 구조가 문제였다.

r5에서는 역할을 다음처럼 분리했다.

```text
Isaac Sim collection
  -> omniverse://10.34.48.221/NVIDIA/Assets/Isaac/6.0
  -> NVIDIA 공식 mirror asset을 읽는 read-only collection

Omniverse > NetAI Nucleus
  -> omniverse://10.34.48.221
  -> mounted_servers 설정으로 등록한 일반 Nucleus connection
  -> Projects/demonstration 등 읽기/쓰기 경로 사용
```

r5 build/push/runtime pull과 개인 저장소 반영값은 다음과 같다.

```text
isaac-twinx commit: 30dc739bde3b29ea507600acb0371a6efae7805e
image tag: 10.34.48.223/omniverse/isaac-sim:6.0-netai-f2606b4-r5
image digest: sha256:cbd29a70ce7d743430ed6794db4aa673cd31fe1141783025f014c2092a9cda68
twinx-k8s preset commit: 20a4fba
portal source commit: d194e2c6346b4cf73ac32233d918526abe40b9e5
portal image: ghcr.io/mj006648/isaac-twinx:sha-d194e2c6346b4cf73ac32233d918526abe40b9e5
```

live portal을 갱신하는 과정에서 app chart를 `--namespace` 없이 수동 렌더해 ClusterRoleBinding subject가 `default/isaac-twinx`로 바뀌었다. Pod health는 정상이었지만 `omniverse/isaac-twinx`가 `nodes`와 `resourceslices.resource.k8s.io`를 list할 수 없어 `/api/gpus`와 `/api/instances`가 503을 반환했다.

다음처럼 destination namespace를 명시해 재렌더·적용했다.

```bash
helm template isaac-twinx apps/omniverse-isaac-saas \
  --namespace omniverse \
  -f patches/omniverse-isaac-saas/values.yaml
```

복구 확인:

```text
ClusterRoleBinding subject: ServiceAccount/omniverse/isaac-twinx
resourceslices list: yes
/api/gpus: 200
/api/instances: 200
live new-instance image: r5 immutable digest
portal footer: NetAI copyright + GIST NetAI Laboratory + SmartX-Team GitHub 확인
test1: Running, restart 0, r4 유지
```

SmartX/Argo CD에서는 `manifest.yaml`의 destination namespace가 `omniverse`이므로 정상 sync 시 같은 값이 사용된다. 수동 `helm template` 리허설에서도 반드시 `--namespace omniverse`를 넣는다.

### 13.3 2026-07-15 Content Browser 자동 연결 보정

사용자 GUI에서 `Omniverse`를 펼쳐도 `NetAI Nucleus`가 자동으로 표시되지 않고, 수동 `Add New Connection`에 `omniverse://10.34.48.221`을 넣으면 연결되는 현상을 확인했다.

Nucleus 데이터 부재나 권한 문제는 아니었다.

```text
동일 Pod Omni Client root list: Result.OK, 4 entries
Robots list: Result.OK, 50 entries
Environments list: Result.OK, 13 entries
Projects/demonstration list: Result.OK
Nucleus auth log: status OK
```

실패 원인은 두 가지 런타임 설정 경계였다.

1. Isaac Sim 6.0 컨테이너의 `OMNICLIENT_HUB_EXE=/usr/local/bin/hub`가 config 파일을 만들기 전에 종료하며 재연결을 반복했다.
2. r5 entrypoint가 쓴 `user.config.json`에는 mounted server가 있었지만 Streaming Kit가 시작 설정으로 소비하지 않아 UI에 자동 등록되지 않았다.

적용한 값:

```text
OMNICLIENT_HUB_MODE=disabled
OMNICLIENT_USE_HUB=0
--/exts/omni.kit.window.content_browser/mounted_servers/NetAI Nucleus=omniverse://10.34.48.221
```

첫 두 값은 실패한 Hub 대신 Client Library의 직접 Nucleus 연결을 사용한다. 마지막 값은 Content Browser 3.1.8이 실제로 읽는 Carb settings 경로를 Kit 실행 인자로 전달한다. 확장 코드의 `_get_mounted_servers()`와 `_init_view()`가 이 dictionary를 읽고 첫 server를 자동 연결하는 것도 컨테이너 소스로 확인했다.

live `test` Deployment에 같은 env/arg를 적용해 Pod만 재시작했다. 기존 ResourceClaim과 `10.34.48.224` Service는 유지됐고 Hub 실패 로그는 사라졌다. 이후 Launch에도 들어가도록 portal resource generator와 테스트에 반영했다.

```text
portal source commit: d194e2c6346b4cf73ac32233d918526abe40b9e5
portal image: ghcr.io/mj006648/isaac-twinx:sha-d194e2c6346b4cf73ac32233d918526abe40b9e5
TwinX preset commit: 20a4fba
pytest: 32 passed
live portal APIs: /api/gpus 200, /api/instances 200
```

---

## 14. 테스트와 검증 명령

### 14.1 개인 저장소

```bash
cd /home/chang/git/isaac-twinx
.venv/bin/python -m pytest
bash -n images/isaac-sim/entrypoint.sh
kubectl kustomize deploy/minix >/tmp/isaac-twinx-rendered.yaml
```

최종 결과:

```text
32 passed
entrypoint bash syntax passed
MiniX kustomize render passed
```

### 14.2 Harbor

```bash
kubectl -n argocd get application harbor
kubectl -n harbor get deploy,statefulset,pod,pvc
curl -fsS http://10.34.48.223/api/v2.0/ping
```

Secret은 값이 아니라 key만 확인한다.

```bash
kubectl -n harbor get secret isaac-builder-regcred -o json | jq '.data|keys'
kubectl -n omniverse get secret harbor-regcred -o json | jq '.data|keys'
kubectl -n omniverse get secret nucleus-cred -o json | jq '.data|keys'
```

### 14.3 DRA와 인스턴스

```bash
kubectl get deviceclass
kubectl get resourceslices
kubectl -n omniverse get resourceclaim isaac-minix-e2e-gpu
kubectl -n omniverse get deploy,pod,svc -l app.kubernetes.io/instance=minix-e2e -o wide
kubectl -n omniverse get endpointslice -l kubernetes.io/service-name=isaac-minix-e2e-stream
```

### 14.4 GPU process

GPU node에서:

```bash
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader
```

---

## 15. 2026-07-15 인스턴스와 임시 포털 정리

사용자가 WebRTC 2.0.0 영상과 입력을 확인한 뒤 외부 포털에서 `minix-e2e` Delete를 실행했다.

삭제 후 다음 동적 리소스가 모두 사라진 것을 확인했다.

```text
isaac-minix-e2e Deployment: 없음
isaac-minix-e2e Pod: 없음
isaac-minix-e2e-gpu ResourceClaim: 없음
isaac-minix-e2e-stream Service: 없음
Isaac Sim GPU process: 없음
```

초기 독립 E2E 검증에 사용한 `isaac-twinx-e2e` Deployment와 ClusterIP Service는 구버전 포털이었다. 최신 `isaac-twinx`가 역할을 대체하고 Argo CD tracking label도 없으므로 함께 삭제했다.

정리 후 `omniverse` namespace에는 최신 `isaac-twinx` 포털과 `omniverse-nucleus-0`만 남았다.

---

## 16. 삭제와 GPU 반환 결과

사용자 포털 동작은 다음 요청에 해당한다.

```text
DELETE /api/instances/minix-e2e
```

삭제 직후 Kubernetes와 GPU inventory를 교차 확인했다.

```text
ResourceClaim: 0
GPU process: 0
GPU inventory: 1 total / 1 available / 0 allocated
RTX 3090: Available
```

따라서 포털 Delete가 동적 Deployment, Service, ResourceClaim을 정리하고 DRA GPU를 정상 반환하는 것까지 검증 완료했다.

---

## 17. 보안 경계

### 17.1 현재 적용

```text
Harbor project private
builder push/pull과 runtime pull-only 계정 분리
Secret 원문 Git 미저장
외부 포털 WRITE_ENABLED=false
내부 ClusterIP 포털만 mutation 허용
Isaac Sim image digest 고정
GPU UUID는 DRA selector로 정확 선택
```

### 17.2 운영 전 필수

```text
Harbor TLS 적용
Keycloak 또는 동등한 서버 측 인증·인가
사용자별 create/delete 권한
quota와 인스턴스 수 제한
LoadBalancer IP pool 정책
NetworkPolicy
Secret을 OpenBao + External Secrets로 이관
audit log
Nucleus 사용자별 권한
```

Isaac Sim WebRTC endpoint를 인증 없이 public internet에 직접 노출하지 않는다.

---

## 18. 알려진 제한과 남은 작업

1. RTX 3090은 최신 NVIDIA Isaac Sim 공식 요구사항의 권장/최소 GPU보다 낮을 수 있으므로 MiniX 결과는 실험 검증으로 취급한다.
2. 실패하던 OmniHub는 `OMNICLIENT_HUB_MODE=disabled`로 비활성화했고, Content Browser는 직접 Nucleus 연결과 Kit mounted-server 인자를 사용한다.
3. 외부 포털은 아직 Keycloak과 연결하지 않았지만 MiniX 실험을 위해 create/delete를 임시 활성화했다. 시험 종료 후 다시 비활성화해야 한다.
4. 인스턴스 삭제와 DRA GPU 반환은 사용자 UI 동작과 live cluster 상태로 검증 완료했다.
5. Extension 9개는 등록만 했고 모두 자동 enable하지 않았다.
6. 개인 `smartx-k8s` chart와 `twinx-k8s` preset 리허설은 완료했다. 실제 외부 `eecs-k8s`/`c-k8s` Isaac 반영은 아직 하지 않았다. 상세 증거는 [`SMARTX_PRE_MIGRATION_REHEARSAL_2026-07-14.md`](./SMARTX_PRE_MIGRATION_REHEARSAL_2026-07-14.md)를 본다.
7. Harbor는 현재 HTTP 실험 구성이다.
8. workspace PVC, metrics, code-server, scenes는 MVP에서 제외했다.

---

## 19. SmartX 이관 시 옮길 값

Standalone E2E에서 검증한 값은 다음처럼 분리한다.

### 19.1 eecs-k8s 공통 chart

```text
Deployment/Service/RBAC template
DRA ResourceClaim 생성 규칙
GPU inventory logic
instance create/list/delete API
imagePullSecret 참조 구조
Nucleus Secret 참조 구조
기본 WebRTC port
```

### 19.2 cluster preset

```text
Harbor repository와 immutable digest
Nucleus endpoint
Nucleus credential Secret name/key
LoadBalancer pool/IP 정책
DRA driver/deviceClass
WebRTC incompatible GPU policy
인증 provider 값
```

### 19.3 feature graph

기능:

```text
org.ulagbulag.io/omniverse/isaac-saas
```

필수 의존성:

```text
org.ulagbulag.io/omniverse/nucleus
org.ulagbulag.io/registry/container/harbor
nvidia.com/gpu
nvidia.com/gpu/dynamic-resource-allocation
```

현재 MVP는 exact GPU device 선택이 필수이므로 별도 `isaac-saas/dra` optional feature로 나누지 않는다.

SmartX 반영 전 `ISAAC_UI_MVP_SCOPE.md`의 feature graph와 실제 `eecs-k8s` naming pattern을 다시 대조한다.

---

## 20. 참고 자료

- 개인 구현: https://github.com/mj006648/isaac-twinx
- NVIDIA Isaac Sim container: https://catalog.ngc.nvidia.com/orgs/nvidia/-/containers/isaac-sim/6.0.0
- Isaac Sim container deployment: https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_container.html
- Isaac Sim livestream client: https://docs.isaacsim.omniverse.nvidia.com/latest/installation/manual_livestream_clients.html
- Isaac Sim requirements: https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html
- GitHub Container registry limits: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- Harbor robot account: https://goharbor.io/docs/2.10.0/working-with-projects/project-configuration/create-robot-accounts/
- BuildKit v0.30.0: https://github.com/moby/buildkit/releases/tag/v0.30.0

---

## 21. 한 문장 요약

MiniX Kubernetes 1.34.3에서 private Harbor의 Isaac Sim 6.0, NVIDIA DRA RTX 3090 정확 선택, Nucleus asset browse/read/write, 인스턴스별 LoadBalancer WebRTC, 사용자 표시와 delete/GPU 반환을 검증했고, Content Browser 역할을 분리한 r5 immutable image와 개인 SmartX chart/TwinX preset/live portal 반영까지 완료했으므로 다음 단계는 새 r5 instance의 GUI 표시를 확인한 뒤 실제 GPU 대상 cluster의 eecs-k8s/preset Argo CD 이관을 수행하는 것이다.
