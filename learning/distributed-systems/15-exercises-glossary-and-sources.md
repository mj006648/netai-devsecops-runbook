# 15. 종합 문제, 용어, 출처

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

[← 이전](14-experiments-and-research-methods.md) · [목차](README.md)
