# ScaleX Karmada + SmartX 운영 계획

이 문서가 **현재 계획의 입구**입니다. 먼저 이 파일만 보면 됩니다.

- 운영 모델/레포 구조/소유권 기준: 이 `README.md`
- 실제 장애/운영 명령: [`RUNBOOK.md`](./RUNBOOK.md)
- Karmada 개념 설명: [`CONCEPTS.md`](./CONCEPTS.md)
- 과거 kind 실험 기록: [`lab/`](./lab/)

---

## 0. 현재 결론

현재 ScaleX PoC의 결론은 다음입니다.

```text
실제 클러스터는 4개:
  TowerX, DataX, EdgeX, TwinX

운영 repo는 5개:
  towerx-k8s, scalex-federation, datax-k8s, edgex-k8s, twinx-k8s

엔진/참조 repo:
  smartx-k8s  = SmartX 엔진. feature graph/app catalog 보유
  mobilex-k8s = 참고용 preset. 우리가 관리하거나 Argo CD에 연결하지 않음

Argo CD server는 TowerX에 1개만 둔다.
Karmada Control Plane도 TowerX에 둔다.
Resource Pool/poolx/pullx는 현재 최종 구조에 포함하지 않는다.
```

핵심 소유권 원칙:

```text
같은 live Kubernetes resource는 반드시 하나의 repo만 소유한다.
cluster-local 리소스와 Karmada federation 리소스를 같은 repo에 섞지 않는다.
```

---

## 1. 전체 구조

```text
towerx-k8s
  -> TowerX Argo CD
    ├─ towerx-k8s
    │   -> TowerX cluster
    │
    ├─ scalex-federation
    │   -> Karmada API Server
    │     -> DataX / EdgeX / TwinX
    │
    ├─ datax-k8s
    │   -> DataX cluster
    │
    ├─ edgex-k8s
    │   -> EdgeX cluster
    │
    └─ twinx-k8s
        -> TwinX cluster
```

의미:

```text
TowerX Argo CD는 여러 repo를 연결한다.
단일 클러스터 전용 리소스는 각 *-k8s repo가 직접 해당 cluster destination으로 sync한다.
멀티클러스터 placement가 필요한 리소스만 scalex-federation이 Karmada API Server로 sync한다.
```

---

## 1.1 동작 방식

ScaleX에서는 앱이 배포되는 경로가 세 가지입니다.

### A. TowerX 제어 평면 동작

TowerX에는 단일 Argo CD가 있습니다. 이 Argo CD가 전체 repo 연결의 시작점입니다.

```text
towerx-k8s/argocd/bootstrap/root-app.yaml
  -> TowerX Argo CD의 tower-root Application
    -> towerx-k8s/argocd/control-plane/
      -> AppProject 생성
      -> scalex-federation Application 생성
      -> datax-local / edgex-local / twinx-local Application 생성
```

역할:

```text
tower-root
  = App of Apps root
  = 어떤 repo를 어떤 project/destination으로 sync할지 관리
```

TowerX 제어 평면에 해당하는 것:

```text
- Argo CD server
- Karmada Control Plane
- Argo CD AppProject
- Argo CD root/child Application
```

일반 서비스 workload는 TowerX에 두지 않습니다.

---

### B. cluster-local 앱 동작

특정 클러스터 하나에서만 필요한 앱은 해당 cluster repo가 직접 관리합니다.

예: DataX 전용 앱

```text
datax-k8s
  -> TowerX Argo CD Application: datax-local 또는 SmartX-generated datax-* Application
    -> Argo CD destination.name: datax
      -> DataX Kubernetes API Server
        -> kube-scheduler가 DataX node 선택
          -> kubelet이 Pod 실행
```

즉, 이 경로에서는 Karmada를 거치지 않습니다.

```text
Git repo: datax-k8s
배포기: TowerX Argo CD
대상: DataX cluster
Karmada: 사용 안 함
```

EdgeX/TwinX도 동일합니다.

```text
edgex-k8s -> TowerX Argo CD -> EdgeX cluster
twinx-k8s -> TowerX Argo CD -> TwinX cluster
```

---

### C. Karmada federation 앱 동작

두 개 이상 클러스터에 전파하거나, replica 분산/override/failover가 필요한 앱은 `scalex-federation`이 담당합니다.

```text
scalex-federation/federation/
  -> TowerX Argo CD Application: scalex-federation
    -> Argo CD destination.name: karmada-apiserver
      -> Karmada API Server
        -> PropagationPolicy가 대상 cluster 선택
          -> Karmada scheduler가 ResourceBinding 생성
            -> Karmada controller가 member cluster에 Work 전파
              -> 각 member cluster의 kube-scheduler가 node 선택
                -> kubelet이 Pod 실행
```

예:

```text
render-demo Deployment replicas=4
  -> Karmada policy
    -> TwinX replicas=3
    -> EdgeX replicas=1
```

이 경로에서 Argo CD는 member cluster를 직접 만지지 않습니다.

```text
Git repo: scalex-federation
배포기: TowerX Argo CD
Argo CD 대상: Karmada API Server
실제 실행 대상: DataX / EdgeX / TwinX
Karmada: 사용함
```

---

### D. SmartX feature graph 앱 동작

SmartX 방식은 `smartx-k8s` 엔진과 각 cluster preset을 조합합니다.

```text
smartx-k8s
  = 엔진 / feature graph / app catalog / Application 생성 템플릿

cluster-k8s
  = preset / values / patches
```

동작 흐름:

```text
1. datax-k8s/values.yaml에서 feature 선택

   features:
     - scalex.io/data/postgresql
     - scalex.io/healthcheck

2. TowerX Argo CD가 smartx-k8s Helm chart를 렌더링

   source 1: smartx-k8s 엔진
   source 2: datax-k8s preset values/patches

3. smartx-k8s/templates/applications.yaml 실행

   - apps/template/features.yaml 읽기
   - feature dependency graph 계산
   - enabled feature에 해당하는 apps/*/manifest.yaml 선택
   - Argo CD Application 생성

4. 생성된 Application이 실제 앱을 설치

   datax-scalex-healthcheck
     -> project: datax-ops
     -> destination.name: datax

   datax-scalex-postgresql
     -> project: datax-ops
     -> destination.name: datax
```

SmartX app 하나는 보통 다음 세 값을 합쳐 배포됩니다.

```text
1. upstream Helm chart 또는 smartx-k8s 내부 local chart
2. smartx-k8s/apps/<app>/values.yaml
3. <cluster>-k8s/patches/<app>/values.yaml
```

`manifest.yaml`에서 `patched: true`인 앱은 해당 preset repo에 다음 파일이 있어야 합니다.

```text
<cluster>-k8s/patches/<app>/values.yaml
```

없으면 Argo CD sync가 실패할 수 있습니다.


현재 kind PoC에서 검증 중인 SmartX feature graph 앱:

| preset | features | 생성되는 Application |
| --- | --- | --- |
| `datax-k8s` | `scalex.io/data/postgresql`, `scalex.io/healthcheck` | `datax`, `datax-scalex-healthcheck`, `datax-scalex-postgresql` |
| `edgex-k8s` | `scalex.io/healthcheck` | `edgex`, `edgex-scalex-healthcheck` |
| `twinx-k8s` | `scalex.io/healthcheck` | `twinx`, `twinx-scalex-healthcheck` |

`datax`, `edgex`, `twinx` root Application은 `towerx-k8s/argocd/bootstrap/smartx-root-apps.yaml`로 최초 1회 생성하고, 이후 각 root Application이 smartx-k8s 렌더링 결과를 자기 project에 맞게 관리합니다.

---

### E. Node까지 내려가는 최종 실행 흐름

Karmada를 쓰든 안 쓰든, member cluster 안에 들어온 뒤에는 일반 Kubernetes와 같습니다.

```text
Deployment / Job / StatefulSet
  -> 해당 cluster의 kube-scheduler
    -> node label / taint / affinity / resource request 기준으로 node 선택
      -> kubelet이 container 실행
```

Kueue는 지금 필수가 아닙니다.

```text
Kueue는 Job/Ray/Spark/GPU batch workload가 많아져서
대기열, quota, admission control이 필요할 때 member cluster 내부에 도입한다.
```

---

## 2. repo별 역할

| repo | 성격 | 역할 | 여기에 두는 것 | 여기에 두지 않는 것 |
| --- | --- | --- | --- | --- |
| `smartx-k8s` | 엔진 | Helm chart, app catalog, feature graph, Application 생성 템플릿 | `apps/template/features.yaml`, `apps/<app>/manifest.yaml`, 공통 chart/app 정의 | 클러스터별 비밀값, 특정 클러스터 전용 values |
| `towerx-k8s` | TowerX preset/control | TowerX 제어 클러스터와 단일 Argo CD bootstrap | Argo CD root, AppProject, child Application, Karmada control-plane 설치 계획 | 일반 서비스 workload |
| `scalex-federation` | Karmada federation repo | 멀티클러스터 전파 정책 관리 | 공통 리소스, `PropagationPolicy`, `OverridePolicy`, `WorkloadRebalancer` | CNI/CSI/GPU Operator 같은 cluster-local 인프라 |
| `datax-k8s` | DataX preset | DataX cluster-local 리소스 | DataX 전용 앱, DataX storage/data/analytics, DataX 전용 patches | TwinX/EdgeX 리소스, Karmada policy |
| `edgex-k8s` | EdgeX preset | EdgeX cluster-local 리소스 | EdgeX 전용 앱, edge/GPU/local ingress, EdgeX 전용 patches | DataX/TwinX 리소스, Karmada policy |
| `twinx-k8s` | TwinX preset | TwinX cluster-local 리소스 | TwinX digital twin/render/AI serving 앱, TwinX 전용 patches | DataX/EdgeX 리소스, Karmada policy |
| `mobilex-k8s` | 참고용 | SmartX preset 구조 참고 | 구조 분석용 reference | 우리 Argo CD 연결 대상 아님 |

---

## 3. repo 구조

### 3.1 `smartx-k8s` 엔진 구조

`smartx-k8s`는 `mobilex-k8s`나 `datax-k8s`처럼 특정 클러스터 설정 repo가 아니라 **엔진 repo**입니다.

```text
smartx-k8s/
├── Chart.yaml                         # repo 전체가 하나의 Helm chart
├── values.yaml                        # upstream default values/features
├── templates/applications.yaml         # feature graph를 읽고 Argo CD Application 생성
├── apps/
│   ├── template/
│   │   ├── features.yaml               # feature 의존성 그래프
│   │   ├── defaults.yaml               # ../../values.yaml 참조
│   │   └── application.yaml            # Application 생성 템플릿
│   └── <app>/
│       ├── manifest.yaml               # 앱 metadata, feature, chart/source 정의
│       ├── values.yaml                 # 앱 공통 values
│       ├── patches.yaml                # Helm valuesObject 생성용 patch
│       └── templates/                  # local chart일 경우 사용
└── README.md
```

중요:

```text
feature graph는 각 preset repo에 복사하지 않는다.
feature graph는 smartx-k8s 엔진에만 둔다.
각 cluster-k8s repo는 values.yaml에서 필요한 feature만 선택한다.
```

---

### 3.2 `towerx-k8s` 구조

```text
towerx-k8s/
├── manifest.yaml                       # SmartX preset 식별자
├── values.yaml                         # TowerX values. repo.name은 smartx-k8s 엔진을 가리킴
├── patches/                            # SmartX 앱 override 예정 위치
├── argocd/
│   ├── bootstrap/
│   │   ├── root-app.yaml               # 최초 1회 apply할 TowerX root Application
│   │   └── smartx-root-apps.yaml       # datax/edgex/twinx SmartX root Application bootstrap
│   └── control-plane/
│       ├── 00-project.yaml             # AppProject 정의
│       ├── 05-towerx-cluster.yaml      # SmartX root app용 TowerX cluster alias
│       ├── 10-scalex-federation-app.yaml
│       ├── 20-datax-local-app.yaml
│       ├── 21-twinx-local-app.yaml
│       └── 22-edgex-local-app.yaml
├── charts/                             # TowerX 전용 local chart 예정 위치
├── ingresses/                          # TowerX ingress 예정 위치
├── projects/                           # AppProject 정책 확장 위치
└── docs/
```

`towerx-k8s`는 `mobilex-k8s`식 preset 구조를 따르지만, TowerX 제어 클러스터이므로 Argo CD control-plane manifest도 함께 보관합니다.

---

### 3.3 `datax-k8s`, `edgex-k8s`, `twinx-k8s` 구조

세 repo는 모두 `mobilex-k8s`와 같은 **cluster preset 계열**입니다.

```text
<cluster>-k8s/
├── manifest.yaml                       # cluster name/group/owner
├── values.yaml                         # cluster values + 활성화할 SmartX features
├── patches/                            # smartx-k8s apps/<app>/values.yaml override
├── apps/local-demo/                    # 현재 PoC용 직접 sync demo app
├── charts/                             # cluster 전용 local chart 예정 위치
├── ingresses/                          # cluster 전용 ingress 예정 위치
├── projects/                           # cluster 전용 project/policy 예정 위치
├── kiss/                               # KISS inventory 예정 위치
└── docs/
```

현재 `apps/local-demo/`는 “단일 TowerX Argo CD가 각 member cluster에 직접 sync할 수 있는지” 확인하기 위한 PoC 경로입니다.
향후 실제 SmartX feature graph 방식으로 앱을 전환하면, 가능하면 `apps/local-demo/` 같은 직접 경로보다 `smartx-k8s` 앱 카탈로그 + preset `features`/`patches` 조합을 우선합니다.

---

### 3.4 `scalex-federation` 구조

`scalex-federation`은 `mobilex-k8s`식 preset이 아닙니다. **Karmada 전용 repo**입니다.

```text
scalex-federation/
├── README.md
├── docs/
└── federation/
    ├── kustomization.yaml
    ├── common/
    │   ├── 00-namespaces.yaml
    │   └── namespace-propagation.yaml
    └── apps/
        ├── render-demo/
        │   ├── resources.yaml
        │   └── propagation-policy.yaml
        └── data-hold-job/
            ├── resources.yaml
            └── propagation-policy.yaml
```

여기에는 다음만 둡니다.

```text
- Karmada API Server에 넣을 resource template
- PropagationPolicy
- OverridePolicy
- WorkloadRebalancer
- 멀티클러스터 placement/failover/rebalance 정책
```

---

## 4. Argo CD AppProject 이름 규칙

SmartX/mobilex 원래 관례는 다음입니다.

```text
AppProject 이름 = <cluster.name>-<manifest.spec.group>
```

예시:

```text
mobilex + ops -> mobilex-ops
datax   + ops -> datax-ops
edgex   + ops -> edgex-ops
twinx   + ops -> twinx-ops
towerx + ops -> towerx-ops
```

현재 PoC AppProject:

| AppProject | 용도 | Argo CD destination |
| --- | --- | --- |
| `default` | `tower-root` bootstrap용. chicken-and-egg 방지 | TowerX in-cluster |
| `towerx-ops` | TowerX 제어용 SmartX-generated Application 예정 | TowerX cluster |
| `scalex-federation` | Karmada federation repo | Karmada API Server |
| `datax-ops` | DataX cluster-local repo/apps | Argo CD cluster name `datax` |
| `edgex-ops` | EdgeX cluster-local repo/apps | Argo CD cluster name `edgex` |
| `twinx-ops` | TwinX cluster-local repo/apps | Argo CD cluster name `twinx` |

헷갈리기 쉬운 부분:

```yaml
# 맞음
spec:
  project: datax-ops
  destination:
    name: datax

# 틀림
spec:
  project: datax-ops
  destination:
    name: datax-ops
```

`project`는 AppProject 이름이고, `destination.name`은 Argo CD에 등록된 실제 cluster name입니다.

---

## 5. 앱을 어디에 둘지 결정하는 기준

```text
1. TowerX 제어용인가?
   -> towerx-k8s

2. 두 개 이상 클러스터에 Karmada policy로 배치해야 하는가?
   -> scalex-federation

3. 특정 클러스터 하나에서만 쓰는가?
   -> datax-k8s / edgex-k8s / twinx-k8s

4. Cilium, CSI, GPU Operator 같은 클러스터 기본 인프라인가?
   -> 각 cluster-local *-k8s preset에서 feature/patch로 관리

5. 여러 클러스터에서 같은 앱을 켜야 하지만 Karmada placement가 필요 없는가?
   -> smartx-k8s app catalog에 공통 app을 두고 각 preset에서 feature를 켠다.
```

예시:

| 앱/리소스 | 위치 | 이유 |
| --- | --- | --- |
| Argo CD root/app projects | `towerx-k8s` | TowerX 제어 평면 |
| Karmada Control Plane | `towerx-k8s` | TowerX 제어 평면 |
| render workload를 TwinX 3, EdgeX 1로 분산 | `scalex-federation` | Karmada replicaScheduling 필요 |
| DataX에만 띄우는 PostgreSQL | `datax-k8s` preset에서 feature 활성화 또는 DataX 전용 patch | 단일 cluster 전용 |
| Cilium | 각 cluster-k8s preset | cluster-local CNI. federation 대상 아님 |
| GPU Operator | EdgeX/TwinX 등 해당 cluster-k8s preset | cluster-local node/GPU 인프라 |
| 공통 demo app을 DataX/EdgeX/TwinX에 각각 설치 | `smartx-k8s` app catalog + 각 preset features | Karmada placement 없이 각 cluster-local로 설치 |

---

## 6. SmartX feature graph 사용 방식

### 6.1 원리

`smartx-k8s`는 다음 흐름으로 Application을 생성합니다.

```text
cluster-k8s/values.yaml
  features:
    - some.feature/name

        ↓

smartx-k8s/apps/template/features.yaml
  feature dependency graph 계산

        ↓

smartx-k8s/apps/*/manifest.yaml
  app.spec.app.features와 매칭

        ↓

smartx-k8s/templates/applications.yaml
  Argo CD Application 자동 생성
```

### 6.2 중요한 주의사항

`smartx-k8s`에서는 다음이 “아무것도 설치하지 않음”이 아닙니다.

```yaml
features: []
```

위 값은 upstream default feature 전체를 의미할 수 있습니다. PoC에서 전체 앱 카탈로그가 갑자기 렌더링되는 것을 막으려면 현재처럼 sentinel을 사용합니다.

```yaml
features:
  - ""
```

실제 앱을 켤 때만 필요한 feature를 명시합니다.

```yaml
features:
  - scalex.io/demo/common
  - scalex.io/demo/postgresql
```

---

## 7. 현재 실제로 띄운 앱

현재까지 실제 cluster에 띄운 것은 두 계열입니다.

### 7.1 cluster-local 직접 sync PoC

이건 `smartx-k8s` feature graph가 아니라, TowerX 단일 Argo CD가 각 repo를 직접 읽어 각 cluster destination으로 sync할 수 있는지 확인한 PoC입니다.

| Argo CD Application | Project | Repo/path | Destination | 상태 |
| --- | --- | --- | --- | --- |
| `datax-local` | `datax-ops` | `datax-k8s/apps/local-demo` | `datax` | Synced/Healthy |
| `edgex-local` | `edgex-ops` | `edgex-k8s/apps/local-demo` | `edgex` | Synced/Healthy |
| `twinx-local` | `twinx-ops` | `twinx-k8s/apps/local-demo` | `twinx` | Synced/Healthy |

실제 리소스:

```text
DataX  namespace scalex-local-datax   -> scalex-datax-local-app Deployment/Service/ConfigMap
EdgeX  namespace scalex-local-edgex   -> scalex-edgex-local-app Deployment/Service/ConfigMap
TwinX  namespace scalex-local-twinx   -> scalex-twinx-local-app Deployment/Service/ConfigMap
```

### 7.2 Karmada federation PoC

이건 `scalex-federation`이 Karmada API Server로 sync하고, Karmada가 member cluster로 전파한 PoC입니다.

| Argo CD Application | Project | Repo/path | Destination | 전파 결과 |
| --- | --- | --- | --- | --- |
| `scalex-federation` | `scalex-federation` | `scalex-federation/federation` | `karmada-apiserver` | DataX/EdgeX/TwinX로 전파 |

실제 전파 결과:

```text
scalex-render-demo Deployment
  -> edgex replicas=1
  -> twinx replicas=3

scalex-data-hold Job
  -> datax replicas=1, Complete
```

---

## 8. 아직 남은 검증

아직 완료되지 않은 것:

```text
smartx-k8s feature graph가 실제 Argo CD Application을 생성하고,
그 Application이 DataX/EdgeX/TwinX에 앱을 설치하는 end-to-end 검증
```

다음 실험 계획:

```text
1. smartx-k8s에 안전한 demo app catalog 추가
   - scalex.io/demo/common
   - scalex.io/demo/postgresql

2. preset에서 feature만 선택
   - datax-k8s: scalex.io/demo/common + scalex.io/demo/postgresql
   - edgex-k8s: scalex.io/demo/common
   - twinx-k8s: scalex.io/demo/common

3. TowerX Argo CD에 SmartX-generated root Application을 bootstrap

4. 기대 결과
   - DataX/EdgeX/TwinX에 common demo app 생성
   - DataX에만 PostgreSQL demo app 생성
   - 생성된 Application 이름과 Project가 SmartX 관례를 따름
```

이 실험이 끝나야 “SmartX feature graph 방식으로 앱 배포까지 검증 완료”라고 말할 수 있습니다.

---

## 9. Resource Pool 상태

현재는 Resource Pool을 하지 않습니다.

```text
현재 실제 클러스터:
  TowerX, DataX, EdgeX, TwinX

현재 Karmada member:
  DataX, EdgeX, TwinX

현재 제외:
  Resource Pool, poolx, pullx
```

`lab/` 아래 과거 실험에는 `poolx`/`pullx` 기록이 남아 있을 수 있습니다. 이는 archive이며 현재 최종 운영 모델에는 포함하지 않습니다.

---

## 10. 현재 검증 명령 요약

```bash
# Argo CD Applications
kubectl --context kind-tower -n argocd get applications.argoproj.io \
  -o custom-columns=NAME:.metadata.name,PROJECT:.spec.project,SYNC:.status.sync.status,HEALTH:.status.health.status

# Argo CD AppProjects
kubectl --context kind-tower -n argocd get appprojects.argoproj.io

# Karmada member clusters
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusters

# Karmada ResourceBindings
kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n scalex-render \
  get resourcebindings.work.karmada.io
kubectl --kubeconfig ~/.kube/karmada-apiserver.config -n scalex-data \
  get resourcebindings.work.karmada.io
```

---

## 9. 현재 kind PoC 최종 검증 결과

### 9.1 kind cluster 구성

현재 kind 환경은 실제 Kubernetes cluster 4개로 구성되어 있습니다.

```text
tower
datax
edgex
twinx
```

각 cluster는 현재 1-node kind cluster입니다.

```text
tower-control-plane
datax-control-plane
edgex-control-plane
twinx-control-plane
```

따라서 지금 검증한 것은 “여러 Kubernetes cluster 간 전파/배포”이고, “한 cluster 내부의 여러 worker node 분산 scheduling”은 아직 검증하지 않았습니다.

### 9.2 Argo CD 최종 상태

현재 TowerX 단일 Argo CD의 주요 Application 상태는 모두 `Synced/Healthy`입니다.

```text
tower-root                 default             Synced   Healthy
scalex-federation          scalex-federation   Synced   Healthy

datax                      towerx-ops          Synced   Healthy
datax-scalex-healthcheck   datax-ops           Synced   Healthy
datax-scalex-postgresql    datax-ops           Synced   Healthy

edgex                      towerx-ops          Synced   Healthy
edgex-scalex-healthcheck   edgex-ops           Synced   Healthy

twinx                      towerx-ops          Synced   Healthy
twinx-scalex-healthcheck   twinx-ops           Synced   Healthy
```

`datax-local`, `edgex-local`, `twinx-local`도 아직 남아 있지만, 이것들은 초기 direct-sync 검증용 임시 앱입니다. 최종 구조에서는 SmartX-generated 앱으로 대체하거나 제거할 수 있습니다.

### 9.3 실제 member cluster 리소스

SmartX feature graph로 생성된 앱은 실제 member cluster에 리소스를 만들었습니다.

| cluster | namespace | 확인된 리소스 |
| --- | --- | --- |
| DataX | `scalex-system` | `scalex-healthcheck` Deployment/Service/ConfigMap, Pod Running |
| DataX | `scalex-data` | `scalex-postgresql` StatefulSet/Service/Secret, Pod Running |
| EdgeX | `scalex-system` | `scalex-healthcheck` Deployment/Service/ConfigMap, Pod Running |
| TwinX | `scalex-system` | `scalex-healthcheck` Deployment/Service/ConfigMap, Pod Running |

### 9.4 Karmada federation 최종 상태

Karmada member cluster는 3개입니다.

```text
datax   Ready
edgex   Ready
twinx   Ready
```

ScaleX federation ResourceBinding도 정상입니다.

```text
scalex-render-demo-deployment   Scheduled=True   FullyApplied=True
scalex-render-demo-service      Scheduled=True   FullyApplied=True
scalex-data-hold-job            Scheduled=True   FullyApplied=True
```

### 9.5 발견한 문제와 해결

#### 문제

SmartX root Application을 처음 적용했을 때 다음 앱이 자동 생성되었습니다.

```text
datax-kubelet-csr-approver
edgex-kubelet-csr-approver
twinx-kubelet-csr-approver
```

이 앱들은 `Unknown` 상태였고, Argo CD에는 다음 오류가 있었습니다.

```text
InvalidSpecError: application repo https://postfinance.github.io/kubelet-csr-approver is not permitted in project '<cluster>-ops'
```

#### 원인

`smartx-k8s/apps/kubelet-csr-approver/manifest.yaml`에서 `features: []`로 선언되어 있었습니다. SmartX 템플릿에서는 app feature가 비어 있으면 항상 생성됩니다.

이 앱은 KISS/bare-metal bootstrap에 필요한 성격인데, 현재 ScaleX kind PoC는 KISS를 쓰지 않습니다.

#### 해결

`kubelet-csr-approver` 앱을 KISS feature가 켜졌을 때만 생성되도록 변경했습니다.

```yaml
features:
  - org.ulagbulag.io/bare-metal-provisioning/kiss
```

그리고 `datax`, `edgex`, `twinx` SmartX root Application을 `--prune` sync하여 기존 `*-kubelet-csr-approver` Application을 제거했습니다.

#### 결과

현재 Argo CD Application 목록에는 `*-kubelet-csr-approver`가 남아 있지 않습니다.

---

## 10. 다음부터 사용하는 방법

### 10.1 먼저 결정할 것

새 리소스를 추가할 때는 아래 질문부터 답합니다.

```text
Q1. 여러 클러스터에 동시에 전파하거나 placement/weight/failover가 필요한가?
  -> yes: scalex-federation

Q2. 특정 클러스터 하나에서만 쓰는 앱인가?
  -> yes: datax-k8s / edgex-k8s / twinx-k8s 중 해당 repo

Q3. 앱 카탈로그나 feature graph 자체가 새로 필요한가?
  -> yes: smartx-k8s

Q4. TowerX Argo CD, AppProject, root Application, Karmada control plane 같은 제어 평면인가?
  -> yes: towerx-k8s
```

### 10.2 cluster-local 앱을 추가하는 방법

예: DataX에만 앱을 추가할 때

1. `smartx-k8s/apps/<app>/`에 앱 정의를 추가합니다.

```text
smartx-k8s/apps/<app>/
├── Chart.yaml
├── manifest.yaml
├── values.yaml
├── patches.yaml
└── templates/
```

2. `smartx-k8s/apps/template/features.yaml`에 feature를 추가합니다.

```yaml
scalex.io/data/my-app:
  requires:
    - scalex.io/data
```

3. `smartx-k8s/values.yaml`의 default feature 목록에도 같은 feature를 등록합니다. SmartX 템플릿은 feature graph와 default feature 목록의 일치 여부를 검증합니다.

4. 대상 preset에서 feature를 켭니다.

```yaml
# datax-k8s/values.yaml
features:
  - scalex.io/data/my-app
```

5. 앱이 `patched: true`이면 preset에 patch를 둡니다.

```text
datax-k8s/patches/<app>/values.yaml
```

6. 렌더링을 먼저 확인합니다.

```bash
helm template smartx ./smartx-k8s --values ./datax-k8s/values.yaml
```

7. push 후 TowerX Argo CD에서 해당 root app을 sync합니다.

```bash
argocd app sync datax --prune
```

### 10.3 여러 클러스터로 전파하는 앱을 추가하는 방법

여러 member cluster에 배포하거나 Karmada placement가 필요하면 `scalex-federation`에 둡니다.

```text
scalex-federation/federation/apps/<workload>/
├── resources.yaml
└── propagation-policy.yaml
```

그리고 `scalex-federation/federation/kustomization.yaml`에 path를 추가합니다.

검증:

```bash
argocd app sync scalex-federation
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebindings -A
```

### 10.4 TowerX 제어 평면을 바꾸는 방법

Argo CD Project, repo 연결, root Application, cluster alias 같은 제어 평면은 `towerx-k8s`에서 바꿉니다.

```text
towerx-k8s/argocd/control-plane/
```

적용:

```bash
argocd app sync tower-root --prune
```

SmartX root Application 최초 생성은 다음 파일을 사용합니다.

```bash
kubectl --context kind-tower -n argocd apply -f towerx-k8s/argocd/bootstrap/smartx-root-apps.yaml
```

### 10.5 확인 명령

Argo CD 전체 상태:

```bash
kubectl --context kind-tower -n argocd get app   -o custom-columns=NAME:.metadata.name,PROJECT:.spec.project,DEST:.spec.destination.name,SYNC:.status.sync.status,HEALTH:.status.health.status
```

Karmada member cluster:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get clusters
```

Karmada 전파 결과:

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebindings -A
```

member cluster 실제 리소스:

```bash
kubectl --context kind-datax get pods -A
kubectl --context kind-edgex get pods -A
kubectl --context kind-twinx get pods -A
```

### 10.6 문제 생기면 먼저 볼 것

| 증상 | 먼저 확인할 것 |
| --- | --- |
| Argo CD Application `Unknown` | AppProject `sourceRepos`, repo credential, destination name |
| `patched: true` 앱 sync 실패 | `<cluster>-k8s/patches/<app>/values.yaml` 존재 여부 |
| 원하지 않는 앱이 생성됨 | `smartx-k8s/apps/<app>/manifest.yaml`의 `features`가 비어 있는지 확인 |
| Karmada 전파 안 됨 | `PropagationPolicy` selector와 `ResourceBinding` 상태 확인 |
| Pod가 노드에 안 뜸 | member cluster의 scheduler event, node label/taint/affinity 확인 |
```

