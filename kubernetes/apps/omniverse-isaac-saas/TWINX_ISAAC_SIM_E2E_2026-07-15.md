# TwinX Isaac Sim E2E 실행 기록 — 2026-07-15

> 목적: 실제 TwinX 이기종 GPU 클러스터에서 `isaac-twinx` 포털이 GPU를 자동 발견하고, 지정 GPU에 Isaac Sim 6.0 인스턴스를 동시에 실행하며, 신규 Kubernetes Nucleus에 실제 인증·조회한 뒤 삭제와 GPU 반환까지 수행한 결과를 기록한다.
> Secret 원문은 기록하지 않는다.

## 1. 결론

최종 E2E는 성공했다.

```text
portal: 10.38.38.243
namespace: omniverse
Nucleus: omniverse://10.38.38.245/
Nucleus HTTP: 200
Isaac Sim image digest:
  sha256:c3a5b1b3402f3f2d6185fccee158023da59e99748ce096c33d5a2404fdea9bb7

동시 실행 1:
  instance: twinx-l40s7-e2e
  node: l40s
  GPU: NVIDIA L40S
  DRA device: l40s/gpu-4
  UUID: GPU-ebac507e-176f-1b5a-eee2-d0fe94cd0874
  WebRTC IP: 10.38.38.180

동시 실행 2:
  instance: twinx-a6000-e2e
  node: sv4000-1
  GPU: NVIDIA RTX A6000
  DRA device: sv4000-1/gpu-1
  UUID: GPU-83657c9e-c369-de7f-0a2d-c24d17f41a2b
  WebRTC IP: 10.38.38.219

삭제 결과:
  portal DELETE: HTTP 204, 두 인스턴스 모두
  Deployment/Service/ResourceClaim 잔여: 0
  두 GPU 상태: Available
```

이번 E2E에서 다른 GPU와 A100은 사용하지 않았다. 포털 제품 기능에는 특정 GPU allowlist를 넣지 않았으며, UI는 일반 GPU와 MIG를 클러스터 API에서 계속 자동 발견한다.

## 2. 보호한 기존 자원

다음 자원은 변경하거나 삭제하지 않았다.

```text
namespace oos-sim
  기존 isaac-ui
  기존 dt-sim-inyong
  기존 Service/ResourceClaim

외부 Nucleus
  10.38.38.32

기존 Secret
  omni-streaming/nucleus-auth
```

새 포털, Nucleus, E2E 인스턴스는 `omniverse` namespace에서만 관리했다.

## 3. 사용한 소스와 배포 revision

### 3.1 isaac-twinx

```text
repository: mj006648/isaac-twinx
commit: 47dcfee
message: fix: remove Nucleus IP hardcoding
tests: 38 passed
```

이 commit은 Time Travel extension의 과거 Nucleus asset URL을 제거하고 런타임 설정으로 바꾼다.

### 3.2 TwinX-Ops

```text
repository: SmartX-Team/TwinX-Ops
portal write/RBAC commit: 130411e
Isaac image update commit: 5c67a44
Argo application: isaac-twinx-preview
final state: Synced / Healthy
```

### 3.3 Isaac Sim image

```text
tag: 10.38.38.210/library/isaac-sim:6.0-netai-47dcfee
digest: 10.38.38.210/library/isaac-sim@sha256:c3a5b1b3402f3f2d6185fccee158023da59e99748ce096c33d5a2404fdea9bb7
size: 11004757876 bytes
```

배포 manifest는 mutable tag가 아니라 digest를 사용했다.

## 4. 포털을 실제 실행 모드로 바꾼 값

TwinX-Ops의 다음 raw app만 수정했다.

```text
argocd/omniverse/apps/isaac-twinx-preview/install.yaml
```

핵심 설정:

```text
WRITE_ENABLED=true
AUTH_ENABLED=false
ISAAC_SIM_IMAGE=<immutable digest>
OMNI_SERVER=omniverse://10.38.38.245/
OMNI_PROJECT_PATH=Projects/demonstration
NUCLEUS_SECRET_NAME=nucleus-twinx-client-auth
DRA_DEVICE_CLASS=gpu.nvidia.com
DRA_MIG_DEVICE_CLASS=mig.nvidia.com
```

Secret은 이름과 key만 참조했고 원문은 manifest, Git, 이 문서에 넣지 않았다.

namespace Role은 동적 인스턴스에 필요한 최소 mutation 권한만 추가했다.

```text
apps/deployments: get, list, create, delete, patch
core/services: get, list, create, delete
core/pods: get, list
resource.k8s.io/resourceclaims: get, list, create, delete
```

cluster inventory 권한은 Node, ResourceSlice, 모든 namespace의 ResourceClaim을 읽는 데만 사용한다.

## 5. GPU와 MIG 자동 발견 범위

포털은 preset에 GPU node/UUID 목록을 저장하지 않는다.

```text
core/v1 Nodes
resource.k8s.io/v1 ResourceSlices
resource.k8s.io/v1 ResourceClaims
```

위 API를 읽어 다음을 계산한다.

```text
node
GPU/MIG device name
GPU UUID 또는 MIG UUID
product/profile
Available/Allocated
WebRTC 호환 여부
현재 claim owner
```

일반 GPU가 있으면 `gpu.nvidia.com`, MIG device가 있으면 `mig.nvidia.com` DeviceClass를 사용한다. MIG가 없는 클러스터에서도 일반 GPU inventory와 launch는 정상 동작한다.

## 6. 동시 실행과 exact DRA 할당

포털 API로 두 인스턴스를 동시에 생성했다.

### 6.1 L40S index 7

```text
instance: twinx-l40s7-e2e
node: l40s
product: NVIDIA L40S
resource claim: isaac-twinx-l40s7-e2e-gpu
allocation: l40s/gpu-4/gpu.nvidia.com
UUID: GPU-ebac507e-176f-1b5a-eee2-d0fe94cd0874
Pod: Running / Ready / restart 0
stream Service: 10.38.38.180
```

### 6.2 sv4000-1 A6000

```text
instance: twinx-a6000-e2e
node: sv4000-1
product: NVIDIA RTX A6000
resource claim: isaac-twinx-a6000-e2e-gpu
allocation: sv4000-1/gpu-1/gpu.nvidia.com
UUID: GPU-83657c9e-c369-de7f-0a2d-c24d17f41a2b
Pod: Running / Ready / restart 0
stream Service: 10.38.38.219
```

두 Pod가 서로 다른 node와 정확한 DRA device에 배치되어 이기종 GPU 동시 실행을 확인했다.

## 7. Nucleus 실제 연결 검증

단순히 env와 TCP 포트만 확인하지 않았다. 각 Isaac Sim Pod 안에서 `omni.client`를 초기화하고 Secret env를 authentication callback으로 전달한 뒤 `OMNI_SERVER`에 `stat()`을 수행했다.

두 Pod의 결과:

```text
NUCLEUS_STAT_RESULT=Result.OK
NUCLEUS_ENTRY_PRESENT=True
```

추가 확인:

```text
Isaac Pod -> http://10.38.38.245:8080/: HTTP 200
servers JSON: NetAI Nucleus = omniverse://10.38.38.245
runtime config library root: omniverse://10.38.38.245/
runtime config server enabled: true
```

따라서 `10.38.38.245`는 단순 표시값이 아니라 실제 인증 가능한 Nucleus endpoint로 주입됐다.

## 8. Extension 포함과 활성화 경계

이미지에는 upstream commit을 pin한 9개 extension이 포함됐다.

```text
upstream: SmartX-Team/Omniverse
commit: f2606b43c437d1e3b70e16edb011fc3b237bb2e4

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

두 실행 Pod에서 확인한 결과:

```text
/isaac-sim/exts symlink: 9개
entrypoint Registered extension log: 9개
upstream pin: f2606b43c437d1e3b70e16edb011fc3b237bb2e4
Isaac Sim Full Streaming: 6.0.0-rc.59 시작
omni.kit.livestream.webrtc 시작
```

중요한 경계:

- 9개 extension은 이미지에 **포함되고 Kit 검색 경로에 등록**된다.
- 모든 extension을 자동 활성화하지는 않는다. 사용자가 앞서 정한 정책이다.
- 각 extension은 필요한 backend, asset, Isaac Sim 6.0 호환성을 확인한 뒤 Extension Manager에서 개별 활성화한다.
- 따라서 이번 결과는 9개 extension의 packaging/registration 성공 증거이며, 9개 기능 전체의 동작 성공을 의미하지 않는다.

## 9. 과거 MiniX/TwinX Nucleus IP 제거

초기 image 검사에서 Time Travel extension 설정에 다음 과거 주소가 남아 있는 것을 발견했다.

```text
omniverse://10.38.38.32/...
```

이 값은 `47dcfee`에서 제거했다.

```text
astronaut_usd 기본값: 빈 값
NETAI_TIMETRAVEL_ASTRONAUT_USD: 선택적 runtime env
상대 경로를 주면 OMNI_SERVER를 prefix로 사용
값이 없으면 auto_generate 비활성화
```

검증 범위:

```text
image source/generated extensions scan
runtime /opt/netai-extensions scan
금지 prefix:
  10.34.48.*
  10.38.38.32
결과: match 없음
```

공통 image에는 MiniX/TwinX Nucleus IP를 bake하지 않는다. 대상 Nucleus는 cluster preset의 `OMNI_SERVER`와 Secret 참조로만 결정한다.

## 10. 삭제와 GPU 반환

검증 후 포털 API로 두 E2E 인스턴스만 삭제했다.

```text
twinx-l40s7-e2e DELETE: HTTP 204
twinx-a6000-e2e DELETE: HTTP 204
```

정리 결과:

```text
E2E Deployment/Service/ResourceClaim remaining: 0
L40S UUID ebac...: Available
A6000 UUID 8365...: Available
```

기존 `oos-sim` 리소스와 외부 Nucleus는 삭제 경로의 대상이 아니었다.

## 11. 이번 E2E가 증명한 것과 남은 것

### 증명 완료

- 실제 TwinX Kubernetes/DRA inventory 자동 조회
- 일반 GPU와 MIG를 함께 표현할 수 있는 source/config
- L40S와 A6000 exact selection
- 두 이기종 GPU에서 동시 Isaac Sim 실행
- 인스턴스별 LoadBalancer Stream IP 할당
- Isaac Sim 6.0 WebRTC 프로세스 시작
- 신규 Nucleus에 실제 인증·stat 성공
- 9개 extension image 포함과 Kit 검색 경로 등록
- 과거 MiniX/외부 Nucleus IP가 새 image/runtime에 없음
- 포털 Delete와 ResourceClaim/GPU 반환

### 별도 확인 또는 후속 작업

- TwinX의 두 Stream IP에서 GUI 영상·입력 수동 확인
- 각 extension의 Isaac Sim 6.0 개별 활성화/기능 시험
- portal 인증 연동
- 실제 `eecs-k8s` 공통 chart와 GPU cluster preset 반영
- 운영 Secret을 ExternalSecret/OpenBao 흐름으로 전환

## 12. SmartX 이관에 반영할 값의 경계

공통 `eecs-k8s` chart:

```text
Deployment/Service/RBAC template
안전한 기본값: WRITE_ENABLED=false, Service=ClusterIP
DRA v1 normal/MIG schema
Nucleus endpoint와 Secret reference schema
GPU inventory 자동 조회 로직을 담은 portal image reference
```

GPU cluster preset:

```text
portal/Isaac Sim immutable image digest
WRITE_ENABLED와 auth 정책
portal LoadBalancer 설정
DRA driver와 normal/MIG DeviceClass
OMNI_SERVER와 OMNI_PROJECT_PATH
Nucleus Secret name/key
WebRTC incompatible product 정책
```

어느 쪽에도 넣지 않는 값:

```text
Secret 원문
GPU node/UUID 고정 목록
현재 free/allocated 수
사용자별 instance/Stream IP
MiniX 또는 TwinX의 과거 Nucleus IP
```

실제 파일별 이관 코드는 [`SMARTX_MIGRATION_PLAN.md`](./SMARTX_MIGRATION_PLAN.md)를 기준으로 한다.

## 13. 2026-07-16 포털 표시와 WebRTC 준비 상태 보정

실사용 중 확인된 혼동을 줄이기 위해 포털 source와 TwinX 배포를 갱신했다.

```text
isaac-twinx: 1e94ca4 feat: clarify GPU launch status
TwinX-Ops:   c04b787 feat: update TwinX portal
portal image digest: sha256:67fc3848cab38bb3503b71bdfc08b1d64e4702e9b95bbdd043287cbe1f0e9254
source tests: 42 passed
Argo CD: Synced / Healthy
Deployment: 1/1 Ready
```

GPU 표시는 ResourceSlice의 DRA 내부 device 이름이 아니라 실제 `index`와 `pcieBusID`를 사용한다.
메모리는 provider가 `46068Mi`, `49140Mi`, `24Gi`, `4864Mi`처럼 서로 다른 단위로 제공해도
포털에서 binary GiB로 정규화한다.

```text
l40s · GPU #7 · NVIDIA L40S · 45 GiB · e1:00.0
```

Kubernetes의 Pod Ready는 Isaac Sim WebRTC 준비 완료를 뜻하지 않는다. RTX, extension, Nucleus,
StreamSDK 초기화에 추가 시간이 필요하므로 상태를 다음처럼 구분했다.

```text
Pending -> Initializing -> Running
STREAM_INITIALIZATION_SECONDS=120
WebRTC is starting. Please wait 1–2 minutes.
```

포털은 15초마다 자동 갱신한다. L40S 인스턴스는 초기 접속 때 실패했지만 1~2분 대기 후 같은 Stream
IP에서 WebRTC 영상 연결이 정상 동작했다. 따라서 이 사례의 공통 원인은 DRA/GPU/LB 실패가 아니라
Pod Ready보다 늦은 WebRTC 준비 시점이었다. A6000의 구형 driver 호환성은 이 결과와 별도 검증 대상으로
남긴다.

배포 직후 브라우저가 이전 `index.html`/`app.js`를 표시한 사례가 있었고, 브라우저 캐시 초기화 후 새
GPU index, PCI, GiB, Initializing UI가 정상 표시됐다.

## 14. Isaac Sim이 사용할 Nucleus 서버 교체

### 14.1 변경 범위

Nucleus 주소는 Isaac Sim image에 bake하지 않는다. 공통 source와 image는 런타임 `OMNI_SERVER`를
읽으므로 Nucleus 서버만 바꾸는 경우 image rebuild는 필요 없다.

현재 TwinX raw app에서 주 변경 파일은 하나다.

```text
SmartX-Team/TwinX-Ops
argocd/omniverse/apps/isaac-twinx-preview/install.yaml
```

현재 runtime 설정의 역할:

```text
OMNI_SERVER=omniverse://10.38.38.245/       Nucleus endpoint
OMNI_PROJECT_PATH=Projects/demonstration    extension 기본 상대 경로
NUCLEUS_SECRET_NAME=nucleus-twinx-client-auth
NUCLEUS_USER_KEY=OMNI_USER
NUCLEUS_PASSWORD_KEY=OMNI_PASS
```

새 Nucleus가 기존 계정과 동일한 프로젝트 경로를 사용하면 `OMNI_SERVER`만 교체한다.

```yaml
- name: OMNI_SERVER
  value: "omniverse://<new-nucleus>/"
```

다른 프로젝트 root를 사용하면 `OMNI_PROJECT_PATH`도 바꾼다. 계정이 다르면 Secret 원문을 Git에
추가하지 않고 기존 Secret 값을 안전하게 갱신하거나, 새 Secret을 만든 뒤 이름/key 참조만 manifest에서
바꾼다.

### 14.2 source에서 값을 소비하는 위치

다음 코드는 수정 대상이 아니라 preset 값이 전달되는 경로다.

```text
src/isaac_twinx/config.py
  OMNI_SERVER, OMNI_PROJECT_PATH, Secret 참조를 읽음

src/isaac_twinx/resources.py
  새 Isaac Deployment에 env와 mounted_servers/NetAI Nucleus 실행 인자를 생성

images/isaac-sim/entrypoint.sh
images/isaac-sim/overrides/gist.*.extension.py
  하드코딩 주소 없이 OMNI_SERVER와 OMNI_PROJECT_PATH 사용
```

### 14.3 적용 시 주의

포털 Deployment를 Argo CD로 rollout한 뒤 생성한 **새 인스턴스**부터 변경된 Nucleus를 사용한다.
이미 실행 중인 Isaac Deployment에는 이전 env/실행 인자가 남으므로 포털에서 삭제 후 다시 생성하거나,
해당 Deployment를 명시적으로 갱신·재시작해야 한다. Secret의 env 값도 Pod 시작 시 읽으므로 credential을
바꾼 인스턴스는 재생성이 필요하다.

검증할 항목:

```text
portal Deployment의 OMNI_SERVER가 새 URI인지 확인
새 Isaac Deployment args의 mounted_servers/NetAI Nucleus 확인
새 Isaac Pod env의 OMNI_SERVER 확인
Secret 값은 출력하지 않고 Secret name/key 참조만 확인
Pod 내부 omni.client stat(OMNI_SERVER) == Result.OK
Content Browser > Omniverse > NetAI Nucleus 자동 등록 확인
```

### 14.4 SmartX 이관 후 변경 위치

`eecs-k8s` 공통 chart에는 Nucleus 값을 하드코딩하지 않고 schema와 env mapping만 둔다. 실제 서버는
GPU cluster preset에서 정한다.

```text
eecs-k8s/apps/omniverse-isaac-saas/values.yaml
  nucleus.server의 안전한 공통 기본값/schema

eecs-k8s/apps/omniverse-isaac-saas/templates/deployment.yaml
  nucleus.server -> OMNI_SERVER 변환

<cluster>-k8s/patches/omniverse-isaac-saas/values.yaml
  nucleus.server
  nucleus.projectPath
  nucleus.passwordSecret.name/key
```

따라서 이관 후 서버 교체도 cluster preset의 `nucleus.server` 한 곳이 기본 변경점이다. 공통 chart나
Isaac Sim image를 서버마다 다시 만들지 않는다.

