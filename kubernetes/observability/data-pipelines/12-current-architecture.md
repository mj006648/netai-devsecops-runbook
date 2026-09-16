# 12. 현재 학습 기준: Airflow와 신호별 옵저버빌리티

2026-09-15 · 학습·설계 방향이며 운영 배포 완료를 뜻하지 않음

[학습 목차](README.md) · [Airflow](10-airflow-orchestration.md) · [LGTM 계열](11-lgtm-observability.md)

## 1. 무엇이 바뀌었나?

초기에는 Kafka→Flink→OpenSearch와 Spark→Iceberg를 중심으로 논의했다. 지금은 운영의 핵심 요구를 로그 검색 자체가 아니라 **신뢰할 수 있는 관측과 작업 단위 오케스트레이션**으로 좁혔다.

- 최근 메트릭: Prometheus
- 로그: Loki
- 주요 작업의 trace: Tempo
- 상세 진단 화면: Grafana
- 계측·수집: OTel과 기존 scrape 경로의 역할 분리
- 작업 흐름: Airflow
- 장기 연구 기록: 선별된 사건→Kafka→Spark→Iceberg

Mimir는 초기 필수가 아니다. 엄밀한 LGTM의 M은 Mimir이지만 초기 구성은 Prometheus를 활용하는 변형이다. OpenSearch·Flink 학습 장은 대안 비교용으로 유지하며 더 이상 기본 설치 순서로 읽지 않는다.

## 2. 연결 예시

```text
사용자/Portal → Airflow → 업무 API → Member·Operator → 데이터 준비
                  ↑                                  │
        최신 수치·검증된 작업 상태                     ↓
                 Prometheus ← OTel/기존 metric scrape
                 Loki       ← OTel logs
                 Tempo      ← OTel 주요 spans
                     └→ Grafana 진단

선별한 작업 사건·결정·결과 → Kafka → Spark → Iceberg → 장기 분석
```

모든 신호를 Kafka·Spark·Iceberg에 먼저 넣은 뒤 제어하지 않는다. 이력 적재 지연과 live 관측·작업 상태는 별도다. 두 경로를 다른 deployment로 만들었어도 같은 broker·node·disk의 장애 영향은 공유할 수 있다.

## 3. Airflow가 하는 일과 하지 않는 일

Airflow는 작업 순서, 조건 대기, 제출, 결과 확인, 안전하게 설계된 재시도를 담당한다. 초단위의 무제한 자원 변경 루프나 메시지 broker가 아니다. task pool은 원격 Kubernetes 자원 예약도 아니다.

예시 흐름:

1. 입력 Collection과 version/hash를 고정한다.
2. 관측의 원본 시각·queue·처리량과 Member 상태를 확인한다.
3. 조건이 부족하면 대기하고, 충족되면 같은 요청 키로 업무 API에 제출한다.
4. Member가 권한·예산·정책 버전을 검사하고 CR 인스턴스/Job을 생성한다.
5. 해당 실행의 검증된 Ready 또는 실패 결과를 기다린다.
6. 실패 원인을 Loki·Tempo로 조사하고 실행 결과를 장기 보존한다.

에러 로그가 없음을 성공으로 사용하지 않는다. 실패 task 재시도는 외부 상태의 자동 rollback도 아니다. [Airflow best practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)

## 4. 수집·저장 선택의 기준

| 질문 | 결정 |
| --- | --- |
| OTel과 Prometheus는 중복인가? | 계측/전달과 TSDB 조회는 다름. 같은 metric 이중 수집만 방지 |
| 왜 Loki·Tempo로 나누나? | 로그·trace의 검색과 보존 목적에 맞춘 분리. 자동 성능 우위는 아님 |
| Grafana가 저장소인가? | 여러 backend의 조회·시각화 계층 |
| Mimir/Thanos/Cortex를 모두 설치하나? | 아니며 중앙화·HA·retention 요구를 확인해 하나의 전략을 선택 |
| Flink를 제거하면 계산은 어디서 하나? | 기본 지표 집계는 metrics query, 로그 필터는 Loki, 작업 결정은 제한된 Airflow/정책 코드. 복잡한 stateful stream 계산은 후속 요구 |
| OpenSearch를 쓰면 안 되나? | 본문 전문 검색 등 명확한 요구가 있으면 대안으로 재평가 |
| 트레이스는 전부 수집하나? | 중요 구간부터 시작하고 sampling/drop·오버헤드를 명시 |

[Prometheus OTel](https://prometheus.io/docs/guides/opentelemetry/), [Loki OTLP](https://grafana.com/docs/loki/latest/send-data/otel/), [Tempo](https://grafana.com/docs/tempo/latest/)

## 5. 연구와 실험은 별개로 설계한다

연구 질문은 “stack을 연결했는가”가 아니라 같은 예산 아래에서 관측·데이터 특성·불확실성을 고려하는 정책이 입력 준비를 개선하는가다.

최소 세 검증:

1. 관측 정확성: 원본 sample 시각·event/run/attempt 연결·sampling·누락·대조 집합
2. 적용 안전성: 권한·예산 예약·중복 요청·정책 세대·실제 Job 결과
3. 정책 효과: 같은 입력·예산·계측 조건에서 튜닝된 고정/반응형과 비교

AQE는 query engine 내부 실행 통계로 남은 계획을 조정하고, LakeHelm은 사전 학습으로 engine/format/config를 추천한다. 이들과 다른 외부 데이터 준비 제어 문제를 정의해야 한다. [AQE 원문](https://www.vldb.org/pvldb/vol17/p3947-bu.pdf), [LakeHelm 원문](https://www.vldb.org/pvldb/vol19/p1768-xu.pdf)

불확실한 sample이나 backend 장애에서 적응 확대를 멈추는 행동도 평가 대상이다. 늦은 archive나 검색 장애 때문에 기존 작업을 무조건 종료하지 않는다.

## 6. 실제 구축 전에 고정할 항목

- OSS/Enterprise 기능·라이선스, 인증·tenant/namespace 경계
- 지원 버전·image digest·CA/Secret 참조와 수집 책임
- source→query freshness, query latency, 판단→적용 latency를 별도 정의
- metric cardinality·sampling·Collector queue·WAL·storage retention
- Airflow task/run과 실제 Job/decision의 ID·재시도 계약
- 원본 데이터·기존 PV/PVC를 건드리지 않는 격리 시험 범위

현재 구조는 도구별 후보와 역할 선택이다. 이 문서에 나오는 구성요소가 실제로 설치됐거나 실시간 성능이 검증됐다고 주장하지 않는다.
