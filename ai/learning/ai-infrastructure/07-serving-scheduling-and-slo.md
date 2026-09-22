# 07. 서빙, 스케줄링, SLO

[AI 인프라 학습 목차](README.md) · 이전: [06. LLM 추론과 KV cache](06-llm-inference-and-kv-cache.md) · 다음: [08. 데이터, 모델, 체크포인트](08-data-models-and-checkpoints.md)

이 장은 사용자의 한 문장이 서버에 도착해서 첫 토큰과 마지막 토큰으로 돌아오기까지를 추적한다.
초점은 모델 품질이 아니라 운영 경로다.
인증, 토큰화, 큐, 스케줄러, GPU 실행, 스트리밍, 취소, timeout이 서로 어디에 붙는지 본다.

이 장의 구체적인 예시는 autoregressive LLM의 텍스트 생성 서빙이다. 이미지 분류나 embedding 생성처럼 한 번의 forward로 끝나는 AI 추론도 있다.
여기서 다루는 생성 요청은 prompt 처리(prefill)와 이후 토큰 반복 생성(decode)으로 나뉜다.
decode는 매 토큰마다 GPU 시간을 조금씩 다시 요구한다.
그래서 같은 GPU에 여러 요청을 섞는 스케줄러가 성능과 지연을 크게 좌우한다.

## 핵심 용어

- **서빙(serving):** 학습된 모델을 요청/응답 API로 제공하는 운영 경로다.
- **프론트엔드:** TLS 종료, 인증, rate limit, 요청 ID 부여, tenant 식별 같은 일을 먼저 처리하는 계층이다.
- **토큰화(tokenization):** 문자열을 모델 vocabulary의 정수 ID 배열로 바꾸는 작업이다.
- **prefill:** prompt 문맥을 처리해 KV cache와 출력 후보 점수를 준비하는 단계다. chunked prefill은 이 작업을 나눠 실행한다.
- **decode:** 이미 만든 KV cache를 사용해 다음 토큰을 반복 생성하는 단계다.
- **KV cache:** attention 계산을 반복하지 않기 위해 과거 토큰의 key/value 텐서를 보관한 메모리다.
- **continuous batching:** 이미 실행 중인 batch에 새 요청을 단계적으로 섞어 GPU 빈틈을 줄이는 방식이다.
- **queue:** 지금 당장 실행할 수 없는 요청이 기다리는 장소다.
- **backpressure:** 뒤쪽 자원이 포화되었음을 앞쪽에 알려 더 받지 않거나 느리게 받는 제어다.
- **timeout:** 특정 단계가 약속한 시간 안에 끝나지 않으면 실패로 판정하는 경계다.
- **SLO:** 사용자가 기대하는 서비스 수준 목표다. 예: p99 TTFT 2초 이하.
- **goodput:** 전체 처리량 중 SLO를 만족한 유효 처리량이다.
- **TTFT:** Time To First Token. 요청 도착부터 첫 출력 토큰이 사용자에게 보일 때까지의 시간이다.
- **ITL:** Inter Token Latency. 스트리밍 중 연속 출력 토큰 사이의 간격이다.
- **E2E latency:** 요청 도착부터 최종 응답 종료까지의 전체 시간이다.
- **cancellation:** 사용자가 연결을 끊거나 중단을 요청했을 때 남은 GPU 작업과 큐 상태를 정리하는 처리다.

## 한 요청의 경로

아래 경로는 하나의 가능한 구현이다.
프레임워크마다 함수 이름과 metric 이름은 다르지만, 병목을 찾는 경계는 비슷하다.

1. 클라이언트가 HTTPS 연결로 요청을 보낸다.
2. 프론트엔드가 TLS를 처리하고 인증 토큰을 검증한다.
3. tenant, model, revision, max output token, streaming 여부를 확정한다.
4. 요청 ID와 deadline을 만든다.
5. 문자열 prompt를 byte에서 token ID로 바꾼다.
6. 입력 길이, 출력 길이 상한, 금지 옵션, quota를 확인한다.
7. scheduler queue에 요청을 넣는다.
8. 스케줄러가 prefill 대상과 decode 대상 중 무엇을 GPU에 올릴지 고른다.
9. GPU가 prefill을 실행하고 KV cache block을 할당한다.
10. 일반적인 decoder-only 모델에서는 prefill 마지막 위치의 logits에서 첫 출력 토큰을 선택해 스트리밍한다.
11. 선택한 토큰을 다음 입력으로 넣어 decode를 반복하며 후속 토큰을 생성한다. 전송은 토큰 하나씩 또는 작은 묶음일 수 있다.
12. stop token, max token, client cancel, timeout 중 하나가 종료 조건이 된다.
13. KV cache block을 반환하고 metric을 기록한다.
14. 로그에는 prompt 원문 대신 정책에 맞는 길이, hash, request ID만 남길 수 있다.

서빙 문제를 볼 때 “GPU가 느리다”로 시작하면 너무 넓다.
인증에서 밀렸는지, tokenization이 CPU에서 막혔는지, queue가 긴지, prefill이 긴지, decode가 긴지, 네트워크 streaming이 막혔는지 나눈다.

## TTFT, ITL, E2E의 경계

TTFT는 보통 프론트엔드가 요청을 받은 시각에서 첫 응답 조각이 나간 시각까지다.
이 안에는 인증, tokenization, queue wait, prefill, 첫 출력 토큰 선택·직렬화가 들어갈 수 있다. 첫 토큰에 필요한 모델 계산을 prefill과 decode 양쪽에 중복해서 더하지 않는다.
엔진 내부 metric은 “엔진 도착”을 시작으로 삼을 수 있으므로 외부 gateway metric과 숫자가 다를 수 있다.

ITL은 스트리밍된 출력 토큰 사이의 벽시계 간격이다.
첫 토큰 이전 시간은 ITL에 넣지 않는다.
출력이 토큰 1개뿐이면 “토큰 사이 간격”이 없으므로 ITL이 비어 있거나 null이 될 수 있다.
실제 계측에서는 token 간격과 streamed output event/chunk 간격이 다를 수 있다. 한 번에 여러 token을 전송한다면 전송 간격을 token당 시간과 그대로 비교할 수 없다. TPOT(Time Per Output Token)를 `(마지막 token 시각 - 첫 token 시각) / (출력 token 수 - 1)`로 정의한 도구라면 분모와 token 집계 기준을 함께 기록한다. vLLM의 metric 이름·집계는 버전에 따라 달라지므로 [metrics 문서](https://docs.vllm.ai/en/latest/design/metrics/)와 사용하는 엔진의 정의를 대조한다.

E2E latency는 마지막 토큰 또는 종료 응답이 나갈 때까지다.
출력 길이가 길면 E2E는 길어지는 것이 정상이다.
그래서 서로 다른 workload를 비교할 때 prompt 길이와 output 길이 분포를 함께 적어야 한다.

## Queue는 숨겨진 응답 시간이다

GPU 실행 시간이 200 ms여도 queue에서 2초 기다리면 사용자는 2.2초를 본다.
Triton Inference Server는 request time, queue time, compute input, compute infer, compute output 같은 latency metric을 구분한다.
이 구분은 “모델이 느린가, 대기열이 긴가”를 나누는 데 중요하다.

큐는 무한히 길면 안 된다.
큐가 길어질수록 이미 SLO를 넘을 요청이 계속 쌓인다.
그런 요청을 뒤늦게 처리하면 GPU 시간은 쓰지만 goodput에는 기여하지 못한다.

bounded queue는 큐 길이 또는 큐 대기 시간을 제한한다.
제한에 걸리면 429, 503, admission 실패 같은 명시적 실패를 반환할 수 있다.
실패 응답도 설계의 일부다.
무작정 받아서 모두 느리게 만드는 것보다, 빨리 거절하고 재시도 위치를 명확히 하는 편이 전체 시스템을 안정시킬 수 있다.

## Timeout과 재시도

timeout은 한 숫자가 아니다.
적어도 다음 경계를 나누어 생각한다.

- 연결 timeout: 서버에 닿지 못했다.
- 인증 timeout: 인증 서비스나 key 조회가 지연됐다.
- queue timeout: 실행 기회를 얻기 전에 deadline을 넘었다.
- first-token timeout: TTFT 목표를 넘었다.
- stream idle timeout: 토큰 사이 간격이 너무 길다.
- total timeout: 전체 요청 시간이 너무 길다.

재시도는 항상 중복 가능성을 만든다.
생성 요청은 같은 seed와 설정을 고정하지 않으면 재시도 결과가 달라질 수 있다.
스트리밍 중간에 끊긴 요청을 재시도하면 사용자는 앞부분을 두 번 받을 수도 있다.
그러므로 client request ID, idempotency 정책, “부분 응답 이후 재시도 금지” 같은 규칙을 문서화해야 한다.

## Continuous batching의 이득과 대가

단순 batching은 batch가 찰 때까지 기다린 뒤 한 번에 실행한다.
continuous batching은 매 decode step마다 끝난 요청을 빼고 새 요청을 넣을 수 있다.
짧은 요청과 긴 요청이 섞여도 GPU를 더 바쁘게 유지할 수 있다.

대가는 스케줄러가 복잡해진다는 점이다.
prefill은 prompt 길이에 따라 큰 덩어리 계산을 만든다.
decode는 많은 요청이 작은 반복 계산을 만든다.
prefill을 너무 많이 넣으면 새 요청의 TTFT는 좋아질 수 있지만 기존 streaming 요청의 ITL이 나빠질 수 있다.
decode를 너무 우선하면 이미 들어온 긴 prompt 요청의 첫 토큰이 늦어진다.

간단한 모델을 보자.

```python
# Python 표준 라이브러리만 사용한다.
# 가정: GPU가 초당 decode token 800개를 처리하고, SLO상 평균 출력은 요청당 80 token이다.
# queue와 prefill 비용은 일부러 제외한 상한 계산이다.

decode_tokens_per_second = 800
tokens_per_request = 80
max_requests_per_second = decode_tokens_per_second / tokens_per_request
print(max_requests_per_second)
```

결과는 10 requests/s다.
하지만 이 값은 순수 decode 상한이다.
prefill, queue, sampling, 네트워크, padding, cache miss, 긴 prompt 분포가 들어가면 실제 허용률은 더 낮다.
capacity 숫자는 “이보다 많이 받을 수 있다”가 아니라 “이 단순 가정에서는 이보다 높기 어렵다”로 읽는다.

## Worked calculation: goodput

1분 동안 요청 1,200개를 받았다고 하자.
그중 1,050개가 성공 응답을 받았다.
SLO는 TTFT 2초 이하, E2E 20초 이하, 오류 없음이다.
성공 1,050개 중 두 조건을 모두 만족한 요청은 900개다.

```python
requests = 1200
ok = 1050
slo_ok = 900
throughput = ok / 60
goodput = slo_ok / 60
goodput_ratio = slo_ok / requests
print(round(throughput, 2), round(goodput, 2), round(goodput_ratio, 3))
```

throughput은 17.5 req/s다.
goodput은 15 req/s다.
전체 요청 기준 goodput ratio는 0.75다.
실패한 요청 150개와, 성공했지만 지연 SLO를 넘긴 요청 150개는 goodput에서 빠진다. 여기서 throughput은 성공 응답 기준으로 정의했으며 전체 입장률 20 req/s와 구별한다.

## Prompt privacy와 tenant cache 경계

KV cache와 prefix cache는 성능을 크게 바꿀 수 있다.
같은 system prompt나 긴 공통 prefix를 재사용하면 TTFT가 줄어든다.
그러나 cache는 tenant 경계를 건드린다.

안전한 기본 원칙은 다음과 같다.

- cache key에는 model revision, tokenizer revision, adapter, decoding 옵션 중 cache에 영향을 주는 값을 포함한다.
- 서로 다른 tenant의 prompt 원문을 같은 cache entry로 공유하지 않는다.
- 공유 가능한 prefix라도 정책상 공개된 공통 prefix인지 확인한다.
- prompt 원문을 metric label에 넣지 않는다.
- debug log는 보존 기간과 접근 권한을 제한한다.

“hash가 같으니 안전하다”는 충분한 설명이 아니다.
hash가 prompt 존재 여부를 드러낼 수도 있고, 짧은 prompt는 추측될 수 있다.
운영 문서에는 cache hit rate와 함께 cache 격리 단위를 적는다.

## Streaming과 cancel

스트리밍 응답은 첫 토큰을 빨리 보여준다.
하지만 서버는 사용자가 창을 닫은 사실을 즉시 알지 못할 수 있다.
TCP 연결 상태, HTTP/2 stream reset, proxy buffering, client library 동작에 따라 cancel 전파가 달라진다.

cancel이 들어오면 세 가지를 정리해야 한다.

- queue에 있던 요청은 실행 전에 제거한다.
- 실행 중 요청은 다음 안전한 scheduler 지점에서 중단 표시를 확인한다.
- 할당한 KV cache와 per-request 상태를 반환한다.

GPU kernel 하나가 이미 제출되었다면 즉시 사라지는 것이 아니다.
취소는 대개 “다음 반복부터 더 넣지 않는다”에 가깝다.
그래서 cancel metric은 “사용자가 취소했다”와 “GPU 시간이 얼마나 더 쓰였나”를 함께 봐야 한다.

## Rollout과 model readiness

모델 배포에서 준비 완료는 Pod가 Running이라는 뜻만으로 부족하다.
다음이 준비되어야 요청을 받는다.

- 모델 weight가 로컬 또는 원격 저장소에서 확인되었다.
- tokenizer, config, adapter, generation template이 같은 revision으로 묶였다.
- GPU 메모리에 필요한 graph, cache, workspace가 준비되었다.
- warmup 요청이 성공했고 첫 요청의 cold-start 비용을 분리했다.
- readiness가 false인 동안 프론트엔드가 트래픽을 보내지 않는다.

rollout은 old model과 new model이 동시에 트래픽을 받을 수 있다.
이때 metric label에는 model name뿐 아니라 revision이 필요하다.
그렇지 않으면 느린 새 revision을 old revision 평균 속에 숨긴다.

## 관측 위치

서빙 경로에는 최소 네 종류의 시계가 있다.

- client 시계: 사용자가 본 전체 지연.
- gateway 시계: 서버 입구에서 본 인증·queue 전 전체 지연.
- engine 시계: scheduler와 GPU 실행 기준의 지연.
- device 시계: GPU kernel 또는 CUDA event 기준의 시간.

이 시계들은 같은 질문에 답하지 않는다.
client p99가 나빠졌는데 device 시간은 그대로라면 queue, network, proxy, streaming flush를 의심한다.
device 시간이 나빠졌다면 batch shape, prompt 길이, cache miss, kernel 선택, clock throttling을 본다.

## 오개념 바로잡기

- “GPU utilization 100%면 좋은 상태다”: SLO를 놓치며 바쁜 상태일 수 있다.
- “처리량이 높으면 사용자는 빠르다”: queue가 길면 throughput은 높아도 TTFT가 나쁠 수 있다.
- “batch를 키우면 항상 좋다”: ITL과 TTFT를 망칠 수 있다.
- “timeout은 실패를 줄인다”: timeout은 늦은 일을 실패로 분류해서 자원을 보호하는 장치다.
- “streaming이면 E2E가 중요하지 않다”: 긴 응답의 총 시간과 중간 멈춤도 사용자 경험이다.
- “cancel은 GPU 작업을 즉시 없앤다”: 이미 제출된 작업은 scheduler 경계에서야 줄어들 수 있다.

## 공식 자료

- Kubernetes의 GPU scheduling은 device plugin 기반 GPU 노출 방식을 설명한다: <https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/>
- Triton Inference Server metrics는 request, queue, compute 계층 지연을 나누어 보여준다: <https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/metrics.html>
- vLLM metrics는 TTFT, ITL, per-request latency 경계를 문서화한다: <https://docs.vllm.ai/en/latest/design/metrics/>
- Kubernetes DRA는 장치 요청과 할당을 구조화하는 새 경로다: <https://kubernetes.io/docs/concepts/resource-management/dynamic-resource-allocation/>

## 연습문제

1. 요청 600개 중 570개가 성공했고, 그중 510개만 TTFT와 E2E SLO를 만족했다. 5분 구간 goodput은?
   답: `510 / 300 = 1.7 req/s`다. 성공 처리량은 `570 / 300 = 1.9 req/s`지만 SLO 위반 60개는 goodput에서 빠진다.

2. TTFT p99가 나빠졌는데 GPU kernel 시간 p50/p99가 그대로다. 먼저 볼 지표 두 개는?
   답: queue wait와 tokenization/front-end time이다. device 시간이 그대로면 GPU 계산 전 대기나 CPU/네트워크 경로가 원인일 수 있다.

3. tenant A와 tenant B가 같은 prompt prefix를 보냈다. prefix cache를 공유해도 된다고 바로 말할 수 있는가?
   답: 아니다. cache key와 접근 정책, tenant 격리, prompt 존재 여부 노출 위험을 먼저 정해야 한다.

4. batch를 키웠더니 tokens/s는 30% 올랐지만 ITL p99가 2배가 되었다. 좋은 변경인가?
   답: SLO에 달려 있다. interactive streaming 서비스라면 goodput이 줄었을 수 있으므로 TTFT, ITL, E2E 기준으로 다시 판정한다.
