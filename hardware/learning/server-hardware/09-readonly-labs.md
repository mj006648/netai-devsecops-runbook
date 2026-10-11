# 09. 읽기 전용 실습 — 서버 구성표를 스스로 완성하기

[학습 안내](README.md) · 이전: [전원·냉각·관리](08-power-cooling-serviceability.md) · 다음: [A7 설계 문제](10-a7-design-exercises.md)

이 실습의 결과물은 **부품 목록, 연결 지도, 상태 스냅샷과 미확인 항목**이다. 명령을 많이 실행하는 것이 목표가 아니다. 각 출력이 어떤 질문에 답하는지 설명할 수 있어야 한다.

아래 명령은 조회용 예시다. 이번 교재 작성에서 새로 서버에 실행하지 않았다. A7에서 이전에 실행해 확인한 결과는 [작업일지](../../npu/a7-expansion-plan-2026-09-21.md)를 기준으로 표시한다. 다른 서버에서는 장치 이름·BDF·도구 존재 여부가 다르므로 먼저 목록을 확인하고 대상을 선택한다.

여기서 `A7`은 명령이나 하드웨어 규격이 아니라 랩 내부 서버의 고유 식별명이다. 실습의 목표는 그 서버의 값을 외우는 것이 아니라, 어떤 서버에서도 다음 조사 순서를 지키는 것이다.

아래 흐름의 **BDF(Bus:Device.Function)**는 운영체제가 PCIe 장치를 식별하는 논리 주소이고, **인터페이스(interface)**는 여기서는 OS가 NIC 포트를 다루기 위해 붙인 이름이며, **블록 장치(block device)**는 저장공간을 일정 크기 블록 단위로 읽고 쓰도록 노출한 장치다. 세 이름 모두 재부팅·장치 이동·설정에 따라 달라질 수 있으므로 물리 슬롯·모델·시리얼과 교차 확인한다.

```mermaid
flowchart LR
    SCOPE[1. 조사 범위와 시각 기록] --> LIST[2. 장치 목록 확인]
    LIST --> PICK[3. 대상 BDF/인터페이스/블록 장치 선택]
    PICK --> DETAIL[4. 세부 상태 조회]
    DETAIL --> CROSS[5. OS·BMC·OEM 자료 교차 확인]
    CROSS --> REPORT[6. 관측/해석/미확인/다음 검증 기록]
```

예제의 `nvme0n1`, `mlx5_0`, BDF를 그대로 복사하면 다른 장치를 설명할 수 있다. 출력이 없을 때도 “장치가 없다”와 “도구·권한·드라이버 때문에 보지 못했다”를 구분한다.

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


## 9. 출력 한 줄을 물리 장치까지 번역하기

명령은 운영체제에 질문을 보내는 짧은 문자열이고, **옵션**은 질문의 범위와 출력 모양을 바꾸는 표식이다. 예를 들어 \`lscpu -e=CPU,NODE,SOCKET,CORE,ONLINE\`에서 \`-e\`는 논리 CPU를 한 줄씩 펼치고, 등호 뒤 이름들은 출력할 열이다. 출력은 하드웨어 자체가 아니라 커널과 펌웨어가 현재 알고 있는 내용을 도구가 글자로 바꾼 것이다. 따라서 한 도구의 출력과 실제 섀시 라벨을 같은 것으로 취급하지 않는다.

아래 출력은 모두 **가상 교육용 예시**다. 이 문서를 쓰며 현재 서버에서 실행하지 않았으며 A7의 실제 새 측정값도 아니다.

~~~text
CPU NODE SOCKET CORE ONLINE
  0    0      0    0    yes
 64    0      0    0    yes
 32    1      1    0    yes
 96    1      1    0    yes
~~~

\`CPU\`는 운영체제가 실행 단위를 올려놓는 논리 CPU 번호다. 같은 \`CORE\`에 CPU 0과 64가 함께 있으면 하나의 물리 코어가 두 하드웨어 스레드를 제공한다는 뜻이다. \`SOCKET\`은 메인보드의 CPU 소켓, \`NODE\`는 가까운 CPU와 메모리를 묶어 커널이 만든 NUMA 노드 번호, \`ONLINE\`은 지금 스케줄러가 사용할 수 있는지다. 소켓 번호와 NUMA 번호가 우연히 같아도 둘은 다른 객체다. 펌웨어 설정에 따라 한 소켓이 여러 NUMA 노드로 나뉠 수 있다.

~~~text
available: 2 nodes (0-1)
node 0 cpus: 0-31,64-95
node 0 size: 64120 MB
node 0 free: 18200 MB
node 1 cpus: 32-63,96-127
node 1 size: 64120 MB
node 1 free: 20100 MB
node distances:
node   0   1
  0:  10  32
  1:  32  10
~~~

\`size\`는 그 노드에 연결된 메모리 중 OS가 보고하는 양이고, \`free\`는 조회 순간 즉시 비어 있다고 집계한 양이다. \`distance\`는 나노초가 아니라 커널이 비교에 쓰는 상대 비용이다. 10과 32를 보고 원격 메모리가 정확히 3.2배 느리다고 결론 내릴 수 없다. 실제 접근 시간은 주소 배치, 캐시 적중, 소켓 간 연결과 동시 부하에 따라 달라진다.

PCIe 주소 \`0000:05:00.0\`은 \`도메인:버스:장치.기능\`으로 읽는다. 도메인은 여러 PCI 주소 공간을 구분하고, 버스는 브리지 아래 구간, 장치는 그 버스의 번호, 기능은 한 장치가 제공하는 논리 기능을 구분한다. 이 주소는 카드에 새겨진 영구 시리얼이 아니다. 재장착이나 펌웨어 설정 변화로 경로가 바뀌면 BDF도 바뀔 수 있다.

~~~text
0000:05:00.0 Non-Volatile memory controller
        Physical Slot: 8
        LnkCap: Port #0, Speed 32GT/s, Width x16
        LnkSta: Speed 16GT/s, Width x8
~~~

GT/s는 초당 전송 횟수이고 GB/s는 초당 바이트 수다. 둘 사이에는 세대별 부호화와 프로토콜 오버헤드가 있으므로 \`16GT/s × 8 = 128GB/s\`로 쓰면 틀린다. Gen4 한 lane의 원시 전송률 16GT/s에 128b/130b 부호화를 적용하면 한 방향 약 1.97GB/s이고 x8은 약 15.75GB/s다. 이는 여전히 이론값이며 실제 저장장치 처리량은 컨트롤러, 플래시, 요청 크기와 큐 깊이에 막힐 수 있다.

\`LnkCap\`은 가능한 최대 광고 능력, \`LnkSta\`는 현재 협상된 상태다. x16 장치가 x8로 보일 때 슬롯 배선이 원래 x8일 수도 있고, 라이저나 신호 상태 때문에 낮아졌을 수도 있다. 모델명만으로 원인을 정하지 않는다. 부모 경로를 따라가서 endpoint, 중간 switch, root port 각각의 \`LnkSta\`를 확인하고 OEM 배선표와 맞춘다.

## 10. 저장장치 이름은 계층마다 달라진다

저장장치는 물리 SSD, RAID 컨트롤러가 만든 논리 디스크, 파티션, 파일시스템, 마운트 지점 순서로 겹쳐 보인다. **파티션**은 한 블록 장치의 주소 범위를 나눈 구역이고, **파일시스템**은 그 구역 안에서 파일 이름과 데이터 블록의 관계를 관리하는 형식이다. **마운트 지점**은 파일시스템을 디렉터리 나무의 어느 위치에 붙였는지를 뜻한다.

다음 역시 가상 출력이다.

~~~text
NAME        TYPE   SIZE FSTYPE MOUNTPOINTS PKNAME
sda         disk   960G
├─sda1      part     1G vfat   /boot/efi   sda
└─sda2      part   959G ext4   /            sda
nvme0n1     disk   7.0T
└─nvme0n1p1 part   7.0T xfs    /data        nvme0n1
~~~

\`NAME\`은 커널 장치 이름, \`TYPE\`은 전체 디스크인지 파티션인지, \`SIZE\`는 보이는 논리 용량, \`FSTYPE\`은 파일시스템 종류, \`MOUNTPOINTS\`는 붙은 디렉터리, \`PKNAME\`은 부모 장치 이름이다. 이 표만 보면 \`sda\` 뒤에 물리 SSD가 한 개인지 RAID 컨트롤러 뒤 두 개인지 알 수 없다. A7의 RAID1 판단에는 BMC가 보고한 볼륨 레벨과 두 멤버의 Online 상태가 추가로 필요했다.

NVMe에서 \`nvme0\`는 호스트와 명령을 주고받는 컨트롤러이고 \`nvme0n1\`은 그 컨트롤러가 제공하는 namespace다. namespace는 저장 주소 범위를 OS에 블록 장치로 내놓는 논리 객체다. 컨트롤러 하나가 여러 namespace를 제공할 수 있으므로 이름이 비슷하다는 이유로 같은 물리 범위라고 단정하지 않는다.

## 11. 네트워크와 가속기 출력에서 서로 다른 속도를 분리하기

가상 NIC 출력이 다음과 같다고 하자.

~~~text
ens1f0np0       UP             192.0.2.10/24
Speed: 100000Mb/s
Duplex: Full
Link detected: yes
driver: mlx5_core
firmware-version: 22.39.1002
~~~

인터페이스 이름은 커널과 udev가 포트에 붙인 이름이다. \`UP\`은 관리자가 인터페이스를 사용 상태로 올렸다는 뜻이고, \`Link detected: yes\`는 맞은편 장치와 물리 링크가 잡혔다는 뜻이다. 둘 중 하나만으로 IP 통신 성공을 보장하지 않는다. \`Speed\`는 현재 링크 협상값이고 \`100000Mb/s\`는 100Gb/s다. 애플리케이션이 100GB/s를 낸다는 뜻이 아니다. bit와 byte는 8배 차이가 있고, 프레임·프로토콜 오버헤드와 경로 병목이 있다.

가속기 도구의 \`memory.total\`은 카드의 장치 메모리 용량, \`power.limit\`은 관리 소프트웨어가 허용한 전력 상한, \`temperature.gpu\`는 특정 센서의 조회 순간 온도다. 프로세스 목록이 비어 있어도 다른 네임스페이스·권한 때문에 보이지 않을 수 있다. 또한 커널이 끝난 직후 메모리 할당이 캐시에 남을 수 있다. 그래서 “목록 없음”은 “장치가 절대로 사용되지 않음”보다 좁은 관측이다.

토폴로지 표의 행과 열은 두 장치 쌍이다. \`PIX\`처럼 한 PCIe 스위치를 거치는 표시와 \`SYS\`처럼 소켓 간 연결까지 지나는 표시는 예상 경로를 설명한다. 실제 전송이 P2P를 지원하는지, 중간에 호스트 메모리를 쓰는지는 드라이버·IOMMU·ACS·런타임 조건까지 확인해야 한다.

## 12. 읽기 전용의 정확한 경계와 조사 실패 반례

여기서 읽기 전용은 하드웨어 설정을 바꾸려는 명령이 아니라는 뜻이다. 그래도 명령은 완전히 무영향하지 않다. BMC 조회는 관리망 요청과 감사 로그를 만들 수 있고, 센서를 읽는 데 시간이 들며, \`sudo\` 사용은 인증 기록을 남긴다. SMART의 \`-i -H\`는 정보와 건강 상태 조회지만 \`-t long\`은 긴 자가시험을 시작하므로 이 장의 범위를 벗어난다. 도움말과 도구 버전으로 옵션 의미를 먼저 확인한다.

대표적인 실패를 다음처럼 구분한다.

| 관측 | 성급한 결론 | 더 정확한 해석과 다음 확인 |
|---|---|---|
| \`command -v nvidia-smi\`가 비어 있음 | GPU 없음 | 사용자 공간 도구 미설치 가능. \`lspci\`와 드라이버 상태를 별도로 확인 |
| \`numa_node\`가 \`-1\` | NUMA0 장치 | 커널이 지역성을 제공하지 않음. 부모 root port와 OEM 도면 확인 |
| NIC가 \`DOWN\` | 카드 고장 | 관리 상태, 케이블, 반대편 포트, 프로토콜 모드가 원인일 수 있음 |
| \`/proc/mdstat\`에 배열 없음 | RAID 없음 | 하드웨어 RAID가 OS에 논리 디스크 하나만 보였을 수 있음 |
| GPU 네 장이 모두 열거됨 | 네 장 병렬 성능 정상 | 인식만 확인. 링크, 전력, 온도, 오류, 실제 업무 부하는 미측정 |
| BMC 순간 전력 798W | 최대 전력 798W | 특정 시점의 측정값. 최고 부하와 장애 시 전원 여유는 미확인 |

## 13. 풀이가 있는 관측 연습

### 문제 1 — 논리 CPU를 물리 코어로 잘못 세지 않기

가상 \`lscpu\`가 socket 2개, socket당 core 32개, core당 thread 2개, CPU 128개를 보인다. 물리 코어와 논리 CPU는 몇 개인가?

**풀이:** 물리 코어는 \`2×32=64\`개다. 각 코어가 하드웨어 스레드 두 개를 제공하므로 논리 CPU는 \`64×2=128\`개다. 작업 128개가 항상 물리 코어 128개와 같은 성능을 낸다고 해석하지 않는다.

### 문제 2 — NUMA 거리표 읽기

노드0의 로컬 거리가 10, 노드1까지 32다. 노드0 CPU에서 노드1 메모리를 읽으면 정확히 3.2배 늦다고 말할 수 있는가?

**풀이:** 말할 수 없다. 값은 상대 비용이며 시간 단위가 아니다. 원격 경로를 피할 이유를 제시하는 단서지만, 실제 차이는 메모리 접근 패턴과 캐시에 따라 측정해야 한다.

### 문제 3 — 링크 폭 손실 계산

장치는 Gen5 x16을 지원하지만 현재 Gen4 x8이다. 현재 이론 한 방향 payload 근사 상한은 얼마인가?

**풀이:** Gen4는 lane당 \`16GT/s × 128/130 ÷ 8 ≈ 1.97GB/s\`다. x8이면 약 15.75GB/s다. Gen5 x16의 약 63GB/s와 비교하면 약 1/4이지만 장치 업무 처리량도 정확히 1/4이라고 단정할 수 없다.

### 문제 4 — 루트 파일시스템 경로

\`findmnt /\`가 \`/dev/sda2\`, \`lsblk\`가 sda2의 부모를 sda로 보인다. 이 정보만으로 RAID1을 증명했는가?

**풀이:** 아니다. 파티션과 논리 디스크 관계만 증명했다. RAID 레벨과 멤버는 컨트롤러나 BMC의 볼륨·멤버 상태로 교차 확인한다.

### 문제 5 — 200G 카드와 DOWN 링크

제품은 200G를 지원하지만 포트 상태가 DOWN/Disabled다. 보고서에는 어떤 문장이 맞는가?

**풀이:** “카드 사양은 200G 지원이며 조회 시 링크는 DOWN/Disabled였다”가 맞다. 실제 협상 속도나 처리량을 200G로 기록하지 않는다.

### 문제 6 — 장치 번호의 수명

NPU를 SLOT10에서 SLOT18로 옮긴 뒤에도 \`npu0\`과 기존 BDF가 같은 카드를 뜻한다고 보아도 되는가?

**풀이:** 안 된다. 열거 순서와 경로가 달라질 수 있다. 이동 전후 시리얼·물리 슬롯·새 BDF를 다시 대응시키고 응용 설정에 오래된 주소가 남았는지 확인한다.

### 문제 7 — 센서 값으로 냉각을 판정하기

유휴 상태에서 GPU 42°C, BMC 전력 798W가 보였다. 증설 후 냉각과 전원이 충분하다고 판정할 수 있는가?

**풀이:** 현재의 한 시점 상태만 말할 수 있다. 예상 최대 부하의 장치별 전력, PSU 장애 시 허용 용량, 흡기 온도, 팬 정책과 부하 상태의 온도 추세가 추가로 필요하다.

### 문제 8 — 미확인을 올바르게 쓰기

권한 부족으로 \`dmidecode\`와 BMC를 읽지 못했다. DIMM 슬롯 수와 RAID 멤버를 어떻게 적는가?

**풀이:** \`free\`가 보여 준 OS 가용 메모리와 \`lsblk\`가 보여 준 논리 장치는 관측으로 기록한다. 물리 DIMM 자리와 RAID 멤버는 “권한 때문에 미확인”으로 남기고 필요한 권한 있는 조회와 OEM 자료를 다음 검증으로 적는다. 추정 숫자로 빈칸을 채우지 않는다.


## 실습 과제

한 노드에 대해 다음 다섯 문장을 완성한다. 실제 서버에 접근하지 못하면 A7 일지로 연습해도 된다.

1. CPU는 __개 소켓에 __코어씩이며, OS에는 __개의 NUMA 노드가 보인다.
2. RAM은 __개 DIMM / __개 자리이고, 소켓별 사용 채널은 __이다.
3. 대상 가속기는 SLOT__ / BDF__ / NUMA__이며, 상위 링크를 __와 공유한다.
4. 루트 파일시스템은 __이고, 그 아래 물리 디스크와 RAID 관계는 __이다.
5. NIC의 지원 속도는 __, 실제 링크 상태는 __, PCIe 링크는 __이다.

빈칸을 추정으로 채우지 않는다. “미확인”을 쓰고 어떤 조회나 OEM 정보가 필요한지 적으면 올바른 조사 결과다.

<details>
<summary>자기 점검용 예시 답안 형식</summary>

> 2026-09-21 14:00 기준으로 OS에서 GPU 두 개를 열거했고 두 BDF의 링크 상태를 조회했다. OEM 슬롯 라벨과 BDF의 대응은 작업일지에서 교차 확인했지만 부하 처리량은 측정하지 않았으므로, “장치 두 개 인식·링크 상태 확인, 성능 미확인”으로 기록한다.

좋은 답은 숫자가 많은 답이 아니라, **어떤 명령이 무엇을 증명했고 무엇은 아직 증명하지 못했는지**가 드러나는 답이다.

</details>

[학습 안내](README.md) · 다음: [10. A7 배치 설계·종합 문제](10-a7-design-exercises.md)
