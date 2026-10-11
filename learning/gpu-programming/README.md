# GPU 병렬 프로그래밍: 주소와 실행 주체를 손으로 추적하는 입문

이 책은 GPU를 “빠른 장치”라는 한 문장으로 설명하지 않는다. Host CPU가 무엇을 준비하고, device GPU의 어느 thread·warp·block이 어떤 주소를 읽으며, 어떤 동기화와 수명 규칙이 결과를 지키는지 숫자로 추적한다.

![CPU에서 GPU kernel과 memory로 이어지는 전체 지도](assets/gpu-programming-map.svg)

## 학습 목표

1. CPU·GPU·host·device·kernel을 객체 위치와 실행 주체로 구분한다.
2. Thread, block, warp, grid index를 실제 array 주소로 계산한다.
3. Register, global, shared memory의 수명·가시성·비용을 구분한다.
4. Barrier, atomic, memory order와 scope가 무엇을 보장하지 않는지 설명한다.
5. Coalescing, alignment, bank conflict를 warp의 실제 주소로 판단한다.
6. Reduction, scan, tiled matrix multiplication의 중간 상태를 검산한다.
7. Tensor Core와 낮은 precision의 오차·형태 제약을 구분한다.
8. Stream, event, async copy, CUDA Graph의 dependency와 buffer 수명을 지킨다.
9. Occupancy, roofline, profiler counter를 성능 원인과 구분한다.
10. Multi-GPU collective를 α·β 통신 모형의 가정과 함께 계산한다.

## 읽는 순서

| 장 | 핵심 질문 |
| --- | --- |
| [00](00-gpu-programming-map.md) | GPU program의 객체는 어디에 있고 누가 실행하는가? |
| [01](01-cpu-gpu-and-parallel-work.md) | 병렬화할 일과 순차 일을 어떻게 나누는가? |
| [02](02-threads-blocks-warps-and-grids.md) | Grid index가 array 주소가 되는 과정은? |
| [03](03-registers-global-and-shared-memory.md) | Memory 공간의 소유자와 수명은? |
| [04](04-synchronization-and-memory-order.md) | Barrier와 ordering은 무엇을 보장하는가? |
| [05](05-coalescing-alignment-and-bank-conflicts.md) | Warp 주소가 transaction과 bank에 어떻게 대응하는가? |
| [06](06-reductions-scans-and-atomics.md) | 병렬 합계와 prefix를 어떻게 정확히 결합하는가? |
| [07](07-matrix-multiplication-and-tiling.md) | Tile이 재사용을 어떻게 만드는가? |
| [08](08-tensor-cores-and-numerical-precision.md) | 빠른 낮은 precision 계산의 오차와 제약은? |
| [09](09-streams-events-and-asynchronous-copies.md) | 비동기 작업의 순서와 buffer 수명은? |
| [10](10-kernel-launches-and-cuda-graphs.md) | Launch 반복 비용과 graph dependency는? |
| [11](11-occupancy-roofline-and-profiling.md) | 병목을 측정값으로 어떻게 좁히는가? |
| [12](12-multi-gpu-and-collectives.md) | 여러 GPU의 통신량과 순서는? |
| [13](13-local-models.md) | GPU 없이 주소·tile·collective를 어떻게 검산하는가? |
| [14](14-experiments-and-research.md) | 재현 가능한 GPU 실험을 어떻게 설계하는가? |
| [15](15-exercises-glossary-and-sources.md) | 문제와 용어를 어떻게 종합하는가? |

## 안전한 로컬 모형

- [coalescing_model.py](examples/coalescing_model.py)
- [tiled_matmul_model.py](examples/tiled_matmul_model.py)
- [collective_cost_model.py](examples/collective_cost_model.py)

세 파일은 Python 표준 라이브러리와 고정 입력만 사용한다. GPU, CUDA, file, network에 접근하지 않는다.

## 그림

- [전체 지도](assets/gpu-programming-map.svg)
- [Thread 계층](assets/thread-hierarchy.svg)
- [Memory 계층](assets/memory-hierarchy.svg)
- [Coalescing과 bank](assets/coalescing-banks.svg)
- [Tile matmul](assets/tiled-matmul.svg)
- [Stream과 collective](assets/streams-collectives.svg)

## 기준 문서

이 책은 [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-programming-guide/), [CUDA 13.2 PDF](https://docs.nvidia.com/cuda/cuda-programming-guide/pdf/cuda-programming-guide.pdf), [CUDA C++ memory model](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/cuda-cpp-memory-model.html)을 기준으로 용어와 보장 범위를 확인했다.

최신 문서가 설명하는 기능과 독자의 GPU, driver, toolkit, compiler가 실제 지원하는 기능은 별개다. 실행 전에 compute capability와 설치 조합을 확인한다.
