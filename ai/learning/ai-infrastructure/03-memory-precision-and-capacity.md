# 03. 메모리·정밀도·용량: 모델이 들어간다는 말의 조건

[이전: 가속기 소프트웨어와 실행](02-accelerator-software-and-execution.md) · [다음: 훈련과 입력 파이프라인](04-training-and-input-pipelines.md) · [하드웨어 메모리](../../../hardware/learning/server-hardware/02-cpu-memory-numa.md) · [Linux OOM](../../../linux/learning/linux-kernel/04-virtual-memory-and-reclaim.md)

“이 모델이 GPU에 들어가나요?”라는 질문은 단순히 weight 파일 크기만 묻는 것이 아니다.
훈련인지 추론인지, batch와 sequence 길이가 얼마인지, dtype이 무엇인지, optimizer 상태가 있는지, KV cache를 얼마나 잡는지에 따라 답이 달라진다.
이 장은 메모리를 구성요소로 나누어 계산한다.

계산은 모델이다.
실제 peak memory는 workspace, allocator, fragmentation, graph capture, checkpointing, offload, tensor parallelism 때문에 달라질 수 있다.
그래도 손계산은 첫 번째 오류를 잡아준다.
단위와 가정을 적으면 “왜 안 들어가는지”를 토론할 수 있다.

## 메모리 구성요소

Weights는 모델 파라미터 값이다.
Inference에서는 주로 읽기 전용으로 사용된다.
Training에서는 optimizer step으로 갱신된다.

Gradients는 loss를 줄이기 위해 각 파라미터가 어느 방향으로 바뀌어야 하는지 나타내는 값이다.
Training backward 뒤에 생긴다.
Inference에서는 보통 필요 없다.

Optimizer state는 Adam 같은 optimizer가 사용하는 추가 상태다.
Adam은 흔히 first moment와 second moment를 저장한다.
구현과 dtype 정책에 따라 크기가 다르다.

Activations는 forward 중 layer 사이에 생기는 중간 tensor다.
Training에서는 backward 계산을 위해 많은 activation을 저장한다.
Inference에서도 layer output, attention 상태, KV cache 같은 중간값이 필요하다.

Temporary workspace는 library나 kernel이 연산을 빠르게 하기 위해 잠시 쓰는 buffer다.

Allocator overhead와 fragmentation 때문에 tensor payload 합과 실제 예약량이 다를 수 있다.

## 단위와 dtype

bit는 0 또는 1 하나다.
byte는 8 bits다.
FP32는 보통 4 bytes, FP16과 BF16은 2 bytes다.
INT8은 1 byte다.
4-bit weight는 값 하나가 0.5 byte처럼 보이지만, packing, scale, zero point, group metadata가 붙을 수 있다.

GB와 GiB를 구별한다.
`1 GB = 1,000,000,000 bytes`이고 `1 GiB = 1,073,741,824 bytes`다.
계산 예제에서는 bytes를 먼저 구하고 필요하면 GiB로 바꾼다.

## Weight memory 계산

7B parameters 모델을 FP16 weight로 저장한다고 하자.

```text
parameters = 7,000,000,000
bytes/parameter = 2
weight bytes = 14,000,000,000 bytes
GiB = 14,000,000,000 ÷ 1,073,741,824 ≈ 13.04 GiB
```

따라서 16 GiB GPU에 weight만 보면 들어갈 수 있어 보인다.
하지만 runtime buffer, KV cache, activation, workspace, allocator 여유가 필요하다.
또 embedding, tied weights, adapter, quantization metadata 때문에 parameter count와 파일 크기가 다르게 보일 수 있다.

## Training memory의 장난감 예

아주 작은 모델이 100M parameters라고 하자.
다음은 특정한 교육용 구성이다.
FP16 training weight 2 bytes, FP32 master weight 4 bytes, FP16 gradient 2 bytes, Adam moment 두 개를 FP32로 각각 4 bytes씩 둔다.
이 arrangement에서는 parameter 하나당 다음과 같다.

```text
FP16 weight        2 bytes
FP32 master weight 4 bytes
FP16 gradient      2 bytes
Adam m             4 bytes
Adam v             4 bytes
total             16 bytes/parameter
```

100M parameters면 다음이다.

```text
100,000,000 × 16 bytes = 1,600,000,000 bytes ≈ 1.49 GiB
```

여기서 16 bytes/parameter는 보편 법칙이 아니다.
명시한 FP16+FP32 master+Adam arrangement의 설명용 수치다.
다른 optimizer, mixed precision 정책, gradient sharding, optimizer offload, 8-bit optimizer를 쓰면 달라진다.

Activation은 별도다.
예를 들어 layer마다 저장해야 하는 activation이 평균 64 MiB이고 24 layers를 모두 보관한다고 단순 가정하면 다음이다.

```text
64 MiB/layer × 24 layers = 1536 MiB = 1.5 GiB
```

실제 training peak는 backward 순서와 activation checkpointing에 따라 달라진다.
Checkpointing은 일부 activation 저장을 줄이고 backward 때 forward를 다시 계산한다.

## Inference memory의 장난감 예

13B parameters 모델을 FP16 weight로 추론한다고 하자.

```text
13,000,000,000 × 2 bytes = 26,000,000,000 bytes ≈ 24.21 GiB
```

24 GiB GPU라면 weight만으로도 여유가 거의 없거나 들어가지 않을 수 있다.
더 큰 GPU, quantization, tensor parallelism, CPU offload, 더 작은 모델 같은 선택지가 생긴다.
하지만 quantization은 metadata와 kernel 지원, 품질 영향을 함께 검토해야 한다.

4-bit weight라고 단순히 13B × 0.5 byte만 계산하면 다음이다.

```text
13,000,000,000 × 0.5 byte = 6,500,000,000 bytes ≈ 6.05 GiB
```

여기에 scale, zero point, group size metadata, alignment, runtime buffer가 붙는다.
따라서 실제 메모리 사용량은 이론적 payload보다 클 수 있다.
“4-bit니까 FP16의 정확히 1/4”이라고 말하지 않는다.

## KV cache 공식

LLM autoregressive inference는 과거 token의 key와 value를 저장한다.
일반적인 per-layer KV cache payload 모델은 다음처럼 쓸 수 있다.

```text
KV bytes = batch × sequence_length × num_kv_heads × head_dim × 2(K and V) × bytes_per_element
```

전체 layer에 대해 저장하면 layers를 곱한다.
Multi-query attention이나 grouped-query attention에서는 query head 수보다 KV head 수가 작을 수 있다.
GQA 논문은 multi-head attention에서 key/value head 수를 줄여 추론 속도와 품질 tradeoff를 다루는 방법을 설명한다.

예를 들어 batch 8, context 4096, layers 32, KV heads 8, head dim 128, FP16이면 다음이다.

```text
per layer = 8 × 4096 × 8 × 128 × 2 × 2 bytes
          = 134,217,728 bytes
          = 128 MiB

all layers = 128 MiB × 32
           = 4096 MiB
           = 4 GiB
```

이 값은 total KV cache payload다.
Tensor parallelism으로 KV cache를 여러 GPU에 나누는 구현이라면 per-device 값은 줄 수 있다.
반대로 replicate하면 각 device가 같은 cache를 가질 수 있다.
항상 total과 per-device를 구별한다.

## Per-device와 total memory

GPU 4장에 모델을 나눴다고 해서 모든 메모리가 자동으로 1/4이 되는 것은 아니다.
Tensor parallelism은 일부 weight와 activation을 나눌 수 있다.
Data parallelism은 모델 복사본을 각 GPU에 둘 수 있다.
Pipeline parallelism은 layer를 장치별 stage로 나눈다.
KV cache도 serving engine의 배치 방식에 따라 shard되거나 replicate될 수 있다.

그래서 표에는 최소한 다음 열이 필요하다.

```text
component | total memory | per-device memory | sharded? | replicated? | assumption
```

이 구분이 없으면 “80GB GPU 8장이니 640GB 모델이 들어간다” 같은 위험한 결론이 나온다.
장치 사이 통신과 per-device peak가 실제 실행 가능성을 결정한다.

## OOM을 분류하기

OOM은 out of memory다.
하지만 모든 OOM이 같은 원인은 아니다.

Capacity OOM은 필요한 총 payload가 장치 용량보다 큰 경우다.
모델 weight와 KV cache만 더해도 안 들어갈 수 있다.
해결은 더 작은 모델, 더 낮은 precision, sharding, offload, context/batch 축소다.

Peak OOM은 평균 사용량은 낮아 보이지만 특정 순간 activation이나 workspace가 치솟는 경우다.
해결은 batch 축소, activation checkpointing, 다른 algorithm, compiler/fusion 조정, workspace 제한이다.

Fragmentation OOM은 총 free memory는 있어 보이지만 필요한 연속 block을 얻지 못하는 경우다.
Allocator 설정, shape 안정화, process 재시작, memory pool 정책 점검이 필요할 수 있다.

External OOM은 다른 process나 display, monitoring, 이전 job이 memory를 잡고 있는 경우다.
프로세스별 사용량을 확인해야 한다.

Host OOM도 있다.
GPU memory가 아니라 CPU RAM이 부족해 dataloader, tokenizer, mmap, page cache, checkpoint load가 실패할 수 있다.
Linux OOM killer는 [Linux 메모리 장](../../../linux/learning/linux-kernel/04-virtual-memory-and-reclaim.md)의 주제다.

## Concrete budget: 작은 추론 서버

가정한다.
모델 weight는 7B parameters FP16이다.
GPU는 24 GiB 하나다.
KV cache는 batch 4, context 2048, layers 32, KV heads 32, head dim 128, FP16이다.
Runtime과 workspace 여유를 2 GiB로 잡는다.

Weight는 앞에서 계산한 것처럼 13.04 GiB다.
KV cache는 다음이다.

```text
per layer = 4 × 2048 × 32 × 128 × 2 × 2 bytes
          = 134,217,728 bytes
          = 128 MiB

all layers = 128 MiB × 32 = 4096 MiB = 4 GiB
```

총 단순 예산은 다음이다.

```text
13.04 GiB weight + 4 GiB KV + 2 GiB runtime/workspace
= 19.04 GiB
```

24 GiB 안에 숫자상 들어갈 수 있어 보인다.
그러나 activation peak, allocator reserved memory, framework overhead, 실제 모델 구조 차이, 다른 프로세스 사용량이 남아 있다.
따라서 이것은 “가능성 검토”이지 배포 보증이 아니다.

## Concrete budget: 작은 훈련 작업

가정한다.
모델은 500M parameters다.
앞의 교육용 16 bytes/parameter arrangement를 쓴다.
Activation peak를 6 GiB, workspace와 allocator 여유를 2 GiB로 잡는다.

```text
parameter states = 500,000,000 × 16 bytes
                 = 8,000,000,000 bytes
                 ≈ 7.45 GiB

total = 7.45 GiB + 6 GiB + 2 GiB
      = 15.45 GiB
```

16 GiB GPU에서는 매우 위험하다.
작은 shape 변화나 workspace 증가만으로 OOM이 날 수 있다.
batch를 줄이거나 activation checkpointing을 쓰거나 optimizer state를 shard/offload하는 선택지를 검토한다.
하지만 각 선택지는 속도와 복잡도를 바꾼다.

## Precision을 볼 때 묻는 질문

어떤 tensor가 어떤 dtype인가?
Weight, activation, gradient, optimizer state, accumulation dtype이 같지 않을 수 있다.
어떤 hardware가 그 dtype을 빠르게 지원하는가?
Kernel과 library가 해당 dtype 경로를 실제로 쓰는가?
Quality metric은 허용 범위 안인가?
Overflow, underflow, scaling 정책은 무엇인가?

BF16은 FP16과 같은 2 bytes지만 exponent 범위가 다르다.
INT8과 4-bit quantization은 scale과 calibration 또는 fine-tuning 전략이 필요할 수 있다.
dtype 이름만으로 품질과 속도를 단정하지 않는다.

## 흔한 오개념

- Weight 파일이 들어가면 추론이 반드시 실행되는 것은 아니다.
- 16 bytes/parameter는 모든 training의 법칙이 아니다. 특정 FP16+FP32 master Adam 예시다.
- 4-bit 모델은 항상 FP16 메모리의 정확히 1/4이 아니다. metadata와 runtime buffer가 있다.
- GPU 여러 장의 용량을 단순 합산하면 per-device peak를 놓친다.
- OOM은 하나의 원인이 아니다. capacity, peak, fragmentation, external, host OOM을 나누어 본다.
- PyTorch allocated와 reserved memory는 같은 지표가 아니다.

## 연습 문제와 해설

문제 1.
3B parameters 모델을 BF16 weight로 저장하면 payload는 몇 GiB인가?

해설.
BF16은 2 bytes로 계산한다.
`3,000,000,000 × 2 = 6,000,000,000 bytes`.
`6,000,000,000 ÷ 1,073,741,824 ≈ 5.59 GiB`다.

문제 2.
Batch 2, context 8192, layers 40, KV heads 8, head dim 128, FP16인 KV cache payload는?

해설.
Per layer는 `2 × 8192 × 8 × 128 × 2 × 2 = 67,108,864 bytes = 64 MiB`다.
All layers는 `64 MiB × 40 = 2560 MiB = 2.5 GiB`다.
이 값이 total인지 per-device인지는 구현의 sharding 정책을 확인해야 한다.

문제 3.
GPU memory가 80 GiB이고 4장이 있다.
총 320 GiB라고만 적으면 왜 부족한가?

해설.
모델과 KV cache가 어떻게 나뉘는지 모르기 때문이다.
Per-device peak가 80 GiB를 넘으면 총합이 충분해도 실패한다.
통신 buffer와 replicated state도 별도로 봐야 한다.

문제 4.
Reserved memory가 높고 allocated memory는 낮은데 OOM이 났다.
가능한 원인 두 가지는?

해설.
첫째, fragmentation 때문에 큰 연속 block을 얻지 못했을 수 있다.
둘째, 다른 프로세스나 allocator가 장치 memory를 잡고 있어 실제 free memory가 부족할 수 있다.
Shape 변화와 allocator 설정, 프로세스별 GPU memory 사용량을 확인한다.

## 공식 자료와 원전

- PyTorch CUDA memory management: https://docs.pytorch.org/docs/stable/notes/cuda.html
- NVIDIA CUDA Programming Guide: https://docs.nvidia.com/cuda/cuda-c-programming-guide/
- Ainslie et al., GQA, Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints: https://arxiv.org/abs/2305.13245
- PyTorch autograd mechanics: https://docs.pytorch.org/docs/stable/notes/autograd.html

이 장은 capacity planning을 위한 손계산을 제공한다.
실제 배포 전에는 같은 모델 파일, 같은 runtime, 같은 batch/context 분포, 같은 GPU와 driver/library 버전에서 peak memory와 실패 모드를 측정해야 한다.
