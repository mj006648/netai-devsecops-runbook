# TwinX control1 GPU/MIG 포털 사전 배포 기록 — 2026-07-15

> 이 문서는 `WRITE_ENABLED=false`였던 사전 preview의 역사적 기록이다. 이후 실제 launch, 신규 Nucleus 인증, Extension 포함, delete/GPU 반환 결과는 [`TWINX_ISAAC_SIM_E2E_2026-07-15.md`](./TWINX_ISAAC_SIM_E2E_2026-07-15.md)를 기준으로 한다.

> 목적: 기존 연구원의 `oos-sim` 워크로드와 외부 Nucleus를 건드리지 않고, 실제 TwinX GPU 클러스터에서 `isaac-twinx`가 일반 GPU와 MIG를 자동 탐색하는지 확인하기 위한 **읽기 전용 웹 포털**을 Argo CD 구조에 추가한 기록이다.
>
> 이 문서는 제품 범위나 최종 eecs-k8s chart 코드를 다시 설명하지 않는다. 제품 범위는 [`ISAAC_UI_MVP_SCOPE.md`](./ISAAC_UI_MVP_SCOPE.md), 최종 이관 파일 경계는 [`SMARTX_MIGRATION_PLAN.md`](./SMARTX_MIGRATION_PLAN.md)를 기준으로 한다.

---

## 1. 결론

다음 두 저장소의 변경을 완료하고 push했다.

| 저장소 | commit | 결과 |
| --- | --- | --- |
| `mj006648/isaac-twinx` | `f175fb0`, `bd7d6f0` | 일반 GPU와 MIG 동시 inventory, MIG별 DeviceClass 선택, 읽기 전용 모드 강화 |
| `SmartX-Team/TwinX-Ops` | `42c5f92` | `argocd/omniverse`에 독립적인 읽기 전용 포털 Application 등록 |

내부 Harbor image도 생성했다.

```text
image: 10.38.38.210/library/isaac-twinx-preview:sha-bd7d6f09e8623ceeedd79cd9a6b3c4cea13f1504
digest: sha256:021f0b34796e3934b0a84c8130e3df58865b8ad8b94361af054e6d73fb0ebb22
size: 67,702,213 bytes
```

현재 단계에서는 Git push만 완료했다.

```text
Argo CD sync: 사용자가 수행
실제 Kubernetes resource 생성: 아직 하지 않음
Isaac Sim instance 생성/삭제: 비활성화
신규 Kubernetes Nucleus: 아직 만들지 않음
```

---

## 2. 절대 건드리지 않은 대상

이번 작업의 가장 중요한 안전 경계다.

```text
namespace oos-sim의 기존 isaac-ui, dt-sim-* 및 다른 연구원 instance
기존 Nucleus 10.38.38.32
omni-streaming/nucleus-auth Secret
MiniX의 Kubernetes Nucleus와 Isaac Sim instance
기존 TwinX-Ops omniverse Application들
```

수행하지 않은 작업:

- 기존 Deployment, Service, ResourceClaim, PVC, Secret을 수정하거나 삭제하지 않았다.
- `oos-sim` namespace에 리소스를 만들지 않았다.
- `10.38.38.32`에 있는 Nucleus를 Kubernetes로 이관하거나 교체하지 않았다.
- Argo CD sync와 `kubectl apply`를 수행하지 않았다.
- 기존 Nucleus credential을 새 namespace로 복사하지 않았다.

---

## 3. 실제 TwinX 클러스터에서 확인한 전제

### 3.1 Kubernetes와 DRA

```text
Kubernetes: v1.35.4
DRA API: resource.k8s.io/v1
GPU DeviceClass: gpu.nvidia.com
MIG DeviceClass: mig.nvidia.com
NVIDIA driver: gpu.nvidia.com
```

일반 GPU와 MIG가 모두 `ResourceSlice`로 게시되고 있었다.

```text
NVIDIA L40S
NVIDIA L40
NVIDIA A100
NVIDIA A10
NVIDIA RTX A6000
NVIDIA Quadro RTX 6000
NVIDIA A100 MIG 1g.5gb
```

확인 당시 실제 ResourceSlice JSON을 포털 inventory parser에 입력한 결과:

```text
전체 device: 25
Available: 15
Allocated: 1
WebRTC incompatible: 9
MIG device: 7
compute-domain helper가 GPU로 잘못 집계된 수: 0
```

이 수치는 실행 시점의 snapshot이다. 포털은 값을 manifest에 저장하지 않고 매 요청마다 Kubernetes API에서 다시 읽으므로 instance 생성/삭제와 MIG 설정 변경에 따라 달라진다.

### 3.2 A100과 WebRTC

A100과 확인된 A100 MIG profile은 NVENC가 없어 Isaac Sim WebRTC 대상으로 사용하지 않는다.

```text
inventory에는 표시
상태: Incompatible
선택/실행 대상: 제외
```

렌더링이나 WebRTC가 아닌 CUDA batch 용도라면 별도 정책으로 사용할 수 있지만, 현재 포털의 목적과는 다르다.

---

## 4. 왜 `argocd/omniverse` 아래에 두었는가

TwinX-Ops 전체 구조를 먼저 확인했다.

```text
argocd/twinx-infra    -> GPU Operator, NVIDIA DRA, Harbor, MetalLB 등 기반 기능
argocd/twinx-storage  -> Rook-Ceph, NFS 등 storage 기반 기능
argocd/omniverse      -> OVAS, Streaming, Kit, Auth 등 Omniverse 계열 앱
argocd/twinx          -> TwinX 자체 서비스
```

`isaac-twinx`는 GPU Operator나 DRA driver를 설치하는 infra 앱이 아니다. 이미 설치된 DRA API를 읽고 Omniverse/Isaac Sim instance를 관리하는 상위 앱이므로 `argocd/omniverse` 아래가 맞다.

이번 배포는 기존 저장소의 raw manifest 패턴을 따랐다.

```text
argocd/omniverse/apps/isaac-twinx-preview/
└── install.yaml
```

의도적으로 만들지 않은 파일:

```text
apps/isaac-twinx-preview/Chart.yaml
apps/isaac-twinx-preview/values.yaml
apps/isaac-twinx-preview/README.md
```

이 app 하나를 위해 중첩 Helm chart를 만들 필요가 없고, 설명 문서는 이 runbook에서 관리한다. 상위 `argocd/omniverse` chart는 child Application을 생성하는 기존 root chart로 그대로 유지한다.

---

## 5. `isaac-twinx`에서 바꾼 코드

### 5.1 MIG 지원 commit `f175fb0`

| 파일 | 변경 이유 |
| --- | --- |
| `src/isaac_twinx/config.py` | 일반 GPU와 다른 MIG DeviceClass `mig.nvidia.com` 설정 추가 |
| `src/isaac_twinx/inventory.py` | ResourceSlice device를 `gpu`/`mig`로 분류하고 MIG profile, parent UUID, memory, encoder 정보를 읽음 |
| `src/isaac_twinx/resources.py` | 선택한 device 종류에 따라 `gpu.nvidia.com` 또는 `mig.nvidia.com` DeviceClass로 ResourceClaim 생성 |
| `src/isaac_twinx/service.py` | API 응답과 instance 생성 경로에 device 종류 전달 |
| `src/isaac_twinx/api.py` | MIG UUID 입력도 유효한 device ID로 처리 |
| `src/isaac_twinx/static/app.js` | GPU 카드에 MIG profile과 구분 가능한 device 정보를 표시 |
| `src/isaac_twinx/static/index.html` | 일반 GPU와 MIG를 함께 선택하는 UI 문구로 정리 |
| `tests/test_inventory.py` | 일반 GPU, MIG, helper device 제외, parent partition 상태 검증 |
| `tests/test_resources.py` | MIG 선택 시 MIG DeviceClass를 사용하는 ResourceClaim 검증 |

전체 수정 파일:

```text
.env.example
README.md
src/isaac_twinx/api.py
src/isaac_twinx/config.py
src/isaac_twinx/inventory.py
src/isaac_twinx/resources.py
src/isaac_twinx/service.py
src/isaac_twinx/static/app.js
src/isaac_twinx/static/index.html
tests/test_api.py
tests/test_inventory.py
tests/test_resources.py
```

### 5.2 읽기 전용 강화 commit `bd7d6f0`

`WRITE_ENABLED=false`인데도 instance 목록 조회 중 stream IP annotation을 patch할 가능성이 있었다. 이를 제거해 읽기 전용 배포에서는 Kubernetes에 어떠한 patch도 수행하지 않도록 했다.

```text
src/isaac_twinx/service.py
tests/test_instance_owner.py
```

### 5.3 MIG가 없는 클러스터의 동작

MIG는 선택 기능이다.

```text
MIG ResourceSlice가 있으면  -> MIG device를 별도 카드로 표시
MIG ResourceSlice가 없으면  -> 기존 일반 GPU만 표시
MIG DeviceClass를 선택하면  -> mig.nvidia.com으로 ResourceClaim 생성
일반 GPU를 선택하면          -> gpu.nvidia.com으로 ResourceClaim 생성
```

따라서 MiniX처럼 일반 GPU 한 장만 있는 클러스터와 TwinX처럼 일반 GPU/MIG가 섞인 클러스터가 같은 application image를 사용할 수 있다.

---

## 6. TwinX-Ops에서 바꾼 파일

### 6.1 추가

```text
argocd/omniverse/apps/isaac-twinx-preview/install.yaml
```

포함된 Kubernetes resource는 정확히 7개다.

```text
ServiceAccount
ClusterRole
ClusterRoleBinding
Role
RoleBinding
Service
Deployment
```

### 6.2 수정

```text
argocd/omniverse/values.yaml
```

추가한 child Application 등록값:

```yaml
applications:
  isaac-twinx-preview:
    enabled: true
    namespace: omniverse
    syncWave: "11"
    project: omniverse
    source:
      path: "argocd/omniverse/apps/isaac-twinx-preview"
```

### 6.3 변경하지 않음

```text
argocd/omniverse/Chart.yaml
argocd/omniverse/templates/applications.yaml
기존 argocd/omniverse/apps/*
```

즉 상위 Argo CD Application 생성 방식은 그대로 쓰고, 앱 목록과 새 raw manifest만 추가했다.

---

## 7. `install.yaml`의 역할과 안전 설정

### 7.1 namespace와 리소스 이름

```text
namespace: omniverse
app name: isaac-twinx-preview
```

기존 `oos-sim`과 이름/namespace가 겹치지 않는다.

### 7.2 읽기 전용 RBAC

cluster scope에서 읽는 리소스:

```text
nodes: list
resourceslices.resource.k8s.io: list
resourceclaims.resource.k8s.io: list
```

`omniverse` namespace에서 읽는 리소스:

```text
deployments: get, list
services: get, list
pods: get, list
resourceclaims.resource.k8s.io: get, list
```

존재하지 않는 권한:

```text
create
update
patch
delete
deletecollection
```

### 7.3 포털 mutation 비활성화

```text
WRITE_ENABLED=false
AUTH_ENABLED=false
ISAAC_SIM_IMAGE=""
```

따라서 UI는 GPU/MIG와 현재 `omniverse` instance 상태를 보여주지만 Launch/Delete API는 동작하지 않는다. 인증 없이 쓰기 기능을 켜지 않는 것이 이번 사전 배포의 의도다.

### 7.4 DRA 설정

```text
DRA_API_VERSION=resource.k8s.io/v1
DRA_DRIVER=gpu.nvidia.com
DRA_DEVICE_CLASS=gpu.nvidia.com
DRA_MIG_DEVICE_CLASS=mig.nvidia.com
WEBRTC_INCOMPATIBLE_PRODUCTS=A100
```

노드명, GPU UUID, MIG UUID, GPU 수량은 넣지 않았다.

### 7.5 Service

```text
type: LoadBalancer
고정 loadBalancerIP: 없음
```

기존 서비스 IP와 충돌하지 않도록 MetalLB가 빈 IP를 할당하게 했다. sync 후 `kubectl -n omniverse get svc isaac-twinx-preview`에서 실제 External IP를 확인한다.

### 7.6 Nucleus 값의 의미

manifest에는 향후 instance launch용 기본 endpoint가 있다.

```text
OMNI_SERVER=omniverse://10.38.38.32/
```

하지만 현재는 `WRITE_ENABLED=false`, `ISAAC_SIM_IMAGE=""`이고 credential Secret도 연결하지 않았다. 포털 자체는 Nucleus에 접속하지 않으므로 이번 웹 inventory 단계에서 기존 Nucleus에 로그인하거나 데이터를 변경하지 않는다.

---

## 8. 하드코딩과 범용성 경계

application image 안에 넣지 않은 것:

```text
클러스터 API 주소
노드 이름
GPU/MIG UUID
GPU/MIG 수량
LoadBalancer IP
Nucleus password
Harbor password
사용자 instance 목록
```

TwinX 배포 manifest에만 둔 값:

```text
namespace=omniverse
DRA API/driver/DeviceClass
기존 Nucleus endpoint 10.38.38.32
A100 WebRTC 제외 정책
내부 Harbor image tag
```

이 값들은 application source의 범용 로직이 아니라 대상 클러스터의 배포 설정이다. 추후 eecs-k8s 구조에서는 공통 chart 기본값과 `<gpu-cluster>-k8s/patches/omniverse-isaac-saas/values.yaml`로 분리한다.

---

## 9. image build와 registry 판단

GH Actions가 만든 아래 image는 package visibility가 private라 TwinX에서 익명 pull할 수 없었다.

```text
ghcr.io/mj006648/isaac-twinx:sha-bd7d6f09e8623ceeedd79cd9a6b3c4cea13f1504
```

기존 namespace의 registry credential을 복사하지 않고, control1에서 같은 commit을 빌드해 공개 내부 Harbor project `library`에 push했다.

```text
10.38.38.210/library/isaac-twinx-preview:sha-bd7d6f09e8623ceeedd79cd9a6b3c4cea13f1504
```

이 선택의 이유:

- `omniverse`에 새 imagePullSecret을 만들 필요가 없다.
- 다른 연구원의 private project credential을 재사용하지 않는다.
- source commit SHA로 image 내용을 추적할 수 있다.
- tag와 registry artifact digest를 함께 기록해 검증할 수 있다.

---

## 10. 수행한 검증

### 10.1 application source

```text
pytest: 37 passed
JavaScript syntax check: 성공
실제 control1 ResourceSlice/ResourceClaim JSON parser 실행: 성공
MIG UUID 중복: 0
compute-domain helper 오집계: 0
```

### 10.2 Harbor

```text
tag: sha-bd7d6f09e8623ceeedd79cd9a6b3c4cea13f1504
digest: sha256:021f0b34796e3934b0a84c8130e3df58865b8ad8b94361af054e6d73fb0ebb22
size: 67,702,213 bytes
```

### 10.3 raw manifest

```text
YAML resource: 7
Secret: 0
StatefulSet: 0
PVC: 0
ResourceClaim: 0
create/delete/patch RBAC verb: 없음
oos-sim 참조: 없음
고정 loadBalancerIP: 없음
기존/private imagePullSecret 참조: 없음
```

### 10.4 Kubernetes API server dry-run

다음 7개 모두 server-side dry-run에 성공했다.

```text
serviceaccount/isaac-twinx-preview
clusterrole/isaac-twinx-preview-inventory
clusterrolebinding/isaac-twinx-preview-inventory
role/isaac-twinx-preview
rolebinding/isaac-twinx-preview
service/isaac-twinx-preview
deployment/isaac-twinx-preview
```

`created (server dry run)`은 API validation 결과일 뿐 실제 리소스 생성이 아니다.

### 10.5 상위 Helm render

`argocd/omniverse` root chart를 렌더해 child Application이 정확히 생성되는 것을 확인했다.

```text
kind: Application
name: isaac-twinx-preview
project: omniverse
destination namespace: omniverse
source path: argocd/omniverse/apps/isaac-twinx-preview
```

### 10.6 Argo CD 자동 동기화 상태

push 직전 live 상태:

```text
application: omniverse-root-app
sync status: Synced
automated.enabled: false
```

따라서 commit `42c5f92`를 main에 push해도 자동 sync되지 않았고, 사용자가 sync할 때까지 실제 cluster에는 아무것도 생성되지 않는다.

---

## 11. 사용자가 수행할 Argo CD sync 순서

### 11.1 root app sync

먼저 `omniverse-root-app`을 sync한다. 이 단계는 child Application `isaac-twinx-preview`를 등록한다.

```bash
kubectl -n argocd get application omniverse-root-app
kubectl -n argocd get application isaac-twinx-preview -o wide
```

### 11.2 child app sync

그 다음 `isaac-twinx-preview`를 sync한다. 이 단계에서 `omniverse` namespace에 7개 포털 리소스가 생성된다.

```bash
kubectl -n omniverse get deploy,pod,svc -l app.kubernetes.io/name=isaac-twinx-preview -o wide
kubectl -n omniverse rollout status deploy/isaac-twinx-preview
kubectl -n omniverse get svc isaac-twinx-preview
```

### 11.3 웹 확인

```bash
PORTAL_IP=$(kubectl -n omniverse get svc isaac-twinx-preview -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl -fsS "http://${PORTAL_IP}/healthz"
curl -fsS "http://${PORTAL_IP}/api/gpus"
```

브라우저에서 `http://<PORTAL_IP>`를 열어 다음을 확인한다.

- 여러 노드의 GPU 제품명이 표시되는가
- 일반 GPU와 MIG profile이 구분되는가
- 사용 중/가용/호환 불가 상태가 실제 DRA claim과 일치하는가
- `oos-sim`의 기존 instance가 삭제되거나 변경되지 않았는가
- Launch/Delete가 비활성화되어 있는가

---

## 12. rollback

이번 변경은 child Application 하나로 격리돼 있다.

1. `argocd/omniverse/values.yaml`에서 `isaac-twinx-preview.enabled`를 `false`로 변경하거나 해당 등록 블록을 되돌린다.
2. root app을 sync한다.
3. 필요하면 child Application과 `omniverse`의 `isaac-twinx-preview` 리소스만 제거한다.

삭제 대상 이름에는 모두 `isaac-twinx-preview`가 들어간다. `oos-sim`, `dt-sim-*`, 기존 Nucleus, 기존 PVC/Secret은 rollback 대상이 아니다.

---

## 13. 이번 단계가 증명한 것과 아직 증명하지 않은 것

### 증명

- 하나의 application image가 일반 GPU-only 클러스터와 GPU/MIG 혼합 클러스터를 모두 처리한다.
- GPU 노드/UUID/MIG profile을 manifest에 하드코딩하지 않아도 실시간 inventory를 만들 수 있다.
- helper ResourceSlice를 GPU로 잘못 집계하지 않는다.
- TwinX-Ops 기존 root Application 구조에 raw manifest 앱을 추가할 수 있다.
- 쓰기 권한 없이 API server validation을 통과한다.
- 기존 workload와 Nucleus를 건드리지 않는 독립 namespace/name/RBAC 경계를 만들었다.

### 아직 미증명

- Argo sync 후 실제 포털 Pod의 image pull과 health
- 웹에서 실제 TwinX GPU/MIG 카드 표시
- MIG를 선택한 Isaac Sim instance 생성
- TwinX용 Isaac Sim runtime image와 WebRTC
- Nucleus credential 주입과 Isaac Sim Content Browser 자동 연결
- 신규 Kubernetes Nucleus StatefulSet과 Ceph RBD PVC

---

## 14. 다음 단계

안전한 순서는 다음과 같다.

1. 사용자가 root app과 child app을 수동 sync한다.
2. 읽기 전용 웹에서 GPU/MIG inventory만 확인한다.
3. 기존 `oos-sim`과 `10.38.38.32`가 그대로인지 재확인한다.
4. TwinX용 Isaac Sim image, registry, WebRTC network 값을 정한다.
5. 인증/사용자 식별을 붙인 뒤에만 `WRITE_ENABLED=true`를 검토한다.
6. 일반 GPU 한 장을 선택해 instance create/delete와 DRA 반환을 검증한다.
7. NVENC 가능한 MIG profile이 실제로 제공될 때 MIG instance를 별도 검증한다.
8. 그 다음에만 신규 Nucleus를 `omniverse`에 독립 StatefulSet + 신규 Ceph RBD PVC + 신규 Service IP로 설계한다.
9. 모든 live 검증 후 동일한 값 경계를 eecs-k8s 공통 chart와 GPU cluster preset patch로 옮긴다.

신규 Nucleus 단계에서도 다음은 불변이다.

```text
기존 10.38.38.32 유지
기존 omni-streaming/nucleus-auth 유지
신규 Secret/PVC/Service/name 사용
기존 oos-sim 리소스 수정 금지
```

---

## 15. 한 문장 결론

TwinX control1에서는 기존 연구원 워크로드와 Nucleus를 전혀 수정하지 않은 채, 일반 GPU와 MIG를 Kubernetes DRA에서 자동 탐색하는 `isaac-twinx` 읽기 전용 포털을 기존 `argocd/omniverse` raw manifest 방식으로 준비하고 image, RBAC, server dry-run, root render, 수동-sync 경계까지 검증했다.
