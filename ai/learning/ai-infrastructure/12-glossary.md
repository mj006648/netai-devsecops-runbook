# 12. AI 인프라 용어 사전

[학습 안내](README.md) · 이전: [로컬 실습과 연구](11-local-labs-and-research.md)

단어의 뜻을 찾은 뒤 해당 장의 동작 예제로 돌아간다. 같은 약어도 계층에 따라 뜻이 달라진다. 이 사전에서 B는 문맥에 따라 batch 또는 billion이므로 계산식에서 정의를 확인한다.

## 모델과 계산

| 용어 | 쉬운 뜻 | 혼동하면 안 되는 것 |
| --- | --- | --- |
| AI, Artificial Intelligence | 지능적 작업을 수행하는 시스템을 다루는 넓은 분야 | 모든 AI가 LLM인 것은 아님 |
| ML, Machine Learning | 데이터로부터 작업에 유용한 규칙·파라미터를 학습하는 방법 | 규칙을 손으로 코딩하는 방식과 구별 |
| 모델 | 입력을 출력으로 바꾸는 계산 구조와 상태 | 가중치 파일 하나만으로 전체 실행 조건이 정해지지 않음 |
| parameter / weight | 학습으로 조정하는 모델의 값 | 학습률 같은 hyperparameter |
| tensor / shape | 여러 축을 가진 숫자 배열 / 각 축의 길이 | shape가 같아도 축의 의미는 다를 수 있음 |
| dtype | 숫자 표현 방식 | 값의 의미, 모델 품질 |
| operator / kernel | 모델의 연산 / 이를 실행하는 장치 코드 | Linux kernel과 GPU kernel은 다른 대상 |
| activation | 모델 계산 도중 만들어진 중간 값 | 파라미터·gradient |
| loss | 정답·목표와 출력 차이를 학습용 수로 나타낸 것 | 모든 서비스 품질을 대표하는 한 숫자는 아님 |
| gradient | 파라미터 변화에 따른 손실의 변화율 | 학습률·파라미터 자체 |
| backward / autograd | 역방향 미분 계산 / 미분 계산을 자동 구성하는 기능 | 기본 방식이 유한 차분인 것은 아님 |
| optimizer | gradient와 내부 상태를 이용해 파라미터를 갱신하는 규칙 | 모델 구조 |
| token / tokenizer | 모델이 처리하는 이산 단위 / 입력을 단위 ID로 바꾸는 구성 | 글자·단어·UTF-8 byte와 일대일이 아님 |
| embedding | ID 등을 숫자 벡터로 나타내는 표현 | 문장을 사람이 이해했다는 증명 |
| attention / Q·K·V | 문맥의 값을 가중 결합하는 계산 / query·key·value | 모든 모델의 전역 검색 장치가 아님 |
| MHA / GQA / MQA | 여러 attention head / KV head를 그룹 공유 / 하나의 KV head 공유 | query head 수를 KV head 수로 무조건 사용하지 않기 |
| MoE, Mixture of Experts | 입력에 따라 일부 expert 계산을 선택하는 구조 | 활성 파라미터 수가 전체 가중치 저장량인 것은 아님 |
| FLOP / FLOP/s | 부동소수점 연산 수 / 초당 연산 수 | 양·속도, 정밀도와 곱셈-덧셈 계수 구별 |

[01장](01-tensors-autograd-and-transformers.md)에서 숫자로 추적하고 [03장](03-memory-precision-and-capacity.md)에서 저장량을 계산한다.

## 학습과 분산 실행

| 용어 | 쉬운 뜻 | 혼동하면 안 되는 것 |
| --- | --- | --- |
| sample / batch | 입력 사례 하나 / 한 번 묶어 계산하는 입력들 | 가변 길이 sample 수와 유효 token 수 |
| microbatch | 큰 작업을 나누어 계산하는 작은 묶음 | optimizer update 횟수 |
| gradient accumulation | 여러 backward의 gradient를 모아 한 번 갱신 | 손실 정규화 없이 단순 반복해도 같은 학습이 된다는 뜻 |
| epoch / step | 데이터 순회 단위 / 정의한 작업 진행 단위 | step이 forward인지 optimizer update인지 명시 |
| rank / world size | 통신 그룹 내 프로세스 번호 / 참여 수 | rank를 언제나 물리 노드 번호로 읽지 않기 |
| DP / DDP | 데이터 병렬 / PyTorch의 gradient 동기화 모델 복제 방식 | 큰 모델을 자동으로 쪼개는 것 |
| FSDP | Fully Sharded Data Parallel, 상태를 분할하는 데이터 병렬 방식 | 피크 메모리가 항상 카드 수만큼 줄어드는 것 |
| ZeRO | Zero Redundancy Optimizer, 단계별로 중복 상태를 줄이는 접근 | 모든 단계에서 가중치까지 분할하는 것은 아님 |
| TP / PP / EP | tensor / pipeline / expert parallelism | 자르는 대상과 통신 패턴이 서로 다름 |
| collective | 그룹이 함께 수행하는 통신 연산 | 참가 순서·shape 불일치가 자동 해결되는 것 |
| all-reduce | 그룹의 값을 합산 등으로 축약해 모두에게 배포 | sum과 average는 명시해야 함 |
| all-gather / reduce-scatter | 조각을 모두에게 모음 / 축약 결과를 조각으로 분배 | 서로 반대 함수라고만 보면 통신·축약 의미를 놓침 |
| NCCL | NVIDIA Collective Communications Library | 네트워크 장비나 모든 장애의 원인 이름이 아님 |
| straggler | 다른 참여자보다 늦어 전체 진행을 지연시키는 작업자 | GPU 연산이 느린 경우만 해당하는 것은 아님 |
| LoRA | Low-Rank Adaptation, 작은 저차원 가중치로 적응 학습 | optimizer 메모리 절약이 전체 학습 메모리 제거는 아님 |
| QLoRA | 양자화한 기반 모델을 활용하는 LoRA 학습 접근 | 어떤 4bit 서빙과도 같은 작업이라는 뜻은 아님 |
| activation checkpointing | 중간 값을 덜 저장하고 backward 때 재계산 | 장애 복구 파일 저장 |
| training checkpoint | 이어서 학습할 상태를 저장한 결과 | 추론용 가중치만 내보낸 파일 |

[04장](04-training-and-input-pipelines.md)과 [05장](05-distributed-training-and-collectives.md)에서 실행 순서를, [08장](08-data-models-and-checkpoints.md)에서 복구 상태를 확인한다.

## 추론과 서비스

| 용어 | 쉬운 뜻 | 혼동하면 안 되는 것 |
| --- | --- | --- |
| prefill | 입력 문맥을 처리하는 단계 | 요청 도착부터의 모든 지연 |
| decode | 이미 처리한 문맥을 이용해 후속 token을 생성하는 단계 | 모든 요청의 token당 시간이 고정이라는 뜻 |
| KV cache | 재사용할 attention의 key·value 상태 | 완성된 답변 cache |
| PagedAttention | KV 상태를 block 단위로 관리·접근하는 설계 | CPU page cache나 GPU 용량 증가 |
| prefix caching | 호환되는 동일 prefix의 계산 상태 재사용 | 의미가 비슷한 다른 문장에도 그대로 재사용 |
| continuous batching | 실행 중 완료·신규 요청을 단계 사이에 반영하는 스케줄링 | 요청 전체를 한 번만 묶는 정적 batch |
| chunked prefill | 긴 입력 처리를 조각으로 나누는 방식 | 그 자체로 입력 계산 총량이 사라지지는 않음 |
| speculative decoding | 후보 token을 제안하고 목표 모델로 검증하는 방식 | 후보를 무조건 출력하거나 언제나 가속되는 것 |
| TTFT | Time To First Token, 요청 시작에서 첫 token까지 시간 | GPU 계산 시간만 재면 종단 TTFT가 아님 |
| ITL / TPOT | token 사이 지연 / 후속 token당 시간 지표 | 전송 event·chunk 기준과 token 기준을 구별; 출력 1개는 간격 없음 |
| E2E latency | 정한 시작에서 응답 완료까지 걸린 시간 | 서버 내부 시간과 클라이언트 시간이 다를 수 있음 |
| throughput / goodput | 전체 처리량 / 정한 품질·지연 조건을 만족한 유효 처리량 | 분모와 포함할 요청 정의 없이 비교하지 않기 |
| SLI / SLO | 측정 지표 / 그 지표에 세운 서비스 목표 | 평균 사용률을 모든 사용자 목표로 대체할 수 없음 |
| admission control | 감당할 수 있는 작업을 받아들이는 제어 | 무한 대기열에 전부 넣기 |
| backpressure | 뒤쪽의 처리 한계를 앞쪽에 전달하는 제어 | 재시도를 무한히 늘리는 것 |
| readiness / warmup | 요청을 받을 준비 / 초기 실행 비용을 치르는 준비 작업 | 프로세스가 살아 있음과 모델이 준비됨은 다름 |
| RAG | Retrieval-Augmented Generation, 검색 결과를 문맥에 넣어 생성 | 모델 가중치를 매 요청 다시 학습하는 것 |

[06장](06-llm-inference-and-kv-cache.md)과 [07장](07-serving-scheduling-and-slo.md)에서 상태·대기·응답의 경계를 읽는다.

## 장치·운영·측정

| 용어 | 쉬운 뜻 | 혼동하면 안 되는 것 |
| --- | --- | --- |
| host / device | 작업을 제어하는 호스트 / 가속 장치 | CPU RAM과 장치 메모리가 언제나 같은 접근 계약인 것은 아님 |
| CUDA stream / event | 장치 작업의 순서 있는 제출 흐름 / 작업 진행을 기록·동기화하는 표식 | 여러 stream이 실제 겹침을 보장하지 않음 |
| allocated / reserved | 살아 있는 tensor에 쓰는 양 / allocator가 확보한 양 | reserved를 모두 메모리 누수로 판정하지 않기 |
| OOM | Out Of Memory, 필요한 할당에 실패 | host·device·container 한계의 실패를 구별 |
| mixed precision | 연산·상태별로 정밀도를 섞는 방식 | 모든 상태가 가장 작은 dtype으로 바뀌는 것은 아님 |
| quantization | 제한된 숫자 표현으로 근사하는 변환 | 파일 크기만으로 품질·속도·실행 메모리를 보장하지 않음 |
| arithmetic intensity | 특정 경계를 오간 byte당 연산량 | HBM과 PCIe 경계를 섞지 않기 |
| roofline | 계산 상한과 데이터 공급 상한을 연결한 성능 모형 | 실제 장치 성능을 측정한 값 |
| device plugin | Kubernetes에 장치 자원을 알리고 할당을 돕는 구성 | 컨테이너 안에 올바른 프레임워크까지 보장하는 것 |
| DRA | Dynamic Resource Allocation, 장치 요구·할당을 표현하는 Kubernetes 체계 | device plugin과 완전히 같은 API |
| MIG | Multi-Instance GPU, 지원 장치의 하드웨어 자원 분할 | 모든 GPU에서 같은 profile을 쓸 수 있다는 뜻 |
| MPS | Multi-Process Service, 여러 CUDA 프로세스 실행 공유를 돕는 기능 | client별 자원 제한을 구성할 수 있으나 MIG와 같은 하드웨어 격리는 아님 |
| time-slicing | 여러 작업이 장치 실행 시간을 나누는 방식 | GPU 메모리와 성능이 같은 비율로 보장되는 것 |
| topology | 장치·링크·NUMA 등의 연결 구조 | 총 GPU 수만으로 표현하기 |
| RDMA | 원격 메모리 접근을 지원하는 통신 방식 | GPU-to-GPU 경로가 자동 구성됐다는 뜻 |
| p99 | 정의한 표본 지연의 99번째 백분위 | 소수 표본의 정밀한 최악 지연 보장 |
| provenance | 데이터·모델·코드·설정의 출처와 생성 이력 | 파일 이름 하나 |
| reproducibility | 조건·절차·결과를 추적하고 다시 검증할 수 있는 성질 | 모든 하드웨어에서 bitwise 일치가 자동 보장됨 |

[02장](02-accelerator-software-and-execution.md), [09장](09-gpu-clusters-and-placement.md), [10장](10-observation-benchmarking-and-cost.md)의 용어다. 정의만 외운 뒤 구현의 버전·조건을 생략하지 않는다.
