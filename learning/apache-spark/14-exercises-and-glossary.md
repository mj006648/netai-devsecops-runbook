# 14. 문제·해설·용어사전

[이 책의 목차](README.md) · [이전 장](13-versions-and-migration.md)

코드의 줄 수 대신 실제 행·파일·task·상태를 계산한다. 먼저 답을 가리고 손으로 표와 화살표를 그려 본다. 숫자는 교육용이다.

## 1. 계산과 실행 문제

### 문제 1. 평균의 평균

Partition A에는 값 10 하나, B에는 값 20 세 개가 있다. 부분 평균을 단순 평균한 결과와 전체 평균은 각각 얼마인가?

**해설.** 부분 평균의 평균은 `(10+20)/2=15`, 전체 평균은 `(10+20+20+20)/4=17.5`다. 전체 평균을 합치려면 sum과 유효 count 등 필요한 상태를 보존한다.

### 문제 2. NULL과 0

온도 `20, 22, NULL`에 `COUNT(*)`, `COUNT(temperature)`, `AVG(temperature)`를 적용한다. NULL을 0으로 채운 뒤 평균은 어떻게 달라지는가?

**해설.** 3, 2, 21이다. 0으로 채우면 평균은 14다. 누락값 정책이 결과를 바꾼다.

### 문제 3. 지연 실행

`clean = raw.filter(...)`와 `summary = clean.groupBy(...).agg(...)`를 실행했다. 결과가 파일로 저장되었다고 주장해도 되는가?

**해설.** 아니다. 계산 표현 구성과 데이터 실행·영구 저장은 다르다. 파일 목록·schema 작업 등이 발생할 수 있지만 결과 쓰기의 증거가 아니다.

### 문제 4. Task 동시성

Executor 3개, 각각 4코어, task당 1 CPU, 다른 제한 없음이라고 가정한다. 120개 task의 최대 동시 실행 수와 균등한 단순 실행 차수는?

**해설.** 최대 약 12개, 모든 task가 같은 시간이라면 10차수다. 실제 I/O·skew·동적 할당은 별도다.

### 문제 5. Job 수

`show()` 하나를 호출했으니 Spark job이 반드시 하나라고 할 수 있는가?

**해설.** 아니다. Broadcast 준비·AQE·내부 실행 경로 등에 따라 여러 job이 생길 수 있다. UI·물리 계획으로 확인한다.

## 2. Join·partition·메모리 문제

### 문제 6. Join 후 행 증가

Events에 S1 두 행, S2 한 행이 있다. Devices에 S1 두 행, S2 한 행이 있다. `device_id`로 inner join하면 몇 행인가?

**해설.** S1은 `2×2=4`, S2는 `1×1=1`, 합계 5다. Join key의 중복은 결과를 곱셈으로 늘릴 수 있다. Devices가 한 장치당 한 행인지 검사한다.

### 문제 7. 파일 수

DataFrame을 `repartition(4)`하고 날짜 두 종류로 `partitionBy("date")` 저장했다. 파일 수가 반드시 4인가?

**해설.** 아니다. 실행 partition과 저장 partition의 조합·writer 규칙에 따라 달라진다. 실제 파일과 행·bytes를 확인한다.

### 문제 8. Driver OOM

Executor 메모리를 두 배로 늘렸지만 `toPandas()`에서 driver가 죽는다. 원인을 해결했다고 볼 수 있는가?

**해설.** 결과를 driver에 모으는 경로는 남아 있다. 분산 결과 저장·작은 요약·제한된 출력 등 요청 자체를 바꿀 필요가 있다.

### 문제 9. Partition 평균 크기

Partition 10개 중 9개는 10 MiB, 하나는 910 MiB다. 평균은 얼마이며 평균만으로 task 메모리·시간을 판단해도 되는가?

**해설.** 합계 1000 MiB, 평균 100 MiB다. 910 MiB partition이 지배하는 skew를 평균이 숨긴다.

### 문제 10. Cache

DataFrame을 변수에 넣고 `count()` 다음 `write`를 호출했다. 입력을 반드시 한 번만 읽는가?

**해설.** 변수 할당만으로 cache되지 않는다. Cache의 실제 채움·재사용·eviction과 실행 계획을 확인한다.

## 3. Streaming·Iceberg·버전 문제

### 문제 11. 재전송과 exactly-once

같은 업무 event ID가 Kafka의 서로 다른 offset 두 개에 있다. 각 offset을 정확히 한 번 처리하면 event도 하나만 남는가?

**해설.** 아니다. 원천 중복 제거는 별도 정책이다.

### 문제 12. Checkpoint 삭제

Streaming job의 checkpoint를 지우고 `startingOffsets=earliest`로 다시 시작했다. 이전과 동일한 재시작인가?

**해설.** 새 query로 입력을 다시 읽을 수 있다. 이전 sink 결과와의 중복·state·query ID 정책을 고려한다.

### 문제 13. SQL 조건과 삭제 파일

`DELETE WHERE device_id='S2'`를 썼다. 반드시 equality delete file이 생성되는가?

**해설.** SQL은 삭제할 논리 조건이다. 실제 표현은 엔진·COW/MOR 설정·테이블 포맷·지원 경로에 따라 다르다.

### 문제 14. 최신 버전 조합

Spark 최신 안정 릴리스와 Iceberg 최신 라이브러리를 설치했다. Artifact의 Spark·Scala suffix를 확인하지 않아도 되는가?

**해설.** 아니다. 최신성은 실제 integration 지원을 보장하지 않는다. 이 책은 Spark 최신 설명과 4.0.4+Iceberg1.12.0 실습을 구분한다.

### 문제 15. API 연결 방식

Spark Connect에서 `df._jdf`나 RDD를 이용한 classic 코드를 그대로 실행해도 되는가?

**해설.** Connect의 클라이언트·서버 분리와 지원 API 경계를 확인해야 한다. Driver JVM에 대한 private 접근과 SparkContext/RDD는 classic과 다르다.

## 4. 연구 과제

### 과제 A. 센서 파이프라인 설계

장치 1000대가 분당 사건 하나를 보낸다. 입력은 3일 늦을 수 있고 중복된다. 원본·정제·일별 평균 테이블을 설계한다.

제출할 항목은 source 위치·event ID·시간·단위 계약, schema와 불량 행 정책, partition·파일 크기 후보, streaming checkpoint·sink의 보장, input/output snapshot 기록이다.

**해설 방향.** 하루 1,440,000건이지만 파일 크기는 실제 payload·포맷·압축을 측정해야 한다. 지연·중복·업무 의미를 엔진의 보장으로 대체하지 않는다.

### 과제 B. 성능 가설 하나 검증

동일 snapshot·SQL에서 join 또는 파일 배치 최적화를 비교하는 계획을 쓴다. 수정한 변수 하나와 결과 정확성 기준을 명시한다.

**해설 방향.** Plan, task 분포, 읽기 bytes, shuffle, spill, elapsed time, 자원과 cache 조건을 기록한다. 결과를 다르게 만들고 속도만 비교하면 같은 작업의 비교가 아니다.

### 과제 C. Kubernetes와 Spark 연결

Driver pod 1개와 executor pod 3개를 그림에 배치한다. 각 executor가 4코어·8 GiB heap을 요청한다고 가정한다. Heap 밖 메모리와 container limit, storage 접근, service account, driver 종료와 checkpoint 보존을 설명한다.

**해설 방향.** Pod와 task는 다른 단위다. Kubernetes는 자원을 배치하고 Spark는 계산을 계획한다. Container 재시작과 sink의 단 한 번 효과도 다른 계약이다.

## 5. 용어사전

| 용어 | 뜻 | 장 |
| --- | --- | --- |
| Application | Driver와 executor들로 이루어진 Spark 실행 프로그램 | 01 |
| Driver | 사용자 흐름·계획·task 조정 주체 | 01 |
| Executor | Task와 cache·shuffle을 처리하는 실행 프로세스 | 01 |
| Cluster manager | Application의 실행 자원 관리자 | 01·10 |
| JVM | Java·Scala 등의 코드를 실행하는 환경 | 00·01 |
| PySpark | Python에서 Spark API를 쓰는 인터페이스 | 00·02 |
| SparkSession | SQL·DataFrame·source 접근의 진입점 | 02 |
| DataFrame | 이름과 타입을 가진 컬럼으로 계산을 표현 | 02 |
| Schema | 컬럼 이름·타입·nullable 구조 | 02 |
| NULL | 값 없음·알 수 없음의 표현 | 02 |
| RDD | Lineage를 가진 분산 데이터 추상화 | 02·03 |
| Lazy evaluation | 결과 요청 전 변환의 표현을 구성하는 실행 모델 | 03 |
| Action | 결과 실행을 요청하는 연산 | 03 |
| Logical plan | 무엇을 계산할지의 표현 | 03 |
| Physical plan | 어떻게 계산할지의 실행 전략 | 03 |
| Catalyst | Spark SQL 계획 분석·최적화 프레임워크 | 03 |
| DAG | 순환 없는 방향 의존 그래프 | 03 |
| Job | 실행 요청에서 생기는 병렬 계산 작업 | 03 |
| Stage | Shuffle 등의 경계로 나뉜 task 집합 | 03 |
| Task | Stage의 데이터 조각을 처리하는 실행 단위 | 03 |
| Partition | 맥락에 따라 실행 조각 또는 저장 묶음 | 04·07 |
| Shuffle | 필요한 분포로 데이터를 재분배 | 04 |
| Exchange | 물리 계획에서 분포 변경을 나타내는 연산 | 03·04 |
| Skew | Key·partition·task 부하의 치우침 | 04·06 |
| Join | Key·조건으로 두 입력 행을 연결 | 05 |
| Broadcast | 작은 입력을 task 쪽으로 전달하는 전략 | 05 |
| AQE | Runtime 통계를 이용한 적응적 계획 조정 | 05 |
| Heap | JVM이 객체를 관리하는 메모리 영역 | 06 |
| Spill | 메모리 압박 시 중간 데이터를 디스크 등에 내려놓기 | 06 |
| GC | 사용하지 않는 JVM 객체의 메모리 회수 | 01·06 |
| Cache/Persist | 재사용할 계산 결과 보관 | 03·06 |
| UDF | 사용자 정의 함수 | 06 |
| Arrow | 컬럼 데이터의 메모리·교환 표현 | 06·13 |
| Row group | Parquet 파일 내부의 행 묶음 | 07 |
| Pushdown / Pruning | 아래 읽기 단계에 조건 전달 / 후보 제외 | 03·07 |
| Micro-batch | 작은 입력 묶음의 반복 실행 | 08 |
| Watermark | 늦은 데이터 처리·state 정리의 진행 기준 | 08 |
| State | 이후 입력 처리에 필요한 누적 계산 상태 | 08 |
| Checkpoint | 복구를 위한 진행·상태 저장 | 03·08 |
| Idempotency | 재시도에도 원하는 효과가 중복되지 않는 성질 | 01·08 |
| Catalog | 테이블 이름과 metadata·commit의 진입점 | 09 |
| COW/MOR | 파일 재작성 / 읽기 시 삭제 정보 반영 | 09 |
| Spark Connect | 논리 계획을 서버에 전달하는 분리 클라이언트 모델 | 10 |
| Materialization | 계산 결과를 실제 저장 데이터로 만들기 | 12 |
| Data leakage | 평가 시 알 수 없는 정보가 학습·feature에 유입 | 12 |

## 6. 공식 자료 지도

| 자료 | 읽을 내용 |
| --- | --- |
| [Spark 4.2.0 docs](https://spark.apache.org/docs/4.2.0/) | 최신 안정 릴리스의 문서 진입점 |
| [Spark 4.0.4 docs](https://spark.apache.org/docs/4.0.4/) | 이 책의 실습 버전 |
| [Cluster overview](https://spark.apache.org/docs/4.2.0/cluster-overview.html) | Driver·executor·task |
| [SQL programming](https://spark.apache.org/docs/4.2.0/sql-programming-guide.html) | DataFrame·SQL |
| [RDD programming](https://spark.apache.org/docs/4.2.0/rdd-programming-guide.html) | Lazy·lineage·RDD |
| [SQL performance](https://spark.apache.org/docs/4.2.0/sql-performance-tuning.html) | Join·AQE·partition·통계 |
| [Tuning](https://spark.apache.org/docs/4.2.0/tuning.html) | Memory·shuffle·직렬화 |
| [Monitoring](https://spark.apache.org/docs/4.2.0/monitoring.html) | UI·event log |
| [Structured Streaming](https://spark.apache.org/docs/4.2.0/streaming/index.html) | Source·state·checkpoint·sink |
| [Spark Connect](https://spark.apache.org/docs/4.2.0/spark-connect-overview.html) | Client/server·API 경계 |
| [Spark on Kubernetes](https://spark.apache.org/docs/4.2.0/running-on-kubernetes.html) | Pods·자원·인증·배포 |
| [Iceberg multi-engine support](https://iceberg.apache.org/multi-engine-support/) | Runtime artifact 호환성 |

## 7. 이 책에서 실행한 범위

실제 실행 예제와 명령은 [11장](11-local-labs.md)에 있다. Local CPU 실습의 행 결과와 파일 round-trip을 실제 실행한 것과, 분산 클러스터·Kubernetes·Kafka·장애 실험의 설명·예상 결과를 구분한다. 최신 Spark 기능을 모든 connector에서 실행한 것으로 해석하지 않는다.

[교재 처음으로](README.md) · [통합 learning 목차](../README.md)
