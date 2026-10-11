# 01. CPU·GPU와 병렬 작업

[이전: 00. 지도](00-gpu-programming-map.md) · [목차](README.md) · [다음: 02. Thread 계층](02-threads-blocks-warps-and-grids.md)

GPU로 옮길 작업은 독립성, 양, data 이동 비용으로 판단한다.

```mermaid
flowchart TD
    P["문제"] --> D{"Element가 독립인가?"}
    D -->|예| N{"작업량이 큰가?"}
    D -->|아니오| S["Dependency 재설계"]
    N -->|예| G["GPU 후보"]
    N -->|아니오| C["CPU가 단순할 수 있음"]
```

## 1. CPU core와 GPU execution resource

CPU는 복잡한 control flow와 낮은 latency에 강한 소수의 강한 core를 가진다. GPU는 많은 lane이 비슷한 계산을 수행해 throughput을 높이는 방향이다.

이는 절대 법칙이 아니라 설계 경향이다. Architecture와 세대에 따라 세부가 다르다.

## 2. Data parallel work

Image pixel 1024개에 각각 2를 곱한다면 각 output은 다른 element에 의존하지 않는다.

```text
input[i] → output[i]=2*input[i]
```

Thread i가 element i를 맡기 쉽다.

## 3. Task parallel work

서로 다른 두 kernel이나 copy와 compute가 겹칠 수 있다. 그러나 stream dependency와 resource가 허용해야 실제 overlap된다.

## 4. Dependency chain

Prefix sum은 output[i]가 앞 값 전체 합이다. 단순히 모든 thread가 `out[i]=out[i-1]+in[i]`를 동시에 하면 out[i-1]이 준비되지 않을 수 있다.

Parallel scan처럼 dependency 구조를 단계로 재설계해야 한다.

## 5. Amdahl 식 손 계산

전체 100 ms 중 GPU로 가속 가능한 부분 80 ms, 순차 부분 20 ms라고 하자. Parallel 부분을 10배 빠르게 해도 `20+80/10=28 ms`다.

Speedup은 `100/28≈3.57`배다. 10배 전체 가속이 아니다.

## 6. Data 이동 포함

Host→device copy 8 ms, kernel 4 ms, device→host copy 8 ms면 GPU 구간은 20 ms다. CPU 계산이 15 ms라면 GPU kernel만 빠르다는 이유로 전체가 빠르지 않다.

| 단계 | 시간 가정 |
| --- | ---: |
| H2D copy | 8 ms |
| Kernel | 4 ms |
| D2H copy | 8 ms |
| 합계 | 20 ms |

H2D는 Host-to-Device, D2H는 Device-to-Host다.

## 7. Batch

작은 요청 100개를 kernel 100번 launch하는 대신 한 batch로 묶으면 launch overhead를 나눌 수 있다. Latency 요구와 memory 크기를 함께 본다.

## 8. Arithmetic intensity

읽은 byte당 arithmetic operation 수다. 4-byte 값 두 개를 읽고 하나를 쓰며 add 하나라면 대략 12 byte 이동에 연산 1개다.

Matrix multiply는 tile 재사용으로 한 번 읽은 값을 여러 multiply-add에 쓸 수 있다.

## 9. CPU reference

GPU kernel의 작은 입력 결과를 비교할 단순 CPU implementation을 둔다. Reference는 빠를 필요보다 명확성이 중요하다.

## 10. Floating-point 비교

Parallel reduction은 덧셈 순서가 CPU와 달라 rounding 결과가 조금 다를 수 있다. Exact equality 대신 허용 오차를 정한다.

오차 허용은 틀린 index나 race를 숨기는 수단이 아니다.

## 11. Work decomposition

n=1000, block=256이면 grid=4 block, 총 1024 thread다. 각 thread 하나씩 처리하면 24 thread가 여분이다.

Grid-stride loop를 쓰면 thread 수보다 큰 n도 여러 index로 처리할 수 있다.

```text
i = global_index
while i < n:
    process(i)
    i += total_grid_threads
```

## 12. Load imbalance

각 element 처리 시간이 다르면 일부 warp·block이 오래 남는다. 평균 작업량보다 최대 작업량이 kernel 종료를 지배할 수 있다.

## 13. Branch 예제

Lane 0~31에서 값이 0~31이고 `value<4`만 비싼 경로 100 step, 나머지 1 step이라고 하자. 네 lane의 긴 경로 때문에 warp가 두 경로를 처리한다.

Data를 분류해 비슷한 work를 묶는 방법을 검토할 수 있지만 분류 비용도 든다.

## 14. CPU와 GPU 협업

CPU는 input 준비, launch, dependency 구성, result 검증을 맡을 수 있다. GPU는 대량 kernel 계산을 맡는다.

CPU가 기다리는 동안 다른 일을 할 수 있는지는 async API와 program 구조에 달렸다.

## 14.1 Work를 byte와 operation으로 세기

Vector add n=1,000,000은 float input 두 개 8 MB, output 4 MB를 이동하고 add 백만 번을 수행한다는 단순 모형이다.

| 항목 | 계산 | 값 |
| --- | --- | ---: |
| Input read | 2×n×4 byte | 8 MB |
| Output write | n×4 byte | 4 MB |
| Add | n | 1,000,000 |
| 총 device traffic 단순값 | 12×n byte | 12 MB |

Cache와 write 정책을 생략했지만 arithmetic intensity가 낮다는 방향을 보여 준다.

Matrix multiply n×n은 대략 O(n³) arithmetic와 O(n²) data를 재사용할 가능성이 있어 다른 성격이다.

## 14.2 Pipeline을 그린 뒤 overlap을 주장한다

Chunk 0 H2D 3 ms, compute 5 ms, D2H 2 ms를 직렬로 하면 10 ms다. 두 chunk가 있어도 dependency 없이 자동 20 ms 또는 자동 10 ms라고 단정하지 않는다.

Copy engine, pinned memory, 서로 다른 stream, buffer 두 세트가 있을 때 다음 chunk copy와 현재 compute를 겹칠 후보가 생긴다.

Overlap 전후에도 각 chunk result가 맞고 buffer 수명이 겹치지 않는지 검증한다.

## 15. Unified memory 주의

통합 주소 공간이 data 이동 비용을 없애는 마법은 아니다. Page migration과 fault, prefetch, access pattern이 있다.

## 16. 반례

Linked list를 pointer 따라 한 node씩 방문하는 작업은 memory locality와 dependency가 나빠 단순 GPU mapping이 어렵다.

각 element가 독립이어도 n=8이면 launch overhead가 더 클 수 있다.

## 문제와 해설

**문제 1.** 전체 50 ms 중 순차 10 ms, 나머지를 무한히 가속하면 최소 시간은?

**해설.** 10 ms 아래로 갈 수 없다. 최대 speedup은 5배다.

**문제 2.** Kernel 2 ms만 보고 CPU 5 ms보다 빠르다고 결론 내릴 수 있는가?

**해설.** Copy, launch, synchronization을 포함한 end-to-end 시간을 봐야 한다.

**문제 3.** 독립 pixel 계산이면 항상 GPU가 빠른가?

**해설.** 아니다. 입력 크기, transfer, batch, hardware, implementation이 결정한다.

## 공식 자료

- [CUDA execution model](https://docs.nvidia.com/cuda/cuda-programming-guide/01-introduction/programming-model.html)
- [CUDA best practices](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
