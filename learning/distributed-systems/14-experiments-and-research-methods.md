# 14. 실험과 연구 방법

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

[← 이전](13-local-models-and-fault-scenarios.md) · [목차](README.md) · [다음 →](15-exercises-glossary-and-sources.md)
