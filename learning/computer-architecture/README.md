# 컴퓨터 구조 심화: 명령 한 개에서 시스템 병목까지

이 책은 CPU 용어를 외우는 목록이 아니다.
명령이 어디에 저장되고, 누가 가져오고, 어떤 중간 상태를 거쳐 결과가 architectural state가 되는지 추적한다.
교육용 5-stage pipeline과 MESI 모형을 실제 제조사 제품의 완전한 구현이라고 단정하지 않는다.

## 학습 순서

00 전체 지도 → 01 논리·clock → 02 ISA → 03 ABI·loading → 04 pipeline → 05 OoO·retirement → 06 cache → 07 coherence → 08 ordering → 09 MMU/TLB → 10 SIMD/roofline → 11 NUMA/DMA/IOMMU → 12 counters → 13 local models → 14 experiments → 15 문제·용어.

## 그림

- [실행 지도](assets/execution-map.svg)
- [5-stage pipeline](assets/pipeline.svg)
- [cache 주소](assets/cache-address.svg)
- [coherence](assets/coherence.svg)
- [page walk](assets/page-walk.svg)
- [roofline](assets/roofline.svg)

## 모형

- [cache_model.py](examples/cache_model.py)
- [pipeline_model.py](examples/pipeline_model.py)
- [memory_order_model.py](examples/memory_order_model.py)

모형은 고정 입력과 assert를 사용한다.
실제 CPU 성능이나 제조사 구현을 검증하지 않는다.

## 공식 근거

- [RISC-V specifications](https://docs.riscv.org/)
- [RISC-V ISA manual](https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/)
- [Linux kernel documentation](https://docs.kernel.org/)

## 읽는 원칙

ISA는 software가 관측하는 instruction 계약이다.
microarchitecture는 그 계약을 구현하는 내부 방법이다.
같은 ISA CPU도 cache, pipeline, predictor, coherence가 다를 수 있다.
모형 수치는 교육 입력이며 제품 specification이나 측정값이 아니다.
## 컴퓨터 구조 심화: 코드가 기계의 상태 변화가 되기까지

이 책은 “CPU가 빠르다” 같은 요약을 외우는 대신, 명령어·레지스터·파이프라인·캐시·메모리 순서가 실제로 어떤 객체이며 서로 어떤 값을 주고받는지 추적한다.
각 장의 계산은 원리를 드러내기 위한 교육 모형이다.
특정 제조사의 제품 성능, 비공개 회로, 정확한 지연 시간을 주장하지 않는다.

## 정확한 학습 순서

1. [00장 구조와 실행 지도](00-architecture-and-execution-map.md) — 소스 코드부터 장치까지 누가 어떤 상태를 바꾸는지 전체 경계를 잡는다.
2. [01장 디지털 논리와 클록](01-digital-logic-and-clock.md) — 비트, 게이트, 조합 논리, 상태 소자, 클록 주기의 뜻을 배운다.
3. [02장 명령어·레지스터·ISA](02-instructions-registers-and-isa.md) — 소프트웨어와 하드웨어 사이의 명령 계약을 읽는다.
4. [03장 함수·ABI·프로그램 적재](03-functions-abi-and-program-loading.md) — 호출 규약, 스택 프레임, 실행 파일이 프로세스가 되는 단계를 추적한다.
5. [04장 파이프라인·위험·forwarding](04-pipelines-hazards-and-forwarding.md) — 5단계 시간표에서 데이터가 언제 생기고 왜 멈추는지 계산한다.
6. [05장 분기·비순차 실행·retirement](05-branches-out-of-order-and-retirement.md) — 추측 실행 결과가 프로그램 상태가 되기 전 ROB가 지키는 순서를 배운다.
7. [06장 캐시 주소와 지역성](06-cache-addresses-and-locality.md) — 주소를 tag·set·offset으로 나누고 hit와 miss를 손으로 판정한다.
8. [07장 coherence와 false sharing](07-coherence-and-false-sharing.md) — 여러 코어의 캐시 복사본이 쓰기 권한을 주고받는 과정을 추적한다.
9. [08장 메모리 순서와 원자 연산](08-memory-ordering-and-atomics.md) — relaxed, acquire, release, seq_cst가 허용하는 실행을 구분한다.
10. [09장 MMU·TLB·page walk](09-mmu-tlb-and-page-walks.md) — 가상 주소 번역과 page fault가 서로 다른 사건임을 계산한다.
11. [10장 SIMD·vector·roofline](10-simd-vectors-and-roofline.md) — 한 명령의 병렬 데이터 처리량과 메모리 대역폭 한계를 함께 본다.
12. [11장 NUMA·interconnect·DMA·IOMMU](11-numa-interconnects-dma-and-iommu.md) — CPU 밖 장치와 여러 메모리 노드가 주소와 권한을 주고받는 경로를 배운다.
13. [12장 성능 카운터와 병목](12-performance-counters-and-bottlenecks.md) — CPI와 PMU 사건을 원인이 아닌 관측 증거로 해석한다.
14. [13장 로컬 모형](13-local-models.md) — 캐시, 파이프라인, 메모리 순서 Python 모형의 입력과 한계를 읽는다.
15. [14장 실험과 조사](14-experiments-and-research.md) — 질문, 가설, 통제 변수, 반복 측정, 반례를 갖춘 실험을 설계한다.
16. [15장 종합 문제·용어·근거](15-exercises-glossary-and-sources.md) — 여러 장을 연결한 풀이와 쉬운 용어 설명, 공식 자료를 확인한다.

처음 읽는 독자는 00장부터 순서대로 읽는 편이 좋다.
이미 ISA와 파이프라인을 아는 독자는 06장부터 시작할 수 있지만, 이 책이 사용하는 “건축 상태”와 “교육 모형”의 경계는 00장에서 먼저 확인한다.
