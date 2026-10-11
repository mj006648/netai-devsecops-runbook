# 10. 스트림, 체크포인트, 복구

## 네 상태를 한 복구 경계로 맞춘다

source offset은 어디까지 입력을 읽었는지 나타낸다. operator state는 합계·window처럼 계산 중 기억이다. checkpoint는 특정 offset과 그때 operator state를 내구 저장한 복구 지점이다. sink commit은 외부 독자가 볼 결과를 게시하는 단계다.

| 구성 요소 | 예 | 수명 | 복구 역할 |
|---|---|---|---|
| source offset | partition 0의 1000 | source·checkpoint | 재생 시작 |
| operator state | 합계 55 | 메모리→checkpoint | 계산 복원 |
| checkpoint metadata | CP20 완료 | 내구 저장소 | 권위 있는 경계 |
| sink transaction | batch CP20 | sink | 중복 게시 차단 |

offset만 저장하고 합계를 빼면 재생 시작은 알지만 이전 계산을 잃는다. 합계만 저장하고 offset을 빼면 어느 입력부터 다시 읽을지 몰라 누락이나 중복이 생긴다.

## crash와 재생 전체 시간표

CP20은 offset 1000과 합계 55를 담는다. 처리기는 1001~1030을 처리해 합계 61을 만들었지만 다음 checkpoint 전에 죽는다.

| 시각 | offset | operator state | sink | checkpoint |
|---:|---:|---:|---|---|
| 0 | 1000 | 55 | CP20까지 공개 | CP20 완료 |
| 10 | 1015 | 58 | 임시 결과 | 없음 |
| 20 | 1030 | 61 | 일부 전송 가능 | 없음 |
| 21 | crash | 메모리 손실 | 기존 공개 결과 남음 | CP20 |
| 30 | 1000 복원 | 55 복원 | CP20과 조정 | 재생 시작 |
| 50 | 1030 재처리 | 61 | 새 transaction commit | CP21 후보 |

sink가 각 record를 즉시 비멱등 기록했다면 1001~1030 효과가 두 번 보일 수 있다. checkpoint ID를 sink transaction ID로 사용해 CP21 commit이 한 번만 공개되게 하거나 멱등 upsert를 사용한다.

## barrier와 여러 입력

두 source partition이 있는 operator는 한쪽 barrier만 보고 snapshot하면 다른 쪽의 경계 뒤 record가 상태에 섞일 수 있다. barrier 정렬은 입력별 CP 번호를 맞춰 일관된 cut을 만든다. unaligned checkpoint 같은 방식은 이동 중 buffer까지 캡처하는 별도 메커니즘과 비용이 있다.

checkpoint 완료는 모든 필요한 operator state가 내구 저장되고 coordinator가 완료 metadata를 기록한 뒤 선언한다. 일부 파일 업로드만으로 완료가 아니다.

## event time 반례

watermark는 이 event time 이전 데이터가 대부분 도착했다고 보는 진행 추정이다. 절대 더 늦은 사건이 없다는 물리 증명이 아니다. 늦은 사건을 버릴지, 이전 window 결과를 수정할지 정책이 필요하다.

## 추가 연습 문제와 해설

### 1. CP가 offset 500, state 20이고 530에서 죽으면 몇 입력을 재생하는가?
501~530의 30개다.

### 2. state만 복원하고 offset을 530에서 시작하면?
501~530의 계산이 state에 없는데 입력도 건너뛰어 누락된다.

### 3. offset만 500으로 돌리고 state 26을 유지하면?
이미 반영한 입력을 다시 더해 중복 계산한다.

### 4. sink가 checkpoint transaction을 지원하지 않으면?
멱등 키, upsert, dedup table 같은 별도 경계로 재생 중복을 처리해야 한다.

### 5. watermark 뒤 늦은 사건이 오면 시스템 오류인가?
반드시 아니다. watermark는 정책적 추정이므로 허용 지연과 결과 수정 규칙에 따라 처리한다.

## 내부 상태 복구와 외부 sink 게시의 별도 경계

**스트림**은 계속 도착하는 event 흐름이다. Processor는 event를 읽어 합계와 input offset 같은 **상태**를 바꾼다. **체크포인트**는 내부 상태와 다음 입력 위치를 durable storage에 저장한 복구 기준점이다.

| 시각 | offset | 내부 합계 | 외부 sink |
|---:|---:|---:|---:|
| t0 | 100, +5 | 5 | 없음 |
| t1 | 101, +7 | 12 | 12 게시 |
| t2 | checkpoint | sum=12,next=102 | 12 |
| t3 | 102, +3 | 15 | 15 게시 시도 |
| t4 | crash | memory 손실 | 15가 이미 있을 수 있음 |

복구하면 checkpoint의 sum 12에서 offset 102를 다시 읽어 15를 만든다. 그러나 sink가 t3의 15를 이미 받았다면 append를 다시 수행할 때 중복된다.

Checkpoint 성공은 외부 sink commit 성공과 다르다. Exactly-once 결과에는 checkpoint ID를 포함한 idempotent upsert, sink transaction, 또는 고유 record key가 필요하다. Email이나 결제 같은 부작용은 input offset 복구만으로 보호되지 않는다.

**Event time**은 사건 발생 시각이고 **processing time**은 system 처리 시각이다. **Watermark**는 특정 event time 이전 자료가 대부분 도착했다는 진행 추정이다.

Watermark 10:05 뒤 10:03 event가 오면 drop, late side output, window 재계산 중 정책을 고른다. 이미 게시한 집계를 수정할 수 있는지도 sink 계약에 달려 있다.

### 완전 해설 문제

1. Checkpoint 뒤 event는? **해설:** 저장된 offset부터 replay되어 같은 외부 결과를 다시 쓸 수 있다.
2. Sink write 뒤 checkpoint 전 crash는? **해설:** 복구 replay가 중복을 만들므로 sink idempotency가 필요하다.
3. Watermark보다 늦으면 오류인가? **해설:** 정상 지연일 수 있으며 사전에 정한 late-data 정책으로 처리한다.

[← 이전](09-retries-idempotency-and-deduplication.md) · [목차](README.md) · [다음 →](11-membership-failure-detection-and-leases.md)

## 스트림 상태

스트림은 끝나지 않을 수 있는 사건 순서다.
source는 사건을 내고 operator는 변환하며 sink는 결과를 저장한다.
offset은 입력 위치다.
checkpoint는 operator 상태와 일관된 입력 위치의 복구 지점이다.

```mermaid
flowchart LR
 S[Source offsets] --> O1[Operator state]
 O1 --> B[Barrier]
 B --> CP[Checkpoint storage]
 O1 --> K[Sink]
```

입력 파티션마다 barrier가 흐른다.
operator는 필요한 입력 barrier가 맞춰질 때 상태 snapshot을 만든다.
coordinator가 모든 snapshot 완료를 기록한다.
장애 뒤 마지막 완료 checkpoint 상태를 읽는다.
저장된 offset부터 입력을 다시 재생한다.

## 수치 추적

checkpoint 20은 offset 1,000과 합계 55를 담는다.
처리기가 offset 1,030, 합계 61에서 죽는다.
복구 시 20을 읽어 합계 55로 돌아간다.
1,001..1,030을 다시 처리한다.
sink가 중복을 막거나 checkpoint와 함께 커밋되지 않으면 출력이 두 번 보일 수 있다.

## event time과 watermark

event time은 사건이 원래 발생한 시각이다.
processing time은 처리기가 본 시각이다.
watermark는 이 시각 이전 사건 대부분이 도착했다고 보는 진행 추정치다.
늦은 사건 허용 범위와 갱신 정책에 따라 결과 수정 여부가 달라진다.

## 반례

checkpoint 파일만 저장하고 source offset을 빼면 정확한 재생 시작점을 모른다.
입력 exactly-once와 외부 sink exactly-once는 같은 주장이 아니다.
watermark는 미래의 늦은 사건이 절대 없다는 증명이 아니다.

## 문제와 해설

### 1. checkpoint에 필요한 두 축은?
operator 상태와 그 상태에 대응하는 입력 위치다.

### 2. 재생이 왜 중복 출력을 만드는가?
장애 전 sink 효과는 남았는데 offset은 과거로 돌아갈 수 있기 때문이다.

### 3. watermark는 물리 시계인가?
아니다. event time 진행에 대한 시스템 정책과 추정이다.

## 공식 자료

- [Apache Flink Dataflow Model](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/)
- [Spark Streaming Programming Guide](https://spark.apache.org/docs/latest/streaming-programming-guide.html)

[← 이전](09-retries-idempotency-and-deduplication.md) · [목차](README.md) · [다음 →](11-membership-failure-detection-and-leases.md)
