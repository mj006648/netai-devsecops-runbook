# 09. GPU 클러스터와 배치

[AI 인프라 학습 목차](README.md) · 이전: [08. 데이터, 모델, 체크포인트](08-data-models-and-checkpoints.md) · 다음: [10. 관측, 벤치마크, 비용](10-observation-benchmarking-and-cost.md)

이 장은 GPU가 여러 대 있는 환경에서 “어디에 어떤 작업을 놓을 것인가”를 다룬다.
Kubernetes나 Slurm을 실제로 배포하지 않는다.
대신 node, Pod, process, rank, GPU, NIC, NUMA, PCIe, RDMA, NCCL 같은 단어가 서로 어떻게 연결되는지 배운다.

AI 클러스터 문제는 단순히 GPU 개수 세기가 아니다.
같은 8 GPU라도 한 노드 안 NVLink로 묶인 8 GPU와, 네트워크를 건너는 8 GPU는 통신 비용이 다르다.
또한 GPU memory가 충분해도 CPU memory, local disk, network, image pull, checkpoint I/O 때문에 pending이나 straggler가 생길 수 있다.

## 핵심 용어

- **node:** Kubernetes나 Slurm이 작업을 올리는 물리/가상 서버다.
- **Pod:** Kubernetes에서 함께 배치되는 하나 이상의 container 묶음이다.
- **process:** OS가 실행하는 프로그램 인스턴스다.
- **rank:** 분산 학습에서 각 process에 붙는 번호다. 보통 rank마다 GPU 하나를 담당한다.
- **world size:** 전체 rank 수다.
- **device plugin:** Kubernetes kubelet에 장치 자원을 알려주는 플러그인 방식이다.
- **DRA:** Dynamic Resource Allocation. Kubernetes에서 장치 요청과 할당을 더 구조화하는 API 경로다.
- **MIG:** NVIDIA Multi-Instance GPU. 지원 GPU를 하드웨어 격리된 여러 인스턴스로 나누는 기능이다.
- **MPS:** NVIDIA Multi-Process Service. 여러 CUDA process가 GPU를 더 잘 공유하도록 돕는 기능이다.
- **time-slicing:** 여러 workload가 시간적으로 GPU를 나누어 쓰는 방식이다.
- **NUMA:** CPU socket과 memory 가까움이 균일하지 않은 구조다.
- **PCIe topology:** GPU, NIC, NVMe가 어떤 root complex와 switch를 공유하는지 나타내는 연결 구조다.
- **RDMA:** CPU 개입을 줄이고 NIC가 원격 memory와 직접 데이터 교환을 돕는 기술 범주다.
- **NCCL:** NVIDIA GPU collective communication library다.
- **placement:** 작업을 어느 node, GPU, topology에 둘지 정하는 일이다.
- **straggler:** 같은 job 안에서 다른 rank보다 늦어 전체를 기다리게 만드는 rank다.

## Device plugin과 DRA

Kubernetes의 전통적인 GPU 사용은 device plugin이 kubelet에 `nvidia.com/gpu` 같은 확장 자원을 알리는 방식이다.
Pod는 resource limit에 GPU 개수를 요청하고, scheduler는 해당 개수를 가진 node를 찾는다.
이 모델은 단순하고 널리 쓰인다.
하지만 장치의 세부 속성, 동적 준비, 복잡한 topology 요구를 표현하기에는 제한이 있다.

DRA는 장치 요청을 ResourceClaim 같은 구조로 표현해 더 풍부한 할당을 가능하게 하려는 경로다.
공식 Kubernetes 문서는 DRA가 device allocation을 구조화한다고 설명한다.
NVIDIA DRA driver 문서는 multi-node NVLink fabric 같은 더 복잡한 할당을 다루는 사례를 제시한다.

초보자는 둘을 “신구 기술”로만 외우면 안 된다.
운영 환경에서는 device plugin 기반 경로가 여전히 존재하고, DRA는 cluster version, driver, plugin, scheduler 통합 상태를 확인해야 한다.
이 장에서는 배포 절차를 제공하지 않고 개념만 다룬다.

## Node, Pod, process, rank

분산 학습 job이 2 node × 4 GPU로 돈다고 하자.
가능한 구조는 다음과 같다.

- node는 2대다.
- 각 node에는 GPU 4개가 있다.
- 각 node에 Pod 1개를 올릴 수 있다.
- 각 Pod 안에서 process 4개를 실행할 수 있다.
- 전체 rank는 8개다.
- 보통 rank 0-3은 node A, rank 4-7은 node B에 놓는다.

rank는 Kubernetes object가 아니다.
rank는 training launcher와 framework가 process에 부여하는 논리 번호다.
Pod가 Running이어도 rank 초기화가 실패할 수 있고, rank가 떠도 NCCL 연결이 실패할 수 있다.
그래서 진단할 때 scheduler 상태와 process 로그를 둘 다 봐야 한다.

## Whole GPU, MIG, MPS, time-slicing

whole GPU는 GPU 하나를 한 workload에 통째로 준다.
격리와 예측 가능성이 가장 단순하다.
대신 작은 추론 workload에는 낭비가 생길 수 있다.

MIG는 지원 GPU에서 GPU를 여러 인스턴스로 나누어 각 인스턴스에 계산/메모리 자원을 격리한다.
MIG profile은 제품과 설정에 의존한다.
MIG를 쓰면 “GPU 한 장”이라는 말보다 “어떤 profile의 몇 인스턴스”가 더 정확하다.

MPS는 여러 process가 같은 GPU에서 CUDA 작업을 공유하도록 돕는다. NVIDIA device plugin의 MPS sharing 경로는 control daemon을 통해 client별 memory와 compute 몫을 제한할 수 있다.
이 자원 제한을 MIG의 하드웨어 자원 분할·격리와 같은 계약으로 보지는 않는다. 확인한 [device plugin 문서](https://github.com/NVIDIA/k8s-device-plugin#with-cuda-mps)는 MPS sharing을 experimental로 설명하고 MIG가 켜진 장치에서는 지원하지 않는다고 명시한다. 지원 조합과 제한 방식은 설치한 plugin·CUDA 버전에서 다시 확인한다.

time-slicing은 여러 Pod나 workload가 GPU를 번갈아 쓰게 한다.
시간을 나누는 것이지 GPU memory를 자동으로 안전하게 fractional guarantee로 나누는 뜻이 아니다.
NVIDIA device plugin 문서는 sharing 전략으로 time-slicing과 MPS를 설명하지만, 운영자는 isolation과 fault boundary를 별도로 이해해야 한다.

## 배치가 성능을 바꾸는 이유

GPU 계산 자체보다 GPU 사이 통신이 느리면 전체 job이 느려진다.
분산 학습의 all-reduce는 모든 rank가 gradient를 교환해야 다음 step으로 간다.
rank 하나가 느리면 나머지도 기다린다.

placement에서 보는 항목은 다음과 같다.

- 같은 node 안 GPU끼리 빠른 링크가 있는가.
- GPU와 NIC가 같은 PCIe switch 또는 NUMA node에 가까운가.
- NIC가 RDMA를 지원하고 설정이 맞는가.
- local NVMe cache와 CPU memory가 충분한가.
- 같은 node에 noisy workload가 있는가.
- scheduler가 topology 정보를 알고 있는가.

NCCL은 topology와 network 선택에 민감하다.
NCCL 환경 변수 문서는 network interface, topology file, debug 같은 설정을 제공한다.
하지만 환경 변수를 임의로 넣는 것은 치료가 아니라 실험이다.
변경 전후의 topology, log, 성능을 함께 남겨야 한다.

## Slurm, Kubernetes, Kueue의 관점

Slurm은 HPC에서 오래 쓰인 cluster workload manager다.
공식 문서는 resource allocation, job queue, scheduling, job launch를 핵심 기능으로 설명한다.
사용자는 `sbatch` 같은 방식으로 job을 제출하고, scheduler는 partition, priority, resource 조건을 보고 실행한다.

Kubernetes는 container orchestration 시스템이다.
Pod, node, resource request/limit, scheduler, controller를 중심으로 움직인다.
long-running service와 batch job을 모두 다룰 수 있지만, AI batch queue 정책은 기본 scheduler만으로 충분하지 않을 수 있다.

Kueue는 Kubernetes-native job queueing을 제공한다.
Kueue 문서는 Workload, ClusterQueue, LocalQueue, admission 같은 개념을 사용한다.
admission은 job을 시작해도 되는지 quota 기준으로 결정하는 단계다.

세 시스템을 “무엇이 더 좋다”로 외우지 않는다.
질문을 나눈다.
누가 quota를 정하는가.
누가 queue 순서를 정하는가.
누가 Pod/process를 실제로 띄우는가.
누가 GPU topology를 알고 있는가.
누가 실패한 rank를 재시작하는가.

## Pending, OOM, straggler 진단 행렬

| 증상 | 먼저 볼 곳 | 가능한 원인 | 다음 질문 |
| --- | --- | --- | --- |
| Pod Pending | scheduler event, quota | GPU 부족, node selector, taint, queue admission 대기 | 자원이 정말 없나, 정책 때문에 막혔나 |
| Pod Running but no GPU | container env, device files | device plugin/CDI/runtime 문제 | container 안에 장치가 보이나 |
| CUDA OOM | process log, memory metric | model/KV/batch가 큼, fragmentation, 다른 process | 누가 GPU memory를 잡고 있나 |
| CPU OOM | kubelet event, cgroup | dataloader, tokenizer, cache, mmap | GPU 문제가 아니라 host memory인가 |
| Slow all-reduce | NCCL log, NIC counter | topology, network, rank imbalance | 특정 rank만 느린가 |
| Low GPU use | dataloader, queue, CPU | input pipeline, small batch, sync wait | GPU가 기다리는 대상은 무엇인가 |
| Random retry storm | job controller, logs | rank failure, checkpoint restore 실패 | 같은 원인이 반복되나 |

이 표는 명령 목록이 아니라 사고 순서다.
실제 명령은 운영 권한과 환경별 runbook을 따라야 한다.

## 읽기 전용 예시 명령

아래 명령은 운영 cluster에서 읽기 전용으로 상태를 보는 예시다.
이 문서는 실행을 요구하지 않는다.
권한, context, namespace를 확인하지 않고 붙여넣지 않는다.

```bash
kubectl get nodes
kubectl describe pod "$POD_NAME" -n "$NAMESPACE"
kubectl get events -n "$NAMESPACE" --sort-by=.lastTimestamp
kubectl logs "$POD_NAME" -n "$NAMESPACE"
```

GPU node 내부에서는 다음 정보가 topology 추정에 쓰일 수 있다.
역시 읽기 예시일 뿐이다.

```bash
nvidia-smi topo -m
nvidia-smi
lspci -tv
numactl --hardware
```

## Worked calculation: rank 배치

8 GPU job이 두 가지 배치 후보를 가진다고 하자.

- 후보 A: 8 GPU가 한 node 안에 있다.
- 후보 B: 4 GPU node 두 대에 걸쳐 있다.

학습 step에서 node 안 통신은 80 ms, node 간 통신은 220 ms라고 단순 가정한다.
계산 시간은 500 ms다.

```python
compute_ms = 500
intra_ms = 80
inter_ms = 220
step_a = compute_ms + intra_ms
step_b = compute_ms + inter_ms
print(step_a, step_b, round(step_b / step_a, 2))
```

후보 A는 580 ms, 후보 B는 720 ms다.
후보 B는 이 단순 모델에서 1.24배 느리다.
현실에서는 통신과 계산이 일부 overlap될 수 있지만, placement가 step time을 바꾸는 이유는 이 계산으로 볼 수 있다.

## 기존 runbook 연결

이 저장소에는 실제 GPU 운영 기록이 있다.
초보자는 먼저 이 장의 개념을 읽고, 그 다음 실제 runbook에서 어떤 문제가 어떤 증거로 기록되었는지 본다.

- Kubernetes GPU 운영 색인: <../../../kubernetes/gpu/README.md>
- NVIDIA AI Infrastructure와 DSX 학습 메모: <../../../kubernetes/gpu/nvidia-ai-infrastructure-dsx-notes-2026-08.md>
- TwinX GPU node onboarding 기록: <../../../kubernetes/gpu/twinx-kiss-gpu-node-onboarding-2026-08-24.md>

실제 runbook은 특정 장비와 날짜의 기록이다.
거기에 나온 명령이나 설정을 일반 처방으로 복사하지 않는다.
개념, 증거, 실패 복구 흐름을 배운다.

## 오개념 바로잡기

- “GPU 8개면 어디 있든 8배다”: topology와 통신 때문에 아니다.
- “MIG/MPS/time-slicing은 모두 같은 GPU 쪼개기다”: 격리와 보장 범위가 다르다.
- “time-slicing이면 memory도 공평히 나뉜다”: 시간 공유와 memory quota는 다른 문제다.
- “Pod Running이면 학습이 정상이다”: rank 초기화, NCCL, data path가 실패할 수 있다.
- “NCCL env 하나면 통신 문제가 해결된다”: topology와 network 증거 없이 넣는 설정은 새 문제를 만들 수 있다.
- “Kubernetes가 topology를 알아서 최적으로 잡는다”: plugin, scheduler, policy가 제공하는 정보에 의존한다.

## 공식 자료

- Kubernetes GPU scheduling: <https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/>
- Kubernetes Dynamic Resource Allocation: <https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/>
- NVIDIA Kubernetes device plugin sharing 문서: <https://github.com/NVIDIA/k8s-device-plugin/blob/main/README.md>
- NVIDIA DRA driver for GPUs: <https://dra-driver-nvidia-gpu.sigs.k8s.io/>
- Kueue concepts: <https://kueue.sigs.k8s.io/docs/concepts/>
- Slurm overview: <https://slurm.schedmd.com/overview.html>
- NCCL environment variables: <https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/env.html>

## 연습문제

1. Pod가 Pending이다. GPU memory가 부족하다고 바로 결론내도 되는가?
   답: 아니다. Pending은 scheduler/admission 단계 문제일 수 있다. GPU 부족, quota, taint, selector, queue 정책을 먼저 본다.

2. 한 GPU를 네 Pod가 time-slicing으로 공유한다. 각 Pod가 GPU memory 1/4을 보장받는가?
   답: 그렇게 일반화할 수 없다. time-slicing은 시간 공유 전략이며 memory 격리/보장은 별도 메커니즘과 설정에 달려 있다.

3. 16 rank job에서 rank 12만 step마다 늦다. 볼 후보 두 가지는?
   답: rank 12가 놓인 GPU/NIC topology, data loader/cache 상태, 해당 process의 OOM/retry/log, node의 noisy neighbor를 본다.

4. Slurm과 Kueue를 한 문장으로 구별하라.
   답: Slurm은 HPC workload manager이고, Kueue는 Kubernetes 위에서 job queue와 quota admission을 제공하는 시스템이다.
