# 11. 로컬 실습: 여섯 행이 계획·Task·Shuffle·파일이 되는 전 과정

[이전: 배포와 Connect](10-deployment-and-connect.md) · [목차](README.md) · [다음: 연구 데이터 처리](12-research-workflows.md)

이 장은 작은 프로그램을 실행하는 법만 나열하지 않는다. 입력 여섯 행이 Driver의 DataFrame 계획이 되고, 실행 Partition과 Task로 나뉘고, Shuffle을 지나 센서별 세 행이 된 다음 Parquet 파일로 기록되는 전 과정을 숫자로 추적한다. 결과가 맞다는 assertion이 무엇을 보장하고 무엇을 보장하지 않는지도 분리한다.

이 실습의 결과와 계획 표시는 고정 커밋의 Python 코드를 읽어 계산한 **교육용 예상값**이다. 이 원고 작성 과정에서는 shell 실행을 하지 않았다. 실행 환경에 따라 Task 번호, 계획의 연산자 이름, 출력 파일 수와 로그 순서는 달라질 수 있다.

## 1. local[2]에서 실제로 만들어지는 것

**로컬 모드**는 한 컴퓨터 안에서 Spark Driver와 실행 스레드를 띄우는 방식이다. 설정 local[2]의 숫자 2는 동시에 Task를 실행할 수 있는 로컬 스레드 수를 뜻한다. 서버 두 대, Executor 두 개, Kubernetes Pod 두 개를 뜻하지 않는다.

**process, 프로세스**는 운영체제가 실행 중인 프로그램에 메모리와 자원을 부여한 단위다. 이 실습을 PySpark로 시작하면 사용자 Python 프로세스가 SparkSession을 만들고, Spark의 계획과 실행 기능은 JVM 경로를 사용한다. **JVM**은 Java Virtual Machine의 약자로 Java와 Scala 바이트코드를 실행하는 프로세스 환경이다. Python UDF가 없는 내장 DataFrame 연산은 주로 Spark SQL의 JVM 실행 연산자로 처리된다.

**Driver**는 사용자의 코드 흐름, DataFrame 계획, Job·Stage·Task 상태를 관리하는 중심 프로세스다. **Task**는 한 Stage에서 Partition 하나를 처리하는 실행 시도다. **Partition**은 Task가 한 번에 담당하는 데이터 조각이다. 이 세 객체의 수명은 다르다. Driver는 Application 동안 살지만 Task는 한 Partition 계산이 끝나면 종료된다. 실패한 Task에는 새 attempt가 생길 수 있다.

로컬 모드는 API와 계획을 공부하기에 좋다. 그러나 한 머신의 메모리와 디스크를 공유하므로 실제 클러스터의 Executor 프로세스 유실, 노드 간 네트워크 지연, Kubernetes 권한과 스케줄링을 검증하지 않는다.

## 2. 실행 환경과 고정된 버전

고정 실습 파일 examples/requirements.txt에는 다음 한 줄이 있다.

~~~text
pyspark==4.0.4
~~~

이 실습 기준선은 Python 3.11, PySpark 4.0.4, Java 21이다. 기준선은 "모든 최신 기능을 반드시 이 조합으로 써야 한다"는 뜻이 아니다. 같은 입력과 assertion을 다시 실행할 수 있도록 선택한 하나의 조합이다.

~~~bash
python3 --version
java -version
python3 -m venv /tmp/netai-spark-lab-venv
source /tmp/netai-spark-lab-venv/bin/activate
python -m pip install -r learning/apache-spark/examples/requirements.txt
python learning/apache-spark/examples/batch_sensor_lab.py
~~~

가상 환경은 이 실습의 Python 패키지를 다른 프로젝트와 분리하는 디렉터리다. JAVA_HOME은 JDK 설치 디렉터리를 가리켜야 하며 java 실행 파일 자체를 가리키는 값이 아니다. 위 명령은 사용자가 실행할 재현 절차다. 이 원고에서 설치와 실행을 실측했다고 주장하지 않는다.

프로그램은 SparkSession을 다음 의미로 설정한다.

| 설정 | 실제 대상 | 이 실습에서 필요한 이유 |
|---|---|---|
| master=local[2] | 로컬 Task 실행 스레드 | 최대 두 Task의 병렬 실행을 관찰 |
| appName | Spark Application 이름 | 로그와 UI에서 실행 식별 |
| spark.ui.enabled=false | 로컬 웹 UI | 짧은 실습에서 포트 사용을 피함 |
| session.timeZone=UTC | SQL 시간 해석 기준 | 실행 머신의 지역 시간대 차이를 줄임 |
| shuffle.partitions=4 | Shuffle 뒤 기본 Partition 후보 수 | 작은 입력에서도 재분배 구조 관찰 |

shuffle.partitions가 4라고 최종 파일이 반드시 네 개가 되는 것은 아니다. Adaptive Query Execution, 줄여서 AQE가 작은 Shuffle Partition을 합칠 수 있고, 뒤의 Join과 Writer가 Partition 구성을 바꿀 수도 있다.

## 3. 스키마와 여섯 입력 행

**스키마**는 각 열의 이름, 자료형, NULL 허용 여부를 적은 구조다. 프로그램의 스키마는 다음과 같다.

| 열 | 자료형 | NULL 허용 | 의미 |
|---|---|---|---|
| event_id | string | 아니오 | 원천 사건을 구분하는 교육용 ID |
| sensor_id | string | 아니오 | 센서 식별자 |
| temperature | double | 예 | 섭씨라고 가정한 측정값 |

**NULL**은 값이 없거나 알려지지 않았음을 나타낸다. 숫자 0과 다르다. e6의 NULL을 0도로 바꾸면 "측정 실패"를 "정확히 0도 측정"으로 바꾸게 된다.

모든 입력은 다음 여섯 행이다.

| 행 | event_id | sensor_id | temperature | 필터 판정 |
|---:|---|---|---:|---|
| 1 | e1 | S1 | 20.0 | 유효 |
| 2 | e2 | S1 | 22.0 | 유효 |
| 3 | e3 | S2 | 19.0 | 유효 |
| 4 | e4 | S2 | 99.0 | 범위 밖 |
| 5 | e5 | S3 | 23.0 | 유효 |
| 6 | e6 | S3 | NULL | 결측 |

위치 DataFrame의 모든 입력은 S1=north, S2=south, S3=west 세 행이다. 이 표는 sensor_id가 유일하다. 만약 S1 위치가 두 행이면 S1 요약 한 행이 Join 후 두 행으로 늘어난다.

## 4. 필터의 논리와 네 행

프로그램의 유효성 조건은 temperature가 NULL이 아니고 -40 이상 60 이하인 것이다.

~~~python
valid = raw.filter(
    F.col("temperature").isNotNull()
    & F.col("temperature").between(-40.0, 60.0)
)
~~~

and의 양쪽을 모두 만족해야 한다. e4=99는 NULL이 아니지만 범위를 넘으므로 제거된다. e6=NULL은 비교 결과가 true가 아니므로 제거된다. 남는 event_id는 e1, e2, e3, e5이며 valid_rows=4다.

Spark가 99를 자동으로 이상치라고 판단한 것이 아니다. 사용자가 -40과 60을 업무 규칙으로 적었다. 이 범위가 실제 센서와 연구 목적에 맞는지는 데이터 소유자가 정해야 한다.

필터는 **transformation, 변환**이다. 호출 순간 전체 여섯 행 계산을 끝냈다는 뜻이 아니다. raw.count와 valid.count 같은 **Action**이 결과를 요구할 때 Job이 시작된다. 이 코드에는 여러 Action이 있으므로 Application 전체에 Job이 정확히 하나라고 예상해서는 안 된다.

## 5. Partition을 가정하고 Task를 손으로 실행하기

createDataFrame의 실제 Partition 배치는 로컬 기본 병렬성과 실행 환경의 영향을 받을 수 있다. 원리를 설명하기 위해 다음 두 입력 Partition을 가정한다.

| Partition | 포함 행 |
|---|---|
| P0 | e1 S1 20, e2 S1 22, e3 S2 19 |
| P1 | e4 S2 99, e5 S3 23, e6 S3 NULL |

Stage의 Task 수는 보통 그 Stage 입력 Partition 수와 연결된다. P0를 처리하는 Task T0와 P1을 처리하는 Task T1이 local[2]의 두 스레드에서 동시에 실행될 수 있다.

T0는 세 행 모두 필터를 통과시킨다. 센서별 부분 집계 상태는 S1=(sum 42, count 2), S2=(sum 19, count 1)다. T1은 e4와 e6를 제거하고 e5만 남겨 S3=(sum 23, count 1)을 만든다.

**부분 집계 상태**는 최종 평균 자체가 아니라 다른 Partition의 상태와 합칠 수 있는 중간 값이다. 평균은 sum/count이므로 sum과 count를 보존해야 한다. 이 예에서는 각 센서가 한 입력 Partition에만 있지만, S1 행이 P0와 P1에 나뉘었다면 두 상태를 합쳐야 한다.

## 6. Shuffle과 Stage 경계

**Shuffle**은 같은 sensor_id의 값을 같은 후속 Partition으로 모으기 위해 네트워크 또는 로컬 블록 전송 경로로 재분배하는 과정이다. 로컬 모드에서는 한 머신 안에서 일어나도 논리적 Shuffle 경계는 존재한다.

물리 계획에서 **Exchange**는 필요한 데이터 분포를 만드는 연산이다. Exchange 앞의 Stage는 입력을 읽고 필터와 부분 집계를 수행한다. Exchange 뒤 Stage는 동일 sensor_id의 상태를 합쳐 최종 집계를 만든다.

~~~mermaid
flowchart LR
    P0["P0: e1,e2,e3"] --> T0["Task T0: filter + partial aggregate"]
    P1["P1: e4,e5,e6"] --> T1["Task T1: filter + partial aggregate"]
    T0 --> X["Exchange: sensor_id별 재분배"]
    T1 --> X
    X --> F["Final aggregate"]
    F --> J["locations와 inner join"]
    J --> W["Parquet write"]
~~~

shuffle.partitions=4는 Exchange 뒤 네 개의 논리 Partition 후보를 만든다. 센서 키는 세 개뿐이라 빈 Partition이 생길 수 있고 AQE가 작은 Partition을 합칠 수 있다. 따라서 이 설정만 보고 Task와 파일 수를 단정하지 않는다.

## 7. 집계와 Join의 모든 결과

집계 코드는 count(*)와 avg(temperature)를 만든다.

| sensor_id | 입력 값 | valid_count | avg_temperature 계산 | 결과 |
|---|---|---:|---|---:|
| S1 | 20, 22 | 2 | (20+22)/2 | 21.0 |
| S2 | 19 | 1 | 19/1 | 19.0 |
| S3 | 23 | 1 | 23/1 | 23.0 |

그다음 locations와 sensor_id로 inner join한다. **Inner join**은 양쪽에 키가 있는 행만 남긴다. 세 센서 모두 위치 표에 있으므로 세 행이 남는다.

| sensor_id | site | valid_count | avg_temperature |
|---|---|---:|---:|
| S1 | north | 2 | 21.0 |
| S2 | south | 1 | 19.0 |
| S3 | west | 1 | 23.0 |

locations에서 S3를 제거하면 S3 요약은 Join에서 사라진다. 집계 성공과 Join 뒤 행 보존은 별도 조건이다. 위치 표의 키 유일성과 누락을 검사해야 한다.

## 8. 코드의 Action과 예상 출력

프로그램의 주요 Action은 다음과 같다.

1. raw.count가 raw_rows=6을 만든다.
2. valid.count가 valid_rows=4를 만든다.
3. summary.explain은 계획을 출력한다. 모드와 버전에 따라 일부 준비 작업이 있을 수 있다.
4. result.orderBy(...).collect가 세 결과 행을 Driver로 가져온다.
5. result.write.parquet가 파일 쓰기 Job을 시작한다.
6. spark.read.parquet(...).orderBy(...).collect가 기록 결과를 다시 읽는다.

예상 핵심 출력은 다음이다.

~~~text
raw_rows=6, valid_rows=4
S1 site=north valid_count=2 avg_temperature=21.0
S2 site=south valid_count=1 avg_temperature=19.0
S3 site=west valid_count=1 avg_temperature=23.0
parquet_roundtrip_rows=3
~~~

세 행 collect는 이 실습에서 작다. 원본 전체가 수억 행이 된 뒤 같은 collect를 쓰면 Driver 메모리를 고갈시킬 수 있다. 작은 결과 검증 방법을 큰 데이터 수집 습관으로 확대하지 않는다.

## 9. explain에서 읽어야 할 객체

summary.explain("formatted")는 물리 계획을 사람이 읽을 수 있는 형식으로 출력한다. 다음 의미를 찾는다.

| 계획 요소 | 이 실습에서 하는 일 |
|---|---|
| ExistingRDD 또는 Scan 계열 | 여섯 행의 입력 관계를 읽음 |
| Filter | NULL과 범위 밖 행 제거 |
| HashAggregate의 partial 단계 | Partition 안에서 sum/count 상태 생성 |
| Exchange | sensor_id 기준으로 상태 재분배 |
| HashAggregate의 final 단계 | 센서별 최종 count와 평균 생성 |
| AdaptiveSparkPlan | 실행 통계를 반영할 수 있는 AQE 포장 |

Join은 result 계획에 있으므로 summary만 explain하면 위치 Join이 보이지 않을 수 있다. summary 계획과 result 계획은 다르다. 어떤 DataFrame 변수에 explain을 호출했는지 함께 기록해야 한다.

연산자 문자열과 Stage 번호는 버전과 설정에 따라 달라진다. Filter와 Exchange의 의미를 읽는 것이 중요하며, 예시 출력 한 줄을 정답 문자열로 고정하면 업그레이드 시 잘못된 실패가 된다.

## 10. 두 assertion이 실제로 검증하는 범위

첫 assertion은 collect한 세 행을 다음 expected 사전과 비교한다.

~~~python
expected = {
    "S1": ("north", 2, 21.0),
    "S2": ("south", 1, 19.0),
    "S3": ("west", 1, 23.0),
}
assert len(rows) == 3 and actual == expected
~~~

이 검사는 센서 ID, 위치, 유효 행 수, 평균이 작은 고정 입력에서 정확한지 확인한다. orderBy 뒤 행을 사전으로 바꾸므로 출력 순서 자체보다 키와 값에 집중한다.

두 번째 assertion은 Parquet를 다시 읽은 행 목록이 쓰기 전 rows와 같은지 확인한다.

~~~python
assert reread == rows
~~~

이 검사는 임시 경로에 쓴 세 결과가 같은 Spark 실행에서 다시 읽혔음을 확인한다. 객체 저장소의 장기 내구성, 장애 중 Commit, 다른 Spark 버전의 호환성, Iceberg Snapshot 원자성을 검증하지 않는다.

부동소수점 평균을 일반 연구 데이터에서 정확한 ==로 비교하면 연산 순서 차이 때문에 문제가 될 수 있다. 이 입력은 작은 정수성 값이라 21.0, 19.0, 23.0이 정확히 표현된다. 일반 실험에서는 허용 오차와 NaN 정책을 명시한다.

## 11. Parquet 쓰기와 Commit

프로그램은 TemporaryDirectory 아래 sensor_summary에 mode("errorifexists")로 쓴다. **Parquet**은 열 단위 저장 파일 형식이다. **Writer Task**는 자기 출력 Partition의 행을 임시 또는 작업 경로에 파일로 만든다. 파일이 하나 보인다는 사실만으로 전체 쓰기가 성공했다고 판단하지 않는다. Spark의 파일 출력 Commit 과정이 모든 성공 Task의 결과를 공개 가능한 상태로 마쳐야 한다.

TemporaryDirectory는 Python 문맥을 벗어나면 제거된다. 따라서 이 실습은 영구 연구 결과를 보존하지 않는다. 기존 경로를 덮어쓰지 않도록 errorifexists를 사용한다. 출력 파일 수는 Partition, AQE, Writer 동작에 따라 달라지며 Executor 수와 동일하지 않다.

Parquet round trip은 행 의미를 확인하지만 테이블 트랜잭션을 제공하지 않는다. Iceberg 같은 테이블 포맷을 사용할 때는 파일뿐 아니라 Metadata와 Snapshot Commit을 함께 봐야 한다.

## 12. 실패가 난 위치별로 상태를 추적하기

P1의 Task가 e5 부분 상태를 만든 뒤 실패했다고 하자. Driver는 같은 논리 Task의 새 attempt를 실행할 수 있다. 입력 DataFrame과 lineage가 남아 있으므로 e4,e5,e6에서 다시 필터와 부분 집계를 수행한다.

Shuffle 출력이 만들어진 Executor가 사라지면 후속 Stage가 그 블록을 읽지 못할 수 있다. 그러면 필요한 이전 Stage Task를 다시 실행해 블록을 재생성한다. local 모드는 별도 Executor 프로세스 유실을 그대로 재현하지 않는다.

Writer Task가 파일을 만든 뒤 Job Commit 전에 실패하면 임시 파일이 남을 수 있다. 프로그램은 "파일이 존재하는가"와 "Job이 성공했는가"를 구분해야 한다. 외부 API 호출처럼 Spark가 관리하지 않는 부작용은 Task 재시도로 중복될 수 있으므로 고유 요청 ID와 멱등한 쓰기 계약이 필요하다.

## 13. 스트리밍 실습이 보여 주는 범위

streaming_rate_lab.py의 rate Source는 실제 센서가 아니라 timestamp와 증가하는 value를 만드는 합성 입력이다. rowsPerSecond=2, numPartitions=2이며 value를 3으로 나눈 나머지로 S1, S2, S3을 만든다. 2초 Trigger는 약 2초마다 Micro-batch 실행을 시도한다.

~~~bash
python learning/apache-spark/examples/streaming_rate_lab.py
~~~

예상 관찰은 Batch: 0, Batch: 1 같은 구분과 timestamp, value, sensor_id 열이다. 시작 준비 시간 때문에 최초 Batch가 비거나 각 Batch 행 수가 정확히 4가 아닐 수 있다. rowsPerSecond는 목표 생성률이지 매 Trigger의 고정 행 수 계약이 아니다.

Checkpoint는 TemporaryDirectory 안에 있다. 프로그램 종료 후 삭제되므로 다음 실행은 이전 offset과 state를 복구하지 못한다. Console Sink는 화면 학습용이며 업무 저장소의 Exactly-once 효과를 증명하지 않는다. 재시작 연구에는 지속 Checkpoint, 같은 Query 의미, 호환되는 State Schema, Source Offset, Sink Commit을 함께 보존해야 한다.

## 14. 입력을 바꿀 때 예상되는 결과

e4를 25로 바꾸면 valid_rows=5다. S2의 값은 19와 25이므로 valid_count=2, 평균=(19+25)/2=22다.

locations에 (S1, backup) 행을 추가하면 S1 요약 한 행이 두 위치 행과 각각 결합해 두 행으로 늘어난다. 전체 Join 결과는 4행이다. 이는 Spark 오류가 아니라 다대다 Cardinality의 결과다.

shuffle.partitions를 4에서 8로 바꾸어도 행 의미가 같다면 세 센서 평균은 같아야 한다. 물리 Partition과 Task 수, 빈 Partition 수, AQE의 합치기 결정은 달라질 수 있다.

필터에서 isNotNull을 빼더라도 between의 NULL 결과는 unknown이어서 e6은 filter를 통과하지 않는다. 그러나 명시적 NULL 검사는 품질 규칙을 독자가 바로 읽게 하고, 별도 결측 건수 계산을 설계하기 쉽게 한다.

## 15. 실습 문제와 완전 풀이

### 문제 1
여섯 행 중 유효 event_id와 개수를 구하라.

**풀이:** e4는 99라 상한 60을 넘고 e6는 NULL이다. 남는 e1,e2,e3,e5 네 행이므로 valid_rows=4다.

### 문제 2
P0에 e1,e2,e3이 있을 때 부분 상태를 구하라.

**풀이:** S1은 sum=20+22=42, count=2다. S2는 sum=19, count=1이다. 평균만 저장하지 않고 sum/count를 저장해야 다른 Partition 상태와 정확히 합칠 수 있다.

### 문제 3
S3의 최종 평균과 위치는 무엇인가?

**풀이:** e6은 제거되고 e5=23만 남는다. 평균은 23/1=23.0이며 locations의 S3=west와 Join해 west가 된다.

### 문제 4
local[2]와 shuffle.partitions=4이면 서버와 출력 파일이 각각 2개와 4개인가?

**풀이:** 아니다. local[2]는 한 머신의 Task 스레드 수이고 Shuffle Partition은 재분배 뒤 논리 조각 후보 수다. AQE와 Writer 때문에 출력 파일 수는 달라질 수 있다.

### 문제 5
result.collect가 안전한 이유와 위험해지는 조건은 무엇인가?

**풀이:** 현재 결과는 센서별 세 행뿐이라 작다. 센서 수나 결과 폭이 Driver 메모리를 넘을 만큼 커지면 모든 행을 모으는 collect가 Driver OOM을 일으킬 수 있다. 분산 저장이나 제한된 표본을 사용한다.

### 문제 6
첫 assertion이 통과하면 Kubernetes 장애 복구도 검증한 것인가?

**풀이:** 아니다. assertion은 고정 여섯 행의 값만 검증한다. local 모드는 별도 노드, 네트워크 단절, Pod 권한과 재스케줄링을 재현하지 않는다.

### 문제 7
Parquet 파일이 보이면 Write가 Commit됐다고 결론내릴 수 있는가?

**풀이:** Task가 만든 파일과 Job Commit은 다른 상태다. Job 성공 상태와 다시 읽은 결과를 확인해야 한다. Iceberg라면 Snapshot Metadata Commit도 따로 확인한다.

### 문제 8
e4를 25로 바꾸면 S2와 전체 출력은 어떻게 변하는가?

**풀이:** e4가 유효해져 valid_rows=5다. S2 count=2, avg=22가 된다. 센서 키 수는 여전히 세 개이고 위치 키도 모두 있으므로 Join 결과와 roundtrip 행 수는 3이다.

## 16. 실행 실패 시 확인 순서

| 증상 | 실제로 확인할 객체 |
|---|---|
| Java Gateway 시작 실패 | java -version, JAVA_HOME, PySpark 지원 JDK |
| pyspark import 실패 | 활성 Python 경로와 설치한 가상 환경 |
| assertion 실패 | 입력 여섯 행, 필터, 위치 키 중복, NULL 처리 |
| 출력 파일 수 차이 | 실제 물리 계획, AQE, 출력 Partition |
| 첫 실행만 느림 | JVM 시작, 코드 생성, 파일 시스템 준비 |
| Streaming 재시작이 이어지지 않음 | Temporary checkpoint가 삭제되었는지 |
| 평균은 맞지만 행 수 증가 | Join 키의 중복과 Cardinality |

공식 계약은 [Spark 4.0.4 PySpark 설치](https://spark.apache.org/docs/4.0.4/api/python/getting_started/install.html), [DataFrame 빠른 시작](https://spark.apache.org/docs/4.0.4/api/python/getting_started/quickstart_df.html), [Structured Streaming](https://spark.apache.org/docs/4.0.4/streaming/index.html)을 기준으로 했다.

[이전: 배포와 Connect](10-deployment-and-connect.md) · [목차](README.md) · [다음: 연구 데이터 처리](12-research-workflows.md)
