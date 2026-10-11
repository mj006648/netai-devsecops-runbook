# 13. 로컬 교육 모델

[이 책 목차](README.md) · [이전: Spark, Iceberg와 최적화](12-spark-iceberg-and-optimization.md) · [다음: 실험과 연구 설계](14-experiments-and-research.md)

이 장의 세 Python 파일은 데이터베이스 서버를 흉내 내는 축소 제품이 아니다. 한 번에 너무 많은 현실 조건을 보면 핵심 규칙을 놓치기 때문에, MVCC 가시성, 조인 작업량, WAL 재적용이라는 세 질문만 작은 메모리 객체와 정수 계산으로 분리한 교육 도구다. 입력, 중간 상태, 출력, assert가 무엇을 주장하는지와 무엇을 주장하지 않는지를 한 줄씩 연결한다.

세 파일은 Python 표준 라이브러리의 dataclass와 정수 계산만 사용한다. 네트워크, 데이터베이스 연결, 파일 쓰기, 임의 난수를 사용하지 않는다. 따라서 같은 코드와 Python의 지원되는 타입 문법에서 논리 출력은 결정적이다. 다만 이 장에서는 실행 시간을 측정하지 않는다. 작은 Python 객체의 시간으로 PostgreSQL이나 Spark 성능을 말할 수 없기 때문이다.

## 1. 모델이라는 말의 뜻

**모델(model)** 은 현실에서 답하려는 질문에 필요한 대상과 규칙만 남긴 표현이다. 지도에 건물 벽의 모든 원자가 없듯이, MVCC 모델에 실제 tuple header의 모든 bit가 없어도 “두 snapshot이 왜 다른 값을 보는가”는 설명할 수 있다. 대신 생략한 조건을 분명히 적어야 모델의 결론을 현실 전체의 보장으로 잘못 확대하지 않는다.

**입력(input)** 은 계산 전에 주어지는 값이다. **중간 상태(state)** 는 규칙을 적용하는 동안 만들어지는 값이다. **출력(output)** 은 호출자가 관찰하는 결과다. **불변식(invariant)** 은 허용된 상태 전이 뒤에도 항상 참이어야 한다고 모델이 정한 조건이다. Python의 **assert** 문은 조건이 거짓이면 즉시 실패시켜 고정 입력에서 불변식을 확인한다. assert 통과는 해당 코드와 입력의 조건이 참이라는 뜻이며, 실제 DBMS 구현이나 성능을 증명하지 않는다.

| 파일 | 질문 | 입력 | 출력 |
|---|---|---|---|
| examples/mvcc_model.py | snapshot마다 어떤 version이 보이는가 | Version 목록, Snapshot | visible boolean과 값 목록 |
| examples/join_cost_model.py | 두 조인 방식의 작업량 크기가 어떻게 다른가 | 행 수, 행 폭, 메모리 | 비교 수, hash 작업, byte, batch |
| examples/wal_recovery_model.py | 어떤 WAL record를 페이지에 적용하는가 | Page, WalRecord, committed 집합 | 새 Page |

## 2. MVCC 모델의 객체부터 읽는다

**트랜잭션 식별자(XID)** 는 이 모델에서 정수로 표현한 작업의 이름이다. 숫자가 크다는 사실만으로 더 늦게 커밋했다고 판단하지 않는다. 30번이 20번 뒤에 시작했어도 20번보다 먼저 끝날 수 있다. 현실 시스템은 commit 상태와 snapshot 경계를 별도 자료로 판정한다.

**Version** 은 논리 행의 특정 버전을 나타내는 불변 Python 객체다. value는 사용자가 읽을 값, creator는 이 버전을 만든 XID, ended는 이 버전을 끝내거나 새 버전으로 대체한 XID다. ended=None이면 이 단순 모델에서 끝낸 트랜잭션이 기록되지 않았다는 뜻이다. 이 객체는 실제 PostgreSQL heap tuple이 아니다. 물리 페이지 위치, xmin/xmax 상태 비트, command ID, subtransaction, wraparound, HOT chain을 생략한다.

**Snapshot** 은 한 읽기가 어느 트랜잭션 결과를 인정할지를 나타낸다. committed는 그 snapshot이 커밋 완료로 인정하는 XID의 불변 집합이고, self_xid는 현재 읽는 자기 트랜잭션이다. frozenset을 쓴 까닭은 계산 중 집합이 우연히 바뀌지 않게 하는 것이다. 현실 PostgreSQL snapshot은 xmin, xmax, 진행 중 XID 배열 등 다른 표현을 쓰며 이 집합과 일대일 구조가 아니다.

~~~python
@dataclass(frozen=True)
class Snapshot:
    committed: frozenset[int]
    self_xid: int

@dataclass(frozen=True)
class Version:
    value: int
    creator: int
    ended: int | None = None
~~~

frozen=True는 인스턴스를 만든 뒤 field를 대입해 바꾸지 못하게 한다. 모델은 상태 전이를 기존 객체 수정이 아니라 새 객체 생성으로 드러내므로 시간표를 읽기 쉽다.

## 3. visible 함수의 두 질문

visible(version, snapshot)은 먼저 “이 버전이 생성된 사실을 독자가 인정하는가?”를 묻는다. creator가 자기 self_xid이거나 committed 집합에 있으면 인정한다. 둘 다 아니면 아직 진행 중일 수도 있고 abort되었을 수도 있으므로 이 모델은 숨긴다.

~~~python
creator_visible = (
    version.creator == snapshot.self_xid
    or version.creator in snapshot.committed
)
if not creator_visible:
    return False
~~~

다음에는 “독자가 인정하는 트랜잭션이 이 버전을 이미 끝냈는가?”를 묻는다. ended가 없으면 보인다. ended가 자기 XID이거나 committed 집합에 있으면 끝난 사실도 보이므로 옛 버전은 숨긴다. ended XID가 snapshot의 committed에 없으면 이 독자에게는 종료가 확정되지 않았으므로 옛 버전을 계속 보인다.

~~~python
if version.ended is None:
    return True
ended_visible = (
    version.ended == snapshot.self_xid
    or version.ended in snapshot.committed
)
return not ended_visible
~~~

“진행 중 집합에 없으니 commit” 같은 추론은 없다. commit과 abort는 모두 진행 중이 아니지만 결과는 반대다. 이 모델은 명시적으로 committed에 있는 XID만 다른 트랜잭션의 성공으로 인정한다.

## 4. MVCC 전체 시간표

초기 버전 old는 value=100, creator=10, ended=30이다. 새 버전 new는 value=80, creator=30, ended=None이다.

| 시각 | 사건 | old | new |
|---|---|---|---|
| t0 | T10이 100을 만들고 commit | creator 10, 끝나지 않음 | 없음 |
| t1 | T20 snapshot 생성 | T20은 committed={10} 기억 | 없음 |
| t2 | T30이 80으로 갱신 | ended=30 | creator=30 |
| t3 | T30 commit | 전역으로는 종료 | 전역으로는 생성 성공 |
| t4 | T20의 옛 snapshot 재사용 | committed에는 여전히 10만 있음 | creator 30 미인정 |
| t5 | T40 새 snapshot | committed={10,30} | creator 30 인정 |

old_snapshot은 committed={10}, self_xid=20이다. new를 검사하면 creator 30이 자기 XID도 committed도 아니므로 False다. old를 검사하면 creator 10은 인정한다. ended 30은 이 snapshot에서 committed가 아니므로 종료를 인정하지 않고 True다. 결과 값 목록은 [100]이다.

new_snapshot은 committed={10,30}, self_xid=40이다. new의 creator 30을 인정하고 ended가 없으므로 True다. old의 creator 10도 인정하지만 ended 30도 인정하므로 False다. 결과는 [80]이다.

~~~text
old snapshot: [100]
new snapshot: [80]
~~~

출력 순서는 코드가 old, new tuple을 순서대로 순회한 결과다. “최신 XID부터 자동 탐색”하는 일반 저장 엔진을 구현한 것은 아니다. 버전 목록을 호출자가 올바른 논리 행의 버전들로 제공한다.

## 5. abort와 자기 쓰기 반례

aborted=Version(value=999, creator=50)을 new_snapshot에서 검사한다. XID 50은 committed={10,30}에 없고 self 40도 아니다. 따라서 보이지 않는다. T50이 현재 진행 중인지 이미 abort했는지 모델은 구별하지 않지만, 두 경우 모두 이 snapshot의 결과에는 포함하지 않는다는 제한된 질문에는 충분하다.

self_version=Version(value=70, creator=40)은 self_xid=40인 new_snapshot에는 보인다. 자기 트랜잭션이 방금 쓴 값을 다음 문장에서 읽는 상황을 표현한다. committed 집합이 같은 other_snapshot의 self_xid=41에는 보이지 않는다. 즉 “committed에 40이 없으니 누구에게도 안 보인다”가 아니라 자기 쓰기 예외를 먼저 검사한다.

이 규칙도 현실의 모든 자기 가시성을 표현하지 않는다. 같은 트랜잭션 안에서도 SQL command 순서와 삭제·갱신 조합은 command ID가 필요할 수 있고 이 모델에는 없다.

## 6. MVCC assert가 고정하는 계약

다음 assert들은 여섯 가지 고정 명제를 검사한다.

1. old snapshot은 old를 본다.
2. old snapshot은 new를 보지 않는다.
3. new snapshot은 old를 보지 않는다.
4. new snapshot은 new를 본다.
5. 두 snapshot의 값 목록은 각각 [100], [80]이다.
6. abort 가능 XID 50은 숨고, 자기 XID 40의 미커밋 버전은 자기에게만 보인다.

assert 하나가 실패하면 Python은 AssertionError를 내고 이후 print에 도달하지 않는다. 이는 회귀를 빠르게 발견하는 장치다. 프로덕션 코드의 데이터 무결성 검사를 assert에 맡겨야 한다는 뜻은 아니다. Python 실행 옵션에 따라 assert가 제거될 수 있으므로 사용자 입력 검증이나 보안 경계에는 명시적 예외 처리가 필요하다.

## 7. 조인 비용 모델의 객체

**JoinEstimate** 는 실행 계획이 아니라 네 정수를 보관하는 불변 계산 입력이다.

- outer_rows: 중첩 반복에서 바깥쪽을 순회할 행 수다.
- inner_rows: 각 outer 행과 비교할 안쪽 행 수이며, 이 모델에서는 hash build 행 수도 된다.
- build_row_bytes: hash table에 넣을 행 하나의 단순 추정 byte다.
- memory_bytes: hash 상태에 허용된 단순 메모리 한도다.

현실 hash table은 key, payload, pointer, bucket의 overhead와 allocator 정렬을 가진다. build_row_bytes=64는 이 교육 계산을 위한 가정이다. memory_bytes=2,000,000도 운영체제 메모리나 DBMS work memory의 완전한 모형이 아니다.

## 8. 네 파생 변수의 단위

nested_loop_comparisons는 outer_rows × inner_rows다. 외부 10,000행과 내부 100,000행이면 1,000,000,000번 키 비교다. 이는 인덱스 없는 단순 이중 반복의 상한 모형이다. page cache, 조기 종료, vectorization, 인덱스 lookup이 없다.

hash_key_operations는 outer_rows + inner_rows다. build 100,000개를 hash table에 넣고 probe 10,000개를 조회하는 개념적 키 작업 110,000번이다. hash 충돌 처리와 결과 행 생성 비용은 포함하지 않는다.

hash_bytes는 inner_rows × build_row_bytes이므로 100,000×64=6,400,000B다. hash_batches는 ceil(hash_bytes / memory_bytes)다. 6,400,000/2,000,000=3.2이므로 올림하여 4다. **batch** 는 여기서 메모리에 한 번에 담을 수 없어 partition하여 처리할 것으로 추정한 묶음 수다. 앞 장의 vector batch와 다른 문맥이다.

~~~text
nested-loop comparisons: 1000000000
hash key operations: 110000
estimated hash batches: 4
~~~

이 출력은 hash가 4회 디스크 I/O를 한다는 정확한 예측이 아니다. 1보다 크므로 단일 메모리 hash table 가정을 만족하지 못하고 spill 가능성을 고려해야 한다는 경고다.

## 9. 조인 모델의 두 가지 숫자 체계

기존 교재에는 page 중심의 또 다른 교육식도 있다. customers=(100행,10page), orders=(10,000행,500page)일 때 page nested loop cost를 10 + 100×500 = 50,010 상대 단위로 둔다. hash는 page 510과 CPU 0.01×10,100=101을 더해 611이다. 이 수치는 현재 join_cost_model.py의 10,000/100,000 행 입력과 다른 예제다.

둘을 섞으면 안 된다. Python 파일은 키 연산 수와 hash memory batch를 계산한다. page 식은 페이지 접근을 설명하는 별도 손 계산이다. 어느 쪽도 ms가 아니며 PostgreSQL cost 공식을 복제하지 않는다. 단위가 다른 50,010과 1,000,000,000을 직접 비율로 비교할 수 없다.

인덱스가 inner key에 있고 outer가 몇 행만 내면 indexed nested loop가 유리할 수 있다. hash build가 메모리를 넘으면 임시 partition I/O가 생긴다. sort-merge는 정렬된 입력이나 범위 조건에서 후보가 될 수 있다. 모델의 결론은 “이 고정 입력의 단순 연산 수가 크게 다르다”까지다.

## 10. 조인 assert와 조건 변경

assert는 10,000×100,000=10억, 합=110,000, hash byte=6,400,000, batch=4를 고정한다. 마지막 assert는 10억>110,000을 확인한다.

memory_bytes만 8,000,000으로 바꾸면 ceil(6,400,000/8,000,000)=1이다. 행 수와 hash byte는 같지만 메모리 조건 때문에 batch 경고가 사라진다. build_row_bytes를 128로 늘리면 hash byte는 12,800,000이고 2,000,000 한도에서 ceil(6.4)=7 batch다. 한 변수씩 바꾸면 결과 원인을 설명할 수 있다.

반면 outer_rows와 inner_rows와 memory를 동시에 바꾸고 “새 optimizer가 좋아졌다”고 말하면 어느 변화가 원인인지 분리할 수 없다. 모델 실험도 독립 변수와 통제 변수를 기록해야 한다.

## 11. WAL 모델의 실제 객체

**Page** 는 value와 page_lsn 두 정수를 가진 불변 객체다. value는 페이지 전체 바이트가 아니라 한 논리 값을 대신한다. page_lsn은 이 페이지에 반영된 마지막 WAL 위치를 나타낸다. **WalRecord** 는 txid, lsn, value를 가진다. 현실 WAL record의 resource manager, block reference, full-page image, checksum과 record header는 없다.

초기 disk_page는 Page(value=50,page_lsn=10)이다. wal tuple에는 T1의 WalRecord(txid=1,lsn=11,value=60)과 T2의 (2,12,70)이 있다. committed 집합은 {1}이므로 모델은 T1만 성공으로 인정한다.

recover는 입력 Page를 result로 가리킨 뒤 WAL을 lsn 오름차순으로 정렬한다. 각 record에 대해 txid가 committed에 있고 record.lsn이 result.page_lsn보다 클 때 새 Page를 만든다.

~~~python
for record in sorted(records, key=lambda item: item.lsn):
    if record.txid in committed and record.lsn > result.page_lsn:
        result = replace(result, value=record.value, page_lsn=record.lsn)
~~~

LSN 11의 T1은 committed이고 11>10이므로 result=(60,11)이 된다. LSN 12의 T2는 committed에 없으므로 건너뛴다. recovered는 Page(60,11)이다. 원본 disk_page는 frozen 객체이므로 Page(50,10)으로 남는다.

## 12. 반복 적용과 idempotence

**idempotence, 멱등성** 은 같은 동작을 한 번 더 적용해도 결과가 더 바뀌지 않는 성질이다. recovered=(60,11)에 같은 WAL과 committed={1}을 다시 적용하면 T1의 11>11이 거짓이라 건너뛰고 T2는 여전히 미커밋이라 건너뛴다. 결과는 그대로 (60,11)이다.

이 성질은 recovery가 중간에 다시 죽어 재시작할 수 있는 이유를 이해하는 데 유용하다. 그러나 실제 PostgreSQL의 모든 redo 함수가 단순히 pageLSN 비교 한 줄만 쓴다는 뜻은 아니다. record 종류별 조건과 page 상태 검증이 있다.

더 중요한 한계는 committed 필터다. 이 Python 모델은 최종 논리 값을 쉽게 설명하려고 committed record만 적용한다. 실제 PostgreSQL crash recovery는 미커밋 트랜잭션의 물리 변경 WAL도 redo할 수 있고, 복구 뒤 행이 질의에 보이는지는 MVCC 트랜잭션 상태가 결정한다. 따라서 이 코드로 실제 redo 구현을 설명하거나 검증해서는 안 된다.

## 13. 세 모델을 하나의 요청과 연결한다

사용자가 잔액 100을 80으로 바꾸고 다른 테이블과 join해 조회한다고 하자. update 중에는 새 version이 생기며 MVCC 모델은 snapshot별 보이는 값을 설명한다. optimizer는 join 후보의 행 수와 메모리를 추정하며 조인 모델은 두 알고리즘의 단순 작업량 차이를 보여 준다. commit 뒤 데이터 페이지가 아직 값 50인 장애 모형에서는 WAL 모델이 pageLSN을 비교해 값 60을 재구성한다.

세 모델의 상태를 하나로 합치지는 않는다. MVCC의 committed 집합은 snapshot의 논리 가시성 입력이고, WAL 모델의 committed 집합은 교육용 record 필터다. join의 batch는 spill 추정이고 columnar vector batch가 아니다. 같은 단어가 보여도 객체와 수명을 먼저 확인한다.

## 14. 실행과 검증의 경계

예제 README가 정한 Python 버전에서 세 파일을 직접 실행하면 고정 assert와 print를 확인할 수 있다. 이 초안 작성 과정에서는 shell 실행을 하지 않았으며, 고정 커밋 74b47cd의 소스와 assert 값을 대조해 문서화했다. 실제 실행 검증 보고가 필요하면 저장소 통합 단계에서 지원 Python으로 세 파일을 실행해야 한다.

출력 문구가 맞는지만 보면 부족하다. assert가 실행됐는지, exit status가 0인지, 수정한 입력이 어떤지 기록한다. 성능 측정을 덧붙이지 않는다. time 명령으로 이 작은 스크립트를 재도 실제 DBMS I/O와 query planning을 포함하지 않는다.

## 15. 완전 풀이 문제

### 문제 1. old snapshot의 결과

old=(100,creator10,ended30), new=(80,creator30), snapshot committed={10}, self=20이다.

**풀이:** new의 creator30은 인정되지 않아 숨는다. old의 creator10은 인정되고 ended30은 이 snapshot에서 commit으로 인정되지 않으므로 old는 계속 보인다. 결과는 [100]이다.

### 문제 2. abort된 creator

Version(999,creator50)을 committed={10,30}, self=40에서 읽는다.

**풀이:** 50은 자기 XID도 committed도 아니므로 creator_visible=False다. 진행 중인지 abort인지 더 구분하지 않고 숨긴다. “active가 아니면 commit”으로 바꾸면 abort 버전을 잘못 보인다.

### 문제 3. 자기 쓰기

Version(70,creator40)을 self=40과 self=41이 각각 읽는다. 둘 다 committed={10,30}이다.

**풀이:** self40은 자기 creator이므로 본다. self41은 creator40이 committed에 없으므로 보지 못한다. commit 전 자기 쓰기 가시성을 표현한 것이다.

### 문제 4. hash byte와 batch

inner_rows=100,000, build_row_bytes=64, memory=2,000,000이다.

**풀이:** hash_bytes=6,400,000B, batches=ceil(3.2)=4다. 정확히 네 번의 물리 I/O라는 뜻이 아니라 단일 메모리 build가 한도를 넘는 교육 경고다.

### 문제 5. 메모리만 변경

같은 hash 상태에서 memory를 8,000,000B로 바꾼다.

**풀이:** ceil(6,400,000/8,000,000)=1이다. key 작업 110,000은 변하지 않는다. 메모리 조건과 키 연산 수는 별도 변수다.

### 문제 6. WAL 적용

Page(50,10), records=(T1,11,60),(T2,12,70), committed={1}이다.

**풀이:** T1은 commit되고 11>10이라 Page(60,11)을 만든다. T2는 LSN이 더 커도 committed 집합에 없으므로 이 모델에서는 제외한다. 출력은 Page(60,11)이다.

### 문제 7. 같은 recovery 재실행

Recovered Page(60,11)에 같은 WAL을 적용한다.

**풀이:** T1의 11>11이 거짓이고 T2는 미커밋이므로 변화가 없다. assert recover(recovered,...)==recovered가 멱등성을 확인한다.

### 문제 8. 모델 결과의 현실 주장

Python hash batches가 4라고 출력됐다. PostgreSQL이 네 번 spill한다고 보고할 수 있는가?

**풀이:** 보고할 수 없다. row overhead, memory accounting, partition algorithm, skew와 제품 구현을 생략했다. “고정 가정에서 6.4MB가 2MB 한도의 3.2배라 ceil 결과가 4”라고만 주장하고 실제 엔진은 EXPLAIN ANALYZE와 spill 지표로 측정한다.

## 16. 모델을 확장할 때 지킬 기준

새 field를 넣기 전에 어떤 질문에 필요한지 적는다. MVCC에 abort 상태를 추가한다면 committed와 aborted를 구별하는 반례와 assert를 먼저 만든다. 조인 모델에 spill I/O를 추가한다면 byte를 page나 ms로 바꾸는 가정을 명시한다. WAL 모델에 여러 page를 넣는다면 record의 page_id와 page별 pageLSN을 분리한다.

현실 기능을 하나 추가할 때 기존 단순 결론이 어느 범위에서만 유지되는지 문서도 함께 바꾼다. 복잡성을 늘리는 것 자체가 더 좋은 모델은 아니다. 입력에서 출력까지 사람이 손으로 계산하고 assert 실패 원인을 설명할 수 있어야 이 장의 목적에 맞는다.

## 근거와 연결 자료

- [PostgreSQL 18: MVCC Introduction](https://www.postgresql.org/docs/18/mvcc-intro.html)
- [PostgreSQL 18: Write-Ahead Logging](https://www.postgresql.org/docs/18/wal-intro.html)
- [CMU 15-445/645 Database Systems](https://15445.courses.cs.cmu.edu/)
