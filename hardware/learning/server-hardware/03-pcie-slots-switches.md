# 03. PCIe·슬롯·스위치: 카드가 CPU까지 가는 길

[학습 목차](README.md) · [이전: CPU·메모리·NUMA](02-cpu-memory-numa.md) · [다음: 스토리지·RAID·부팅](04-storage-raid-boot.md)

PCIe(Peripheral Component Interconnect Express)는 GPU·NPU·NIC·NVMe 같은 장치와 CPU가 데이터를 주고받는 연결이다. 카드를 어디에 꽂았는지만으로 속도나 장치 간 직접 통신을 판단할 수 없다. **물리 자리**, **전기적으로 훈련된 링크**, **실제로 협상된 세대·폭**, **CPU까지의 경로**, **동시에 쓰는 다른 장치**를 함께 본다. A7 예시는 [2026-09-21 실측 작업일지](../../npu/a7-expansion-plan-2026-09-21.md)의 구성과 그때의 미확정 사항을 사용한다.

PCI-SIG의 공식 사양 목록을 2026-09-22에 확인하면 PCI Express Base Specification의 current approved revision은 **7.1, 2026-09-17**로 표시된다. 이 장의 A7 계산은 관측된 Gen5 링크를 대상으로 하며, Gen6/Gen7의 FLIT/PAM4 방식까지 A7에 적용됐다고 주장하지 않는다. [PCI-SIG PCI Express Base](https://pcisig.com/specification-overview/pci-express-base).

## 1. 경로를 따라 용어 익히기

```text
CPU / PCIe 루트 컴플렉스(root complex)
  └─ 루트 포트(root port)
       └─ 상위 링크(uplink): Gen5 x16
            └─ PCIe 스위치
                 ├─ 하위 포트 → SLOT8  → 빈 자리 / GPU 후보
                 ├─ 하위 포트 → SLOT10 → 현재 NPU
                 └─ 하위 포트 → NVME9  → NVMe SSD
```

이 그림은 A7 그룹 B를 단순화한 경로다. SLOT8은 현재 빈 자리이며 GPU는 배치 후보일 뿐이다. 연결 가능성과 장착 확정은 구분한다.

**루트 컴플렉스**는 CPU 쪽 PCIe 계층의 시작점이다. **루트 포트**는 그 계층에서 아래 장치로 나가는 포트다. **PCIe 스위치**는 하나의 상위 링크를 여러 하위 포트로 연결하고 패킷을 전달한다. 스위치가 있다고 CPU 방향 링크의 처리량이 자동으로 늘지는 않는다. PCIe **브리지**는 버스를 잇는 기능 이름이며, 루트 포트·스위치 포트도 OS의 PCI 계층에서 브리지로 나타날 수 있다. “브리지로 보인다”가 곧 별도 물리 스위치 한 대를 뜻하지 않는다. [Linux PCI 문서](https://docs.kernel.org/PCI/pci.html).

**버스(bus)**는 장치를 열거하는 논리 구획이다. OS의 PCI 주소 **BDF**(Bus:Device.Function)는 장치를 식별하는 버스·장치·기능 번호이며, 앞에 도메인(segment)을 붙이면 `0000:81:00.0` 같은 형태가 된다. 여기서 `81`은 16진수 버스 번호이지 물리 SLOT81이 아니다. 카드 이동, BIOS 설정, 열거 순서 변경 뒤 BDF는 달라질 수 있다. 실물 카드의 슬롯 라벨·시리얼과 OS 주소를 대조한다.

**슬롯**은 카드를 꽂는 물리 위치다. **라이저(riser)**는 슬롯의 방향·위치를 바꾸는 보드, **백플레인(backplane)**은 여러 드라이브나 장치 연결을 모으는 보드다. 이 부품과 케이블의 종류가 실제 연결·공간·전원·냉각 조건을 정한다. **bifurcation**은 CPU 쪽 레인 묶음을 예를 들어 x16 하나 대신 x8+x8 또는 x4 네 개처럼 분할하는 구성이다. 스위치와 달리 새 레인을 만들지 않으며, 보드·BIOS·라이저가 지원해야 한다.

### 스위치, 리타이머, 분할은 같은 일이 아니다

PCIe **리타이머(retimer)**는 긴 배선·케이블에서 약해진 신호를 다시 정렬해 전달하는 부품이다. PCIe 스위치처럼 여러 장치의 패킷을 라우팅하거나 장치 수를 늘리지 않는다. 리타이머를 지나도 양 끝 장치가 협상한 링크의 레인 수와 상위 포트 한계가 그대로 중요하다. [PCI-SIG의 리타이머 설명](https://pcisig.com/blog/pci-express%C2%AE-retimers-vs-redrivers-eye-popping-difference).

예를 들어 CPU의 x16 묶음을 두 개의 x8 포트로 나누는 것은 **bifurcation**이다. CPU의 x16 포트와 여러 x16 하위 포트를 가진 부품을 잇는 것은 **스위치**다. 긴 신호 경로를 보완하는 것은 **리타이머**다. 세 방식 모두 CPU에서 출발하는 레인을 마술처럼 추가하지 않는다.

## 2. 전기적 링크: 레인은 두 쌍의 고속 길이다

**PCIe 레인(lane)**은 한 방향 송신 differential pair와 한 방향 수신 differential pair로 이루어진 기본 연결 단위다. 쉬운 뜻은 “보내는 길 하나와 받는 길 하나가 짝을 이룬 왕복 차선”이다. 왜 필요할까? 한 레인의 속도를 높이고 여러 레인을 묶어 x4, x8, x16처럼 대역폭을 키울 수 있다. 기작은 각 레인이 고속 직렬 신호를 보내고, 링크 계층이 여러 레인을 묶어 패킷을 전달하는 것이다. 도로 차선 비유의 한계는 PCIe 레인이 차처럼 충돌을 피하며 달리는 길이 아니라, 클록 복구·equalization·encoding을 거치는 전기 신호 경로라는 점이다.

**차동 신호(differential signaling)**는 두 선의 전압 차이로 0과 1을 표현하는 방식이다. 쉬운 뜻은 “한 선의 절대 전압보다 두 선의 차이를 읽는 방법”이다. 왜 필요할까? 고속 신호에서 외부 잡음이 두 선에 비슷하게 들어오면 차이를 읽어 일부를 상쇄할 수 있다. 기작은 송신기가 한 쌍의 선을 서로 반대 방향으로 흔들고 수신기가 두 선의 차이를 판정하는 것이다. 비유의 한계는 실제 고속 링크는 단순 잡음 제거만이 아니라 impedance, loss, crosstalk, jitter, equalization까지 포함한다는 점이다.

**링크 훈련(link training)**은 장치와 상대 포트가 사용할 세대, 레인 수, 신호 보정 값을 맞추는 절차다. 쉬운 뜻은 “두 장치가 대화하기 전에 속도와 발음을 맞추는 일”이다. 왜 필요할까? 카드, 라이저, 케이블, 스위치, 슬롯마다 지원 능력과 신호 품질이 다르다. 기작은 링크가 낮은 속도에서 시작해 공통 능력과 신호 상태를 확인하고 가능한 속도·폭으로 올라가는 것이다. 대화 비유의 한계는 링크 훈련이 사람의 협상이 아니라 상태 기계와 전기 측정에 가까운 자동 절차라는 점이다.

## 3. 레인·세대·속도를 따로 읽기

**레인(lane)**은 송신용과 수신용 경로를 가진 PCIe 연결의 기본 단위다. `x16`은 레인 16개를 사용한다는 뜻이고 `Gen5`는 PCIe 5세대 링크라는 뜻이다. 장치·상대 포트·중간 배선의 공통 지원 범위와 신호 상태에 따라 실제 링크 세대·폭이 협상된다. x16 길이의 커넥터가 항상 x16으로 연결되는 것은 아니다.

**GT/s**는 초당 전송 심볼 수를 나타내며 **GB/s**(초당 바이트 수)와 다르다. PCIe 3·4·5세대는 128b/130b 인코딩을 사용하므로, 한 방향의 인코딩 반영 이론값은 다음처럼 계산한다. 아래 값은 전송 패킷 등의 추가 오버헤드 *전*이다. [PCI-SIG 세대별 신호·인코딩 표](https://pcisig.com/sites/default/files/files/PCI-SIG%20Cabling%20Webinar_FINAL.pdf).

```text
한 방향 GB/s = GT/s × (128 / 130) × 레인 수 ÷ 8
Gen5 x16 = 32 × (128 / 130) × 16 ÷ 8 ≈ 63.02 GB/s
```

| 실제 링크 | GT/s·레인 | x8 한 방향 | x16 한 방향 |
|---|---:|---:|---:|
| PCIe Gen3 | 8 | 약 7.88GB/s | 약 15.75GB/s |
| PCIe Gen4 | 16 | 약 15.75GB/s | 약 31.51GB/s |
| PCIe Gen5 | 32 | 약 31.51GB/s | 약 63.02GB/s |

PCIe는 **전이중(full duplex)**으로 양방향 동시 통신이 가능하다. Gen5 x16의 “약 63GB/s”는 **각 방향의 상한**이다. 마케팅 자료에서 송신·수신을 더해 약 126GB/s 또는 128GB/s라고 표현해도 한 방향에 그 전부를 쓸 수 없다. 트랜잭션 계층 패킷(TLP) 헤더, 흐름 제어, 작은 전송, 프로토콜 및 장치 처리 비용 때문에 애플리케이션 처리량은 위 표보다 낮을 수 있다. [PCI-SIG 5.0 설명](https://pcisig.com/what-bit-rates-does-pcie-50-specification-support-and-how-does-it-compare-prior-pcie-generations).

Gen6와 Gen7은 PAM4 신호 방식과 FLIT(고정 크기 전송 단위), FEC(전방 오류 정정)를 사용한다. 따라서 위의 **128/130 식을 Gen6/7 숫자에 그대로 대입하지 않는다**. 이 장의 A7 측정 경로는 Gen5까지다. [PCI-SIG Gen6 기술 설명](https://pcisig.com/blog/evolution-pci-express-specification-its-sixth-generation-third-decade-and-still-going-strong), [Gen7 설명](https://pcisig.com/blog/pcie-70-specification-next-generation-performance-meet-needs-advanced-ai-applications-webinar).

### 왜 x16 카드가 x8로 보일까

우선 카드가 지원하는 **최대 링크**와 운영 중 **현재 링크**를 구분한다. 카드가 x16이어도 라이저가 x8만 배선했거나, 포트가 x8+x8로 분할됐거나, 상대 포트가 x8이라면 실제 링크는 x8일 수 있다. 신호 품질이나 접촉 문제 때문에 폭 또는 세대가 낮아지는 경우도 있다. 이것은 가능한 원인 목록이며, A7의 특정 카드에 그런 고장이 있다는 진단은 아니다.

정상 축소인지 문제인지 판단할 때는 카드 사양, OEM 슬롯 배선·라이저, BIOS 설정, 실제 링크 상태, 오류 로그를 같은 카드에 대해 대조한다. 커넥터 외형, BMC의 슬롯 지원 능력, Linux의 현재 협상 결과는 서로 다른 정보를 준다. 리타이머가 있다는 사실만으로 x16이 보장되지 않는다.

링크 세대는 두 끝의 공통 능력으로 제한된다. Gen5 슬롯에 Gen4 NIC를 꽂아도 NIC가 Gen5로 업그레이드되지 않는다. 반대로 Gen5 카드가 낮은 세대 포트에 연결되면 링크는 낮은 세대로 동작할 수 있다. 상위 링크와 하위 링크의 세대도 별도로 관측해야 한다.

## 4. A7의 네 스위치 그룹과 공유 링크

A7 작업일지는 네 개의 **논리적 스위치 그룹 A/B/C/D**를 분류했다. 이 이름은 설명용이며 물리 스위치 보드 네 장이라는 뜻이 아니다. 관측한 상위 포트는 모두 **32GT/s x16 = Gen5 x16**이다. 각 그룹에서 여러 장치가 같은 CPU 방향 링크를 공유한다.

| 그룹 | NUMA | 상위 포트 BDF | 아래에서 확인된 자리·장치 |
|---|---:|---|---|
| A | 0 | `0000:01:00.0` | GPU SLOT4/6, 부팅 RAID SLOT2 |
| B | 0 | `0000:7b:00.0` | SLOT3/8/10, NVME9의 데이터 SSD |
| C | 1 | `0000:9b:00.0` | SLOT12/14/20 |
| D | 1 | `0000:e1:00.0` | SLOT16/18/21 |

GPU 두 장이 각각 Gen5 x16 하위 연결을 사용할 수 있어도, 두 장이 동시에 **호스트 메모리**로 대량 전송하면 같은 상위 링크 약 63GB/s(한 방향 이론값)를 나눠 쓴다. “하위 슬롯 두 개 × 63 = 호스트 방향 126GB/s”라는 계산은 여기서 성립하지 않는다. 실제 경쟁 정도는 전송 방향·시점·크기와 스위치 내부 경로에 따라 달라진다.

### 공유 링크를 워크로드로 해석하기

| 동시에 일어나는 일 | 중요한 경로 | 단순 판단이 왜 틀릴까 |
|---|---|---|
| 그룹 A GPU 둘이 각각 호스트 RAM에서 입력을 읽음 | 두 하위 링크 → 그룹 A 상위 링크 → CPU·RAM | 상위 링크를 공유하므로 하위 x16 둘을 합산할 수 없음 |
| 그룹 B NVMe가 호스트로 읽고 GPU도 호스트로 보냄 | 둘의 방향·시점에 따라 상위 링크 | 같은 스위치여도 항상 같은 방향으로 경쟁하지 않음 |
| 같은 스위치의 장치끼리 직접 DMA | 스위치 내부 또는 루트 쪽 | ACS·드라이버·플랫폼 정책이 경로를 바꿀 수 있음 |
| CPU0 장치가 CPU1 메모리에 DMA | PCIe 외에 소켓 간 경로도 관여 | PCIe 링크 수치만으로 전체 대역폭·지연을 설명 못 함 |

따라서 슬롯 배치 결론은 “같은 스위치인가”에서 끝나지 않는다. 데이터가 **어디서 시작해 어디서 끝나는지**, 어느 방향으로 동시에 흐르는지, CPU·메모리의 NUMA 위치가 어딘지, 실제 전송이 P2P인지 호스트 경유인지 확인한다. A7 작업일지는 토폴로지를 관측했지만 이 모든 경로의 실측 처리량을 보장하지 않는다.

스위치 아래 장치끼리의 P2P(peer-to-peer) 통신은 상위 링크를 반드시 왕복한다고 단정할 수도 없다. **ACS**(Access Control Services) 리다이렉션 설정과 플랫폼·드라이버 지원에 따라 스위치 내부로 전달되거나 루트 쪽으로 보낼 수 있다. Linux의 [PCI P2P DMA 문서](https://docs.kernel.org/driver-api/pci/p2pdma.html)는 스위치·ACS가 경로 판단에 영향을 준다고 설명한다. A7의 후보 포트에서는 ACS 리다이렉션이 켜진 것으로 관측됐다. 같은 스위치라는 이유만으로 직접 전송 성공을 보증하지 않는다.

**NVMe SSD와 GPU가 같은 스위치에 있으면 안 된다**는 규칙도 없다. 그룹 B에서 호스트를 향한 동시 I/O가 크면 상위 링크 경쟁이 생길 수 있다. 반면 지원되는 GPU·NVMe P2P 경로에서는 가까운 PCIe 배치가 유리할 수도 있다. 경로·ACS·드라이버 지원과 실제 작업량을 확인해 판단한다. [NVIDIA GPUDirect Storage 가이드](https://docs.nvidia.com/gpudirect-storage/best-practices-guide/index.html).

## 5. BDF, configuration space, BAR를 읽는 법

**BDF(Bus:Device.Function)**는 PCIe 장치를 OS가 식별하는 논리 주소다. 쉬운 뜻은 “PCIe 장치의 행정 주소”다. 왜 필요할까? CPU와 OS가 여러 장치를 구분하고 드라이버를 붙여야 한다. 기작은 firmware와 OS가 PCIe fabric을 열거하며 bus 번호를 부여하고, 각 device/function의 configuration space를 읽는 것이다. 주소 비유의 한계는 BDF가 물리 슬롯 번호가 아니며 부팅 설정과 장치 이동에 따라 달라질 수 있다는 점이다.

**configuration space**는 PCIe 장치가 자기 정체성과 제어 정보를 노출하는 표준 레지스터 공간이다. 쉬운 뜻은 “장치의 신분증과 설정표”다. 왜 필요할까? OS는 vendor ID, device ID, class code, capability, BAR 정보를 읽어 어떤 드라이버가 필요한지 판단한다. 기작은 root complex가 configuration transaction으로 각 function의 표준 영역을 읽고 쓴다. 신분증 비유의 한계는 여기에 성능 측정값이 전부 들어 있는 것이 아니고, 실제 동작은 드라이버와 장치 내부 상태가 함께 결정한다는 점이다. Linux PCI 문서는 PCI 장치 식별과 드라이버 모델을 설명한다. [Linux PCI documentation](https://docs.kernel.org/PCI/pci.html).

**BAR(Base Address Register)**는 장치의 MMIO 또는 I/O 영역을 시스템 주소 공간 어디에 배치할지 나타내는 configuration register다. 쉬운 뜻은 “장치 레지스터 창문의 주소표”다. 왜 필요할까? CPU가 장치 제어 레지스터나 doorbell에 접근하려면 주소 공간 어딘가에 장치 창을 매핑해야 한다. 기작은 OS가 BAR 크기를 파악하고 주소를 배정한 뒤 드라이버가 그 영역을 매핑해 읽고 쓴다. 창문 비유의 한계는 BAR를 읽는다고 장치 메모리 전체를 일반 RAM처럼 마음대로 쓰는 것은 아니라는 점이다.

### 열거 추적 예

```text
1. firmware/OS가 root port 아래 bus를 스캔한다.
2. 어떤 function에서 vendor ID와 device ID가 유효하게 읽힌다.
3. OS가 class code를 보고 NVMe, VGA, network 같은 장치 종류를 분류한다.
4. capability list에서 PCIe, MSI/MSI-X, ACS 같은 기능을 확인한다.
5. BAR 크기를 확인하고 MMIO 주소를 배정한다.
6. matching driver가 장치를 claim하고 초기화한다.
```

이 과정 때문에 “장치가 물리적으로 꽂힘”, “PCIe 링크가 올라옴”, “OS가 BDF를 부여함”, “드라이버가 정상 초기화함”, “애플리케이션이 성능을 냄”은 모두 다른 단계다. 어느 단계에서 멈췄는지 구분해야 장애를 줄일 수 있다.

## 6. NUMA, P2P, ACS, IOMMU는 서로 다른 질문

| 개념 | 답하는 질문 | 한계 |
|---|---|---|
| NUMA 근접성 | 장치가 어느 CPU·메모리 영역과 가까운가? | 장치 간 직접 전송 보장은 아님 |
| 같은 PCIe 스위치 | 두 장치의 물리 경로가 어디서 만나는가? | ACS·드라이버에 따라 실제 패킷 경로가 달라짐 |
| P2P | 장치가 호스트 RAM을 경유하지 않고 서로 DMA할 수 있는가? | 토폴로지와 소프트웨어 지원이 모두 필요 |
| ACS | PCIe 패킷 전달·격리·리다이렉션을 어떻게 제어하는가? | “같은 스위치”의 효과를 바꿀 수 있음 |
| IOMMU | DMA 주소를 어떻게 변환·격리하는가? | NUMA나 스위치 구조 자체를 바꾸지 않음 |

DMA(Direct Memory Access)는 장치가 CPU의 바이트별 복사 개입 없이 메모리에 접근하는 방식이다. IOMMU(Input-Output Memory Management Unit)는 그 DMA 주소 변환·접근 제어에 관여한다. ACS나 IOMMU를 임의로 끄면 격리·보안·운영 안정성에 영향을 줄 수 있다. 이 학습자료는 설정 변경을 권하지 않는다. 장치 간 GPU 전용 연결인 **NVLink**는 PCIe와 다른 기술이며 [07. 가속기 인터커넥트 장](07-accelerator-interconnects.md)에서 별도로 다룬다.

### DMA와 IOMMU 주소 추적

Linux DMA API 문서는 CPU 가상 주소, CPU 물리 주소, 장치가 보는 bus/DMA 주소가 다를 수 있다고 설명한다. [Linux Dynamic DMA mapping Guide](https://www.kernel.org/doc/html/v6.6/core-api/dma-api-howto.html).

```text
1. 드라이버가 커널 버퍼를 준비한다.
   CPU가 보는 주소: virtual address X

2. 페이지 테이블이 X를 실제 RAM 위치로 매핑한다.
   CPU physical address: Y

3. 드라이버가 DMA mapping API를 호출한다.
   IOMMU가 DMA address Z -> physical Y 변환을 준비할 수 있다.

4. 드라이버가 장치의 descriptor ring에 Z와 길이를 써 준다.

5. 장치가 PCIe transaction으로 DMA address Z에 읽기 또는 쓰기를 수행한다.

6. IOMMU가 Z를 Y로 변환하고 권한을 검사한다.

7. 전송이 끝나면 장치가 completion 상태를 쓰거나 interrupt를 보낸다.
```

이 추적에서 CPU가 `memcpy`로 모든 바이트를 옮기지 않는다는 점이 DMA의 핵심이다. 그러나 CPU가 전혀 관여하지 않는다는 뜻은 아니다. 드라이버는 버퍼 준비, DMA mapping, descriptor 작성, 동기화, 완료 처리를 맡는다. 캐시 일관성이 자동으로 보장되지 않는 플랫폼에서는 DMA 전후 cache maintenance도 필요할 수 있다.

**MSI-X(Message Signaled Interrupts eXtended)**는 장치가 별도 interrupt 핀을 흔드는 대신 메모리 쓰기 형태의 메시지로 인터럽트를 알리는 PCI 기능이다. 쉬운 뜻은 “장치가 정해진 주소에 완료 알림 쪽지를 쓰는 방식”이다. 왜 필요할까? 고성능 NIC나 NVMe는 여러 큐와 CPU에 interrupt를 나눠 처리해야 한다. 기작은 장치가 MSI-X table의 vector별 주소와 데이터를 사용해 interrupt message를 발생시키는 것이다. 쪽지 비유의 한계는 실제 interrupt routing은 APIC/interrupt remapping/IOMMU/커널 설정과 함께 움직인다는 점이다. Linux MSI HOWTO는 MSI/MSI-X 사용 조건과 드라이버 API를 설명한다. [Linux MSI Driver Guide HOWTO](https://cdn.kernel.org/doc/html/latest/PCI/msi-howto.html).

### P2P 가능성과 성능은 별도로 확인

P2P가 가능하다는 말은 장치 두 개가 특정 DMA 경로를 사용할 수 있다는 뜻이다. 그 경로가 일반적인 호스트 경유보다 늘 빠르다는 뜻은 아니다. 작은 전송에서는 설정·동기화 비용이 더 클 수도 있고, 전송 대상 장치의 메모리 등록과 드라이버 기능이 필요할 수 있다. GPU와 NPU 사이의 지원 조건은 제조사 스택마다 다르다.

**ACS**는 브리지나 스위치 포트에서 패킷 전달 방향과 격리 정책을 제어한다. **IOMMU**는 장치 DMA 주소 공간을 관리한다. 둘은 역할이 다르지만 특정 P2P 시나리오의 가능성·안전성에 함께 영향을 줄 수 있다. Linux 커널은 루트 포트 위로 올라가는 경로의 P2P를 무조건 허용하지 않는다. [Linux P2P DMA 문서](https://docs.kernel.org/driver-api/pci/p2pdma.html).

## 7. 빈 자리, 지원 자리, 장착 가능한 자리는 다르다

실제 슬롯 선정에는 최소 네 층위가 있다.

1. **라벨**: `SLOT10`처럼 섀시에 쓰인 위치 번호를 확인한다.
2. **전기적 연결**: 슬롯의 지원 세대·폭과 카드 장착 뒤 협상된 세대·폭을 구분한다. 빈 슬롯의 `x0` 표시는 현재 장치가 없음을 나타낼 수 있다.
3. **물리 공간**: 카드 길이·높이·두께, 인접 슬롯 점유, 라이저·케이블·백플레인·브래킷이 맞아야 한다.
4. **운영 조건**: 카드의 전원·냉각·펌웨어·OEM 지원과 같은 그룹의 기존 장치 대역폭을 확인한다.

A7에서 매핑된 큰 가속기 자리는 **SLOT4/6/8/10/12/14/16/18의 여덟 곳**이다. 공식 백서는 8개 double-width GPU 배치를 설명하지만, 현재 제품 페이지에는 10개 GPU 사양도 있다. 둘의 옵션·개정·BOM 차이가 확정되지 않았다. 따라서 **현 장비에 매핑한 여덟 자리를 넘는 확장을 확정하지 않는다**. SLOT20/21을 큰 GPU·NPU용 자리로 세지도 않는다. [xFusion 백서 후면 도면](https://www.xfusion.com/wp-content/uploads/2025/11/FusionServer-G6550-V8-Server-Technical-White-Paper.pdf#page=40), [현행 제품 페이지](https://www.xfusion.com/en/product/ai-servers/fusionserver-g6550-v8-ai), [A7 작업일지](../../npu/a7-expansion-plan-2026-09-21.md).

추가 NIC 후보도 “가까워 보인다”만으로 결정하지 않는다. GPU 쪽 SLOT3은 NUMA0·그룹 B라서 SLOT8/10 및 NVME9와 상위 링크를 공유한다. NPU 쪽 SLOT20 또는 SLOT21은 NUMA1이지만 각각 그룹 C 또는 D에 속한다. NIC 한 장이 NPU 네 장 모두와 같은 스위치에 놓이는 것은 아니다. 카드 형태·연결 폭·망 용도·실제 통신 상대를 확인해야 한다.

> **스위치와 소켓 구별**: PCIe 스위치는 서버 안에서 PCIe 장치를 잇는다. Ethernet/InfiniBand 네트워크 스위치는 NIC가 케이블로 연결되는 외부 장비다. “CPU 소켓을 바꾼다”는 말은 장치를 어느 CPU의 PCIe 루트에 가깝게 놓을지의 문제이며, 네트워크 스위치 포트 변경과 같은 작업이 아니다.

### A7 슬롯 선택을 종이에 그려 보기

예를 들어 네트워크 카드 한 장을 GPU 통신에 쓸 계획이라면 첫 질문은 “100G 카드인가?”가 아니다. 통신 상대 GPU가 어느 그룹에 있는지, NIC가 어느 그룹 아래에 놓일지, NIC의 실제 PCIe 세대·폭은 무엇인지가 먼저다. SLOT3을 후보로 잡으면 NUMA0·그룹 B에 놓이지만, 기존 SLOT4/6 GPU는 그룹 A다. 같은 NUMA라는 사실과 같은 스위치라는 사실은 다르다.

NPU 쪽 후보 SLOT20은 그룹 C, SLOT21은 그룹 D다. NPU가 C와 D에 나뉘면 어느 NIC도 네 장 모두와 동일한 스위치에 있지는 않다. NIC 자체가 x16을 지원해도 OEM 배선과 실제 협상 결과가 x8이면 계산에는 x8을 넣는다. 상위 그룹 링크, NIC 링크, 네트워크 케이블 속도는 서로 다른 세 개의 제한이다.

후보를 고른 뒤에도 물리 크기와 냉각을 확인한다. 이 서버의 SLOT20/21이 비었다는 것과 두 슬롯 폭의 큰 가속기를 수용한다는 것은 다른 주장이다. 제품 페이지의 최대 GPU 숫자와 현 장비의 BOM도 같은 개념이 아니다.

### 링크 문제와 대역폭 경쟁을 구별

**협상 문제**는 특정 카드의 링크가 예상 Gen5 x16 대신 Gen4 x8 등으로 보이는 경우다. 먼저 카드·포트의 최대 능력, 라이저 배선, 분할 설정, 신호 품질과 오류를 확인한다. **경쟁 문제**는 링크가 정상 Gen5 x16이어도 같은 상위 링크 아래 장치가 동시에 사용해 처리량을 나누는 경우다.

두 문제는 관측 시점도 다르다. 링크 속도·폭 표시는 연결 상태의 속성이고, 처리량은 작업 중의 측정값이다. 빈 슬롯에 카드가 없을 때 표시된 x0이나 지원 가능 최대치만으로 어느 문제도 판정할 수 없다.

### 병목 계산: PCIe, NIC, 스위치 상위 링크

대역폭 병목은 한 숫자로 끝나지 않는다. 세 구간을 따로 놓고 작은 값을 찾은 뒤, 공유 여부를 다시 본다.

```text
가상 NIC:
  네트워크 포트 = 100Gb/s = 12.5GB/s
  PCIe 링크 = Gen4 x8 ≈ 15.75GB/s 한 방향
  같은 PCIe 스위치 상위 링크 = Gen5 x16 ≈ 63.02GB/s 한 방향

NIC 한 장만 호스트로 받는다면:
  min(12.5, 15.75, 63.02) = 12.5GB/s 전후가 선로 쪽 상한

같은 스위치 아래 NIC 네 장이 동시에 100G를 모두 호스트로 밀면:
  네트워크 합 = 12.5 × 4 = 50GB/s
  상위 링크 = 63.02GB/s
  숫자상 상위 링크는 충분해 보인다.

하지만 같은 순간 GPU 두 장이 각각 20GB/s씩 호스트로 보낸다면:
  총 요구 = 50 + 20 + 20 = 90GB/s
  상위 링크 63.02GB/s보다 크므로 공유 링크 경쟁을 예상해야 한다.
```

이 산수는 패킷 오버헤드, DMA 효율, CPU 처리, NUMA, 소프트웨어 큐를 제외한 1차 거름망이다. 그래도 “NIC PCIe 링크는 충분한데 스위치 상위 링크가 붐빈다”와 “네트워크 선로 자체가 작다”를 분리하는 데 도움이 된다.

### 100G NIC를 대역폭으로만 살펴보면

네트워크의 **100Gb/s**는 초당 100기가비트이며, 8로 나누면 초당 **12.5GB**다. 이것도 네트워크 선로 쪽 비트율을 바이트로 바꾼 값일 뿐, 애플리케이션의 유효 데이터 처리량은 아니다. NIC가 호스트 메모리와 한 방향으로 이 속도에 가까운 데이터를 주고받으려면 PCIe 쪽에도 충분한 여유가 있어야 한다.

Gen3 x8의 한 방향 이론값 **7.88GB/s**는 12.5GB/s보다 작다. 따라서 한 포트 100G의 최대 선로 속도를 호스트로 그대로 넘길 경로로는 부족하다. Gen4 x8의 **15.75GB/s**는 숫자상 12.5GB/s보다 크지만, 패킷·DMA·동시 트래픽 비용이 남아 있으므로 실제 성능을 보증하지 않는다. 카드의 포트 수와 실제 PCIe 협상 폭, 스위치 상위 링크 공유까지 함께 계산한다. [A7 작업일지의 NIC 검토](../../npu/a7-expansion-plan-2026-09-21.md).

이 비교는 NIC 구매를 결정하는 표가 아니다. 네트워크 스위치 포트, 케이블·광모듈, Ethernet과 InfiniBand의 사용 목적, 드라이버와 실제 작업의 메시지 크기도 필요하다. 해당 주제는 [06. 네트워크·RDMA 장](06-networking-rdma.md)에서 다룬다.

### 슬롯 배치 검토 기록에 남길 최소 정보

| 기록 | 목적 |
|---|---|
| 카드 모델·물리 SLOT 라벨 | 주문 사양과 실제 장착 위치를 연결 |
| 장착 전 슬롯 지원 능력·라이저 옵션 | 계획의 전기적·기계적 가능성 확인 |
| 장착 후 BDF·현재 링크 세대·폭 | 예상 배선과 실제 협상 결과 비교 |
| 루트·스위치 경로와 NUMA 번호 | 상위 링크 공유와 소켓 근접성 확인 |
| 같은 그룹의 기존 장치 | 동시 전송 때 경쟁 가능성 검토 |
| 카드 전원·크기·냉각·OEM 승인 | 링크가 정상이어도 운용 가능한지 확인 |

BDF는 재열거될 수 있으므로 카드 식별 정보와 실물 슬롯 라벨을 함께 남긴다. 지원 가능한 최대 링크와 **장착 뒤 현재 링크**도 별개 열로 기록해야 나중에 x8 표시의 원인을 조사할 수 있다.

## 8. 스스로 계산해 보기

1. Gen4 x8 링크와 Gen5 x16 링크의 한 방향 인코딩 반영 이론값은 각각 얼마인가?
2. 가상으로 그룹 B의 하위 GPU 두 장이 각각 Gen5 x16으로 호스트에 동시에 같은 방향 전송할 때, 그룹 B 상위 링크가 제공하는 이론 상한은 얼마인가?
3. `0000:81:00.0`의 `81`을 SLOT81로 적어도 되는가? 카드를 옮기면 무엇을 다시 확인해야 하는가?
4. 100G NIC 두 장이 같은 Gen4 x8 하위 링크가 아니라 각각 Gen4 x8로 연결되어 있고, 같은 Gen5 x16 상위 링크를 공유한다. 두 NIC가 동시에 한 방향 최고 선로 속도를 낸다면 상위 링크만 보면 충분한가?
5. DMA에서 CPU virtual address X, physical address Y, DMA address Z가 모두 같은 숫자라고 가정해도 되는가?

<details>
<summary>해설 보기</summary>

1. `16 × 128/130 × 8/8` = **약 15.75GB/s**, `32 × 128/130 × 16/8` = **약 63.02GB/s**다. 둘 다 한 방향, 패킷 오버헤드 전이다.
2. 그룹 B 상위 링크는 **약 63.02GB/s**다. 장치 하위 링크 둘의 속도를 더해 호스트 방향 상한으로 쓰지 않는다.
3. 안 된다. `81`은 16진수 PCI 버스 번호다. 이동 뒤에는 실물 슬롯 라벨·카드 식별 정보·새 BDF·협상 링크·NUMA·스위치 경로를 다시 대조한다.
4. 100G 두 장의 선로 합은 `12.5 × 2 = 25GB/s`다. 상위 Gen5 x16의 63.02GB/s보다 작으므로 상위 링크만 보면 충분하다. 그러나 각 NIC의 실제 PCIe 협상, 패킷 처리, NUMA, CPU, 네트워크 스위치 포트는 별도 확인이 필요하다.
5. 안 된다. 단순 시스템에서는 같을 수 있지만 일반적으로 CPU 가상 주소, CPU 물리 주소, DMA/bus 주소는 다른 주소 공간이다. IOMMU가 Z를 Y로 변환할 수 있다.

</details>

## 9. 흔한 오해 바로잡기

- “x16 커넥터면 실제로 Gen5 x16이다” → 장착 뒤 협상된 세대와 폭을 확인해야 한다.
- “PCIe 스위치가 레인과 CPU 방향 대역폭을 늘린다” → 여러 하위 경로가 상위 링크를 공유한다.
- “같은 NUMA면 P2P가 된다” → NUMA는 CPU·메모리 근접성의 표현이다.
- “NVMe와 GPU의 스위치 공유는 금지다” → 경합 가능성과 P2P 가능성을 실제 경로·작업량으로 판단한다.
- “BDF의 버스 번호가 슬롯 번호다” → 논리 주소와 물리 라벨은 따로 기록한다.
- “양방향 128GB/s이니 단방향 128GB/s다” → 송신·수신의 상한을 각각 계산한다.
- “BDF가 보이면 드라이버와 성능도 정상이다” → 열거, 드라이버 초기화, 실제 처리량은 다른 단계다.
- “DMA는 CPU를 전혀 쓰지 않는다” → 바이트 복사는 장치가 하지만 드라이버, mapping, 동기화, 완료 처리는 CPU와 OS가 맡는다.
- “MSI-X는 성능을 무조건 올리는 스위치다” → 큐, interrupt affinity, 드라이버, 워크로드가 함께 맞아야 한다.

## Primary Sources

- PCI-SIG, [PCI Express Base specification overview](https://pcisig.com/specification-overview/pci-express-base), [PCIe 5.0 bit rates FAQ](https://pcisig.com/what-bit-rates-does-pcie-50-specification-support-and-how-does-it-compare-prior-pcie-generations)
- Linux Kernel, [PCI documentation](https://docs.kernel.org/PCI/pci.html), [PCI Peer-to-Peer DMA](https://docs.kernel.org/driver-api/pci/p2pdma.html), [Dynamic DMA mapping Guide](https://www.kernel.org/doc/html/v6.6/core-api/dma-api-howto.html), [MSI Driver Guide HOWTO](https://cdn.kernel.org/doc/html/latest/PCI/msi-howto.html)
- PCI-SIG, [PCI Express Retimers vs. Redrivers](https://pcisig.com/blog/pci-express%C2%AE-retimers-vs-redrivers-eye-popping-difference)
- NVIDIA, [GPUDirect Storage Best Practices Guide](https://docs.nvidia.com/gpudirect-storage/best-practices-guide/index.html)
- xFusion, [FusionServer G6550 V8 AI product page](https://www.xfusion.com/en/product/ai-servers/fusionserver-g6550-v8-ai)

다음 장에서는 PCIe 뒤에 있는 **부팅 RAID와 데이터 SSD**가 OS에서 어떻게 보이는지 살펴본다.
