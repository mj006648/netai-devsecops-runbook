# 11. 용어 사전 — 같은 말처럼 들리지만 다른 것들

[학습 안내](README.md) · 이전: [A7 설계 문제](10-a7-design-exercises.md)

약어를 처음부터 외울 필요는 없다. 이 표에서 **무엇을 가리키는 단어인지** 확인하고 해당 장의 연결 그림으로 돌아간다. 숫자가 붙으면 단위와 제품 버전을 함께 확인한다.

## 시스템과 연산

| 용어 | 뜻·역할 | 다음에 연결할 개념 | 장 |
|---|---|---|---|
| Node | 클러스터의 실행 단위 | 물리 서버·VM·멀티노드 섀시의 구분 | [01](01-system-map.md) |
| Chassis / U | 장비의 구조물 / 랙 높이 단위 | 카드 수·보드 옵션·깊이·전원 | [01](01-system-map.md) |
| Motherboard | CPU·메모리·I/O가 연결되는 메인보드 | 소켓·라이저·펌웨어 | [01](01-system-map.md) |
| Socket | CPU가 장착되는 자리 | 코어·NUMA와 개수 구분 | [02](02-cpu-memory-numa.md) |
| Core / Thread | 물리 실행 자원 / 실행 문맥 | SMT·논리 CPU·성능 | [02](02-cpu-memory-numa.md) |
| ISA | CPU 명령 집합의 약속 | x86-64·확장 명령·컴파일 | [02](02-cpu-memory-numa.md) |
| Cache / SRAM | 재사용을 돕는 저장 구조 / 메모리 기술 | SRAM 전부가 자동 캐시는 아님 | [02](02-cpu-memory-numa.md), [05](05-gpu-npu-execution.md) |
| GPU / NPU | 병렬·신경망 연산에 특화된 처리 장치 | 지원 연산·런타임·메모리·통신 | [05](05-gpu-npu-execution.md) |
| PE | Processing Element, 연산 구성 단위 | RNGD 카드 수·PE 수·TP 지원은 별개 | [05](05-gpu-npu-execution.md) |
| TCP | 네트워크 Transmission Control Protocol 또는 RNGD Tensor Contraction Processor | 문맥에 따라 완전히 다른 의미 | [05](05-gpu-npu-execution.md), [06](06-networking-rdma.md) |

## 메모리와 지역성

| 용어 | 뜻·역할 | 자주 혼동하는 것 | 장 |
|---|---|---|---|
| DRAM / DDR | 작업용 메모리 기술 / 전송 방식·규격 계열 | 디스크·캐시와 구분 | [02](02-cpu-memory-numa.md) |
| DIMM | 메모리 모듈 | 슬롯·CPU 채널과 개수 구분 | [02](02-cpu-memory-numa.md) |
| Channel / Subchannel | CPU 메모리 경로 / DDR5 내부의 더 작은 독립 경로 | 숫자를 중복해서 대역폭 합산하지 않음 | [02](02-cpu-memory-numa.md) |
| Rank / RDIMM | 모듈 내부 칩 조직 / 등록형 모듈 | 같은 의미가 아님 | [02](02-cpu-memory-numa.md) |
| ECC | 오류 검출·정정용 부호 | 모든 고장 복구·백업을 뜻하지 않음 | [02](02-cpu-memory-numa.md) |
| NUMA / NPS | 접근 위치에 따른 비용 차이 / 소켓당 NUMA 노드 관련 설정 | NUMA 하나가 항상 소켓 하나는 아님 | [02](02-cpu-memory-numa.md) |
| Affinity / First-touch | 실행 위치 제한 / 처음 실제 페이지를 할당하는 접근과 지역성 | CPU 고정만으로 기존 메모리가 이동하지 않음 | [02](02-cpu-memory-numa.md) |
| VRAM / GDDR / HBM | GPU 메모리를 부르는 말 / 장치용 DRAM 기술들 | 모든 GPU가 HBM을 쓰는 것은 아님 | [05](05-gpu-npu-execution.md) |
| KV cache | 추론에서 이전 토큰의 Key·Value 상태 저장 | 가중치·CPU 캐시·모델 파일과 별개 | [05](05-gpu-npu-execution.md) |
| Unified Memory | 여러 물리 메모리의 사용을 돕는 주소·이동 기능 | 물리 거리·대역폭 차이를 제거하지 않음 | [05](05-gpu-npu-execution.md) |

## PCIe와 장착 위치

| 용어 | 뜻·역할 | 자주 혼동하는 것 | 장 |
|---|---|---|---|
| PCIe | 범용 고속 I/O 연결 | NVLink·Ethernet과 다른 프로토콜 | [03](03-pcie-slots-switches.md) |
| Lane / x16 | 링크의 레인 / 레인 16개의 폭 | 세대 없이 속도를 정하지 않음 | [03](03-pcie-slots-switches.md) |
| Gen / GT/s | 세대 / 초당 전송 횟수 단위 | GB/s와 직접 같은 수가 아님 | [03](03-pcie-slots-switches.md) |
| BDF | PCI Domain:Bus:Device.Function 주소 | 실제 SLOT 번호가 아님 | [03](03-pcie-slots-switches.md) |
| Root complex / Port | CPU 쪽 I/O 연결 구조 / 링크의 포트 | 서버 NIC의 네트워크 포트와 구분 | [03](03-pcie-slots-switches.md) |
| PCIe switch / Bridge | PCIe 경로를 분기·연결하는 장치/기능 | 외부 Ethernet 스위치와 구분 | [03](03-pcie-slots-switches.md) |
| Uplink / Downstream | CPU 등 상위 방향 / 장치 쪽 연결 | 각 방향의 실제 폭·공유를 확인 | [03](03-pcie-slots-switches.md) |
| Riser / Backplane | 카드 위치를 배치·연결하는 보드 / 여러 장치의 연결판 | 둘 다 독립 레인을 무한히 만드는 장치는 아님 | [03](03-pcie-slots-switches.md), [04](04-storage-raid-boot.md) |
| Bifurcation / Retimer | 레인 묶음 분할 / 신호 재정형·타이밍 복원 | PCIe 스위치처럼 대역폭을 늘리지 않음 | [03](03-pcie-slots-switches.md) |
| P2P | 지원되는 장치 간 직접 전송 | 같은 스위치면 항상 활성이라는 뜻이 아님 | [03](03-pcie-slots-switches.md) |
| ACS / IOMMU | PCIe 접근·경로 제어 / DMA 주소 변환·보호 | 같은 기능도, 성능 스위치 하나도 아님 | [03](03-pcie-slots-switches.md) |

## 스토리지

| 용어 | 뜻·역할 | 자주 혼동하는 것 | 장 |
|---|---|---|---|
| SSD / HDD | 저장 매체·장치 종류 | 인터페이스나 파일시스템 이름이 아님 | [04](04-storage-raid-boot.md) |
| SATA / SAS / NVMe | 저장장치 접근·전송 규격 계열 | M.2 같은 형태와 별개 | [04](04-storage-raid-boot.md) |
| M.2 / U.2 / U.3 | 장착·연결 형식 관련 이름 | 같은 모양이어도 지원 프로토콜 확인 | [04](04-storage-raid-boot.md) |
| FTL / GC / TRIM | SSD 주소 매핑 / 공간 회수 / 불필요 데이터 범위 통지 | 파일 삭제가 곧 즉시 NAND 삭제는 아님 | [04](04-storage-raid-boot.md) |
| DWPD / TBW / PLP | 쓰기 내구성 지표 / 누적 쓰기 기준 / 전원 손실 보호 | 단위·보증 조건·보호 범위가 다름 | [04](04-storage-raid-boot.md) |
| RAID / HBA | 여러 디스크의 데이터 배치 방식 / 호스트 연결 어댑터 | RAID 레벨과 구현 하드웨어를 구분 | [04](04-storage-raid-boot.md) |
| VD / PD | Virtual Drive 논리 디스크 / Physical Drive 물리 디스크 | OS에서 하나라고 실제 SSD 하나는 아님 | [04](04-storage-raid-boot.md) |
| JBOD | 개별 디스크 노출 등의 모드·구성 문맥 | 자동으로 RAID1이라는 뜻이 아님 | [04](04-storage-raid-boot.md) |
| Partition / LVM / Filesystem | 영역 분할 / 논리 볼륨 관리 / 파일·디렉터리 관리 | 서로 다른 계층이며 조합 순서가 달라질 수 있음 | [04](04-storage-raid-boot.md) |
| Mount / ESP | 파일시스템을 경로에 붙임 / EFI System Partition | `/data`는 디스크 제품명이 아님 | [04](04-storage-raid-boot.md) |

## 네트워크·가속기 연결

| 용어 | 뜻·역할 | 자주 혼동하는 것 | 장 |
|---|---|---|---|
| NIC / RNIC | 네트워크 카드 / RDMA 기능을 갖춘 NIC | 포트 속도·PCIe 속도·실효 처리량 구분 | [06](06-networking-rdma.md) |
| OCP NIC | 별도 서버 NIC 폼팩터 | 표준 PCIe 슬롯에 그대로 꽂는 카드가 아님 | [06](06-networking-rdma.md) |
| Ethernet / InfiniBand | 서로 다른 네트워크 기술 | 비슷한 커넥터라도 같은 스위치에 자동 호환되지 않음 | [06](06-networking-rdma.md) |
| VPI | 지원 NIC의 InfiniBand/Ethernet 선택 기능 | 아무 설정 없이 상호 변환되는 기능은 아님 | [06](06-networking-rdma.md) |
| DMA / RDMA | 장치의 메모리 직접 접근 / 원격 메모리 접근 통신 | CPU·소프트웨어 작업이 완전히 없어지지 않음 | [06](06-networking-rdma.md) |
| RoCE / ECN / PFC | Ethernet 위 RDMA / 혼잡 표시 / 우선순위 흐름 제어 | 같은 계층의 세 이름이 아님 | [06](06-networking-rdma.md) |
| QSFP / DAC / AOC | 포트·모듈 폼팩터 계열 / 직접 연결 구리 케이블 / 능동 광 케이블 | 형태와 실제 지원 속도·프로토콜을 함께 확인 | [06](06-networking-rdma.md) |
| GPUDirect RDMA / Storage | 지원 GPU 메모리와 NIC / 저장 경로의 직접 이동 기능 | 둘은 같은 기능이 아니며 플랫폼 조건 필요 | [06](06-networking-rdma.md) |
| NVLink / NVSwitch | 지원 endpoint의 가속기 연결 / 해당 패브릭 스위치 | RTX PRO 6000 Blackwell Server Edition은 NVLink 미지원 | [07](07-accelerator-interconnects.md) |
| NVLink-C2C / Fusion | 지원 칩간 연결 / 파트너 설계 생태계 | 일반 PCIe 카드의 자동 호환 규격이 아님 | [07](07-accelerator-interconnects.md) |
| UALink / UEC | 가속기 scale-up 규격 / Ultra Ethernet 조직·규격 생태계 | 이름이 비슷해도 적용 계층·목적 구분 | [07](07-accelerator-interconnects.md) |
| CXL / UCIe | 메모리·일관성 연결 / 패키지 내부 칩렛 연결 | GPU 랙 연결을 모두 같은 기술로 분류하지 않음 | [07](07-accelerator-interconnects.md) |
| xGMI / CPO | AMD GPU 간 연결 / 광 I/O 패키징 접근 | 하나는 통신 연결, 다른 하나는 물리 구현 방식 | [07](07-accelerator-interconnects.md) |

## 운영·성능·전원

| 용어 | 뜻·역할 | 자주 혼동하는 것 | 장 |
|---|---|---|---|
| Bandwidth / Latency / Throughput | 이동량 한계 / 한 작업 지연 / 유용 작업 완료량 | 하나의 숫자로 대체할 수 없음 | [01](01-system-map.md) |
| TP / PP / DP | 텐서 / 파이프라인 / 데이터 병렬화 | 물리 카드 수와 각 옵션 숫자가 항상 같지 않음 | [05](05-gpu-npu-execution.md) |
| Prefill / Decode | 입력 문맥 처리 / 토큰 생성 | 병목이 항상 고정돼 있는 것은 아님 | [05](05-gpu-npu-execution.md) |
| TTFT / TPOT | 첫 토큰까지 / 토큰 간 시간 | 큐·전처리와 계산 시간을 나눠 봄 | [05](05-gpu-npu-execution.md) |
| Firmware / Driver / SDK | 장치 제어 코드 / OS 연결 코드 / 개발·실행 도구 집합 | 번호가 같아야 하는 것이 아니라 호환 조합이 필요 | [05](05-gpu-npu-execution.md), [08](08-power-cooling-serviceability.md) |
| PSU / VRM / PDU | 서버 전원 공급 / 칩 전압 조절 / 랙 전력 분배 | 같은 전압·용량 계산 대상이 아님 | [08](08-power-cooling-serviceability.md) |
| TDP / Power limit / Power draw | 열·설계 기준 / 설정 상한 / 실제 소비 | 같은 W 단위라도 의미가 다름 | [08](08-power-cooling-serviceability.md) |
| N+1 / N+N | 필요한 용량에 대한 중복 구성 | 모든 PSU 정격 합계가 장애 시 가용량은 아님 | [08](08-power-cooling-serviceability.md) |
| BMC / IPMI / Redfish | 관리 프로세서 / 관리 인터페이스들 | 호스트 OS 계정·NIC·주소와 구분 | [08](08-power-cooling-serviceability.md) |
| FRU / RAS | 교체 가능한 부품·정보 / 신뢰성·가용성·정비성 | 센서 정상과 부하 검증은 별개 | [08](08-power-cooling-serviceability.md) |
| Cold boot / Power cycle | 전원 상태를 다시 시작하는 절차 | 모델별 요구가 다르며 AC 완전 분리와 항상 같지 않음 | [08](08-power-cooling-serviceability.md) |

## 가장 자주 하는 열 가지 오해

1. **“x16 슬롯이면 다 같은 속도다.”** 세대·실제 배선·협상 폭·상위 공유 링크를 본다.
2. **“DIMM 두 개면 소켓마다 두 채널이다.”** 어느 CPU의 어느 채널에 있는지 확인한다.
3. **“NVMe는 RAM이나 슬롯 형태 이름이다.”** NVMe는 저장장치 접근 규격이며 M.2와 구분한다.
4. **“RAID 카드를 꽂으면 RAID1이다.”** 실제 논리 볼륨의 레벨과 멤버를 확인한다.
5. **“GPU끼리 통신하면 전부 NVLink다.”** PCIe·NVLink·NIC 경로와 제품 지원을 구분한다.
6. **“Blackwell이면 B200 사양을 쓰면 된다.”** 정확한 RTX PRO/B200/B300 등의 제품을 확인한다.
7. **“RDMA면 CPU도 OS도 필요 없다.”** 등록·접근권한·큐·완료·동기화 관리는 남는다.
8. **“카드 메모리를 다 더하면 한 모델이 자유롭게 쓴다.”** 장치별 메모리·분할·런타임 지원이 필요하다.
9. **“새 표준이 나왔으니 기존 카드도 지원한다.”** 실리콘·보드·펌웨어·드라이버·스위치 조합이 필요하다.
10. **“장치가 보이고 센서가 정상이면 작업 완료다.”** 인식·상태·부하·모델 성능은 각각 다른 검증 단계다.

[학습 안내](README.md) · [읽기 전용 실습](09-readonly-labs.md) · [실제 A7 작업일지](../../npu/README.md)
