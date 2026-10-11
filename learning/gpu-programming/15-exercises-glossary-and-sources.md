# 15. 종합 문제·용어사전·공식 출처

[이전: 14. 실험과 연구](14-experiments-and-research.md) · [목차](README.md)

각 문제는 주소와 상태를 손으로 쓴 뒤 해설을 본다.

```mermaid
flowchart LR
    O["객체 위치"] --> I["Index·주소"]
    I --> S["중간 상태"]
    S --> R["결과"]
    R --> C["반례·한계"]
```

## 1. 종합 worked problems

### 문제 1. Global index

Block 크기 128, blockIdx.x=2, threadIdx.x=17의 global index는?

**해설.** `2×128+17=273`이다. 이 thread가 array element 273을 맡는 mapping이라면 n보다 작은지 확인한다.

### 문제 2. Warp와 lane

Block threadIdx.x=77의 warp 번호와 lane은?

**해설.** `77//32=2`번 warp, `77%32=13`번 lane이다. Warp는 block 안 thread 번호를 32개씩 묶는다.

### 문제 3. Coalescing

32 lane이 base 0에서 4-byte element를 연속 읽을 때 주소 범위와 32-byte sector 수는?

**해설.** 주소 0,4,...,124이며 각 4 byte이므로 범위는 0~127이다. Sector 0~3 네 개다. 128-byte aligned 단순 모형 한 범위와 실제 sector 관점을 구분한다.

### 문제 4. Misalignment

같은 warp가 base 4에서 읽으면 sector 수는?

**해설.** 주소 4~131이므로 sector 0~4 다섯 개다. Architecture cache와 transaction 전체 성능은 별도 측정한다.

### 문제 5. Shared bank

32-bank, 4-byte word 모형에서 lane l이 shared[32l]을 읽는다. 무엇이 생기는가?

**해설.** Word index mod 32가 모두 0이다. 서로 다른 주소가 bank 0에 몰려 conflict가 난다. 모두 shared[0]을 read하는 broadcast와 다르다.

### 문제 6. Barrier

64-thread block에서 threadIdx<32만 `__syncthreads()`를 호출한다. 안전한가?

**해설.** 아니다. 참여 조건이 block 전체에 일치하지 않아 위험하다. Warp 하나만 온다는 사실로 block barrier를 만족하지 않는다.

### 문제 7. Reduction

`[1,2,3,4,5,6,7,8]`의 tree reduction 단계는?

**해설.** `[3,7,11,15]→[10,26]→[36]`이다. 각 shared 단계 사이 barrier가 필요하다.

### 문제 8. Tile matmul

A=`[[1,2],[3,4]]`, B=`[[5,6],[7,8]]`의 C01은?

**해설.** A row0과 B col1의 dot product `1×6+2×8=22`다.

### 문제 9. Async 수명

Host buffer로 async H2D를 enqueue한 뒤 event가 ready가 아닌데 buffer를 재사용해도 되는가?

**해설.** 안 된다. Copy가 아직 읽을 수 있다. Matching stream/event completion 뒤 재사용한다.

### 문제 10. Occupancy

SM 최대 64 warp 중 40 warp가 resident면 occupancy는?

**해설.** `40/64=62.5%`다. 이 숫자만으로 속도를 판단하지 않는다.

### 문제 11. Ring collective

P=4, message N=800 MiB인 단순 ring all-reduce의 GPU당 byte volume은?

**해설.** `2×(3/4)×800=1200 MiB`다. α·β와 topology를 생략한 volume 모형이다.

### 문제 12. Precision

FP16 input과 FP32 accumulator를 썼다. 결과가 CPU FP32와 bitwise 같아야 하는가?

**해설.** 아니다. Input quantization과 operation 순서가 다르다. Output dtype과 tolerance를 명시한다.

## 2. 추가 문제

1. n=1001, block=256의 grid와 여분 thread 수를 구하라.
2. Thread 5의 grid-stride가 64이면 처리 index 세 개를 쓰라.
3. Shared tile 두 phase 사이 두 번째 barrier가 없을 때의 race를 설명하라.
4. Device-scope atomic을 system-scope로 오해하면 어떤 observer를 놓치는가?
5. Graph build 1 ms, replay당 5 µs 절감의 break-even을 계산하라.
6. Intensity 3 FLOP/byte, bandwidth 2 TB/s의 bandwidth roof를 구하라.
7. All-reduce sum 뒤 average를 만들 때 world size 8이면 무엇을 하는가?
8. Profiler run과 timing run을 분리하는 이유를 쓰라.

## 3. 용어사전

| 용어 | 뜻 |
| --- | --- |
| GPU | 많은 병렬 계산 lane을 가진 processor |
| CPU | Host control과 범용 계산을 수행하는 processor |
| Host | CPU program과 system memory 쪽 실행 영역 |
| Device | GPU와 GPU-visible 자원 영역 |
| Kernel | GPU thread들이 실행하는 device 함수 |
| Thread | Kernel body의 한 logical 실행 instance |
| Block | Shared memory와 block barrier를 공유하는 thread 집합 |
| Grid | 한 kernel launch의 block 집합 |
| Warp | 함께 scheduling되는 현재 32-thread 묶음 |
| Lane | Warp 안 thread 위치 0~31 |
| SM | Streaming Multiprocessor, warp를 실행하는 GPU 단위 |
| SIMT | Single Instruction Multiple Threads 실행 관점 |
| Divergence | Warp lane이 다른 control path를 실행하는 상황 |
| Active mask | Warp operation에 참여하는 lane 집합 |
| Occupancy | 최대 active warp 대비 resident warp 비율 |
| Residency | Block·warp가 SM 자원을 점유하며 실행 가능한 상태 |
| Register | Thread scalar state에 쓰는 빠른 on-chip 자원 |
| Register pressure | Thread의 register 요구가 residency·spill을 제한하는 정도 |
| Spill | Register에 못 둔 값을 local memory로 내리는 현상 |
| Local memory | Thread-private device address space |
| Global memory | Device의 큰 공유 address space |
| Shared memory | Block thread가 공유하는 on-chip scratchpad |
| Constant memory | Read-only constant access에 쓰는 공간 |
| Cache | 최근 data를 가까운 memory에 보관하는 계층 |
| Allocation | Memory 영역을 확보하는 작업 |
| Alignment | 주소가 요구 byte 경계에 맞는 성질 |
| Coalescing | Warp memory 요청을 적은 transaction으로 묶는 성질 |
| Transaction | Memory system이 처리하는 전송 요청 단위 |
| Sector | Cache/transaction을 설명하는 작은 byte 구간 |
| Stride | 연속 lane 또는 iteration 주소 사이 간격 |
| AoS | Array of Structures layout |
| SoA | Structure of Arrays layout |
| Pitch | 2D row 사이 실제 byte 간격 |
| Bank | Shared memory 동시 접근을 나누는 내부 단위 |
| Bank conflict | 서로 다른 주소가 같은 bank에 몰리는 상황 |
| Broadcast | 여러 lane의 같은 주소 read를 공유하는 경로 |
| Barrier | 참여 execution 주체가 모두 도달할 때까지 기다리는 지점 |
| `__syncthreads()` | CUDA block 범위 barrier primitive |
| Synchronization | 실행 순서와 memory visibility 관계를 만드는 과정 |
| Data race | 충돌 access가 synchronization 없이 일어나는 오류 |
| Atomic | 한 location의 read-modify-write를 indivisible하게 하는 operation |
| Scope | Atomic/synchronization이 연결하는 observer 범위 |
| Memory order | Atomic 주변 memory operation의 ordering 계약 |
| Fence | Memory ordering/visibility를 만드는 primitive |
| Reduction | 여러 값을 하나로 결합하는 계산 |
| Scan | 각 prefix의 결합 결과를 만드는 계산 |
| Inclusive scan | 현재 element를 포함한 prefix 결과 |
| Exclusive scan | 현재 element 전까지의 prefix 결과 |
| Identity | 결합해도 값을 바꾸지 않는 원소 |
| Tiling | Data를 재사용 가능한 작은 tile로 나누는 방법 |
| Tile | 행렬·image 등의 작은 rectangular data 조각 |
| Matrix multiplication | Row와 column dot product로 output을 만드는 계산 |
| Accumulator | Partial result를 누적하는 변수·type |
| Tensor Core | 지원 matrix operation을 가속하는 GPU hardware 경로 |
| FP32 | 32-bit floating-point 형식 |
| FP16 | 16-bit floating-point 형식 |
| BF16 | 넓은 exponent와 짧은 significand의 16-bit 형식 |
| TF32 | Tensor Core용 TensorFloat-32 계산 형식/모드 |
| FP8 | 8-bit floating-point 계열 형식 |
| Rounding | 실수를 representable 값으로 근사하는 과정 |
| Overflow | 표현 가능한 큰 범위를 넘는 현상 |
| Underflow | 매우 작은 값이 0/subnormal 쪽으로 가는 현상 |
| ULP | 인접 representable 값 간격 관점의 단위 |
| Mixed precision | Input·accumulation·output에 다른 precision을 쓰는 방식 |
| Stream | GPU operation을 enqueue하는 ordered sequence |
| Event | Stream 진행 지점을 기록하는 object |
| Asynchronous | API 반환과 작업 completion이 분리되는 성질 |
| H2D | Host-to-Device data copy |
| D2H | Device-to-Host data copy |
| Pinned memory | Page-locked host memory |
| Double buffering | 두 buffer로 copy와 compute를 pipeline하는 방법 |
| CUDA Graph | GPU operation node와 dependency edge object |
| Graph capture | Stream 작업을 graph로 기록하는 기능 |
| Kernel fusion | 여러 kernel 계산을 하나로 합치는 최적화 |
| Launch overhead | Host가 kernel work를 enqueue하는 제어 비용 |
| Arithmetic intensity | 이동 byte당 arithmetic operation 수 |
| Roofline | Bandwidth·compute 상한으로 성능을 해석하는 모형 |
| Throughput | 단위 시간당 처리량 |
| Latency | 한 작업 완료까지 시간 |
| Profiler | Timeline·counter를 수집하는 도구 |
| Baseline | 비교 기준 implementation과 측정값 |
| Warm-up | 초기화 영향을 분리하는 준비 실행 |
| Collective | 여러 GPU/rank가 함께 수행하는 통신 operation |
| Rank | Collective participant의 논리 번호 |
| Broadcast collective | Root data를 모든 rank에 전달하는 operation |
| Reduce collective | 여러 rank 값을 root에 결합하는 operation |
| All-reduce | 결합 결과를 모든 rank가 받는 operation |
| All-gather | 각 rank 조각을 모든 rank가 모으는 operation |
| Reduce-scatter | Reduce 결과 조각을 rank별로 나누는 operation |
| Ring algorithm | Rank를 ring으로 연결해 chunk를 순환하는 방식 |
| Tree algorithm | Tree 단계로 data를 결합·전파하는 방식 |
| α·β model | Startup latency와 byte 비용으로 통신 시간을 근사하는 모형 |
| Peer access | GPU가 다른 GPU memory에 접근하는 기능 |
| Topology | GPU·link·switch의 물리 연결 구조 |
| Strong scaling | 총 문제 크기를 고정하고 자원을 늘리는 실험 |
| Weak scaling | 자원당 문제 크기를 고정하는 실험 |

## 4. 공식 출처

- [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-programming-guide/)
- [CUDA 13.2 Programming Guide PDF](https://docs.nvidia.com/cuda/cuda-programming-guide/pdf/cuda-programming-guide.pdf)
- [CUDA C++ memory model](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/cuda-cpp-memory-model.html)
- [CUDA Best Practices Guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
- [CUDA Runtime API](https://docs.nvidia.com/cuda/cuda-runtime-api/)
- [Nsight Systems](https://docs.nvidia.com/nsight-systems/)
- [Nsight Compute](https://docs.nvidia.com/nsight-compute/)
- [NCCL User Guide](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/)
- [CUDA Samples](https://github.com/NVIDIA/cuda-samples)

## 5. 마지막 점검

GPU code를 설명할 때 “빠르다”보다 먼저 실행 주체, memory 위치, index→주소, synchronization 범위, async 수명, result 검증을 쓴다. 성능 주장은 input·hardware·version·측정 범위와 profiler 증거를 함께 남긴다.
