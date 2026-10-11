# 11. Columnar·vectorized query engine

[이 책 목차](README.md) · [이전: Replication과 distributed transaction](10-replication-and-distributed-transactions.md) · [다음: Spark, Iceberg와 최적화](12-spark-iceberg-and-optimization.md)

![11. Columnar·vectorized query engine 흐름](assets/columnar-vectorized.svg)

분석 질의는 흔히 수억 행 중 두세 열만 읽어 합계나 그룹 수십 개를 만든다. 행 전체를 하나씩 객체로 복원하면 필요 없는 문자열까지 저장장치에서 읽고, CPU는 각 행마다 함수 호출과 분기 비용을 낸다. 열 지향 저장과 벡터 실행은 “무엇을 읽는가”와 “한 번에 몇 값을 계산하는가”를 바꾼다. 이 장은 디스크 파일의 열 조각과 실행 중 메모리 배열을 먼저 구분하고, 필터 한 개가 실제 비트와 위치 목록으로 변하는 과정을 끝까지 추적한다.

## 1. 행, 열, 블록은 실제로 무엇인가

**행(row)** 은 주문 한 건처럼 여러 속성을 한 논리 레코드로 묶은 것이다. order_id=7, region=KR, amount=120, status=paid가 한 행이다. **열(column)** 은 모든 행의 같은 속성, 예를 들어 amount 값들의 순서다. 스키마는 각 열의 이름·타입·null 허용 여부를 정한다.

**row-oriented layout, 행 지향 배치** 는 한 행의 여러 열 바이트를 가까이 둔다. 주문 한 건을 찾아 모든 필드를 고칠 때 유리하다. **columnar layout, 열 지향 배치** 는 같은 열의 값들을 연속해서 둔다. 1억 건의 amount만 합산할 때 order_id, 긴 주소, 메모 열을 읽지 않아도 되고 비슷한 값끼리 압축하기 쉽다.

파일을 열 하나짜리 거대한 배열로 만들면 병렬 읽기와 통계 건너뛰기가 어렵다. 그래서 Parquet 같은 형식은 행들을 **row group, 행 그룹** 으로 나눈다. 한 행 그룹은 예를 들어 10만 행의 수평 범위다. 그 안에서 각 열에 해당하는 연속 바이트 구간이 **column chunk, 열 조각** 이다. 열 조각은 다시 인코딩과 압축 단위인 data page들로 나뉠 수 있다. Parquet 파일 끝의 footer metadata는 행 그룹, 열 조각 위치, 행 수와 통계를 기록한다. reader는 footer를 먼저 읽어 필요한 바이트 범위를 찾는다.

여기서 **page** 는 데이터베이스 버퍼 페이지나 운영체제 가상 메모리 페이지와 같은 객체가 아니다. Parquet 안의 인코딩 단위라는 문맥이다. **chunk** 도 제품마다 크기와 뜻이 다르므로 “파일의 특정 행 범위·특정 열 바이트”라고 대상을 함께 말해야 한다.

## 2. 디스크 chunk와 메모리 batch

질의 엔진은 열 조각을 읽어 압축을 풀고 메모리에 타입이 같은 값의 배열을 만든다. 이때 연산자가 한 번에 처리하도록 자른 행 묶음을 **batch 또는 vector batch** 라고 한다. 디스크의 column chunk는 파일 수명 동안 존재하고 파일 writer가 만든다. 메모리 batch는 한 질의 실행 중 scanner와 operator가 만들고 소비한 뒤 해제한다. 이름이 비슷해도 수명과 관리자가 다르다.

**vectorized execution, 벡터화 실행** 은 연산자가 한 행씩 함수를 부르는 대신 amount 배열 1,024개처럼 값 묶음을 한 루프에서 처리하는 방식이다. 타입 검사와 함수 호출을 batch마다 한 번만 할 수 있고, CPU가 연속 메모리를 미리 가져오기 쉽다. 벡터화는 CPU 한 명령이 여러 값을 계산하는 **SIMD** 와 같은 말이 아니다. 벡터 루프가 SIMD 명령으로 컴파일될 수 있지만, SIMD 없이도 함수 호출·분기 감소와 메모리 지역성 이익을 얻을 수 있다.

**CPU cache** 는 코어 가까이에 있는 작고 빠른 하드웨어 저장 공간이다. 최근 접근한 메모리의 cache line을 보관한다. amount 정수들이 연속하면 한 line을 가져올 때 다음 여러 값도 함께 온다. 행 객체 포인터를 따라 여러 주소로 뛰면 cache miss가 늘 수 있다. “columnar가 항상 빠르다”가 아니라 필요한 열이 적고 순차 스캔이 많을 때 이 배치가 유리하다는 뜻이다.

## 3. projection으로 읽을 열을 줄인다

**projection, 투영** 은 SELECT 결과와 이후 연산에 필요한 열만 남기는 변환이다. 1억 행, 논리 행 폭 200B이면 전체 논리 크기는 약 20GB다. 질의가 각각 8B인 amount와 customer_id 두 열만 필요하면 압축 전 대상은 1.6GB다.

~~~sql
SELECT customer_id, SUM(amount)
FROM orders
WHERE amount >= 100
GROUP BY customer_id;
~~~

이 질의에 status나 shipping_address가 필요 없다면 scanner는 그 열 조각을 읽지 않는다. 선택한 두 열이 4:1로 압축됐다면 저장장치에서 약 400MB를 읽을 수 있다. 행 그룹 통계로 75%를 건너뛴다면 후보는 약 100MB가 된다. 이 숫자는 교육용 계산이며 실제 압축률과 통계 효과는 데이터 분포·인코딩·파일 구성에 따라 달라진다.

열 지향 파일도 SELECT *처럼 대부분 열을 복원하거나 행 하나를 자주 갱신하면 이점이 작아질 수 있다. 갱신은 여러 열 조각을 다시 쓰거나 별도 delete/update 구조를 요구한다. 저장 형식 선택은 읽기 패턴과 변경 패턴을 함께 본다.

## 4. 행 그룹 통계로 건너뛰기

**predicate, 조건식** 은 각 행을 결과에 포함할지 판정하는 식이다. **min/max statistics** 는 한 행 그룹의 열 최솟값과 최댓값이다. 조건 amount >= 100인데 그룹 max=90이면 그 그룹에는 참인 행이 없으므로 열 데이터를 읽지 않아도 된다. 이를 data skipping 또는 pruning이라고 한다.

네 행 그룹이 각각 1,000행이고 amount 범위가 다음과 같다고 하자.

| 그룹 | min | max | amount >= 100 판단 |
|---|---:|---:|---|
| G1 | 0 | 90 | 전체 건너뜀 |
| G2 | 0 | 200 | 읽어야 함 |
| G3 | 10 | 70 | 전체 건너뜀 |
| G4 | 20 | 80 | 전체 건너뜀 |

G2의 max=200이라고 모든 행이 100 이상인 것은 아니다. 통계는 “가능성”을 판정한다. G2를 읽어 실제 값을 검사해야 한다. 반대로 min/max가 손상되거나 오래된 별도 카탈로그 통계라면 잘못 건너뛰어 정답을 잃을 수 있으므로 파일 메타데이터의 정확성 계약이 중요하다. 문자열 정렬 순서, NaN, null 통계, 잘린 bound 같은 형식 세부 조건도 reader가 지켜야 한다.

## 5. 한 batch의 필터·선택·집계 전체 추적

G2에서 amount batch 8개를 해제했다고 하자.

값 배열: [50, 100, 120, NULL, 80, 150, 100, 20]

**validity bitmap, 유효성 비트맵** 은 각 위치가 실제 값인지 null인지를 1비트로 표시하는 별도 메모리 버퍼다. 여기서는 [1,1,1,0,1,1,1,1]이다. NULL 위치의 값 버퍼 바이트는 의미가 없을 수 있으므로 먼저 비트를 확인해야 한다.

조건 amount >= 100의 세 값 논리 결과는 [F,T,T,U,F,T,T,F]다. U는 unknown이다. SQL WHERE는 true인 위치만 통과시키므로 최종 포함 마스크는 [0,1,1,0,0,1,1,0]이다.

**selection vector, 선택 위치 벡터** 는 통과한 행의 위치 번호 목록이다. 위 마스크를 [1,2,5,6]으로 바꿀 수 있다. 다음 연산자는 전체 열을 복사하지 않고 이 네 위치만 참조한다. 합계 연산의 내부 상태는 다음과 같다.

| 처리 위치 | 값 | 이전 합 | 새 합 |
|---:|---:|---:|---:|
| 1 | 100 | 0 | 100 |
| 2 | 120 | 100 | 220 |
| 5 | 150 | 220 | 370 |
| 6 | 100 | 370 | 470 |

이 작은 batch의 결과는 sum=470, count=4다. G2의 나머지 batch를 같은 방식으로 처리해 최종 sum=128,000이 되었다고 하자. 128,000은 실제 벤치마크 결과가 아니라 operator 상태 결합을 설명하기 위한 값이다.

## 6. NULL은 값 0이 아니다

NULL은 “0”, 빈 문자열, 거짓이 아니라 값이 알려지지 않았음을 나타낸다. [10,NULL,30,50]에서 x >= 30은 [F,U,T,T]다. WHERE 결과는 30과 50이고 SUM은 80이다. NULL을 0으로 바꾸면 어떤 집계에서는 우연히 합계가 같지만 COUNT(x)와 AVG(x)가 달라진다. COUNT(x)=3, COUNT(*)=4, AVG(x)=30이다.

비트맵은 null 여부를 값 버퍼와 분리해 한 위치당 1비트로 조밀하게 저장한다. 1,024개 위치의 bitmap은 128B다. 그러나 중첩 타입은 부모와 자식 배열이 각각 유효성 정보를 가질 수 있고, 파일의 definition level 같은 표현에서 메모리 bitmap으로 바꾸는 decode 과정이 필요하다.

## 7. dictionary와 run-length encoding

문자열 status가 반복되면 매 행에 문자열 바이트를 되풀이하지 않고 고유 값 사전과 작은 정수 ID를 저장할 수 있다. 이를 **dictionary encoding, 사전 인코딩** 이라 한다.

원래 12개 값:

[paid, paid, paid, cancelled, cancelled, paid, paid, paid, paid, paid, cancelled, paid]

사전은 0=paid, 1=cancelled이고 ID 배열은 다음과 같다.

[0,0,0,1,1,0,0,0,0,0,1,0]

status=paid 비교는 긴 문자열을 12번 비교하는 대신 사전에서 paid의 ID 0을 찾고 정수 ID를 비교할 수 있다. 선택 위치는 [0,1,2,5,6,7,8,9,11]이다. 단, 두 파일의 dictionary ID 0이 같은 문자열을 뜻한다는 보장은 없다. 사전의 범위와 내용을 함께 읽어야 한다.

연속 반복을 길이로 저장하는 **RLE(run-length encoding)** 를 적용하면 위 ID는 (0,3),(1,2),(0,5),(1,1),(0,1)로 표현된다. 같은 값이 길게 이어질 때 작아지고, 0과 1이 매번 바뀌면 오히려 run 메타데이터 비용이 늘 수 있다. 엔트로피가 낮다는 말만으로 RLE 효과를 보장할 수 없고 값 순서가 중요하다.

## 8. compression과 encoding을 구분한다

**encoding** 은 값의 논리적 배열을 dictionary, delta, RLE 같은 다른 표현으로 바꾸는 규칙이다. **compression** 은 인코딩된 바이트를 Snappy, Zstandard 같은 압축 코덱으로 더 줄이는 단계다. reader는 압축을 풀고 인코딩을 해석해야 원래 값 배열을 얻는다.

G2 amount column chunk가 비압축 8KiB이고 압축 뒤 2KiB라면 압축률은 4:1이다. 저장장치 읽기는 2KiB지만 CPU는 해제 작업을 수행하고 메모리에는 최소 8KiB에 가까운 값 표현이 생길 수 있다. 저장장치가 병목이면 유리하고 CPU가 이미 포화면 강한 압축의 해제 비용이 손해일 수 있다. 코덱 이름만 비교하지 말고 읽은 바이트, 해제 CPU 시간, 최종 질의 시간을 같은 데이터에서 측정한다.

## 9. late materialization

**materialization, 구체화** 는 여러 열을 다시 한 행 형태로 조립하거나 최종 객체로 만드는 일이다. **late materialization, 늦은 구체화** 는 필터와 집계를 열 배열과 위치 벡터 상태로 먼저 수행하고, 실제 출력에 필요한 소수 행만 뒤에서 조립하는 전략이다.

orders가 amount, status, 긴 comment 열을 갖고 있고 amount >= 100 통과율이 1%라고 하자. 먼저 작은 amount 배열만 읽어 선택 위치를 만든다. 그 뒤 선택 위치에 해당하는 comment만 읽을 수 있는 파일·reader 능력이 있다면 긴 문자열 99%의 decode를 피한다. 하지만 comment 페이지가 선택 위치와 무관하게 통째로 압축돼 있으면 페이지 읽기 자체는 필요할 수 있다. 늦은 구체화의 실제 절약은 페이지 인덱스, 인코딩, reader 구현에 달려 있다.

## 10. hash aggregation과 spill

GROUP BY region은 region 값마다 합계 상태를 메모리 hash table에 둔다. **hash table** 은 키를 hash 함수로 bucket 위치에 매핑해 평균적으로 빠르게 상태를 찾는 자료구조다. distinct region이 10,000개이고 키·합계·관리 정보가 그룹당 64B라는 교육용 가정이면 상태는 640,000B다. 실행기에 허용된 메모리가 512KiB, 즉 524,288B라면 넘친다.

**spill** 은 메모리 한도를 넘은 중간 상태를 로컬 디스크에 임시로 쓰고 나중에 다시 읽어 합치는 동작이다. 정답을 유지하지만 추가 쓰기·읽기와 직렬화 비용이 생긴다. 실행 시간이 갑자기 길어졌을 때 입력 파일 읽기만 보지 말고 spill bytes, partition 수, hash key 쏠림을 본다. 20,000개 그룹이 그룹당 80B라면 1,600,000B이므로 1MiB 한도를 넘는다.

## 11. SIMD가 적용되는 자리와 한계

SIMD 레지스터는 여러 작은 숫자를 한 CPU 명령의 입력으로 담는 하드웨어 공간이다. 예를 들어 개념적으로 256비트 레지스터에는 32비트 정수 8개가 들어간다. amount 8개와 상수 100을 비교해 8개 결과 비트를 한 번에 만들 수 있다. 실제 명령 폭과 생성 코드는 CPU ISA, 컴파일러, 엔진 구현, 데이터 정렬에 따라 달라진다.

가변 길이 문자열, 복잡한 분기, null이 많은 중첩 값은 단순 정수보다 SIMD 활용이 어렵다. 또한 메모리 대역폭이 이미 한계라면 계산 명령을 줄여도 전체 시간이 거의 줄지 않는다. 벡터화가 곧 SIMD이고 SIMD가 곧 일정 배수 속도 향상이라는 결론은 틀리다. CPU cycles, instructions, cache misses, 읽은 바이트를 함께 측정해야 한다.

## 12. 파일 통계와 정확성 경계

min/max, dictionary, bloom filter는 후보를 줄이는 데 쓰인다. **Bloom filter** 는 “이 값이 확실히 없다”를 빠르게 말할 수 있는 확률적 비트 구조다. 있을 수 있다고 답한 경우 실제 데이터에서 확인해야 하며 false positive가 가능하다. 올바르게 구성된 Bloom filter는 false negative를 내면 안 된다.

pruning 보조 구조가 “없다”고 말해 행 그룹을 건너뛰는 순간 정확성 경로에 들어간다. 타입 정렬, null, NaN, 대소문자 규칙, 암호화된 metadata, 손상 검출을 형식 계약대로 처리해야 한다. 통계를 이해하지 못하는 reader는 보통 건너뛰지 않고 읽는 안전한 선택을 해야 한다.

## 13. 전체 파이프라인에서 바이트와 행을 분리한다

1억 행 × 200B = 20GB는 논리 행 폭 계산이다. 필요한 두 열 1.6GB는 투영 뒤 비압축 값 크기다. 400MB는 4:1 압축 가정의 저장 바이트다. 100MB는 행 그룹 pruning 뒤 읽을 후보 바이트다. 8개 batch에서 4개가 통과했다는 값은 한 batch의 행 선택 결과다. 최종 3개 그룹 행은 집계 결과다.

이 수치를 한 문장에 “20GB를 3행으로 줄였다”고만 쓰면 병목을 찾을 수 없다. storage bytes read, decompressed bytes, input rows, selected rows, output rows, CPU time, spill bytes를 단계별로 기록해야 한다. cold run은 OS와 저장장치 cache가 비어 있을 수 있고 warm run은 이전 데이터가 cache에 남는다. 둘을 같은 조건의 성능 비교로 섞지 않는다.


## 14. Parquet 파일을 여는 실제 순서

reader는 파일 이름을 봤다고 곧바로 첫 행부터 읽지 않는다. 파일 끝에는 metadata 길이와 PAR1 표식이 있고, 그 앞의 footer metadata에 스키마와 row group별 column chunk 위치가 있다. 먼저 끝부분의 작은 범위를 읽고, footer가 가리키는 offset과 compressed size를 이용해 필요한 열 조각만 범위 읽기한다. 원격 object storage에서는 이 순서가 요청 횟수와 지연에 직접 영향을 준다.

orders.parquet에 두 row group과 세 열 order_id, region, amount가 있다고 하자. 질의가 amount만 필요하면 reader는 두 amount chunk의 위치만 요청할 수 있다. region으로 필터하지만 amount를 합산한다면 region chunk를 먼저 decode해 선택 위치를 만들고, 같은 row group의 amount 위치를 결합한다. 행 번호 정렬이 깨지면 다른 주문의 amount를 더하게 되므로 모든 열 배열은 같은 row group의 논리 행 순서를 유지해야 한다.

footer가 파일 뒤에 있는 까닭은 writer가 데이터를 한 번 흘려 쓰며 각 chunk의 실제 offset과 크기를 모은 뒤 마지막에 완성된 목차를 기록할 수 있기 때문이다. 파일 전송이 중간에 끊겨 footer가 없거나 길이가 맞지 않으면 완성된 Parquet 파일로 읽어서는 안 된다. 데이터 lake의 table format은 보통 완성 파일을 먼저 만들고 metadata commit으로 공개해 reader가 반쪽 파일을 선택하지 않게 한다.

## 15. 행 지향이 더 나은 반례

고객 ID 하나로 point lookup해 이름·주소·등급·최근 연락을 모두 반환하는 요청을 생각하자. 인덱스가 정확한 행 위치를 찾고 한 행의 열들이 같은 페이지에 가까이 있다면 행 지향 저장은 적은 읽기로 끝난다. 열 파일에서는 여러 column chunk와 page에서 한 위치를 찾아 다시 조립해야 할 수 있다. 초당 수천 번 한 행을 갱신하는 OLTP에서는 파일 전체 또는 큰 조각을 다시 쓰는 비용도 크다.

반대로 날짜 한 달의 1억 주문에서 amount 평균만 구하는 요청은 columnar가 유리하다. 따라서 제품 이름이 아니라 접근 모양을 적는다. 반환 행 비율, 필요한 열 비율, 업데이트 빈도, 스캔 연속성, 압축 가능성, 지연 목표가 선택 근거다. 현대 시스템은 최근 변경은 행 지향으로 받고 오래된 분석 자료는 열 형식으로 옮기는 혼합 구조를 쓰기도 한다. 두 사본 사이 최신성 경계도 측정해야 한다.

## 16. 연산자 사이 batch 수명과 backpressure

scan 연산자가 batch를 만드는 속도가 aggregate가 소비하는 속도보다 빠르면 메모리에 batch가 무한히 쌓여서는 안 된다. **backpressure, 역압** 은 하류 연산자의 처리 가능량에 맞춰 상류 생산을 늦추는 흐름 제어다. 한 batch는 scanner가 버퍼를 소유하고 다음 연산자에 넘기거나, 참조 수명 계약에 따라 공유한다. 하류가 처리를 끝내기 전에 버퍼를 재사용하면 값이 덮여 정확성이 깨진다.

batch를 크게 하면 호출 횟수는 줄지만 working set이 cache를 넘어갈 수 있고, 첫 결과까지 기다리는 시간과 메모리가 늘 수 있다. 너무 작으면 per-batch metadata와 함수 호출 비용이 커진다. 1,024행, 4,096행 같은 값은 보편 정답이 아니다. 타입 폭과 연산자, cache 크기, 선택률을 고정한 실험으로 결정한다.


## 17. 완전 풀이 문제

### 문제 1. 필요한 두 열의 크기

1억 행에서 8B 열 두 개만 읽는다.

**풀이:** 100,000,000 × 16B = 1,600,000,000B, 약 1.6GB다. 이는 압축 전 논리 값 크기이며 파일 footer, validity bitmap, page header는 제외한 교육용 계산이다. 압축률 4:1이면 약 400MB지만 실제 값 분포에 따라 달라진다.

### 문제 2. min/max pruning

조건 amount >= 100이고 G1 min/max=0/99, G2=50/150, G3=100/100이다.

**풀이:** G1은 max<100이라 건너뛴다. G2는 일부 가능하므로 읽어 행별 검사한다. G3은 모든 비-null 값이 조건을 만족할 수 있지만 null 처리와 통계 정확성 조건을 확인해야 한다. 통계만으로 G2의 통과 행 수는 알 수 없다.

### 문제 3. NULL mask

배열 [10,NULL,30,50]에 x >= 30을 적용한다.

**풀이:** 비교는 [F,U,T,T], WHERE 포함 mask는 [0,0,1,1], selection vector는 [2,3], SUM=80이다. COUNT(x)=3이고 COUNT(*)=4다. NULL을 0으로 치환하면 AVG 의미를 바꾼다.

### 문제 4. dictionary ID 비교

파일 A의 dictionary 0=paid이고 파일 B의 dictionary 0=cancelled다.

**풀이:** 두 파일의 ID 0을 직접 같은 값으로 묶으면 오류다. 각 dictionary로 의미를 해석하거나 공통 dictionary로 재매핑해야 한다. ID는 dictionary 범위 안에서만 의미가 있다.

### 문제 5. selection vector 이후 합

값 [50,100,120,NULL,80,150,100,20], 선택 [1,2,5,6]이다.

**풀이:** 위치 값은 100,120,150,100이고 누적 합은 100→220→370→470, count=4다. NULL 위치 3은 선택되지 않았다. 위치는 값 자체가 아니라 batch 안의 0부터 시작하는 인덱스다.

### 문제 6. hash state memory

20,000 distinct key, 그룹당 80B, 한도 1MiB다.

**풀이:** 20,000×80=1,600,000B로 1,048,576B를 넘는다. 엔진은 spill, partitioned aggregation, 더 압축된 상태 중 하나가 필요하다. 실제 메모리는 allocator와 hash table 빈 bucket 때문에 더 클 수 있다.

### 문제 7. 4:1 압축이면 질의도 4배 빠른가?

**풀이:** 저장장치 읽기 바이트는 4분의 1이 될 수 있지만 decode CPU, cache, predicate, 집계, spill이 남는다. 저장장치가 전체 시간의 20%였다면 그 부분만 줄어 전체 4배는 불가능하다. 단계별 시간을 측정한다.

### 문제 8. 벡터화는 항상 SIMD인가?

**풀이:** 아니다. batch API와 연속 배열만 사용해도 per-row 호출을 줄이는 벡터화다. SIMD 명령 생성은 타입, CPU, compiler와 engine kernel에 달려 있다. 실행 계획의 columnar/vectorized 표시와 하드웨어 counter를 구분해 확인한다.

## 18. 재현 가능한 측정

같은 파일과 같은 질의를 여러 번 실행할 때 파일 목록, row group 수, 압축 코덱, projection, predicate, batch 크기, 실행기 메모리를 기록한다. 첫 실행과 반복 실행을 cold/warm으로 나누고, 파일 cache를 임의로 비우는 조작은 격리된 시험 환경에서만 한다. 결과 행과 checksum을 먼저 비교해 최적화가 정답을 바꾸지 않았는지 확인한다. 그 뒤 bytes read, row groups skipped, rows selected, decode time, spill bytes와 전체 시간을 비교한다.

## 근거와 더 읽을 자료

- [Apache Parquet: File Format](https://parquet.apache.org/docs/file-format/)
- [Apache Parquet Format repository](https://github.com/apache/parquet-format)
- [Apache Arrow: Columnar Format](https://arrow.apache.org/docs/format/Columnar.html)
