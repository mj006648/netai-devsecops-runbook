# 02. DataFrame과 Spark SQL: 표를 선언하면 실행 계획이 되는 과정

[이전: Driver와 Executor](01-driver-executor.md) · [목차](README.md) · [다음: Lazy Evaluation, DAG, Job과 Stage](03-lazy-dag-jobs-stages.md)

데이터를 여러 서버에 나누어 놓는 것만으로는 분석이 끝나지 않는다. 사용자는 보통 "한국의 매출 합계를 구해라", "정상 온도만 남겨 센서별 평균을 구해라"처럼 데이터의 의미를 말하고 싶다. 반면 컴퓨터는 어느 파일의 어느 바이트를 읽고, 어떤 자료형으로 비교하고, 어느 Partition 사이에서 값을 옮길지까지 알아야 한다. Spark의 DataFrame과 SQL은 이 두 수준 사이를 연결한다.

이 장에서는 먼저 작은 표를 만든다. 그다음 한 줄의 DataFrame 코드가 어떤 객체를 만들고, 언제 실제 데이터를 읽으며, 어떤 논리 계획과 물리 계획으로 바뀌는지 전 과정을 따라간다. 마지막에는 NULL, 형 변환, Python UDF처럼 정답이 조용히 달라지기 쉬운 경계를 숫자로 확인한다.

## 1. DataFrame이 실제로 가리키는 것

**DataFrame, 데이터프레임**은 이름과 자료형이 정해진 열들로 구성된 분산 표를 표현하는 객체다. Python을 쓴다면 Driver의 Python 프로세스에 DataFrame 변수 하나가 생기지만, 그 변수 안에 대규모 행 전체가 들어 있는 것은 아니다. 변수는 어떤 데이터를 어떤 순서로 변환할지 설명하는 계획의 손잡이에 가깝다. 실제 행은 파일에 있거나 Executor의 Partition에서 처리된다.

**행, row**는 한 대상에 관한 값들의 묶음이다. 매출 표의 한 행 (KR, 10)은 country가 KR이고 amount가 10인 사건 하나를 뜻한다. **열, column**은 모든 행에서 같은 의미를 갖는 값의 자리다. country 열은 국가 코드, amount 열은 금액을 담는다. 열 이름만으로 의미가 완성되지는 않는다. 금액의 단위가 원인지 달러인지, 시간의 기준대가 무엇인지 같은 업무 규칙도 필요하다.

**schema, 스키마**는 열 이름, 자료형, NULL 허용 여부처럼 표의 구조를 적은 설명이다. 스키마는 Driver가 분석하는 계획에 포함되며 DataFrame이 살아 있는 동안 연산 검증과 최적화에 사용된다. 예를 들어 country가 string이고 amount가 long이면 Spark는 amount >= 20을 숫자 비교로 해석할 수 있다.

**자료형, data type**은 값의 가능한 범위와 연산 규칙이다. string은 문자, long은 64비트 정수, double은 부동소수점 수를 표현한다. 같은 글자 12라도 string "12"와 long 12는 다르다. 전자는 문자열 연결과 사전식 비교의 대상이고, 후자는 덧셈과 수치 비교의 대상이다.

다음은 이 장에서 계속 사용할 8행이다.

| Partition | country | amount |
|---|---|---:|
| P0 | KR | 10 |
| P0 | US | 20 |
| P0 | KR | 30 |
| P1 | JP | 40 |
| P1 | KR | 50 |
| P1 | US | 60 |
| P2 | KR | 70 |
| P2 | JP | 80 |

Partition은 병렬 처리할 데이터 묶음이다. 표가 논리적 모양이라면 Partition은 실행 시 실제로 Task가 하나씩 처리하는 조각이다. DataFrame API는 표를 다루게 해 주지만 분산 배치를 없애지는 않는다.

## 2. SparkSession과 두 가지 표현 방식

**SparkSession**은 DataFrame 생성, 파일 읽기, SQL 실행, 설정 접근을 시작하는 Driver 측 진입 객체다. 사용자는 보통 Python 변수 spark로 잡는다. SparkSession이 각 행을 직접 계산하는 것은 아니다. Driver에서 계획을 만들고, 실행 시 Scheduler와 Executor를 연결한다. Application이 끝나면 이 세션을 통한 작업도 끝난다.

같은 계산은 DataFrame API와 SQL로 표현할 수 있다.

~~~python
from pyspark.sql import functions as F

rows = [
    ("KR", 10), ("US", 20), ("KR", 30),
    ("JP", 40), ("KR", 50), ("US", 60),
    ("KR", 70), ("JP", 80),
]
sales = spark.createDataFrame(rows, ["country", "amount"])

result_df = (
    sales
    .filter(F.col("amount") >= 20)
    .groupBy("country")
    .agg(
        F.sum("amount").alias("total"),
        F.count("*").alias("n"),
        F.avg("amount").alias("avg_amount"),
    )
)
~~~

SQL로 쓰려면 DataFrame에 세션 안에서 사용할 임시 이름을 붙인다.

~~~python
sales.createOrReplaceTempView("sales")

result_sql = spark.sql("""
SELECT country,
       SUM(amount) AS total,
       COUNT(*) AS n,
       AVG(amount) AS avg_amount
FROM sales
WHERE amount >= 20
GROUP BY country
""")
~~~

**temporary view, 임시 뷰**는 DataFrame 계획에 붙인 SQL 이름이다. 위의 sales 뷰는 별도 데이터 복사본이 아니다. SparkSession의 카탈로그가 이름과 계획을 관리하며, 보통 해당 세션 범위에서 사용한다. 영구 테이블이나 원본 파일과 수명이 같다고 생각하면 안 된다.

DataFrame API와 SQL은 표현 문법이 다르지만 Spark SQL 실행 엔진으로 들어간다. 하나는 Python 메서드 연결이고 다른 하나는 SQL 문자열이다. 두 표현이 같은 의미와 같은 자료형을 가지면 유사한 최적화 계획이 나올 수 있다. 문법이 다르다는 이유만으로 SQL이 항상 빠르거나 DataFrame이 항상 빠르다고 단정할 수 없다.

## 3. Transformation과 Action: 지금 실행했는가

**transformation, 변환**은 기존 DataFrame에서 새 DataFrame 계획을 만드는 연산이다. filter, select, withColumn, groupBy 뒤의 집계가 여기에 속한다. transformation을 호출하면 Driver에 새 계획 객체가 만들어지지만 보통 전체 입력 파일을 즉시 읽지는 않는다.

**action, 동작**은 결과를 실제로 요구하는 연산이다. show, count, collect, write가 대표적이다. Action이 호출되면 Driver가 계획을 완성하고 Job을 시작한다. 이처럼 결과가 필요할 때까지 실행을 미루는 성질을 **lazy evaluation, 지연 실행**이라고 한다.

~~~python
filtered = sales.filter(F.col("amount") >= 20)  # 계획 생성
grouped = filtered.groupBy("country").sum("amount")  # 계획 확장
grouped.show()  # 이 시점에 Job 실행
~~~

지연 실행이 필요한 이유는 Spark가 연산 전체를 한꺼번에 볼 수 있기 때문이다. filter 다음에 필요 없는 열을 버린다면, Spark는 가능한 경우 저장소에서 필요한 열만 읽고 조건을 아래로 밀 수 있다. 연산을 작성할 때마다 즉시 실행했다면 중간 결과를 매번 저장하고 다시 읽어야 했을 수 있다.

다만 모든 메서드가 메타데이터 작업조차 전혀 하지 않는다고 단정해서는 안 된다. 파일 목록과 스키마를 확인하는 과정에서 저장소 접근이 생길 수 있다. 핵심은 전체 데이터 계산과 Job 실행이 Action까지 미뤄진다는 점이다.

## 4. 8행이 실제 답으로 바뀌는 숫자 추적

조건 amount >= 20을 먼저 적용한다. P0의 KR 10만 제거되고 나머지 7행이 남는다.

| Partition | 조건 통과 행 | 로컬 부분 집계 (sum, count) |
|---|---|---|
| P0 | US 20, KR 30 | US=(20,1), KR=(30,1) |
| P1 | JP 40, KR 50, US 60 | JP=(40,1), KR=(50,1), US=(60,1) |
| P2 | KR 70, JP 80 | KR=(70,1), JP=(80,1) |

같은 country를 모으기 위해 shuffle이 일어난다. shuffle은 서로 다른 Partition의 데이터를 키에 따라 네트워크로 재배치하는 과정이다. 국가별 부분 집계를 합치면 다음 답이 된다.

| country | total | n | avg_amount |
|---|---:|---:|---:|
| KR | 150 | 3 | 50.00 |
| US | 80 | 2 | 40.00 |
| JP | 120 | 2 | 60.00 |

원본에 US 90 행을 하나 더 넣은 9행 예제에서는 US가 20+60+90=170, n=3, 평균 약 56.67이 된다. 기존 9행 모델의 최종 값 KR=(150,3), US=(170,3), JP=(120,2)를 유지하려면 P2에 US 90이 있어야 한다. 8행과 9행 결과를 섞어 쓰면 합계가 맞지 않는다.

평균은 Partition별 평균을 다시 평균내면 안 된다. P0의 KR 평균은 30이고 P1은 50, P2는 70이어서 우연히 (30+50+70)/3=50이다. Partition별 행 수가 다르면 틀린다. Spark는 결합 가능한 중간 상태 sum과 count를 보내 최종적으로 total sum / total count를 계산한다.

## 5. 계획은 네 층을 거친다

사용자가 작성한 식이 바로 CPU 명령으로 실행되는 것은 아니다. 계획은 다음 층을 거친다.

~~~mermaid
flowchart LR
    A[DataFrame API 또는 SQL] --> B[미해결 논리 계획]
    B --> C[분석된 논리 계획]
    C --> D[최적화된 논리 계획]
    D --> E[물리 계획]
    E --> F[Stage와 Task 실행]
~~~

**logical plan, 논리 계획**은 무엇을 계산할지를 관계 연산으로 표현한다. Scan, Filter, Project, Aggregate, Join 같은 노드가 연결된 트리다. 아직 특정 shuffle 구현이나 정렬 알고리즘을 고르지 않았다는 점에서 논리적이다.

처음 SQL에서 sales와 amount라는 이름은 문자열일 뿐이다. 이 이름이 어느 뷰와 어느 열을 뜻하는지 확정하기 전 계획을 **미해결 논리 계획**이라고 한다. **Analyzer, 분석기**는 세션 카탈로그와 스키마를 사용해 이름을 실제 관계와 열 ID에 연결하고, 함수와 자료형을 검사한다. 존재하지 않는 열 amuont를 쓰면 이 단계에서 오류가 난다.

**optimized logical plan, 최적화된 논리 계획**은 결과 의미를 유지하면서 불필요한 일을 줄인 계획이다. 사용하지 않는 열 제거, 상수 식 단순화, 가능한 filter 이동 등이 여기에 들어갈 수 있다.

**physical plan, 물리 계획**은 논리 연산을 실제 실행 연산자로 바꾼 후보와 선택 결과다. 같은 join도 데이터 크기와 통계에 따라 broadcast hash join 또는 sort merge join 같은 실행법이 가능하다. 이 장의 집계는 개념적으로 다음과 같다.

1. Scan: country와 amount를 읽는다.
2. Filter: amount >= 20이 아닌 행을 버린다.
3. Partial Aggregate: 각 Partition에서 country별 sum과 count를 만든다.
4. Exchange: country 기준으로 부분 상태를 shuffle한다.
5. Final Aggregate: 같은 country의 상태를 합친다.
6. 필요하면 Sort: 화면에 일정한 순서로 보이게 정렬한다.

**Catalyst**는 Spark SQL에서 식과 계획을 분석하고 변환하는 최적화 기반의 이름이다. Catalyst를 단순히 "쿼리를 빠르게 하는 마법"이라고 외우면 부족하다. 입력은 표현식 트리이고, 규칙과 통계 기반 선택을 거쳐 결과 의미를 보존하는 다른 트리로 바뀐다. 최적화가 가능하려면 Spark가 열, 자료형, 함수 의미를 알아야 한다.

explain을 사용하면 계획을 관찰할 수 있다.

~~~python
result_df.explain("extended")
~~~

출력의 정확한 연산자 이름과 배치는 Spark 버전, 설정, 통계에 따라 달라질 수 있다. 따라서 이 코드는 위 여섯 단계의 개념을 확인하는 관찰 도구이며 특정 문자열 전체를 영구 계약으로 간주해서는 안 된다.

## 6. NULL은 빈 문자열도 0도 아니다

**NULL**은 값이 없거나 알려지지 않았음을 나타내는 SQL 표지다. 실제 데이터 행의 해당 열 자리에 저장되거나 계산 중 만들어진다. 빈 문자열은 길이 0인 알려진 문자열이고, 0은 알려진 숫자다. NULL을 둘 중 하나로 바꾸면 데이터 의미가 달라진다.

SQL 비교는 true와 false만 쓰지 않고 unknown까지 쓰는 **3값 논리**를 따른다.

| 식 | 결과 |
|---|---|
| 20 > 10 | true |
| 5 > 10 | false |
| NULL > 10 | unknown |
| NULL = NULL | unknown |
| NULL IS NULL | true |

WHERE와 filter는 조건이 true인 행만 남긴다. false와 unknown은 모두 제거된다. 따라서 amount > 10은 amount가 NULL인 행을 남기지 않는다. NULL 자체를 찾으려면 isNull 또는 IS NULL을 써야 한다.

집계의 NULL 규칙도 숫자로 확인하자. 값이 20, 22, NULL인 열이 있다.

| 집계 | 결과 | 이유 |
|---|---:|---|
| COUNT(*) | 3 | 행 자체를 센다 |
| COUNT(value) | 2 | NULL이 아닌 value만 센다 |
| SUM(value) | 42 | NULL을 제외하고 합친다 |
| AVG(value) | 21 | 42 / 2 |
| NULL을 0으로 채운 뒤 AVG | 14 | (20+22+0) / 3 |

NULL을 0으로 채우는 것은 단순 청소가 아니라 "모르는 값은 실제 0이다"라는 가정을 추가하는 일이다. 센서가 측정하지 못한 온도를 0도로 바꾸면 평균이 21에서 14로 내려간다.

## 7. 센서 6행으로 보는 조건과 NULL

다음 입력을 보자.

| sensor_id | temperature |
|---|---:|
| S1 | 20 |
| S1 | 22 |
| S2 | 19 |
| S2 | 99 |
| S3 | 23 |
| S3 | NULL |

정상 범위를 -40 이상 60 이하로 정의하고 센서별 평균을 낸다. 99는 조건이 false라 제거된다. NULL과의 비교는 unknown이라 제거된다.

| sensor_id | 남은 값 | avg | count(temperature) |
|---|---|---:|---:|
| S1 | 20, 22 | 21 | 2 |
| S2 | 19 | 19 | 1 |
| S3 | 23 | 23 | 1 |

S3의 원래 행 수는 2지만 count(temperature)는 1이다. 측정 누락률을 보려면 COUNT(*)와 COUNT(temperature)를 함께 계산해 2-1=1개의 누락을 드러내야 한다. 평균만 보면 S3 데이터가 완전하다고 오해할 수 있다.

## 8. 형 변환은 실패 정책까지 포함한다

외부 CSV의 숫자 열이 string으로 들어왔다고 하자. 값은 "12", "12.5", "unknown"이다. 이를 long으로 바꾸려는 요구에는 이미 정책 질문이 있다. 소수 12.5를 버릴 것인가, 오류로 막을 것인가, NULL로 바꿀 것인가?

**cast, 형 변환**은 한 자료형의 값을 다른 자료형 규칙으로 해석하는 연산이다. 변환 불가능한 입력을 어떻게 처리하는지는 ANSI 설정과 사용하는 함수에 따라 달라질 수 있다. ANSI 모드에서는 잘못된 변환이 오류가 될 수 있고, try_cast는 변환할 수 없는 값을 NULL로 돌려준다.

개념적 결과는 다음과 같다.

| 원문 | try_cast(... AS BIGINT) |
|---|---:|
| "12" | 12 |
| "12.5" | NULL |
| "unknown" | NULL |

그다음 dropna로 NULL 행을 제거하면 3행 중 1행만 남는다. 파이프라인은 성공해도 데이터의 66.7%가 사라졌다. 안전한 처리에는 원문 열, 변환 결과, 실패 여부를 함께 남기고 실패 건수를 검사하는 단계가 필요하다.

~~~python
parsed = raw.withColumn(
    "amount_long",
    F.expr("try_cast(amount_text AS BIGINT)")
).withColumn(
    "parse_failed",
    F.col("amount_text").isNotNull() & F.col("amount_long").isNull()
)
~~~

이 예제는 Spark 4.2 계열의 try_cast 계약을 전제로 한 설명이다. 실제 실행 환경의 Spark 버전과 ANSI 설정을 확인해야 한다.

## 9. Python UDF를 쓰면 계획이 보는 것이 달라진다

**UDF, user-defined function, 사용자 정의 함수**는 사용자가 만든 함수를 열 연산처럼 등록해 쓰는 기능이다. Python UDF의 함수 코드는 Executor 쪽 Python worker에서 실행된다. 입력 값은 JVM 실행 엔진과 Python 사이를 직렬화해 전달되고, 결과도 다시 돌아온다. 함수의 등록 정보는 Driver의 계획에 있고, 실제 호출 수명은 Task 실행에 묶인다.

예를 들어 amount에 10을 더하는 일은 내장 표현식 F.col("amount") + 10으로 쓸 수 있다. Spark는 이 식의 의미와 자료형을 안다. 반면 임의 Python UDF의 내부 코드는 Catalyst가 일반 SQL 식처럼 분해하기 어렵다. 이 때문에 조건 이동, 코드 생성, NULL 처리 추론 같은 최적화 기회가 줄고 언어 경계 비용이 생길 수 있다.

그렇다고 Python UDF가 항상 금지되는 것은 아니다. 내장 함수로 표현할 수 없는 도메인 로직이 있고 비용을 측정해 받아들일 수 있다면 쓸 수 있다. 판단 순서는 다음과 같다.

1. 내장 Spark SQL 함수로 표현 가능한지 확인한다.
2. 가능하면 내장 표현식을 사용해 계획에 의미를 드러낸다.
3. 불가능하면 scalar Python UDF, Pandas UDF, Arrow UDF 등 입력·출력 계약이 맞는 방식을 고른다.
4. NULL 입력, 예외, 반환 자료형을 명시하고 실제 데이터 크기로 측정한다.

Spark 4.2 공식 PySpark 문서는 scalar Python UDF, Pandas UDF, Arrow UDF를 구분한다. Pandas UDF는 Arrow를 통해 열 묶음을 전달해 벡터화할 수 있지만, 모든 함수가 자동으로 빨라지는 보증은 아니다. 변환 비용, 묶음 크기, 함수 계산량을 함께 봐야 한다.

## 10. DataFrame, Dataset, RDD를 구분하기

**RDD, Resilient Distributed Dataset**은 Partition으로 나뉜 객체 모음과 변환 관계를 표현하는 Spark의 저수준 분산 자료 구조다. 각 원소의 업무 열 이름과 SQL 자료형을 Spark가 항상 아는 것은 아니다.

**Dataset**은 JVM 언어에서 객체 형식 정보와 Spark SQL 실행 엔진을 결합한 API다. **DataFrame**은 이름 있는 열을 가진 Dataset으로 설명할 수 있으며, Scala와 Java 문맥에서는 Dataset[Row]에 해당한다. PySpark 사용자는 주로 DataFrame을 사용한다.

차이는 단순한 속도 서열이 아니다. DataFrame은 스키마와 표현식 의미가 드러나 Catalyst가 분석하기 좋다. RDD는 임의 객체와 함수를 직접 다룰 자유가 크지만, 그 함수 내부 의미를 SQL 최적화기가 알기 어렵다. 구조화된 표 계산이라면 DataFrame과 SQL이 보통 더 많은 검증과 최적화 정보를 제공한다.

## 11. repartition과 파일 수를 혼동하지 않기

**repartition**은 다음 계산을 위해 데이터 행을 새 Partition들로 다시 나누는 transformation이다. 호출 순간 기존 원본 파일을 수정하지 않는다. Action이 실행될 때 shuffle이 생길 수 있고, 이후 write Action이 새 파일을 쓸 때 Partition 수가 출력 파일 수에 영향을 줄 수 있다.

**테이블 partition**은 country=KR 같은 값 기준으로 저장 경로를 나누는 데이터 배치 규칙을 뜻할 수도 있다. 실행 Partition과 같은 단어를 쓰지만 객체가 다르다. 실행 Partition은 Task 입력 단위이고 Application 실행 중 바뀔 수 있다. 테이블 partition은 저장소의 파일 배치와 메타데이터에 남아 여러 쿼리에서 사용된다.

repartition(3)을 호출했다고 기존 Parquet 파일이 세 개로 즉시 바뀌지 않는다. write가 실행되어야 새 출력 파일이 만들어진다. 각 Partition이 반드시 정확히 한 파일이라는 약속도 출력 형식과 쓰기 동작을 고려해야 한다.

## 12. 전체 흐름을 한 번에 추적하기

다음 코드를 Driver에서 작성했다고 하자.

~~~python
answer = (
    spark.read.parquet("/sales")
    .filter(F.col("amount") >= 20)
    .groupBy("country")
    .agg(F.sum("amount").alias("total"))
)
answer.show()
~~~

1. spark.read.parquet가 파일의 스키마와 읽기 관계를 나타내는 DataFrame을 만든다.
2. filter가 조건 표현식을 포함한 새 논리 계획을 만든다.
3. groupBy와 agg가 country별 집계 계획을 더한다.
4. 여기까지 Driver는 주로 계획을 관리하고 전체 행 결과는 아직 만들지 않는다.
5. show가 Action이 되어 Job 생성을 요구한다.
6. Analyzer가 country와 amount를 스키마의 열에 연결하고 자료형을 검사한다.
7. Catalyst 규칙이 필요한 열과 filter 위치, 집계 형태를 다듬는다.
8. Planner가 scan, filter, partial aggregate, exchange, final aggregate의 물리 연산을 고른다.
9. Scheduler가 Stage와 Task를 만들고 Executor에 Partition별 Task를 배치한다.
10. Executor가 파일을 읽고 로컬 부분 합계를 만든 뒤 shuffle한다.
11. 최종 Stage가 국가별 합계를 만들고 show에 필요한 일부 결과가 Driver로 온다.
12. Driver가 표를 화면에 출력한다.

show는 결과 일부를 표시하기 위한 Action이다. collect처럼 전체 결과를 Driver 메모리에 가져오는 용도로 이해하면 안 된다. 반대로 결과가 매우 크다면 어떤 Action이 Driver로 얼마나 반환하는지 확인해야 한다.

## 13. 연습 문제와 자세한 풀이

### 문제 1. DataFrame 변수 안에 1TB 데이터가 들어 있는가?

**풀이:** 아니다. Driver의 변수는 스키마와 변환 계획을 가리키는 객체다. 1TB 행은 저장소에 있고 실행 시 Executor가 Partition별로 읽는다. collect를 호출하면 결과를 Driver로 모으려 하므로 위험하지만, filter만 연결한 DataFrame 변수가 생겼다는 사실만으로 1TB가 Driver 메모리에 복사되지는 않는다.

### 문제 2. 8행 예제에서 amount >= 20 뒤 KR 합계와 개수는 얼마인가?

**풀이:** KR 행은 10, 30, 50, 70이다. 10은 조건에서 제거된다. 남은 값은 30+50+70=150이고 개수는 3이다. 평균은 150/3=50이다. US 90이 없는 8행 입력에서 US 합계를 170이라고 답하면 다른 9행 모델을 섞은 것이다.

### 문제 3. values가 20, 22, NULL일 때 COUNT(*)와 AVG(value)는?

**풀이:** COUNT(*)는 행 세 개를 세므로 3이다. AVG는 NULL이 아닌 값만 사용해 (20+22)/2=21이다. NULL을 0으로 채운 뒤에는 (20+22+0)/3=14가 된다. 채우기는 단순 형식 변경이 아니라 평균의 모집단과 의미를 바꾼다.

### 문제 4. filter를 두 번 작성하면 파일을 두 번 읽는가?

**풀이:** transformation 두 줄만으로 Job이 두 번 실행되지는 않는다. 지연 계획이 두 단계로 늘어난다. 마지막 Action에서 최적화된 하나의 실행 흐름으로 계산할 수 있다. 그러나 서로 다른 Action을 두 번 호출하고 중간 결과를 cache하지 않았다면 공통 구간을 다시 계산할 수 있다.

### 문제 5. country별 평균을 Partition별 평균의 평균으로 구해도 되는가?

**풀이:** 각 Partition의 해당 국가 행 수가 같을 때만 우연히 맞을 수 있다. P0 평균 10에 행 1개, P1 평균 50에 행 9개라면 단순 평균은 30이지만 실제 평균은 (10×1+50×9)/10=46이다. 결합할 때는 각 부분의 sum과 count를 보내 전체 sum/전체 count로 계산해야 한다.

### 문제 6. 문자열 "12", "12.5", "unknown"을 long으로 바꾸고 NULL을 버린 결과는?

**풀이:** try_cast 계약을 쓰면 12만 성공하고 나머지는 NULL이 될 수 있다. NULL을 버리면 한 행만 남는다. 성공 여부만 보면 파이프라인은 정상처럼 보이지만 원본의 2/3가 사라졌다. 변환 실패 수, 원문 값, 허용 임계치를 함께 기록해야 한다.

### 문제 7. Python UDF와 내장 표현식이 같은 계산이면 무엇을 먼저 고르는가?

**풀이:** 보통 내장 표현식을 먼저 고른다. Spark가 식의 자료형과 의미를 알고 논리 계획을 변환할 수 있으며 JVM과 Python 사이 값 전달을 피할 기회가 있기 때문이다. UDF가 항상 느리다는 절대 명제는 아니다. 내장식으로 표현할 수 없는 로직이면 적절한 UDF 종류를 선택하고 실제 입력 크기에서 직렬화와 계산 시간을 측정한다.

### 문제 8. repartition(3) 뒤 원본 파일이 즉시 세 개가 되는가?

**풀이:** 아니다. repartition은 새 실행 Partition을 만들 계획이다. Action 전에는 데이터 재배치가 일어나지 않으며 원본 파일도 그대로다. 이후 write Action이 실행되면 새 출력이 생성된다. 실행 Partition, 테이블의 저장 partition, 실제 출력 파일은 서로 관련될 수 있지만 같은 객체는 아니다.

## 14. 공식 근거와 버전 경계

이 장의 DataFrame·Dataset·SQL 통합 실행 설명은 [Spark 4.2.0 Spark SQL 가이드](https://spark.apache.org/docs/latest/sql-programming-guide)를 기준으로 했다. NULL의 3값 논리와 집계 규칙은 [Spark SQL NULL semantics](https://spark.apache.org/docs/latest/sql-ref-null-semantics.html), 형 변환 오류 정책은 [ANSI compliance](https://spark.apache.org/docs/latest/sql-ref-ansi-compliance.html), Python 함수 종류는 [PySpark UDF·UDTF 가이드](https://spark.apache.org/docs/latest/api/python/user_guide/udfandudtf.html)에 근거한다.

latest 링크가 가리키는 버전은 시간이 지나면 바뀔 수 있다. 이 장에서 고정된 원리는 DataFrame이 구조와 계산 계획을 표현하고 Action이 실행을 요구한다는 점이다. 구체적인 물리 연산자 이름, 기본 설정, 지원 함수와 Spark Connect 지원 범위는 실제 배포 버전의 계약을 확인해야 한다.

[이전: Driver와 Executor](01-driver-executor.md) · [목차](README.md) · [다음: Lazy Evaluation, DAG, Job과 Stage](03-lazy-dag-jobs-stages.md)
