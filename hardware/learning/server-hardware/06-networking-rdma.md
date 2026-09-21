# 06. 서버 네트워크: NIC에서 RDMA 패브릭까지

[교재 목차](README.md) · [이전: GPU·NPU 실행 경로](05-gpu-npu-execution.md) · [다음: 가속기 간 연결](07-accelerator-interconnects.md)

이 장은 서버 밖의 다른 서버와 데이터를 주고받는 경로를 다룬다.
GPU끼리 같은 서버 안에서 통신하는 경로는 다음 장의 주제다.
서버 여러 대를 네트워크로 묶어 작업을 나누는 것을 **scale-out**이라고 부른다.
scale-out에서는 가속기의 계산 속도만큼 NIC, 호스트 버스, 케이블, 스위치와 소프트웨어 경로가 중요하다.

> 사례 기준일: **2026-09-21**. 아래 A7 구성의 ‘실측’은 [A7 증설 검토 일지](../../npu/a7-expansion-plan-2026-09-21.md)의 읽기 전용 조사 결과다. 카드의 공식 최대 사양, 실제 협상 상태, 앞으로의 장착 후보를 구분한다.

## 1. NIC, 포트, 케이블은 서로 다른 물건

**NIC(Network Interface Card)**는 서버의 데이터를 네트워크 신호로 내보내고 들어온 신호를 호스트에 전달하는 장치다.
OS에는 PCIe 장치와 네트워크 인터페이스로 보일 수 있다.
NIC에는 패킷 처리 회로, 큐, DMA 엔진, 포트가 있고, RDMA 기능을 갖춘 NIC는 RNIC라고도 부른다.
‘NIC가 200G를 지원한다’는 말은 장치 능력의 상한이며, 지금 200G로 연결됐다는 관측은 아니다.

포트는 NIC의 외부 접속 지점이고, **케이지(cage)**는 모듈 또는 케이블 끝을 받아들이는 물리적 자리다.
RJ45는 흔히 구리 이더넷 케이블의 플러그·소켓 형태를 가리킨다.
SFP 계열과 QSFP 계열은 탈착식 모듈 또는 직접 연결 케이블에 쓰는 별도의 폼팩터다.
이들은 모두 ‘네트워크 구멍’이지만 같은 형상이나 배선 규칙을 공유하지 않는다.

광 연결에서는 광 트랜시버가 전기 신호와 빛을 변환하고, 광섬유가 신호를 운반한다.
DAC는 양끝 커넥터가 붙은 구리 직접 연결 케이블이고, AOC는 광 변환부가 케이블 양끝에 붙는다.
선택할 때는 NIC 포트와 스위치 포트의 지원 표준, 모듈·케이블 호환성, 거리, 광섬유 종류, FEC까지 맞춰야 한다.
**QSFP56 모양만 보고 200G가 나온다고 판단할 수 없다.** 포트 양끝의 프로토콜·속도·레인 구성과 실제 링크 협상이 맞아야 한다.
같은 QSFP 외형에도 여러 속도·배선 방식이 있다. 100G 포트도 모듈과 상대 포트가 맞지 않으면 100G 링크가 되지 않는다.
[NVIDIA의 해당 카드 포트·지원 속도 표](https://networking-docs.nvidia.com/connectx6vpihw/specifications)는 ‘지원’의 근거이며 현재 연결 상태의 근거는 아니다.

```text
호스트 메모리 / GPU 메모리
       │ 데이터 이동 가능 여부는 소프트웨어·토폴로지에 달림
CPU ─ PCIe 루트 ─ [PCIe NIC] ─ 포트 케이지 ─ 모듈·케이블 ─ 스위치 ─ 상대 서버
                   ↑ 서버 안 장치       ↑ 물리 접속       ↑ 네트워크 패브릭
```

카드가 꽂히는 자리도 포트와 구별해야 한다.
일반 PCIe 확장 카드는 표준 PCIe 슬롯과 브래킷을 쓴다.
**OCP NIC 3.0**은 서버의 별도 OCP NIC 베이와 커넥터를 위한 카드 규격이다.
둘 다 내부적으로 PCIe 신호를 사용할 수 있지만 물리 장착 방식은 같지 않다.
‘OCP 슬롯이 있으니 일반 PCIe 카드를 꽂는다’거나 그 반대라고 가정하면 안 된다.
이 사례의 `OCP1`은 서버가 표시한 위치 이름이며, 그 표기만으로 베이의 정확한 OCP 규격 개정을 확정하지 않는다.
[OCP NIC 3.0 공식 규격](https://www.opencompute.org/documents/ocp-nic-3-0-r1v60-20250410a-tn-no-cb-pdf)은 전용 폼팩터와 PCIe 전기 인터페이스를 별도로 정의한다.

## 2. 패킷은 어느 길로 가는가

Ethernet은 링크 계층의 프레임·주소·스위칭 방식이다.
IP는 서로 다른 네트워크 사이의 주소 지정과 라우팅을 담당한다.
TCP는 IP 위에서 바이트 스트림의 순서와 재전송을 제공한다.
일반적인 웹·파일 전송은 `애플리케이션 → TCP → IP → Ethernet` 경로를 쓸 수 있다.
UDP는 TCP와 다른 전송 계층 프로토콜이며, UDP라는 이름만으로 신뢰성·재전송 정책을 단정할 수 없다.

InfiniBand(IB)는 Ethernet과 다른 링크·패브릭 체계다.
IB 포트를 일반 Ethernet 스위치 포트에 연결한다고 양쪽이 자동으로 공통 프로토콜을 찾는 것은 아니다.
IB 패브릭은 장치를 발견하고 경로를 배정하는 **서브넷 매니저(SM)**가 필요하다.
SM은 IB 스위치 내장형 또는 별도 호스트에서 실행될 수 있다.
[NVIDIA InfiniBand 서브넷 매니저 설명](https://docs.nvidia.com/networking/display/NVIDIAMLNXOSUserManualv3112200LTS/Subnet%2BManager)은 이 역할을 명시한다.

**RoCEv2**는 Ethernet 위에서 RDMA 전송을 쓰는 방식이다.
패킷에 IP와 UDP 헤더가 들어가므로 IP 라우팅 경로를 구성할 수 있다.
그러나 데이터 전송 의미론은 TCP 소켓의 바이트 스트림과 다르다.
즉, `RDMA 작업 → RDMA 전송 → UDP/IP → Ethernet`으로 이해하면 된다.
‘IP가 있으므로 TCP를 쓴다’는 추론은 틀리다.
[NVIDIA의 RoCEv2 패킷 설명](https://docs.nvidia.com/doca/archive/2-10-0/RDMA%2Bover%2BConverged%2BEthernet/index.html)이 IP/UDP 캡슐화를 확인해 준다.

| 경로 | 물리·링크 패브릭 | IP/TCP의 역할 | 필요한 상대 환경 |
|---|---|---|---|
| 보통 Ethernet/TCP | Ethernet | IP 주소·TCP 연결로 데이터 교환 | Ethernet 포트, L2/L3 경로 |
| InfiniBand RDMA | IB | 기본 RDMA 데이터 경로에 TCP 불필요 | IB 포트·스위치·SM |
| RoCEv2 RDMA | Ethernet | IP/UDP 캡슐화, TCP 전송 아님 | RoCE 지원 NIC와 맞춘 Ethernet 패브릭 |

‘VPI(Virtual Protocol Interconnect)’ 카드는 지원 범위 안에서 포트를 IB 또는 Ethernet 용도로 구성할 수 있다.
**VPI는 두 패브릭을 카드가 자동 변환하거나 브리지한다는 뜻이 아니다.**
포트 프로토콜을 바꾸려면 카드 설정, 드라이버·펌웨어 상태, 상대 스위치·케이블과 운영 계획을 함께 바꿔야 한다.
기존 IB 연결을 임의로 Ethernet으로 돌리면 그 용도의 통신이 끊길 수 있다.
[NVIDIA ConnectX-6 VPI 모델 표](https://networking-docs.nvidia.com/connectx6vpihw/introduction), [포트 모드 설정 설명](https://docs.nvidia.com/networking/display/mlnxofedv543400/ethernet%2Binterface), [포트·스위치 일치 안내](https://docs.nvidia.com/dgx/archives/pdf/dgx2-user-guide.pdf)를 함께 본다.

## 3. NIC가 CPU 일을 덜어주는 지점

CPU가 모든 바이트를 직접 복사해 네트워크 선에 실어 나르는 것은 아니다.
NIC의 **DMA(Direct Memory Access)** 엔진은 허용된 메모리와 NIC 사이에서 데이터를 이동한다.
드라이버와 OS는 버퍼·주소 매핑·권한·전송 완료를 준비하고 관리한다.
이 분리는 데이터 이동 중 CPU 부담을 줄일 수 있지만 CPU 작업을 완전히 없애지는 않는다.

NIC의 송수신 **큐(queue)**는 여러 작업을 병렬로 처리하는 통로다.
**RSS(Receive Side Scaling)**는 수신 패킷의 흐름을 여러 큐로 나누어 여러 CPU가 처리하도록 돕는다.
체크섬 계산이나 패킷 분할·병합 같은 **오프로드**도 NIC와 드라이버의 지원 범위 안에서 CPU 일을 줄인다.
어떤 오프로드가 실제 켜져 있는지는 카드 지원표가 아니라 현재 인터페이스 상태로 확인해야 한다.
큐가 많다고 단일 흐름의 속도가 큐 수만큼 늘지는 않는다.
[Linux 커널의 네트워크 스케일링 문서](https://docs.kernel.org/networking/scaling.html)는 RSS, 큐, CPU 매핑의 관계를 설명한다.

RDMA(Remote Direct Memory Access)는 한 서버의 RNIC가 원격 서버의 **등록된 메모리 영역**과 데이터를 교환하는 모델이다.
일반 소켓 경로에 비해 CPU 개입·복사를 줄일 수 있지만, 애플리케이션과 드라이버가 RDMA 자원을 준비해야 한다.
메모리 등록은 사용할 버퍼의 범위와 접근 권한을 NIC에 알리고 장치가 쓸 주소 관계를 관리하는 과정이다. 일반적인 등록 방식은 페이지를 고정(pinning)하지만, On-Demand Paging(ODP)을 지원하는 구성에서는 등록 시 전체 페이지를 미리 고정하지 않고 필요한 시점에 매핑할 수 있다. [NVIDIA ODP 설명](https://docs.nvidia.com/networking/display/mlnxofedv23105140lts/optimized-memory-access).
I/O 가상 주소(IOVA), 로컬 키, 원격 키는 장치가 임의의 메모리를 읽지 못하게 하는 경계의 일부다.
운영체제·드라이버는 등록과 해제, 보호, 완료 처리에 관여한다.
[Linux 커널 userspace verbs 문서](https://docs.kernel.org/infiniband/user_verbs.html)도 메모리 고정과 자원 관리 경로를 구분한다.

**One-sided RDMA Read/Write**에서는 데이터 전송 시 상대 CPU의 일반적인 `recv` 호출이 매번 개입하지 않을 수 있다.
하지만 상대 프로그램은 먼저 메모리를 등록하고 접근 권한과 주소·키를 안전하게 알려줘야 한다.
연결·큐 페어(QP) 설정, 완료 확인, 오류 복구와 애플리케이션 동기화도 남는다.
따라서 ‘RDMA = CPU 사용량 0’도, ‘원격 RAM 전체를 마음대로 읽는다’도 틀리다.
[NVIDIA RDMA 프로그래밍 설명](https://docs.nvidia.com/rdma-aware-networks-programming-user-manual-1-7.pdf)은 등록 영역의 접근 권한과 Read/Write 작업을 다룬다.

```text
일반 소켓 경로의 개념: 앱 버퍼 ↔ OS 네트워크 경로 ↔ NIC ↔ 선 ↔ 상대 NIC ↔ 상대 OS ↔ 앱
RDMA 데이터 경로의 개념: 등록 버퍼 ↔ RNIC ═══ 패브릭 ═══ 상대 RNIC ↔ 등록 버퍼
                                 연결·등록·권한·완료·오류 처리는 소프트웨어가 담당
```

이 그림은 경로 차이를 보여 주기 위한 것이다.
모든 소켓 전송이 반드시 같은 횟수로 복사되는 것도, 모든 RDMA 전송이 같은 하드웨어 경로를 쓰는 것도 아니다.

## 4. RoCE 패브릭에서 ‘연결됨’ 뒤에 남는 일

RoCEv2는 Ethernet/IP 장비를 활용하지만, 높은 처리량과 낮은 지연을 함께 얻으려면 혼잡 관리를 설계해야 한다.
스위치의 버퍼가 차면 패킷 손실, 큐 대기, 재전송 또는 성능 저하가 생길 수 있다.
**PFC(Priority Flow Control)**는 선택한 우선순위의 송신을 잠시 멈추게 하여 손실을 줄이는 방법이다.
**ECN(Explicit Congestion Notification)**은 혼잡을 패킷에 표시해 송신 측이 속도를 조절하게 하는 방법이다.
둘은 같은 기능이 아니며, NIC·스위치·우선순위 매핑과 워크로드에 맞게 설계한다.
[NVIDIA PFC 설명](https://docs.nvidia.com/networking/display/mlnxofedv23100540/flow%2Bcontrol)과 [RoCEv2 ECN 설명](https://docs.nvidia.com/networking/display/mlnxofedv590590/explicit%2Bcongestion%2Bnotification%2B%28ecn%29)이 각각의 동작을 설명한다.

PFC를 쓰면 손실을 줄일 수 있지만 pause가 위쪽 장치로 번져 지연·head-of-line blocking을 만들 수도 있다.
ECN만으로 모든 손실이 사라진다고 약속할 수도 없다.
따라서 ‘RoCE에는 언제나 PFC를 켜야 한다’거나 ‘ECN만 켜면 손실 없는 망이다’라는 단정은 피한다.
손실 허용 정도, 혼잡 제어 지원, 스위치 버퍼와 운영 기준을 함께 검토한다.
이러한 PFC 부작용은 [IEEE 802.1 기술 자료](https://grouper.ieee.org/groups/802/1/files/public/docs2022/new-blendin-SFC-sim-0522-v01.pdf)에도 설명돼 있다.
이 장은 설정값을 제시하지 않는다. 현재 서버의 RoCE 패브릭은 실측·확정되지 않았다.

MTU는 한 패킷에 담는 데이터 크기를 제한한다.
Jumbo MTU는 패킷당 오버헤드를 줄일 수 있지만 경로의 모든 관련 인터페이스가 맞아야 한다.
서로 다른 MTU, 케이블·광모듈 호환 문제, FEC 불일치는 연결 실패나 성능 저하를 낳을 수 있다.
**Breakout**은 한 고속 포트를 여러 낮은 속도 포트로 나누는 방식이지만 양쪽 장치의 포트·레인·케이블 지원이 맞아야 한다.
스위치의 외부 **uplink**도 서버 여러 대가 공유하므로 서버 NIC 속도만 합산해 랙 밖 처리량으로 해석할 수 없다.

## 5. 숫자를 읽는 순서: 포트, PCIe, 응용 처리량

네트워크 속도의 `Gb/s`는 **기가비트/초**, 호스트 메모리 대역폭의 `GB/s`는 **기가바이트/초**다.
1바이트 = 8비트이므로 **100Gb/s ÷ 8 = 12.5GB/s**다.
이 값은 100G 링크의 한 방향 표시 속도를 단위만 바꾼 상한이며, 실제 파일·모델 데이터 처리량이 아니다.
Ethernet 프레임, IP/UDP/TCP, RDMA 헤더와 기타 오버헤드가 추가된다.

PCIe 4.0은 레인당 16GT/s이고 128b/130b 인코딩을 사용한다.
따라서 Gen4 x8의 한 방향 상한은 `16 × 8 × 128/130 ÷ 8 ≈ 15.75GB/s`다.
Gen4 x16은 같은 계산으로 약 31.51GB/s다.
[PCI-SIG의 세대별 대역폭 표](https://pcisig.com/sites/default/files/files/PCIe_Specification_Webinar_Rev%206_FINAL_0.pdf)는 Gen4 x16 한 방향을 인코딩 반영 후 약 252Gb/s로 제시한다.
PCIe 패킷 오버헤드가 있으므로 이 값도 실제 DMA 유효 처리량보다 높다.
단일 100G 포트의 12.5GB/s 원시 요구량을 Gen4 x8의 15.75GB/s와 비교하면 여유가 있지만, 카드의 실제 지원 링크와 작업 부하를 확인해야 한다.

**100G 포트 두 개가 같은 방향으로 각각 100Gb/s를 낸다면 합계는 25GB/s**다.
Gen4 x8의 15.75GB/s 상한에는 못 들어가므로 Gen4 x16 같은 적절한 호스트 연결을 검토한다.
하지만 듀얼 포트 카드라고 항상 두 포트가 동시에 최대 속도를 내는 것은 아니다.
카드 P/N, PCIe 세대·폭, 네트워크 상대와 처리 경로를 함께 확인한다.
[NVIDIA ConnectX-6 모델 표](https://networking-docs.nvidia.com/connectx6vpihw/introduction)에는 단일 100G Gen4 x8 모델과 듀얼 100G Gen3/4 x16 모델이 따로 있다.

| 숫자 | 뜻 | 그 숫자만으로 알 수 없는 것 |
|---|---|---|
| NIC ‘최대 200G 지원’ | 카드가 지원하는 상한 | 케이블 연결·프로토콜·협상 속도 |
| `PCIe Gen4 x16` | 호스트와 NIC 사이의 실제 버스 링크 | 외부 네트워크가 200G인지 |
| `Ethernet 100Gb/s` | 포트의 한 방향 링크 속도 | TCP·RDMA·애플리케이션 유효 처리량 |
| `iperf` 등 측정값 | 특정 조건의 끝단 간 전송 결과 | 모든 앱·메시지 크기의 지연과 처리량 |

전이중(full duplex) 포트는 송신과 수신을 동시에 할 수 있다.
100G의 ‘양방향 합계 200Gb/s’라는 표현은 각 방향 100Gb/s를 더한 것이지, 한 방향에 200Gb/s가 생긴다는 뜻이 아니다.
PCIe도 송신·수신 방향의 경로를 구분해 계산한다.
작은 요청 하나의 **지연(latency)**과 초당 전송한 총 데이터의 **처리량(throughput)**은 다른 성능 지표다.
많은 작은 메시지는 처리량이 낮아도 지연이 중요하고, 큰 데이터를 연속으로 보내면 처리량과 CPU·메모리 병목이 중요하다.

## 6. A7에서 이미 관측한 것과 아직 모르는 것

| 위치 | 2026-09-21 관측 | 해석 |
|---|---|---|
| SLOT1 / NUMA0 | ConnectX-6 VPI `MCX653105A-HDAT`, QSFP56 **단일 포트**, PCIe **Gen4 x16** | 공식 최대 HDR 200Gb/s IB·200GbE 지원. 실제 IB `DOWN`, `Disabled` |
| OCP1 / NUMA0 | Broadcom BCM57416 **듀얼 10GbE**, PCIe **Gen3 x8** | 관리 NIC 한 포트의 실제 링크는 **1Gbps** |
| 추가 NIC | 모델과 장착 여부 **미확정** | GPU 통신 후보 SLOT3/NUMA0, NPU 통신 후보 SLOT20·21/NUMA1 |

SLOT1 카드는 ‘200G 지원’과 ‘현재 200G로 통신’이 다른 사례다.
실측 `link_layer: InfiniBand`, `state: DOWN`, `phys_state: Disabled`이므로 현재 IB 전송 가능 상태라고 적을 수 없다.
이 결과만으로 케이블 미연결, 스위치 문제, 포트 관리 상태 중 어느 것이 원인인지 특정할 수도 없다.
또한 QSFP56 한 포트이므로 별도 물리 포트 두 개를 가진 듀얼 카드로 취급하면 안 된다.
공식 모델 사양은 [NVIDIA ConnectX-6 VPI 모델 표](https://networking-docs.nvidia.com/connectx6vpihw/introduction), 현재 상태는 [A7 실측 일지](../../npu/a7-expansion-plan-2026-09-21.md)에 각각 근거한다.

OCP1 카드의 **10G 지원**과 관리 포트의 **1Gbps 협상**도 구별한다.
관리망의 실제 1Gbps를 10Gbps 실효 처리량으로 기록할 수 없다.
이 카드는 이미 OCP1에 장착되어 있으며, 추가 100G 카드가 OCP1에 들어갈 수 있다고 가정하지 않는다.
추가 NIC의 정확한 모델·포트 수·크기·브래킷·라이저·OEM 지원은 확인되지 않았다.

### 통신 상대가 배치 후보를 바꾼다

NIC가 GPU의 데이터를 주로 전달한다면 NUMA0의 SLOT3을 후보로 볼 수 있다.
SLOT3은 GPU 후보 SLOT8/10, NVMe와 PCIe 스위치 B 및 CPU 방향 **Gen5 x16 상위 링크**를 공유한다.
이 스위치의 하위 슬롯이 각각 x16이어도 상위 링크가 무한히 늘지 않는다.
NIC가 NPU 통신을 주로 맡는다면 NUMA1의 SLOT20(스위치 C) 또는 SLOT21(스위치 D)이 후보가 된다.
그러나 NIC 한 장이 NPU 네 장 모두와 같은 스위치에 놓이는 것은 아니다.
어느 후보도 실제 장착 가능성과 GPUDirect 경로를 보장하지 않는다.
[A7 실측 일지의 슬롯 지도와 스위치 그룹](../../npu/a7-expansion-plan-2026-09-21.md)이 이 판단의 범위다.

NIC가 어느 NUMA에 붙는지만으로 최적 경로가 정해지지 않는다.
애플리케이션 스레드의 CPU affinity, 버퍼의 메모리 배치, 인터럽트·큐의 CPU 배치가 서로 엇갈리면 소켓 간 이동이 생길 수 있다.
같은 스위치의 GPU/NIC라 해도 ACS, IOMMU, 드라이버와 플랫폼 조건에 따라 PCIe peer-to-peer가 막히거나 우회할 수 있다.
GPU·NPU가 생산하는 데이터량과 통신 상대, 다른 카드의 동시 I/O를 먼저 정해야 한다.
실제 일지는 현재 ACS 리다이렉션이 켜져 있음을 보고한다. 이 상태에서 직접 P2P를 단정하지 않는다.

## 7. GPUDirect RDMA는 별도의 성립 조건이 있다

**GPUDirect RDMA**는 지원되는 GPU 메모리와 NIC 사이에 직접 DMA 경로를 제공하는 기술이다.
이 경로를 쓰면 호스트 RAM의 중간 복사 버퍼를 줄일 수 있다.
그러나 GPU, NIC, 드라이버·커널 구성, 메모리 등록 방식과 PCIe 토폴로지가 모두 맞아야 한다.
특히 GPU와 NIC가 어떤 PCIe 루트·스위치를 공유하는지, IOMMU 주소 변환과 ACS가 경로에 어떤 영향을 주는지 확인한다.
[NVIDIA GPUDirect RDMA 개요](https://docs.nvidia.com/cuda/gpudirect-rdma/)는 같은 PCIe 루트 복합체 등 토폴로지 제약과 드라이버 협력을 설명한다.
‘GPUDirect 지원 NIC’라는 제품명만으로 이 A7에서 GPU VRAM 직접 경로가 검증됐다고 말할 수 없다.

**GPUDirect Storage(GDS)**는 스토리지와 GPU 메모리 사이의 데이터 경로를 다루는 별도 기술이다.
로컬 NVMe뿐 아니라 지원되는 원격 스토리지에서는 NIC/RDMA가 그 경로의 일부일 수 있지만, GDS와 GPUDirect RDMA는 같은 기능 이름이 아니다.
[NVIDIA GDS 설계 문서](https://docs.nvidia.com/gpudirect-storage/design-guide/)는 스토리지 경로와 NIC 경로를 구분한다.
RDMA를 활성화하면 여러 서버의 GPU VRAM이 자동으로 하나의 공유 메모리가 되는 것도 아니다.
어느 메모리를 어떻게 노출하고 동기화할지는 애플리케이션과 런타임이 정한다.

## 8. 읽기 전용으로 확인하는 순서

현재 상태를 읽을 때는 ‘카드 존재 → 버스 연결 → 포트 프로토콜 → 물리 링크 → 끝단 성능’ 순서로 질문을 좁힌다.
아래 조회 도구는 설정을 바꾸지 않는다. 실제 A7에서 사용한 조회와 관측값은 [실측 일지](../../npu/a7-expansion-plan-2026-09-21.md)에 있다.

| 읽기 전용 조회 | 확인할 질문 | 주의할 해석 |
|---|---|---|
| `lspci -D -t`, `lspci -vv` | NIC가 어느 PCIe 경로에 있고 실제 `LnkSta` 세대·폭은 무엇인가 | 카드의 최대 `LnkCap`과 실제 `LnkSta`를 구별 |
| `ip link`, `ethtool` | Ethernet 인터페이스·관리 상태·현재 속도·링크 감지는 무엇인가 | 인터페이스 이름과 10G 지원표만으로 현재 10G라 하지 않음 |
| `ibstat`, `/sys/class/infiniband/.../ports/1/` | IB 포트의 `link_layer`, `state`, `phys_state`는 무엇인가 | `DOWN`과 `Disabled`의 원인을 한 번의 조회로 확정하지 않음 |
| `/sys/bus/pci/devices/.../numa_node`, `lspci -t` | NIC와 GPU/NPU가 어느 NUMA·스위치 경로에 속하는가 | 같은 NUMA가 직접 P2P의 증명은 아님 |
| `/proc/interrupts`, `/sys/class/net/.../queues/` | 큐와 인터럽트가 어떤 CPU에 분포하는가 | 큐 개수만으로 앱 처리량을 예측하지 않음 |

이 표는 조회 **대상과 해석 기준**이다. A7 일지에서 실제 사용이 확인된 것은 `lspci`, `ethtool`, IB sysfs 조회이며, `ip link`와 `ibstat`은 이 조사에서 실행 여부가 확인되지 않은 일반 조회 경로다.
여기서는 포트 설정 변경, 케이블 교체, 부하 측정 절차를 실행 명령으로 제시하지 않는다.
실제 협상 속도는 연결된 양쪽 포트와 스위치에서 대조해야 한다.
성능을 논할 때는 케이블·광모듈·FEC·breakout·MTU·스위치 uplink·동시 사용자와 측정 조건을 함께 기록한다.

## 9. 연습문제와 해설

**문제 1.** SLOT1의 QSFP56 포트와 200GbE 지원 사양만 보고 ‘현재 200Gb/s Ethernet 연결’이라고 기록할 수 있는가?

**해설.** 없다. 2026-09-21 실측은 포트가 IB로 표시되고 `DOWN`/`Disabled`다. 200GbE는 카드의 가능한 모드이고, 실제 링크 프로토콜·상태·속도는 별도 관측해야 한다.

**문제 2.** 단일 100G 포트의 한 방향 원시 속도와 Gen4 x8 PCIe의 한 방향 이론 상한은 각각 얼마인가?

**해설.** 100Gb/s는 12.5GB/s, Gen4 x8은 약 15.75GB/s다. 둘 다 오버헤드 전 숫자이며 이 비교만으로 애플리케이션이 12.5GB/s를 얻는다고 보장할 수 없다.

**문제 3.** 100G 포트 두 개가 동시에 같은 방향으로 최대 속도를 낸다면 Gen4 x8 호스트 링크 하나로 충분한가?

**해설.** 원시 합계가 25GB/s여서 Gen4 x8의 약 15.75GB/s보다 크다. 카드와 슬롯이 지원한다면 Gen4 x16급 연결을 검토한다. 반대 방향까지 합산해 한 방향 수요를 부풀리지 않는다.

**문제 4.** IB로 설정된 VPI NIC를 Ethernet 스위치에 꽂으면 RoCEv2로 자동 전환되는가?

**해설.** 아니다. 카드 포트 모드, 상대 장비, 케이블과 운영 설정을 맞춰야 한다. IB 패브릭에는 IB 스위치와 SM이 필요하다. VPI는 자동 프로토콜 변환기가 아니다.

**문제 5.** SLOT3과 GPU가 NUMA0에 있으므로 GPUDirect RDMA가 검증됐다고 말할 수 있는가?

**해설.** 없다. GPU/NIC의 실제 PCIe 경로, ACS·IOMMU, 드라이버와 메모리 등록 지원을 검증해야 한다. SLOT3의 물리 장착 가능성도 아직 OEM 확인 전이다.

**문제 6.** RoCEv2 패킷이 IP/UDP를 사용한다는 사실은 TCP와 같은 전송이라는 뜻인가?

**해설.** 아니다. IP/UDP는 패킷을 운반하는 헤더이고, RDMA의 작업·권한·완료 의미론은 TCP 바이트 스트림과 다르다. 혼잡과 손실 정책도 패브릭에 맞춰 설계해야 한다.

[이전: GPU·NPU 실행 경로](05-gpu-npu-execution.md) · [다음: 가속기 간 연결](07-accelerator-interconnects.md) · [교재 목차](README.md)
