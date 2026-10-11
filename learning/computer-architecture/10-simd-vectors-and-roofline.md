# 10. SIMD·벡터·Roofline

[← 이전](09-mmu-tlb-and-page-walks.md) · [목차](README.md) · [다음 →](11-numa-interconnects-dma-and-iommu.md)

**배열**은 같은 종류의 값을 번호 순서대로 저장한 구조이고 그 안의 값 하나를 **원소**라고 한다. 원소를 하나씩 읽고 계산하고 쓰면 CPU가 같은 종류의 기계 명령을 반복해서 해독한다. 많은 과학 계산과 인공지능 작업은 여러 값에 같은 연산을 적용한다. 이 장에서 설명하는 SIMD와 벡터 명령은 한 기계 명령으로 여러 원소의 작업을 나타내어 해독 비용을 줄이고 여러 계산 회로를 함께 사용한다.

![roofline](assets/roofline.svg)

## 1. 스칼라, 벡터, SIMD

**스칼라(scalar)**는 한 번의 연산에서 하나의 수를 다루는 형태다. 스칼라 ADD는 두 수를 더해 한 결과를 만든다.

**벡터(vector)**는 같은 종류의 원소 여러 개를 순서 있는 묶음으로 표현한 data다. [10,20,30,40]은 4개 정수 원소의 vector다. **벡터 레지스터**는 이런 원소 묶음을 CPU 내부에 담도록 ISA가 제공하는 register다. 일반 정수 register보다 넓거나 여러 물리 slice로 구현될 수 있다.

**SIMD(Single Instruction, Multiple Data)**는 하나의 instruction이 여러 데이터 원소에 같은 operation을 적용하는 실행 방식이다. 벡터 ADD가 두 vector의 같은 위치 원소를 각각 더한다.

~~~text
A = [10, 20, 30, 40]
B = [ 1,  2,  3,  4]
C = [11, 22, 33, 44]
~~~

**lane(레인)**은 한 시점에 vector의 특정 원소 연산을 담당하는 논리 실행 통로다. 4lane 장치라면 네 원소를 병렬 처리할 수 있다. lane은 소스 배열 원소 자체도, OS thread도 아니다. 물리 ALU 수와 pipeline 방식에 따라 한 벡터 instruction을 여러 cycle에 나누어 실행할 수도 있다.

ISA가 한 instruction에 표현하는 벡터 길이와 microarchitecture가 한 cycle에 처리하는 lane 수를 구분한다. 512bit register에 32bit 원소 16개가 들어가도 물리 lane이 8개면 두 묶음으로 처리할 수 있다. ISA 폭만 보고 latency와 throughput을 단정하지 않는다.

## 2. 실제 배열을 4lane으로 처리한다

길이 10인 int 배열의 모든 원소에 1을 더한다고 하자.

| 벡터 실행 | 배열 index | 입력 | 활성 mask | 출력 |
|---:|---|---|---|---|
| 1 | 0~3 | 10,20,30,40 | 1111 | 11,21,31,41 |
| 2 | 4~7 | 50,60,70,80 | 1111 | 51,61,71,81 |
| 3 | 8~9 | 90,100,없음,없음 | 1100 | 91,101,미기록,미기록 |

**mask(마스크)**는 각 원소 위치의 연산과 메모리 access를 활성화할지 나타내는 비트 묶음이다. 마지막 두 bit를 0으로 두면 존재하지 않는 index 10,11에 store하지 않는다.

배열 길이가 vector가 한 번에 표현하는 원소 수의 배수가 아닐 때 남는 부분을 **tail(꼬리)**이라고 한다. tail을 스칼라 loop로 처리할 수도 있고 masked 벡터 연산 또는 벡터-length register로 처리할 수 있다.

RISC-V V extension은 구현의 벡터 레지스터 비트 길이 VLEN과 program이 현재 처리할 원소 수 VL을 분리하는 벡터-length-agnostic programming을 지원한다. software는 남은 원소 수를 보고 VL을 설정하고 반복한다. 특정 VLEN=256bit라고 고정한 binary만 만드는 방식과 다르다.

~~~mermaid
flowchart LR
  N[남은 원소 10] --> V1[VL=4, index 0~3]
  V1 --> V2[VL=4, index 4~7]
  V2 --> V3[VL=2, index 8~9]
  V3 --> Z[배열 밖 접근 없이 완료]
~~~

## 3. 조건문과 mask 추적

다음 스칼라 loop는 양수 원소만 두 배로 만든다.

~~~c
for (i=0; i<8; i++)
    if (a[i] > 0) out[i] = a[i] * 2;
    else out[i] = 0;
~~~

입력 [-3,5,0,7, -1,2,4,-8]을 4lane 두 묶음으로 처리한다.

첫 벡터:
- 비교 a>0 결과 mask=0101
- multiply 결과 후보 [-6,10,0,14]
- mask가 1인 lane은 후보, 0인 lane은 0을 선택
- 출력 [0,10,0,14]

둘째 벡터:
- 입력 [-1,2,4,-8]
- mask=0110
- 후보 [-2,4,8,-16]
- 출력 [0,4,8,0]

CPU 벡터 ISA는 compare가 mask register를 만들고 masked 연산 또는 select가 결과를 조합할 수 있다. 모든 조건문이 자동으로 효율적인 벡터 code가 되는 것은 아니다. branch 양쪽 일이 많고 mask가 자주 바뀌면 불필요한 lane 계산이 늘 수 있다.

## 4. GPU 스레드, warp, lane

GPU program은 많은 **스레드**를 만든다. thread는 자신의 index와 레지스터 상태를 가진 논리 실행 instance다. NVIDIA CUDA 용어의 **warp**는 하드웨어 scheduler가 함께 실행하도록 묶은 스레드 집단이며 현재 CUDA 문서의 일반 programming model에서는 warp size 32를 사용한다. 다른 GPU vendor의 wave 개념과 exact width는 별도다.

warp 안 thread가 같은 instruction을 실행하면서 각자 다른 data를 다루는 방식을 SIMT(Single Instruction, Multiple Threads)라고 설명한다. **warp lane**은 warp 안 thread의 위치다. CPU SIMD lane과 비슷한 병렬 ALU 사용이 있지만 programming state와 scheduling model은 같지 않다.

~~~text
thread 0: index 0 data 10
thread 1: index 1 data 20
...
thread 31: index 31 data 320
~~~

warp의 thread가 branch에서 서로 다른 경로를 선택하면 **divergence(분기 발산)**가 생긴다. hardware는 경로별 active mask를 사용해 한쪽을 실행한 뒤 다른 쪽을 실행하고 다시 합칠 수 있다. 두 경로를 동시에 모두 full throughput으로 실행하는 것이 아니다.

8thread 교육 warp에서 조건이 [T,T,F,F,T,F,T,F]라면 true mask=11001010, false mask=00110101처럼 서로 보완된다. true path 실행 때 false lane은 inactive, 이어 false path에서 true lane이 inactive다. 결과 correctness는 유지해도 실행 자원 활용률이 낮아진다.

독립 스레드 scheduling을 지원하는 GPU에서도 warp-synchronous한 암묵 가정을 함부로 쓰지 않는다. shared 데이터 교환에는 API가 요구하는 synchronization과 active mask를 사용한다.

## 5. 메모리 access와 coalescing

여러 lane이 연속 주소를 읽으면 메모리 subsystem이 적은 transaction으로 합칠 수 있다. 이를 **coalescing**이라고 한다. 스레드 i가 base+4i의 4byte float를 읽으면 32thread가 연속 128B 범위를 요청한다.

스레드 i가 base+4096i를 읽으면 각 lane이 먼 위치를 요청해 많은 transaction과 TLB/캐시 pressure가 생긴다. arithmetic lane이 많아도 memory가 data를 공급하지 못하면 성능이 오르지 않는다.

**gather**는 여러 비연속 주소에서 벡터 원소를 읽고 **scatter**는 비연속 주소에 쓴다. pointer나 index 배열을 vectorize할 수 있지만 contiguous load/store보다 latency와 bandwidth 효율이 낮을 수 있다. scatter에서 여러 lane이 같은 주소를 쓰면 conflict와 ordering 규칙을 확인해야 한다.

## 6. reduction

**reduction(축약)**은 여러 원소를 하나의 합, 최댓값, 논리값으로 줄인다. [1,2,3,4]의 합을 pairwise tree로 계산하면 (1+2)+(3+4)=10이다.

8개 원소를 sequential로 더하면 의존성 depth 7이지만 균형 tree는 3단계다. lane 간 shuffle 또는 shared memory와 synchronization이 필요하다. global 배열 reduction은 block별 partial sum을 만든 뒤 다시 합칠 수 있다.

floating-point 덧셈은 유한 정밀도 반올림 때문에 수학적 결합법칙이 정확히 성립하지 않는다. (a+b)+c와 a+(b+c)의 마지막 bit가 다를 수 있다. parallel reduction이 스칼라 순서와 bitwise 같은 결과를 보장하는지, 오차 tolerance인지 요구를 정한다.

## 7. matrix multiply와 tensor unit

matrix C=A×B의 C[i,j]는 A의 i행과 B의 j열 dot product다. 각 output에 multiply-add가 반복되어 vector와 GPU에 적합하다. 하지만 memory에서 같은 tile을 재사용하지 않으면 bandwidth가 병목이다.

**tile**은 큰 matrix를 작은 block으로 나눈 부분이다. fast shared memory나 cache에 A와 B tile을 올려 여러 multiply에 재사용한다. tile size는 레지스터, shared 메모리, 캐시, matrix shape에 맞춰야 한다.

**tensor 코어 또는 matrix unit**은 작은 matrix multiply-accumulate를 한 명령 또는 특수 pipeline으로 처리하는 실행 장치다. tensor는 여기서 다차원 숫자 배열을 뜻한다. input type FP16, BF16, INT8과 accumulation type FP32 같은 조합에 따라 throughput과 오차가 다르다.

peak tensor throughput은 원하는 shape, 정렬, 데이터 type, sparsity 조건을 충족할 때의 상한이다. 임의 스칼라 code가 자동으로 그 수치를 얻지 않는다. 데이터 conversion과 layout transform, tail, launch overhead도 포함해 측정한다.

## 8. arithmetic intensity

**FLOP(Floating-point Operation)**은 floating-point 덧셈이나 곱셈 같은 연산 수를 세는 단위다. fused multiply-add를 2FLOP으로 세는 관례가 흔하지만 보고서에서 정의한다.

**arithmetic intensity(연산 집약도)**는 메모리 hierarchy의 특정 경계에서 이동한 byte당 수행한 연산 수다. 단위는 FLOP/B다. 어느 메모리 경계인지가 중요하다. DRAM 바이트 기준 intensity와 L1 바이트 기준 intensity는 다르다.

벡터 add C=A+B는 원소 하나당 A 4B read, B 4B read, C 4B write로 최소 12B 이동하고 floating add 1회라 intensity는 약 1/12=0.083 FLOP/B다. write allocate나 캐시 effect가 있으면 traffic은 더 커질 수 있다.

matrix multiply는 tile reuse로 같은 A/B 원소를 여러 FLOP에 사용해 intensity를 높일 수 있다.

## 9. Roofline 모형

Roofline은 계산 장치의 peak rate와 메모리 bandwidth가 만드는 성능 상한을 비교하는 model이다.

~~~text
attainable performance <= min(peak compute, bandwidth × arithmetic intensity)
~~~

그림의 교육 시스템이 50GB/s, 200GFLOP/s라면 ridge point는 200/50=4FLOP/B다.

- intensity 2: bandwidth roof=50×2=100GFLOP/s, 메모리-bound
- intensity 8: bandwidth roof=400이지만 compute peak 200이 더 낮아 compute-bound
- intensity 4: 두 상한이 만나는 경계

단위를 맞춘다. GB/s×FLOP/B=GFLOP/s가 된다. peak에 도달한다는 보장이 아니라 위쪽 경계다. 명령 mix, 의존성, occupancy, 캐시, branch, synchronization으로 실제는 더 낮다.

**메모리-bound**는 현재 조건에서 데이터 이동 상한이 더 낮다는 뜻이고 **compute-bound**는 계산 상한이 더 낮다는 뜻이다. algorithm의 영원한 속성이 아니다. 캐시 reuse와 데이터 type, hardware가 바뀌면 위치가 달라진다.

## 10. operational intensity를 실제로 재기

source의 배열 크기만으로 DRAM traffic을 정확히 알 수 없다. 캐시 hit, writeback, prefetch가 있다. 하드웨어 counter나 profiler로 메모리 byte와 operation을 추정하되 카운터 정의를 확인한다.

warm cache와 cold 캐시, matrix size, batch, precision을 기록한다. GPU kernel time만 재면 host-device transfer와 launch를 제외한 값이다. end-to-end 연구라면 input copy, synchronization, output copy도 포함한 결과를 별도로 보고한다.

분모 byte를 줄이는 fusion은 intermediate array를 DRAM에 쓰고 다시 읽는 일을 없앨 수 있다. 하지만 fusion으로 레지스터 pressure가 높아져 occupancy가 떨어지는 반례도 있다.

## 11. 최신 연구 연결

scalable 벡터 ISA는 하드웨어 VLEN이 달라도 같은 반복문 binary가 VL을 조절해 실행되도록 한다. compiler의 벡터-length-agnostic code generation과 cost model이 중요하다.

AI accelerator 연구는 low 정밀도, structured sparsity, near-메모리 compute로 tensor throughput과 energy를 개선한다. 정확도 손실, sparsity metadata, unsupported 연산 fallback을 함께 평가한다. peak TOPS 숫자 하나로 모형 latency를 예측하지 않는다.

GPU 연구는 warp scheduling, asynchronous copy, tensor pipeline, multi-GPU collective overlap을 다룬다. 결과는 GPU generation, clock, matrix shape, library version, 데이터 type과 warm-up 조건의 측정이며 ISA 보장이 아니다.

## 12. 문제와 전체 풀이

### 문제 1
길이 14 배열을 4lane fixed vector로 처리하면 full 실행과 tail은?

**풀이:** 14//4=3번 full 실행으로 12개, tail 2개다. 마지막 mask는 두 lane만 활성화하거나 scalar로 2개를 처리한다.

### 문제 2
입력 [-2,3,0,5]에서 양수만 두 배로 하는 mask와 출력은?

**풀이:** 비교 a>0의 mask는 0101이다. multiply 후보는 [-4,6,0,10], inactive lane에 0을 선택하면 [0,6,0,10]이다.

### 문제 3
50GB/s, intensity 3FLOP/B, peak 200GFLOP/s의 Roofline 상한은?

**풀이:** bandwidth×intensity=150GFLOP/s가 peak 200보다 낮다. 상한은 150이고 model상 메모리-bound다.

### 문제 4
벡터 add의 최소 intensity가 낮은 이유는?

**풀이:** 원소당 4B input 두 개와 4B output, 총 12B를 옮겨 add 1회만 한다. 약 0.083FLOP/B다. cache와 write policy에 따라 실제 byte는 달라진다.

### 문제 5
warp branch의 절반만 true면 결과가 틀리는가?

**풀이:** active mask로 true와 false path를 나누어 실행하면 correctness는 유지된다. 다만 각 path에서 일부 lane이 쉬어 throughput이 낮아질 수 있다.

### 문제 6
4lane floating reduction이 scalar와 마지막 bit가 다를 수 있는 이유는?

**풀이:** pairwise tree와 스칼라 left-to-right의 덧셈 순서가 다르고 각 단계 반올림이 달라지기 때문이다. reproducibility 요구를 별도로 정해야 한다.

## 공식 자료

- [RISC-V Vector Extension](https://docs.riscv.org/)
- [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-programming-guide/)

[← 이전](09-mmu-tlb-and-page-walks.md) · [목차](README.md) · [다음 →](11-numa-interconnects-dma-and-iommu.md)
