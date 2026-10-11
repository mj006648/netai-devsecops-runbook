# 15. 종합 문제, 용어, 출처

## 용어를 한 요청의 문맥으로 연결하기

클라이언트가 request ID R9로 쓰기를 보낸다. RPC stub이 직렬화하고 리더가 현재 term의 log entry를 만든다. 쿼럼 복제 뒤 commitIndex가 전진하고 상태 기계가 lastApplied를 올린다. 응답이 유실되면 클라이언트는 timeout을 보지만 결과는 미상이다. 같은 R9 재시도는 영속 dedup 기록에서 기존 결과를 찾는다.

이 한 흐름에서 node는 실행 주체, log는 명령 역사, term은 선거 시대, quorum은 교집합을 만드는 집합, commit은 합의 경계, apply는 업무 실행, timeout은 기다림 정책, idempotency는 반복 효과의 성질이다. 용어는 독립 사전 항목이 아니라 앞뒤 상태를 설명한다.

두 번째 흐름은 stream이다. source offset 1000과 operator state 55가 checkpoint CP20에 함께 저장된다. 1030에서 crash하면 CP20을 복원하고 1001부터 재생한다. sink가 CP ID로 중복 commit을 막지 않으면 외부 출력은 두 번 보일 수 있다.

## 추가 종합 문제

### 13. 5노드 matchIndex가 `[9,9,8,8,3]`이면 과반수 복제 최대 index는?
세 번째 큰 값 8이므로 복제 수 기준 index 8이다. 직접 커밋은 index 8의 term이 현재 term인지 확인한다.

### 14. lease token 7 worker가 정지한 뒤 token 8이 발급됐다. 7의 쓰기는?
실제 저장소가 현재 token 8을 검사해 7을 거부해야 한다. 발급자 판단만으로는 부족하다.

### 15. Iceberg writer 둘이 같은 metadata pointer를 읽었다. 둘 다 성공할 수 있는가?
같은 기대 pointer에 대한 CAS는 한 writer만 성공한다. 다른 writer는 최신 metadata로 재계획한다.

### 16. checkpoint state는 50인데 offset을 80에서 재개하면?
51~80 입력 효과가 state에 없고 재생도 건너뛰므로 누락된다. 상태와 offset은 같은 경계여야 한다.

### 17. p99가 500 ms인데 평균이 20 ms인 결과를 어떻게 읽는가?
대부분은 빠르지만 느린 꼬리가 존재한다. 표본 수와 분포, 느린 요청의 장애 구간을 함께 조사한다.

## 기존 문제를 풀 때 따라갈 공통 추적법

각 문제를 `입력 상태 → message 순서 → durable write → 응답 → 장애 → 복구 상태`로 다시 쓴다. “성공”이라는 말은 client 응답, quorum commit, state machine 적용, 외부 부작용 중 무엇인지 표시한다.

### 상세 추적 1: 응답 유실과 retry

Request ID R1의 업무 commit 뒤 response만 유실됐다. 같은 ID·같은 payload retry는 dedup table의 저장 결과를 반환해야 한다. 새 ID retry는 새 업무가 되어 중복될 수 있다. 같은 ID·다른 payload는 충돌로 거절한다.

### 상세 추적 2: checkpoint와 sink

Checkpoint C10 이후 event E11의 sink write는 성공했지만 C11 저장 전에 crash했다. 복구는 C10부터 E11을 다시 처리한다. Sink가 `(job,E11)` 고유 key나 transaction을 지원하지 않으면 결과가 두 번 생긴다.

### 상세 추적 3: lease와 stale writer

A token 8의 lease가 끊긴 뒤 B가 token 9를 받았다. A가 늦게 돌아와 write해도 storage의 highest token 9 검사에서 8을 거절해야 한다. TTL 만료만으로 A process가 멈췄다고 가정하지 않는다.

### 상세 추적 4: Iceberg 게시

Data file 존재, metadata 존재, catalog pointer 변경은 세 상태다. Reader에게 보이는 기준은 선택한 snapshot이다. File upload 성공을 table commit 성공이라고 부르지 않는다.

## 용어를 연결해서 읽기

**복제**는 같은 data 사본을 여러 node에 두는 일이고, **합의**는 어느 값과 순서를 채택할지 정하는 protocol이다. 사본 수가 많다고 자동으로 합의되는 것은 아니다.

**멱등성**은 반복 적용 결과를 한 번과 같게 만들고, **중복 제거**는 request identity를 기억해 반복 실행을 막는 구현 방법이다. 내구성 없는 기억은 재시작 뒤 사라진다.

**리스**는 시간 제한 권리이고 **fencing token**은 이전 holder의 늦은 write를 실제 자원에서 차단하는 세대 번호다.

**Checkpoint**는 내부 상태 복구점이고 **commit**은 특정 system이 변경을 확정한 경계다. 외부 sink의 commit과 같은 말이 아니다.

**Linearizable**은 실시간 순서와 맞는 단일 최신 관찰을 요구하고, **serializable read**는 etcd 문맥에서 한 revision의 일관된 값을 주지만 최신성은 약할 수 있다.

[← 이전](14-experiments-and-research-methods.md) · [목차](README.md)

## 종합 문제 12개와 해설

1. **3복제본 중 리더와 한 팔로워가 entry를 영속 저장했다. 조건부 과반수인가?**
   3노드 과반수 2개다. 다만 Raft 커밋은 현재 term entry 규칙과 리더 상태도 확인해야 한다.
2. **결제 timeout 뒤 새 요청 ID로 재시도해도 되는가?**
   안 된다. 첫 결과가 미상이므로 중복 결제가 될 수 있다.
3. **snapshot isolation이면 선형화 읽기인가?**
   아니다. 오래된 시작 snapshot을 의도적으로 읽을 수 있다.
4. **5노드가 2대와 3대로 갈라졌다. 어느 쪽이 커밋 가능한가?**
   과반수 규칙에서는 3대 쪽만 가능하다.
5. **2PC participant가 YES 뒤 coordinator를 잃었다. 자동 abort 가능한가?**
   아니다. 전역 commit이 기록됐을 수 있어 결정을 배울 때까지 막힐 수 있다.
6. **lease 보유자가 긴 정지 뒤 깨어났다. 로컬 시간만 보고 써도 되는가?**
   위험하다. 저장소가 최신 fencing token을 검사해야 한다.
7. **Iceberg data file 업로드 성공은 테이블 커밋인가?**
   아니다. 현재 metadata pointer가 새 snapshot을 가리켜야 한다.
8. **Spark task 재실행은 언제 안전하지 않은가?**
   외부 비멱등 API 효과를 남겼는데 중복 경계가 없을 때다.
9. **checkpoint에 상태만 있고 offset이 없으면?**
   어느 입력부터 재생할지 몰라 누락이나 중복이 생긴다.
10. **CAP는 평상시 모든 지연 절충을 설명하는가?**
    아니다. 핵심 조건은 네트워크 파티션이다.
11. **오래된 term entry가 과반수에 있으면 새 리더가 즉시 커밋 표시 가능한가?**
    Raft는 현재 term entry를 과반수 복제해 commit index를 전진시키고 prefix를 간접 커밋한다.
12. **평균 지연만 보고 실험 결론을 내릴 수 있는가?**
    꼬리 지연, 오류, 정확성 위반, 반복 분산을 함께 봐야 한다.

## 용어 60개

1. 노드: 참여 컴퓨터나 프로세스.
2. 클라이언트: 요청을 시작하는 주체.
3. 서버: 요청을 처리하는 주체.
4. 상태: 다음 행동에 영향을 주는 기억값.
5. 복제본: 같은 논리 상태의 사본.
6. 로그: 순서 있는 사건·명령 기록.
7. entry: 로그 한 항목.
8. index: 로그 위치.
9. term: Raft 선거 임기.
10. leader: 쓰기 순서를 제안하는 노드.
11. follower: 리더 복제를 따르는 노드.
12. candidate: 선거에 출마한 노드.
13. 쿼럼: 결정을 진행하는 필요 집합.
14. 과반수: 전체 절반보다 큰 수.
15. 커밋: 시스템 규칙상 결정된 상태.
16. 적용: 명령을 상태 기계에 실행함.
17. 상태 기계: 명령 순서로 상태를 바꾸는 계산.
18. RPC: 원격 프로세스 기능 호출.
19. 직렬화: 객체를 바이트로 변환.
20. timeout: 기다림을 끝내는 시간 정책.
21. retry: 같은 목적의 재요청.
22. 멱등성: 반복 적용 결과가 한 번과 같음.
23. deduplication: 중복 요청 탐지·억제.
24. partial failure: 일부만 실패한 상태.
25. partition: 집합 사이 통신 단절.
26. linearizability: 실시간 순서를 지키는 단일 연산 관점.
27. snapshot isolation: 시작 snapshot을 읽는 격리.
28. eventual consistency: 통신 회복 뒤 최종 수렴.
29. transaction: 하나의 논리 작업 단위.
30. atomicity: 전부 적용 또는 전부 취소.
31. 2PC: prepare와 결정의 2단계 커밋.
32. coordinator: 2PC 결정을 모으는 주체.
33. participant: 2PC 변경 담당자.
34. prepared: YES 뒤 결정을 기다리는 상태.
35. shard: 키 공간 일부.
36. shard map: 키와 담당 그룹의 대응표.
37. epoch: 구성 세대 번호.
38. reconfiguration: 구성원·소유권 변경.
39. checkpoint: 복구 가능한 처리 상태.
40. offset: 스트림 입력 위치.
41. barrier: checkpoint 경계를 맞추는 표식.
42. watermark: event time 진행 추정.
43. heartbeat: 생존을 알리는 주기 메시지.
44. failure detector: 관측으로 장애를 의심하는 모듈.
45. lease: 기간 제한 사용 권리.
46. fencing token: 오래된 소유자를 막는 증가 번호.
47. wall clock: 달력 시각.
48. monotonic clock: 경과 측정용 비감소 시계.
49. logical clock: 사건 순서용 논리 값.
50. happens-before: 인과적 선행 관계.
51. snapshot: 특정 시점 상태 이미지.
52. compaction: 오래된 기록 정리.
53. MVCC: 버전별 값을 보존하는 동시성 방식.
54. revision: 저장소 변경 논리 번호.
55. Spark driver: 작업 계획·조정을 맡는 프로세스.
56. Spark executor: task를 실행하는 프로세스.
57. shuffle: partition 사이 데이터 이동.
58. Iceberg manifest: data file 목록·통계 메타데이터.
59. catalog: 테이블 현재 metadata 위치를 관리하는 서비스.
60. invariant: 모든 허용 실행에서 지켜야 하는 조건.

## 주요 공식·원 논문 자료

- [Raft](https://raft.github.io/raft.pdf)
- [Lamport clocks](https://lamport.azurewebsites.net/pubs/time-clocks.pdf)
- [etcd documentation](https://etcd.io/docs/)
- [Apache Spark documentation](https://spark.apache.org/docs/latest/)
- [Apache Iceberg documentation](https://iceberg.apache.org/docs/latest/)
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [Google SRE Book](https://sre.google/sre-book/table-of-contents/)

자료 확인일: 2026-10-11.



## 객체를 한 요청 흐름으로 연결한다

**분산 객체**는 이름만 아는 용어가 아니라 위치·관리자·수명과 전이를 가진다. 요청 R9는 client에서 만들어져 RPC message로 이동한다. leader는 현재 term의 log entry를 만들고 follower log에 복제한다. quorum 조건이 맞으면 commitIndex가 전진하며 state machine이 lastApplied까지 실행한다. dedup row는 R9와 결과를 업무 변경과 함께 보존한다. 응답 timeout은 client의 기다림 수명만 끝내며 commit된 entry나 업무 효과를 지우지 않는다.

stream E9는 source partition과 offset을 갖고 operator state를 바꾼다. checkpoint는 offset·state·watermark를 한 cut에 저장한다. crash 뒤 replay가 sink write를 반복할 수 있어 sink transaction이나 idempotent key가 필요하다. lease는 coordinator의 임시 소유권이고 fencing token은 storage가 낡은 writer를 거부하는 세대다. Iceberg data file은 catalog snapshot이 선택할 때만 현재 table에 보인다.

이 연결에서 같은 단어도 대상이 다르다. Raft commit은 log 결정, 2PC commit은 참여자 전체 결정, sink commit은 출력 게시, Iceberg commit은 metadata pointer 교체다. 성공 지점을 섞지 않는다.

## 종합 문제 15개와 전체 풀이

### 문제 1. 응답 유실 뒤 R9를 새 ID로 재시도하면 무엇이 깨지는가?

**풀이:** server가 첫 R9를 commit하고 응답만 잃었을 수 있다. 새 ID R10은 dedup 저장소에서 새 업무로 보이므로 효과가 두 번 생긴다. 같은 R9와 같은 payload hash로 재시도해 저장 결과를 받아야 한다. 같은 R9에 다른 payload면 충돌로 거부한다. timeout은 실패 판정이 아니라 결과 미상이다.

### 문제 2. 3노드 Raft에서 A·B가 current term index7을 저장했다. client 성공까지 무엇이 남는가?

**풀이:** 과반수2에 복제돼 leader가 commitIndex7을 전진시킬 수 있다. 그러나 state machine이 lastApplied7까지 실행하고 업무 결과를 내구화해야 한다. 응답 packet 전달도 별도다. leader가 apply 뒤 응답 전에 죽으면 client는 미상이지만 효과는 남는다. 새 leader와 request ID 조회로 결과를 배운다.

### 문제 3. 5노드 matchIndex가 [9,9,8,8,3]이면 무엇을 직접 commit할 수 있는가?

**풀이:** 세 번째 큰 값8까지 과반수3이 복제했다. index8 entry가 current term이면 leader는 8을 직접 commit하고 prefix도 간접 commit한다. index8이 과거 term뿐이면 복제 수만으로 직접 commit하지 않는다. current term entry를 과반수에 복제한 뒤 prefix를 포함시킨다. 숫자와 term 조건을 함께 본다.

### 문제 4. 5노드가 2대와3대로 분할됐다. 양쪽이 쓰기를 받으면 왜 위험한가?

**풀이:** majority가3이면 3대 집합만 새 commit을 만들 수 있다. 2대 쪽은 옛 leader가 살아 있어도 quorum 증거가 없다. 양쪽 쓰기를 성공시키면 서로 다른 log가 외부 효과를 만들 수 있다. 2대 쪽은 읽기 계약에 따라 제한된 stale read만 제공하거나 실패한다. partition 회복 뒤 log repair가 client에 이미 약속한 두 성공을 모두 정당화하지 못한다.

### 문제 5. 2PC 참여자가 YES 뒤 coordinator를 잃었다. 30초 후 abort 가능한가?

**풀이:** coordinator가 COMMIT을 영속화하고 메시지만 잃었을 수 있다. 독자 abort는 다른 participant의 commit과 갈린다. PREPARED WAL과 잠금을 유지하고 권위 결정 로그를 조회한다. 복제 coordinator가 있으면 같은 transaction ID의 결정을 재전송한다. timeout은 경보이지 abort 증거가 아니다.

### 문제 6. lease token7 worker가 40초 멈춘 사이 token8이 발급됐다. 누가 막는가?

**풀이:** lease 서비스는 token8을 발급해도 token7 process를 멈추지 못한다. worker가 깨어나 storage에 쓸 수 있다. storage가 highest token8을 영속 기억하고 token7 write를 거부해야 한다. 이것이 fencing이다. API front door만 검사하면 직접 storage 경로가 우회할 수 있다.

### 문제 7. CP20이 P0=1000, P1=2000, sum55다. 장애 전 각 3개를 처리해 sum62였다면 복구는?

**풀이:** 완료 checkpoint CP20의 state55와 두 offset을 함께 복원한다. P0 1001~1003, P1 2001~2003 여섯 record를 replay해 62를 만든다. 장애 전 sink 효과가 남았을 수 있어 CP transaction ID나 upsert key로 중복을 막는다. state만55로 돌리고 offset을 최신으로 두면 누락이다. offset만 과거로 돌리고 state62를 두면 중복 계산이다.

### 문제 8. watermark10:05 뒤 event time10:03 사건이 오면 버그인가?

**풀이:** watermark는 이 시각 이전 사건이 대체로 왔다는 정책적 진행값이다. 허용 지연 안이면 window 결과를 update하고, side output으로 보내거나 계약 밖이면 drop metric을 남긴다. 이미 sink에 게시한 결과를 수정할 수 있는지도 확인한다. append-only sink에는 version이나 retract 표현이 필요하다. 물리적으로 늦은 사건이 불가능하다는 증명은 아니다.

### 문제 9. shard snapshot100 뒤 log101~130을 옮겼다. 몇 개이며 cutover 조건은?

**풀이:** 양 끝 포함 130-101+1=30개다. target이 130까지 연속 적용하고 source가 새 승인 중단 뒤 마지막 boundary를 확인해야 한다. 그 다음 epoch를 올려 owner를 바꾼다. old source는 data copy가 남아도 새 epoch write를 거부한다. snapshot만 복사하면 이동 중 30개를 잃는다.

### 문제 10. Spark task가 결제 뒤 crash해 retry됐다. Spark가 exactly-once를 보장하는가?

**풀이:** lineage는 partition 계산을 다시 만들지만 외부 결제 성공을 기억하지 않는다. 같은 task가 두 번째 결제를 보낼 수 있다. 외부 API에 안정된 idempotency key를 전달하고 결과를 조회한다. 순수 data file output은 commit protocol이 한 attempt만 선택하게 한다. Spark checkpoint와 외부 effect once는 다른 경계다.

### 문제 11. Iceberg writer A와 B가 M10을 읽고 M11·M12를 만들었다. 둘 다 현재가 되는가?

**풀이:** catalog의 M10 기대 CAS는 먼저 한 writer만 성공한다. A가 M11을 게시하면 B의 M10→M12는 실패한다. B는 M11을 읽고 충돌을 검사해 새 metadata로 재계획한다. B data file은 존재해도 현재 snapshot이 참조하지 않으면 독자에게 보이지 않는다. file upload와 table commit을 구분한다.

### 문제 12. etcd follower가 rev29일 때 leader는 rev30이다. 최신 설정 판단은?

**풀이:** serializable follower read는 rev29를 반환할 수 있다. 최신 소유권·설정 결정에는 linearizable read나 etcd transaction compare를 쓴다. revision은 30초 같은 wall clock이 아니라 논리 변경 번호다. watch가 compacted revision을 요구하면 현재 snapshot을 다시 읽고 새 revision부터 이어 간다. 오래된 cache로 CAS 없이 writer를 시작하지 않는다.

### 문제 13. history에서 W1은 10~30ms x=2, R1은 40~45ms 결과1이다. 판정은?

**풀이:** W1 응답 뒤 R1 호출이라 실시간 순서가 확정된다. register 초기값1이라도 R1은 완료된 W1의2를 봐야 한다. 결과1은 linearizability 반례다. 평균 latency가 좋아도 정확성 guardrail을 위반한다. 호출·응답 둘 다 있어야 이 선후를 판단한다.

### 문제 14. retry model의 assert가 통과하면 재시작에도 안전한가?

**풀이:** 예제 results는 process memory dict다. restart하면 ID 기록을 잃어 다시 차감할 수 있다. balance 변경과 dedup 결과를 같은 durable transaction에 저장하고 복구해야 한다. 같은 ID의 payload hash도 검사한다. toy assert는 순차 메모리 실행의 분기만 확인한다.

### 문제 15. 후보 시스템 throughput이 20% 높지만 node도 5대에서7대로 늘고 한 run에 checker 위반1건이 있었다. 채택하는가?

**풀이:** 자원 증가와 algorithm 효과가 섞여 공정하지 않다. 같은 node와 같은 durability·consistency로 재실험하고 동일 비용 비교도 둔다. checker 위반은 사전 정확성 조건이 0이면 즉시 기각 사유다. 성공 run만 골라 평균내지 않는다. seed와 최소 history를 보존해 원인을 고친 뒤 전체 계획을 다시 수행한다.



## 용어를 관계로 기억하기

node는 process나 machine이라는 실행 주체이고, replica는 그 주체가 보관한 논리 상태 사본이다. log entry는 command와 term·index를 묶으며 quorum 복제가 commit 근거를 만든다. lastApplied는 commit된 command 중 state machine에 실제 반영한 끝을 나타낸다.

wall clock은 달력 시각이라 조정될 수 있고 monotonic clock은 timeout 경과 측정에 쓴다. logical clock과 happens-before는 사건 인과 순서를 설명한다. 서로 다른 목적의 시계를 바꾸어 쓰지 않는다.

transaction은 업무 경계, atomicity는 전부 또는 전무, isolation은 동시 실행 관측 규칙이다. 2PC는 여러 participant의 원자 결정을 맞추지만 isolation을 자동 제공하지 않는다. idempotency는 반복 결과의 성질이고 dedup row는 이를 구현하는 영속 객체다.

shard는 key 공간 일부, shard map은 key와 owner의 대응, epoch는 구성 세대다. migration은 snapshot과 tail을 옮기고 cutover에서 epoch를 바꾼다. 이전 owner의 copy 수명과 쓰기 권한 수명은 다르다.

## 문제를 푸는 공통 절차

첫째 실제 객체와 관리자를 쓴다. 둘째 입력 message 순서와 durable write를 표로 만든다. 셋째 client 응답, 내부 commit, apply와 외부 effect를 분리한다. 넷째 정확한 장애 지점을 넣는다. 다섯째 복구 뒤 허용 결과와 금지 결과를 계산한다. 마지막으로 모델·실험이 생략한 범위를 적는다.

## 보장 경계 점검

- 복제본 수와 합의된 순서는 다른 개념이다.
- commit과 apply, client ack는 다른 사건이다.
- timeout은 원격 실패 증거가 아니다.
- lease는 기간제 권리이고 fencing은 실제 저장소 거부다.
- checkpoint는 내부 복구점이고 sink 게시와 자동 동일하지 않다.
- Spark retry, Iceberg CAS와 etcd revision은 서로 다른 객체를 관리한다.
- 가상 숫자는 교육 계산이며 실제 성능 관측값이 아니다.


[← 이전](14-experiments-and-research-methods.md) · [목차](README.md)
