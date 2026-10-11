# 03. B-tree와 LSM index

[이 책 목차](README.md) · [이전: Page, record와 buffer pool](02-pages-records-and-buffer-pools.md) · [다음: Scan, filter와 join](04-scans-filters-and-joins.md)

테이블에서 주문 번호 42017을 찾는 가장 단순한 방법은 첫 page부터 모든 record를 읽어 비교하는 것이다. 데이터가 커질수록 읽은 page 수가 늘어난다. **index(인덱스)**는 검색에 사용할 값과 record 위치를 별도 구조로 조직해 후보를 빨리 찾게 하는 저장 객체다. 책의 목차처럼 원본 내용을 전부 복사하지 않고 위치를 좁힐 정보를 둔다.

이 장의 page 수와 비용은 구조를 손으로 추적하기 위한 교육 모형이다. PostgreSQL B-tree와 LSM 기반 저장 엔진은 제품별 동시성·복구·파일 형식 규칙이 더 있으며, 여기의 숫자를 특정 제품 보장으로 해석하지 않는다.

## 1. page, record, key, pointer의 실제 대상

**page(페이지)**는 데이터베이스가 저장 장치와 buffer pool 사이에서 읽고 쓰며 내부적으로 관리하는 고정 크기 블록이다. 한 page에는 header, 여러 entry와 빈 공간 관리 정보가 들어간다. 디스크나 SSD에는 데이터베이스 파일의 일부로 오래 존재하고, 접근할 때는 buffer pool의 메모리 frame에 복사된다.

**record(레코드)**는 한 행 또는 인덱스 entry를 물리적으로 표현한 바이트 묶음이다. 테이블 record에는 열 값과 가시성 정보가, 인덱스 record에는 검색 key와 row 위치가 들어갈 수 있다. SQL의 논리적 row와 물리 record는 일대일로 영원히 고정되지 않는다. 갱신으로 여러 version이 생기거나 record 위치가 바뀔 수 있다.

**key(키)**는 index가 정렬하거나 hash할 때 비교하는 값이다. 여기서는 주문 번호 같은 검색 열 값이다. primary key라는 논리 제약과 index key라는 물리 정렬 값은 관련 있지만 같은 용어가 아니다. 하나의 index는 여러 열을 합친 복합 key를 가질 수 있고 중복 key도 허용할 수 있다.

**pointer(포인터 또는 참조)**는 다른 page나 table record 위치를 식별하는 값이다. 메모리 주소만을 뜻하지 않는다. B-tree 내부 entry의 child page 번호, leaf entry의 heap page 번호와 slot 번호가 예다. 이 참조는 index가 존재하는 동안 저장되며 page split이나 record 정리 때 갱신될 수 있다.

**index access method(인덱스 접근 방법)**는 key 비교, 탐색, 삽입과 삭제를 수행하는 데이터베이스 구성 요소다. 실행기는 query predicate에서 검색 key를 만들고 접근 방법에 요청한다. buffer manager는 필요한 page를 메모리에 가져오고, 접근 방법은 page 안 entry를 비교한다.

## 2. B-tree와 B+tree 구조

**tree(트리)**는 한 root에서 child로 내려가는 계층 구조다. **B-tree**는 page 하나에 많은 key와 child pointer를 담는 균형 검색 트리 계열이다. 이름의 B는 binary를 뜻하지 않는다. 모든 탐색 경로의 높이가 비슷하게 유지되고, 한 page가 많은 child를 가리켜 큰 데이터도 적은 단계로 내려간다.

데이터베이스 설명에서는 실제 row 참조를 leaf에 모으고 내부 page는 경계 key와 child pointer를 저장하는 형태를 **B+tree**라고 구분한다. 많은 제품 문서는 이런 구현도 넓게 B-tree라고 부른다. 이 장의 수치 모형은 내부 page가 경계와 child를, leaf page가 key와 row 참조를 가지며 leaf끼리 key 순서로 연결된 B+tree 형태다.

- **root page**: 탐색이 시작되는 최상위 page다. index 수명 동안 위치를 찾을 metadata가 유지된다.
- **internal page**: key 범위를 나누는 separator key와 아래 level의 child page 참조를 가진다.
- **leaf page**: 정렬된 key와 table row 참조 또는 포함된 값을 가진다.
- **sibling link**: leaf를 key 순서로 이어 범위 탐색이 다음 leaf로 진행하게 한다.
- **fan-out**: internal page 하나가 가리킬 수 있는 child 수다.

fan-out이 큰 이유는 저장 장치 접근 횟수를 줄이기 위해서다. 이진 트리는 한 node가 두 child만 가지지만, 8 KiB page에 작은 key와 pointer를 많이 담으면 수백 child를 가리킬 수 있다. 실제 fan-out은 page 크기, key 길이, header, fill factor에 따라 달라진다.

## 3. 100만 entry의 높이 계산과 한 key 탐색

교육 모형에서 fan-out 200, leaf당 200 entry, 전체 leaf entry 1,000,000개라고 하자.

1. leaf page 수 = ceil(1,000,000 / 200) = 5,000
2. 그 위 internal page 수 = ceil(5,000 / 200) = 25
3. root 한 page가 internal page 25개를 모두 가리킬 수 있다.
4. 경로는 root → internal → leaf의 3 page level이다.

key 42017을 찾는 실제 상태를 추적한다.

| 단계 | 읽는 객체 | 비교와 결과 |
|---:|---|---|
| 1 | root page | separator와 비교해 40000~59999 범위 child 선택 |
| 2 | internal page | 더 작은 범위의 leaf pointer 선택 |
| 3 | leaf page | 정렬 entry에서 42017을 찾음 |
| 4 | leaf entry | (heap page 812, slot 4) 참조 획득 |
| 5 | table page | record version을 읽고 현재 snapshot 가시성 검사 |
| 6 | predicate 재검사 | index 후보가 query 조건을 실제 만족하는지 확인 |

세 index page가 항상 세 장치 I/O라는 뜻은 아니다. page가 buffer pool에 있으면 메모리 hit일 수 있고, 없으면 저장 장치 읽기가 필요하다. leaf에서 row 위치를 얻은 뒤 table page를 추가로 읽을 수 있다.

**covering index(포함 인덱스)**는 query가 필요한 값을 index entry만으로 제공할 수 있는 index다. 그러나 MVCC 가시성 확인 때문에 table 접근이 여전히 필요할 수 있으며 제품 조건에 따라 index-only scan 가능 여부가 달라진다. “index에 열이 있으니 table은 절대 읽지 않는다”는 보장이 아니다.

## 4. leaf split을 byte 수명으로 추적하기

leaf 한 page가 최대 네 entry를 담는 교육 모형이고 현재 [10,20,30,40]으로 가득 찼다고 하자. key 25를 넣는다.

1. 탐색은 25가 이 leaf 범위임을 찾는다.
2. 메모리 안에서 정렬 후보 [10,20,25,30,40]을 만든다.
3. 기존 page 하나에 다 들어가지 않으므로 새 leaf page를 할당한다.
4. entry를 왼쪽 [10,20]과 오른쪽 [25,30,40]으로 나눈다.
5. 왼쪽의 next sibling을 새 오른쪽에 연결하고, 오른쪽의 next를 옛 next로 연결한다.
6. 부모에 separator 25와 새 오른쪽 page pointer를 넣는다.
7. 부모도 가득 차면 internal split이 위로 전파된다.
8. root가 split되면 새 root가 두 child를 가리키며 높이가 1 증가한다.

~~~mermaid
flowchart TD
 R0[기존 루트 겸 잎 10 20 30 40] --> I[키 25 삽입 시도]
 I --> L[왼쪽 잎 10 20]
 I --> H[오른쪽 잎 25 30 40]
 N[새 루트 경계키 25] --> L
 N --> H
~~~

그림에서 기존 root가 leaf 하나였던 작은 tree가 두 leaf와 새 root를 가진 tree로 바뀐다. page split은 단순 배열 나누기가 아니다. 검색 중인 다른 worker가 절반만 연결된 구조를 보지 않도록 latch와 page 상태 규칙이 필요하고, crash 뒤에도 일관된 구조를 복구하도록 WAL 같은 로그와 정해진 기록 순서가 필요하다.

**latch(래치)**는 메모리의 page 자료 구조를 동시에 바꾸는 worker 사이를 조정하는 짧은 내부 잠금이다. 사용자 transaction의 row lock과 목적·수명이 다르다. latch는 구조 변경의 짧은 구간을 보호하지만 transaction commit까지 유지하는 논리 lock은 아니다.

split 뒤 모든 page가 절반만 찬 상태가 계속된다고 가정하면 안 된다. split 정책은 균형과 동시 삽입 패턴을 고려한다. 순차 증가 key는 오른쪽 끝 page에 삽입이 몰릴 수 있고, 무작위 key는 여러 leaf에 분산된다.

## 5. equality와 range 탐색

key = 42017 equality 탐색은 한 leaf 위치를 좁힌다. 중복 key가 있다면 인접 entry를 더 읽어 모든 row 참조를 찾아야 한다.

key BETWEEN 42000 AND 42999 같은 **range scan(범위 탐색)**은 시작 key 42000을 root에서 leaf까지 찾은 뒤, leaf entry를 순서대로 읽고 sibling link를 따라간다. upper bound 42999를 넘으면 멈춘다.

예를 들어 leaf가 다음과 같다고 하자.

- L10: [41980, 41990, 42000, 42010]
- L11: [42020, 42030, 42500, 42999]
- L12: [43000, 43100]

시작 탐색이 L10의 42000에 도달한 뒤 L10의 2개, L11의 4개를 출력하고 L12 첫 key 43000에서 멈춘다. root 탐색을 각 row마다 반복하지 않는다.

하지만 leaf 순서가 좋아도 table record가 물리적으로 흩어져 있으면 row fetch는 random I/O가 될 수 있다. clustering, buffer hit, covering 여부에 따라 범위 scan 비용이 달라진다.

복합 index (country, created_at)는 먼저 country로 정렬하고 같은 country 안에서 created_at으로 정렬한다. country 조건 없이 created_at만 찾을 때 얼마나 쓸 수 있는지는 제품과 skip-scan 지원에 달린다. SQL WHERE에 조건을 적은 순서보다 index key의 정렬 순서와 operator 지원이 중요하다.

## 6. LSM tree가 쓰기를 모으는 이유

**LSM(Log-Structured Merge) tree**는 작은 random update를 메모리에서 정렬해 모은 뒤 immutable sorted file로 순차 기록하고, 나중에 여러 file을 merge하는 저장 구조다. B-tree처럼 기존 leaf page를 그 자리에서 계속 수정하는 대신 새 version을 뒤에 기록한다.

LSM의 핵심 객체는 다음과 같다.

- **WAL(Write-Ahead Log, 선행 기록 로그)**: 메모리 변경을 잃었을 때 복구할 정보를 durable storage에 먼저 기록하는 순차 로그다.
- **memtable**: 새 key/value를 받는 변경 가능한 메모리 정렬 구조다.
- **immutable memtable**: 한도에 도달해 새 write는 받지 않지만 flush가 끝날 때까지 메모리에 남는 정렬 구조다.
- **SSTable(Sorted String Table)**: key 순서로 기록되고 완성 뒤 제자리 수정하지 않는 file이다.
- **manifest 또는 version metadata**: 어느 SSTable 집합이 현재 읽기 상태를 구성하는지 기록한다.
- **compaction worker**: 겹치는 run을 읽어 새 sorted file을 만들고 오래된 version을 정리하는 background 작업이다.

여기서 immutable은 파일 bytes를 제자리 update하지 않는다는 뜻이다. file이 영원히 남는다는 뜻이 아니다. compaction output이 설치되고 어떤 reader도 옛 file을 필요로 하지 않으면 삭제된다.

## 7. 한 write의 WAL→memtable→flush 수명

client가 k=7, v=A를 쓴다고 하자.

1. database worker가 request를 검증하고 sequence number 101을 부여한다.
2. 복구에 필요한 (101, k=7, v=A)를 WAL buffer에 추가한다.
3. durability 계약이 요구하는 시점까지 WAL을 storage에 기록한다.
4. mutable memtable에 key 7, sequence 101, value A를 넣는다.
5. client success를 돌려주는 정확한 시점은 제품의 sync 설정과 transaction 계약에 따른다.
6. memtable이 64 MiB 한도에 차면 immutable로 전환한다.
7. 새 write는 새 mutable memtable에 들어가므로 foreground가 계속 진행할 수 있다.
8. background flush가 immutable 내용을 key 순서 SSTable F3로 기록한다.
9. F3를 현재 version에 원자적으로 설치한다.
10. 어떤 복구에도 필요 없는 WAL 구간과 immutable memtable을 회수한다.

WAL보다 memtable만 먼저 바꾸고 성공을 알린 뒤 crash하면 메모리 내용이 사라질 수 있다. “write-ahead”는 복구 가능한 로그가 해당 데이터 page나 영구 file보다 먼저 안전해져야 한다는 순서 계약이다. 정확한 fsync와 group commit 정책은 엔진 설정에 따라 다르다.

**flush**는 immutable memtable을 SSTable로 내리는 과정이다. dirty OS page cache에 write call이 끝난 것과 storage가 정전 뒤에도 보존하는 durable 상태는 같지 않을 수 있다. durability 설명에는 어느 계층까지 완료했는지 명시해야 한다.

## 8. 조회에서 최신 version을 고르는 전체 trace

현재 상태가 다음과 같다고 하자.

| 위치 | key 7 entry | sequence |
|---|---|---:|
| mutable memtable | v=C | 105 |
| immutable memtable | 없음 | - |
| L0 F5 | v=B | 103 |
| L1 F2 | v=A | 101 |

조회 snapshot이 sequence 105까지 볼 수 있으면 memtable의 C가 가장 최신 visible version이므로 C를 반환한다. snapshot이 102라면 sequence 105와 103은 미래라 볼 수 없고 F2의 A를 반환할 수 있다.

LSM read는 보통 최신 가능성이 높은 메모리와 높은 level 후보부터 확인하고, file key range, index block, Bloom filter로 불필요한 file을 줄인다. level 구성과 탐색 순서는 엔진별로 다르며 “항상 모든 SSTable을 읽는다”거나 “항상 하나만 읽는다”고 단정할 수 없다.

같은 key의 여러 version을 발견했을 때 sequence와 snapshot 규칙을 적용해야 한다. 값이 먼저 발견되었다는 이유만으로 즉시 반환하면 더 최신 tombstone이나 보이지 않는 version을 놓칠 수 있다.

## 9. tombstone과 안전한 삭제 시점

LSM에서 key 7을 삭제할 때 옛 SSTable F2의 A와 F5의 B를 제자리에서 지우지 않는다. 새 sequence 106의 **tombstone(삭제 표식)**을 memtable에 기록한다. tombstone은 “이 sequence 이후에는 이 key가 삭제됨”을 나타내는 record다.

sequence 106까지 보는 read는 tombstone을 만나 결과 없음으로 처리한다. 오래된 snapshot 104는 tombstone보다 과거이므로 B를 볼 수 있다. 따라서 tombstone을 보자마자 옛 version을 모두 버리면 오래된 reader의 의미를 깨뜨릴 수 있다.

compaction에서 tombstone을 제거하려면 더 아래 level에 가려야 할 옛 value가 없고, 어떤 snapshot도 삭제 전 version을 필요로 하지 않는다는 조건이 필요하다. 이 조건은 engine의 sequence, snapshot, level 범위 규칙으로 판단한다.

tombstone이 오래 쌓이면 read가 삭제 표식과 옛 version을 많이 확인하고 공간도 차지한다. 반대로 너무 일찍 제거하면 삭제한 값이 아래 오래된 SSTable에서 다시 나타나는 잘못된 결과가 생긴다.

## 10. compaction의 입력과 출력

L0 F5에 [(2,X,104),(7,B,103),(9,Q,104)], L1 F2에 [(1,M,90),(7,A,101),(8,P,99)]가 있다고 하자. compaction은 두 정렬 stream을 key 순서로 merge한다.

| 비교 | 선택·보존 |
|---|---|
| F2 key1 vs F5 key2 | key1 M 출력 |
| F5 key2 vs F2 key7 | key2 X 출력 |
| key7 vs key7 | snapshot 조건에 따라 B와 A 중 필요한 version 보존 |
| F2 key8 vs F5 key9 | key8 P 출력 |
| F5 key9 | key9 Q 출력 |

새 SSTable F6를 완전히 쓰고 metadata에 설치하기 전에는 old files를 삭제하지 않는다. crash가 나면 이전 version이나 완성된 새 version 중 일관된 집합으로 복구해야 한다. F6가 설치되어도 진행 중인 reader가 F5/F2 file handle을 참조하면 즉시 물리 삭제하지 않을 수 있다.

**leveled compaction**은 level별 크기 목표와 key 범위 중복을 줄여 read 후보를 제한하는 전략이다. **tiered 또는 universal compaction**은 여러 비슷한 run을 묶는 방식이다. 어느 쪽이 항상 좋지 않다. write 양, read 형태, 공간 여유, tail latency 목표가 선택을 바꾼다.

## 11. Bloom filter의 정확한 보장

**Bloom filter**는 file에 key가 들어 있을 가능성을 작은 bit 배열로 요약한 확률적 자료 구조다. key를 여러 hash 함수로 bit 위치에 바꾸어 표시한다. read는 같은 위치를 확인한다.

- 하나라도 0이면 그 filter가 대표하는 집합에는 key가 없다고 판단할 수 있다. false negative가 없도록 올바르게 구성했다는 조건이다.
- 모두 1이면 key가 있을 수도 있고 다른 key들이 우연히 같은 bit를 켰을 수도 있다. false positive가 가능하다.

따라서 Bloom negative는 SSTable read를 건너뛰지만 positive는 index와 data block을 확인해야 한다. “Bloom filter hit 수”를 실제 key hit 수로 해석하면 안 된다.

filter가 사용하는 bit/key를 늘리면 false-positive 확률을 낮출 수 있지만 메모리와 cache 비용이 증가한다. range query에는 단일 key 부재 filter가 큰 도움을 주지 못할 수 있으며 prefix filter 등 별도 설계가 필요하다.

## 12. 읽기·쓰기·공간 증폭

**write amplification(쓰기 증폭)**은 사용자가 논리적으로 쓴 byte에 비해 storage 계층에 실제로 쓴 byte의 비율이다. 100 MiB 사용자 입력에 다음 쓰기가 발생했다고 하자.

- WAL 100 MiB
- flush SSTable 100 MiB
- 첫 compaction output 200 MiB
- 둘째 compaction output 300 MiB

단순 합계는 700 MiB이고 쓰기 증폭은 700 / 100 = 7배다. 실제 측정에서는 filesystem과 device 내부 write까지 범위를 정의해야 한다.

**read amplification(읽기 증폭)**은 한 논리 read를 위해 확인한 memtable, SSTable, index block, data block의 수나 byte 비율이다. 단위 정의를 보고한다. Bloom filter와 level 중복 감소가 불필요한 file read를 줄일 수 있다.

**space amplification(공간 증폭)**은 최신 논리 데이터 크기에 비해 live old version, tombstone, compaction 중복 file이 차지하는 실제 공간 비율이다. 100 GiB 최신 데이터에 실제 140 GiB를 사용하면 단순 공간 증폭은 1.4배다.

세 증폭은 trade-off다. compaction을 자주 하면 read와 공간은 줄 수 있지만 write와 background I/O가 늘고 foreground tail latency를 방해할 수 있다. compaction을 늦추면 write는 가벼워도 L0 file과 tombstone이 늘어 read가 느려질 수 있다.

## 13. B+tree와 LSM 선택의 조건

B+tree는 page를 그 자리에서 갱신하고 정렬 leaf를 이용해 point와 range read를 안정적으로 제공하기 좋다. random write와 split, WAL, page latch 비용이 있다.

LSM은 write를 메모리에 모아 순차 file로 내리므로 높은 write 처리량에 유리할 수 있다. 대신 최신 version을 여러 구조에서 찾고 compaction을 수행한다. storage가 SSD라고 random I/O 비용과 write endurance, background contention이 사라지지 않는다.

비교할 때 다음을 고정한다.

- point read와 range read 비율
- write와 delete 비율
- key와 value 크기
- snapshot 보존 시간
- memory budget과 Bloom filter 크기
- storage 대역폭·latency와 남은 공간
- foreground p50·p99 latency
- crash recovery와 durability 설정

“LSM은 write가 한 번”, “B-tree는 read가 한 번” 같은 문장은 구조의 실제 write path와 table lookup을 생략한다.

## 14. 완전 풀이 문제

### 문제 1. fan-out과 높이

fan-out 200, leaf 40,000 page면 바로 위 internal page는 최소 몇 개인가?

**풀이:** ceil(40,000 / 200) = 200 page다. root 한 page가 그 200 internal page를 모두 가리킬 수 있다고 가정하면 root→internal→leaf 3 level이다. key 크기로 실제 fan-out이 작아지면 높이는 달라진다.

### 문제 2. split 부모 갱신

leaf를 둘로 나눴는데 부모에 새 pointer를 넣지 않으면 무슨 일이 생기는가?

**풀이:** 새 오른쪽 leaf는 storage에 존재해도 root에서 내려오는 탐색 경로가 없다. 경계 key 이상의 검색이 old leaf로만 가거나 결과를 놓친다. sibling만으로 우연히 range scan이 찾을 수 있어도 정상 point search 구조가 아니다.

### 문제 3. range scan

L1=[10,20,30], L2=[40,50,60], L3=[70,80]일 때 25~65 범위가 읽고 출력하는 key는?

**풀이:** root 탐색으로 L1에서 25 이상의 위치를 찾고 30을 출력한다. sibling L2에서 40,50,60을 출력한다. L3 첫 key 70이 upper bound 65를 넘으므로 멈춘다. 출력은 [30,40,50,60]이다.

### 문제 4. Bloom positive

Bloom filter가 key 7에 positive면 SSTable에 반드시 key가 있는가?

**풀이:** 아니다. 다른 key가 같은 bit들을 켠 false positive가 가능하다. SSTable index와 data block을 확인해야 한다. 올바른 filter의 negative만 file에 key가 없다는 skip 근거가 된다.

### 문제 5. tombstone 수명

최신 tombstone 106, 옛 value 103이 있고 snapshot 104 reader가 살아 있다. compaction이 value 103을 버려도 되는가?

**풀이:** 안 된다. snapshot 104는 tombstone 106을 볼 수 없고 value 103을 볼 수 있어야 한다. reader가 끝나고 아래 level에 되살아날 더 오래된 value가 없다는 조건까지 확인한 뒤 정리한다.

### 문제 6. 쓰기 증폭

사용자 200 MiB, WAL 200 MiB, flush 200 MiB, compaction outputs 400 MiB와 600 MiB라면 단순 증폭은?

**풀이:** 실제 쓴 양은 200+200+400+600 = 1400 MiB다. 1400/200 = 7배다. device 내부 garbage collection까지 포함할지 측정 경계를 밝혀야 한다.

### 문제 7. 최신 version

memtable sequence 120 값 C, L0 sequence 118 tombstone, L1 sequence 110 값 A가 있다. snapshot 119와 120의 결과는?

**풀이:** snapshot 119는 sequence 120을 볼 수 없고 118 tombstone을 보므로 결과 없음이다. snapshot 120은 가장 최신 visible entry인 C를 보므로 C다. 위치 순서보다 sequence와 snapshot 가시성이 우선이다.

### 문제 8. index 추가 비용

read가 빨라질 index를 하나 추가하면 write 비용은 왜 늘 수 있는가?

**풀이:** INSERT와 indexed key UPDATE마다 table WAL뿐 아니라 index WAL·page update 또는 LSM entry·flush·compaction이 필요하다. page split, cache 사용과 저장 공간도 늘 수 있다. read 이득과 write·recovery 비용을 같은 workload에서 측정한다.

## 공식 자료

- [PostgreSQL B-Tree indexes](https://www.postgresql.org/docs/current/btree.html)
- [PostgreSQL index types](https://www.postgresql.org/docs/current/indexes-types.html)
- [RocksDB Wiki](https://github.com/facebook/rocksdb/wiki)
- [RocksDB compaction](https://github.com/facebook/rocksdb/wiki/Compaction)
