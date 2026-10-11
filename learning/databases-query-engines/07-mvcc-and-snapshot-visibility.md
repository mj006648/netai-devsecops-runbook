# 07. MVCC와 snapshot visibility

[이 책 목차](README.md) · [이전: Transaction과 ACID](06-transactions-and-acid.md) · [다음: Isolation과 concurrency](08-isolation-and-concurrency.md)

한 transaction이 account A를 읽는 동안 다른 transaction이 A를 갱신해도 첫 reader가 갑자기 다른 시점의 값을 보지 않게 하려면 어떻게 해야 할까. PostgreSQL은 기존 row byte를 항상 제자리에서 덮어쓰는 대신 여러 물리 tuple version과 snapshot을 사용한다. 각 reader는 자기 snapshot 규칙으로 같은 논리 row의 어느 version이 visible한지 고른다.

이 방식이 MVCC다. 이 장의 XID와 snapshot 경계는 가시성 원리를 손으로 계산하기 위한 교육 모형이다. PostgreSQL 18의 실제 tuple header에는 command ID, 상태 bit, subtransaction, wraparound 처리 등 더 많은 규칙이 있으며 숫자 크기만 비교하는 모형이 아니다.

![07. MVCC와 snapshot visibility 흐름](assets/mvcc-visibility.svg)

## 1. logical row, tuple, version은 같은 대상이 아니다

**logical row(논리 행)**는 SQL 사용자가 account id='A'처럼 하나의 업무 객체로 보는 row다. UPDATE 전후에도 “A 계좌”라고 부른다.

**tuple(튜플)**은 heap page 안에 저장된 한 물리 row record다. PostgreSQL heap은 table row를 page에 저장하는 영역이다. tuple에는 column data와 transaction visibility를 판단할 header가 있다. buffer manager가 page를 메모리에 올리면 backend가 header와 값을 읽는다.

**row version(행 버전)**은 logical row가 특정 transaction 상태에서 가진 값을 표현하는 tuple이다. UPDATE는 흔히 old tuple을 그대로 덮지 않고 new tuple을 만든다. 그래서 A/v1 balance=100과 A/v2 balance=80이 한동안 동시에 heap에 있을 수 있다.

version의 수명은 creator가 tuple을 만든 때부터, 어떤 snapshot도 필요로 하지 않아 vacuum이 공간을 재사용할 수 있게 할 때까지다. logical row 수명과 다르다. SQL 결과에는 A 한 row만 보이더라도 storage에는 old·new version 여러 개가 존재할 수 있다.

## 2. transaction ID, xmin, xmax의 실제 의미

**transaction ID(XID, 트랜잭션 식별자)**는 transaction을 식별하고 version 상태를 판단하는 데 사용하는 번호다. PostgreSQL XID는 유한한 공간에서 순환하며 특수 ID와 freeze 규칙이 있으므로 일반 정수를 영원히 증가하는 timestamp처럼 비교하면 안 된다.

tuple header의 **xmin**은 그 tuple version을 만든 transaction의 XID다. 여기서 xmin은 snapshot의 xmin 경계와 이름이 같지만 대상이 다르다. “tuple xmin”과 “snapshot xmin”을 문맥으로 구분한다.

tuple header의 **xmax**는 그 version을 삭제하거나 대체하려 한 transaction 정보를 담는 필드다. 값이 없거나 유효한 삭제가 아니면 version이 아직 종료되지 않았을 수 있다. xmax가 있다고 곧바로 invisible은 아니다. 그 XID가 진행 중이거나 abort했다면 삭제가 현재 snapshot에 효력을 갖지 않을 수 있다.

다음 물리 상태를 사용한다.

| logical row | tuple version | balance | tuple xmin | tuple xmax |
|---|---|---:|---:|---:|
| account A | A/v1 | 100 | 10 | 없음 |
| account B | B/v1 | 50 | 11 | 없음 |

XID 10과 11은 이미 commit되었다고 가정한다. A/v1을 XID30이 update하면 A/v1.xmax=30이 되고 새 A/v2는 xmin=30, balance=80이 된다.

## 3. commit status가 필요한 이유

XID 숫자와 tuple header만으로 commit 여부를 알 수 없다. **commit-status 저장소**는 XID가 in progress, committed, aborted 중 어떤 상태인지 판단할 정보를 제공한다. backend는 tuple hint bit와 transaction status 자료를 사용해 반복 확인 비용을 줄일 수 있다.

세 경우를 비교한다.

- XID30이 진행 중: A/v1의 xmax=30은 아직 current snapshot에 확정된 삭제가 아닐 수 있고 A/v2 creator도 미완료다.
- XID30이 commit: 새 snapshot은 A/v1을 끝난 version, A/v2를 visible creator version으로 볼 수 있다.
- XID30이 abort: A/v1 종료는 효력이 없고 A/v2 creator가 abort했으므로 v2는 visible하지 않다.

따라서 “xmax가 nonzero면 dead”, “xmin이 작으면 visible” 같은 규칙은 틀린다.

## 4. snapshot은 table 복사본이 아니다

**snapshot(스냅샷)**은 어느 transaction 결과를 visible한 것으로 인정할지 판단하는 backend memory의 metadata다. database file 전체를 복사한 사진이 아니다.

교육 모형의 snapshot은 다음을 가진다.

- **snapshot xmin**: 오래된 active transaction과 cleanup horizon 계산에 쓰이는 아래 경계
- **snapshot xmax**: 이 경계 이상의 XID는 snapshot 관점에서 아직 미래로 본다
- **in-progress set**: 경계 사이지만 snapshot 시점에 아직 진행 중이던 XID 집합
- 현재 transaction 자신과 command 순서 정보

실제 PostgreSQL 구조와 이름은 이 원리를 더 세밀하게 구현한다. visibility 코드는 tuple creator·deleter status, snapshot 범위, self transaction과 command ID를 함께 본다.

snapshot은 isolation level에 따라 statement마다 새로 얻거나 transaction 동안 유지한다. Read Committed는 각 command 시작 snapshot을 사용한다. Repeatable Read는 첫 non-transaction-control statement 시점의 transaction snapshot을 이후 command가 계속 사용한다.

## 5. visibility를 creator와 deleter 두 단계로 판정하기

단순화한 visible 판정은 두 질문이다.

1. 이 version을 만든 transaction이 내 snapshot에서 효력이 있는가?
2. 이 version을 끝낸 delete/update transaction이 내 snapshot에서 효력이 있는가?

creator가 abort했거나 snapshot 당시 진행 중이거나 미래면 일반 reader에게 version은 보이지 않는다. creator가 visible한 committed transaction이면 다음으로 xmax를 본다.

유효한 xmax가 없거나 deleter가 abort했다면 version은 살아 있다. deleter가 snapshot 당시 진행 중 또는 미래라면 그 snapshot에서는 삭제 전 version이 보일 수 있다. deleter가 snapshot 전에 commit했다면 old version은 보이지 않는다.

자기 transaction이 만든 version은 별도 self 규칙과 command order가 필요하다. 같은 transaction의 뒤 statement는 앞 statement가 INSERT한 row를 볼 수 있어야 하지만, 같은 command의 내부 처리와 rollback된 subtransaction은 다르게 판단할 수 있다.

## 6. T1·T2·T3 전체 시간표

초기 상태는 A/v1=(balance100,xmin10,xmax 없음)이고 XID10은 committed다.

- **T1**: Repeatable Read reader. old snapshot S1을 유지한다.
- **T2**: updater. XID30을 할당받아 A를 100에서 80으로 바꾼다.
- **T3**: T2 commit 뒤 시작하는 새 reader. snapshot S2를 얻는다.

교육 snapshot은 다음과 같다.

- S1: xmax=30, in_progress={} — XID30 이상은 미래
- S2: xmax=41, in_progress={} — XID30 committed를 볼 수 있음

| 시각 | T1 | T2(XID30) | T3 | heap 상태 |
|---:|---|---|---|---|
| t0 | BEGIN RR | - | - | A/v1 100, xmin10 |
| t1 | S1 획득, SELECT→100 | - | - | v1만 존재 |
| t2 | S1 유지 | BEGIN | - | XID30 진행 |
| t3 | S1 유지 | UPDATE 100→80 | - | v1.xmax30, v2.xmin30 |
| t4 | SELECT 요청 가능 | COMMIT | - | XID30 committed |
| t5 | S1로 SELECT→100 | 완료 | BEGIN, S2 | v1과 v2 모두 물리 존재 |
| t6 | 계속 100 | - | S2로 SELECT→80 | reader마다 다른 visible version |
| t7 | COMMIT | - | COMMIT | old snapshot 해제 가능 |

T1 S1에서 v1 creator XID10은 visible하다. v1 deleter XID30은 snapshot xmax 이상인 미래라 종료 효력이 없으므로 v1이 보인다. v2 creator XID30은 미래이므로 보이지 않는다.

T3 S2에서 XID30은 경계 안의 committed transaction이다. v1의 delete/update가 효력을 가져 v1은 보이지 않고, v2 creator가 visible하므로 balance 80을 반환한다.

두 reader가 같은 heap page의 다른 tuple을 선택한다. table 전체 복사본이 두 개 생긴 것이 아니다.

~~~mermaid
sequenceDiagram
 participant T1 as Backend T1 RR
 participant P42 as Heap page 42
 participant T2 as Backend T2 XID30
 participant T3 as Backend T3
 T1->>P42: S1로 A/v1 조회
 P42-->>T1: balance=100
 T2->>P42: v1.xmax=30, v2.xmin=30
 T2->>T2: XID30 COMMIT
 T1->>P42: S1로 다시 조회
 P42-->>T1: A/v1=100
 T3->>P42: S2로 조회
 P42-->>T3: A/v2=80
~~~

## 7. Read Committed의 두 SELECT

T1 대신 Read Committed transaction R을 사용한다고 하자.

| 시점 | R | T2 | 결과 |
|---:|---|---|---|
| r1 | 첫 SELECT snapshot SR1 | 아직 시작 전 | 100 |
| r2 | 대기 | UPDATE·COMMIT 80 | - |
| r3 | 둘째 SELECT snapshot SR2 | committed | 80 |

각 SELECT가 시작할 때 새 snapshot을 얻기 때문에 한 transaction 안에서도 100 다음 80을 볼 수 있다. 이것이 nonrepeatable read에 해당할 수 있다. 한 SELECT가 실행 중인 동안에는 그 command snapshot이 안정된 view를 제공한다.

R이 첫 SELECT 뒤 자기 UPDATE로 값을 바꾸면 다음 SELECT는 다른 transaction에 아직 commit되지 않은 자기 변경도 볼 수 있다. “snapshot은 committed transaction만 본다”는 문장에 self-visibility 조건을 붙여야 한다.

## 8. in-progress set이 숫자 대소보다 강한 반례

snapshot Sx가 xmax=40, in_progress={25,30}이라고 하자. tuple V의 xmin=25다. 25는 40보다 작지만 snapshot을 얻을 때 진행 중이었으므로 V는 Sx에 보이지 않는다. XID25가 나중에 commit해도 Sx가 transaction snapshot이라면 계속 보이지 않을 수 있다.

tuple W의 xmin=20 committed, xmax=30이라고 하자. deleter 30이 Sx 당시 진행 중이므로 W는 Sx에 보일 수 있다. 30이 나중에 commit해도 Sx는 deletion 전 version을 유지한다.

반대로 XID22가 abort했다면 xmin22 version은 번호가 작아도 보이지 않는다. visibility는 경계, 진행 집합, commit·abort status를 모두 요구한다.

## 9. index가 있어도 heap visibility가 필요한 이유

B-tree leaf entry는 key와 table tuple 위치를 가리킨다. UPDATE로 new version이 생길 때 index key가 바뀌지 않아 old index entry가 여러 version chain의 시작을 가리킬 수 있고, 새 index tuple이 생길 수도 있다.

index scan은 candidate를 찾은 뒤 heap tuple header를 snapshot으로 검사한다. old version이 현재 snapshot에 dead이고 new version이 visible한지 확인해야 한다. “index entry를 찾았으니 row가 존재한다”는 결론은 빠르다.

**index-only scan**은 필요한 column을 index에서 얻어 heap 접근을 줄이는 계획이다. PostgreSQL은 heap page의 모든 tuple이 모든 transaction에 visible하다고 알려 주는 visibility map 같은 추가 조건을 사용한다. map bit가 없으면 visibility 확인을 위해 heap을 방문할 수 있다.

**HOT(Heap-Only Tuple) update**는 indexed column이 바뀌지 않고 page 조건을 만족할 때 new version을 같은 heap page에 두고 index entry 추가를 피할 수 있는 PostgreSQL 최적화다. old byte를 제자리 overwrite하는 것이 아니다. version chain과 visibility 검사는 계속 필요하다.

## 10. horizon은 무엇을 안전하게 지울 수 있는가

old version을 언제 제거할 수 있는지는 현재 commit 여부만으로 정하지 않는다. active snapshot 중 하나라도 그 version을 볼 수 있으면 보존해야 한다.

**cleanup horizon(정리 경계)**은 어떤 XID 이전의 dead version을 더 이상 active snapshot이 필요로 하지 않는지 판단하는 경계 개념이다. 시스템은 active transaction과 replication slot, prepared transaction 같은 보존 요인을 고려할 수 있다.

T1이 S1을 오래 유지하면 T2 commit 뒤에도 A/v1을 볼 수 있어 vacuum이 v1을 제거할 수 없다. T1이 끝나고 다른 old snapshot도 없다면 v1은 새 snapshot에 필요 없는 dead tuple 후보가 된다.

horizon은 한 table의 단순 minimum XID만 보는 교육 숫자보다 복잡하다. transaction ID wraparound와 freeze를 위해서도 오래된 tuple metadata를 관리해야 한다.

## 11. vacuum의 주체와 결과

**VACUUM**은 dead tuple이 차지한 공간을 table 내부에서 재사용 가능하게 하고, visibility map과 통계를 유지하며, transaction ID wraparound 위험을 관리하는 PostgreSQL 작업이다. 사용자가 명시적으로 실행할 수도 있고 autovacuum worker가 background에서 수행할 수 있다.

일반 VACUUM은 보통 table file을 운영체제에 즉시 완전히 줄이지 않는다. page 안 공간을 future INSERT·UPDATE가 재사용하게 한다. VACUUM FULL처럼 table을 다시 쓰는 별도 작업은 lock과 추가 공간 등 비용이 다르다.

vacuum 순서는 단순화하면 다음과 같다.

1. cleanup horizon을 계산한다.
2. heap page의 tuple version 상태를 검사한다.
3. 어떤 snapshot도 필요로 하지 않는 dead tuple을 식별한다.
4. 관련 index entry를 안전하게 정리한다.
5. heap 공간을 재사용 가능하게 표시한다.
6. page가 all-visible 조건을 만족하면 visibility map을 갱신할 수 있다.

vacuum은 active snapshot에 visible한 old version을 지우면 안 된다. long-running transaction은 직접 write하지 않아도 horizon을 붙잡아 table과 index bloat를 늘릴 수 있다.

## 12. dead, recently dead, aborted를 구분한다

“old tuple”이 모두 즉시 dead는 아니다.

- **live**: 현재 또는 future snapshot이 볼 수 있는 version
- **recently dead**: delete/update가 commit했지만 아직 old snapshot이 필요로 할 수 있음
- **dead**: 어떤 필요한 snapshot에도 visible하지 않아 정리 가능
- **aborted creator version**: creator가 abort해 정상 snapshot에 visible하지 않으며 안전 조건 뒤 정리 가능

정확한 PostgreSQL 내부 분류와 이름에는 더 많은 상태가 있다. 중요한 원리는 reader 보호 경계가 끝나기 전 storage를 재사용하지 않는 것이다.

삭제도 DELETE가 old tuple byte를 즉시 0으로 지우는 것으로 이해하지 않는다. xmax와 transaction status로 invisible해지고 vacuum이 나중에 공간을 정리한다.

## 13. long transaction과 bloat의 전체 경로

T1이 오전 10시에 RR snapshot S1을 얻고 6시간 동안 열린다고 하자. 그 사이 T2 계열 transaction이 같은 table row들을 반복 update한다.

1. 각 UPDATE가 new tuple version을 만든다.
2. old versions는 새 snapshot에는 필요 없더라도 S1이 볼 가능성이 있다.
3. vacuum은 S1 horizon을 넘어 필요한 version을 제거하지 못한다.
4. heap page free space가 줄어 새 page가 늘 수 있다.
5. index에도 version churn entry가 쌓일 수 있다.
6. buffer와 storage I/O가 증가하고 scan이 더 많은 tuple을 검사할 수 있다.
7. T1 종료 후 vacuum이 안전한 old version을 정리할 수 있다.
8. 공간은 table 내부 재사용 가능해져도 file 크기가 즉시 OS에 반환되지 않을 수 있다.

**bloat(팽창)**은 live logical data에 비해 table과 index가 불필요하게 많은 공간과 scan 비용을 갖는 현상이다. long transaction 하나가 유일한 원인은 아니며 update 패턴, fillfactor, vacuum 속도, replica horizon을 함께 본다.

## 14. XID wraparound와 freeze

XID는 유한한 번호 공간에서 순환한다. 매우 오래된 XID를 단순 숫자 비교하면 새 transaction으로 오해할 위험이 있다. PostgreSQL은 transaction age를 관리하고 tuple의 creator가 충분히 오래된 committed transaction임을 안전하게 표시하는 **freeze(동결)** 작업을 수행한다.

autovacuum은 공간 회수뿐 아니라 wraparound 방지 때문에도 필요하다. table에 update가 거의 없어 dead tuple이 적더라도 anti-wraparound vacuum이 필요할 수 있다.

운영에서 transaction age 경고를 무시하거나 autovacuum을 장기간 막으면 database가 wraparound 손상을 피하기 위해 쓰기를 제한하는 심각한 상황이 생길 수 있다. “vacuum은 삭제 공간을 줄이는 선택적 정리”만으로 이해하면 안 된다.

## 15. MVCC가 lock을 없애지는 않는다

reader와 writer가 일반 SELECT와 UPDATE에서 서로 불필요하게 block하지 않도록 version을 나누는 것이 MVCC의 큰 장점이다. 하지만 writer 두 개가 같은 row를 갱신하면 충돌을 조정해야 한다. schema 변경과 table operation에는 table-level lock이 있을 수 있다.

SELECT FOR UPDATE는 읽은 row를 이후 update할 의도로 lock한다. unique constraint 검사와 foreign key도 concurrency coordination을 사용한다. MVCC는 모든 lock이 사라지는 기술이 아니라 read visibility와 write conflict를 서로 다른 도구로 처리하는 방식이다.

## 16. 관측 시 범위와 단위

MVCC 문제를 진단할 때 다음을 함께 본다.

- long-running transaction과 snapshot 시작 시각
- active, idle in transaction 상태
- table의 live/dead tuple 추정
- autovacuum 마지막 실행과 진행
- transaction age와 freeze 관련 지표
- replication slot 또는 standby가 붙잡는 horizon
- table·index size 증가와 update 비율
- query가 실제로 읽은 heap page와 rows removed

통계의 dead tuple 수는 추정일 수 있다. vacuum이 실행되었다는 사실만으로 모든 dead version이 사라졌다고 단정하지 않는다. active horizon, lock, 비용 제한 때문에 일부만 처리될 수 있다.

## 17. 완전 풀이 문제

### 문제 1. old snapshot

T1 S1의 xmax=30이고 T2 XID30이 v2를 만들고 commit했다. T1은 v1과 v2 중 무엇을 보는가?

**풀이:** S1에서 XID30은 경계 이상의 미래 transaction이다. v2 creator가 visible하지 않고 v1의 xmax30 deletion도 효력을 갖지 않으므로 v1을 본다. T2가 나중에 commit해도 T1이 transaction snapshot을 유지하면 결과가 바뀌지 않는다.

### 문제 2. new snapshot

T3 S2의 xmax=41이고 XID30은 committed, in-progress 집합에 없다. 무엇을 보는가?

**풀이:** v1은 committed XID30에 의해 대체되어 S2에 invisible하고, v2 creator XID30은 visible하다. T3는 v2 balance 80을 본다.

### 문제 3. abort updater

XID30이 v1.xmax=30과 v2.xmin=30을 쓴 뒤 abort했다. 새 reader 결과는?

**풀이:** aborted xmax는 v1을 유효하게 종료하지 못한다. aborted creator가 만든 v2는 visible하지 않다. 새 reader는 v1 balance 100을 본다. 물리 v2는 cleanup 전까지 남을 수 있다.

### 문제 4. 경계보다 작은 XID

snapshot xmax=40이고 in_progress={25}다. tuple xmin25는 40보다 작으니 visible한가?

**풀이:** 아니다. snapshot을 얻을 때 XID25가 진행 중이었으므로 이 snapshot에는 creator가 완료된 것으로 보이지 않는다. 숫자 대소만으로 판단하지 않는다.

### 문제 5. RC와 RR

첫 SELECT 뒤 concurrent update가 commit했다. 둘째 SELECT에서 Read Committed와 Repeatable Read 결과는?

**풀이:** RC는 둘째 command 시작에 새 snapshot을 얻어 new version을 볼 수 있다. PostgreSQL RR은 transaction snapshot을 유지해 old version을 계속 본다. 자기 transaction 변경은 별도 self 규칙으로 보일 수 있다.

### 문제 6. index visibility

B-tree에서 key A entry를 찾았으면 현재 snapshot에 A row가 반드시 존재하는가?

**풀이:** 아니다. entry가 old/invisible tuple을 가리킬 수 있고 MVCC visibility를 heap에서 확인해야 할 수 있다. index-only scan도 visibility map 등 지원 조건이 필요하다.

### 문제 7. long reader

읽기만 하는 RR transaction이 6시간 열려 있으면 write가 없어도 storage에 영향을 줄 수 있는가?

**풀이:** 가능하다. old snapshot이 cleanup horizon을 붙잡아 그 뒤 update로 생긴 old version을 vacuum이 정리하지 못할 수 있다. heap·index bloat와 scan 비용이 늘 수 있다.

### 문제 8. vacuum 후 file 크기

VACUUM이 dead tuple을 정리했는데 table file 크기가 그대로다. 실패인가?

**풀이:** 일반 VACUUM은 page 안 공간을 future tuple이 재사용하게 하는 것이 주 목적이며 OS에 file을 즉시 줄이지 않을 수 있다. dead tuple 추정, reusable space, query 성능과 VACUUM 종류를 함께 본다.

## 공식 자료

- [PostgreSQL MVCC introduction](https://www.postgresql.org/docs/current/mvcc-intro.html)
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [PostgreSQL database page layout](https://www.postgresql.org/docs/current/storage-page-layout.html)
- [PostgreSQL routine vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html)
- [PostgreSQL index-only scans](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)
