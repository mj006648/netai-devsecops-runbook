# 04. OpenSearch와 Data Prepper — 검색 인덱스와 수집 파이프라인

## 이 장의 위치

- 상위 문서: [운영 데이터 파이프라인 학습 자료](README.md), [Kubernetes Observability](../README.md)
- 이전 장: [03 Flink](03-flink.md)
- 다음 장: [05 Apache Iceberg](05-iceberg.md), [07 Metrics and Prometheus](07-metrics-and-prometheus.md)

## 문서 기준

- 조사일: **2026-09-15**
- 기준 문서: OpenSearch latest docs, OpenSearch Data Prepper latest docs, Kubernetes storage docs, Apache Iceberg spec
- 예시는 학습용입니다. 이 저장소에서는 OpenSearch, Kafka, Data Prepper, Iceberg 작업을 실행하지 않았습니다.
- 실제 endpoint, IP, credential, private incident, 원시 운영 dump를 쓰지 않습니다.

## 먼저 기억할 문장

OpenSearch는 **검색 index와 query engine**입니다.
Data Prepper는 OpenSearch 앞단의 **수집·정제·전달 pipeline**입니다.
둘은 Kafka의 durable event log나 Flink의 stateful stream processing을 대체하지 않습니다.
PV가 있다고 OpenSearch HA가 자동으로 생기지 않습니다.

## 1. 이 장에서 가정하는 전체 그림

- 이 학습 경로의 예시 아키텍처는 배포 사실이 아니라 설명용 모델이다.
- 로그와 이벤트는 `OTel -> Kafka -> hot consumer -> OpenSearch` 흐름으로 설명한다.
- 배치 분석 데이터는 독립적으로 `Spark -> Iceberg` 경로를 사용한다고 둔다.
- OpenSearch는 빠른 검색·필터·대시보드 조회를 위한 hot index 계층이다.
- Iceberg는 재현 가능한 분석 테이블 계층이며 OpenSearch 스냅샷과 다른 개념이다.
- Data Prepper는 OpenSearch 앞단의 수집·정제·전달 도구로 다룬다.
- Data Prepper는 Kafka나 Flink의 일반 대체재가 아니다.

## 2. OpenSearch를 먼저 검색 엔진으로 이해하기

- OpenSearch의 기본 단위는 document다.
- document는 JSON 구조로 저장되는 검색 대상 레코드다.
- index는 관련 document를 모아 검색 가능한 단위로 관리하는 논리 컨테이너다.
- shard는 index를 나누어 저장하는 물리·논리 분할 단위다.
- OpenSearch 문서는 shard가 Lucene index라는 점을 명시한다. [OpenSearch concepts](https://docs.opensearch.org/latest/getting-started/concepts/)
- replica shard는 primary shard의 복사본이며 node 장애 시 가용성과 검색 처리량을 돕는다. [OpenSearch introduction](https://docs.opensearch.org/latest/getting-started/intro/)
- `number_of_shards`는 나중에 쉽게 줄이는 값이 아니다.
- `number_of_replicas`는 장애 허용과 비용 사이의 선택이다.
- shard 수가 많다고 항상 좋은 것은 아니다.
- 너무 큰 shard는 recovery와 relocation 시간을 늘린다.
- 학습 설계에서는 shard 수를 “데이터 보관 기간, 쓰기량, 검색 패턴”에서 역산한다.

## 3. PersistentVolume은 HA가 아니다

- Kubernetes PersistentVolume은 Pod 수명과 독립적인 저장소 추상화다. [Kubernetes Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- PV가 있다고 해서 OpenSearch replica가 생기지는 않는다.
- PV가 있다고 해서 같은 데이터를 다른 node에 자동 복제하지도 않는다.
- local PV는 node 장애 시 해당 volume 접근이 막힐 수 있다. [Kubernetes Volumes](https://kubernetes.io/docs/concepts/storage/volumes/)
- OpenSearch 고가용성은 replica shard 배치, node topology, snapshot, restore 전략을 같이 봐야 한다.
- 단일 PV에 primary와 replica가 같이 있으면 물리 장애 보호가 약하다.
- StatefulSet replica 수와 OpenSearch shard replica 수를 혼동하지 않는다.
- PVC가 Bound인 상태는 storage claim이 연결되었다는 뜻이지 검색 데이터가 안전하다는 뜻이 아니다.

## 4. mapping은 저장 계약이다

- mapping은 document field를 어떻게 저장하고 색인할지 정하는 구조다.
- OpenSearch 문서는 explicit mapping을 권장하며 dynamic mapping만 의존하면 타입 일관성이 흔들릴 수 있다. [Mappings](https://docs.opensearch.org/latest/mappings/)
- `text`는 analyzer를 거쳐 전문 검색에 맞게 token으로 나뉜다.
- `keyword`는 정확 일치, 집계, 정렬, ID류 값에 적합하다.
- keyword analyzer는 입력 전체를 하나의 token으로 다룬다. [Keyword analyzer](https://docs.opensearch.org/latest/analyzers/supported-analyzers/keyword/)
- `message` 같은 본문은 보통 `text`가 자연스럽다.
- `service.name`, `trace_id`, `namespace`, `severity`는 보통 `keyword`가 자연스럽다.
- timestamp는 `date`로 고정해야 range query와 retention 정책이 명확해진다.
- 숫자 field는 실제 연산 가능성을 기준으로 integer, long, double 등을 고른다.
- 매핑은 검색 경험뿐 아니라 storage와 cardinality 비용을 결정한다.
- analyzer는 text field에서 index time과 search time 해석을 바꾼다.
- 기존 field의 analyzer 변경은 일반적으로 reindex가 필요하므로 초기에 보수적으로 설계한다. [Analyzer mapping parameter](https://docs.opensearch.org/latest/mappings/mapping-parameters/analyzer/)

## 5. refresh, translog, durability를 분리해서 기억하기

- indexing 요청은 document를 translog와 in-memory buffer에 반영한다.
- 기본 `index.translog.durability=request`에서는 primary와 할당된 replica의 translog fsync/commit 이후 쓰기 응답을 확인한다. `async`에서는 주기적으로 동기화하므로 마지막 동기화 이후 응답한 쓰기도 장애 때 유실될 수 있다. 따라서 ACK의 내구성은 설정 조건과 함께 설명해야 한다. [Index settings](https://docs.opensearch.org/latest/install-and-configure/configuring-opensearch/index-settings/)
- refresh는 in-memory 구조를 searchable segment로 바꾸어 검색 가능하게 만든다.
- refresh는 “검색 가능성”을 높이는 동작이지 durability 자체와 같지 않다.
- flush는 Lucene segment를 fsync하고 translog 의존을 줄인다.
- Lucene segment는 immutable이며 작은 segment가 큰 segment로 merge된다.
- merge는 검색 성능과 디스크 회수에 중요하지만 쓰기 I/O와 CPU를 쓴다.
- `index.refresh_interval`을 줄이면 fresh search는 빨라질 수 있지만 쓰기 비용이 증가할 수 있다. [Refresh Index API](https://docs.opensearch.org/latest/api-reference/index-apis/refresh/)
- `refresh=true`를 모든 쓰기에 붙이는 습관은 hot path 병목이 될 수 있다.
- “문서가 검색되지 않는다”는 현상은 유실, refresh 지연, routing, mapping, time filter를 나눠 본다.

## 6. snapshot과 Iceberg snapshot은 이름만 비슷하다

- OpenSearch snapshot은 index와 cluster metadata를 repository에 백업·복구하기 위한 기능이다. [OpenSearch snapshot restore](https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/snapshots/snapshot-restore/)
- OpenSearch snapshot은 incremental 방식이지만 완벽한 전역 point-in-time view라고 단정하지 않는다.
- restore는 같은 이름의 open index와 충돌할 수 있으므로 rename, close, delete 정책을 검토해야 한다.
- Iceberg snapshot은 table의 data file 집합을 가리키는 table metadata 버전이다. [Apache Iceberg spec](https://iceberg.apache.org/spec/)
- Iceberg snapshot은 time travel과 rollback의 기준이다.
- OpenSearch snapshot은 검색 cluster 복구 단위다.
- Iceberg table snapshot은 lakehouse table 상태를 재현하는 단위다.
- 둘 다 “snapshot”이지만 운영 질문이 다르다.
- OpenSearch 질문: index를 어떤 repository에서 어떤 이름으로 복구할 것인가?
- Iceberg 질문: table의 어느 snapshot ID나 timestamp를 읽을 것인가?

## 7. Data Prepper 파이프라인의 구성 요소

- Data Prepper pipeline은 source, sink를 필수로 가진다.
- buffer와 processor는 선택 사항이다.
- 공식 문서에 따르면 buffer나 processor가 없으면 기본 buffer와 no-op processor가 사용된다. [Data Prepper concepts](https://docs.opensearch.org/latest/data-prepper/)
- source는 외부 입력을 event로 들여온다.
- processor는 event를 변환, 보강, 필터링한다.
- buffer는 source와 downstream 처리 사이의 압력 완충 역할을 한다.
- sink는 OpenSearch, stdout, S3, Prometheus 등 대상으로 event를 전달한다.
- 하나의 Data Prepper instance는 여러 pipeline을 가질 수 있다.
- pipeline이 많아질수록 worker, buffer, backpressure, DLQ 관찰이 중요해진다.
- Data Prepper는 stream processor처럼 보일 수 있지만 stateful window 연산 플랫폼으로 가정하지 않는다.

## 8. Kafka source를 읽을 때 조심할 점

- Kafka source는 Kafka Consumer API로 topic record를 읽어 Data Prepper event를 만든다. [Kafka source](https://docs.opensearch.org/latest/data-prepper/pipelines/configuration/sources/kafka/)
- Kafka source의 `acknowledgments` 옵션은 end-to-end acknowledgment를 켜는 설정이다.
- 공식 Kafka source 문서의 기본값은 `false`다. [Kafka source](https://docs.opensearch.org/latest/data-prepper/pipelines/configuration/sources/kafka/)
- 그러므로 “Kafka를 쓰면 OpenSearch까지 성공한 뒤 offset이 안전하게 확정된다”고 기본 가정하지 않는다.
- end-to-end ack를 켰는지, 어떤 sink가 ack를 release하는지, 실패 시 재처리가 어떤지 별도 확인한다.
- Kafka consumer group은 병렬성과 offset 관리를 제공하지만 idempotent indexing을 대신하지 않는다.
- 같은 event가 재처리될 수 있으므로 deterministic document ID가 필요하다.
- document ID가 매번 달라지면 retry가 duplicate document를 만들 수 있다.

## 9. OpenSearch sink에서 ID, retry, DLQ를 설계하기

- OpenSearch sink는 `document_id` 형식 문자열을 지원한다. [OpenSearch sink](https://docs.opensearch.org/latest/data-prepper/pipelines/configuration/sinks/opensearch/)
- event 내부 field나 metadata를 조합해 `_id`를 만들 수 있다.
- 예시 아키텍처에서는 `trace_id + span_id`, `event_id`, `source + offset`처럼 재현 가능한 키를 우선 검토한다.
- Data Prepper OpenSearch sink는 `max_retries`와 DLQ 설정을 제공한다. [OpenSearch sink](https://docs.opensearch.org/latest/data-prepper/pipelines/configuration/sinks/opensearch/)
- 공식 문서는 end-to-end ack와 DLQ를 같이 고려하라고 설명한다.
- DLQ는 실패를 숨기는 쓰레기통이 아니다.
- DLQ는 재처리, 원인 분류, schema 보정의 입력 큐다.
- `max_retries`를 낮추면 빠르게 DLQ로 보내지만 일시 장애 복구 기회를 줄인다.
- `max_retries`를 무한에 가깝게 두면 poison event가 pipeline을 붙잡을 수 있다.
- mapping 오류는 retry로 해결되지 않는 경우가 많다.
- 네트워크 오류나 5xx는 retry로 해결될 수 있다.

## 10. Iceberg source와 아직 검증되지 않은 Iceberg sink를 구분하기

- Data Prepper 2.15 문서는 `iceberg` source를 experimental로 표시한다. [Iceberg source](https://docs.opensearch.org/latest/data-prepper/pipelines/configuration/sources/iceberg/)
- Iceberg source는 Iceberg table snapshot을 polling하고 CDC event를 downstream sink로 보낼 수 있다.
- Iceberg source 문서는 `identifier_columns` 기반 document ID metadata를 설명한다. [Iceberg source](https://docs.opensearch.org/latest/data-prepper/pipelines/configuration/sources/iceberg/)
- 이 기능은 “Iceberg에서 OpenSearch로 동기화”하는 방향이다.
- 반대로 “Data Prepper가 Iceberg table에 sink로 쓴다”는 기능은 이 문서 작성일 기준 배포 기능으로 가정하지 않는다.
- Data Prepper 저장소에는 Iceberg sink RFC가 있지만, RFC와 운영 가능 release는 다르다. [Iceberg sink RFC issue](https://github.com/opensearch-project/data-prepper/issues/6664)
- S3 Tables/Iceberg sink 요청 중 `wontfix`로 닫힌 제안도 있으므로 기능 존재를 이름만 보고 단정하지 않는다. [S3 Tables sink issue](https://github.com/opensearch-project/data-prepper/issues/6652)
- 따라서 학습 아키텍처는 OpenSearch hot path와 Spark->Iceberg analytical path를 분리한다.

## 11. Alerting은 safe actuator가 아니다

- OpenSearch Alerting은 monitor, trigger, action, notification 모델을 제공한다. [OpenSearch Alerting](https://docs.opensearch.org/latest/observing-your-data/alerting/index/)
- monitor는 schedule에 따라 query를 실행하고 trigger 조건을 평가한다.
- action은 notification channel로 메시지를 보낼 수 있다.
- 이것은 승인된 controller가 상태를 바꾸는 것과 다르다.
- Alerting webhook을 직접 scale, delete, quarantine actuator로 쓰면 권한·중복·재시도·감사 문제가 생긴다.
- 안전한 제어는 별도 승인 경로와 authorized Member Operator가 담당한다고 둔다.
- OpenSearch Alerting은 “관찰과 통지” 계층으로 제한하는 것이 기본 안전선이다.

## 12. OpenSearch가 Kafka나 Flink를 대체하지 않는 이유

- OpenSearch는 검색과 집계가 강한 저장·검색 계층이다.
- Kafka는 durable log, fan-out, replay, consumer group 중심의 event backbone이다.
- Flink는 stateful stream processing, event time, window, exactly-once sink 설계가 중심이다.
- OpenSearch index에 document를 저장한다고 replay log가 생기는 것은 아니다.
- OpenSearch query로 일부 집계를 할 수 있어도 stream state backend가 되는 것은 아니다.
- 장기 재처리와 분석 재현성은 Kafka retention, Iceberg table, batch engine과 나누어 설계한다.
- OpenSearch에는 빠른 operational search에 맞는 보존 기간과 mapping을 적용한다.

## 13. 예시 query — 실행 금지, 형태 설명용

```text
# 설명용: 최근 오류 로그 수를 service 단위로 집계하는 OpenSearch DSL 형태
GET /logs-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "term": { "severity": "ERROR" } },
        { "range": { "@timestamp": { "gte": "now-15m" } } }
      ]
    }
  },
  "aggs": {
    "by_service": { "terms": { "field": "service.name" } }
  }
}
```

- 위 예시는 live cluster에 실행하지 않는다.
- index 이름, field 이름, retention 기간은 실제 설계와 다를 수 있다.
- `service.name`이 `keyword`로 매핑되어 있지 않으면 terms aggregation 결과가 의도와 다를 수 있다.
- `now-15m`은 query evaluation time 기준이므로 ingest 지연과 다르다.

```text
# 설명용: deterministic document_id를 쓰는 Data Prepper sink 단편
sink:
  - opensearch:
      hosts: ["https://OPENSEARCH-ENDPOINT.example"]
      index: "logs-%{yyyy.MM.dd}"
      document_id: "${/event_id}"
      # max_retries는 운영 기준으로 별도 결정한다.
      dlq_file: "/path/to/local/dlq"
```

- 위 YAML은 즉시 사용 가능한 설정이 아니다.
- endpoint, 인증, TLS, DLQ 위치, 권한, version 호환성을 모두 별도 검증해야 한다.
- placeholder는 실제 주소나 비밀값이 아니다.

## 14. 설계 체크리스트

| 질문 | 안전한 답의 방향 |
| --- | --- |
| 검색 freshness가 필요한가? | refresh interval과 ingest 지연을 분리해 정의한다. |
| retry가 duplicate를 만들 수 있는가? | deterministic document ID와 idempotent action을 설계한다. |
| mapping 오류가 반복되는가? | retry보다 DLQ와 schema 수정 절차를 둔다. |
| PV가 있으니 안전한가? | replica shard, node topology, snapshot repository를 별도 확인한다. |
| Alerting webhook이 조치해도 되는가? | notification과 authorized controller를 분리한다. |
| Iceberg와 OpenSearch snapshot을 혼동했는가? | table metadata snapshot과 cluster backup snapshot을 분리한다. |
| Data Prepper가 stream processor인가? | 수집·변환 도구이며 Kafka/Flink 대체로 설계하지 않는다. |

## 15. Troubleshooting table

| 증상 | 먼저 볼 것 | 흔한 원인 | 안전한 다음 단계 |
| --- | --- | --- | --- |
| 방금 넣은 문서가 검색되지 않음 | refresh, time filter, index alias | refresh 전이거나 timestamp field 불일치 | refresh 강제보다 query window와 mapping 확인 |
| 같은 이벤트가 여러 개 보임 | `_id`, retry, consumer offset | document ID가 매번 다름 | source offset 또는 event ID 기반 `_id` 검토 |
| DLQ가 증가함 | DLQ record reason | mapping conflict, auth, rejected document | DLQ 샘플을 비식별화해 schema 원인 분류 |
| shard relocation이 느림 | shard size, disk I/O, network | shard 과대, node 압박 | hot index rollover와 shard 크기 재검토 |
| Alert가 반복 발송됨 | monitor schedule, trigger, action | condition flapping 또는 notify throttling 부재 | alert 상태와 notification throttle 조정 |
| Kafka lag가 줄지 않음 | source worker, sink latency, retries | OpenSearch sink 병목 | sink bulk, mapping error, OpenSearch health 확인 |
| Iceberg source 동기화가 불명확함 | experimental flag, identifier_columns | source 기능과 sink 기능 혼동 | 공식 Iceberg source 문서와 release note 확인 |

## 16. 복습 문제

1. refresh와 flush의 차이는 무엇인가?
2. PV가 Bound이면 OpenSearch 데이터가 고가용성이라고 말할 수 있는가?
3. `text`와 `keyword` field 선택 기준은 무엇인가?
4. retry가 duplicate document를 만드는 이유는 무엇인가?
5. OpenSearch snapshot과 Iceberg snapshot은 무엇이 다른가?
6. Data Prepper Kafka source에서 end-to-end ack를 기본값으로 가정하면 왜 위험한가?
7. OpenSearch Alerting webhook을 직접 actuator로 쓰면 어떤 문제가 생기는가?

## 17. 정답

1. refresh는 검색 visibility를 갱신한다. 쓰기 ACK의 translog 내구성은 `request`/`async` 설정에 따라 다르며, flush는 Lucene commit을 만들고 segment를 디스크에 동기화해 이전 translog에 대한 복구 의존을 줄인다. 검색 가능·쓰기 응답·Lucene commit은 같은 시점이 아니다.
2. 아니다. PV는 스토리지 리소스이고 PVC는 이를 사용하는 요청이다. 영속 볼륨 연결만으로 replica shard, 독립 failure domain, snapshot backup과 복구 시험까지 보장되지는 않는다.
3. 전문 검색과 tokenization이 필요하면 `text`, 정확 일치·집계·정렬·ID 성격이면 `keyword`를 우선 검토한다.
4. 실패 후 재전송 시 `_id`가 달라지면 OpenSearch가 같은 event를 새 document로 저장할 수 있기 때문이다.
5. OpenSearch snapshot은 index/cluster 복구용 백업이고, Iceberg snapshot은 table data file 집합을 가리키는 metadata 버전이다.
6. 공식 Kafka source 문서의 `acknowledgments` 기본값은 `false`이므로 sink 성공까지 보장한다고 볼 수 없다.
7. 알림 재시도, 중복, 권한, 감사, 승인 경로가 불명확해져 안전한 제어와 분리되지 않기 때문이다.

## 18. 버전 주의와 검증 상태

- 문서 기준일은 2026-09-15이다.
- OpenSearch, Data Prepper, Kubernetes, Iceberg 문서는 버전에 따라 옵션과 기본값이 바뀔 수 있다.
- 이 장의 DSL과 YAML은 설명용이며 live 실행으로 검증하지 않았다.
- 공개 문서 안전을 위해 실제 endpoint, IP, credential, 내부 장애 식별자는 포함하지 않았다.
- 운영 적용 전에는 대상 버전의 공식 문서, staging pipeline, rollback 절차를 별도로 확인한다.
