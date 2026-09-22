# 06. LLM 추론과 KV cache: 한 토큰씩 생성하는 서비스의 속도와 메모리

[학습 안내](README.md) · 이전: [분산 학습과 collective](05-distributed-training-and-collectives.md) · 다음: [서빙·스케줄링·SLO](07-serving-scheduling-and-slo.md)

근거 확인일: **2026-09-22**. 이 장은 Hugging Face Transformers의 cache 문서, vLLM의 PagedAttention·automatic prefix caching·disaggregated prefill 문서, LoRA/PEFT 문서, speculative decoding의 공개 논문을 기준으로 한다. 추론 엔진의 구현은 빠르게 변하므로, 여기서는 개별 명령 대신 prefill, decode, KV cache, batching, memory manager의 원리를 익힌다.

## 1. Autoregressive 생성은 한 토큰씩 이어 붙인다

**Autoregressive LLM**은 앞 token들을 보고 다음 token의 확률분포를 만든다. 완성 문장을 통째로 계산하는 것이 아니라, 다음 token 하나를 고르고 그 token을 다시 입력 맥락에 붙인다.

```text
prompt: "RAID1은"

step 1: model(prompt) → "두"
step 2: model(prompt + "두") → "개"
step 3: model(prompt + "두 개") → "의"
...
```

**Prefill**은 prompt 전체를 한 번 통과시켜 각 layer의 attention 상태를 준비하는 구간이다.
**Decode**는 새 token을 하나씩 생성하며 이전 token들의 상태를 재사용하는 구간이다.
일반적인 decoder-only 생성에서는 prefill의 마지막 위치 logits(정규화 전 후보 점수)에서 첫 출력 token을 고른다. 그 token을 다음 입력으로 넣는 decode 계산이 두 번째 출력 token을 만든다. 첫 출력 전에 prefill과 별도의 추가 decode forward가 언제나 하나씩 필요하다고 계산하지 않는다.

**TTFT(Time To First Token)**는 요청을 보낸 뒤 첫 token이 나오기까지 걸린 시간이다.
queue 대기, tokenization, prefill, scheduler가 영향을 준다.

**ITL(Inter-Token Latency)**은 생성 중 token 사이 간격이다.
decode step의 GPU 시간, KV cache 접근, batch 구성, sampling, network flush가 영향을 준다.

서비스 사용자는 TTFT와 ITL을 다 느낀다. 첫 token이 늦으면 멈춘 것처럼 보이고, 이후 token 간격이 길면 답변이 답답하게 보인다.

## 2. Attention과 KV cache의 이유

Transformer attention은 query, key, value를 사용한다.
새 token을 생성할 때 현재 token의 query는 새로 계산해야 하지만, 이전 token들의 key/value는 이미 계산한 적이 있다.
이를 저장해 두는 것이 **KV cache**다.

Hugging Face Transformers 문서는 cache가 이전 token의 key/value를 저장해 generation을 빠르게 한다고 설명한다. 공식 문서: <https://huggingface.co/docs/transformers/v4.50.0/kv_cache>.

KV cache가 없으면 decode step마다 이전 모든 token의 key/value를 다시 계산해야 한다. KV cache가 있으면 이전 token의 K/V tensor를 읽어 attention에 사용하므로 계산은 줄지만 memory capacity와 bandwidth를 많이 쓴다.

```text
prefill:
  prompt token 0..N-1의 K/V를 계산하고 cache에 저장
  마지막 위치 logits에서 첫 출력 token N을 선택

decode step:
  새 token N의 Q/K/V 계산
  cache에 있던 token 0..N-1의 K/V를 읽음
  attention 결과로 token N+1 확률 계산
  새 token N의 K/V를 cache에 추가
```

KV cache는 학습용 optimizer state가 아니라 요청마다 생기는 추론 중간 상태이며, 요청이 끝나면 보통 해제된다.

## 3. MHA, MQA, GQA와 KV head

**Attention head**는 attention을 여러 부분 공간으로 나눠 계산하는 단위다.
**MHA(Multi-Head Attention)**는 query head 수와 key/value head 수가 보통 같다.
**MQA(Multi-Query Attention)**는 여러 query head가 하나의 key/value head를 공유하는 방식이다.
**GQA(Grouped-Query Attention)**는 query head 여러 개가 key/value head 하나를 공유하되, MQA보다 더 많은 KV head를 둔다.

KV cache 크기는 query head 수보다 **KV head 수**에 직접 비례한다. GQA를 쓰면 같은 hidden size에서도 KV cache가 줄 수 있다.

단순 dense full KV cache 공식:

```text
KV bytes per request
  = layers × context_tokens × kv_heads × head_dim × 2(K and V) × bytes_per_value
```

이 공식은 모든 layer와 모든 context token에 대해 dense K/V를 저장한다고 가정한다. Sliding window, hybrid attention, KV compression, offload를 넣은 모델은 별도 계산이 필요하다.

## 4. KV cache 계산 예제: 512MiB/request

요구 조건을 그대로 넣어 보자.

```text
layers = 32
kv_heads = 8
head_dim = 128
bytes_per_value = 2       # FP16/BF16 저장이라고 가정
context_tokens = 4096
K and V = 2
```

계산:

```text
32 × 4096 × 8 × 128 × 2 × 2 bytes
= 536,870,912 bytes
= 512 MiB
```

MiB 변환:

```text
1 MiB = 1024 × 1024 = 1,048,576 bytes
536,870,912 / 1,048,576 = 512 MiB
```

이 값은 **요청 하나**의 dense full KV cache다. 동시 요청 40개가 모두 4096 token context를 채운다면 KV cache만 단순히 `512MiB × 40 = 20GiB`가 된다.

여기에 model weight, activation workspace, scheduler metadata, fragmentation, CUDA graph capture buffer, communication buffer가 추가된다. 그래서 “가중치가 14GB니까 24GB GPU에 충분하다”는 추론은 긴 context 동시 요청에서 깨질 수 있다.

## 5. Prefill과 decode는 병목이 다르다

Prefill은 prompt token 전체를 병렬로 처리한다.
큰 matrix multiplication 비중이 높아 GPU compute를 잘 채우기 쉽다.
긴 prompt가 많으면 TTFT가 늘어난다.

Decode는 보통 token 하나씩 진행한다.
각 step은 이전 token들의 KV cache를 많이 읽는다.
동시 요청을 묶지 않으면 matrix가 작아 GPU가 비기 쉽다.
긴 context에서는 KV memory bandwidth가 더 중요해진다.

```text
긴 prompt 1개:
  prefill 시간이 큼
  decode는 요청 하나라 GPU를 덜 채울 수 있음

짧은 prompt 100개:
  prefill은 작지만 scheduler와 batching이 중요
  decode를 잘 묶으면 처리량이 올라감
```

서빙 시스템은 두 구간의 SLO를 따로 봐야 한다.
TTFT만 좋아지고 ITL이 나빠질 수도 있고, throughput을 올리다 tail latency가 나빠질 수도 있다.

## 6. Static batching, continuous batching

**Static batching**은 같은 시점에 들어온 요청들을 묶고, batch 전체가 끝날 때까지 같이 움직이는 단순 방식이다.
한 요청이 긴 답변을 만들면 짧은 요청도 빈자리를 낭비한다.

**Continuous batching**은 decode iteration 사이에 끝난 요청을 빼고 새 요청을 넣어 GPU를 더 계속 채우는 방식이다.
Hugging Face Transformers의 continuous batching 문서는 token 예산과 cache 공간에 맞춘 요청 입장을 설명한다. CPU offload를 사용하는 경로에서는 KV block을 내렸다가 다시 올려 재개할 수 있고, 설정과 공간 조건에 따라 상태를 초기화해 다시 계산하는 soft reset/recompute가 필요할 수도 있다. 모든 엔진이 공간 부족을 비용 없이 pause/resume으로 해결하는 것은 아니다. 공식 문서: <https://github.com/huggingface/transformers/blob/main/docs/source/en/continuous_batching_architecture.md>.

Continuous batching의 핵심은 “batch는 요청 목록이 아니라 매 decode iteration마다 바뀌는 작업 집합”이라는 점이다.

```text
iteration 10: request A, B, C decode
iteration 11: A finished, B, C continue, D joins
iteration 12: B, C, D decode
```

좋은 scheduler는 GPU를 채우면서도 오래 기다리는 요청과 짧은 요청을 균형 있게 다룬다.
이 주제는 다음 장의 serving SLO와 이어진다.

## 7. Paged memory와 PagedAttention

KV cache를 요청마다 큰 연속 메모리로 잡으면 fragmentation이 생긴다.
요청마다 길이가 다르고, 생성 중 길이가 계속 늘기 때문이다.

vLLM의 PagedAttention은 KV cache를 fixed-size block으로 나누고, sequence의 logical block을 non-contiguous physical block에 매핑하는 방식으로 설명된다. 공식 블로그와 논문: <https://vllm.ai/blog/2023-06-20-vllm>, <https://arxiv.org/abs/2309.06180>.

운영체제 virtual memory와 비슷한 감각으로 보면 쉽다.

```text
request logical tokens:
  block 0, block 1, block 2

physical KV blocks:
  slot 17, slot 03, slot 44

block table:
  logical 0 → physical 17
  logical 1 → physical 03
  logical 2 → physical 44
```

이 방식은 남는 작은 조각을 줄이고, prefix 공유나 copy-on-write 같은 최적화의 기반이 된다.
하지만 attention kernel이 block table을 따라 KV를 읽어야 하므로, 구현 복잡도와 kernel 지원이 중요하다.

## 8. Prefix cache와 response cache는 다르다

**Prefix cache**는 같은 prompt prefix의 KV cache를 재사용한다.
예를 들어 긴 system prompt와 문서가 같고 마지막 질문만 다르면, 공통 prefix의 prefill을 다시 하지 않을 수 있다.
vLLM Automatic Prefix Caching 문서는 기존 query의 KV cache를 캐시해 같은 prefix를 공유하는 새 query가 공통 부분 계산을 건너뛸 수 있다고 설명한다. 공식 문서: <https://docs.vllm.ai/en/v0.10.1/features/automatic_prefix_caching.html>.

**Response cache**는 완성된 응답 텍스트 자체를 캐시하는 것이다.
같은 질문에 같은 답변을 그대로 돌려주는 HTTP cache 같은 감각에 가깝다.

둘은 다르다.
Prefix cache는 모델 계산 중간 상태를 재사용하지만, 뒤의 sampling은 새로 할 수 있다.
Response cache는 답변을 그대로 재사용하므로 temperature, user context, permission, freshness에 더 민감하다.

개인정보와 권한도 중요하다.
다른 사용자의 private document prefix에서 만든 KV cache를 권한 없이 공유하면 안 된다.
캐시 key는 토큰열뿐 아니라 tenant, model revision, adapter, system prompt, safety policy 같은 경계를 반영해야 한다.

## 9. Chunked prefill과 disaggregated prefill

긴 prefill 하나가 decode batch를 오래 막으면 다른 사용자의 ITL이 튈 수 있다.
**Chunked prefill**은 긴 prompt를 작은 chunk로 나눠 decode 작업 사이에 끼워 넣는 방식이다.
TTFT와 ITL 사이 tradeoff를 조절하는 장치다.

**Disaggregated prefill**은 prefill과 decode를 다른 instance나 GPU pool에 나눠 배치하는 방식이다.
vLLM 문서는 disaggregated prefill이 prefill과 decode phase를 다른 vLLM instance에 두며 TTFT와 ITL을 따로 조정하고 tail ITL을 제어하는 데 도움을 줄 수 있지만, throughput을 개선하는 기능은 아니라고 설명한다. 공식 문서: <https://docs.vllm.ai/en/latest/features/disagg_prefill/>.

비용도 생긴다.
Prefill instance에서 만든 KV cache를 decode instance로 보내야 한다.
이 전송이 PCIe, NVLink, RDMA, CPU memory, network를 지나면 delay와 bandwidth 비용이 붙는다.

```text
prefill GPU:
  prompt → KV cache 생성

transfer:
  KV blocks 이동

decode GPU:
  KV cache를 받아 token 생성 계속
```

따라서 disaggregation은 “무조건 빠름”이 아니라 자원 격리와 tail latency 제어를 위한 설계 선택이다.

## 10. Speculative decoding

**Speculative decoding**은 작은 draft model이 여러 token 후보를 빠르게 제안하고, 큰 target model이 그 후보들을 검증해 받아들이는 방식이다.
후보가 많이 받아들여지면 target model 호출 횟수 대비 여러 token을 전진할 수 있다.

기본 흐름:

```text
draft model: 후보 token 4개 제안
target model: 후보들이 target distribution과 맞는지 검증
accepted prefix: 0~4개 token 채택
rejected 이후: target model 기준으로 보정 sampling
```

원 논문들은 target model의 분포를 보존하도록 acceptance/rejection 절차를 설계한다.
대표 자료: <https://arxiv.org/abs/2211.17192>, <https://arxiv.org/abs/2302.01318>.

주의할 점은 “작은 모델이 낸 token을 그냥 믿는다”가 아니라는 것이다.
정확한 speculative decoding은 target distribution을 유지하기 위한 검증과 보정이 필요하다.
Draft 품질이 낮거나 memory bandwidth가 이미 병목이면 이득이 작을 수 있다.
배치 scheduler, KV cache, sampling 옵션과도 얽힌다.

## 11. Quantization과 LoRA serving

추론에서 quantization은 weight memory와 bandwidth를 줄일 수 있다.
하지만 weight가 INT4라고 KV cache도 자동으로 INT4가 되는 것은 아니다.
KV cache dtype, activation dtype, dequantization kernel, accuracy를 따로 본다.

LoRA serving은 base model 위에 adapter를 적용해 요청별 또는 tenant별 동작을 바꾸는 방식이다.
Hugging Face PEFT 문서는 LoRA adapter 설정과 merge 흐름을 제공한다. 공식 문서: <https://huggingface.co/docs/peft/en/package_reference/lora>.

운영 관점의 질문:

- adapter를 base weight에 merge할 것인가, runtime에 적용할 것인가?
- 한 batch에 서로 다른 adapter 요청을 섞을 수 있는가?
- quantized base와 adapter dtype 조합을 kernel이 지원하는가?
- adapter별 cache key를 분리했는가?
- LoRA rank와 target module이 latency에 미치는 영향을 측정했는가?

같은 모델 이름이라도 base revision, tokenizer, chat template, adapter, quantization scheme이 다르면 cache와 품질을 같은 것으로 취급하면 안 된다.

## 12. 표준 라이브러리로 KV cache 산술 확인

아래 코드는 GPU나 deep learning framework가 필요 없다.
KV cache bytes 공식을 계산한다.

```python
layers = 32
context_tokens = 4096
kv_heads = 8
head_dim = 128
bytes_per_value = 2

kv_bytes = layers * context_tokens * kv_heads * head_dim * 2 * bytes_per_value
mib = kv_bytes / (1024 * 1024)

print(kv_bytes)
print(mib)
print(mib * 40 / 1024)
```

기대 출력:

```text
536870912
512.0
20.0
```

마지막 줄은 같은 조건의 동시 요청 40개가 KV cache만 약 20GiB를 쓴다는 뜻이다.
실제 엔진은 block 크기, 예약률, fragmentation, prefix sharing, page eviction 정책 때문에 이 값과 달라질 수 있다.

## 13. 자주 하는 오해

“LLM은 prompt를 넣으면 한 번에 답 전체를 계산한다”는 틀렸다.
대부분의 autoregressive generation은 token을 순차 생성한다.

“KV cache는 모델 가중치의 일부다”도 틀렸다.
KV cache는 요청별로 생기는 추론 중간 상태다.

“GQA는 항상 품질 손실 없이 KV cache를 줄인다”는 너무 강한 말이다.
모델 아키텍처와 학습 결과에 의존한다.

“PagedAttention은 GPU 메모리를 늘린다”는 틀렸다.
물리 메모리를 늘리는 것이 아니라 할당과 공유를 효율화한다.

“Prefix cache와 response cache는 같다”도 틀렸다.
하나는 중간 KV 상태, 다른 하나는 완성 응답이다.

“Disaggregated prefill은 throughput을 무조건 올린다”는 공식 문서 설명과 맞지 않는다.
주요 목적은 prefill/decode 자원 조정과 tail ITL 제어다.

## 14. 해설 문제

문제 1. L=24, KV heads=8, head_dim=128, context=2048, dtype=2bytes일 때 dense full KV cache는?

해설: `24 × 2048 × 8 × 128 × 2 × 2 = 201,326,592 bytes = 192 MiB`다.

문제 2. 동시 요청 80개가 각각 512MiB KV cache를 쓴다면 KV cache 총량은?

해설: `512MiB × 80 = 40,960MiB = 40GiB`다.

문제 3. `eval()`로 모델을 평가 중인데 KV cache가 계속 커지는 현상은 autograd 때문인가?

해설: 보통 아니다.
KV cache는 autoregressive 추론을 빠르게 하기 위한 요청별 상태다.
Autograd graph와 목적이 다르며, `no_grad()`를 써도 generation 중 KV cache는 필요할 수 있다.

문제 4. Prefix cache를 켜면 같은 문서 기반 질문의 모든 답변이 항상 같아지는가?

해설: 아니다.
공통 prefix의 KV 계산을 재사용하는 것이며, suffix, sampling 설정, random seed, adapter, policy가 다르면 이후 생성은 달라질 수 있다.

[용어 사전](12-glossary.md) · [로컬 실습](11-local-labs-and-research.md) · [다음 장](07-serving-scheduling-and-slo.md)
