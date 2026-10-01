# TwinX GPU 노드별 장착 장치·빈 슬롯·추가 장착 후보

최초 조사: **2026-09-23 UTC** · 재확인: **2026-10-01 05:22 UTC**

대상: `sv4000-1`, `sv4000-2`, `rm352-1`, `rm352-2`, `l40s`. 5대 모두 SSH로 CPU·DIMM·GPU·PCIe·SSD·펌웨어 슬롯 정보를 다시 읽었다. 카드 이동, BIOS 변경, 부하 시험, 섀시 개방은 하지 않았다.

## 먼저 보는 구성표

| 노드 | GPU 슬롯 설계 / 현재 GPU | 현재 추가 NIC | 기존 카드의 연결 폭을 유지하는 x16 추가 후보 | RAM / 빈 DIMM |
| --- | --- | --- | --- | --- |
| [sv4000-1](#sv4000-1) | Gen5 x16 GPU 베이 4개 / A6000×2 + A100×1 | ConnectX-5 Ex 100G×1 | **GPU 베이 1개 후보** | 256 GB / **8개** |
| [sv4000-2](#sv4000-2) | Gen5 x16 GPU 베이 4개 / L40×2 + A100×1 | ConnectX-5 100G×1 | **GPU 베이 1개 후보** | 256 GB / **8개** |
| [rm352-1](#rm352-1) | Gen4, x16 형상 4개 + x8 형상 3개 / RTX 6000 + A10 | ConnectX-5 Ex 100G + X540 10G | **PCIE1 1개 후보** | 192 GB / **2개** |
| [rm352-2](#rm352-2) | Gen4, x16 형상 4개 + x8 형상 3개 / RTX 6000 + A10 | ConnectX-5 100G + X540 10G | **확정 가능한 후보 없음**; 남은 것은 x8/레인 공유 자리 | 192 GB / **2개** |
| [l40s](#l40s) | Gen5 x16 GPU 베이 8개 / L40S×8 | ConnectX-5 100G×1 | **GPU 베이 없음**; 소형 NIC·M.2 후보는 별도 | 768 GB / **12개** |

**“후보”는 장착 보증이 아니다.** 빈 커넥터가 있어도 큰 카드가 옆 슬롯을 가리거나 전원·냉각·라이저가 맞지 않을 수 있다. 아래 표는 장착 장치와 전기적 연결을 보여 주며, 빈 자리의 실제 간격·케이블은 현장 확인이 필요하다.

- **Gen**은 PCIe 세대, **x16/x8/x4/x1**은 사용하는 레인 수다. Gen5 슬롯에 Gen4 카드가 꽂히면 최대 Gen4로 연결된다.
- **슬롯 설계**는 서버·보드가 제공하는 자리의 규격이고, **장치 최대 규격**은 장착 장치가 보고한 지원 규격이다. SV4000의 GPU 베이는 Gen5 x16이고, RM352의 PCIe 확장 슬롯은 Gen4이며 일부는 레인을 공유한다. 설계가 확인되지 않은 경로는 **미확인**으로 표시한다.
- **측정 당시 링크**는 재확인 시점에 실제 협상된 값이다. 유휴 GPU의 Gen1/Gen2는 절전 상태일 수 있다. 슬롯 설계·장치 최대 규격과 구분해서 읽으며, 부하 중 최대 속도 복귀는 시험하지 않았다.
- **PCIE 번호는 펌웨어 명칭**이다. 후면 실물 라벨과 대조하지 않았다. 특히 RM352의 일부 번호는 링크 폭과 맞지 않아 **추정**으로 표시했다. PCI 주소·루트 포트는 맨 아래 [실측 상세](#실측-상세)에서 볼 수 있다.

## sv4000-1

**ASUS ESC4000A-E12 · EPYC 9124 1개, 16코어/32스레드 · NUMA 0**

큰 GPU용 자리는 **Gen5 x16 이중 폭 베이 4개**, 현재 GPU는 **3장**이다. 작은 NIC/RAID 자리는 GPU 베이와 별도다.

아래 PCIE 슬롯 쌍은 펌웨어 보고를 묶은 **베이 대응 추정**이다. 빈 실물 베이의 라벨·위치는 아직 확정하지 않았다.

| 자리 / 펌웨어 보고 | 슬롯 설계 | 장착 장치 | 장치 최대 규격 | 측정 당시 링크 | 상태 / 추가 장착 조건 |
| --- | --- | --- | --- | --- | --- |
| GPU — PCIE1/2 보고 | **Gen5 x16** | RTX A6000 48 GB #2 | Gen4 x16 | 유휴 **Gen1 x16** | 장착 |
| GPU — PCIE3/4 보고 | **Gen5 x16** | **빈 GPU 베이 후보** | — | 미장착 | 추가 GPU/NPU **1장 후보**; 정확한 실물 베이 대조 필요 |
| GPU — PCIE8/9 보고 | **Gen5 x16** | RTX A6000 48 GB #0 | Gen4 x16 | 유휴 **Gen1 x16** | 장착 |
| GPU — PCIE10/11 보고 | **Gen5 x16** | A100 PCIe 40 GB #1 | Gen4 x16 | **Gen4 x16** | 장착 |
| NIC — PCIE5 보고 | 별도 NIC 자리; 설계 규격 미확인 | ConnectX-5 Ex, 100G 2포트 | Gen4 x16 | **Gen4 x16** | 카드 1장; 두 포트가 링크를 공유 |
| NVMe 경로 | 별도 NVMe 경로; 설계 규격 미확인 | Samsung MZQL23T8HCLS, 약 3.84 TB | Gen4 x4 | **Gen4 x4** | SSD 1개; GPU 베이와 별도 |
| 온보드 LAN | 온보드; 확장 슬롯 아님 | Intel I350, 1G 2포트 | Gen2 x4 | Gen2 x4 | 추가 카드 자리로 세지 않음 |
| 소형 확장 — PCIE6/7·PIKE 보고 | 미확인; 실제 라이저·SKU 대조 필요 | 미장착 후보; 펌웨어 `Available` | — | 미확인 | NIC/RAID 후보; 추가 대형 GPU 자리로 합산하지 않음 |

**여기에 추가할 수 있는 것:** 남은 큰 GPU 베이에 PCIe x16 GPU/NPU **1장**이 우선 후보다. RNGD나 RTX PRO 6000 Server Edition도 인터페이스상 검토 대상이지만 카드 크기·OEM 지원·보조전원·패시브 냉각 확인이 필요하다.

**메모리:** DDR5, 현재 4800 MT/s. **A1·C1·G1·I1에 각 64 GB**, **B1·D1·E1·F1·H1·J1·K1·L1은 비어 있다**. 총 256 GB, 12개 중 4개 장착.

**전원·디스크:** PSU 2600 W×2, 펌웨어 Present/OK. 1+1 중복 유지 시 한 모듈 용량으로 예산을 잡는다. SATA SSD 약 447 GiB + NVMe 약 3.5 TiB. 빈 디스크 베이 수는 확인하지 않았다.

## sv4000-2

**ASUS ESC4000A-E12 · EPYC 9124 1개, 16코어/32스레드 · NUMA 0**

큰 GPU용 자리는 **Gen5 x16 이중 폭 베이 4개**, 현재 GPU는 **3장**이다.

아래 PCIE 슬롯 쌍은 펌웨어 보고를 묶은 **베이 대응 추정**이다. 빈 실물 베이의 라벨·위치는 아직 확정하지 않았다.

| 자리 / 펌웨어 보고 | 슬롯 설계 | 장착 장치 | 장치 최대 규격 | 측정 당시 링크 | 상태 / 추가 장착 조건 |
| --- | --- | --- | --- | --- | --- |
| GPU — PCIE1/2 보고 | **Gen5 x16** | L40 48 GB #1 | Gen4 x16 | **Gen4 x16** | 장착 |
| GPU — PCIE3/4 보고 | **Gen5 x16** | A100 PCIe 40 GB #2 | Gen4 x16 | **Gen4 x8** | 장착; 연결 폭이 카드 최대의 절반 |
| GPU — PCIE8/9 보고 | **Gen5 x16** | L40 48 GB #0 | Gen4 x16 | 유휴 **Gen1 x16** | 장착 |
| GPU — PCIE10/11 보고 | **Gen5 x16** | **빈 GPU 베이 후보** | — | 미장착 | 추가 GPU/NPU **1장 후보**; 정확한 실물 베이 대조 필요 |
| NIC — PCIE5 보고 | 별도 NIC 자리; 설계 규격 미확인 | ConnectX-5, 100G 2포트 | Gen3 x16 | **Gen3 x16** | 카드 1장 |
| NVMe 경로 | 별도 NVMe 경로; 설계 규격 미확인 | Samsung MZQL23T8HCLS, 약 3.84 TB | Gen4 x4 | **Gen4 x4** | SSD 1개; GPU 베이와 별도 |
| 온보드 LAN | 온보드; 확장 슬롯 아님 | Intel I350, 1G 2포트 | Gen2 x4 | Gen2 x4 | 추가 카드 자리로 세지 않음 |
| 소형 확장 — PCIE6/7·PIKE 보고 | 미확인; 실제 라이저·SKU 대조 필요 | 미장착 후보; 펌웨어 `Available` | — | 미확인 | NIC/RAID 후보; GPU 베이와 별도 |

**여기에 추가할 수 있는 것:** 남은 큰 GPU 베이에 PCIe x16 GPU/NPU **1장 후보**. 조건은 `sv4000-1`과 같다.

**먼저 확인할 것:** A100은 이번에도 **Gen4 x8**이다. 카드와 상위 루트 포트의 최대 폭은 x16이지만 현재 둘 다 x8로 연결되어 있다. 유휴 Gen1과 다른 문제이며, 슬롯·라이저·BIOS 분기·접점을 대조해야 한다. 빈 베이로 옮기면 해결된다고 단정하지 않는다. A100의 MIG 모드는 현재 Enabled다.

**메모리:** DDR5, 현재 4800 MT/s. **A1·C1·G1·I1에 각 64 GB**, **B1·D1·E1·F1·H1·J1·K1·L1은 비어 있다**. 총 256 GB.

**전원·디스크:** PSU 2600 W×2, Present/OK. SATA SSD 약 466 GiB + NVMe 약 3.5 TiB. 빈 디스크 베이 수는 미확인.

## rm352-1

**ASRock Rack SPC621D8 · Xeon Silver 4310 1개, 12코어/24스레드 · NUMA 0**

실제 섀시 SKU·라이저·PSU 정격은 미확인이다. 보드의 슬롯은 **Gen4**이고, x16 형상 4개와 x8 형상 3개가 있다. **모두 동시에 x16/x8 최대 폭을 제공하는 구조가 아니다.**

| 자리 / 펌웨어 보고 | 슬롯 설계 | 장착 장치 | 장치 최대 규격 | 측정 당시 링크 | 상태 / 추가 장착 조건 |
| --- | --- | --- | --- | --- | --- |
| **PCIE1** — 펌웨어 빈 자리 보고 | **독립 Gen4 x16** | **빈 x16 후보** | — | 미열거 | GPU/NPU 또는 x16 NIC **1장 후보**; 이중 폭 간격·전원 확인 필요 |
| PCIE2 — 펌웨어 대응 | **Gen4 x8**; PCIE3과 공유 | ConnectX-5 Ex, 100G 2포트 | Gen4 x16 | **Gen4 x8** | 장착; PCIE3과 레인을 나눔 |
| PCIE3 — 펌웨어 대응 | **Gen4 x16**; PCIE2 사용 시 x8 | Intel X540-AT2, 10G 2포트 | Gen2 x8 | **Gen2 x8** | 장착; 이 그룹은 현재 x8+x8 |
| PCIE4 — **추정** | **Gen4 x8**; PCIE5와 공유 | PCIe 장치 없는 자리 후보 | — | 미열거 | 사용 시 PCIE5 GPU가 x8로 줄 수 있음; GPU 두께가 자리를 가릴 수도 있음 |
| PCIE5 — **추정** | **Gen4 x16**; PCIE4 사용 시 x8 | Quadro RTX 6000 24 GB #0 | Gen3 x16 | 유휴 **Gen1 x16** | 장착; 실물 슬롯 번호 대조 필요 |
| PCIE6 — **추정** | **Gen4 x8**; PCIE7과 공유 | PCIe 장치 없는 자리 후보 | — | 미열거 | 사용 시 PCIE7의 A10이 x8로 줄 수 있음 |
| PCIE7 — **추정** | **Gen4 x16**; PCIE6 사용 시 x8 | A10 24 GB #1 | Gen4 x16 | 유휴 **Gen1 x16** | 장착; 실물 슬롯 번호 대조 필요 |
| M2_1 — x4 경로 | **Gen3 x4** | **NVMe 미장착 후보** | — | NVMe 미열거 | M.2 SSD 후보; 실물 확인 필요 |
| M2_2 — x1 경로 | **Gen3 x1** | Samsung 970 EVO Plus **2 TB** | Gen3 x4 | **Gen3 x1** | 장착; 보드 경로는 x1 |
| 온보드 LAN | 온보드; 확장 슬롯 아님 | Intel I210 1G×2 | Gen1 x1, 각 장치 | Gen1 x1, 각 장치 | PCIe 추가 카드 슬롯과 별도 |
| SATA | SATA 경로; PCIe 확장 슬롯 아님 | SATA SSD 약 447 GiB | 해당 없음 | 해당 없음 | PCIe 추가 카드 슬롯과 별도 |

**여기에 추가할 수 있는 것:** 기존 카드의 연결 폭을 유지하려면 **PCIE1이 우선 후보**다. GPU/NPU를 넣을 경우 **Gen4 x16**으로 검토하며, Gen5 x16 대역폭을 제공하는 자리가 아니다. 나머지 빈 x8 후보는 NIC·NVMe 어댑터 등 소형 카드용으로 검토하되 옆 GPU의 레인 감소를 함께 계산한다.

**추정 표시의 이유:** 펌웨어는 RTX 6000을 `PCIE4`, A10을 `PCIE6`으로 보고하지만 두 카드의 실제 연결은 x16이다. 매뉴얼에서 이 번호는 x8이므로 그대로 실물 슬롯 번호로 쓰지 않았다. 위 PCIE5/7 배치는 보드의 슬롯 쌍과 실측 폭으로 추정한 것이며, 사진·실크스크린 확인 전 확정하지 않는다. M2_1의 펌웨어 주소도 NVMe가 아닌 I210 경로를 가리킨다.

**메모리:** DDR4, 현재 2666 MT/s. **A·B·D·E·F·H에 각 32 GB**, **C·G는 비어 있다**. 총 192 GB. 장착 DIMM의 정격은 2666/3200 MT/s가 섞여 있으므로 증설 시 모듈 규격을 대조한다.

**디스크:** SATA 약 447 GiB + NVMe 약 1.8 TiB. 현재 2 TB NVMe는 x1이라 x4 M.2보다 전송 상한이 낮다.

## rm352-2

**ASRock Rack SPC621D8 · Xeon Silver 4310 1개, 12코어/24스레드 · NUMA 0**

`rm352-1`과 같은 Gen4 보드지만 **100G NIC가 x16 경로를 사용한다**. 실제 섀시·전원·슬롯 간격은 미확인이다.

| 자리 / 펌웨어 보고 | 슬롯 설계 | 장착 장치 | 장치 최대 규격 | 측정 당시 링크 | 상태 / 추가 장착 조건 |
| --- | --- | --- | --- | --- | --- |
| PCIE1 — 펌웨어 대응 | **독립 Gen4 x16** | A10 24 GB #1 | Gen4 x16 | **Gen4 x16** | 장착 |
| **PCIE2** — 펌웨어 빈 자리 보고 | **Gen4 x8**; PCIE3과 공유 | **빈 x8 후보** | — | 미열거 | PCIE3의 X540과 공유하는 그룹 |
| PCIE3 — 펌웨어 대응 | **Gen4 x16**; PCIE2 사용 시 x8 | Intel X540-AT2, 10G 2포트 | Gen2 x8 | **Gen2 x8** | 장착 |
| PCIE4 — **추정** | **Gen4 x8**; PCIE5와 공유 | PCIe 장치 없는 자리 후보 | — | 미열거 | 사용 시 PCIE5 GPU의 x16 유지 불가 |
| PCIE5 — **추정** | **Gen4 x16**; PCIE4 사용 시 x8 | Quadro RTX 6000 24 GB #0 | Gen3 x16 | 유휴 **Gen2 x16** | 장착; 실물 슬롯 번호 대조 필요 |
| PCIE6 — **추정** | **Gen4 x8**; PCIE7과 공유 | PCIe 장치 없는 자리 후보 | — | 미열거 | 사용 시 PCIE7의 100G NIC가 **Gen3 x8**로 줄 수 있음 |
| PCIE7 — **추정** | **Gen4 x16**; PCIE6 사용 시 x8 | ConnectX-5, 100G 2포트 | Gen3 x16 | **Gen3 x16** | 장착; 실물 슬롯 번호 대조 필요 |
| M2_1 — x4 경로 | **Gen3 x4** | Samsung 970 EVO Plus **500 GB** | Gen3 x4 | **Gen3 x4** | 장착 |
| M2_2 — x1 경로 | **Gen3 x1** | Samsung 970 EVO Plus **500 GB** | Gen3 x4 | **Gen3 x1** | 장착; 보드 경로는 x1 |
| 온보드 LAN | 온보드; 확장 슬롯 아님 | Intel I210 1G×2 | Gen1 x1, 각 장치 | Gen1 x1, 각 장치 | PCIe 추가 카드 슬롯과 별도 |
| SATA | SATA 경로; PCIe 확장 슬롯 아님 | SATA SSD 약 447 GiB | 해당 없음 | 해당 없음 | PCIe 추가 카드 슬롯과 별도 |

**여기에 추가할 수 있는 것:** 빈 후보는 **x8 소형 카드 자리**다. 기존 GPU와 100G NIC의 x16 연결을 유지하면서 추가할 **독립 x16 자리는 확인되지 않았다**. 특히 100G NIC를 Gen3 x8로 줄이면 이론상 한 방향 약 7.88 GB/s로, 100G 선로의 12.5 GB/s보다 작다.

**슬롯 번호 주의:** PCIE4–7은 `rm352-1`과 같은 펌웨어/실측 폭 불일치가 있어 추정이다. 빈 커넥터가 보여도 “x16 GPU를 성능 저하 없이 추가할 수 있다”로 읽지 않는다.

**메모리:** DDR4, 현재 2666 MT/s. **A·B·D·E·F·H에 각 32 GB**, **C·G는 비어 있다**. 총 192 GB, 정격 2666/3200 MT/s DIMM 혼재.

**디스크:** SATA 약 447 GiB + NVMe 약 466 GiB×2. **M.2 두 경로 모두 사용 중**이다.

## l40s

**ASUS ESC8000A-E12 · EPYC 9254 2개, 총 48코어/96스레드 · NUMA 0·1**

큰 GPU 자리는 **Gen5 x16 이중 폭 베이 8개**, **8개 모두 L40S가 꽂혀 있다**. 아래 GPU 슬롯 번호는 펌웨어 주소와 GPU가 일대일로 대응하지만 후면 실물 라벨은 미대조다.

| 자리 / 펌웨어 보고 | 현재 꽂힌 장치 | 소속 | 장치 지원 / 현재 협상 |
| --- | --- | --- | --- |
| PCIE1 | L40S 48 GB #3 | NUMA 0 | Gen4 x16 / 유휴 Gen1 x16 |
| PCIE2 | L40S 48 GB #2 | NUMA 0 | Gen4 x16 / Gen4 x16 |
| PCIE3 | L40S 48 GB #0 | NUMA 0 | Gen4 x16 / Gen4 x16 |
| PCIE4 | L40S 48 GB #1 | NUMA 0 | Gen4 x16 / Gen4 x16 |
| PCIE5 | L40S 48 GB #7 | NUMA 1 | Gen4 x16 / 유휴 Gen1 x16 |
| PCIE6 | L40S 48 GB #6 | NUMA 1 | Gen4 x16 / Gen4 x16 |
| PCIE7 | L40S 48 GB #4 | NUMA 1 | Gen4 x16 / Gen4 x16 |
| PCIE8 | L40S 48 GB #5 | NUMA 1 | Gen4 x16 / Gen4 x16 |
| PCIE_NIC1 | ConnectX-5, 100G 2포트 | NUMA 0 | Gen3 x16 / Gen3 x16 |
| **PCIE_NIC2** | **빈 소형 카드 자리 후보** | 미확인 | 펌웨어 **Gen5 x8**, `Available`; 실제 SKU·라이저 확인 필요 |
| PCIE_NIC3 보고 / NVMe 경로 | **NVMe 연결로 보고됨** | NUMA 1 | 대응 주소의 SSD는 **Gen4 x4**; 빈 NIC 슬롯으로 세지 않음 |
| NVMe 경로 3개 | Samsung SSD **1.92 TB + 3.84 TB + 3.84 TB** | 모두 NUMA 1 | 각각 **Gen4 x4** |
| **M.2** | **빈 SSD 자리 후보** | 미확인 | 펌웨어 x4, `Available`; 세대·길이·실제 장착 여부 확인 필요 |
| 온보드 LAN | Intel X710, 10G 2포트 | NUMA 1 | Gen3 x4 / Gen3 x4 |
| SATA 컨트롤러 | Marvell 88SE9230, SATA 6G 4포트 | 미확인 | Gen2 x2 / Gen2 x2; GPU 베이로 세지 않음 |

**여기에 추가할 수 있는 것:** **추가 큰 GPU/NPU 베이는 없다.** 별도 `PCIE_NIC2`는 크기와 SKU가 맞는 소형 NIC/스토리지 카드 후보, M.2는 SSD 후보다. 두 자리를 “9번째 GPU 자리”로 세지 않는다. NVMe와 PCIE_NIC3 보고는 중복 집계하지 않는다.

**NUMA 배치:** GPU는 CPU당 4장이다. 100G NIC는 NUMA 0이므로 NUMA 1의 GPU가 이 NIC를 쓸 때 소켓 간 경로를 거친다. PCIe 슬롯 Gen5 여부와 별개인 데이터 이동 조건이다.

**메모리:** CPU1·CPU2 **각각 A1·B1·C1·G1·H1·I1에 64 GB**, **각각 D1·E1·F1·J1·K1·L1은 비어 있다**. 총 768 GB, 24개 중 12개 장착. DIMM 정격은 5600 MT/s이고 실제 설정은 **4800 MT/s**다.

**전원·디스크:** PSU 3000 W×4, Present/OK. 실제 중복 모드·랙 전력 여유는 별도 확인. 물리 NVMe 약 1.7 TiB + 3.5 TiB + 3.5 TiB.

## 어떤 카드를 어느 노드에 검토할 수 있나

| 추가 장치 | 우선 자리 | 가능한 범위 / 조건 |
| --- | --- | --- |
| Gen5 x16 GPU/NPU | sv4000-1·2의 빈 큰 GPU 베이, **각 1개** | Gen5 x16 설계 후보. 카드 두께·길이·전원 케이블·냉각·OEM QVL 대조 필요 |
| Gen4 x16 GPU/NPU 또는 x16 NIC | rm352-1 **PCIE1 후보 1개** | 독립 x16 설계. 섀시 공간·PSU가 미확인이라 대형/고전력 카드 장착은 아직 확정 불가 |
| x8 소형 NIC·NVMe 어댑터 | RM352의 빈 x8 후보, l40s **PCIE_NIC2 후보** | 슬롯 공유, 인접 카드 간섭, 라이저·SKU 확인. RM352에서는 옆 장치의 x16→x8 감소를 함께 계산 |
| M.2 SSD | rm352-1 **M2_1 후보**, l40s **M.2 후보** | 전자는 Gen3 x4 설계·NVMe 미열거, 후자는 펌웨어 빈 자리 보고. 실물 장착 여부·길이·지원 세대 확인 |
| 추가 대형 GPU를 l40s에 장착 | **빈 GPU 베이 없음** | 기존 GPU 교체 또는 다른 서버 배치가 필요 |

이전에 요청한 **NPU 4장 + AMD GPU 4장 + RTX PRO 6000 4장 = 12장**을 기존 카드 유지 조건으로 이 5대에 모두 추가할 수는 없다. 위의 **독립 x16 대형 카드 후보는 총 3개**이며 이마저 현장 장착 보증은 아니다. **Gen5 GPU 베이 후보는 SV4000의 2개뿐**이다.

[RNGD](https://developer.furiosa.ai/docs/v2024.2.1/en/overview/rngd.html)는 Gen5 x16을 지원한다. [RTX PRO 6000 Blackwell Server Edition](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-family/)은 Gen5 x16·이중 폭·패시브 냉각이며 400–600 W 전력 조건을 대조해야 한다. AMD GPU는 모델과 PCIe/OAM 형태가 미확정이므로 자리 배정을 확정하지 않는다.

## 실측 상세

<details>
<summary>PCI 주소·CPU 루트 포트·카드 지원 세대·현재 링크 보기</summary>

PCI 주소는 모두 도메인 `0000`이다. 주소와 GPU #번호는 재부팅·카드 이동 후 바뀔 수 있다. 두 포트 NIC의 `.0/.1`은 카드 하나로 묶었다. GPU의 오디오/USB 기능은 별도 카드로 세지 않았다. 여기의 “지원”은 장치가 보고한 최대값이며 빈 슬롯의 배선을 뜻하지 않는다.

### sv4000-1

| 장치 | BDF | 상위 루트 | NUMA | 장치 지원 | 현재 링크 |
| --- | --- | --- | --- | --- | --- |
| NVIDIA RTX A6000 #0 | `01:00.0` | `00:01.1` | 0 | Gen4 x16 | Gen1 x16 |
| NVIDIA A100-PCIE-40GB #1 | `02:00.0` | `00:03.1` | 0 | Gen4 x16 | Gen4 x16 |
| Intel I350 1G 2포트 | `03:00.0` | `00:05.1` | 0 | Gen2 x4 | Gen2 x4 |
| ConnectX-5 Ex 100G 2포트 | `41:00.0` | `40:01.1` | 0 | Gen4 x16 | Gen4 x16 |
| SAMSUNG MZQL23T8HCLS-00A07 | `42:00.0` | `40:03.2` | 0 | Gen4 x4 | Gen4 x4 |
| NVIDIA RTX A6000 #2 | `c1:00.0` | `c0:01.1` | 0 | Gen4 x16 | Gen1 x16 |
| ASPEED 관리 그래픽 브리지 | `c2:00.0` | `c0:05.2` | 0 | Gen2 x1 | Gen2 x1 |

### sv4000-2

| 장치 | BDF | 상위 루트 | NUMA | 장치 지원 | 현재 링크 |
| --- | --- | --- | --- | --- | --- |
| NVIDIA L40 #0 | `01:00.0` | `00:01.1` | 0 | Gen4 x16 | Gen1 x16 |
| Intel I350 1G 2포트 | `02:00.0` | `00:05.1` | 0 | Gen2 x4 | Gen2 x4 |
| ConnectX-5 100G 2포트 | `41:00.0` | `40:01.1` | 0 | Gen3 x16 | Gen3 x16 |
| SAMSUNG MZQL23T8HCLS-00A07 | `42:00.0` | `40:03.2` | 0 | Gen4 x4 | Gen4 x4 |
| NVIDIA L40 #1 | `c1:00.0` | `c0:01.1` | 0 | Gen4 x16 | Gen4 x16 |
| NVIDIA A100-PCIE-40GB #2 | `c2:00.0` | `c0:03.1` | 0 | Gen4 x16 | Gen4 x8 |
| ASPEED 관리 그래픽 브리지 | `c3:00.0` | `c0:05.2` | 0 | Gen2 x1 | Gen2 x1 |

### rm352-1

| 장치 | BDF | 상위 루트 | NUMA | 장치 지원 | 현재 링크 |
| --- | --- | --- | --- | --- | --- |
| Intel I210 1G | `02:00.0` | `00:1c.4` | 0 | Gen1 x1 | Gen1 x1 |
| Intel I210 1G | `03:00.0` | `00:1c.5` | 0 | Gen1 x1 | Gen1 x1 |
| Samsung SSD 970 EVO Plus 2TB | `05:00.0` | `00:1d.2` | 0 | Gen3 x4 | Gen3 x1 |
| ASPEED 관리 그래픽 브리지 | `06:00.0` | `00:1d.3` | 0 | Gen2 x1 | Gen2 x1 |
| ConnectX-5 Ex 100G 2포트 | `18:00.0` | `17:02.0` | 0 | Gen4 x16 | Gen4 x8 |
| Intel X540 10G 2포트 | `19:00.0` | `17:04.0` | 0 | Gen2 x8 | Gen2 x8 |
| Quadro RTX 6000 #0 | `51:00.0` | `50:02.0` | 0 | Gen3 x16 | Gen1 x16 |
| NVIDIA A10 #1 | `8a:00.0` | `89:02.0` | 0 | Gen4 x16 | Gen1 x16 |

### rm352-2

| 장치 | BDF | 상위 루트 | NUMA | 장치 지원 | 현재 링크 |
| --- | --- | --- | --- | --- | --- |
| Samsung SSD 970 EVO Plus 500GB | `01:00.0` | `00:1c.0` | 0 | Gen3 x4 | Gen3 x4 |
| Intel I210 1G | `02:00.0` | `00:1c.4` | 0 | Gen1 x1 | Gen1 x1 |
| Intel I210 1G | `03:00.0` | `00:1c.5` | 0 | Gen1 x1 | Gen1 x1 |
| Samsung SSD 970 EVO Plus 500GB | `05:00.0` | `00:1d.2` | 0 | Gen3 x4 | Gen3 x1 |
| ASPEED 관리 그래픽 브리지 | `06:00.0` | `00:1d.3` | 0 | Gen2 x1 | Gen2 x1 |
| Intel X540 10G 2포트 | `18:00.0` | `17:04.0` | 0 | Gen2 x8 | Gen2 x8 |
| Quadro RTX 6000 #0 | `51:00.0` | `50:02.0` | 0 | Gen3 x16 | Gen2 x16 |
| ConnectX-5 100G 2포트 | `8a:00.0` | `89:02.0` | 0 | Gen3 x16 | Gen3 x16 |
| NVIDIA A10 #1 | `c3:00.0` | `c2:02.0` | 0 | Gen4 x16 | Gen4 x16 |

### l40s

| 장치 | BDF | 상위 루트 | NUMA | 장치 지원 | 현재 링크 |
| --- | --- | --- | --- | --- | --- |
| NVIDIA L40S #0 | `01:00.0` | `00:01.1` | 0 | Gen4 x16 | Gen4 x16 |
| NVIDIA L40S #1 | `21:00.0` | `20:01.1` | 0 | Gen4 x16 | Gen4 x16 |
| ConnectX-5 100G 2포트 | `22:00.0` | `20:03.1` | 0 | Gen3 x16 | Gen3 x16 |
| NVIDIA L40S #2 | `41:00.0` | `40:01.1` | 0 | Gen4 x16 | Gen4 x16 |
| NVIDIA L40S #3 | `61:00.0` | `60:01.1` | 0 | Gen4 x16 | Gen1 x16 |
| ASPEED 관리 그래픽 브리지 | `62:00.0` | `60:05.2` | 0 | Gen2 x1 | Gen2 x1 |
| NVIDIA L40S #4 | `81:00.0` | `80:01.1` | 1 | Gen4 x16 | Gen4 x16 |
| Intel X710 10G 2포트 | `82:00.0` | `80:05.1` | 1 | Gen3 x4 | Gen3 x4 |
| NVIDIA L40S #5 | `a1:00.0` | `a0:01.1` | 1 | Gen4 x16 | Gen4 x16 |
| NVIDIA L40S #6 | `c1:00.0` | `c0:01.1` | 1 | Gen4 x16 | Gen4 x16 |
| SAMSUNG MZQL21T9HCJR-00A07 | `c3:00.0` | `c0:03.2` | 1 | Gen4 x4 | Gen4 x4 |
| SAMSUNG MZQL23T8HCLS-00A07 | `c4:00.0` | `c0:03.3` | 1 | Gen4 x4 | Gen4 x4 |
| SAMSUNG MZQL23T8HCLS-00A07 | `c5:00.0` | `c0:03.4` | 1 | Gen4 x4 | Gen4 x4 |
| NVIDIA L40S #7 | `e1:00.0` | `e0:01.1` | 1 | Gen4 x16 | Gen1 x16 |

</details>

<details>
<summary>RM352 레인 공유 구조와 슬롯 번호 검증 근거</summary>

[SPC621D8 매뉴얼](https://download.asrock.com/Manual/SPC621D8.pdf)의 인쇄 쪽수 2·34 기준으로 **PCIE1은 독립 x16**, 나머지는 아래와 같이 짝을 이룬다. 짝의 x8 슬롯을 쓰면 x16 슬롯도 x8로 바뀐다.

```text
PCIE1             → 독립 x16
PCIE2 + PCIE3     → x8 + x8 또는 PCIE3 단독 x16
PCIE4 + PCIE5     → x8 + x8 또는 PCIE5 단독 x16
PCIE6 + PCIE7     → x8 + x8 또는 PCIE7 단독 x16
```

이번 실측에서 `rm352-1`의 두 NIC는 루트 `17:02.0`·`17:04.0`에 각각 x8로 연결되고, 두 GPU는 `50:02.0`·`89:02.0`에서 각각 x16이다. 펌웨어는 PCIE1을 Available로 보고한다. 이를 보드 구조와 대조해 PCIE1을 독립 x16 후보로 남겼다.

`rm352-2`의 x16 경로 3개는 RTX 6000·A10·100G NIC가 사용하고, X540은 `17:04.0`에서 x8이다. 독립 PCIE1은 A10이 사용한다. 남은 커넥터를 새 독립 x16 경로로 더하지 않았다.

펌웨어의 GPU PCIE4/6 명칭, `PCIE47` 표기와 M2_1 주소에는 불일치가 있다. 실제 사진이 없으므로 PCIE4–7 배치와 빈 커넥터의 접근성은 추정이다. PCI 루트가 비어 있거나 OS에서 숨겨져 있다고 해서 케이블이 연결된 실제 확장 자리가 있다고 단정하지 않는다.

기존 문서의 “최대 5자리”는 x16 형상 커넥터/베이 중심의 낙관적 계산이었다. 이번 표는 **기존 카드의 연결 폭 유지**와 레인 공유를 반영해 **3개 후보**로 좁혔다.

</details>

<details>
<summary>성능·운영 상태·전원에 관한 보충 기록</summary>

- **PCIe 전송 상한:** Gen4 x16 약 31.5 GB/s, Gen4 x8 또는 Gen3 x16 약 15.75 GB/s, Gen3 x8 약 7.88 GB/s, Gen3 x1 약 0.985 GB/s. 한 방향·인코딩 반영 후·프로토콜 오버헤드 제외 값이며 실제 처리량 측정값이 아니다.
- **100G NIC:** 두 포트가 카드 한 장의 PCIe 링크를 공유한다. 100G 두 포트의 한 방향 선로 합계는 25 GB/s이므로 Gen3 x16/Gen4 x8의 집계 상한을 넘는다. 한 포트만 사용할 때의 실제 병목은 별도 측정해야 한다.
- **메모리:** SV4000은 12채널 중 4개, L40S는 소켓마다 12채널 중 6개, RM352는 8채널 중 6개 장착. 메모리 공급 대역폭의 여지는 있지만 STREAM/워크로드 성능은 측정하지 않았다. OEM 메모리 QVL·RDIMM 종류·채널 균형을 대조해야 한다.
- **2026-09-23의 Kubernetes 기록:** sv4000-1 GPU 3, sv4000-2 GPU 2 + A100 MIG 1g.5gb×7, rm352-1/2 GPU 각 2, l40s GPU 8. 당시 모두 Ready이고 rm352-2는 cordon 상태였다. **이번에는 Kubernetes API·MIG 인스턴스 수·네트워크 포트 Up/Down을 재확인하지 않았다.**
- **2026-09-23의 전력 한도 기록:** SV4000 두 노드의 GPU 설정 한도 합은 각각 850 W였다. CPU·팬·디스크·NIC는 별도다. 이번 PSU Present/OK는 펌웨어 보고이며 실물 라벨·중복 모드·랙 전력 확인을 대체하지 않는다.
- **현장 확인:** 빈 베이/슬롯 라벨, 라이저 P/N, 카드 간격·길이, 보조전원 커넥터, PSU 정격·중복 모드, GPU/NPU의 냉각 방식과 OEM QVL을 대조한다. 카드 이동·BIOS 변경·부하 시험은 별도 유지보수 작업으로 수행한다.
- 공개 기록에는 내부 주소·BMC 접속 정보·UUID·시리얼을 싣지 않는다. GB/TB는 제품 용량, GiB/TiB는 Linux 표시 용량으로 구분한다.

</details>

## 재확인 명령

다음 명령은 대상 노드에서 정보를 읽는다. `dmidecode`는 관리자 권한이 필요하다. 출력 전체에는 시리얼 등이 포함될 수 있어 공개 문서에는 필요한 필드만 옮긴다.

```bash
lscpu
sudo dmidecode -t slot
sudo dmidecode -t memory
sudo dmidecode -t 39
lspci -Dnn
lspci -Dtv
nvidia-smi --query-gpu=index,name,pci.bus_id,pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current,pcie.link.width.max --format=csv
nvidia-smi topo -m
lsblk -d -o NAME,SIZE,MODEL,TRAN

# 장착 장치의 현재/최대 링크와 NUMA. BDF를 실제 주소로 바꾼다.
bdf=0000:c2:00.0
for field in current_link_speed current_link_width max_link_speed max_link_width numa_node; do
  printf '%s: ' "$field"
  cat "/sys/bus/pci/devices/$bdf/$field"
done
```

이번 재확인은 `nvidia-smi`와 PCI sysfs의 링크 폭·세대를 대조하고, NVMe 컨트롤러의 sysfs 주소와 SSD 용량을 연결했다. 장치가 없는 자리의 실제 링크 속도는 측정할 수 없으므로 **설계 또는 펌웨어 후보**로 기록했다.

## 제조사 기준 문서

- [ASUS ESC4000A-E12 슬롯·전원 데이터시트](https://dlcdnets.asus.com/pub/ASUS/server/ESC4000A-E12/Datasheet/DataSheet_ESC4000A-E12_20221020.pdf), [제품 페이지](https://servers.asus.com/products/detail/overview/ESC4000A-E12)
- [ASUS ESC8000A-E12 제품·슬롯·전원](https://servers.asus.com/products/detail/overview/ESC8000A-E12)
- [ASRock Rack SPC621D8 매뉴얼: 슬롯 배선·M.2·DIMM](https://download.asrock.com/Manual/SPC621D8.pdf)
- [Furiosa RNGD 사양](https://developer.furiosa.ai/docs/v2024.2.1/en/overview/rngd.html)
- [NVIDIA RTX PRO 6000 Blackwell 제품군 사양](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000-family/)
