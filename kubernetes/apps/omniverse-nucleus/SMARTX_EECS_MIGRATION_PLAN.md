# Omniverse Nucleus SmartX/eecs-k8s 이관 계획

> 위치: 이 문서는 **외부 작업 레포가 아니라** `mj006648/netai-devsecops-runbook` 아래에 둔다.
> 현재 상태: **이관과 C 클러스터 배포까지 완료**했다. 이 문서는 이후 동일 작업을 재현하거나 값을 변경할 때 사용하는 구현 가이드다.
> 완료 증거: [`SMARTX_EECS_EXECUTION.md`](./SMARTX_EECS_EXECUTION.md)에 eecs-k8s/c-k8s commit, Helm render, C 클러스터 12/12 Ready, PVC Bound, LoadBalancer, Navigator HTTP 200 결과를 기록했다.

## 0. 결론

실제 이관은 다음 구조로 완료했고, 이후 재현/변경도 같은 소유권 경계를 사용한다.

```text
내 런북
  netai-devsecops-runbook/kubernetes/apps/omniverse-nucleus/
    └── SMARTX_EECS_MIGRATION_PLAN.md   # 계획/작업 기록

SmartX 엔진 레포
  eecs-k8s
    └── apps/omniverse-nucleus/          # 실제 앱 카탈로그 추가 대상

C 클러스터 preset 레포
  c-k8s
    ├── values.yaml                      # feature 활성화
    └── patches/omniverse-nucleus/       # C 클러스터 전용 override

Tower preset 레포
  tower-k8s
    └── 이번 Nucleus 앱 manifest는 넣지 않음
```

핵심은 **공통 앱 정의는 `eecs-k8s`에 넣고**, C 클러스터에서 다른 값만 **`c-k8s` patch로 주입**하는 것이다.

즉, `c-k8s/apps/omniverse-nucleus` 같은 cluster-local 앱으로 먼저 만들지 않는다. SmartX/mobilex 방식에 맞춰 **engine app catalog + preset patch** 구조로 간다.

## 1. 레포별 역할

| 레포 | 역할 | 이번 작업 여부 |
| --- | --- | --- |
| `netai-devsecops-runbook` | 계획, 실험 결과, 재현 절차 기록 | 문서 추가 |
| `eecs-k8s` | SmartX식 공통 엔진/app catalog | `apps/omniverse-nucleus` 추가 |
| `c-k8s` | C 클러스터 preset. feature 선택과 patch만 관리 | `values.yaml`, `patches/omniverse-nucleus/values.yaml` 수정 |
| `tower-k8s` | Tower Argo CD가 root app들을 관리하는 preset | Nucleus manifest 직접 추가하지 않음 |

## 2. 현재 확인한 환경

### C 클러스터

```text
API endpoint: https://10.33.201.181:6443
Kubernetes: v1.34.3
노드: 3대
```

### C 클러스터 StorageClass

현재 확인된 StorageClass:

```text
ceph-block
ceph-block-noreplicas
ceph-filesystem
ceph-filesystem-noreplicas
nfs-csi
```

1차 적용은 대상 C 클러스터의 현재 설정에 맞춰 다음을 사용한다.

```text
storageClassName: ceph-block-noreplicas
```

나중에 운영 안정화 단계에서 Nucleus 전용 Retain StorageClass를 추가한다.

```text
예상 이름: rook-ceph-block-nucleus-retain
reclaimPolicy: Retain
```

### C 클러스터 LoadBalancer IP Pool

현재 Cilium LB IPAM pool:

```text
pool: c-lb-pool
range: 10.33.143.1 - 10.33.143.254
```

Nucleus는 고정 IP로 시작한다.

```text
1차 검증 완료 IP: 10.33.143.10
```

예약 IP 정책이 변경되면 c-k8s patch와 검증 기록을 함께 갱신한다.

### Argo CD

Tower Argo CD가 C 클러스터 root app을 관리한다.

```text
Argo CD: 10.34.25.17
cluster name: c
project: c-ops
```

실제 완료된 branch/commit 기준:

```text
eecs-k8s/main
  3bbfdde feat: add omniverse nucleus app
  4c1ab24 fix: align nucleus secret keys

c-k8s/main
  1042776 feat: enable omniverse nucleus
```

초기 작업에서는 `c-k8s/ops`에도 같은 내용을 push한 뒤 `main`으로 fast-forward했다. 현재 완료 상태의 기준은 `c-k8s/main`이다. 재적용할 때는 추측하지 말고 Tower Argo CD root Application의 `targetRevision`을 다시 확인한다.

## 3. 구현할 구조와 파일별 코드 매핑

이 절은 MiniX에서 검증한 고정 Kubernetes manifest를 `eecs-k8s` 공통 chart와 `c-k8s` cluster patch로 나누는 실제 기준이다.

### 3.1 원본 manifest → eecs-k8s chart 매핑

원본 기준:

```text
netai-devsecops-runbook/kubernetes/apps/omniverse-nucleus/manifests/nucleus/
├── 00-namespace.yaml
├── 00-storageclass.yaml
├── 10-headless-service.yaml
├── 10-internal-services.yaml
├── 10-loadbalancer-service.yaml
└── 20-statefulset.yaml
```

변환 결과:

| 원본 manifest | eecs-k8s 대상 | 무엇을 바꾸는가 | 왜 그렇게 나누는가 |
| --- | --- | --- | --- |
| `00-namespace.yaml` | `templates/namespace.yaml` | `omniverse` 고정 namespace를 helper/values로 처리 | chart release namespace와 SmartX destination을 일치시키기 위해 |
| `00-storageclass.yaml` | Nucleus app chart에 직접 복사하지 않음 | `values.yaml`/preset에서 기존 StorageClass 이름만 참조 | StorageClass는 Ceph/CSI 인프라 소유 리소스이며 앱마다 중복 생성하면 안 됨 |
| `10-headless-service.yaml` | `templates/service-headless.yaml` | name/namespace/labels를 helper로 통일 | StatefulSet의 안정적인 Pod DNS와 serviceName 유지 |
| `10-internal-services.yaml` | `templates/service-internal.yaml` | 11개 Compose DNS Service를 한 template 파일로 유지 | Nucleus 컨테이너가 기대하는 service name/port 관계를 보존 |
| `10-loadbalancer-service.yaml` | `templates/service-loadbalancer.yaml` | type, LB IP, annotations, external host를 values화 | 클러스터마다 LB pool과 예약 IP가 다름 |
| `20-statefulset.yaml` | `templates/statefulset.yaml` | image, Secret 이름, storage, scheduling, external host를 values화 | 12개 컨테이너의 공통 구조는 engine에 두고 환경 차이만 preset으로 분리 |
| 수동 생성한 image pull/Nucleus runtime Secret | `templates/secrets.yaml` 또는 외부 ExternalSecret | `create` 조건과 Secret 이름/참조 schema만 공통화 | PoC와 운영 Secret 전달 방식을 분리하고 원문 노출을 막기 위해 |
| 해당 없음 | `templates/_helpers.tpl` | 이름, namespace, labels, external host 계산 helper 추가 | 여러 template의 문자열 조합 중복 제거 |
| 해당 없음 | `Chart.yaml` | Helm chart metadata 추가 | SmartX Application이 앱을 Helm source로 렌더링하기 위해 |
| 해당 없음 | `manifest.yaml` | SmartX app metadata/feature/patch/sync 정책 추가 | root chart가 `c-omniverse-nucleus` Application을 생성하기 위해 |
| 고정값 전체 | `values.yaml` | 공통 기본값과 입력 schema로 이동 | chart 재사용성과 cluster patch 경계 확보 |

중요:

```text
00-storageclass.yaml을 apps/omniverse-nucleus/templates/storageclass.yaml로 기계적으로 복사하지 않는다.
```

Nucleus 전용 Retain StorageClass가 필요하면 Ceph/storage app 또는 해당 클러스터 인프라 preset이 한 번만 생성한다. Nucleus app은 다음 값으로 이미 존재하는 class를 참조한다.

```yaml
nucleus:
  storage:
    className: <EXISTING_STORAGE_CLASS>
```

### 3.2 실제 eecs-k8s 앱 카탈로그 파일

현재 구현 기준 파일은 다음과 같다.

```text
eecs-k8s/apps/omniverse-nucleus/
├── Chart.yaml
├── manifest.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl
    ├── namespace.yaml
    ├── secrets.yaml
    ├── service-headless.yaml
    ├── service-internal.yaml
    ├── service-loadbalancer.yaml
    └── statefulset.yaml
```

초기 계획과 다른 점:

- 실제 구현에는 `templates/secrets.yaml`이 있다.
- 실제 구현에는 app-local `patches.yaml`이 없다.
- cluster preset patch 연결은 `manifest.yaml`의 `patched: true`와 SmartX multi-source Application이 담당한다.
- 별도 ServiceAccount/RBAC는 없다. Nucleus 컨테이너가 Kubernetes API를 호출하는 controller가 아니기 때문이다.
- PVC는 독립 `pvc.yaml`이 아니라 StatefulSet `volumeClaimTemplates`로 생성한다.

### 3.3 `Chart.yaml`

역할: Nucleus 앱을 독립 Helm chart로 렌더링한다.

```yaml
apiVersion: v2
name: omniverse-nucleus
description: NVIDIA Omniverse Nucleus Server
type: application
version: 2.0.0-alpha.2
appVersion: 2.0.0-alpha.2
```

Nucleus container image 버전을 바꿀 때는 `values.yaml`의 image를 먼저 검증하고 chart/app version 정책에 맞춰 version을 올린다.

### 3.4 `manifest.yaml`

역할: eecs-k8s root chart가 Nucleus Argo CD Application을 만들도록 한다.

현재 핵심 형태:

```yaml
appVersion: org.ulagbulag.io/v1alpha1
kind: Manifest
metadata:
  name: smartx.apps.omniverse-nucleus
spec:
  group: ops
  phase: alpha
  scale: small
  app:
    autoSync: true
    namespace: omniverse
    patched: true
    unsafe: true
    useClusterValues: false
    features:
      - org.ulagbulag.io/omniverse/nucleus
    sync:
      createNamespace: true
      respectIgnoreDifferences: true
      serverSideApply: true
```

필드별 이유:

| 필드 | 이유 |
| --- | --- |
| `namespace: omniverse` | Navigator/API와 Isaac Sim 연동 리소스를 같은 서비스 namespace에 배치 |
| `patched: true` | `c-k8s/patches/omniverse-nucleus/values.yaml`을 app chart에 결합 |
| `unsafe: true` | StatefulSet와 영구 PVC가 있어 prune/재설치가 데이터 수명 주기에 영향을 줄 수 있음을 표시 |
| `createNamespace: true` | destination namespace가 없을 때 먼저 생성 |
| `serverSideApply: true` | 큰 StatefulSet와 다수 container/env 필드를 안정적으로 적용 |

Nucleus는 데이터 서비스이므로 `autoPrune`을 가볍게 추가하지 않는다. PVC retention과 삭제 절차를 먼저 확정해야 한다.

### 3.5 `values.yaml`: 공통 코드로 남길 값

`eecs-k8s/apps/omniverse-nucleus/values.yaml`에는 모든 클러스터가 공유할 구조와 안전한 기본값을 둔다.

공통으로 둘 항목:

```text
Nucleus resource 이름 규칙
replicaCount 기본 1
12개 Nucleus container image 구조
container command/args/ports
내부 Service 이름과 port
data/log/temp mount 경로
PVC access mode schema
StatefulSet PVC retention 기본 정책
Secret name/key를 참조하는 schema
nodeSelector/affinity/tolerations 빈 기본값
```

클러스터별 실제값을 기본값으로 박지 않을 항목:

```text
LoadBalancer IP
StorageClass 이름
실제 NGC credential
실제 Nucleus master password
runtime signing key 원문
특정 nodeName
클러스터 전용 taint/toleration
```

주요 values 경로:

| values 경로 | template 사용 위치 | 의미 |
| --- | --- | --- |
| `nucleus.name` | helpers와 모든 리소스 | 리소스 basename |
| `nucleus.namespace` | helpers | release namespace override |
| `nucleus.replicaCount` | StatefulSet | 1차 단일 replica |
| `nucleus.images.*` | StatefulSet 12개 container | Compose Stack에서 추출한 image |
| `nucleus.initImage` | StatefulSet initContainer | data path 초기화 |
| `nucleus.instance` | 여러 container env | Nucleus instance 이름 |
| `nucleus.service.*` | LoadBalancer Service/helper | type, IP, external host, annotation |
| `nucleus.storage.*` | volumeClaimTemplates | class, size, accessModes, retention |
| `nucleus.imagePullSecret.*` | StatefulSet/optional Secret | NGC pull Secret 참조 또는 PoC 생성 |
| `nucleus.secrets.passwords.*` | containers/optional Secret | password Secret 이름과 생성 여부 |
| `nucleus.secrets.runtime.*` | volume/optional Secret | runtime Secret 이름과 생성 여부 |
| `nucleus.scheduling.*` | Pod spec | nodeSelector, affinity, tolerations |

### 3.6 `_helpers.tpl`

helper가 담당할 것:

```text
Nucleus fullname
namespace
공통 labels
외부 접속 host
```

외부 host는 다음 우선순위로 계산한다.

```text
nucleus.service.externalHost
  -> 없으면 nucleus.service.loadBalancerIP
```

StatefulSet 여러 container에 같은 외부 주소를 직접 반복하지 않는다.

### 3.7 `namespace.yaml`

원본의 고정 namespace:

```yaml
metadata:
  name: omniverse
```

변환 후에는 helper가 반환한 namespace를 사용한다. `manifest.yaml` destination namespace와 다른 값이 되지 않게 한다.

Namespace를 Nucleus chart와 별도 cluster bootstrap이 동시에 관리하지 않도록 ownership을 확인한다.

### 3.8 `service-headless.yaml`

원본 `omniverse-nucleus-headless`의 다음 성질을 유지한다.

```text
clusterIP: None
StatefulSet serviceName과 동일
StatefulSet Pod selector와 동일
```

이 Service는 외부 노출용이 아니다. StatefulSet의 안정적인 내부 DNS를 제공한다.

### 3.9 `service-internal.yaml`

원본 Compose service DNS를 Kubernetes ClusterIP Service로 보존한다.

대표 서비스:

```text
nucleus-api
nucleus-lft
nucleus-lft-lb
nucleus-log-processor
nucleus-resolver-cache
utl-monpx
nucleus-discovery
nucleus-auth
nucleus-navigator
nucleus-search
nucleus-tagging
```

이름과 port를 임의로 정리하거나 합치지 않는다. Nucleus container env/config가 이 DNS 이름을 참조한다.

변경 허용 범위:

```text
namespace helper
공통 labels
selector helper
values로 외부화하기로 명시한 port
```

### 3.10 `service-loadbalancer.yaml`

외부 Navigator/API/Omniverse client 진입점을 제공한다.

cluster patch에서 바꿀 값:

```yaml
nucleus:
  service:
    type: LoadBalancer
    loadBalancerIP: <NUCLEUS_RESERVED_IP>
    externalHost: <NUCLEUS_EXTERNAL_HOST_OR_IP>
    loadBalancerAnnotations: {}
```

고정 IP는 반드시 대상 Cilium/MetalLB pool에서 예약하고 다른 Service와 충돌하지 않는지 확인한다.

### 3.11 `statefulset.yaml`

원본 `20-statefulset.yaml`의 12개 container 구조를 유지한다.

```text
nucleus-api
nucleus-lft
nucleus-lft-lb
nucleus-log-processor
nucleus-resolver-cache
utl-monpx
nucleus-discovery
nucleus-auth
nucleus-navigator
nucleus-search
nucleus-thumbnails
nucleus-tagging
```

chart로 바꾸면서 수정하는 부분:

| 원본의 고정 코드 | Helm 값 | 이유 |
| --- | --- | --- |
| `replicas: 1` | `nucleus.replicaCount` | schema화하되 1차 기본값은 1 유지 |
| 각 container image | `nucleus.images.*` | image 버전 변경을 template 수정 없이 수행 |
| image pull Secret 이름 | `nucleus.imagePullSecret.name` | 클러스터 Secret 이름 차이 |
| password Secret 이름 | `nucleus.secrets.passwords.name` | Secret 원문과 workload 분리 |
| runtime Secret 이름 | `nucleus.secrets.runtime.name` | signing/runtime 파일 전달 분리 |
| 외부 host/IP | service helper | LB IP 변경을 12개 container에 반복하지 않음 |
| `nodeName: com3` | `nucleus.scheduling.*` | PoC 강제 배치를 제거하고 scheduler 정책 사용 |
| `storageClassName` | `nucleus.storage.className` | 클러스터 Ceph class 차이 |
| PVC size | `nucleus.storage.size` | 환경별 용량 계획 |
| RWO | `nucleus.storage.accessModes` | storage schema 명시 |
| PVC retention | `nucleus.storage.retention.*` | scale/delete 시 데이터 보호 정책 명시 |

`nodeName`은 template에 남기지 않는다.

```yaml
nucleus:
  scheduling:
    nodeSelector: {}
    affinity: {}
    tolerations: []
```

노드 제한이 필요하면 C cluster patch에서 label 기반으로 설정한다.

PVC는 다음 경로를 보존한다.

```text
/omni/data
/omni/log
/omni/temp
/omni/scratch-meta-dump
```

StatefulSet 이름이나 `volumeClaimTemplates.metadata.name`을 바꾸면 기존 PVC와 연결이 끊길 수 있으므로 운영 중 rename하지 않는다.

### 3.12 `secrets.yaml`

현재 chart는 PoC를 위해 다음 Secret을 조건부 렌더링할 수 있다.

```text
NGC image pull Secret
Nucleus password Secret
Nucleus runtime Secret
```

조건:

```yaml
nucleus:
  imagePullSecret:
    create: false
  secrets:
    passwords:
      create: false
    runtime:
      create: false
```

운영 권장값은 모두 `create: false`다. OpenBao/External Secrets 또는 사전 생성 Secret의 **이름만** chart에 전달한다.

PoC에서 `create: true`를 쓸 때도 Secret 원문은 eecs-k8s나 runbook에 넣지 않는다. private preset에 임시 저장했다면 실험 후 rotation과 제거 commit이 필요하다.

### 3.13 feature graph 추가

`eecs-k8s/apps/template/features.yaml`:

```yaml
org.ulagbulag.io/omniverse:
  requires:
    - org.ulagbulag.io/cni
    - org.ulagbulag.io/csi

org.ulagbulag.io/omniverse/nucleus:
  requires:
    - org.ulagbulag.io/csi/block
    - org.ulagbulag.io/distributed-storage-cluster/ceph
    - org.ulagbulag.io/omniverse
```

의미:

- Nucleus 외부 Service를 위해 CNI가 필요하다.
- StatefulSet RBD PVC를 위해 CSI/block/Ceph가 필요하다.
- feature 이름은 SmartX 기존 관례인 `org.ulagbulag.io/*`를 사용한다.

`eecs-k8s/values.yaml`의 feature 목록에도 다음을 등록한다.

```yaml
features:
  - org.ulagbulag.io/omniverse
  - org.ulagbulag.io/omniverse/nucleus
```

기존 key가 있으면 중복 추가하지 않는다.

### 3.14 `c-k8s/values.yaml`에서 feature 활성화

```yaml
features:
  # 기존 feature 유지
  - org.ulagbulag.io/omniverse/nucleus
```

직접 의존성 feature를 모두 수동으로 중복 나열할 필요는 없다. SmartX feature graph가 필요한 CNI/CSI/Ceph feature를 계산한다. 다만 실제 C 클러스터에 해당 인프라가 준비되어 있는지는 별도로 확인한다.

### 3.15 `c-k8s/patches/omniverse-nucleus/values.yaml`

이 파일에는 C 클러스터에서 달라지는 값만 둔다.

Secret 원문 없는 구조 예:

```yaml
nucleus:
  service:
    type: LoadBalancer
    loadBalancerIP: <C_NUCLEUS_RESERVED_IP>
    externalHost: <C_NUCLEUS_EXTERNAL_HOST_OR_IP>
    loadBalancerAnnotations: {}

  storage:
    className: <C_EXISTING_BLOCK_STORAGE_CLASS>
    size: 10Gi
    accessModes:
      - ReadWriteOnce
    retention:
      whenDeleted: Retain
      whenScaled: Retain

  imagePullSecret:
    create: false
    name: <NGC_PULL_SECRET_NAME>

  secrets:
    passwords:
      create: false
      name: <NUCLEUS_PASSWORD_SECRET_NAME>
    runtime:
      create: false
      name: <NUCLEUS_RUNTIME_SECRET_NAME>

  scheduling:
    nodeSelector: {}
    affinity: {}
    tolerations: []
```

preset에 두는 이유:

| 값 | 이유 |
| --- | --- |
| LB IP/external host | C 클러스터 IP pool에 종속 |
| StorageClass/size | C 클러스터 Ceph 구성과 용량 정책에 종속 |
| Secret 이름 | C 클러스터 Secret delivery에 종속 |
| scheduling | C 노드 label/taint에 종속 |
| image override가 필요한 경우 | registry mirror 또는 검증 image가 환경마다 다름 |

preset에 두지 않는 것:

```text
12개 container 전체 YAML 복사
내부 Service 전체 YAML 복사
Secret 원문을 문서에 복사
특정 Pod UID/PVC/PV 이름
현재 LoadBalancer status
```

### 3.16 Tower와 Argo CD에서 바꾸는 코드

`tower-k8s`에 Nucleus Deployment/Service/StatefulSet를 직접 추가하지 않는다.

Tower Argo CD가 이미 C root Application을 관리하고 있으면 다음 흐름만 사용한다.

```text
C root Application
  -> eecs-k8s root chart
  -> feature graph가 c-omniverse-nucleus Application 생성
  -> eecs-k8s app chart + c-k8s patch multi-source render
```

Tower에서 필요한 변경은 private repo credential, targetRevision, destination cluster 등록 같은 제어-plane 설정뿐이다. 동일한 live Nucleus 리소스를 Tower local manifest로 중복 생성하지 않는다.

### 3.17 변경해야 하는 파일 요약

#### eecs-k8s

```text
추가:
  apps/omniverse-nucleus/Chart.yaml
  apps/omniverse-nucleus/manifest.yaml
  apps/omniverse-nucleus/values.yaml
  apps/omniverse-nucleus/templates/_helpers.tpl
  apps/omniverse-nucleus/templates/namespace.yaml
  apps/omniverse-nucleus/templates/secrets.yaml
  apps/omniverse-nucleus/templates/service-headless.yaml
  apps/omniverse-nucleus/templates/service-internal.yaml
  apps/omniverse-nucleus/templates/service-loadbalancer.yaml
  apps/omniverse-nucleus/templates/statefulset.yaml

수정:
  apps/template/features.yaml
  values.yaml
```

#### c-k8s

```text
수정:
  values.yaml

추가:
  patches/omniverse-nucleus/values.yaml
```

#### tower-k8s

```text
Nucleus workload manifest 변경 없음
```

## 4. Secret 처리

기본/운영 가이드는 `create: false`다.

```text
OpenBao 또는 기존 Secret 관리 경로
  -> ExternalSecret 또는 사전 생성 Kubernetes Secret
  -> c-k8s patch에는 Secret 이름만 기록
  -> Nucleus StatefulSet는 secretKeyRef/volume으로 참조
```

실제 완료된 1차 private PoC에서는 재현 속도를 위해 다음 예외를 사용했다.

```text
eecs-k8s/apps/omniverse-nucleus/templates/secrets.yaml
  -> 조건부 Secret 리소스 템플릿

private c-k8s/patches/omniverse-nucleus/values.yaml
  -> create: true와 PoC 값을 주입
```

이 방식은 당시 배포 사실을 설명하기 위한 기록이며 공개/운영 repo 권장안이 아니다. 실제 값은 runbook에 기록하지 않고, 운영 전에는 `create: false`와 External Secrets/OpenBao로 전환한다.

### PoC용 values 예시

`c-k8s/patches/omniverse-nucleus/values.yaml`에 아래 형태를 둔다.

```yaml
nucleus:
  imagePullSecret:
    create: true
    name: nvcr-io
    registry: nvcr.io
    username: "$oauthtoken"
    password: "<NGC_API_KEY>"

  secrets:
    passwords:
      create: true
      name: nucleus-passwords
      stringData:
        MASTER_PASSWORD: "<관리자 비밀번호>"

    runtime:
      create: true
      name: nucleus-secrets
      stringData:
        SECRET_1: "<값>"
        SECRET_2: "<값>"
```

### 보안 기준

- 운영/공개 레포에서는 실제 key/password를 커밋하지 않는다.
- 이번처럼 private PoC에서 빠르게 검증할 때만 실제 값을 넣을 수 있다.
- 그래도 NGC API key는 개인 계정 권한이 걸리므로 **짧은 만료/최소 권한/실험 후 rotation**을 전제로 한다.
- 장기 운영으로 넘어가면 `create: false`로 바꾸고 OpenBao + External Secrets가 만든 Secret을 참조한다.

운영 전환 예시:

```yaml
nucleus:
  imagePullSecret:
    create: false
    name: nvcr-io
  secrets:
    passwords:
      create: false
      name: nucleus-passwords
    runtime:
      create: false
      name: nucleus-secrets
```

## 5. 검증 순서

### 5.1 로컬 렌더링 검증

대상 레포들을 로컬에 받은 뒤:

```bash
helm template c ./eecs-k8s -f ./c-k8s/values.yaml > /tmp/eecs-c-render.yaml
```

성공 기준:

```text
c-omniverse-nucleus Argo CD Application이 생성된다.
```

### 5.2 앱 chart 단독 렌더링 검증

```bash
helm template omniverse-nucleus ./eecs-k8s/apps/omniverse-nucleus \
  -f ./eecs-k8s/apps/omniverse-nucleus/values.yaml \
  -f ./c-k8s/patches/omniverse-nucleus/values.yaml \
  > /tmp/nucleus-render.yaml
```

성공 기준:

```text
Namespace
StatefulSet와 그 안의 volumeClaimTemplates
Headless Service
11개 Internal Service
LoadBalancer Service
create=true일 때만 선택적 Secret
```

가 렌더링된다. Nucleus chart에는 ServiceAccount/RBAC가 없고 PVC는 독립 manifest가 아니라 StatefulSet가 생성한다.

### 5.3 Kubernetes dry-run

```bash
kubectl apply --dry-run=client -f /tmp/nucleus-render.yaml
```

성공 기준:

```text
YAML schema 수준에서 적용 가능
```

### 5.4 Secret 위치 확인

PoC에서 실제 Secret 값을 GitOps로 같이 넣는다면, 값이 있는 위치를 명확히 제한한다.

```bash
# 엔진에는 실제 key/password가 없어야 한다.
grep -R "nvapi-" ./eecs-k8s

# 런북에도 실제 key/password가 없어야 한다.
grep -R "nvapi-" ./netai-devsecops-runbook

# PoC preset에만 실제 값이 있을 수 있다.
grep -R "nvapi-" ./c-k8s
```

성공 기준:

```text
eecs-k8s: 실제 key/password 없음
netai-devsecops-runbook: 실제 key/password 없음
c-k8s: private PoC에서 의도한 Secret manifest/values에만 존재
```

`c-k8s`에 실제 값을 넣은 경우 실험 종료 후 key rotation 또는 Secret 제거 커밋을 남긴다.

### 5.5 Argo CD 적용 후 확인

Argo CD에서 확인할 앱:

```text
c-omniverse-nucleus
```

성공 기준:

```text
Application: Synced / Healthy
Pod: omniverse-nucleus-0 Running
Containers: 12/12 Ready
PVC: Bound
Service: EXTERNAL-IP 10.33.143.10
Isaac Sim 또는 웹 브라우저에서 Nucleus 접속 가능
```

## 6. 주의사항

### 같은 리소스를 두 곳에서 관리하면 안 됨

Nucleus는 이번 구조에서는 `eecs-k8s` app catalog + `c-k8s` preset patch로 관리한다.

따라서 같은 namespace/service/statefulset을 `tower-k8s/apps`나 `c-k8s/apps`에 중복으로 넣으면 안 된다.

### StorageClass Delete 정책

`ceph-block-noreplicas`는 현재 1차 검증용이다. 운영 데이터 보호를 위해서는 Retain StorageClass가 필요하다.

1차:

```text
ceph-block-noreplicas
```

운영 전환:

```text
rook-ceph-block-nucleus-retain
```

### Nucleus는 단일 replica로 시작

Nucleus data path는 RBD RWO PVC 하나를 붙이는 구조로 시작한다.

```text
replicas: 1
accessMode: ReadWriteOnce
```

여러 replica로 수평 확장하는 구조로 바로 가지 않는다.

### Docker Compose를 Kubernetes로 변환한 구조

NVIDIA가 제공하는 것은 Helm chart가 아니라 Enterprise Nucleus Docker Compose stack이다.

이번 구현은 다음 변환이다.

```text
NVIDIA compose services
  -> Kubernetes StatefulSet의 여러 container
  -> Kubernetes Service로 compose DNS 이름 보존
  -> DATA_ROOT를 Rook-Ceph RBD PVC로 mount
```

## 7. 재현 또는 후속 변경 작업 단계

1. `eecs-k8s/apps/omniverse-nucleus` chart 추가
2. `eecs-k8s/apps/template/features.yaml`에 `org.ulagbulag.io/omniverse/nucleus` 추가
3. `eecs-k8s/values.yaml` default feature 목록에 Nucleus feature 추가
4. `c-k8s/values.yaml`에서 Nucleus feature 활성화
5. `c-k8s/patches/omniverse-nucleus/values.yaml` 추가
6. Helm 렌더링 검증
7. Secret 누출 확인
8. `eecs-k8s/main`과 Tower root Application이 현재 참조하는 c-k8s branch에 반영한다. 완료 기준은 `c-k8s/main`이며 `ops`는 당시 임시 작업 branch였다.
9. Argo CD에서 `c-omniverse-nucleus` sync/health 확인
10. Isaac Sim 접속 테스트

## 8. 현재 결정 사항

```text
앱 정의 위치: eecs-k8s/apps/omniverse-nucleus
preset 위치: c-k8s
Tower 변경: 없음
1차 StorageClass: ceph-block-noreplicas
운영 StorageClass: rook-ceph-block-nucleus-retain
1차 검증 완료 LoadBalancer IP: 10.33.143.10
PoC Secret: private c-k8s preset으로 렌더링했으며 값은 runbook에 기록하지 않음
운영 Secret: OpenBao/External Secrets로 이관 권장
```
