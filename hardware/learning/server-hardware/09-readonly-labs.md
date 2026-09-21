# 09. 읽기 전용 실습 — 서버 구성표를 스스로 완성하기

[학습 안내](README.md) · 이전: [전원·냉각·관리](08-power-cooling-serviceability.md) · 다음: [A7 설계 문제](10-a7-design-exercises.md)

이 실습의 결과물은 **부품 목록, 연결 지도, 상태 스냅샷과 미확인 항목**이다. 명령을 많이 실행하는 것이 목표가 아니다. 각 출력이 어떤 질문에 답하는지 설명할 수 있어야 한다.

아래 명령은 조회용 예시다. 이번 교재 작성에서 새로 서버에 실행하지 않았다. A7에서 이전에 실행해 확인한 결과는 [작업일지](../../npu/a7-expansion-plan-2026-09-21.md)를 기준으로 표시한다. 다른 서버에서는 장치 이름·BDF·도구 존재 여부가 다르므로 먼저 목록을 확인하고 대상을 선택한다.

## 1. 실습 전 기록할 범위

| 항목 | 기록할 내용 |
|---|---|
| 대상·시각 | 서버 별칭, 날짜, 시간대 |
| 조사 목적 | 예: GPU 슬롯 확인, RAID 구성 확인, NIC 링크 상태 확인 |
| OS·버전 | 배포판, 커널, 관련 관리 도구·드라이버·펌웨어 |
| 작업 영향 | 정보 조회. 설정·전원·구성 변경과 부하 시험은 별도 작업 |
| 결과 보관 | 내부 원본과 공개용 요약을 분리 |

필요한 도구가 없으면 “없음”으로 기록한다. 이 실습을 위해 운영 서버에 패키지를 설치하거나 드라이버를 교체하지 않는다. 민감한 식별자가 나오는 `dmidecode`, SMART, FRU, NIC 출력과 `furiosa-smi ps`의 사용자·프로세스 정보 원문을 공개 저장소에 그대로 복사하지 않는다.

```bash
date -Is
cat /etc/os-release
uname -r
command -v lscpu lspci lsblk numactl ethtool smartctl ipmitool
```

`command -v` 결과에 도구가 없다는 사실은 하드웨어가 없다는 뜻이 아니다. 관리 도구와 실제 장치를 구분한다.

## 2. CPU·메모리의 물리 구성과 OS 표시를 대조

```bash
lscpu
lscpu -e=CPU,NODE,SOCKET,CORE,ONLINE
free -h
cat /sys/devices/system/node/online
sudo dmidecode -t 16 -t 17
```

설치돼 있다면 다음 조회도 사용할 수 있다.

```bash
numactl --hardware
```

읽는 순서:

1. 소켓 수, 소켓당 코어, 코어당 스레드와 전체 논리 CPU 수를 대조한다.
2. NUMA 노드 수와 각 노드의 CPU 목록·메모리를 확인한다. 소켓 수와 같을 것이라고 미리 가정하지 않는다.
3. DIMM 항목의 `Size`, `Locator`, `Bank Locator`, `Configured Memory Speed`를 모은다.
4. `No Module Installed`는 메모리 슬롯은 있지만 DIMM이 없다는 의미로 구분한다.
5. `Maximum Capacity` 같은 SMBIOS 보고값은 OEM의 지원 DIMM 조합을 대신하지 않는다.

**A7 기준 답:** 소켓 2개, 물리 64코어·논리 128 CPU, NUMA 2개, DIMM 24자리 중 64GB 두 개만 장착. CPU별 채널 A를 사용했다. 이 구성만으로 메모리 병목이 측정됐다고 쓰지 않는다.

## 3. PCIe 트리에서 장치의 부모를 따라가기

```bash
lspci -Dnn
lspci -D -t
sudo dmidecode -t slot
ls /sys/bus/pci/slots
```

`lspci`의 BDF를 선택한 뒤 아래 조회를 한다. 이 예의 주소는 A7 작업일지에서 RAID 컨트롤러였던 주소다. 다른 서버에서 그대로 같은 장치를 뜻하지 않는다.

```bash
PCI_BDF='0000:05:00.0'
sudo lspci -D -s "$PCI_BDF" -vv
cat "/sys/bus/pci/devices/$PCI_BDF/numa_node"
readlink -f "/sys/bus/pci/devices/$PCI_BDF"
readlink -f "/sys/bus/pci/devices/$PCI_BDF/driver"
```

| 필드 | 해석 | 이 필드만으로 확정하지 않는 것 |
|---|---|---|
| 장치 ID·모델 | 어떤 PCIe 장치인가 | 최종 카드 P/N과 장착 키트 전체 |
| Physical Slot | 펌웨어가 보고한 슬롯 번호 | 실제 현장 라벨·케이블 상태 |
| LnkCap | 해당 링크가 광고하는 최대 능력 | 현재 협상 속도 |
| LnkSta | 현재 협상 속도·폭 | 실제 애플리케이션 처리량 |
| numa_node | OS가 연결 지역성으로 제공하는 값 | 프로세스 버퍼의 실제 메모리 위치 |
| sysfs 부모 경로 | endpoint가 어느 포트·스위치 아래인지 | 해당 경로의 부하와 실제 P2P 사용 여부 |

아래는 **해석 연습용 출력**이며 A7 장치의 실제 출력이 아니다.

```text
LnkCap: Speed 32GT/s, Width x16
LnkSta: Speed 16GT/s, Width x8
```

이 장치는 현재 Gen4 x8로 동작한다. 장치/슬롯/상위 경로 중 제한, 라이저 배선, 협상·신호 문제 등을 살펴야 한다. 이 두 줄만으로 고장을 확정하거나 BIOS를 바꾸지 않는다. 빈 포트의 x0는 장치가 없는 상태일 수 있다.

NUMA 값이 `-1`이면 해당 인터페이스에 지역성 정보가 제공되지 않는 상황을 고려한다. 이를 임의로 NUMA0으로 바꾸어 기록하지 않는다.

## 4. SSD에서 `/`까지 연결하기

```bash
lsblk -b -e 7 -o NAME,TYPE,SIZE,MODEL,TRAN,FSTYPE,MOUNTPOINTS
findmnt -no SOURCE,FSTYPE /
findmnt -T /data
cat /proc/mdstat
```

`mdadm`이 설치된 경우:

```bash
sudo mdadm --detail --scan
```

A7 기록에 있는 경로를 추적하는 예:

```bash
readlink -f /sys/class/block/sda/device
readlink -f /sys/class/block/nvme0n1/device
```

**A7 기준 답:** `/dev/sda2`가 ext4 루트이고 `/dev/sda`는 `MR9520-2M2`가 제공하는 논리 디스크다. 실제 물리 SSD 두 개의 RAID1이라는 사실은 `lsblk`만으로 확인한 것이 아니라 BMC의 `RAIDType`, 멤버 링크·상태와 교차 확인했다. `/data`는 별도의 `nvme0n1p1`이다.

`/proc/mdstat`에 `[raid1]`이라는 지원 이름만 보이는 것과 실제 `md0` 배열이 활성화된 것은 다르다. 반대로 md 배열이 없다고 하드웨어 RAID가 없는 것도 아니다.

SMART는 먼저 현재 접근 가능한 장치 목록을 조회한다.

```bash
sudo smartctl --scan
```

그 결과에 해당 대상이 있을 때만 타입과 번호를 사용한다. A7의 이전 조회에서는 아래 대상 두 개를 읽을 수 있었다.

```bash
sudo smartctl -i -H -d megaraid,0 /dev/bus/0
sudo smartctl -i -H -d megaraid,1 /dev/bus/0
```

위 명령은 정보·상태 조회이며 장시간 자가시험을 시작하지 않는다. 디스크 번호는 다른 서버나 구성 변경 후 달라질 수 있다. SMART 정상은 향후 고장 가능성이 없다는 보증이 아니고, RAID의 멤버·레벨·재빌드 상태를 대신하지도 않는다.

## 5. NIC의 세 숫자를 따로 기록

NIC는 **지원 포트 속도**, **현재 링크 속도**, **호스트 PCIe 속도**를 구분한다. 데이터 처리량은 그 뒤에 측정할 별도 값이다.

```bash
ip -br link
ip -br addr
```

목록에서 실제 인터페이스를 골라 조회한다. 아래 이름은 A7 기록의 관리 NIC다.

```bash
ethtool ens65f0np0
ethtool -i ens65f0np0
```

설치된 InfiniBand 장치를 확인할 때는 실제 sysfs 이름을 먼저 본다.

```bash
ls /sys/class/infiniband
cat /sys/class/infiniband/mlx5_0/ports/1/link_layer
cat /sys/class/infiniband/mlx5_0/ports/1/state
cat /sys/class/infiniband/mlx5_0/ports/1/phys_state
```

`mlx5_0`와 포트 1은 A7 당시의 이름이다. **A7 기준 답:** ConnectX-6의 포트는 InfiniBand, DOWN/Disabled였고 PCIe는 Gen4 x16이었다. 200G 지원 카드라는 사양이 현재 200G 링크를 맺었다는 뜻은 아니다. 링크가 DOWN이면 보조 속도 표시를 정상 협상값으로 채택하지 않는다.

## 6. GPU·NPU의 개수·버전·상태 조회

해당 도구가 있는 시스템에서 필요한 조회만 수행한다.

```bash
nvidia-smi
nvidia-smi topo -m
nvidia-smi --query-gpu=name,pci.bus_id,memory.total,power.limit,temperature.gpu --format=csv
furiosa-smi version
furiosa-smi info
furiosa-smi topo
furiosa-smi status
sudo furiosa-smi ps
```

장치 개수와 이름, BDF, NUMA·토폴로지, 메모리, 드라이버/펌웨어와 도구 버전을 나눠 기록한다. `furiosa-smi` 도구 버전과 커널 드라이버 버전이 반드시 같은 번호여야 하는 것은 아니다. 호환 조합인지가 중요하다.

`nvidia-smi topo`의 PIX/PXB/PHB/NODE/SYS와 `furiosa-smi topo`의 Bridge/Cpu/Interconnect는 각각 도구의 범례로 해석한다. 서로 다른 도구의 단어를 동일한 코드로 간주하지 않는다. 원격 사용자 프로세스는 권한에 따라 보이지 않을 수 있어 목록이 비었다는 해석에도 범위를 남긴다.

진단 도구의 존재와 옵션이 궁금하면 버전·도움말부터 확인한다. **진단 본 실행, P2P·stress·서빙 부하는 이 읽기 실습의 범위 밖**이다. 도구 이름만 보고 부하가 없을 것이라고 가정하지 않는다.

## 7. 전원·팬·BMC 정보 조회

로컬 IPMI 접근이 허용된 시스템에서 사용하는 읽기 명령이다.

```bash
sudo ipmitool chassis power status
sudo ipmitool fru print
sudo ipmitool sdr type 'Power Supply'
sudo ipmitool sensor list
sudo ipmitool dcmi power reading
```

전원 상태, PSU 모델·장착 수, 센서 상태와 시각을 함께 남긴다. 팬 F/R 같은 여러 속도 센서를 각각 독립 팬 모듈로 합산하지 않는다. 순간 전력은 최대 부하나 전원 이중화 가용량과 다르다.

BMC Redfish를 쓰면 읽기용 GET으로 시스템→스토리지→볼륨→멤버 드라이브 관계를 확인할 수 있다. 리소스 경로는 BMC가 반환한 링크를 따라간다. 공개 문서에 비밀번호·토큰을 넣지 않고, 설정 변경 요청과 GET을 구분한다. A7에서 사용한 리소스 이름은 [RAID 조회 기록](../../npu/a7-expansion-plan-2026-09-21.md)에 있다.

## 8. 조사 결과를 문장으로 만드는 법

| 좋지 않은 결론 | 증거에 맞는 결론 |
|---|---|
| “NIC가 200G다” | “이 P/N은 200G 지원이며 조회 시 IB 링크는 DOWN이었다” |
| “RAID 카드를 봤으니 RAID1이다” | “논리 볼륨의 RAIDType이 RAID1이고 두 Online 멤버를 확인했다” |
| “alive니까 성능 정상이다” | “SMI 조회 시 alive였다. 부하·모델 성능은 미측정이다” |
| “x16이니 네 장 모두 최고 속도다” | “endpoint 링크와 공유 상위 링크를 구분했다. 동시 처리량은 미측정이다” |
| “PSU 8개니 전력 충분하다” | “8개 Presence/OK. 정격·입력 회로·이중화 시 용량은 별도 확인이다” |

최종 결과는 **관측 → 해석 → 아직 모르는 것 → 다음 검증** 순서로 적는다. 바꾸지 않고 알 수 있는 사실을 충분히 모은 뒤에 변경 작업을 별도로 설계한다.

## 실습 과제

한 노드에 대해 다음 다섯 문장을 완성한다. 실제 서버에 접근하지 못하면 A7 일지로 연습해도 된다.

1. CPU는 __개 소켓에 __코어씩이며, OS에는 __개의 NUMA 노드가 보인다.
2. RAM은 __개 DIMM / __개 자리이고, 소켓별 사용 채널은 __이다.
3. 대상 가속기는 SLOT__ / BDF__ / NUMA__이며, 상위 링크를 __와 공유한다.
4. 루트 파일시스템은 __이고, 그 아래 물리 디스크와 RAID 관계는 __이다.
5. NIC의 지원 속도는 __, 실제 링크 상태는 __, PCIe 링크는 __이다.

빈칸을 추정으로 채우지 않는다. “미확인”을 쓰고 어떤 조회나 OEM 정보가 필요한지 적으면 올바른 조사 결과다.

[학습 안내](README.md) · 다음: [10. A7 배치 설계·종합 문제](10-a7-design-exercises.md)
