# 07. Metrics와 Prometheus — 신뢰 가능한 제어 텔레메트리

## 이 장의 위치

- 상위 문서: [운영 데이터 파이프라인 학습 자료](README.md), [Kubernetes Observability](../README.md)

## 문서 기준

- 조사일: **2026-09-15**
- 기준 문서: Prometheus latest docs, OpenTelemetry metrics spec, Grafana latest docs
- 예시는 학습용입니다. 이 저장소에서는 Prometheus, Alertmanager, Grafana, OTel Collector를 실행하지 않았습니다.
- 실제 endpoint, receiver, credential, private incident, 원시 운영 metric을 쓰지 않습니다.

## 먼저 기억할 문장

Prometheus는 **metric time series를 수집·저장·조회**하는 시스템입니다.
Alertmanager는 알림을 라우팅하는 계층이지 실제 상태를 고치는 controller가 아닙니다.
제어에 쓰는 metric은 freshness, cardinality, reset, aggregation 오류를 견딜 수 있어야 합니다.

## 1. 이 장에서 가정하는 전체 그림

- 예시 흐름은 `metrics fast path -> operations policy -> authorized Member Operator`다.
- Prometheus는 상태를 관찰하고 alert rule을 평가한다.
- Alertmanager는 알림을 그룹화, 억제, 라우팅한다.
- Grafana는 optional visualizer로 둔다.
- Portal은 사용자가 보는 제품 경험과 정책 흐름의 일부일 수 있지만, Grafana 자체와 동일하지 않다.
- metric은 제어 판단의 입력이지 자동 조치 권한이 아니다.

## 2. Prometheus data model의 핵심

- Prometheus는 모든 데이터를 time series로 저장한다.
- time series는 metric name과 label set으로 식별된다. [Prometheus data model](https://prometheus.io/docs/concepts/data_model/)
- 같은 metric name이라도 label 값 조합이 달라지면 다른 series다.
- label 하나의 값이 계속 늘어나면 저장 series 수가 폭발한다.
- Prometheus 문서는 label 값 변경도 새 time series를 만든다고 설명한다. [Prometheus data model](https://prometheus.io/docs/concepts/data_model/)
- metric name은 측정 대상을 나타내야 한다.
- label은 같은 측정 대상의 차원을 나타내야 한다.
- label에 user ID, request ID, email, trace ID처럼 무한에 가까운 값을 넣지 않는다.
- Prometheus naming best practice는 high-cardinality label 사용을 경고한다. [Metric and label naming](https://prometheus.io/docs/practices/naming/)

## 3. 네 가지 metric type

- Prometheus instrumentation library는 counter, gauge, histogram, summary 네 가지 core type을 제공한다. [Metric types](https://prometheus.io/docs/concepts/metric_types/)
- Counter는 증가만 하며 restart 때 reset될 수 있다.
- 요청 수, error 수, 처리 byte 누계는 counter 후보가 된다.
- Gauge는 오르내릴 수 있는 현재값이다.
- queue depth, in-flight request, memory usage는 gauge 후보가 된다.
- Histogram은 관측값을 bucket에 누적하고 sum과 count도 제공한다.
- 요청 latency, response size 분포는 histogram 후보가 된다.
- Summary는 client 측에서 sliding window quantile을 계산해 노출한다.
- Summary quantile은 instance 간 집계가 어렵다.
- 운영 SLO는 가능하면 histogram 기반으로 설계하는 편이 합산과 집계에 안전하다. [Histograms and summaries](https://prometheus.io/docs/practices/histograms/)

## 4. Counter에는 rate를 쓴다

- raw counter 값은 “프로세스 시작 이후 누계”일 수 있다.
- 그래서 대시보드와 alert에는 보통 `rate(counter[window])`를 사용한다.
- Prometheus 함수 문서는 `rate()`가 counter 증가율 계산에 쓰인다고 설명한다. [Query functions](https://prometheus.io/docs/prometheus/latest/querying/functions/)
- counter reset은 restart나 scrape target 교체 때 발생할 수 있다.
- `resets(counter[window])`는 reset 횟수를 확인하는 보조 query다. [Query functions](https://prometheus.io/docs/prometheus/latest/querying/functions/)
- gauge에 `rate()`를 적용하면 의미가 깨질 수 있다.
- queue depth 변화율이 필요하면 gauge 자체, derivative, predict 계열 사용 여부를 별도로 검토한다.

## 5. Scrape, evaluation, freshness를 구분하기

- Prometheus는 target을 주기적으로 scrape한다.
- `scrape_interval`은 target에서 sample을 가져오는 주기다. [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- `evaluation_interval`은 rule을 평가하는 주기다. [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- query evaluation time은 PromQL 식이 평가되는 기준 시각이다.
- metric freshness는 최근 sample이 실제로 언제 수집되었는지의 문제다.
- 두 값이 같다고 가정하면 stale data로 잘못된 제어 판단을 할 수 있다.
- PromQL은 기본 lookback period 안의 최신 sample을 사용한다. [Querying basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- series가 더 이상 나오지 않으면 stale로 표시되고 query 결과에서 사라질 수 있다. [Querying basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- “0”과 “없음”은 다르다.
- target down으로 series가 사라진 것과 실제 값이 0인 것을 구분해야 한다.

## 6. Percentile 평균은 틀린 신호일 수 있다

- p95는 평균이 아니다.
- instance별 p95를 `avg()`로 평균내면 전체 요청의 p95가 되지 않는다.
- Prometheus histogram 문서는 summary quantile 평균이 통계적으로 의미 없다고 경고한다. [Histograms and summaries](https://prometheus.io/docs/practices/histograms/)
- classic histogram은 `_bucket{le="..."}`, `_sum`, `_count` series를 만든다.
- p90이나 p95는 `histogram_quantile()`로 bucket rate를 집계해서 계산한다. [Query functions](https://prometheus.io/docs/prometheus/latest/querying/functions/)
- classic histogram을 aggregate할 때는 `le` label을 보존해야 한다.
- native histogram은 query 형태가 더 단순할 수 있지만 backend와 client 지원 상태를 확인해야 한다.
- latency SLO는 “무엇을 aggregate할지”를 먼저 정해야 한다.
- service 전체인지, route별인지, cluster별인지가 PromQL 구조를 바꾼다.

## 7. Label cardinality 설계

- cardinality는 metric name과 label 조합 수다.
- `method`, `status_class`, `service`, `namespace`는 bounded label 후보가 될 수 있다.
- `path`는 raw URL path를 그대로 넣으면 위험하다.
- `/users/123`, `/users/456`을 label로 분리하면 series가 계속 늘어난다.
- route template인 `/users/{id}`는 상대적으로 안전하다.
- `pod` label은 Kubernetes에서 자연스럽지만 churn이 크다.
- long-term SLO에는 `deployment`나 `service`처럼 안정적인 차원을 우선한다.
- cardinality 예산은 개발팀과 플랫폼팀의 계약이어야 한다.

## 8. OTel metric bridge와 duplicate scrape

- OpenTelemetry metric data model은 Prometheus 같은 기존 metric format과의 변환을 목표로 한다. [OpenTelemetry metrics data model](https://opentelemetry.io/docs/specs/otel/metrics/data-model/)
- OTel Collector는 receive, process, export를 제공하는 vendor-agnostic collector다. [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- OTel Prometheus exporter는 Prometheus가 pull할 수 있는 endpoint를 제공하는 모델이다. [OTel Prometheus exporter](https://opentelemetry.io/docs/specs/otel/metrics/sdk_exporters/prometheus/)
- 한 target을 Prometheus가 직접 scrape하면서 동시에 OTel Collector가 같은 metric을 export하면 duplicate series가 생길 수 있다.
- duplicate를 피하려면 “누가 scrape의 source of truth인가”를 정한다.
- app이 Prometheus endpoint를 직접 노출하고 Prometheus가 scrape하는 방식이 하나다.
- app이 OTLP로 Collector에 보내고 Collector가 Prometheus remote write 또는 exporter 역할을 하는 방식도 있다.
- 두 방식을 섞을 때는 label, resource attribute, temporality 변환을 명확히 한다.
- OpenTelemetry data model은 metric stream의 single-writer 원칙과 duplicate writer 문제를 설명한다. [OpenTelemetry metrics data model](https://opentelemetry.io/docs/specs/otel/metrics/data-model/)
- 제어 telemetry에서는 중복 수집이 false positive와 잘못된 scaling 판단을 만들 수 있다.

## 9. Alertmanager와 controller의 역할 분리

- Prometheus alerting은 Prometheus server의 alert rule과 Alertmanager로 나뉜다. [Prometheus alerting overview](https://prometheus.io/docs/alerting/latest/overview/)
- Alertmanager는 grouping, inhibition, silence, receiver routing을 담당한다. [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/)
- Alertmanager는 실제 Kubernetes resource를 고치는 controller가 아니다.
- webhook receiver를 붙일 수 있지만, webhook이 곧 안전한 actuator라는 뜻은 아니다.
- 자동 조치가 필요하면 별도 controller가 인증, 인가, idempotency, audit, rate limit을 가져야 한다.
- 이 학습 아키텍처에서는 operations policy가 조건을 해석하고 authorized Member Operator가 조치한다.
- Alertmanager notification은 사람과 시스템에 상태를 알리는 계층으로 제한한다.
- silence는 조치가 아니라 알림 억제다.
- inhibition은 root-cause alert가 있을 때 파생 alert 알림을 줄이는 기능이다.

## 10. Grafana는 optional visualizer다

- Grafana dashboard는 data source query 결과를 panel로 시각화한다. [Grafana visualizations](https://grafana.com/docs/grafana/latest/visualizations/)
- Grafana Prometheus data source는 PromQL query를 Prometheus-compatible backend에 보낸다. [Grafana Prometheus data source](https://grafana.com/docs/grafana/latest/datasources/prometheus/configure/)
- Grafana는 metric 저장소 자체가 아니다.
- Grafana가 있다고 Prometheus alert rule이 자동으로 안전해지는 것도 아니다.
- 따라서 “Grafana 대시보드가 있으니 Portal이 있다”고 말하지 않는다.
- Grafana는 optional visualizer로 두고, source of truth는 Prometheus rule과 policy repository에서 찾는다.

## 11. Trustworthy control telemetry의 조건

- 제어에 쓰는 metric은 일반 dashboard metric보다 기준이 엄격해야 한다.
- 값의 의미가 문서화되어 있어야 한다.
- scrape 실패와 실제 0을 구분해야 한다.
- freshness SLO가 있어야 한다.
- label cardinality가 bounded여야 한다.
- reset과 restart를 해석할 수 있어야 한다.
- query가 aggregation 오류를 만들지 않아야 한다.
- alert rule은 promtool test나 staging replay로 검증해야 한다.
- control loop는 metric 한 개가 아니라 guardrail metric 묶음을 봐야 한다.
- 예를 들어 scale-out 판단은 latency, error rate, queue depth, scrape health를 함께 볼 수 있다.
- 이 조건을 만족하지 못하면 metric은 notification에는 써도 actuator 입력으로 쓰지 않는다.

## 12. 예시 PromQL — 실행 금지, 형태 설명용

```text
# 설명용: service별 5분 HTTP error rate
sum by (service) (
  rate(http_requests_total{status_class="5xx"}[5m])
)
/
sum by (service) (
  rate(http_requests_total[5m])
)
```

- 위 query는 metric과 label이 실제 존재한다고 가정하지 않는다.
- `status_class`는 raw status code보다 cardinality가 낮은 label 예시다.
- denominator가 0일 때 처리 방식은 alert rule에서 별도로 검토해야 한다.

```text
# 설명용: classic histogram으로 service별 p95 latency
histogram_quantile(
  0.95,
  sum by (service, le) (
    rate(http_request_duration_seconds_bucket[5m])
  )
)
```

- classic histogram에서는 `le` label을 보존해야 한다.
- instance별 p95를 평균내는 방식이 아니다.
- bucket 설계가 SLO 경계 주변을 충분히 표현해야 한다.

```text
# 설명용: target freshness 확인 형태
max by (job, instance) (
  time() - timestamp(up{job="EXAMPLE_JOB"})
)
```

- `EXAMPLE_JOB`은 placeholder다.
- `up == 1`이어도 다른 metric이 stale일 수 있으므로 핵심 metric별 freshness도 본다.
- live 환경에서 실행하기 전에 cardinality와 결과 series 수를 확인한다.

## 13. Recording rule과 alert rule의 안전한 사용

- 복잡한 query는 dashboard마다 반복하기보다 recording rule로 사전 계산할 수 있다.
- recording rule은 비용을 낮추고 query 의미를 표준화한다.
- 잘못된 recording rule은 잘못된 값을 빠르게 전파한다.
- rule 이름은 단위와 aggregation 차원을 드러내야 한다.
- alert rule은 “조건, 지속 시간, severity, runbook link”가 함께 있어야 한다.
- `for:`는 순간 spike와 지속 장애를 구분하는 장치다.
- `for:`가 너무 길면 감지가 늦고 너무 짧으면 flapping이 늘어난다.
- alert label은 routing에 쓰이므로 cardinality를 제한한다.
- annotation에는 사람이 읽는 설명과 안전한 runbook link를 둔다.
- 자동 조치에 필요한 내부 세부정보나 비밀값은 annotation에 넣지 않는다.

## 14. Troubleshooting table

| 증상 | 먼저 볼 것 | 흔한 원인 | 안전한 다음 단계 |
| --- | --- | --- | --- |
| error rate가 음수처럼 보임 | counter reset, query window | reset을 gauge처럼 해석 | `rate()` window와 `resets()` 확인 |
| p95가 이상하게 낮음 | histogram bucket, aggregation | instance p95 평균 또는 `le` 누락 | `histogram_quantile` 입력 구조 재검토 |
| dashboard가 느림 | result series 수, label matcher | high-cardinality selector | tabular query로 series 수 줄인 뒤 graph 사용 |
| alert가 flapping | `for`, scrape 실패, threshold | threshold가 noise에 가까움 | 지속 시간과 multi-signal guardrail 조정 |
| 값이 0인지 없음인지 불명확 | stale marker, `up`, timestamp | target down 또는 metric 제거 | freshness query와 target health 확인 |
| OTel과 Prometheus 값이 두 배 | scrape 경로 | direct scrape와 collector export 중복 | source of truth와 label 변환 정리 |
| Grafana만 장애 | Prometheus API, data source config | visualizer 문제 | control loop가 Grafana 의존인지 확인 |
| 자동 조치가 과함 | actuator audit, policy | alert를 직접 actuator로 연결 | Alertmanager와 controller 경계 재설계 |

## 15. 설계 체크리스트

| 질문 | 안전한 답의 방향 |
| --- | --- |
| metric type을 알고 있는가? | counter, gauge, histogram, summary를 문서화한다. |
| label cardinality가 bounded인가? | unbounded ID류 label을 금지한다. |
| freshness를 측정하는가? | query evaluation time과 sample timestamp를 분리한다. |
| reset을 해석할 수 있는가? | restart, rollout, scrape target 변경 기록과 연결한다. |
| percentile을 올바르게 aggregate하는가? | histogram bucket rate로 계산하고 summary quantile 평균을 피한다. |
| OTel bridge가 중복 수집을 만들지 않는가? | scrape source of truth를 하나로 정한다. |
| Alertmanager가 actuator가 되었는가? | notification과 authorized controller를 분리한다. |
| Grafana 장애가 제어 장애인가? | visualizer와 policy/control plane 의존성을 분리한다. |

## 16. 복습 문제

1. Counter와 gauge를 구분하는 가장 간단한 기준은 무엇인가?
2. label cardinality가 높은 metric이 위험한 이유는 무엇인가?
3. query evaluation time과 metric freshness는 어떻게 다른가?
4. instance별 p95를 평균내면 왜 안 되는가?
5. OTel Collector와 Prometheus direct scrape를 동시에 쓰면 어떤 문제가 생길 수 있는가?
6. Alertmanager와 controller의 역할은 어떻게 다른가?
7. Grafana와 Portal을 구분해야 하는 이유는 무엇인가?

## 17. 정답

1. 값이 감소할 수 있으면 gauge, 단조 증가하고 restart 때 reset될 수 있으면 counter를 우선 검토한다.
2. label 값 조합마다 새 time series가 생겨 저장 비용, query 비용, alert 비용이 급증하기 때문이다.
3. evaluation time은 PromQL 식이 평가되는 기준 시각이고 freshness는 sample이 실제 수집된 최신 시각과의 차이다.
4. quantile은 합산 가능한 평균값이 아니며 전체 요청 분포의 p95를 보존하지 않기 때문이다.
5. 같은 metric stream을 두 경로가 쓰면 duplicate series, double counting, reset 오해가 생길 수 있다.
6. Alertmanager는 알림을 그룹화·억제·라우팅하고, controller는 인증·인가·감사·idempotency를 갖고 실제 상태를 변경한다.
7. Grafana는 시각화 도구이고 Portal은 사용자 workflow, 승인, 정책, 권한을 담을 수 있는 제품 표면이기 때문이다.

## 18. 버전 주의와 검증 상태

- 문서 기준일은 2026-09-15이다.
- Prometheus 3.x 문서에는 native histogram, UTF-8 name 등 버전별 주의가 포함되어 있다.
- OpenTelemetry metric 변환과 Collector component 지원 상태는 배포판과 버전에 따라 다를 수 있다.
- Grafana 기능과 UI 명칭은 release에 따라 바뀔 수 있다.
- 이 장의 PromQL은 설명용이며 live 실행으로 검증하지 않았다.
- 공개 문서 안전을 위해 실제 endpoint, receiver, credential, 내부 장애 식별자는 포함하지 않았다.
- 운영 적용 전에는 대상 버전 공식 문서, rule test, staging dashboard, rollback 절차를 별도로 확인한다.
