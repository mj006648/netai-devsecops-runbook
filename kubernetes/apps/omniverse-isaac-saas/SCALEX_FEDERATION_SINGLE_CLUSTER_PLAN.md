# Isaac TwinX ScaleX Federation 단일 클러스터 배포 계획

> 작성일: 2026-07-23
> 상태: 설계 및 이관 계획. 아직 `isaac-twinx`와 `scalex-federation`에 이 구조를 구현하거나 활성화하지 않았다.
> 목표: `isaac-twinx` 포털을 child Helm chart로 만들고, Tower Argo CD와 Karmada를 통해 **하나의 TwinX member cluster에만** 배포한다.

---

## 0. 결론

`scalex-federation`은 여러 클러스터에 반드시 동시에 배포하는 저장소가 아니다.
Karmada `PropagationPolicy`의 `clusterNames`를 하나만 지정하면 중앙 GitOps 경로를
유지하면서 단일 member cluster에만 배포할 수 있다.

이번 목표 구조는 다음과 같다.

```text
isaac-twinx
  └─ Portal source/image/Helm chart/Karmada policy
       │
       │ immutable Git revision
       ▼
scalex-federation
  └─ releases/isaac-twinx
       ├─ release.yaml
       ├─ runtime-values.yaml
       └─ values.yaml
       │
       ▼
Tower Argo CD
  └─ ApplicationSet
       │ Helm render + sync
       ▼
Tower Karmada API
  └─ PropagationPolicy
       │ clusterNames: [<TWINX_KARMADA_CLUSTER_NAME>]
       ▼
TwinX member cluster 한 곳
  └─ isaac-portal
       ├─ GPU/DRA inventory 자동 조회
       └─ 사용자 요청 시 Isaac Sim/ResourceClaim/WebRTC Service 동적 생성
```

핵심 원칙:

```text
Karmada가 관리하는 것:
  Portal Deployment/Service/RBAC와 이를 전파하는 policy

TwinX 내부 Portal이 관리하는 것:
  사용자별 Isaac Sim Deployment
  사용자별 DRA ResourceClaim
  사용자별 WebRTC Service
```

사용자별 Isaac Sim 인스턴스는 Git 또는 Karmada release로 만들지 않는다.

---

## 1. 이 문서의 역할

기존 문서와 역할을 분리한다.

```text
SMARTX_MIGRATION_PLAN.md
  = eecs-k8s 공통 app catalog + c-k8s/twinx-k8s preset 직접 배포 경로

SCALEX_FEDERATION_SINGLE_CLUSTER_PLAN.md
  = isaac-twinx child chart + scalex-federation release + Karmada 단일-target 경로
```

두 경로는 같은 Portal을 배포할 수 있지만 **동일한 live resource를 동시에 소유하면 안 된다.**

예:

```text
허용:
  C cluster Portal      -> eecs-k8s + c-k8s
  TwinX sandbox Portal  -> scalex-federation + Karmada

금지:
  같은 TwinX namespace의 isaac-portal을
    eecs-k8s/twinx-k8s와 scalex-federation이 동시에 관리
```

---

## 2. 확인한 기준 저장소

### 2.1 ScaleX Federation 원본

확인한 원본:

```text
repository: https://github.com/SJoon99/scalex-federation
branch: main
inspected revision: 76021cf
```

현재 원본은 예전의 단순 `federation/*.yaml` 저장소가 아니다.
ScaleX child 기능의 **배포 승인 release catalog** 역할을 한다.

```text
argocd/
  ├─ appproject.yaml
  └─ applicationset.yaml

releases/
  └─ <child>/
      ├─ release.yaml
      ├─ runtime-values.yaml
      └─ values.yaml

docs/
  ├─ child-design-recommendations.md
  ├─ child-design-review.md
  └─ child-values-schema.md
```

### 2.2 현재 로컬 포크 주의

2026-07-23 확인 당시 로컬 저장소:

```text
path: /home/chang/git/scalex-federation
remote: git@github.com:mj006648/scalex-federation.git
branch: default
revision: dd96193
```

이 로컬 포크에는 예전 `federation/kustomization.yaml` 중심 구조가 남아 있다.
따라서 실제 구현을 시작할 때는 이 로컬 브랜치에 바로 파일을 추가하지 않는다.

먼저 해야 할 일:

```text
1. SJoon99/scalex-federation main을 upstream 기준으로 확인
2. 로컬 개인 포크가 upstream main을 추적하도록 정렬
3. 기존 default 브랜치의 과거 구조와 신규 release catalog 구조를 섞지 않음
4. clean branch에서 isaac-twinx release를 작성
```

### 2.3 활성 child 참조 구현

원본에서 현재 활성화된 `temp-poc` release의 흐름을 참조했다.

```text
child repository
  -> chart/templates에 workload와 Karmada policy 포함

scalex-federation/releases/temp-poc
  -> release descriptor와 image identity 제공

ApplicationSet
  -> child chart + Federation values를 조합해 Karmada API에 sync
```

단, 현재 `temp-poc` child 기본 values에는 cluster 이름과 LoadBalancer IP가 남아 있다.
`docs/child-design-recommendations.md`는 이를 Federation의
`runtime-values.yaml`로 옮기는 것을 권장한다.

`isaac-twinx`는 신규 이관이므로 처음부터 권장 경계를 적용한다.

---

## 3. 왜 단일 클러스터에 Federation을 사용하는가

단순 cluster-local 운영만 고려하면 `twinx-k8s` 직접 배포가 더 단순할 수 있다.
이번 경로에서 Federation을 사용하는 이유는 다음과 같다.

```text
1. Tower Argo CD에서 child release를 중앙 승인하고 싶다.
2. 실제 ScaleX Federation child 구조를 데모하고 싶다.
3. 향후 동일 chart를 다른 GPU cluster로 placement할 수 있어야 한다.
4. chart revision과 image digest를 release 단위로 고정하고 싶다.
5. 현재는 TwinX 한 곳에만 배포해 위험과 범위를 제한하고 싶다.
```

즉 다음 두 문장은 동시에 성립한다.

```text
배포 제어 경로는 멀티클러스터 제어 평면인 Karmada를 사용한다.
실제 workload placement는 TwinX 한 곳으로 제한한다.
```

---

## 4. 저장소별 소유권

| 저장소/계층 | 소유하는 것 | 소유하지 않는 것 |
| --- | --- | --- |
| `isaac-twinx` | Portal source, UI, Kubernetes client, Dockerfile, Helm chart, Karmada policy template, chart 기본값, 렌더 검증 | 실제 cluster 이름, LB IP, Secret 원문, 특정 GPU UUID |
| `scalex-federation` | release 활성/비활성, child repo/SHA, namespace, TwinX placement, endpoint/Secret 참조, image promotion 결과 | Python source, Dockerfile, Secret 생성, GPU Operator/DRA 설치 |
| `twinx-k8s` 또는 TwinX cluster-local GitOps | GPU Operator, NVIDIA DRA driver, DeviceClass, LB pool, registry pull Secret, Nucleus credential Secret | Portal source와 Karmada policy 중복 |
| Tower Argo CD | AppProject/ApplicationSet, Karmada destination sync | 사용자별 Isaac Sim 인스턴스 |
| Karmada | Portal/RBAC를 지정 member cluster로 전파 | Portal이 동적으로 만든 사용자 인스턴스의 수명주기 |
| `isaac-portal` | GPU inventory, exact DRA claim, Isaac Sim Deployment, WebRTC Service, 삭제/GPU 반환 | GPU Operator/DRA 설치, Secret 값 조회·출력 |

단일 writer 원칙:

```text
같은 API object는 한 GitOps 경로만 소유한다.
```

---

## 5. 목표 namespace와 리소스 이름

현재 Federation 검증 테스트는 release namespace가 `scalex-`로 시작해야 한다고 강제한다.

권장 값:

```text
release name: isaac-twinx
release namespace: scalex-isaac-twinx
Portal Deployment: isaac-portal
Portal Service: isaac-portal
```

기존 MiniX/TwinX raw manifest의 `omniverse` namespace를 그대로 하드코딩하지 않는다.
Portal 환경변수 `NAMESPACE`에는 Helm `.Release.Namespace`를 주입한다.

결과:

```text
Portal이 실행되는 namespace: scalex-isaac-twinx
Portal이 동적 인스턴스를 생성하는 namespace: scalex-isaac-twinx
```

기존 `omniverse` namespace의 Nucleus 또는 다른 연구자의 workload와 이름 충돌을 줄일 수 있다.

---

## 6. `isaac-twinx`에 추가할 구조

현재 `isaac-twinx`에는 `deploy/minix` Kustomize manifest가 있지만 Federation에서 사용할
Helm chart는 없다.

추가 예정:

```text
isaac-twinx/
├─ chart/
│  ├─ Chart.yaml
│  ├─ values.yaml
│  ├─ values.schema.json
│  └─ templates/
│     ├─ _helpers.tpl
│     ├─ serviceaccount.yaml
│     ├─ role.yaml
│     ├─ rolebinding.yaml
│     ├─ clusterrole.yaml
│     ├─ clusterrolebinding.yaml
│     ├─ deployment.yaml
│     ├─ service.yaml
│     ├─ propagation-policy.yaml
│     ├─ cluster-propagation-policy.yaml
│     └─ override-policy.yaml
└─ scripts/
   └─ validate-render.sh
```

기존 `deploy/minix`는 MiniX 검증 기록으로 유지한다.
Federation chart가 안정화되기 전에는 삭제하지 않는다.

---

## 7. child chart 기본 values

child 기본값에는 특정 TwinX cluster 이름, LB IP, Nucleus IP를 넣지 않는다.

예시:

```yaml
nameOverride: ""
fullnameOverride: ""

images:
  portal:
    repository: ghcr.io/mj006648/isaac-twinx
    tag: main
    pullPolicy: IfNotPresent

portal:
  replicas: 1
  writeEnabled: false
  service:
    port: 80
    exposure: internal
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: "1"
      memory: 512Mi

instanceImages:
  amd64: ""
  arm64: ""

imagePullSecrets: []

dra:
  apiVersion: resource.k8s.io/v1
  driver: gpu.nvidia.com
  deviceClass: gpu.nvidia.com
  migDeviceClass: mig.nvidia.com
  incompatibleProducts:
    - A100

nucleus:
  server: ""
  projectPath: Projects/demonstration
  secretName: nucleus-cred
  userKey: OMNI_USER
  passwordKey: OMNI_PASS

stream:
  initializationSeconds: 120
  dshmSize: 8Gi
  arm64:
    startXvfb: false
    hostNetwork: true

karmada:
  enabled: false
  placement:
    cluster: ""
  portalService:
    exposure: internal
    loadBalancerIP: ""
    annotationKey: ""
```

기본 `karmada.enabled=false`는 로컬 Helm render와 직접 배포 경로를 유지하기 위한 값이다.
Federation의 `runtime-values.yaml`에서만 `true`로 덮어쓴다.

---

## 8. child chart가 렌더할 Kubernetes 리소스

### 8.1 ServiceAccount

```text
Portal Pod가 member cluster의 in-cluster Kubernetes API를 사용한다.
```

### 8.2 namespace Role/RoleBinding

필요 권한:

```text
apps/deployments:
  get, list, create, delete, patch

core/services:
  get, list, create, delete

core/pods:
  get, list

resource.k8s.io/resourceclaims:
  get, list, create, delete
```

Portal이 사용자 요청에 따라 같은 namespace에 Isaac Sim 리소스를 생성하고 삭제하기 위한 권한이다.

### 8.3 ClusterRole/ClusterRoleBinding

필요 권한:

```text
core/nodes:
  list

resource.k8s.io/resourceslices:
  list

resource.k8s.io/resourceclaims:
  list
```

이 권한은 다음 용도다.

```text
Node architecture/Ready/cordon 상태 확인
NVIDIA DRA GPU/MIG inventory 확인
다른 namespace에서 이미 할당한 GPU까지 확인
```

GPU UUID와 노드명을 values에 하드코딩하지 않는다.

### 8.4 Portal Deployment

현재 `deploy/minix/deployment.yaml`의 하드코딩 값을 모두 values로 외부화한다.

```text
Portal image
namespace
write/auth mode
amd64/arm64 Isaac Sim image
imagePullSecret 이름
DRA API/driver/device class
WebRTC 비호환 제품
Nucleus endpoint
Nucleus Secret 이름/key
stream initialization 시간
arm64 hostNetwork/Xvfb 설정
```

### 8.5 Portal Service

child base Service는 `ClusterIP`를 기본으로 한다.
member cluster의 LoadBalancer 노출은 `OverridePolicy`가 적용한다.

이렇게 하면 cluster-local 네트워크 설정이 base workload에 섞이지 않는다.

---

## 9. Karmada policy 설계

### 9.1 namespaced 리소스용 `PropagationPolicy`

대상:

```text
ServiceAccount
Role
RoleBinding
Deployment
Service
```

개념 예시:

```yaml
apiVersion: policy.karmada.io/v1alpha1
kind: PropagationPolicy
metadata:
  name: isaac-portal
spec:
  conflictResolution: Abort
  preemption: Never
  propagateDeps: true
  resourceSelectors:
    - apiVersion: v1
      kind: ServiceAccount
      name: isaac-portal
      namespace: {{ .Release.Namespace }}
    - apiVersion: rbac.authorization.k8s.io/v1
      kind: Role
      name: isaac-portal
      namespace: {{ .Release.Namespace }}
    - apiVersion: rbac.authorization.k8s.io/v1
      kind: RoleBinding
      name: isaac-portal
      namespace: {{ .Release.Namespace }}
    - apiVersion: apps/v1
      kind: Deployment
      name: isaac-portal
      namespace: {{ .Release.Namespace }}
    - apiVersion: v1
      kind: Service
      name: isaac-portal
      namespace: {{ .Release.Namespace }}
  placement:
    clusterAffinity:
      clusterNames:
        - {{ required "karmada.placement.cluster is required" .Values.karmada.placement.cluster }}
    spreadConstraints:
      - spreadByField: cluster
        minGroups: 1
        maxGroups: 1
```

`required`를 사용해 target cluster가 없으면 Helm render가 실패하게 한다.

### 9.2 cluster-scoped RBAC용 `ClusterPropagationPolicy`

대상:

```text
ClusterRole
ClusterRoleBinding
```

`Role`만으로는 cluster-scoped `Node`와 `ResourceSlice`를 조회할 수 없기 때문에 제거할 수 없다.

개념 예시:

```yaml
apiVersion: policy.karmada.io/v1alpha1
kind: ClusterPropagationPolicy
metadata:
  name: isaac-portal-inventory
spec:
  resourceSelectors:
    - apiVersion: rbac.authorization.k8s.io/v1
      kind: ClusterRole
      name: isaac-portal-inventory
    - apiVersion: rbac.authorization.k8s.io/v1
      kind: ClusterRoleBinding
      name: isaac-portal-inventory
  placement:
    clusterAffinity:
      clusterNames:
        - {{ required "karmada.placement.cluster is required" .Values.karmada.placement.cluster }}
```

ClusterRole 이름은 다른 child와 충돌하지 않도록 release 기반으로 생성한다.

### 9.3 Portal Service용 `OverridePolicy`

base Service:

```yaml
spec:
  type: ClusterIP
```

TwinX override:

```text
type: LoadBalancer
TwinX에서 사용하는 LB IPAM annotation 적용
```

중요:

```text
spec.loadBalancerIP
metallb.io/loadBalancerIPs
lbipam.cilium.io/ips
```

이 세 방식을 동시에 섞지 않는다.
대상 TwinX가 실제 사용하는 한 가지 방식만 `runtime-values.yaml`에서 선택한다.

예를 들어 Cilium LB IPAM을 사용하면:

```yaml
karmada:
  portalService:
    exposure: member-lb
    loadBalancerIP: <TWINX_PORTAL_IP>
    annotationKey: lbipam.cilium.io/ips
```

---

## 10. `scalex-federation`에 추가할 release

추가 예정:

```text
scalex-federation/
└─ releases/
   └─ isaac-twinx/
      ├─ release.yaml
      ├─ runtime-values.yaml
      └─ values.yaml
```

### 10.1 `release.yaml`

초기 등록 예시:

```yaml
name: isaac-twinx
namespace: scalex-isaac-twinx
state: disabled
disabledReason: >-
  The child Helm chart, immutable portal image, and TwinX placement have not
  completed render and live validation.
renderer: helm/v1
source:
  repoURL: https://github.com/mj006648/isaac-twinx.git
  path: chart
  revision: <ISAAC_TWINX_FULL_40_CHARACTER_GIT_SHA>
values:
  path: releases/isaac-twinx/values.yaml
promotion:
  mode: pinned
requiredKinds:
  - ClusterRole
  - ClusterRoleBinding
  - ClusterPropagationPolicy
```

처음부터 `active`로 만들지 않는다.

활성화 조건:

```text
Helm lint 통과
Helm render 통과
Federation contract test 통과
Portal image digest 확정
target cluster 이름 확인
TwinX GPU/DRA 준비 확인
Secret 이름/key 확인
LB IP 충돌 없음 확인
```

### 10.2 `runtime-values.yaml`

사람이 관리하는 TwinX 환경 값:

```yaml
karmada:
  enabled: true
  placement:
    cluster: <TWINX_KARMADA_CLUSTER_NAME>
  portalService:
    exposure: member-lb
    loadBalancerIP: <TWINX_PORTAL_IP>
    annotationKey: <TWINX_LB_IPAM_ANNOTATION>

portal:
  writeEnabled: true

instanceImages:
  amd64: <AMD64_ISAAC_SIM_REPOSITORY>@sha256:<DIGEST>
  arm64: <ARM64_ISAAC_SIM_REPOSITORY>@sha256:<DIGEST>

imagePullSecrets:
  - harbor-regcred

dra:
  apiVersion: resource.k8s.io/v1
  driver: gpu.nvidia.com
  deviceClass: gpu.nvidia.com
  migDeviceClass: mig.nvidia.com
  incompatibleProducts:
    - A100

nucleus:
  server: omniverse://<TWINX_NUCLEUS_ENDPOINT>/
  projectPath: Projects/demonstration
  secretName: nucleus-cred
  userKey: OMNI_USER
  passwordKey: OMNI_PASS

stream:
  initializationSeconds: 120
  arm64:
    startXvfb: false
    hostNetwork: true
```

이 파일에 넣지 않는 것:

```text
Nucleus password
Harbor password/token
GPU UUID
GPU index
특정 GPU 노드 목록
Portal image의 generated digest identity
```

### 10.3 `values.yaml`

이 파일은 promotion이 관리하는 Portal image identity만 가진다.

```yaml
images:
  portal:
    repository: <HARBOR>/omniverse/isaac-twinx
    tag: sha-<FULL_GIT_SHA>
    pullPolicy: IfNotPresent
    digest: sha256:<PORTAL_IMAGE_DIGEST>
    sourceRevision: <FULL_GIT_SHA>
```

Federation contract:

```text
values.yaml의 top-level key는 images만 허용
runtime-values.yaml에는 images key 금지
active release는 40자 Git SHA 필요
image sourceRevision과 chart effective revision이 같아야 함
digest는 sha256:<64hex> 형식
```

### 10.4 AppProject

`argocd/appproject.yaml`의 `sourceRepos`에 추가:

```yaml
- https://github.com/mj006648/isaac-twinx.git
```

현재 AppProject는 다음 필요한 kind를 이미 허용한다.

```text
ServiceAccount
Service
Deployment
Role
RoleBinding
PropagationPolicy
OverridePolicy
ClusterPropagationPolicy
ClusterRole
ClusterRoleBinding
```

현재 기준으로 새로운 kind를 선제 개방하지 않는다.

### 10.5 ApplicationSet

`argocd/applicationset.yaml`은 수정하지 않는다.

현재 generator:

```yaml
files:
  - path: releases/*/release.yaml
```

`state: active` release를 자동 발견한다.

---

## 11. image 계약

### 11.1 Portal image

Portal image는 `isaac-twinx` chart와 동일한 Git revision에서 생성해야 한다.

```text
chart source revision
  == release effective revision
  == images.portal.sourceRevision
```

실제 Deployment image는 tag보다 digest를 우선한다.

```text
<repository>@sha256:<digest>
```

### 11.2 Isaac Sim runtime image

Portal은 사용자 Launch 시 다음 image 중 하나를 선택한다.

```text
amd64 NVIDIA GPU node -> instanceImages.amd64
arm64 DGX Spark/GB10 -> instanceImages.arm64
```

Isaac Sim runtime image는 Portal image와 빌드/용량/승격 주기가 다르다.
따라서 Federation generated `images.portal`과 분리해
`runtime-values.yaml`의 `instanceImages`로 주입한다.

두 이미지 모두 mutable tag가 아니라 digest로 고정한다.

---

## 12. Secret과 dependency 경계

child chart와 Federation release는 Secret을 생성하지 않는다.

TwinX member cluster의 `scalex-isaac-twinx` namespace에 미리 준비할 것:

```text
nucleus-cred
  keys:
    OMNI_USER
    OMNI_PASS

harbor-regcred
  type:
    kubernetes.io/dockerconfigjson
```

중요:

```text
Secret 이름과 key 이름은 Git에 기록 가능
Secret 값은 Git, Helm render 출력, 응답에 기록 금지
```

Portal은 Nucleus Secret 값을 API로 읽지 않는다.
생성하는 Isaac Sim Deployment에 `secretKeyRef`만 작성한다.

cluster-local dependency:

```text
NVIDIA GPU Operator
NVIDIA DRA driver
DeviceClass gpu.nvidia.com
필요 시 DeviceClass mig.nvidia.com
ResourceSlice
LoadBalancer/IPAM
Nucleus
registry pull credential
```

이 dependency들은 Federation child chart가 설치하지 않는다.

---

## 13. 실제 실행 흐름

### 13.1 Portal 배포

```text
1. isaac-twinx chart revision 확정
2. scalex-federation release를 active로 변경
3. Tower Argo CD ApplicationSet이 federation-isaac-twinx 생성
4. child chart + runtime-values + generated values 병합
5. Karmada API에 Portal/RBAC/policy 생성
6. PropagationPolicy가 TwinX 한 곳 선택
7. TwinX에 isaac-portal Pod와 Service 생성
```

### 13.2 GPU inventory

Portal은 실행된 member cluster의 in-cluster API를 사용한다.

```text
Node
ResourceSlice
ResourceClaim
Deployment
Pod
Service
```

따라서 Federation values에 노드명, GPU 제품, UUID 목록을 넣지 않아도 된다.

### 13.3 사용자 Launch

```text
1. 사용자가 Portal에서 GPU 선택
2. Portal이 정확한 GPU UUID를 지정한 ResourceClaim 생성
3. 선택 GPU 노드 affinity를 가진 Isaac Sim Deployment 생성
4. amd64/arm64 image 자동 선택
5. WebRTC Service 또는 arm64 hostNetwork 구성
6. Nucleus endpoint와 Secret 참조 주입
7. Initializing 후 Stream IP 표시
```

이 리소스는 TwinX member API에 직접 생성된다.
Karmada policy 대상으로 다시 넣지 않는다.

### 13.4 Delete

```text
Portal Delete
  -> Isaac Sim Deployment 삭제
  -> WebRTC Service 삭제
  -> ResourceClaim 삭제
  -> GPU Available 반환
```

---

## 14. 구현 및 승인 순서

### Gate 0 — target 확정

읽기 전용 확인:

```bash
kubectl --context karmada get clusters
kubectl --context <TWINX_CONTEXT> get nodes -o wide
kubectl --context <TWINX_CONTEXT> get deviceclass
kubectl --context <TWINX_CONTEXT> get resourceslices
kubectl --context <TWINX_CONTEXT> -n scalex-isaac-twinx get secret
```

확정할 값:

```text
Karmada의 정확한 member cluster 이름
namespace 준비 방식
Portal LoadBalancer IP
사용하는 LB IPAM 종류
Nucleus endpoint
Secret 이름/key
Portal/Isaac Sim image digest
```

### Gate 1 — 로컬 child chart 작성

수정 대상:

```text
isaac-twinx/chart/**
isaac-twinx/scripts/validate-render.sh
```

이 단계에서는 push와 live sync를 하지 않는다.

### Gate 2 — child chart 검증

```bash
helm lint --strict chart

helm template isaac-twinx chart \
  --namespace scalex-isaac-twinx \
  -f /tmp/isaac-twinx-runtime-values.yaml \
  -f /tmp/isaac-twinx-generated-values.yaml \
  > /tmp/isaac-twinx-rendered.yaml
```

검증 후 Secret 참조가 포함된 임시 render는 삭제한다.

### Gate 3 — `isaac-twinx` push와 image build

```text
chart commit
Portal image sourceRevision
Portal image digest
```

세 값의 일치를 확인한다.

### Gate 4 — Federation disabled release 작성

수정 대상:

```text
scalex-federation/releases/isaac-twinx/release.yaml
scalex-federation/releases/isaac-twinx/runtime-values.yaml
scalex-federation/releases/isaac-twinx/values.yaml
scalex-federation/argocd/appproject.yaml
```

초기 상태:

```yaml
state: disabled
```

### Gate 5 — Federation 계약 검증

```bash
python3 tests/test_promotion_contract.py
```

추가 정적 확인:

```text
active 전 full Git SHA 확인
sourceRepos 허용 확인
requiredKinds와 AppProject whitelist 확인
runtime-values에 images 없음
generated values에 images 외 top-level key 없음
```

### Gate 6 — 사용자 승인 후 active

```yaml
state: active
```

이 변경부터 실제 Argo/Karmada 배포가 발생할 수 있다.

### Gate 7 — Tower Argo sync

확인:

```text
Application: federation-isaac-twinx
destination: karmada
namespace: scalex-isaac-twinx
source revision: 승인한 40자 SHA
```

### Gate 8 — live 검증

Karmada:

```bash
kubectl --context karmada -n scalex-isaac-twinx get \
  deploy,svc,sa,role,rolebinding,propagationpolicy,overridepolicy

kubectl --context karmada get \
  clusterrole,clusterrolebinding,clusterpropagationpolicy | grep isaac
```

TwinX:

```bash
kubectl --context <TWINX_CONTEXT> -n scalex-isaac-twinx get \
  deploy,svc,pod -o wide
```

Portal API:

```bash
curl -fsS http://<PORTAL_IP>/healthz
curl -fsS http://<PORTAL_IP>/api/gpus
```

사용자 Launch 후:

```bash
kubectl --context <TWINX_CONTEXT> -n scalex-isaac-twinx get \
  deploy,svc,pod,resourceclaim -l app.kubernetes.io/managed-by=isaac-twinx
```

---

## 15. 합격 기준

### Git/Helm

```text
isaac-twinx chart가 cluster IP/Secret/GPU UUID를 하드코딩하지 않음
Helm lint 통과
Helm template 통과
Federation contract test 통과
Portal image digest와 chart revision 일치
```

### Karmada

```text
target cluster가 정확히 TwinX 한 곳
Portal namespaced resource가 TwinX에만 존재
ClusterRole/Binding이 TwinX에 전파
다른 member cluster에 Portal이 생성되지 않음
```

### Portal

```text
Portal Pod Ready
healthz 정상
GPU/MIG inventory 자동 조회
노드/GPU UUID 하드코딩 없음
```

### Isaac Sim E2E

```text
exact DRA GPU 선택
ResourceClaim Allocated
선택 GPU가 있는 노드에 Pod 배치
amd64/arm64 image 자동 선택
WebRTC 연결
Nucleus 연결
Delete 후 Deployment/Service/ResourceClaim 삭제
GPU Available 반환
```

---

## 16. 롤백

### 16.1 release 비활성화

```yaml
state: disabled
```

ApplicationSet 대상에서 제외하고 Portal/RBAC/Karmada policy를 제거하는 기본 롤백이다.

주의:

```text
Portal이 생성한 사용자 Isaac Sim 인스턴스는 member cluster에 직접 생성된다.
Portal release를 제거하기 전에 남은 인스턴스를 확인하고 필요한 경우 Portal을 통해 삭제한다.
```

### 16.2 revision 롤백

이전 검증 SHA와 image digest로 되돌린다.

```text
release source.revision
values.yaml images.portal.sourceRevision
values.yaml images.portal.digest
```

세 값을 같은 성공 revision으로 맞춘다.

### 16.3 placement 롤백

잘못된 member cluster 이름이 입력됐으면 active 상태에서 임의 cluster로 바꾸지 않는다.

```text
1. release disabled
2. 기존 Karmada binding/target 상태 확인
3. runtime-values의 cluster 이름 수정
4. render/contract 검증
5. 다시 active
```

---

## 17. 주요 위험과 대응

| 위험 | 결과 | 대응 |
| --- | --- | --- |
| 로컬 과거 Federation 구조에 신규 파일 추가 | upstream main과 완전히 다른 배포 경로 생성 | 구현 전 포크를 SJoon99/main 기준으로 정렬 |
| eecs/twinx direct app과 Federation이 같은 Portal 소유 | Argo prune/self-heal 충돌 | 한 cluster/namespace/resource당 writer 하나 |
| target cluster 이름 오타 | workload 미전파 또는 잘못된 cluster 배치 | `required` 렌더 + `kubectl get clusters` 실측 |
| `omniverse` namespace 하드코딩 | 기존 Nucleus/연구자 workload와 충돌 | `scalex-isaac-twinx`, `.Release.Namespace` 사용 |
| Secret을 child chart에 포함 | credential 노출 | cluster-local Secret, chart는 name/key 참조만 |
| LB IPAM 방식 혼합 | Service IP 할당 실패 | Cilium/MetalLB/spec 방식 중 정확히 하나만 사용 |
| Portal과 chart image revision 불일치 | 재현 불가능, contract 실패 | Git SHA/image sourceRevision/digest 동시 고정 |
| user instance를 Karmada가 관리 | Portal delete와 Argo/Karmada 충돌 | 동적 instance는 member Portal만 관리 |
| ClusterRole 전파 누락 | GPU inventory API 403 | ClusterPropagationPolicy와 requiredKinds 검증 |
| target에 DRA 없음 | GPU 목록 없음, Launch 실패 | 활성화 전 DeviceClass/ResourceSlice 확인 |

---

## 18. 현재 하지 않는 것

이 문서 작성 시점에는 다음을 수행하지 않았다.

```text
isaac-twinx chart 생성
scalex-federation 포크 rebase
release.yaml 작성
AppProject 변경
Git commit/push
Argo CD sync
Karmada resource 생성
TwinX live resource 변경
```

또한 `docs/child-design-recommendations.md`의 `scalex.yaml`은 현재 필수 계약이 아니라
향후 구조 개선 제안이다. 이번 첫 Federation 이관에서 필수로 도입하지 않는다.

---

## 19. 구현 시 변경 파일 체크리스트

### `isaac-twinx`

```text
[ ] chart/Chart.yaml
[ ] chart/values.yaml
[ ] chart/values.schema.json
[ ] chart/templates/_helpers.tpl
[ ] chart/templates/serviceaccount.yaml
[ ] chart/templates/role.yaml
[ ] chart/templates/rolebinding.yaml
[ ] chart/templates/clusterrole.yaml
[ ] chart/templates/clusterrolebinding.yaml
[ ] chart/templates/deployment.yaml
[ ] chart/templates/service.yaml
[ ] chart/templates/propagation-policy.yaml
[ ] chart/templates/cluster-propagation-policy.yaml
[ ] chart/templates/override-policy.yaml
[ ] scripts/validate-render.sh
```

### `scalex-federation`

```text
[ ] releases/isaac-twinx/release.yaml
[ ] releases/isaac-twinx/runtime-values.yaml
[ ] releases/isaac-twinx/values.yaml
[ ] argocd/appproject.yaml sourceRepos
[ ] tests/test_promotion_contract.py 통과
```

### TwinX cluster-local prerequisite

```text
[ ] NVIDIA GPU Operator
[ ] NVIDIA DRA driver
[ ] DeviceClass
[ ] ResourceSlice
[ ] LoadBalancer IP pool
[ ] scalex-isaac-twinx/nucleus-cred
[ ] scalex-isaac-twinx/harbor-regcred
[ ] Nucleus endpoint
```

---

## 20. 참고

- `https://github.com/SJoon99/scalex-federation/blob/main/README.md`
- `https://github.com/SJoon99/scalex-federation/blob/main/argocd/applicationset.yaml`
- `https://github.com/SJoon99/scalex-federation/blob/main/argocd/appproject.yaml`
- `https://github.com/SJoon99/scalex-federation/blob/main/releases/README.md`
- `https://github.com/SJoon99/scalex-federation/blob/main/docs/child-design-recommendations.md`
- `https://github.com/SJoon99/scalex-federation/blob/main/docs/child-values-schema.md`
- `https://github.com/SJoon99/scalex-federation/blob/main/tests/test_promotion_contract.py`
- `https://github.com/mj006648/isaac-twinx`

---

## 21. 한 문장 결론

`isaac-twinx`가 Portal Helm chart와 Karmada policy를 소유하고,
`scalex-federation`이 승인한 revision·TwinX placement·runtime values를 제공하며,
Tower Argo CD와 Karmada가 Portal만 TwinX 한 곳에 전파하고 사용자별 Isaac Sim은
member cluster의 Portal이 직접 관리하는 구조로 이관한다.
