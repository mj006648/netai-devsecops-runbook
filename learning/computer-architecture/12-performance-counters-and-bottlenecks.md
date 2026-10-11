# 12. 성능 카운터와 병목

[← 이전](11-numa-interconnects-dma-and-iommu.md) · [목차](README.md) · [다음 →](13-local-models.md)

**성능 카운터(performance counter)**는 주기·명령·캐시 사건 등의 횟수를 세는 수치다. **PMU(Performance Monitoring Unit)**는 이런 하드웨어 사건을 관측하는 장치다. **CPI**는 명령당 주기 수, **IPC**는 주기당 명령 수다. 같은 숫자도 측정 구간과 사건 정의가 다르면 비교할 수 없다.

## 숫자를 원인으로 착각하지 않는 성능 관측

instruction count는 관측 구간에서 retire한 명령 수다.
cycle count는 선택한 클록 기준으로 센 주기 수다.
PMU는 이런 하드웨어 사건을 세는 장치이고 counter는 그 누적값을 담는 제한된 개수의 레지스터다.
CPI는 `cycles/instructions`, IPC는 `instructions/cycles`다.

10억 instructions와 25억 cycles면 CPI=2.5 cycle/instruction, IPC=0.4 instruction/cycle다.
둘은 같은 구간과 같은 의미의 count를 썼을 때 역수 관계다.
2.5 GHz에서 25억 기준 cycle이 실제 경과 1초와 대응한다는 가정이 맞다면 시간은 1초지만, 주파수 변화와 counter 정의를 먼저 확인해야 한다.

cache miss 500만을 10억 instructions로 나누면 MPKI는 `5,000,000/1,000,000,000×1000=5`다.
MPKI 단위는 천 명령당 miss다.
miss 하나의 비용이 모두 같지 않으므로 MPKI만으로 잃은 cycle을 확정할 수 없다.

PMU counter 수보다 동시에 요청한 event가 많으면 도구가 시간을 나눠 multiplexing할 수 있다.
각 event는 전체 구간 일부만 측정되고 도구가 확대 추정하므로 짧거나 변동 큰 실행에서는 오차가 커진다.
스레드 이동, 다른 프로세스, interrupt, turbo, warm cache도 관측을 바꾼다.

```mermaid
flowchart LR
  Q[같은 입력·구간] --> C[cycles·instructions]
  C --> M[CPI·IPC·MPKI]
  M --> H[병목 가설]
  H --> T[추가 event와 통제 실험]
```

### 문제 1
4억 instructions, 6억 cycles의 CPI와 IPC는?
**풀이:** CPI=1.5, IPC=2/3≈0.667이다. 서로 다른 실행 구간 count를 섞으면 안 된다.

### 문제 2
2백만 miss, 4억 instructions의 MPKI는?
**풀이:** `2,000,000/400,000,000×1000=5`다.

### 문제 3
CPI가 1.2에서 2.0이 되면 cache가 원인인가?
**풀이:** 아직 모른다. miss, branch, frontend, 스케줄 이동과 주파수를 함께 관측하고 한 조건씩 통제해야 한다.

## 공식 자료

[Linux perf security](https://docs.kernel.org/admin-guide/perf-security.html)

[← 이전](11-numa-interconnects-dma-and-iommu.md) · [목차](README.md) · [다음 →](13-local-models.md)
