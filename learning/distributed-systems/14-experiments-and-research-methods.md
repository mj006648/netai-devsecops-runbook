# 14. 실험과 연구 방법

## 질문을 검증 가능한 문장으로 바꾼다

“빠른가?”나 “복구가 잘 되는가?”는 실험 질문으로 부족하다. 대상, 바꾸는 조건, 측정값과 실패 조건을 포함해야 한다. 예를 들어 가설 H1을 다음처럼 쓸 수 있다.

> 5노드 동일 하드웨어에서 한 follower 링크에 왕복 100ms 지연을 넣어도 quorum write의 p99가 기준선보다 25% 넘게 증가하지 않고, acknowledged write 손실과 linearizability 위반이 0이다.

여기서 25%는 제품 목표로 정한 교육용 기준이지 관측 결과가 아니다. **독립 변수**는 의도적으로 바꾸는 follower 링크의 추가 지연 0ms와 100ms다. **종속 변수**는 성공 처리량, 전체 요청 p50·p95·p99, timeout율, 복구 시간과 정확성 위반 수다. 서버 수 5, CPU·메모리, software commit, fsync, 요청 구성, key 분포, client 수, payload와 측정 시간은 **통제 변수**로 고정한다.

```mermaid
flowchart LR
 Q[연구 질문] --> H[반증 가능한 가설]
 H --> D[실험과 중단 기준 사전 등록]
 D --> M[성능·장애·history 측정]
 M --> V[정확성 guardrail 검증]
 V --> C[분석·결론·한계]
```

## 정확성의 측정 객체: history

**history(연산 이력)**는 각 연산의 ID, 호출 시각, 응답 시각, 입력, 출력과 오류를 모은 기록이다. 실행 artifact로 내구 저장하고 분석·감사 기간 동안 보존한다. **선형화 가능성(linearizability)** 검사는 각 연산을 호출과 응답 사이의 한 점에 놓아 실시간 선후 관계와 순차 명세를 동시에 만족할 수 있는지 묻는다.

history의 실제 산출물은 request별 레코드와 run metadata 파일이다. client recorder가 invocation을 먼저 쓰고 completion에서 상태와 반환값을 덧붙인다. checker는 이 레코드 집합, 초기 상태와 `write(x)`·`read()` 같은 순차 명세를 입력으로 받으며, 출력은 유효 판정 또는 순서를 만들 수 없는 최소 반례다. 서버 로그만으로 history를 대신하면 client가 실제로 받은 응답과 timeout을 잃을 수 있다. 반대로 client history만으로 장애가 어느 링크에 적용됐는지는 알 수 없어 서버 term·commit index와 주입 증거를 같은 run ID로 연결한다.

| op | invoke | complete | 입력 | 출력 |
|---|---:|---:|---|---|
| W1 | 10ms | 30ms | `x=2` | ok |
| R1 | 40ms | 45ms | `read x` | 1 |
| W2 | 42ms | 60ms | `x=3` | ok |
| R2 | 61ms | 66ms | `read x` | 3 |

W1은 30ms에 끝나고 R1은 40ms에 시작하므로 실시간 순서상 W1이 먼저다. 초기값이 `x=1`인 register에서 R1이 1을 반환한 것은 선형화 반례다. W2는 R1과 겹치므로 R1을 설명하지 못한다. R2가 3을 반환한 것은 W2 완료 뒤이므로 허용된다. 평균 지연과 처리량이 좋아도 이 위반은 사라지지 않는다.

history에는 성공뿐 아니라 timeout도 넣는다. timeout 연산은 서버 효과가 있었을 수 있어 미상으로 다루고, 후속 read와 request ID로 제약한다. 여러 client 머신의 timestamp 오차가 선후 판정을 바꿀 수 있으므로 한 recorder를 쓰거나 clock 조건을 검증해 기록한다.

요청 ID 1~10,000을 발급했다면 성공 응답 집합 A를 보존한다. 복구 뒤 A의 모든 효과가 존재하는지 확인한다. 같은 ID의 효과가 둘 이상이면 중복이고, A에 있는데 효과가 없으면 acknowledged loss다. timeout 집합 U는 성공·미실행·미상 중 하나이므로 결과 조회로 분류한다. 최종 checksum만 같으면 중간 선형화 위반을 놓칠 수 있어 history 검사와 최종 상태 검사를 함께 쓴다.

## 성능 값의 뜻과 계산

**지연(latency)**은 요청 호출부터 응답까지의 시간 표본이고, **처리량(throughput)**은 단위 시간에 계약을 만족하며 완료한 요청 수다. 클라이언트 recorder가 request ID별로 저장한다. 오류와 timeout을 제외한 성공 표본만으로 지연을 계산하면 가장 나쁜 요청을 숨길 수 있다.

10초 동안 12,000개 요청을 보내 11,700개 성공, 200개 timeout, 100개 명시 오류가 났다면 offered load는 1,200 req/s, successful throughput은 1,170 req/s, 성공률은 97.5%다. 이 값은 계산 예이며 실험 결과가 아니다.

**p99**는 관측 표본의 99%가 그 값 이하인 분위수다. 평균 10ms가 소수의 2초 요청을 숨길 수 있으므로 p50·p95·p99, 최대와 원시 분포를 함께 본다. 100개 표본의 최악 한 점을 안정적인 p99로 일반화하지 않으며, 사용하는 분위수 계산법을 명시한다. 서버 응답 뒤 다음 요청을 보내는 closed-loop 부하만 쓰면 과부하 대기 시간을 숨기는 coordinated omission이 생기는지도 검토한다.

p99의 입력은 분석 대상으로 포함하기로 한 요청들의 지연 표본이다. timeout을 표본에서 삭제하면 긴 요청이 관측에서 잘리는 **검열(censoring)** 문제가 생긴다. client deadline이 2초라면 실제 완료 시간을 모르더라도 “적어도 2초 이상 또는 미완료”라는 결과와 timeout율을 보존해야 한다. 성공 요청 p99를 별도로 계산할 수 있지만 이름을 `successful-request p99`로 제한하고 전체 요청 성공률과 함께 제시한다. 오류를 0ms나 누락값으로 섞는 방식도 분포의 의미를 바꾸므로 결과 범주와 지연을 분리해 보관한다.

offered load는 client가 시스템에 제시한 요청률이고 successful throughput은 계약을 만족해 성공 응답을 끝낸 요청률이다. 둘의 차이는 queue, timeout과 오류로 사라진 부하다. 부하를 높였는데 successful throughput이 그대로인 상황에서 성공 요청 latency만 좋아 보일 수도 있으므로 offered load, 성공·timeout·오류 개수와 queueing 방식을 한 표에 둔다. closed-loop client가 응답을 기다리는 동안 새 요청을 덜 보내면 장애 구간의 offered load 자체가 낮아져 시스템이 빨라진 것처럼 보일 수 있다.

## 장애 시간표와 적용 증거

한 run에서는 다음 시간표처럼 기준선, 장애, 복구를 겹치지 않게 정의한다. 원문의 다른 예에 나온 `60~360초 기준선, 180초 주입`처럼 구간이 겹치는 계획과 혼합하지 않는다.

| 구간 | 시각 | 행동 | 수집 |
|---|---|---|---|
| 준비 | 0~60s | 연결·JIT·cache warm-up | 분석 표본에서 분리 |
| 기준선 | 60~180s | 장애 없는 고정 부하 | QPS, latency, history |
| 주입 | 180s | follower F2 링크에 +100ms | 도구 timestamp, packet probe |
| 장애 | 180~240s | 같은 부하 유지 | 오류, leader·term, latency |
| 해제 | 240s | 장애 규칙 제거 | 실제 RTT 회복 확인 |
| 복구 | 240~360s | backlog와 replica 추적 | catch-up, history |
| 검증 | 이후 | 모든 ack write 조회 | checker, checksum |

장애 명령의 exit code 0은 실제 데이터 경로에 장애가 적용됐다는 증거가 아니다. F2 방향 probe RTT가 기준 설계값 2ms에서 약 102ms로 변했는지, packet counter와 peer metric이 같은 구간을 가리키는지 확인한다. 2ms와 102ms도 목표 예시이며 관측 결과가 아니다. interface나 namespace가 틀렸다면 성능이 좋아도 그 run은 무효다.

주입 위치는 재현할 수 있게 쓴다.

- network delay는 leader와 특정 follower 사이에서 단방향인지 양방향인지 적는다.
- packet loss는 비율, burst 길이와 재정렬 여부를 적는다.
- process kill은 SIGKILL 시각과 restart policy를 적는다.
- CPU pause는 프로세스가 살아 있지만 진행하지 않는 기간을 적는다.
- disk stall은 어느 WAL device의 write 또는 fsync를 늦췄는지 적는다.
- clock fault는 wall clock과 monotonic clock 중 대상을 구분한다.

한 run에서 여러 장애를 동시에 바꾸면 원인을 분리하기 어렵다. 상호작용이 질문이라면 각 조합과 기준군을 둔 factorial design으로 설계한다.

복구 시간도 시작과 끝을 하나의 숫자로 뭉치지 않는다. 주입 시각, 마지막 성공, 새 leader 선출, 첫 성공, p99 정상 범위 복귀, backlog 0, 모든 replica catch-up을 각각 기록한다. 새 leader가 2초에 뽑혀도 p99가 30초 동안 높고 follower가 90초에 따라잡았다면 서비스 가용성, 성능 안정화, redundancy 회복의 종료점은 각각 다르다. 이 숫자들은 설명용이다.

## 재현성과 사전 등록

반복마다 software commit, kernel, runtime, storage class, 실제 하드웨어와 topology, 설정, 데이터 크기, seed, workload trace, 명령, node 배치, 시작 시각과 clock source를 보존한다. 같은 instance 이름도 세대와 noisy neighbor가 다를 수 있어 실제 할당 정보를 남긴다. 원시 자료에서 표를 만드는 계산식과 제외 규칙도 version control한다.

seed 비교 방식도 질문에 맞춰 정한다. **독립 seed 설계**는 baseline과 candidate가 서로 다른 난수 trace를 써 더 넓은 schedule을 탐색하지만, 두 조건의 차이에 workload 차이가 섞일 수 있다. **paired seed 설계**는 같은 seed와 같은 workload trace를 두 조건에 적용해 run별 차이를 짝지어 비교한다. paired 분석의 실제 산출물은 seed마다 `candidate-baseline` 차이와 그 분포다. 단, candidate 동작 때문에 사건 소비 순서가 달라져 같은 seed가 같은 trace를 뜻하지 않을 수 있으므로 생성된 workload·장애 schedule 파일 자체를 보존한다. 여러 seed 탐색과 paired 비교는 목적이 다르며 한 seed 반복만으로 대체할 수 없다.

최소 3회 반복이라는 출발 기준을 쓰되 효과 크기와 실행 간 변동에 따라 늘린다. 항상 baseline 다음 candidate 순서로 돌리면 시간 drift가 섞일 수 있으므로 순서를 무작위화하거나 교차한다. 성공한 실행이나 가장 빠른 실행만 고르지 않는다. request 수백만 개를 독립 반복처럼 취급하지 않고 run 간 분산도 본다.

| 항목 | 사전 기록 예 | 목적 |
|---|---|---|
| hypothesis | 100ms follower 지연에서 p99 증가 ≤25% | 사후 기준 변경 방지 |
| primary metric | 전체 요청 p99 | 좋은 지표만 고르는 선택 편향 방지 |
| correctness guardrail | ack loss=0, checker violation=0 | 성능보다 먼저 계약 판정 |
| baseline | 같은 5node·fsync·복제 수 | 의미가 같은 비교 |
| seeds | 101, 202, 303 이상 | schedule 재현과 탐색 |
| sample unit | request와 run 모두 | 의사 반복 방지 |
| stop rule | 계획 반복 완료 또는 guardrail 위반 | 좋아질 때까지 반복 방지 |
| artifacts | config, history, raw metric, 주입 증거 | 재검산 가능 |

**seed**는 난수 workload와 장애 schedule을 다시 만드는 입력 정수다. 같은 seed의 재현과 여러 seed의 탐색을 함께 한다. **기각 조건**은 성능 수치와 무관하게 가설을 받아들이지 않을 사전 조건이다. H1의 기각 조건은 다음과 같다.

사전 등록의 실제 산출물은 실험 전에 고정한 계획서와 machine-readable run manifest다. 가설 문장, primary metric 계산식, guardrail, 유효 run 판정, 반복 수, seed 목록, stop rule과 artifact 경로를 commit에 묶는다. 실행 뒤에는 manifest의 계획값을 덮어쓰지 않고 관측 결과와 deviation(계획에서 벗어난 이유)을 별도 필드에 남긴다. 그래야 p99가 불리해진 뒤 primary metric을 평균으로 바꾸거나, 위반 run을 사후 제외하는 선택을 발견할 수 있다.

1. 장애가 목표 링크에 실제 적용되지 않았다.
2. 어느 run에서든 acknowledged write가 복구 뒤 사라졌다.
3. history checker가 선형화 불가능 반례를 냈다.
4. 후보와 기준군의 durability 또는 consistency 설정이 다르다.
5. 유효 표본이나 반복 수가 사전 최소에 못 미친다.

위반이 나오면 seed와 최소 history를 즉시 보존한다. 이후 정상 run과 평균내어 위반을 0에 가깝게 만들지 않는다. checker 자체는 작은 known-valid와 known-invalid history로 검증한다.

## 공정한 비교와 분석

**강한 기준군**은 후보와 같은 하드웨어, 내구성, 일관성, 부하 조건에서 합리적으로 잘 조정된 비교 대상이다. 후보가 node 7개이고 기준군이 5개면 algorithm과 자원 증가 효과가 섞인다. 동일 node 비교와 동일 비용 비교를 나누고 CPU core-hour, 저장 byte, network egress, 운영 복잡도와 복구 여유 용량을 기록한다.

fsync를 끄거나 batch 크기를 키워 지연을 낮춘 후보는 승인 응답의 의미가 다른 비교일 수 있다. ack 의미, fsync, replication factor, compression, dataset와 consistency를 맞춘다. 관측 도구도 모든 RPC payload를 동기 기록하면 지연을 바꿀 수 있으므로 sampling on/off 대조 run이나 recorder CPU를 기록한다. history 필수 필드는 유지하되 전체 payload 대신 hash를 보존할 수 있다.

다음 교육 표에서는 평균 처리량이 비슷하지만 run 2의 정확성 위반 때문에 성공으로 묶을 수 없다.

| run | 조건 | throughput/s | p99 ms | violation |
|---:|---|---:|---:|---:|
| 1 | 예시 baseline | 1000 | 120 | 0 |
| 2 | 예시 baseline | 980 | 900 | 1 |
| 3 | 예시 baseline | 1010 | 140 | 0 |

median, 범위, 표준편차나 bootstrap confidence interval 중 선택한 방법과 표본 단위를 적는다. 여러 metric 중 가장 좋은 것만 고르지 않도록 primary metric과 guardrail을 사전 등록한다. 인과 결론은 대조군과 교란 요인을 검토한 뒤 측정 범위 안에서만 쓴다.

## 보고와 중단 기준

결과 문장은 “빠르다” 대신 조건, 효과 추정, 불확실성과 guardrail 판정을 담는다. 측정 전 숫자는 목표나 가상 trace라고 표시하고 실제 결과처럼 쓰지 않는다. 모든 유효 run, 요약 통계와 분산을 보고하며 제외한 run은 장애 미적용 같은 근거를 남긴다. 빈 결과도 같은 기준으로 보존한다.

정확성 위반, 장애 미적용, 비교 계약 불일치가 나오면 성능 반복을 늘려 덮지 않는다. run 또는 가설을 사전 기준에 따라 기각하고 원인을 고친다. 계획한 반복을 마치거나 guardrail을 위반하면 중단한다.

## 통합 문제와 해설

### 1. 평균 latency가 10ms면 모든 요청이 빠른가?

아니다. 예를 들어 99개가 약 0ms이고 한 개가 1,000ms여도 평균은 약 10ms가 된다. 평균만 보면 대부분의 빠른 요청과 한 사용자의 긴 정지를 구분할 수 없다. p50·p95·p99, 최대와 원시 분포를 함께 보고 느린 요청 ID를 장애 구간 history에 연결한다. “평균 10ms이므로 SLA 100ms를 모두 만족했다”는 결론은 평균을 최대값으로 오해한 것이다. 목표가 평균 응답 비용이라면 평균은 여전히 유용하지만 사용자 꼬리 지연 계약을 대신하지 않는다.

### 2. 장애 명령이 exit 0이면 run은 유효한가?

exit 0은 주입 도구가 명령을 받아들였다는 제어 경로의 성공이다. 실제 traffic이 다른 interface나 namespace를 지나면 data path에는 변화가 없다. F2 방향 probe RTT, packet counter와 peer timeout이 180~240초에 함께 변했는지 확인해야 한다. 기준 2ms에서 목표 약 102ms가 예상인데 probe가 계속 2ms라면 “지연에도 p99가 유지됐다”가 아니라 장애 미적용으로 run을 기각한다. 반대로 RTT가 변했지만 엉뚱한 follower였다면 질문의 독립 변수와 다르므로 역시 재실험한다.

### 3. 후보 node를 5개에서 7개로 늘려 throughput이 30% 증가했다. algorithm 개선인가?

관측된 30%는 algorithm, CPU·메모리·network와 quorum 구성이 함께 바뀐 합성 효과다. 그래서 “새 algorithm이 30% 빠르다”는 인과 결론은 낼 수 없다. 먼저 baseline과 candidate를 모두 5node로 비교해 algorithm 효과를 보고, 별도로 같은 비용 예산에서 node 수를 조정한다. 7node 구성이 실제 배포 후보라면 총 처리량뿐 아니라 node당 처리량, core-hour, egress와 장애 시 여유 용량을 보고한다. 질문이 “예산과 무관한 최종 배포 처리량”이라면 7node 결과도 답이 될 수 있지만 가설 문장을 그 질문에 맞게 미리 바꿔야 한다.

### 4. W1 완료 뒤 R1이 옛 값을 읽었지만 평균 성능은 좋아졌다. 채택 가능한가?

W1은 30ms에 성공 완료했고 R1은 40ms에 호출되었으므로 두 연산은 겹치지 않는다. 순차 register 명세에서 R1은 적어도 2를 읽어야 하며, 42ms에 시작한 W2의 3은 R1과 겹치므로 옛 값 1을 정당화하지 못한다. 평균 성능이 좋아도 이 한 history는 정확성 guardrail을 위반한다. “위반율이 낮으니 평균내자”는 결론은 0건으로 사전 등록한 계약을 사후 변경한다. 최소 반례, 관련 서버 log와 seed를 보존하고 원인을 고친 뒤 새 run을 수행한다. 계약이 eventual consistency였다면 허용 판단은 달라지므로 실험 전에 읽기 의미를 명시해야 한다.

### 5. seed 하나에서 위반이 0이면 안전한가?

seed 하나는 workload와 장애 생성 규칙이 만든 한 schedule의 주소다. 위반 0은 그 schedule의 관측 결과이지 모든 interleaving의 증명은 아니다. 여러 seed로 탐색 범위를 넓히고, baseline과 candidate의 효과 차이를 줄이려면 같은 trace를 사용하는 paired seed run도 둔다. 실패 seed는 workload 파일과 함께 보존해 고정 회귀로 만든다. 생성기가 응답 직후 장애 같은 경계 timing을 만들지 않는다면 seed 수만 늘려도 그 영역은 비어 있으므로 생성 범위 자체를 점검한다.

### 6. p99가 개선됐지만 timeout을 표본에서 제외했다. 결론은?

deadline 2초에서 timeout된 요청을 지우면 최소 2초 걸린 표본들이 분포에서 검열되어 성공 요청 p99가 인위적으로 낮아진다. 따라서 성공 요청 p99라고 정확히 이름 붙이고 timeout 200개, 명시 오류 100개, 성공 11,700개를 모두 보고한다. 10초 run이면 offered load 1,200 req/s, successful throughput 1,170 req/s, 성공률 97.5%다. timeout을 모두 정확히 2초로 넣는 것도 실제 상한을 아는 것처럼 왜곡할 수 있으므로 deadline 이상 또는 미상이라는 범주를 유지한다. 후속 결과 조회로 완료 여부를 알 수 있으면 history 판정도 갱신한다.

### 7. 후보는 fsync를 끄고 기준군은 켰다면?

기준군의 ack가 fsync 완료를 뜻하고 후보 ack가 메모리 기록만 뜻하면 두 latency는 서로 다른 계약의 완료 시간을 잰다. 후보가 빨라도 전원 장애 뒤 승인 쓰기를 잃을 수 있으므로 algorithm 우위로 해석할 수 없다. fsync, replication factor와 ack 의미를 맞춰 다시 비교한다. 제품이 의도적으로 relaxed durability를 선택할 수는 있지만, 그 실험은 별도 조건으로 이름 붙이고 장애 후 손실량과 위험을 함께 보고해야 한다. 단순히 후보 숫자만 기존 표에 넣으면 독자가 같은 성공 의미로 오인한다.

### 8. 새 leader가 2초에 뽑히면 복구 시간은 2초인가?

2초는 process kill부터 새 leader 선출까지의 control-plane 복구다. 첫 client 성공이 3초, p99 정상 범위 복귀가 30초, backlog 0이 60초, 모든 follower catch-up이 90초라면 각각 가용성·성능·작업량·redundancy의 다른 종료점이다. “복구 2초”만 보고하면 88초 동안 줄어든 장애 여유를 숨긴다. 제품 목표가 쓰기 재개라면 첫 성공을, 완전 redundancy라면 catch-up을 주 종료점으로 사전 등록하고 나머지도 보조 지표로 남긴다.

### 9. timeout 요청을 모두 실패로 세면 정확한가?

timeout은 client가 deadline 안에 completion을 받지 못했다는 관측이다. 요청이 서버에 도달하지 않았을 수도 있고, commit 뒤 response만 유실됐을 수도 있다. 모두 실패로 세면 실제 적용된 효과를 누락하고 재시도 중복도 놓친다. request ID 결과 조회와 최종 state로 성공, 미실행, 여전히 미상을 분류한다. 반면 성공 ack를 받은 A 집합의 효과가 없으면 이는 timeout 분류가 아니라 acknowledged loss다. 분석 종료 때도 미상인 요청은 임의로 성공이나 실패에 넣지 말고 범위와 민감도 분석에 남긴다.

### 10. 세 run 중 가장 빠른 하나만 보고해도 되는가?

가장 빠른 run은 warm cache, 유리한 scheduling이나 낮은 이웃 부하를 선택했을 가능성이 높다. 대표값으로 쓰면 일반적인 성능을 과장하고 재현 가능성을 잃는다. 사전 계획한 세 run 모두와 median·범위 또는 선택한 불확실성 통계를 보고한다. 장애 미적용처럼 사전 무효 조건을 만족한 run은 제외할 수 있지만 이유와 원시 artifact를 남기고 대체 run 규칙을 따른다. 질문이 “최적 조건에서 가능한 최고치”라면 best run을 보조 결과로 제시할 수 있으나 일반 성능이나 기대값이라고 부르면 안 된다.

## 공식 자료

- [Google SRE: Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [Jepsen Analyses](https://jepsen.io/analyses/)

[← 이전](13-local-models-and-fault-scenarios.md) · [목차](README.md) · [다음 →](15-exercises-glossary-and-sources.md)
