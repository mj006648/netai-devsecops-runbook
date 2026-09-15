# 8. 통합 설계: 무엇을 넣고 무엇을 빼야 하나?

[학습 목차](README.md) · 이전: [메트릭](07-metrics-and-prometheus.md) · 다음: [실습·복습](09-labs-and-review.md)

> 아래 구조는 학습용 설계 예시다. 특정 클러스터에서 구현·성능·가용성이 검증된 배포판을 뜻하지 않는다.

## 1. 먼저 요구를 문장으로 적는다

예시 요구:

- 데이터 준비 작업의 상태·지연·오류를 최근 화면에서 조회한다.
- 일부 기록은 장기 테이블에 남겨 정책별 결과를 비교한다.
- archive가 느려져도 최근 조회가 그것을 기다리지 않는다.
- 허용된 범위에서 신규 작업 수·profile을 조정한다.
- 원본 데이터·다른 사용자의 작업·권한을 침범하지 않는다.

여기에 수집량, 평균/최대 payload, 허용 지연, 장애 보존 시간, 데이터 손실 허용 범위, replay 필요 기간, 운영 가능한 인력·자원 예산을 붙인다. 숫자를 정하지 않은 상태에서 “실시간”, “대규모”, “무손실”만 쓰면 시험할 수 없는 요구가 된다.

## 2. 가장 단순한 구성부터 비교한다

### A. broker 없는 관측 경로

```text
OTel → 수집·변환 → OpenSearch
         └→ 독립 archive 경로 → 장기 저장
```

구성이 작다. Collector의 유한 queue와 retry·persistent storage로 필요한 장애 시간을 견딜 수 있는지 확인한다. backend 장애가 길어지거나 여러 독립 소비자가 필요하면 이 방식의 한계가 드러날 수 있다. 작은 규모라고 무조건 안전하거나, Kafka가 없다고 운영 불가능한 것은 아니다. [Collector 복원력](https://opentelemetry.io/docs/collector/resiliency/)

### B. broker를 둔 독립 hot/archive 소비

```text
                    ┌→ 최근 검색 소비자 → OpenSearch
OTel → Kafka ───────┤
                    └→ archive 소비자 → Iceberg
```

두 소비자는 각각 진행률과 재시도를 관리한다. 최근 검색과 archive가 서로 다른 시간 요구를 가져도 운영할 수 있다. 대신 Kafka의 보존·복제·디스크·ACL과 각 소비자 운영 부담이 추가된다.

### C. 하나의 Flink Job에서 두 sink

```text
Kafka → Flink 가공 ─┬→ OpenSearch
                   └→ Iceberg
```

같은 계산 결과를 두 곳으로 보낼 수 있지만, 느린 sink의 backpressure와 checkpoint/task failure가 전체 job에 영향을 줄 수 있다. “선이 두 갈래이니 장애가 완전히 분리됐다”고 판단하면 안 된다. 또한 각 sink의 전달 보장과 두 저장소의 원자적 commit은 별개다. [Flink 보장 범위](https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/guarantees/)

### D. Flink hot + Spark archive

```text
Kafka ─┬→ Flink 실시간 계산 → OpenSearch
       └→ Spark 증분 적재 → Iceberg
```

온라인에서 상태·시간 기반 계산이 실제 필요하고 Spark를 이미 운영한다면 유효하다. 두 engine의 schema·시간·중복 처리 의미가 달라지지 않도록 검증한다. 단순 문서 적재만 한다면 hot Flink를 Data Prepper 같은 도구로 줄일 수 있다.

## 3. 도구별 채택 질문

| 도구 | 도입 이유가 되는 요구 | 먼저 확인할 것 |
| --- | --- | --- |
| Kafka | 두 소비자, replay, burst와 backend 장애 보존 | retention 시간/bytes, replicas와 failure domain, source ACK 경계 |
| Flink | event-time join, late event 수정, keyed state·연속 계산 | 실제 계산 명세와 window/watermark·sink 호환 |
| Data Prepper | Kafka/OTel 등에서 받아 OpenSearch에 검증·변환·적재 | source codec·ACK·mapping·DLQ 계약 |
| Spark | 기존 생태계 활용, 배치 분석, 증분 archive | Kafka connector/Scala/runtime, checkpoint, overlapping runs |
| Iceberg Kafka Connect | 변환이 거의 없는 Kafka→Iceberg append | Connect worker·내부 topic·plugin 운영까지 포함한 비용 |
| Iceberg | 장기 SQL·schema/table version 분석 | catalog·data files·commit/retention·작은 파일 관리 |

Kafka Connect는 “코드 없이 무료로 되는 서비스”가 아니라 별도 runtime이다. 반대로 Flink가 없으면 Iceberg에 쓸 수 없다는 것도 아니다. [공식 Iceberg Kafka Connect](https://iceberg.apache.org/docs/latest/kafka-connect/)

## 4. 가공을 어디에 둘까?

### Collector: 전송 전에 해야 하는 일

민감정보 제거, resource 식별자 보강, 필요한 신호 선택, batch·queue 제한이 후보가 된다. 개인정보나 credential이 Kafka에 들어간 뒤 제거하는 것보다 전송 전에 통제하는 편이 노출 범위를 줄인다.

### Source/공통 schema: 의미를 일치시키는 일

`event_id`, 발생 시각, producer, site/cluster, run/attempt, 상태와 schema version을 고정한다. 읽는 쪽마다 임의로 다른 필드 의미를 추측하지 않는다.

### 처리 engine: 계산이 필요한 일

여러 사건의 시간 관계, 누적 상태, join과 재계산을 맡는다. 단순히 한 컬럼 이름을 바꾸기 위해 분산 처리 engine을 추가할 필요는 없다. 기본적인 비율·histogram 집계도 메트릭 backend나 검색 query로 충분한지 먼저 본다.

### Sink: 저장소의 계약에 맞추는 일

OpenSearch mapping/document ID, Iceberg schema/partition/commit과 인증을 처리한다. 이것이 “정리·적재”의 구체적 책임이다. 변환이 한 단계에만 있어야 하는 것은 아니지만 같은 규칙을 여기저기 중복 구현하면 drift가 생긴다.

## 5. 공통 이벤트와 파생 데이터

공통 이벤트 예시:

```json
{
  "schema_version": 1,
  "event_id": "event-001",
  "event_time": "2026-09-15T10:00:00Z",
  "producer_id": "member-a",
  "run_id": "run-001",
  "attempt": 1,
  "stage": "input-preparation",
  "state": "Preparing"
}
```

설명용 schema이며 OTel OTLP wire format이나 특정 제품 API 명세가 아니다.

- 최근 검색 문서는 event ID로 원시 사건을 보거나, 별도 ID로 작업별 최신 projection을 표현할 수 있다. 둘을 같은 index/document 의미로 섞지 않는다.
- archive는 원시 전달 record와 논리 사건의 중복을 구분해서 보존할 수 있다.
- Flink가 1분 window 결과를 저장하고 Spark가 원시 이벤트를 보존한다면 두 저장소의 행 수는 원래 다르다.
- 동일 사건의 재전송과 동일 ID에 다른 내용이 들어온 충돌은 다르다. 충돌을 마지막 값으로 덮어쓰고 정상 dedup로 처리하지 않는다.

## 6. 버전 호환은 그림보다 먼저 확인한다

실제 구성에는 engine뿐 아니라 connector, JDK/Scala, serializer, auth, catalog와 storage client 버전이 함께 들어간다. 이름에 OpenSearch/Iceberg가 들어 있다고 어느 최신 버전과나 호환되는 것은 아니다.

버전 점검표:

| 구간 | 기록할 것 |
| --- | --- |
| 앱→Collector | OTel SDK/Collector 배포판, signal/encoding, 인증 |
| Collector→Kafka | exporter 버전, encoding, producer 보장, broker 호환 |
| Kafka→hot sink | consumer/connector 버전, offset/ACK, mapping |
| Kafka→Spark→Iceberg | Spark/Scala/Kafka/Iceberg runtime, catalog, stable checkpoint |
| 제어 API | policy schema, Member capability, 승인된 action 범위 |

배포할 때는 `latest` 이미지 대신 확인한 버전/digest를 기록하고, actual-service 시험에서 회복까지 확인한다. 공식 표에 공통 지원 조합이 없으면 자체 patch를 당연한 전제로 넣지 않는다. [Flink 배포·connector 목록](https://flink.apache.org/downloads/)

## 7. 제어 경로는 관측 경로와 다르다

```text
최신 메트릭 + Member의 현재 상태
                ↓
          Operations 정책 판단
                ↓
      권한·예산·만료·중복 여부 확인
                ↓
       Member·Operator가 적용
                ↓
        실제 결과와 관측 재확인
```

OpenSearch Alerting은 이상 징후의 한 입력이 될 수 있다. 하지만 webhook을 받았다는 이유만으로 Pod를 바로 바꾸는 것은 안전한 제어가 아니다. 동일 알림 반복, 오래된 관측, 정책 만료, 수동 변경과의 충돌을 다뤄야 한다. [Alerting](https://docs.opensearch.org/latest/observing-your-data/alerting/index/)

### 예시: 입력 준비의 스토리지 경쟁

1. 여러 작업이 S3를 동시에 읽는다.
2. 지연·retry가 증가하지만 CPU는 여유가 있다.
3. 정책은 단순 CPU 증설이 아니라 신규 작업·읽기 동시성 제한을 검토한다.
4. Member가 자신의 예산·권한·현재 실행 작업을 확인하고 다음 Job부터 적용한다.
5. 완료 시간뿐 아니라 대기·실패·공정성과 자원 비용까지 비교한다.

설계 예시이며 효과가 검증됐다는 뜻이 아니다. 기존 작업을 강제로 죽여 새 상한을 맞추거나, 임의 데이터셋의 버전 검증을 생략하지 않는다.

## 8. 장애 표를 먼저 작성한다

| 장애 | 기대 동작 | 검증할 증거 |
| --- | --- | --- |
| OpenSearch 중단 | archive와 직접 결합하지 않음; hot backlog 관측 | 소비 위치, DLQ, 복구 후 event-ID 집합 |
| Iceberg/catalog 중단 | live 검색·제어가 archive 완료를 기다리지 않음 | hot latency, archive checkpoint/lag |
| Kafka 장애 | 제한된 edge queue/retry; 초과 시 명시적 손실 표시 | broker 이전/이후 ACK 경계와 drop 수 |
| 관측 stale | adaptive 확대 금지 | 원본 sample time, fallback 결정 |
| Member 상태 불명 | 신규 예약 보류 | 실제 Job UID·예약 상태 대조 |
| archive가 retention보다 늦음 | 복구 불가능한 구간을 숨기지 않음 | earliest available offset와 미처리 범위 |

별도 consumer라도 같은 broker·node·disk를 공유하면 서로 영향을 줄 수 있다. deployment 분리, resource quota, checkpoint 분리는 필요하지만 물리 HA와 같지 않다.

## 9. 논문·평가에서 구분할 것

- **관측 시스템 검증:** 사건을 잃지 않고 필요한 시간 안에 전달·조회했는가?
- **제어 정확성 검증:** 예산을 넘거나 중복 작업을 만들지 않고 승인된 변경을 적용했는가?
- **성능 효과 검증:** 같은 입력·예산에서 충분히 튜닝한 비교군보다 실제로 나아졌는가?

Collector 설치, 두 sink 저장 성공, 예쁜 dashboard만으로 마지막 질문에 답한 것은 아니다. 실패·누락·불리한 결과를 포함해서 재현 가능한 raw/summary를 남긴다.

## 10. 복습 질문과 답

1. **두 consumer이면 완전한 장애 격리인가?** 아니다. shared broker·storage·node와 용량 제한도 확인한다.
2. **같은 event를 두 곳에 쓰면 분산 트랜잭션인가?** 아니다. 각 sink 성공·복구·중복 계약을 따로 정의한다.
3. **Iceberg에 넣기 위해 Flink가 필수인가?** 아니다. Spark나 Kafka Connect 등 요구에 맞는 writer를 선택한다.
4. **최근 상태를 OpenSearch에서 찾았으면 바로 제어해도 되는가?** 원본 시각·권한·예산·실제 현재 상태를 다시 검증한다.
5. **Flink를 추가할 강한 이유는?** 단순 전달이 아니라 상태·event time·늦은 데이터 처리가 필요한 명확한 계산 요구다.

[학습 목차](README.md) · 다음: [실습·복습](09-labs-and-review.md)
