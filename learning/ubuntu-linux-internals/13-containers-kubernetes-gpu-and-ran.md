# 13. Container, Kubernetes, GPU와 RAN

[이 책 목차](README.md) · [이전: Network I/O와 kernel 관찰](12-network-io-and-kernel-observation.md) · [다음: Troubleshooting과 증거](14-troubleshooting-and-evidence.md)

Kubernetes가 Pod를 node에 배치하는 결정, Linux가 process의 CPU·memory를 제한하는 결정, NVIDIA GPU가 device memory와 compute를 나누는 결정, RAN application이 deadline을 지키는 결정은 서로 다른 층에 있다. 한 층의 성공을 다음 층의 보장으로 바꾸지 않고 권한·배치·자원·지연의 전체 경로를 잇는다. 이 장의 YAML·수치·결과는 실행하지 않은 교육용 가상 모형이다. cluster, cgroup, GPU, RAN system을 변경하지 않았다.

![Application에서 kernel과 device까지 이어지는 workload 경로](assets/kernel-workload-path.svg)

## container는 별도 kernel이 아니라 격리된 process다

**namespace(이름공간)**는 process가 PID, mount, network interface, hostname, IPC, user 같은 kernel resource를 서로 다른 view로 보게 하는 격리 기능이다. kernel이 namespace object와 membership을 관리하고 reference가 사라지면 수명이 끝난다. network namespace 안의 eth0이나 PID 1은 host 전체와 같은 객체 번호가 아닐 수 있다. 이름과 가시성을 나누기 위해 필요하지만 CPU·memory 양을 제한하지는 않는다.

**cgroup(control group)**은 process 묶음의 CPU, memory, PID, I/O 사용을 계정하고 제한하는 kernel 계층 객체다. cgroup filesystem의 controller file로 상태와 정책을 표현한다. process가 이동하거나 종료될 때 membership이 바뀌며 빈 cgroup도 관리 주체가 제거하기 전까지 남을 수 있다. namespace는 “무엇을 보나”, cgroup은 “얼마나 쓰나”라는 질문에 답한다.

**container(컨테이너)**는 image에서 시작한 process를 namespace, cgroup, mount, capability와 보안 정책으로 묶은 실행 단위다. container마다 자동으로 별도 kernel이 생기는 VM이 아니다. **container runtime**은 kubelet 요청을 받아 OCI bundle을 준비하고 namespace·cgroup·mount·device 접근을 구성해 process를 시작·정리하는 node software다. runtime이 scheduler처럼 node를 고르지는 않는다.

**Pod**는 Kubernetes scheduler가 node에 배치하는 최소 workload 단위다. Pod 안 container들은 같은 node와 Pod network identity, 명시한 volume을 공유할 수 있지만 process와 container별 resource limit은 나뉠 수 있다. API object는 control plane 저장소에 있고 실제 process는 선택된 node에서 kubelet/runtime이 만든다.

~~~mermaid
flowchart TD
 P[Pod spec] --> S[Kubernetes scheduler]
 S --> B[Pod to node binding]
 B --> K[kubelet]
 K --> R[container runtime]
 R --> N[namespace와 mount]
 R --> C[cgroup CPU memory pids io]
 R --> D[GPU NIC device access]
 N --> A[application process]
 C --> A
 D --> A
 A --> X[RAN frame deadline]
~~~

### 문제 1: namespace와 cgroup이 각각 막는 것

container A와 B가 서로 다른 PID·network namespace지만 같은 CPU cgroup에 있고 quota 2 CPU를 공유한다고 하자. A가 B의 PID를 볼 수 있는가? CPU 2개씩 쓸 수 있는가?

서로 다른 PID namespace이면 일반적으로 각 view에서 다른 process가 보이지 않는다. network namespace도 interface와 socket table을 분리한다. 그러나 같은 CPU cgroup quota를 공유하면 A와 B 합계가 period budget을 경쟁하며 각각 2 CPU를 보장받지 않는다. 조건을 바꾸어 cgroup을 나눠도 host CPU와 cache, memory bandwidth는 공유할 수 있다. 가시성 격리와 성능 격리를 따로 검증한다.

## request는 배치 입력이고 limit는 실행 경계다

Kubernetes **request**는 scheduler가 Pod가 node에 fit하는지 계산하는 자원 요구량이다. node allocatable 16 CPU·64 GiB, 기존 request 12 CPU·48 GiB, 새 Pod request 6 CPU·8 GiB라면 CPU는 \(12+6=18>16\)이라 후보에서 제외되고 memory는 \(48+8=56≤64\)로 맞는다. 모든 조건을 만족해야 배치된다. 실제 CPU 사용이 낮아도 request 합 때문에 Pending일 수 있다.

**limit**는 runtime 사용 상한을 표현한다. CPU request는 share·weight에, CPU limit는 cgroup quota에 연결될 수 있다. scheduler는 기본적으로 request로 fit을 계산하므로 request 4, limit 6인 container는 4 CPU를 배치량으로 센다.

~~~yaml
resources:
  requests:
    cpu: "4"
    memory: 8Gi
  limits:
    cpu: "6"
    memory: 12Gi
~~~

이 조각은 교육용 container spec이며 단독 manifest로 적용하지 않았다.

**CPU quota**는 일정 period마다 cgroup이 쓸 수 있는 CPU time budget이다. 교육용으로 quota 600 ms/period 100 ms는 period 안에서 합산 6 CPU 상당을 허용한다. 6 thread가 100 ms 내내 쓰면 budget이 소진돼 다음 period까지 runnable thread가 throttled될 수 있다. CPU가 물리적으로 사라진 것이 아니라 정책 때문에 실행을 기다린다.

### 문제 2: request 4·limit 6과 7개 thread

node에 배치된 Pod가 CPU request 4, limit 6이고 runnable thread 7개다. scheduler 계산, 최대 burst와 deadline 위험을 설명하라.

scheduler fit에는 4 CPU가 쓰인다. node 여유와 cgroup 정책 아래에서 6 CPU 상당까지 실행할 수 있지만 7 thread가 계속 CPU를 요구하면 quota를 빨리 소진해 period 말에 throttling될 수 있다. request 4가 매 순간 네 core 즉시 실행을 보장하지 않고 limit 6도 여섯 전용 core를 예약하지 않는다. 조건을 바꾸어 limit를 없애면 여유 CPU burst는 가능하지만 다른 workload와의 contention과 node admission 정책을 봐야 한다.

## memory.high와 memory.max는 압력과 hard boundary다

cgroup v2의 **memory.high**는 사용량이 넘으면 process를 즉시 kill하는 hard limit가 아니라 강한 reclaim과 throttling을 유도하는 pressure 경계다. kernel memory controller가 charge와 reclaim을 관리한다. **memory.max**는 cgroup memory의 hard limit로, 회수해도 charge를 만족하지 못하면 cgroup OOM과 process kill로 이어질 수 있다.

memory charge에는 anonymous heap만 아니라 page cache와 일부 kernel memory가 포함될 수 있다. Kubernetes memory request는 배치에, container memory limit는 memory.max 같은 실행 경계에 연결될 수 있다. Pod phase가 Running이어도 한 container가 OOMKilled 뒤 restart될 수 있다.

~~~mermaid
sequenceDiagram
 participant A as application
 participant M as memory cgroup
 participant R as reclaim
 participant O as cgroup OOM
 A->>M: heap cache socket charge
 M->>R: memory.high 초과 pressure
 R-->>M: 충분한 page 회수 실패
 M->>O: memory.max charge 실패
 O-->>A: process kill 가능
~~~

### 문제 3: high 10 GiB, max 12 GiB에서 11 GiB 사용

memory.current가 11 GiB이고 high 10, max 12 GiB다. 즉시 OOM인가? 2 GiB를 추가하면 무엇이 가능한가?

high는 넘었으므로 allocation path에서 reclaim·throttling과 memory pressure가 생길 수 있지만 즉시 kill이라는 뜻은 아니다. 2 GiB 추가 요구는 단순 합 13 GiB로 max를 넘으므로 kernel은 reclaim을 시도하고 충분하지 않으면 cgroup OOM이 가능하다. 조건을 바꾸어 3 GiB가 깨끗한 회수 가능 page cache라면 max 아래로 만들 수 있으나 cache miss와 I/O 지연이 늘 수 있다. memory.events, PSI, OOM status를 같은 시간에 본다.

## scheduler, kubelet과 runtime의 권한이 다르다

scheduler는 미배치 Pod의 request, affinity, taint/toleration, volume과 device 조건을 보고 node binding을 기록한다. process를 실행하거나 cgroup file을 직접 쓰는 주체가 아니다. 선택된 node의 kubelet은 PodSpec을 관찰해 runtime과 device driver에 실제 준비를 요청하고 status를 보고한다. runtime은 process·namespace·cgroup·mount를 만들며 node 선택 권한은 없다.

Kubernetes RBAC은 API object 읽기·쓰기 권한을 제어한다. container 내부 Linux capability와 device node 접근 권한은 별도다. ResourceClaim을 만들 권한, driver가 allocation status를 갱신할 권한, container가 /dev/nvidia*를 여는 권한을 같은 “GPU 권한”으로 묶지 않는다.

### 문제 4: Scheduled지만 GPU application이 시작하지 못한 경우

Pod binding은 성공했고 ResourceClaim도 allocated로 보이지만 container가 GPU device를 열지 못했다. 어느 단계와 주체를 확인하는가?

scheduler의 node·allocation 선택은 끝났지만 node preparation, CDI 정보 생성, runtime device injection, device node permission, driver health, application library 초기화가 남는다. kubelet event, DRA driver 상태, runtime spec와 application error를 순서대로 본다. 조건을 바꾸어 device는 열리지만 kernel launch가 실패하면 VRAM, compute capability, driver/runtime version과 GPU health가 다음 범위다. Scheduled는 runtime usability 보장이 아니다.

## GPU device와 VRAM은 host memory와 다른 자원이다

**GPU(Graphics Processing Unit)**는 많은 계산을 병렬 수행하는 accelerator hardware다. PCIe나 전용 interconnect로 host에 붙고 kernel driver와 user runtime이 command·memory를 관리한다. **GPU device assignment**는 특정 GPU 또는 분할 instance에 container가 접근하도록 scheduler·device mechanism·runtime이 권한과 node 정보를 연결하는 과정이다.

**VRAM(Video RAM)**은 GPU에 붙은 device memory다. model weight, activation, communication buffer가 놓이며 GPU context와 driver가 수명을 관리한다. Linux cgroup memory.max는 주로 host memory charge 경계이며 같은 숫자로 VRAM 사용을 제한한다고 가정하지 않는다. pinned host buffer는 host memory이지만 reclaim이 어려워 memcg pressure를 키울 수 있다.

~~~text
교육용 host memory:
  process RSS 6 GiB
  pinned host buffer 4 GiB
  page cache 2 GiB

교육용 GPU memory:
  model weight 18 GiB
  activation peak 10 GiB
  communication buffer 2 GiB
~~~

host 관련 합은 12 GiB, GPU 관련 합은 30 GiB다. 두 주소 공간과 controller·telemetry가 다르다.

**MIG(Multi-Instance GPU)**는 지원 NVIDIA GPU를 hardware-isolated GPU instance로 나누어 compute와 memory resource 일부를 제공하는 기능이다. 모든 NVIDIA GPU에서 되는 일반 기능이 아니다. 지원 GPU, MIG mode·profile, driver와 NVIDIA device plugin 또는 DRA driver 구성이 맞아야 한다. “GPU 1개”라는 resource name이 full physical GPU인지 특정 MIG profile인지 확인한다. MIG는 instance 사이 격리를 제공하지만 node CPU, PCIe uplink, host memory와 다른 공용 자원까지 없애지 않는다.

### 문제 5: host 12 GiB limit와 GPU 30 GiB 사용

container memory limit가 12 GiB이고 GPU telemetry가 30 GiB다. limit 위반인가? pinned host buffer가 4 GiB에서 7 GiB로 늘면 무엇을 봐야 하는가?

GPU VRAM 30 GiB를 host memory.max 12 GiB와 직접 비교하지 않는다. 별도 device capacity와 driver accounting을 본다. pinned host buffer는 host charge에 포함될 수 있어 3 GiB 증가가 memory.max, reclaim과 OOM을 촉발할 수 있다. 조건을 바꾸어 GPU OOM이 나면 host limit을 올리는 것만으로 해결되지 않으며 model·activation·GPU instance capacity를 확인한다. host OOM과 GPU OOM의 error source를 구별한다.

## DRA는 device를 표현·배치하는 Kubernetes 자원 모델이다

**DRA(Dynamic Resource Allocation, 동적 자원 할당)**는 DeviceClass, ResourceSlice, ResourceClaim 같은 API object로 device 속성, 요청, allocation을 표현하고 scheduler·driver·kubelet이 준비를 조정하는 Kubernetes mechanism이다. device 자체나 NVIDIA driver의 다른 이름이 아니다.

2026-10 현재 Kubernetes 공식 문서에서 DRA core는 v1.35부터 stable이고 resource.k8s.io/v1 API를 사용한다. 이 문장은 cluster가 DRA-compatible driver를 자동으로 갖는다는 뜻이 아니다. driver가 ResourceSlice를 광고하고 claim에 맞는 device를 준비해 CDI(Container Device Interface) 등으로 runtime 접근 정보를 줘야 한다. 세부 기능은 버전 상태가 다르다. 예를 들어 device binding conditions는 v1.36부터 beta이며, resource pool status 같은 일부 관측 기능은 alpha feature gate가 필요할 수 있다. cluster의 정확한 minor version과 feature gate, driver 지원을 확인한다.

DRA 흐름은 driver의 ResourceSlice 광고, workload의 ResourceClaim, scheduler의 후보 device·node allocation, Pod binding, kubelet과 node driver의 prepare, runtime device access, application init, 종료 뒤 unprepare·cleanup 순이다. claim이 allocated여도 node prepare와 application init은 실패할 수 있다. 공식 제한으로 DRA resource를 점유한 기존 Pod를 필요한 고우선순위 Pod가 preempt하지 못해 Pending이 지속될 수 있는 조건도 확인한다.

### 문제 6: DRA stable을 “모든 GPU 자동 지원”으로 오해한 경우

Kubernetes 1.35 cluster라는 이유로 vendor GPU가 claim만 만들면 동작한다고 주장했다. 빠진 전제와 확인 상태를 적어라.

DRA core API 안정성만 확인됐다. GPU를 ResourceSlice로 광고하고 allocation·prepare·CDI를 수행하는 compatible driver, GPU kernel driver, runtime, 권한과 DeviceClass가 필요하다. cluster minor version의 세부 API와 driver release 호환성도 맞아야 한다. 조건을 바꾸어 전통적 device plugin extended resource를 쓴다면 그 경로와 DRA claim 경로를 구분한다. 최신 Kubernetes의 일부 extended-resource-to-DRA 기능도 해당 버전·gate 상태를 확인하고 일반 기능으로 소급하지 않는다.

## RAN deadline은 평균 처리량보다 늦은 꼬리를 본다

**RAN(Radio Access Network, 무선 접속망)**은 단말과 core network 사이의 radio 접속 계층이다. baseband의 PHY/MAC 작업은 frame·slot 시각에 맞춰 결과를 내야 한다. **deadline**은 해당 결과가 끝나야 하는 마지막 시각이고, 늦게 끝난 정확한 결과도 실시간 protocol에서는 쓸 수 없을 수 있다.

교육용 1 ms, 즉 1000 µs budget을 NIC/kernel 120, userspace parse 80, PHY/MAC 또는 accelerator 500, result queue/TX 150, jitter reserve 150으로 나누면 합이 1000이다. 평균 700 µs라도 p99.999가 1200이면 deadline miss가 있다. CPU quota throttling, scheduler preemption, IRQ·softirq, page fault·reclaim, GPU launch·queue, PCIe transfer, IOMMU, NIC queue를 같은 monotonic clock에 놓는다.

~~~text
정상 교육용 시간표
t=0µs    NIC RX 도착
t=90µs   NAPI/kernel 완료
t=160µs  application receive
t=260µs  GPU submit
t=720µs  GPU complete
t=810µs  send submit
t=880µs  TX path 진입

memory pressure 반례
t=160µs  receive
t=210µs  page fault와 memcg reclaim 시작
t=620µs  reclaim 종료
t=700µs  GPU submit
t=1160µs send 준비, deadline miss
~~~

### 문제 7: 1 ms budget 합산과 최적화 선택

kernel 150 µs, application 200, GPU 550, TX 180이 걸렸다. 합계와 초과를 구하고 GPU를 50 µs 줄인 경우를 계산하라.

합은 \(150+200+550+180=1080\) µs로 deadline을 80 µs 넘는다. GPU를 50 줄여도 1030 µs라 30 초과한다. 다른 경로와 reserve도 줄여야 한다. 조건을 바꾸어 평균이 900이어도 1% 요청이 reclaim 때문에 400 추가되면 tail miss가 남는다. throughput 평균 대신 frame ID별 deadline histogram과 각 단계 timestamp를 본다.

## CPU isolation과 device locality는 함께 맞춘다

cpuset으로 CPU를 배정해도 IRQ·softirq, kernel worker, RCU callback, SMT sibling, frequency·thermal throttling이 간섭할 수 있다. **NUMA(Non-Uniform Memory Access)**는 CPU socket에 따라 local·remote memory 접근 비용이 다른 구조다. NIC와 GPU PCIe locality, CPU cpuset, hugepage가 다른 NUMA node면 data 이동과 jitter가 늘 수 있다.

Kubernetes CPU Manager static policy와 Topology Manager는 조건에 맞는 Pod의 CPU·device topology 정렬을 도울 수 있지만 설치·정책·QoS 전제가 있다. 실제 Pod cpuset, IRQ affinity, device NUMA, hugepage allocation을 확인한다. Guaranteed QoS는 request=limit 설정을 바탕으로 eviction 우선순위에 영향을 주지만 realtime 실행, quota 무발생, GPU latency, NIC queue exclusivity, RAN deadline을 보장하지 않는다.

### 문제 8: Guaranteed Pod가 deadline을 놓친 이유

CPU·memory request와 limit가 같아 Guaranteed인 RAN Pod가 1 ms deadline을 놓쳤다. 확인할 Linux·device 증거를 순서대로 제시하라.

application frame timestamp로 어느 단계가 늘었는지 먼저 나눈다. cgroup cpu.stat의 throttling, run queue·scheduler latency, memory.events·PSI·page fault·reclaim, IRQ·softirq CPU, cpuset과 NUMA locality, GPU queue·VRAM·temperature·completion, NIC queue drop을 같은 시각에 연결한다. 조건을 바꾸어 CPU throttling이 0이어도 remote NUMA transfer와 GPU queue가 원인일 수 있다. QoS class는 원인 배제 증거가 아니다.

## 제출부터 radio 응답까지 책임을 잇는다

사용자가 request·limit과 GPU/NIC claim이 있는 PodSpec을 제출하면 API server가 object를 저장한다. scheduler는 allocatable, affinity, volume·device 조건으로 node와 device allocation을 고르고 binding을 기록한다. kubelet은 runtime과 driver에 sandbox, namespace, cgroup, mount와 device prepare를 요청한다. container process가 host heap·pinned buffer와 GPU VRAM을 각각 할당한다.

packet은 NIC queue, NAPI, kernel/socket 또는 userspace I/O path를 지나 application에 온다. CPU thread와 GPU kernel이 PHY/MAC 계산을 수행하고 deadline 전에 TX queue로 결과를 보낸다. kubelet은 container 생존과 restart를, cgroup은 CPU·memory 사건을, device telemetry는 GPU를, application은 frame deadline을 각각 보고한다. Pod scheduled, container Running, claim Allocated, frame deadline success는 서로 다른 상태다.

## 공식 근거

- [Kubernetes Pod and container resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Kubernetes Dynamic Resource Allocation](https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/)
- [Kubernetes DRA 작동 방식](https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/how-dra-works/)
- [Kubernetes CPU management policies](https://kubernetes.io/docs/tasks/administer-cluster/cpu-management-policies/)
- [NVIDIA MIG User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/)

[이 책 목차](README.md) · [이전: Network I/O와 kernel 관찰](12-network-io-and-kernel-observation.md) · [다음: Troubleshooting과 증거](14-troubleshooting-and-evidence.md)
