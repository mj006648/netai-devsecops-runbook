# 14. 실험을 설계하고 근거를 읽는 법

[이전: 로컬 실행 모델](13-local-models.md) · [목차](README.md) · [다음: 종합 문제와 용어](15-exercises-glossary-and-sources.md)

데이터베이스 실험은 명령을 한 번 실행해 나온 ms를 적는 일이 아니다. 같은 정답을 계산했는지 먼저 확인하고, 바꾼 조건 하나와 고정한 조건을 분리하며, 계획·메모리·I/O·동시성이 시간을 어떻게 만들었는지 추적해야 한다. 이 장은 상관된 두 열의 통계가 조인 질의의 추정과 실행에 미치는 영향을 연구하는 하나의 완결된 예를 설계한다.

아래 20회 시간은 계산과 해석 방법을 설명하려고 만든 **가상 교육 자료** 다. 실제 PostgreSQL을 실행해 측정한 값이 아니며 논문이나 제품 성능 주장에 사용할 수 없다. 실제 연구에서는 같은 설계를 실행하고 원시 계획과 측정 파일을 공개해야 한다.

## 1. 질문을 검증 가능한 문장으로 바꾼다

“다변량 통계가 좋은가?”는 좋고 나쁨의 기준과 데이터 조건이 없다. 다음처럼 쓴다.

> region과 channel이 강하게 상관된 orders 데이터에서, 두 열의 다변량 통계를 수집하면 기본 열별 통계만 쓴 기준군보다 필터 행 수 추정 오차가 줄고, 동일 결과를 내는 집계 조인의 warm-cache 중앙 실행 시간이 15% 이상 줄어드는가?

**가설(hypothesis)** 은 관측 전에 세운 검증 가능한 예상이다. 처리군 B의 필터 estimate error가 2배 이내이고, 기준군 A보다 paired median 실행 시간이 15% 이상 짧을 것이라고 정한다. **귀무가설(null hypothesis)** 은 차이가 없거나 B가 더 낫지 않다는 출발 주장이다.

**기각 기준** 을 결과를 본 뒤 정하면 원하는 결론에 맞출 수 있다. 이 실험은 다음을 미리 정한다.

1. 모든 A/B 실행의 결과 행과 checksum이 같아야 한다. 하나라도 다르면 성능 비교를 중단한다.
2. B의 핵심 필터 추정 오차가 2배 이하여야 한다.
3. B의 paired median 지연 감소가 15% 이상이어야 한다.
4. 10개 pair 중 B가 더 빠른 pair가 9개 이상이어야 한다.
5. 실행 plan과 spill 여부가 기록되어 차이의 기작을 설명할 수 있어야 한다.

이 조건을 만족하지 못하면 “이 설계에서 가설을 지지하지 못했다”고 쓴다. 제품 전체에 효과가 없다는 뜻은 아니다.

## 2. 독립·종속·통제·교란 변수

**독립 변수** 는 연구자가 의도적으로 바꾸는 조건이다. A는 orders의 region, channel에 개별 열 통계만 있는 상태다. B는 같은 데이터에서 두 열의 dependencies와 MCV를 포함한 extended statistics를 만들고 ANALYZE한 상태다.

**종속 변수** 는 변화의 결과로 측정한다. 필터 node의 estimated rows와 actual rows, 오차 배수, physical join operator, planning time, execution time, shared hit/read blocks, temp blocks, hash batches와 memory, 결과 checksum을 기록한다.

**통제 변수** 는 A/B에서 같게 유지한다. PostgreSQL major/minor와 설정, 데이터 파일과 행 순서, schema와 index, SQL text와 parameter, 클라이언트, CPU 고정 정책, memory 한도, storage, 동시 세션 수, cache 상태, 반복 순서의 균형을 고정한다.

**교란 변수** 는 독립 변수 외에 결과를 바꿀 수 있는 조건이다. autovacuum, checkpoint, 통계 sampling, 다른 tenant의 I/O, OS page cache, thermal throttling, prepared statement의 generic/custom plan, 네트워크, JIT compilation이 있다. 제거할 수 없다면 각 반복에 관측값을 남기고 분석에서 분리한다.

## 3. 실제 데이터 객체와 분포

orders는 1,000,000행이며 order_id, customer_id, region, channel, amount를 가진다고 하자. customers는 100,000행이며 customer_id와 tier가 있다. customer_id에는 유일 인덱스가 있고 조인은 두 테이블의 customer_id 동등 조건이다.

orders의 교육용 분포는 다음과 같다.

| 조건 | 행 수 | 전체 비율 |
|---|---:|---:|
| region=KR | 200,000 | 20% |
| channel=mobile | 250,000 | 25% |
| 둘 다 만족 | 180,000 | 18% |

열을 서로 독립이라고 가정하면 결합 선택도는 0.20×0.25=0.05이고 50,000행으로 추정한다. 실제 교집합 180,000행보다 3.6배 적다. region과 channel의 값 조합이 강하게 상관되어 있기 때문이다.

**분포(distribution)** 는 단순 행 수가 아니라 값이 얼마나 자주, 어떤 조합으로 나타나는지를 뜻한다. 같은 100만 행이어도 KR-mobile이 5만인지 18만인지에 따라 조인 입력 크기가 달라진다. 데이터 생성 절차는 각 조합의 정확한 행 수와 random seed를 보관하고, A와 B가 같은 물리 데이터를 사용하게 한다.

## 4. 연구할 SQL과 결과 계약

~~~sql
SELECT c.tier, COUNT(*) AS order_count, SUM(o.amount) AS total_amount
FROM orders AS o
JOIN customers AS c
  ON c.customer_id = o.customer_id
WHERE o.region = 'KR'
  AND o.channel = 'mobile'
GROUP BY c.tier
ORDER BY c.tier;
~~~

결과 계약은 tier별 order_count와 total_amount 전체 행 집합이다. A와 B는 통계만 다르고 SQL 의미와 데이터는 같으므로 결과가 완전히 같아야 한다. 각 실행에서 정렬된 결과를 안정적인 직렬화로 바꾸고 cryptographic checksum을 계산한다고 가정한다. checksum만 저장하지 않고 결과 행 수도 함께 저장해 serialization bug를 찾는다.

EXPLAIN ANALYZE는 SELECT를 실제 실행하지만 일반 클라이언트로 결과를 전송하는 비용과 같지 않다. PostgreSQL 18의 SERIALIZE 옵션은 출력 변환 비용을 별도로 계측할 수 있으나 네트워크 전송은 포함하지 않는다. 연구 질문이 엔진 내부 plan이라면 네트워크를 제외하고, 사용자 end-to-end라면 별도 클라이언트 시간도 재되 두 시간을 섞지 않는다.

## 5. 기준군 A와 처리군 B

A에서는 일반 ANALYZE로 각 열의 빈도와 histogram을 수집하되 region-channel 다변량 통계 객체가 없는지 확인한다.

B에서는 같은 table에 다음 개념의 통계를 추가한다.

~~~sql
CREATE STATISTICS orders_region_channel_stats
  (dependencies, mcv)
ON region, channel
FROM orders;

ANALYZE orders;
~~~

**dependencies** 는 열 값 사이의 함수적 의존 경향을 요약한다. **MCV(most-common values) list** 는 자주 나타나는 열 값 조합과 실제 빈도를 기록한다. PostgreSQL 공식 예제는 상관된 두 조건을 독립으로 곱해 과소 추정하는 문제와 다변량 통계가 그 추정을 고치는 사례를 보여 준다.

ANALYZE는 sample을 사용할 수 있어 같은 데이터에서도 통계가 조금 달라질 수 있다. A와 B 비교에서 ANALYZE 횟수와 statistics target을 기록한다. 더 엄격한 연구라면 여러 독립 통계 생성 seed 또는 반복 구축을 별도 block으로 다룬다. 여기서는 하나의 고정 통계 snapshot이라는 제한을 명시한다.

## 6. 비용과 시간을 구분한다

EXPLAIN의 cost는 planner가 후보 plan을 비교하는 상대 단위다. startup cost는 첫 행을 내기 전 작업량, total cost는 모든 행을 내는 추정 작업량이다. cost 500은 500ms 보장이 아니다. estimated rows도 계획 시점 통계로 계산한 예상이다.

EXPLAIN ANALYZE의 actual rows와 execution time은 실제 실행 계측이다. node의 loops가 10이면 표시된 per-loop 값의 해석을 확인해야 한다. 상위 node의 buffer 수는 자식 사용량을 포함할 수 있으므로 단순 합계로 중복 계산하지 않는다. TIMING ON은 clock 호출 overhead를 늘릴 수 있어 행 수와 buffer 중심 연구에서는 TIMING OFF와 전체 실행 시간을 사용할 수 있다.

각 반복의 한 row에는 다음을 보관한다.

| 필드 | 뜻 |
|---|---|
| run_id, pair_id, condition | 반복 신원과 A/B |
| dataset_hash, stats_hash | 동일 입력과 통계 상태 확인 |
| query_id, parameters | 동일 SQL 확인 |
| plan_hash와 plan JSON | 선택한 연산자와 추정치 |
| estimate, actual | 첫 오차 node의 행 수 |
| shared hit/read, temp read/write | buffer와 spill |
| planning_ms, execution_ms | 계획과 실행 분리 |
| result_rows, checksum | 정확성 gate |
| cache_mode, concurrency | 실행 환경 |
| background events | checkpoint 등 이상 원인 |

## 7. cache를 실제 위치별로 정의한다

“cold”라는 한 단어로는 부족하다. PostgreSQL shared buffers, 운영체제 page cache, storage controller cache, CPU cache는 위치와 관리 주체가 다르다. 서버 재시작은 shared buffers를 비울 수 있지만 OS cache를 반드시 비우지 않는다. OS cache 제거는 다른 workload와 시스템 전체에 영향을 주며 격리 시험 환경에서만 한다.

이 연구의 주 분석은 **warm-cache** 로 고정한다. 측정 전 동일 query를 각 조건에서 충분히 실행하고, EXPLAIN buffer 지표에서 물리 read가 안정됐는지 확인한다. warmup 값은 20회 측정에 포함하지 않는다. A와 B의 실행 순서를 A1,B1,B2,A2처럼 균형 있게 교차해 시간 경과와 온도 상승이 한 조건에 몰리지 않게 한다.

cold 결과가 필요하면 별도 실험으로 설계한다. 어떤 계층을 비웠는지, object와 DB를 재시작했는지, 첫 metadata read를 포함하는지 명시한다. cold와 warm을 한 평균에 넣지 않는다.

## 8. 동시성 조건

이 실험의 첫 단계는 concurrency=1이다. 한 client만 실행해 plan과 통계 변화의 직접 효과를 본다. 백그라운드 autovacuum과 수동 checkpoint는 측정 창에서 통제하거나 발생 시각을 기록한다. CPU core와 memory pressure도 동일하게 유지한다.

그 뒤 부하 실험은 별도로 concurrency 8, 32를 둔다. 이때 종속 변수는 query 하나의 중앙값뿐 아니라 throughput, p95/p99 latency, lock wait, I/O queue, spill 총량이 된다. 동시 사용자 수가 늘면 같은 plan도 cache 경쟁과 memory grant 때문에 달라질 수 있다. 단일 사용자 결과를 다중 사용자 SLA로 확대하지 않는다.

## 9. 실행 계획을 실험 상태로 취급한다

A와 B의 plan hash가 다르면 어떤 node가 바뀌었는지 읽는다. 예를 들어 A가 필터 결과를 50,000으로 보고 nested loop를 선택했지만 actual 180,000행 때문에 inner index lookup을 많이 반복할 수 있다. B가 180,000에 가까운 추정으로 hash join을 선택한다면 실행 시간 차이를 “통계 객체 자체가 빨라서”가 아니라 “카디널리티 추정이 join 선택을 바꾸어서”라고 연결할 수 있다.

반대로 A와 B가 같은 hash join plan을 고르고 estimate만 달라졌다면 실행 시간 차이가 크지 않을 수 있다. 이는 실험 실패가 아니라 기작상 자연스러운 결과다. statistics가 plan을 바꿀 만큼 후보 cost 경계에 있지 않았다는 뜻이다. plan을 억지로 원하는 방향으로 만들려고 random_page_cost나 enable_nestloop까지 함께 바꾸면 독립 변수가 둘이 된다.

prepared statement를 사용하면 parameter 값별 custom plan과 재사용 generic plan이 다를 수 있다. 연구는 매번 literal SQL을 새 session에서 plan할지, PREPARE/EXECUTE의 generic 전환을 포함할지 고정한다.

## 10. 20회 가상 측정 자료

아래 값은 warm-cache, concurrency=1, 동일 결과 checksum, A의 plan=NESTED_LOOP, B의 plan=HASH_JOIN이라고 **가정해 만든 교육용 자료** 다. 실제 실행 결과가 아니다. pair는 가까운 시간에 A/B를 교차 실행한 비교 단위다.

| pair | A ms | B ms | A-B ms | checksum 동일 |
|---:|---:|---:|---:|---|
| 1 | 520 | 420 | 100 | 예 |
| 2 | 510 | 410 | 100 | 예 |
| 3 | 535 | 430 | 105 | 예 |
| 4 | 500 | 405 | 95 | 예 |
| 5 | 560 | 440 | 120 | 예 |
| 6 | 515 | 415 | 100 | 예 |
| 7 | 505 | 425 | 80 | 예 |
| 8 | 545 | 435 | 110 | 예 |
| 9 | 530 | 400 | 130 | 예 |
| 10 | 600 | 455 | 145 | 예 |

총 실행은 A 10회와 B 10회로 20회다. A 정렬값은 500,505,510,515,520,530,535,545,560,600이고 중앙값은 (520+530)/2=525ms다. B 정렬값은 400,405,410,415,420,425,430,435,440,455이고 중앙값은 422.5ms다.

paired median 차이는 각 pair 차이를 정렬한 80,95,100,100,100,105,110,120,130,145의 가운데 두 값 평균 102.5ms다. 중앙값 기준 상대 감소는 (525-422.5)/525≈19.5%다. A의 MAD는 중앙값으로부터 절대 편차의 중앙값 17.5ms, B의 MAD는 12.5ms다. MAD는 극단값에 평균·표준편차보다 덜 흔들리는 분산 요약이다.

10개 pair 모두 B가 더 빠르다. 차이가 날 확률이 양쪽에 1/2이고 tie가 없다는 단순 귀무가설에서 exact two-sided sign test의 확률은 2×(1/2)^10≈0.00195다. 그러나 이 p값도 가상 자료의 산수일 뿐 실제 효과의 증거가 아니다. 독립 반복, 순서 randomization, 환경 안정성이 깨지면 해석도 깨진다.

## 11. estimate와 plan의 가상 기록

A가 50,000행으로 추정하고 actual은 180,000이면 underestimate factor는 180,000/50,000=3.6이다. B가 170,000으로 추정하면 actual/estimate≈1.06이다. 사전 기준 2배 이내를 만족한다.

| 조건 | estimated rows | actual rows | error factor | join |
|---|---:|---:|---:|---|
| A 기본 통계 | 50,000 | 180,000 | 3.60 | nested loop 가정 |
| B 다변량 통계 | 170,000 | 180,000 | 1.06 | hash join 가정 |

실제 계획이 꼭 이렇게 나온다는 보장은 없다. customers index와 cache, random_page_cost, work_mem, row width에 따라 A도 hash를 고를 수 있다. 이 표는 논리 사슬을 연습하는 가상 상태다. 실제 보고서에는 plan JSON을 첨부해야 한다.

## 12. 정확성 gate

성능 분석 전에 각 실행의 tier별 count와 sum checksum을 비교한다. 한 pair라도 다르면 다음을 조사한다.

- A와 B가 같은 MVCC snapshot 또는 데이터 시점을 읽었는가?
- concurrent writer가 있었는가?
- SQL parameter와 NULL 처리, collation이 같은가?
- timeout이나 partial result가 있었는가?
- 결과 정렬과 checksum serialization이 결정적인가?

다변량 통계는 query 결과를 바꾸면 안 된다. 계획만 바꾼다. 결과 차이를 “빠른 approximate 결과”로 받아들이면 연구 질문을 바꾼 것이다.

## 13. 통계적 결론과 실용적 결론

p값이 작아도 1ms 차이가 업무에 의미 없을 수 있고, 20% 차이가 있어도 변동이 커 confidence interval이 넓을 수 있다. **통계적 유의성** 은 우연만으로 이런 차이를 보기 어렵다는 모형 아래 판단이고, **효과 크기** 는 실제로 얼마나 달라졌는지다. SLA, CPU 비용, plan 안정성은 실용적 의미를 결정한다.

paired design은 같은 시간대의 A/B를 묶어 공통 환경 변동을 일부 줄인다. 실제 연구에서는 paired difference의 bootstrap confidence interval이나 사전 선택한 비모수 검정을 사용하고 분석 코드를 공개한다. 여러 query와 지표를 동시에 시험하면 우연한 유의 결과가 늘므로 primary metric을 미리 하나 정하고 나머지는 탐색 결과로 표시한다.

가상 자료는 사전 기준을 모두 통과한다. 하지만 쓸 수 있는 문장은 “이 가상 예제에서는 다변량 통계 조건의 median이 19.5% 낮고 10/10 pair가 개선됐다”까지다. “PostgreSQL은 항상 19.5% 빨라진다”가 아니다.

## 14. 결과가 가설을 기각하는 반례

B 추정이 정확해도 physical plan이 같고 median이 3%만 줄면 15% 기준을 만족하지 못한다. B가 더 빠르지만 checksum이 다르면 정확성 gate에서 중단한다. median은 20% 줄었지만 10 pair 중 5개만 개선되고 나머지는 긴 tail이면 안정성 기준을 충족하지 못한다. planning time이 통계 처리 때문에 100ms 늘고 execution은 50ms 줄어 짧은 query의 end-to-end가 나빠질 수도 있다.

따라서 “통계가 정확해졌다”, “plan이 바뀌었다”, “엔진 시간이 줄었다”, “사용자 지연이 줄었다”는 네 개의 별도 주장이다. 각 화살표에 관측 근거가 있어야 한다.

## 15. WAL·MVCC 연구로 같은 원칙 옮기기

WAL 실험에서는 page value=50,pageLSN=10, update WAL LSN=11,value=60, commit LSN=12 같은 교육 시간표를 쓸 수 있다. 독립 변수는 crash 경계, 종속 변수는 recovery 뒤 page와 reader 결과다. 생성된 WAL, durable WAL, disk page, MVCC 가시성을 분리한다. 정상 shutdown만으로 crash recovery를 주장하지 않는다.

동시성 실험에서는 세션 A/B의 SQL만 적지 않고 statement 시작, snapshot 획득, lock 획득, commit을 barrier로 동기화한다. 예를 들어 write skew 재현은 두 트랜잭션이 모두 옛 상태를 읽은 뒤 각자 쓰도록 read barrier가 필요하다. scheduler 우연에 맡긴 실험은 anomaly가 나오지 않았다고 보장을 증명할 수 없다.

## 16. 분산·Spark 실험으로 옮기기

복제 실험은 primary generated LSN, replica write/flush/replay LSN과 client ACK를 각각 기록한다. failover 시간만 재고 성공 ACK 데이터가 남았는지 확인하지 않으면 RTO만 측정하고 RPO를 놓친다.

Spark/Iceberg 실험은 input snapshot ID와 file set, plan, task 수, bytes read, shuffle, spill, 결과 checksum을 기록한다. cold object-store read와 warm executor cache를 섞지 않는다. optimizer가 manifest pruning을 늘렸다고 해도 결과 filter 정확성과 delete 적용을 확인해야 한다. executor 수를 늘리며 file size와 snapshot까지 바꾸면 독립 변수가 여러 개가 된다.

## 17. 논문과 preprint를 읽는 질문

연구 결과를 읽을 때 제품 이름보다 실험 계약을 먼저 본다.

1. baseline이 최신이며 충분히 튜닝됐는가?
2. 어떤 query와 데이터 분포를 썼는가?
3. exact answer를 요구하는가, approximation을 허용하는가?
4. cold/warm, concurrency, hardware와 version이 명시됐는가?
5. planning과 execution, index build와 query를 분리했는가?
6. 실패·unsupported workload를 평균에서 숨기지 않았는가?
7. 결과 동일성, recall, filter correctness를 각각 검증했는가?
8. artifact로 재현할 수 있는가?

예를 들어 ANN의 recall@10=0.9는 관련 이웃 10개 중 평균 9개를 찾았다는 지표일 수 있다. SQL WHERE 조건을 90%만 지켜도 된다는 뜻이 아니다. filtered vector 검색은 filter correctness와 recall을 별도로 보고해야 한다. optimizer service 연구도 planning time 우위와 선택된 plan의 execution time을 합쳐 end-to-end로 본다.

## 18. 완전 풀이 문제

### 문제 1. 추정 오차

estimate=100, actual=10,000이다.

**풀이:** actual/estimate=100배 과소 추정이다. 최상위 node가 아니라 이 오차가 처음 나타난 아래 filter의 column 통계와 상관을 조사한다.

### 문제 2. tail이 있는 시간

[90,91,92,93,94,95,96,97,150,300]ms다.

**풀이:** 합은 1,198ms, 평균 119.8ms다. 중앙값은 정렬 5·6번째 94와95의 평균 94.5ms다. 평균 하나는 긴 두 값을 숨기므로 원시값과 tail 원인을 보관한다.

### 문제 3. checksum 불일치

B가 30% 빠르지만 결과 checksum이 A와 다르다.

**풀이:** 정확성 gate 실패다. 성능 우승자를 정하지 않고 snapshot, SQL, NULL, serialization과 오류를 조사한다.

### 문제 4. cost 120

EXPLAIN total cost가 120이다.

**풀이:** planner의 상대 cost 단위이지 120ms 보장이 아니다. 실제 실행에는 ANALYZE 계측과 반복 분포가 필요하고 계측 overhead도 기록한다.

### 문제 5. cold와 warm

첫 실행 120ms, 다음 네 실행 84,82,83,81ms다.

**풀이:** 첫 값을 조용히 제거하지 않는다. cold 1회와 warm 4회로 분리하며 warm 평균과 중앙은 모두 82.5ms다. 무엇이 warm해졌는지는 buffer 지표로 확인한다.

### 문제 6. 20회 가상 자료

A median 525, B median 422.5다.

**풀이:** 상대 감소는 102.5/525≈19.5%다. 15% 기준을 넘지만 가상 자료이므로 실제 제품 주장으로 쓰지 않는다.

### 문제 7. estimate가 좋아졌지만 plan 동일

**풀이:** 통계 정확성 가설은 지지할 수 있지만 실행 시간 개선 가설은 별도다. 후보 plan cost 순서가 바뀌지 않았거나 scan 자체가 지배적일 수 있다. plan node와 병목을 확인한다.

### 문제 8. concurrency 확대

단일 client에서 20% 개선됐다.

**풀이:** concurrency 32에서도 같은 결과라고 말할 수 없다. buffer 경쟁, lock, memory, I/O queue와 tail latency가 달라진다. 별도 workload로 throughput과 p95/p99를 측정한다.

## 19. 재현 패키지의 완료 조건

보고서에는 schema와 데이터 생성기, 정확한 PostgreSQL version과 설정, statistics 정의, ANALYZE 절차, SQL, 실행 순서, 모든 plan JSON, 원시 timing CSV, checksum, 분석 script를 포함한다. 실패한 run과 제외 이유도 남긴다. hardware와 OS, CPU frequency 정책, storage, cache 절차, 동시성도 기록한다.

누군가 같은 package로 같은 결론 방향을 재현하지 못한다면 환경 차이인지 분석 오류인지 조사할 수 있어야 한다. 예쁜 평균 그래프보다 원시 관측에서 주장까지의 추적 가능성이 연구 결과의 수명을 늘린다.

## 근거와 더 읽을 자료

- [PostgreSQL 18: Multivariate Statistics Examples](https://www.postgresql.org/docs/18/multivariate-statistics-examples.html)
- [PostgreSQL 18: EXPLAIN](https://www.postgresql.org/docs/18/sql-explain.html)
- [PostgreSQL 18: Using EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html)
- [The Art of PostgreSQL: Statistics source documentation](https://www.postgresql.org/docs/18/planner-stats.html)
