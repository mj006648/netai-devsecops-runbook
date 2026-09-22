# AI 인프라: 숫자 한 번의 계산에서 GPU 클러스터와 서비스까지

작성·근거 확인: **2026-09-22**. [전체 학습 안내](../../../learning/README.md) · [AI 목차](../../README.md) · [검증 범위](VALIDATION.md)

기존 하드웨어·Linux·네트워크·데이터 시스템 교재는 AI 인프라를 배우는 기반이다. CPU와 메모리, 프로세스와 파일, 패킷과 분산 저장을 이해하면 모델 실행 중 데이터가 어디에서 기다리는지 추적할 수 있다. 이 교재는 그 위에 **모델 계산·학습·추론·GPU 자원 관리·서비스 운영**을 연결하는 다섯 번째 교재다.

AI 인프라를 잘 안다는 것은 GPU 제품 이름을 많이 안다는 뜻만은 아니다. 같은 모델과 품질 목표를 두고 필요한 메모리와 통신을 계산하고, 느린 구간을 관측으로 구별하며, 실패한 작업을 정해진 상태로 복구할 수 있어야 한다. 설명을 읽은 뒤에는 직접 계산하고 결과를 검증하는 과제가 남는다.

## 1. 어떤 질문에 답하는 교재인가?

- 모델, 파라미터, 텐서, 토큰, 배치가 각각 무엇인가?
- 학습 한 스텝에서 CPU·GPU·저장소가 어떤 일을 하는가?
- 가중치 파일은 작은데 GPU 메모리가 부족한 이유는 무엇인가?
- GPU 네 장을 꽂으면 왜 모델 메모리나 속도가 자동으로 네 배가 되지 않는가?
- DDP·FSDP·TP·PP는 무엇을 복제하고 무엇을 나누는가?
- 입력 문장이 길 때와 출력 문장이 길 때 병목은 어떻게 달라지는가?
- 첫 토큰 지연과 전체 토큰 처리량을 어떻게 함께 평가하는가?
- 학습 중단 후 가중치만 읽으면 정말 같은 작업을 이어가는가?
- Kubernetes의 GPU 한 개 요청은 어떤 자원 계약인가?
- 높은 GPU 사용률과 좋은 사용자 경험이 왜 다를 수 있는가?

## 2. 처음 읽는 사람을 위한 선수지식

모든 기존 교재를 끝내고 시작할 필요는 없다. 아래 연결 장을 오가며 읽는다.

| 필요한 개념 | 기존 교재 | AI에서 쓰이는 곳 |
| --- | --- | --- |
| byte·GB/GiB·행렬 계산 | [하드웨어 GPU·NPU](../../../hardware/learning/server-hardware/05-gpu-npu-execution.md) | 가중치·KV cache 크기와 연산량 |
| 프로세스·스레드·가상 메모리 | [Linux 프로그램과 프로세스](../../../linux/learning/linux-kernel/01-programs-processes-and-shell.md) | loader worker·rank·host memory |
| 메모리·NUMA·PCIe | [CPU·메모리·NUMA](../../../hardware/learning/server-hardware/02-cpu-memory-numa.md) | 데이터 공급·GPU/NIC 배치 |
| 대역폭·지연·패킷 | [네트워크 전송 계층](../../../kubernetes/networking/networking-foundations/03-transport-tcp-udp-quic.md) | collective·서비스 요청 |
| fsync·rename·객체 저장 | [Linux 읽기·쓰기](../../../kubernetes/storage/data-systems-foundations/01-linux-read-write.md) | 체크포인트 게시와 복구 |
| 관측과 가설 | [Linux 진단](../../../linux/learning/linux-kernel/07-observation-and-troubleshooting.md) | CPU·I/O·GPU·통신 병목 분리 |

수학은 단위 변환과 행렬의 행·열에서 출발한다. 미분은 작은 가중치 하나가 손실을 얼마나 바꾸는지부터 설명한다. 대학원 수준의 최적화·확률·분산 시스템 연구를 이 교재만으로 모두 대체하는 것은 아니다.

## 3. 전체 목차

| 장 | 내용 | 읽고 나서 할 일 |
| --- | --- | --- |
| 00 | [AI 작업과 모델](00-ai-workloads-and-models.md) | 데이터·모델·학습·추론·품질의 관계를 설명 |
| 01 | [텐서·역전파·Transformer](01-tensors-autograd-and-transformers.md) | shape를 추적하고 작은 가중치를 한 번 갱신 |
| 02 | [가속기 소프트웨어와 실행](02-accelerator-software-and-execution.md) | Python 호출에서 GPU kernel까지 경로를 그림 |
| 03 | [메모리·정밀도·용량](03-memory-precision-and-capacity.md) | 학습과 추론의 메모리 예산을 구별 |
| 04 | [학습과 입력 파이프라인](04-training-and-input-pipelines.md) | 배치 로딩·역전파·누적·갱신을 시간순 추적 |
| 05 | [분산 학습과 collective](05-distributed-training-and-collectives.md) | 병렬 방식별 복제·분할·통신 대상을 설명 |
| 06 | [LLM 추론과 KV cache](06-llm-inference-and-kv-cache.md) | prefill·decode와 요청당 상태 증가를 계산 |
| 07 | [서빙·스케줄링·SLO](07-serving-scheduling-and-slo.md) | 대기열·첫 토큰·취소·과부하를 함께 설계 |
| 08 | [데이터·모델·체크포인트](08-data-models-and-checkpoints.md) | 재시작에 필요한 상태와 게시 완료 조건을 정의 |
| 09 | [GPU 클러스터와 배치](09-gpu-clusters-and-placement.md) | 자원 할당·공유·토폴로지·실행의 차이를 설명 |
| 10 | [관측·벤치마크·비용](10-observation-benchmarking-and-cost.md) | 품질과 지연 조건을 고정한 비교 실험 작성 |
| 11 | [로컬 실습과 연구 과제](11-local-labs-and-research.md) | GPU 없이 계산·복구 모형을 실행하고 해석 |
| 12 | [용어 사전](12-glossary.md) | 약어의 뜻과 혼동하기 쉬운 경계를 찾기 |

입문 순서는 **00 → 01 → 02 → 03 → 11의 실습 1~3**이다. 그 뒤 학습 경로는 **04 → 05 → 08**, 추론 경로는 **06 → 07**로 갈라진다. 마지막에는 **09 → 10 → 11의 설계 과제**로 합친다.

## 4. 한 모델이 두 경로를 지나가는 지도

```text
데이터·코드·설정·모델 구조
        |
학습: 읽기 → 전처리 → forward → loss → backward → optimizer
        |                           ↕ 여러 rank의 통신
        └── 체크포인트·평가·모델 게시
                           |
추론: 요청 → tokenization → queue → 모델 실행 → 응답
                                  ↕
                         가중치·작업 상태·KV cache
```

모든 모델이 텍스트를 토큰화하거나 KV cache를 사용하는 것은 아니다. 이미지 분류, 추천, 음성, 확산 모델은 입력 형태·상태·반복 방식이 다르다. LLM은 구체적인 사례가 풍부해 자세히 다루지만, LLM의 실행 경로를 AI 전체의 정의로 삼지 않는다.

## 5. 기초가 쌓였는지 판정하는 기준

| 단계 | 산출물 | 스스로 확인할 기준 |
| --- | --- | --- |
| 이해 | 학습 한 스텝 그림 | 어떤 객체가 CPU RAM·장치 메모리·파일에 있는지 표시 |
| 계산 | 모델 메모리 예산표 | 가중치 외 상태와 GB/GiB, GPU별 최대량까지 명시 |
| 추적 | 느린 요청 시간표 | 대기·첫 토큰·후속 토큰·전체 응답의 경계 구별 |
| 진단 | 병목 가설 두 개 | 같은 낮은 GPU 사용률을 설명하는 다른 원인을 관측으로 분리 |
| 복구 | 재시작 상태 목록 | 모델뿐 아니라 optimizer·데이터 위치·난수 등 조건 기록 |
| 실험 | 비교 보고서 | 입력 길이·동시성·정밀도·품질·실패 요청·비용의 분모 고정 |

문제를 보고 정답 용어가 떠오르는 단계에서 멈추지 않는다. 숫자를 바꾸거나 GPU 수를 바꾸었을 때 자신의 설명이 어떻게 달라지는지까지 확인한다.

## 6. 실제 시스템으로 넘어갈 때

본문의 작은 Python 실습은 표준 라이브러리만 사용한다. GPU나 모델 다운로드 없이 계산식, 상태 차이, 큐의 의미를 확인하는 교육 모형이다. 이 실행 결과는 CUDA·NCCL·vLLM·GPU Operator의 동작 검증이나 성능 측정이 아니다.

실제 GPU 실습에서는 제품·드라이버·프레임워크·모델 revision·정밀도·데이터·GPU 토폴로지를 먼저 기록한다. 설치 명령이나 최신 기본값은 문서의 `stable`/`latest` 링크만 보고 영구 계약으로 취급하지 않는다. 현재 환경과 일치하는 릴리스 문서를 선택한다.

[GPU 운영 기록](../../../kubernetes/gpu/README.md)은 현장 사례로 읽는다. 특정 장비에서 해결한 명령을 다른 장비의 정답으로 복사하기 전에 증상·버전·복구 조건을 대조한다.

검증된 범위와 남은 실험은 [검증 기록](VALIDATION.md)에 구분한다.
