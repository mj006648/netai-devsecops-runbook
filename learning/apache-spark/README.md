# 처음부터 배우는 Apache Spark

**데이터가 여러 파일과 서버에 나뉘어 있을 때, 누가 어떤 순서로 읽고 계산하고 저장하는가?** 이 책은 작은 센서 테이블에서 시작해 그 질문을 Spark의 실행 계획·프로세스·작업·메모리·파일로 펼친다. Python과 SQL을 처음 접하는 독자도 용어부터 배우고, 이미 Iceberg를 공부했다면 실제 읽기·쓰기 엔진의 동작으로 연결할 수 있다.

자료 확인 기준일은 **2026-10-09**다. 최신 Spark의 공식 릴리스 설명과 재현 실습의 버전을 구분한다. 최신 기능은 [13장](13-versions-and-migration.md)에서 다루고, 실행 실습은 앞서 사용한 **PySpark 4.0.4·Java 21** 조합으로 고정한다. Iceberg 1.12.0의 runtime 지원 범위와 최신 Spark 릴리스는 별도 축이다. 가장 큰 버전 번호끼리 무조건 조합하지 않는다.

![Spark의 driver와 executor, 자원 관리자, 데이터 저장소의 역할](assets/architecture.svg)

## 왜 연구에서 중요한가

Iceberg가 파일과 스냅샷으로 테이블 상태를 관리하면, Spark는 그 테이블을 **실제로 읽고 변환하고 집계하고 수정하는 엔진**이 될 수 있다. 처리 시간, shuffle, 메모리 사용, 파일 크기, task 실패, 재처리 결과를 설명하려면 테이블 포맷과 실행 엔진을 함께 이해해야 한다.

이 저장소의 기존 [Spark 운영 문서](../../kubernetes/observability/data-pipelines/06-spark.md)는 batch archive와 Structured Streaming을 통한 Iceberg 적재를 학습용 설계로 설명한다. 새 교재는 그 앞에 필요한 실행 원리를 자세히 다룬다. 문서에 있는 설계 예시를 연구실에서 실제 실행한 현황으로 단정하지 않는다.

모든 데이터 처리에 Spark를 사용할 필요는 없다. 입력이 작은 경우 분산 작업 준비 비용이 계산보다 클 수 있다. 연구에서 중요한 것은 “Spark를 사용했다”보다 **왜 이 실행 방식이 필요한지, 결과가 맞는지, 병목과 실패 조건이 무엇인지** 설명하는 능력이다. 연구 연결은 [12장](12-research-workflows.md)에 있다.

## 한 권의 목차

| 장 | 시작 질문 | 배우는 내용 |
| --- | --- | --- |
| [00. 데이터에서 Spark까지](00-data-to-spark.md) | 파일을 여러 컴퓨터에서 계산하면 무엇이 어려울까? | 행·열·SQL·Python·배치·분산 처리와 역할 구분 |
| [01. Driver와 executor](01-driver-executor.md) | 내 Python 코드와 실제 계산은 어디에서 실행될까? | application·프로세스·JVM·driver·executor·cluster manager |
| [02. DataFrame과 SQL](02-dataframes-sql.md) | 표에 계산을 표현하는 방법은 무엇일까? | schema·타입·null·필터·컬럼·집계·SQL과 API |
| [03. 지연 실행과 DAG](03-lazy-dag-jobs-stages.md) | 코드를 썼는데 왜 아직 계산하지 않을까? | logical/physical plan·action·job·stage·task·lineage |
| [04. Partition과 shuffle](04-partitions-and-shuffle.md) | 같은 장치의 기록을 어떻게 같은 곳으로 모을까? | 분할·좁은/넓은 의존성·재분배·spill·skew |
| [05. Join과 AQE](05-joins-and-aqe.md) | 다른 테이블을 붙일 때 왜 행과 비용이 늘어날까? | join 의미·broadcast·sort-merge·실행 중 계획 조정 |
| [06. 메모리와 성능](06-memory-and-performance.md) | 데이터보다 RAM이 작으면 못 쓰는가? | heap·Python worker·cache·OOM·UI·측정과 진단 |
| [07. 읽기와 쓰기](07-reading-and-writing.md) | Partition 수가 출력 파일 수인가? | CSV/JSON/Parquet·pruning·파일 배치·쓰기 모드·커밋 |
| [08. Structured Streaming](08-structured-streaming.md) | 끝없이 들어오는 데이터는 어떻게 처리할까? | micro-batch·시간·watermark·state·checkpoint·보장 범위 |
| [09. Spark와 Iceberg](09-iceberg-integration.md) | DELETE 조건이 어떻게 COW·MOR·DV가 될까? | runtime·catalog·포맷·메타데이터·삭제·지원 조합 |
| [10. 배포와 Spark Connect](10-deployment-and-connect.md) | 노트북·클러스터·Kubernetes 실행은 무엇이 다를까? | local·standalone·YARN·Kubernetes·client/cluster·Connect |
| [11. 로컬 실습](11-local-labs.md) | CPU 한 대로 실행 계획과 결과를 볼 수 있을까? | 실제 PySpark 프로그램·예상 결과·파일·배치·스트리밍 |
| [12. 연구 데이터 처리](12-research-workflows.md) | NetAI·센서·학습 데이터 연구에 어떻게 연결할까? | 적재·정제·물리화·재현성·실험 설계·주장의 경계 |
| [13. 버전과 마이그레이션](13-versions-and-migration.md) | 최신 Spark로 올리면 무엇을 다시 확인할까? | 3.5·4.x·최신 릴리스·Java/Python/Scala·ANSI·호환성 |
| [14. 문제·해설·용어사전](14-exercises-and-glossary.md) | 단어를 외운 것과 동작을 이해한 것을 어떻게 구분할까? | 계산 문제·반례·연구 과제·공식 문서 지도 |

## 읽는 순서

처음이라면 **00 → 01 → 02 → 03**으로 시작한다. 이어 **11장의 배치 실습**을 실행해 표와 실행 계획을 확인한다. 한 줄의 `groupBy`가 왜 여러 작업과 데이터 이동으로 바뀌는지 궁금하면 04·05로 이동한다.

Iceberg 연구와 연결하려면 **07 → 09 → [Iceberg 교재](../apache-iceberg/README.md)**를 함께 읽는다. 데이터가 계속 들어오는 경로는 08, 실제 실행 환경은 10, 성능과 연구 주장은 06·12에서 연결한다.

```mermaid
flowchart LR
    A["00~03: 데이터와 실행의 원리"] --> L["11: 작은 로컬 실행"]
    A --> P["04~07: 분산 처리·성능·파일"]
    L --> P
    P --> I["09: Iceberg 읽기·쓰기"]
    P --> S["08·10: 스트리밍·배포"]
    I --> R["12~14: 연구·버전·문제"]
    S --> R
```

## 예시와 실행 환경을 읽는 법

개념 장의 센서 데이터는 직접 만든 교육용 예시다. 11장의 실습도 작은 교육용 입력을 사용하며 정확한 값은 해당 장의 표를 따른다. 도식의 시간·파일 크기·스냅샷 번호는 실제 측정과 구분해 표시한다. 이를 연구실의 실측 성능이나 현재 운영 상태로 인용하지 않는다.

`sql`은 SQL 문법, `bash`는 셸 명령, `text`는 출력·설정 예시·설명용 코드다. 설치와 실행 순서는 11장에서 따른다. Python 라이브러리가 필요한 실행 예제는 [examples](examples/)의 파일로 제공한다. SVG를 크게 보려면 [그림 목록](assets/README.md)을 연다.

## 기존 자료와 연결

- 파일과 저장 원리는 [데이터 시스템 교재](../../kubernetes/storage/data-systems-foundations/README.md).
- 테이블과 삭제·스냅샷은 [Iceberg 교재](../apache-iceberg/README.md).
- 학습 입력과 GPU의 관계는 [AI 인프라 교재](../../ai/learning/ai-infrastructure/README.md).
- 전체 적재 설계는 [관측 데이터 파이프라인](../../kubernetes/observability/data-pipelines/README.md).

[통합 learning 목차](../README.md) · [첫 장 시작](00-data-to-spark.md)
