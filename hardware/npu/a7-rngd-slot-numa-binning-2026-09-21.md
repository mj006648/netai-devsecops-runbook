# A7 RNGD NPU 작업일지 — PCIe 슬롯·NUMA·binning 조회 (2026-09-21)

- 조회 시각: 2026-09-21 14:50–14:52 KST
- 서버: XFUSION G6550 V8 (Turin), 보드 BC16MBSBB V1.0
- CPU: AMD EPYC 9355 32-Core × 2, NUMA 노드 2개
- 범위: 현재 서버 읽기 전용 조회. 설정 변경, 재부팅, 카드 이동, 부하 테스트, 펌웨어 갱신은 수행하지 않음. 비밀번호는 기록하지 않음.

## Current status

- **완료:** 읽기 전용 원격 조회, 실제 PCIe/NUMA/슬롯 대조, 공식 후면 배치도 확인.
- **권고:** CARD-A(npu0)를 SLOT10에서 SLOT18로 이전. 실제 이전은 아직 하지 않았다.
- **미완료:** 현장 장착 조건 확인, 카드 이전, 이전 후 인식·토폴로지·성능 검증, CARD-B의 binning/전력 제한 원인에 대한 제조사 판정.
- **공개 범위:** 카드 실제 시리얼·UUID, 접속 계정·주소 및 인증 정보는 싣지 않는다. CARD-A/B/C/D는 이 기록의 별칭이며 실제 시리얼 매핑은 내부 기록으로 보관한다. 이동 작업에서는 내부 시리얼로 대조해야 한다.

## Symptom

NPU 4장 중 한 장만 다른 NUMA 노드에 있고, 별도의 한 장에서 binning·클럭 차이가 보고되어 이동 대상과 목적지를 확인했다. 아래 값은 2026-09-21 조회 당시의 스냅샷이다.

## 결론

**현재 서버에서 한 장을 옮긴다면 SLOT10의 npu0(카드 별칭 `CARD-A`)를 빈 SLOT18로 옮기는 안을 우선 권고한다.**

**현장 위치 요약:** 서버 후면을 바라보고 첫 블랙웰(SLOT4)을 1번으로 잡아 빈 자리를 포함해 두 슬롯 폭씩 세면, **4번 자리(SLOT10) → 8번 자리(SLOT18)**다. 꽂힌 GPU/NPU 카드만 세면 이동 대상은 왼쪽 세 번째 카드다.

SLOT18은 NUMA1이며 SLOT16의 npu3와 같은 PCIe 스위치에 연결된다. 기존 SLOT12/14의 두 장과 합쳐 NUMA1 안에서 스위치별 2장+2장 배치가 된다. 이는 연결 구조를 근거로 한 권고이며 성능 실측으로 최적임을 검증한 결과는 아니다.

장착 전 섀시의 실제 SLOT18 표기, 카드 공간, 라이저, 보조전원, 냉각 및 OEM 장착 조건을 현장에서 대조해야 한다. OS에서 빈 슬롯으로 확인했지만 물리적인 장착 가능성까지 원격으로 검증한 것은 아니다. 이 권고는 조회한 현재 서버에만 적용한다. 다른 서버로 네 장을 이전한다면 대상 서버의 슬롯 구성을 별도로 확인해야 한다.

**Binning/클럭 차이를 보이는 카드는 이동 대상 npu0가 아니라 SLOT14의 npu1(카드 별칭 `CARD-B`)이다.**

## 현장에서 찾는 위치 — 공식 설명서 기준

출처: [xFusion G6550 V8 Technical White Paper, Figure 5-15](https://www.xfusion.com/wp-content/uploads/2025/11/FusionServer-G6550-V8-Server-Technical-White-Paper.pdf#page=40), 본문 34쪽 / PDF 40쪽. 도면 이미지를 직접 확인했다.

**서버 뒤쪽(케이블·전원 연결면)을 정면으로 바라보면**, 상단 세로 확장 슬롯은 왼쪽부터 SLOT1, SLOT2, …, SLOT21 순서다. 앞에서 바라보면 이 좌우 기준을 적용할 수 없다.

왼쪽 첫 블랙웰(NVIDIA GPU, SLOT4)을 1번으로 놓고, 두 슬롯 폭의 자리 단위로 빈 자리까지 세면 다음과 같다. 카드 목록은 SSH 실측이고 좌우 순서는 공식 도면과 결합한 결과다.

| SLOT4 기준 두 슬롯 폭 자리 순서 | 실제 슬롯 | 현재 장치 |
|---|---|---|
| 1 | SLOT4 | NVIDIA GPU / 0000:04:00.0 |
| 2 | SLOT6 | NVIDIA GPU / 0000:03:00.0 |
| 3 | SLOT8 | 비어 있음(SMBIOS Available) |
| **4** | **SLOT10** | **npu0 / CARD-A — 이동할 카드** |
| 5 | SLOT12 | npu2 / CARD-C |
| 6 | SLOT14 | npu1 / CARD-B — binning 차이 카드 |
| 7 | SLOT16 | npu3 / CARD-D |
| **8** | **SLOT18** | **비어 있음 — 권장 목적지** |

따라서 이 기준에서는 **4번 자리의 카드를 8번 빈 자리로** 옮기는 안이다. 빈 자리를 제외하고 현재 꽂힌 GPU/NPU 카드만 세면 이동 대상 npu0는 왼쪽 세 번째 카드다. 위의 자리 순서는 설명용 번호이며 서버의 SLOT 번호를 대체하지 않는다. 최종 작업 전 SLOT10 카드 시리얼과 후면 방향을 대조한다.

공식 배치도:

- [공식 설명서 PDF — PDF 40쪽 / 본문 34쪽](https://www.xfusion.com/wp-content/uploads/2025/11/FusionServer-G6550-V8-Server-Technical-White-Paper.pdf#page=40)

설명서 그림은 라벨을 덧붙인 도면이다. 실제 장비에 인쇄된 글씨의 위치·가독성까지 확인한 것은 아니므로 후면 상단 슬롯 열과 공식 도면을 대조한다.

## 1. 현재 카드 식별표

| 조회 시 장치 | 카드 별칭 | 현재 슬롯 | PCI-BDF | NUMA | 현재 PCIe 링크 | 클럭 | 권고 |
|---|---|---|---|---|---|---|---|
| npu0 | CARD-A | SLOT10 | 0000:81:00.0 | 0 | 32GT/s x16 | 2000MHz | SLOT18로 이동 후보 |
| npu1 | CARD-B | SLOT14 | 0000:9d:00.0 | 1 | 32GT/s x16 | 1700MHz | 위치 유지, 전력 제한·binning 별도 문의 |
| npu2 | CARD-C | SLOT12 | 0000:9e:00.0 | 1 | 32GT/s x16 | 2000MHz | 유지 |
| npu3 | CARD-D | SLOT16 | 0000:e4:00.0 | 1 | 32GT/s x16 | 2000MHz | 유지 |

네 장 모두 P/N `RNGA0UNO-04`, 펌웨어 `2026.2.2, c96cc0d`, governor `Performance`, Liveness `alive`. 조회 시 메모리 사용량은 각 0.00/47.50GiB이고 `sudo furiosa-smi ps`의 점유 프로세스 목록은 비어 있었다. 장치 번호와 BDF는 이동 후 바뀔 수 있으므로 시리얼로 추적한다.

슬롯 매핑은 SMBIOS `dmidecode`, `lspci`의 Physical Slot 및 `/sys/bus/pci/slots/*/address`를 대조했다.

## 2. Diagnosis — 실제 토폴로지

```text
NUMA0
  PCIe 스위치 0000:7b:00.0
    ├─ 7c:02.0 → 7f:00.0  NVME9 / Samsung NVMe
    └─ 7c:04.0 → 81:00.0  SLOT10 / npu0  ← 이동 대상

NUMA1
  PCIe 스위치 0000:9b:00.0 (상위 링크 32GT/s x16)
    ├─ 9c:00.0 → 9d:00.0  SLOT14 / npu1
    ├─ 9c:01.0 → 9e:00.0  SLOT12 / npu2
    └─ 9c:02.0 → [비어 있음] SLOT20

  PCIe 스위치 0000:e1:00.0 (상위 링크 32GT/s x16)
    ├─ e2:00.0 → [비어 있음] SLOT18  ← 권장 목적지
    ├─ e2:01.0 → e4:00.0  SLOT16 / npu3
    └─ e2:04.0 → [비어 있음] SLOT21
```

`furiosa-smi topo` 실제 출력 요약:

| 장치 | npu0 | npu1 | npu2 | npu3 | NUMA |
|---|---|---|---|---|---|
| npu0 | Noc | Interconnect | Interconnect | Interconnect | 0 |
| npu1 | Interconnect | Noc | Bridge | Cpu | 1 |
| npu2 | Interconnect | Bridge | Noc | Cpu | 1 |
| npu3 | Interconnect | Cpu | Cpu | Noc | 1 |

NPU0와 NVMe가 같은 스위치 아래 있다는 사실은 확인했다. 다만 실제 대역폭 경합이나 성능 저하는 측정하지 않았다.

## 3. 목적지 후보 비교

| 슬롯 | 연결 포트 | NUMA | 포트 지원 능력 | 조회된 상태 | 판단 |
|---|---|---|---|---|---|
| SLOT18 | 0000:e2:00.0 | 1 | 32GT/s x16 | Available / PresDet- / x0 | 우선 후보: npu3와 같은 스위치, 2+2 배치 |
| SLOT21 | 0000:e2:04.0 | 1 | 32GT/s x16 | Available / PresDet- / x0 | 동일 스위치이나 RNGD 장착 지원 미확인; 즉시 대체 목적지로 사용하지 않음 |
| SLOT20 | 0000:9c:02.0 | 1 | 32GT/s x16 | Available / PresDet- / x0 | 같은 NUMA지만 스위치별 3+1 배치가 됨 |

SLOT18은 SMBIOS의 `Designation: SLOT18`, 포트의 `Slot #18`, sysfs 슬롯 주소 `0000:e3:00`으로 교차 확인했다. 비어 있는 포트의 현재 `2.5GT/s x0`는 장착 카드가 없는 상태의 표시이며 장착 후 동작 속도를 뜻하지 않는다.

SLOT18과 SLOT21은 같은 스위치에 연결되지만 같은 물리 베이가 아니다. 공식 설명서의 후면 GPU double-width 베이는 SLOT4/5부터 SLOT18/19까지이므로, SLOT20/21의 RNGD 장착 지원은 별도 확인이 필요하다. SLOT18을 우선 제시하되 물리적인 장착 여건은 현장 확인 대상이다. SLOT20보다 2+2 배치를 우선하는 것은 상위 링크 사용을 분산하는 설계 판단이며, 실제 워크로드에 따른 최적 배치는 측정이 필요하다.

이동 후 예상: 네 장 모두 NUMA1, 이동 카드와 기존 npu3 사이 `Bridge`, 기존 npu1/npu2 사이 `Bridge`, 두 스위치 사이 카드 관계는 `Cpu`. 네 장 모두 서로 `Bridge`가 되는 배치는 아니다.

## 4. ACS 조회 결과

세 목적지 후보 포트 모두 다음 값을 보였다.

```text
ACSCtl: SrcValid+ TransBlk- ReqRedir+ CmpltRedir+ UpstreamFwd+ EgressCtrl- DirectTrans-
```

리다이렉션 비트가 활성화돼 있다. 같은 스위치로 옮겨도 직접 P2P 경로나 성능 향상을 보장하지 않는다. 이번 작업에서는 ACS/IOMMU/BIOS 설정을 변경하지 않았다. 목적은 우선 npu0의 소켓 간 경로를 없애는 것이다.

## 5. Binning 및 클럭·전력 제한 차이 — Root cause 미확정

`/sys/kernel/debug/rngd/mgmt*/binning_result`와 관리 sysfs 값을 읽었다.

| 항목 | npu0 / mgmt0 | npu1 / mgmt1 | npu2 / mgmt2 | npu3 / mgmt3 |
|---|---|---|---|---|
| PE0–7 binning | 모두 0x0001 | **PE2만 0x0162**, 나머지 0x0001 | 모두 0x0001 | 모두 0x0001 |
| HBM binning | 0x0003 | 0x0003 | 0x0003 | 0x0003 |
| PE 클럭 | 모두 2GHz | 모두 1.7GHz | 모두 2GHz | 모두 2GHz |
| throttle_reason | 0x00000000 | **0x00000004** | 0x00000000 | 0x00000000 |
| power_limit_mw | 300000 | **225000** | 300000 | 300000 |
| power_limit_default_mw | 300000 | 300000 | 300000 | 300000 |
| power_max_mw (원시 값) | 675000 | **225000** | 675000 | 675000 |
| npu_freq_limit_hz (원시 값) | 2147483000 | 2147483000 | 2147483000 | 2147483000 |

설치된 드라이버가 제공하는 `throttle_reason_list`에서 `0x00000004`는 `THROTTLE_APP_POWER_CAP`이다. npu1에는 전력 제한 표시와 binning 차이가 함께 존재한다. 이것만으로 binning이 전력 제한을 일으켰는지, 제한의 설정 주체가 누구인지, 카드 등급이나 불량 여부가 무엇인지는 확정할 수 없다. `power_max_mw` 원시 값 역시 실제 허용 전력으로 해석하거나 설정에 사용하지 않는다.

따라서 SLOT14의 카드를 단순히 옮기거나 전력 제한을 올리는 조치는 권고하지 않는다. 공급자에게 다음 내용으로 확인하는 것이 적절하다.

> 카드 별칭 CARD-B(SLOT14, 현재 npu1)만 PE2 binning_result=0x0162이며, 나머지 PE 및 다른 카드의 PE는 0x0001입니다. 모든 카드의 FW는 2026.2.2/c96cc0d, governor는 Performance입니다. 해당 카드는 1.7GHz, THROTTLE_APP_POWER_CAP(0x4), power_limit_mw=225000, power_max_mw=225000이며 default는 300000입니다. 다른 카드는 2GHz, power_limit_mw=300000입니다. 정상 출하 구성인지, 제한의 원인과 지원되는 조치가 무엇인지 확인 부탁드립니다.

이 메시지는 초안이며 외부로 전송하지 않았다.

## 6. 버전 및 수집 명령

- Ubuntu 24.04.4 LTS / kernel 6.8.0-136-generic
- furiosa-smi CLI 2026.1.1 / 패키지 2026.1.1-4
- device driver 2026.3.1, e28c5c0
- furiosa-toolkit-rngd 2026.2.1-4

주요 조회:

```bash
furiosa-smi info --format full
furiosa-smi info --format json
furiosa-smi topo
furiosa-smi status
sudo furiosa-smi ps
furiosa-smi version
lscpu
lspci -D -t
sudo dmidecode -t system -t baseboard -t slot
sudo lspci -D -s 0000:e2:00.0 -vv
cat /sys/bus/pci/slots/18/address
cat /sys/bus/pci/devices/0000:e2:00.0/numa_node
cat '/sys/class/rngd_mgmt/rngd!npu1mgmt/throttle_reason_list'
sudo cat /sys/kernel/debug/rngd/mgmt1/binning_result
sudo cat /sys/kernel/debug/rngd/mgmt1/power_limit_mw
```

`rngd-diag --help`도 조회했다. 실제 옵션은 `--no-hal-bench --no-stress-test`이며, 메모의 `--no-stres-test`는 오타다. 진단 본 실행과 벤치마크는 수행하지 않았다.

## 7. Fix 계획 — 실제 이동은 이번에 실행하지 않음

1. SLOT10 카드의 내부 시리얼(CARD-A와 대조) 및 목적지 SLOT18의 실제 라벨·공간·전원·냉각 조건 대조.
2. 작업 시간 확보 후 정상 종료 및 OEM 전원 차단 절차로 카드 이전.
3. 부팅 후 시리얼로 카드 재식별. NPU 번호/BDF 유지 여부를 가정하지 않음.
4. 네 장 인식, alive, 각 PCIe 링크 32GT/s x16, 네 장 NUMA1 및 예상 topo 확인.
5. 이후 별도 합의된 유휴 시간에 동일 조건으로 진단/P2P/모델 성능 검증.

이번 보고서의 완료 범위는 실제 조회 근거에 따른 이동 대상·목적지 후보 식별이다. 물리 이전 및 성능 개선 검증은 아직 수행하지 않았다.

## Prevention / 다음 작업 기록

다음 작업은 같은 문서의 새 날짜 구간 또는 NPU 디렉터리의 별도 일지로 기록한다. 확인하지 않은 항목을 완료로 바꾸지 않는다.

- [ ] 섀시 후면 방향, SLOT10 카드 내부 시리얼, SLOT18의 공간·보조전원·냉각 확인
- [ ] 정상 종료 및 OEM 전원 차단 절차 후 카드 이전
- [ ] 이전 후 카드 별칭 ↔ 실제 시리얼 ↔ 새 장치 번호/BDF/슬롯 매핑 기록
- [ ] 네 장 alive, NUMA1, 각 링크 32GT/s x16 및 예상 토폴로지 확인
- [ ] 유휴 작업 시간에 동일 버전·설정으로 진단 및 P2P 성능 비교
- [ ] CARD-B의 PE2 binning=0x0162, 225W 제한 및 1.7GHz 동작에 대한 제조사 답변 기록

전후 비교에는 커널·드라이버·펌웨어·도구 버전과 ACS/governor 조건을 함께 남긴다. 공개 일지에는 실제 시리얼이나 인증 정보를 추가하지 않는다.

## 참고

- [NPU 작업일지 목록](README.md)
- [공식 G6550 V8 설명서 — Figure 5-15](https://www.xfusion.com/wp-content/uploads/2025/11/FusionServer-G6550-V8-Server-Technical-White-Paper.pdf#page=40)
- [Furiosa SMI CLI](https://developer.furiosa.ai/latest/en/device_management/system_management_interface/furiosa_smi_cli.html)
- [Furiosa Host PCI Optimization Tuning](https://developer.furiosa.ai/latest/en/device_management/host_tuning.html)
