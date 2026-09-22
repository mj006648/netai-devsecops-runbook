# 11. GPU 없이 확인하는 AI 인프라 실습과 연구 과제

[학습 안내](README.md) · 이전: [관측·벤치마크·비용](10-observation-benchmarking-and-cost.md) · 다음: [용어 사전](12-glossary.md)

이 장은 **표준 Python만으로 실행하는 작은 교육 모형**이다. 계산과 상태의 의미를 검증한다. GPU kernel, 실제 모델 품질, CUDA stream, NCCL 통신, vLLM 스케줄러의 실성능을 검증하는 실습은 아니다.

각 Python 블록을 별도 파일로 저장해 실행하거나, [예제 검사 도구](examples/README.md)로 교재의 모든 Python 블록을 실행할 수 있다. 외부 패키지·모델·데이터 다운로드가 없고, 마지막 실습은 자신이 만든 임시 디렉터리만 사용한다. 먼저 예상 결과를 적은 뒤 실행한다.

## 실습 1. 숫자 하나를 학습시키고 미분을 대조한다

입력 x를 두 배로 만드는 데이터가 있다. 모델은 `예측 = w × x`이며 w가 유일한 파라미터다. 손실은 각 예제의 `(예측 - 정답)² / 2`를 평균 낸 값이다. 1/2는 미분식의 2를 없애기 위한 선택이고, 손실의 정의 자체를 명시하는 것이 중요하다.

`w = 0`이면 예측은 모두 0이다. x가 1·2일 때 정답은 2·4이므로 평균 손실은 5, gradient는 -5다. 학습률 0.1로 한 번 갱신하면 `w = 0 - 0.1 × (-5) = 0.5`다.

```python
from math import isclose

samples = [(1.0, 2.0), (2.0, 4.0)]

def loss(w):
    return sum((w * x - y) ** 2 / 2 for x, y in samples) / len(samples)

def gradient(w):
    return sum((w * x - y) * x for x, y in samples) / len(samples)

w = 0.0
assert loss(w) == 5.0
assert gradient(w) == -5.0
w -= 0.1 * gradient(w)
assert w == 0.5
assert loss(w) == 2.8125

probe = 0.3
epsilon = 1e-5
finite_difference = (loss(probe + epsilon) - loss(probe - epsilon)) / (2 * epsilon)
assert isclose(gradient(probe), finite_difference, rel_tol=1e-7)

w = 0.0
for _ in range(40):
    w -= 0.1 * gradient(w)
assert loss(w) < 1e-8
print("weight", w, "loss", loss(w), "gradient check", finite_difference)
```

**해석:** 숫자를 바꾸어 손실을 재는 유한 차분은 여기서 미분식을 검산하는 도구다. PyTorch의 일반적인 autograd가 모든 가중치를 하나씩 흔들어 계산한다는 뜻은 아니다. 자동 미분은 연산의 미분 규칙을 연결한다. [PyTorch autograd 입문](https://docs.pytorch.org/tutorials/beginner/basics/autogradqs_tutorial.html)

**추가 문제:** 학습률을 1.0으로 바꾸면 왜 이 예제에서 발산하는가?

**해설:** gradient는 `2.5(w - 2)`다. 정답으로부터의 오차가 매번 `1 - 학습률 × 2.5`배가 되므로 학습률 1에서는 -1.5배가 된다. 부호가 뒤집히며 오차 크기가 커진다. 다른 모델에 그대로 적용할 보편적인 학습률 기준은 아니다.

## 실습 2. 크기가 다른 배치의 평균을 다시 평균 내면?

같은 시점의 모델로 세 예제를 계산하되 한 rank는 두 예제, 다른 rank는 한 예제를 맡았다고 하자. rank는 여기서는 역할을 나눈 목록 이름이며 실제 분산 프로세스를 띄우지 않는다.

```python
from math import isclose

w = 1.0
rank_samples = [[(1.0, 2.0), (2.0, 4.0)], [(3.0, 6.0)]]
local_sums = [
    sum((w * x - y) * x for x, y in samples)
    for samples in rank_samples
]
counts = [len(samples) for samples in rank_samples]
local_means = [total / count for total, count in zip(local_sums, counts)]
naive_mean = sum(local_means) / len(local_means)
weighted_mean = sum(local_sums) / sum(counts)
all_samples = [sample for group in rank_samples for sample in group]
reference = sum((w * x - y) * x for x, y in all_samples) / len(all_samples)
assert isclose(weighted_mean, reference)
assert not isclose(naive_mean, reference)
assert naive_mean == -5.75
assert isclose(reference, -14 / 3)
print("rank means", local_means, "naive", naive_mean, "correct", weighted_mean)
```

**해석:** 같은 수의 예제를 가진 rank 평균과 서로 다른 수의 예제를 가진 rank 평균은 같은 문제가 아니다. token별 손실에서는 padding·mask 뒤의 유효 token 수를 분모로 삼는 경우도 있다. 실제 DDP에서는 gradient의 축약·평균 규칙과 손실 정규화를 함께 맞춰야 한다. 이 실습은 DDP 구현을 호출하지 않는다.

**추가 문제:** 첫 rank의 두 예제를 하나의 평균값으로 저장하고 그 평균만 남겼다. 올바른 전체 평균을 복구하려면 어떤 정보가 더 필요한가?

**해설:** 각 평균에 대응하는 표본 수 또는 사용한 가중치 총량이 필요하다. 평균 둘만으로는 원래 표본 수 비율을 알 수 없다.

## 실습 3. GQA의 KV cache와 block 반올림

다음은 모든 층에서 전체 과거 문맥의 K·V를 같은 dtype으로 저장하는 가상 decoder다. sliding window, 혼합 attention, 압축, KV 복제·분할, prefix 공유를 제외한다.

`2 × 층 수 × KV head 수 × head 차원 × 저장 token 수 × 값당 byte`가 요청 하나의 논리적 KV 크기다. 앞의 2는 K와 V 두 배열이다. 여기서 query head 수가 아니라 **KV head 수**를 쓴다.

```python
from math import ceil

gib = 2 ** 30
mib = 2 ** 20
layers, kv_heads, head_dim, tokens, value_bytes = 32, 8, 128, 4096, 2
per_request = 2 * layers * kv_heads * head_dim * tokens * value_bytes
assert per_request == 512 * mib
mha_request = 2 * layers * 32 * head_dim * tokens * value_bytes
assert mha_request == 2 * gib

device = 24 * gib
weights = 8_000_000_000 * 2
other_reserved = 4 * gib  # 가정: 이 모형이 따로 잡아 둔 비-KV 예산
available = device - weights - other_reserved
capacity = max(0, available // per_request)
assert capacity == 10
assert weights + other_reserved + capacity * per_request <= device
assert weights + other_reserved + (capacity + 1) * per_request > device

lengths = [17, 31]
block_size = 16
slots = sum(ceil(length / block_size) * block_size for length in lengths)
assert slots == 64
assert slots - sum(lengths) == 16
print("KV MiB", per_request / mib, "arithmetic capacity", capacity)
print("allocated token slots", slots, "unused slots", slots - sum(lengths))
```

**해석:** 이 10은 정해진 가정 아래의 용량 계산이다. 실제 엔진은 KV pool, 예약 정책, workspace와 피크 activation, 그래프 캡처, 문맥 성장, 안전 여유 때문에 다른 제한을 가진다. 이 숫자를 실제 24 GiB GPU의 동시 요청 보장으로 쓰지 않는다.

**추가 문제:** 17-token 요청이 token 하나를 더 만들면 KV block 하나를 더 할당하는가?

**해설:** 이 모형에서는 이미 32개 슬롯을 확보했으므로 18번째 token은 그 안에 들어간다. 33번째부터 세 번째 block이 필요하다. 논리 token 길이와 확보한 슬롯 수를 구별한다.

## 실습 4. all-reduce의 값과 ring 통신량을 따로 본다

all-reduce는 참가자의 값을 합산 등의 연산으로 합쳐 모두에게 제공한다. 여기서는 목록을 직접 합산한다. 실제 ring 알고리즘이나 네트워크를 실행하지 않는다.

```python
from fractions import Fraction

local_vectors = [[1, 10], [2, 20], [3, 30], [4, 40]]
participants = len(local_vectors)
reduced = [sum(column) for column in zip(*local_vectors)]
averaged = [value / participants for value in reduced]
assert reduced == [10, 100]
assert averaged == [2.5, 25.0]

payload = 8 * 2 ** 30
sent_per_rank = Fraction(2 * (participants - 1), participants) * payload
received_per_rank = sent_per_rank
assert sent_per_rank == 12 * 2 ** 30
print("sum", reduced, "average", averaged)
print("sent GiB/rank", float(sent_per_rank / 2 ** 30))
print("received GiB/rank", float(received_per_rank / 2 ** 30))
```

**해석:** 통신량 공식은 동일 크기의 데이터를 균등하게 쪼개는 단순 ring all-reduce 모형이다. 송신과 수신 각각의 크기이며, 둘을 더한 값을 단일 링크 처리 시간으로 곧바로 나누지 않는다. 알고리즘 선택, 양방향 전송·겹침, 링크 공유, 메시지 크기와 지연이 실제 시간을 바꾼다.

**추가 문제:** 평균을 원할 때 all-reduce의 SUM 결과를 그대로 optimizer에 주면 무엇이 달라지는가?

**해설:** 이 예에서는 gradient가 참가자 수인 4배가 된다. 다른 정규화가 없으면 갱신 크기도 커진다. API 또는 프레임워크가 어느 단계에서 나누는지 확인해야 한다.

## 실습 5. 높은 총 처리량이 모든 요청의 낮은 TTFT를 뜻하지 않는다

가상 서버가 요청 하나를 끝까지 처리한 뒤 다음 요청을 시작한다. 도착 순서대로 처리하는 FCFS(First Come, First Served) 모형이다. 첫 token은 prefill이 끝날 때 나온다고 정의하고, 이후 token마다 10 ms가 걸린다고 가정한다. 모든 시간은 실제 시계를 재지 않는 가상 시간이다.

```python
requests = [
    {"arrival": 0, "prefill": 20, "output_tokens": 3},
    {"arrival": 5, "prefill": 10, "output_tokens": 1},
    {"arrival": 10, "prefill": 10, "output_tokens": 2},
]
clock_ms = 0
results = []
for request in requests:
    start = max(clock_ms, request["arrival"])
    first = start + request["prefill"]
    finish = first + (request["output_tokens"] - 1) * 10
    results.append({
        "queue_ms": start - request["arrival"],
        "ttft_ms": first - request["arrival"],
        "e2e_ms": finish - request["arrival"],
        "mean_itl_ms": None if request["output_tokens"] == 1 else 10,
    })
    clock_ms = finish

assert [r["ttft_ms"] for r in results] == [20, 45, 50]
assert [r["e2e_ms"] for r in results] == [40, 45, 60]
assert results[1]["mean_itl_ms"] is None
window_seconds = (clock_ms - requests[0]["arrival"]) / 1000
output_tokens = sum(r["output_tokens"] for r in requests)
good_requests = sum(r["ttft_ms"] <= 30 and r["e2e_ms"] <= 50 for r in results)
assert good_requests == 1
print(results)
print("output tokens/s", output_tokens / window_seconds)
print("SLO-passing requests/s", good_requests / window_seconds)
```

**해석:** 총 출력 처리량은 약 85.71 tokens/s지만, 예시 지연 목표를 만족한 요청은 셋 중 하나다. 분모는 첫 도착부터 마지막 완료까지 같은 70 ms다. 실제 측정에서는 HTTP 연결·네트워크·tokenization·stream buffering의 포함 범위를 정해야 한다. 출력 token이 하나이면 두 token 사이 간격은 없으므로 ITL을 0으로 넣어 평균을 낮추지 않는다.

**추가 문제:** 이 모형만으로 continuous batching이 반드시 빨라진다고 결론 낼 수 있는가?

**해설:** 없다. batching의 실행 비용, prefill과 decode 간 간섭, 실제 GPU 처리 시간과 정책을 구현하지 않았다. 비교 대상 스케줄러와 같은 입력·측정 경계를 추가해야 한다.

## 실습 6. 같은 가중치에서 재시작해도 optimizer 상태가 다르면 달라진다

momentum은 이전 gradient 방향을 일부 기억하는 optimizer 상태다. 이 예에서는 `v = 0.8v + gradient`, `w = w - 0.05v`를 사용한다. 세 예제를 같은 순서로 순환한다. 난수나 데이터 섞기는 없으므로 이 모형의 재시작 상태는 w, v, 다음 예제를 가리키는 step으로 충분하다.

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory

samples = [(1.0, 2.0), (2.0, 4.0), (3.0, 6.0)]

def advance(state, count):
    state = dict(state)
    for _ in range(count):
        x, y = samples[state["step"] % len(samples)]
        gradient = (state["weight"] * x - y) * x
        state["momentum"] = 0.8 * state["momentum"] + gradient
        state["weight"] -= 0.05 * state["momentum"]
        state["step"] += 1
    return state

initial = {"weight": 0.0, "momentum": 0.0, "step": 0}
reference = advance(initial, 20)
at_eight = advance(initial, 8)

with TemporaryDirectory(prefix="ai-checkpoint-lesson-") as directory:
    checkpoint = Path(directory) / "state.json"
    checkpoint.write_text(json.dumps(at_eight), encoding="utf-8")
    restored = json.loads(checkpoint.read_text(encoding="utf-8"))
    resumed = advance(restored, 12)
    weights_only = advance({
        "weight": restored["weight"], "momentum": 0.0, "step": restored["step"],
    }, 12)
    assert resumed == reference
    assert weights_only["weight"] != reference["weight"]

assert not Path(directory).exists()
print("uninterrupted", reference)
print("full-state resume", resumed)
print("weights-only resume", weights_only)
```

**해석:** optimizer 상태가 결과에 영향을 준다는 것을 검사했다. JSON 쓰기의 정전 안전성, 분산 checkpoint의 모든 shard 게시, 장치별 부동소수점 재현성을 검사한 것은 아니다. 실제 학습은 LR scheduler, RNG, sampler·데이터 위치, mixed-precision scaler 등 구성에 맞는 추가 상태를 요구한다. [PyTorch 일반 checkpoint 안내](https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html#saving-loading-a-general-checkpoint-for-inference-and-or-resuming-training)

**추가 문제:** momentum을 저장해도 step을 0으로 바꾸면 이 예에서 같은 결과가 보장되는가?

**해설:** 없다. 다음에 고를 예제와 남은 진행 위치가 달라진다. 실제 파이프라인에서는 prefetch 상태, 재샘플링 규칙과 shard 경계까지 데이터 진행 의미를 정의해야 한다.

## 7. 운영 장비를 쓰기 전의 설계 과제

아래는 정해진 실제 제품 구매 권고나 성능 예측이 아닌 **가상 조건**이다.

- 24 GiB 장치 두 개, 장치 간 연결 속도는 아직 측정하지 않았다.
- 가중치 16 GB인 가상 모델, 실습 3의 4096-token KV 구조를 사용한다.
- 각 요청의 생성 길이는 최대 256 tokens지만 도착률·길이 분포는 아직 모른다.
- 첫 token 1초 이내라는 목표를 검토 중이다.

먼저 별도 장치에 복제본 하나씩 둘지, 한 모델을 두 장치에 나눌지 두 안을 작성한다. 가중치가 한 장치에 들어간다는 사실만으로 복제본 방식을 확정하지 않는다. 남는 KV 공간, 긴 요청, 통신 비용, 단일 요청 지연과 복구 단위를 대조한다.

**답안에 필요한 것:** GPU별 메모리 표, 입력·출력 길이 분포, 과부하 시 입장 제한, 동시성 변화 실험, 실패·취소 포함 측정 규칙, 모델 품질 비교, 사용할 프레임워크·revision 기록. 아직 관측하지 않은 연결 속도와 처리량은 빈칸으로 남기고 측정 계획을 쓴다.

## 8. 실제 실습으로 확장하는 순서

| 단계 | 작업 | 통과 조건 |
| --- | --- | --- |
| A | 이 장의 모형·해설 확인 | 값·단위·모형 한계를 설명 |
| B | 격리된 기존 개발 환경에서 작은 framework tensor 연산 | CPU와 GPU 결과 비교, 비동기 완료를 고려한 측정 |
| C | 장치 한 개의 작은 학습·추론 | OOM 없는 한도, 입력/계산 구간·품질·peak memory 기록 |
| D | 장치 두 개의 분산 실행 | rank 대응·collective 일치·통신 시간·재시작 검증 |
| E | 제한된 요청의 서비스 실험 | TTFT·ITL·E2E·실패율·goodput과 모델 revision 기록 |
| F | 장애·확장·비용 실험 | 명시한 장애 범위에서 복구·SLO·비용 판정 |

이 교재의 자동 검사는 A까지만 실행한다. B 이후는 사용 가능한 장치·버전·작업 예산에 맞춘 별도 실험이다. 장치 명칭이나 endpoint를 가정해 운영 클러스터에 작업을 제출하지 않는다.

## 9. 연구 문제로 바꾸기

“GPU를 더 쓰면 빨라지는가”를 그대로 연구 질문으로 두기보다 **같은 품질·데이터 순서·global batch를 유지하면서 한 스텝의 통신과 계산 겹침을 바꾸면 유효 학습 처리량이 어떻게 달라지는가**처럼 비교 조건을 명시한다.

추론에서는 **동일 모델·입력 분포·출력 길이 정책에서 prefill 작업 크기 제한을 바꾸면 TTFT와 decode 지연을 동시에 만족하는 요청 수가 달라지는가**를 물을 수 있다. 결과가 나빠지는 긴 입력·낮은 도착률·짧은 출력 조건도 함께 시험한다.

논문·보고서에는 가설, 구현의 차이, 기준군, 정확성 조건, 원시 시간표, 표본 수, 반복, 실패 요청 처리, 자원 비용과 재현 방법을 남긴다. 우수한 평균 하나보다 어떤 조건에서 결론이 깨지는지 설명하는 편이 더 강한 근거다.
