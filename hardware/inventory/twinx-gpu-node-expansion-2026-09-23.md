# TwinX GPU 노드 5대 실측 인벤토리와 가속기 증설 판단

조사일: **2026-09-23 UTC** · 범위: `sv4000-1`, `sv4000-2`, `rm352-1`, `rm352-2`, `l40s`. Edgebox와 control-plane은 제외했다. **장치 이동·부하 시험·섀시 개방은 하지 않았다.** 이 문서는 현재 장착 상태와 보드 수준의 확장 상한을 구분한다.

## 먼저 결정에 필요한 숫자

| 노드 | 실제 플랫폼 / 물리 CPU 수·총 코어 수 | NUMA 영역 수 | 실장 RAM / 빈 DIMM | 현재 GPU | 신규 x16급 카드 자리 후보¹ |
| --- | --- | ---: | --- | --- | ---: |
| `sv4000-1` | ASUS ESC4000A-E12 / EPYC 9124 **1개·16코어** | **1개** | 64 GB×4 = 256 GB / 8 | RTX A6000×2, A100 PCIe 40GB×1 | **1**, Gen5 x16 설계 |
| `sv4000-2` | ASUS ESC4000A-E12 / EPYC 9124 **1개·16코어** | **1개** | 64 GB×4 = 256 GB / 8 | L40×2, A100 PCIe 40GB×1 | **1**, Gen5 x16 설계 |
| `rm352-1` | ASRock Rack SPC621D8 보드 / Xeon Silver 4310 **1개·12코어** | **1개** | 32 GB×6 = 192 GB / 2 | Quadro RTX 6000×1, A10×1 | **최대 2**, Gen4 x16 보드 슬롯 |
| `rm352-2` | ASRock Rack SPC621D8 보드 / Xeon Silver 4310 **1개·12코어** | **1개** | 32 GB×6 = 192 GB / 2 | Quadro RTX 6000×1, A10×1 | **최대 1**, Gen4 x16 보드 슬롯 |
| `l40s` | ASUS ESC8000A-E12 / EPYC 9254 **2개·총 48코어** | **2개** | 64 GB×12 = 768 GB / 12 | L40S×8 | **0**: GPU 베이 8/8 사용 |

이 표의 CPU 수는 **실제로 장착된 프로세서/소켓 수**이고, NUMA는 **영역 개수**다. 아래 장치별 표의 `NUMA 0`·`NUMA 1`은 개수가 아닌 **영역 번호**다. 따라서 `l40s`는 CPU 2개와 NUMA 영역 2개(번호 0, 1)를 가진다.

¹ ASUS의 **완전한 이중 폭 GPU 베이** 수와 ASRock Rack 보드의 **x16 슬롯 잔여 수**를 센 것이다. RM352의 실제 섀시 모델·라이저·인접 슬롯 간격·전원 케이블·냉각은 미확인이다. 따라서 **5개는 장착 보증이 아닌 낙관적 상한**이며, RM352에서 실제 사용 가능한 수는 더 적을 수 있다. `l40s`의 빈 NIC/스토리지용 PCIe 자리는 9번째 GPU 베이가 아니다.

요청한 **추가 NPU 4장 + AMD GPU 4장 + RTX PRO 6000 4장 = 12장**을 모두 이 5대에 기존 카드 유지 조건으로 넣을 수 없다. NPU를 Furiosa RNGD, PRO 6000을 Blackwell **Server Edition**으로 가정하면 두 제품 모두 이중 폭 x16 카드다. **이 두 종류 8장만으로도 위 5자리 상한을 3장 초과**한다. AMD GPU도 이중 폭 x16이면 총 **최소 7자리 부족**하다. Gen5 x16 설계의 빈 GPU 베이는 두 SV4000의 **2자리뿐**이다. AMD GPU의 정확한 모델·PCIe/OAM 형태·두께·소비전력은 확인 전이므로 장착 수 계산에 확정값으로 쓰지 않는다. [RNGD 공식 사양](https://developer.furiosa.ai/docs/v2024.2.1/en/overview/rngd.html), [RTX PRO 6000 Blackwell 제품군 사양](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-family/).

## 증거 범위와 표기

- 5대에 SSH 키로 읽기 전용 접속하여 `lscpu`, `dmidecode`, `lspci -Dnn/-tv`, PCI sysfs 링크·NUMA, `nvidia-smi`, `lsblk`를 수집했다. Kubernetes API에서 Ready·스케줄 가능 여부·GPU 자원을 별도 확인했다.
- `BDF`는 조사 당시의 PCI 주소이고 실물 슬롯 라벨이 아니다. 재부팅·BIOS 변경·카드 이동 후 달라질 수 있다. SMBIOS 슬롯의 `In Use`/주소와 Linux 슬롯 번호에는 중복·불일치가 있어 **RM352의 정확한 물리 슬롯 ↔ BDF 매핑은 현장 대조 전 미확정**이다.
- 링크 표기는 `실제 협상 폭 / 세대`다. 일부 유휴 GPU는 절전 때문에 순간 속도가 Gen1로 보였다. **x16 폭은 정상이고 유휴 Gen1만으로 병목이라고 판단하지 않는다.** 부하 중 재측정은 아직 하지 않았다.
- GB는 DIMM/제품 표기 용량이다. Linux의 GiB·사용 가능 메모리는 예약 영역 때문에 더 작다. 공개 문서에는 BMC 주소, 로그인 정보, 카드 UUID·시리얼을 싣지 않았다.

## CPU·메모리·NUMA

| 노드 | 논리 CPU / 로컬 메모리 | 꽂힌 DIMM 위치, 속도 | 해석 |
| --- | --- | --- | --- |
| `sv4000-1/2` | 각 16C/32T, 단일 NUMA 0 | 각 DDR5-4800 64 GB×4: A1·C1·G1·I1, 12개 중 4개 | 12채널 플랫폼에서 4채널만 채웠다. 호스트 메모리 공급 대역폭 검토 대상. |
| `rm352-1/2` | 각 12C/24T, 단일 NUMA 0 | 각 DDR4-2666 32 GB×6: A·B·D·E·F·H, 8개 중 6개 | C·G 채널 미장착. 196 GB로 적힌 기존 목록은 실장 기준 **192 GB**로 수정해서 해석. |
| `l40s` | 24C/48T×2 = 48C/96T, NUMA 0·1 | 각 소켓에 DDR5-4800 64 GB×6: A·B·C·G·H·I, 전체 24개 중 12개 | 각 소켓 RAM 384 GB, Linux NUMA 메모리 약 378 GiB. 두 소켓 모두 12채널 중 6채널만 채움. |

빈 DIMM 수는 증설 가능성을 뜻할 뿐, 메모리 속도·RDIMM 종류·채널 균형·OEM 메모리 QVL을 무시하고 임의 증설해도 된다는 뜻이 아니다. 채널 미장착은 **잠재적** 메모리 대역폭 제약이며, 이 조사에서는 STREAM/실제 추론 처리량을 측정하지 않았다. [ASUS ESC4000A-E12 사양](https://dlcdnets.asus.com/pub/ASUS/server/ESC4000A-E12/Datasheet/DataSheet_ESC4000A-E12_20221020.pdf), [ASUS ESC8000A-E12 사양](https://servers.asus.com/products/detail/overview/ESC8000A-E12), [SPC621D8 설명서](https://download.asrock.com/Manual/SPC621D8.pdf).

## 슬롯 설계와 현재 점유를 세는 기준

| 플랫폼 | 제조사에 명시된 슬롯 구조 | 이 조사에서 확장 판단에 사용한 부분 |
| --- | --- | --- |
| ESC4000A-E12 (`sv4000-1/2`) | 후면 **Gen5 x16 FHFL 이중 폭 GPU 4개** 또는 Gen5 x8 단일 폭 GPU 8개. 별도 FHHL x16 NIC 1개, FHHL x16/x8 또는 OCP 선택 1개, LP/HL x8 1개. SKU1에는 전면 LP/HL x8 추가 | 각각 GPU 3장이므로 이중 폭 GPU 베이 1개씩. 작은 NIC/RAID 자리를 PRO 6000·RNGD용 FHFL GPU 자리로 합산하지 않음 |
| SPC621D8 (`rm352-1/2`) | 보드 **PCIE1·3·5·7 = Gen4 x16**, **PCIE2·4·6 = Gen4 x8**. M.2 한 개 Gen3 x4, 다른 한 개 Gen3 x1/SATA | `rm352-1`: x16 GPU 2개 + x8 NIC 2개 → x16 최대 2개 후보. `rm352-2`: x16 GPU 2개 + x16 NIC 1개 + x8 NIC 1개 → x16 최대 1개 후보. 물리 이중 폭 공간·섀시 PSU는 별도 |
| ESC8000A-E12 (`l40s`) | **Gen5 x16 FHFL 이중 폭 GPU 8개**, 별도 NIC/RAID 슬롯은 SKU별 변형 | GPU 8장으로 GPU 자리는 0. NIC/RAID 슬롯은 GPU 자리와 구분 |

위 표의 x16/x8은 **제조사 배선/슬롯 설계**이고, 아래 장치별 표는 **현재 협상된 실제 링크**다. 예를 들어 Gen5 x16 슬롯의 Gen4 GPU는 정상적으로 Gen4로 연결될 수 있다. 또한 슬롯이 비어도 이중 폭 카드가 옆의 NIC, 케이블 또는 섀시 벽과 간섭할 수 있다.

## 노드별 현재 카드와 PCIe 경로

### `sv4000-1` — ASUS ESC4000A-E12

| 장치 | BDF | CPU 루트 포트 | NUMA | 실측 링크 |
| --- | --- | --- | ---: | --- |
| RTX A6000 48 GB #0 | `0000:01:00.0` | `00:01.1` | 0 | Gen4 x16 지원, 조회 시 유휴 Gen1 x16 |
| A100 PCIe 40 GB | `0000:02:00.0` | `00:03.1` | 0 | **Gen4 x16** |
| RTX A6000 48 GB #1 | `0000:c1:00.0` | `c0:01.1` | 0 | **Gen4 x16** |
| ConnectX-5 Ex 100G NIC 2포트 | `0000:41:00.0/.1` | `40:01.1` | 0 | **Gen4 x16**, 한 포트 100G 링크 Up |

ASUS는 이 모델에 Gen5 x16 이중 폭 GPU 4장을 명시한다. 3장이 있으므로 **GPU 베이 1개가 보드/제품 설계상 남는다**. 실제 빈 베이의 후면 라벨과 12V 보조전원 커넥터는 열어 확인해야 한다. PSU는 SMBIOS에서 **2600 W×2, 모두 Present/OK**로 보이며, 제품의 1+1 중복 구성에서는 전체 설계를 **한 모듈 2600 W 이내**로 계산해야 한다. GPU 현 설정 전력 한도 합은 300+250+300 = **850 W**이며 CPU·팬·디스크·NIC 전력은 별도다. 보조전원 케이블 종류와 카드별 OEM 지원은 확인되지 않았다. [ASUS 제품 사양](https://servers.asus.com/products/detail/overview/ESC4000A-E12).

### `sv4000-2` — ASUS ESC4000A-E12

| 장치 | BDF | CPU 루트 포트 | NUMA | 실측 링크 |
| --- | --- | --- | ---: | --- |
| L40 48 GB #0 | `0000:01:00.0` | `00:01.1` | 0 | Gen4 x16 지원, 조회 시 유휴 Gen1 x16 |
| L40 48 GB #1 | `0000:c1:00.0` | `c0:01.1` | 0 | **Gen4 x16** |
| A100 PCIe 40 GB | `0000:c2:00.0` | `c0:03.1` | 0 | **Gen4 x8**, 카드·루트 포트의 최대 폭은 x16 |
| ConnectX-5 100G NIC 2포트 | `0000:41:00.0/.1` | `40:01.1` | 0 | **Gen3 x16**, 한 포트 100G 링크 Up |

이 노드도 설계상 GPU 베이 **1개 후보**가 있다. 그러나 A100은 같은 카드가 `sv4000-1`에서 x16으로 동작하는 데 비해 여기서는 **x8로 협상**했다. Gen4 한 방향의 이론 데이터량이 x16 약 31.5 GB/s에서 x8 약 15.75 GB/s로 줄어든다. A100 및 상위 루트 포트가 모두 x8을 보고하므로 단순 유휴 속도 하향과 다르다. **x8 배선/분기 설정, 슬롯 선택, 라이저·접점·카드 상태**를 실제 후면 슬롯·BIOS와 대조해야 원인을 확정할 수 있다. 빈 x16 베이로 옮기면 고쳐진다는 보장은 없다. A100은 현재 MIG 1g.5gb×7로 노출되어 Kubernetes의 일반 `nvidia.com/gpu`는 2개(L40 두 장)다.

PSU는 **2600 W×2 Present/OK**, 현 GPU 전력 한도는 300+300+250 = **850 W**다. NIC는 Gen3 x16으로, 단일 100G Up 포트에 대해 PCIe 이론 상한만으로 병목을 단정할 수 없다. 두 100G 포트를 동시에 최대 속도로 쓸 경우 Gen3 x16의 약 15.75 GB/s 한 방향이 선로 합계 25 GB/s보다 작아 **PCIe가 집계 상한**이 된다. [ASUS 제품 사양](https://servers.asus.com/products/detail/overview/ESC4000A-E12).

### `rm352-1` — ASRock Rack SPC621D8 보드, 실제 섀시 SKU 미확인

| 장치 | BDF / 루트 포트 | NUMA | 실측 링크 |
| --- | --- | ---: | --- |
| Quadro RTX 6000 24 GB | `51:00.0` / `50:02.0` | 0 | Gen3 x16 지원, 조회 시 유휴 Gen1 x16 |
| A10 24 GB | `8a:00.0` / `89:02.0` | 0 | **Gen4 x16** |
| ConnectX-5 Ex 100G 2포트 | `18:00.0/.1` / `17:02.0` | 0 | **Gen4 x8**, 한 포트 100G Up |
| Intel X540-AT2 10G 2포트 | `19:00.0/.1` / `17:04.0` | 0 | Gen2 x8, 현재 포트 Down |
| Samsung 970 EVO Plus 2 TB | `05:00.0` / PCH M.2 | 0 | **Gen3 x1** (SSD 자체 최대 x4) |

보드 매뉴얼은 **Gen4 x16 슬롯 4개 + Gen4 x8 슬롯 3개**를 명시한다. 현재 GPU가 x16급 경로 2개를, 두 NIC가 x8급 경로 2개를 사용하므로 **보드 x16 자리 최대 2개 후보**다. 하지만 카드의 실제 위치·이중 폭 간격·RM352 섀시의 GPU 덕트·케이블은 미확인이다. PSU 정격도 SMBIOS/BMC 조회로 확정하지 못했다. `RM352`라는 현장 명칭만으로 특정 Chenbro 섀시와 1600 W PSU를 가정하지 않는다. [SPC621D8 설명서](https://download.asrock.com/Manual/SPC621D8.pdf).

2 TB NVMe는 보드의 **Gen3 x1 M.2** 경로에 설치되어 있다. 설명서상 이 보드는 x4 M.2와 x1 M.2를 각각 하나씩 제공하므로 장애 증거는 아니지만, 이 SSD는 이론상 x1 약 0.985 GB/s 한 방향으로 제한된다. 현재 컨테이너 데이터 경로에 마운트되어 있어 I/O 요구량에 따라 병목 후보이다. **실측 I/O 지연·처리량은 미조사**다. 100G NIC의 Gen4 x8 이론 상한 약 15.75 GB/s는 한 포트 100G 선로 약 12.5 GB/s보다 크지만, 두 포트 합 25 GB/s에는 못 미친다.

### `rm352-2` — ASRock Rack SPC621D8 보드, 실제 섀시 SKU 미확인

| 장치 | BDF / 루트 포트 | NUMA | 실측 링크 |
| --- | --- | ---: | --- |
| Quadro RTX 6000 24 GB | `51:00.0` / `50:02.0` | 0 | Gen3 x16 지원, 조회 시 유휴 Gen2 x16 |
| A10 24 GB | `c3:00.0` / `c2:02.0` | 0 | **Gen4 x16** |
| ConnectX-5 100G 2포트 | `8a:00.0/.1` / `89:02.0` | 0 | **Gen3 x16**, 한 포트 100G Up |
| Intel X540-AT2 10G 2포트 | `18:00.0/.1` / `17:04.0` | 0 | Gen2 x8, 한 포트 1G Up |
| Samsung 970 EVO Plus 500 GB×2 | `01:00.0` 및 `05:00.0` | 0 | 각각 **Gen3 x4**, **Gen3 x1** |

여기서는 100G NIC가 `rm352-1`과 달리 **x16급 CPU 경로 한 개를 차지한다**. GPU 2개와 NIC 1개가 x16 경로를 점유하므로 4개 중 **최대 1개**가 남는 계산이다. NIC를 x8 슬롯으로 무작정 이동하면 구형 ConnectX-5의 Gen3 x8에서 100G 한 포트조차 이론 상한 약 7.88 GB/s로 제한되므로, GPU 자리 확보만 보고 이동하면 안 된다. 정확한 라이저·실물 슬롯 라벨과 PSU는 미확인이다. 이 노드는 Kubernetes에서 Ready이지만 **SchedulingDisabled(cordon)** 상태다. x1 NVMe는 500 GB 장치이고 보드의 두 번째 M.2 경로 사양과 일치한다. [SPC621D8 설명서](https://download.asrock.com/Manual/SPC621D8.pdf).

### `l40s` — ASUS ESC8000A-E12

| GPU | BDF | 펌웨어 PCIE 명칭² | NUMA | 실측 링크 |
| --- | --- | --- | ---: | --- |
| L40S 48 GB #0 | `01:00.0` | PCIE3 | 0 | Gen4 x16 |
| L40S 48 GB #1 | `21:00.0` | PCIE4 | 0 | Gen4 x16 |
| L40S 48 GB #2 | `41:00.0` | PCIE2 | 0 | Gen4 x16 |
| L40S 48 GB #3 | `61:00.0` | PCIE1 | 0 | Gen4 x16, 조회 시 유휴 Gen1 x16 |
| L40S 48 GB #4 | `81:00.0` | PCIE7 | 1 | Gen4 x16 |
| L40S 48 GB #5 | `a1:00.0` | PCIE8 | 1 | Gen4 x16 |
| L40S 48 GB #6 | `c1:00.0` | PCIE6 | 1 | Gen4 x16 |
| L40S 48 GB #7 | `e1:00.0` | PCIE5 | 1 | Gen4 x16, 조회 시 유휴 Gen1 x16 |

² SMBIOS `dmidecode -t slot` 명칭이며 후면 실크스크린은 현장에서 대조해야 한다. GPU는 **소켓별 4장으로 균형 있게 분배**되어 있고 모두 x16으로 연결된다. ConnectX-5 100G NIC(`22:00.0/.1`)는 **NUMA 0, Gen3 x16**이고 한 포트 100G Up이다. 따라서 NUMA 1의 GPU #4–#7에서 이 NIC로 가는 경로는 `nvidia-smi topo -m`에서 **SYS**, 즉 소켓 간 경로를 지난다. 실제 워크로드의 네트워크 병목 여부는 트래픽·GPU/NIC 어피니티 측정이 필요하다.

GPU 베이는 ASUS 사양의 **8개 이중 폭 자리 모두 사용**한다. 별도 NIC/스토리지 슬롯을 9번째 GPU 자리로 세지 않는다. PSU는 SMBIOS에서 **3000 W×4 Present/OK**다. 실제 중복 모드와 랙 전력 여유는 BMC/전원 설비와 대조해야 한다. [ASUS ESC8000A-E12 사양](https://servers.asus.com/products/detail/overview/ESC8000A-E12).

### 그 밖에 현재 보이는 PCIe 종단 장치

위 표의 GPU·고속 NIC 외에도 다음 장치가 이미 연결되어 있다. 포트가 여러 개인 NIC는 **카드 한 장의 PCIe 링크를 공유**하므로 포트 수만큼 x8/x16 슬롯을 중복 계산하지 않는다. 온보드 장치와 NVMe 백플레인도 여기 기록하지만, 이 BDF를 빈 확장 슬롯으로 해석하지 않는다.

| 노드 | 장치·BDF | 실측 링크와 비고 |
| --- | --- | --- |
| `sv4000-1` | Intel I350 1G×2 `03:00.0/.1`; Samsung NVMe `42:00.0`; ASPEED 관리 그래픽 브리지 `c2:00.0` | 각각 **Gen2 x4**, **Gen4 x4**, **Gen2 x1** |
| `sv4000-2` | Intel I350 1G×2 `02:00.0/.1`; Samsung NVMe `42:00.0`; ASPEED 브리지 `c3:00.0` | 각각 **Gen2 x4**, **Gen4 x4**, **Gen2 x1** |
| `rm352-1` | Intel I210 1G 2개 `02:00.0`·`03:00.0`; Samsung NVMe `05:00.0`; ASPEED 브리지 `06:00.0` | I210 각각 **Gen1 x1**, NVMe **Gen3 x1**, ASPEED **Gen2 x1** |
| `rm352-2` | Intel I210 1G 2개 `02:00.0`·`03:00.0`; Samsung NVMe `01:00.0`·`05:00.0`; ASPEED 브리지 `06:00.0` | I210 각각 **Gen1 x1**, NVMe 순서대로 **Gen3 x4**·**Gen3 x1**, ASPEED **Gen2 x1** |
| `l40s` | Intel X710 10G×2 `82:00.0/.1`; Samsung NVMe `c3:00.0`·`c4:00.0`·`c5:00.0`; Marvell SATA `e2:00.0`; ASPEED 브리지 `62:00.0` | 각각 **Gen3 x4**, NVMe 각 **Gen4 x4**, **Gen2 x2**, **Gen2 x1**. X710 한 포트는 조회 시 1G Up |

## 저장장치와 Kubernetes 상태

아래는 OS에 보인 **물리 SSD**만 세었다. Ceph RBD·loop·가상 미디어는 제외한다.

| 노드 | 물리 SSD (Linux 표시 용량) | Kubernetes 상태 / 가속기 노출 |
| --- | --- | --- |
| `sv4000-1` | SATA 약 447 GiB + NVMe 약 3.5 TiB | Ready, GPU 3 |
| `sv4000-2` | SATA 약 466 GiB + NVMe 약 3.5 TiB | Ready, GPU 2 + A100 MIG 1g.5gb×7 |
| `rm352-1` | SATA 약 447 GiB + NVMe 약 1.8 TiB | Ready, GPU 2 |
| `rm352-2` | SATA 약 447 GiB + NVMe 약 466 GiB×2 | Ready, **cordoned**, GPU 2 |
| `l40s` | NVMe 약 3.5 + 1.7 + 3.5 TiB | Ready, GPU 8 |

## 우선순위가 높은 병목·불확실성

| 우선순위 | 관측 | 영향과 다음 확인 |
| --- | --- | --- |
| **1** | `sv4000-2` A100만 **Gen4 x8**, 카드·루트 포트 최대 x16 | GPU ↔ 호스트 전송 상한이 x16의 절반. BIOS 분기·배선·라이저·실물 슬롯 확인 후 부하 중 링크 재확인. `sv4000-1` A100 x16과 비교. |
| **1** | 12장 추가 요구 대비 x16 후보 **최대 5**, 그중 Gen5 설계 후보 **2** | 기존 카드 유지라면 현 5대만으로 요구 충족 불가. 카드 SKU와 필요한 Gen/폭을 확정하고 별도 서버/재배치안을 산정. |
| **2** | `rm352-2` 100G NIC가 x16급 슬롯 사용 | 추가 카드 자리 1개 감소. Gen3 NIC를 x8로 옮기면 100G 한 포트도 제한될 수 있어 기존 서비스 속도와 맞바꿀 수 없음. |
| **2** | `rm352-1` 2 TB 및 `rm352-2` 500 GB NVMe 하나가 Gen3 x1 M.2 | 보드 설계에 맞는 연결이지만 데이터 I/O 상한 낮음. NVMe 실제 사용량·지연 확인 후 x4 M.2/다른 저장 위치 검토. |
| **2** | `l40s` NIC NUMA 0, GPU 절반 NUMA 1 | 네트워크를 많이 쓰는 GPU #4–#7은 소켓 간 경로 사용. GPU/NIC/CPU/메모리 배치와 실제 전송량 검증. |
| **3** | SV4000 DIMM 4/12, L40S 소켓별 6/12, RM352 6/8 | 채널 미장착으로 호스트 메모리 대역폭 여지 남음. 메모리 집약 워크로드에서만 실측 후 증설 판단. |
| **미판정** | 일부 GPU 링크 조회 순간 Gen1/Gen2 | 유휴 절전 속도일 수 있다. **폭이 x16이면 이 수치만으로 장애로 분류하지 않음.** |

## 추가 카드별 판단과 현장 확인

| 추가 카드 | 공식 요구/가정 | 현재 5대에서의 판단 |
| --- | --- | --- |
| Furiosa RNGD NPU×4 | **Gen5 x16, 이중 폭, 3/4 길이, 패시브, 150 W, 12VHPWR** | SV4000의 2개 빈 GPU 베이가 우선 검토 대상. RM352의 후보는 Gen4여서 인터페이스 최대 대역폭이 절반이고 OEM 지원·보조전원·냉각 확인 필요. 네 장의 동일 성능·동일 토폴로지 배치는 현재 증거로 불가능. |
| RTX PRO 6000 Blackwell Server Edition×4 | **Gen5 x16, 이중 폭 FHFL, 패시브, 설정에 따라 400–600 W** | SV4000 2자리는 물리 설계 후보이나 케이블·600 W 연속 공급·OEM QVL 확인 전 장착 확정 불가. RM352는 Gen4이고 PSU/덕트가 미확인이라 고전력 카드 후보로 승인할 수 없음. |
| AMD GPU×4 | **모델·폼팩터·전력 미확정** | PCIe 카드인지 OAM 모듈인지에 따라 판단 자체가 달라진다. 모델/P/N, 크기, 냉각 방식, 보조전원, PCIe 세대·폭을 받은 뒤 위 슬롯 표로 재계산. |

구매·배치 확정 전 **각 서버를 실제로 열어** (1) 후면 슬롯·라이저·GPU 간 간격과 장착 길이/높이, (2) PSU **실제 라벨/중복 모드**, 카드별 보조전원 케이블·커넥터·전력 예산, (3) 패시브 카드의 전면→후면 공기 흐름과 OEM QVL, (4) RM352 정확한 섀시 모델, (5) 슬롯 라벨 ↔ BDF ↔ CPU 루트·NUMA를 사진과 함께 확인해야 한다. 슬롯 변경은 서비스 중단·Kubernetes GPU 노출 변경을 수반하므로 별도 작업 계획과 유지보수 창에서 수행한다. 이 단계에서는 카드 이동, BIOS 변경, 성능 부하 시험을 수행하지 않았다.

재측정 명령 예시: `lscpu`, `sudo dmidecode -t memory -t slot -t 39`, `lspci -Dnn`, `lspci -Dtv`, `cat /sys/bus/pci/devices/<BDF>/{numa_node,current_link_width,current_link_speed,max_link_width,max_link_speed}`, `nvidia-smi --query-gpu=index,name,pci.bus_id,pcie.link.gen.current,pcie.link.width.current --format=csv`, `nvidia-smi topo -m`, `kubectl get nodes -o wide`. **PCIe 속도는 실제 GPU 부하 중 다시 확인**하고, 기존 장치와 신규 장치의 드라이버·Kubernetes device plugin 공존도 설치 계획에서 별도 검증한다.

## 제조사 기준 문서

- [ASUS ESC4000A-E12 제품/슬롯·전원](https://servers.asus.com/products/detail/overview/ESC4000A-E12), [상세 데이터시트](https://dlcdnets.asus.com/pub/ASUS/server/ESC4000A-E12/Datasheet/DataSheet_ESC4000A-E12_20221020.pdf)
- [ASUS ESC8000A-E12 제품/슬롯·전원](https://servers.asus.com/products/detail/overview/ESC8000A-E12)
- [ASRock Rack SPC621D8 보드 설명서: PCIe·M.2·DIMM](https://download.asrock.com/Manual/SPC621D8.pdf)
- [Furiosa RNGD 하드웨어 사양](https://developer.furiosa.ai/docs/v2024.2.1/en/overview/rngd.html)
- [NVIDIA RTX PRO 6000 Blackwell Server Edition 사양](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-family/)
