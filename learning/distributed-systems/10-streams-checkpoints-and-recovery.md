# 10. 스트림, 체크포인트, 복구

스트림 작업은 끝나지 않는 입력을 읽어 내부 상태를 바꾸고 외부 결과를 계속 낸다. 장애 뒤 단순히 “마지막 위치부터 다시 읽기”만 하면 충분하지 않다. 입력 위치, 계산 상태, 이동 중 레코드와 외부 출력이 같은 논리 경계를 가리켜야 한다. 이 장은 두 입력 파티션과 한 sink의 장애를 처음부터 끝까지 추적한다.

## 용어를 실제 객체와 수명으로 정의한다

**스트림(stream, 시간에 따라 계속 도착하는 사건의 순서)**은 주문·센서·로그 레코드의 연속이다. 브로커가 파티션 로그로 관리하고 보존 기간까지 산다. **소스(source, 입력을 제공하는 주체)**는 파티션별 레코드와 위치를 노출한다. 작업이 장애 뒤 같은 입력을 다시 얻으려면 소스가 일정 기간 재읽기를 지원해야 한다.

**오프셋(offset, 파티션 안에서 레코드 위치를 나타내는 번호)**은 P0:1000 같은 논리 정수다. 소스와 체크포인트 메타데이터가 관리하며 입력 보존 기간과 작업 수명 동안 의미가 있다. 어느 레코드까지 상태에 포함됐는지 연결하기 위해 필요하다.

**상태(state, 다음 출력에 영향을 주는 계산 중 기억)**는 키별 합계, 윈도우 버킷, 중복 제거 ID와 타이머다. operator가 메모리와 로컬 저장소에 관리하고 체크포인트로 내구화한다. 입력만 재생하기 어려운 장기간 집계를 복구하려면 상태가 필요하다.

**워터마크(watermark, 이 event time 이전 사건이 대체로 도착했다고 보는 진행 추정값)**는 operator가 입력별 관측과 정책으로 만든다. 윈도우를 닫고 타이머를 실행하는 데 필요하지만 더 늦은 사건이 절대 없다는 증명은 아니다. 체크포인트에 상태와 함께 저장해야 복구 뒤 윈도우 진행이 일관된다.

**배리어(barrier, 특정 체크포인트 경계를 표시해 데이터 흐름을 따라가는 제어 레코드)**는 coordinator가 소스에 주입하고 operator가 입력별로 관측한다. CP21 배리어가 두 입력에 모두 도달할 때 같은 논리 절단면을 만든다. 한 체크포인트 시도 동안 살고 완료 또는 실패 뒤 정리된다.

**체크포인트(checkpoint, 상태와 그 상태에 대응하는 입력 위치를 내구 저장한 복구 지점)**는 CP20 같은 ID, operator snapshot 파일, 소스 offset, watermark와 완료 메타데이터다. coordinator가 관리하고 외부 내구 저장소에 둔다. 다음 체크포인트와 보존 정책이 허용할 때까지 산다. 일부 파일이 업로드된 것과 완료 선언은 다르며, 모든 필요한 상태 뒤 완료 레코드를 쓴다.

**재생(replay, 완료 체크포인트 이후 입력을 다시 읽어 상태를 재계산하는 과정)**은 장애 복구기가 시작한다. 같은 레코드가 다시 실행될 수 있으므로 계산과 출력은 이를 견뎌야 한다. **싱크(sink, 계산 결과를 외부에 저장하거나 게시하는 대상)**는 데이터베이스·파일·메시지 브로커다.

**커밋(commit, sink 결과를 독자에게 보이도록 확정하는 경계)**은 sink transaction ID나 원자 pointer 교체로 존재한다. 체크포인트 완료와 자동으로 같은 사건이 아니다. **정확히 한 번(exactly-once, 명시한 관측 경계에서 각 논리 입력 효과가 한 번만 보이는 계약)**은 입력 전달 횟수가 한 번이라는 뜻이 아니다. 재생을 허용하되 상태와 sink 게시가 한 결과로 수렴해야 한다.

**멱등성(idempotency, 같은 논리 출력을 반복 적용해도 관측 결과가 한 번과 같아지는 성질)**은 sink transaction을 쓸 수 없을 때 중요한 대안이다. 결과 키에 job ID·window·checkpoint 또는 record ID를 넣고 upsert하거나 dedup한다.

## 두 입력과 한 sink의 정상 처리

소스 P0와 P1이 같은 key K의 금액을 낸다. CP20 완료 상태는 P0 offset 1000, P1 offset 2000, sum=55, watermark=10:00:00이며 sink에는 CP20 결과 55가 공개돼 있다. 다음 레코드는 다음과 같다.

| 순서 | 입력 | offset | event time | 값 | 처리 뒤 sum |
|---:|---|---:|---|---:|---:|
| 1 | P0 | 1001 | 10:00:01 | +2 | 57 |
| 2 | P1 | 2001 | 10:00:02 | +3 | 60 |
| 3 | P0 | 1002 | 10:00:04 | -1 | 59 |
| 4 | P1 | 2002 | 10:00:03 | +4 | 63 |
| 5 | P0 | 1003 | 10:00:06 | +2 | 65 |
| 6 | P1 | 2003 | 10:00:07 | -3 | 62 |

처리 순서와 event time 순서는 다를 수 있다. P1:2002는 처리 순서 4지만 event time 10:00:03이다. operator는 정한 윈도우 정책에 따라 event time을 사용한다. sum은 도착 순 처리라 위 표에서 62가 된다.

CP21을 시작하면 coordinator가 P0와 P1에 barrier 21을 넣는다. P0 barrier가 먼저 도착했을 때 operator는 P0의 뒤 레코드를 잠시 정렬 버퍼에 두고 P1의 barrier를 기다린다. 두 barrier 전에 받은 레코드까지 state에 포함해 P0=1003, P1=2003, sum=62, watermark=10:00:05를 snapshot한다. 그 뒤 버퍼를 풀어 CP21 이후 입력을 처리한다.

| CP21 객체 | 값 | 관리자 |
|---|---|---|
| source offsets | P0=1003, P1=2003 | source connector/coordinator |
| operator state | K.sum=62 | operator state backend |
| event-time state | watermark=10:00:05, 미완료 window | operator |
| sink transaction | tx=job7-CP21, PREPARED | sink connector |
| completion | CP21 COMPLETE | checkpoint coordinator |

## 한쪽 배리어만 보고 snapshot하면 생기는 반례

P0 barrier 뒤 P1:2003을 처리하고 바로 snapshot해 sum=65라고 가정하자. 저장 offset은 실수로 P1=2002다. 복구는 P1:2003을 다시 읽어 -3을 또 적용해 62가 된다. 반대로 state에 P1:2003이 빠졌는데 offset은 2003이면 -3이 영원히 누락된다. 상태와 각 입력 위치가 하나의 절단면이어야 한다.

정렬 체크포인트는 빠른 입력을 막아 backpressure를 만들 수 있다. 비정렬 체크포인트는 이동 중 네트워크 버퍼까지 snapshot해 정렬 대기를 줄이는 대신 snapshot 크기와 복구 복잡도를 늘린다. 어느 방식이든 포함된 레코드와 offset의 관계를 명시한다.

## crash 전후 전체 시간표

CP21 결과를 sink transaction으로 준비하다가 응답이 유실되는 사례다.

| 시각(ms) | P0/P1 마지막 처리 | operator | sink | checkpoint metadata |
|---:|---|---|---|---|
| 0 | 1000/2000 | sum55, WM 10:00:00 | CP20=55 공개 | CP20 COMPLETE |
| 10 | 1001/2001 | sum60 | tx21 없음 | CP20 |
| 20 | 1002/2002 | sum63 | tx21 OPEN | CP21 진행 |
| 28 | 1003/2003 | sum62 | tx21 PREPARED=62 | snapshot 업로드 |
| 32 | 1003/2003 | snapshot 완료 | tx21 COMMIT 요청 수신 | 완료 기록 전 |
| 34 | 동일 | 메모리 sum62 | **tx21이 실제 commit됐을 수 있음** | CP20만 COMPLETE |
| 35 | crash | 메모리 손실 | 62 공개 여부 미상 | CP20 권위 |
| 50 | 1000/2000 복원 | sum55, WM 복원 | tx21 상태 조회 | CP20에서 재생 |
| 65 | 1003/2003 재처리 | sum62 | tx21 기존 commit이면 재사용 | CP21 재구성 |
| 72 | 동일 | sum62 | tx21=62 한 번 공개 | CP21 COMPLETE |

35ms에 권위 있는 완료 메타데이터는 CP20이므로 내부 상태는 CP20으로 돌아간다. P0 1001~1003 세 개와 P1 2001~2003 세 개, 합계 여섯 레코드를 재생한다. sink tx21이 이미 commit됐는지 조회하지 않고 새 append를 하면 결과 62가 두 번 보일 수 있다. transaction ID를 job7-CP21로 안정적으로 재사용하면 sink는 기존 commit 결과를 반환할 수 있다.

## sink commit과 checkpoint 완료 순서

프로토콜은 sink가 제공하는 능력에 맞춰 경계를 만든다. 2단계 sink라면 operator snapshot과 함께 tx21을 prepare하고, 모든 task 상태가 내구화된 뒤 coordinator 완료에 맞춰 commit한다. commit 메시지는 유실될 수 있으므로 상태 조회와 반복 commit이 멱등해야 한다.

sink가 transaction을 지원하지 않으면 다음 대안을 쓴다.

1. 결과 키를 (job, window, key)로 고정해 upsert한다.
2. 각 record ID를 sink dedup 표에서 업무 변경과 함께 커밋한다.
3. 파일은 임시 경로에 쓰고 완료 manifest 또는 pointer를 원자 교체한다.
4. 이메일처럼 멱등하지 않은 외부 효과는 outbox와 수신자 idempotency key를 둔다.

checkpoint만 성공했다고 외부 부수 효과가 정확히 한 번인 것은 아니다. 소스 offset 커밋만으로도 마찬가지다.

## 워터마크와 늦은 사건

P0 watermark 10:06, P1 watermark 10:04라면 두 입력을 기다리는 operator의 공통 watermark는 보통 느린 쪽 10:04를 넘을 수 없다. P1이 유휴 상태인데 이를 영원히 기다리면 window가 닫히지 않으므로 명시적 idle-source 정책이 필요하다.

watermark 10:05 뒤 event time 10:03인 +7이 도착할 수 있다. 정책은 세 가지다.

- 허용 지연 안이면 이전 window를 7만큼 수정하고 update 결과를 sink에 쓴다.
- late side output으로 보내 별도 재처리한다.
- 계약한 허용 지연 밖이면 버리되 metric과 감사 로그를 남긴다.

이미 append-only sink에 최종 결과를 보냈다면 수정 표현이 필요하다. 같은 window key의 새 버전을 쓰거나 retract와 update를 함께 보낸다. watermark는 물리적 완결 증명이 아니라 결과 게시 시점을 정하는 정책이다.

## 상태만 또는 offset만 복원하는 오류

CP20의 sum55에 대응하는 위치는 P0=1000, P1=2000이다. 장애 직전 sum62를 그대로 두고 offset만 CP20으로 돌리면 여섯 레코드를 다시 적용해 69가 된다. 반대로 sum55를 복원하면서 offset을 1003/2003에서 시작하면 여섯 레코드 효과를 건너뛰어 55에 머문다. 상태와 모든 입력 위치를 같이 복원해야 62로 돌아온다.

원본의 단일 입력 교육값도 같다. CP20이 offset 1000, sum55이고 장애 시점이 1030, sum61이면 1001~1030의 **1030-1001+1=30개**를 재생한다.

## 내구 저장소와 완료 메타데이터

operator snapshot 파일 세 개 중 두 개만 업로드됐는데 CP21 COMPLETE를 쓰면 나머지 state를 복구할 수 없다. 순서는 모든 파일 내구화, checksum 검증, sink prepare, coordinator 완료 레코드다. 완료 레코드가 권위 있는 root이며 부분 파일은 다음 정리에서 제거한다.

내구성의 범위도 적는다. 로컬 executor 디스크만 사용하면 노드 손실에 취약하다. 원격 객체 저장소를 쓰더라도 업로드 성공 응답의 내구 계약, 다중 리전 여부, 암호화와 권한이 별도 조건이다. checkpoint 주기가 짧으면 재생량은 줄지만 저장 I/O와 정렬 비용이 늘어난다.

## checkpoint coordinator 자체가 죽는 경우

coordinator도 실패할 수 있으므로 CP 상태를 내구 메타데이터로 구분한다.

| 상태 | 의미 | 복구 처리 |
|---|---|---|
| TRIGGERED | CP22 ID와 참여 task가 정해짐 | 동일 시도 응답 수집 또는 중단 |
| SNAPSHOTTING | 일부 task 파일 업로드 | COMPLETE가 없으면 권위 복구점으로 쓰지 않음 |
| PREPARED | 모든 state와 sink prepare 확인 | 동일 tx ID로 완료 절차 재개 |
| COMPLETE | 권위 완료 레코드 영속화 | 장애 뒤 선택 가능한 복구점 |
| ABORTED | 시도 실패 기록 | 임시 파일·sink tx 정리 |

coordinator가 모든 task의 성공을 메모리에서만 확인하고 COMPLETE 기록 전에 죽으면 새 coordinator는 CP22를 완료됐다고 추측하지 않는다. 각 task 파일이 존재해도 하나의 원자적 완료 레코드가 없기 때문이다. 반대로 COMPLETE를 내구 저장한 뒤 작업자에게 알리기 전에 죽으면 새 coordinator는 CP22를 선택한다. 알림 유실이 완료 사실을 취소하지 않는다.

sink와 coordinator의 순서에는 구현별 protocol이 필요하다. COMPLETE 뒤에만 sink를 commit하면 coordinator 완료 직후 sink 전 crash에서 내부 복구점은 CP22지만 외부 결과는 아직 없다. sink commit 뒤 COMPLETE를 쓰면 앞의 tx21 사례처럼 외부 결과만 먼저 보일 수 있다. 2단계 sink transaction, 복구 가능한 commit ID와 상태 질의를 결합해 어느 순서의 결과 미상도 수렴시킨다.

## source 보존 기간과 복구 가능성

checkpoint가 완전해도 source가 재생 구간을 삭제하면 복구할 수 없다. 마지막 완료 CP20이 P0=1000인데 브로커 보존 시작점이 1050으로 전진했다면 1001~1049가 없다. operator state를 55로 돌린 뒤 1050부터 시작하면 그 구간을 누락한다. checkpoint 간격, 최악 복구 시간과 source retention을 함께 정한다.

소스 offset 커밋의 의미도 connector마다 다르다. 브로커 소비자 그룹 offset을 1030으로 먼저 올리고 state checkpoint가 CP20에 머물면 복구가 1031에서 시작해 누락된다. 반대로 그룹 offset을 늦게 올리면 재전달은 늘지만 정확한 checkpoint offset에서 재생할 수 있다. 외부 offset 저장소가 아니라 checkpoint metadata를 권위로 사용하고, source commit은 그 경계와 조정한다.

source가 재생 불가능한 HTTP webhook이라면 입력을 먼저 내구 로그에 수락한 뒤 stream job이 그 로그를 읽도록 경계를 바꾼다. 장애 뒤 같은 사건을 다시 얻을 수 없는 source에서 상태 exactly-once를 주장할 수 없다.

## 여러 operator와 분산 상태

실제 DAG에는 source 다음 map, keyBy, window, sink가 있다. CP21 barrier는 각 edge를 흐르고 operator별 snapshot을 만든다. keyBy 뒤 shuffle 채널의 레코드도 cut에 포함돼야 한다. upstream에서는 보냈지만 downstream은 아직 받지 않은 in-flight 레코드를 양쪽 state에서 모두 빠뜨리면 누락되고, 둘 다 포함하면 중복될 수 있다.

정렬 방식은 downstream이 각 input barrier를 받을 때 앞선 데이터가 모두 처리됐다는 채널 순서를 이용한다. 한 input barrier 뒤 그 채널을 막고 다른 input의 앞선 데이터를 계속 처리한다. 모든 barrier가 모이면 operator state를 찍고 막힌 데이터를 푼다. 채널이 FIFO가 아니거나 제어 메시지가 데이터를 추월한다면 이 가정이 깨지므로 transport 조건을 명시한다.

비정렬 방식은 barrier가 처음 도착한 순간 operator state와 아직 도착하지 않은 채널의 in-flight buffer를 함께 캡처한다. 복구는 buffer를 먼저 복원해 같은 순서를 재현한다. 정렬 대기는 줄지만 checkpoint가 순간 backlog만큼 커질 수 있다. 예를 들어 초당 50MB 입력이 8초 밀렸다면 단순 상한으로 400MB의 이동 중 데이터가 추가될 수 있다. 이는 교육 계산이며 실제 압축과 채널 구조에 따라 달라진다.

## window 결과의 버전과 sink 표현

10:00~10:05 window의 최초 결과가 100이고 watermark 뒤 늦은 +7이 왔다고 하자. append sink에 단순히 107을 추가하면 독자는 100과 107 두 행 중 무엇이 현재인지 모를 수 있다. 결과 키를 (job7, windowStart=10:00, key=K)로 두고 version 2의 107로 upsert하거나, changelog sink에 UPDATE_BEFORE 100과 UPDATE_AFTER 107을 보낸다.

sink가 append-only 파일이면 checkpoint별 파일과 manifest를 쓴 뒤 현재 snapshot pointer를 교체할 수 있다. CP21 시도의 임시 파일은 이름에 attempt와 transaction ID를 넣는다. task retry가 같은 파일 이름을 덮는지, 새 파일을 만들고 manifest에서 하나만 선택하는지 정한다. 파일 존재만으로 공개 성공이라고 판단하지 않는다.

## 30개 재생의 처리량 계산

CP20 이후 30개를 재생하고 레코드당 순수 계산이 평균 2ms라고 가정하면 단일 worker 계산 시간은 **30×2ms=60ms**다. sink round trip을 레코드마다 10ms씩 직렬 수행하면 추가 300ms가 되어 총 360ms다. 30개를 하나의 멱등 batch로 20ms에 commit할 수 있다면 약 80ms다. 이 숫자는 실제 성능 측정이 아니라 I/O 경계가 복구 시간에 미치는 영향을 보이는 모형이다.

정상 처리량이 초당 1,000개이고 복구 처리량이 초당 1,500개라면 backlog 순감소율은 500개/s다. 장애 동안 15,000개가 쌓였다면 따라잡는 데 최소 **15,000÷500=30초**가 걸린다. 복구 처리량이 정상 유입률 이하이면 backlog가 줄지 않으므로 단순 재시작만으로 정상화되지 않는다.

## 완전 풀이 문제

### 문제 1. CP가 offset 500, state20이고 530에서 죽으면 몇 개를 재생하는가?

**풀이:** 501부터 530까지 양 끝을 포함해 30개다. state20을 복원하고 501에서 시작한다. sink에 이 구간 결과가 일부 남았을 수 있으므로 checkpoint transaction이나 멱등 키로 중복 게시를 막는다.

### 문제 2. state만 CP20으로 복원하고 offset을 1030 다음에서 시작하면?

**풀이:** sum55에는 1001~1030이 반영되지 않았는데 입력도 건너뛴다. 결과는 기대 sum61이 아니라 55에 머무는 누락이다. state와 offset은 같은 checkpoint 절단면에서 복원한다.

### 문제 3. offset만 1000으로 돌리고 장애 직전 state61을 유지하면?

**풀이:** 이미 반영한 30개를 다시 처리한다. 값의 합이 단순히 6 증가한 예라면 67이 되어 중복 계산이다. 실제 비가환 연산은 더 복잡하게 틀릴 수 있다.

### 문제 4. P0 barrier만 보고 CP21 snapshot을 만들면 왜 위험한가?

**풀이:** P1의 경계 뒤 레코드가 state에 들어가면서 저장 offset에는 빠지거나 그 반대가 될 수 있다. 두 입력 barrier를 정렬하거나 이동 중 버퍼까지 snapshot해 하나의 일관된 cut을 만든다.

### 문제 5. sink write 뒤 checkpoint 완료 전에 crash하면 입력 exactly-once가 출력을 보호하는가?

**풀이:** 아니다. 내부 상태는 이전 checkpoint로 돌아가 입력을 재생한다. 장애 전 sink 효과는 남을 수 있다. sink transaction ID, upsert key 또는 dedup 표가 재생 출력을 한 번처럼 만들어야 한다.

### 문제 6. watermark 10:05 뒤 10:03 사건이 오면 시스템 오류인가?

**풀이:** 반드시 아니다. watermark는 지연 정책에 따른 진행 추정이다. 허용 지연 안이면 window를 수정하고, 별도 late stream으로 보내거나, 정책 밖이면 버리면서 관측한다. 선택은 sink가 update를 표현할 수 있는지와 업무 계약에 달렸다.

### 문제 7. tx21 COMMIT 요청 응답이 유실됐다. 새 tx22로 같은 결과를 append해도 되는가?

**풀이:** tx21이 실제 commit됐을 수 있어 중복된다. 먼저 안정된 tx21 ID로 상태를 조회하고, 미결이면 같은 commit을 반복한다. sink가 조회·멱등 commit을 지원하지 않으면 결과 키 중복 제거가 필요하다.

### 문제 8. checkpoint 주기를 60초에서 5초로 줄이면 무조건 좋은가?

**풀이:** 최악 재생 시간은 줄 수 있지만 snapshot I/O, 네트워크, barrier 정렬과 sink transaction 수가 늘어난다. 상태 크기, 증분 snapshot, 장애 복구 목표와 정상 처리 지연을 함께 측정한다.

## 보장 문장을 쓰는 법

“정확히 한 번 처리한다” 대신 범위를 적는다. 예를 들어 “브로커 입력은 재생될 수 있지만 CP ID transaction을 지원하는 분석 sink에서는 window 결과가 한 번만 공개된다. 이메일 sink는 별도 중복 제거가 없으므로 같은 보장을 하지 않는다”라고 쓴다. 상태 복구, 입력 전달, 외부 관측을 나누면 장애 반례를 찾을 수 있다.

또한 복구가 끝났다는 운영 신호에는 선택한 checkpoint ID, source 재생 완료 위치, sink commit ID와 backlog 0 확인을 함께 남긴다.

## 검토 기준

- 상태, 모든 source offset, watermark와 timer가 같은 checkpoint를 가리킨다.
- barrier가 여러 입력에서 어떤 cut을 만드는지 설명한다.
- checkpoint 파일 완료와 coordinator COMPLETE를 구분한다.
- sink commit의 결과 미상과 멱등 재시도를 설계한다.
- exactly-once가 적용되는 관측 경계를 명시한다.
- 가상 수치는 교육 trace이며 측정 결과가 아님을 밝힌다.

## 공식 자료

- [Apache Flink, Fault Tolerance](https://nightlies.apache.org/flink/flink-docs-stable/docs/learn-flink/fault_tolerance/) — checkpoint, barrier와 상태 복구
- [Apache Flink, Event Time and Watermarks](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/) — event time 진행과 늦은 사건
- [Apache Kafka, Exactly Once Semantics](https://kafka.apache.org/documentation/#semantics) — transaction과 처리 보장 경계

[← 이전](09-retries-idempotency-and-deduplication.md) · [목차](README.md) · [다음 →](11-membership-failure-detection-and-leases.md)
