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

## 0.1 이번 Nessie/Trino 작업 요약

이번 작업은 “DataX에만 뜨는 data-plane 앱을 SmartX/mobilex 방식으로 추가하면 실제로 동작하는가”를 확인한 것입니다. Karmada 전파가 아니라 **cluster-local SmartX feature graph 경로**로 검증했습니다.

### 무엇을 바꿨나

| repo | 파일 | 변경 내용 | 이유 |
| --- | --- | --- | --- |
| `smartx-k8s` | `apps/template/features.yaml` | `scalex.io/data/nessie`, `scalex.io/data/trino` 추가. `trino -> nessie` 의존성 선언 | feature graph 동작 검증 |
| `smartx-k8s` | `values.yaml`, `apps/template/defaults.yaml` | 새 `scalex.io/*` feature를 default feature 목록에 등록 | SmartX feature 검증 통과 |
| `datax-k8s` | `values.yaml` | `scalex.io/data/trino` 활성화 | DataX에서 Trino를 켜고 Nessie는 의존성으로 자동 생성되게 함 |
| `datax-k8s` | `README.md` | DataX 기준 변경/추가/검증 정리 | 이후 작업자가 같은 패턴으로 앱을 추가할 수 있게 함 |
| `netai-devsecops-runbook` | `README.md`, `RUNBOOK.md` | 현재 구조, 확인 명령, 문제/해결 기록 추가 | 보고/운영 참고용 |

### 무엇을 추가했나

| repo | 추가한 것 | 역할 |
| --- | --- | --- |
| `smartx-k8s` | `apps/scalex-nessie/` | Nessie REST catalog PoC 앱. feature는 `scalex.io/data/nessie` |
| `smartx-k8s` | `apps/scalex-trino/` | Trino single-node query engine PoC 앱. feature는 `scalex.io/data/trino` |
| `datax-k8s` | `patches/scalex-nessie/values.yaml` | DataX 전용 Nessie resource override |
| `datax-k8s` | `patches/scalex-trino/values.yaml` | DataX 전용 Trino resource override와 Nessie endpoint |

### 어떤 식으로 작성했나

```text
1. smartx-k8s/apps/<app>/manifest.yaml
   -> app 이름, namespace, feature, patched 여부 선언

2. smartx-k8s/apps/<app>/values.yaml
   -> 모든 cluster에 공통으로 쓸 기본값 작성

3. smartx-k8s/apps/<app>/templates/*
   -> PoC용 Deployment/Service/ConfigMap 작성

4. smartx-k8s/apps/template/features.yaml
   -> feature 의존성 작성
      scalex.io/data/app   -> scalex.io/data/postgresql
      scalex.io/data/trino -> scalex.io/data/nessie

5. datax-k8s/values.yaml
   -> DataX에서 직접 켤 feature만 선택
      scalex.io/data/app
      scalex.io/data/trino
      scalex.io/healthcheck

6. datax-k8s/patches/<app>/values.yaml
   -> DataX에서만 다른 resource/endpoint 값 override

7. TowerX Argo CD datax root Application sync
   -> SmartX 엔진이 datax-scalex-* Application들을 자동 생성
```

### 실제 검증 결과

```text
Argo CD:
  datax-scalex-nessie Synced/Healthy
  datax-scalex-trino  Synced/Healthy

kind-datax/scalex-data:
  deployment.apps/scalex-nessie 1/1 Running
  deployment.apps/scalex-trino  1/1 Running

Smoke test:
  Nessie /api/v2/config -> OK
  Trino  /v1/info       -> ACTIVE, version 482
  Trino CLI             -> select count(*) from tpch.tiny.nation = 25
```

### 이번 작업에서 일부러 하지 않은 것

| 하지 않은 것 | 이유 |
| --- | --- |
| `scalex-federation`에 Nessie/Trino 추가 | DataX 전용 앱이라 Karmada placement가 필요 없기 때문 |
| `datax-k8s/apps/`에 직접 앱 작성 | MobileX 방식처럼 앱 정의는 엔진 `smartx-k8s`, 선택/patch는 preset `datax-k8s`에 두기 때문 |
| 운영형 Iceberg/S3 warehouse 연동 | 이번 목표는 SmartX feature graph와 DataX 배포 검증. 운영형 lakehouse는 다음 단계 |
| Kueue 도입 | Trino/Nessie는 long-running service이고, batch admission/queue가 필요한 Job이 아니기 때문 |

---


## 0.2 이번 CNPG/Milvus 작업 요약

이번 작업은 “DataX에만 필요한 database/vector DB 앱을 SmartX/mobilex 방식으로 추가하면 실제로 동작하는가”를 확인한 것입니다. Karmada 전파가 아니라 **cluster-local SmartX feature graph 경로**로 검증했습니다.

### 무엇을 바꿨나

| repo | 파일 | 변경 내용 | 이유 |
| --- | --- | --- | --- |
| `smartx-k8s` | `apps/template/features.yaml` | `scalex.io/data/cnpg/operator`, `scalex.io/data/cnpg`, `scalex.io/ai/milvus` 추가 | CNPG/Milvus를 SmartX feature graph로 선택하기 위해 |
| `smartx-k8s` | `values.yaml`, `apps/template/defaults.yaml` | 새 `scalex.io/*` feature를 default feature 목록에 등록 | SmartX feature 검증 통과 |
| `smartx-k8s` | `templates/applications.yaml` | 앱 manifest의 추가 sync option을 Argo CD Application에 반영 | CNPG CR에 `SkipDryRunOnMissingResource=true`를 넣기 위해 |
| `datax-k8s` | `values.yaml` | `scalex.io/data/cnpg`, `scalex.io/ai/milvus` 활성화 | DataX에서 CNPG/Milvus 앱을 켜기 위해 |
| `datax-k8s` | `patches/scalex-cnpg-*`, `patches/scalex-milvus` | DataX/KIND resource, storage, instance override 추가 | preset은 cluster별 차이만 관리한다는 mobilex 패턴 유지 |
| `towerx-k8s` | `argocd/control-plane/00-project.yaml` | `datax-ops.sourceRepos`에 CNPG chart repo 허용 | CNPG operator는 외부 Helm chart를 source로 사용하기 때문 |

### 무엇을 추가했나

| repo | 추가한 것 | 역할 |
| --- | --- | --- |
| `smartx-k8s` | `apps/scalex-cnpg-operator/` | CloudNativePG operator Helm chart wrapper. feature는 `scalex.io/data/cnpg/operator` |
| `smartx-k8s` | `apps/scalex-cnpg-cluster/` | CNPG `Cluster` CR local chart. feature는 `scalex.io/data/cnpg` |
| `smartx-k8s` | `apps/scalex-milvus/` | Milvus standalone + embedded etcd local chart. feature는 `scalex.io/ai/milvus` |
| `datax-k8s` | `patches/scalex-cnpg-operator/values.yaml` | DataX CNPG operator resource/concurrency override |
| `datax-k8s` | `patches/scalex-cnpg-cluster/values.yaml` | DataX CNPG instance/storage/resource override |
| `datax-k8s` | `patches/scalex-milvus/values.yaml` | DataX Milvus resource override |

### 어떻게 작성했나

```text
1. smartx-k8s/apps/<app>/manifest.yaml
   -> app 이름, namespace, feature, patched 여부 선언

2. smartx-k8s/apps/<app>/values.yaml
   -> 모든 cluster에 공통으로 쓸 기본값 작성

3. smartx-k8s/apps/<app>/templates/* 또는 외부 Helm chart source
   -> CNPG operator는 외부 chart, CNPG cluster/Milvus는 local chart

4. smartx-k8s/apps/template/features.yaml
   -> feature 의존성 작성
      scalex.io/data/cnpg -> scalex.io/data/cnpg/operator
      scalex.io/ai/milvus -> scalex.io/data

5. datax-k8s/values.yaml
   -> DataX에서 직접 켤 feature 선택
      scalex.io/data/cnpg
      scalex.io/ai/milvus

6. datax-k8s/patches/<app>/values.yaml
   -> DataX에서만 다른 resource/storage 값 override

7. TowerX Argo CD datax root Application sync
   -> SmartX 엔진이 datax-scalex-* Application들을 자동 생성
```

### 실제 검증 결과

```text
Argo CD:
  datax-scalex-cnpg-operator Synced/Healthy
  datax-scalex-cnpg-cluster  Synced/Healthy
  datax-scalex-milvus        Synced/Healthy

kind-datax:
  deployment.apps/scalex-cnpg-operator-cloudnative-pg 1/1 Running
  cluster.postgresql.cnpg.io/scalex-cnpg READY=1, Cluster in healthy state
  pod/scalex-cnpg-1 1/1 Running
  deployment.apps/scalex-milvus 1/1 Running

Smoke test:
  CNPG pg_isready -> accepting connections
  Milvus /healthz local/service -> OK
```

주의:

```text
현재 KIND 단일 노드 PoC에서는 CNPG operator/Milvus가 리소스 압박과 embedded etcd/lease 지연으로 재시작할 수 있다.
따라서 이번 결과는 “SmartX feature graph + DataX preset + Argo CD sync + smoke test 1차 통과”로 기록하고,
장시간 안정성은 DataX 노드 리소스 증설 또는 운영형 분산 구성으로 다시 검증한다.
```

### 문제와 해결

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| CNPG operator Application이 AppProject에서 거부됨 | 외부 chart repo가 `datax-ops.sourceRepos`에 없었음 | `towerx-k8s` AppProject에 `https://cloudnative-pg.github.io/charts` 추가 |
| CNPG `Cluster` 앱이 `Unknown` | ServerSideApply structured diff가 CNPG CR에서 실패 | CNPG cluster app은 `ServerSideApply=false`, `SkipDryRunOnMissingResource=true`로 변경 |
| Milvus CrashLoopBackOff | KIND 단일 노드에서 embedded etcd lease가 지연됨 | Milvus resource 상향, `rootCoord.dmlChannelNum=1`, etcd timeout 완화 |
| Kueue webhook connection refused | 과거 실험 Kueue webhook이 endpoint 없이 admission을 막음 | 이번 구조에서 Kueue는 보류라 stale Kueue webhook 제거 |
| CNPG operator leader election lost | 낮은 resource와 KIND API lease 갱신 지연 | operator resource 상향, `maxConcurrentReconciles=2` |

### 일부러 하지 않은 것

| 하지 않은 것 | 이유 |
| --- | --- |
| `scalex-federation`에 CNPG/Milvus 추가 | DataX 전용 앱이라 Karmada placement가 필요 없기 때문 |
| `datax-k8s/apps/`에 직접 앱 작성 | MobileX 방식처럼 앱 정의는 엔진 `smartx-k8s`, 선택/patch는 preset `datax-k8s`에 두기 때문 |
| 운영형 Milvus distributed/MinIO/Pulsar 구성 | 이번 목표는 SmartX feature graph와 DataX 배포 검증. 운영형 vector DB는 다음 단계 |
| Kueue 유지 | 현재는 Job queue가 아니라 long-running service 검증이므로 Kueue는 보류 |

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
      -> datax / edgex / twinx SmartX root Application bootstrap
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
     - scalex.io/data/app
     - scalex.io/data/trino
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

   datax-scalex-nessie / datax-scalex-trino
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
| `datax-k8s` | `scalex.io/data/app`, `scalex.io/data/trino`, `scalex.io/data/cnpg`, `scalex.io/ai/milvus`, `scalex.io/healthcheck` | `datax`, `datax-scalex-data-api`, `datax-scalex-healthcheck`, `datax-scalex-postgresql`, `datax-scalex-nessie`, `datax-scalex-trino`, `datax-scalex-cnpg-operator`, `datax-scalex-cnpg-cluster`, `datax-scalex-milvus` |
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
├── patches/                            # TowerX SmartX 앱 override 예정 위치
├── argocd/
│   ├── bootstrap/
│   │   ├── root-app.yaml               # 최초 1회 apply할 TowerX root Application
│   │   └── smartx-root-apps.yaml       # datax/edgex/twinx SmartX root Application bootstrap
│   └── control-plane/
│       ├── 00-project.yaml             # AppProject 정의
│       ├── 05-towerx-cluster.yaml      # SmartX root app용 TowerX cluster alias
│       ├── 10-scalex-federation-app.yaml
│       └── kustomization.yaml
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
├── charts/                             # cluster 전용 local chart 예정 위치
├── ingresses/                          # cluster 전용 ingress 예정 위치
├── projects/                           # cluster 전용 project/policy 예정 위치
├── kiss/                               # KISS inventory 예정 위치
└── docs/
```

초기에는 `apps/local-demo/`로 단일 TowerX Argo CD가 각 member cluster에 직접 sync 가능한지 확인했지만, 현재 active 구조에서는 제거했습니다. 이제 cluster-local 앱은 `smartx-k8s` 앱 카탈로그 + preset `features`/`patches` 조합을 우선합니다.

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
        │   ├── propagation-policy.yaml
        │   └── override-policy.yaml
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

최종 운영 기준은 [13. 운영 기준 확정](#13-운영-기준-확정)을 따른다.

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
| `datax-local` | `datax-ops` | `datax-k8s/apps/local-demo` | `datax` | 검증 완료 후 제거 |
| `edgex-local` | `edgex-ops` | `edgex-k8s/apps/local-demo` | `edgex` | 검증 완료 후 제거 |
| `twinx-local` | `twinx-ops` | `twinx-k8s/apps/local-demo` | `twinx` | 검증 완료 후 제거 |

실제 리소스는 검증 후 `tower-root --prune`으로 제거했습니다. 현재 운영 구조에서는 `apps/local-demo` 직접 sync 방식이 아니라 SmartX feature graph 또는 Karmada federation 방식을 사용합니다.

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

## 8. 추가 검증 항목

SmartX/Karmada/kube-scheduler PoC 검증은 현재 단계에서 완료했습니다.

```text
완료:
  - smartx-k8s feature graph가 Argo CD Application 생성
  - datax/edgex/twinx preset별 Application 생성
  - DataX에서 scalex.io/data/app 하나만 켜도 scalex.io/data/postgresql 자동 생성
  - DataX에서 scalex.io/data/trino 하나만 켜도 scalex.io/data/nessie 자동 생성
  - Nessie/Trino DataX live sync 및 smoke test 검증
  - Karmada PropagationPolicy/OverridePolicy live sync 검증
  - 별도 multi-node kind lab에서 kube-scheduler nodeSelector/affinity/taint 배치 검증

남음:
  - 실제 물리 DataX/EdgeX/TwinX 클러스터에 13장 label/taint 표준 적용
  - 실제 GPU/스토리지 노드에 동일한 scheduling 정책 적용
```

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

# Scheduler lab
kubectl --context kind-scalex-scheduler-lab get nodes -L scalex.io/pool,scalex.io/workload
kubectl --context kind-scalex-scheduler-lab -n scalex-scheduler-lab get pods -o wide
```

---

## 11. 현재 kind PoC 최종 검증 결과

### 11.1 kind cluster 구성

현재 kind 환경은 실제 Kubernetes cluster 4개로 구성되어 있습니다.

```text
tower
datax
edgex
twinx
```

각 운영 PoC cluster는 현재 1-node kind cluster입니다.

```text
tower-control-plane
datax-control-plane
edgex-control-plane
twinx-control-plane
```

따라서 TowerX/DataX/EdgeX/TwinX 4개 cluster 자체는 “여러 Kubernetes cluster 간 전파/배포” 검증용입니다.
member cluster 내부의 여러 worker node scheduling은 운영 PoC cluster를 건드리지 않고 별도 lab-only cluster인 `scalex-scheduler-lab`에서 검증했습니다.

### 11.2 Argo CD 최종 상태

현재 TowerX 단일 Argo CD의 주요 Application 상태는 모두 `Synced/Healthy`입니다.

```text
tower-root                 default             Synced   Healthy
scalex-federation          scalex-federation   Synced   Healthy

datax                      towerx-ops          Synced   Healthy
datax-scalex-data-api      datax-ops           Synced   Healthy
datax-scalex-healthcheck   datax-ops           Synced   Healthy
datax-scalex-postgresql    datax-ops           Synced   Healthy
datax-scalex-nessie        datax-ops           Synced   Healthy
datax-scalex-trino         datax-ops           Synced   Healthy

edgex                      towerx-ops          Synced   Healthy
edgex-scalex-healthcheck   edgex-ops           Synced   Healthy

twinx                      towerx-ops          Synced   Healthy
twinx-scalex-healthcheck   twinx-ops           Synced   Healthy
```

`datax-local`, `edgex-local`, `twinx-local`은 초기 direct-sync 검증용 임시 앱이었고, 현재는 `tower-root --prune`으로 제거했습니다.

### 11.3 실제 member cluster 리소스

SmartX feature graph로 생성된 앱은 실제 member cluster에 리소스를 만들었습니다.

| cluster | namespace | 확인된 리소스 |
| --- | --- | --- |
| DataX | `scalex-system` | `scalex-healthcheck` Deployment/Service/ConfigMap, Pod Running |
| DataX | `scalex-data` | `scalex-data-api` Deployment/Service/ConfigMap, Pod Running |
| DataX | `scalex-data` | `scalex-postgresql` StatefulSet/Service/Secret, Pod Running |
| DataX | `scalex-data` | `scalex-nessie` Deployment/Service, Pod Running, `/api/v2/config` OK |
| DataX | `scalex-data` | `scalex-trino` Deployment/Service/ConfigMap, Pod Running, `/v1/info` ACTIVE |
| EdgeX | `scalex-system` | `scalex-healthcheck` Deployment/Service/ConfigMap, Pod Running |
| TwinX | `scalex-system` | `scalex-healthcheck` Deployment/Service/ConfigMap, Pod Running |

### 11.4 Karmada federation 최종 상태

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

추가로 `scalex-render-demo`에는 `OverridePolicy`를 붙여 TwinX/EdgeX별 label/env가 다르게 적용되도록 검증했습니다.
```

### 11.5 발견한 문제와 해결

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

### 11.6 member cluster 내부 kube-scheduler 검증

목적은 Karmada가 member cluster까지 리소스를 전파한 뒤, cluster 내부 node 배치는 별도 전파 시스템이 아니라 Kubernetes 기본 scheduler가 담당한다는 것을 확인하는 것입니다.

기존 TowerX/DataX/EdgeX/TwinX kind cluster는 1-node이므로 건드리지 않았고, 별도 lab-only multi-node kind cluster를 만들었습니다.

```text
scalex-scheduler-lab
  - scalex-scheduler-lab-control-plane
  - scalex-scheduler-lab-worker
  - scalex-scheduler-lab-worker2
```

노드 라벨/taint:

```text
scalex-scheduler-lab-worker
  scalex.io/pool=left
  scalex.io/workload=general

scalex-scheduler-lab-worker2
  scalex.io/pool=right
  scalex.io/workload=gpu-sim
  taint: scalex.io/dedicated=gpu:NoSchedule
```

검증 workload:

| workload | scheduling 조건 | 결과 |
| --- | --- | --- |
| `node-selector-left` | `nodeSelector: scalex.io/pool=left` | replica 2개 모두 `scalex-scheduler-lab-worker`에 배치 |
| `affinity-right-tolerated` | required nodeAffinity `pool=right` + `scalex.io/dedicated=gpu` toleration | replica 2개 모두 `scalex-scheduler-lab-worker2`에 배치 |
| `taint-blocked-no-toleration` | `nodeSelector: pool=right`, toleration 없음 | `Pending`; scheduler가 untolerated taint로 거절 |

실제 결과:

```text
node-selector-left-*
  -> scalex-scheduler-lab-worker

affinity-right-tolerated-*
  -> scalex-scheduler-lab-worker2

taint-blocked-no-toleration
  -> Pending
  -> FailedScheduling: untolerated taint {scalex.io/dedicated: gpu}
```

의도적으로 Pending시킨 `taint-blocked-no-toleration` Pod는 증거 확인 후 삭제했습니다. 현재 lab cluster에는 정상 Running workload만 남겨두었습니다.

결론:

```text
Argo CD -> Karmada -> member cluster
  여기까지는 멀티클러스터 전파 영역

member cluster -> kube-scheduler -> node -> kubelet
  여기부터는 일반 Kubernetes scheduling 영역
```

따라서 각 cluster 내부에 별도의 “노드 전파 시스템”은 필요하지 않습니다. 실제 운영에서는 노드에 표준 label/taint를 붙이고, 각 workload에 nodeSelector/affinity/toleration을 선언하면 됩니다.

---

## 12. 다음부터 사용하는 방법

### 12.1 먼저 결정할 것

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

### 12.2 cluster-local 앱을 추가하는 방법

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

### 12.3 여러 클러스터로 전파하는 앱을 추가하는 방법

여러 member cluster에 배포하거나 Karmada placement가 필요하면 `scalex-federation`에 둡니다.

```text
scalex-federation/federation/apps/<workload>/
├── resources.yaml
├── propagation-policy.yaml
└── override-policy.yaml   # cluster별 차이가 필요할 때만
```

그리고 `scalex-federation/federation/kustomization.yaml`에 path를 추가합니다.

검증:

```bash
argocd app sync scalex-federation
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get resourcebindings -A
```

### 12.4 TowerX 제어 평면을 바꾸는 방법

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

### 12.5 확인 명령

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

### 12.6 문제 생기면 먼저 볼 것

| 증상 | 먼저 확인할 것 |
| --- | --- |
| Argo CD Application `Unknown` | AppProject `sourceRepos`, repo credential, destination name |
| `patched: true` 앱 sync 실패 | `<cluster>-k8s/patches/<app>/values.yaml` 존재 여부 |
| 원하지 않는 앱이 생성됨 | `smartx-k8s/apps/<app>/manifest.yaml`의 `features`가 비어 있는지 확인 |
| Karmada 전파 안 됨 | `PropagationPolicy` selector와 `ResourceBinding` 상태 확인 |
| Pod가 노드에 안 뜸 | member cluster의 scheduler event, node label/taint/affinity 확인 |
| `argocd --core`가 `argocd-cm`을 못 찾음 | 현재 kube-context namespace가 `argocd`인지 확인. `kubectl config set-context --current --namespace=argocd` 적용 |
| Trino가 catalog 설정 오류로 뜨지 않음 | `/etc/trino/catalog/*.properties`에는 반드시 `connector.name` 필요. 단순 Nessie URI 메모 파일은 catalog 밖에 둔다 |

### 12.7 이번에 추가로 검증한 것

#### SmartX feature dependency

```text
datax-k8s/values.yaml
  features:
    - scalex.io/data/app
    - scalex.io/data/trino
    - scalex.io/healthcheck

smartx-k8s/apps/template/features.yaml
  scalex.io/data/app   requires scalex.io/data/postgresql
  scalex.io/data/trino requires scalex.io/data/nessie
```

검증 결과:

```text
helm template 결과:
  datax
  datax-scalex-data-api
  datax-scalex-healthcheck
  datax-scalex-postgresql
  datax-scalex-nessie
  datax-scalex-trino
```

즉 DataX preset은 PostgreSQL/Nessie를 직접 켜지 않고, SmartX 엔진이 feature graph로 의존 앱을 자동 생성합니다.

실제 적용 결과:

```text
argocd app sync datax --prune
  datax-scalex-data-api Synced/Healthy
  datax-scalex-nessie   Synced/Healthy
  datax-scalex-trino    Synced/Healthy

kind-datax/scalex-data:
  deployment.apps/scalex-data-api 1/1 Running
  statefulset.apps/scalex-postgresql 1/1 Running
  deployment.apps/scalex-nessie 1/1 Running
  deployment.apps/scalex-trino  1/1 Running

Smoke test:
  Nessie /api/v2/config -> OK
  Trino  /v1/info       -> ACTIVE, version 482
  Trino CLI             -> select count(*) from tpch.tiny.nation = 25
```

#### Karmada OverridePolicy

```text
scalex-federation/federation/apps/render-demo/
  resources.yaml
  propagation-policy.yaml
  override-policy.yaml
```

검증 결과:

```text
argocd app sync scalex-federation
  overridepolicy.policy.karmada.io/scalex-render-demo serverside-applied
  scalex-federation Synced/Healthy

ResourceBinding:
  scalex-render/scalex-render-demo-deployment Scheduled=True FullyApplied=True
  scalex-render/scalex-render-demo-service    Scheduled=True FullyApplied=True
```

`OverridePolicy`는 같은 render Deployment에 대해 다음 차이를 만듭니다.

```text
twinx: replicas=3, render-role=primary,   SCALEX_RENDER_CLUSTER=twinx
edgex: replicas=1, render-role=secondary, SCALEX_RENDER_CLUSTER=edgex
```
---

## 13. 운영 기준 확정

이 섹션은 현재 PoC 결과를 바탕으로 실제 ScaleX repo를 만들 때 따를 기준입니다. 결론은 다음 세 가지입니다.

```text
1. 물리 노드는 공통 label/taint 표준으로 분류한다.
2. cluster-local 앱은 smartx-k8s app catalog + feature graph로 관리한다.
3. 멀티클러스터 placement/failover/weight가 필요한 리소스만 scalex-federation으로 보낸다.
```

### 13.1 repo ownership 최종 기준

| repo | 소유하는 것 | 소유하지 않는 것 |
| --- | --- | --- |
| `towerx-k8s` | TowerX 단일 Argo CD, AppProject, repo credential, cluster secret/alias, root Application, Karmada Control Plane bootstrap | 일반 workload, DataX/EdgeX/TwinX 내부 앱 |
| `smartx-k8s` | app catalog, Helm chart, feature graph, Application 생성 템플릿 | 클러스터별 values, 비밀값, Karmada PropagationPolicy |
| `datax-k8s` | DataX 전용 preset, DataX feature 선택, DataX patch | EdgeX/TwinX workload, Karmada placement policy |
| `edgex-k8s` | EdgeX 전용 preset, Edge/GPU feature 선택, EdgeX patch | DataX/TwinX workload, Karmada placement policy |
| `twinx-k8s` | TwinX 전용 preset, digital twin/render/serving feature 선택, TwinX patch | DataX/EdgeX workload, Karmada placement policy |
| `scalex-federation` | Karmada resource + PropagationPolicy + OverridePolicy + ClusterPropagationPolicy | SmartX preset, CNI/CSI/GPU Operator, cluster-local 기본 인프라 |

절대 원칙:

```text
같은 live resource는 한 repo만 소유한다.
두 repo가 같은 namespace/name/kind를 동시에 관리하지 않는다.
이관할 때는 새 owner를 sync하기 전에 기존 owner에서 prune/cascade 위험을 확인한다.
```

### 13.2 Karmada vs cluster-local 경계

`scalex-federation`에 넣는 경우:

| 조건 | 예시 | 이유 |
| --- | --- | --- |
| 하나의 workload를 둘 이상 cluster에 나눠 배치 | TwinX 3 replicas + EdgeX 1 replica render workload | Karmada `replicaScheduling` 필요 |
| cluster별 override가 필요 | TwinX는 `primary`, EdgeX는 `secondary` env/label | Karmada `OverridePolicy` 필요 |
| 장애/점검 시 placement를 바꿔야 함 | EdgeX 장애 시 TwinX로 이동 | Karmada failover/rebalancing 대상 |
| 여러 cluster에 같은 namespace/tenant shell을 만들어야 함 | 공통 tenant namespace | `ClusterPropagationPolicy` 대상 |
| 중앙 TowerX에서 batch 실행 위치를 정책으로 고정해야 함 | DataX-only Job | placement를 GitOps/Karmada로 보이게 하기 위함 |

각 `*-k8s`에 넣는 경우:

| 조건 | 예시 | 이유 |
| --- | --- | --- |
| 특정 cluster 하나에서만 쓰는 앱 | DataX PostgreSQL/CNPG, DataX Trino | 단일 cluster 전용 |
| 각 cluster 생존에 필요한 기본 인프라 | CNI, CSI, GPU Operator, Ingress Controller | cluster-local failure domain |
| 여러 cluster에 같은 앱을 설치하지만 서로 독립 운영 | healthcheck, monitoring agent, node exporter | Karmada placement 필요 없음 |
| cluster별 patch/secret/storageClass 차이가 큼 | Harbor/Keycloak/MinIO per cluster | preset patch가 맞음 |

판단 문장:

```text
“어디 cluster에 몇 개 둘지”가 핵심이면 scalex-federation.
“이 cluster에 어떤 앱을 설치할지”가 핵심이면 각 cluster-k8s preset.
“그 앱을 어떤 chart/의존성으로 정의할지”가 핵심이면 smartx-k8s.
```

### 13.3 물리 노드 label 표준

모든 DataX/EdgeX/TwinX node에는 아래 공통 label을 붙입니다.

| label key | 값 예시 | 의미 | 필수 여부 |
| --- | --- | --- | --- |
| `scalex.io/cluster` | `datax`, `edgex`, `twinx` | 노드가 속한 ScaleX cluster | 필수 |
| `scalex.io/pool` | `general`, `data`, `gpu`, `render`, `storage`, `infra` | scheduling pool | 필수 |
| `scalex.io/workload` | `general`, `data`, `ai`, `render`, `edge`, `storage` | 주 workload 성격 | 필수 |
| `scalex.io/accelerator` | `none`, `nvidia`, `dgx-spark`, `a10` | 가속기 계열 | GPU node 필수 |
| `scalex.io/storage` | `none`, `local`, `ceph`, `nfs` | 주 storage 역할 | storage node 필수 |
| `topology.kubernetes.io/zone` | `datax`, `edgex`, `twinx` | topology/anti-affinity 기준 | 권장 |

cluster별 1차 기준:

| cluster | 기본 node label | 비고 |
| --- | --- | --- |
| DataX | `scalex.io/cluster=datax`, `scalex.io/pool=data`, `scalex.io/workload=data`, `scalex.io/accelerator=none` | data/batch/analytics 기본 위치 |
| EdgeX | `scalex.io/cluster=edgex`, `scalex.io/pool=gpu`, `scalex.io/workload=edge`, `scalex.io/accelerator=nvidia` | GPU/edge workload 우선 위치 |
| TwinX | `scalex.io/cluster=twinx`, `scalex.io/pool=render`, `scalex.io/workload=render`, `scalex.io/accelerator=none 또는 nvidia` | digital twin/render/serving 기본 위치 |

예시 명령:

```bash
# DataX 일반 data node
kubectl label node <node> \
  scalex.io/cluster=datax \
  scalex.io/pool=data \
  scalex.io/workload=data \
  scalex.io/accelerator=none \
  topology.kubernetes.io/zone=datax

# EdgeX GPU node
kubectl label node <node> \
  scalex.io/cluster=edgex \
  scalex.io/pool=gpu \
  scalex.io/workload=edge \
  scalex.io/accelerator=nvidia \
  topology.kubernetes.io/zone=edgex

# TwinX render node
kubectl label node <node> \
  scalex.io/cluster=twinx \
  scalex.io/pool=render \
  scalex.io/workload=render \
  topology.kubernetes.io/zone=twinx
```

### 13.4 물리 노드 taint 표준

기본 원칙은 “일반 node에는 taint를 걸지 않고, 특별한 node만 보호한다”입니다.

| taint | 적용 대상 | workload가 필요한 toleration | 비고 |
| --- | --- | --- | --- |
| `scalex.io/dedicated=gpu:NoSchedule` | GPU 전용 node | GPU/AI/render workload | 일반 Pod가 GPU node를 점유하지 못하게 함 |
| `scalex.io/dedicated=storage:NoSchedule` | storage daemon 전용 node | Rook/Ceph/storage workload | 일반 workload와 storage daemon 분리 |
| `scalex.io/dedicated=infra:NoSchedule` | ingress/registry/control add-on 전용 node | infra workload | 운영 안정화 후 적용 |
| `scalex.io/maintenance=true:NoSchedule` | 점검 중 node | 없음 | 임시 점검용. 작업 후 제거 |

예시 명령:

```bash
# GPU node 보호
kubectl taint node <gpu-node> scalex.io/dedicated=gpu:NoSchedule

# workload toleration 예시
tolerations:
  - key: scalex.io/dedicated
    operator: Equal
    value: gpu
    effect: NoSchedule
```

`NoExecute` taint는 기존 Pod eviction을 유발하므로 기본 표준에는 넣지 않습니다. 장애/강제 축출 실험이나 명시적 drain 절차에서만 사용합니다.

### 13.5 실제 앱 feature graph 편입 기준

feature 이름 규칙:

```text
기존 smartx-k8s 앱/기능을 그대로 쓸 수 있으면 org.ulagbulag.io/* feature를 우선 사용한다.
ScaleX 전용 앱이나 조합은 scalex.io/<domain>/<capability> 형식으로 추가한다.
cluster별 값은 feature graph가 아니라 각 <cluster>-k8s/patches/<app>/values.yaml에 둔다.
```

1차 편입 계획:

| 앱/스택 | feature 예시 | app catalog 위치 | 기본 활성 cluster | 비고 |
| --- | --- | --- | --- | --- |
| healthcheck/common demo | `scalex.io/healthcheck` | 이미 추가됨 | DataX/EdgeX/TwinX | PoC 검증용 |
| DataX API demo | `scalex.io/data/app` | 이미 추가됨 | DataX | `scalex.io/data/postgresql` 의존성 검증용 |
| PostgreSQL demo | `scalex.io/data/postgresql` | 이미 추가됨 | DataX | 운영 시 CNPG로 대체 후보 |
| CNI | 기존 SmartX CNI feature 또는 `scalex.io/network/cni` | `smartx-k8s/apps/<cni>` | 각 cluster | Karmada로 전파하지 않음 |
| CSI / storage | 기존 Ceph/NFS feature 또는 `scalex.io/storage/*` | `smartx-k8s/apps/<storage>` | DataX 우선, 필요 시 각 cluster | cluster-local |
| GPU Operator | 기존 `nvidia.com/gpu` 계열 feature | `smartx-k8s/apps/nvidia-gpu-operator` | EdgeX/TwinX GPU node | node label/taint와 같이 사용 |
| OpenBao | `scalex.io/security/openbao` | `smartx-k8s/apps/openbao` 또는 TowerX 전용 app | TowerX 우선 | secret source of truth |
| External Secrets | `scalex.io/security/external-secrets` | `smartx-k8s/apps/external-secrets` | 각 cluster | OpenBao 연동 |
| Kyverno | `scalex.io/policy/kyverno` | `smartx-k8s/apps/kyverno` | 각 cluster | admission/policy |
| CNPG | `scalex.io/data/cnpg` | `smartx-k8s/apps/cnpg` | DataX | PostgreSQL 운영 대체 |
| Kafka | 기존 Kafka feature 또는 `scalex.io/data/kafka` | `smartx-k8s/apps/strimzi-kafka` | DataX | messaging/data pipeline |
| Nessie | `scalex.io/data/nessie` | `smartx-k8s/apps/scalex-nessie` | DataX | 이미 추가/검증됨. PoC REST catalog |
| Trino | `scalex.io/data/trino` | `smartx-k8s/apps/scalex-trino` | DataX | 이미 추가/검증됨. PoC single-node query engine |
| Superset | `scalex.io/data/superset` | `smartx-k8s/apps/superset` | DataX | BI/UI |
| Milvus | `scalex.io/ai/milvus` | `smartx-k8s/apps/milvus` | DataX 또는 TwinX | vector DB, storage dependency 필요 |
| Omniverse | `scalex.io/twin/omniverse` | `smartx-k8s/apps/omniverse` | TwinX | digital twin/render |
| Partridge multi-tenancy | `scalex.io/tenant/partridge` | `smartx-k8s/apps/partridge` | TwinX 우선 | tenant 관리 |
| Trident portal | `scalex.io/portal/trident` | `smartx-k8s/apps/trident-portal` | TwinX | front/service portal |
| Kueue | `scalex.io/scheduling/kueue` | `smartx-k8s/apps/kueue` | DataX/EdgeX/TwinX 중 Job 많은 cluster | 초기에는 보류, Job 증가 시 도입 |

의존성 예시:

```yaml
scalex.io/data/trino:
  requires:
    - scalex.io/data/nessie
# 운영형 Iceberg/Nessie/Trino로 확장할 때는 object storage/warehouse feature를 추가한다.

scalex.io/ai/milvus:
  requires:
    - scalex.io/storage/filesystem

scalex.io/twin/omniverse:
  requires:
    - scalex.io/render
  optional:
    - nvidia.com/gpu

scalex.io/scheduling/kueue:
  requires:
    - scalex.io/scheduling
```

편입 순서:

```text
1. cluster 생존 인프라: CNI, CSI, cert-manager, ingress, GPU Operator
2. 보안/정책: OpenBao, External Secrets, Kyverno
3. DataX data plane: CNPG, Kafka, Nessie, Trino, Superset, Milvus
4. TwinX service plane: Omniverse, Partridge, Trident portal
5. 필요 시 scheduling: Kueue
6. 여러 cluster placement가 필요한 workload만 scalex-federation으로 분리
```

### 13.6 각 repo에 실제로 넣을 때의 체크리스트

SmartX app catalog에 앱을 추가할 때:

```text
- smartx-k8s/apps/<app>/Chart.yaml
- smartx-k8s/apps/<app>/manifest.yaml
- smartx-k8s/apps/<app>/values.yaml
- smartx-k8s/apps/<app>/patches.yaml
- smartx-k8s/apps/<app>/templates/*
- smartx-k8s/apps/template/features.yaml
- smartx-k8s/values.yaml default feature 목록
- 대상 <cluster>-k8s/values.yaml feature 활성화
- patched: true이면 <cluster>-k8s/patches/<app>/values.yaml 추가
```

이번 Nessie/Trino 예시:

```text
- smartx-k8s/apps/scalex-nessie/*
- smartx-k8s/apps/scalex-trino/*
- smartx-k8s/apps/template/features.yaml
  scalex.io/data/trino -> scalex.io/data/nessie
- datax-k8s/values.yaml
  scalex.io/data/trino 활성화
- datax-k8s/patches/scalex-nessie/values.yaml
- datax-k8s/patches/scalex-trino/values.yaml
```

Karmada federation workload를 추가할 때:

```text
- scalex-federation/federation/apps/<workload>/resources.yaml
- scalex-federation/federation/apps/<workload>/propagation-policy.yaml
- 필요 시 override-policy.yaml
- federation/kustomization.yaml에 resource path 추가
- argocd app sync scalex-federation
- ResourceBinding Scheduled/FullyApplied 확인
```
