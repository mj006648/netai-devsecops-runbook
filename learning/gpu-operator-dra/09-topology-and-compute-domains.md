# 09. 토폴로지와 ComputeDomain

GPU 개수만 같아도 성능은 크게 달라질 수 있다.
## 09.0 토폴로지는 “무엇과 무엇이 어떤 길로 연결되는가”다

**토폴로지**는 GPU 개수 목록이 아니라 CPU, 메모리, PCIe switch, GPU, NIC 사이의 연결 구조다. 같은 모델 GPU 두 장도 서로 다른 CPU socket에 붙거나 NVLink 연결 유무가 다르면 데이터 이동 시간과 대역폭이 달라진다. scheduler가 장치를 등록하고 Claim에 할당했다는 사실은 이 연결 품질을 자동 최적화했다는 뜻이 아니다.

**NUMA**, Non-Uniform Memory Access는 CPU socket마다 가까운 RAM이 있어 접근 시간이 위치에 따라 달라지는 서버 구조다. **PCIe**는 CPU·GPU·NIC 같은 장치를 연결하는 버스다. **root complex**는 CPU 쪽 PCIe 계층의 시작점이다. **NVLink**는 지원 NVIDIA GPU 사이의 고대역폭 직접 연결이다. **NIC**는 network interface card, 즉 다른 node와 packet을 주고받는 물리 네트워크 장치다.

분산 학습은 GPU만 쓰지 않는다. CPU가 batch를 준비하고 RAM에서 GPU로 데이터를 보내며, 여러 GPU가 gradient를 교환한다. 따라서 CPU thread와 memory가 GPU에서 먼 NUMA node에 있거나, GPU 통신이 느린 PCIe/NIC 경로를 타면 계산 engine이 쉬는 시간이 늘어난다.

## 09.1 한 노드의 두 GPU와 두 workload를 추적한다

node-a에 CPU socket 0과 가까운 `gpu0`, socket 1과 가까운 `gpu1`이 있고 두 GPU 사이에는 NVLink가 없다고 하자. Pod A는 GPU 두 개로 data parallel 학습을 하고, Pod B는 CPU preprocessing을 많이 하는 추론 작업이다.

```mermaid
flowchart LR
    M0["NUMA0 RAM"] --- C0["CPU socket0"]
    C0 --- P0["PCIe root0"]
    P0 --- G0["GPU0"]
    M1["NUMA1 RAM"] --- C1["CPU socket1"]
    C1 --- P1["PCIe root1"]
    P1 --- G1["GPU1"]
    P1 --- N["NIC"]
    A["Pod A: GPU0+GPU1"] --> G0
    A --> G1
    B["Pod B: CPU NUMA0 + GPU1"] --> C0
    B --> G1
```

Pod A가 두 GPU를 할당받았다는 것은 Claim allocation 성공이다. NCCL이 GPU0과 GPU1 사이의 최적 통신 경로를 선택해 실제 collective를 시작해야 학습이 진행된다. NVLink가 없으면 PCIe와 CPU interconnect를 거칠 수 있다. Pod B의 CPU thread가 NUMA0에 있고 GPU1이 NUMA1에 가까우면 host-to-device 전송이 socket 사이 링크를 지난다.

**NCCL**, NVIDIA Collective Communications Library는 여러 GPU process가 all-reduce, broadcast 같은 집단 통신을 수행하는 사용자 공간 라이브러리다. **all-reduce**는 각 GPU의 값을 합산한 결과를 모든 참여 GPU에 돌려주는 연산이다. NCCL은 Kubernetes 장치를 할당하지 않는다. 이미 열린 GPU와 network를 사용해 통신 알고리즘을 선택한다.

| 단계 | 주체 | 증명되는 것 | 증명되지 않는 것 |
| --- | --- | --- | --- |
| ResourceSlice 광고 | DRA driver | GPU와 속성이 API에 보임 | GPU 사이 실제 대역폭 |
| Claim allocation | scheduler | 선택 device와 node 결정 | NCCL 연결 성공 |
| 노드 준비 RPC 성공 | kubelet/driver 로그 | NodePrepareResources 호출이 성공함 | 컨테이너 기동·collective 성능 |
| CDI/runtime | runtime | container device 접근 | CPU NUMA 배치 적합성 |
| CUDA context | app/driver | kernel 실행 가능 | 다중 GPU 동기화 |
| NCCL test | NCCL/process | 해당 경로 collective 성공 | 실제 모델 end-to-end SLO |

## 09.2 수치로 보는 가까운 경로와 먼 경로

1 GiB batch를 host RAM에서 GPU로 보낸다고 하자. 가까운 경로의 유효 대역폭이 20 GiB/s이면 단순 전송 시간은 `1/20 s = 50 ms`다. 먼 NUMA 경로가 12 GiB/s이면 `1/12 s ≈ 83 ms`다. 계산이 100 ms라면 한 step은 단순 합으로 150 ms와 183 ms가 된다. pipeline overlap이 있으면 실제 값은 달라지지만 위치 차이가 왜 중요한지 보여 준다.

두 GPU가 4 GiB gradient를 교환한다고 하자. 40 GiB/s 경로면 최소 전송 성분은 약 100 ms, 16 GiB/s 경로면 250 ms다. protocol overhead와 여러 rank의 collective 알고리즘 때문에 실제 시간은 더 길 수 있다. GPU 개수 2라는 숫자는 이 차이를 표현하지 않는다.

**Topology Manager**는 kubelet이 CPU, device, hugepage 같은 자원의 topology hint를 조정하는 기능이다. hint는 가능한 NUMA 위치 정보다. policy가 어떻게 설정됐는지와 device manager/DRA integration 지원을 확인해야 한다. Topology Manager가 존재한다고 모든 Pod가 최적 경로에 배치되는 것은 아니다.

## 09.3 ComputeDomain의 실체와 수명

**ComputeDomain**은 NVIDIA의 다중 node GPU 통신 구성을 표현하는 custom resource다. custom resource는 CRD가 추가한 Kubernetes API 객체다. 이 객체는 어떤 workload Pod들이 같은 통신 domain에 참여하는지 관리하는 데 쓰이지만, 실제 GPU 한 장을 선택하는 ResourceClaim을 대신하지 않는다.

**MNNVL**, Multi-Node NVLink는 지원 플랫폼에서 여러 node 사이에 NVLink 계열 연결을 확장하는 기술이다. **IMEX**, Internode Memory Exchange는 이런 구성에서 GPU memory sharing과 통신을 지원하는 NVIDIA 구성요소다. 이 기능들은 일반 Ethernet cluster의 모든 GPU에 자동 제공되지 않는다. GPU 모델, fabric, driver, Operator와 DRA driver 지원 조건이 맞아야 한다.

ComputeDomain 객체는 API server에 존재하고 관련 controller가 desired membership과 실제 daemon 상태를 조정한다. node의 IMEX daemon은 실제 통신 준비를 맡는다. Pod가 삭제되면 domain membership과 node-local endpoint 정리를 수행해야 한다. domain Ready가 Claim allocation을 뜻하지 않고, Claim Allocated가 domain 통신 Ready를 뜻하지도 않는다.

## 09.4 2노드·3장치·2Pod 분산 trace

node-a에 `a0`, `a1`, node-b에 `b0`이 있다. Pod A는 node-a의 a0, Pod B는 node-b의 b0을 받아 같은 ComputeDomain에서 통신한다고 하자.

1. DRA driver가 a0, a1, b0을 ResourceSlice로 광고한다.
2. scheduler가 Claim A→a0/node-a, Claim B→b0/node-b를 할당한다.
3. 각 kubelet이 prepare하고 runtime이 CDI device를 container에 넣는다.
4. ComputeDomain controller가 두 Pod membership과 IMEX 준비 상태를 조정한다.
5. 각 process가 CUDA context를 만들고 rank 번호를 얻는다.
6. NCCL이 NIC와 GPU topology를 탐색해 연결을 만든다.
7. 첫 all-reduce에서 network route, firewall, MTU, RDMA 조건 중 하나가 틀리면 hang 또는 timeout이 날 수 있다.
8. Claim의 allocation이 기록되고 NodePrepareResources RPC도 성공했을 수 있다. 표준 `NodePrepared` condition은 없으므로 RPC 결과는 kubelet·DRA 드라이버 로그로 확인한다. 그 뒤 컨테이너가 기동하고도 NCCL이 실패할 수 있으며, 이때 증거는 NCCL log, NIC/RDMA metric, ComputeDomain condition에 있다.

**RDMA**, Remote Direct Memory Access는 remote node 메모리와 데이터를 주고받을 때 CPU 복사를 줄이는 통신 방식이다. 지원 NIC, driver, network 설정과 권한이 모두 필요하다. PeRF 같은 연구 시스템의 RDMA 성능 결과는 특정 fabric과 workload 조건에 의존하며, DRA가 등록됐다는 이유로 같은 결과가 생기지 않는다.

## 09.5 실패와 정리

Pod A만 종료하면 Claim A와 node-a 준비 상태를 해제하고 ComputeDomain membership에서도 빠져야 한다. Pod B가 계속 실행 중이면 domain 전체 daemon을 무조건 내리면 안 된다. 마지막 member와 공유 infrastructure의 수명을 구분한다.

NCCL hang을 고치려고 Claim을 반복 삭제하면 장치만 다시 선택될 뿐 network MTU나 route 문제는 남는다. 반대로 Claim이 같은 node의 멀리 떨어진 GPU를 골라 topology가 병목이면 selector, device attribute, scheduler 조건을 바꿔야 한다. 증상과 실패 계층을 맞춘다.

## 09.6 지원 표와 연구를 읽는 기준

NVIDIA GPU Operator 26.7 platform matrix와 ComputeDomain 문서는 지원 GPU, Kubernetes, OS, fabric 조건을 확인하는 1차 근거다. 지원 조합은 기능 경로가 검증됐다는 뜻이며 사용자 모델의 bandwidth와 scaling efficiency를 보장하지 않는다.

network-sensitive GPU scheduling 연구는 통신량과 topology를 scheduler 입력으로 쓸 때의 개선을 특정 cluster와 trace에서 평가한다. Kubernetes 기본 scheduler나 DRA가 논문 정책을 자동 구현한다고 해석하지 않는다. GPU 수, link bandwidth, workload 통신 행렬, baseline, p99와 job completion time을 맞춰야 비교할 수 있다.

## 09.7 추가 완전 풀이 문제

**문제 1.** GPU 두 개가 같은 node에 있으므로 항상 NVLink로 통신하는가?

**해설.** 아니다. 물리 topology에 NVLink가 있어야 하고 NCCL이 사용 가능한 경로로 선택해야 한다. PCIe root, link 상태, NCCL topology log를 확인한다.

**문제 2.** Claim 두 개의 allocation이 기록되고 노드 준비 RPC도 성공했는데 all-reduce가 timeout이다. 어떤 계층을 본다?

**해설.** device 선택과 주입은 통과했다. ComputeDomain/IMEX 준비, NCCL rank 구성, NIC·RDMA·route·MTU와 firewall을 본다. allocation status만 반복 확인해서는 통신 오류를 설명할 수 없다.

**문제 3.** 1 GiB 전송에서 20 GiB/s와 10 GiB/s 경로의 단순 시간은?

**해설.** 각각 `1/20=0.05 s`, `1/10=0.1 s`로 50 ms와 100 ms다. 계산 overlap과 protocol overhead를 제외한 하한 모델이다.

**문제 4.** ComputeDomain Ready면 GPU allocation도 완료됐는가?

**해설.** 아니다. ComputeDomain은 다중 node 통신 구성을 관리하고 ResourceClaim은 device 선택을 기록한다. 두 객체 condition과 Pod 상태를 별도로 연결해야 한다.

**문제 5.** 논문에서 topology-aware 정책이 15% 빨랐으므로 모든 cluster에서 같은가?

**해설.** 아니다. GPU 연결, network, workload 통신량, baseline scheduler가 다르면 결과가 달라진다. 자신의 topology와 동일한 metric으로 재현 실험을 해야 한다.
CPU 메모리에 가까운 GPU인지, GPU끼리 NVLink로 연결되는지,
여러 노드의 GPU가 올바른 통신 도메인에 들어가는지가 분산 학습 성능을 좌우한다.

이 장에서는 NUMA, PCIe, NVLink, NCCL, MNNVL, IMEX와 ComputeDomain을 한 흐름으로 연결한다.
핵심은 **ComputeDomain은 GPU 할당 객체가 아니라는 점**이다.

![GPU 토폴로지](assets/topology.svg)

## 9.1 NUMA부터 시작하기

NUMA(Non-Uniform Memory Access) 시스템에서는 CPU 소켓마다 가까운 메모리가 있다.
GPU도 특정 PCIe root complex를 통해 한 CPU 소켓에 더 가깝게 연결될 수 있다.

```mermaid
flowchart LR
    subgraph N0[NUMA node 0]
      C0[CPU 0] --- M0[Memory 0]
      C0 --- P0[PCIe root 0]
      P0 --- G0[GPU 0]
      P0 --- G1[GPU 1]
    end
    subgraph N1[NUMA node 1]
      C1[CPU 1] --- M1[Memory 1]
      C1 --- P1[PCIe root 1]
      P1 --- G2[GPU 2]
      P1 --- G3[GPU 3]
    end
    G1 == NVLink ==> G2
```

GPU 0이 NUMA node 0에 가까운데 CPU 작업 스레드와 메모리를 NUMA node 1에 놓으면
CPU-GPU 데이터 이동이 더 먼 경로를 탈 수 있다.

Kubernetes의 Topology Manager는 CPU, 장치, 메모리 힌트를 조정할 수 있다.
그러나 힌트를 받는 각 구성요소와 정책 설정이 올바르게 연결되어야 한다.
[Topology Manager 공식 문서](https://kubernetes.io/docs/tasks/administer-cluster/topology-manager/)를 함께 참고한다.

## 9.2 PCIe와 NVLink

PCIe는 CPU·메모리·GPU·NIC를 연결하는 범용 입출력 경로다.
NVLink는 지원 GPU 사이에 높은 대역폭 연결을 제공한다.

NVLink가 있다고 모든 통신이 자동으로 NVLink만 사용하는 것은 아니다.
GPU 쌍의 실제 연결, 통신 라이브러리의 경로 선택, 데이터 배치가 모두 영향을 준다.

| 연결 | 주 용도 | 관찰할 점 |
|---|---|---|
| PCIe | CPU-GPU, GPU-NIC, 일반 장치 연결 | root complex, 세대, lane |
| NVLink | GPU-GPU 고속 통신 | 연결된 GPU 쌍, 링크 상태 |
| 네트워크 | 노드 간 통신 | NIC 위치, RDMA, 스위치 구조 |

## 9.3 NCCL은 토폴로지를 사용한다

NCCL은 NVIDIA GPU 집단 통신 라이브러리다.
AllReduce, AllGather, ReduceScatter 같은 연산을 제공하고,
가용한 NVLink, PCIe, 네트워크 경로를 고려해 통신한다.

NCCL은 GPU를 Kubernetes에 할당하지 않는다.
할당된 GPU 집합에서 통신을 수행하는 사용자 공간 계층이다.

NVIDIA NCCL의 개념과 지원 연산은
[공식 NCCL 문서](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/overview.html)를 기준으로 한다.

## 9.4 MNNVL과 IMEX

MNNVL(Multi-Node NVLink)은 지원 플랫폼에서 여러 노드의 GPU를 NVLink 도메인으로 연결한다.
IMEX는 그 다중 노드 GPU 메모리 접근과 교환을 지원하는 구성요소다.

이 기능은 모든 GPU 서버에서 사용할 수 있는 일반 네트워크 기능이 아니다.
지원 하드웨어, 펌웨어, 드라이버, Operator 버전과 플랫폼 매트릭스를 확인해야 한다.

## 9.5 ComputeDomain의 역할

ComputeDomain은 함께 통신할 워크로드와 노드 측 IMEX 구성을 연결하는 수명주기 객체다.
GPU를 몇 개 할당할지 결정하는 `ResourceClaim`을 대신하지 않는다.

```mermaid
flowchart TD
    CD[ComputeDomain] --> CP[ComputeDomain controller/plugin]
    CP --> N1[Node 1 IMEX 구성]
    CP --> N2[Node 2 IMEX 구성]
    RC1[GPU ResourceClaim 1] --> P1[Pod 1]
    RC2[GPU ResourceClaim 2] --> P2[Pod 2]
    P1 -. 도메인 참여 .-> CD
    P2 -. 도메인 참여 .-> CD
    P1 <== NCCL / MNNVL ==> P2
```

그림에서 두 수명주기를 분리해서 본다.

- `ResourceClaim`: Pod가 사용할 실제 GPU 장치의 선택과 할당
- `ComputeDomain`: 여러 Pod·노드가 공유할 통신 도메인의 구성과 수명

ComputeDomain API는 NVIDIA DRA 문서에서 확인한다.
[NVIDIA DRA 설치와 ComputeDomain 안내](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.7/dra-intro-install.html)는
지원 버전의 실제 필드와 사전 조건을 설명한다.

## 9.6 수명주기 예

2개 노드에 각각 GPU 4개를 사용하는 8-GPU 학습 작업을 생각하자.

1. 관리자가 통신에 참여할 워크로드를 위한 ComputeDomain을 준비한다.
2. 컨트롤러와 노드 플러그인이 필요한 IMEX 구성을 조정한다.
3. 각 Pod는 별도의 GPU `ResourceClaim`으로 4개 GPU를 요청한다.
4. 스케줄러가 claim을 만족하는 노드와 장치를 고른다.
5. Pod가 같은 ComputeDomain에 참여한다.
6. 애플리케이션의 NCCL 프로세스가 할당된 GPU로 집단 통신을 시작한다.
7. 작업 종료 후 claim과 ComputeDomain의 정리 조건에 따라 각각 해제한다.

GPU claim이 성공해도 ComputeDomain 준비가 실패할 수 있다.
반대로 ComputeDomain이 준비되어도 GPU claim이 부족하면 Pod는 실행되지 못한다.

### 9.6.1 두 수명주기를 한 시간축에 겹쳐 보기

2노드 학습 Job에 worker Pod 두 개가 있고, 각 Pod가 GPU 두 개를 요청한다고 하자. ComputeDomain `train-42`는 두 Pod가 함께 쓸 IMEX 통신 구성을 나타내고, Claim `gpu-worker-0`, `gpu-worker-1`은 실제 GPU identity를 가진다.

```text
t0  ComputeDomain train-42 생성
t1  domain controller가 node-a, node-b의 IMEX 준비 시작
t2  worker-0/1 Pod와 각자의 GPU Claim 생성
t3  scheduler가 worker-0 → node-a GPU0,1 할당
t4  scheduler가 worker-1 → node-b GPU0,1 할당
t5  두 Claim의 node Prepare와 CDI 주입 완료
t6  ComputeDomain Ready, 두 Pod 시작
t7  rank 0~3이 NCCL communicator 생성
t8  worker-1 실패, 해당 Pod/Claim 정리 시작
t9  replacement worker-1과 새 Claim 생성·할당
t10 replacement가 train-42 domain에 참여
t11 Job 종료, 모든 GPU Claim 해제
t12 마지막 참여자 종료 뒤 ComputeDomain 정리
```

```mermaid
sequenceDiagram
    participant CD as ComputeDomain train-42
    participant C0 as Claim worker-0
    participant C1 as Claim worker-1
    participant P as Pods/ranks
    CD->>CD: 두 노드 IMEX 준비
    C0->>C0: node-a GPU0,1 할당·Prepare
    C1->>C1: node-b GPU0,1 할당·Prepare
    CD-->>P: domain ready
    C0-->>P: GPU identity 전달
    C1-->>P: GPU identity 전달
    P->>P: NCCL communicator 생성
    P-->>C1: worker-1 종료, Claim 해제
    Note over CD: domain은 worker-0과 교체를 위해 유지 가능
    C1->>P: replacement Claim으로 재참여
    P-->>C0: Job 종료
    P-->>C1: Job 종료
    P-->>CD: 마지막 참여자 종료 후 domain 정리
```

이 예에서 t8에 GPU Claim 하나가 사라져도 ComputeDomain을 바로 지우면 남은 worker와 교체 Pod의 통신 구성이 깨질 수 있다. 반대로 t11에 GPU Claim을 모두 해제했는데 domain을 무기한 남기면 IMEX 관련 노드 상태와 객체가 누수될 수 있다. Job controller나 상위 워크로드가 두 객체군의 owner와 종료 순서를 분명히 해야 한다.

상태를 판단할 때는 다음 네 질문을 독립적으로 답한다.

| 질문 | 증거 |
|---|---|
| 실제 GPU가 정해졌는가? | 각 ResourceClaim의 allocation |
| 선택 노드에서 GPU 접근이 준비됐는가? | Claim Prepare와 Pod container 상태 |
| 통신 도메인이 준비됐는가? | ComputeDomain과 IMEX controller/plugin 상태 |
| 모든 rank가 통신에 참가했는가? | 애플리케이션/NCCL 로그와 rank membership |

ComputeDomain Ready와 Claim 4개 Allocated는 필요 조건일 수 있지만 충분 조건은 아니다. 예를 들어 rank 3 process가 시작 전에 종료되면 Kubernetes 객체는 준비돼 보여도 communicator 생성은 모든 참가자를 기다리다 실패할 수 있다.

반대로 Claim 하나가 Pending이라고 ComputeDomain controller를 먼저 재시작하는 것도 원인과 맞지 않을 수 있다. GPU 수량, selector, node placement를 먼저 본다. Domain은 GPU capacity를 만들어 내지 않는다.

Replacement Pod가 이전 Pod와 같은 GPU를 다시 받아야 한다고도 단정하지 않는다. 새 Claim allocation은 가용 inventory에서 다른 identity를 고를 수 있다. 애플리케이션이 checkpoint의 rank-to-device mapping을 고정했다면 재시작 시 새 rank, node, GPU mapping을 다시 구성해야 한다. ComputeDomain 이름이 같다는 사실은 물리 GPU identity까지 같다는 뜻이 아니다.

## 9.7 개념 YAML

다음은 객체 관계를 읽기 위한 축약 예다.
정확한 스키마는 설치한 CRD 버전을 확인한다.
더 이상 권장되지 않는 `spec.numNodes: 0` 같은 값을 새 예제로 복사하지 않는다.

```yaml
apiVersion: resource.nvidia.com/v1beta1
kind: ComputeDomain
metadata:
  name: training-domain
spec:
  numNodes: 2
```

이 객체만으로 GPU 8개가 할당되지는 않는다.
각 Pod 또는 워크로드가 사용할 GPU claim을 별도로 정의해야 한다.

## 9.8 숫자로 보는 경로 차이

다음 수치는 원리를 설명하는 가상의 측정값이다.

| 배치 | 1회 AllReduce | 100회 누적 |
|---|---:|---:|
| 같은 NVLink 도메인 | 8 ms | 0.8 s |
| PCIe 중심 경로 | 18 ms | 1.8 s |
| 노드 간 잘못된 NIC 경로 | 35 ms | 3.5 s |

GPU 계산이 동일해도 매 step마다 집단 통신을 하면 경로 차이가 누적된다.
그래서 GPU 개수와 모델만 기록하지 말고 실제 토폴로지와 통신 메트릭도 남긴다.

## 9.9 장애를 계층별로 나누기

| 증상 | 먼저 확인할 계층 |
|---|---|
| Pod가 Pending | claim, 장치 용량, 스케줄링 |
| Pod는 실행되나 도메인 준비 실패 | ComputeDomain controller, IMEX |
| 통신 연결 실패 | NCCL, 네트워크, IMEX 상태 |
| 실행되지만 느림 | NUMA, PCIe/NVLink, NIC affinity |
| 일부 rank만 멈춤 | rank 로그, NCCL 오류, 노드별 링크 |

## 9.10 흔한 오해

**오해 1: GPU 8개를 요청하면 자동으로 가장 빠른 8개가 선택된다.**
요청 표현과 드라이버의 선택 정책이 토폴로지 요구를 담아야 한다.

**오해 2: ComputeDomain이 GPU를 예약한다.**
GPU 할당은 ResourceClaim 수명주기다. ComputeDomain은 통신 도메인을 관리한다.

**오해 3: NVLink가 보이면 노드 간에도 바로 쓸 수 있다.**
노드 간 NVLink는 지원 MNNVL 플랫폼과 IMEX 구성이 필요하다.

**오해 4: NCCL은 Kubernetes 스케줄러다.**
NCCL은 할당 후 애플리케이션 프로세스가 사용하는 통신 라이브러리다.

## 9.11 확인 문제

1. NUMA와 PCIe 위치가 GPU 워크로드에 영향을 주는 이유는 무엇인가?
2. ComputeDomain과 ResourceClaim의 책임을 각각 한 문장으로 설명하라.
3. GPU claim은 성공했지만 분산 통신이 시작되지 않을 때 무엇을 구분해 확인해야 하는가?
4. NCCL의 역할은 무엇이며 무엇을 하지 않는가?

### 해설

1. CPU 메모리와 GPU 사이의 실제 데이터 경로와 지연이 위치에 따라 달라지기 때문이다.
2. ComputeDomain은 다중 노드 통신 구성을, ResourceClaim은 실제 GPU 선택과 할당을 담당한다.
3. ComputeDomain·IMEX 준비 상태와 NCCL·네트워크 연결을 claim 할당 상태와 분리해 본다.
4. NCCL은 GPU 집단 통신을 수행하며 Kubernetes 장치 할당은 하지 않는다.

---

[이전 장](08-sharing-mig-timeslicing-mps.md) · [다음 장](10-deployment-compatibility-and-gitops.md)
