# 14. 실험과 연구 방법

## 성능 숫자와 실제 history 정확성을 함께 기록한다

**history**는 각 연산의 호출 시각, 응답 시각, 입력, 출력, 오류를 모은 기록이다. 처리량과 p99만으로 커밋된 쓰기 손실이나 중복 효과를 찾을 수 없다. 정확성 검사는 history가 주장한 일관성 모델을 만족하는지 본다.

| request | 호출 | 응답 | 입력 | 출력 |
|---|---:|---:|---|---|
| W1 | 10 ms | 30 ms | x=2 | ok |
| R1 | 40 ms | 45 ms | read x | 1 |

W1 완료 뒤 시작한 R1이 1을 반환했으므로 선형화 주장에는 반례다. 평균 지연이 좋아도 정확성 위반은 사라지지 않는다.

## 공정한 장애 측정

독립 변수는 링크 지연 100 ms처럼 의도적으로 바꾸는 값이다. 종속 변수는 처리량·지연·오류·불변식 위반이다. 하드웨어, 버전, 요청 분포, 내구성 설정은 통제한다.

0~60초 warm-up, 60~180초 기준선, 180~240초 장애, 240~360초 복구처럼 구간을 나눈다. 장애 도구가 실제 대상 링크에 적용됐는지 별도 관측한다. 장애 명령 성공은 데이터 경로에 효과가 생겼다는 증거가 아니다.

p99는 표본의 99%가 그 값 이하라는 분위수다. 100개 표본의 “한 개 최악값”을 안정적인 p99로 일반화하면 표본이 너무 작을 수 있다. 반복 횟수, 표본 수, 신뢰 구간이나 실행 간 분산을 함께 기록한다.

| 실행 | 처리량/s | p50 ms | p99 ms | 정확성 위반 |
|---|---:|---:|---:|---:|
| 1 | 1000 | 8 | 120 | 0 |
| 2 | 980 | 9 | 900 | 1 |
| 3 | 1010 | 8 | 140 | 0 |

평균 처리량만 보면 비슷하지만 실행 2는 꼬리 지연과 정확성 위반 때문에 같은 결론으로 묶으면 안 된다.

## 추가 문제와 해설

### 1. 평균 10 ms면 모든 요청이 빠른가?
아니다. 소수 2초 요청을 평균이 숨길 수 있어 p95·p99와 분포를 본다.

### 2. fault injection 명령 exit 0이면 장애가 적용됐는가?
아니다. 대상 경로의 패킷·지연 관측으로 검증한다.

### 3. 설정이 다른 두 시스템 처리량을 바로 비교해도 되는가?
내구성·일관성·데이터·부하 조건을 맞춰야 공정하다.

### 4. history에 호출·응답 둘 다 필요한 이유는?
연산 겹침과 실시간 선후를 판단하기 위해서다.

### 5. 한 번 실행으로 결론 내리기 어려운 이유는?
JIT, 캐시, 배경 작업, 네트워크 변동 때문에 반복 분산이 존재한다.

## 분산 실험을 검증 가능한 문장으로 만들기

“재구성이 빠르다” 대신 “3 node에서 shard 1 GiB를 옮길 때 p99 client latency와 완료 시간을 기존 방식보다 비교한다”처럼 입력, 조건, metric을 적는다.

독립 변수는 한 번에 바꾸는 조건이고 종속 변수는 측정 결과다. Hardware, data 크기, failure timing이 함께 바뀌면 어느 요인이 원인인지 알기 어렵다.

| 시각 | 단계 | 기록 |
|---:|---|---|
| t0 | 정상 상태 5분 | QPS, p99, CPU baseline |
| t1 | node 1 network 차단 | 정확한 주입 명령 시각 |
| t2 | leader 교체 | term과 새 leader |
| t3 | traffic 회복 | 오류율과 p99 |
| t4 | 검증 | 누락·중복·불변조건 |

정확성 실험은 “모든 acknowledged write가 복구 뒤 존재하는가”를 본다. 성능 실험은 latency와 throughput을 본다. 빠르게 잘못된 결과를 내는 system을 성공으로 세지 않는다.

반복마다 seed, workload trace, version, node 배치, clock source를 기록한다. 평균만 보고하지 않고 p50/p95/p99, 최대, 실패 횟수를 함께 남긴다.

장애 주입이 정말 적용됐는지도 독립 증거가 필요하다. Firewall 명령 성공만으로 packet이 차단됐다고 단정하지 않고 packet counter나 peer timeout을 확인한다.

### 완전 해설 문제

1. 후보에서 node 수도 함께 늘리면? **해설:** Algorithm과 자원 증가 효과가 섞인다. 같은 자원 비교나 별도 축 실험이 필요하다.
2. 최고 한 번만 보고하면? **해설:** 우연한 scheduling과 cache 효과를 평균 성능으로 과장한다.
3. Latency가 개선됐지만 acknowledged write가 사라지면? **해설:** 정확성 guard 위반이므로 성능 성공으로 보고할 수 없다.

[← 이전](13-local-models-and-fault-scenarios.md) · [목차](README.md) · [다음 →](15-exercises-glossary-and-sources.md)

## 질문을 검증 가능한 문장으로 바꾼다

“빠른가?” 대신 “5노드 중 한 팔로워에 100 ms 지연을 넣었을 때 쓰기 p99가 얼마나 변하는가?”라고 쓴다.
독립 변수는 의도적으로 바꾸는 값이다.
종속 변수는 측정 결과다.
통제 변수는 비교 동안 고정하는 조건이다.

```mermaid
flowchart LR
 Q[연구 질문] --> H[가설]
 H --> D[실험 설계]
 D --> M[측정]
 M --> V[불변식 검증]
 V --> C[결론과 한계]
```

## 정확성과 성능을 분리한다

성능 지표는 처리량, 평균, p50, p95, p99 지연을 포함한다.
정확성 지표는 승인된 쓰기 손실, 중복 효과, 단조 읽기 위반 같은 사건 수다.
빠르지만 커밋된 쓰기를 잃는 시스템은 같은 의미의 비교 대상이 아니다.
먼저 응답 의미와 일관성 수준을 고정한다.

## 실험 시간표

0~60초는 준비와 캐시 가열 구간이다.
60~360초는 정상 부하 기준선이다.
180초에 특정 링크 지연을 주입한다.
240초에 장애를 해제한다.
360~420초는 복구 확인 구간이다.
이 숫자는 교육용 설계 예이며 제품 기준이 아니다.

클라이언트 요청 ID, 시작·종료 시각, 응답 상태를 기록한다.
서버 term, leader, commit index, applied index를 기록한다.
네트워크 장애 시작과 종료를 같은 시간축에 표시한다.
관측 도구 자체가 부하를 바꿀 수 있으므로 샘플링 비용도 적는다.

## 재현성

버전, 설정, 하드웨어, 데이터 크기, seed, 명령을 기록한다.
최소 세 번 반복하고 분산을 본다.
성공한 실행만 고르지 않는다.
원시 자료와 계산식을 보존한다.
인과 결론은 대조군과 교란 요인을 검토한 뒤 제한적으로 쓴다.

## 반례

평균 10 ms는 p99 2초를 숨길 수 있다.
장애 주입 프로세스가 죽었다고 실제 장애가 적용됐다는 뜻은 아니다.
로그에 오류가 없다고 정확성 위반이 없다는 뜻도 아니다.

## 문제와 해설

### 1. p99는 무엇인가?
관측 요청의 99%가 그 값 이하이고 약 1%가 더 느리다는 분위수다.

### 2. 장애 실험의 첫 검증은?
의도한 링크와 시간에 장애가 실제 적용됐는지 확인하는 것이다.

### 3. 처리량 비교 전 맞춰야 할 것은?
요청 의미, 내구성, 일관성, 데이터와 부하 조건이다.

## 공식 자료

- [Google SRE Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [Jepsen Analyses](https://jepsen.io/analyses)



## 용어를 측정 객체로 정의한다

**연구 가설**은 독립 변수를 바꾸면 어떤 종속 변수가 어떤 방향으로 변한다는 반증 가능한 문장이다. 실험 계획서에 기록되고 분석 종료까지 산다. **장애 주입**은 특정 링크·프로세스·디스크 경계에 지연, 손실이나 중단을 넣는 실제 사건이다. 주입 도구와 대상 경로가 관리하며 정한 구간에만 유효해야 한다.

**지연 latency**는 요청 호출부터 응답까지의 시간 표본이고, **처리량 throughput**은 단위 시간에 계약을 만족해 완료한 요청 수다. 클라이언트 recorder가 request ID별로 저장한다. 오류나 timeout을 빼고 성공만 계산하면 왜곡된다.

**history**는 각 연산의 ID, invocation, completion, 입력, 출력과 오류를 모은 기록이다. run artifact로 내구 저장하고 분석·감사 기간 동안 보존한다. **선형화 가능성 검사**는 history가 각 연산을 호출과 응답 사이 한 점에 배치해 실시간 순서와 순차 명세를 만족하는지 묻는다. 로그에 오류가 없다는 말보다 강한 정확성 증거가 필요해 쓴다.

**seed**는 난수 workload와 장애 schedule을 다시 만드는 입력 정수다. 실험 harness가 run metadata에 보관한다. 같은 seed 재현과 여러 seed 탐색을 모두 위해 필요하다. **통계**는 표본 분포, 반복 간 변동과 불확실성을 요약하는 계산이다. 평균 하나가 꼬리와 실패 run을 숨기지 못하게 한다.

**강한 기준군**은 후보와 같은 하드웨어·내구성·일관성·부하 조건에서 합리적으로 잘 조정된 비교 대상이다. **기각 조건**은 성능 수치와 무관하게 가설을 받아들이지 않을 사전 조건이다. acknowledged write 손실 1건, checker 위반, 장애 미적용 등이 예다.

## 검증 가능한 가설

가설 H1을 다음처럼 쓴다. “5노드 동일 하드웨어에서 한 follower 링크에 왕복 100ms 지연을 넣어도 quorum write의 p99가 기준선보다 25% 넘게 증가하지 않고, acknowledged write 손실과 linearizability 위반이 0이다.” 25%는 제품 목표로 정한 교육 기준이지 관측 결과가 아니다.

독립 변수는 follower 링크 추가 지연 0ms와 100ms다. 종속 변수는 성공 throughput, 전체 요청 p50·p95·p99, timeout율, 복구 시간, 정확성 위반 수다. 통제 변수는 서버 수5, CPU·메모리, software commit, fsync, request mix, key 분포, client 수, payload와 측정 시간이다.

기각 조건은 다음처럼 미리 쓴다.

1. 장애가 목표 링크에 실제 적용되지 않았다.
2. 어느 run에서든 acknowledged write가 복구 뒤 사라졌다.
3. history checker가 선형화 불가능 반례를 냈다.
4. 후보와 기준군의 durability 또는 consistency 설정이 다르다.
5. 유효 표본이나 반복 수가 사전 최소에 못 미친다.

## 구체적 시간표와 장애 검증

| 구간 | 시각 | 행동 | 수집 |
|---|---|---|---|
| 준비 | 0~60s | 연결·JIT·cache warm-up | 분석에서 분리 |
| 기준선 | 60~180s | 장애 없는 고정 부하 | QPS, latency, history |
| 주입 | 180s | follower F2 링크 +100ms | tool timestamp, packet probe |
| 장애 | 180~240s | 같은 부하 유지 | 오류, leader/term, latency |
| 해제 | 240s | 규칙 제거 | 실제 RTT 회복 확인 |
| 복구 | 240~360s | backlog와 replica 추적 | catch-up, history |
| 검증 | 이후 | 모든 ack write 조회 | checker와 checksum |

기존 원문의 0~60, 60~180, 180~240, 240~360 구간을 유지한다. 다른 예의 60~360 기준선과 360~420 검증을 혼합하지 않고 run별 계획을 하나 선택한다.

장애 명령 exit0은 적용 증거가 아니다. F2 방향 probe RTT가 예를 들어 기준 2ms에서 교육 목표 약102ms로 변했는지, packet counter와 peer metric이 같은 시간을 가리키는지 확인한다. 여기의 2와102는 기대 설계값이며 측정 결과로 주장하지 않는다. 대상 interface나 namespace가 틀리면 run을 무효로 처리한다.

## history를 손으로 검사하는 최소 예

| op | invoke | complete | 입력 | 출력 |
|---|---:|---:|---|---|
| W1 | 10ms | 30ms | x=2 | ok |
| R1 | 40ms | 45ms | read x | 1 |
| W2 | 42ms | 60ms | x=3 | ok |
| R2 | 61ms | 66ms | read x | 3 |

W1은 30ms에 끝나고 R1은 40ms에 시작하므로 실시간 순서상 W1이 R1보다 앞이다. R1이 1을 반환했으므로 초기 x=1, register 명세에서는 선형화 반례다. W2는 R1과 겹치므로 R1을 설명할 수 없다. 이미 완료된 W1의 2보다 이전 값이기 때문이다. R2의 3은 W2 뒤라 허용된다.

checker 입력에는 성공뿐 아니라 timeout도 둔다. timeout operation은 effect가 있었을 수 있어 unknown으로 처리하고 후속 read와 request ID로 제약한다. 클라이언트 clock이 여러 머신이면 timestamp 오차가 순서 판단을 바꿀 수 있으므로 한 recorder 또는 검증된 clock 조건을 쓴다.

## latency와 throughput 계산

10초 동안 12,000개를 보냈고 11,700개 성공, 200 timeout, 100 명시 오류라면 offered load는 1,200 req/s, successful throughput은 1,170 req/s다. 실패 300개를 분모에서 지우지 않고 성공률 97.5%도 함께 보고한다. 숫자는 계산 예이지 실험 결과가 아니다.

p99는 정렬 표본의 분위수 정의를 명시한다. 100개에서 최악 한 점을 p99의 안정 추정으로 일반화하지 않는다. 표본이 적으면 raw 분포와 최대를 보여 준다. coordinated omission을 피하려면 서버 응답 뒤 다음 요청을 보내는 closed-loop 결과만으로 과부하 대기 시간을 숨기지 않는지 검토한다.

## 반복과 통계

각 조건을 최소 3회라는 기존 기준으로 시작하되, 효과 크기와 변동에 맞춰 더 늘린다. 순서를 항상 baseline→candidate로 고정하면 시간 drift가 섞이므로 run 순서를 무작위화하거나 교차한다. seed, workload trace, 배치와 시작 시각을 기록한다.

| run | 조건 | throughput/s | p99 ms | violation |
|---:|---|---:|---:|---:|
| 1 | 예시 baseline | 1000 | 120 | 0 |
| 2 | 예시 baseline | 980 | 900 | 1 |
| 3 | 예시 baseline | 1010 | 140 | 0 |

이 원문 수치는 교육 표다. 평균 throughput은 비슷해도 run2의 정확성 위반 1건 때문에 성공 조건을 통과하지 않는다. median, 범위, 표준편차나 bootstrap confidence interval 중 선택한 방법과 표본 단위를 적는다. request 수백만 개를 독립 반복처럼 취급하지 않고 run 간 변동도 본다.

다중 metric 중 가장 좋은 것만 고르면 선택 편향이 생긴다. primary metric과 guardrail을 사전 등록한다. p99 개선이 25% 기준을 넘더라도 오류율, CPU 비용과 정확성 guardrail을 함께 본다.

## 공정한 비용 비교

후보가 node 7개, 기준군이 5개면 algorithm과 자원 증가가 섞인다. 동일 node 비교와 동일 비용 비교를 분리한다. cloud 비용뿐 아니라 CPU core-hour, 저장 byte, network egress, 운영 복잡도와 복구 중 여유 용량을 기록한다.

내구성을 끄거나 batch 크기를 키워 latency를 낮춘 후보를 같은 의미로 비교하지 않는다. ack 의미, fsync, replication factor, compression, dataset와 consistency를 맞춘다. 강한 기준군도 권장 설정과 충분한 warm-up을 사용한다. 약하게 튜닝한 기준군은 후보 장점을 과장한다.

관측 도구의 비용도 측정한다. 모든 RPC payload를 동기 로그로 남기면 latency가 바뀔 수 있다. sampling on/off 대조 run이나 recorder CPU를 기록한다. 정확성 history에 필요한 필드는 잃지 않되 payload 전체 대신 hash를 보존할 수 있다.

## 장애 종류별 주입 위치

- network delay: leader↔특정 follower 양방향인지 단방향인지 명시한다.
- packet loss: 비율, burst 길이와 재정렬 여부를 기록한다.
- process kill: SIGKILL 시각과 restart policy를 기록한다.
- CPU pause: process는 살아 있으나 진행하지 않는 시간을 주입한다.
- disk stall: 특정 WAL device의 write/fsync 지연을 겨냥한다.
- clock fault: wall clock과 monotonic clock 중 대상을 구분한다.

한 run에서 여러 장애를 동시에 바꾸면 원인이 섞인다. 상호작용이 질문이면 factorial design으로 각 조합과 기준을 둔다.

## 완전 풀이 문제

### 문제 6. 평균 latency 10ms면 모든 요청이 빠른가?

**풀이:** 아니다. 소수 2초 요청을 평균이 숨길 수 있다. p50·p95·p99, 최대와 raw 분포를 보고 느린 요청이 장애 구간에 몰렸는지 history와 연결한다.

### 문제 7. 주입 명령 exit0이면 run은 유효한가?

**풀이:** 아니다. 대상 링크 RTT, packet counter와 peer timeout으로 실제 데이터 경로에 적용됐음을 검증한다. 증거가 없으면 결과가 좋아도 무효 run이다.

### 문제 8. 후보 node를 5에서7로 늘려 throughput이 30% 증가했다. algorithm 개선인가?

**풀이:** 자원 증가 효과가 섞였다. 동일 5node 비교와 동일 비용 비교를 따로 수행하고 core-hour·network 비용을 함께 본다.

### 문제 9. W1 완료 뒤 R1이 옛 값을 읽었다. 평균 성능이 좋아도 채택 가능한가?

**풀이:** linearizability가 계약이면 즉시 guardrail 위반이다. 빠르게 틀린 결과는 성능 성공이 아니다. 최소 반례 history를 보존하고 원인을 조사한다.

### 문제 10. seed 하나에서 위반0이면 안전한가?

**풀이:** 해당 schedule에서 발견하지 못했다는 뜻이다. 여러 seed와 경계 timing을 탐색하고 실패 seed를 고정 회귀로 남긴다.

### 문제 11. p99가 개선됐지만 timeout을 표본에서 제외했다. 결론은?

**풀이:** 가장 느린 요청을 제거해 왜곡했을 수 있다. timeout을 별도 결과와 지연 상한으로 포함하고 offered load, 성공 throughput과 성공률을 함께 보고한다.

### 문제 12. 후보가 fsync를 끄고 기준군은 켰다면?

**풀이:** ack durability가 달라 공정 비교가 아니다. 같은 설정으로 재실험한다. 내구성 완화 실험은 별도 조건과 위험으로 보고한다.



## 사전 등록 실험표

| 항목 | 기록 예 | 왜 필요한가 |
|---|---|---|
| hypothesis | 100ms follower 지연에서 p99 증가≤25% | 사후 기준 변경 방지 |
| primary metric | 전체 요청 p99 | 좋은 지표만 고르기 방지 |
| correctness guard | ack loss=0, checker violation=0 | 성능보다 먼저 판정 |
| baseline | 같은 5node·fsync·RF | 의미가 같은 비교 |
| seeds | 101,202,303 이상 | schedule 재현 |
| sample unit | request와 run 둘 다 | 의사 반복 방지 |
| stop rule | 계획 반복 완료 또는 guard 위반 | 좋아질 때까지 반복 방지 |
| artifacts | config, history, raw metric, 주입 증거 | 재검산 가능 |

실험 도중 violation이 나오면 seed와 최소 history를 즉시 보존한다. 이후 run이 정상이라고 앞 위반을 평균내 0에 가깝게 만들지 않는다. 정확성 조건은 비율 최적화 대상이 아니라 계약에 따른 기각 조건일 수 있다.

## 복구 시간의 시작과 끝

장애 복구 시간은 어느 사건부터 어느 사건까지인지 정의한다. process kill 시각부터 새 leader 선출까지만 재면 replica catch-up과 client 성공 회복을 빼게 된다. 이 실험에서는 주입 시각, 마지막 성공, 새 leader, 첫 성공, p99 정상 범위 복귀, backlog0, 모든 replica catch-up을 각각 기록한다.

예를 들어 새 leader가 2초에 선출됐지만 p99가 30초 동안 높고 follower가 90초에 따라잡았다면 “복구2초” 하나로 요약하지 않는다. 서비스 가용성, 성능 안정화와 redundancy 회복은 다른 종료점이다. 이 숫자들은 설명용이며 실제 관측이 아니다.

## 누락과 중복 검사

요청 ID 1~10,000을 발급하고 성공 ack 집합 A를 저장한다. 복구 뒤 state에서 A의 모든 효과가 있는지 검사한다. 같은 ID 효과가 둘 이상이면 중복, A에 있는데 효과가 없으면 acknowledged loss다. timeout 집합 U는 성공 또는 미실행 둘 다 가능하므로 결과 조회로 분류하고 즉시 loss로 세지 않는다.

최종 checksum만 같아도 중간 선형화 위반을 놓칠 수 있다. history checker와 최종 state 검사를 함께 쓴다. checker 자체 버그 가능성 때문에 작은 known-valid와 known-invalid history로 분석기를 검증하지만 검사기 구현을 연구 결과의 분량으로 대신하지 않는다.

## 추가 풀이

### 문제 13. 새 leader가 2초에 뽑히면 복구 시간은 2초인가?

**풀이:** 정의에 따라 일부일 뿐이다. client 성공, latency 안정화, backlog0와 replica redundancy 회복 시각을 별도 기록한다. 제품 목표에 맞는 종료점을 사전 정의한다.

### 문제 14. timeout 요청을 모두 실패로 세면 정확한가?

**풀이:** 아니다. server effect 뒤 response만 유실됐을 수 있다. request ID로 결과를 조회해 성공·미실행·미상으로 분류한다. acknowledged success 손실과도 섞지 않는다.

### 문제 15. 세 run 중 가장 빠른 하나만 논문 표에 넣어도 되는가?

**풀이:** scheduling과 cache 운을 선택해 과장한다. 사전 계획한 모든 유효 run, 요약 통계와 분산을 보고하고 제외 run은 장애 미적용 같은 근거를 남긴다.

실험 환경의 software commit, kernel, runtime, storage class와 topology도 artifact에 고정한다. 같은 이름의 instance라도 세대와 noisy-neighbor가 다를 수 있어 실제 할당 정보를 남긴다. 원시 자료에서 표까지의 계산식과 제외 규칙을 version control하고, 결론은 측정한 범위를 넘어 일반화하지 않는다.

빈 결과도 같은 기준으로 보존한다.

항상 검증한다.

## 결과 문장과 중단 기준

“빠르다” 대신 조건, 효과 추정, 불확실성, guardrail을 쓴다. 측정 전 숫자는 목표·가상 trace로 표시하고 실제 결과처럼 서술하지 않는다. 정확성 위반이나 장애 미적용이 나오면 성능 반복을 늘려 덮지 않고 run을 기각하고 원인을 고친다.


[← 이전](13-local-models-and-fault-scenarios.md) · [목차](README.md) · [다음 →](15-exercises-glossary-and-sources.md)
