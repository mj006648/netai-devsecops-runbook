# 05. Query planning과 cost

[이 책 목차](README.md) · [이전: Scan, filter와 join](04-scans-filters-and-joins.md) · [다음: Transaction과 ACID](06-transactions-and-acid.md)

같은 SQL 결과를 만드는 실행 방법은 하나가 아니다. table 전체를 순서대로 읽을 수도 있고 index로 후보를 찾을 수도 있다. 두 table을 nested loop, hash join, sort-merge join으로 결합할 수 있고, 세 table은 결합 순서까지 바뀐다. 실행 전에 모든 방법을 실제로 수행해 가장 빠른 것을 고를 수는 없으므로 데이터베이스는 저장된 통계와 비용 모형으로 후보를 비교한다.

이 장의 cost 숫자는 선택 과정을 손으로 추적하기 위한 교육 단위다. PostgreSQL cost는 설정과 통계, 물리 환경에 따라 계산되며 wall-clock millisecond와 같지 않다.

![05. Query planning과 cost 흐름](assets/query-plan-tree.svg)

## 1. SQL text에서 실행 계획까지 존재하는 객체

client가 보낸 **SQL text**는 문자로 된 요청이다. parser는 문법을 확인해 **parse tree(구문 트리)**를 만든다. 이 트리는 SELECT, FROM, WHERE 같은 문법 구조를 나타내며 아직 실제 table 객체와 열 type이 모두 연결되지 않았을 수 있다.

binder 또는 analyzer는 이름을 catalog의 실제 table·column과 연결하고 type과 연산자를 결정한다. **catalog(카탈로그)**는 schema, table, index, 통계 같은 database metadata를 저장하는 내부 table 집합이다. query 문장보다 오래 존재하며 DDL과 ANALYZE 같은 작업으로 바뀐다.

**logical plan(논리 계획)**은 무엇을 계산해야 하는지 관계 연산자로 표현한 tree다. scan 대상 관계, filter predicate, projection, join과 aggregate가 들어가지만 구체적인 scan과 join algorithm은 아직 열어 둘 수 있다. 논리 계획은 SQL의 결과 의미를 보존해야 한다.

**physical plan(물리 계획)**은 실행기가 실제 수행할 방법을 고른 tree다. sequential scan인지 index scan인지, hash join인지 nested loop인지, sort가 필요한지, 어느 입력을 먼저 처리하는지 정한다.

**plan node(계획 노드)**는 physical plan의 연산 하나다. 실행 때 node마다 cursor, hash table, sort buffer 같은 상태가 생긴다. plan 객체는 준비된 statement cache에 남을 수도 있고 query 뒤 버려질 수도 있다. 실행 상태는 각 실행마다 새로 만들어진다.

## 2. optimizer가 필요한 이유

**optimizer(최적화기)**는 결과가 같다고 판단한 여러 후보 계획을 만들고 추정 cost가 가장 낮은 계획을 고르는 데이터베이스 구성 요소다. 이름이 “항상 실제 최적”을 보장한다는 뜻은 아니다. 탐색한 후보와 가진 통계, cost model 안에서 가장 낮다고 추정한 것을 선택한다.

optimizer는 세 종류의 질문에 답한다.

1. 어느 조건을 scan 가까이 내릴 수 있는가?
2. 각 scan과 join이 몇 row를 만들 것인가?
3. 같은 결과를 만드는 물리 algorithm과 join order 중 무엇의 cost가 낮은가?

후보 수는 빠르게 증가한다. table이 세 개면 (A join B) join C, (A join C) join B, (B join C) join A 같은 순서가 있고, 각 leaf에는 여러 scan, 각 join에는 여러 algorithm이 있다. table 수가 늘면 모든 조합을 단순 열거하기 어려워 dynamic programming, pruning, heuristic, 제한 탐색을 사용한다.

**search space(탐색 공간)**는 optimizer가 고려할 후보 계획 집합이다. 가장 낮은 cost라는 말은 이 공간 밖의 계획까지 모두 증명했다는 뜻이 아니다.

## 3. cardinality와 selectivity

**cardinality(카디널리티)**는 plan node가 출력할 row 수다. planner 단계에서는 추정값이고, 실제 실행 뒤에는 actual row count를 관측할 수 있다.

**selectivity(선택도)**는 입력 row 중 predicate가 TRUE가 될 비율이다.

selectivity = output rows / input rows

table 1,000,000 row에서 country = 'KR'가 100,000 row면 실제 선택도는 0.1이다. planner가 0.08로 추정하면 예상 cardinality는 80,000 row다.

여러 predicate를 독립이라고 가정하면 선택도를 곱할 수 있다. country='KR' 추정 0.1, status='paid' 추정 0.2면 결합 선택도는 0.1 × 0.2 = 0.02, 예상 20,000 row다.

그러나 실제 KR row의 90%가 paid라면 두 조건을 모두 만족하는 row는 100,000 × 0.9 = 90,000이다. 추정 20,000에 비해 4.5배 많다. 두 열 값이 서로 관련된 **correlation(상관관계)**을 독립 가정이 놓친 것이다.

이 오차는 한 node에서 끝나지 않는다. 20,000 row라고 생각해 nested loop를 고르거나 작은 hash table을 예상했는데 실제 90,000 row면 inner lookup과 memory가 함께 늘고 spill이 발생할 수 있다.

## 4. statistics는 원본 row의 요약이다

**statistics(통계)**는 planner가 전체 table을 실행 전 매번 읽지 않고 분포를 추정하도록 catalog에 저장한 요약 정보다. ANALYZE 같은 수집 작업이 sample이나 전체 자료를 읽어 갱신한다. table 내용이 계속 바뀌면 통계는 stale, 즉 현재 분포와 어긋날 수 있다.

주요 통계의 의미는 다음과 같다.

- **row count**: table에 있는 row 수의 추정
- **null fraction**: NULL row 비율
- **n_distinct**: 서로 다른 값 수의 추정
- **MCV(Most Common Values)**: 자주 나타나는 값과 빈도
- **histogram(히스토그램)**: 나머지 값 분포를 여러 경계 구간으로 요약
- **physical correlation**: column 정렬 순서와 table 물리 순서의 관련성
- **extended statistics**: 여러 column의 dependency, distinct 조합, MCV를 함께 요약

histogram을 예로 보자. age 값을 경계 [20,30,40,50,60]으로 요약했다면 age BETWEEN 30 AND 40의 비율을 해당 구간과 주변 분포로 근사한다. 구간 안에 모든 값이 균등하다는 가정이 숨어 있을 수 있다. age 35에 row 절반이 몰린다면 MCV가 따로 잡지 못한 경우 크게 틀린다.

MCV에 status='paid'가 20%라고 기록되어 있으면 equality 선택도에 직접 사용할 수 있다. MCV 밖 값은 남은 비율과 distinct 수로 균등 가정할 수 있다. sample 크기가 작거나 데이터가 급변하면 희귀값 추정이 흔들린다.

열 간 dependency 통계가 country와 status 관계를 포착하면 독립 곱보다 나은 결합 선택도를 만들 수 있다. 모든 predicate 종류와 복잡한 표현식에 자동으로 정확한 것은 아니다.

## 5. cost의 단위와 구성

**cost**는 후보 계획을 상대 비교하기 위한 추정 수치다. 일반적으로 page I/O, row 처리 CPU, operator 시작 비용과 전체 비용을 설정된 가중치로 더한다. 20,000 cost가 20,000 ms라는 뜻이 아니다.

교육 모형에서 다음 단가를 사용한다.

- sequential page read = 1 cost
- random page read = 4 cost
- row CPU predicate = 0.01 cost
- hash build 또는 probe row = 0.02 cost
- index level page = random page와 같은 4 cost

1,000,000 row, 10,000 page인 orders를 모두 읽고 predicate를 검사하는 sequential plan은

10,000 × 1 + 1,000,000 × 0.01 = 20,000 cost

다.

index 탐색 높이가 3 page이고 20,000 matching row가 각각 다른 heap page에 있다고 추정하면

3 × 4 + 20,000 × 4 + 20,000 × 0.01
= 12 + 80,000 + 200
= 80,212 cost

다. index가 있어도 예상 match가 많고 table 순서가 흩어져 있으면 sequential scan이 더 낮다.

실제로 matching row가 같은 heap page에 모였거나 page가 cache에 있거나 covering index가 table 접근을 줄이면 index 경로가 싸질 수 있다. cost parameter는 hardware와 cache 현실의 근사이며 결과를 보장하지 않는다.

## 6. startup cost와 total cost

**startup cost(시작 비용)**는 첫 row를 내기 전까지의 추정 비용이다. **total cost(전체 비용)**는 모든 row를 낼 때의 추정 비용이다.

sequential scan은 첫 page에서 qualifying row를 빨리 찾을 수 있어 startup이 낮을 수 있다. full sort는 모든 input을 읽어 정렬한 뒤 첫 row를 내므로 startup이 높다. hash join도 build side를 모두 읽어 hash table을 만든 뒤 probe output을 내기 시작한다.

LIMIT 1 query는 전체 row를 만들 필요가 없어 startup과 초반 row cost가 중요하다. total cost가 낮은 full sort보다 index order로 첫 row를 빠르게 찾는 경로를 선호할 수 있다.

반대로 client가 모든 row를 읽는다면 startup만 낮고 이후 random I/O가 많은 계획보다 total이 낮은 계획이 낫다. client가 중간에 fetch를 멈추는지까지 planner가 항상 정확히 알지는 못한다.

## 7. predicate pushdown의 의미 조건

**predicate pushdown**은 filter를 data source나 join 아래로 내려 intermediate row를 줄이는 변환이다. orders.status='paid'가 orders에만 의존하고 inner join 결과 의미가 같다면 orders scan에서 먼저 적용할 수 있다.

그러나 outer join의 preserved row를 제거하면 안 된다. LEFT JOIN 오른쪽 열 조건을 ON에서 WHERE로 옮기면 NULL-extended row가 사라질 수 있다. optimizer는 null-rejecting 조건과 join type을 분석해 의미가 보존되는 변환만 해야 한다.

storage engine이나 remote source에 filter를 보내는 pushdown은 지원 연산자와 collation, NULL, timezone 의미가 같아야 한다. source가 predicate를 처리하지 못하면 database에서 다시 filter한다. “pushdown됨”은 row가 반드시 정확한 추정 수만큼 줄었다는 뜻이 아니다.

projection pushdown은 필요한 column만 읽어 row width와 I/O를 줄인다. 이후 join·sort·output에 필요한 column과 MVCC 정보는 남겨야 한다.

## 8. 세 table의 join order가 intermediate를 바꾼다

다음 실제 크기를 가정한다.

- customers C: 100,000 row
- orders O: 1,000,000 row
- lineitems L: 5,000,000 row

predicate 후 추정은 다음과 같다.

- C.country='KR': 10,000 row
- O.status='paid': 200,000 row
- L.shipped=true: 4,000,000 row

관계는 O.customer_id = C.id, L.order_id = O.id다.

### 후보 순서 A: C와 O를 먼저 join

C filter 10,000과 O filter 200,000을 join해 paid KR orders를 추정 20,000 row로 만든다. 그 order_id를 L과 join해 order당 평균 4 lineitem, shipped 비율 0.8을 적용하면 약 64,000 row를 예상한다.

### 후보 순서 B: O와 L을 먼저 join

O 200,000과 L 4,000,000을 먼저 join하면 order당 평균 4 shipped item이라고 단순화할 때 800,000 intermediate row가 된다. 이후 C 10,000과 join해 64,000 output으로 줄어든다.

최종 output 추정이 같아도 A는 큰 intermediate 800,000을 만들기 전에 customer filter로 orders를 줄인다. hash table, memory, CPU와 spill 위험이 작을 수 있다.

하지만 실제로 KR customer의 paid 비율이 매우 높아 C⋈O가 90,000 order이고, 특정 shipped order에 lineitem이 평균 20개라면 A의 실제 intermediate와 output은 예상보다 훨씬 커진다. join order 선택은 cardinality 추정 품질에 달려 있다.

outer join은 순서를 자유롭게 바꾸기 어렵다. preserved side와 NULL 확장 의미를 유지하는 순서만 후보가 된다. optimizer의 algebraic 변환에는 SQL semantics 조건이 붙는다.

## 9. 세 가지 복수 계획의 cost와 최종 선택

country='KR' AND status='paid' 조건의 orders와 customers를 join하는 query를 단순화해 비교한다. planner 추정은 orders 20,000 row, customers의 KR 10,000 row다.

### 계획 P1: orders sequential scan + customers hash join

- orders scan/filter: 20,000 cost
- customers scan 1,000 page: 1,000
- customers row filter CPU: 100,000 × 0.01 = 1,000
- hash build 10,000 × 0.02 = 200
- orders probe 20,000 × 0.02 = 400
- 합계: 22,600 cost

### 계획 P2: orders index scan + customers hash join

- orders index와 heap: 80,212
- customers scan/filter/hash: 1,000 + 1,000 + 200
- probe: 400
- 합계: 82,812 cost

### 계획 P3: KR customers를 outer로 index nested loop

- customers scan/filter: 2,000
- 고객 10,000명마다 orders index root→leaf 3 page를 모두 random read한다고 단순화: 10,000 × 3 × 4 = 120,000
- 예상 output 20,000 heap fetch: 20,000 × 4 = 80,000
- predicate CPU: 200
- 합계: 202,200 cost

교육 모형 optimizer는 P1의 22,600을 최저로 선택한다.

| 계획 | 추정 cost | 선택 |
|---|---:|---|
| P1 seq + hash | 22,600 | 선택 |
| P2 index + hash | 82,812 | 제외 |
| P3 index nested loop | 202,200 | 제외 |

이 선택은 index가 나쁘다는 일반 결론이 아니다. buffer cache hit, heap clustering, 실제 output, LIMIT과 parallel scan 지원이 바뀌면 순서가 달라진다.

## 10. 오추정이 계획을 바꾸는 반례

이번에는 통계가 status='rare' 선택도를 0.0001로 추정해 orders 100 row라고 하자. 실제 데이터가 최근 급변해 100,000 row다.

추정에 따른 index 경로:

- index 3 page: 12
- heap 100 row: 400
- CPU: 1
- 합계 약 413

sequential scan 20,000보다 훨씬 낮아 index plan을 선택한다.

실제 실행에서 heap fetch가 100,000 random page라고 단순화하면 400,000 cost 성격의 I/O가 생길 수 있다. estimate 100, actual 100,000은 actual/estimate = 1000배 과소 추정이다.

이 오차가 nested loop outer row 수라면 inner index lookup도 예상 100회에서 실제 100,000회로 늘어난다. hash join을 골랐다면 build가 예상보다 커져 memory budget을 넘고 spill할 수 있다.

고치는 순서는 “index를 강제로 금지”부터가 아니다.

1. actual rows와 estimate rows가 처음 갈라지는 node를 찾는다.
2. statistics가 stale인지, MCV나 histogram이 분포를 표현하는지 본다.
3. 열 간 correlation이나 parameter 값에 따른 skew를 확인한다.
4. 통계를 갱신하고 필요한 extended statistics를 검토한다.
5. 같은 입력에서 새 estimate와 plan, 실제 시간을 재검증한다.

## 11. join cardinality와 중복 key

A와 B의 equality join output은 단순히 작은 table row 수가 아니다. 각 key k의 빈도를 A_k와 B_k라고 하면 output은 key별 A_k × B_k를 합한 값이다.

예를 들어 A에서 key7이 100 row, B에서 key7이 200 row면 그 key만 20,000 pair다. n_distinct가 같아도 한 key에 몰린 skew를 MCV가 잡지 못하면 join cardinality를 과소 추정할 수 있다.

foreign key와 unique constraint가 있으면 강한 상한 정보를 줄 수 있다. B의 join key가 unique이면 A row 하나가 B에서 최대 한 row와 match한다. 그러나 NULL과 outer join, predicate로 보존 row 수가 달라지는 조건을 함께 본다.

통계와 constraint는 optimizer가 읽는 metadata다. 실제 데이터가 constraint를 만족하도록 database가 집행하는 것과, sample 통계가 분포를 근사하는 것은 신뢰 수준이 다르다.

## 12. sort, aggregation, memory cost

ORDER BY와 merge join은 정렬된 입력이 필요하다. index가 required order를 제공하면 sort를 생략할 수 있다. 그렇지 않으면 memory에서 sort하고 예산을 넘으면 sorted run을 temporary storage에 쓴다.

planner가 row count뿐 아니라 **row width(행 너비)**를 추정하는 이유가 여기 있다. 100,000 row × 32 B는 payload 3.2 MB지만 100,000 × 2 KiB는 약 200 MB다. 같은 cardinality라도 memory와 spill 가능성이 다르다.

hash aggregation도 group 수를 cardinality로 추정해 hash table 크기를 예상한다. distinct group이 100이라고 생각했는데 실제 1,000,000이면 memory 계획이 깨진다.

cost model이 spill을 완벽히 예측하지 못하거나 storage 경쟁을 모를 수 있다. EXPLAIN에서 계획된 sort 방식과 실행 후 actual sort method, disk 사용을 비교한다.

## 13. prepared statement와 parameter skew

**prepared statement(준비된 문장)**는 SQL 구조를 한 번 분석하고 parameter 값만 바꿔 반복 실행하는 객체다. parameter별 분포가 크게 다르면 하나의 generic plan이 모든 값에 좋지 않을 수 있다.

status='rare'는 index scan이 좋고 status='paid'는 table 대부분이라 sequential scan이 좋을 수 있다. **custom plan**은 실제 parameter를 보고 각 실행에 맞춘 계획이고, **generic plan**은 parameter에 공통인 계획을 재사용해 planning 비용을 줄인다.

어느 방식을 선택하는지는 제품 정책과 실행 이력에 달린다. prepared statement가 항상 같은 plan 또는 항상 parameter 최적 plan이라고 단정하지 않는다. 성능 문제를 재현할 때 literal query와 prepared parameter 실행을 구분한다.

## 14. EXPLAIN과 EXPLAIN ANALYZE를 안전하게 읽기

**EXPLAIN**은 planner가 선택한 plan과 estimated rows, startup/total cost, width를 보여 준다. 기본 형태는 query를 실행해 actual time을 재는 명령이 아니다.

**EXPLAIN ANALYZE**는 statement를 실제 실행하고 actual rows, loops, time 같은 관측을 붙인다. node의 actual rows가 loop당 값인지 총합인지 출력 형식을 확인한다. nested loop inner node가 actual rows 2, loops 100이면 총 200 row가 생산되었을 수 있다.

UPDATE, DELETE, INSERT 또는 side-effect 함수에 EXPLAIN ANALYZE를 쓰면 실제 부작용이 발생한다. transaction rollback로 table 변경을 되돌릴 수 있어도 sequence 증가, 외부 API 호출, 알림 같은 효과는 rollback되지 않을 수 있다. 격리된 복제 데이터와 안전한 transaction 경계를 설계한다.

actual time은 server executor node 관측이며 client network 전송과 화면 출력 전체 시간을 반드시 포함하지 않는다. instrumentation 자체도 overhead를 만든다. 실행 시간 비교는 별도의 반복 benchmark와 함께 한다.

## 15. 계획을 아래에서 위로 읽는 절차

![구체적인 쿼리 실행 계획 트리](assets/query-plan-tree.svg)

1. 가장 아래 scan node에서 estimated rows와 실제 rows를 비교한다.
2. filter에서 removed rows와 선택도를 계산한다.
3. join의 각 input actual rows와 loops를 확인한다.
4. 첫 큰 estimation error가 어느 node인지 찾는다.
5. hash와 sort memory, batches, spill 또는 temp I/O를 본다.
6. root output이 SQL 예상 row와 맞는지 확인한다.
7. planning time과 execution time을 분리한다.
8. cache, parameter, statistics timestamp와 configuration을 기록한다.

상위 node의 큰 오차는 아래 오차가 곱해져 올라온 결과일 수 있다. root만 보고 optimizer 전체가 틀렸다고 하지 않고 최초 분기점을 찾는다.

## 16. 연구 방향을 기본 원리와 연결하기

여러 query engine이 각자 optimizer를 구현하면 규칙, cost model, engine capability 표현을 중복 개발한다. optimizer를 서비스로 분리하는 연구는 SQL 의미와 각 실행 engine의 물리 operator·통계를 공통 interface로 표현하는 문제를 다룬다.

이런 연구의 평가에서는 planning time과 execution time을 분리하고, 동일 SQL 의미와 통계 신선도, engine별 지원 operator를 고정해야 한다. 서비스가 낮은 추정 cost를 만들었다는 것과 실제 wall-clock이 개선되었다는 것을 별도로 보여야 한다.

lakehouse의 file pruning과 vector search를 결합할 때도 selectivity 원리가 적용된다. metadata filter가 읽을 file을 줄이지만 approximate nearest-neighbor 탐색의 recall을 깨뜨리지 않는 정확성 계약이 필요하다. cold file I/O와 warm cache를 분리하고 filter 정확도와 vector recall, 실행 시간을 각각 측정한다.

최신 연구 결과를 특정 PostgreSQL version이나 모든 workload의 보장으로 옮기지 않는다. 논문의 후보 탐색 범위, 통계 입력, baseline, hardware와 실패 조건을 확인한다.

## 17. 완전 풀이 문제

### 문제 1. 선택도와 cardinality

1,000,000 row에서 선택도 0.03이면 예상 output은?

**풀이:** 1,000,000 × 0.03 = 30,000 row다. 이것은 planner estimate라면 실제 count와 다를 수 있다. 선택도가 어느 통계와 가정에서 나왔는지 기록한다.

### 문제 2. 상관관계 오차

country KR 10%, paid 20%를 독립으로 추정했지만 KR 중 paid가 90%다. 전체에서 두 조건 실제 비율과 오차는?

**풀이:** KR이 전체 10%이고 그중 paid 90%이므로 실제 결합 선택도는 0.1 × 0.9 = 0.09, 90,000 row다. 독립 추정은 0.02, 20,000 row다. actual/estimate = 4.5배 과소 추정이다.

### 문제 3. cost와 시간

plan cost 22,600이면 22.6초인가?

**풀이:** 아니다. page와 CPU 작업에 설정한 상대 단위를 합한 수치다. 같은 optimizer 설정 안의 후보 비교에 사용한다. 실제 시간은 hardware, cache, 동시 부하에서 측정한다.

### 문제 4. index가 있는데 sequential scan

1,000,000 row 중 200,000 row가 여러 heap page에 흩어져 필요하다. index가 있어도 sequential scan을 고를 수 있는 이유는?

**풀이:** index traversal 뒤 많은 random heap page를 읽는 비용이 table 10,000 page를 순서대로 읽고 filter하는 비용보다 클 수 있다. covering 여부, clustering, cache와 cost parameter가 바뀌면 선택도 바뀐다.

### 문제 5. join order

A 순서의 intermediate가 20,000 row, B 순서가 800,000 row이며 최종은 둘 다 64,000이라고 추정한다. 다른 조건이 같으면 어느 쪽이 유리한가?

**풀이:** A가 hash·copy·spill할 intermediate가 작아 보이므로 cost가 낮을 가능성이 크다. 그러나 actual cardinality, required order, index와 parallelism을 포함해 전체 cost를 계산해야 한다. row 수 하나만으로 확정하지 않는다.

### 문제 6. estimation error

estimate 100, actual 100,000이면 몇 배 과소 추정인가?

**풀이:** actual/estimate = 100,000/100 = 1000배다. 이 node가 nested-loop outer라면 inner 실행 횟수도 1000배가 될 수 있다. stale stats, skew, parameter와 correlation을 조사한다.

### 문제 7. EXPLAIN ANALYZE DELETE

운영 table에 관측 목적으로 EXPLAIN ANALYZE DELETE를 실행해도 되는가?

**풀이:** 안전한 read-only가 아니다. DELETE가 실제 실행된다. rollback 가능성을 검토해도 sequence나 외부 함수 같은 비transactional effect가 남을 수 있다. 격리된 복제 데이터나 부작용 없는 query로 실험한다.

### 문제 8. loops 해석

inner node에 actual rows=3, loops=200이라고 표시되고 rows가 loop당 값인 형식이라면 총 생산 row는?

**풀이:** 3 × 200 = 600 row다. 도구 version과 출력 형식에서 rows가 loop당인지 확인해야 한다. 상위 node output과 같다고 단정하지 않는다.

## 공식 자료

- [PostgreSQL Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
- [PostgreSQL planner statistics](https://www.postgresql.org/docs/current/planner-stats.html)
- [PostgreSQL explicit joins and planner control](https://www.postgresql.org/docs/current/explicit-joins.html)
- [PostgreSQL source: optimizer](https://github.com/postgres/postgres/tree/master/src/backend/optimizer)
