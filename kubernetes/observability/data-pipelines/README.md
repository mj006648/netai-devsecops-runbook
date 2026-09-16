# 운영 데이터 파이프라인 학습 자료

현재 경로: Airflow · OpenTelemetry · Prometheus · Loki · Tempo · Grafana

장기 분석: Kafka · Spark · Iceberg / 대안 학습: Flink · OpenSearch · Data Prepper

**한국어 학습 경로 — 개념부터 내부 동작, 장애·복구, 설계와 검증까지**

- 정리 기준: 2026-09-15
- 대상: Kubernetes와 데이터 레이크하우스의 기본 개념은 접했지만 관측·스트리밍 도구의 역할이 혼동되는 개발자·연구자
- 목적: 특정 도구를 무조건 도입하는 것이 아니라, 어떤 요구에 어떤 도구가 필요한지 설명하고 검증할 수 있게 되기
- 범위: 공개 문서 기반 학습 자료. 예시 아키텍처가 현재 NetAI/Trident에 구현·배포됐다는 뜻은 아니다.

## 최신 학습 순서

현재 운영 방향은 [12장 전체 구성](12-current-architecture.md)에서 시작한다.

1. [OTel](01-opentelemetry.md) → [Prometheus](07-metrics-and-prometheus.md)
2. [Loki·Tempo·Grafana와 선택적 Mimir](11-lgtm-observability.md)
3. [Airflow의 작업 오케스트레이션](10-airflow-orchestration.md)
4. [Kafka](02-kafka.md) → [Spark](06-spark.md) → [Iceberg](05-iceberg.md): 선별한 장기 이력 경로
5. [오프라인 실습](09-labs-and-review.md)

Flink·OpenSearch 장과 기존 통합 예시는 기술 비교·참고용으로 보존한다. 현재 필수 stack 또는 설치 완료 상태를 뜻하지 않는다. [현재 구성과 연구 경계](12-current-architecture.md)를 우선한다.

## 전체 자료 목록

| 순서 | 문서 | 핵심 질문 | 학습 완료 기준 |
| --- | --- | --- | --- |
| 0 | [전체 그림과 공통 개념](00-big-picture.md) | 수집·전달·계산·검색·테이블 관리는 무엇이 다른가? | 도구 이름 없이 데이터 흐름을 설명 |
| 1 | [OpenTelemetry](01-opentelemetry.md) | SDK와 Collector는 각각 무엇을 하는가? | 로그·메트릭·트레이스의 생성부터 전달까지 설명 |
| 2 | [Kafka](02-kafka.md) | partition, offset, consumer group과 replay란? | 메시지 보관과 처리 성공을 구분 |
| 3 | [Flink](03-flink.md) | state, watermark, checkpoint가 왜 필요한가? | 늦은 이벤트·장애 시 계산 결과를 설명 |
| 4 | [OpenSearch와 Data Prepper](04-opensearch-and-data-prepper.md) | 검색 저장과 수집 가공은 어떻게 연결되는가? | 색인·검색 반영·내구성·복구를 구분 |
| 5 | [Apache Iceberg](05-iceberg.md) | 파일 포맷·테이블 포맷·엔진·카탈로그는 무엇이 다른가? | snapshot/manifest/catalog 관계 설명 |
| 6 | [Spark와 증분 archive](06-spark.md) | 배치·micro-batch·checkpoint는 어떻게 동작하는가? | Kafka→Iceberg 재시작·중복 위험 설명 |
| 7 | [메트릭과 Prometheus](07-metrics-and-prometheus.md) | 지표·label·histogram·신선도를 어떻게 읽는가? | 평균/p95·counter reset·stale 문제 식별 |
| 8 | [통합 설계와 선택 기준](08-integration-design.md) | 무엇을 넣고 무엇을 빼야 하는가? | 요구에 맞는 최소 구성과 실패 경계 제시 |
| 9 | [안전한 실습과 종합 복습](09-labs-and-review.md) | 수집·중복·보존·복구를 어떻게 확인하는가? | 오프라인 실습과 검증 계획 작성 |
| 10 | [Airflow](10-airflow-orchestration.md) | 실행·대기·재시도를 어떻게 안전하게 조율하나? | workflow와 실제 자원 제어 책임 구분 |
| 11 | [LGTM 계열 관측](11-lgtm-observability.md) | 로그·메트릭·트레이스를 어디에 저장하나? | 신호별 수집·조회·신선도 설명 |
| 12 | [현재 구성과 연구 방향](12-current-architecture.md) | 현재 선택과 과거 대안은 무엇인가? | 최신 구성의 역할·검증 조건 설명 |

## 추천 학습 방법

### 먼저 개념만 잡기

0장 → 각 장의 처음 요약 → 8장 순서로 읽는다. “OTel이 있으니 Kafka가 필요 없다”, “Iceberg에 넣으려면 Flink가 필수다” 같은 문장을 스스로 검토해 본다.

### 한 도구씩 익히기

1~7장을 읽으면서 구성요소, 데이터 한 건의 이동 경로, 저장되는 상태, 장애 시 재시도 위치를 종이에 그린다. 각 장의 질문을 먼저 풀고 답을 확인한다.

### 설계·논문 준비

8~9장에서 freshness, 손실, 중복, checkpoint, 권한과 자원 비용을 함께 정한다. 실제 서비스 시험을 하기 전에 예상 결과와 실패 판정을 고정한다.

## 이 자료에서 가장 중요한 다섯 문장

1. **OTel은 관측 정보를 계측·수집·전달하는 기반이지 저장·검색 제품 자체가 아니다.**
2. **Kafka는 처리 엔진이 아니라 유한한 보존·전달·재처리 기반이다.**
3. **Flink와 Spark는 처리 엔진이고, OpenSearch는 검색·분석 엔진, Iceberg는 테이블 포맷이다.**
4. **검색 가능, 디스크 영속화, source offset 진행, archive commit, 실제 업무 완료는 서로 다른 시점이다.**
5. **운영 계층은 레이크하우스를 관측·제어하지만, 실시간 동작이 장기 Iceberg 적재 성공을 기다리도록 만들 필요는 없다.**

## 예제와 검증 범위

- 식별자와 수치는 설명용이다. 실제 클러스터 주소·credential·실험 원시 데이터를 포함하지 않는다.
- 9장의 Python 실습은 표준 라이브러리만 사용하는 **오프라인 모형**이다. Kafka/OpenSearch/Iceberg를 실행하거나 성능을 측정하지 않는다.
- 실제 서비스용 설정·명령·SQL 예시는 각 장의 전제와 미검증 표시를 따른다. 현재 환경에서 그대로 동작한다고 가정하지 않는다.
- 라이브 시스템 설치·장애 주입·삭제는 이 문서를 작성하면서 실행하지 않았다. 운영 클러스터에 예제를 무작정 적용하지 않는다.
- `latest`·`stable` 링크는 시간이 지나면 바뀐다. 실제 실습은 버전·connector·JDK/Scala·인증·저장소 조합을 별도 기록한다.

## 실제 프로젝트 문서와의 관계

이 폴더는 재사용 가능한 학습 자료다. Trident v3의 승인된 정책, 배포 설정, 구현 진행 상태는 해당 제품 저장소의 설계·release 문서에서 관리한다. 여기의 가상 예시를 제품의 구현 완료 증거로 사용하지 않는다.

[상위 관측 런북](../README.md) · [Kubernetes 런북](../../README.md) · [저장소 홈](../../../README.md)
