# 07. NVLink·UALink·CXL — 최신 연결 기술을 같은 기준으로 읽기

[학습 안내](README.md) · 이전: [NIC·RDMA](06-networking-rdma.md) · 다음: [전원·냉각·관리](08-power-cooling-serviceability.md)

공식 자료 확인 기준은 **2026-09-21**이다. 이 장은 기술 이름뿐 아니라 연결 대상, 프로토콜의 역할, 제품 지원 상태, 숫자의 집계 범위를 비교한다. 표준의 발표와 구매 가능한 제품, 실제 서버에 설치된 기능은 각각 다른 증거가 필요하다.

## 1. 왜 PCIe 외에 다른 연결이 필요한가?

카드 한 장에 모델과 작업이 모두 들어가면 계산 중 다른 가속기와 통신할 필요가 작을 수 있다. 모델을 여러 장에 나누면 중간 텐서를 전달하거나 합쳐야 한다. TP의 layer별 collective, MoE의 expert 사이 전달, 분산 학습의 gradient 동기화가 대표적인 예다.

연산기를 늘렸는데 매번 다른 카드의 결과를 기다리면 성능이 기대만큼 늘지 않는다. PCIe는 다양한 장치를 연결하는 범용 I/O이고, 별도의 가속기 연결은 많은 가속기 사이의 대역폭·지연·확장성을 다른 방식으로 설계한다.

단순한 전송 시간 모델을 먼저 기억하자.

```text
통신 시간 ≈ 고정 지연 α + 메시지 크기 S / 유효 대역폭 B
```

작은 메시지에서는 α와 동기화 횟수가 중요하다. 큰 메시지에서는 B와 혼잡·공유 링크가 중요해진다. 높은 peak bandwidth 하나만으로 모든 통신이 빨라진다고 결론 낼 수 없다.

## 2. Scale-up과 scale-out은 상자 개수를 세는 말이 아니다

**Scale-up**은 서로 밀접하게 통신하는 가속기 집합을 큰 실행 영역으로 묶는 데 초점을 둔다. **Scale-out**은 여러 서버·실행 집합을 네트워크로 확장하는 데 초점을 둔다. 업계에서 용어를 사용하는 경계에는 차이가 있지만, “scale-up은 무조건 서버 한 대 내부”라는 정의는 현재 시스템에 맞지 않는다.

```text
         가속기들이 밀접하게 통신하는 scale-up 영역
   GPU ─┐                                  ┌─ GPU
   GPU ─┼──── NVLink 또는 UALink fabric ────┼─ GPU
   GPU ─┘                                  └─ GPU
          여러 트레이·서버에 걸칠 수도 있음
                         ↕ NIC
           Ethernet / InfiniBand scale-out 망
                         ↕ NIC
                  다른 실행 영역·서버
```

NVIDIA **GB200 NVL72**는 72 GPU와 36 Grace CPU를 **한 랙**에 연결하는 사례다. 독립 트레이와 스위치가 있다고 해서 scale-up이 아닌 것도 아니고, NVL72라는 이름이 임의의 여러 랙을 뜻하는 것도 아니다. [GB200 NVL72 공식 설명](https://www.nvidia.com/en-us/data-center/gb200-nvl72/).

## 3. 먼저 비교할 역할 지도

| 기술 | 주로 연결하는 대상 | 중심 역할 | 구분할 점 |
|---|---|---|---|
| PCIe | CPU 루트와 NIC·SSD·가속기 | 범용 I/O, DMA, 지원되는 P2P | 물리 슬롯·세대·레인·스위치 공유를 확인 |
| NVLink | 지원되는 NVIDIA GPU 등 정해진 endpoint | 높은 대역폭의 가속기 통신 | 모든 NVIDIA GPU의 기능이 아님 |
| NVSwitch | NVLink endpoint들 | NVLink 패브릭의 스위칭 | GPU도 Ethernet 스위치도 아님 |
| NVLink-C2C | 지원되는 CPU·GPU superchip 등의 칩 | 플랫폼 내부의 고속·일관성 연결 | GPU↔GPU NVLink와 대상·대역폭을 분리 |
| UALink | 지원하는 가속기와 UALink 스위치 | 공개 규격의 AI scale-up 연결 | 일반 Ethernet 포트로 자동 변환되지 않음 |
| Ethernet / InfiniBand | 서버 NIC와 네트워크 스위치 | 서버 사이 데이터 통신 | 구체적인 RDMA/혼잡 제어·배선이 필요 |
| Ultra Ethernet | UEC를 구현하는 NIC·Ethernet 네트워크 | AI/HPC scale-out을 위한 통신 스택 | 기존 Ethernet 카드가 자동으로 전 기능을 얻지 않음 |
| CXL | CPU·메모리 장치·가속기 등 | 지원 타입의 메모리 접근·일관성·확장 | GPU collective 링크와 같은 제품 범주가 아님 |

패브릭(fabric)은 여러 endpoint와 스위치·링크를 연결한 통신 구조를 뜻한다. 케이블 하나의 이름이 아니다. endpoint, 스위치, 관리 소프트웨어와 애플리케이션 지원을 함께 봐야 한다.

## 4. NVLink와 NVSwitch

NVLink는 해당 기능을 갖춘 GPU 등의 endpoint 사이에 사용하는 NVIDIA의 연결 기술이다. PCIe 기반 서버에서도 특정 GPU는 별도 NVLink 연결을 가질 수 있지만, 그 GPU와 보드·토폴로지가 지원해야 한다. 과거 일부 카드의 브리지 형태를 오늘의 모든 GPU에 적용하지 않는다.

NVSwitch는 여러 NVLink 연결 사이에서 트래픽을 전달한다. GPU 각각을 모든 GPU와 직접 케이블로 연결하지 않고도 큰 연결 구성을 만들 수 있게 한다. 스위치가 있다는 사실만으로 모든 트래픽 패턴이 동일한 성능을 내거나 총 집계 대역폭을 한 GPU가 독점할 수 있는 것은 아니다.

**NVLink로 연결돼도 GPU들의 물리 메모리가 사라지고 하나의 무제한 RAM이 되는 것은 아니다.** 주소 지정, 원격 접근, 복제·분할, 동기화와 일관성은 지원 하드웨어·소프트웨어의 규칙을 따른다. 모델을 어떻게 나누고 통신할지는 프레임워크와 프로그램이 결정한다.

NVIDIA HGX B200의 예는 8개 GPU, 5세대 NVLink 및 4세대 NVSwitch를 사용한다. **NVLink 세대와 NVSwitch 세대의 숫자가 항상 같지는 않다.** [NVIDIA HGX 구성 설명](https://docs.nvidia.com/enterprise-reference-architectures/hgx-ai-factory-h100-h200-b200/latest/components.html).

### 제품과 세대가 지정된 대역폭 예

아래 수치는 제조사의 집계 사양이다. 응용프로그램이 측정한 payload 처리량이 아니다.

| 대상 | 기술 | 공식 표기 | 범위·방향 | 근거 |
|---|---|---|---|---|
| Hopper GPU | 4세대 NVLink | 900GB/s | GPU당 양방향 합산 | [Hopper](https://www.nvidia.com/en-us/data-center/technologies/hopper-architecture/) |
| Blackwell B200 | 5세대 NVLink | 1.8TB/s | GPU당 양방향 합산 | [HGX B200](https://docs.nvidia.com/enterprise-reference-architectures/hgx-ai-factory-h100-h200-b200/latest/components.html) |
| GB200 superchip | NVLink-C2C | 900GB/s | CPU↔GPU 연결의 양방향 합산 | [GB200](https://www.nvidia.com/en-us/data-center/gb200-nvl72/) |
| Rubin 발표 사양 | 6세대 NVLink | 3.6TB/s | GPU당 양방향 합산 | [2026-01-05 NVIDIA 발표](https://nvidianews.nvidia.com/news/rubin-platform-ai-supercomputer) |

1.8TB/s와 900GB/s를 보고 전자가 모든 의미에서 두 배라고 말하기 전에, 첫 번째는 GPU↔GPU 영역이고 두 번째 GB200 수치는 CPU↔GPU C2C임을 구분한다. 링크 대상과 집계 범위가 다르다.

### 우리 Blackwell 카드에는 NVLink가 있는가?

**RTX PRO 6000 Blackwell Server Edition은 NVIDIA 공식 표에서 `NVLink Support: No`다.** 이 제품은 PCIe 5.0 기반 96GB GDDR7 카드이며, HGX B200의 SXM GPU와 같은 제품이 아니다. Blackwell이라는 아키텍처 이름이 같다고 NVLink 기능까지 같지는 않다. [NVIDIA 공식 제품 비교표, 2026-08-19 갱신본](https://docs.nvidia.com/vgpu/sizing/virtual-workstation/latest/gpus-vws.html).

따라서 현재 A7 GPU 네 장을 NVLink 케이블로 묶는 안을 만들 수 없다. 현재 검토할 경로는 PCIe와 소프트웨어가 지원하는 통신 방식이다. RNGD와 RTX를 한 모델의 동종 장치처럼 묶는 기능도 별도 런타임 지원 없이 생기지 않는다. 두 종류의 가속기로 서로 다른 서비스를 운영하는 것과, 하나의 모델을 이종 장치에 분할하는 것은 다른 설계다.

## 5. NVLink-C2C와 NVLink Fusion

NVLink-C2C는 Grace Hopper/Grace Blackwell 같은 지원 플랫폼에서 CPU와 GPU 사이의 고속 연결과 일관성 기능에 사용된다. CPU 쪽 주소와 GPU 메모리에 대한 접근을 시스템 설계로 통합하는 사례다. AMD EPYC 보드의 일반 PCIe 슬롯에 GPU를 꽂는 것만으로 이 superchip 연결이 만들어지지는 않는다.

**NVLink Fusion**은 NVIDIA가 2025-05-18 발표한 semi-custom AI 인프라용 파트너 설계·실리콘 생태계다. 비-NVIDIA CPU나 맞춤 가속기를 포함하는 설계를 지향하지만, 아무 PCIe 카드나 기존 NVLink 장치와 연결할 수 있는 범용 변환기의 이름은 아니다. endpoint 실리콘, 시스템과 파트너 솔루션의 지원을 확인해야 한다. [NVIDIA NVLink Fusion 발표](https://nvidianews.nvidia.com/news/nvidia-nvlink-fusion-semi-custom-ai-infrastructure-partner-ecosystem).

“공개된 파트너 계획”, “설계 솔루션 제공”, “완성 시스템의 출하”도 구분한다. 제휴 기업 목록은 우리 카드의 호환 목록을 대신하지 않는다.

## 6. UALink — 공개 규격의 가속기 scale-up

UALink는 **Ultra Accelerator Link**다. 가속기와 스위치를 연결하는 AI/HPC scale-up 규격이며, endpoint 사이의 메모리 읽기·쓰기와 atomic 같은 동작을 다루는 데 초점을 둔다. atomic은 여러 실행 주체가 같은 값에 접근할 때 정해진 연산을 쪼개지지 않는 동작으로 처리하는 기능이다. atomic 지원만으로 모든 메모리가 전역 캐시 일관성을 자동으로 갖는다는 뜻은 아니다.

UALink 200G 1.0은 **2025-04-08** 공개됐고, lane당 200G급 연결과 최대 1,024 가속기의 규모를 설명한다. 이것은 규격의 설계 범위다. 아무 서버에 카드 1,024개를 추가할 수 있다는 뜻이 아니다. [UALink 1.0 공식 발표](https://ualinkconsortium.org/wp-content/uploads/2025/04/UALink-1.0-Specification-PR_FINAL.pdf).

### Ethernet PHY를 사용하면 Ethernet 스위치를 써도 되는가?

그렇지 않다. PHY는 전기·광 신호를 보내는 물리 계층이다. 그 위에서 어떤 패킷·트랜잭션과 흐름 제어를 사용할지는 별개다. UALink는 Ethernet 계열 물리 기술을 활용하면서 UALink의 프로토콜 계층을 정의한다. **UALink endpoint와 UALink 스위치 구현이 필요**하다. [UALink 1.0 백서](https://ualinkconsortium.org/wp-content/uploads/2025/04/UALink-1.0-White_Paper_v3.pdf).

비슷한 커넥터나 케이블을 사용할 수 있다는 설명을 프로토콜 호환성으로 바꾸면 안 된다. 이는 QSFP 형태의 포트가 있다고 Ethernet/InfiniBand가 저절로 상호 변환되지 않는 것과 같은 구분이다.

### 2026년에는 어디까지 공개됐는가?

**2026-04-07 공개된 UALink 2.0 관련 규격은 이미 공개·비준된 상태**다. 단순한 향후 계획으로 적지 않는다. 구성은 Common 2.0, 200G Data Link/Physical Layers 2.0, Manageability 1.0, Chiplet 1.0 등이다. in-network compute와 관리·칩렛 통합을 확장한다. [UALink 2.0 공식 발표](https://ualinkconsortium.org/wp-content/uploads/2026/04/UALink-2.0-Specification-PR_FINAL.pdf).

In-network compute는 통신 경로에서 지원되는 집계 같은 연산을 수행해 endpoint의 이동·처리 부담을 줄이는 접근이다. 스위치가 임의의 모델 전체를 대신 실행한다는 뜻은 아니다. 어떤 연산을 어느 장치가 지원하는지는 실제 구현을 본다.

규격 공개가 현재 구매 가능한 모든 가속기·스위치의 상호 호환을 증명하지는 않는다. consortium의 로드맵도 회원사의 구현과 상용 배포 목표를 별도로 설명한다. 이 교재에서는 **A7의 RNGD·RTX·스위치가 UALink를 지원한다고 확인하지 않았다.** [UALink 로드맵](https://ualinkconsortium.org/blog/ualink-roadmap-insights-accelerating-open-scalable-ai-networking-1296/).

## 7. Ultra Ethernet은 UALink와 무엇이 다른가?

**Ultra Ethernet Consortium(UEC)**은 AI/HPC의 Ethernet 기반 scale-out 통신을 위한 스택을 정의한다. 전송 계층, 혼잡과 패킷 전달, NIC·네트워크 구현을 함께 다룬다. 기존 Ethernet 생태계를 이용한다는 점과 새로운 전송 기능이 실제로 구현돼야 한다는 점을 동시에 기억한다.

UALink가 밀접한 가속기 집합의 scale-up 메모리 트랜잭션 연결을 중심으로 한다면, Ultra Ethernet은 서버·실행 집합 사이 Ethernet 통신을 중심으로 한다. 서로 경쟁하는 부분을 논의할 수는 있지만 같은 케이블의 두 상표처럼 취급하면 기술 계층을 놓친다.

UEC의 최초 1.0 공개는 **2025-06-11**, 2026-09-21 확인 시 최신 공개판은 **1.0.3(2026-07-16)**이다. 이미 설치한 ConnectX-6나 Ethernet 스위치가 이 규격을 자동으로 전부 구현한다고 쓰지 않는다. [UEC 공개 버전 이력](https://ultraethernet.org/specification-history/), [UEC 1.0 발표](https://ultraethernet.org/ultra-ethernet-consortium-uec-launches-specification-1-0-transforming-ethernet-for-ai-and-hpc-at-scale/).

RoCE와 Ultra Ethernet도 같은 이름이 아니다. 06장에서 본 기존 RDMA 스택과 어떤 호환·전환 경로를 제품이 제공하는지는 NIC·드라이버·네트워크의 구체적인 지원 문서로 확인한다.

## 8. CXL — 메모리를 확장·공유하는 다른 축

**Compute Express Link(CXL)**는 CPU, 메모리 확장 장치와 가속기 사이의 메모리 접근·일관성을 다루는 연결 기술이다. PCIe와 물리적 기반을 공유하지만, PCIe 카드라면 모두 CXL 장치인 것은 아니다.

| 구성 요소 | 기본 역할 |
|---|---|
| CXL.io | 장치 탐색·설정 등 I/O 기반 기능 |
| CXL.cache | 지원 장치가 호스트 메모리를 일관성 있게 캐시하는 프로토콜 |
| CXL.mem | 호스트가 장치에 연결된 메모리에 접근하는 프로토콜 |
| Type 1 | 장치 자체 메모리 없이 캐시 접근을 사용하는 유형 |
| Type 2 | 장치 메모리와 cache/mem 기능을 사용하는 가속기 유형 |
| Type 3 | 메모리 확장 중심 유형, 일반적으로 io/mem 사용 |

세부 기능은 장치 유형과 버전·협상에 달려 있다. CXL.cache는 모든 구성에서 필수가 아니며, 호스트·장치·스위치·BIOS·OS의 구현이 함께 맞아야 한다. [CXL 4.0 규격 §2.1–2.2](https://computeexpresslink.org/wp-content/uploads/2025/11/CXL-Specification_rev4p0_ver1p0_2025November17_clean_evalcopy.pdf).

**메모리 확장**은 호스트가 이용할 수 있는 메모리를 추가하는 것이고, **풀링**은 여러 호스트에 배정할 메모리 자원을 구성하는 개념이다. **공유**와 **캐시 일관성**은 별도의 기능·규칙이다. 모든 pooled memory가 모든 호스트에게 동시에 같은 주소로 보인다고 가정하지 않는다.

CXL 메모리도 접근 경로의 대역폭과 지연이 있다. 기존 CPU에 직결된 DDR과 동일한 성능이라고 단정할 수 없고, NUMA·메모리 계층·데이터 배치가 다시 중요해진다. 128GB RAM 문제를 해결한다며 CXL 장치를 무조건 구매하기 전에 이 서버의 호스트 지원부터 확인해야 한다.

CXL 4.0은 **2025년 11월 공개된 규격**이며 128GT/s, bundled port와 메모리 RAS 확장을 설명한다. 규격의 128GT/s를 128GB/s로 읽지 않는다. **CXL 4.0 공개 ≠ 우리 EPYC 보드의 CXL 4.0 지원**이다. GPU간 collective를 위한 NVLink를 대체한다고 일반화하지도 않는다. [CXL 공식 개요](https://computeexpresslink.org/about-cxl/).

## 보충: Infinity Fabric·UCIe·CPO는 어느 위치인가?

**AMD Infinity Fabric/xGMI:** AMD 공식 문서는 xGMI를 Infinity Fabric 기반 GPU 간 고속 연결로 설명한다. AMD CPU 내부·소켓 연결 문맥의 Infinity Fabric과 가속기 제품의 xGMI를 같은 커넥터로 이해하면 안 된다. 지원 Instinct SKU와 OAM/baseboard·토폴로지 조건을 확인한다. AMD가 UALink 생태계에 참여한다는 사실만으로 기존 Instinct 제품이 모두 UALink endpoint가 되지는 않는다. [AMD xGMI 문서](https://instinct.docs.amd.com/projects/virt-drv/en/mainline-9.0.0.k/userguides/XGMI_configuration.html), [AMD MI300 계열 플랫폼](https://www.amd.com/en/products/accelerators/instinct/mi300.html).

**UCIe(Universal Chiplet Interconnect Express):** 주로 하나의 패키지 안에 있는 여러 die/chiplet 사이의 연결 규격이다. 칩렛은 큰 칩을 여러 작은 반도체 조각으로 구성하는 설계 단위다. 패키지 내부 연결, 카드 사이 연결, 랙 사이 연결을 같은 계층으로 놓지 않는다. UALink 2.0의 Chiplet 규격은 이 설계 계층과의 접점을 다루지만, UCIe 자체가 랙의 GPU 스위치라는 뜻은 아니다. [UCIe 공식 규격 소개](https://www.uciexpress.org/specifications).

**CPO(Co-Packaged Optics):** 스위치 ASIC 등에 가까운 패키지/기판에 광 부품을 배치하는 접근이다. 멀리 있는 광 모듈까지 고속 전기 신호를 보내는 경로의 전력·신호 문제를 줄이는 것을 목표로 한다. CPO는 Ethernet이나 UALink 같은 상위 통신 프로토콜의 이름이 아니다. 어떤 프로토콜을 그 광 I/O로 운반하는지는 제품 설계에 달려 있다. [OIF Co-Packaging Framework](https://www.oiforum.com/wp-content/uploads/OIF-Co-Packaging-FD-01.0.pdf).

```text
칩 안/패키지:     연산 die ↔ chiplet              예: UCIe
보드/장치:        CPU ↔ 가속기·메모리             예: PCIe, 지원 CXL, 특정 C2C
가속기 집합:      가속기 ↔ 가속기/스위치          예: NVLink, xGMI, UALink
서버·집합 사이:   NIC ↔ 네트워크 ↔ NIC            예: Ethernet, InfiniBand, UEC 구현
물리 광 I/O 배치: 위의 일부 링크를 광으로 구현     예: pluggable optics, CPO
```

이 그림의 위치는 이해를 위한 대표 범위다. 실제 기술은 여러 보드·서버·랙으로 확장될 수 있다. 특정 계층의 이름이 다른 계층의 소프트웨어·프로토콜 지원을 대신하지 않는다.

## 9. 대역폭 숫자를 공정하게 비교하는 방법

숫자 옆에 최소한 다섯 항목을 적는다: **단위, 방향, 집계 대상, 링크 수/폭, 오버헤드 포함 여부**.

| 광고·사양에서 본 값 | 실제로 비교 전에 물어야 할 것 |
|---|---|
| NVLink 1.8TB/s | GPU 하나의 여러 링크 양방향 합산인가? 상대 장치와 토폴로지는? |
| NVL72 약 130TB/s | 랙 전체의 집계인가? 한 GPU가 쓸 수 있는 값인가? |
| UALink 200G/lane | lane 수와 TX/RX를 어떻게 묶었는가? 물리·프로토콜 오버헤드는? |
| PCIe Gen5 x16 약 63GB/s | 한 방향 인코딩 반영 상한인가? 실제 payload는? |
| HBM 1.5TB/s | 칩의 로컬 메모리 인터페이스인가? 다른 카드로 전송하는 값인가? |

UALink 1.0 백서는 x4 station에 대해 **TX 800Gb/s, RX 800Gb/s**를 설명한다. 방향당 byte 단위로 단순 환산하면 100GB/s씩이다. 이것을 NVLink GPU당 모든 링크의 양방향 집계와 바로 비교할 수는 없다. [UALink 백서](https://ualinkconsortium.org/wp-content/uploads/2025/04/UALink-1.0-White_Paper_v3.pdf).

NVL72의 약 130TB/s 역시 GPU당 1.8TB/s를 72개에 걸쳐 집계한 규모와 대응한다. 130TB/s짜리 단일 전송 통로가 있거나, 호스트 NIC로 그 속도를 낼 수 있다는 뜻이 아니다. 토폴로지의 **bisection bandwidth**는 집합을 둘로 나눴을 때 그 사이를 통과할 수 있는 대역폭이며, 단순한 모든 포트 속도의 합과 다를 수 있다.

## 10. All-reduce·All-gather와 링크 속도

**All-reduce**는 각 참여자의 값을 합산 같은 연산으로 모으고 결과를 모두에게 전달한다. **All-gather**는 각자의 데이터 조각을 모아 전체를 모두에게 전달한다. **Broadcast**는 한 참여자의 데이터를 여러 참여자에게 보낸다. 같은 카드 수라도 통신 패턴이 다르면 성능이 달라진다.

예를 들어 단순 ring all-reduce에서 참여자 P개, 각자의 입력 크기 S라고 하면 각 참여자가 보내는 총량은 이상적인 분할 기준으로 약 `2(P−1)/P × S`다. 한 단계에 약 S/P를 보내는 reduce-scatter와 all-gather를 각각 P−1단계 수행하므로 이 총량이 나온다. 이 식은 특정 알고리즘의 계산 예이며 다른 구현에 그대로 적용하지 않는다.

P=4, S=64MiB라면 각 참여자 전송량은 96MiB다. 병목 경로의 유효 대역폭을 **가상의 한 방향 10GB/s**로 두면 데이터 이동만 약 `96×2²⁰/10¹⁰ = 10.07ms`이고, 단계 지연·계산·혼잡은 추가된다. 더 많은 카드나 링크를 넣어도 알고리즘·메시지 크기를 함께 봐야 하는 이유다.

네 장 모두 같은 NUMA라는 것은 소켓 간 경로를 피할 가능성을 높이는 배치 정보다. 네 장 모두 같은 스위치에 연결됐다는 뜻도, collective가 어떤 경로를 선택했는지 증명하는 값도 아니다. 10장에서 다룰 A7 NPU 네 장의 2+2 배치가 정확히 이 사례다.

## 11. 표준·제품·현장을 나눠 기록하기

| 기술/제품 | 2026-09-21 기준 공식 근거의 상태 | A7에 적용할 때 |
|---|---|---|
| RTX PRO 6000 Server Edition | NVLink 미지원 명시 | PCIe 기반 통신을 검토 |
| B200/HGX·GB200 | NVLink/NVSwitch 시스템 사양 공개 | 현재 RTX 카드의 기능으로 전용하지 않음 |
| GB300 NVL72 | 공식 제품 페이지에서 제공 중으로 안내 | 별도 시스템/SKU. 구매 가능 여부·납기는 공급자 확인 |
| Rubin/NVLink 6 | 2026-01 발표에서 생산·파트너 제품 일정 안내 | 조사 날짜만으로 특정 OEM 시스템 출하를 확정하지 않음 |
| NVLink Fusion | 2025년 파트너 설계 생태계 발표 | 개별 endpoint·시스템 호환 문서 필요 |
| UALink | 1.0 및 2.0 관련 규격 공개 | 실제 가속기·스위치·관리 구현과 상호 호환 확인 |
| Ultra Ethernet | 공개판 1.0.3 확인 | NIC·드라이버·스위치 구현 확인 |
| CXL | 4.0 규격 공개 | 플랫폼·장치 타입·펌웨어·OS 지원 확인 |

출시 상태의 추가 근거: [GB300 NVL72 제품 페이지](https://www.nvidia.com/en-gb/data-center/gb300-nvl72/), [Rubin 발표의 일정](https://nvidianews.nvidia.com/news/rubin-platform-ai-supercomputer). 브랜드·회원사 로고·로드맵 그림은 카드의 장착·프로토콜 지원 증명이 아니다.

## 연습 문제와 해설

**문제 1.** RTX PRO 6000 Blackwell 네 장을 샀다. B200의 1.8TB/s NVLink 사양을 서버 설계서에 적어도 되는가?

**해설:** 안 된다. 정확한 제품이 다르며 RTX PRO 6000 Server Edition의 NVLink는 공식적으로 미지원이다. 실제 PCIe 토폴로지와 지원 통신을 사용해야 한다.

**문제 2.** 200G/lane과 1.8TB/s 중 어느 것이 더 빠른가?

**해설:** 이 정보만으로 비교할 수 없다. bit/byte, lane/GPU 집계, 방향, 링크 수와 overhead를 맞춘 뒤 같은 트래픽 조건으로 비교한다.

**문제 3.** UALink 표준이 공개됐고 공급자가 consortium 회원사다. 그 회사 NIC를 기존 Ethernet 스위치에 꽂으면 UALink가 되는가?

**해설:** 아니다. 회원 자격은 제품 구현 증명이 아니다. UALink endpoint·스위치·관리 스택·호환 조합이 필요하다.

**문제 4.** CXL 메모리를 추가하면 NPU 네 장이 모두 같은 HBM을 공유하게 되는가?

**해설:** 아니다. CXL 메모리의 접근 주체와 일관성·배정은 타입과 플랫폼에 달려 있다. NPU의 HBM과 CXL 메모리는 별개이며 해당 NPU의 지원이 확인돼야 한다.

[학습 안내](README.md) · 다음: [08. 전원·냉각·BMC·정비](08-power-cooling-serviceability.md)
