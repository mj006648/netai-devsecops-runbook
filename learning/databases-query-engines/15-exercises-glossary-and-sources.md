# 15. 종합 문제, 연결 개념과 출처

[이전: 실험과 연구](14-experiments-and-research.md) · [목차](README.md) · 다음 장 없음

이 장은 용어를 한 줄씩 외우는 사전이 아니다. 사용자가 SQL을 보내면 어떤 객체가 언제 생기고, 메모리와 저장장치 어디에 놓이며, 누가 바꾸고, 장애 뒤 무엇이 남는지를 한 흐름으로 다시 연결한다. 같은 “page”, “snapshot”, “partition”도 문맥마다 실제 대상과 수명이 다르므로 이름만 외우지 않고 이웃 개념과 함께 읽는다.

## 1. SQL 문장에서 논리 결과까지

**데이터베이스 관리 시스템(DBMS)** 은 오래 보관할 데이터의 구조, 동시 읽기와 쓰기, 장애 복구를 관리하는 서버 소프트웨어다. 사용자는 보통 **SQL** 로 원하는 결과를 선언한다. 선언형이라는 말은 “어떤 결과가 필요한지”를 쓰고 페이지를 어느 순서로 읽을지는 optimizer와 executor에 맡긴다는 뜻이다.

**relation** 은 같은 속성 구조를 가진 tuple의 집합이라는 논리 모델이고, SQL **table** 은 사용자가 이름을 붙여 관리하는 논리 객체다. **row** 는 주문 한 건처럼 열 값들의 논리 묶음이다. 저장장치의 한 위치에 놓인 **record** 또는 MVCC **tuple version** 과 같은 말이 아니다. 한 논리 행을 갱신하면 옛 버전과 새 버전 두 record가 잠시 함께 존재할 수 있다.

**schema** 는 열 이름과 type, NULL 허용, primary key와 foreign key 같은 constraint를 정한다. primary key는 논리 행을 유일하게 식별하고, foreign key는 다른 table의 유효한 key를 참조하게 한다. constraint는 애플리케이션 설명문이 아니라 DBMS가 write 때 검사하는 허용 상태 규칙이다.

NULL은 0이나 빈 문자열이 아니라 값이 알려지지 않았거나 적용되지 않음을 나타낸다. 비교 결과가 TRUE, FALSE, UNKNOWN인 3값 논리를 쓰며 WHERE는 TRUE만 통과시킨다. COUNT(*)는 행을 세고 COUNT(column)은 NULL이 아닌 표현식 결과를 세므로 서로 다르다.

## 2. 논리 행이 페이지에 놓이는 과정

저장 엔진은 파일 전체를 매번 옮기지 않고 고정 크기 **page** 단위로 주로 읽고 쓴다. PostgreSQL의 보통 page는 8KiB다. page header는 페이지 종류와 free-space 경계 같은 관리 정보를 담고, slot array의 항목은 record 위치를 가리킨다. record가 페이지 안에서 이동해도 slot 번호를 유지할 수 있어 다른 구조의 참조를 안정시키기 쉽다.

table의 heap file은 key 정렬을 보장하지 않는 record 페이지 집합이다. 여기서 heap은 프로세스 동적 메모리 영역과 다른 저장 구조 이름이다. DBMS의 **buffer pool** 은 저장장치 page의 메모리 사본을 두는 영역이고, 한 page가 들어가는 자리가 buffer frame이다. executor가 frame을 사용하는 동안 **pin** 을 잡으면 교체 관리기가 그 frame을 내보내지 않는다. 메모리 사본을 바꾸고 데이터 파일에 아직 쓰지 않은 page는 **dirty page** 다.

page, record, slot, frame은 수명이 다르다. page는 파일의 논리 블록으로 데이터베이스 수명 동안 재사용될 수 있고, record는 insert/update/vacuum에 따라 생기거나 사라진다. frame은 서버 메모리의 일시 자리이며 다른 page로 교체될 수 있다. slot은 특정 page 안의 위치 식별자다.

## 3. 인덱스가 후보 위치를 찾는 과정

**index** 는 검색 key에서 table record 위치 또는 다른 index node로 빠르게 이동하도록 돕는 별도 자료구조다. B+tree 계열 index는 정렬된 key와 child pointer를 page 크기 node에 담는다. 한 내부 node가 가리키는 평균 child 수를 **fan-out** 이라고 한다. fan-out이 크면 많은 key도 낮은 높이로 탐색할 수 있다.

B+tree leaf는 정렬된 key와 row locator를 담고 이웃 leaf 연결로 범위 scan을 돕는다. insert로 leaf가 넘치면 split하여 두 node로 나누고 parent에 separator를 올린다. index도 page이므로 buffer pool, dirty 상태와 WAL 보호가 필요하다. index가 있다고 모든 query가 index scan을 고르는 것은 아니다. 결과 비율이 높으면 무작위 table page 접근보다 sequential scan이 쌀 수 있다.

LSM-tree 계열은 새 write를 메모리의 정렬 구조인 **memtable** 에 모으고 WAL로 내구성을 보호한 뒤, 변경 불가능한 정렬 파일 **SSTable** 로 flush한다. 여러 SSTable의 겹치는 key와 tombstone을 background **compaction** 으로 병합한다. B+tree의 node split과 LSM의 compaction은 모두 index 관리지만 I/O 모양과 읽기·쓰기 증폭이 다르다.

## 4. plan이 접근 방법과 조인을 고른다

parser와 analyzer가 SQL 이름·type을 확정하면 optimizer는 여러 **query plan** 을 비교한다. plan은 sequential scan, index scan, filter, join, aggregate 같은 operator를 연결한 tree다. **cardinality** 는 문맥에 따라 operator가 내는 행 수 또는 열의 distinct 값 수를 뜻하므로 어느 쪽인지 적는다. **selectivity** 는 전체 입력 중 조건을 통과하는 비율이다.

통계에는 행·페이지 수, distinct 수, 자주 등장하는 값, 값 범위를 근사한 histogram이 있다. optimizer의 **cost model** 은 예상 I/O와 CPU를 상대 숫자로 계산한다. cost는 실행 ms가 아니다. estimate가 실제와 크게 다르면 작은 입력을 전제로 고른 nested loop가 많은 반복을 하거나, 큰 hash table이 memory를 넘어 spill할 수 있다.

**nested loop join** 은 outer의 각 행마다 inner에서 일치 항목을 찾는다. inner key index가 있거나 outer가 작으면 좋을 수 있다. **hash join** 은 build side의 동등 key로 hash table을 만들고 probe side의 key로 조회한다. build 상태가 memory 한도를 넘으면 임시 저장장치에 partition을 내려 쓰는 spill이 생긴다. **sort-merge join** 은 두 입력을 key 순으로 정렬해 함께 전진한다. 어느 알고리즘도 모든 조건에서 항상 이기지 않는다.

## 5. 트랜잭션이 여러 문장을 한 상태 전이로 묶는다

**transaction** 은 함께 성공하거나 함께 취소되어야 할 읽기와 쓰기의 논리 단위다. BEGIN에서 시작해 COMMIT으로 성공을 확정하거나 오류·ROLLBACK으로 abort한다. **원자성** 은 일부만 성공 상태로 남지 않게 하고, **일관성** 은 constraint와 업무 불변식을 지키는 유효 상태 전이를 뜻하며, **격리성** 은 동시 실행의 관찰 범위를 제어하고, **내구성** 은 성공 commit이 장애 뒤에도 남는 약속이다.

MVCC는 한 논리 행의 여러 version과 **snapshot** 을 이용해 reader와 writer 충돌을 줄인다. PostgreSQL tuple의 xmin은 그 version을 만든 XID, xmax는 삭제하거나 대체하려 한 XID와 관련된다. snapshot은 XID 숫자 크기만 보는 것이 아니라 어느 transaction이 commit했고 어느 것이 진행 중인지로 **visibility** 를 판정한다.

Read Committed는 PostgreSQL에서 문장마다 새 snapshot을 얻을 수 있어 한 transaction의 두 SELECT가 다른 commit 상태를 볼 수 있다. Repeatable Read는 transaction snapshot을 유지하며 PostgreSQL 구현에서는 phantom도 막지만, 동시 write 충돌에서 serialization failure가 날 수 있다. Serializable은 성공한 결과가 어떤 직렬 실행 순서와 동등하도록 만들며, 불가능한 실행 중 하나를 중단할 수 있다. 실패한 문장만이 아니라 그 문장이 의존한 읽기와 결정까지 포함한 transaction 전체를 재시도한다.

오래된 version은 즉시 지우면 옛 snapshot을 깨뜨린다. vacuum은 더 이상 필요한 snapshot이 없는 horizon을 확인해 dead tuple 공간을 재사용 가능하게 한다. 오래 열린 transaction이나 replication 조건이 horizon을 붙잡으면 정리가 늦어진다.

## 6. WAL이 메모리 변경을 장애 뒤 상태로 잇는다

WAL은 데이터 page의 새 바이트보다 그 변경을 복원할 log record를 먼저 durable storage에 확정하는 방식이다. **LSN** 은 WAL byte stream의 위치이지 시간이나 transaction 수가 아니다. page의 **pageLSN** 은 그 page에 반영한 최신 log 위치를 나타낸다.

commit 때 모든 dirty page를 데이터 파일에 내릴 필요는 없다. 변경 WAL과 commit record가 필요한 경계까지 flush되면 성공 ACK를 보낼 수 있고, 장애 뒤 recovery가 뒤처진 page에 redo한다. checkpoint는 “모든 것을 한순간 복사한 snapshot”이 아니라 dirty page를 점진적으로 쓰고 recovery가 시작할 redo 경계를 앞으로 옮기는 절차다.

redo가 page byte를 재구성했다고 곧 reader에게 행이 보이는 것은 아니다. MVCC가 transaction commit 상태와 snapshot으로 visibility를 판정한다. 앞 장의 로컬 WAL 모델이 committed record만 적용한 것은 교육 단순화이며 실제 PostgreSQL의 물리 redo 알고리즘 전체가 아니다.

## 7. 복제가 다른 서버의 상태로 잇는다

primary는 write와 WAL 생성을 담당하고 standby/replica는 WAL을 받아 재생한다. sent LSN은 주 서버가 네트워크로 보낸 끝, write LSN은 replica 파일 시스템에 쓴 끝, flush LSN은 replica durable storage에 확정한 끝, replay LSN은 data page에 적용한 끝이다. 한 replica가 flush 960,replay 900이면 950 record는 장애 뒤 살릴 수 있어도 지금 replica query에는 아직 안 보일 수 있다.

비동기 복제는 replica 완료를 기다리지 않아 latency가 낮지만 primary 전체 손실 때 ACK한 최근 transaction을 잃을 수 있다. 동기 복제도 remote_write, remote flush, remote_apply 중 어느 경계를 기다리는지 명시해야 한다. failover 때 옛 primary를 fencing하지 않으면 두 writer가 생기는 split brain이 발생할 수 있다.

2PC는 서로 독립적인 여러 database의 한 업무를 prepare와 commit/abort 두 단계로 맞춘다. prepared participant는 최종 결정을 기다리며 lock과 상태를 유지할 수 있다. coordinator의 durable decision이 없거나 통신이 끊기면 in-doubt 상태가 길어지는 blocking 문제가 있다. replication이 사본을 유지하는 문제와 분산 transaction이 여러 원본의 원자성을 맞추는 문제는 다르다.

## 8. 분석 읽기는 열과 batch로 바뀐다

행 지향 저장은 한 행의 여러 열을 가까이 두고 point lookup과 update에 적합하다. **columnar storage** 는 같은 열 값을 가까이 두어 분석 query가 필요한 열만 읽고 압축하기 쉽게 한다. Parquet file은 row group 안에 column chunk를 두고 footer metadata로 위치와 통계를 찾게 한다.

executor는 열 값을 메모리 array의 **vector batch** 로 만들고 여러 값을 한 loop에서 계산할 수 있다. validity bitmap은 NULL 여부를 위치당 한 bit로 표현하고, selection vector는 filter를 통과한 위치 목록을 담는다. dictionary encoding은 반복 문자열을 사전과 정수 ID로 바꾸고, min/max 통계는 조건과 겹치지 않는 row group을 건너뛴다.

predicate pushdown은 filter를 data source 가까이 내려 불필요한 byte를 줄인다. 통계 pruning은 후보를 제거할 뿐 남은 행의 조건 검사를 대신하지 않는다. memory를 넘는 aggregate나 join은 columnar여도 spill할 수 있다.

## 9. Spark와 Iceberg에서 객체 수명이 다시 갈린다

Spark driver는 logical/physical plan과 stage를 조정하고 executor는 task를 실행한다. **Spark partition** 은 한 task의 일시 입력 조각이다. shuffle은 key에 따라 중간 record를 worker 사이로 재분배하며 network, serialization, 임시 file 비용을 만든다.

Iceberg는 current metadata JSON, snapshot, manifest list, manifest, data/delete file의 pointer graph로 table version을 관리한다. **Iceberg partition** 은 days(ts), bucket(id) 같은 지속 metadata transform 결과다. Spark partition과 다른 객체다. Iceberg **snapshot** 은 특정 file 집합을 고정하고, MVCC snapshot은 transaction visibility를 고정한다. 둘 다 일관된 읽기를 돕지만 판단 대상과 관리자, 수명이 다르다.

writer task가 data file upload에 성공해도 table commit은 끝나지 않았다. driver가 manifest와 새 snapshot metadata를 만들고 catalog current pointer를 조건부 교체해야 새 reader에게 보인다. 실패해 metadata에서 참조되지 않는 file은 orphan 후보지만 진행 중 write와 과거 snapshot을 고려해 안전하게 정리한다.

row-level delete는 data file을 즉시 rewrite하지 않고 position delete나 equality delete로 나타낼 수 있다. reader는 snapshot이 가리키는 delete를 data에 적용한 뒤 live row를 Spark에 넘긴다. file record count와 reader output row count는 다를 수 있다.

## 10. 한 요청의 전체 수명

사용자가 “KR 모바일 주문의 고객 등급별 합계” SQL을 보낸다고 하자.

1. SQL text는 session에 들어와 parser/analyzer가 table, column, type에 연결한다.
2. optimizer는 통계로 filter cardinality를 추정하고 scan·join·aggregate plan을 고른다.
3. row store라면 buffer manager가 heap/index page를 frame에 읽고 pin한다. lake table이라면 connector가 Iceberg snapshot과 manifest를 읽어 Parquet 후보를 고른다.
4. executor는 MVCC snapshot에서 visible row/version만 전달하거나 delete file을 적용해 live rows를 만든다.
5. filter는 3값 논리로 TRUE만 선택하고 join은 key가 맞는 row를 결합한다.
6. aggregate는 group state를 memory에 만들고 부족하면 spill한다. Spark에서는 shuffle로 같은 key를 모은다.
7. SELECT 결과는 client에 직렬화된다. write라면 새 tuple/page와 WAL 또는 새 data/metadata file이 생긴다.
8. PostgreSQL commit ACK는 WAL durable 경계와 연결되고, Iceberg commit은 catalog pointer publication과 연결된다.
9. replica 또는 후속 Spark query가 새 상태를 보는 시점은 각각 replay LSN 또는 current snapshot 선택에 달렸다.
10. 오래된 tuple/version/snapshot/file은 reader가 더 요구하지 않을 때 vacuum이나 maintenance가 정리한다.

## 11. 종합 문제와 완전 풀이

### 문제 1. NULL과 집계

score 값이 [10,NULL,20,NULL]이다. COUNT(*), COUNT(score), SUM(score)를 구하라.

**풀이:** COUNT(*)는 입력 row 네 개를 세어 4다. COUNT(score)는 NULL이 아닌 표현식 결과 10과20만 세어 2다. SUM도 NULL을 제외해 30이다. NULL을 0으로 바꾼 계산이 아니므로 AVG(score)는 30/2=15다.

### 문제 2. 페이지 수용량

page 8,192B, header 192B, 고정 record 200B, slot 2B/행이다.

**풀이:** record 영역에 쓸 수 있는 공간은 8,192-192=8,000B다. 행 하나는 record와 slot 합계 202B다. floor(8,000/202)=39행이다. 40행은 8,080B로 넘친다. 실제 엔진의 alignment, variable field, fill factor는 결과를 바꿀 수 있다.

### 문제 3. dirty page와 commit

T1이 page 42를 바꿨고 메모리 page는 dirty지만 data file은 옛 값이다. 성공 commit이 가능한가?

**풀이:** 필요한 change와 commit WAL이 durable storage까지 flush되면 모든 data page를 그 순간 쓰지 않고 성공할 수 있다. 장애 뒤 redo가 page를 복원한다. WAL이 확정되기 전에 새 data page를 먼저 내리면 write-ahead 순서를 깨뜨린다.

### 문제 4. B+tree 높이

leaf 하나가 key 100개, 평균 fan-out 100이고 총 key가 1억 개다.

**풀이:** leaf는 100,000,000/100=1,000,000개다. fan-out 100이면 root에서 세 child-pointer edge로 최대 100^3=1,000,000 leaf 범위를 가리킬 수 있다. 실제 높이는 node 점유율, key 폭, root와 cache 상태에 따라 달라진다.

### 문제 5. index가 있어도 sequential scan

1,000,000행 중 800,000행을 반환한다.

**풀이:** index로 800,000 locator를 찾고 table page를 흩어 읽는 비용이 대부분 page를 순서대로 읽는 비용보다 클 수 있다. projection, clustering, covering index와 cache에 따라 달라지므로 “index 존재=사용”이 아니다. EXPLAIN의 선택과 실제 buffer를 확인한다.

### 문제 6. 조인 작업량

outer 10,000행, inner 100,000행이고 inner index가 없는 단순 모형이다.

**풀이:** nested loop 비교는 10,000×100,000=1,000,000,000번이다. hash는 build와 probe key 작업 약 110,000번이다. 그러나 build row 64B면 6.4MB이며 memory 2MB에서는 로컬 모델상 4 batch라 spill 가능성이 있다. 작업 수만으로 ms를 단정하지 않는다.

### 문제 7. 추정 오차

planner는 filter 뒤 200행, executor는 8,000행을 관찰했다.

**풀이:** 8,000/200=40배 과소 추정이다. 오차가 처음 생긴 filter의 distinct, MCV, histogram, 통계 갱신 시점과 다중 열 상관을 조사한다. 이 오차가 다음 join의 build/outer 선택을 바꾸었는지도 본다.

### 문제 8. 송금 원자성

A=100,B=50에서 A에서30을 빼는 write만 남고 B 증가가 없다.

**풀이:** 합계가 150에서120으로 줄어 업무 불변식을 깨뜨린다. 두 write를 한 transaction으로 묶어 전부 commit 또는 abort하게 하는 원자성 문제다. CHECK나 업무 constraint로 합계를 직접 표현할 수 있는지는 schema 범위에 따라 별도 설계한다.

### 문제 9. MVCC 두 번 읽기

T20이 100을 읽은 뒤 T30이 80으로 update/commit하고 T20이 다시 읽는다.

**풀이:** PostgreSQL Read Committed는 두 번째 statement에서 새 snapshot을 얻어 80을 볼 수 있다. Repeatable Read는 transaction snapshot을 유지해 100을 본다. T30 commit이 두 번째 SELECT 전이라는 시간 조건이 필요하다.

### 문제 10. serialization failure 재시도

한 Serializable transaction의 마지막 UPDATE가 실패했다.

**풀이:** UPDATE만 재전송하면 앞에서 읽은 값과 그로 내린 결정이 이미 낡았다. transaction 전체를 BEGIN부터 다시 실행한다. 재시도 상한과 backoff를 두고 email·결제 같은 외부 부작용은 요청 ID로 중복을 막는다.

### 문제 11. WAL 로컬 모형

Page(50,10), committed T1의 record(11,60), 미커밋 T2 record(12,70)다.

**풀이:** 교육 모델은 T1이 committed이고 11>10이므로 Page(60,11)을 만든다. T2는 제외한다. 같은 입력을 다시 적용하면 11>11이 거짓이라 그대로다. 실제 PostgreSQL은 미커밋 WAL도 물리 redo할 수 있고 가시성은 MVCC가 판정한다.

### 문제 12. checkpoint와 보존

crash recovery redo 경계는800인데 replication slot이620부터 요구한다.

**풀이:** recovery만 보면 오래된 WAL을 지울 수 있어도 replica가 620 이후를 아직 요구한다. 보존 경계는 더 오래된 620이다. max_wal_size를 절대 상한으로 믿지 말고 slot lag와 archive 상태를 본다.

### 문제 13. 복제 단계

primary=1000, replica sent=980,write=970,flush=960,replay=900이고 commit은950이다.

**풀이:** replica는 950 WAL을 durable하게 보유하지만 data page에는 아직 적용하지 않았다. 현재 replica query는 그 commit을 못 볼 수 있다. replica 재시작이나 promotion recovery는 보유 WAL을 960까지 재생할 수 있다. flush와 reader visibility를 구분한다.

### 문제 14. failover 손실

비동기 primary는1000까지 ACK했고 후보 replica flush는960이다.

**풀이:** primary storage를 완전히 잃으면 961~1000 사이 commit이 사라질 수 있다. LSN 차이40이 40건이라는 뜻은 아니다. 해당 구간의 commit record와 업무 요청 ID로 손실을 판정하고 옛 primary를 fencing한 뒤 승격한다.

### 문제 15. column batch

값 [20,NULL,80,100,40]에 x>=80을 적용한다.

**풀이:** 비교 결과는 [FALSE,UNKNOWN,TRUE,TRUE,FALSE]다. WHERE는 위치2,3을 선택하고 합은180이다. validity bitmap이 NULL 위치를 표시하며 selection vector [2,3]은 batch 안의 위치이지 값 자체가 아니다.

### 문제 16. row-group pruning

A amount 0~90, B 80~150, C 200~500이고 조건 amount>100이다.

**풀이:** A는 max90<=100이라 확실히 건너뛴다. B는 일부 가능해 읽어야 한다. C의 비NULL 값은 범위상 모두 조건을 만족하지만 NULL과 통계 계약을 확인한다. B 통계만으로 통과 행 수를 알 수 없다.

### 문제 17. Spark와 Iceberg

snapshot의 1,000파일 중 partition summary로800개, file 통계로150개를 더 제외하고 100 task를 만든다.

**풀이:** 후보는50파일, 제거율은95%다. 한 큰 file을 여러 split으로 나눌 수 있어 50파일과100 task는 모순이 아니다. file 집합은 Iceberg snapshot의 지속 metadata이고 task partition은 이번 Spark 실행의 일시 객체다.

### 문제 18. Iceberg commit 실패

80 data file upload 뒤 catalog compare-and-swap이 실패했다.

**풀이:** current snapshot이 참조하지 않으므로 정상 reader에게 행은 보이지 않는다. 충돌 없는 append라면 최신 metadata에 rebase해 파일을 재사용할 수 있다. 끝내 참조되지 않으면 orphan 후보지만 진행 중 writer와 retention 기간을 고려해 정리한다.

### 문제 19. position delete와 equality delete

(A.parquet,4) position delete와 customer_id=7 equality delete가 있다.

**풀이:** position delete는 A의 물리 위치4만 지운다. 다른 파일 위치4에는 적용하지 않는다. equality delete는 같은 field ID 값 7인 적용 대상 data file 행을 지우지만 partition과 sequence 조건을 충족해야 한다. 같은 값이라는 이유만으로 모든 snapshot의 모든 file을 지우지 않는다.

### 문제 20. 연구 결과

새 optimizer planning=5ms,execution=500ms이고 기존은20ms,300ms다.

**풀이:** planning만 보면 새 방식이15ms 짧다. 단순 end-to-end 합은 새505ms, 기존320ms다. 결과 checksum, cache, 반복 분포와 지원 실패를 확인한 뒤 이 조건에서는 기존 실행이 더 빠르다고 관찰할 수 있다. planning 우위를 전체 성능 우위로 확대하지 않는다.

## 12. 같은 이름을 구분하는 연결표

| 이름 | 문맥과 실제 대상 | 수명 |
|---|---|---|
| page | DB 파일·buffer pool의 고정 블록 | 파일에서 오래 존재, frame 사본은 교체 |
| Parquet data page | column chunk 안의 encoding 단위 | data file 수명 |
| snapshot | MVCC visibility 경계 | statement 또는 transaction |
| Iceberg snapshot | manifest/file 집합을 가리키는 commit | 만료 전까지 metadata에 존재 |
| partition | Spark task 입력 조각 | 한 execution |
| Iceberg partition | transform으로 조직한 data 범위 | spec/file metadata 수명 |
| batch | vector operator의 메모리 값 묶음 | operator가 소비할 때까지 |
| hash batch | spill partition 수의 실행 단위 | join 실행 동안 |
| commit | DB transaction 성공 결정 | transaction 상태로 지속 |
| Iceberg commit | catalog current metadata pointer 교체 | 새 snapshot이 current인 기간 |

## 13. 장애를 읽는 공통 순서

첫째, 신원을 적는다. transaction XID, query ID, page ID, LSN, snapshot ID, Spark application/stage/task attempt를 구별한다. 둘째, 생성과 공개를 나눈다. tuple/data file이 생긴 것과 commit되어 reader에게 보이는 것은 다르다. 셋째, durable과 applied를 나눈다. replica flush와 replay, WAL과 data page가 다르다.

넷째, estimate와 actual을 나눈다. optimizer cost, manifest candidate bytes, actual decoded bytes, 결과 rows는 다른 단계다. 다섯째, retry 범위를 확인한다. serialization failure는 transaction 전체, Spark task failure는 attempt, Iceberg CAS conflict는 operation 의미에 따라 재검증한다. 여섯째, 외부 부작용과 orphan을 찾는다.

## 14. 출처를 읽는 기준

공식 specification은 파일 형식과 protocol의 계약을 확인하는 1차 자료다. 제품 공식 문서는 특정 version의 지원 동작과 설정을 확인한다. 강의 자료와 논문은 원리와 연구 질문을 배우는 데 유용하지만 현재 제품 version의 보장을 대신하지 않는다. blog와 benchmark를 읽을 때 데이터 분포, hardware, cache, concurrency, correctness와 실패 workload를 찾는다.

이 책의 손 계산과 로컬 model 숫자는 개념을 분리하기 위한 교육 값이다. PostgreSQL, Spark, Iceberg에서 실제 측정했다는 주장이 아니다. 실행 계획과 내부 형식은 version에 따라 바뀔 수 있으므로 운영 판단은 사용 중인 version의 공식 문서와 재현 실험으로 확인한다.

## 15. 주요 1차 자료

- [PostgreSQL 18 Documentation](https://www.postgresql.org/docs/18/)
- [PostgreSQL 18: Transaction Isolation](https://www.postgresql.org/docs/18/transaction-iso.html)
- [PostgreSQL 18: MVCC](https://www.postgresql.org/docs/18/mvcc.html)
- [PostgreSQL 18: EXPLAIN](https://www.postgresql.org/docs/18/sql-explain.html)
- [PostgreSQL 18: WAL](https://www.postgresql.org/docs/18/wal-intro.html)
- [PostgreSQL 18: Streaming Replication](https://www.postgresql.org/docs/18/warm-standby.html)
- [Apache Parquet File Format](https://parquet.apache.org/docs/file-format/)
- [Apache Arrow Columnar Format](https://arrow.apache.org/docs/format/Columnar.html)
- [Apache Spark SQL Performance Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
- [Apache Iceberg Specification](https://iceberg.apache.org/spec/)
- [Apache Iceberg Spark Writes](https://iceberg.apache.org/docs/latest/spark-writes/)
- [CMU 15-445/645 Database Systems](https://15445.courses.cs.cmu.edu/)

읽기를 마쳤다면 새 용어 하나를 정의로만 답하지 말고 “어떤 실제 객체인가, 어디에 있는가, 누가 만들고 바꾸는가, 언제 사라지는가, 어떤 이웃 객체와 상태를 주고받는가”의 다섯 문장으로 설명해 본다. 그 설명이 가능해야 숫자와 장애 trace도 스스로 연결할 수 있다.
