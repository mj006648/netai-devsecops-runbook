# 13. 로컬 교육 모형

[← 이전](12-performance-counters-and-bottlenecks.md) · [목차](README.md) · [다음 →](14-experiments-and-research.md)

**교육 모형(toy model)**은 일부 규칙을 작은 상태와 계산으로 옮긴 프로그램이다. **assert**는 예상한 조건이 틀리면 실행을 실패시키는 검사다. 아래 세 모형은 주소 분해·파이프라인 의존성·메모리 사건 순서의 계산을 확인하며, 실제 CPU를 측정하는 프로그램은 아니다.

## 세 로컬 모형의 입력에서 결과까지

이 디렉터리의 Python은 실제 CPU 성능 검증기가 아니라 앞 장 계산을 반복 가능한 작은 상태 전이로 옮긴 교육 모형이다.

`cache_model.py`의 입력은 4096B 용량, 64B block, 2-way와 주소 `0x1234`다.
블록 수 64, set 수 32를 구하고 주소를 block 번호 72로 나눈다.
`offset=52`, `set=72 mod 32=8`, `tag=72//32=2`가 되어 `(2,8,52)` assertion을 만족한다.
이 결과는 hit를 보장하지 않는다. 실제 hit 판정에는 set 8의 valid와 저장 tag가 필요하다.

`pipeline_model.py`는 IF·ID·EX·MEM·WB 각 단계의 현재 명령을 상태로 둔다.
매 주기에 단계별 명령을 기록하고, EX의 LOAD가 만들 값이 ID 명령의 입력인지 검사한다.
의존성이 있으면 IF·ID를 유지하고 다음 EX에 빈 작업을 넣는다. LOAD는 MEM으로 진행한다.
주기는 1부터 센다. LOAD의 MEM은 4주기, ADD의 ID는 3·4주기, ADD의 EX는 5주기다.
LOAD의 MEM 끝에서 나온 값이 다음 주기 ADD의 EX에 전달되는 시간 관계를 assertion으로 확인한다.
실제 CPU의 단계 수나 load 지연을 재는 프로그램이 아니다.

`memory_order_model.py`는 seq_cst store-buffering의 사건 순서를 열거한다.
각 스레드의 `store<load` 순서를 보존하는 전역 순서에서 읽기 결과를 계산하므로 `(0,0)`은 나오지 않는다.
relaxed 교육 집합에는 store buffer 때문에 `(0,0)`을 포함한다.
별도 message passing은 acquire가 release의 flag=1을 실제로 읽은 경우에만 data=42를 보장한다.

```mermaid
flowchart LR
  I[고정 입력] --> S[중간 상태를 한 단계씩 갱신]
  S --> A[assert 예상 불변식]
  A --> O[교육용 결과 출력]
```

### 문제 1
cache 주소 `0x1a34`의 결과는?
**풀이:** block 104, set 8, tag 3, offset 52다. `0x1234`와 같은 set의 다른 tag다.

### 문제 2
load-use bubble을 제거하면 무엇이 깨지는가?
**풀이:** add EX 시작에 load 데이터가 아직 없어 오래된 값을 쓸 수 있다. 모형의 생성 시점 불변식이 실패한다.

### 문제 3
release/acquire store-buffering에서 둘 다 0이면 왜 동기화가 없는가?
**풀이:** 어느 acquire도 상대 release가 쓴 1을 읽지 않았다. synchronizes-with가 생기지 않았으므로 seq_cst처럼 금지할 수 없다.

## 공식 자료

[RISC-V specifications](https://docs.riscv.org/)

[← 이전](12-performance-counters-and-bottlenecks.md) · [목차](README.md) · [다음 →](14-experiments-and-research.md)
