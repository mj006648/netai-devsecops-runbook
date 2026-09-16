# 10. Airflow 상위 워크플로 오케스트레이션
[위로: data-pipelines README](README.md) · 이전: [실습·복습](09-labs-and-review.md) · 다음: [LGTM 관측 스택](11-lgtm-observability.md)

## 문서 기준
- 조사 기준: **2026-09-15**
- 범위: Airflow를 “상위 워크플로 오케스트레이터”로 이해하기 위한 학습 자료다.
- 연결 학습: [OpenTelemetry](01-opentelemetry.md), [Metrics와 Prometheus](07-metrics-and-prometheus.md), [현재 아키텍처](12-current-architecture.md)
- 설치·배포 절차가 아니며 실제 endpoint, credential, 운영 namespace, private incident를 쓰지 않는다.
- YAML/Python 조각은 **실행하지 않은 illustrative 예시**다. 이 저장소에서 Airflow나 Kubernetes cluster를 실행하지 않았다.

## 먼저 기억할 문장
Airflow는 여러 시스템의 “언제 어떤 순서로 호출할지”를 정하는 상위 오케스트레이터다.
Airflow 자체가 Kubernetes quota controller, cross-system transaction manager, 데이터 저장소, audit system이 되는 것은 아니다.
Airflow task 성공은 “호출이 끝났다”는 뜻이지, 원격 시스템의 정책 승인·리소스 생성·WAP publish 완료 증거가 아니다.

## 1. Airflow가 맡는 위치
- DAG는 workflow 의도를 코드로 표현한다.
- Scheduler는 실행할 Task Instance를 만들고 queue에 넣는다.
- Executor/worker는 각 task의 operator 코드를 실행한다.
- Operator는 외부 API, SQL, shell, sensor 같은 구체 작업을 감싼다.
- Metadata DB는 Dag Run, task instance state, retry, log 위치 같은 Airflow 내부 상태를 저장한다.
- Airflow 공식 core concepts는 Dag, Dag Run, Task, Task Instance, Sensors, Deferrable Operators를 별도 개념으로 설명한다. [Airflow Core Concepts](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/)

## 2. 책임 경계
| 구성 요소 | 이 장에서의 역할 | 맡지 않는 것 |
| --- | --- | --- |
| Airflow | 승인된 workflow 순서, retry, timeout, pool 제한 | Kubernetes 실제 quota enforcement, 원격 rollback |
| Hub API | 요청 검증과 Member 쪽 조치 요청 | CRD 소유자 또는 모든 cluster 상태의 단일 truth |
| Member Connector | Hub 요청을 검증하고 Custom Resource **인스턴스** 생성 | CRD 정의 생성, 로컬 reconcile |
| Local Operator | 생성된 CR과 하위 Job의 reconcile·상태 보고 | Airflow retry 정책 결정, Hub 업무 상태 직접 변경 |
| WAP audit/publish | write-audit-publish 결과 증거 | “로그에 에러 없음”으로 대체 불가 |
| Observability stack | 실행 상태 관측 | 업무 승인 상태의 최종 증거 |

## 3. DAG, Task, Task Instance, Dag Run
- **DAG**는 task와 dependency graph의 정의다.
- **Task**는 DAG 안의 작업 정의다.
- **Task Instance**는 특정 Dag Run에서 특정 task가 실행되는 실체다.
- **Dag Run**은 DAG가 한 번 실행된 인스턴스다. Airflow 문서는 Dag Run을 “DAG의 시간상 실행 인스턴스”로 설명하고, 각 Dag Run은 서로 별도로 실행될 수 있다고 설명한다. [Airflow Dag Runs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html)
- `run_id`는 수동 실행, 예약 실행, backfill, 외부 trigger를 구분하는 핵심 식별자다.
- `task_id`만으로 실행을 특정하지 않는다. `dag_id + run_id + task_id + map_index + try_number`까지 보아야 같은 시도를 찾는다.

## 4. Run ID와 입력 고정
좋은 workflow는 “같은 run이 무엇을 처리했는지”를 재구성할 수 있어야 한다.
| 값 | 권장 사용 |
| --- | --- |
| `dag_id` | workflow 종류 |
| `run_id` | 실행 인스턴스 식별 |
| `logical_date` | schedule 의미가 있는 시간 축 |
| `request_id` | Hub API 요청과 외부 audit 연결 |
| `input_digest` | 실행 입력 snapshot 검증 |
| `target_revision` | 적용할 정책/템플릿/이미지 버전 |
Retry 때 입력을 다시 “현재값”으로 읽으면 같은 task가 다른 결과를 만들 수 있다.
승인 요청 payload, policy revision, 대상 resource 이름, dry-run 결과는 run 시작 시점에 고정하고 audit에 남긴다.

## 5. Retry는 idempotent해야 한다
Airflow는 transient failure를 다루기 위해 retry를 제공하지만, retry는 같은 side effect를 여러 번 만들 수 있다.
Airflow best practices는 task를 database transaction처럼 다루고, 실패 후 재실행해도 같은 결과를 만들도록 설계하라고 설명한다. [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/3.0.0/best-practices.html)

Idempotent 설계 원칙:
- `POST create`만 쓰지 말고 idempotency key나 deterministic resource name을 쓴다.
- 이미 생성된 요청은 `GET`/`PATCH`/server-side apply처럼 수렴하는 방식으로 확인한다.
- 외부 job ID는 task retry 사이에 보존한다.
- “마지막 시도에서 성공”만 보지 말고 이전 시도가 만든 side effect도 audit한다.
- timeout 후 원격 작업이 계속될 수 있으므로 cancel/cleanup API의 의미를 문서화한다.

## 6. Pools는 Airflow 내부 동시성 제한이다
Airflow Pools는 특정 task 묶음이 동시에 너무 많이 실행되지 않도록 worker slot을 제한한다.
공식 문서는 pool이 arbitrary task set의 execution parallelism을 제한하고, capacity가 차면 runnable task가 queued 상태가 된다고 설명한다. [Airflow Pools](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/pools.html)

중요한 경계:
- Pool slot은 Airflow scheduling 제한이다.
- Pool slot은 Kubernetes CPU/memory quota가 아니다.
- Pool slot은 Member cluster의 API rate limit을 실제로 보장하지 않는다.
- Pool slot은 이미 실행 중인 원격 reconcile을 중단하지 않는다.
- 원격 quota는 Kubernetes ResourceQuota, admission policy, operator validation, API gateway rate limit에서 별도로 집행한다.

## 7. Sensor와 deferrable operator
Sensor는 어떤 조건이 만족될 때까지 기다리는 operator다.
Airflow sensor 문서는 `poke` mode가 전체 runtime 동안 worker slot을 차지하고, `reschedule` mode가 check 사이에 worker slot을 놓는다고 설명한다. [Airflow Sensors](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html)

Deferrable operator는 기다릴 일이 있을 때 worker slot을 비우고 triggerer로 대기 로직을 넘긴다.
Airflow deferring 문서는 deferred phase에서 worker slot을 점유하지 않으며, 기본적으로 deferred task가 pool slot도 점유하지 않는다고 설명한다. 필요하면 pool 설정에서 deferred task 포함 여부를 바꾼다. [Deferrable Operators & Triggers](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html)

운영 주의:
- Triggerer는 async Python 코드가 막히면 많은 대기 task에 영향을 준다.
- Trigger는 network partition 등으로 두 번 실행될 수 있다고 가정해야 한다.
- Deferrable sensor는 worker 절약 장치이지 외부 이벤트의 정확히 한 번 처리를 보장하지 않는다.
- Deferred task를 pool 계산에 포함하지 않으면 대기 task가 pool budget을 우회할 수 있다.
- Long polling은 Hub API와 Member Operator 모두에서 idempotent하고 bounded해야 한다.

## 8. Airflow는 자동 cross-system rollback을 제공하지 않는다
예시 순서:
1. Airflow task가 Hub API에 publish 요청을 보낸다.
2. Hub API가 요청을 accepted 상태로 저장한다.
3. Member Connector가 CR 인스턴스를 만든다.
4. Local Operator reconcile이 일부 Kubernetes resource를 만든다.
5. WAP audit publish 단계에서 검증이 실패한다.
Airflow가 task 실패를 감지해도 2~4단계 side effect를 자동으로 되돌리지 않는다.
Rollback이 필요하면 보상 task를 설계해야 한다.
보상 task도 “이미 지워졌음”, “일부만 생성됨”, “다른 run이 소유권을 이어받음”을 안전하게 처리해야 한다.

## 9. Hub API와 Member Operator의 책임 분리
이 학습 아키텍처에서 Airflow는 직접 CRD를 만들지 않는다.
Airflow는 Hub API를 호출하고, Hub API는 Member 쪽 권한 있는 경로로 요청을 전달한다.
Member Connector는 요청을 검증해 사전에 설치된 CRD의 **Custom Resource 인스턴스**를 만들고, Local Operator가 이를 reconcile한다.
CRD 정의, admission rule, RBAC, namespace quota는 platform lifecycle의 소유물이다.
권장 흐름: `Airflow Dag Run → Hub API request → Member Connector CR instance → Local Operator reconcile/status → WAP audit → publish result`.

## 10. WAP audit 성공 판정
절대 금지: “에러 로그가 없으니 audit 성공”이라고 판단하지 않는다.
Audit 성공에는 명시적인 증거가 필요하다.
- 요청 ID와 run ID가 연결되어 있다.
- 입력 digest와 정책 revision이 audit record에 있다.
- 생성/수정된 CR 인스턴스 이름과 UID가 있다.
- Local Operator status condition이 관찰됐다.
- 테이블·자산 참조·snapshot/commit·실행 세대에 대한 Audit 결과가 명시적으로 저장됐다.
- 실패 시 어떤 단계에서 멈췄는지 reason code가 있다.
Audit 통과 뒤에만 Publish를 수행하고, 최종 성공은 Audit 결과와 Publish 적용 결과를 함께 확인한다. 로그는 원인 분석 보조 자료다.

## 11. Kafka → Spark → Iceberg의 위치
Airflow live path가 장기 저장 성공을 기다릴 필요는 없다.
선별된 장기 이벤트만 Kafka에 남기고, Spark가 batch 또는 micro-batch로 Iceberg에 적재할 수 있다.
이 경로는 분석·재현·장기 감사에 유용하지만, live 승인·publish 경로의 필수 의존성으로 두지 않는다.
Kafka 지연이나 Iceberg commit 실패가 곧바로 사용자 workflow 실패가 되면 운영 제어면이 장기 archive 상태에 묶인다.

## 12. Illustrative DAG 조각
```python
# 실행하지 않은 illustrative 예시: 실제 Airflow package와 provider를 검증하지 않았다.
with DAG(dag_id="training_member_publish", schedule=None, catchup=False) as dag:
    freeze_input = PythonOperator(task_id="freeze_input", python_callable=freeze_request)
    call_hub = SimpleHttpOperator(task_id="call_hub_api", method="POST", endpoint="/example/member/publish", pool="hub_api_writes", retries=3)
    wait_member = HttpSensor(task_id="wait_member_status", endpoint="/example/member/status/{{ run_id }}", mode="reschedule", poke_interval=60, timeout=3600)
    verify_wap = PythonOperator(task_id="verify_wap_result", python_callable=verify_wap_result)
    freeze_input >> call_hub >> wait_member >> verify_wap
```
이 코드는 모양 설명용이다. 실제 운영에서는 auth, TLS, idempotency key, request body template, response validation, audit schema, retry policy를 별도 검증해야 한다.

## 13. Lifecycle 예시
| 단계 | 성공 증거 | 실패 시 판단 |
| --- | --- | --- |
| 입력 고정 | `input_digest` 저장 | retry 전 입력 변경 금지 |
| Hub API 호출 | `request_id` accepted | timeout이면 중복 호출 가능성 확인 |
| CR 인스턴스 생성 | name/uid/status observed | CRD 없음과 권한 오류 구분 |
| reconcile | condition transition | operator 재시도와 Airflow 재시도 분리 |
| WAP audit | 명시적 검증 결과 | 로그 부재로 통과 처리 금지 |
| Publish | 적용된 catalog/metadata 참조와 상태 | Audit 통과와 실제 Publish 적용을 구분 |
| 장기 archive | optional event emitted | live path 성공과 분리 |

## 14. Failure table
| 증상 | 흔한 원인 | 먼저 볼 증거 | 안전한 대응 |
| --- | --- | --- | --- |
| task retry 후 중복 생성 | non-idempotent POST | request_id, resource name | idempotency key와 deterministic name 도입 |
| pool이 있는데 API 과부하 | pool을 quota로 오해 | Airflow queued/running, API 429 | gateway/operator rate limit 별도 설정 |
| sensor가 worker를 고갈 | `poke` mode 장시간 대기 | worker slot, sensor mode | reschedule/deferrable 검토 |
| deferrable 전환 후 동시성 증가 | deferred task가 pool slot 미점유 | pool 설정 | deferred 포함 여부와 remote limit 재검토 |
| Airflow 성공인데 publish 누락 | 마지막 task가 Publish 결과를 확인하지 않음 | Audit 결과와 Publish 적용 상태 | 최종 확인 task를 terminal gate로 둠 |
| 실패 뒤 원격 리소스 잔존 | rollback 자동화 오해 | CR owner/status | 보상 workflow를 idempotent하게 작성 |
| 장기 archive 지연이 live 장애로 전파 | archive를 필수 경로로 둠 | dependency graph | selected event archive를 비동기로 분리 |
| “로그 조용함”을 성공으로 판정 | audit source 부재 | audit table/status condition | 명시적 Audit와 Publish 결과만 성공 인정 |

## 15. 복습 문제와 답
1. **질문:** DAG와 Dag Run은 어떻게 다른가?  
   **답:** DAG는 workflow 정의이고, Dag Run은 그 정의가 한 번 실행된 인스턴스다.
2. **질문:** Airflow Pool이 Kubernetes quota가 아닌 이유는?  
   **답:** Pool은 Airflow scheduler 내부의 task slot 제한이며, 원격 cluster의 CPU/memory/API quota를 집행하지 않는다.
3. **질문:** Deferrable operator를 쓰면 어떤 slot이 비워지는가?  
   **답:** 대기 중 worker slot을 비울 수 있다. 기본적으로 pool slot도 점유하지 않을 수 있어 pool 설정 확인이 필요하다.
4. **질문:** Airflow retry에서 idempotency가 중요한 이유는?  
   **답:** 실패한 task가 이미 외부 side effect를 만들었을 수 있고, 재실행이 같은 side effect를 중복 생성할 수 있기 때문이다.
5. **질문:** “에러 로그 없음”이 WAP audit 성공이 될 수 없는 이유는?  
   **답:** 로그는 관측 보조 자료일 뿐이며, 성공은 요청 ID·입력 digest·상태 condition·publish marker 같은 명시적 audit evidence로 판단해야 한다.

## 16. 공식 자료
- [Airflow Core Concepts](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/)
- [Airflow Dag Runs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html)
- [Airflow Pools](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/pools.html)
- [Airflow Sensors](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html)
- [Airflow Deferrable Operators & Triggers](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html)
- [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/3.0.0/best-practices.html)

[위로: data-pipelines README](README.md) · 이전: [실습·복습](09-labs-and-review.md) · 다음: [LGTM 관측 스택](11-lgtm-observability.md)
