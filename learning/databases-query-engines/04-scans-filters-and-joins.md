# 04. Scan, filter와 join

[이 책 목차](README.md) · [이전: B-tree와 LSM index](03-btree-and-lsm-indexes.md) · [다음: Query planning과 cost](05-query-planning-and-costs.md)

질의 실행기는 SQL 문장을 그대로 한 번에 계산하지 않는다. table이나 index에서 row를 만들고, 조건을 검사하고, 필요한 열을 고르고, 두 입력의 관련 row를 결합하는 작은 실행 연산자를 연결한다. 이 장은 여섯 주문과 네 고객을 사용해 각 연산자가 소유하는 상태, NULL 비교, 중복 key가 만드는 출력 수, 메모리가 부족할 때 임시 파일로 내려가는 과정을 모두 추적한다.

숫자와 page 비용은 교육 모형이다. SQL의 NULL과 outer join 의미는 지켜야 하지만, 특정 PostgreSQL 실행 계획이나 정확한 메모리 사용량을 보장하는 예는 아니다.

## 1. row를 만드는 scan

**table(테이블)**은 같은 열 정의를 가진 논리적 row 집합이다. 저장 장치에서는 여러 page와 record version으로 존재한다. **row(행)**는 query가 다루는 한 record의 논리적 값 묶음이다. 실행 중 row는 실행기 메모리의 tuple 또는 column batch 형태로 잠시 존재하고 상위 연산자가 소비하면 재사용되거나 해제된다.

**scan(스캔)**은 저장 객체에서 현재 transaction snapshot에 보이는 row 후보를 순서대로 생산하는 실행 연산자다. 연산자는 plan tree의 node로 존재하며 query 시작 때 cursor와 buffer 참조를 만들고 query가 끝나면 닫는다.

**sequential scan(순차 스캔)**은 table page를 정해진 순서로 읽고 각 record의 가시성을 검사한다. 모든 row가 필요하거나 table이 작거나 조건이 많은 row를 통과시키면 index를 오가는 것보다 유리할 수 있다.

**index scan(인덱스 스캔)**은 검색 조건으로 index entry 범위를 찾고 row 위치를 따라 table 후보를 읽는다. index 후보도 현재 snapshot에서 보이는지와 나머지 조건을 검사해야 한다. index가 존재한다는 사실만으로 index scan이 항상 싸지 않다.

**cursor(커서)**는 scan이 현재 어느 page와 entry까지 읽었는지 저장하는 실행 상태다. 다음 row 요청을 받으면 그 위치에서 계속한다. query 종료나 오류 시 수명이 끝난다.

## 2. filter, predicate, projection과 선택도

**predicate(조건식)**는 row가 query 조건을 만족하는지 계산하는 식이다. amount >= 50, country = 'KR'가 예다. **filter(필터)**는 입력 row마다 predicate를 계산해 TRUE인 row만 통과시키는 연산자다.

SQL 조건식은 TRUE와 FALSE뿐 아니라 **UNKNOWN(알 수 없음)**을 가질 수 있다. NULL은 값이 없거나 알려지지 않았음을 나타내는 표지이며 일반 비교에서 NULL = NULL도 UNKNOWN이다. WHERE는 TRUE인 row만 남기고 FALSE와 UNKNOWN을 제거한다.

**projection(투영)**은 필요한 열과 계산식만 출력한다. id와 amount만 필요한데 큰 text payload를 일찍 버리면 복사와 hash-table 메모리를 줄일 수 있다. 그러나 이후 join이나 ORDER BY에 필요한 열을 먼저 제거하면 query 의미를 계산할 수 없다.

**selectivity(선택도)**는 입력 중 predicate를 통과한 비율이다. 1000 row 중 100 row가 TRUE면 선택도는 100/1000 = 0.1, 즉 10%다. UNKNOWN을 TRUE에 포함하지 않는다. 선택도는 planner의 추정값일 수도 있고 실행 뒤 actual 비율일 수도 있으므로 둘을 구분한다.

filter를 storage나 scan 가까이 옮겨 불필요한 row를 일찍 줄이는 것을 **predicate pushdown(조건식 내려보내기)**이라고 한다. 의미가 같은 경우에만 안전하다. outer join의 ON과 WHERE처럼 위치가 NULL 확장 의미를 바꾸는 조건은 함부로 이동할 수 없다.

## 3. 이 장의 실제 입력

고객 C는 네 row다. id 2가 두 번 있으므로 join key가 unique하다고 가정하지 않는다.

| C row | id | name |
|---|---:|---|
| C1 | 1 | 가람 |
| C2 | 2 | 누리 |
| C3 | 2 | 누리-지점 |
| C4 | 3 | 다온 |

주문 O는 여섯 row다.

| O row | order_id | customer_id | amount |
|---|---:|---:|---:|
| O1 | 10 | 1 | 60 |
| O2 | 11 | 2 | 40 |
| O3 | 12 | 2 | 80 |
| O4 | 13 | 2 | 90 |
| O5 | 14 | 4 | 70 |
| O6 | 15 | NULL | 100 |

다음 query 의미를 계산한다.

~~~sql
SELECT C.id, C.name, O.order_id, O.amount
FROM C
LEFT JOIN O
  ON C.id = O.customer_id
 AND O.amount >= 50;
~~~

LEFT JOIN은 왼쪽 C row를 모두 보존한다. ON이 TRUE인 O row가 있으면 결합하고, 하나도 없으면 O 열을 NULL로 채운 row를 하나 만든다. ON이 FALSE이거나 UNKNOWN이면 match가 아니다.

## 4. 24개 후보와 정확한 여섯 출력

C 네 row와 O 여섯 row를 전부 비교하는 nested-loop 모형은 4 × 6 = 24 pair를 검사한다.

C1 id 1은 O1과 key가 같고 amount 60이라 TRUE다. C2 id 2는 O2, O3, O4와 key가 같다. O2 amount 40은 FALSE, O3 80과 O4 90은 TRUE다. C3도 id 2이므로 같은 두 qualifying 주문과 match한다. C4 id 3은 같은 key 주문이 없다. O6의 customer_id NULL과 어떤 C.id를 비교해도 UNKNOWN이라 match하지 않는다.

실제 출력은 다음 여섯 row다.

| 출력 순번 | C.id | C.name | O.order_id | O.amount | 생성 이유 |
|---:|---:|---|---:|---:|---|
| 1 | 1 | 가람 | 10 | 60 | C1×O1 ON TRUE |
| 2 | 2 | 누리 | 12 | 80 | C2×O3 ON TRUE |
| 3 | 2 | 누리 | 13 | 90 | C2×O4 ON TRUE |
| 4 | 2 | 누리-지점 | 12 | 80 | C3×O3 ON TRUE |
| 5 | 2 | 누리-지점 | 13 | 90 | C3×O4 ON TRUE |
| 6 | 3 | 다온 | NULL | NULL | C4 unmatched, NULL 확장 |

중복 key 때문에 id 2 그룹은 왼쪽 2 row × 오른쪽 qualifying 2 row = 4 row를 만든다. join 출력이 큰 입력의 row 수 이하라는 주장은 틀릴 수 있다.

O5 key 4는 오른쪽에만 있는 row이므로 LEFT JOIN 출력에 남지 않는다. FULL OUTER JOIN이라면 왼쪽 unmatched C4뿐 아니라 오른쪽 unmatched O2, O5, O6의 보존 규칙을 조건에 따라 계산해야 한다.

## 5. ON과 WHERE가 다른 반례

다음처럼 amount 조건을 WHERE로 옮겼다고 하자.

~~~sql
SELECT C.id, C.name, O.order_id, O.amount
FROM C
LEFT JOIN O ON C.id = O.customer_id
WHERE O.amount >= 50;
~~~

먼저 key equality만으로 LEFT JOIN한다. C4는 unmatched라 O 열이 NULL인 row가 생긴다. 그 뒤 WHERE O.amount >= 50은 이 NULL에 대해 UNKNOWN이며 row를 제거한다. O2 amount 40 row도 FALSE라 제거된다. 최종 출력은 위 표의 1~5번 다섯 row뿐이다.

첫 query에서는 amount < 50인 O2가 match하지 않아도 C2와 C3에는 다른 qualifying 주문이 있고, C4는 unmatched 보존된다. 둘째 query는 NULL 확장 C4를 WHERE에서 제거해 결과가 inner join처럼 좁아진다. pushdown은 단순히 빠른 위치로 옮기는 일이 아니라 SQL 의미가 동일하다는 증명이 필요하다.

## 6. iterator와 batch 실행

**iterator model(반복자 실행 모형)**에서는 상위 연산자가 child에게 next row를 요청한다. root projection이 join에 요청하고, join이 filter와 scan에 요청하는 식이다. 각 node는 다음 호출까지 cursor, hash table, matched flag 같은 상태를 유지한다.

**batch 또는 vectorized execution(묶음 실행)**은 row 하나 대신 여러 row의 column 값을 한 묶음으로 전달한다. 함수 호출과 분기 오버헤드를 줄이고 CPU의 SIMD 연산을 사용하기 쉽다. batch가 1024 row라고 해도 마지막 batch는 더 작을 수 있고, NULL bitmap과 selection vector를 함께 관리한다.

**selection vector**는 batch 안에서 predicate가 TRUE인 row 위치만 나열하는 배열이다. 원본 column을 매번 복사하지 않고 [0,2,5]처럼 살아남은 index를 다음 연산자에 전달할 수 있다.

row와 batch 방식은 같은 SQL 결과를 내야 한다. 내부 상태의 형태와 호출 횟수가 다를 뿐 NULL, 중복, outer join 의미를 바꾸지 않는다.

## 7. nested-loop join의 모든 상태

**nested-loop join(중첩 반복 조인)**은 바깥 입력 row 하나를 잡고 안쪽 입력을 탐색해 predicate를 검사한다. index 없는 full nested loop에서는 C row마다 O scan cursor를 처음으로 되돌린다.

C2를 처리하는 상태를 보자.

| inner 위치 | O key·amount | key 비교 | amount 비교 | 행동 |
|---:|---|---|---|---|
| O1 | 1,60 | FALSE | 검사 생략 가능 | 다음 |
| O2 | 2,40 | TRUE | FALSE | 다음 |
| O3 | 2,80 | TRUE | TRUE | 출력 C2×O3 |
| O4 | 2,90 | TRUE | TRUE | 출력 C2×O4 |
| O5 | 4,70 | FALSE | 생략 | 다음 |
| O6 | NULL,100 | UNKNOWN | TRUE | match 아님 |

outer row마다 matched flag를 FALSE로 시작하고 하나라도 ON TRUE pair를 출력하면 TRUE로 바꾼다. inner scan이 끝났는데 flag가 FALSE면 LEFT JOIN은 NULL 확장 row 하나를 출력한다. C4가 그 경우다.

O.customer_id B-tree index가 있다면 C.id로 후보 O row만 찾는 index nested loop를 쓸 수 있다. C1은 key1, C2/C3은 key2, C4는 key3 범위를 조회한다. 그러나 index root·leaf와 table row 접근, duplicate 후보 filter 비용이 있다. small inner table이나 많은 match에서는 sequential inner scan이 더 쌀 수 있다.

## 8. hash join의 build와 probe 상태

**hash function(해시 함수)**은 key를 정수 bucket 번호로 바꾸는 계산이다. 같은 equality key는 같은 bucket으로 가야 하지만 다른 key도 같은 bucket에 충돌할 수 있어 실제 equality를 다시 검사한다.

**hash join**은 한 입력의 key와 payload를 메모리 hash table에 넣는 build 단계와, 다른 입력 key로 bucket을 찾는 probe 단계로 나뉜다. 이 예에서는 C를 build side로 사용하고 hash(id) mod 4를 쓴다고 하자.

build 뒤 상태:

| bucket | entry |
|---:|---|
| 0 | 비어 있음 |
| 1 | C1:(1,가람) |
| 2 | C2:(2,누리), C3:(2,누리-지점) |
| 3 | C4:(3,다온) |

probe를 순서대로 수행한다.

1. O1 key1은 bucket1 C1을 찾아 amount 60도 TRUE, 출력 1개.
2. O2 key2는 bucket2의 C2·C3과 equality는 TRUE지만 amount 40이 FALSE, 출력 없음.
3. O3 key2 amount80은 C2·C3 두 entry와 결합, 출력 2개.
4. O4 key2 amount90도 출력 2개.
5. O5 key4의 bucket0에는 후보가 없어 출력 없음.
6. O6 NULL은 일반 equality hash match 대상이 아니어서 출력 없음.
7. probe 종료 뒤 build entry의 matched bit를 본다. C4만 false라 NULL 확장 1개를 출력한다.

총 1+2+2+1 = 6 row다. C2와 C3을 한 entry로 합치면 중복 의미를 잃는다. hash table은 distinct key 집합이 아니라 각 build row를 보존해야 한다.

hash join은 equality predicate에 자연스럽다. a.x < b.x 같은 일반 부등 조건은 동일 key bucket 조회만으로 모든 pair를 찾지 못한다. equality key로 후보를 찾은 뒤 추가 residual predicate를 적용하는 경우는 가능하다.

~~~mermaid
flowchart LR
 S1[C scan 4행] --> B[hash build 4 entry]
 S2[O scan 6행] --> F[amount와 NULL 판정]
 F --> P[probe 6 row]
 B --> P
 P --> J[match 5행과 unmatched C4]
 J --> X[projection 6행]
~~~

## 9. sort-merge join과 중복 그룹

**sort-merge join(정렬 병합 조인)**은 두 입력을 join key 순서로 준비하고 현재 key pointer를 함께 전진한다. 이미 index order나 앞선 sort가 있으면 정렬 비용을 줄일 수 있다.

정렬된 C key는 [1:C1, 2:C2, 2:C3, 3:C4]다. O의 non-NULL key는 [1:O1, 2:O2, 2:O3, 2:O4, 4:O5]이고 O6 NULL은 일반 equality match하지 않는다.

- key1 그룹: 1×1 pair, amount filter 뒤 1 output
- key2 그룹: 왼쪽 2×오른쪽 3 = 6 pair를 고려하고 amount 40인 O2 두 pair를 제거해 4 output
- key3: 오른쪽 same key 없음, LEFT JOIN NULL 확장 1 output
- key4: 왼쪽 same key 없음, LEFT JOIN이므로 버림

merge join이 key2에서 pointer를 한 번씩만 전진해 C2×O2, C3×O3 같은 일부만 만들면 틀린다. duplicate group의 Cartesian product를 만들거나 같은 의미의 상태를 유지해야 한다.

NULL이 sort order의 앞이나 뒤에 배치될 수 있어도 equality ON에서 NULL = NULL은 UNKNOWN이다. 정렬 위치와 SQL 비교 진릿값을 혼동하지 않는다.

## 10. spill이 생기는 이유와 partition trace

hash table과 sort run은 query 실행기 메모리를 사용한다. **memory budget(메모리 예산)**은 한 연산자가 메모리에 둘 수 있는 양의 정책 경계다. build input이 예산을 넘으면 일부를 **spill(임시 저장 장치로 내리기)**할 수 있다.

hash join에서 partitioned spill을 단순화해 보자. memory에는 두 C entry만 들어가고 C는 네 row다.

1. build row를 hash의 상위 bit로 partition 0과 1에 나눈다.
2. memory에 처리 가능한 partition을 남기고 나머지 build row를 temporary file에 쓴다.
3. probe O row도 같은 partition 함수로 나누며, 내려간 build partition에 해당하는 O row를 probe temp file에 쓴다.
4. memory partition의 join을 끝낸다.
5. spilled build partition을 다시 읽어 hash table을 만든다.
6. 대응 probe partition을 다시 읽어 join한다.
7. outer join의 matched 상태를 partition별로 보존하고 unmatched build row를 마지막에 출력한다.
8. query 종료 후 temporary files를 삭제한다.

spill은 올바른 partition과 NULL·matched 상태를 유지하면 결과 오류가 아니다. 그러나 temp write와 read, 추가 CPU, 장치 경쟁으로 latency가 늘어난다. partition 하나가 지나치게 크면 **skew(편향)** 때문에 다시 partition하거나 여러 pass가 필요할 수 있다. key2가 대부분인 입력은 단순 hash partition에도 같은 큰 group이 몰릴 수 있다.

sort도 memory에서 다 정렬하지 못하면 작은 **run(정렬된 부분 파일)**을 여러 개 만들고 나중에 merge한다. 입력 byte, row width, 비교 key, temp storage 대역폭이 비용을 좌우한다.

## 11. join 종류와 보존 규칙

- **INNER JOIN**: ON TRUE pair만 출력한다.
- **LEFT OUTER JOIN**: TRUE pair와 match가 없는 왼쪽 row의 NULL 확장을 출력한다.
- **RIGHT OUTER JOIN**: 반대로 오른쪽을 보존한다.
- **FULL OUTER JOIN**: 양쪽 unmatched row를 각각 NULL 확장한다.
- **SEMI JOIN 의미**: 왼쪽 row에 match가 하나라도 있으면 왼쪽 row를 한 번 출력한다.
- **ANTI JOIN 의미**: match가 없는 왼쪽 row를 출력한다.

EXISTS를 일반 inner join으로 바꾸면 오른쪽 중복 때문에 왼쪽 row가 여러 번 나올 수 있다. semi join은 match 존재 여부만 필요하므로 첫 match 뒤 멈출 수 있다. NOT IN은 NULL이 있을 때 UNKNOWN 규칙 때문에 NOT EXISTS와 다르게 동작할 수 있다. 변환은 NULL 가능성과 중복 의미를 증명해야 한다.

## 12. selectivity와 연산 위치의 비용

O.amount >= 50은 여섯 O row 중 O1, O3, O4, O5, O6의 다섯 row에서 TRUE이므로 단독 선택도는 5/6이다. 그러나 join key와 함께 보면 O5는 왼쪽 key가 없고 O6은 NULL이라 output을 만들지 않는다. predicate 선택도 하나만으로 join output을 정확히 계산할 수 없다.

중복 분포가 중요하다. id 2가 왼쪽 두 번, 오른쪽 qualifying 두 번 나와 4 row가 된다. distinct count만 알고 각 key 빈도를 모르면 output cardinality를 크게 틀릴 수 있다.

filter를 join 전에 적용해 O2를 제거하면 hash probe가 여섯 번에서 다섯 번으로 줄 수 있다. O6는 amount filter를 통과하지만 equality match는 여전히 없다. outer join의 preserved side와 ON/WHERE 의미를 지키는 범위에서만 push한다.

projection으로 name이 최종 출력에 필요하다면 build payload에 유지해야 한다. amount와 order_id도 출력에 필요하다. 사용하지 않는 큰 memo 열이 있었다면 scan 직후 버려 hash와 spill byte를 줄일 수 있다.

## 13. correctness와 performance 관측

각 node에서 다음을 기록하면 문제를 좁힐 수 있다.

- input row와 output row
- predicate TRUE/FALSE/UNKNOWN 수
- build row와 distinct key 수
- probe row와 candidate pair 수
- matched와 unmatched row 수
- peak memory와 spill file byte
- page read와 buffer hit
- sort run 수와 merge pass 수
- 실제 실행 시간과 반복 횟수

24 pair를 검사해 6 row를 출력한 nested loop와, 4 build+6 probe로 같은 6 row를 만든 hash join은 결과가 같아야 한다. 내부 연산 수를 단순 비교할 때 hash 계산, bucket collision, row materialization 비용도 포함한다.

cache가 warm한 실행과 cold한 실행을 섞지 않는다. spill storage가 다른 query와 경쟁하면 같은 계획도 tail latency가 달라진다. algorithm 이름만으로 절대 속도를 정하지 않는다.

## 14. 완전 풀이 문제

### 문제 1. full nested loop

왼쪽 1000 row, 오른쪽 100 row를 index 없이 전부 비교하면 pair 수는?

**풀이:** 각 왼쪽 row마다 오른쪽 100 row를 보므로 1000 × 100 = 100,000 pair다. output row 수는 predicate와 중복에 따라 이보다 작거나 클 수 없지만 비교 수와 같지 않다.

### 문제 2. 여섯 출력 검증

이 장 입력에서 id 2 관련 output이 네 row인 이유는?

**풀이:** 왼쪽 C에 id 2가 C2와 C3 두 row 있고, 오른쪽에서 amount 조건을 만족하는 id 2 주문이 O3와 O4 두 row다. inner equality group은 2 × 2 = 4 pair를 출력한다. O2는 amount 40이라 ON FALSE다.

### 문제 3. ON을 WHERE로 이동

LEFT JOIN의 O.amount >= 50을 ON에서 WHERE로 옮기면 C4는 남는가?

**풀이:** 남지 않는다. key join 뒤 C4는 O 열이 NULL인 확장 row가 되며 WHERE NULL >= 50은 UNKNOWN이다. WHERE는 TRUE만 남기므로 C4가 제거된다. 원래 ON 조건에서는 unmatched C4를 LEFT JOIN이 보존한다.

### 문제 4. hash collision

hash(1)과 hash(5)가 같은 bucket이면 두 key가 join되는가?

**풀이:** 아니다. bucket은 후보를 좁힐 뿐이다. candidate entry의 실제 equality key를 다시 비교한다. 이를 생략하면 hash collision이 잘못된 output을 만든다.

### 문제 5. duplicate merge

정렬 join에서 왼쪽 key7이 3 row, 오른쪽 key7이 4 row면 key7 output 후보는 몇 개인가?

**풀이:** 추가 predicate가 모두 TRUE라면 3 × 4 = 12 row다. 양쪽 pointer를 한 번씩만 전진하면 중복 조합을 놓친다. group 경계와 모든 조합 상태가 필요하다.

### 문제 6. build memory

build 100,000 row이고 row payload가 64 B면 payload만 얼마인가?

**풀이:** 100,000 × 64 = 6,400,000 B, 즉 십진 6.4 MB다. bucket array, pointer, allocator 정렬, hash 값과 matched bit가 추가되므로 실제 memory는 더 크다.

### 문제 7. spill correctness

hash join이 spill하면 결과가 바뀌어도 되는가?

**풀이:** 안 된다. 같은 partition 함수를 build와 probe에 사용하고, 모든 partition을 다시 읽으며, outer join matched 상태와 NULL 규칙을 보존해야 한다. 결과는 같고 temp I/O와 latency만 추가되어야 한다.

### 문제 8. NULL key

O6 customer_id NULL과 C의 id가 NULL인 row가 있어도 일반 C.id = O.customer_id에서 match하는가?

**풀이:** 일반 equality에서 NULL = NULL은 UNKNOWN이므로 match하지 않는다. NULL-safe comparison을 명시한 다른 연산자는 의미가 다를 수 있으므로 SQL 표현을 확인해야 한다.

## 공식 자료

- [PostgreSQL table expressions and joins](https://www.postgresql.org/docs/current/queries-table-expressions.html)
- [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
- [PostgreSQL executor source](https://github.com/postgres/postgres/tree/master/src/backend/executor)
