# 공통 용어사전: 전문용어를 뜻과 역할로 다시 찾기

[첫 지도](START-HERE.md) · [통합 목차](README.md)

현장에서 자주 쓰는 영어·약어를 한국어 뜻과 함께 정리했다. 이름을 외우기 위한 목록보다는 읽다가 잠깐 의미를 확인하는 용도다. 동작 과정, 계산, 예외는 표 아래의 해당 교재에서 이어서 설명한다. 같은 단어의 뜻이 계층마다 달라지면 별도 항목으로 나누었다.

## 1. 컴퓨터와 실행의 기본

| 용어 | 무엇을 가리키고 무엇을 하는가? | 작은 예 |
| --- | --- | --- |
| 인프라, infrastructure | 프로그램의 실행을 받쳐 주는 장치·저장·통신·운영 기반 | AI 계산용 서버와 연결망 |
| 서버, server | 요청을 처리하는 역할, 또는 그 역할의 컴퓨터 | 웹 요청을 받아 답을 반환 |
| 서비스, service | 사용자나 다른 프로그램에 제공하는 기능 | 파일 저장 서비스 |
| 노드, node | 연결된 시스템에서 구별하는 한 컴퓨터나 실행 자원 | 클러스터의 서버 한 대 |
| 클러스터, cluster | 여러 노드를 함께 운영하는 묶음 | 서비스를 여러 서버에 분산 |
| 프로그램, program | 컴퓨터가 실행할 명령들의 묶음 | 브라우저 실행 파일 |
| 프로세스, process | 실행 중인 프로그램의 코드·상태·자원 관리 주체 | 같은 프로그램을 두 번 시작한 실행 주체 |
| 스레드, thread | 프로세스 안의 실행 흐름 | 입력 처리와 저장을 나누는 실행 흐름 |
| 운영체제, OS(Operating System) | 프로그램 실행과 자원 사용을 관리하는 소프트웨어 | CPU 시간과 메모리 배정 |
| 커널, kernel | 운영체제의 중심에서 자원·장치를 관리하는 부분 | Linux 커널 |
| 셸, shell | 입력한 명령을 해석해 프로그램을 실행하는 도구 | Bash에 파일 조회 명령 입력 |
| 드라이버, driver | 운영체제와 특정 장치 사이의 제어·통신 소프트웨어 | GPU 드라이버 |
| API(Application Programming Interface) | 프로그램 사이에 기능을 요청하는 형식과 약속 | 파일 읽기 함수나 웹 요청 |
| 런타임, runtime | 프로그램·장치 실행에 필요한 지원 기능 | GPU 메모리 할당과 실행 요청 |
| 시스템 호출, syscall | 사용자 프로그램이 커널 기능을 요청하는 진입 방식 | 파일을 여는 open |
| 인터럽트, interrupt | 장치 등에서 CPU에 처리할 사건을 알리는 방식 | 수신 데이터 도착 알림 |
| 스케줄러, scheduler | 실행 대상을 골라 자원을 배정하는 구성 요소 | OS가 다음 실행 스레드를 고름 |
| 문맥 교환, context switch | 실행 대상을 바꾸며 상태를 저장·복원하는 일 | 다른 스레드에 CPU 시간 제공 |

자세한 실행 흐름은 [Linux·운영체제 교재](../linux/learning/linux-kernel/README.md)에서 배운다. OS 스레드와 CUDA 스레드는 서로 다른 실행 모델이다.

## 2. 메모리와 장치 연결

| 용어 | 무엇을 가리키고 무엇을 하는가? | 작은 예 |
| --- | --- | --- |
| CPU(Central Processing Unit) | 프로그램 명령을 실행하는 중앙처리장치 | 요청 해석과 전처리 |
| 코어, core | 물리적으로 명령을 실행하는 CPU 자원 | CPU 한 개 안의 여러 코어 |
| 소켓, socket | 이 문맥에서는 메인보드에 CPU를 꽂는 자리 | 두 소켓 서버 |
| RAM(Random Access Memory) | 실행 중인 명령·데이터를 보관하는 주메모리 | 프로그램 입력 버퍼 |
| DRAM(Dynamic Random Access Memory) | 전하로 비트를 저장하고 주기적으로 복원하는 메모리 | 서버 DDR 메모리 칩 |
| SRAM(Static Random Access Memory) | 전원을 공급하는 동안 회로 상태로 값을 유지하는 메모리 | CPU 캐시·GPU 내부 저장소 |
| 클록, clock·Hz | 동작 타이밍을 맞추는 반복 신호·초당 반복 주기 수 | 3200MHz는 초당 32억 주기 |
| DDR(Double Data Rate) | 클록 신호의 상승·하강 양쪽을 활용해 한 주기에 두 번 전송하는 DRAM 기술 계열 | DDR4·DDR5의 숫자는 세대 |
| MT/s(Megatransfers per second) | 초당 백만 번의 전송 횟수 | 6400MT/s를 6400MHz나 6400MB/s로 읽지 않음 |
| DIMM(Dual In-line Memory Module) | 슬롯에 꽂는 메모리 모듈 기판 | 여러 DRAM 칩이 올라간 모듈 |
| UDIMM(Unbuffered DIMM)·RDIMM(Registered DIMM) | 명령·주소 신호의 등록·완충 회로 유무로 구별하는 모듈 종류 | 시스템 지원 없이 두 종류를 혼용하지 않음 |
| SO-DIMM(Small Outline DIMM) | 작은 메모리 모듈 형태 | 일부 노트북·소형 시스템 |
| LPDDR(Low Power DDR) | 저전력 기기용의 별도 메모리 규격 계열 | 일반 DDR DIMM 슬롯의 교체품으로 가정하지 않음 |
| 슬롯, slot | 부품을 꽂는 물리 커넥터 | DIMM 슬롯·PCIe 슬롯 |
| 채널, channel | 메모리 컨트롤러와 모듈 사이 데이터 경로 | 독립 경로에 요청을 분산 |
| 서브채널, subchannel | 데이터 경로 내부의 하위 경로 | DDR5의 두 32비트 데이터 경로 |
| 메모리 랭크, rank | 함께 선택되어 데이터 폭을 제공하는 DRAM 장치 묶음 | 1R·2R 모듈 조직 |
| x4·x8 조직 | DRAM 장치 하나의 병렬 데이터 입출력 폭 | x8 장치가 8비트 담당 |
| 뱅크 그룹, bank group | DRAM 칩 안에서 여러 뱅크를 묶은 조직 | 그룹에 따른 명령 간격 차이 |
| DRAM 뱅크, bank | 독립적으로 행 상태를 관리하는 내부 구역 | 뱅크마다 행을 열어 준비 |
| 행·열, row·column | DRAM에서 함께 선택하는 줄과 그 안의 위치 | 행을 연 뒤 열을 골라 읽기 |
| 행 버퍼, row buffer | 활성 행의 데이터를 유지하는 감지 회로 상태 | 같은 열린 행의 읽기 재사용 |
| 리프레시, refresh | DRAM의 약해지는 전하를 복원하는 동작 | 유지 작업 동안 일부 접근 대기 |
| ECC(Error-Correcting Code) | 여분의 정보로 일정 범위의 오류를 검출·정정하는 기법 | 모든 고장을 복구하는 것은 아님 |
| 캐시, cache | 반복 사용을 위해 가까이 보관하는 데이터와 관리 구조 | 다시 읽을 값을 CPU 가까이 저장 |
| 캐시 히트·미스 | 해당 캐시에 값이 있음·없음 | 미스이면 다른 계층에서 찾기 |
| 캐시 라인, cache line | 캐시가 데이터를 다루는 일정 크기 묶음 | 한 바이트 요청과 전송 단위가 다름 |
| 버퍼, buffer | 전달·처리할 데이터를 잠시 모으는 공간 | 파일 읽기 버퍼 |
| 페이지, page | 가상 주소·메모리를 관리하는 일정 크기 구획 | 4KiB 페이지라는 가정으로 계산 |
| TLB(Translation Lookaside Buffer) | 최근 주소 변환 결과와 권한을 보관하는 캐시 | 가상 페이지를 물리 페이지로 변환 |
| 페이지 폴트, page fault | 정상 주소 접근을 진행할 수 없어 OS 처리가 필요한 예외 | 새 페이지 할당 또는 오류 처리 |
| NUMA(Non-Uniform Memory Access) | CPU와 메모리의 위치에 따라 접근 비용이 다른 구조 | 다른 소켓의 RAM 접근 |
| PCIe(Peripheral Component Interconnect Express) | CPU와 GPU·NIC·NVMe 장치 등의 연결 표준 | 슬롯과 공유 업링크 |
| 레인, lane | PCIe 데이터 전송의 기본 연결 단위 | x16은 16레인 링크 |
| 업링크, uplink | 상위 장치 쪽으로 이어지는 링크 | 여러 카드가 공유하는 스위치 연결 |
| DMA(Direct Memory Access) | 장치가 CPU의 값 하나씩 복사 없이 메모리에 데이터를 전달하는 기능 | NIC의 수신 버퍼 쓰기 |

위치와 읽기 과정은 [CPU·DRAM·NUMA](../hardware/learning/server-hardware/02-cpu-memory-numa.md), 연결 경로는 [PCIe](../hardware/learning/server-hardware/03-pcie-slots-switches.md)에서 설명한다.

## 3. GPU·AI 실행

| 용어 | 무엇을 가리키고 무엇을 하는가? | 작은 예 |
| --- | --- | --- |
| GPU(Graphics Processing Unit)·NPU(Neural Processing Unit) | 병렬 계산·신경망 계산에 활용하는 가속기 | 행렬 계산을 맡음 |
| 호스트·디바이스, host·device | 작업을 준비하는 CPU 쪽 환경과 계산 장치 | CPU에서 GPU로 입력 복사 |
| VRAM(Video Random Access Memory) | GPU 가까이 배치한 장치 메모리의 통칭 | 모델 가중치 저장 |
| GDDR(Graphics Double Data Rate)·HBM(High Bandwidth Memory) | 가속기 메모리에 쓰는 DRAM 기술·배치 계열 | 기판의 GDDR, 적층 HBM |
| GPU 커널, kernel | GPU 스레드들이 실행하는 함수 | 배열 덧셈 함수 |
| 그리드·블록, grid·block | 한 GPU 함수 실행의 작업 전체와 스레드 묶음 | 256스레드 블록 네 개 |
| 워프, warp | NVIDIA GPU에서 함께 진행하는 32스레드 묶음 | 준비된 워프의 명령 실행 |
| SM(Streaming Multiprocessor) | GPU 내부에서 블록의 실행 자원을 제공하는 단위 | 워프의 명령을 진행 |
| 공유 메모리, shared memory | 일반 CUDA 블록이 함께 사용하는 칩 내부 저장 공간 | 행렬 조각을 재사용 |
| 공유 메모리 뱅크, bank | GPU 내부 공유 메모리의 병렬 접근 구역 | DRAM 행 상태와 다른 구조 |
| 점유율, occupancy | 지원 최대 워프 중 자원을 확보해 머무는 워프의 비율 | GPU 사용률과 다른 수치 |
| 텐서, tensor | 여러 축을 가진 숫자 배열 | 행·열이 있는 행렬 |
| 형상, shape | 텐서 각 축의 길이 | 2행×3열은 (2,3) |
| 자료형, dtype | 값을 저장·계산하는 표현 형식 | FP32·BF16 |
| 가중치, weight | 학습으로 정하는 모델의 계산 숫자 | 입력에 곱하는 계수 |
| 활성값, activation | 모델 안에서 입력을 처리한 중간 결과 | 계층 출력 텐서 |
| 임베딩, embedding | 항목을 숫자 벡터로 바꾼 표현 | 토큰 번호를 벡터로 변환 |
| 배치, batch | 함께 처리하는 여러 입력의 묶음 | 요청 여덟 개를 함께 계산 |
| 순전파·역전파, forward·backward | 예측 계산과 그 계산의 변화량을 역방향으로 구하는 과정 | 손실에 대한 가중치의 영향 계산 |
| 손실, loss | 예측과 목표의 차이를 나타내는 값 | 정답과 예측 오차 |
| 기울기, gradient | 어떤 값 변화에 따른 함수의 변화 방향·크기 | 손실이 줄도록 가중치 수정 |
| 최적화기, optimizer | 기울기와 상태를 이용해 가중치를 갱신하는 방식 | SGD·Adam |
| 토큰, token | 모델이 텍스트를 입력·출력으로 처리하는 단위 | 한 단어와 항상 같지는 않음 |
| 토큰화, tokenization | 문자열을 토큰 번호 배열로 바꾸는 과정 | 모델별 분할 규칙 적용 |
| 프리필·디코드, prefill·decode | 입력 문맥 계산과 다음 출력 토큰의 반복 생성 | 긴 질문 처리 후 답 생성 |
| KV 캐시 | 이전 토큰의 Key·Value 숫자 배열을 재사용하려고 저장하는 공간 | 문맥 길이·동시 요청에 따라 증가 |
| 샤드·복제본, shard·replica | 나누어 가진 부분과 같은 내용을 별도로 가진 것 | 가중치 분할과 모델 복제 |
| 분산 랭크, rank | 통신 그룹의 참가자 번호 | rank 0~3; DIMM rank와 무관 |
| 월드 크기, world size | 같은 분산 실행 그룹의 참가자 수 | 참가자 네 개면 4 |
| 집합 통신, collective | 여러 참가자가 함께 수행하는 통신 연산 | 결과를 모으고 합산해 공유 |
| 체크포인트, checkpoint | 중단 뒤 복구에 필요한 상태의 저장본 | 가중치·최적화기 상태 등 |

실행 구조는 [GPU·NPU](../hardware/learning/server-hardware/05-gpu-npu-execution.md), 모델과 학습은 [AI 인프라 교재](../ai/learning/ai-infrastructure/README.md)에서 계산과 연결한다.

## 4. 네트워크와 저장

| 용어 | 무엇을 가리키고 무엇을 하는가? | 작은 예 |
| --- | --- | --- |
| 프로토콜, protocol | 서로 통신할 때 지키는 형식과 절차 | TCP·HTTP |
| 페이로드, payload | 해당 계층에서 전달하려는 내용 | HTTP의 본문 |
| 헤더, header | 내용을 전달·해석하기 위한 부가 정보 | 주소와 길이 |
| 프레임·패킷, frame·packet | 링크·네트워크 계층의 전송 단위 | Ethernet 프레임과 IP 패킷 |
| Ethernet | 같은 링크에서 장치끼리 데이터를 전달하는 네트워크 표준 계열 | 구리 케이블 또는 광 링크 |
| NIC(Network Interface Card) | 컴퓨터와 네트워크 사이의 송수신 장치 | 서버의 네트워크 카드·내장 포트 |
| RJ45·8P8C | 현장에서 RJ45라 부르는 Ethernet 커넥터는 보통 8개 위치·8개 접점을 가진 8P8C | 구리 Ethernet 케이블의 플러그 |
| SFP(Small Form-factor Pluggable)·QSFP(Quad Small Form-factor Pluggable) | 장치 포트에 꽂는 모듈·플러그의 형태 계열 | 광 모듈이나 일체형 케이블 끝 |
| 트랜시버, transceiver | 신호를 송신하고 수신하는 장치 | 광 모듈의 전기·광 변환 |
| DAC(Direct Attach Copper)·AOC(Active Optical Cable) | 양 끝 플러그와 구리 케이블·광섬유가 각각 결합된 연결 | 가까운 서버와 스위치의 연결 |
| MAC(Media Access Control)·IP(Internet Protocol) 주소 | 링크의 인터페이스 식별과 네트워크 전달 주소 | 같은 구간 전달과 라우팅의 구분 |
| 포트, port | 전송 계층에서 통신 끝점을 구별하는 번호 | TCP 서비스 연결 |
| 네트워크 소켓, socket | 프로그램이 통신을 하는 OS 객체·끝점 | CPU 장착 소켓과 다른 뜻 |
| 라우터·스위치 | 네트워크 사이 경로 선택·링크 구간의 프레임 전달 장치 | 다른 서브넷에 요청 전달 |
| DNS(Domain Name System) | 도메인 이름에 대한 정보와 주소 등을 찾는 시스템 | 이름으로 서버 주소 찾기 |
| TLS(Transport Layer Security) | 상대 인증과 암호화로 통신을 보호하는 프로토콜 | 웹의 보호된 연결 |
| ACK(Acknowledgment)·RTT(Round-Trip Time) | 수신 확인 정보와 왕복 시간 | TCP의 전달 확인·재전송 판단 |
| HDD(Hard Disk Drive)·SSD(Solid State Drive) | 회전하는 자성 원판·반도체에 데이터를 저장하는 장치 | 헤드가 이동하는 HDD, NAND 기반 SSD |
| NAND 플래시 | 전원이 없어도 데이터를 보존하는 반도체 메모리 기술 | 페이지 단위로 기록하고 더 큰 블록 단위로 지우기 |
| 폼 팩터, form factor | 부품의 크기·형태·장착 방식 규격 | 2.5인치 장치와 M.2 모듈 |
| M.2·U.2 | 모듈 형태·커넥터 규격과 서버 저장장치 커넥터 계열 | M.2 2280 모듈, U.2 2.5인치 SSD |
| NVMe(Non-Volatile Memory Express) | 비휘발성 메모리 저장장치에 명령을 전달하는 프로토콜 | PCIe 연결의 NVMe SSD |
| SATA(Serial ATA)·SAS(Serial Attached SCSI) | 저장장치를 연결하고 명령을 전달하는 규격 계열 | 같은 베이 외형이 모든 규격 지원을 뜻하지 않음 |
| SCSI(Small Computer System Interface) | 저장장치 등에 명령·응답을 전달하는 표준 계열 | SAS가 사용하는 저장장치 명령 |
| 백플레인, backplane | 여러 장치 커넥터를 호스트 쪽 연결에 이어 주는 기판 | 서버 드라이브 베이 뒤의 기판 |
| 파일시스템, filesystem | 파일 이름·내용·공간을 조직하는 방식 | 파일을 저장장치 블록에 연결 |
| inode·dentry | 파일 메타데이터·이름과 대상의 연결을 다루는 구조 | 이름을 따라 파일 객체 찾기 |
| 파일 디스크립터, fd | 프로세스가 열린 파일·소켓 등을 구별하는 번호 | 파일 열기에서 받은 번호 |
| 오프셋, offset | 시작점에서 얼마나 떨어졌는지를 나타내는 위치 | 파일 안의 바이트 위치 |
| 페이지 캐시, page cache | OS가 파일 데이터를 RAM에 보관하는 구조 | 반복 읽기·대기 중인 쓰기 |
| flush·fsync | 사용자 버퍼를 전달·파일의 동기화를 요청하는 서로 다른 동작 | 성공 뒤의 보장 범위도 다름 |
| dirty·writeback | 바뀌어 저장 반영이 필요한 상태·그 내용을 내려쓰는 과정 | RAM에서 장치로 파일 반영 |
| WAL(Write-Ahead Log) | 변경 전에 복구용 기록을 남기는 방식 | DB의 장애 후 재생 |
| 트랜잭션, transaction | 여러 작업을 정한 일관성·완료 규칙으로 묶는 단위 | 계좌 간 이체 |
| 메타데이터, metadata | 데이터의 위치·구조·상태를 설명하는 정보 | 파일 크기, 테이블 스키마 |
| 스키마, schema | 데이터 필드의 이름·자료형·구조의 약속 | 이름은 문자열, 나이는 정수 |
| 스냅샷, snapshot | 특정 시점의 데이터를 읽게 하는 상태·참조 | 이전 테이블 상태 조회 |
| 정족수, quorum | 정한 규칙을 만족하는 응답·합의 참가자 수 | 복제 시스템의 완료 조건 |

전송 단위는 [네트워크 교재](../kubernetes/networking/networking-foundations/README.md), 저장과 복구의 보장은 [데이터 시스템 교재](../kubernetes/storage/data-systems-foundations/README.md)에서 배운다.

## 5. 측정과 운영의 말

| 용어 | 뜻과 판단할 때 필요한 조건 |
| --- | --- |
| 용량, capacity | 저장 가능한 양. GB·GiB 등 단위를 확인 |
| 대역폭, bandwidth | 초당 전달 가능한 양. bit/s와 byte/s, 방향을 구별 |
| 처리량, throughput | 정한 시간에 완료한 작업 수 또는 데이터량 |
| 지연시간, latency | 요청부터 정한 완료 지점까지의 시간 |
| 백분위, percentile | 관측값을 순서대로 놓았을 때 정한 비율의 지점; 계산법·표본 수 필요 |
| p99 | 99백분위 지점. 평균과 다른 질문이며 극단 표본에 민감 |
| 벤치마크, benchmark | 비교 조건을 정해 성능 등을 재는 작업 |
| 병목, bottleneck | 전체 속도나 진행을 먼저 제한하는 자원·구간 |
| SLO(Service Level Objective) | 서비스가 목표로 정한 품질 수준; 요청 범위·측정창 필요 |
| SLA(Service Level Agreement) | 서비스 제공자와 사용자 사이의 약속; SLO와 계약 의미가 다름 |
| 큐, queue | 처리 순서를 기다리는 요청들의 모음 |
| 동시성, concurrency | 같은 기간에 진행 중인 작업이 겹치는 성질; 물리적 동시 실행과 구별 |
| 격리, isolation | 프로그램의 자원·권한·실패 영향을 분리하는 성질 |
| 이중화, redundancy | 일부 자원이 고장 나도 필요한 기능을 유지하도록 여분을 구성 |

## 6. 연구실 고유명 다시 확인하기

**A7은 특정 서버 이름**, **TwinX·MiniX는 클러스터 이름**이다. 기술 표준의 보편 규칙으로 읽지 않는다. 관측이 있는 문서는 관측 날짜와 해당 제품·구성을 함께 확인한다. 같은 이름의 서버도 부품 이동과 설정 변경 뒤에는 다른 구성을 가질 수 있다.

모르는 전문용어가 남으면 본문에서 처음 나오는 위치를 먼저 확인한다. 사전은 짧은 뜻을 다시 찾는 곳이고, 동작을 배우는 본문을 대체하지 않는다.
