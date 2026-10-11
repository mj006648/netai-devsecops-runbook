# 11. NUMA·장치 연결·DMA·IOMMU

[← 이전](10-simd-vectors-and-roofline.md) · [목차](README.md) · [다음 →](12-performance-counters-and-bottlenecks.md)

**NUMA(Non-Uniform Memory Access)**에서는 어느 위치의 메모리에 접근하는지에 따라 지연과 대역폭이 달라진다. **DMA(Direct Memory Access)**는 장치가 메모리와 데이터를 옮기는 기능이고, **IOMMU**는 장치가 사용하는 주소를 번역하고 범위를 제한한다. CPU 가상 주소를 장치에 그대로 주는 것과 올바른 DMA 매핑은 다르다.

## CPU 밖의 주소와 데이터 이동

NUMA node는 CPU와 가까운 메모리 및 연결 경로를 묶은 운영체제·하드웨어 지역성 단위다.
node와 CPU가 일대일이라는 뜻은 아니다. 한 node에 여러 core가 있고, 한 소켓에 여러 node가 구성될 수도 있다.
local 접근은 요청 core와 가까운 메모리 controller 경로를 쓰고, remote 접근은 interconnect를 건너 다른 node의 메모리에 간다.

코어0이 node0의 주소를 읽으면 `core→local cache→node0 controller→DRAM` 경로를 따른다.
같은 코어가 node1 주소를 읽으면 요청과 응답이 interconnect를 지나므로 지연과 공유 대역폭 조건이 달라질 수 있다.
항상 remote가 정확히 두 배 느리다고 정할 수는 없으며 토폴로지와 부하를 측정해야 한다.

DMA는 장치가 CPU의 매 바이트 복사 명령 없이 메모리와 데이터를 옮기는 기능이다.
PCIe 장치가 쓰는 주소는 프로세스 가상주소와 같다고 가정할 수 없다.
드라이버와 OS는 버퍼 페이지를 준비하고 IOMMU에 장치가 볼 I/O 가상주소와 물리 page, 권한을 연결한다.

| 시점 | 주체 | 상태 |
|---:|---|---|
| 1 | 드라이버 | 버퍼 page 할당, 장치 사용 중 이동·재사용되지 않게 수명 확보 |
| 2 | OS/IOMMU | page들을 IOVA 범위에 map, read/write 권한 설정 |
| 3 | 드라이버 | 장치 descriptor에 IOVA와 길이 기록 |
| 4 | 장치 | PCIe 요청으로 범위 안 DMA 수행 |
| 5 | 장치·드라이버 | completion으로 전송 종료 확인 |
| 6 | OS | 동기화 뒤 unmap, unpin·재사용 |

완료 전에 unmap하거나 page를 다른 용도로 재사용하면 늦은 DMA가 새 소유자의 데이터를 손상할 수 있다.
IOMMU는 매핑된 범위를 제한하지만 잘못 넓은 권한, 장치 버그, 캐시 일관성 조건까지 자동 해결하지 않는다.
pin은 “영원히 물리주소가 고정”이라는 일반 약속이 아니라 해당 DMA 수명 동안 요구되는 이동·회수 제약을 관리하는 개념이다.

```mermaid
flowchart LR
  D[장치 IOVA+길이] --> I[IOMMU 권한·page 번역]
  I --> P[물리 page]
  P --> C[completion]
  C --> U[unmap·수명 해제]
```

### 문제 1
node0 CPU가 node1 메모리를 읽으면 왜 remote인가?
**풀이:** 요청이 local controller에서 끝나지 않고 interconnect를 건너 node1 controller로 가기 때문이다. node가 CPU 하나라는 뜻은 아니다.

### 문제 2
4 KiB page 두 개를 IOVA `0x8000`부터 매핑하면 범위는?
**풀이:** 첫 page `0x8000~0x8fff`, 둘째 `0x9000~0x9fff`, 총 길이 8192바이트다.

### 문제 3
completion 전에 unpin하면 어떤 문제가 생기는가?
**풀이:** 장치가 여전히 이전 주소로 쓰는 동안 OS가 page를 이동·재사용할 수 있어 다른 데이터가 손상된다. 완료와 동기화 뒤 해제해야 한다.

## 공식 자료

[Linux DMA API](https://docs.kernel.org/core-api/dma-api.html)

[← 이전](10-simd-vectors-and-roofline.md) · [목차](README.md) · [다음 →](12-performance-counters-and-bottlenecks.md)
