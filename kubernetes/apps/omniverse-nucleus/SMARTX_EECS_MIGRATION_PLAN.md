# Omniverse Nucleus SmartX/eecs-k8s 이관 계획

> 위치: 이 문서는 **외부 작업 레포가 아니라** `mj006648/netai-devsecops-runbook` 아래에 둔다.  
> 목적: MiniX에서 검증한 Omniverse Nucleus Kubernetes PoC를 대상 SmartX 계열 구조(`eecs-k8s` + `c-k8s`)로 옮기기 위한 구현 계획을 정리한다.

## 0. 결론

이번 이관은 다음 구조로 진행한다.

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
예상 이름: ceph-block-nucleus-retain
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
1차 후보: 10.33.143.10
```

별도 예약 IP가 정해지면 그 IP로 변경한다.

### Argo CD

Tower Argo CD가 C 클러스터 root app을 관리한다.

```text
Argo CD: 10.34.25.17
cluster name: c
project: c-ops
```

중요한 branch 기준:

```text
eecs-k8s: main
c-k8s: ops
```

따라서 실제 적용 시 `eecs-k8s` 변경은 `main`, `c-k8s` 변경은 `ops`에 반영되어야 Argo CD가 본다.

## 3. 구현할 구조

### 3.1 `eecs-k8s`에 추가할 앱 카탈로그

```text
eecs-k8s/apps/omniverse-nucleus/
├── Chart.yaml
├── manifest.yaml
├── values.yaml
├── patches.yaml
└── templates/
    ├── namespace.yaml
    ├── service-headless.yaml
    ├── service-internal.yaml
    ├── service-loadbalancer.yaml
    └── statefulset.yaml
```

의미:

| 파일 | 의미 |
| --- | --- |
| `manifest.yaml` | SmartX 엔진이 읽는 앱 메타데이터. app name, namespace, feature, patched 여부 정의 |
| `Chart.yaml` | Omniverse Nucleus 앱을 Helm chart처럼 렌더링하기 위한 최소 chart metadata |
| `values.yaml` | 모든 클러스터에 적용 가능한 기본값 |
| `patches.yaml` | preset patch 허용/검증용 구조 |
| `templates/` | 실제 Kubernetes 리소스 생성 템플릿 |

### 3.2 feature graph 추가

`eecs-k8s/apps/template/features.yaml`에 Nucleus feature를 추가한다.

```yaml
scalex.io/omniverse/nucleus:
  requires:
    - org.ulagbulag.io/cni
    - org.ulagbulag.io/csi
    - org.ulagbulag.io/csi/block
    - org.ulagbulag.io/distributed-storage-cluster/ceph
```

의미:

- `scalex.io/omniverse/nucleus`를 켜면 Nucleus 앱이 설치 대상이 된다.
- Nucleus는 외부 접속과 스토리지가 필요하므로 CNI, CSI, block storage, Ceph를 선행 의존성으로 둔다.
- feature 이름은 기존 `org.ulagbulag.io/*`와 구분하기 위해 우리 실험/ScaleX 네임스페이스인 `scalex.io/*`를 사용한다.

`eecs-k8s/values.yaml`의 default feature 목록에도 같은 feature를 등록해야 SmartX 검증을 통과한다.

### 3.3 `c-k8s`에서 feature 활성화

`c-k8s/values.yaml`:

```yaml
features:
  - org.ulagbulag.io/cni
  - org.ulagbulag.io/csi
  - org.ulagbulag.io/distributed-storage-cluster/ceph
  - scalex.io/omniverse/nucleus
```

### 3.4 `c-k8s` patch 추가

`c-k8s/patches/omniverse-nucleus/values.yaml`:

```yaml
nucleus:
  service:
    type: LoadBalancer
    loadBalancerIP: 10.33.143.10

  storage:
    className: ceph-block-noreplicas
    size: 10Gi

  imagePullSecret:
    name: nvcr-io

  secrets:
    passwords:
      name: nucleus-passwords
    runtime:
      name: nucleus-secrets
```

이 파일에는 클러스터마다 달라지는 값만 둔다.

- LoadBalancer IP
- StorageClass / PVC size
- Secret 이름
- 필요 시 nodeSelector/affinity

## 4. Secret 처리

NGC API key, Nucleus password, runtime secret 값은 Git에 커밋하지 않는다.

클러스터에 직접 Secret을 만들거나, 추후 External Secrets/OpenBao로 연결한다.

예시:

```bash
kubectl -n omniverse create secret docker-registry nvcr-io \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password='<NGC_API_KEY>'

kubectl -n omniverse create secret generic nucleus-passwords \
  --from-literal=MASTER_PASSWORD='<관리자 비밀번호>'

kubectl -n omniverse create secret generic nucleus-secrets \
  --from-literal=SECRET_1='<값>' \
  --from-literal=SECRET_2='<값>'
```

> 실제 key/password는 문서나 Git에 남기지 않는다.

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
ServiceAccount
StatefulSet
PVC
Headless Service
Internal Service
LoadBalancer Service
```

가 렌더링된다.

### 5.3 Kubernetes dry-run

```bash
kubectl apply --dry-run=client -f /tmp/nucleus-render.yaml
```

성공 기준:

```text
YAML schema 수준에서 적용 가능
```

### 5.4 Secret 누출 확인

```bash
grep -R "nvapi-" ./eecs-k8s ./c-k8s
grep -R "<실제 비밀번호>" ./eecs-k8s ./c-k8s
```

성공 기준:

```text
아무것도 나오지 않아야 함
```

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
ceph-block-nucleus-retain
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

## 7. 작업 단계

1. `eecs-k8s/apps/omniverse-nucleus` chart 추가
2. `eecs-k8s/apps/template/features.yaml`에 `scalex.io/omniverse/nucleus` 추가
3. `eecs-k8s/values.yaml` default feature 목록에 Nucleus feature 추가
4. `c-k8s/values.yaml`에서 Nucleus feature 활성화
5. `c-k8s/patches/omniverse-nucleus/values.yaml` 추가
6. Helm 렌더링 검증
7. Secret 누출 확인
8. `eecs-k8s main`, `c-k8s ops`에 반영
9. Argo CD에서 `c-omniverse-nucleus` sync/health 확인
10. Isaac Sim 접속 테스트

## 8. 현재 결정 사항

```text
앱 정의 위치: eecs-k8s/apps/omniverse-nucleus
preset 위치: c-k8s
Tower 변경: 없음
1차 StorageClass: ceph-block-noreplicas
운영 StorageClass: 추후 Retain 전용 class
1차 LoadBalancer IP: 10.33.143.10 후보
Secret: Git에 커밋하지 않음
```
