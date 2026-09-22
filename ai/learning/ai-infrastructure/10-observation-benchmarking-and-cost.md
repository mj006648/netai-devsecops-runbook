# 10. 관측, 벤치마크, 비용

[AI 인프라 학습 목차](README.md) · 이전: [09. GPU 클러스터와 배치](09-gpu-clusters-and-placement.md) · 다음: [11. 로컬 실습과 연구](11-local-labs-and-research.md)

이 장은 AI 시스템을 “빠르다” 또는 “비싸다”라고 말하기 전에 무엇을 재고 무엇을 고정해야 하는지 다룬다.
GPU utilization, achieved throughput, memory usage, TTFT, ITL, p99, goodput, cost per million tokens는 서로 다른 질문에 답한다.
숫자 하나로 모든 것을 설명하려 하면 대부분 틀린다.

여기서 계산하는 가격은 모두 가상의 숫자다.
특정 cloud, GPU, vendor, 모델을 추천하지 않는다.
목표는 비용 산식과 측정 경계를 익히는 것이다.

## 핵심 용어

- **GPU utilization:** 측정 도구가 본 GPU busy 비율이다. 어떤 engine이 얼마나 효율적으로 일했는지 직접 말하지 않는다.
- **achieved throughput:** 실제 완료한 요청/토큰/샘플 처리량이다.
- **memory usage:** GPU 또는 host memory가 얼마나 할당되었는지 나타낸다.
- **TTFT:** 요청 도착부터 첫 토큰까지의 시간이다.
- **ITL:** 연속 출력 토큰 사이 간격이다.
- **E2E latency:** 마지막 응답까지의 전체 시간이다.
- **p99:** 표본 중 99%가 이 값 이하였다는 분위수다.
- **censoring:** timeout, cancel, drop 때문에 실제 완료 시간이 관측되지 않는 현상이다.
- **goodput:** SLO를 만족한 유효 처리량이다.
- **warmup:** cold start, JIT, cache fill, graph 준비 같은 초기 비용을 분리하는 준비 구간이다.
- **roofline:** 계산 성능과 메모리 대역폭 한계를 함께 보는 단순 성능 모델이다.
- **Amdahl 법칙:** 일부만 빨라질 때 전체 속도 향상 한계를 계산하는 모델이다.
- **Little 법칙:** 안정 상태에서 평균 동시성은 도착률 × 평균 체류 시간이라는 관계다.

## Utilization, throughput, memory는 다르다

GPU utilization이 95%라고 해서 좋은 서비스라고 말할 수 없다.
queue가 길어 사용자가 늦게 받는데 GPU가 계속 바쁠 수 있다.
반대로 utilization이 낮아도 interactive workload에서 TTFT와 ITL을 잘 지키면 의도한 상태일 수 있다.

throughput은 완료된 일의 양이다.
LLM에서는 requests/s, output tokens/s, total tokens/s, good tokens/s가 모두 가능하다.
prompt token과 output token 비용이 다르므로 어떤 token을 세는지 적어야 한다.

memory usage는 capacity 경고에 가깝다.
GPU memory가 98%여도 안정적으로 동작할 수 있고, 70%에서도 fragmentation이나 KV cache 정책 때문에 OOM이 날 수 있다.
memory 숫자는 batch shape와 allocator 상태를 같이 본다.

## E2E와 device-only timing

사용자는 device-only kernel 시간이 아니라 E2E를 경험한다.
E2E에는 client, network, gateway, auth, queue, CPU preprocessing, GPU compute, postprocess, streaming flush가 들어간다.
device-only timing은 kernel 또는 GPU stream 구간을 잘라 본다.

CUDA API는 비동기 실행이 많다.
CPU 타이머로 kernel 호출 전후를 감싸면 호출 제출 시간만 재고 실제 GPU 완료 시간을 놓칠 수 있다.
NVIDIA CUDA 문서는 asynchronous execution과 CUDA event timing을 설명한다.
device-only timing을 하려면 event나 synchronization 경계를 정확히 잡아야 한다.

측정 보고서에는 “무엇을 시작과 끝으로 삼았는가”를 써야 한다.
`request_arrival -> first_byte`, `engine_enqueue -> first_token`, `cuda_event_start -> cuda_event_stop`은 서로 다른 값이다.

## Benchmark workload를 고정한다

AI serving benchmark에서 다음 분포를 적지 않으면 비교가 불공정해진다.

- prompt 길이 분포.
- output 길이 분포.
- 동시 요청 수 또는 도착률.
- streaming 여부.
- prefix cache cold/warm/hit rate.
- 모델 revision과 tokenizer revision.
- batch/prefill/decode scheduler 설정.
- quantization과 dtype.
- warmup 길이.
- timeout과 retry 정책.

평균 prompt 1,000 token이라고만 쓰면 부족하다.
모든 요청이 1,000 token인 경우와 90%는 100 token, 10%는 9,100 token인 경우는 scheduler 압력이 다르다.
tail이 긴 workload에서는 p99와 queue가 크게 달라진다.

## Warmup과 cache 상태

첫 요청은 느릴 수 있다.
모델 weight load, CUDA context 생성, kernel autotune, JIT compile, memory pool 준비, prefix cache miss가 한꺼번에 들어갈 수 있다.
이것을 steady-state 성능과 섞으면 평균이 의미를 잃는다.

측정은 최소한 다음을 분리한다.

- cold start: process 시작 뒤 첫 요청.
- warm model: 모델은 올라갔지만 prefix/data cache가 비어 있음.
- warm cache: 반복 prefix나 dataset shard가 cache에 있음.
- rollout: 새 revision이 들어오며 일부 replica만 warm인 상태.

“cache를 켠 benchmark”는 cache hit rate를 적어야 한다.
hit rate 90% 결과를 miss-heavy production에 적용하면 틀린다.

## p99와 censoring

p99는 꼬리 지연을 보는 데 유용하지만 표본 수와 timeout 정책에 민감하다.
요청 100개에서 p99는 사실상 가장 느린 한두 요청에 가깝다.
요청 10,000개와 요청 100개 p99를 같은 신뢰도로 말하면 안 된다.

timeout으로 30초에 끊긴 요청이 100개 있다면 실제 완료 시간은 30초보다 길 수 있다.
이 표본을 제외하면 p99가 좋아 보인다.
30초로 넣으면 “최소 30초 이상”이라는 정보만 남는다.
그래서 timeout, cancel, drop 개수를 latency와 함께 보고해야 한다.

goodput은 censoring을 드러내는 데 도움이 된다.
SLO를 못 지킨 요청과 실패 요청을 처리량에서 빼기 때문이다.
하지만 goodput 정의도 명시해야 한다.
TTFT만 보는지, ITL도 보는지, E2E와 오류까지 포함하는지 적는다.

## Worked calculation: p99 위치

정렬된 latency 표본이 1,000개라고 하자.
간단한 nearest-rank 방식에서는 p99가 990번째 값이다.

```python
import math
n = 1000
rank = math.ceil(0.99 * n)
print(rank)
```

표본 100개면 99번째 값이다.
표본 20개면 20번째 값이다.
작은 표본의 p99는 불안정하므로 반복 측정과 원시 분포를 함께 남긴다.

## Worked calculation: synthetic cost

가상의 GPU 서버 비용이 시간당 12달러라고 하자.
측정된 goodput이 output token 기준 6,000 token/s이고, SLO 위반 token은 제외했다고 하자.

```python
usd_per_hour = 12
good_tokens_per_second = 6000
tokens_per_hour = good_tokens_per_second * 3600
usd_per_million_tokens = usd_per_hour / (tokens_per_hour / 1_000_000)
print(round(usd_per_million_tokens, 4))
```

결과는 백만 output token당 약 0.5556달러다.
이것은 가상 단가와 가상 goodput만 쓴 산식이다.
실제 비용에는 idle time, replica 여유분, storage, network egress, control plane, engineer time, 실패 재시도, 예약/온디맨드 계약이 들어간다.

## Roofline 감각

roofline은 작업이 compute bound인지 memory bandwidth bound인지 묻는다.
연산량이 1e12 FLOP이고 메모리 이동이 1e12 byte라면 arithmetic intensity는 1 FLOP/byte다.
GPU의 peak가 100 TFLOP/s이고 memory bandwidth가 2 TB/s라면 memory roof는 `1 FLOP/byte × 2 TB/s = 2 TFLOP/s`다.
이 단순 모델에서는 peak compute 100 TFLOP/s보다 memory roof 2 TFLOP/s가 낮다.

```python
intensity = 1       # FLOP per byte
bandwidth_tb_s = 2
compute_peak_tflop_s = 100
memory_roof = intensity * bandwidth_tb_s
attainable = min(memory_roof, compute_peak_tflop_s)
print(attainable)
```

결과는 2 TFLOP/s다.
실제 kernel은 cache, tensor core, layout, overlap, occupancy에 영향을 받는다.
roofline은 원인 후보를 좁히는 모델이지 측정을 대체하지 않는다.

## Amdahl 법칙

요청 시간 1,000 ms 중 GPU decode가 600 ms, queue와 CPU와 network가 400 ms라고 하자.
decode를 2배 빠르게 해도 전체는 `400 + 600/2 = 700 ms`다.

```python
total = 1000
decode = 600
other = total - decode
new_total = other + decode / 2
speedup = total / new_total
print(new_total, round(speedup, 2))
```

전체 속도 향상은 1.43배다.
GPU kernel만 최적화했는데 TTFT가 조금만 좋아졌다면 나머지 400 ms가 어디인지 찾아야 한다.

## Little 법칙

안정 상태에서 평균 동시성 L은 도착률 λ와 평균 체류 시간 W의 곱이다.
초당 20 요청이 들어오고 평균 E2E가 5초면 평균 동시성은 100 요청이다.

```python
arrival_rate = 20
mean_latency = 5
concurrency = arrival_rate * mean_latency
print(concurrency)
```

큐가 안정 상태라는 가정이 중요하다.
도착률이 처리 능력을 넘으면 평균 체류 시간은 계속 커지고 단순 계산이 무너진다.

## 재현 가능한 study 기록

좋은 benchmark 기록에는 다음이 들어간다.

- 목적: 어떤 결정을 위해 측정했는가.
- 하드웨어: GPU, CPU, memory, NIC, storage, topology.
- 소프트웨어: OS, driver, CUDA, framework, serving engine, commit/revision.
- 모델: model revision, tokenizer revision, dtype, quantization, adapter.
- workload: prompt/output 길이 분포, 도착률, concurrency, seed.
- cache: cold/warm, prefix cache 상태, local cache 상태.
- 지표: TTFT, ITL, E2E, throughput, goodput, error, timeout, GPU/memory.
- 방법: warmup, 측정 시간, 반복 횟수, 제외 규칙.
- 원시 결과: summary뿐 아니라 bucket 또는 raw sample 위치.
- 한계: 실제 사용자 traffic과 다른 점.

측정 결과는 그래프보다 먼저 정의가 맞아야 한다.
정의가 다르면 예쁜 그래프도 비교할 수 없다.

## 세 가지 실패 사례

첫 번째 실패는 device-only timing만 보고 출시하는 것이다.
GPU kernel은 20% 빨라졌지만 queue와 tokenization 때문에 사용자 TTFT는 그대로일 수 있다.
출시 판단에는 E2E와 goodput을 포함해야 한다.

두 번째 실패는 timeout 표본을 버리는 것이다.
느린 요청을 제외하면 p99가 좋아 보인다.
하지만 사용자는 실패를 경험했다.
timeout count와 censored latency를 함께 보고한다.

세 번째 실패는 prompt/output 분포를 바꾸고 엔진만 비교하는 것이다.
짧은 output benchmark에서 빠른 설정이 긴 output streaming에서 ITL을 망칠 수 있다.
분포가 다르면 결론도 다르다.

## 오개념 바로잡기

- “utilization이 높으면 효율적이다”: SLO를 못 지키며 바쁠 수 있다.
- “tokens/s 하나면 충분하다”: prompt/output, goodput, latency 경계가 빠져 있다.
- “p99는 표본 수와 무관하다”: 작은 표본에서는 매우 흔들린다.
- “timeout 요청은 실패니까 latency에서 빼도 된다”: censoring을 숨기면 꼬리가 사라진다.
- “GPU memory 여유가 있으면 OOM은 안 난다”: fragmentation, workspace, KV growth가 영향을 준다.
- “벤치마크 1회면 된다”: warmup, cache, background load, clock 상태가 결과를 바꾼다.

## 공식 자료

- CUDA asynchronous execution과 event timing: <https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/asynchronous-execution.html>
- NVIDIA CUDA Best Practices의 timing 설명: <https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/>
- vLLM metrics 정의: <https://docs.vllm.ai/en/latest/design/metrics/>
- Triton metrics 정의: <https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/metrics.html>

## 연습문제

1. 전체 요청 1,000개 중 100개가 timeout으로 30초에 끊겼다. 성공 요청만으로 p99를 내도 되는가?
   답: 안 된다. timeout은 censored sample이다. timeout 수를 따로 보고하고 SLO goodput에도 반영해야 한다.

2. 가상 비용이 시간당 6달러, goodput이 3,000 output token/s다. 백만 token당 비용은?
   답: 시간당 10,800,000 token이므로 `6 / 10.8 = 0.5556달러`다.

3. CPU timer로 CUDA kernel 호출 전후만 쟀더니 0.1 ms가 나왔다. 실제 kernel 시간이 0.1 ms라고 말할 수 있는가?
   답: 없다. CUDA 호출은 비동기일 수 있으므로 synchronization이나 CUDA event 경계를 확인해야 한다.

4. 평균 E2E가 4초이고 초당 12 요청을 안정적으로 받는다. 평균 동시성 추정은?
   답: Little 법칙의 단순 가정에서 `12 × 4 = 48` 요청이다. 안정 상태가 아니라면 적용하지 않는다.
