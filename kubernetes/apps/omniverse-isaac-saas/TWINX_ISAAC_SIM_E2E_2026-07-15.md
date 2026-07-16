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

