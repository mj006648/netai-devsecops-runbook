# 05. Query planning과 cost

[이 책 목차](README.md) · [이전: Scan, filter와 join](04-scans-filters-and-joins.md) · [다음: Transaction과 ACID](06-transactions-and-acid.md)

Planner는 SQL 결과가 같은 여러 physical plan을 열거하고 통계와 cost parameter로 비교한다. Cost는 wall-clock millisecond가 아니라 plan을 상대 비교하기 위한 추정 단위다.

이 장의 숫자와 출력은 교육용이며 실제 PostgreSQL 실행 결과가 아니다.

## 논리 계획에서 물리 계획으로

**논리 계획**은 관계 대수 관점에서 무엇을 계산할지 나타낸다. filter, projection, join 같은 노드가 있지만 scan 방식이나 join 알고리즘은 아직 정하지 않을 수 있다. **물리 계획**은 순차 스캔·인덱스 스캔·hash join처럼 실행기가 수행할 구현을 고른 트리다. 플래너는 카탈로그 통계를 읽어 후보별 **cardinality**, 즉 출력 행 수를 추정한다. **selectivity**는 입력 중 통과 비율이며 `출력 행/입력 행`이다.

100만 행에서 `country='KR'` 선택도 0.1, `status='paid'` 선택도 0.2라고 하자. 독립이라고 가정하면 둘 다 만족할 선택도는 `0.1×0.2=0.02`, 예상 20,000행이다. 실제로 KR 주문의 90%가 paid라면 실제는 90,000행으로 4.5배 과소 추정한다. 두 열 상관관계를 단일 열 통계가 놓친 결과다. 이 오차가 join 앞에 있으면 nested loop 반복, hash build 크기, spill 여부를 함께 틀릴 수 있다.

cost 단위는 ms가 아니다. 설명용으로 순차 페이지 1, 임의 페이지 4, 행 CPU 0.01이라고 하자. 순차 스캔 10,000페이지와 100만 행 필터는 `10000×1 + 1000000×0.01 = 20,000 cost`다. 인덱스 경로가 3페이지 탐색과 20,000개 임의 힙 페이지를 예상하면 `3×4 + 20000×4`만으로 80,012가 되어 인덱스가 있어도 더 비싸다. cache, correlation, covering 여부가 바뀌면 상대 순서도 달라진다.

## 탐색 공간과 실행 관측

세 테이블 A,B,C의 inner join은 `(A⋈B)⋈C`, `(A⋈C)⋈B`, `(B⋈C)⋈A` 등 순서와 각 scan/join 구현 조합을 가진다. 테이블 수가 늘면 후보가 폭발하므로 optimizer는 동적 계획법, pruning, 휴리스틱 또는 제한된 탐색을 쓴다. 최저 cost 선택은 탐색한 후보와 모형 안에서의 선택이지 모든 하드웨어 상태에서 절대 최적이라는 증명이 아니다.

EXPLAIN은 추정 계획을 보이고 실행하지 않는 형태가 기본이다. EXPLAIN ANALYZE는 문장을 실제 수행하고 actual rows, loops, time을 붙인다. 노드의 actual rows가 loop당 값인지 총합인지 도구 형식을 확인한다. UPDATE·DELETE·함수 호출을 ANALYZE하면 실제 부작용이 생길 수 있으며 rollback되지 않는 외부 효과나 sequence도 고려한다.

CIDR 2025의 QOaaS 연구는 Calcite/Cascades 계열 탐색을 여러 엔진에 서비스로 제공하는 방향을 탐구한 prototype이다. 기초 원리에서 바뀌는 비용은 “각 엔진이 계획 탐색과 규칙을 중복 구현하는 비용”과 “여러 실행 엔진의 통계·물리 능력을 하나의 최적화 인터페이스로 표현하는 비용”이다. 모든 Spark 질의에서 실측 우위를 보장한다는 뜻이 아니다. 비교 실험은 동일 SQL 의미, 엔진별 지원 연산자, 통계 신선도, cold/warm cache를 고정하고 planning time과 execution time을 분리해야 한다.

2026 preprint의 filtered vector lakehouse 연구는 파일 pruning과 근사 최근접 이웃 탐색을 결합하는 문제를 다룬다. 전통 optimizer 관점에서는 filter selectivity가 어느 파일과 벡터 후보를 읽을지 바꾼다. 조건을 먼저 강하게 적용하면 탐색 공간은 줄지만 recall을 잃지 않는 조건부 정확성 계약이 필요하다. 아직 preprint이므로 특정 제품의 일반 보장으로 쓰지 않고, cold run의 파일 I/O와 warm run의 cache 효과, filter 정확성과 ANN recall을 별도 축으로 측정한다.

### 문제 5개

1. 100만행, 선택도 0.03의 예상 행 수는? **해설:** 30,000행이다.
2. estimate 1,000, actual 100,000의 오차는? **해설:** actual/estimate 100배 과소 추정이다.
3. cost 200이 200ms인가? **해설:** 아니다. 설정된 I/O·CPU 상대 단위의 합이며 실시간과 직접 같지 않다.
4. LIMIT 1은 무엇을 바꾸는가? **해설:** 모든 행의 total cost보다 첫 행까지 startup cost가 낮은 경로를 선호하게 할 수 있다.
5. EXPLAIN ANALYZE DELETE를 운영 데이터에서 관찰용으로 실행해도 되는가? **해설:** 실제 DELETE를 실행한다. 격리된 복제 데이터와 트랜잭션 경계, 외부 효과를 먼저 설계해야 한다.

![05. Query planning과 cost 흐름](assets/query-plan-tree.svg)

## 1. 단어와 실제 위치

| 용어 | 뜻 |
| --- | --- |
| Parse tree | SQL grammar 구조를 표현한 tree |
| Logical plan | 무엇을 계산할지 표현한 relational operator tree |
| Physical plan | 구체 scan·join·sort algorithm을 고른 tree |
| Cardinality | Operator가 만들 것으로 예상한 row 수 |
| Selectivity | Input 중 predicate를 통과할 비율 |
| Statistics | Row 수, distinct count, 분포를 요약한 catalog data |
| Startup cost | 첫 row 전까지 드는 추정 비용 |
| Total cost | 모든 row를 만들 때의 추정 비용 |
| Plan node | Executor가 수행할 한 physical operation |
| EXPLAIN | Planner가 만든 plan과 추정치를 보여 주는 PostgreSQL command |

## 2. 관련 객체

- SQL text와 bound expression

- Catalog statistics

- Candidate join order와 access path

- Chosen plan tree

- EXPLAIN estimated rows/cost/width

- ANALYZE 실행 시 actual rows/loops/time

## 3. 입력→주체→중간 상태→결과

```mermaid
flowchart LR
 I["입력"] --> A["실행 주체"]
 A --> S["중간 상태"]
 S --> R["결과"]
```

1. Parser와 binder가 valid query tree를 만든다.

2. Rewrite가 view 등을 base relation으로 바꿀 수 있다.

3. Planner가 가능한 scan path를 만든다.

4. Join graph에서 허용 join order를 탐색한다.

5. 각 path의 cardinality를 통계로 추정한다.

6. I/O·CPU·startup·total cost를 계산한다.

7. Required ordering과 LIMIT을 반영한다.

8. 가장 낮다고 추정한 plan을 선택한다.

9. Executor가 plan node를 실제 수행한다.

10. EXPLAIN ANALYZE이면 실제 실행 통계를 plan에 붙인다.

## 4. 숫자로 연결하기

- table rows 1,000,000

- predicate true rows 실제 100,000 = 10%

- 통계 추정 1,000 = 0.1%

- nested loop inner lookup 100,000회 가능

- estimate error 100배가 join 선택을 바꿀 수 있음

## 5. 왜 필요한가와 조건

Cost 100은 100ms라는 뜻이 아니다.

Estimated rows가 틀리면 좋은 algorithm도 잘못된 input 크기에서 느려질 수 있다.

Multi-column correlation을 독립으로 가정하면 selectivity를 크게 틀릴 수 있다.

LIMIT은 total cost보다 startup cost가 작은 plan을 선호하게 할 수 있다.

Prepared statement는 parameter별 custom plan과 generic plan trade-off가 있다.

EXPLAIN ANALYZE는 statement를 실제 실행하므로 write statement의 side effect가 발생한다.

## 6. 실행 계획 또는 상태를 읽는 질문

- Input과 output cardinality는 얼마인가?

- Memory budget을 넘으면 spill·wait·abort 중 무엇이 일어나는가?

- Snapshot 또는 transaction 경계는 어디인가?

- Cache와 storage 상태가 달라도 correctness가 유지되는가?

- Error가 client까지 전달되는가?

## 7. 오해와 반례

- EXPLAIN은 query를 실행해 실제 시간을 보여 준다.

- EXPLAIN ANALYZE는 SELECT 외 statement도 안전한 read-only다.

- Actual time은 network 전송까지 모두 포함한다.

- Cost가 낮은 plan은 모든 cache 상태에서 빠르다.

- Index 존재만으로 index scan cost가 낮다.

## 8. 교육용 실험 설계

1. 고정된 작은 input을 적는다.

2. 예상 intermediate state를 표로 만든다.

3. 한 조건만 바꾼다.

4. 추정과 실제 관찰을 분리한다.

5. Side effect가 있는 명령은 실행 여부를 명시한다.

6. Version과 configuration을 기록한다.

## 9. 문제

1. Estimate 1,000, actual 100,000이면 몇 배 error인가?

2. EXPLAIN과 EXPLAIN ANALYZE 차이는?

3. ANALYZE write statement를 다룰 때 주의점은?

## 10. 해설

1. Actual/estimate=100으로 100배 underestimate다.

2. 전자는 plan 추정, 후자는 statement를 실제 실행해 actual 통계를 더한다.

3. 실제 side effect가 일어나므로 격리·transaction rollback 가능성과 sequence 등 비transactional 효과를 검토한다.

## 11. 공식 자료

- [공식 문서](https://www.postgresql.org/docs/current/sql-explain.html)

- [CMU 15-445/645 Fall 2024](https://15445.courses.cs.cmu.edu/fall2024/syllabus.html)

다음 장에서는 이 상태가 concurrency, recovery 또는 analytical execution과 만나는 경계를 이어서 본다.


## 보강: 계획 트리를 아래에서 위로 읽기

![구체적인 쿼리 실행 계획 트리](assets/query-plan-tree.svg)

Planner는 SQL과 catalog statistics를 입력으로 여러 operator tree를 만들고 cost model로 후보를 비교한다. Cardinality는 여기서 연산자가 낼 행 수이며 selectivity는 입력 중 통과 비율이다. 100만 행에 선택도 0.01이면 예상 출력은 10,000행이다. 실제가 400,000행이면 40배 오차이며 그 뒤 Hash Join의 build side와 메모리 예상도 틀어진다. EXPLAIN의 cost와 rows는 추정이고, EXPLAIN ANALYZE는 쿼리를 실제 실행해 actual rows와 loops를 더한다. 쓰기 SQL의 부작용도 실제 발생할 수 있다.
