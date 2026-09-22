# 08. 데이터, 모델, 체크포인트

[AI 인프라 학습 목차](README.md) · 이전: [07. 서빙, 스케줄링, SLO](07-serving-scheduling-and-slo.md) · 다음: [09. GPU 클러스터와 배치](09-gpu-clusters-and-placement.md)

AI 인프라에서 데이터는 학습용 파일만 뜻하지 않는다.
dataset, tokenizer, model weight, adapter, config, 학습 코드, optimizer 상태, checkpoint manifest, serving bundle이 모두 운영 대상이다.
이 장은 “파일이 있다”와 “재현 가능하고 재시작 가능한 상태다”를 구별한다.

목표는 두 가지다.
첫째, 많은 작은 파일과 큰 객체 저장소가 왜 병목을 만드는지 계산한다.
둘째, 체크포인트가 모델 weight 하나가 아니라 학습을 이어가기 위한 상태 묶음임을 이해한다.

## 핵심 용어

- **dataset:** 학습이나 평가에 쓰는 입력/정답 자료의 모음이다.
- **sample:** 학습 loop가 한 번 읽는 한 예시다.
- **shard:** 큰 dataset이나 checkpoint를 여러 파일로 나눈 조각이다.
- **object storage:** S3 같은 key-value 형태의 원격 객체 저장소다.
- **POSIX filesystem:** `open`, `read`, `write`, `rename` 같은 파일 API와 계층적 경로를 제공하는 파일시스템이다.
- **cache:** 느린 저장소에서 읽은 데이터를 가까운 곳에 임시로 보관하는 계층이다.
- **model artifact:** serving이나 fine-tuning에 필요한 weight, tokenizer, config, code, adapter, template 묶음이다.
- **revision:** artifact의 정확한 버전 식별자다. branch 이름보다 불변 commit/hash가 더 강하다.
- **checkpoint:** 학습 중 특정 시점에서 재시작하기 위한 저장 상태다.
- **manifest:** 여러 shard와 metadata가 모두 무엇인지 적은 목록이다.
- **durable:** 성공 응답 뒤 장애가 나도 저장 내용이 남는다고 기대할 수 있는 상태다.
- **activation checkpointing:** forward 중간 activation을 덜 저장하고 backward 때 다시 계산하는 메모리 절약 기법이다.
- **training checkpoint save:** 학습 재시작을 위해 weight와 optimizer 등 상태를 저장하는 일이다.

## Dataset 읽기 경로

학습 worker가 sample 하나를 읽을 때 실제 경로는 다음처럼 길 수 있다.

1. sampler가 이번 step에서 읽을 sample ID를 고른다.
2. dataset index가 sample ID를 shard와 offset으로 바꾼다.
3. local cache에 shard나 range가 있는지 본다.
4. 없으면 object storage 또는 분산 파일시스템에서 읽는다.
5. 압축을 풀고 record를 decode한다.
6. tokenizer나 image transform을 적용한다.
7. batch로 묶고 device 전송을 준비한다.
8. GPU가 기다리지 않도록 prefetch queue에 넣는다.

GPU가 비어 있는데 storage와 CPU decode가 느리면 expensive accelerator가 대기한다.
반대로 data loader worker를 무작정 늘리면 object store 요청 수, metadata lookup, local disk cache 경합이 터질 수 있다.

## 많은 작은 파일 문제

작은 파일 1,000,000개와 큰 shard 1,000개는 총 바이트 수가 같아도 운영 비용이 다르다.
작은 파일은 파일마다 open, metadata lookup, 권한 확인, 네트워크 round trip, TLS 연결 재사용, object key lookup 같은 고정 비용을 낸다.

예를 들어 파일 하나를 여는 고정 비용이 평균 2 ms이고 파일 데이터 전송은 작아서 무시한다고 하자.

```python
files = 1_000_000
open_ms = 2
total_seconds = files * open_ms / 1000
print(total_seconds, total_seconds / 3600)
```

결과는 2,000초, 약 0.56시간이다.
이 계산은 “열기”만 센 것이다.
실제에는 LIST, retry, decode, small read amplification이 더 붙는다.
그래서 AI dataset은 tar shard, parquet, webdataset, recordio 같은 묶음 형식을 쓰기도 한다.
형식 선택은 학습 프레임워크와 재현성 요구에 맞춰야 한다.

## Object storage와 POSIX 의미 차이

POSIX 파일시스템에서는 같은 디렉터리 안 `rename`을 원자적 publish에 자주 사용한다.
임시 파일을 쓰고 fsync한 뒤 최종 이름으로 바꾸면 독자는 이전 파일 또는 새 파일 중 하나를 본다.
정확한 내구성은 파일시스템과 mount 옵션, 디렉터리 동기화에 의존한다.

object storage는 보통 `PUT object`, `GET object`, `LIST prefix` 같은 API를 제공한다.
S3는 현재 일반 목적 bucket에서 성공한 PUT/DELETE 이후 GET/LIST에 강한 일관성을 제공한다고 문서화한다.
그래도 POSIX rename과 같은 “디렉터리 안에서 여러 파일을 한 번에 교체” 의미가 자동으로 생기지는 않는다.
여러 shard를 올리는 중 독자가 일부 shard만 보는 문제는 manifest publish 규칙으로 막아야 한다.

안전한 publish 패턴은 다음과 같다.

1. shard를 임시 prefix에 업로드한다.
2. 각 shard의 크기와 checksum을 확인한다.
3. manifest에 shard 목록, 크기, checksum, revision, 생성 시각을 쓴다.
4. manifest를 마지막에 최종 위치에 올린다.
5. 독자는 manifest가 가리키는 shard만 읽는다.

manifest가 마지막 commit record가 된다.
shard가 먼저 보이는 것은 괜찮지만, manifest가 없는 shard는 published dataset으로 취급하지 않는다.

## Model artifact의 구성

serving 가능한 모델은 weight 파일 하나보다 크다.
최소한 다음을 묶어야 한다.

- weight shard와 dtype.
- tokenizer vocabulary와 tokenizer config.
- model config.
- generation config 또는 chat template.
- adapter와 base model revision.
- custom code가 있다면 코드 revision과 실행 신뢰 정책.
- license와 사용 제한.
- 변환 도구와 quantization 설정.

Hugging Face Transformers의 `save_pretrained`/`from_pretrained` 흐름은 model과 tokenizer를 디렉터리 또는 model ID로 저장/로드하는 관용 경로를 제공한다.
운영에서는 branch 이름보다 불변 revision을 기록해야 한다.
`main`이 오늘과 내일 다른 파일을 가리키면 재현이 깨진다.

## 학습 체크포인트에 들어갈 상태

재시작 가능한 training checkpoint에는 보통 다음이 들어간다.

- model parameters.
- optimizer state.
- learning-rate scheduler state.
- gradient scaler state, mixed precision을 쓴다면.
- random number generator state.
- epoch, global step, micro step.
- sampler state 또는 다음 data position.
- distributed rank/world size 관련 저장 형식 정보.
- 코드와 config revision.

PyTorch의 일반 checkpoint 예시는 model state와 optimizer state, epoch, loss 등을 함께 저장하는 패턴을 보여준다.
실제 대규모 학습에서는 ZeRO/FSDP/tensor parallel 때문에 optimizer와 parameter가 rank별 shard로 나뉠 수 있다.
그래서 “rank 3의 파일 하나가 없다”는 전체 checkpoint 불능으로 이어질 수 있다.

## Activation checkpointing과 save checkpoint는 다르다

이름이 비슷해서 자주 헷갈린다.

activation checkpointing은 GPU 메모리를 아끼려고 forward 중간값 저장을 줄이는 기법이다.
대신 backward 때 일부 계산을 다시 한다.
이것은 학습 중 메모리/시간 tradeoff다.

training checkpoint save는 장애나 중단 뒤 학습을 이어가기 위해 저장소에 상태를 쓰는 일이다.
이것은 복구와 재현성 문제다.

둘 다 checkpoint라는 단어를 쓰지만 하나는 메모리 절약, 다른 하나는 내구성 저장이다.
운영 문서에는 “activation checkpointing enabled”와 “checkpoint saved every N steps”를 분리해서 적는다.

## Sharded checkpoint publish

8개 rank가 각각 checkpoint shard를 쓴다고 하자.
rank 0이 manifest를 먼저 올리고 rank 7이 나중에 실패하면 독자는 깨진 checkpoint를 볼 수 있다.
올바른 순서는 모든 shard가 durable해진 뒤 manifest를 publish하는 것이다.

간단한 상태 기계는 다음과 같다.

1. `checkpoint-123.tmp/rank-*.bin` 작성 시작.
2. 각 rank가 파일 크기와 checksum을 기록한다.
3. coordinator가 모든 rank 완료를 확인한다.
4. manifest를 작성한다.
5. manifest를 최종 이름으로 publish한다.
6. old checkpoint cleanup은 새 checkpoint 검증 뒤 별도로 한다.

cleanup을 publish와 묶지 않는다.
새 checkpoint가 깨졌는데 old checkpoint까지 지우면 재시작 지점이 사라진다.

## Worked calculation: bandwidth

checkpoint 크기가 2 TiB이고 저장 경로의 실제 지속 쓰기 처리량이 4 GiB/s라고 하자.

```python
tib = 2
gib_per_s = 4
seconds = tib * 1024 / gib_per_s
print(seconds, seconds / 60)
```

쓰기만 512초, 약 8.53분이다.
동시에 학습이 계속 달리면 storage bandwidth와 CPU, network가 학습 step과 경쟁할 수 있다.
checkpoint interval을 10분으로 잡으면 대부분의 시간이 checkpoint I/O와 겹칠 수 있다.

## Worked calculation: lost work

학습 step이 3초이고 checkpoint를 1,000 step마다 저장한다고 하자.
장애가 checkpoint 직전에 나면 최대 잃는 작업은 거의 3,000초다.
평균적으로는 interval의 절반을 잃는다고 단순 가정할 수 있다.

```python
step_seconds = 3
interval_steps = 1000
max_lost_minutes = step_seconds * interval_steps / 60
expected_lost_minutes = max_lost_minutes / 2
print(max_lost_minutes, expected_lost_minutes)
```

최대 50분, 평균 25분이다.
하지만 checkpoint를 너무 자주 저장하면 I/O 때문에 학습 자체가 느려진다.
복구 시간 목표와 저장 비용을 같이 계산해야 한다.

## 데이터 위치와 cache 정책

cache는 성능 도구이면서 재현성 위험이다.
cache hit이면 빠르고 miss이면 느리다.
old revision이 cache에 남아 있으면 잘못된 데이터를 읽을 수도 있다.

cache key에는 dataset revision, transform version, tokenizer version, compression format, shard checksum을 포함한다.
“경로가 같으니 같은 데이터”라고 가정하지 않는다.
object storage key가 overwrite될 수 있는 정책이라면 immutable prefix를 쓰거나 manifest hash로 고정한다.

local NVMe cache를 쓰는 경우 eviction도 실험 조건이다.
첫 실행 cold cache와 두 번째 실행 warm cache의 처리량은 다르다.
benchmark에는 cache 상태를 반드시 적는다.

## 오개념 바로잡기

- “모델 파일만 있으면 재현된다”: tokenizer, config, code, adapter revision이 빠지면 달라질 수 있다.
- “S3는 파일시스템이다”: object API와 POSIX rename/lock 의미는 다르다.
- “checkpoint는 weight 저장이다”: optimizer, scheduler, RNG, sampler 위치가 없으면 이어달리기가 달라질 수 있다.
- “manifest는 친절한 목록이다”: sharded publish에서는 commit record 역할을 한다.
- “작은 파일은 총량이 작으니 괜찮다”: metadata와 요청 고정 비용이 병목이 될 수 있다.
- “activation checkpointing을 켰으니 장애 복구가 된다”: 전혀 다른 의미다.

## 공식 자료

- PyTorch는 일반 checkpoint에서 model과 optimizer state 등을 함께 저장하는 예시를 제공한다: <https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html>
- Hugging Face Transformers는 model/tokenizer의 `save_pretrained`와 local directory load 경로를 문서화한다: <https://huggingface.co/docs/transformers/main_classes/model>
- Amazon S3의 현재 consistency model은 성공한 PUT 뒤 GET/LIST 동작을 설명한다: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel>
- Linux·파일시스템 동기화 기초는 이 교재의 데이터 시스템 장을 다시 본다: <../../../kubernetes/storage/data-systems-foundations/01-linux-read-write.md>

## 연습문제

1. 500 GiB checkpoint를 2 GiB/s로 저장한다. 순수 쓰기 시간은?
   답: `500 / 2 = 250초`, 약 4.17분이다. metadata, checksum, flush, contention은 제외한 하한이다.

2. rank 0-7 중 rank 6 shard 업로드가 실패했다. manifest를 publish해도 되는가?
   답: 안 된다. manifest는 모든 shard의 durable 확인 뒤 마지막에 publish해야 한다.

3. 학습을 정확히 이어가기 위해 weight 외에 최소 세 가지를 말하라.
   답: optimizer state, scheduler state, RNG state, sampler/data position 등이 필요하다.

4. cold cache benchmark와 warm cache benchmark를 섞어 평균을 냈다. 무엇이 문제인가?
   답: 서로 다른 조건을 평균낸 것이다. cache 상태가 처리량과 tail latency를 바꾸므로 따로 보고해야 한다.
