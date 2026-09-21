# A7 GPU·NPU·NIC 증설 검토 — 실측 구성과 배치안 (2026-09-21)

- 대상: XFUSION G6550 V8 (Turin), AMD EPYC 9355 × 2.
- 추가 조회: 2026-09-21 약 16:59–17:04 KST. RAID 후속 조회: 17:18–17:21 KST. SSH와 BMC Redfish GET으로 하드웨어 정보·구성·상태만 읽었다.
- 연결 문서: [NPU 슬롯·NUMA·binning 작업일지](a7-rngd-slot-numa-binning-2026-09-21.md).
- 학습 자료: [서버 하드웨어 교재](../learning/server-hardware/README.md) — 구성요소 원리, 최신 연결 기술, A7 설계 실습.
- 범위: 설정 변경, 카드 이동, 펌웨어 갱신, 재부팅, 진단·부하 테스트는 수행하지 않았다. 실제 시리얼·UUID·접속 주소·인증 정보는 공개하지 않는다.

## Current status — 배치 결론

**최종 구성이 Blackwell GPU 4장 + RNGD NPU 4장이라면, GPU는 SLOT4/6/8/10, NPU는 SLOT12/14/16/18로 배치하는 안을 우선 검토한다.** 현재 SLOT10의 CARD-A를 SLOT18로 옮기고 GPU 2장을 SLOT8/10에 추가하는 안이다. 기존 GPU는 2장이며, “최종 GPU 4장”은 사용자의 잠정 해석으로 구매 수량이 확정된 것은 아니다.

추가 NIC 후보는 GPU 통신용이면 SLOT3, NPU 통신용이면 SLOT20 또는 SLOT21이다. 이는 NUMA와 PCIe 연결을 근거로 한 후보이며, 정확한 NIC 모델·크기·라이저·OEM 지원 확인 전 장착 확정으로 해석하지 않는다.

추가 조사에서 확인한 중요 사항:

- **호스트 RAM은 총 128GB(64GB × 2), 24개 DIMM 자리 중 2개만 사용한다.** CPU마다 메모리 채널 하나씩만 채워져 있어, 가속기 증설과 함께 호스트 메모리 용량·대역폭을 검토해야 한다. 병목 여부는 아직 측정하지 않았다.
- **SLOT1에는 이미 200G 지원 ConnectX-6 VPI가 있다.** 현재 InfiniBand 포트는 DOWN/Disabled다. 새 100G NIC 구매 전 기존 카드의 용도·연결 상태를 확인한다.
- **PCIe 스위치 그룹 네 개의 CPU 방향 상위 링크는 모두 Gen5 x16이다.** 여러 카드가 동일한 상위 링크를 공유하므로 슬롯별 x16 표기만으로 합산 처리량을 계산하지 않는다.
- PSU 8개가 감지되고 상태는 정상이다. 현재 센서 조회만으로 증설 후 최대 부하·전원 이중화·냉각 여유가 검증된 것은 아니다.
- 공식 백서의 8-GPU 구성과 현행 제품 페이지의 10-GPU 사양이 다르다. 우리 장비에 매핑한 8개 가속기 자리를 기준으로 계획하고, 추가 확장 가능성은 실제 BOM으로 OEM에 확인한다.

## 1. 소켓·NUMA·버스·스위치·슬롯의 차이

| 용어 | 의미 | 이 서버에 적용하면 |
|---|---|---|
| CPU 소켓 | 메인보드에 CPU를 장착하는 자리 | 2개 모두 EPYC 9355로 사용 중. CPU를 세 번째로 추가할 자리는 없음 |
| NUMA 노드 | CPU와 가까운 메모리·장치를 구분하는 OS의 지역성 단위 | 현재 2개. 이 설정에서는 두 CPU 소켓과 대응하지만 모든 서버에서 반드시 1:1인 것은 아님 |
| PCIe 루트 | CPU 쪽 PCIe 연결의 출발점 | 다른 소켓 소속 장치로 가면 소켓 간 연결도 사용하게 될 수 있음 |
| PCIe 스위치 | 하나의 상위 PCIe 연결을 여러 장치 쪽 연결로 확장하는 장치 | 아래 A/B/C/D 네 그룹을 관측. 스위치가 CPU의 총 레인이나 상위 대역폭을 늘리지는 않음 |
| PCI 버스 / BDF | OS가 장치를 찾는 논리 주소 | `0000:81:00.0`은 도메인:버스:장치.기능. 물리 SLOT81이라는 뜻이 아님 |
| 슬롯 / 레인 | 슬롯은 카드 장착 위치, 레인은 PCIe 데이터 경로의 폭 | SLOT10은 위치 이름, Gen5 x16은 세대와 링크 폭. 빈 슬롯의 x0는 카드가 없다는 상태 |

CPU 소켓 수와 DIMM 슬롯 수는 보드 설계로 정해진다. RAM은 지원되는 DIMM을 빈 자리에 추가하거나 기존 DIMM을 교체할 수 있지만, 지원 용량·장착 순서·속도·랭크 혼용 조건이 있다. PCIe도 실제 라이저·케이블·스위치 옵션의 범위에서 확장한다. 물리 커넥터가 x16 모양이어도 실제 연결 폭과 협상 속도는 별도 확인한다.

## 2. 현재 슬롯 전체 지도와 조건부 배치안

서버 **후면을 정면으로 바라보는 방향**이다. 공식 도면의 상단 슬롯 라벨은 왼쪽부터 SLOT1…SLOT21이다. 두 슬롯 폭 가속기 자리는 SLOT4/5부터 SLOT18/19까지 매핑했다. 따라서 “슬롯이 총 8개라 NIC 자리가 없다”는 해석은 맞지 않는다. [공식 백서 Figure 5-15, 본문 34쪽/PDF 40쪽](https://www.xfusion.com/wp-content/uploads/2025/11/FusionServer-G6550-V8-Server-Technical-White-Paper.pdf#page=40).

| 슬롯 | 현재 장치 | NUMA / 연결 | GPU 최종 4장 가정의 배치안 |
|---|---|---|---|
| SLOT1 | ConnectX-6 VPI, `11:00.0` | 0 / CPU 루트 직접 | 유지. 기존 IB/Ethernet 용도부터 확인 |
| SLOT2 | MegaRAID 9520-2M2, `05:00.0` | 0 / 스위치 A | 유지. 960GB M.2 SSD 두 개의 RAID1로 Ubuntu 부팅 |
| SLOT3 | 비어 있음 | 0 / 스위치 B | GPU용 추가 NIC 후보 |
| SLOT4 | Blackwell GPU, `04:00.0` | 0 / 스위치 A | 기존 GPU 유지 |
| SLOT6 | Blackwell GPU, `03:00.0` | 0 / 스위치 A | 기존 GPU 유지 |
| SLOT8 | 비어 있음 | 0 / 스위치 B | 추가 GPU 후보 |
| SLOT10 | RNGD npu0 / CARD-A, `81:00.0` | 0 / 스위치 B | CARD-A를 SLOT18로 이동 후 추가 GPU 후보 |
| SLOT12 | RNGD npu2 / CARD-C, `9e:00.0` | 1 / 스위치 C | 기존 NPU 유지 |
| SLOT14 | RNGD npu1 / CARD-B, `9d:00.0` | 1 / 스위치 C | 기존 NPU 유지. binning·225W 제한 별도 확인 |
| SLOT16 | RNGD npu3 / CARD-D, `e4:00.0` | 1 / 스위치 D | 기존 NPU 유지 |
| SLOT18 | 비어 있음 | 1 / 스위치 D | SLOT10에서 옮길 CARD-A 후보지 |
| SLOT20 | 비어 있음 | 1 / 스위치 C | NPU용 추가 NIC 후보 |
| SLOT21 | 비어 있음 | 1 / 스위치 D | NPU용 추가 NIC 후보 |
| OCP1 | Broadcom BCM57416 2포트 10GbE, `8b:00.0/1` | 0 | 현재 관리망 유지 |
| NVME9 | Samsung 7.68TB NVMe, `7f:00.0` | 0 / 스위치 B | `/data`용 단일 디스크 유지. GPU·NIC와 공유되는 경로 고려 |

표의 BDF는 도메인 `0000:`을 생략했다. 장치 번호/BDF는 이동 후 달라질 수 있다. 공개 별칭 CARD-A/B/C/D와 내부 시리얼을 대조해 작업한다.

**숫자를 셀 때의 기준:** 이번에 식별한 상단 외부 슬롯 라벨은 13개, 그중 큰 가속기용으로 매핑한 자리는 8개다. 이 숫자는 모든 옵션을 포함한 모델의 최대 확장 수가 아니다. OCP1은 이미 사용 중이다. 내부 SLOT28 등의 SMBIOS 항목이나 옵션 후면 I/O 자리까지 빈 외부 카드 자리로 합산하지 않는다. SLOT20/21에는 큰 GPU·RNGD를 장착할 수 있다고 확인하지 않았다.

조건부 최종 배치에서, 첫 Blackwell 자리부터 빈 자리까지 포함해 왼쪽부터 세면 다음과 같다.

```text
후면에서 바라봄 / 가속기 자리만 표시
자리       1       2       3       4       5       6       7       8
SLOT       4       6       8      10      12      14      16      18
계획      GPU     GPU     GPU     GPU     NPU     NPU     NPU     NPU
상태      유지    유지    추가    추가    유지    유지    유지    이전
NUMA      0       0       0       0       1       1       1       1
스위치    A       A       B       B       C       C       D       D
```

## 3. 스위치와 공유 대역폭 — Diagnosis

A/B/C/D는 이 문서의 설명용 별칭이다. 네 개의 PCIe 상위 스위치 그룹을 관측했으며, 이를 물리 스위치 보드 네 장이라는 뜻으로 해석하지 않는다. FRU에 PCIe 스위치 보드 `BC16RSWA`, P/N `0302Y870`이 보고된다.

| 그룹 | 상위 포트 BDF | NUMA | 실제 상위 링크 | 하위 장치 / 슬롯 |
|---|---|---|---|---|
| A | `0000:01:00.0` | 0 | 32GT/s x16 = Gen5 x16 | GPU SLOT4/6, RAID SLOT2 |
| B | `0000:7b:00.0` | 0 | 32GT/s x16 = Gen5 x16 | SLOT3/8/10, NVME9 |
| C | `0000:9b:00.0` | 1 | 32GT/s x16 = Gen5 x16 | SLOT12/14/20 |
| D | `0000:e1:00.0` | 1 | 32GT/s x16 = Gen5 x16 | SLOT16/18/21 |

Gen5 x16 상위 링크는 인코딩을 반영하면 한 방향 약 63GB/s이며, 패킷 오버헤드 전 이론값이다. 같은 그룹의 장치가 동시에 호스트 메모리와 통신하면 이 상위 링크를 공유한다. PCIe 스위치 안에서 지원되는 P2P 트래픽의 경로는 별개이며, ACS·IOMMU·드라이버·플랫폼 지원에 따라 달라진다.

**NVMe와 같은 스위치에 GPU를 꽂는 것은 금지 조건이 아니다.** 동시 호스트 I/O에서는 경합할 수 있지만, 지원되는 GPUDirect Storage 구성에서는 GPU와 NVMe의 가까운 배치가 유리할 수도 있다. 기존 GPU 두 장도 RAID와 스위치 A를 공유한다. 실제 워크로드를 측정해 판단해야 한다. [NVIDIA GPUDirect Storage Best Practices](https://docs.nvidia.com/gpudirect-storage/best-practices-guide/index.html).

현재 관측한 후보 포트의 ACS 리다이렉션은 켜져 있다. 같은 NUMA/스위치라는 이유만으로 직접 P2P가 된다고 단정하지 않는다. GPU/NPU를 나눠 배치해도 각각 두 스위치 사이에는 CPU 쪽 경로가 남으며, 네 장 전체가 한 스위치 아래가 되는 안은 아니다. ACS/IOMMU 변경은 이번 조사·배치안에 포함하지 않는다.

## 4. CPU와 RAM — 추가로 확인한 제약

| 항목 | 실측 |
|---|---|
| CPU | EPYC 9355 32코어 × 2 = 물리 64코어, 논리 128 CPU |
| NUMA0 CPU 목록 | 0–31, 64–95 |
| NUMA1 CPU 목록 | 32–63, 96–127 |
| 메모리 자리 / 장착 | 24개 / 2개 |
| 장착 용량 | 64GB × 2 = 128GB, OS 표시 약 125GiB |
| CPU0 DIMM | DIMM000 / J125 / P0 CHANNEL A |
| CPU1 DIMM | DIMM100 / J137 / P1 CHANNEL A |
| DIMM 사양 | Samsung DDR5 `M321R8GA0EB2-CCPWC`, 설정 속도 6400MT/s |
| 나머지 채널 | 두 CPU 모두 B–L 미장착 |
| NUMA별 메모리 | 각 약 64GB |

두 CPU에 용량은 대칭이지만 **각 CPU의 12개 채널 중 하나씩만 사용**한다. 가속기 모델 로딩, CPU 전처리, 호스트 버퍼, CPU offload, 네트워크 I/O가 겹치면 용량이나 대역폭의 제약이 될 수 있다. GPU VRAM/NPU HBM은 호스트 RAM과 별도이므로 합산해 RAM 부족을 판단하지 않는다. 단일 스냅샷으로 메모리가 현재 병목이라고 확정하지 않는다.

증설량은 모델 크기·동시 서비스·CPU offload·데이터 처리량을 기준으로 정하고, OEM의 DIMM 호환표와 채널 장착 순서를 따른다. CPU별 균형과 여러 채널 활용을 함께 검토한다. SMBIOS의 `Maximum Capacity: 12 TB`는 펌웨어 보고값이며 구매 가능한 검증된 최대 구성으로 사용하지 않는다. 모델의 24개 DDR5 슬롯 사양은 [xFusion 제품 페이지](https://www.xfusion.com/en/product/ai-servers/fusionserver-g6550-v8-ai)에서도 확인된다.

## 5. 기존 NIC와 100G 추가 기준

| 항목 | 현재 실측 / 공식 사양 구분 |
|---|---|
| SLOT1 NIC | 실측 P/N `MCX653105A-HDAT`, ConnectX-6 VPI, 단일 QSFP56 포트 |
| 카드 지원 | 공식 사양: 최대 HDR 200Gb/s InfiniBand 및 200GbE |
| PCIe 링크 | 실측 Gen4 x16, NUMA0 |
| 현재 프로토콜·상태 | 실측 `link_layer: InfiniBand`, `state: DOWN`, `phys_state: Disabled` |
| OCP1 | BCM57416 / XC331, 2포트 10GbE, 실측 PCIe Gen3 x8 |
| 호스트 관리망 포트 | `ens65f0np0`, 실측 1000Mb/s Full, Link detected yes |

ConnectX-6 카드 지원 속도의 근거는 [NVIDIA ConnectX-6 VPI 공식 모델 표](https://networking-docs.nvidia.com/connectx6vpihw/introduction)다. 현재 링크가 DOWN이므로 sysfs `rate` 표시를 실제 협상 속도나 처리량으로 기록하지 않는다. DOWN만으로 케이블 미연결·스위치 설정·관리 상태 중 원인을 특정할 수 없다.

**먼저 기존 ConnectX-6를 어떤 망에 쓰는지 확인한다.** 이미 할당된 IB 용도를 임의로 Ethernet으로 전환하지 않는다. 100G Ethernet이 추가로 필요한지, 기존 카드와 스위치가 그 용도를 지원하는지, 별도 패브릭이 필요한지를 구분한다. 일반 PCIe NIC는 표준 슬롯을 쓰지만 OCP NIC는 별도 폼팩터다. 현재 OCP1이 비어 있다고 가정하지 않는다.

100Gb/s는 한 방향 12.5GB/s다. 아래는 인코딩을 반영하고 패킷 오버헤드 전인 이론값이며, 전이중에서는 송수신 방향을 각각 계산한다.

| 실제 PCIe 링크 | 한 방향 이론 대역폭 | 100G 용량 검토 |
|---|---|---|
| Gen3 x8 | 약 7.88GB/s | 단일 100G를 호스트로 온전히 전달하기에는 부족 |
| Gen3 x16 / Gen4 x8 | 약 15.75GB/s | 단일 100G 검토 가능. 카드 자체의 지원 링크도 확인 |
| Gen4 x16 | 약 31.51GB/s | 2×100G 동시 한 방향 합계 25GB/s를 검토할 기준 |
| Gen5 x16 | 약 63.02GB/s | 공유 스위치 상위 링크의 현재 규격. NIC가 자동으로 Gen5가 되지는 않음 |

NVIDIA ConnectX-6 VPI 제품군에도 단일 100G Gen4 x8 모델과 듀얼 100G Gen3/4 x16 모델이 있어, “100G면 무조건 x16”이라는 규칙은 맞지 않는다. 정확한 주문 P/N과 포트 수·동시 처리 목표를 기준으로 선택한다. 위 수치는 애플리케이션 속도 보장이 아니다. [NVIDIA 모델별 PCIe·포트 사양](https://networking-docs.nvidia.com/connectx6vpihw/introduction).

- GPU에 가까운 추가 NIC: SLOT3 / NUMA0 / 스위치 B 후보. SLOT8/10 GPU 및 NVMe와 상위 링크를 공유한다.
- NPU에 가까운 추가 NIC: SLOT20 / 스위치 C 또는 SLOT21 / 스위치 D 후보. 두 후보 모두 NUMA1이다. NIC 한 장이 NPU 네 장 모두와 같은 스위치에 연결되는 것은 아니다.
- 공통 확인: NIC 길이·높이·브래킷, OEM 승인 라이저, 슬롯 실제 링크 폭, 케이블/광모듈·스위치 포트·FEC, IB/Ethernet 목적, 기존 슬롯 예약 여부.

## 6. GPU·PSU·냉각 스냅샷

| 항목 | 조회 결과 |
|---|---|
| 기존 GPU | RTX PRO 6000 Blackwell **Server Edition** × 2 |
| GPU 전력 한도 | 두 장 모두 현재/default/max 600W |
| 조회 시 GPU | 약 29W/34W, 22°C/24°C; 부하 시험 결과 아님 |
| PSU | 8개 모두 Presence detected / 상태 ok |
| PSU FRU | `PAC3K2S12-TG`, P/N `0213Y041` |
| 이중화 센서 | PS Redundancy ok; 정확한 N+N/N+M 정책·사용 가능 용량 미확인 |
| 입력 전압 | PSU 센서 각각 약 222V |
| 팬 | Fan1–24의 F/R 속도 센서 상태 ok; 센서 수를 별도 팬 개수로 중복 합산하지 않음 |
| 흡기 / 배기 | 약 17°C / 20°C |
| 전체 전력 | DCMI 순간값 798W, 17:03:04 KST. 최대 부하 검증값 아님 |
| BIOS | `01.13.06.06`, 2026-04-13 |

[NVIDIA 공식 사양](https://www.nvidia.com/en-us/data-center/rtx-pro-6000-blackwell-server-edition/)에서 Server Edition은 최대 600W이며 공랭 모델은 dual-slot FHFL이다. **GPU 4장만 최대 2.4kW**이므로 NPU·CPU·메모리·스토리지·팬 소비와 전원 여유를 별도로 계산해야 한다. 현재 NPU 중 한 장의 225W 제한을 임의로 올려 산정하거나 변경하지 않는다.

**추가 공식 사양 확인(2026-09-21): RTX PRO 6000 Blackwell Server Edition은 NVLink 미지원**으로 [NVIDIA 공식 GPU 비교표](https://docs.nvidia.com/vgpu/sizing/virtual-workstation/latest/gpus-vws.html)에 명시돼 있다. B200/GB200의 NVLink 사양을 이 카드에 적용하지 않는다. GPU 증설의 통신 계획은 현재 PCIe 연결과 지원 소프트웨어를 기준으로 검토한다.

PSU 8개가 정상이라는 관측만으로 모든 증설이 가능하다고 판단하지 않는다. 제품 페이지의 PSU 최대 옵션과 실제 장착 PSU의 정격·입력 조건은 구분한다. PSU 라벨/공식 부품 사양, 입력 회로·PDU·케이블 용량, 이중화 상태에서의 허용 부하, GPU 전원 하네스·팬·에어덕트 및 정확한 GPU P/N의 OEM 지원을 확인해야 한다.

## 7. 공식 문서 차이와 남은 확인 — Root cause / 미확정 사항

“G6550 V8은 반드시 GPU 8장까지만 가능” 또는 “최신 페이지가 10장이니 우리 노드도 바로 10장 가능”으로 결론 내리지 않는다.

- [2025-11 공식 백서](https://www.xfusion.com/wp-content/uploads/2025/11/FusionServer-G6550-V8-Server-Technical-White-Paper.pdf)는 8개 double-width GPU 구성과 해당 후면 배치를 설명한다.
- [2026-09-21 확인한 제품 페이지](https://www.xfusion.com/en/product/ai-servers/fusionserver-g6550-v8-ai)는 10개 double-width GPU, switch 구성 최대 15개 standard PCIe 슬롯 등 다른 확장 수치를 제시한다.

구성·개정 차이가 있을 수 있고 슬롯 집계 범주도 같다고 보장되지 않는다. 실제 메인보드 `BC16MBSBB`, PCIe 스위치 보드 `BC16RSWA`와 납품 BOM·라이저·GPU 키트를 OEM에 대조해야 한다. 공개 설명서만으로 우리 장비의 추가 두 GPU 자리까지 확인되지는 않았다.

| 우선순위 | 남은 확인 | 필요한 근거 |
|---|---|---|
| 1 | GPU 최종 4장인지, 기존 2장에 4장을 더해 6장인지 | 구매 담당자의 총수량·정확한 Server Edition P/N |
| 1 | 제안 슬롯에 RNGD/GPU/NIC를 실제 장착할 수 있는지 | 현장 SLOT 라벨·공간·라이저·전원·냉각 및 OEM BOM 호환 확인 |
| 1 | CARD-B의 binning·225W 제한·1.7GHz가 정상 출하 조건인지 | 기존 작업일지의 관측값에 대한 Furiosa/공급자 답변 |
| 2 | RAM 증설 용량과 채널 배치 | 모델·동시 서비스·호스트 메모리 요구량, OEM DIMM 장착표 |
| 2 | 기존 200G NIC의 DOWN 원인과 사용 목적 | 스위치 포트/프로토콜·케이블·관리 상태 및 운영 계획 |
| 2 | 추가 100G NIC 필요 여부·단일/듀얼 포트 | 통신 대상 GPU/NPU, 동시 처리량, 정확한 NIC P/N |
| 2 | 증설 후 전력·냉각 한계 | PSU 정격·이중화·PDU/전원 회로·OEM GPU 키트 검증 |
| 3 | 실제 성능 병목과 배치 개선 효과 | 작업 시간 확보 후 동일 조건의 전후 진단·통신·서빙 측정 |

이 문서는 조사 결과와 작업 후보를 정리한 것이며, 하드웨어 장착 승인서나 실측 성능 보증이 아니다. 실제 장착 지원과 구매 수량이 확정되면 슬롯 계획을 갱신한다. GPU가 최종 6장이면 현재 매핑한 큰 가속기 자리 8개로는 GPU 6장 + NPU 4장을 배치할 수 없으므로 다른 옵션 또는 노드 분리가 필요하다.

## 8. 수집 명령과 다음 검증 — Fix 계획 / Prevention

실행한 주요 읽기 전용 명령은 다음과 같다. 원시 출력에는 시리얼 등이 포함될 수 있으므로 공개 기록에는 필요한 필드만 남겼다.

```bash
lscpu
free -h
sudo dmidecode -t 16 -t 17
lspci -D -t
sudo lspci -D -s 0000:01:00.0 -vv
sudo lspci -D -s 0000:7b:00.0 -vv
sudo lspci -D -s 0000:9b:00.0 -vv
sudo lspci -D -s 0000:e1:00.0 -vv
sudo lspci -D -s 0000:11:00.0 -vv
nvidia-smi --query-gpu=name,pci.bus_id,memory.total,power.limit,power.default_limit,power.max_limit,power.draw,temperature.gpu --format=csv
nvidia-smi topo -m
cat /sys/class/infiniband/mlx5_0/ports/1/state
cat /sys/class/infiniband/mlx5_0/ports/1/phys_state
cat /sys/class/infiniband/mlx5_0/ports/1/link_layer
ethtool ens65f0np0
sudo ipmitool fru print
sudo ipmitool sdr type 'Power Supply'
sudo ipmitool sensor list
sudo ipmitool dcmi power reading
```

장착·변경 후에 수행할 검증이며 **이번에는 미실행**:

1. 카드 내부 시리얼과 새 SLOT/BDF/장치 번호를 대조하고 NPU 4장 alive 및 GPU 인식을 확인한다.
2. 각 링크의 실제 Gen·레인 수, NUMA, 스위치 연결을 다시 기록한다. 빈 슬롯의 지원 능력만으로 완료 판정하지 않는다.
3. NIC의 프로토콜·실제 링크 속도·스위치 연결을 확인하고, 필요하면 합의된 작업 시간에 단일/양포트 통신을 측정한다.
4. 동일한 ACS·드라이버·펌웨어·전력 제한 조건으로 RNGD 진단/P2P 및 실제 모델 서빙을 전후 비교한다. 명령·시간·단위·대상 장치를 남긴다.
5. 승인된 부하 시험 중 온도·전력·스로틀링·PCIe 오류를 확인한다. 저부하 센서 정상만으로 증설 검증을 끝내지 않는다.

## 9. RAID 후속 조회 — Ubuntu 부팅 디스크 구성 확인

2026-09-21 17:18–17:21 KST에 Linux 블록 장치, PCIe 경로, SMART 조회와 BMC Redfish GET을 교차 확인했다. 추가 도구 설치, RAID 생성·초기화·재빌드·설정 변경, SMART 자가시험은 하지 않았다.

**SLOT2는 MegaRAID 9520-2M2 부트 어댑터다. 카드의 960GB M.2 NVMe SSD 두 개를 하드웨어 RAID1로 묶고, 그 논리 디스크에 Ubuntu가 설치돼 있다.** 앞서 설명한 일반적인 RAID 카드→케이블→디스크 백플레인 구조와 달리, 이 모델은 카드에 M.2 SSD 두 개를 장착하는 형태다. 모델 구조는 [Broadcom 제품 페이지](https://www.broadcom.com/products/storage/raid-controllers/megaraid-9520-2m2), 실측 위치는 BMC의 `M.2 Disk0/1(PCIe2)` 및 `Position: raidcard`로 확인했다.

| 항목 | 실제 조회 결과 |
|---|---|
| 컨트롤러 | Broadcom MegaRAID 9520-2M2 / SAS3808 |
| 위치 / 링크 | SLOT2, `0000:05:00.0`, NUMA0 / 스위치 A, 실제 Gen4 x8 |
| 드라이버 / FW | `megaraid_sas` / `5.340.04-4198` |
| 물리 SSD | Samsung `MZ1L2960HCJR-00A07`, 960GB M.2 NVMe × 2 |
| 물리 위치 | `M.2 Disk0(PCIe2)`, `M.2 Disk1(PCIe2)` — 둘 다 카드 위 M.2 자리 |
| 논리 디스크 | `LogicalDrive0`, `RAIDType: RAID1`, `VolumeType: Mirrored` |
| 논리 디스크 상태 | `Health: OK`, `State: Optimal`, `BootEnable: true` |
| RAID 멤버 | 두 SSD 모두 `Online`, `Member`, `Health: OK` |
| SMART | 두 SSD 모두 Health OK. 조회된 NVMe media errors 및 critical warning은 0 |
| 논리 용량 | 959,656,755,200 bytes, 약 960GB / 893.8GiB |
| Linux 장치 | `/dev/sda`, 모델 `MR9520-2M2`, 위 논리 용량과 일치 |
| 파티션 | `/dev/sda1` → `/boot/efi`(vfat), `/dev/sda2` → `/`(ext4) |
| 별도 데이터 SSD | Samsung `MZQL27T6HBLA-00A07`, 약 7.68TB / 7TiB, PCIe `0000:7f:00.0` |
| 데이터 마운트 | `/dev/nvme0n1p1` → `/data`(ext4). 위 RAID1의 멤버가 아님 |

```text
NUMA0 / CPU0
 ├─ PCIe 스위치 A
 │    ├─ SLOT4/6: Blackwell GPU 두 장
 │    └─ SLOT2: MegaRAID 9520-2M2
 │         ├─ 카드 위 M.2 SSD0: 960GB ┐
 │         └─ 카드 위 M.2 SSD1: 960GB ┴─ RAID1 미러링
 │                                      └─ /dev/sda 약 960GB
 │                                           ├─ /boot/efi
 │                                           └─ / (Ubuntu)
 └─ PCIe 스위치 B
      └─ NVME9: 단일 7.68TB NVMe
           └─ /dev/nvme0n1p1 → /data
```

RAID1이므로 두 SSD를 합산한 약 1.92TB를 사용할 수 있는 구성이 아니다. 동일 데이터를 두 장에 기록하며, 논리 용량은 약 한 장 분량이다. 현재 상태 조회로 정상 구성을 확인했으며, 디스크 장애·교체·복구 시험을 수행한 것은 아니다. `/data`는 별도의 단일 NVMe 경로로 관측됐고 이 부팅용 RAID1의 이중화 대상이 아니다. 백업 유무는 이번 조회 범위에 포함하지 않았다.

### RAID 레벨과 구현 방식은 별개

**RAID0/1/5/6/10 같은 숫자는 데이터 배치 방식을 가리키며, RAID 카드의 종류나 디스크 개수를 뜻하지 않는다.** 같은 RAID1도 전용 컨트롤러가 처리하는 하드웨어 RAID와 Linux `md`가 처리하는 소프트웨어 RAID로 구현할 수 있다. Linux 소프트웨어 RAID에는 전용 RAID 카드가 필수는 아니다. [Linux 커널 md 문서](https://cdn.kernel.org/doc/html/latest/admin-guide/md.html).

| 구분 | 처리 주체 | 이 노드의 관측 |
|---|---|---|
| 하드웨어 RAID | 전용 컨트롤러·펌웨어가 디스크를 묶어 OS에 논리 디스크 제공 | 9520-2M2의 RAID1이 `/dev/sda`로 제공됨 |
| 소프트웨어 RAID | OS의 RAID 기능이 직접 보이는 디스크를 묶음 | 활성 Linux md 배열은 관측되지 않음 |

`/proc/mdstat`의 `Personalities: [raid0] [raid1] ...`는 지원 모듈 목록이지 현재 해당 RAID를 사용한다는 뜻이 아니다. 실제 md 배열 항목은 없었고 `mdadm --detail --scan` 출력도 비어 있었다. 루트 파티션은 md 장치가 아닌 `/dev/sda2`의 ext4였다.

이 카드의 공식 모델 문서는 RAID0/RAID1을 설명한다. RAID2는 이 모델의 지원 목록에 없으며, RAID1 다음에 RAID2로 업그레이드하는 식의 순서를 뜻하지 않는다. 실제 구성의 판정 근거는 BMC의 지원 기능 목록이 아니라 **현재 볼륨의 `RAIDType: RAID1`과 두 멤버 링크**다. [9520-2M2 User Guide](https://docs.broadcom.com/doc/9520-2M2-UG).

### 확인에 사용한 읽기 전용 인터페이스

```bash
lsblk -b -e 7 -o NAME,TYPE,SIZE,MODEL,FSTYPE,MOUNTPOINTS
findmnt -no SOURCE,FSTYPE /
cat /proc/mdstat
sudo mdadm --detail --scan
readlink -f /sys/class/block/sda/device
readlink -f /sys/class/block/nvme0n1/device
sudo lspci -s 0000:05:00.0 -vv
sudo smartctl --scan
sudo smartctl -i -H -d megaraid,0 /dev/bus/0
sudo smartctl -i -H -d megaraid,1 /dev/bus/0
```

StorCLI/MegaCLI는 확인한 PATH 및 일반 설치 경로에 없었다. 설치하는 대신 기존 BMC의 다음 리소스를 인증 후 **GET만** 수행했다. BMC 주소·계정·비밀번호는 기록하지 않는다. 원시 출력의 시리얼·고유 식별자는 공개 기록에서 제외했다.

```text
GET /redfish/v1/Systems/1/Storages/RAIDStorage0
GET /redfish/v1/Systems/1/Storages/RAIDStorage0/Volumes/LogicalDrive0
GET /redfish/v1/Chassis/1/Drives/raidcardM.2Disk0(PCIe2)
GET /redfish/v1/Chassis/1/Drives/raidcardM.2Disk1(PCIe2)
GET /redfish/v1/Chassis/1/Drives/HDDPlaneDisk9
```

BMC가 보고하는 BDF가 상위 포트를 가리키는 경우가 있어, 엔드포인트 BDF/NUMA는 Linux `lspci`와 sysfs 경로를 기준으로 적었다. 디스크 `SMART` 출력의 SCSI/SAS 전달 형식만으로 매체를 SAS SSD라고 분류하지 않고 BMC의 PCIe/NVMe·M.2 정보와 모델을 함께 대조했다.

[NPU 작업일지 목록](README.md) · [이전 슬롯·binning 관측](a7-rngd-slot-numa-binning-2026-09-21.md)
