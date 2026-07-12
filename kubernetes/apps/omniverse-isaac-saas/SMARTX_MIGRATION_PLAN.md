# Omniverse Isaac SaaS SmartX 이관 계획

> 대상 원본: `SmartX-Team/Omniverse/isaac-saas`  
> 목표: 원본 Isaac Sim self-service 플랫폼을 우리 `eecs-k8s` 공통 엔진 + `c-k8s`/`twinx-k8s` preset 구조로 이관한다.  
> 원칙: Secret 원문 값은 문서에 기록하지 않는다.

## 1. 목표 요약

Nucleus는 이미 Kubernetes StatefulSet + RBD PVC + LoadBalancer 방식으로 검증했다. 다음 단계는 Isaac Sim을 여러 사용자가 웹 UI로 생성/삭제할 수 있도록 `isaac-saas` 구조를 가져오는 것이다.

최종 목표 구조는 다음과 같다.

```text
eecs-k8s
  -> apps/omniverse-isaac-saas 추가
  -> SmartX feature graph에 org.ulagbulag.io/omniverse/isaac-saas 등록

c-k8s 또는 twinx-k8s
  -> values.yaml에서 feature 활성화
  -> patches/omniverse-isaac-saas/values.yaml에서 클러스터별 값 주입

ArgoCD / SmartX
  -> isaac-ui Deployment, Service, RBAC만 GitOps로 관리

isaac-ui
  -> Kubernetes API를 호출해 사용자별 Isaac Sim 인스턴스를 동적으로 생성/삭제

Isaac Sim 인스턴스
  -> Deployment + LoadBalancer Service + ResourceClaimTemplate
  -> Git에 직접 나열하지 않음
```

## 2. 원본 `isaac-saas`에서 확인한 구조

원본은 단순 Isaac Sim Pod 매니페스트가 아니다. 핵심은 **Isaac Sim self-service controller UI**다.

| 원본 경로 | 확인한 역할 |
| --- | --- |
| `isaac-saas/ui/` | FastAPI 기반 `isaac-ui` 웹 애플리케이션 |
| `isaac-saas/deploy/k8s/` | `isaac-ui`를 띄우는 Kustomize 매니페스트 |
| `isaac-saas/isaac-sim-image/` | 실제 Isaac Sim 컨테이너 이미지 빌드 소스 |
| `isaac-saas/examples/dra/` | DRA/CEL 기반 GPU UUID selector 검증 예제 |
| `isaac-saas/docs/` | metrics, Prometheus 연동 설계 |

원본 동작 흐름:

```text
사용자
  -> isaac-ui 웹 접속
    -> New instance 클릭
      -> isaac-ui가 Kubernetes API 호출
        -> ResourceClaimTemplate 생성, DRA 사용 시
        -> LoadBalancer Service 생성
        -> Isaac Sim Deployment 생성
        -> 필요 시 workspace PVC, code-server sidecar, metrics sidecar 생성
```

중요한 설계 포인트:

1. ArgoCD는 `isaac-ui` 자체만 관리한다.
2. 사용자가 만든 개별 Isaac Sim 인스턴스는 `isaac-ui`가 동적으로 관리한다.
3. 개별 인스턴스를 Git에 직접 넣지 않는다.
4. ArgoCD prune이 사용자 인스턴스를 지우면 안 되므로, GitOps 범위를 `isaac-ui` 리소스로 제한해야 한다.

## 3. 우리 구조에서 가져갈 것과 바꿀 것

### 3.1 그대로 가져올 것

| 항목 | 이유 |
| --- | --- |
| `isaac-ui` self-service 방식 | 멀티테넌트 사용자가 직접 Isaac Sim 인스턴스를 만들 수 있음 |
| `Deployment + Service` 기반 인스턴스 생성 | Kubernetes 기본 리소스라 디버깅과 운영이 쉬움 |
| 인스턴스별 LoadBalancer Service | Isaac Sim WebRTC 접속 IP를 인스턴스마다 분리 가능 |
| DRA `ResourceClaimTemplate` 설계 | GPU UUID/product 단위 스케줄링 제어 가능 |
| GPU ban ConfigMap 구조 | 별도 DB 없이 초기에 운영 가능 |
| code-server sidecar 옵션 | 사용자별 extension/code 수정 환경 제공 가능 |
| metrics/scene history 구조 | 나중에 GPU 사용량, scene별 부하 분석 가능 |

### 3.2 반드시 바꿀 것

| 원본 항목 | 원본 상태 | 우리 변경 방향 | 바꾸는 이유 |
| --- | --- | --- | --- |
| 배포 방식 | Kustomize + 수동/Argo 예시 | SmartX app catalog Helm chart | `smartx-k8s`/`eecs-k8s` 방식과 맞추기 위해 |
| namespace | `oos-sim` | `omniverse` 또는 cluster preset 값 | Nucleus와 같은 도메인으로 묶기 위해 |
| Harbor 주소 | `10.38.38.210/dt-saas` | 우리 Harbor/project | 이미지 pull 환경이 다름 |
| `isaac-ui` image | 원본 registry tag | 우리 registry로 build/push한 tag | C/TwinX 클러스터에서 pull 가능해야 함 |
| Isaac Sim image | `5.1-exp1` env, Dockerfile은 6.0 기반 | 우리 `isaac-sim:6.0` tag로 통일 | 버전 혼동 제거 |
| Nucleus 주소 | 코드 안 `omniverse://10.38.38.32/` | values로 외부화, 예: `omniverse://10.33.143.10/` | 클러스터별 Nucleus endpoint가 다름 |
| Nucleus 계정 | `admin` 하드코딩 | Secret 참조 + preset 값 | 사용자/비밀번호 분리 필요 |
| GPU 노드 목록 | `l40s,rm352-1,...` | C/TwinX 실제 GPU 노드 | 원본 노드명은 우리 클러스터에 없음 |
| default GPU bans | 원본 GPU UUID | 우리 GPU UUID로 재작성 또는 비움 | 원본 UUID를 쓰면 잘못된 ban 발생 |
| DRA | 기본 enabled | 클러스터 지원 확인 후 enabled | DeviceClass/ResourceSlice가 없으면 실패 |
| workspace storage | 기본 `emptyDir` | 필요 시 RBD PVC 옵션화 | 사용자 코드 보존 여부 결정 필요 |
| Secret 방식 | out-of-band Secret 전제 | 실험은 GitOps Secret 가능, 운영은 ESO/OpenBao 권장 | 재현성과 보안 수준 분리 |

## 4. SmartX식 목표 레포 구조

### 4.1 `eecs-k8s`에 추가할 것

`eecs-k8s`는 공통 엔진/app catalog다. 클러스터별 IP, 노드명, 비밀번호 같은 값은 넣지 않는다.

추가 예상 파일:

```text
eecs-k8s/apps/omniverse-isaac-saas/
├── Chart.yaml
├── manifest.yaml
├── values.yaml
└── templates/
    ├── serviceaccount.yaml
    ├── rbac.yaml
    ├── deployment.yaml
    ├── service.yaml
    └── secrets.yaml              # 선택: 실험용 Secret 렌더링 옵션
```

수정 예상 파일:

```text
eecs-k8s/apps/template/features.yaml
eecs-k8s/values.yaml
```

Feature graph 예시:

```yaml
org.ulagbulag.io/omniverse/isaac-saas:
  requires:
    - org.ulagbulag.io/omniverse/nucleus
    - nvidia.com/gpu
    - org.ulagbulag.io/registry/container/harbor

org.ulagbulag.io/omniverse/isaac-saas/dra:
  requires:
    - org.ulagbulag.io/omniverse/isaac-saas
    - nvidia.com/gpu
```

`manifest.yaml` 예상 방향:

```yaml
metadata:
  name: smartx.apps.omniverse-isaac-saas
spec:
  app:
    name: omniverse-isaac-saas
    namespace: omniverse
    autoSync: true
    patched: true
    features:
      - org.ulagbulag.io/omniverse/isaac-saas
  source:
    path: apps/omniverse-isaac-saas
```

### 4.2 `c-k8s` 또는 `twinx-k8s`에 추가할 것

Preset은 클러스터별 차이만 가진다.

수정 예상 파일:

```text
c-k8s/values.yaml
c-k8s/patches/omniverse-isaac-saas/values.yaml
```

`values.yaml` feature 활성화 예시:

```yaml
features:
  - org.ulagbulag.io/omniverse/nucleus
  - org.ulagbulag.io/omniverse/isaac-saas
```

DRA 검증 후:

```yaml
features:
  - org.ulagbulag.io/omniverse/nucleus
  - org.ulagbulag.io/omniverse/isaac-saas
  - org.ulagbulag.io/omniverse/isaac-saas/dra
```

`patches/omniverse-isaac-saas/values.yaml` 예시:

```yaml
namespace: omniverse

ui:
  image:
    repository: <OUR_HARBOR>/omniverse/isaac-ui
    tag: 0.15.0
  service:
    type: LoadBalancer
    loadBalancerIP: <ISAAC_UI_FIXED_IP>

instance:
  image: <OUR_HARBOR>/omniverse/isaac-sim:6.0
  nodes:
    - <gpu-node-1>
    - <gpu-node-2>
  denyProducts:
    - A100
  dra:
    enabled: false       # 1차 검증은 false 권장, DRA 확인 후 true
    apiVersion: resource.k8s.io/v1
    driver: gpu.nvidia.com
    deviceClass: gpu.nvidia.com

nucleus:
  server: omniverse://10.33.143.10/
  user: netai
  passwordSecret:
    name: nucleus-cred
    key: OMNI_PASS

registry:
  kind: harbor
  url: http://<OUR_HARBOR>
  project: omniverse
  repos:
    - isaac-sim
  pullSecretName: harbor-regcred

workspace:
  persist: false
  storageClassName: ""
  size: 5Gi

metrics:
  enabled: false         # Prometheus/DCGM 연동 후 true
  prometheusUrl: http://prometheus-server.monitoring.svc.cluster.local

codeServer:
  enabled: true
  image: <OUR_HARBOR>/omniverse/code-server:latest
  port: 8443

defaultGpuBans: []
```

## 5. 구현 단계 계획

### Phase 0 — 현재 클러스터 능력 확인

목적: DRA를 바로 켤 수 있는지 판단한다.

확인 명령:

```bash
kubectl api-resources | grep resource.k8s.io
kubectl get deviceclass
kubectl get resourceslices
kubectl get nodes -o wide
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\t"}{.metadata.labels.nvidia\.com/gpu\.product}{"\n"}{end}'
```

판단:

| 결과 | 선택 |
| --- | --- |
| `DeviceClass gpu.nvidia.com`과 `ResourceSlice`가 있음 | DRA path 사용 가능 |
| 없음 | 1차는 `DRA_ENABLED=0`, 기존 `nvidia.com/gpu: 1` 방식으로 검증 |

### Phase 1 — 이미지 정리

목표 이미지:

```text
<OUR_HARBOR>/omniverse/isaac-ui:<tag>
<OUR_HARBOR>/omniverse/isaac-sim:6.0
<OUR_HARBOR>/omniverse/code-server:<tag>
<OUR_HARBOR>/omniverse/otel-collector-contrib:<tag>  # metrics 사용 시
<OUR_HARBOR>/omniverse/node-exporter:<tag>            # netstat metrics 사용 시
```

해야 할 일:

1. `isaac-sim-image`는 `nvcr.io/nvidia/isaac-sim:6.0.0` 기반으로 build한다.
2. NGC login이 필요한 build host에서만 build한다.
3. 결과 이미지는 우리 Harbor로 push한다.
4. `isaac-ui` image도 우리 Harbor로 push한다.
5. metrics/code-server sidecar 이미지는 public registry 의존을 줄이기 위해 Harbor mirror를 권장한다.

기대 효과:

- 클러스터 노드가 외부 registry에 의존하지 않음
- 이미지 태그를 preset에서 고정 가능
- 원본 `5.1-exp1`/`6.0` 혼동 제거

### Phase 2 — `eecs-k8s` app catalog 추가

작업:

1. `apps/omniverse-isaac-saas` Helm chart 생성
2. 원본 `deploy/k8s/rbac.yaml`을 Helm template으로 변환
3. 원본 `deploy/k8s/deployment.yaml`을 values 기반 Helm template으로 변환
4. 원본 `deploy/k8s/service.yaml`을 values 기반 Helm template으로 변환
5. 하드코딩된 값 제거
6. feature graph 등록
7. `helm template`으로 Application 생성 여부 검증

기대 효과:

- `eecs-k8s`는 공통 엔진 역할만 수행
- C/TwinX/DataX마다 같은 app catalog를 재사용 가능
- namespace, image, IP, 노드, DRA 여부는 preset에서만 관리

### Phase 3 — `c-k8s` preset patch 추가

작업:

1. `c-k8s/values.yaml`에 feature 추가
2. `c-k8s/patches/omniverse-isaac-saas/values.yaml` 작성
3. Nucleus endpoint를 현재 검증된 주소로 설정
4. image registry를 우리 Harbor로 설정
5. GPU node 목록을 C 클러스터 실제 노드로 설정
6. 1차 검증은 `DRA_ENABLED=false`로 시작
7. Secret은 실험 단계에서는 GitOps 값 또는 수동 Secret 중 하나로 통일

기대 효과:

- C 클러스터 전용 값이 engine에 섞이지 않음
- 나중에 TwinX로 옮길 때 `twinx-k8s/patches/...`만 바꾸면 됨

### Phase 4 — 1차 배포 검증, DRA 없이

목표: 가장 단순한 형태로 Isaac Sim 인스턴스가 뜨는지 확인한다.

검증 항목:

```bash
kubectl -n omniverse get deploy isaac-ui
kubectl -n omniverse get svc isaac-ui
curl -fsS http://<ISAAC_UI_IP>/healthz
```

UI에서 인스턴스 1개 생성 후:

```bash
kubectl -n omniverse get deploy,svc,pod -l group=dt-sim -o wide
kubectl -n omniverse logs deploy/dt-sim-<name> -c isaac-sim --tail=100
```

성공 조건:

- `isaac-ui` 접속 가능
- UI에서 Isaac Sim 인스턴스 생성 가능
- 인스턴스 Pod가 GPU 노드에 스케줄됨
- 인스턴스 Service가 LoadBalancer IP를 받음
- Isaac Sim WebRTC client에서 접속 가능
- Isaac Sim이 Nucleus endpoint를 사용함

### Phase 5 — DRA 검증 후 활성화

DRA가 있는 클러스터라면 다음을 검증한다.

```bash
kubectl get deviceclass
kubectl get resourceslices
kubectl -n omniverse get resourceclaimtemplates
kubectl -n omniverse get resourceclaims
```

성공 조건:

- 인스턴스 생성 시 `dt-sim-<name>-gpu` ResourceClaimTemplate 생성
- Pod가 `resourceClaims`를 통해 GPU를 할당받음
- 특정 UUID ban 시 해당 GPU가 선택되지 않음
- A100 등 `denyProducts`에 걸린 GPU가 제외됨

DRA 실패 시 fallback:

```yaml
instance:
  dra:
    enabled: false
```

### Phase 6 — workspace persistence 결정

선택지:

| 선택 | 설명 | 장점 | 단점 |
| --- | --- | --- | --- |
| `emptyDir` | Pod 재시작 시 workspace 사라짐 | 단순, PVC 불필요 | 사용자 수정사항 보존 안 됨 |
| RBD PVC | 인스턴스별 workspace PVC 생성 | 사용자 코드/extension 보존 | PVC lifecycle/정리 필요 |
| Nucleus 중심 | asset/USD는 Nucleus에 저장, workspace는 임시 | 운영 단순 | 코드 작업 지속성은 약함 |

1차 권장:

```yaml
workspace:
  persist: false
```

운영 전 재검토:

```yaml
workspace:
  persist: true
  storageClassName: rook-ceph-block-nucleus-retain 또는 별도 isaac-workspace-retain
```

## 6. 중요한 설계 결정

### 결정 1 — ArgoCD가 개별 Isaac Sim 인스턴스를 관리하지 않는다

이유:

- 개별 인스턴스는 사용자 요청에 따라 생성/삭제된다.
- Git에 인스턴스를 모두 나열하면 self-service 의미가 사라진다.
- ArgoCD prune이 사용자 인스턴스를 지우는 사고를 막아야 한다.

따라서 GitOps 관리 범위는 다음으로 제한한다.

```text
GitOps 관리:
  - isaac-ui Deployment
  - isaac-ui Service
  - RBAC
  - 기본 Secret 참조

isaac-ui 동적 관리:
  - dt-sim-* Deployment
  - dt-sim-*-stream Service
  - dt-sim-*-gpu ResourceClaimTemplate
  - optional workspace PVC
```

### 결정 2 — engine에는 기본값만, cluster 값은 preset에 둔다

`eecs-k8s`에 넣으면 안 되는 값:

```text
LoadBalancer 고정 IP
C/TwinX 실제 노드명
Nucleus 비밀번호
Harbor credential
GPU UUID ban 목록
```

이 값들은 `c-k8s` 또는 `twinx-k8s` patch에 둔다.

### 결정 3 — DRA는 바로 필수로 만들지 않는다

이유:

- 원본은 DRA를 강하게 활용하지만, 우리 클러스터의 DRA 준비 상태를 먼저 확인해야 한다.
- DRA 미준비 상태에서 feature를 켜면 인스턴스 생성이 실패할 수 있다.

권장 흐름:

```text
1차: DRA_ENABLED=false로 Isaac Sim 실행 검증
2차: DeviceClass/ResourceSlice 확인
3차: DRA_ENABLED=true로 GPU UUID/product ban 검증
```

## 7. Secret 처리 계획

필요한 Secret:

| Secret | 용도 |
| --- | --- |
| `harbor-regcred` | `isaac-ui`, sidecar, Isaac Sim image pull |
| `nucleus-cred` | Isaac Sim이 Nucleus에 로그인할 때 사용하는 비밀번호 |
| 선택: `harbor-api` | UI가 private Harbor catalog를 읽을 때 사용 |

실험 단계 선택지:

```text
A. c-k8s patch values에서 Secret manifest 렌더링
B. kubectl create secret으로 클러스터에 직접 생성
```

운영 단계 권장:

```text
External Secrets + OpenBao
```

문서 원칙:

- Secret 원문 값은 runbook에 기록하지 않는다.
- Git에 Secret 값을 넣는 경우에도 해당 레포가 private인지 확인한다.
- 운영 전에는 ESO/OpenBao 이관 계획을 별도로 만든다.

## 8. 검증 기준

### 렌더링 검증

```bash
helm template c eecs-k8s -f c-k8s/values.yaml
helm template omniverse-isaac-saas eecs-k8s/apps/omniverse-isaac-saas \
  -f c-k8s/patches/omniverse-isaac-saas/values.yaml
```

성공 조건:

- SmartX root render에서 `c-omniverse-isaac-saas` Application 생성
- app chart render에서 ServiceAccount/RBAC/Deployment/Service 생성
- placeholder 값이 남지 않음
- image, namespace, Nucleus endpoint, node list가 preset 값으로 치환됨

### 클러스터 검증

```bash
kubectl -n omniverse get deploy,svc,pod -l app=isaac-ui -o wide
curl -fsS http://<ISAAC_UI_IP>/healthz
```

인스턴스 생성 후:

```bash
kubectl -n omniverse get deploy,svc,pod -l group=dt-sim -o wide
kubectl -n omniverse get resourceclaimtemplates,resourceclaims  # DRA enabled일 때
kubectl -n omniverse describe pod -l group=dt-sim
```

### 사용자 검증

- 브라우저에서 `isaac-ui` 접속
- `New instance` 생성
- Isaac Sim WebRTC Streaming Client에서 인스턴스 IP 입력
- Isaac Sim 내부에서 Nucleus asset 접근 확인
- Nucleus에 새 USD/asset 저장 확인

## 9. 예상 리스크와 대응

| 리스크 | 원인 | 대응 |
| --- | --- | --- |
| ImagePullBackOff | Harbor trust/pull secret 문제 | node containerd registry 설정, `harbor-regcred` 확인 |
| Isaac Sim Pod Pending | GPU 부족 또는 DRA 실패 | `DRA_ENABLED=false` fallback, node list 확인 |
| Nucleus login 실패 | OMNI_SERVER/OMNI_USER/OMNI_PASS 불일치 | `nucleus-cred` Secret, Nucleus 계정 확인 |
| WebRTC 접속 실패 | LB IP/port/firewall 문제 | Service ports 8211/49100/47998 확인 |
| ArgoCD가 인스턴스 삭제 | 동적 인스턴스를 GitOps path에 포함 | GitOps 범위를 `isaac-ui`로 제한 |
| workspace 데이터 유실 | 기본 emptyDir | 필요 시 RBD workspace PVC 활성화 |
| A100에 스케줄되어 스트리밍 불가 | NVENC 없음 | `denyProducts: [A100]`, DRA product selector 검증 |
| GPU UUID ban 미동작 | DRA 미준비 | DeviceClass/ResourceSlice 확인, DRA 예제로 선검증 |

## 10. 실행 순서 체크리스트

- [ ] C/TwinX 클러스터 DRA 지원 여부 확인
- [ ] 우리 Harbor project 결정
- [ ] `isaac-ui` image build/push
- [ ] `isaac-sim:6.0` image build/push
- [ ] sidecar image mirror 여부 결정
- [ ] `eecs-k8s/apps/omniverse-isaac-saas` chart 추가
- [ ] feature graph 추가
- [ ] `c-k8s/patches/omniverse-isaac-saas/values.yaml` 작성
- [ ] `helm template` 렌더링 검증
- [ ] ArgoCD sync
- [ ] `isaac-ui /healthz` 확인
- [ ] UI에서 test instance 생성
- [ ] Isaac Sim WebRTC 접속 확인
- [ ] Isaac Sim -> Nucleus 접속/저장 확인
- [ ] DRA enabled 재검증
- [ ] 운영 Secret 방식을 ESO/OpenBao로 정리

## 11. ADR

### Decision

`SmartX-Team/Omniverse/isaac-saas`를 그대로 ArgoCD Kustomize 앱으로 가져오지 않고, `eecs-k8s` 공통 app catalog + cluster preset patch 구조로 변환한다.

### Drivers

1. SmartX 방식과 맞춰 여러 클러스터에서 재사용해야 한다.
2. C/TwinX별 IP, 노드, Secret, GPU UUID는 클러스터마다 다르다.
3. 사용자가 만든 Isaac Sim 인스턴스는 GitOps prune 대상이 되면 안 된다.
4. Nucleus와 Isaac Sim을 같은 Omniverse 운영 단위로 묶어야 한다.

### Alternatives considered

| 대안 | 판단 |
| --- | --- |
| 원본 `deploy/k8s`를 그대로 ArgoCD에 연결 | 빠르지만 SmartX feature/preset 구조와 맞지 않음 |
| 개별 Isaac Sim 인스턴스를 Git에 직접 작성 | self-service 목적과 충돌, prune 위험 큼 |
| `isaac-ui` 없이 StatefulSet/Deployment만 직접 배포 | 단일 인스턴스 PoC는 쉽지만 멀티테넌트 운영이 어려움 |
| `eecs-k8s` chart + preset patch | 재사용성, 운영 분리, SmartX 구조에 가장 적합 |

### Consequences

- 초기 작업량은 늘어난다.
- 대신 C/TwinX/DataX 등 다른 클러스터에 동일 app catalog를 재사용할 수 있다.
- 클러스터별 차이는 patch values로만 관리된다.
- ArgoCD는 플랫폼 UI만 관리하고, 사용자 인스턴스 lifecycle은 `isaac-ui`가 담당한다.

### Follow-ups

1. DRA 지원 여부를 실제 클러스터에서 확인한다.
2. `isaac-ui`의 `OMNI_SERVER` 하드코딩을 values/env 기반으로 바꾼다.
3. `defaultGpuBans`는 우리 GPU UUID 기준으로 다시 작성한다.
4. workspace persistence 정책을 운영 전에 확정한다.
5. Secret은 실험 후 ESO/OpenBao 방식으로 정리한다.
