# 처음 배우는 인프라: 전기 신호에서 커널·네트워크·데이터 시스템·AI까지

이 학습 과정은 **컴퓨터 용어를 처음 만나는 사람**이 읽을 출발점과, 이미 기초를 아는 사람이 설계·실험으로 나아갈 경로를 함께 제공한다. 출발점에서는 비트·전압·명령·파일 같은 단어를 풀고, 뒤에서는 같은 대상을 주소 변환·큐·복구·격리·측정의 관점으로 다시 본다.

읽기만으로 특정 학위 수준이나 운영 숙련을 보장할 수는 없다. 여기서 목표로 삼는 실력은 **원리를 자기 말로 설명하고, 작은 예제를 손으로 계산하고, 안전한 실습으로 확인하고, 관측하지 않은 것은 구별해서 말하는 능력**이다. 대학원 단계에서는 여기에 기존 연구 비교, 반례 구성, 재현 가능한 실험이 더해진다.

## 다섯 권의 교재와 맡은 질문

| 교재 | 가장 아래에서 시작하는 질문 | 연결되는 심화 주제 |
| --- | --- | --- |
| [서버 하드웨어](../hardware/learning/server-hardware/README.md) | 전기 신호가 어떻게 0·1, 계산과 저장이 되는가? | CPU·DRAM·NUMA·PCIe·GPU/NPU·RAID·전력·냉각 |
| [Linux·운영체제·커널](../linux/learning/linux-kernel/README.md) | 여러 프로그램이 한 컴퓨터를 어떻게 나누어 쓰는가? | 부팅·syscall·스케줄링·메모리·동기화·드라이버·격리 |
| [네트워크](../kubernetes/networking/networking-foundations/README.md) | 신호로 표현한 바이트가 다른 컴퓨터에 어떻게 도착하는가? | 스위치·라우터·TCP/IP·DNS/TLS·Linux 패킷 경로·eBPF·Cilium |
| [데이터 시스템](../kubernetes/storage/data-systems-foundations/README.md) | 파일을 읽고 쓴다는 것은 어떤 작업이며 언제 저장 완료인가? | 파일시스템·SSD·HDFS·Ceph/S3·DB·Parquet·Iceberg·논문 실험 |
| [AI 인프라](../ai/learning/ai-infrastructure/README.md) | 모델의 숫자 계산이 어떻게 GPU 작업과 사용자 응답이 되는가? | 텐서·역전파·메모리·분산 학습·LLM 추론·서빙·복구·클러스터 |

네트워크 교재가 `kubernetes/` 아래 있다고 Kubernetes부터 알아야 하는 것은 아니다. 앞부분은 일반 네트워크 기초이며 Kubernetes는 뒤쪽 응용이다. Linux 교재와 하드웨어 교재도 특정 랩 장비가 없어도 학습할 수 있다. A7 같은 실제 사례는 기본 원리 뒤에 읽는다.

## 1. 정말 처음이라면 이 순서로 읽는다

날짜나 진도량 대신 **통과할 수 있는 과제**로 다음 단계를 정한다. 한 절을 여러 번 읽어도 정상이다. 막히는 용어가 나오면 본문 문장과 사전의 정의를 함께 본다.

| 단계 | 읽을 곳 | 다음으로 가기 전 직접 할 일 |
| --- | --- | --- |
| A. 정보의 재료 | 하드웨어 [00](../hardware/learning/server-hardware/00-physical-bits-to-computer.md) | `13`을 2진수로 바꾸고 전압·전류·전력의 차이를 말한다 |
| B. 실행의 주체 | Linux [00](../linux/learning/linux-kernel/00-why-operating-systems.md), [01](../linux/learning/linux-kernel/01-programs-processes-and-shell.md) | 프로그램·프로세스·스레드·셸·커널을 한 그림에 놓는다 |
| C. 한 컴퓨터 내부 | 하드웨어 [01](../hardware/learning/server-hardware/01-system-map.md)–[03](../hardware/learning/server-hardware/03-pcie-slots-switches.md) | CPU→RAM→PCIe→NIC/SSD 경로와 공유 링크를 그린다 |
| D. 값과 바이트 | 데이터 [00](../kubernetes/storage/data-systems-foundations/00-map-and-vocabulary.md), [00a](../kubernetes/storage/data-systems-foundations/00a-bytes-payload-and-packets.md) | 문자 수·바이트 수·레코드 수·패킷 수를 구별한다 |
| E. 파일 저장 | 데이터 [01](../kubernetes/storage/data-systems-foundations/01-linux-read-write.md), [02](../kubernetes/storage/data-systems-foundations/02-filesystems-block-devices.md), [08](../kubernetes/storage/data-systems-foundations/08-guided-labs.md) | 쓰기·flush·fsync·rename을 순서대로 설명하고 작은 파일 실습을 한다 |
| F. 컴퓨터 사이 | 네트워크 [00](../kubernetes/networking/networking-foundations/00-signals-frames-and-packets.md)–[04](../kubernetes/networking/networking-foundations/04-dns-http-tls.md) | 다른 서브넷으로 갈 때 MAC·IP·포트가 각각 어떻게 쓰이는지 추적한다 |
| G. 커널 내부 | Linux [02](../linux/learning/linux-kernel/02-boot-syscalls-and-interrupts.md)–[06](../linux/learning/linux-kernel/06-isolation-security-and-containers.md) | syscall과 interrupt, TLB miss와 page fault, mutex와 atomic을 구별한다 |
| H. 운영 경로 | 네트워크 [05](../kubernetes/networking/networking-foundations/05-linux-packet-path.md)–[08](../kubernetes/networking/networking-foundations/08-troubleshooting-and-labs.md), Linux [07](../linux/learning/linux-kernel/07-observation-and-troubleshooting.md) | 패킷이 지나가는 hook·queue·namespace와 관측 위치를 설명한다 |
| I. 저장 서비스 | 데이터 [03](../kubernetes/storage/data-systems-foundations/03-hdfs-distributed-files.md)–[06](../kubernetes/storage/data-systems-foundations/06-parquet-arrow-iceberg.md) | 복제·WAL·snapshot의 성공 응답과 장애 범위를 구별한다 |
| J. 가속·설계·연구 | 하드웨어 [05](../hardware/learning/server-hardware/05-gpu-npu-execution.md)–[10](../hardware/learning/server-hardware/10-a7-design-exercises.md), 데이터 [07](../kubernetes/storage/data-systems-foundations/07-measurement-and-paper-reading.md)·[09](../kubernetes/storage/data-systems-foundations/09-study-roadmap-and-questions.md) | 병목 가설 하나, 반례 하나, 공정한 비교 실험 하나를 작성한다 |
| K. AI 작업 연결 | AI [00](../ai/learning/ai-infrastructure/00-ai-workloads-and-models.md)–[03](../ai/learning/ai-infrastructure/03-memory-precision-and-capacity.md), [실습](../ai/learning/ai-infrastructure/11-local-labs-and-research.md) | 한 번의 학습 계산과 추론 메모리 예산을 손으로 검산한다 |
| L. AI 학습·서비스 | AI [04](../ai/learning/ai-infrastructure/04-training-and-input-pipelines.md)–[10](../ai/learning/ai-infrastructure/10-observation-benchmarking-and-cost.md) | 분산 실행·서빙 지연·체크포인트 복구·자원 배치의 조건을 설명한다 |

한 번 읽고 모든 것을 기억할 필요는 없다. 같은 `주소`도 처음에는 위치를 구별하는 번호로, 다음에는 가상 주소·LBA·IP 주소처럼 서로 다른 관리자의 이름 공간으로 이해하게 된다.

## 2. 비유와 정확한 설명을 함께 읽는 법

“RAM은 책상이고 SSD는 서랍이다”라는 비유는 작업용 공간과 보관 공간의 차이를 떠올리는 데 도움을 준다. 하지만 책상의 종이가 사라지는 조건과 DRAM의 전원 의존성은 같지 않고, CPU가 메모리를 읽는 방식도 사람이 서랍을 여는 방식과 다르다.

각 개념을 다음 다섯 문장으로 바꾸어 본다.

1. **대상:** 무엇을 부르는 이름인가? 예: page cache는 Linux가 파일 데이터를 RAM에 보관하는 구조다.
2. **문제:** 왜 필요한가? 예: 저장장치에서 같은 내용을 반복 읽는 비용을 줄인다.
3. **동작:** 누가 무엇을 옮기거나 갱신하는가? 예: 읽기 miss 뒤 데이터를 채우거나 쓰기로 dirty 상태를 만든다.
4. **경계:** 무엇까지 보장하는가? 예: cache에서 읽힌다고 정전 후 보존을 증명하지는 않는다.
5. **증거:** 무엇을 관측하면 설명을 확인할 수 있는가? 예: syscall 순서와 내용 일치를 관측하되 전원 내성은 별도 검증한다.

다섯 문장 중 하나가 비면 “외운 단어는 있는데 작동을 설명하지 못하는” 지점일 수 있다. 사전은 이름을 찾는 곳이고 본문은 인과관계를 배우는 곳이다.

## 3. 필요한 수학을 계산에서 배운다

이 교재를 시작할 때 미적분을 먼저 끝낼 필요는 없다. 초반에는 자리수·나눗셈·단위 변환·비율을 사용하고, 실험 단계에서 평균·분포·확률과 측정 오차로 확장한다.

### 나눗셈은 주소의 두 부분을 찾는다

페이지 크기 4,096 B, 주소 9,000이라면 `9000 = 2 × 4096 + 808`이다. 페이지 번호 2와 내부 위치 808로 나누었다. 파일 offset을 block과 내부 위치로 바꿀 때도 같은 몫·나머지 계산을 쓰지만, 두 page/block이 같은 객체가 되는 것은 아니다.

### 단위가 맞아야 더하거나 비교할 수 있다

`100 Gbit/s ÷ 8 = 12.5 GB/s`다. 초당 비트와 초당 바이트를 맞춘 것이다. 여기서 `GB`는 decimal 10^9 bytes이고, `GiB`는 2^30 bytes다. 반면 `100 GB + 10 GB/s`는 용량과 속도를 더하므로 용도가 없다. PCIe 수치가 양방향 합산인지 한 방향인지도 확인해야 한다.

교육용으로 처리량 2 GB/s에서 데이터 6 GB를 옮기면 순수 전송 시간 하한은 `6 GB ÷ 2 GB/s = 3 s`다. 실제에는 대기·메타데이터·프로토콜·경합이 더해질 수 있다. 산술적 하한과 실측 예측을 구분한다.

### 병목을 바꾸지 않으면 전체 속도는 거의 그대로다

작업 100 ms 중 80 ms는 직렬 준비, 20 ms는 GPU 계산이라고 하자. GPU 계산을 10배 빠르게 해도 `80 + 20/10 = 82 ms`, 전체 배속은 `100/82 ≈ 1.22`다. 이것은 겹침이 없고 다른 비용이 유지되는 단순 모델이다. 왜 더 빠른 장치를 꽂아도 전체 작업은 조금만 빨라지는지 설명할 수 있다.

### 평균만으로는 사용자가 겪는 느린 요청을 알 수 없다

9개 요청이 1 ms이고 1개가 91 ms이면 평균은 10 ms다. 평균 10 ms인 요청 10개와 총합은 같지만 사용 경험은 다르다. 꼬리 지연을 보려면 분포와 충분한 표본을 함께 봐야 한다. 10개 표본으로 정밀한 p99 성능을 주장하지 않는다. [측정 장](../kubernetes/storage/data-systems-foundations/07-measurement-and-paper-reading.md)에서 계산 규칙과 반복 실험을 배운다.

## 4. 역사는 “처음 누가 만들었나”와 “왜 필요했나”를 나눠 읽는다

아래는 모든 발명을 한 사람에게 귀속하는 연표가 아니다. 해당 시스템이 해결하려던 제약을 읽는 출발점이다. 실제 설계들은 서로 영향을 주며 겹쳐 발전했다.

| 흐름 | 해결하려던 제약 | 오늘의 개념으로 이어지는 지점 | 원전 |
| --- | --- | --- | --- |
| 저장 프로그램 컴퓨터 | 작업을 바꿀 때 연결·제어를 바꾸는 비용 | 명령도 메모리에 놓고 가져와 해석한다는 원리 | [Computer History Museum의 저장 프로그램 구상 설명](https://www.computerhistory.org/revolution/birth-of-the-computer/4/88) |
| Unix의 초기 발전 | 작은 시스템에서 대화형 개발과 파일·프로세스 도구 구성 | 파일 descriptor, 계층적 이름, 작은 도구의 조합 | [Dennis Ritchie의 Unix 발전사](https://pdos.csail.mit.edu/6.828/2008/readings/ritchie79evolution.html) |
| Unix와 C | 특정 장치에 묶인 어셈블리 구현의 부담 | 시스템 언어와 이식 가능한 운영체제 구현 | [The Open Group의 Unix 역사](https://www.unix.org/unix_history.html) |
| GNU 최초 발표, 1983 | 사용·수정·공유할 수 있는 Unix 호환 운영 환경 | 커널과 별개인 사용자 도구·컴파일러·라이브러리 생태계 | [GNU 최초 발표 원문](https://www.gnu.org/gnu/initial-announcement.en.html) |
| Linux 초기 공개, 1991 | i386용 Unix와 비슷한 자유 커널의 개발 | 커널과 GNU 도구 등을 결합한 실행 환경 | [Linux 0.01 릴리스 노트](https://www.kernel.org/pub/linux/kernel/Historic/old-versions/RELNOTES-0.01) |
| 분산 저장 시스템 | 한 장치 용량·처리량·장애 범위를 넘어서는 저장 | metadata/data 분리, 복제, 장애 가정 | [GFS 원전](https://research.google/pubs/the-google-file-system/) |
| 현대 패킷 필터·eBPF | 모든 관측·정책마다 커널 전체를 새로 고치는 부담 | 제한된 실행 지점에 검증된 프로그램과 상태 연결 | [커널 BPF 문서](https://docs.kernel.org/bpf/), [네트워크 eBPF 장](../kubernetes/networking/networking-foundations/06-ebpf-xdp-tc.md) |

Unix는 처음부터 C로 만든 완제품이 아니었다. 초기 구현에서 발전하여 1973년 C로 다시 작성한 역사가 있다. Linux도 처음 공개되었을 때 오늘의 완성된 배포판 전체였던 것은 아니다. 출발점의 한계를 보면 현재의 이름과 구현을 과거에 그대로 투영하는 실수를 줄일 수 있다.

역사적 자료의 성능 수치는 당시 하드웨어·workload에 대한 것이다. 설계 동기는 배울 수 있지만 수십 년 전 수치를 지금의 SSD나 클라우드에 그대로 적용하지 않는다.

## 5. 기초 교재를 잇는 한 번의 저장 요청

사용자가 웹 API에 문자열 `가A`를 저장한다고 가정하자. UTF-8에서는 4바이트이며 HTTP 헤더·TLS·전송 헤더 크기는 별도다. 다음은 가능한 **특정 구현 예시**이지 모든 웹 서비스의 고정 경로가 아니다.

1. 프로그램이 문자열을 바이트로 바꾼다. 이 작업은 CPU 명령으로 실행되고 RAM을 사용한다.
2. 프로그램이 소켓으로 요청을 보낸다. Linux 네트워크 스택과 장치 드라이버가 전송을 준비한다.
3. NIC가 전기·광 신호를 내보낸다. Ethernet 구간에서는 스위치가 프레임을, 다른 IP 네트워크 사이에서는 라우터가 패킷을 전달한다.
4. 서버 NIC와 커널이 바이트를 수신한다. TCP 스트림에서 요청 경계를 찾고, 보호된 통신이라면 TLS와 애플리케이션 처리가 진행된다.
5. 서버 프로세스가 파일을 쓰거나 DB 트랜잭션을 요청한다. 사용자 버퍼, page cache, DB buffer pool 등은 선택한 경로에 따라 다르다.
6. 약속한 동기화·복제·commit 조건을 충족한 뒤 응답한다. 성공 응답의 의미는 해당 서비스가 정의한다.
7. 응답이 유실되면 클라이언트는 서버 처리 여부를 모를 수 있다. 이때 재시도와 중복 방지 설계가 필요하다.

이 요청에서 **CPU cache line, 메모리 page, 파일시스템 block, Ethernet frame, TCP sequence, DB page**는 서로 다른 단위다. 값이 여러 계층을 통과한다고 같은 물리 조각 하나가 이름만 바뀌는 것은 아니다. 복사·분할·병합·암호화·주소 변환이 사이에 일어난다.

## 6. 어느 수준까지 이해했는지 확인하는 과제

“읽었다”와 “할 수 있다”를 나누기 위한 자체 평가다. 점수는 자격증이나 학위 판정이 아니다.

| 단계 | 과제 | 통과에 필요한 내용 |
| --- | --- | --- |
| 설명 | `write 성공 = 정전 안전`이 아닌 이유를 초보자에게 설명 | buffer·cache·동기화·장애 범위를 구별 |
| 계산 | /26 IPv4 범위, PCIe 대역폭, 페이지 주소 변환 계산 | 단위·가정·예약 범위·예외까지 기록 |
| 추적 | 파일 한 글자 저장과 라우터 한 홉 통과를 시간표로 작성 | 누가 어떤 이름·주소·상태를 바꾸는지 명시 |
| 관찰 | 작은 로컬 실습의 예상과 실제 결과를 비교 | 성공 코드뿐 아니라 내용·호출 순서·정리까지 확인 |
| 진단 | “CPU는 한가로운데 요청이 느림”의 가설 둘을 분리 | 두 가설을 구별할 관측과 예상 결과 제시 |
| 설계 | 장애 영역·처리량·복구 목표가 있는 서버·저장 경로 설계 | 공유 병목·필요 증거·실패 후 동작까지 설명 |
| 연구 | 기존 방식과 비교할 변경 하나를 정의 | 공정한 기준군·정확성 조건·반례·재현 절차·한계 포함 |

각 과제에서 `0: 용어만 나열`, `1: 원리는 설명`, `2: 예제를 계산/추적`, `3: 관측 근거와 한계까지 설명`으로 스스로 평가한다. 낮은 항목의 연결 장으로 돌아간다. 모든 분야의 최고 점수를 한 번에 달성할 필요는 없다.

## 7. 연구 단계는 긴 설명 뒤에 자동으로 생기지 않는다

연구 질문의 예는 “eBPF가 빠른가?”보다 구체적이어야 한다. 예를 들어 **같은 정책·입력·관측 범위를 유지할 때 패킷 처리 지점을 바꾸면 CPU 비용과 p99 지연이 어떻게 달라지는가?**라고 묻는다. 이때 drop·redirect의 의미와 관측 손실이 같지 않으면 속도만 비교할 수 없다.

실험 계획에는 다음 여섯 항목을 쓴다.

1. 기존 방식이 지불하는 구체적인 비용.
2. 바꿀 메커니즘 하나와 그대로 둘 조건.
3. 입력 분포·요청 크기·동시성·장애 가정.
4. 정확성과 성능의 독립 판정 기준.
5. 기대한 이득이 사라지거나 악화될 반례.
6. 버전·설정·원시 결과·집계 코드·실행 횟수.

데이터 [연구 경로](../kubernetes/storage/data-systems-foundations/09-study-roadmap-and-questions.md), Linux [실습·연구](../linux/learning/linux-kernel/08-labs-and-research.md), 네트워크 [설계 문제](../kubernetes/networking/networking-foundations/09-design-exercises-and-glossary.md)를 이용해 실제 산출물을 만든다.

## 8. 실습 결과의 범위를 지킨다

교재의 실행 예제는 기본적으로 Python 표준 라이브러리, 메모리 내 모형, 짧은 로컬 조회, 작은 임시 파일을 사용한다. 분산 서비스 설치, 운영 네트워크 변경, eBPF 프로그램의 실제 부착, 전역 cache 제거, 디스크 포맷과 전원 차단을 학습 시작 조건으로 삼지 않는다.

예제 코드 실행 성공은 그 예제가 확인한 계약의 근거다. 모델 계산은 실제 하드웨어 측정이 아니고, readback은 전원 장애 시험이 아니며, 로컬 패킷 파싱은 실제 네트워크 전체를 검증한 것이 아니다. 더 깊은 실험으로 넘어갈 때는 격리 환경·복구 방법·자원 예산·완료 조건을 먼저 명시한다.

[2026-09-22 교재·실습 검증 기록](VALIDATION.md)에서 실행한 검사와 검증하지 않은 범위를 확인할 수 있다.

## 9. AI 인프라로 이어가는 경로

앞의 네 기초 교재는 AI 인프라를 배우는 기반이다. 모델이 사용하는 숫자·메모리·프로세스·파일·통신을 설명할 수 있다면 AI 실행을 이해할 준비가 된 것이다. 여기에 모델 계산과 학습 상태, GPU별 메모리 예산, 요청 스케줄링과 성능 측정이 더 필요하다.

[AI 인프라 교재](../ai/learning/ai-infrastructure/README.md)는 이 연결을 맡는다. 기존 네 권을 모두 완독해야 시작하는 구조는 아니다. CPU·RAM·byte·프로세스가 익숙하면 AI 00–03장을 읽고, 막히는 기초 개념을 연결 문서에서 보충한다.

- 학습 중심: 입력 → forward → loss → backward → optimizer → 분산 gradient 통신 → 체크포인트를 추적한다.
- 추론 중심: 요청 → tokenization → 대기열 → prefill·decode → 스트리밍·취소를 추적한다. 이 경로는 autoregressive LLM 사례다.
- 운영 중심: 모델 품질을 고정하고 GPU 메모리·데이터 공급·통신·지연 목표·복구·비용을 함께 비교한다.

AI [로컬 실습](../ai/learning/ai-infrastructure/11-local-labs-and-research.md)은 GPU 없이 gradient 검산, 크기가 다른 배치의 평균, KV cache 용량, collective 통신량, 큐 지연, 복구 상태의 차이를 확인한다. 실제 GPU 학습·서빙은 이 계산 모형 다음의 별도 실험이다.

[AI 교재 검증 기록](../ai/learning/ai-infrastructure/VALIDATION.md)에서 추가 교재의 검사를 확인한다. 위의 기존 네 교재 검증 기록과 범위를 구분한다.
