# 15. 문제·해설·용어사전·공식 자료 지도

답을 외우는 대신 요청부터 장치와 계산 결과까지 한 경로를 그린다. 문제의 숫자와 장치 이름은 교육용 예시다. 실제 성능 측정이나 특정 제품의 사양을 뜻하지 않는다.

## 15.1 계산과 경로 문제

### 문제 1. GPU가 두 장이면 30 GiB를 할당할 수 있나

각각 24 GiB GPU 두 장이 있다. 한 GPU에서 30 GiB allocation이 필요한 프로그램이 GPU 두 개를 요청했다. 자동으로 성공하는가?

**해설:** 아니다. 두 장치를 배정받는 일과 한 allocation을 분산하는 일은 다르다. 프로그램의 모델/텐서 분할·메모리 기능·통신 구조를 구현하고 peak를 확인해야 한다.

### 문제 2. 전체 GPU는 세 개인데 Pod가 Pending이다

node-a에 한 장, node-b에 한 장, node-c에 한 장이 있다. Pod 하나가 두 장을 요청한다. 다른 제약은 없다고 가정한다.

**해설:** 한 Pod는 한 node에 배치된다. 한 node에서 두 장을 제공하지 못하므로 클러스터 합계 세 장만으로 해결되지 않는다. 여러 node를 사용할 분산 workload는 별도 Pod·launcher 구조가 필요하다.

### 문제 3. DRA 요청 이름 세 개를 구별하기

Template 이름은 `gpu-per-pod`, Pod의 claim 참조 이름은 `accelerator`, Template 내부 device request 이름은 `gpu`다. container `resources.claims[].name`에는 무엇을 넣나?

**해설:** `accelerator`다. 이는 Pod의 claim 참조 이름을 연결한다. 특정 request만 소비할 때 `request: gpu`를 추가한다. 실제 생성된 ResourceClaim object 이름과도 구별한다.

### 문제 4. memory 조건이 맞는데도 할당 실패

같은 Pod가 40 GiB 이상 장치 하나와 20 GiB 이상 장치 하나를 요구한다. node-a는 48+24, node-b는 80이다.

**해설:** node-a에서 48과 24를 선택하면 만족한다. 80을 먼저 선택한 뒤 다른 node의 24를 묶으면 Pod의 공동 node 조건을 위반한다. 12장 모형으로 이 조합을 직접 확인한다.

### 문제 5. time-slicing replica 4의 의미

24 GiB 물리 GPU 한 장을 replica 4로 광고한다. workload 네 개가 각각 8 GiB를 사용할 예정이다. 모두 안전한가?

**해설:** 요구 합계는 32 GiB이고 광고된 slot은 독립 6 GiB VRAM 영역을 만드는 기능이 아니다. 실제 메모리·실행 동시성·오류 경계를 측정해야 한다. replica 개수로 memory isolation을 증명할 수 없다.

### 문제 6. Claim allocation과 CUDA 성공

ResourceClaim에 allocation이 있고 Pod가 Running이며 `nvidia-smi`도 성공한다. CUDA vectorAdd는 실패했다. 어디를 더 보나?

**해설:** prepare·CDI device/mount·runtime·library·CUDA 오류를 비교한다. 저장소 8월 기록은 UVM 관련 CDI 누락을 관찰했지만 모든 실패가 같은 원인이라는 결론은 아니다.

### 문제 7. Claim을 공유하면 GPU 두 장을 받나

container 두 개가 장치 하나를 할당한 같은 Claim을 참조한다.

**해설:** 같은 allocation 결과를 소비하는 구조다. 참조가 두 번 있다고 장치 두 개를 새로 할당하지 않는다. 공유 실행과 memory 조건은 별도다.

### 문제 8. Pod 종료 후 Claim은 항상 사라지나

명시적으로 만든 ResourceClaim을 Pod가 참조하고 있다. Pod만 삭제했다.

**해설:** 명시 Claim은 Pod보다 오래 남고 장치 allocation을 유지할 수 있다. Template 기반 Pod별 Claim의 owner 수명과 다르다. reservation·unprepare·claim deletion 조건을 구분한다.

### 문제 9. Stable DRA와 Alpha DynamicMIG

Kubernetes DRA core가 stable이다. NVIDIA DynamicMIG를 production 기본 기능으로 설명해도 되나?

**해설:** 아니다. 기준일 NVIDIA v0.5.0에서는 DynamicMIG가 Alpha·기본 비활성이다. upstream API·vendor 구현·hardware·policy는 별도 축이다.

### 문제 10. ComputeDomain이면 GPU도 할당됐나

지원 MNNVL 시스템에서 ComputeDomain을 만들었다. 학습 Pod의 GPU 배정도 완료됐는가?

**해설:** ComputeDomain은 IMEX domain/channel 등의 fabric 준비 경로다. GPU 자체의 Claim 할당·사용과 구별한다. 이름 하나로 두 생애를 합치지 않는다.

### 문제 11. 기존 YAML로 DRA를 쓰는가

Pod에는 `limits: nvidia.com/gpu: 1`만 보인다. device plugin을 쓴다고 확정할 수 있나?

**해설:** 최신 extended-resource compatibility 경로에서는 DeviceClass mapping에 따라 DRA backend가 충족할 수 있다. 실제 광고·Class·backend를 확인해야 한다.

### 문제 12. 같은 GPU를 allocator 두 개에 공개하기

기존 device plugin과 DRA GPU driver가 같은 GPU를 독립 inventory로 광고한다. 한쪽에서 할당해도 다른 쪽은 free라고 보인다.

**해설:** 같은 물리 장치를 중복 할당할 위험이 있다. 최신 Operator의 ClusterPolicy/GPUCluster 관리 모드 제약과 extended-resource 전환 경로를 따라 한 allocation 책임을 명확히 한다.

## 15.2 설계 과제와 해설 방향

**과제 A:** 24·48·80 GiB 장치가 섞인 교육용 클러스터에 서로 다른 메모리 요구의 작업을 배치한다. 속성 선택·공동 node 조건·예약·대기 이유를 표로 만든다. **해설 방향:** claim allocation 적합성과 계산 성공을 별도 판정하고 quota·queue가 모형에 포함됐는지 명시한다.

**과제 B:** 공유 방식 두 개를 비교하는 실험을 설계한다. **해설 방향:** 동일 GPU·image·입력·driver를 고정하고 throughput·tail latency·peak memory·실패 영향·metric 귀속 한계를 기록한다. 지원하지 않는 GPU에 MIG를 가정하지 않는다.

**과제 C:** Pod가 Pending → Running → CUDA 오류로 변한 가상 장애 보고서를 작성한다. **해설 방향:** 시각·객체 identity·allocation·prepare·runtime·실제 오류를 연결하고, 각 가설을 구별할 관찰을 제안한다. 관측 전 원인을 확정하지 않는다.

## 15.3 용어사전

| 용어 | 이 책에서의 뜻 |
| --- | --- |
| GPU | 병렬 계산을 수행하는 가속 장치 |
| VRAM | GPU 작업이 사용하는 장치 메모리 |
| Host RAM | CPU·프로세스가 사용하는 시스템 메모리 |
| Driver | 운영체제·프로그램과 장치 제어를 연결하는 소프트웨어 |
| Kernel module | Linux kernel에서 실행되는 모듈 |
| Device node | `/dev` 등의 장치 인터페이스 파일 |
| CUDA | NVIDIA GPU 개발·실행 생태계 |
| CUDA kernel | GPU에서 실행하도록 작성한 계산 함수 |
| NVML | NVIDIA 장치 관리·관측 library API |
| nvidia-smi | NVML 기반 GPU 상태 관리 도구 |
| UVM | NVIDIA Unified Virtual Memory 관련 driver 구성 |
| CUDA Toolkit | CUDA compiler·library·도구 묶음 |
| Container Toolkit | NVIDIA GPU 접근을 container runtime에 연결하는 도구 |
| Container runtime | container 실행 spec과 프로세스를 구현하는 runtime |
| CRI | Kubernetes kubelet과 container runtime의 interface |
| OCI | container image·runtime 등의 표준 규격 생태계 |
| CDI | Container Device Interface; 장치 주입 설정 규격 |
| Device injection | container에 장치·mount·설정을 전달하는 과정 |
| Device plugin | kubelet에 vendor 장치 자원을 등록하는 구현 |
| Extended resource | CPU/RAM 외 이름 있는 정수 자원 |
| Capacity | 공개된 총 자원/용량; 문맥별 대상 확인 |
| Allocatable | Node 등에서 배치에 사용할 수 있게 공개된 자원 |
| GPU Operator | NVIDIA GPU 구성요소를 선언에 맞춰 관리하는 controller |
| Operand | Operator가 관리·배포하는 구성요소 |
| CRD | Kubernetes API에 사용자 resource 정의를 추가하는 객체 |
| ClusterPolicy | NVIDIA Operator의 기존 device-plugin 관리 CR |
| GPUCluster | 최신 NVIDIA Operator의 DRA 관리 CR |
| NVIDIADriver | containerized GPU driver의 별도 관리 CR |
| NFD | Node Feature Discovery; node 속성 발견과 label |
| GFD | GPU Feature Discovery; NVIDIA GPU 속성 label |
| DCGM | NVIDIA Data Center GPU Manager; 관리·관측 기능 |
| DCGM Exporter | DCGM 지표를 metrics endpoint로 공개하는 구성요소 |
| Validator | 특정 GPU 실행 경로의 준비·사용 조건을 확인하는 workload |
| DRA | Dynamic Resource Allocation; 장치 요청·할당·준비 API 경로 |
| DRA driver | 특정 자원을 DRA 경로에 연결하는 구현 |
| DeviceClass | cluster 범위 장치 선택 규칙·설정 묶음 |
| ResourceSlice | driver가 공개하는 장치 inventory의 slice |
| Pool | 한 driver가 관리하는 inventory 집합의 이름 |
| ResourceClaim | namespace 범위 구체 장치 요청·allocation 객체 |
| ResourceClaimTemplate | Pod별 Claim을 만들기 위한 요청 template |
| Attribute | 장치 모델·주소 등 driver가 공개한 속성 |
| CEL | Common Expression Language; selector 표현 언어 |
| Exactly | 하나의 명확한 device 요청 묶음 |
| FirstAvailable | 우선순위 있는 대안 subrequest 목록 |
| Allocation | 요청을 구체 device identity와 연결하는 결정 |
| Reservation | allocation의 소비 Pod 등 사용 관계 추적 |
| ReservedFor | Claim을 예약한 소비자를 나타내는 status 정보 |
| Prepare | node-local driver가 할당 자원의 사용 준비를 하는 과정 |
| Unprepare | 사용 종료 후 node-local 준비를 해제하는 과정 |
| MIG | 지원 GPU의 하드웨어 인스턴스 분할 |
| MIG geometry | 하나의 GPU에 구성한 instance/profile 배치 |
| Time-slicing | 여러 작업의 GPU 실행을 시간적으로 공유 |
| MPS | Multi-Process Service; 여러 CUDA process 실행 공유 |
| Consumable capacity | 독립 Claim이 장치의 광고 용량을 나누어 소비하는 회계 |
| Partitionable device | underlying 자원을 공유하는 논리 device 표현 |
| Device taint | 장치 allocation·소비를 제한하는 상태/정책 |
| NUMA | CPU·memory·device의 거리 차이를 가진 구조 |
| PCIe topology | GPU·NIC 등이 연결된 root·switch·link 관계 |
| NVLink | 지원 GPU 사이의 고속 연결 기술 |
| MNNVL | Multi-Node NVLink; 지원 시스템의 노드 간 NVLink 연결 |
| IMEX | 지원 시스템의 GPU memory export/import 접근을 관리하는 구성 |
| ComputeDomain | NVIDIA MNNVL/IMEX 작업 연결을 관리하는 CR |
| NCCL | NVIDIA GPU collective communication library |
| Rank | 분산 실행에서 process에 붙이는 논리 번호 |
| Image digest | image 내용을 식별하는 hash identity |
| Feature gate | 특정 기능을 활성화하는 버전별 설정 |
| GA/Stable | 기능이 정식 지원 단계에 도달한 상태 |
| Beta/Alpha | 각각의 시험·지원 조건을 확인해야 하는 단계 |

## 15.4 공식 자료 지도

| 궁금한 질문 | 공식 근거 |
| --- | --- |
| GPU Operator의 현재 지원·component 버전 | [Platform support](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/platform-support.html) |
| 최신 managed DRA 설치·상호배타·제한 | [Operator 26.7 DRA](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.7/dra-intro-install.html) |
| GPU Operator 릴리스 변경 | [Release notes](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/release-notes.html) |
| Container 연결의 내부 구조 | [Toolkit architecture](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/arch-overview.html) |
| CDI 설정과 제한 | [Toolkit CDI](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html) |
| CUDA와 driver 호환성 | [CUDA Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/latest/index.html) |
| 기존 plugin의 등록·Allocate | [Kubernetes Device Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/) |
| DRA 기본 객체 | [DRA 개념](https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/) |
| Scheduler·controller·kubelet 생애 | [How DRA works](https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/how-dra-works/) |
| Claim API의 정확한 필드 | [ResourceClaim v1](https://kubernetes.io/docs/reference/kubernetes-api/resource/resource-claim-v1/) |
| 실제 workload 참조 구조 | [Allocate devices task](https://kubernetes.io/docs/tasks/configure-pod-container/assign-resources/allocate-devices-dra/) |
| NVIDIA GPU selector | [Request full GPUs](https://dra-driver-nvidia-gpu.sigs.k8s.io/docs/guides/gpu-allocation/allocating-gpus/) |
| NVIDIA driver 구성요소 | [Driver architecture](https://dra-driver-nvidia-gpu.sigs.k8s.io/docs/concepts/architecture/) |
| ComputeDomain과 IMEX | [ComputeDomain workload](https://dra-driver-nvidia-gpu.sigs.k8s.io/docs/guides/compute-domain-workloads/) |
| Time-slicing의 memory·fault 한계 | [NVIDIA sharing](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html) |
| MIG의 실제 지원·profile | [MIG User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/index.html) |
| DRA MPS 조건 | [MPS guide](https://dra-driver-nvidia-gpu.sigs.k8s.io/docs/guides/mps/) |
| Upstream 고급 기능 단계 | [DRA features](https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/dra-features/) |
| Device status·health·metadata | [DRA observability](https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/dra-observability/) |
| DRA 권한 경계 | [DRA hardening](https://kubernetes.io/docs/concepts/security/hardening-guide/dynamic-resource-allocation/) |

위 문서의 `latest`는 앞으로 내용이 바뀔 수 있다. 재현 실험에서는 설치 버전·release tag·지원 표 확인 날짜를 함께 남긴다. 교육용 모형과 실제 적용 기록도 분리한다.

[이전: 버전·기능 단계](14-versions-and-feature-status.md) · [목차](README.md) · [통합 교재](../README.md)
