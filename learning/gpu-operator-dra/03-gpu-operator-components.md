# 03. GPU Operator의 구성요소와 소유권

GPU Operator는 GPU 한 개를 단순히 “설치”하는 프로그램이 아니다.
## Operator는 무엇을 관찰하고 무엇을 만든다

이 장의 상태와 출력은 교육용이며 실제 설치 기록이 아니다. GPU Operator는 GPU를 계산하는 application이 아니라 Kubernetes controller와 node DaemonSet들을 배포·조정하는 운영 계층이다.

CustomResourceDefinition은 ClusterPolicy 같은 새 API kind의 schema를 API server에 등록한다. Custom resource는 사용자가 원하는 driver·toolkit·plugin 설정을 담는다. Operator controller는 그 object를 watch하고 DaemonSet, ConfigMap, ServiceAccount를 만든다. CRD만 설치하고 controller가 없으면 객체는 저장돼도 host driver는 준비되지 않는다.

```mermaid
flowchart LR
    C["ClusterPolicy spec<br/>desired state"] -->|"watch"| O["GPU Operator controller"]
    O -->|"create/update"| D["Driver DaemonSet"]
    O -->|"create/update"| T["Container toolkit DaemonSet"]
    O -->|"create/update"| P["Device plugin DaemonSet"]
    O -->|"create/update"| F["GPU Feature Discovery"]
    O -->|"create/update"| V["Validator"]
    D -->|"module·device node"| N["GPU node host"]
    T -->|"runtime/CDI config"| N
    P -->|"register resources"| K["kubelet"]
    F -->|"Node labels"| A["API Node"]
    V -->|"검사 결과"| S["status·log"]
```

Custom resource→operator는 제어 입력이다. Operator→DaemonSet은 API 객체 생성이지 node shell을 직접 호출하는 동기 함수가 아니다. DaemonSet Pod→host는 privileged mount와 node 작업이다.

## 구성 요소별 소유권

**Driver component**는 지원 조건에서 host kernel module과 user library를 준비한다. Host에 preinstalled driver가 있다면 Operator가 driver를 관리하지 않도록 설정할 수 있다. 두 설치 주체가 같은 module을 소유하면 upgrade·rollback 충돌이 난다.

**Container toolkit component**는 container runtime이 선택 GPU device와 driver library를 container에 넣도록 host 설정을 준비한다. Runtime config 변경이 필요한 경우 재시작 영향과 node drain을 확인한다.

**Device plugin**은 kubelet registration socket을 통해 GPU extended resource와 health를 광고한다. Scheduler가 개수로 node를 고르고 kubelet이 Allocate를 호출한다. Plugin이 driver module을 대체하지 않는다.

**GPU Feature Discovery**는 GPU model, memory, MIG capability 같은 정보를 Node label로 게시할 수 있다. Label은 scheduling input이며 hardware를 바꾸지 않는다. Stale label과 실제 device health 차이를 확인한다.

**Node Feature Discovery**는 CPU·PCI·kernel feature 같은 node 정보를 label·resource로 발견하는 별도 프로젝트다. GPU 전용 GFD와 역할이 겹치거나 연결될 수 있지만 같은 process라고 단정하지 않는다.

**Validator**는 driver, toolkit, plugin, CUDA workload 경로를 검사한다. 모든 application model과 성능을 검증하는 것은 아니다. Validator 성공은 지원 경로가 동작할 가능성의 증거이지 training correctness와 isolation 보장이 아니다.

## Reconcile 수치 trace

| 시각 | Desired object | Operator/DaemonSet | Node observed state |
|---:|---|---|---|
| t0 | ClusterPolicy generation 1 | controller 관찰 전 | driver 없음 |
| t1 | gen1 | Driver DS desired 2 | Pod 0/2 Ready |
| t2 | gen1 | Driver Pod node-a Running | module load 중 |
| t3 | gen1 | Toolkit DS 생성 | `/dev/nvidia0`, runtime config |
| t4 | gen1 | Device plugin 2/2 | Node capacity GPU=4+4 |
| t5 | gen1 | GFD 2/2 | model/MIG labels |
| t6 | gen1 | Validator node-b 실패 | node-a usable, node-b library 오류 |
| t7 | gen1 | status degraded | scheduler에는 stale capacity 가능성 조사 |
| t8 | spec 수정 generation 2 | observedGeneration 아직 1 | reconcile 진행 중 |
| t9 | gen2 관찰 | component rollout | status 조건 갱신 |

Operator Pod Running 하나만 보고 완료라 하지 않는다. 각 DaemonSet desired/ready, Node capacity/labels, validator, 실제 CUDA Pod를 본다. Generation과 observedGeneration이 다르면 status가 최신 spec을 반영하지 않았을 수 있다.

## DaemonSet과 host mutation

Driver Pod는 privileged permission, host `/run`, module, kernel header 경로를 사용할 수 있다. Container가 지워져도 load된 module과 host file이 남을 수 있다. Rollback과 uninstall이 무엇을 제거하는지 공식 절차를 따른다.

Toolkit Pod가 runtime config를 바꾸면 이미 실행 중인 container와 새 container의 동작이 다를 수 있다. Node별 rollout, runtime restart, drain 필요성을 확인한다. 모든 node를 동시에 바꾸면 GPU workload 가용성을 잃을 수 있다.

## MIG Manager와 configuration

MIG Manager는 label/config에 따라 GPU를 MIG mode와 profile로 구성하는 component일 수 있다. Reconfiguration은 기존 GPU process를 중단하거나 reset을 요구할 수 있다. Desired label 변경을 단순 metadata 변경으로 보지 않는다.

MIG instance가 광고돼도 database 같은 application state는 없다. Scheduler resource 이름과 profile, node label, actual `nvidia-smi` 관찰을 맞춘다. MIG memory partition은 time-slicing과 다른 isolation 메커니즘이다.

## Version과 support matrix

GPU Operator 26.7 support matrix에서 Kubernetes, OS, container runtime, GPU/driver 조건을 함께 확인한다. Kubernetes minor가 지원돼도 custom kernel이나 secure boot, preinstalled component 조합이 별도 제약일 수 있다.

DRA core의 Kubernetes 1.34 GA와 1.35 stable/locked gate 표시는 역사와 현재 상태를 구분한다. GPU Operator classic device plugin 구성과 vendor DRA driver의 지원 범위도 같지 않다.

## Terminal failure와 복구 주체

Driver build가 kernel header 불일치로 실패하면 같은 Pod restart만으로 해결되지 않는다. Toolkit config 오류는 runtime integration owner가 수정한다. Device plugin registration 실패는 kubelet socket·permission·API capacity를 본다. Validator CUDA failure는 library ABI, device node, driver health를 단계별로 본다.

Hardware Xid와 uncorrected ECC가 반복되면 workload reschedule만으로 device가 건강해지는 것은 아니다. Node cordon·drain·hardware remediation 같은 운영 판단이 필요하다. Operator reconcile은 물리 고장을 수리하지 않는다.

## 연구 성능 경계

Operator가 GPU를 Ready로 만들었다는 것은 sharing 성능 격리를 뜻하지 않는다. IWQoS scheduling 연구의 policy는 별도 scheduler와 workload 가정을 가진다. Time-slicing replica 등록은 capacity 이름을 늘릴 수 있지만 HBM quota와 latency SLO를 자동 분리하지 않는다.

Power·fragmentation 연구도 Operator 설치 성공과 다른 질문이다. GPU profile, clock/power cap, co-location, allocator trace를 기록한다.

## 문제와 완전 해설

1. CRD만 설치하면 driver가 설치되는가? **아니다.** Controller가 custom resource를 reconcile해야 한다.
2. Operator Ready면 모든 GPU node가 Ready인가? **아니다.** Component DaemonSet과 node별 validator·capacity를 본다.
3. GFD label이 있으면 GPU health가 보장되는가? **아니다.** Discovery metadata와 현재 driver/device health는 다르다.
4. MIG label 변경이 무중단 metadata 변경인가? **아니다.** GPU reset·process 중단 가능성을 검토한다.
5. Validator 성공이면 training 성능 isolation도 검증됐는가? **아니다.** 기본 stack path와 application 성능 계약은 다르다.
노드 드라이버, 컨테이너 런타임 연결, Kubernetes 장치 광고, 상태 라벨,
관측과 검증을 여러 DaemonSet과 컨트롤러로 관리하는 운영 계층이다.

이 장의 목표는 다음 세 가지다.

1. 각 구성요소가 어느 문제를 해결하는지 설명한다.
2. Operator가 관리하는 것과 이미 설치된 것을 사용하는 경우를 구분한다.
3. 기존 `ClusterPolicy`와 최신 `GPUCluster` 워크플로의 차이를 이해한다.

![GPU Operator 구성요소](assets/operator-components.svg)

## 3.1 먼저 보는 전체 흐름

```mermaid
flowchart LR
    A[GPU가 있는 노드] --> B[Driver]
    B --> C[Container Toolkit]
    C --> D[Device Plugin 또는 DRA Driver]
    D --> E[kubelet]
    E --> F[GPU Pod]
    A --> G[NFD와 GFD]
    G --> H[노드 라벨]
    A --> I[DCGM Exporter]
    I --> J[GPU 메트릭]
    K[Validator] --> B
    K --> C
    K --> D
```

Pod가 GPU를 쓰려면 어느 한 상자만 정상이어서는 부족하다.
드라이버가 하드웨어를 제어하고, Toolkit이 컨테이너에 필요한 장치를 넣으며,
장치 플러그인이나 DRA 드라이버가 kubelet과 GPU 할당을 연결해야 한다.

NVIDIA의 GPU Operator 구성요소 설명은
[공식 플랫폼 개요](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/overview.html)에서 확인할 수 있다.

## 3.2 구성요소별 역할

| 구성요소 | 해결하는 문제 | 대표 결과 |
|---|---|---|
| NVIDIA Driver | OS 커널과 GPU 통신 | 커널 모듈, 장치 노드 |
| Container Toolkit | 컨테이너 런타임에 GPU 주입 | CDI 또는 런타임 설정 |
| Device Plugin | 정수형 GPU 자원 광고와 할당 | `nvidia.com/gpu` |
| DRA Driver | claim 기반 동적 장치 할당 | `ResourceClaim` 준비 |
| NFD | 노드 하드웨어 특징 탐지 | 표준 노드 라벨 |
| GFD | NVIDIA GPU 특징 탐지 | GPU 모델·메모리·MIG 라벨 |
| DCGM Exporter | GPU 상태 측정 | Prometheus 메트릭 |
| MIG Manager | MIG 구성을 선언에 맞게 조정 | MIG 인스턴스 구성 |
| Validator | 설치 경로의 주요 기능 확인 | 검증 Pod와 상태 |

### Driver

드라이버는 GPU의 커널 측 경계다.
호스트에 이미 검증된 드라이버가 있으면 Operator가 새로 설치하지 않도록 구성할 수 있다.
Operator 관리 드라이버와 호스트 관리 드라이버를 동시에 덮어쓰려 하면 소유권이 충돌한다.

### Container Toolkit

Toolkit은 컨테이너가 GPU 장치와 라이브러리를 보도록 런타임을 구성한다.
Toolkit은 CUDA 계산 라이브러리 자체와 같은 개념이 아니다.
또한 최신 `GPUCluster` 객체를 만들었다는 사실만으로 Toolkit이 반드시 설치된다고 단정하면 안 된다.
선택한 관리 방식과 실제 생성된 하위 리소스를 확인해야 한다.

### Device Plugin과 DRA Driver

기존 device plugin은 보통 다음처럼 정수형 확장 자원을 제공한다.

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

DRA는 `ResourceClaim`과 장치 클래스를 통해 요청을 표현한다.
두 방식은 API와 수명주기가 다르며, 같은 워크로드에 무심코 혼용하면 안 된다.

### NFD와 GFD

NFD는 CPU, PCI, OS 같은 일반 노드 특징을 찾는다.
GFD는 그 위에 GPU 모델, 메모리, MIG 가능 여부 같은 NVIDIA 특징을 라벨로 표현한다.
라벨은 “할당 결과”가 아니라 스케줄링과 관찰을 위한 사실 또는 정책 입력이다.

### DCGM Exporter

DCGM Exporter는 사용률, 온도, 전력, 오류 같은 메트릭을 노출한다.
메트릭이 있다는 사실만으로 장애가 자동 복구되지는 않는다.
경보 규칙, 대시보드, 대응 절차가 별도로 필요하다.

### MIG Manager

MIG Manager는 지원 GPU에서 MIG 구성을 조정한다.
MIG 변경은 실행 중인 작업에 영향을 줄 수 있으므로 선언 변경 전에 워크로드 배출과 변경 창을 설계한다.

### Validator

Validator는 드라이버, Toolkit, CUDA, 플러그인 경로가 기대대로 연결됐는지 확인한다.
모든 애플리케이션 성능과 수치 정확성을 증명하는 종합 시험은 아니다.

## 3.3 관리형과 비관리형

```mermaid
flowchart TD
    A[구성요소 선택] --> B{Operator가 설치하는가?}
    B -->|예| C[관리형]
    B -->|아니오| D[비관리형 또는 사전 설치]
    C --> E[Operator CR의 선언과 하위 리소스 확인]
    D --> F[호스트 이미지·외부 배포 도구의 책임 확인]
    E --> G[상태와 실제 노드 확인]
    F --> G
```

관리형에서는 Operator가 원하는 상태를 만들고 유지한다.
비관리형에서는 구성요소가 사라지는 것이 아니라 다른 주체가 책임진다.

예를 들어 드라이버를 OS 이미지 파이프라인이 설치한다면 다음을 문서화한다.

- 지원 커널과 드라이버 버전 조합
- 노드 이미지 갱신 절차
- 드라이버 검증 책임자
- Operator가 드라이버 DaemonSet을 만들지 않는다는 설정
- 장애 시 어느 팀이 먼저 조사하는지

## 3.4 ClusterPolicy와 GPUCluster

`GPUCluster` 자체는 NVIDIA GPU driver를 관리하지 않는다. Containerized driver는 별도 `NVIDIADriver` CR로 관리하거나 사전 설치한 host driver를 사용한다. CDI-compatible runtime도 사전 준비 조건이다. 따라서 최신 관리 객체가 기존 정책의 모든 driver·Toolkit 관리 책임을 그대로 가진다고 해석하지 않는다.

`ClusterPolicy`는 GPU Operator의 전통적인 클러스터 범위 구성 API다.
하나의 정책 객체가 드라이버, Toolkit, 플러그인, 모니터링 등 여러 구성요소의 설정을 모은다.

최신 릴리스에서는 `GPUCluster`를 중심으로 한 관리형 워크플로가 추가되었다.
두 API를 단순히 이름만 바뀐 같은 객체로 보면 안 된다.
생성되는 리소스, 지원 토글, 상태 필드, 업그레이드 절차가 다를 수 있다.
정확한 버전별 기능은 [14장](14-versions-and-feature-status.md)에서 확인한다.

| 질문 | ClusterPolicy | GPUCluster 워크플로 |
|---|---|---|
| 성격 | 기존 단일 정책 중심 | 최신 관리형 클러스터 구성 |
| 동시에 사용 | GPUCluster와 동시 소유 금지 | ClusterPolicy와 동시 소유 금지 |
| Toolkit | 정책 설정으로 판단 | 객체 존재만으로 설치 단정 금지 |
| 마이그레이션 | 기존 운영 기준점 | in-place 자동 전환으로 가정 금지 |

공식 설치 및 플랫폼 선택은
[GPU Operator 설치 문서](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html)를 기준으로 한다.

## 3.5 숫자로 보는 교육 예

GPU 노드가 4대이고 각 노드에 GPU가 8개라고 하자.
정수형 device plugin 방식이라면 최대 광고량은 단순 계산으로 32 GPU다.

그러나 다음 상태에서는 실제 사용 가능량이 달라진다.

| 상태 | 계산상 GPU | 스케줄 가능 GPU |
|---|---:|---:|
| 4대 모두 정상 | 32 | 32 |
| 1대 NotReady | 32 | 24 |
| 1대 드라이버 검증 실패 | 32 | 운영 정책에 따라 24 이하 |
| MIG로 재구성 | 물리 GPU 32 | 광고되는 MIG 자원 종류별 계산 |

따라서 “GPU가 32개 있다”는 자산 정보와 “현재 32개를 할당할 수 있다”는 운영 상태는 다르다.

### 3.5.1 선언 한 줄이 노드 상태가 되기까지

Operator의 핵심은 설치 명령 한 번이 아니라 반복되는 **reconciliation(조정)**이다. 사용자가 정책 객체의 `spec`을 바꾸면 API 서버의 desired state가 먼저 바뀌고, controller가 이를 읽어 하위 리소스를 생성·수정한다. DaemonSet controller와 kubelet이 Pod를 노드에 만들고, 각 구성요소가 준비된 뒤에야 actual state가 따라온다.

```mermaid
sequenceDiagram
    participant U as 관리자/GitOps
    participant A as API server
    participant O as GPU Operator controller
    participant D as DaemonSet controller
    participant K as node kubelet
    participant S as 상태/conditions
    U->>A: spec 변경, metadata.generation 증가
    O->>A: 새 generation 관찰
    O->>D: 하위 DaemonSet/ConfigMap 조정
    D->>K: 새 Pod가 필요한 노드 결정
    K-->>D: Pod Ready 또는 실패
    D-->>O: desired/updated/available 상태
    O-->>S: 지원되는 status/condition 갱신
```

GPU 노드 3대에 Toolkit Pod를 하나씩 두는 단순 예를 보자.

| 시각 | 정책 generation | DaemonSet desired | updated | available | 해석 |
|---|---:|---:|---:|---:|---|
| t0 | 7 | 3 | 3 | 3 | 이전 선언이 세 노드에서 준비됨 |
| t1 | 8 | 3 | 0 | 3 | 새 선언 저장, rollout은 아직 시작 전 |
| t2 | 8 | 3 | 1 | 2 | 한 노드 교체 중, old/new Pod 혼재 |
| t3 | 8 | 3 | 3 | 2 | 새 Pod는 모두 생성됐지만 한 Pod 미준비 |
| t4 | 8 | 3 | 3 | 3 | 하위 리소스 관점 rollout 완료 |

`generation=8`이라는 숫자만으로 t4라고 말할 수 없다. 이는 spec이 여덟 번째 세대라는 뜻이다. Controller가 제공하는 `observedGeneration`이나 condition이 있다면 어느 세대를 처리했는지 확인하고, 실제 하위 DaemonSet의 desired/updated/available과 노드 Pod 상태를 함께 본다. 정확한 status 필드 이름은 사용 중인 CRD 버전이 제공하는 스키마를 따른다.

노드 한 대가 cordon되어 있어 desired가 3이 아니라 2가 되는지, selector에서 빠졌는지, Pod가 생성됐지만 driver mount 때문에 Ready가 아닌지도 구별한다. “Operator Ready”는 controller process가 살아 있다는 신호일 수 있고, 모든 구성요소가 모든 GPU 노드에서 준비됐다는 증명과는 다르다.

각 단계의 작성 주체도 다르다.

- 관리자 또는 GitOps는 `ClusterPolicy`나 `GPUCluster`의 spec을 바꾼다.
- GPU Operator controller는 선택한 관리 모델에 맞는 하위 객체를 조정한다.
- DaemonSet controller는 노드별 Pod 수를 맞춘다.
- kubelet은 자기 노드에서 image, mount, device 접근을 준비하고 Pod status를 갱신한다.
- Validator와 각 operand는 기능 확인 결과와 로그를 남긴다.

반례로, DaemonSet `available=3`이어도 새 커널로 재부팅한 뒤 host driver가 로드되지 않으면 CUDA 경로는 실패할 수 있다. 반대로 한 validator가 실패했다고 물리 GPU 세 장이 모두 고장 난 것도 아니다. Desired/actual 차이가 어느 객체와 어느 노드에서 생겼는지 좁혀야 한다.

## 3.6 흔한 오해

**오해 1: Operator 하나가 CUDA 애플리케이션까지 설치한다.**
Operator는 플랫폼 구성요소를 관리한다. 애플리케이션 이미지의 CUDA 사용자 공간은 별도 책임이다.

**오해 2: 노드 라벨이 있으면 GPU가 정상이다.**
라벨은 탐지 결과다. 드라이버와 할당 경로의 현재 정상 여부는 상태와 검증 결과를 함께 본다.

**오해 3: DCGM 메트릭이 있으면 자동 복구된다.**
관측, 판단, 복구는 서로 다른 단계다.

**오해 4: GPUCluster는 기존 ClusterPolicy를 자동으로 안전하게 바꾼다.**
지원되는 in-place 마이그레이션으로 가정하지 말고 소유권을 분리한 전환 계획을 세운다.

## 3.7 확인 문제

1. 호스트 이미지가 드라이버를 설치할 때 Operator 설정에서 가장 먼저 확인할 것은 무엇인가?
2. GFD 라벨과 device plugin의 자원 광고는 어떻게 다른가?
3. Validator가 성공했어도 애플리케이션 성능 시험이 필요한 이유는 무엇인가?
4. GPUCluster가 있으면 Toolkit이 반드시 설치된다고 말할 수 있는가?

### 해설

1. Operator도 같은 드라이버를 설치하도록 되어 있는지 확인해 소유권 충돌을 막는다.
2. GFD는 GPU 특징을 라벨로 표현하고, device plugin은 kubelet이 할당할 자원을 광고한다.
3. Validator는 플랫폼 연결을 확인하지만 데이터·모델·통신 패턴별 성능을 보장하지 않는다.
4. 말할 수 없다. 해당 버전의 관리 설정과 실제 하위 리소스 및 상태를 확인해야 한다.

---

[이전 장](02-device-plugin-path.md) · [다음 장](04-dra-concepts-and-objects.md)
