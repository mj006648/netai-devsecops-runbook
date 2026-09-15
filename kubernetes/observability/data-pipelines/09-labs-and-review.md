# 9. 안전한 실습과 종합 복습

[학습 목차](README.md) · 이전: [통합 설계](08-integration-design.md)

## 1. 실습 범위와 준비

이 장의 실행 가능한 실습은 Python 표준 라이브러리만 사용하는 **메모리 기반 모형**이다.

- Kafka, Flink, OpenSearch, Spark, Iceberg를 설치하거나 실행하지 않는다.
- 네트워크에 연결하지 않고 파일을 읽어 결과를 출력한다.
- 실제 broker ACK, 디스크 내구성, checkpoint 또는 성능을 검증하지 않는다.
- production credential, Kubernetes 권한, Docker daemon이 필요하지 않다.
- 저장소를 내려받고 Python 3.10 이상이 있는 환경에서 실행한다.

도구의 용어를 이해하기 전에 무거운 stack 전체를 설치하면 문제의 원인보다 설치 오류를 먼저 만나기 쉽다. 이 실습은 **중복·진행률·보존기간·순서**에 집중한다. 실제 서비스 시험 계획은 뒤에서 별도로 설명한다.

## 2. 제공 파일

| 파일 | 내용 |
| --- | --- |
| [events.jsonl](examples/events.jsonl) | 물리 record 10개, 논리 사건 8개인 가상 입력 |
| [replay_demo.py](examples/replay_demo.py) | hot/archive 독립 진행, 재시도, 보존 구간 누락 모형 |
| [test_replay_demo.py](examples/test_replay_demo.py) | 모형의 재현 가능한 자동 테스트 |

입력에는 같은 event의 재전송 2건과, 늦게 도착한 이전 상태 사건이 포함돼 있다. 모든 이름과 byte 값은 설명용이다. 이 모형은 run마다 producer/attempt가 하나라는 가정을 가지며, sequence를 전역 Kafka 순서나 실제 업무 상태의 권위 기준으로 일반화하지 않는다.

## 3. 실습 A — archive가 멈춰도 hot은 진행

저장소 루트에서 실행한다.

```bash
python3 kubernetes/observability/data-pipelines/examples/replay_demo.py
```

모형의 동작:

1. 입력을 순서대로 메모리의 source log에 넣는다.
2. hot 소비자는 한 번의 가상 실패에서 cursor를 진행하지 않고 다음에 재시도한다.
3. archive 소비자는 초반에 멈춰 있다가 backlog를 처리한다.
4. hot은 event ID로 문서를 표현하고 archive는 물리 source record를 보존한다.

주요 기대값:

| 필드 | 값 | 의미 |
| --- | ---: | --- |
| simulation | true | 실제 서비스가 아닌 모형 |
| source_records | 10 | 전달 record 수 |
| logical_events | 8 | 서로 다른 사건 ID 수 |
| duplicate_source_records | 2 | 같은 사건을 다시 보낸 record 수 |
| hot_documents | 8 | ID 기준 검색 문서 수 |
| archive_records | 10 | source record를 보존한 수 |
| logical_sink_sets_match | true | 물리 행 수는 달라도 논리 사건 집합은 같음 |

**핵심:** OpenSearch 쪽 문서 수와 archive 행 수가 다르다고 즉시 누락이라고 판단하면 안 된다. 무엇을 한 건으로 셌는지 먼저 확인한다. 반대로 행 수가 같다고 내용도 같다는 뜻은 아니다.

## 4. 실습 B — retention을 넘긴 소비자는 어떻게 되나?

```bash
python3 kubernetes/observability/data-pipelines/examples/replay_demo.py --scenario retention-gap
```

이 명령은 의도적으로 **종료 코드 2**를 반환한다. `set -e` 환경에서는 명령 묶음이 종료될 수 있으므로 별도 터미널 명령으로 실행한다.

주요 결과:

- `status`: `retention_gap`
- `archive_next_offset`: `0`
- `earliest_available_source_offset`: `3`
- `missing_source_offsets`: `[0, 1, 2]`
- `logical_sink_sets_match`: `false`

archive는 아직 offset 0부터 필요하지만 source가 제공하는 시작점은 3이다. 모형은 이것을 숨기고 3부터 성공한 것처럼 진행하지 않는다.

**주의:** “이 source에서 재처리할 수 없다”와 “어디에서도 복구할 수 없다”는 다른 말이다. 별도 백업이나 다른 저장소의 충분한 기록이 있으면 복구 경로를 검토할 수 있다. 모형은 그러한 외부 복구를 구현하지 않는다.

## 5. 실습 C — 도착 순서가 최신 업무 상태일까?

정상 실행 결과에서 다음을 비교한다.

- `naive_arrival_state.run-002`: `Preparing`
- `source_sequence_state.run-002`: `Ready`

원인은 Ready 사건 뒤에 이전 Preparing 사건이 늦게 도착했기 때문이다. Kafka가 수신 순서를 보존하더라도 **업무 사건이 처음부터 시간순으로 들어온다는 보장은 별개**다.

실제 운영에서는 producer/attempt/sequence, event time, watermark와 late-event 정책을 검토한다. 실제 자원 제어와 완료 판정은 업무 상태 소유자의 현재 상태로 검증해야 하며, 이 모형의 단순 sequence 선택을 그대로 적용하면 안 된다.

## 6. 자동 테스트 실행

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s kubernetes/observability/data-pipelines/examples \
  -p 'test_*.py'
```

검증 항목:

1. 중복 source record와 논리 사건 수 구분
2. archive pause 중 hot 진행과 재시도
3. 도착 순서와 source sequence 차이
4. retention gap의 명시적 실패와 무단 cursor 이동 방지
5. 같은 event ID에 다른 내용이 들어왔을 때 충돌 검출
6. CLI의 JSON 출력과 정상/예상 실패 종료 코드

현재 모형은 다섯 개의 test method로 위 동작을 묶어 검사한다. 테스트 통과는 모형의 동작 증거일 뿐 실제 Kafka·Iceberg의 exactly-once나 장애 복구 증거가 아니다.

## 7. 실습 D — 보존 용량 계산

가정: 초당 100개 record, 평균 payload 2,000 bytes, 3일 보존, 복제 3개.

```python
rate = 100
payload_bytes = 2000
seconds = 3 * 24 * 60 * 60
replicas = 3
logical_bytes = rate * payload_bytes * seconds
replicated_bytes = logical_bytes * replicas
print(logical_bytes / 1_000_000_000)
print(replicated_bytes / 1_000_000_000)
```

출력은 각각 `51.84`, `155.52`다. **십진 GB** 기준이며 실제 broker 용량 요구의 완성된 계산은 아니다.

이 계산에는 다음이 빠져 있다.

- framing/index/segment/metadata overhead
- 실제 압축률과 payload 분포
- burst와 consumer catch-up 여유
- 디스크 안전 여유, 운영 log와 다른 topic 사용량
- retention.bytes에 의해 시간 조건보다 먼저 만료될 가능성

따라서 평균 payload만으로 디스크를 정확히 채우도록 설계하지 않는다. 실제 입력 분포와 안전 여유를 측정한다.

## 8. 실습 E — p95를 평균내면 왜 틀리나?

다음은 성능 측정이 아니라 수학적 예시다. nearest-rank 정의를 사용한다.

```python
import math

def p95(values):
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]

a = [1] * 99 + [1000]
b = [100] * 100
print(p95(a), p95(b))
print((p95(a) + p95(b)) / 2)
print(p95(a + b))
```

출력:

```text
1 100
50.5
100
```

각 집단의 p95 평균은 전체 p95가 아니다. 실제 시스템에서는 원시 sample이나 병합 가능한 histogram bucket을 이용하고, 어떤 quantile 정의·집계 구간·sample 수를 사용했는지 기록한다.

## 9. 실제 서비스 실습으로 넘어가는 순서

다음 절차는 **학습용 검증 계획이며 이 자료 작성 중 실제 서비스에서 실행하지 않았다.** 현재 환경에서 곧바로 복사할 배포 명세가 아니다.

### 준비 gate

- engine/connector/JDK/Scala/schema/auth 버전 조합 기록
- 격리 namespace·topic·index·catalog/table·checkpoint 이름 지정
- 해당 실습이 만든 리소스를 구분할 label·목록·소유권 기록
- 실제 credential은 Secret/보안 저장소 참조로 주입
- 원본 데이터·기존 PV/PVC·공유 topic/index는 건드리지 않음
- 고정된 synthetic corpus와 expected ID 집합, 시간·byte retention 목표 준비

### 단계별 시험

| 단계 | 시험 | 모을 증거 |
| --- | --- | --- |
| 1 | OTel 한 신호를 Collector까지 전달 | 발생/수신 record 수, schema, 민감정보 제외 |
| 2 | Kafka에 보내고 독립 소비 | partition/offset/key, broker ACK와 consumer 진행 |
| 3 | OpenSearch 적재·검색 | bulk item 결과, 안정된 ID, refresh 이후 검색 집합 |
| 4 | Spark/Flink로 Iceberg 기록 | input offset, query/checkpoint ID, snapshot·행 집합 |
| 5 | 격리한 hot 또는 archive 소비자만 중단·재시작 | 반대 경로의 진행, backlog, 재시도·중복·누락 |
| 6 | 의도한 retention 초과와 잘못된 schema | 명시적 실패, DLQ/quarantine, 복구 한계 |
| 7 | 실제 workload의 관측·제어 | 권한·예산·정책 세대·적용 영수증·효과 |

OpenSearch refresh를 강제로 호출해 correctness를 동기화할 수 있지만 그 소요 시간을 일반 검색 latency로 보고하지 않는다. 테스트 완료 뒤에는 소유권이 확인된 테스트 리소스만 별도 절차로 정리한다.

## 10. 장애를 받았을 때의 사고 순서

1. 원본 사건이 생성됐는가? 외부 기준 기록이 있는가?
2. 어느 단계까지 ACK가 확인됐는가?
3. source의 가장 오래된 offset과 consumer가 필요한 offset은 무엇인가?
4. 오류가 일부 record인가, transport 전체인가?
5. sink는 기록을 했지만 응답만 유실됐을 가능성이 있는가?
6. retry가 동일 identity와 checkpoint를 사용하는가?
7. 데이터가 실제로 없는가, 아직 검색에서만 보이지 않는가?
8. 두 저장소가 같은 것을 같은 단위로 세고 있는가?
9. 미처리 record가 DLQ로 갔는데 성공 수에 섞인 것은 아닌가?
10. 복구 조치가 원본·기존 사용자 리소스를 지우는가?

## 11. 종합 복습 — 답을 가리고 풀기

| 질문 | 핵심 답 |
| --- | --- |
| OTel Collector가 Kafka를 항상 대체하는가? | 아니다. 큐·retry 범위와 durable replay·다중 소비 요구가 다름 |
| Kafka의 offset은 전체 topic의 전역 순서인가? | partition별 위치이며 업무 사건 시간과도 다름 |
| 같은 consumer group을 두 저장 경로가 공유하면? | partition 작업을 나누게 되어 두 경로 모두 전체 데이터를 받으려는 목적과 다를 수 있음 |
| Spark는 Kafka auto commit으로 archive 진척을 판단하는가? | Structured Streaming은 자체 checkpoint의 source offset을 관리 |
| Flink exactly-once이면 모든 외부 저장소도 하나의 트랜잭션인가? | 아니다. sink 계약과 여러 destination의 원자성은 별개 |
| OpenSearch 문서가 ACK됐는데 검색되지 않는 이유는? | refresh/visibility 지연이나 mapping/query 조건 등을 확인 |
| OpenSearch snapshot은 Iceberg snapshot과 같은가? | 아니다. backup/restore와 테이블 버전의 의미가 다름 |
| archive가 멈췄는데 hot도 느려지는 이유는? | 같은 job/checkpoint 또는 shared broker·CPU·disk의 영향 가능 |
| 모니터링 화면의 Ready가 업무 완료를 입증하는가? | 상태 원천과 버전·검증 조건이 있어야 함 |
| 운영 자동화의 성능 향상은 무엇과 비교하는가? | 동일 입력·예산·계측과 충분히 튜닝한 고정/반응형 기준 |

## 12. 스스로 작성할 최종 산출물

학습이 끝나면 다음 한 페이지를 작성해 본다.

- 수집할 데이터와 제외할 데이터
- 구간별 도구와 각 도구가 필요한 이유
- source ACK·checkpoint·sink commit의 경계
- 예상 장애 3개와 재처리/손실 판정 방법
- 실제 적용 권한·예산과 stale 관측 대응
- 버전·config·event-ID corpus·raw/summary 증거 목록

이 질문에 답할 수 있으면 도구 이름을 나열하는 단계에서 실제 파이프라인을 검토하는 단계로 넘어온 것이다.

[학습 목차](README.md) · [오프라인 실습 코드](examples/replay_demo.py)
