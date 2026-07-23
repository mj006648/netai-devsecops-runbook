# Omniverse Isaac SaaS SmartX/eecs-k8s 이관 구현 가이드

> 목적: MiniX에서 검증한 `isaac-twinx` 포털과 Isaac Sim 실행 구조를 SmartX의 `eecs-k8s` 공통 앱 카탈로그와 `c-k8s`/`twinx-k8s` 클러스터 preset 구조로 옮길 때, **어느 파일에 어떤 코드를 넣고 왜 넣는지**를 구현 단위로 설명한다.
> 이 문서는 제품 범위를 다시 결정하는 문서가 아니다. 유지·제거 기능과 UI 범위는 [`ISAAC_UI_MVP_SCOPE.md`](./ISAAC_UI_MVP_SCOPE.md), 현재 실제 TwinX 성공 기준은 [`TWINX_ISAAC_SIM_E2E_2026-07-15.md`](./TWINX_ISAAC_SIM_E2E_2026-07-15.md)를 기준으로 한다.
> Secret 원문은 이 문서, `eecs-k8s`, 공개 저장소, Helm render 출력에 기록하지 않는다.

---

## 0A. 2026-07-16 최신 구현 기준

### 0A.0 이번 단계의 전제와 목표

이번 단계에서는 **C 클러스터에 DGX Spark 노드가 이미 join되어 있고 Ready 상태**라고 가정한다. 실제 join 완료 여부를 기다리는 작업이 아니라, 조인 완료 후 바로 재현할 수 있는 설치·검증 계획을 먼저 확정한다.

최종 순서는 다음과 같다.

```text
Kubernetes 1.34.3
  -> NVIDIA GPU Operator
  -> NVIDIA DRA GPU Driver
  -> GPU/MIG/DRA 리소스 확인
  -> Nucleus 유지 또는 별도 Nucleus 배포
  -> isaac-twinx UI 배포
  -> GPU 선택
  -> Isaac Sim 인스턴스 생성
  -> WebRTC 연결 및 삭제/GPU 반환 검증
  -> eecs-k8s 공통 chart + c-k8s preset으로 정리
```

기존 C 클러스터의 `oos-sim` 네임스페이스, 기존 연구원 워크로드, 외부 Nucleus endpoint는 이 작업의 소유 범위가 아니다. 기존 Nucleus를 삭제하거나 재설치하지 않고, 필요한 경우 `omniverse` 네임스페이스에 별도 리소스로 배포한다.

### 0A.0.1 C 클러스터 GPU 사전조건

DGX Spark가 조인된 뒤 다음 항목을 순서대로 확인한다.

```bash
kubectl version
kubectl get nodes -o wide
kubectl get nodes --show-labels
kubectl get pods -n gpu-operator
kubectl get clusterpolicy -A
kubectl get crd | grep -E 'nvidia|resource'
```

확인 기준:

| 단계 | 확인할 것 | 실패 시 조치 |
| --- | --- | --- |
| Kubernetes | C 클러스터가 목표 버전 `v1.34.3`인지 | Kubespray 업그레이드 계획 적용 후 재검증 |
| Node | DGX Spark가 `Ready`인지 | kubelet/container runtime/CNI 상태 확인 |
| GPU Operator | NVIDIA device plugin, toolkit, feature discovery가 정상인지 | GPU Operator 설치 또는 버전 호환성 수정 |
| GPU 리소스 | `nvidia.com/gpu` 또는 GPU Operator가 제공하는 리소스가 allocatable인지 | 드라이버·toolkit·operator 로그 확인 |
| MIG | MIG device/profile이 노출되는지 | MIG strategy와 실제 GPU profile 확인 |
| DRA | `resource.k8s.io` API, `DeviceClass`, `ResourceSlice`가 존재하는지 | NVIDIA DRA Driver 설치 및 kubelet/controller 상태 확인 |

GPU Operator와 DRA Driver는 서로 대체 관계가 아니다. GPU Operator는 노드 드라이버, container toolkit, device plugin, node labeling 등 GPU 실행 기반을 제공하고, DRA Driver는 Kubernetes ResourceClaim 기반으로 특정 GPU 또는 MIG 자원을 선택·할당할 수 있게 한다. 따라서 둘 다 설치·검증한 뒤 Isaac UI의 DRA 기능을 켠다.

초기 배포에서는 DRA가 완전히 검증되기 전까지 기존 `nvidia.com/gpu: 1` 경로를 fallback으로 남긴다. DRA가 정상 확인되면 `ResourceClaimTemplate` 기반 선택을 활성화한다.

### 0A.0.2 GPU Operator 및 DRA 설치 원칙

설치 소유권은 C 클러스터의 ArgoCD/eecs-k8s 구조에 맞춘다. 임시로 `kubectl apply`하여 운영 리소스를 우회하지 않고, 다음 순서로 manifest/application을 준비한다.

```text
1. Kubernetes 1.34.3 호환성 확인
2. NVIDIA GPU Operator chart/version 확인
3. GPU Operator 설치 또는 기존 설치 상태 확인
4. NVIDIA DRA Driver chart/application 추가
5. DeviceClass/ResourceSlice 및 실제 allocatable GPU 확인
6. 그 다음에 omniverse-nucleus와 isaac-twinx 배포
```

DRA Driver는 eecs-k8s의 기존 `apps/nvidia-gpu-dra` 패턴을 재사용한다. c-k8s에서는 기능 활성화와 클러스터별 값만 patch로 지정한다. 설치가 끝나기 전에는 `org.ulagbulag.io/omniverse/isaac-saas/dra` feature를 활성화하지 않는다.


이 절은 기존 계획을 현재 검증된 `isaac-twinx` 코드와 최신 SmartX 엔진 구조에 맞춰 해석하기 위한
기준이다. 아래 기준과 기존 본문이 다르면 이 절과 실제 `isaac-twinx` source를 우선한다.

### 현재 source/image 기준

```text
isaac-twinx source: 3013986
source tests: 42 passed
portal image used by MiniX/TwinX: sha256:67fc3848cab38bb3503b71bdfc08b1d64e4702e9b95bbdd043287cbe1f0e9254
Isaac Sim runtime image: TwinX E2E verified immutable digest recorded in TWINX_ISAAC_SIM_E2E
```

현재 포털의 실제 범위는 `isaac-ui` 전체 기능을 복제하는 것이 아니다.

```text
포함:
  - Kubernetes/DRA GPU inventory
  - 일반 GPU와 MIG inventory
  - 실제 GPU index/PCI 정보가 있으면 UI에 표시
  - memory quantity를 GiB로 정규화
  - GPU UUID 선택
  - 선택 GPU 한 장에 대한 ResourceClaim
  - Isaac Sim Deployment 생성
  - 인스턴스별 WebRTC TCP/UDP LoadBalancer Service
  - 사용자 이름, Stream IP, 노드/GPU, 삭제와 GPU 반환
  - Nucleus URI/Secret reference runtime 주입
  - Pending -> Initializing(기본 120초) -> Running 상태 표시

제외:
  - Metrics/Prometheus UI
  - Scenes 관리
  - GPU bans 관리 UI
  - code-server sidecar
  - 사용자별 PVC/workspace
  - preview mode
  - 원본 isaac-ui의 모든 self-service 부가 기능
```

`Pod Ready`는 Isaac Sim WebRTC 준비 완료가 아니므로, `STREAM_INITIALIZATION_SECONDS=120` 동안
포털은 `Initializing`으로 표시한다. 이 값은 공통 chart의 기본값으로 두고 preset에서 조정할 수 있게
한다. 사용자가 실제로 1~2분 대기 후 WebRTC 연결에 성공한 결과를 현재 기준으로 삼는다.

### 최신 isaac-twinx 코드에서 반드시 보존할 설정

| source | 현재 의미 | SmartX chart/preset 전달값 |
| --- | --- | --- |
| `src/isaac_twinx/inventory.py` | DRA ResourceSlice의 GPU/MIG, UUID, index, PCI, memoryGiB 계산 | 별도 inventory values를 만들지 않음 |
| `src/isaac_twinx/config.py` | DRA class와 `STREAM_INITIALIZATION_SECONDS` 환경변수 | `dra.*`, `instance.streamInitializationSeconds` |
| `src/isaac_twinx/resources.py` | exact one-device ResourceClaim, Isaac Deployment, WebRTC Service | `instance.*`, `dra.*`, `nucleus.*` |
| `src/isaac_twinx/service.py` | instance lifecycle, Initializing/Running 판정 | `instance.streamInitializationSeconds` |
| `src/isaac_twinx/api.py` | `/api/gpus`, `/api/instances`, `/api/config` | chart가 포털을 배포하고 RBAC를 제공 |
| `images/isaac-sim/entrypoint.sh` | `OMNI_SERVER` runtime Nucleus config | image에 주소를 bake하지 않음 |

### 최신 eecs-k8s 기준의 실제 app catalog 연결

현재 최신 `eecs-k8s`는 `apps/*/manifest.yaml`을 `/templates/applications.yaml`이 자동 발견한다.
`apps/template/application.yaml`은 `patched: true`인 앱에 대해 다음 cluster patch를 multi-source로 연결한다.

```text
$origin/apps/<app>/values.yaml
$cluster/patches/<app>/values.yaml
$cluster repository ref
```

따라서 Isaac SaaS 앱은 기존 Nucleus처럼 다음 경로를 새로 만든다.

```text
eecs-k8s/apps/omniverse-isaac-saas/
  Chart.yaml
  manifest.yaml
  values.yaml
  patches.yaml                # 필요할 때만 작은 계산값
  templates/
    _helpers.tpl
    serviceaccount.yaml
    role.yaml
    rolebinding.yaml
    clusterrole.yaml           # cluster inventory가 필요할 때
    clusterrolebinding.yaml
    deployment.yaml
    service.yaml
```

현재 개인 `smartx-k8s` working tree에 이 chart의 재사용 가능한 파일이 남아 있지 않으므로, 존재하지 않는
개인 chart를 복사한다고 가정하지 않는다. `isaac-twinx/deploy/minix/deployment.yaml`,
`deploy/minix/service.yaml`, `src/isaac_twinx/resources.py`, `src/isaac_twinx/config.py`를 기준으로
새 SmartX chart를 작성한다. 사용자별 Isaac Sim 리소스는 chart template에 넣지 않는다.

### feature graph와 GPU/DRA 의존성

최신 eecs-k8s에는 이미 다음 feature가 존재한다.

```text
nvidia.com/gpu
nvidia.com/gpu/dynamic-resource-allocation
org.ulagbulag.io/omniverse
org.ulagbulag.io/omniverse/nucleus
org.ulagbulag.io/registry/container/harbor
```

추가할 feature는 포털과 GPU 실행 capability를 분리해 표현한다.

```yaml
org.ulagbulag.io/omniverse/isaac-saas:
  requires:
    - org.ulagbulag.io/omniverse/nucleus

org.ulagbulag.io/omniverse/isaac-saas/dra:
  requires:
    - org.ulagbulag.io/omniverse/isaac-saas
    - nvidia.com/gpu
    - nvidia.com/gpu/dynamic-resource-allocation
```

Harbor는 현재 C 외부 registry `10.34.25.18`을 사용할 예정이므로 hard dependency로 넣지 않는다.
Harbor 자체 feature는 별도 인프라 소유권이며, Isaac portal은 `imagePullSecret`으로 외부 Harbor를
사용한다. 계정/비밀번호는 Secret으로만 전달한다.

C에는 DGX Spark가 추가되었으므로 다음 순서로 C를 1차 실제 대상에 포함한다.

```text
c-k8s/values.yaml
  org.ulagbulag.io/omniverse/isaac-saas 추가
  GPU/DRA 확인 후 org.ulagbulag.io/omniverse/isaac-saas/dra 추가

c-k8s/patches/omniverse-isaac-saas/values.yaml
  C portal/image/Harbor/Nucleus/DRA/LB/Secret 참조
```

DGX Spark가 실제 `DeviceClass`, `ResourceSlice`, `ResourceClaim`을 제공하는지 확인하기 전에는
`/dra` feature와 `WRITE_ENABLED=true`를 켜지 않는다. DRA가 확인되면 C에서 일반 GPU/MIG 선택과
Isaac Sim launch까지 검증한다. 이후 같은 공통 chart를 실제 `twinx-k8s`로 별도 이관한다.

현재 c preset의 `cluster.group: ops`는 원격 `ops` branch가 존재하지 않고
`eecs-k8s/apps/template/application.yaml`이 이를 cluster repo `targetRevision`으로 사용한다.
C Argo 적용 전 `main`으로 정렬하거나 `ops` branch를 명시적으로 생성하는 branch 결정을 먼저 완료한다.

### C 1차 patch와 Secret 경계

C에는 이미 `org.ulagbulag.io/omniverse/nucleus`가 있으므로 Nucleus StatefulSet을 복제하지 않는다.
포털은 별도의 Nucleus client Secret 이름/key만 참조한다. Nucleus 내부 password Secret의 key 구조가
`OMNI_USER`/`OMNI_PASS`와 다를 수 있으므로, 포털용 client Secret은 ExternalSecret 또는 클러스터
운영 절차로 별도 제공한다.

```yaml
ui:
  writeEnabled: false
  image:
    repository: 10.34.25.18/<harbor-project>/isaac-twinx
    digest: sha256:<PORTAL_DIGEST>
  imagePullSecrets: [<PORTAL_PULL_SECRET>]
  service:
    type: LoadBalancer
    loadBalancerIP: <C_PORTAL_IP>

instance:
  image:
    repository: 10.34.25.18/<harbor-project>/isaac-sim
    digest: sha256:<ISAAC_SIM_DIGEST>
  imagePullSecrets: [<ISAAC_PULL_SECRET>]
  streamInitializationSeconds: 120

dra:
  apiVersion: resource.k8s.io/v1
  driver: gpu.nvidia.com
  deviceClass: gpu.nvidia.com
  migDeviceClass: mig.nvidia.com

nucleus:
  server: omniverse://<C_NUCLEUS_LB>/
  projectPath: Projects/demonstration
  credentialSecret:
    name: <NUCLEUS_CLIENT_SECRET>
    userKey: OMNI_USER
    passwordKey: OMNI_PASS
```

Harbor 계정/비밀번호는 values, Git, render output에 기록하지 않는다. 먼저 C namespace에 pull Secret을
준비하고, 이후 portal/Isaac image pull과 Nucleus client Secret 참조만 검증한다.

### 최신 preset patch schema

현재 `twinx-k8s` 개인 patch에는 구형 portal tag와 MiniX Nucleus 값이 남아 있으므로 그대로 복사하지
않는다. 새 patch는 다음 schema를 기준으로 다시 작성한다.

```yaml
ui:
  image:
    repository: <PORTAL_REGISTRY>/isaac-twinx
    digest: sha256:<PORTAL_DIGEST>
  imagePullSecrets: [<PORTAL_PULL_SECRET>]
  writeEnabled: false
  service:
    type: LoadBalancer
    loadBalancerIP: <PORTAL_IP>

instance:
  image:
    repository: <HARBOR>/omniverse/isaac-sim
    digest: sha256:<ISAAC_SIM_DIGEST>
  imagePullSecrets: [<ISAAC_PULL_SECRET>]
  dshmSize: 8Gi
  streamCommand: /isaac-sim/isaac-sim.streaming.sh
  publicEndpointFlag: --/app/livestream/publicEndpointAddress=
  streamIPWaitSeconds: 15
  streamInitializationSeconds: 120

dra:
  apiVersion: resource.k8s.io/v1
  driver: gpu.nvidia.com
  deviceClass: gpu.nvidia.com
  migDeviceClass: mig.nvidia.com

nucleus:
  server: omniverse://<CLUSTER_NUCLEUS>/
  projectPath: Projects/demonstration
  credentialSecret:
    name: <SECRET_NAME>
    userKey: OMNI_USER
    passwordKey: OMNI_PASS

webrtc:
  incompatibleProducts: [A100]
```

MiniX의 Harbor endpoint는 내부 registry로 사용하되 계정/비밀번호는 이 문서나 values에 기록하지 않는다.
Kubernetes `imagePullSecret` 또는 ExternalSecret이 전달하는 구조만 사용한다.

### 최신 MiniX rollout 증거

MiniX 포털은 최신 immutable portal digest로 rollout했고 다음을 확인했다.

```text
Service: 10.34.48.222
Deployment: 1/1 Ready
/healthz: 200 OK
UI: Initializing 표시 코드 제공
/api/gpus: memoryGiB 제공
```

MiniX ResourceSlice provider는 현재 GPU index/PCI attribute를 제공하지 않아 해당 필드가 빈 값일 수
있다. 이것은 UI 실패가 아니라 클러스터 inventory source의 차이다. TwinX처럼 ResourceSlice에 index와
PCI가 있는 클러스터에서는 `GPU #N`과 PCI가 표시된다.

### 이관 후 검증 기준

```text
1. eecs-k8s chart lint
2. engine root helm template에서 isaac app Application 생성 확인
3. multi-source에 $cluster/patches/omniverse-isaac-saas/values.yaml 연결 확인
4. Secret 원문 없이 rendered manifest kind/image/env key 검증
5. GPU cluster에서 DeviceClass/ResourceSlice/portal /api/gpus 확인
6. exact UUID 선택 -> ResourceClaim count=1 확인
7. Isaac Pod가 Initializing 후 Running으로 전환
8. Stream IP WebRTC 연결 확인
9. Nucleus omni.client stat Result.OK 확인
10. 삭제 후 Deployment/Service/ResourceClaim와 GPU 반환 확인
```

이 절의 완료 전까지 `eecs-k8s`, `c-k8s`, `twinx-k8s`에는 push하지 않는다.

## 0. 이 문서만 보면 알 수 있어야 하는 것

이관 작업자는 이 문서를 따라 다음을 판단할 수 있어야 한다.

1. `isaac-twinx`의 어떤 코드는 컨테이너 이미지에 남기는가?
2. 어떤 Kubernetes manifest를 `eecs-k8s` Helm chart로 바꾸는가?
3. 어떤 값은 공통 `values.yaml`에 두고, 어떤 값은 `c-k8s`/`twinx-k8s` patch에 두는가?
4. SmartX feature graph에는 무엇을 추가하는가?
5. Argo CD와 포털이 각각 어떤 리소스를 소유하는가?
6. GPU 노드명, GPU UUID, 현재 가용 수를 왜 preset에 쓰지 않는가?
7. 실제 대상 클러스터에 반영하기 전에 무엇을 렌더링하고 확인하는가?
8. 적용 실패 시 무엇을 되돌리는가?

---


## 0B. C 클러스터 DRA Driver 이관 계획 (2026-07-20)

이번 단계는 DGX Spark가 C 클러스터에 이미 join되어 있고, NVIDIA GPU Operator가 설치되어 있다는 전제에서 진행한다. Isaac TwinX 포털보다 먼저 NVIDIA DRA Driver를 eecs-k8s/c-k8s 구조로 활성화한다.

### 변경 범위

공통 엔진 저장소인 eecs-k8s에는 기존 `apps/nvidia-gpu-dra` 앱이 이미 존재하므로 새 앱을 만들지 않는다. 해당 앱의 `manifest.yaml`에서 `patched: true`만 활성화하여 클러스터별 patch를 받을 수 있게 한다.

```text
eecs-k8s/apps/nvidia-gpu-dra/manifest.yaml
  -> patched: false -> true
```

C preset에서는 다음 두 파일만 DRA 관련으로 변경한다.

```text
c-k8s/values.yaml
  -> nvidia.com/gpu/dynamic-resource-allocation feature 활성화

c-k8s/patches/nvidia-gpu-dra/values.yaml
  -> C 클러스터 전용 driver root/resource/kubelet plugin 설정
```

GPU Operator와 DRA Driver의 역할은 다르다.

```text
GPU Operator
  -> NVIDIA driver, container toolkit, device plugin, GPU node discovery

NVIDIA DRA Driver
  -> DeviceClass, ResourceSlice, ResourceClaim 기반 GPU 할당
```

따라서 GPU Operator를 다시 설치하지 않고, 기존 GPU Operator 상태 위에 DRA Driver만 ArgoCD로 배포한다. 노드명을 하드코딩하지 않고 `nvidia.com/gpu.present=true` label 기반으로 kubelet plugin을 배치한다.

### C preset 적용 후 검증

ArgoCD sync 이후 다음을 확인한다.

```bash
kubectl -n gpu-nvidia get deploy,daemonset,pods -o wide
kubectl get deviceclass
kubectl get resourceslices
kubectl get nodes -o json
```

성공 기준:

- DRA controller와 kubelet plugin이 Running
- `DeviceClass`가 생성됨
- GPU 노드별 `ResourceSlice`가 생성됨
- GPU device가 ResourceSlice에 표시됨
- MIG가 구성된 장치는 해당 MIG device/profile이 표시됨

실제 C 클러스터 sync 검증에서 `/run/nvidia/driver`가 비어 있고 `nvidia-smi` 및 `libnvidia-ml.so.1`이 발견되지 않아 DRA Init 컨테이너가 대기했다. C는 GPU Operator가 driver container를 관리하는 방식이 아니라 호스트에 NVIDIA driver가 직접 설치된 구조이므로, C patch의 `nvidiaDriverRoot`는 `/`로 설정한다. 다른 클러스터에서는 driver container 사용 여부를 확인해 `/run/nvidia/driver` 또는 `/`를 별도로 선택해야 한다.

이번 단계에서는 eecs-k8s와 c-k8s를 원격 push하지 않고 로컬 검증만 수행한다. DRA 검증이 끝난 뒤에만 Isaac SaaS feature와 portal patch를 별도로 적용한다.

## 1. 최종 목표 구조

```text
소스/이미지 저장소
  mj006648/isaac-twinx
    ├── 포털 Python 코드
    ├── 포털 컨테이너 Dockerfile
    ├── Isaac Sim 6.0 컨테이너 Dockerfile/entrypoint/Extension lock
    └── 단위 테스트

SmartX 공통 엔진
  eecs-k8s
    ├── apps/omniverse-isaac-saas/      # 포털을 설치하는 공통 Helm chart
    ├── apps/template/features.yaml     # 의존성 graph
    └── values.yaml                     # feature 이름 등록

클러스터 preset
  c-k8s 또는 twinx-k8s
    ├── values.yaml                     # feature 활성화
    └── patches/omniverse-isaac-saas/
        └── values.yaml                 # 그 클러스터의 image/DRA/Nucleus/LB/Secret 참조

클러스터
  Argo CD
    └── isaac-ui Deployment/Service/RBAC를 관리

  isaac-ui
    ├── Kubernetes Node와 DRA ResourceSlice/ResourceClaim 조회
    └── 사용자 요청마다 다음 리소스를 동적으로 생성/삭제
        ├── Isaac Sim Deployment
        ├── GPU ResourceClaim
        └── WebRTC LoadBalancer Service
```

핵심 경계:

```text
Git/Argo CD가 관리: 포털 자체
포털이 관리: 사용자별 Isaac Sim 인스턴스
```

사용자별 인스턴스를 Helm template에 미리 만들지 않는다. 그래야 사용자가 웹에서 생성·삭제할 수 있고, Argo CD가 인스턴스 수명 주기를 간섭하지 않는다.

---

## 2. 현재 검증된 기준과 실제 이관 대상

### 2.1 소스 저장소

```text
https://github.com/mj006648/isaac-twinx
```

기준 구현에는 다음이 포함된다.

- Kubernetes Node/DRA inventory를 읽는 포털
- 노드, GPU product, GPU UUID를 선택하는 UI
- 선택한 UUID를 DRA selector에 넣는 `ResourceClaim`
- Isaac Sim `Deployment`
- WebRTC TCP/UDP `LoadBalancer Service`
- 인스턴스 생성 사용자 표시
- 인스턴스 삭제 시 Deployment/Service/ResourceClaim 정리
- Nucleus endpoint와 credential Secret 참조
- TwinX에서 검증한 Isaac Sim 6.0 immutable image와 Extension 9개 lock
- 일반 GPU와 MIG DeviceClass를 모두 처리하는 inventory/ResourceClaim 생성
- Nucleus 주소를 runtime env로만 주입하고 과거 cluster IP를 image에 남기지 않는 구성

### 2.2 사전 이관 리허설

실제 `eecs-k8s`와 `c-k8s`에 바로 넣기 전에 개인 저장소에서 SmartX 구조를 렌더링했다.

```text
mj006648/smartx-k8s commit: 964c4c1
mj006648/twinx-k8s commit: 2a616de
```

상세 실행 증거는 다음 문서에만 기록한다.

- chart/preset 렌더: [`SMARTX_PRE_MIGRATION_REHEARSAL_2026-07-14.md`](./SMARTX_PRE_MIGRATION_REHEARSAL_2026-07-14.md)
- 실제 TwinX E2E: [`TWINX_ISAAC_SIM_E2E_2026-07-15.md`](./TWINX_ISAAC_SIM_E2E_2026-07-15.md)

현재 성공 기준은 `isaac-twinx` commit `3013986`, 42 tests, portal digest `sha256:67fc3848cab38bb3503b71bdfc08b1d64e4702e9b95bbdd043287cbe1f0e9254`, Isaac Sim digest `sha256:c3a5b1b3402f3f2d6185fccee158023da59e99748ce096c33d5a2404fdea9bb7`이다.

### 2.3 대상 클러스터 전제

Isaac MVP는 다음 조건을 전제로 한다.

```text
Kubernetes: v1.34.3
NVIDIA GPU Operator/DRA driver: 설치 및 정상
DeviceClass: gpu.nvidia.com
ResourceSlice: GPU device별 정보 존재
LoadBalancer: 포털 IP와 인스턴스별 WebRTC IP 할당 가능
Nucleus: endpoint와 credential Secret 준비
Registry: 포털/Isaac Sim image pull 가능
```

C 클러스터처럼 GPU가 없는 클러스터에서는 chart를 렌더링할 수는 있지만 실제 feature를 활성화해 배포하지 않는다. 실제 배포는 GPU와 DRA가 있는 `twinx-k8s` 또는 해당 GPU 클러스터 preset에서 수행한다.

---

## 3. 세 저장소의 책임

| 저장소 | 넣는 것 | 넣지 않는 것 | 이유 |
| --- | --- | --- | --- |
| `isaac-twinx` | 포털 코드, 정적 UI, Kubernetes client 로직, 인스턴스 리소스 생성 코드, Dockerfile, Isaac Sim image source | 클러스터별 IP/Secret 원문, 특정 GPU UUID | 애플리케이션 소스와 이미지 재현성을 담당 |
| `eecs-k8s` | 공통 Helm chart, SmartX Manifest, feature graph, 안전한 기본값 | 특정 클러스터 IP, 실제 Secret 값, 현재 GPU inventory | 모든 클러스터가 공유할 앱 카탈로그 |
| `c-k8s`/`twinx-k8s` | feature 선택, image digest, DRA 이름, Nucleus 주소, Secret 이름/key, LB 정책 | Python 코드, Dockerfile, 하드코딩 GPU inventory | 클러스터마다 달라지는 설정만 override |
| `tower-k8s` | 기존 root app/Argo CD 제어 | Isaac 포털 manifest 중복 | 실제 앱 정의 소유권은 engine+cluster preset에 둠 |
| `scalex-federation` | 이 문서의 eecs-k8s/c-k8s 직접 배포 경로에는 사용하지 않음 | 같은 Portal/인스턴스의 중복 소유 | Tower Argo CD/Karmada를 통한 단일 또는 복수 member-cluster placement는 별도 [`SCALEX_FEDERATION_SINGLE_CLUSTER_PLAN.md`](./SCALEX_FEDERATION_SINGLE_CLUSTER_PLAN.md)를 따름 |

소유권 원칙:

```text
같은 Deployment/Service/RBAC를 두 저장소가 동시에 관리하지 않는다.
```

`scalex-federation`도 `clusterNames`를 하나만 지정하면 단일 member cluster에 배포할 수 있다.
다만 그것은 이 문서의 SmartX app catalog/preset 직접 배포와 다른 소유권 경로다.
동일한 TwinX namespace의 Portal을 두 경로로 동시에 활성화하지 않는다.

---

## 4. `isaac-twinx`에서 무엇을 가져오고 무엇을 가져오지 않는가

### 4.1 Helm chart로 변환할 source manifest

| 현재 source | eecs-k8s 대상 | 변환 내용 |
| --- | --- | --- |
| `deploy/minix/rbac.yaml` | `templates/serviceaccount.yaml`, `role.yaml`, `rolebinding.yaml`, `clusterrole.yaml`, `clusterrolebinding.yaml` | 하나의 고정 YAML을 역할별 template로 분리하고 이름/namespace/label을 Helm helper로 바꿈 |
| `deploy/minix/deployment.yaml` | `templates/deployment.yaml` | image, pull secret, auth, DRA, Nucleus, runtime image, WebRTC 설정을 values로 외부화 |
| `deploy/minix/service.yaml` | `templates/service.yaml` | Service type, port, 고정 LB IP, annotation을 values로 외부화 |
| `deploy/minix/namespace.yaml` | 별도 template로 복사하지 않음 | `manifest.yaml`의 `createNamespace: true`와 Application destination namespace 사용 |
| `deploy/minix/kustomization.yaml` | 복사하지 않음 | SmartX가 Helm/Application을 생성하므로 Kustomize entrypoint가 필요 없음 |

### 4.2 컨테이너 이미지 안에 남기는 코드

다음 코드는 chart에 복사하지 않는다.

```text
src/isaac_twinx/api.py
src/isaac_twinx/config.py
src/isaac_twinx/inventory.py
src/isaac_twinx/k8s.py
src/isaac_twinx/resources.py
src/isaac_twinx/service.py
Dockerfile
images/isaac-sim/Dockerfile
images/isaac-sim/entrypoint.sh
images/isaac-sim/extensions.lock.json
scripts/prepare_isaac_extensions.py
```

이유:

- GPU inventory 해석은 Python 애플리케이션 로직이다.
- ResourceClaim/Deployment/Service 생성은 사용자 입력에 따라 동적으로 실행된다.
- Helm은 포털 자체만 설치하고 사용자별 인스턴스를 미리 렌더링하지 않는다.
- Isaac Sim과 Extension 구성은 큰 runtime image의 재현 가능한 build 책임이다.
- chart에는 image reference와 runtime 설정만 둔다.

### 4.3 다시 가져오지 않는 원본 SmartX 기능

다음 기능은 MVP에서 제거한 상태를 유지한다.

```text
Prometheus per-pod metrics 화면
Scenes/history 관리
GPU ban 관리 화면
registry catalog/mirror UI
code-server sidecar
metrics/node-exporter sidecar
workspace PVC 자동 생성
orphan prune 버튼
preview mode
```

이 기능을 chart values만 만들어서 되살리지 않는다. 제품 요구가 생기면 먼저 `ISAAC_UI_MVP_SCOPE.md`를 변경하고 포털 코드·테스트·RBAC를 함께 설계한다.

---

## 5. `eecs-k8s`에 추가할 정확한 파일

```text
eecs-k8s/
├── apps/
│   ├── omniverse-isaac-saas/
│   │   ├── Chart.yaml
│   │   ├── README.md
│   │   ├── manifest.yaml
│   │   ├── patches.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── _helpers.tpl
│   │       ├── serviceaccount.yaml
│   │       ├── role.yaml
│   │       ├── rolebinding.yaml
│   │       ├── clusterrole.yaml
│   │       ├── clusterrolebinding.yaml
│   │       ├── deployment.yaml
│   │       └── service.yaml
│   └── template/
│       └── features.yaml                 # 수정
└── values.yaml                           # 수정
```

이 앱에는 다음 리소스만 렌더링한다.

```text
ServiceAccount
Role
RoleBinding
ClusterRole, inventory 조회가 켜진 경우
ClusterRoleBinding, inventory 조회가 켜진 경우
Deployment, isaac-ui 포털
Service, isaac-ui 포털 진입점
```

사용자별 Isaac Sim Deployment/Service/ResourceClaim은 렌더링 결과에 없어야 한다.

---

## 6. eecs-k8s 파일별 코드와 이유

### 6.1 `apps/omniverse-isaac-saas/Chart.yaml`

역할: Helm이 앱 chart를 식별하도록 한다.

```yaml
apiVersion: v2
name: omniverse-isaac-saas
description: Minimal Kubernetes DRA portal for NVIDIA Isaac Sim
type: application
version: 2.0.0-alpha.2
appVersion: 2.0.0-alpha.2
```

변경 기준:

- chart 구조 자체가 바뀌는 릴리스에서 `version`을 올린다.
- 포털 앱 버전을 추적하려면 `appVersion`을 올린다.
- image tag 대신 digest를 사용하는 것은 cluster patch에서 처리한다.

### 6.2 `apps/omniverse-isaac-saas/manifest.yaml`

역할: SmartX root chart가 이 디렉터리를 어떤 Argo CD Application으로 만들지 결정한다.

필수 형태:

```yaml
appVersion: org.ulagbulag.io/v1alpha1
kind: Manifest
metadata:
  name: smartx.apps.omniverse-isaac-saas
spec:
  group: ops
  phase: alpha
  scale: medium
  app:
    autoPrune: true
    autoSync: true
    namespace: omniverse
    patched: true
    unsafe: false
    useClusterValues: false
    features:
      - org.ulagbulag.io/omniverse/isaac-saas
    sync:
      createNamespace: true
      respectIgnoreDifferences: true
      serverSideApply: true
```

각 필드 이유:

| 필드 | 이유 |
| --- | --- |
| `metadata.name` | SmartX app catalog에서 앱을 유일하게 식별 |
| `group: ops` | 운영 인프라 성격의 포털 |
| `phase: alpha` | GUI WebRTC는 확인했지만 delete/GPU 반환과 실제 조직 클러스터 이관이 남아 있음 |
| `namespace: omniverse` | Nucleus와 같은 서비스 영역을 사용하되 리소스 이름은 분리 |
| `patched: true` | cluster preset의 `patches/omniverse-isaac-saas/values.yaml`을 결합 |
| `autoPrune: true` | chart에서 제거한 포털 리소스를 정리. 포털이 만든 동적 인스턴스는 Argo manifest가 아니므로 prune 대상이 아님 |
| `createNamespace: true` | 별도 Namespace manifest를 복사하지 않음 |
| `serverSideApply: true` | RBAC/Deployment 같은 리소스를 SmartX 기본 sync 방식으로 적용 |

### 6.3 `apps/omniverse-isaac-saas/values.yaml`

역할: 클러스터에 종속되지 않은 안전한 기본값과 입력 schema를 정의한다.

권장 기본 원칙:

```yaml
ui:
  writeEnabled: false
  auth:
    enabled: false
  service:
    type: ClusterIP
    loadBalancerIP: ""

instance:
  image:
    repository: ""
    tag: ""
    digest: ""

dra:
  apiVersion: resource.k8s.io/v1
  driver: gpu.nvidia.com
  deviceClass: gpu.nvidia.com
  migDeviceClass: mig.nvidia.com

nucleus:
  server: ""
  projectPath: Projects/demonstration
  credentialSecret:
    name: nucleus-cred
    userKey: OMNI_USER
    passwordKey: OMNI_PASS
```

왜 기본값을 보수적으로 두는가:

- 공통 chart 단독 설치만으로 외부 mutation endpoint가 열리면 안 된다.
- 실제 Isaac Sim image가 지정되지 않은 상태에서 인스턴스 생성이 성공한 것처럼 보이면 안 된다.
- Nucleus endpoint와 고정 IP는 클러스터마다 다르다.
- Secret 원문이 아니라 Secret 이름과 key만 schema에 둔다.

주요 values 분류:

| values 경로 | 소비 위치 | 의미 |
| --- | --- | --- |
| `ui.image.*` | Deployment | 포털 image |
| `ui.writeEnabled` | `WRITE_ENABLED` | create/delete API 허용 여부 |
| `ui.auth.*` | 포털 환경변수 | 인증 연동 상태와 사용자 표시 |
| `ui.service.*` | Service | 포털 노출 방식 |
| `instance.image.*` | `ISAAC_SIM_IMAGE` | 포털이 생성할 runtime image |
| `instance.imagePullSecrets` | `IMAGE_PULL_SECRETS` | 동적 instance Pod가 사용할 pull Secret |
| `instance.prefix` | `INSTANCE_PREFIX` | 동적 리소스 이름 prefix |
| `instance.dshmSize` | `DSHM_SIZE` | Isaac Sim `/dev/shm` 크기 |
| `instance.streamCommand` | runtime env | Isaac Sim streaming launcher |
| `dra.*` | 포털 환경변수 | ResourceClaim API/driver와 일반 GPU/MIG DeviceClass |
| `nucleus.server` | `OMNI_SERVER` | Isaac Sim이 연결할 Nucleus URI |
| `nucleus.projectPath` | `OMNI_PROJECT_PATH` | Content Browser와 Nucleus 사용 Extension이 조회할 상대 경로 |
| `nucleus.credentialSecret.*` | 포털 환경변수 | 동적 Deployment에 넣을 Secret name/key |
| `webrtc.incompatibleProducts` | inventory 정책 | NVENC가 없는 A100 등을 Launch 불가 표시 |
| `rbac.clusterInventory` | ClusterRole 조건 | cluster-wide Node/ResourceSlice 조회 허용 |

### 6.4 `apps/omniverse-isaac-saas/patches.yaml`

역할: SmartX cluster context에서 계산 가능한 작은 표시값을 chart에 전달한다.

현재 리허설 예:

```yaml
ui:
  auth:
    displayDetail: {{ printf "Cluster %s" .Values.cluster.name | quote }}
```

여기에 image digest, Secret, 고정 IP를 넣지 않는다. 해당 값은 cluster preset의 앱 patch가 소유한다.

### 6.5 `templates/_helpers.tpl`

역할:

- release 이름을 63자 Kubernetes 이름 제한에 맞춤
- 모든 리소스 label 통일
- image `repository:tag`와 `repository@digest` 조합을 한 곳에서 처리

특히 production/runtime image는 digest가 있으면 다음 형태가 우선되어야 한다.

```text
<repository>@sha256:<digest>
```

같은 helper를 Deployment 여러 곳에서 중복 구현하지 않는다.

### 6.6 `templates/serviceaccount.yaml`

역할: 포털 Pod가 Kubernetes API를 호출할 전용 identity를 만든다.

왜 default ServiceAccount를 사용하지 않는가:

- 포털에는 동적 Deployment/Service/ResourceClaim 생성 권한이 필요하다.
- 권한을 앱 전용 ServiceAccount에만 묶어야 한다.
- audit log에서 포털의 API 호출 주체를 구분할 수 있다.

### 6.7 `templates/role.yaml`

역할: `omniverse` namespace 안의 동적 instance 리소스를 관리한다.

필요 권한:

```text
apps/deployments: get, list, create, delete, patch
core/services: get, list, create, delete
core/pods: get, list
resource.k8s.io/resourceclaims: get, list, create, delete
```

넣지 않는 권한:

```text
Secrets get/list/watch
Nodes write
ResourceSlice write
ClusterRole write
wildcard apiGroups/resources/verbs
```

포털은 Secret 값을 읽을 필요가 없다. 포털은 Secret name/key를 동적 Deployment의 `secretKeyRef`에 기록하고 kubelet이 runtime Pod에 주입하게 한다.

### 6.8 `templates/rolebinding.yaml`

역할: namespace Role을 포털 ServiceAccount에 연결한다.

고정 namespace/name을 쓰지 말고 `.Release.Namespace`와 helper 이름을 사용한다.

### 6.9 `templates/clusterrole.yaml`

역할: 전체 클러스터의 GPU inventory를 읽는다.

필요한 읽기 권한:

```text
nodes: list
resource.k8s.io/resourceslices: list
resource.k8s.io/resourceclaims: list
```

`ResourceClaim`을 cluster-wide로 읽는 이유는 다른 namespace가 이미 할당한 GPU도 `Allocated`로 표시하기 위해서다. 이 ClusterRole은 list-only이며 create/delete 권한을 주지 않는다.

### 6.10 `templates/clusterrolebinding.yaml`

역할: inventory ClusterRole을 포털 ServiceAccount에 연결한다.

`rbac.clusterInventory=false`이면 ClusterRole과 ClusterRoleBinding 모두 렌더링하지 않도록 같은 조건을 사용한다.

### 6.11 `templates/deployment.yaml`

역할: `isaac-ui` 포털 자체를 실행하고 values를 환경변수로 전달한다.

반드시 values로 바꿀 항목:

```text
포털 image/tag/digest/pull policy
포털 imagePullSecret
write/auth 상태
Isaac Sim image digest
동적 instance imagePullSecret
DRA API version/driver와 normal/MIG DeviceClass
Nucleus endpoint
Nucleus credential Secret name/key
WebRTC incompatible GPU product
stream command/public endpoint flag
/dev/shm 크기
```

하드코딩해서는 안 되는 것:

```text
특정 클러스터의 LoadBalancer IP
특정 GPU node name
특정 GPU UUID
현재 GPU free/allocated 수
Secret 원문
Nucleus password
```

readiness/liveness는 `/healthz`를 사용한다. `/healthz`는 Kubernetes API가 일시적으로 실패해도 포털 프로세스 생존 여부를 확인할 수 있어야 한다.

### 6.12 `templates/service.yaml`

역할: 포털 HTTP 진입점을 제공한다.

공통 기본값은 `ClusterIP`, 실제 외부 테스트/운영 preset은 `LoadBalancer`로 override한다.

```yaml
ui:
  service:
    type: LoadBalancer
    port: 80
    loadBalancerIP: <PORTAL_RESERVED_IP>
```

인스턴스 WebRTC Service는 이 template이 만들지 않는다. 포털이 인스턴스마다 별도 Service를 생성한다.

---

## 7. feature graph에 넣을 코드

### 7.1 `eecs-k8s/apps/template/features.yaml`

현재 eecs-k8s에는 다음 기반 feature가 이미 존재한다.

```text
nvidia.com/gpu
nvidia.com/gpu/dynamic-resource-allocation
org.ulagbulag.io/omniverse/nucleus
org.ulagbulag.io/registry/container/harbor
```

따라서 새로 추가할 핵심은 다음 하나다.

```yaml
org.ulagbulag.io/omniverse/isaac-saas:
  requires:
    - org.ulagbulag.io/omniverse/nucleus

org.ulagbulag.io/omniverse/isaac-saas/dra:
  requires:
    - org.ulagbulag.io/omniverse/isaac-saas
    - nvidia.com/gpu
    - nvidia.com/gpu/dynamic-resource-allocation
```

왜 base portal과 `isaac-saas/dra`를 분리하는가:

- C에 포털을 먼저 배포하고 DGX Spark GPU capability는 별도로 검증해야 한다.
- legacy `nvidia.com/gpu: 1` fallback은 구현 범위가 아니다.
- DRA가 없으면 GPU 선택/launch만 비활성화하고 웹 health/inventory 상태는 확인할 수 있다.

Nucleus feature 정의는 이미 있으므로 중복 key를 추가하지 않는다.

### 7.2 `eecs-k8s/values.yaml`

SmartX가 feature 이름을 유효한 catalog key로 인식하도록 기본 feature 목록에 등록한다.

```yaml
features:
  # 기존 항목 유지
  - org.ulagbulag.io/omniverse/isaac-saas
```

기존 목록 전체를 재정렬하지 말고 관련 Omniverse 항목 근처에 한 줄만 추가한다.

---

## 8. `<gpu-cluster>-k8s`에 넣을 정확한 파일

> 현재 C 클러스터에는 GPU가 없으므로 `c-k8s`는 Isaac SaaS 활성화 대상이 아니다. 아래 구조는 C preset에도 적용 가능한 형식이지만, 실제 feature 활성화 대상은 GPU/DRA가 검증된 TwinX 또는 별도 GPU 클러스터 preset이다.

```text
<cluster>-k8s/
├── values.yaml                                      # 수정
└── patches/
    └── omniverse-isaac-saas/
        └── values.yaml                              # 추가
```

앱 chart나 Python 코드를 preset repo에 복사하지 않는다.

### 8.1 `<cluster>-k8s/values.yaml`

GPU와 DRA가 준비된 클러스터에서 feature를 활성화한다.

```yaml
features:
  # 기존 cluster feature 유지
  - org.ulagbulag.io/omniverse/isaac-saas
```

feature graph가 Nucleus, Harbor, GPU, DRA 의존성을 계산한다. 다만 dependency feature 활성화가 해당 클러스터의 실제 장치 설치를 대신하지는 않는다. DRA driver와 ResourceSlice는 사전에 정상이어야 한다.

C 클러스터에 GPU가 없다면 이 줄을 넣지 않거나, merge하더라도 실제 C preset 활성화는 보류한다.

### 8.2 `<cluster>-k8s/patches/omniverse-isaac-saas/values.yaml`

다음은 구조 예시다. 실제 Secret 값은 넣지 않는다.

```yaml
fullnameOverride: isaac-twinx

ui:
  image:
    repository: <PORTAL_REGISTRY>/isaac-twinx
    tag: ""
    digest: sha256:<PORTAL_IMAGE_DIGEST>
    pullPolicy: IfNotPresent
  imagePullSecrets:
    - <PORTAL_PULL_SECRET_NAME>
  writeEnabled: false
  auth:
    enabled: false
    displayName: Guest
    displayDetail: Login not connected
  service:
    type: LoadBalancer
    port: 80
    loadBalancerIP: <PORTAL_RESERVED_IP>
    annotations: {}

instance:
  image:
    repository: <HARBOR>/omniverse/isaac-sim
    tag: ""
    digest: sha256:<ISAAC_SIM_IMAGE_DIGEST>
  imagePullSecrets:
    - <HARBOR_PULL_SECRET_NAME>
  prefix: isaac-
  dshmSize: 8Gi
  streamCommand: /isaac-sim/isaac-sim.streaming.sh
  publicEndpointFlag: --/app/livestream/publicEndpointAddress=
  streamIPWaitSeconds: 15

dra:
  apiVersion: resource.k8s.io/v1
  driver: gpu.nvidia.com
  deviceClass: gpu.nvidia.com
  migDeviceClass: mig.nvidia.com

nucleus:
  server: omniverse://<NUCLEUS_LOADBALANCER_IP>/
  projectPath: Projects/demonstration
  credentialSecret:
    name: <NUCLEUS_CREDENTIAL_SECRET_NAME>
    userKey: OMNI_USER
    passwordKey: OMNI_PASS

webrtc:
  incompatibleProducts:
    - A100
```

### 8.3 preset에 넣는 값과 이유

| 값 | preset에 두는 이유 |
| --- | --- |
| 포털 image digest | 배포 버전 고정과 rollback |
| Isaac Sim image digest | 수 GB runtime image의 불변성 보장 |
| pull Secret 이름 | registry와 클러스터마다 이름이 다름 |
| 포털 LB IP | 클러스터 LB pool마다 다름 |
| Nucleus URI | 클러스터/환경마다 endpoint가 다름 |
| Nucleus Secret name/key | credential delivery 방식이 환경마다 다름 |
| DRA API/driver/class | Kubernetes/GPU Operator 구성에 따라 다름 |
| incompatible GPU product | WebRTC/NVENC 정책이 GPU 구성에 따라 다름 |
| auth/write 상태 | 외부 노출과 인증 준비 상태에 따라 다름 |

### 8.4 preset에 절대 넣지 않는 값

```text
GPU node name 목록
GPU UUID 목록
GPU 총 수/가용 수
현재 ResourceClaim 상태
사용자별 instance 목록
WebRTC instance IP 목록
Nucleus password 원문
registry password/token 원문
```

이 값들은 실행 중 변한다. 포털이 Kubernetes API에서 실시간으로 읽어야 한다.

---

## 9. GPU inventory가 자동으로 표시되는 방식

UI Pod가 뜬다고 GPU가 values에서 자동 생성되는 것이 아니다. 다음 API를 읽어서 화면을 계산한다.

```text
core/v1 Nodes
resource.k8s.io/v1 ResourceSlices
resource.k8s.io/v1 ResourceClaims, 모든 namespace
```

계산 흐름:

1. Node Ready/unschedulable 상태를 읽는다.
2. NVIDIA DRA ResourceSlice의 device name, UUID, product, nodeName을 읽는다.
3. 모든 ResourceClaim의 allocation 결과를 읽는다.
4. 이미 claim된 UUID는 `Allocated`, 사용 가능한 UUID는 `Available`로 표시한다.
5. A100처럼 WebRTC에 필요한 NVENC가 없는 product는 정책에 따라 `Incompatible`로 표시한다.
6. 사용자가 선택한 UUID를 exact selector로 ResourceClaim에 넣는다.
7. 선택한 장치가 MIG이면 `mig.nvidia.com`, 일반 GPU이면 `gpu.nvidia.com` DeviceClass를 사용한다.

따라서 preset은 **API를 읽는 방법과 정책만 설정**하고 inventory 데이터 자체는 저장하지 않는다.

필요 RBAC가 빠지면 UI는 하드코딩 목록이 아니라 inventory 오류를 표시해야 한다.

---

## 10. Nucleus와 Isaac Sim image 연결

### 10.1 chart가 하는 일

chart는 포털 Deployment에 다음 정보만 전달한다.

```text
OMNI_SERVER
OMNI_PROJECT_PATH
NUCLEUS_SECRET_NAME
NUCLEUS_USER_KEY
NUCLEUS_PASSWORD_KEY
ISAAC_SIM_IMAGE
```

### 10.2 포털이 하는 일

사용자가 Launch를 누르면 포털은 Isaac Sim Deployment에 다음을 구성한다.

```text
OMNI_SERVER=<preset의 Nucleus URI>
OMNI_PROJECT_PATH=<preset의 Nucleus 상대 경로>
OMNI_USER=valueFrom.secretKeyRef
OMNI_PASS=valueFrom.secretKeyRef
선택 GPU의 DRA ResourceClaim 사용
WebRTC streaming command 실행
```

포털은 Secret 원문을 API 응답이나 UI에 반환하지 않는다.

### 10.3 Isaac Sim image가 하는 일

Isaac Sim image에는 다음이 들어간다.

```text
NVIDIA Isaac Sim 6.0 base runtime
WebRTC/headless launcher
SmartX Extension 9개, lock commit 기준
Extension 등록/검증 entrypoint(자동 활성화 없음)
Nucleus endpoint와 project path를 runtime config/Content Browser에 반영하는 처리
Time Travel 선택 asset은 `NETAI_TIMETRAVEL_ASTRONAUT_USD` runtime env로만 주입
```

Nucleus 주소와 계정 값 자체는 image에 bake하지 않는다. 같은 image를 여러 클러스터에서 재사용하고 preset/Secret만 바꾼다. 공통 image와 생성 extension을 검사해 MiniX `10.34.48.*`, 기존 외부 Nucleus `10.38.38.32` 같은 과거 주소가 없어야 한다.

9개 extension은 image에 포함하고 Kit 검색 경로에 등록하지만 자동 활성화하지 않는다. 각 extension의 backend/asset과 Isaac Sim 6.0 호환성을 확인한 뒤 필요한 것만 활성화한다.

---

## 11. Argo CD와 포털 리소스 소유권

### 11.1 Argo CD가 소유

```text
isaac-ui ServiceAccount
Role/RoleBinding
ClusterRole/ClusterRoleBinding
isaac-ui Deployment
isaac-ui Service
```

### 11.2 포털이 소유

```text
isaac-<instance> Deployment
isaac-<instance>-gpu ResourceClaim
isaac-<instance>-stream Service
```

### 11.3 금지하는 구조

- 사용자별 인스턴스를 `eecs-k8s/templates/`에 넣기
- 포털이 만든 인스턴스와 같은 이름의 manifest를 Git에 넣기
- `tower-k8s`, cluster preset local chart, SmartX app chart 세 곳에 같은 포털 배포하기
- Argo CD resource tracking annotation을 동적 인스턴스에 복사하기

---

## 12. 실제 이관 작업 순서

이 절의 `<cluster>-k8s`는 반드시 GPU/DRA 대상 preset을 의미한다. 현재 GPU가 없는 `c-k8s`에서는 Isaac feature를 켜지 않는다.


### 12.1 시작 전 상태 확인

```bash
git -C eecs-k8s status --short --branch
git -C c-k8s status --short --branch
kubectl version
kubectl api-resources --api-group=resource.k8s.io
kubectl get deviceclass
kubectl get resourceslices
kubectl get resourceclaims -A
kubectl get nodes -o wide
```

중단 조건:

```text
Kubernetes가 v1.34.3이 아님
resource.k8s.io/v1 API가 없음
DeviceClass gpu.nvidia.com 없음
NVIDIA ResourceSlice 없음
대상 registry image pull 경로 미정
Nucleus endpoint/Secret 이름 미정
```

### 12.2 eecs-k8s chart 복사/검토

개인 리허설 chart를 기준으로 다음 디렉터리를 옮긴다.

```text
eecs-k8s/apps/omniverse-isaac-saas/는 현재 개인 working tree에 재사용 가능한 chart가
남아 있지 않으므로, `isaac-twinx` source/deploy와 Nucleus chart precedent를 기준으로 새로 작성한다.
```

새 chart를 작성한 뒤 반드시 검토할 것:

| 항목 | 변경 |
| --- | --- |
| owner metadata | eecs-k8s의 기존 운영 owner 관례로 변경 |
| 기본 portal repository | 조직 registry 정책에 맞게 변경하거나 빈 값으로 보수화 |
| README 링크 | 실제 조직 저장소/런북 링크로 변경 |
| chart version | eecs-k8s 릴리스 규칙과 맞춤 |

그대로 유지할 것:

```text
최소 RBAC verbs
DRA v1 설정 schema
Secret name/key 참조 방식
동적 인스턴스가 chart에 없는 구조
writeEnabled=false 기본값
ClusterIP 기본값
```

### 12.3 feature graph 수정

`apps/template/features.yaml`에 Isaac feature 한 항목을 추가한다. 기존 Nucleus/GPU/DRA/Harbor feature를 수정하거나 중복 선언하지 않는다.

`values.yaml` default feature catalog에도 같은 이름을 추가한다.

### 12.4 cluster preset 수정

1. 대상 cluster의 `values.yaml`에 Isaac feature를 추가한다.
2. `patches/omniverse-isaac-saas/values.yaml`을 추가한다.
3. image는 tag보다 digest를 우선한다.
4. Secret은 이름/key만 참조한다.
5. 외부 인증 전에는 `writeEnabled=false`로 시작한다.
6. 내부 검증용 포털을 별도로 띄울 경우 외부 Service와 ownership이 겹치지 않게 한다.

### 12.5 root SmartX 렌더링

```bash
helm template <cluster> ./eecs-k8s \
  --values ./<cluster>-k8s/values.yaml \
  > /tmp/<cluster>-smartx-render.yaml
```

확인할 것:

```text
<cluster>-omniverse-isaac-saas Application 생성
engine repo URL/revision 정확
preset repo URL/revision 정확
preset valueFiles가 $cluster/patches/omniverse-isaac-saas/values.yaml을 가리킴
destination namespace가 omniverse
```

### 12.6 app chart 단독 렌더링

Secret이 포함될 수 있는 실제 preset은 stdout에 출력하지 않는다.

```bash
umask 077
helm template omniverse-isaac-saas \
  ./eecs-k8s/apps/omniverse-isaac-saas \
  -f ./<cluster>-k8s/patches/omniverse-isaac-saas/values.yaml \
  > /tmp/omniverse-isaac-saas-render.yaml
```

검증 후 삭제한다.

```bash
rm -f /tmp/omniverse-isaac-saas-render.yaml
```

### 12.7 Argo CD 반영

브랜치 기준을 먼저 확인한다.

```text
eecs-k8s: 일반적으로 main
c-k8s: 현재 운영 branch 확인, 기존 기록에서는 ops
twinx-k8s: 해당 root Application targetRevision 확인
```

push 전에 root app이 보는 branch와 정확히 일치해야 한다.

---

## 13. 검증 기준

### 13.1 정적 검증

```bash
helm lint ./eecs-k8s/apps/omniverse-isaac-saas \
  -f ./<cluster>-k8s/patches/omniverse-isaac-saas/values.yaml

git -C eecs-k8s diff --check
git -C <cluster>-k8s diff --check
```

렌더 결과에 있어야 하는 kind:

```text
ServiceAccount
Role
RoleBinding
ClusterRole
ClusterRoleBinding
Deployment
Service
```

렌더 결과에 없어야 하는 것:

```text
사용자별 Isaac Sim Deployment
사용자별 ResourceClaim
사용자별 WebRTC Service
Secret 원문
MiniX 전용 IP, 실제 대상이 MiniX가 아닌 경우
기존 외부 Nucleus IP가 새 cluster preset/image에 남은 값
mutable Isaac Sim latest tag
```

### 13.2 Argo CD/포털 검증

```bash
kubectl -n argocd get application <cluster>-omniverse-isaac-saas -o wide
kubectl -n omniverse get deploy,svc,pod -l app.kubernetes.io/part-of=omniverse -o wide
curl -fsS http://<PORTAL_IP>/healthz
```

### 13.3 GPU inventory 검증

```bash
kubectl get nodes
kubectl get resourceslices
kubectl get resourceclaims -A
curl -fsS http://<PORTAL_IP>/api/gpus
```

UI/API와 Kubernetes 비교:

```text
Node 이름 일치
GPU product 일치
GPU UUID 일치
claim된 GPU는 Allocated
미할당 GPU는 Available
A100은 정책상 Incompatible
```

### 13.4 인스턴스 E2E

인증된 write 경로에서 한 개를 생성한다.

```bash
kubectl -n omniverse get deploy,svc,pod,resourceclaim -o wide
kubectl -n omniverse describe resourceclaim <INSTANCE_CLAIM>
kubectl -n omniverse logs deploy/<INSTANCE> -c isaac-sim --tail=100
```

성공 기준:

```text
선택한 GPU UUID가 claim allocation에 기록
Pod가 선택 GPU가 있는 node에 배치
Isaac Sim Running
WebRTC Service External IP 할당
stream TCP/UDP endpoint 준비
Nucleus URI 설정 확인
각 Pod의 omni.client stat 결과가 Result.OK
Extension lock 9개가 image와 Kit 검색 경로에 등록
과거 cluster IP scan 결과가 0
```

### 13.5 삭제/GPU 반환

```text
포털 Delete
  -> Deployment 삭제
  -> Service 삭제
  -> ResourceClaim 삭제
  -> GPU가 다시 Available
```

검증:

```bash
kubectl -n omniverse get deploy,svc,resourceclaim | grep <INSTANCE> || true
kubectl get resourceclaims -A
curl -fsS http://<PORTAL_IP>/api/gpus
```

---

## 14. Secret 처리

### 14.1 chart에 넣는 것

```text
Secret resource가 아니라 Secret 이름과 key를 받는 schema
```

예:

```yaml
nucleus:
  credentialSecret:
    name: nucleus-cred
    userKey: OMNI_USER
    passwordKey: OMNI_PASS
```

### 14.2 운영 권장

```text
OpenBao/Vault
  -> ExternalSecret
  -> Kubernetes Secret
  -> Isaac Sim Pod secretKeyRef
```

### 14.3 금지

```text
values.yaml에 Nucleus password 원문
Deployment env.value에 password 원문
Docker image ENV에 password 원문
문서/CI log/Helm render를 통한 Secret 출력
```

---

## 15. 롤백

### 15.1 포털 chart 롤백

1. preset의 portal image digest를 이전 digest로 되돌린다.
2. chart 변경이 원인이면 eecs-k8s commit을 revert한다.
3. Argo CD sync 후 `/healthz`와 inventory를 확인한다.

포털 Deployment를 롤백해도 이미 실행 중인 Isaac Sim 인스턴스를 임의로 삭제하지 않는다.

### 15.2 feature 비활성화

cluster preset `values.yaml`에서 Isaac feature를 제거하면 Argo CD가 포털 리소스를 prune할 수 있다.

이 작업 전 반드시 사용자별 인스턴스가 남았는지 확인한다.

```bash
kubectl -n omniverse get deploy,svc,resourceclaim
```

동적 인스턴스 정리 정책이 확정되지 않은 상태에서 포털부터 제거하지 않는다.

### 15.3 runtime image 롤백

새 인스턴스에 사용할 Isaac Sim digest만 이전 값으로 되돌린다. 기존 Running Pod는 재생성 전까지 기존 image를 계속 사용한다.

---

## 16. 실제 eecs-k8s/c-k8s 반영 전 남은 게이트

현재까지 자동 검증된 것:

```text
개인 SmartX chart lint/render
개인 TwinX preset multi-source value path
MiniX에 render 결과 적용
TwinX 포털 health와 일반 GPU/MIG live inventory
L40S index 7과 sv4000-1 A6000 동시 Isaac Sim Running
두 exact DRA allocation과 WebRTC LoadBalancer IP
두 Pod에서 신규 Nucleus omni.client stat Result.OK
Extension 9개 image 포함과 Kit 검색 경로 등록
과거 MiniX/외부 Nucleus IP image/runtime scan 0
포털 Delete HTTP 204
Deployment/Service/ResourceClaim 삭제와 두 GPU Available 반환
```

사람 확인 완료:

```text
MiniX WebRTC 2.0.0 client 영상과 입력
```

실제 이관 전 남은 게이트:

```text
TwinX Stream IP의 GUI 영상/입력 수동 확인
각 필요한 extension의 Isaac Sim 6.0 개별 활성화/기능 확인
실제 eecs-k8s 공통 chart review/render
실제 GPU cluster preset review/render
인증 및 운영 Secret 전달 방식 확정
```

C 클러스터에는 GPU가 없으므로 C에 실제 feature를 켜는 것이 목적이 아니다. 실제 활성화는 GPU/DRA가 검증된 TwinX 또는 별도 GPU 클러스터 preset에서 수행한다.

---

## 17. 작업 완료 체크리스트

### eecs-k8s

- [ ] `apps/omniverse-isaac-saas` chart 추가
- [ ] source manifest의 고정값을 values로 외부화
- [ ] 최소 RBAC 확인
- [ ] Secret read 권한 없음 확인
- [ ] 사용자별 instance resource가 chart에 없음 확인
- [ ] feature graph 추가
- [ ] root `values.yaml` feature 등록
- [ ] Helm lint/render 성공

### cluster preset

- [ ] 실제 GPU/DRA 클러스터인지 확인
- [ ] feature 활성화
- [ ] app patch 추가
- [ ] immutable portal image 지정
- [ ] immutable Isaac Sim image 지정
- [ ] DRA v1 driver/class 지정
- [ ] Nucleus URI와 Secret name/key 지정
- [ ] 포털 LB IP 예약
- [ ] Secret 원문 없음 확인

### live validation

- [ ] Argo CD Synced/Healthy
- [ ] portal `/healthz` 성공
- [ ] GPU inventory가 live API와 일치
- [ ] 정확한 GPU UUID로 instance 생성
- [ ] WebRTC GUI 영상/입력 확인
- [x] TwinX E2E instance 삭제
- [x] TwinX E2E GPU 반환 확인
- [ ] 실행 기록 runbook 업데이트

---

## 18. 한 문장 결론

`isaac-twinx`의 애플리케이션·이미지 코드는 그대로 이미지 저장소에서 관리하고, 포털 자체를 설치하는 최소 Deployment/Service/RBAC만 `eecs-k8s` 공통 chart로 옮기며, image digest·DRA·Nucleus·LoadBalancer·Secret 참조 같은 클러스터별 값만 `<cluster>-k8s/patches/omniverse-isaac-saas/values.yaml`에 두고, GPU 목록과 사용자 인스턴스는 포털이 Kubernetes API에서 실시간으로 관리한다.


## 0C. C GB10 DRA v0.4.1 업그레이드 (2026-07-20)

C 클러스터에서 DRA v25.8.1의 driver root 문제를 `/`로 수정한 뒤에도 GPU kubelet-plugin의 `gpus` 컨테이너가 다음 오류로 CrashLoopBackOff가 되었다.

```text
error enumerating GPUs and MIG devices
error getting memory info for device 0: Not Supported
```

C의 GPU는 NVIDIA GB10이며, GPU Operator/controller/compute-domain은 정상이나 v25.8.1 GPU enumeration 경로가 GB10 NVML memory 정보를 처리하지 못하는 것으로 판단한다. 따라서 NVIDIA가 현재 제공하는 `dra-driver-nvidia-gpu` chart `0.4.1`로 업그레이드한다.

변경 범위:

```text
eecs-k8s/apps/nvidia-gpu-dra/manifest.yaml
  chart: nvidia-dra-driver-gpu -> dra-driver-nvidia-gpu
  version: 25.8.1 -> 0.4.1

eecs-k8s/apps/nvidia-gpu-dra/values.yaml
  nameOverride: nvidia-dra-driver-gpu
  resources.computeDomains.enabled: false

c-k8s/patches/nvidia-gpu-dra/values.yaml
  nameOverride: nvidia-dra-driver-gpu
  nvidiaDriverRoot: /
  resources.computeDomains.enabled: false
  kubeletPlugin.nodeSelector: nvidia.com/gpu.present=true
```

v0.4.1 chart에는 `ComputeDomain`/`ComputeDomainClique` CRD가 포함되어 있으므로 별도 CRD 파일을 복사하지 않는다. `nameOverride`는 v25.x 리소스 이름을 유지하여 업그레이드 중 중복 리소스가 생기지 않게 하기 위한 설정이다.

ComputeDomain은 Isaac Sim의 단일 GPU 할당에 필요하지 않으므로 C 검증에서는 비활성화하고, GPU kubelet-plugin의 `gpus` 컨테이너와 GPU ResourceSlice 생성에 집중한다.
