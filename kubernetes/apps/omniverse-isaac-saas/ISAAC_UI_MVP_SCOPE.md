# Isaac UI MVP 범위와 원본 대비 변경 설계

> 작성일: 2026-07-13  
> 대상 원본: `SmartX-Team/Omniverse/isaac-saas`  
> 적용 대상: `eecs-k8s` 공통 app catalog + `c-k8s`/`twinx-k8s` cluster preset  
> 문서 원칙: Secret, 비밀번호, API key 원문은 기록하지 않는다.  
> 우선순위: 이 문서는 현재 합의한 MVP 구현 범위의 기준 문서다. 기존 `SMARTX_MIGRATION_PLAN.md`와 충돌하면 이 문서를 우선한다.

---

## 0. 결론

원본 `isaac-saas`를 그대로 복제하지 않는다.

우리에게 필요한 것은 다음 기능이다.

```text
1. Kubernetes가 인식한 GPU를 노드/제품/UUID 단위로 보여준다.
2. 사용자가 자동, GPU 제품, 특정 노드, 특정 GPU 중 하나를 선택한다.
3. 선택 결과를 DRA ResourceClaim으로 예약한다.
4. 예약한 GPU 1개로 Isaac Sim Pod 1개를 실행한다.
5. 인스턴스마다 LoadBalancer IP를 할당한다.
6. 사용자는 해당 IP로 Isaac Sim WebRTC에 접속한다.
7. Isaac Sim은 기존 Nucleus에 런타임으로 연결한다.
8. 사용자가 인스턴스를 삭제하면 Deployment, Service, ResourceClaimTemplate을 정리한다.
```

원본의 모니터링, scene 분석, code-server, workspace, registry image 선택, GPU ban 관리 기능은 1차 MVP에서 제외한다.

GPU가 여러 노드에 이기종으로 섞여 있고 사용자가 특정 GPU까지 선택해야 하므로, 최종 MVP에서는 DRA가 부가 기능이 아니라 핵심 기능이다.

단, 이미지와 WebRTC 경로만 먼저 검증하는 단일 인스턴스 smoke test에서는 `nvidia.com/gpu: 1` 방식을 임시 fallback으로 사용할 수 있다.

---

## 1. 사용자가 원하는 최종 동작

### 1.1 사용자 흐름

```text
사용자
  -> Isaac UI 접속
  -> 사용 가능한 GPU 목록 확인
  -> 노드와 GPU 선택
  -> 인스턴스 이름 입력
  -> Create

Isaac UI
  -> 선택한 GPU가 현재 DRA inventory에 존재하는지 검증
  -> ResourceClaimTemplate 생성
  -> 인스턴스별 LoadBalancer Service 생성
  -> 외부 IP 확인
  -> Isaac Sim Deployment 생성
  -> 상태와 Stream IP 반환

사용자
  -> Isaac Sim WebRTC Streaming Client 실행
  -> Stream IP 입력
  -> Isaac Sim 사용

사용 종료
  -> Delete
  -> Deployment, Service, ResourceClaimTemplate 정리
```

### 1.2 성공 기준

- GPU 노드, GPU 제품명, GPU UUID, 사용 가능 여부를 UI에서 확인할 수 있다.
- 같은 노드에 서로 다른 GPU가 있어도 특정 GPU를 선택할 수 있다.
- 선택한 GPU가 다른 인스턴스에 중복 할당되지 않는다.
- 인스턴스 하나는 GPU 하나만 사용한다.
- 인스턴스별 LoadBalancer IP가 발급된다.
- WebRTC 클라이언트가 인스턴스에 연결된다.
- Isaac Sim에서 Nucleus asset과 USD stage를 열 수 있다.
- 삭제 후 GPU와 LoadBalancer IP가 다시 사용 가능해진다.

---

## 2. 원본 `isaac-ui`는 현재 어떻게 되어 있는가

### 2.0 원본 코드 위치

| 경로 | 역할 |
| --- | --- |
| `ui/app/web.py` | FastAPI endpoint와 정적 UI 제공 |
| `ui/app/instances.py` | 인스턴스 생성, 조회, 삭제 orchestration |
| `ui/app/resources.py` | Deployment, Service, ResourceClaimTemplate, PVC spec 생성 |
| `ui/app/gpu.py` | GPU node/product/사용량 조회 |
| `ui/app/policy.py` | node/product/UUID ban 정책 |
| `ui/app/metrics.py` | Prometheus/DCGM metric 조회 |
| `ui/app/scenes.py` | scene load history 저장과 집계 |
| `ui/app/registry.py` | Harbor/Docker Hub image catalog 조회 |
| `ui/app/static/` | 인스턴스, GPU, ban, metrics, scene 화면 |
| `deploy/k8s/` | 원본 isaac-ui Deployment, Service, RBAC |
| `isaac-sim-image/Dockerfile` | Isaac Sim 6.0 custom image build |
| `isaac-sim-image/entrypoint.sh` | Extension, Nucleus, stage, WebRTC runtime 설정 |

### 2.1 원본 화면 기능

원본 UI에는 다음 기능이 함께 들어 있다.

| 기능 | 원본 상태 |
| --- | --- |
| 인스턴스 생성 | 있음 |
| 인스턴스 목록/상태 | 있음 |
| 인스턴스 삭제 | 있음 |
| Stream IP 표시 | 있음 |
| GPU 노드/제품/사용량 표시 | 있음 |
| 사용자가 생성 시 특정 GPU 선택 | 없음 |
| GPU node/product/UUID ban | 있음 |
| DRA UUID/product 제외 selector | 있음 |
| Registry image 선택 | 있음 |
| code-server | 있음, 기본 활성화 |
| workspace PVC | 선택 기능 |
| OpenTelemetry metrics | 있음, 기본 활성화 |
| node-exporter netstat metrics | 있음, 기본 활성화 |
| Prometheus dashboard | 있음 |
| scene load history | 있음, 기본 활성화 |
| Redis/ConfigMap policy store | 있음 |

화면에는 `New instance`, `Refresh`, `Prune orphans`, `GPU bans`, `Metrics`, `Scenes`가 모두 노출된다.

### 2.2 원본 Create 요청의 한계

원본 `CreateReq`는 다음 값만 받는다.

```text
name
owner
description
image
```

즉 원본은 사용자가 생성 화면에서 `node`, `GPU product`, `GPU UUID`를 직접 선택하지 않는다.

원본의 `NODES` 값은 전체 허용 노드 목록이고, GPU ban은 특정 장치를 제외하는 기능이다. 사용자가 특정 GPU를 긍정적으로 선택하는 기능과는 다르다.

### 2.3 원본 생성 흐름

```text
POST /api/create
  -> 이름과 image 검증
  -> ban 정책으로 사용 가능한 노드 계산
  -> DRA enabled이면 ResourceClaimTemplate 생성
  -> code-server persistence enabled이면 PVC 생성
  -> LoadBalancer Service 생성
  -> 최대 15초 동안 외부 IP 확인
  -> Isaac Sim Deployment 생성
```

원본 ResourceClaimTemplate은 주로 금지 UUID와 금지 product를 제외하기 위한 CEL selector다.

우리 구현은 이를 바꿔서 사용자가 선택한 UUID 또는 product를 포함하는 positive selector를 생성해야 한다.

### 2.4 원본 인스턴스 Service

원본은 인스턴스별로 다음 Service를 만든다.

```text
type: LoadBalancer
TCP 8211
TCP 49100
UDP 47998
externalTrafficPolicy: Local
```

Native WebRTC 연결의 핵심 포트는 다음이다.

```text
49100/TCP  signaling
47998/UDP  media
```

`8211/TCP`는 기존 브라우저 WebRTC endpoint와의 호환 여부를 이미지 버전별로 확인한 후 선택적으로 유지한다.

### 2.5 원본 Kubernetes 권한

원본 RBAC에는 다음 권한이 포함된다.

- Deployments 생성/조회/삭제/patch
- Services 생성/조회/삭제
- Pods와 Events 조회
- ConfigMaps 생성/patch
- PVC 생성/삭제
- ResourceClaimTemplate 생성/삭제
- cluster-wide Nodes, Pods, ResourceClaims, ResourceSlices 조회

이 중 ConfigMap policy store, PVC workspace, cluster-wide Pod 사용량 집계는 MVP에서 제거할 수 있다.

---

## 3. 원본 `isaac-sim-image`는 현재 어떻게 되어 있는가

### 3.1 이미지에 들어 있는 것

원본 Dockerfile은 다음 이미지에서 시작한다.

```dockerfile
FROM nvcr.io/nvidia/isaac-sim:6.0.0
```

그 위에 다음 내용을 추가한다.

- ROS 2 Jazzy 기본 환경
- Git, Xvfb 등 실행 도구
- 선택적 외부 ROS workspace build
- Omniverse Extension source clone 경로
- `wander.py`, `set_4k.py`, `stage_report.py`
- Nucleus와 Extension을 설정하는 custom entrypoint
- Isaac Sim 5.1/6.0 WebRTC launcher 호환 처리

GPU 종류마다 다른 이미지를 만드는 구조는 아니다. 동일한 Isaac Sim 이미지를 여러 GPU 노드에서 사용하고, GPU 할당은 Kubernetes와 DRA가 담당한다.

### 3.2 Nucleus는 이미지 안에 포함되지 않는다

Nucleus server는 별도 Kubernetes StatefulSet/Service다.

Isaac Sim 이미지에는 Nucleus server가 들어 있지 않다. 이미지의 entrypoint가 실행 시 다음 환경변수를 사용해 Nucleus client 설정을 만든다.

```text
OMNI_SERVER
OMNI_USER
OMNI_PASS
```

entrypoint는 런타임에 다음 작업을 수행한다.

1. 사용자 home 아래에 `omniverse.toml` 생성
2. Nucleus server와 계정 설정
3. Isaac asset root를 Nucleus 경로로 지정
4. 필요하면 시작 USD stage와 camera를 자동으로 연다.

따라서 Nucleus endpoint와 credential 때문에 GPU별 이미지를 새로 만들 필요는 없다.

credential은 Isaac Sim Deployment의 Secret reference로 런타임 주입한다.

### 3.3 Extension은 두 방식으로 공급할 수 있다

#### Build-time 포함

현재 `build.env`의 `EXT_REPO_URLS`를 Docker build argument로 넘긴다.

Dockerfile은 해당 repo를 다음 경로 아래에 clone한다.

```text
/opt/oos_omniverse_extensions
```

컨테이너가 시작되면 entrypoint가 `extension.toml`을 검색하고 `/isaac-sim/exts` 아래에 symlink를 만든다.

#### Runtime mount

이미지에 Extension을 넣지 않고 같은 경로에 volume을 mount할 수도 있다.

원본 entrypoint는 해당 경로가 Git repo이면 시작 시 `git pull`도 시도한다.

### 3.4 우리 운영 이미지 정책

운영에서는 시작할 때마다 Git pull하지 않는다.

권장 방식:

```text
필요한 Extension만 선정
  -> Git commit 또는 tag 고정
  -> Docker build 시 이미지에 포함
  -> 내부 Harbor에 immutable tag 또는 digest로 push
  -> 모든 GPU 노드에서 같은 digest 사용
```

개발 중 빠른 Extension 수정이 필요한 경우에만 PVC 또는 read-only volume mount 방식을 사용한다.

모든 Extension을 자동으로 등록하지 않고 allowlist 또는 `EXT_PREFIX`로 필요한 Extension만 활성화한다.

---

## 4. 원본에서 유지할 것

| 항목 | 유지 이유 | 우리 구현 |
| --- | --- | --- |
| FastAPI 기반 self-service controller | 사용자 요청을 Kubernetes 리소스로 변환하기 쉬움 | 최소 API만 유지 |
| in-cluster Kubernetes client | 별도 kubeconfig 없이 ServiceAccount 사용 | 유지 |
| Deployment 기반 인스턴스 | replica 1과 GPU 1개 모델에 적합 | 유지 |
| 인스턴스별 LoadBalancer Service | 사용자별 Stream IP 분리 | 유지 |
| ResourceClaimTemplate | 특정 GPU 선택과 중복 방지 | 핵심 기능으로 유지 |
| ResourceSlice 조회 | GPU node/product/UUID inventory 제공 | 유지 |
| 인스턴스 list/detail/delete | 기본 운영에 필요 | 단순화해 유지 |
| LoadBalancer IP를 WebRTC public address에 반영 | 외부 접속에 필요 | 유지 |
| Isaac Sim custom entrypoint | Nucleus, Extension, WebRTC 설정 | 정리 후 유지 |
| Nucleus runtime injection | 클러스터별 endpoint/credential 분리 | Secret reference로 유지 |

---

## 5. 원본에서 변경할 것

### 5.1 GPU 선택 모델

원본:

```text
허용 노드 목록 + ban으로 제외 + scheduler가 자동 선택
```

우리 구현:

```text
auto
node
product
device UUID
```

UI는 다음 형태를 제공한다.

```text
Selection mode: [Auto] [Product] [Node] [Exact GPU]

Node        Product       Device UUID       Status
c-gpu-01    L40S          GPU-...           Available
c-gpu-01    L40S          GPU-...           Allocated
c-gpu-02    RTX A6000     GPU-...           Available
```

UI에 보이는 상태는 정보 제공용이다. 실제 중복 할당 방지는 Kubernetes scheduler와 DRA allocation 결과가 담당한다.

### 5.2 Create API

원본:

```json
{
  "name": "demo",
  "owner": "user",
  "description": "",
  "image": ""
}
```

우리 MVP 예시:

```json
{
  "name": "demo",
  "selectionMode": "device",
  "node": "c-gpu-01",
  "device": "<selected-device-id>"
}
```

MVP에서는 사용자가 임의 image를 입력하거나 고르지 않는다. instance image는 cluster preset에서 고정한다.

### 5.3 DRA selector

원본은 ban UUID와 product를 제외한다.

우리 구현은 selection mode에 따라 다음 조건을 만든다.

```text
auto:
  DeviceClass에 맞는 사용 가능한 GPU 1개

product:
  선택한 productName과 일치하는 GPU 1개

node:
  Pod required nodeAffinity를 선택한 node로 제한하고 DRA로 GPU 1개 요청

device:
  선택한 device UUID와 일치하는 GPU 1개
```

`node` 모드에서 node 이름을 임의의 CEL device attribute로 가정하지 않는다. Pod의 required nodeAffinity와 DRA claim을 함께 사용한다. `device` 모드에서는 선택 UUID가 해당 node의 ResourceSlice에 속하는지 먼저 검증한다.

실제 CEL attribute key는 대상 클러스터의 NVIDIA DRA driver가 생성한 `ResourceSlice`를 읽고 확정한다. repo에 임의 attribute schema를 하드코딩하지 않는다.

### 5.4 이미지 선택

원본은 Harbor/Docker Hub catalog를 조회해 Create modal에서 image를 선택할 수 있다.

우리 MVP는 다음 하나를 preset에서 고정한다.

```text
instance.image.repository
instance.image.tag 또는 digest
```

이미지 종류가 추가로 필요해지면 검증된 profile 목록만 제공한다. 자유 입력은 허용하지 않는다.

### 5.5 Nucleus credential

원본에는 코드 또는 환경변수 기본값에 Nucleus 관련 값이 섞인 부분이 있다.

우리 구현은 다음만 chart/preset에 둔다.

```text
nucleus.server
nucleus.credentialSecret.name
nucleus.credentialSecret.userKey
nucleus.credentialSecret.passwordKey
```

생성되는 Isaac Sim Deployment는 `valueFrom.secretKeyRef`를 직접 참조한다. `isaac-ui`가 비밀번호 원문을 읽거나 응답에 포함하지 않는다.

### 5.6 Extension 공급

원본은 build 시 clone한 뒤 컨테이너 시작 시 Git pull을 다시 수행할 수 있다.

우리 운영 방식은 다음으로 바꾼다.

- build 시 commit/tag 고정
- runtime Git pull 비활성화
- 필요한 Extension만 allowlist
- image tag보다 digest pin 권장
- Extension 변경은 새 이미지 build와 rollout으로 반영

---

## 6. MVP에서 제거할 것

| 제거 대상 | 원본 역할 | 제거 이유 |
| --- | --- | --- |
| Metrics dashboard | 인스턴스 네트워크/GPU metric 표시 | 목표 기능과 무관, Prometheus 의존성 증가 |
| OpenTelemetry sidecar | 인스턴스 network metric 수집 | 인스턴스 시작 실패 지점과 이미지 수 증가 |
| node-exporter sidecar | TCP/UDP/socket metric 보강 | 1차 WebRTC 기능에 불필요 |
| Scene history | USD stage와 GPU 부하 이력 | 분석 기능이며 생성/접속과 무관 |
| `stage_report.py` 연동 | scene event 전송 | scene history 제거에 따라 비활성화 |
| code-server sidecar | 브라우저에서 Extension 편집 | 사용자 목표에 없음 |
| workspace PVC | code-server 편집 내용 보존 | code-server 제거에 따라 불필요 |
| Registry catalog | 생성 시 image 선택 | MVP는 검증된 image 하나 사용 |
| Harbor API credential | private catalog 조회 | Registry catalog 제거에 따라 불필요 |
| GPU ban UI | node/product/UUID 제외 정책 | 사용자가 직접 원하는 GPU를 선택하는 모델로 변경 |
| Redis policy store | GPU ban 저장 | ban 기능 제거에 따라 불필요 |
| ConfigMap policy store | GPU ban 저장 | ban 기능 제거에 따라 불필요 |
| ban applied 상태 | node-side exclusion 추적 | DRA claim 선택 결과로 대체 |
| Metrics/Scenes frontend modal | 부가 UI | 화면 단순화 |

`Prune orphans`는 사용자 화면에서 제거한다. 필요하면 관리자 전용 maintenance API 또는 정기 controller reconcile로 대체한다.

원본 Dockerfile의 GUI VSCode package 설치도 사용하지 않으면 삭제 후보이다. 이는 code-server sidecar와 별개이며 이미지 크기만 증가시킬 수 있다.

---

## 7. 나중에 추가할 수 있는 기능

다음 기능은 폐기하는 것이 아니라 MVP 이후 요구가 생길 때 별도 feature로 추가한다.

- GPU/네트워크 모니터링
- DCGM/Prometheus 연동
- Scene별 부하 분석
- Extension 개발용 code-server
- 사용자 workspace PVC
- 여러 Isaac Sim image profile
- GPU maintenance/ban 정책
- 사용자 quota와 최대 실행 시간
- 자동 idle shutdown
- 사용자 인증과 프로젝트별 권한
- 예약/대기열

부가 기능은 Isaac Sim 인스턴스 생성 경로가 안정화된 뒤 추가한다.

---

## 8. 우리 GPU 선택 설계

### 8.1 Inventory source

GPU inventory의 기준은 다음이다.

```text
DeviceClass
ResourceSlice
ResourceClaim allocation status
Node metadata
```

`nvidia-smi`를 UI Pod가 SSH로 실행하거나 각 노드에서 직접 수집하지 않는다.

WebRTC 호환 여부는 검증된 GPU capability 정책으로 계산한다. 원본은 NVENC가 없는 GPU 제품군을 WebRTC 대상에서 제외하므로, 우리 클러스터의 실제 GPU 제품별 지원 여부를 먼저 검증하고 allow/deny 정책을 정한다.

UI API는 최소 다음 정보를 반환한다.

```json
{
  "node": "c-gpu-01",
  "device": "<driver-device-id>",
  "uuid": "<gpu-uuid>",
  "product": "L40S",
  "allocatable": true,
  "compatibleWithWebRTC": true
}
```

### 8.2 선택 모드

| 모드 | 의미 | DRA 필요 여부 |
| --- | --- | --- |
| `auto` | 호환 가능한 GPU 아무거나 1개 | 최종 구현은 DRA 사용 |
| `product` | 특정 제품군 GPU 아무거나 1개 | 필요 |
| `node` | 특정 노드의 호환 GPU 아무거나 1개 | 혼합 GPU 노드에서는 필요 |
| `device` | 특정 GPU UUID 1개 | 필수 |

### 8.3 `nvidia.com/gpu: 1` fallback 한계

다음 구성은 노드 안에서 사용 가능한 GPU 하나를 할당한다.

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

하지만 같은 노드에 L40S와 A100처럼 여러 종류가 섞여 있으면 정확한 UUID를 선택할 수 없다.

따라서 fallback은 다음 용도로만 사용한다.

- 이미지 pull 확인
- NVIDIA runtime 확인
- Nucleus 연결 확인
- WebRTC 포트와 LoadBalancer 확인

최종 사용자 선택 기능은 DRA로 검증한다.

### 8.4 할당 경쟁 처리

두 사용자가 같은 GPU를 동시에 선택할 수 있다.

UI의 `Available` 표시는 실시간 절대 보장이 아니다. 생성 요청 시 DRA allocation이 최종 판정을 한다.

할당 실패 시 UI는 다음처럼 명확하게 응답해야 한다.

```text
선택한 GPU가 이미 할당되었거나 현재 사용할 수 없습니다.
GPU 목록을 새로고침하고 다른 GPU를 선택하십시오.
```

UI가 자체 DB lock만으로 GPU를 예약하지 않는다.

---

## 9. Isaac Sim Pod 설계

### 9.1 기본 구조

```text
Deployment replicas: 1
  Pod
    isaac-sim container 1개
    DRA claim 1개
    GPU 1개
    /dev/shm emptyDir
```

MVP에서는 sidecar를 두지 않는다.

### 9.2 필수 환경변수

일반 값:

```text
ACCEPT_EULA
PRIVACY_CONSENT
NVIDIA_DRIVER_CAPABILITIES
OMNI_SERVER
START_WEBRTC
ISAACSIM_HOST 또는 public endpoint argument
```

Secret reference:

```text
OMNI_USER
OMNI_PASS
```

선택 값:

```text
STARTUP_USD_STAGE
STARTUP_CAMERA_PATH
EXT_PREFIX
```

### 9.3 Volume

MVP 필수:

```text
/dev/shm -> memory emptyDir
```

초기에는 사용자 workspace PVC를 만들지 않는다.

Isaac Sim cache persistence는 기능 검증 후 별도로 결정한다. 대용량 image startup 시간에 영향이 크면 cache PVC 또는 node-local cache를 검토한다.

### 9.4 Image pull

```text
우리 Harbor
  -> omniverse/isaac-sim:<immutable-tag>
```

image pull credential은 Pod의 `imagePullSecrets`로 참조한다.

---

## 10. WebRTC와 LoadBalancer 설계

### 10.1 인스턴스별 Service

```text
dt-sim-<name>-stream
type: LoadBalancer
```

필수 포트:

```text
49100/TCP
47998/UDP
```

선택 포트:

```text
8211/TCP
```

### 10.2 외부 IP 반영

권장 흐름:

```text
1. Service 생성
2. LoadBalancer IP 할당 대기
3. IP를 Isaac Sim WebRTC public endpoint에 반영
4. Deployment 생성
```

IP 할당이 늦으면 Deployment를 먼저 생성하고 controller가 이후 patch할 수 있다. 어떤 방식을 사용하더라도 최종 container argument와 Service external IP가 일치해야 한다.

### 10.3 IP pool 용량

인스턴스별 LoadBalancer Service를 사용하면 동시 인스턴스 수만큼 IP가 필요하다.

```text
동시 Isaac Sim 10개
  -> LoadBalancer IP 최대 10개 필요
```

구현 전 C/TwinX MetalLB 또는 Cilium LB IP pool의 가용 주소 수를 확인한다.

### 10.4 보안

Isaac Sim WebRTC endpoint는 인증과 암호화가 없는 형태로 직접 노출될 수 있다.

최소한 다음 중 하나가 필요하다.

- 내부망/VPN 전용 IP pool
- 사용자 source CIDR 제한
- 방화벽 정책
- 인증/TLS가 있는 별도 streaming gateway

기능 smoke test와 운영 공개를 구분한다.

---

## 11. 최소 `isaac-ui` API

### 11.1 유지할 API

```text
GET    /healthz
GET    /api/gpus
GET    /api/instances
GET    /api/instances/{name}
POST   /api/instances
DELETE /api/instances/{name}
```

### 11.2 제거할 API

```text
/api/metrics*
/api/scenes
/api/stage-report
/api/images
/api/bans
/api/ban
/api/unban
/api/ban-applied
```

### 11.3 instance 상태

최소 표시 항목:

```text
name
phase
ready
node
GPU product
GPU UUID
Stream IP
createdAt
error/message
```

---

## 12. 최소 RBAC

### 12.1 Namespace Role

```text
deployments: get, list, create, delete, patch
services: get, list, create, delete
pods: get, list
events: get, list
resourceclaimtemplates: get, list, create, delete
resourceclaims: get, list
```

### 12.2 ClusterRole read-only

```text
nodes: get, list
deviceclasses: get, list
resourceslices: get, list
```

### 12.3 제거할 권한

```text
configmaps create/patch
persistentvolumeclaims create/delete
cluster-wide pods list
secrets get/list
```

Isaac UI는 Secret 이름과 key 이름만 알고 생성하는 Deployment에 `secretKeyRef`를 넣는다. Secret 원문 조회 권한은 부여하지 않는다.

---

## 13. SmartX 레포 반영 구조

### 13.1 `eecs-k8s`

공통 chart:

```text
apps/omniverse-isaac-saas/
├── Chart.yaml
├── manifest.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl
    ├── serviceaccount.yaml
    ├── role.yaml
    ├── rolebinding.yaml
    ├── clusterrole.yaml
    ├── clusterrolebinding.yaml
    ├── deployment.yaml
    └── service.yaml
```

수정:

```text
apps/template/features.yaml
values.yaml
```

`eecs-k8s`에는 다음 값을 넣지 않는다.

- 실제 노드명
- GPU UUID
- Nucleus credential
- LoadBalancer 고정 IP
- Harbor credential
- C/TwinX 전용 endpoint

### 13.2 Feature graph

목표 feature:

```yaml
org.ulagbulag.io/omniverse/isaac-saas:
  requires:
    - org.ulagbulag.io/omniverse/nucleus
    - nvidia.com/gpu
    - nvidia.com/gpu/dynamic-resource-allocation
    - org.ulagbulag.io/registry/container/harbor
```

정확한 feature 이름은 현재 `eecs-k8s/apps/template/features.yaml`의 NVIDIA DRA naming과 맞춘다.

### 13.3 `c-k8s` 또는 `twinx-k8s`

```text
values.yaml
patches/omniverse-isaac-saas/values.yaml
```

preset에 둘 값:

```yaml
ui:
  image:
    repository: <our-harbor>/omniverse/isaac-ui
    tag: <tag>
  service:
    type: LoadBalancer

instance:
  image:
    repository: <our-harbor>/omniverse/isaac-sim
    tag: <tag>
  allowedNodes: []
  dra:
    enabled: true
    apiVersion: resource.k8s.io/v1
    driver: gpu.nvidia.com
    deviceClass: gpu.nvidia.com

nucleus:
  server: omniverse://<nucleus-endpoint>/
  credentialSecret:
    name: nucleus-cred
    userKey: OMNI_USER
    passwordKey: OMNI_PASS

streaming:
  serviceType: LoadBalancer
  ports:
    signal: 49100
    media: 47998
```

위 값은 예시 schema이며 실제 chart 구현 시 기존 `eecs-k8s` values 관례에 맞춘다.

### 13.4 `tower-k8s`

Tower는 Argo CD control plane 역할만 한다.

Isaac UI 또는 사용자별 `dt-sim-*` manifest를 `tower-k8s/apps`에 중복 추가하지 않는다.

---

## 14. 이미지 build 결정

### 14.1 이미지 종류

최소 두 이미지가 필요하다.

```text
isaac-ui
isaac-sim
```

MVP에서 필요하지 않은 이미지:

```text
code-server
otel-collector-contrib
node-exporter
```

### 14.2 Isaac Sim image build 기준

다음 조건이면 custom image를 build한다.

- 우리 Extension이 필요함
- ROS 2 Jazzy package가 필요함
- custom entrypoint가 필요함
- 시작 stage/camera 자동화가 필요함
- 내부 Harbor에서 고정된 image를 제공해야 함

Nucleus endpoint와 credential은 build argument로 넣지 않는다.

### 14.3 Extension pinning

다음과 같이 기록 가능한 version을 사용한다.

```text
base image digest
extension repository URL
extension commit SHA
image build commit SHA
result image digest
```

`latest`와 startup `git pull`에 의존하지 않는다.

---

## 15. 구현 순서

### Phase 0 — 클러스터 GPU/DRA inventory

```bash
kubectl api-resources | grep resource.k8s.io
kubectl get deviceclass
kubectl get resourceslices
kubectl get nodes -o wide
```

확인할 것:

- Kubernetes version과 DRA API version
- NVIDIA DRA driver 설치 여부
- DeviceClass 이름
- ResourceSlice의 node/device/UUID/product attribute schema
- GPU별 WebRTC/NVENC 호환성
- LoadBalancer IP pool 가용 수

### Phase 1 — Isaac Sim image 확인/build

1. 현재 Harbor에 사용할 수 있는 Isaac Sim image가 있는지 확인
2. 없거나 extension commit이 불명확하면 새로 build
3. NGC base image version/digest 기록
4. 필요한 Extension만 pin
5. 내부 Harbor에 push
6. image pull smoke test

### Phase 2 — UI 없는 단일 인스턴스 smoke test

목적:

- image 실행
- GPU runtime
- Nucleus 연결
- WebRTC 연결
- LoadBalancer 포트

이 단계에서는 임시로 `nvidia.com/gpu: 1`을 사용할 수 있다.

### Phase 3 — 특정 GPU DRA smoke test

1. 실제 ResourceSlice에서 GPU 하나 선택
2. exact selector ResourceClaimTemplate 생성
3. Pod가 선택 GPU를 할당받는지 확인
4. 동일 GPU 중복 claim 실패 확인
5. Pod 삭제 후 claim 반환 확인

### Phase 4 — 최소 Isaac UI 구현

1. GPU inventory API
2. 인스턴스 create/list/detail/delete API
3. GPU 선택 화면
4. Stream IP 표시
5. 오류 처리
6. 최소 RBAC

### Phase 5 — SmartX chart/preset

1. `eecs-k8s/apps/omniverse-isaac-saas` 추가
2. feature graph 추가
3. `c-k8s` 또는 `twinx-k8s` feature 활성화
4. cluster patch 추가
5. Helm render 검증
6. Argo CD sync/health 검증

### Phase 6 — 사용자 검증

1. UI에서 GPU 확인
2. 특정 GPU 선택
3. 인스턴스 생성
4. WebRTC 접속
5. Nucleus asset 열기
6. 인스턴스 삭제
7. GPU/IP 반환 확인

---

## 16. 테스트 기준

### 16.1 정적 검증

- 원본 registry, namespace, 노드명이 남아 있지 않다.
- Secret 원문이 chart, preset diff, runbook에 없다.
- UI image와 Isaac Sim image가 내부 Harbor를 가리킨다.
- metrics/code-server/scene 관련 env와 RBAC가 없다.

### 16.2 Helm 검증

```bash
helm template omniverse-isaac-saas <chart-path> \
  -f <cluster-patch-values> \
  > /tmp/rendered-isaac-saas.yaml
```

render 결과에 Secret 값이 포함될 가능성이 있으면 내용을 출력하지 않고 검증 후 삭제한다.

### 16.3 Kubernetes 검증

```bash
kubectl -n omniverse get deploy,svc,pod -l app=isaac-ui
kubectl get deviceclass
kubectl get resourceslices
kubectl -n omniverse get resourceclaimtemplates,resourceclaims
kubectl -n omniverse get deploy,svc,pod -l group=dt-sim
```

### 16.4 선택 정확성

- UI에서 선택한 node와 실제 Pod node가 일치한다.
- UI에서 선택한 GPU UUID와 ResourceClaim allocation 결과가 일치한다.
- 선택하지 않은 GPU가 컨테이너에 노출되지 않는다.
- 같은 GPU로 두 번째 인스턴스를 만들면 중복 할당되지 않는다.

### 16.5 WebRTC/Nucleus

- signaling TCP 연결 가능
- media UDP 연결 가능
- advertised public IP와 Service external IP 일치
- Isaac Sim ready log 확인
- Nucleus asset root 접근 가능
- Secret 값이 로그에 출력되지 않음

---

## 17. 미확정 항목

구현 전에 실제 환경에서 확인해야 한다.

1. C 또는 TwinX 클러스터의 Kubernetes version
2. NVIDIA DRA driver 설치 상태와 version
3. DeviceClass 이름
4. ResourceSlice attribute key와 device name 형식
5. GPU 노드별 제품/UUID/NVENC 호환성
6. 사용할 Isaac Sim base image의 최종 version/digest
7. 포함할 Extension 목록과 고정 commit
8. Isaac UI와 Isaac Sim을 push할 Harbor project
9. LoadBalancer IP pool 범위와 동시 인스턴스 상한
10. Native WebRTC client만 제공할지 browser client도 제공할지
11. 운영 전 사용자 인증과 네트워크 접근 제한 방식

---

## 18. 참고 자료

- Kubernetes DRA: <https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/>
- Kubernetes device allocation: <https://kubernetes.io/docs/tasks/configure-pod-container/assign-resources/allocate-devices-dra/>
- NVIDIA GPU Operator DRA: <https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/dra-intro-install.html>
- Isaac Sim cloud/WebRTC deployment: <https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_advanced_cloud_setup_aws.html>
- Nucleus credential injection: <https://docs.omniverse.nvidia.com/ovas/latest/configuration/nucleus-storage-credentials.html>

---

## 19. 한 문장 요약

원본의 광범위한 연구/모니터링 플랫폼을 그대로 가져오지 않고, 이기종 GPU inventory와 정확한 DRA GPU 선택, Isaac Sim 생성/삭제, 인스턴스별 LoadBalancer WebRTC, 기존 Nucleus 연결만 제공하는 최소 self-service 플랫폼으로 다시 구성한다.
