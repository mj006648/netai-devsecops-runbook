# Omniverse Nucleus SmartX/eecs-k8s 실행 기록

> 이 문서는 계획서가 아니라 실제로 수행한 작업 기록이다. Secret 원문 값은 기록하지 않는다.

## 1. 작업 범위

NVIDIA Omniverse Nucleus를 SmartX 방식으로 이관하기 위해 다음 두 레포 구조를 사용했다.

```text
eecs-k8s
  -> 공통 SmartX 엔진/app catalog
  -> apps/omniverse-nucleus 추가

c-k8s
  -> C 클러스터 preset
  -> feature 활성화 + patches/omniverse-nucleus/values.yaml 작성
```

실제 Kubernetes 배포까지 완료했다.

```text
eecs-k8s/main: Nucleus app catalog push 완료
c-k8s/main: C 클러스터 preset push 완료
C cluster: StatefulSet/PVC/Service/HTTP 응답 확인 완료
```

## 2. eecs-k8s 작업

### 2.1 추가한 앱 카탈로그

추가 위치:

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

역할:

| 파일 | 역할 |
| --- | --- |
| `manifest.yaml` | SmartX가 `c-omniverse-nucleus` Argo CD Application을 만들기 위한 앱 메타데이터 |
| `Chart.yaml` | 앱 디렉터리를 Helm chart로 인식시키는 메타데이터 |
| `values.yaml` | 기본 image, service, storage, secret 이름 기본값 |
| `templates/secrets.yaml` | `nvcr-io`, `nucleus-passwords`, `nucleus-secrets` Secret 생성 템플릿 |
| `templates/statefulset.yaml` | NVIDIA Compose Stack 기반 12-container StatefulSet |
| `templates/service-*.yaml` | Nucleus 내부 DNS/외부 LoadBalancer Service |

### 2.2 feature graph 추가

수정 파일:

```text
eecs-k8s/apps/template/features.yaml
eecs-k8s/values.yaml
```

추가한 feature:

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

`org.ulagbulag.io/*` 형식을 사용해 기존 SmartX feature graph 네이밍과 맞췄다.

### 2.3 eecs-k8s push 기록

```text
3bbfdde feat: add omniverse nucleus app
4c1ab24 fix: align nucleus secret keys
```

두 커밋 모두 `eecs-k8s/main`에 push했다.

## 3. c-k8s 작업

작업 브랜치:

```text
local branch: ops
remote branch: ops push 완료
main branch: ops 내용을 fast-forward merge 후 push 완료
```

원격 `ops` 브랜치가 없어서 로컬에서 최신 `origin/main` 기준으로 `ops` 브랜치를 만들었고, 검증 후 `main`에도 동일 커밋을 반영했다.

### 3.1 feature 활성화

수정 파일:

```text
c-k8s/values.yaml
```

추가:

```yaml
features:
  - org.ulagbulag.io/cni
  - org.ulagbulag.io/csi
  - org.ulagbulag.io/distributed-storage-cluster/ceph
  - org.ulagbulag.io/omniverse/nucleus
```

### 3.2 C 클러스터 patch 작성

추가 파일:

```text
c-k8s/patches/omniverse-nucleus/values.yaml
```

설정한 값:

```text
LoadBalancer IP: 10.33.143.10
externalHost: 10.33.143.10
StorageClass: ceph-block-noreplicas
PVC size: 10Gi
imagePullSecret: nvcr-io 생성
nucleus-passwords 생성
nucleus-secrets 생성
```

### 3.3 Secret 처리

Secret은 노드에서 수동으로 `kubectl create secret` 하지 않고, `c-k8s/patches/omniverse-nucleus/values.yaml` 값으로 Helm chart가 렌더링하게 했다.

```text
eecs-k8s/apps/omniverse-nucleus/templates/secrets.yaml
  + c-k8s/patches/omniverse-nucleus/values.yaml
  -> Kubernetes Secret manifest 렌더링
```

값 출처:

```text
nvcr.io imagePullSecret: MiniX에서 성공한 nvcr-io Secret 기반
runtime secret: MiniX에서 성공한 nucleus-secrets 기반
Nucleus password: 0070으로 설정
```

실제 NGC API key와 runtime secret 값은 이 문서에 기록하지 않는다.

### 3.4 username 관련 메모

Nucleus password는 `0070`으로 설정했다. 다만 현재 Compose-to-Kubernetes 변환 템플릿은 `master-password`, `service-password`만 설정하고, `netai` 사용자를 자동 생성하는 필드는 확인하지 못했다.

따라서 다음 단계에서 확인이 필요하다.

```text
1. 배포 후 기본 Nucleus admin/master 계정으로 로그인 가능한지 확인
2. Nucleus UI/API에서 netai 사용자 생성 가능 여부 확인
3. 필요하면 초기 사용자 생성 Job 또는 Config를 chart에 추가
```

## 4. 렌더링 검증 결과

### 4.1 SmartX root Application 렌더링

명령:

```bash
helm template c eecs-k8s -f c-k8s/values.yaml
```

결과:

```text
root_applications: 8
has_c_omniverse_nucleus: True
project: c-ops
destination.name: c
destination.namespace: omniverse
valueFiles: $cluster/patches/omniverse-nucleus/values.yaml
```

즉, `c-k8s`에서 feature를 켜면 SmartX가 `c-omniverse-nucleus` Application을 생성한다.

### 4.2 Nucleus chart 렌더링

명령:

```bash
helm template omniverse-nucleus eecs-k8s/apps/omniverse-nucleus \
  -f c-k8s/patches/omniverse-nucleus/values.yaml
```

결과:

```text
nucleus_docs: 18
Namespace: 1
Secret: 3
Service: 13
StatefulSet: 1
containers: 12
storageClass: ceph-block-noreplicas
storageSize: 10Gi
LoadBalancer type: LoadBalancer
LoadBalancer IP: 10.33.143.10
placeholder_remaining: False
```

렌더링 결과에는 Secret 값이 포함되므로 임시 렌더링 파일은 검증 후 삭제했다.

## 5. 현재 상태

```text
eecs-k8s/main: push 완료
c-k8s/ops: push 완료
c-k8s/main: push 완료
실제 C 클러스터 배포: 완료
Nucleus HTTP 응답: 확인 완료
```

관련 커밋:

```text
eecs-k8s/main
  3bbfdde feat: add omniverse nucleus app
  4c1ab24 fix: align nucleus secret keys

c-k8s/main
  1042776 feat: enable omniverse nucleus
```

## 6. C 클러스터 배포 검증

검증 일시: 2026-07-12

검증 대상:

```text
cluster context: kubernetes-admin@ops.site-c.openark
namespace: omniverse
statefulset: omniverse-nucleus
pod: omniverse-nucleus-0
service: omniverse-nucleus
external IP: 10.33.143.10
```

검증 결과:

| 항목 | 결과 |
| --- | --- |
| Pod | `omniverse-nucleus-0` Running |
| Container readiness | 12/12 Ready |
| StatefulSet | 1/1 Ready |
| PVC | `nucleus-data-omniverse-nucleus-0` Bound |
| StorageClass | `ceph-block-noreplicas` |
| PVC size | 10Gi |
| Service type | LoadBalancer |
| External IP | `10.33.143.10` |
| HTTP check | `http://10.33.143.10:8080/` -> 200 OK |
| UI title check | `Omniverse Navigator` 응답 확인 |

확인 명령:

```bash
kubectl -n omniverse get pod omniverse-nucleus-0 -o wide
kubectl -n omniverse get sts omniverse-nucleus
kubectl -n omniverse get pvc nucleus-data-omniverse-nucleus-0
kubectl -n omniverse get svc omniverse-nucleus
curl -fsS -D - http://10.33.143.10:8080/ | head
```

현재 관찰된 restart는 `nucleus-api` 컨테이너 1회다. 재검증 시 Pod는 Running이고 12개 컨테이너가 모두 Ready 상태였으므로 현재 차단 이슈는 아니다.

## 7. 남은 확인 사항

1. Isaac Sim에서 `10.33.143.10` Nucleus 접속 및 로그인 재확인
2. `netai` 사용자 자동 생성이 필요한 경우 초기화 Job/API 절차 추가
3. 운영 전 Nucleus 전용 `Retain` RBD StorageClass로 전환 여부 결정
4. Secret을 계속 GitOps 값으로 둘지, 운영 단계에서 External Secrets/OpenBao로 이관할지 결정
