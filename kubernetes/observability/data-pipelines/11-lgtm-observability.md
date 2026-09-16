# 11. LGTM 관측 스택 — Prometheus, Loki, Tempo, Grafana와 선택적 Mimir
[위로: data-pipelines README](README.md) · 이전: [Airflow 오케스트레이션](10-airflow-orchestration.md) · 다음: [현재 아키텍처](12-current-architecture.md)

## 문서 기준

- 조사 기준: **2026-09-15**
- 범위: OTel SDK/Collector와 Prometheus, Loki, Tempo, Grafana, 선택적 Mimir의 역할 경계를 학습한다.
- 연결 학습: [OpenTelemetry](01-opentelemetry.md), [Metrics와 Prometheus](07-metrics-and-prometheus.md), [현재 아키텍처](12-current-architecture.md)
- 이 문서는 설치 가이드가 아니다. 실제 endpoint, credential, tenant, 운영 로그, cluster 주소를 포함하지 않는다.
- 아래 설정 조각은 **실행하지 않은 illustrative 예시**다. 이 저장소에서 Collector, Prometheus, Loki, Tempo, Grafana, Mimir를 실행하지 않았다.

## 먼저 기억할 문장

LGTM의 M은 기술적으로 **Mimir**를 뜻하지만, 초기 학습·소규모 운영 변형에서는 Prometheus가 metrics 저장·query의 중심일 수 있다.
OpenTelemetry는 telemetry를 만들고 모으는 표준 경로이고, Prometheus/Loki/Tempo/Mimir는 저장·query backend이며, Grafana는 시각화와 탐색 UI다.
Kafka→Spark→Iceberg는 선별된 장기 이벤트 archive 경로로 둘 수 있지만, live metric/log/trace 조회의 필수 경로가 아니다.

## 1. 현재 권장 기본형

| 신호 | 생성/수집 | 저장·query | 시각화 |
| --- | --- | --- | --- |
| Metrics | Prometheus scrape, OTel SDK/Collector | 초기: Prometheus, 확장: Mimir | Grafana |
| Logs | app log, OTel log pipeline, Collector | Loki | Grafana Explore/dashboard |
| Traces | OTel SDK/instrumentation, Collector | Tempo | Grafana Tempo data source |
| Long-term selected events | app/domain event, optional Kafka | Spark→Iceberg | notebook/warehouse/query tool |

OpenSearch와 Flink는 이 장의 기본 경로가 아니다.
검색 중심 로그 분석이나 stateful stream processing 요구가 명확할 때 별도 설계로 검토한다.

## 2. Collection과 backend를 분리해서 말하기

- OTel SDK는 애플리케이션 안에서 span, metric, log record를 만든다.
- OTel Collector는 receiver → processor → exporter pipeline으로 telemetry를 받고 가공하고 내보낸다.
- OpenTelemetry Collector 공식 문서는 Collector를 telemetry를 receive, process, export하는 vendor-agnostic 구현으로 설명한다. [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- Prometheus는 metric scrape, TSDB 저장, PromQL query, rule evaluation을 담당한다.
- Loki는 log stream과 LogQL query를 담당한다.
- Tempo는 trace backend다.
- Grafana는 여러 data source를 조회해 dashboard와 Explore UI를 제공한다.

말을 정확히 해야 장애 분석도 정확해진다.
“OTel이 안 된다”보다 “SDK export 실패”, “Collector receiver 미연결”, “Loki ingestion reject”, “Grafana data source auth 실패”가 훨씬 유용하다.

## 3. OTel SDK와 Collector의 역할

OpenTelemetry metrics spec은 API가 측정값 capture와 SDK 분리를 제공하고, SDK가 aggregation, processor, exporter 같은 실제 기능을 구현한다고 설명한다. [OpenTelemetry Metrics](https://opentelemetry.io/docs/specs/otel/metrics/)
OTel logs spec은 기존 logging library와의 통합, trace context가 포함된 log correlation, Collector 기반 log pipeline을 설명한다. [OpenTelemetry Logs](https://opentelemetry.io/docs/specs/otel/logs/)

운영 경계:

- SDK 설정은 sampling, resource, exporter, batch 동작을 좌우한다.
- Collector 설정은 수집 fan-in, redaction, batching, retry, backend routing을 좌우한다.
- Backend 설정은 retention, index/cardinality, query 성능, multi-tenancy를 좌우한다.
- SDK만 넣고 Collector/backend가 없으면 저장·query가 완성되지 않는다.
- Collector만 설치하고 애플리케이션 계측이 없으면 의미 있는 span과 metric이 생기지 않는다.

## 4. Metrics: Prometheus first, Mimir optional scale

Prometheus는 scrape와 PromQL의 기준점이다.
Prometheus configuration 문서는 `scrape_interval`과 `evaluation_interval`을 별도 설정으로 다룬다. [Prometheus Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
Prometheus querying basics는 query 시점에 lookback period 안의 최신 sample을 사용하고, 사라진 series는 stale 처리될 수 있다고 설명한다. [Prometheus Querying Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)

초기형:

- Prometheus가 Kubernetes target을 scrape한다.
- Prometheus rule이 alert 조건을 평가한다.
- Grafana가 Prometheus data source로 PromQL을 실행한다.

확장형:

- Prometheus는 edge scrape/agent 역할을 유지한다.
- Remote write로 Mimir에 장기 저장과 중앙 query를 맡긴다.
- Grafana는 Prometheus-compatible data source로 Mimir를 조회한다.

Grafana Mimir 공식 문서는 Mimir를 Prometheus와 OpenTelemetry metrics의 장기 저장소이며, Prometheus remote write, PromQL, alerting과 호환되는 scale-out backend로 설명한다. [Grafana Mimir Introduction](https://grafana.com/docs/mimir/latest/introduction/)

## 5. OTel metrics와 Prometheus scrape 중복 피하기

OTel SDK가 metric을 OTLP로 Collector에 보내고, 동시에 Prometheus가 같은 app `/metrics` endpoint를 scrape하면 duplicate series가 생길 수 있다.
[07장](07-metrics-and-prometheus.md)에서 다룬 것처럼 source of truth를 하나로 정해야 한다.

선택지:

1. Prometheus 직접 scrape가 source of truth다.
2. OTel SDK → Collector → Prometheus remote write가 source of truth다.
3. 둘 다 쓰되 metric 이름, label, temporality, resource 변환을 분리한다.

중복 수집은 error rate가 두 배처럼 보이거나 autoscaling 판단을 왜곡할 수 있다.
특히 제어 telemetry는 “많이 모을수록 좋다”보다 “중복 없이 의미가 고정돼야 한다”가 중요하다.

## 6. Logs: Loki와 native OTLP

Loki는 log line 전체를 전부 index하는 방식이 아니라 label로 log stream을 좁히고 LogQL로 조회한다.
Loki label 문서는 label이 낮은 cardinality 값을 담아야 하며, high-cardinality metadata는 structured metadata 사용을 권장한다. [Loki Labels](https://grafana.com/docs/loki/latest/get-started/labels/)

Loki는 OpenTelemetry log ingestion을 native OTLP endpoint로 지원한다.
Grafana Loki 문서는 native OTLP endpoint가 Loki Exporter보다 권장되는 방식이며, structured metadata를 활용한다고 설명한다. [Loki native OTLP vs Loki Exporter](https://grafana.com/docs/loki/latest/send-data/otel/native_otlp_vs_loki_exporter/)
Structured metadata 문서는 OTLP data 수용에 structured metadata가 필요하다고 설명한다. [Loki Structured Metadata](https://grafana.com/docs/loki/latest/get-started/labels/structured-metadata/)

로그 설계 원칙:

- label에는 `service`, `namespace`, `environment`, `level`처럼 bounded 값만 둔다.
- `trace_id`, `span_id`, `request_id`는 검색에 유용하지만 label cardinality를 폭발시킬 수 있으므로 structured metadata 또는 log field로 둔다.
- raw payload, token, email, phone, cookie는 log body에도 넣지 않는다.
- “로그 없음”은 성공 증거가 아니다. Audit 성공은 별도 record가 필요하다.

## 7. Traces: Tempo와 context

Tempo는 trace backend이며 Grafana와 통합된다.
Tempo setup 문서는 tracing pipeline에 client instrumentation, pipeline, backend, visualization이 필요하다고 설명한다. [Tempo Set up for tracing](https://grafana.com/docs/tempo/latest/set-up-for-tracing/)
Tempo architecture 문서는 trace가 instrumented application → collector/pipeline → backend store → Grafana 같은 visualization tool로 이동한다고 설명한다. [Tempo Architecture](https://grafana.com/docs/tempo/latest/introduction/architecture/)

Trace 운영 원칙:

- 모든 요청을 100% 장기 보존하지 않아도 된다. Sampling과 retention 정책을 둔다.
- 오류와 고지연 trace는 놓치지 않도록 head/tail sampling 정책을 설계한다.
- Log에는 trace_id와 span_id를 연결하되 label로 무제한 확장하지 않는다.
- Span attribute에는 bounded enum과 route template을 우선한다.
- 사용자 ID, request ID, raw URL, 예외 메시지 전체를 high-cardinality dimension으로 남용하지 않는다.

## 8. Grafana는 visualization과 탐색 UI다

Grafana는 Prometheus, Loki, Tempo, Mimir 같은 data source를 조회해 panel, Explore, alert UI를 제공한다.
Grafana dashboard가 있다는 사실은 backend 저장 성공이나 audit 성공을 뜻하지 않는다.
Grafana 장애와 Prometheus/Loki/Tempo ingestion 장애도 분리해서 보아야 한다.

운영 질문:

- Dashboard가 느린가, data source query가 느린가?
- Grafana auth 문제인가, backend tenant header 문제인가?
- Query time range가 잘못됐는가, source sample이 stale인가?
- Dashboard panel이 없는가, telemetry 자체가 없는가?

## 9. Source sample freshness와 query time

Prometheus에서 query evaluation time은 PromQL이 평가되는 기준 시각이다.
Sample freshness는 source에서 마지막 sample이 언제 수집됐는지다.
둘이 다르면 dashboard가 “현재값”처럼 보여도 실제로는 오래된 sample일 수 있다.

확인해야 할 값:

- scrape target `up`
- 핵심 metric별 `timestamp()`와 `time()` 차이
- Collector exporter queue와 실패 count
- Loki/Tempo ingestion reject count
- backend query frontend latency
- source app clock skew

## 10. Shared backend fault domain

한 개 object store, 한 개 gateway, 한 개 DNS, 한 개 identity provider에 metrics/logs/traces가 모두 의존하면 관측 전체가 동시에 흔들릴 수 있다.
Mimir, Loki, Tempo를 같은 Kubernetes cluster와 같은 object storage에 올리는 것은 운영 단순성을 주지만 shared fault domain도 만든다.

설계 질문:

- backend 장애 때 애플리케이션 SDK가 blocking되는가, drop되는가?
- Collector queue가 memory인지 disk인지, overflow 때 무엇을 버리는가?
- object storage 장애가 metrics/logs/traces 모두에 같은 영향을 주는가?
- Grafana가 죽어도 alert evaluation은 계속되는가?
- remote write 장애가 edge Prometheus local query까지 망가뜨리는가?

## 11. Tenant header는 인증이 아니다

Mimir, Loki, Tempo 계열은 multi-tenancy에서 `X-Scope-OrgID` 같은 tenant header를 쓴다.
그러나 header 값 자체가 사용자 인증은 아니다.
Mimir 문서는 요청의 tenant ID를 `X-Scope-OrgID` header에서 읽고, 실수·악성 호출 방지를 위해 인증 reverse proxy가 요청을 인증하고 tenant header를 주입해야 한다고 설명한다. [Mimir authentication and authorization](https://grafana.com/docs/mimir/latest/manage/secure/authentication-and-authorization/)
Tempo 인증 문서도 Tempo 자체에 포함된 authentication layer가 없고, multi-tenant mode에서는 `X-Scope-OrgID`를 trusted client 또는 인증 proxy가 채워야 한다고 설명한다. [Tempo authentication](https://grafana.com/docs/tempo/latest/operations/authentication/)

따라서:

- 외부 client가 tenant header를 임의로 보낼 수 있으면 안 된다.
- Gateway/reverse proxy가 인증 후 tenant를 결정해야 한다.
- Grafana data source secret과 backend tenant header를 혼동하지 않는다.
- Tenant isolation test는 “다른 tenant query가 실패하는지”까지 확인해야 한다.

## 12. OSS, AGPL, Enterprise, CNCF 구분

- Prometheus는 CNCF graduated project다. CNCF project page는 Prometheus가 2018-08-09 Graduated로 이동했다고 설명한다. [Prometheus CNCF](https://www.cncf.io/projects/prometheus/)
- OpenTelemetry도 CNCF project다. CNCF project page는 OTel이 2026-05-11 Graduated로 이동했다고 설명한다. [OpenTelemetry CNCF](https://www.cncf.io/projects/opentelemetry/)
- Grafana Labs의 Loki, Tempo, Mimir는 open source이지만 모두가 CNCF project인 것은 아니다.
- Grafana Labs licensing page는 핵심 OSS 프로젝트들이 Apache-2.0에서 AGPLv3로 이동했다고 설명한다. [Grafana Licensing](https://grafana.com/licensing/)
- Mimir GitHub README는 Mimir가 AGPL-3.0-only로 배포된다고 설명한다. [Grafana Mimir GitHub](https://github.com/grafana/mimir)
- Enterprise/Cloud 제품은 지원, 운영 기능, 관리형 서비스, 인증 통합이 다를 수 있다.

라이선스와 거버넌스는 기능 선택과 별개로 검토해야 한다.
“오픈소스”, “CNCF”, “Grafana Labs 제품”, “Enterprise 기능”은 같은 말이 아니다.

## 13. Illustrative Collector 조각

```yaml
# 실행하지 않은 illustrative 예시: 실제 component 이름과 backend URL은 배포판별로 검증해야 한다.
receivers:
  otlp/app:
    protocols:
      grpc: {}
      http: {}
processors:
  memory_limiter: { limit_mib: 512 }
  batch: { timeout: 5s }
exporters:
  otlphttp/loki_logs:
    endpoint: https://loki.example.invalid/otlp
  otlp/tempo_traces:
    endpoint: tempo.example.invalid:4317
  prometheusremotewrite/mimir_metrics:
    endpoint: https://mimir.example.invalid/api/v1/push
service:
  pipelines:
    logs: { receivers: [otlp/app], processors: [memory_limiter, batch], exporters: [otlphttp/loki_logs] }
    traces: { receivers: [otlp/app], processors: [memory_limiter, batch], exporters: [otlp/tempo_traces] }
    metrics: { receivers: [otlp/app], processors: [memory_limiter, batch], exporters: [prometheusremotewrite/mimir_metrics] }
```

이 조각은 구조 설명용이다.
실제 운영에서는 TLS, auth proxy, tenant header injection, queue/retry, redaction, component availability, version compatibility를 별도 검증한다.

## 14. Lifecycle 예시

| 단계 | Metrics | Logs | Traces |
| --- | --- | --- | --- |
| 생성 | SDK counter/histogram 또는 `/metrics` | app logger 또는 OTel log appender | OTel span |
| 수집 | Prometheus scrape 또는 Collector OTLP | Collector OTLP/filelog | Collector OTLP |
| 처리 | relabel, aggregation, remote write | redaction, structured metadata | sampling, batch |
| 저장 | Prometheus 또는 Mimir | Loki | Tempo |
| 조회 | PromQL | LogQL | TraceQL/trace ID |
| 시각화 | Grafana panel/alert | Grafana Explore | Grafana trace view |

## 15. Failure table

| 증상 | 흔한 원인 | 먼저 볼 증거 | 안전한 대응 |
| --- | --- | --- | --- |
| metric 값이 두 배 | Prometheus scrape와 OTel export 중복 | series label, scrape target | source of truth 하나로 정리 |
| dashboard는 현재인데 실제 source stale | query time과 sample time 혼동 | `timestamp()`, scrape health | freshness panel과 alert 추가 |
| Loki ingestion 400 | label/metadata 제한 초과, OTLP config 불일치 | rejected sample metric, distributor log | label 줄이고 structured metadata 조정 |
| trace 검색 불가 | sampling/drop, context 전파 누락 | collector queue, trace_id log | propagation과 sampling 정책 확인 |
| Grafana만 장애 | data source auth/UI 문제 | backend direct query, Grafana log | backend ingestion과 UI 장애 분리 |
| tenant data가 섞임 | header를 client가 직접 설정 | proxy config, tenant tests | 인증 proxy가 header 주입 |
| 모든 신호가 동시에 중단 | shared object store/gateway 장애 | backend component health | fault domain 분리와 degraded mode |
| archive 실패가 live path를 막음 | Kafka→Spark→Iceberg를 필수 dependency로 둠 | workflow dependency | selected event archive를 비동기로 분리 |

## 16. 설계 체크리스트

- Metrics source of truth가 Prometheus scrape인지 OTel OTLP인지 정했는가?
- Loki label cardinality와 structured metadata 경계를 정했는가?
- Tempo trace retention과 sampling 정책을 정했는가?
- Grafana 장애가 alert evaluation과 ingestion을 멈추지 않는가?
- Mimir 도입 이유가 장기 저장·중앙 scale인지 명확한가?
- Tenant header를 인증으로 오해하지 않고 proxy에서 주입하는가?
- OSS/AGPL/Enterprise/CNCF 구분을 dependency review에 남겼는가?
- Kafka→Spark→Iceberg archive가 live observability path와 분리됐는가?

## 17. 복습 문제와 답

1. **질문:** LGTM의 M은 무엇이며 초기형에서는 무엇을 쓸 수 있는가?  
   **답:** 기술적으로 Mimir를 뜻하지만, 초기형에서는 Prometheus가 metrics 저장·query 중심이 될 수 있다.
2. **질문:** OTel Collector와 backend의 차이는 무엇인가?  
   **답:** Collector는 telemetry를 receive/process/export하는 pipeline이고, backend는 저장·query·retention을 담당한다.
3. **질문:** Prometheus scrape와 OTel metric export를 동시에 쓰면 왜 위험한가?  
   **답:** 같은 값을 중복 수집해 rate, alert, autoscaling 판단을 왜곡할 수 있기 때문이다.
4. **질문:** Loki에서 trace_id를 label로 남용하면 왜 위험한가?  
   **답:** trace_id는 요청마다 달라지는 high-cardinality 값이라 index와 query 비용을 폭발시킬 수 있다.
5. **질문:** `X-Scope-OrgID`가 인증이 아닌 이유는?  
   **답:** tenant 식별 header일 뿐이며, 누가 어떤 tenant를 쓸 수 있는지는 인증 reverse proxy가 검증하고 주입해야 한다.

## 18. 공식 자료

- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [OpenTelemetry Metrics](https://opentelemetry.io/docs/specs/otel/metrics/)
- [OpenTelemetry Logs](https://opentelemetry.io/docs/specs/otel/logs/)
- [Prometheus Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Prometheus Querying Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Mimir Introduction](https://grafana.com/docs/mimir/latest/introduction/)
- [Loki labels](https://grafana.com/docs/loki/latest/get-started/labels/)
- [Loki native OTLP](https://grafana.com/docs/loki/latest/send-data/otel/native_otlp_vs_loki_exporter/)
- [Tempo setup](https://grafana.com/docs/tempo/latest/set-up-for-tracing/)
- [Mimir authentication and authorization](https://grafana.com/docs/mimir/latest/manage/secure/authentication-and-authorization/)
- [Grafana Licensing](https://grafana.com/licensing/)
- [Prometheus CNCF](https://www.cncf.io/projects/prometheus/), [OpenTelemetry CNCF](https://www.cncf.io/projects/opentelemetry/)

[위로: data-pipelines README](README.md) · 이전: [Airflow 오케스트레이션](10-airflow-orchestration.md) · 다음: [현재 아키텍처](12-current-architecture.md)
