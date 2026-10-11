# 11. GPU 없이 확인하는 AI 인프라 실습과 연구 과제

[학습 안내](README.md) · 이전: [관측·벤치마크·비용](10-observation-benchmarking-and-cost.md) · 다음: [용어 사전](12-glossary.md)

이 장은 **표준 Python(외부 패키지 없이 쓰는 기본 파이썬)만으로 실행하는 작은 교육 모형**이다. 계산과 상태의 의미를 검증한다. GPU에서 실제 계산을 수행하는 **GPU kernel(장치 함수)**, GPU 명령 순서를 관리하는 **CUDA stream(작업 순서열)**, 여러 GPU가 값을 교환하는 **NCCL 통신**, 생성 요청을 묶어 실행하는 **vLLM 스케줄러**의 실성능을 검증하는 실습은 아니다.

각 Python 블록을 별도 파일로 저장해 실행하거나, [예제 검사 도구](examples/README.md)로 교재의 모든 Python 블록을 실행할 수 있다. 외부 패키지·모델·데이터 다운로드가 없고, 마지막 실습은 자신이 만든 임시 디렉터리만 사용한다. 먼저 예상 결과를 적은 뒤 실행한다.

## 모형 실습과 실제 장비 검증의 경계

```mermaid
flowchart LR
    H[가설과 손계산] --> S[표준 Python 모형]
    S --> A[예상값과 assert 비교]
    A --> I[원리 이해]
    I -.별도 단계.-> G[실제 GPU/분산 실험]
    G --> O[장비·버전·관측값 기록]
```

이 장의 코드가 `512 MiB`를 출력하면 “주어진 공식과 입력으로 512MiB가 계산됐다”는 뜻이다. 실제 GPU에서 512MiB가 할당되었다는 측정 결과가 아니다. 실제 검증에는 모델의 정확한 버전을 뜻하는 revision, 숫자 저장 형식인 dtype, 한 번에 묶는 요청 수와 문맥 길이인 batch/context, 엔진 버전, GPU 모델, 메모리 배정 상태를 보여 주는 allocator 통계와 실행 명령이 필요하다. 반대로 실제 장비 출력 한 번도 공식의 보편적 증명은 아니다. 모형은 변수를 통제하고, 실험은 구현의 추가 비용을 관측한다.

## 예제 검사 방법과 한계

[예제 검사 도구](examples/README.md)는 기본 실행에서 교재의 Python·Bash 구문, 상대 링크, 표와 코드 fence를 확인한다. `--run-python`을 주면 정적 검사를 통과한 Python block을 각각 별도 임시 디렉터리에서 실행해 종료 코드와 `assert`를 확인한다. 이 초안을 수선하며 명령을 실제 실행하지 않았으므로 아래 수치는 원문 코드와 명시된 `assert`를 손으로 추적한 결과다.

검사 통과는 선택한 작은 입력에서 Python 계산과 기대값이 일치한다는 뜻이다. GPU kernel, CUDA stream, NCCL 통신, 장치 메모리 peak, 실제 scheduler 시간과 원격 URL은 검증하지 않는다. 임시 디렉터리도 보안 sandbox가 아니므로 신뢰한 교재 코드만 실행한다.


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

### 입력부터 assert까지의 상태표

`w`, `x`, `y`, `loss`와 `gradient`는 Python의 배정밀도 부동소수점 값이다. `samples`는 `(입력, 정답)` tuple 두 개를 가진 list이고 실습 전체 동안 변하지 않는다.

| 단계 | w | 예측 `(x=1,x=2)` | 오차 | 평균 loss | gradient |
|---|---:|---|---|---:|---:|
| 시작 | 0 | 0, 0 | -2, -4 | `(2+8)/2=5` | `(-2×1-4×2)/2=-5` |
| 1회 갱신 | 0.5 | 0.5, 1 | -1.5, -3 | 2.8125 | -3.75 |
| 수렴 목표 | 2 | 2, 4 | 0, 0 | 0 | 0 |

`w -= 0.1×gradient`가 첫 상태를 0.5로 바꾼다. `probe=0.3`에서는 해석 gradient `2.5(0.3-2)=-4.25`와 `epsilon=1e-5` 유한 차분이 `isclose` 범위에서 같아야 한다. 40회 반복 뒤 `loss<1e-8` assert는 이 고정 학습률과 볼록한 한 변수 문제에서 수렴했는지 본다. 일반 신경망의 최적화·GPU 반올림·자동 미분 구현을 증명하지 않는다.


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

### 두 rank의 중간값 전체 추적

`rank_samples`는 실제 process가 아니라 두 묶음을 담은 중첩 list다. `local_sums`는 rank별 gradient 합, `counts`는 표본 수다.

| 논리 rank | x 값 | 각 gradient `(w×x-y)×x` | 합 | 개수 | local mean |
|---:|---|---|---:|---:|---:|
| 0 | 1,2 | -1,-4 | -5 | 2 | -2.5 |
| 1 | 3 | -9 | -9 | 1 | -9 |

Local mean 둘을 같은 비중으로 평균하면 `(-2.5-9)/2=-5.75`다. 모든 표본을 같은 비중으로 합치면 `(-5-9)/(2+1)=-14/3≈-4.6667`이다. 첫 `assert`는 weighted mean과 펼친 reference가 같음을, 둘째는 naive mean이 다름을 확인한다. 실제 DDP의 process·collective·통신 실패·padding mask는 포함하지 않는다.


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

### KV와 block 상태를 바이트 단위로 추적

모든 변수는 Python 정수다. `gib=2^30`, `mib=2^20`이므로 십진 GB와 섞지 않는다.

| 계산 | 식 | 결과 |
|---|---|---:|
| GQA 요청 KV | `2×32×8×128×4096×2` | 536,870,912 B = 512 MiB |
| KV head 32인 비교값 | `2×32×32×128×4096×2` | 2 GiB |
| 장치 byte | `24×2^30` | 25,769,803,776 B |
| FP16 weight | `8,000,000,000×2` | 16,000,000,000 B |
| 비-KV 예약 | `4×2^30` | 4 GiB |
| KV에 남은 양 | 장치-weight-예약 | 5,474,836,480 B |
| floor capacity | 남은 양÷512 MiB | 10 requests |

길이 17과 31은 block 16 기준으로 각각 `ceil(length/16)=2` block, 32 slot을 잡는다. 총 64 slot 중 실제 token은 48이라 16이 빈다. Assert는 10개가 예산 안이고 11개가 넘는지, block 올림이 맞는지 확인한다. 실제 allocator metadata·graph buffer·prefix 공유·문맥 성장은 생략한다.


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

### 값 축약과 byte 모형을 분리해 추적

`local_vectors`는 네 논리 참가자가 가진 길이 2의 Python list다. `zip(*local_vectors)`는 첫 열 `(1,2,3,4)`과 둘째 열 `(10,20,30,40)`을 만든다. 합은 `[10,100]`, 참가자 4로 나눈 평균은 `[2.5,25]`다.

통신 payload는 8 GiB이고 참가자는 4다. 단순 ring에서 rank당 송신량은 `2(P-1)N/P=2×3×8/4=12 GiB`다. `Fraction`은 이 비율을 유리수로 보존해 부동소수점 반올림 없이 assert한다. 결과값 assert와 통신량 assert는 서로 다른 사실이다. Python은 packet, link, reduce-scatter 단계, NCCL stream이나 시간을 실행하지 않는다.


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

### FCFS queue의 시계 전체 추적

`clock_ms`는 실제 시계가 아니라 서버가 다음 요청을 시작할 수 있는 가상 시각이다. FCFS는 도착 순서대로 하나를 끝낸 뒤 다음 하나를 시작한다.

| 요청 | 도착 | 시작 `max(clock,arrival)` | queue | first | finish | TTFT | E2E |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 0 | 0 | 0 | 20 | 40 | 20 | 40 |
| B | 5 | 40 | 35 | 50 | 50 | 45 | 45 |
| C | 10 | 50 | 40 | 60 | 70 | 50 | 60 |

A는 첫 token 뒤 두 간격, B는 출력 하나라 간격 없음, C는 한 간격이 있다. 측정 창은 70 ms이고 출력은 6 token이라 `6/0.07≈85.71 tokens/s`다. TTFT≤30과 E2E≤50을 모두 만족한 것은 A 하나라 goodput은 `1/0.07≈14.29 req/s`다. Assert는 queue·TTFT·E2E 목록과 통과 개수를 확인한다. 실제 continuous batch, 병렬 GPU, network와 wall-clock jitter는 생략한다.


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

### 저장·복원 상태의 숫자 추적

`state` dictionary의 `weight`와 `momentum`은 부동소수점, `step`은 정수다. `step%3`이 다음 sample index를 정한다. `advance`는 입력 dictionary를 복사하므로 원본을 직접 바꾸지 않는다.

| 상태 | weight | momentum | step |
|---|---:|---:|---:|
| initial | 0 | 0 | 0 |
| 8 step checkpoint | 2.757184 | 4.47632 | 8 |
| 중단 없이 20 step | 2.2084575018 | 1.0480134998 | 20 |
| 전체 상태 복원 뒤 12 step | 2.2084575018 | 1.0480134998 | 20 |
| weight만 복원 뒤 12 step | 2.2011263640 | -0.1061823353 | 20 |

임시 JSON에는 8-step dictionary 전체를 쓰고 다시 읽는다. 전체 복원 결과가 reference와 같다는 assert와 momentum을 0으로 버린 결과가 다르다는 assert가 핵심이다. 임시 directory가 문맥 종료 뒤 삭제됐다는 것도 확인한다. 실제 정전 중 원자적 파일 게시, rank shard, RNG, 부동소수점 bitwise 재현은 검사하지 않는다.


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

교육 모형을 연구로 확장할 때는 **가설**을 결과 전에 쓰고, 연구자가 바꾸는 **독립 변수**, 결과로 측정하는 **종속 변수**, 같게 유지하는 **통제 변수**, 결론을 보류할 **실패 조건**을 정한다. 모형의 assert 통과는 연구 결과가 아니라 실험 설계를 시작할 자격 조건이다.

### 계획 A: KV block 크기와 유효 용량

가설은 “동일 요청 길이 분포에서 block을 16 token에서 8 token으로 줄이면 마지막 block 빈칸이 줄어 admission 가능한 요청 수가 늘지만 block table 처리 비용 때문에 decode ITL은 나빠질 수 있다”이다.

| 구분 | 값 |
|---|---|
| 독립 변수 | KV block 8·16·32 token |
| 통제 변수 | 동일 model/tokenizer revision, GPU, dtype, 도착 trace, scheduler |
| 종속 변수 | 내부 단편화, admission 수, TTFT·ITL p50/p99, goodput |
| 정확성 | 같은 seed·sampling 계약에서 token ID 또는 허용한 분포 검증 |
| 실패 조건 | OOM, 오류 token, timeout 제외로 표본 왜곡, profiler overhead 혼입 |

실습 3은 `ceil(length/block_size)` 산술만 검산한다. 실제 연구에서는 block table kernel과 allocator metadata가 추가되므로 작은 block이 항상 이긴다고 예상하지 않는다.

### 계획 B: Gradient 평균 규칙

가설은 “rank별 유효 token 수가 다를 때 local mean을 같은 비중으로 평균하면 전체 token mean과 다른 gradient가 되어 동일 초기값에서도 학습 궤적이 달라진다”이다. 독립 변수는 정규화 방식이고, 통제 변수는 sample 순서·global token·초기 weight·optimizer·world size다. 종속 변수는 한 step gradient, validation loss와 처리량이다. NaN, sample 중복, 서로 다른 global batch, collective 실패가 생기면 성능 비교를 중단한다.

### 계획 C: Scheduler와 goodput

가설은 “긴 prefill을 작은 chunk로 나누면 높은 도착률에서 TTFT p99는 줄지만 실행 중 decode의 ITL p99가 늘 수 있다”이다. 동일 arrival trace, prompt/output 길이, model revision, cache 상태에서 chunk 크기만 바꾼다. TTFT·ITL·E2E, timeout, cancel, output tokens/s와 SLO goodput을 모두 측정한다. 출력 품질이나 sampling 설정이 달라지거나 한 조건만 warm cache이면 비교가 성립하지 않는다.

모든 계획은 최소한 기준 구현, 반복 횟수, 원시 timestamp, software·driver version, 실패 요청 포함 규칙과 비용을 남긴다. 평균이 좋아도 사전 SLO를 넘긴 p99나 정확성 실패가 있으면 “개선”으로 판정하지 않는다.
