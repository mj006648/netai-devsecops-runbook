# 00. AI 워크로드와 모델: 무엇을 계산하고 무엇을 운영하는가

[AI 인프라 교재 홈](README.md) · [다음: 텐서·자동미분·Transformer](01-tensors-autograd-and-transformers.md) · [통합 학습 안내](../../../learning/README.md) · [하드웨어 GPU 장](../../../hardware/learning/server-hardware/05-gpu-npu-execution.md)

이 장은 AI를 처음 배우는 독자가 “모델을 돌린다”는 말을 더 작게 나누어 볼 수 있게 한다.
모델은 파일 하나이기도 하고, 함수이기도 하고, 서비스의 일부이기도 하다.
훈련은 모델의 값을 바꾸는 작업이고, 추론은 이미 정한 값을 사용해 답을 계산하는 작업이다.
둘 다 전기 신호, 메모리, 커널, 네트워크, 파일 저장 위에서 실행된다.

이 교재의 관심사는 “AI가 똑똑한가”보다 “AI 작업이 컴퓨터에서 어떤 자원을 요구하는가”다.
정확도, 비용, 지연, 처리량, 재현성, 보안은 모두 인프라 선택에 영향을 준다.
그래서 모델 이름만 보지 않고 입력의 모양, 파라미터 수, 데이터 흐름, 실패 조건을 함께 본다.

## 먼저 구별할 단어

AI는 사람이 지능적이라고 부르는 행동을 컴퓨터가 하게 만드는 넓은 분야다.
머신러닝은 규칙을 사람이 모두 쓰지 않고 데이터에서 패턴을 배우게 하는 방법이다.
딥러닝은 여러 층의 신경망을 사용해 표현을 배우는 머신러닝의 한 갈래다.
LLM은 대규모 언어 모델이며, 텍스트 토큰의 다음 분포를 예측하는 방식으로 많이 훈련된다.

모델은 입력을 출력으로 바꾸는 계산 규칙과 그 안의 숫자 묶음이다.
파라미터는 훈련으로 바뀌는 숫자다.
가중치와 bias가 대표적이다.
하이퍼파라미터는 사람이 정하거나 탐색하는 설정이다.
학습률, batch size, layer 수, context 길이가 예다.

데이터셋은 훈련·검증·평가에 쓰는 예제 모음이다.
task는 풀려는 문제다.
분류, 번역, 요약, 검색, 다음 토큰 예측, 이미지 생성, 추천이 서로 다른 task가 될 수 있다.
metric은 품질을 숫자로 보는 규칙이다.
정답률, loss, BLEU, ROUGE, latency, cost per request처럼 목적에 따라 달라진다.

워크로드는 컴퓨터가 실제로 처리하는 일의 모양이다.
AI 워크로드는 모델 계산만 뜻하지 않는다.
데이터 읽기, 전처리, 토큰화, batch 만들기, GPU 전송, checkpoint 저장, 로그 수집, 네트워크 통신도 포함한다.

## 왜 이 구분이 인프라에서 중요한가

파라미터가 많으면 보통 저장 용량과 메모리 요구가 커진다.
하지만 파라미터 수만으로 속도와 비용을 말할 수는 없다.
입력 길이, batch 크기, 정밀도, 커널 구현, 캐시 재사용, 통신 방식이 함께 작동한다.

훈련은 forward 계산 뒤 backward 계산으로 gradient를 만들고 optimizer가 파라미터를 갱신한다.
그래서 가중치뿐 아니라 gradient, optimizer 상태, activation 저장 공간이 필요하다.
[03장](03-memory-precision-and-capacity.md)에서 이 메모리를 따로 계산한다.

추론은 보통 파라미터를 바꾸지 않는다.
하지만 LLM 추론은 prompt와 생성 토큰의 KV cache를 계속 저장한다.
그래서 “훈련보다 추론이 무조건 가볍다”는 말은 조건부다.
짧은 batch의 단일 요청과 긴 context의 대량 serving은 전혀 다른 워크로드다.

품질도 인프라와 분리되지 않는다.
너무 작은 batch는 GPU를 놀릴 수 있고, 너무 큰 batch는 지연이나 메모리 부족을 만든다.
낮은 정밀도는 메모리를 줄일 수 있지만 모델·연산·하드웨어 지원에 따라 품질과 속도 영향이 달라진다.
모든 수치는 버전과 설정을 함께 기록해야 한다.

## 한 요청을 끝까지 따라가기

사용자가 “서울에서 부산까지 KTX 시간 알려줘”라고 묻는 LLM 서비스를 상상하자.
이 예시는 제품 기본값이나 성능 주장이 아니다.
경로를 보기 위한 작은 지도다.

1. 클라이언트가 문자열을 보낸다.
2. 서버가 요청을 인증하고 queue에 넣는다.
3. tokenizer가 문자열을 token id 배열로 바꾼다.
4. runtime이 같은 모델·비슷한 길이의 요청을 batch로 묶을 수 있다.
5. CPU 메모리의 token id와 metadata가 GPU가 읽을 수 있는 버퍼로 준비된다.
6. GPU에서 embedding lookup, attention, MLP 같은 연산이 실행된다.
7. 다음 token의 확률 분포에서 하나 이상의 token이 선택된다.
8. 생성이 끝날 때까지 4-7단계가 반복된다.
9. token id가 다시 문자열로 바뀌고 응답이 전송된다.

여기서 모델 파일만 빠르면 충분하지 않다.
tokenizer가 CPU에서 병목이 될 수 있다.
batch queue가 너무 오래 기다리면 p99 지연이 커진다.
KV cache가 부족하면 요청을 거절하거나 더 작은 batch로 낮춰야 한다.
네트워크 응답이 streaming이면 사용자 체감 시간은 첫 token 시간과 전체 완료 시간이 모두 중요하다.

## 작은 계산: 요청 하나가 쓰는 token 처리량

가정한다.
입력 prompt가 800 tokens이고 출력이 200 tokens이다.
한 요청은 총 1,000 tokens를 모델 경로에 태운다.
서버가 초당 20 requests를 처리한다면 단순 token 처리량은 다음과 같다.

```text
총 token/s = 20 requests/s × 1,000 tokens/request
           = 20,000 tokens/s
```

이 값은 전체 시스템 처리량 모델의 한 조각이다.
prefill은 prompt 800 tokens를 한 번에 처리하는 성격이 강하고, decode는 새 token을 하나씩 생성한다.
따라서 같은 1,000 tokens라도 연산 모양이 같지 않다.
LLM serving에서는 prefill 처리량과 decode 지연을 따로 본다.

이번에는 비용을 단순 계산한다.
GPU 서버 1대 비용을 시간당 4달러라고 가정한다.
이 서버가 안정적으로 20 requests/s를 처리하고 하루 24시간 동작하면 하루 요청 수는 다음과 같다.

```text
20 requests/s × 86,400 s/day = 1,728,000 requests/day
4 dollar/hour × 24 hour/day = 96 dollar/day
96 dollar/day ÷ 1,728,000 requests/day ≈ 0.0000556 dollar/request
```

이 계산은 전기료, idle 시간, 장애 여유, CPU 서버, 네트워크, 저장, 운영 인건비, 품질 재시도 비용을 제외했다.
따라서 가격표가 아니라 산술 모델이다.
모델을 세울 때 무엇을 뺐는지 적어야 한다.

## 훈련 파이프라인의 큰 단계

훈련 데이터는 원본 그대로 들어가지 않는다.
대개 수집, 정제, 중복 제거, 필터링, 샘플링, 토큰화, shard 작성, 로딩 단계를 거친다.
각 단계는 파일 포맷, 압축, 네트워크, CPU, 저장장치의 영향을 받는다.

훈련 실행은 반복 구조다.
batch를 읽고, forward를 계산하고, loss를 만들고, backward로 gradient를 계산한다.
optimizer가 파라미터를 갱신하고, 주기적으로 checkpoint를 저장한다.
분산 훈련이면 GPU 사이의 gradient나 activation 통신이 추가된다.
[05장](05-distributed-training-and-collectives.md)에서 all-reduce 같은 collective를 다룬다.

checkpoint는 “모델 파일”보다 넓을 수 있다.
가중치만 저장하면 추론에는 충분할 수 있다.
훈련을 같은 상태에서 재개하려면 optimizer 상태, scheduler 상태, random seed, dataloader 위치가 필요할 수 있다.
어디까지 저장했는지 모르면 재현성을 주장하기 어렵다.

## 추론 파이프라인의 큰 단계

추론은 모델 로드, warmup, 요청 수신, 전처리, 스케줄링, 실행, 후처리, 응답으로 나뉜다.
서빙 시스템은 단일 함수 호출이 아니라 queue와 resource manager다.
같은 GPU에 여러 요청을 섞어 throughput을 올리려 하지만, 기다리는 시간이 늘면 지연 목표를 놓칠 수 있다.

LLM 추론에서는 prefill과 decode를 구분한다.
prefill은 prompt 전체를 읽어 내부 상태를 만든다.
decode는 방금 만든 token을 다시 넣어 다음 token을 만든다.
decode 중에는 과거 token의 key/value를 KV cache로 보관해 재계산을 줄인다.
KV cache 크기는 [03장](03-memory-precision-and-capacity.md)과 [06장](06-llm-inference-and-kv-cache.md)에서 계산한다.

## 역사: 왜 지금의 AI 인프라가 이런 모양인가

신경망은 오래된 아이디어지만, 현재의 인프라 문제는 데이터·연산·소프트웨어 생태계가 함께 커지며 생겼다.
1986년 Rumelhart, Hinton, Williams의 back-propagation 논문은 다층 표현 학습을 널리 설명한 고전이다.
2012년 AlexNet은 ImageNet 분류에서 GPU 기반 convolutional network가 큰 효과를 낼 수 있음을 보였다.
2017년 Transformer 논문은 recurrence나 convolution 없이 attention 중심 구조로 기계 번역 성능을 보였다.

이 흐름을 “GPU가 있으니 AI가 됐다”로 줄이면 놓치는 것이 많다.
데이터셋, 손실함수, optimizer, 병렬화, 자동미분, 라이브러리, 분산 파일 시스템, checkpoint 운영이 함께 필요했다.
하드웨어는 가능성을 열고, 소프트웨어와 데이터 파이프라인은 그것을 반복 가능한 작업으로 만든다.

## 인프라 관점의 품질 질문

정확한 답을 내는가?
일관되게 같은 입력을 처리하는가?
느린 요청의 꼬리는 어느 정도인가?
장애 뒤 checkpoint에서 재개할 수 있는가?
비용이 예산 안에 들어오는가?
데이터와 모델 버전을 추적할 수 있는가?

AI 서비스에서 “성공”은 HTTP 200만이 아니다.
답의 품질, 생성 중단 여부, 안전 정책 적용, 지연 목표, 로그 기록, 비용 예산이 모두 계약이 될 수 있다.
어떤 계약을 확인했는지 명시해야 나중에 같은 결과를 비교할 수 있다.

## 흔한 오개념

- “AI 모델 = LLM”은 아니다. 이미지, 음성, 추천, 표 데이터 모델도 AI 모델이다.
- “파라미터 수가 크면 항상 더 좋다”는 아니다. 데이터, task, 평가 기준, 배포 제약이 함께 결정한다.
- “훈련은 GPU만 빠르면 된다”는 아니다. 입력 파이프라인과 checkpoint 저장이 전체 시간을 제한할 수 있다.
- “추론은 훈련보다 메모리가 항상 작다”는 아니다. 긴 context와 많은 동시 요청의 KV cache가 커질 수 있다.
- “benchmark 수치 하나면 충분하다”는 아니다. batch, sequence length, precision, hardware, software version이 있어야 해석된다.

## 연습 문제와 해설

문제 1.
모델 A는 7B parameters이고 모델 B는 13B parameters다.
두 모델 중 어느 쪽 serving 비용이 항상 높은가?

해설.
항상 말할 수 없다.
파라미터 메모리는 B가 더 클 가능성이 높지만, 지연과 비용은 정밀도, batch, context 길이, 커널, KV cache, 목표 품질, GPU 활용률에 따라 달라진다.
비교하려면 같은 task, 같은 품질 기준, 같은 입력 분포, 같은 하드웨어·소프트웨어 조건을 적어야 한다.

문제 2.
prompt 2,000 tokens, output 500 tokens인 요청이 초당 8개 들어온다.
단순 token 처리량은 얼마인가?

해설.
요청당 총 token은 2,500 tokens다.
`8 × 2,500 = 20,000 tokens/s`다.
단, prefill 16,000 tokens/s와 decode 4,000 tokens/s는 실행 성격이 다르므로 하나의 평균만으로 GPU 병목을 판단하지 않는다.

문제 3.
checkpoint에 가중치만 저장했다.
훈련을 정확히 같은 상태에서 이어갈 수 있다고 말해도 되는가?

해설.
보통 충분하지 않다.
optimizer 상태, 학습률 스케줄러, random seed, 데이터 순서, 누적 step, 분산 sharding 정보가 필요할 수 있다.
“추론용 모델을 저장했다”와 “훈련 재개 상태를 저장했다”를 구별해야 한다.

문제 4.
AI 서비스에서 p50 latency는 목표 안에 있지만 p99가 크게 튄다.
가능한 원인 두 가지와 확인 방법을 말하라.

해설.
첫째, batch queue에서 일부 요청이 오래 기다릴 수 있다.
queue wait 시간을 별도 metric으로 본다.
둘째, 긴 prompt나 큰 output 요청이 섞여 GPU 실행 시간을 늘릴 수 있다.
요청별 input/output token 수와 실행 시간을 함께 기록한다.

## 공식 자료와 원전

- PyTorch autograd 개요: https://docs.pytorch.org/tutorials/beginner/basics/autograd_tutorial.html
- PyTorch CUDA memory semantics: https://docs.pytorch.org/docs/stable/notes/cuda.html
- NVIDIA CUDA Programming Guide, asynchronous execution: https://docs.nvidia.com/cuda/cuda-c-programming-guide/02-basics/asynchronous-execution.html
- Rumelhart, Hinton, Williams, 1986, back-propagation: https://www.nature.com/articles/323533a0
- Krizhevsky, Sutskever, Hinton, ImageNet classification with deep convolutional neural networks: https://proceedings.neurips.cc/paper/2012/hash/c399862d3b9d6b76c8436e924a68c45b-Abstract.html
- Vaswani et al., Attention Is All You Need: https://arxiv.org/abs/1706.03762

공식 문서와 논문은 개념의 기준점이다.
제품 기본값, 특정 라이브러리 최적화, GPU 세대별 성능은 시간이 지나며 바뀐다.
이 장의 계산은 구조를 이해하기 위한 모델이며 benchmark 증거가 아니다.
