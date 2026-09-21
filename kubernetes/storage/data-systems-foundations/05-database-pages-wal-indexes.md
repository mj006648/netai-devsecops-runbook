# 05. 데이터베이스 페이지, WAL, 인덱스, LSM을 한 층씩 보기

작성·문헌 확인일: **2026-09-21**. 이 장은 연구자가 데이터 시스템 논문과 운영 문서를 읽을 때 혼동하기 쉬운 “페이지”, “로그”, “스냅샷”, “컴팩션”을 낮은 층에서 정리한다. 공식 문서의 세부는 버전별로 달라질 수 있으므로, 구현 판단 전에는 사용 중인 PostgreSQL·RocksDB·Iceberg 릴리스 문서를 다시 고정한다. 여기서 쓰는 예제는 모두 **개념 설명용 가상 사례**이며, 실제 데이터베이스에 실행할 SQL이나 운영 명령이 아니다. Lakehouse 논문별 성능·연구 리뷰는 이미 [Iceberg·Open Table Format 주요 논문 리뷰](../lakehouse/02-paper-reviews.md)에 정리되어 있으므로, 이 장은 파일·페이지·로그의 기계적 동작에 집중한다.

## 1. 세 종류의 “페이지”를 먼저 분리한다

데이터베이스 페이지는 DB 엔진이 테이블·인덱스 내용을 나누어 관리하는 논리적 저장 단위다. PostgreSQL heap과 기존 인덱스는 보통 8 KiB 고정 크기 페이지 배열로 저장되며, 컴파일 시 다른 크기를 고를 수 있다. [PostgreSQL 18 Database Page Layout](https://www.postgresql.org/docs/18/storage-page-layout.html) 파일시스템 블록은 OS와 파일시스템이 파일 바이트를 디스크 블록에 배치하고 캐시하는 단위다. 메모리 페이지는 CPU MMU와 커널 가상 메모리가 주소 변환·보호·스왑을 관리하는 단위다. 이 셋은 우연히 비슷한 단어를 쓰지만, 소유자·목적·크기·수명 주기가 다르다. DB 페이지는 행·인덱스 엔트리·free space 같은 DB 의미를 가진다. 파일시스템 블록은 파일 오프셋과 물리 저장 장치 사이의 매핑을 가진다. 메모리 페이지는 프로세스 주소 공간과 물리 RAM 사이의 매핑을 가진다. 따라서 “페이지 캐시 hit”라는 표현이 OS page cache인지, DB buffer pool인지, CPU TLB 근처의 가상 메모리 이야기인지 확인해야 한다.

```text
개념 흐름

SQL row / index entry
        ↓ DB 엔진이 배치
Database page, 예: heap page 또는 btree page
        ↓ 파일 바이트로 저장
Filesystem file offset / block mapping
        ↓ 커널 캐시와 장치 I/O
OS page cache / storage device
        ↓ 프로세스 주소 변환
Virtual memory page / physical RAM
```

### 1.1 worked example: 같은 8 KiB라는 숫자가 같은 뜻은 아니다

가상 테이블 `sensor_event`의 한 행이 200 bytes라고 하자. DB 엔진은 여러 행을 한 DB 페이지에 넣고, 페이지 안의 item id로 각 행 위치를 찾는다. 파일시스템은 그 DB 페이지가 들어 있는 파일 범위를 여러 블록에 배치할 수 있다. 커널은 그 파일 범위를 OS page cache에 올릴 수 있지만, DB 엔진은 자기 buffer pool에 별도 사본을 둘 수도 있다. 메모리 페이지 크기가 4 KiB인 시스템에서는 한 DB 페이지를 담는 버퍼가 두 가상 메모리 페이지에 걸칠 수 있다. 이 숫자 예제는 단순화이며, 실제 정렬·padding·압축·TOAST·파일시스템 extent에 따라 달라진다. 핵심은 “8 KiB를 읽었다”는 말만으로 DB row 수, 디스크 블록 수, RAM page 수를 추론하지 않는 것이다.

## 2. Slotted page는 행을 밀어 넣는 봉투가 아니라 주소 안정성 장치다

PostgreSQL 문서는 페이지가 `PageHeaderData`, `ItemIdData`, free space, items, special space로 나뉜다고 설명한다. [PostgreSQL 18 Database Page Layout](https://www.postgresql.org/docs/18/storage-page-layout.html) `ItemIdData`는 실제 item의 offset과 길이를 가리키며, PostgreSQL의 `CTID`는 page number와 item identifier index의 조합으로 구성된다. [PostgreSQL 18 Database Page Layout](https://www.postgresql.org/docs/18/storage-page-layout.html) 이 구조를 일반적으로 slotted page라고 부른다. 새 item id는 앞쪽에서 자라고, 실제 row bytes는 뒤쪽에서 거꾸로 자라며, 가운데 free space가 줄어든다. 행 본문을 페이지 안에서 옮겨도 item id 슬롯이 유지되면 외부 참조는 비교적 안정적으로 남는다. 인덱스 페이지는 special space를 이용해 access method별 부가 정보를 넣을 수 있고, PostgreSQL btree 페이지는 형제 링크 같은 정보를 둔다. [PostgreSQL 18 Database Page Layout](https://www.postgresql.org/docs/18/storage-page-layout.html)

```text
PostgreSQL식 slotted page 단순도

+-------------------- page 시작
| PageHeaderData     | 24 bytes 등: LSN, free-space 포인터
+--------------------
| ItemId[1]          | offset,length → row A
| ItemId[2]          | offset,length → row B
| ...                |
+-------------------- pd_lower
| free space         |
+-------------------- pd_upper
| row B bytes        |
| row A bytes        |
+-------------------- pd_special
| special space      | index page면 access method 정보
+-------------------- page 끝
```

### 2.1 worked example: 행 하나 update의 물리적 흔적

가상 행 `event_id=e7, temp=20`이 page 42의 slot 3에 있다고 하자. MVCC 엔진은 update 시 기존 row bytes를 제자리 수정하지 않고 새 row version을 만들 수 있다. 새 version이 같은 페이지에 들어가면 free space가 줄고, 오래된 version은 아직 보일 수 있는 transaction 때문에 즉시 지워지지 않을 수 있다. 이때 “한 논리 행을 고쳤다”와 “한 페이지 안의 bytes가 덮어써졌다”는 같은 말이 아니다. 인덱스가 새 version을 어떻게 가리키는지는 access method와 update된 컬럼, HOT 같은 최적화에 따라 달라진다. PostgreSQL HOT은 인덱스가 참조하는 컬럼을 바꾸지 않고 같은 페이지에 공간이 있을 때 새 인덱스 엔트리를 피할 수 있다. [PostgreSQL 18 Heap-Only Tuples](https://www.postgresql.org/docs/18/storage-hot.html)

## 3. Buffer pool과 OS cache는 협력하지만 같은 캐시가 아니다

DB buffer pool은 DB 엔진이 자기 페이지 단위로 pin, dirty 상태, eviction, WAL LSN, checkpoint 정책을 관리하는 메모리 영역이다. PostgreSQL의 `shared_buffers`는 서버가 공유 메모리 버퍼로 쓰는 양을 정하며, 값은 보통 `BLCKSZ` 블록 단위로 해석된다. [PostgreSQL 18 Resource Consumption](https://www.postgresql.org/docs/18/runtime-config-resource.html) PostgreSQL 공식 문서는 PostgreSQL이 OS cache에도 의존하므로 `shared_buffers`를 RAM의 40%보다 크게 잡는 것이 항상 더 낫다고 보기는 어렵다고 설명한다. [PostgreSQL 18 Resource Consumption](https://www.postgresql.org/docs/18/runtime-config-resource.html) OS page cache는 파일 읽기·쓰기 바이트를 커널이 캐시하는 계층이다. DB가 buffered I/O를 쓰면 같은 데이터가 DB buffer pool과 OS page cache에 중복될 수 있다. DB가 direct I/O 또는 다른 I/O 방식을 쓰면 중복 양상은 달라질 수 있지만, 이 장은 특정 엔진 설정을 일반화하지 않는다. 중요한 구분은 DB buffer pool이 “페이지 내용의 DB적 의미”를 안다는 점이다. OS cache는 파일 바이트를 빠르게 제공하지만, 어느 tuple이 visible인지, 어느 page LSN이 안전한지 알지 못한다.

```text
개념 읽기 경로

Query executor
  → Buffer manager: DB page가 buffer pool에 있는가?
      hit  → page latch/pin 후 읽기
      miss → storage manager에 파일 범위 요청
              → OS page cache hit면 디스크 없이 복사 가능
              → miss면 장치 I/O
```

### 3.1 worked example: cache hit 통계 해석

가상 쿼리가 1,000개 DB 페이지를 읽는다고 하자. DB buffer pool에 700개가 있으면 DB cache hit rate는 70%다. 나머지 300개 중 250개가 OS page cache에 있다면 실제 장치 I/O는 50개 page 범위로 줄 수 있다. 반대로 DB hit rate가 낮아도 OS cache가 뜨거우면 장치 지연은 낮을 수 있다. 또 DB hit rate가 높아도 CPU decoding, latch 경합, visibility check가 병목이면 전체 쿼리는 느릴 수 있다. 따라서 하나의 cache 지표를 전체 성능 원인으로 단정하지 않는다.

## 4. B+tree는 정렬된 경로와 범위를 관리하고, hash는 동등 비교에 특화된다

PostgreSQL 문서는 기본 `CREATE INDEX`가 B-tree를 만들며, B-tree가 정렬 가능한 값의 equality와 range query에 쓰일 수 있다고 설명한다. [PostgreSQL 18 Index Types](https://www.postgresql.org/docs/18/indexes-types.html) 같은 문서에서 hash index는 indexed column 값의 hash code를 저장하고 단순 equality 비교만 처리한다고 설명한다. [PostgreSQL 18 Index Types](https://www.postgresql.org/docs/18/indexes-types.html) B+tree 계열 인덱스는 root에서 internal page를 따라 leaf page까지 내려간다. Leaf page는 key 순서로 정렬되어 있어 특정 key를 찾은 뒤 인접 key range를 순차적으로 읽기 쉽다. Hash index는 hash bucket을 찾아 equality lookup에는 적합하지만, `temperature BETWEEN 20 AND 25` 같은 range 순서를 직접 표현하지 못한다. 실제 옵티마이저가 어떤 인덱스를 선택하는지는 통계, selectivity, 정렬 필요성, visibility, random I/O 비용 모델에 좌우된다.

```text
B+tree range scan 단순도

root page
  ├─ key < 100  → internal A
  └─ key ≥ 100  → internal B
                   ├─ key < 150 → leaf L1: 100, 110, 120
                   └─ key ≥150 → leaf L2: 150, 160, 170

조건: 110 <= key < 165
1. root/internal을 따라 110이 있을 leaf를 찾는다.
2. leaf L1에서 시작한다.
3. leaf sibling을 따라 L2까지 읽다가 165 이상에서 멈춘다.
```

### 4.1 worked example: equality와 range가 함께 있을 때

가상 조건이 `device_id = 'A' AND event_time BETWEEN 09:00 AND 10:00`이라고 하자. 복합 B-tree `(device_id, event_time)`는 `device_id='A'` 구간 안에서 `event_time` range를 순서대로 찾을 수 있다. Hash index on `device_id`는 `A`인 후보를 찾는 데 도움이 될 수 있지만, 후보 안의 시간 순서는 별도 처리해야 한다. B-tree가 항상 빠르다는 뜻은 아니다. 후보가 테이블 대부분이면 sequential scan이 더 싸거나, 데이터가 메모리에 있거나, index-only scan 조건이 맞지 않을 수 있다. 이 장은 구조적 가능성을 설명할 뿐, workload 없이 성능 보장을 주장하지 않는다.

## 5. WAL은 “먼저 로그”이지 “모든 ACID를 혼자 해결”이 아니다

PostgreSQL WAL 설명의 핵심은 data file 변경이 영구 저장소에 쓰이기 전에 해당 변경을 설명하는 WAL record가 먼저 flush되어야 한다는 것이다. [PostgreSQL 18 WAL](https://www.postgresql.org/docs/18/wal-intro.html)

이 규칙은 “commit된 transaction의 data page만 디스크에 내려간다”는 뜻이 아니다. 어떤 dirty data page가 쓰이려면 그 page의 변경을 설명하는 WAL이 먼저 durable해야 한다는 순서 제약이다. 따라서 write-ahead rule을 만족하면 아직 commit ACK를 받지 않은 transaction의 page bytes도 data file 쪽에 먼저 내려갈 수 있고, 그 row가 query에 보이는지는 MVCC snapshot과 transaction 상태가 따로 결정한다. PostgreSQL MVCC 문서는 statement가 특정 시점의 database version snapshot을 본다고 설명한다. [PostgreSQL 18 MVCC Introduction](https://www.postgresql.org/docs/18/mvcc-intro.html)

동기 commit 설명은 기본적으로 WAL-backed synchronous commit 설정을 전제한다. PostgreSQL의 일반 synchronous commit은 success indication을 client에 돌려주기 전에 transaction WAL record가 permanent storage에 flush되기를 기다린다. [PostgreSQL 18 Asynchronous Commit](https://www.postgresql.org/docs/18/wal-async-commit.html) 이 절차 덕분에 transaction commit마다 모든 dirty data page를 즉시 flush하지 않아도 crash 후 WAL redo로 data page 상태를 복구할 수 있다. [PostgreSQL 18 WAL](https://www.postgresql.org/docs/18/wal-intro.html)

예외도 명확히 적어야 한다. `synchronous_commit=off`에서는 success가 보고된 뒤 transaction이 crash-safe해지기까지 지연이 있을 수 있고, PostgreSQL 문서는 최대 지연을 `wal_writer_delay`의 세 배로 설명한다. [PostgreSQL 18 WAL Settings](https://www.postgresql.org/docs/18/runtime-config-wal.html) `fsync=off`는 더 위험하다. PostgreSQL 문서는 `fsync`를 끄면 power failure나 system crash 때 unrecoverable data corruption이 생길 수 있다고 경고한다. [PostgreSQL 18 WAL Settings](https://www.postgresql.org/docs/18/runtime-config-wal.html)

Durability 관점에서 WAL은 commit acknowledged transaction의 변경을 crash 뒤 다시 만들 수 있게 한다. Atomicity 관점에서는 WAL record, transaction status, undo/redo 또는 MVCC 설계가 함께 “전부 반영 또는 미반영” 관측을 만든다. Isolation 관점에서는 WAL만으로 충분하지 않고 lock, MVCC snapshot, predicate conflict 감지 같은 동시성 제어가 필요하다. 따라서 WAL을 “ACID의 D에 강하게 연결된 복구 로그”로 보는 편이 안전하다. A와 I까지 설명하려면 commit protocol과 concurrency control을 함께 읽어야 한다.

```text
개념 commit 경로

Transaction changes buffer pages
        ↓
Generate WAL records for page changes
        ↓ write-ahead rule for a dirty page write
Flush WAL at least through the page LSN before that page reaches data file
        ↓ transaction commit path, synchronous case
Flush commit WAL through commit LSN before success ACK
        ↓ async/non-durable variants differ
Acknowledge commit according to synchronous_commit/fsync settings
        ↓ later or earlier, as long as WAL ordering is safe
Dirty data pages are written by checkpoint/background/user backends
        ↓ crash case
Restart reads durable WAL and replays needed records; MVCC decides visibility
```

### 5.1 worked example: data page가 아직 디스크에 없어도 commit될 수 있다

가상 transaction T1이 page 42에 행 하나를 추가한다고 하자. Page 42가 data file에 먼저 내려가려면 그 page 변경 record까지의 WAL이 먼저 flush되어야 한다. 하지만 이 사실만으로 T1이 commit되어 보인다는 뜻은 아니다. Query visibility는 MVCC snapshot과 transaction 상태가 결정한다.

Synchronous commit 설정에서 T1이 commit ACK를 받았다면 commit WAL도 durable하다는 뜻에 가깝다. 그래도 page 42의 최신 image가 아직 data file에 쓰이지 않았을 수 있다. 전원 장애가 나면 data file의 page 42는 옛 모습일 수 있고, 복구 과정은 durable WAL을 읽어 빠진 변경을 redo한다.

반대로 asynchronous commit에서는 client가 success를 받은 직후 crash가 나면 아직 flush되지 않은 최근 transaction이 사라질 수 있다. PostgreSQL 문서는 이 경우 risk가 data corruption이 아니라 최근 transaction loss라고 설명한다. [PostgreSQL 18 Asynchronous Commit](https://www.postgresql.org/docs/18/wal-async-commit.html) 따라서 commit 응답의 의미는 설정과 durability 옵션을 함께 적어야 하며, “data file page가 이미 제자리 저장됐다”로 해석하면 안 된다.

## 6. MVCC snapshot, backup snapshot, Iceberg snapshot은 서로 다른 계약이다

PostgreSQL MVCC에서 각 SQL statement는 어떤 과거 시점의 database version snapshot을 보며, concurrent update의 불완전 상태를 보지 않도록 한다. [PostgreSQL 18 MVCC Introduction](https://www.postgresql.org/docs/18/mvcc-intro.html) 이 snapshot은 주로 transaction visibility 규칙이다. 물리 backup snapshot은 특정 시간대의 파일 집합과 WAL 범위를 함께 보존해 복구 가능성을 제공하는 운영 산출물이다. PostgreSQL WAL 문서는 online backup과 point-in-time recovery가 WAL archive로 가능하며, backup이 순간 snapshot이 아니어도 WAL replay로 내부 불일치를 고칠 수 있다고 설명한다. [PostgreSQL 18 WAL](https://www.postgresql.org/docs/18/wal-intro.html) Iceberg snapshot은 analytic table의 data file 집합을 가리키는 table-format metadata 상태다. Iceberg spec은 snapshot을 특정 시점의 table state로 정의하고, data file은 manifest와 manifest list를 통해 추적된다고 설명한다. [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/) 이 셋을 모두 “스냅샷”이라고 부르지만, 하나는 읽기 가시성, 하나는 복구 자료, 하나는 파일 집합 버전이다.

| 이름 | 주체 | 보장하려는 질문 | 혼동하면 생기는 오류 |
| --- | --- | --- | --- |
| MVCC snapshot | DB transaction engine | 이 statement/transaction이 어떤 row version을 볼까 | backup이 됐다고 착각 |
| Backup snapshot | backup/restore 운영 | 이 파일과 WAL로 어디까지 복구할까 | query isolation과 동일시 |
| Iceberg snapshot | table format metadata | 이 table version의 data/delete files는 무엇인가 | DB row lock이나 WAL로 착각 |

### 6.1 worked example: 같은 “S1”이라는 이름을 붙여도 의미가 다르다

가상 PostgreSQL transaction이 09:00에 snapshot을 잡고 긴 SELECT를 실행한다. 그 SELECT는 09:05에 commit된 row를 보지 않을 수 있다. 동시에 운영자는 09:00–09:10 사이 physical backup을 수행하고 WAL을 보존한다. 이 backup은 복구 시 09:07 상태로 replay할 수 있을지의 문제이지, 긴 SELECT가 무엇을 봤는지의 문제가 아니다. 또 Iceberg table의 snapshot S1은 특정 manifest list와 data files를 가리킨다. S1을 보존한다고 원본 PostgreSQL heap page나 WAL record가 보존되는 것은 아니다.

## 7. LSM은 쓰기를 정렬된 파일로 밀어내고, 읽기 때 여러 층을 조합한다

RocksDB overview는 기본 구성 요소를 memtable, sstfile, logfile이라고 설명한다. [RocksDB Overview](https://github.com/facebook/rocksdb/wiki/RocksDB-Overview) 새 write는 memtable에 들어가고 선택적으로 WAL이라고도 부르는 logfile에 기록되며, memtable이 차면 sorted SST file로 flush된다. [RocksDB Overview](https://github.com/facebook/rocksdb/wiki/RocksDB-Overview) SST file은 key 순서로 정렬되어 lookup을 쉽게 한다. [RocksDB Overview](https://github.com/facebook/rocksdb/wiki/RocksDB-Overview) LSM의 기본 tradeoff는 random in-place write를 줄이고 sequential write·background compaction으로 비용을 이동하는 것이다. Write amplification은 한 논리 write가 storage에 여러 번 다시 쓰이는 비율이다. Read amplification은 하나의 lookup 또는 range scan이 memtable과 여러 SST run을 확인해야 하는 부담이다. Space amplification은 최신 논리 데이터보다 더 많은 physical bytes가 임시·오래된 version·tombstone 때문에 존재하는 부담이다. 이 세 값은 compaction style과 workload에 따라 서로 교환된다.

```text
LSM write path 단순도

Client Put(k=42,v=20)
    ↓
WAL/logfile append
    ↓
Memtable insert
    ↓ memtable full
Flush to SST L0: sorted run
    ↓ background
Compaction merges overlapping SSTs to lower levels
    ↓
Older value versions and tombstones may be dropped when safe
```

### 7.1 worked example: update 세 번과 tombstone 하나

가상 key `device:A`에 값 20, 21, 22가 순서대로 들어오고 마지막에 delete가 들어온다고 하자. Memtable flush가 자주 일어나면 L0 SST 세 개와 delete tombstone이 서로 다른 파일에 있을 수 있다. 읽기는 최신 sequence number를 고려해 22 또는 삭제 상태를 찾아야 한다. Compaction은 같은 key의 오래된 20·21 version을 버리고, tombstone이 더 아래 level의 오래된 값을 가렸다는 사실이 충분히 반영되면 tombstone도 제거할 수 있다. 하지만 snapshot iterator나 복제, 백업, 보존 정책이 있으면 오래된 파일을 즉시 지울 수 없을 수 있다. RocksDB도 compaction 후 새 version을 만들고 live SST file 목록을 관리하며, outstanding iterator가 이전 파일을 필요로 할 수 있다고 설명한다. [RocksDB live SST files](https://github.com/facebook/rocksdb/wiki/How-we-keep-track-of-live-SST-files)

## 8. Leveled, universal, FIFO compaction은 목적 함수가 다르다

RocksDB compaction 문서는 level, universal, FIFO 같은 compaction style을 구분한다. [RocksDB Compaction](https://github.com/facebook/rocksdb/wiki/Compaction) Leveled compaction은 일반적으로 space amplification을 낮추려 하지만 read/write amplification tradeoff를 가진다. [RocksDB Compaction](https://github.com/facebook/rocksdb/wiki/Compaction) Universal compaction은 write amplification을 낮추려는 use case에 맞지만 read amplification과 space amplification이 커질 수 있다. [RocksDB Universal Compaction](https://github.com/facebook/rocksdb/wiki/Universal-Compaction) FIFO compaction은 오래된 파일을 버리는 cache-like 데이터에 맞는 스타일로 설명된다. [RocksDB Compaction](https://github.com/facebook/rocksdb/wiki/Compaction) 따라서 “compaction을 켜면 빨라진다”가 아니라 “어느 amplification을 줄이고 어느 비용을 받아들이는가”로 읽어야 한다. Write-heavy workload에서 universal이 유리할 수 있어도, point lookup latency나 임시 공간 요구가 문제가 될 수 있다. Read-heavy workload에서 leveled가 유리할 수 있어도, hot key update가 많은 경우 write bytes가 커질 수 있다. 이 장은 일반 원리를 설명하며, 특정 설정의 성능 보장을 하지 않는다.

## 9. DB LSM compaction과 Iceberg file compaction은 이름만 비슷한 다른 층이다

RocksDB LSM compaction은 key-value storage engine 내부에서 SST run을 병합하고 오래된 key version·tombstone을 정리한다. Iceberg file compaction은 table snapshot이 참조하는 data/delete files를 더 큰 파일이나 더 나은 배치로 다시 쓰고 새 snapshot으로 게시하는 table-format 작업이다. Iceberg는 개별 data file을 table metadata에서 추적하고, manifest와 manifest list 통계를 이용해 planning과 pruning을 돕는다. [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/) Iceberg maintenance 문서는 manifest metadata tree가 table data 위의 index처럼 planning을 빠르게 하는 역할을 한다고 설명한다. [Apache Iceberg Maintenance](https://iceberg.apache.org/docs/latest/maintenance/) RocksDB compaction은 DB engine이 자체 key order와 sequence number를 해석한다. Iceberg compaction은 Parquet/ORC/Avro data file과 delete file을 table metadata 경계에서 교체한다. RocksDB compaction 결과는 보통 같은 key-value database의 내부 파일 version 변화다. Iceberg compaction 결과는 독자가 볼 수 있는 table snapshot 변화이며, commit 실패·동시 writer conflict·orphan file 정리까지 별도 고려한다.

```text
혼동 방지 도식

RocksDB LSM
  key/value write → WAL + memtable → SST → LSM compaction

Iceberg table
  engine output rows → Parquet files → manifest → snapshot metadata → catalog commit
                                     ↘ file rewrite/compaction creates new files and snapshot
```

### 9.1 worked example: “작은 파일 정리”라는 말의 두 의미

RocksDB에서 작은 SST가 많으면 compaction이 SST run을 합쳐 read amplification을 줄일 수 있다. Iceberg에서 작은 Parquet data file이 많으면 rewrite data files가 query planning과 object open overhead를 줄일 수 있다. 둘 다 “작은 파일”을 말하지만, 첫 번째는 key-value engine 내부 구조이고 두 번째는 analytic table의 data file layout이다. RocksDB compaction이 Iceberg manifest를 수정하지 않는다. Iceberg rewrite가 RocksDB memtable을 flush하지도 않는다. 스토리지 계층을 섞어 “LSM compaction이 lakehouse compaction을 대신한다”고 쓰면 잘못된 문서가 된다.

## 10. ACID를 페이지와 파일 층으로 다시 분해한다

Atomicity는 transaction의 논리 결과가 전부 보이거나 전부 보이지 않는 규칙이다. Durability는 commit된 결과가 crash 후에도 복구 가능해야 한다는 규칙이다. Isolation은 concurrent transaction이 서로의 중간 상태를 보지 않도록 하는 규칙이다. Consistency는 DB가 정의한 constraint와 application invariant가 transaction 전후에 유지되어야 한다는 규칙이다. WAL은 durability와 recovery에 핵심적이지만, isolation은 MVCC와 lock/protocol이 만든다. B+tree는 빠른 접근 경로이지만, 단독으로 transaction atomicity를 만들지 않는다. Slotted page는 행 배치와 item pointer 안정성을 돕지만, 단독으로 backup 보존을 만들지 않는다. LSM compaction은 오래된 version을 정리하지만, 단독으로 SQL snapshot isolation을 의미하지 않는다.

## 11. 연구 논문을 읽을 때 체크할 질문

논문이 “page”라고 할 때 DB page, OS page, file block 중 무엇을 말하는가? 성능 개선이 buffer pool hit, OS cache hit, 장치 I/O 감소, CPU decode 감소 중 어디에서 오는가? B-tree와 hash 비교가 equality lookup만 보는지, range scan과 order by까지 보는지 확인했는가? WAL latency가 commit ACK 기준인지, data file flush 기준인지, replication durable 기준인지 구분했는가? Snapshot이라는 단어가 MVCC visibility, backup recovery point, Iceberg table version 중 무엇인지 표시했는가? Compaction이 RocksDB SST 병합인지, Iceberg file rewrite인지, Parquet row group 재작성인지 분리했는가? Write amplification을 줄였다는 주장이 read amplification과 space amplification을 어디로 이동시켰는지 확인했는가? 제시된 숫자가 특정 version·hardware·workload의 측정인지, 일반 보장처럼 과장됐는지 확인했는가?

## 12. 복습 문제

1. DB page와 filesystem block, memory page의 차이는 무엇인가?
   - 짧은 답: DB page는 DB가 row/index를 배치하는 논리 단위, filesystem block은 파일 바이트의 저장 배치 단위, memory page는 가상 메모리 주소 변환 단위다.
2. WAL이 commit마다 모든 data page flush를 피하게 해 주는 이유는 무엇인가?
   - 짧은 답: 동기 commit 설정에서는 commit WAL이 durable하면 crash 후 redo로 data page에 빠진 변경을 재적용할 수 있기 때문이다. 단, `synchronous_commit=off`나 `fsync=off`에서는 ACK와 durability의 관계가 약해진다.
3. B-tree가 hash index보다 range query에 자연스러운 이유는 무엇인가?
   - 짧은 답: B-tree leaf는 key order를 유지하고 인접 범위를 따라갈 수 있지만, hash는 equality hash bucket 중심이라 순서를 보존하지 않는다.
4. MVCC snapshot과 Iceberg snapshot을 한 문장으로 구분하라.
   - 짧은 답: MVCC snapshot은 transaction이 볼 row version 규칙이고, Iceberg snapshot은 analytic table의 data/delete file 집합을 가리키는 metadata version이다.
5. RocksDB compaction과 Iceberg compaction을 혼동하면 어떤 잘못된 결론이 나오는가?
   - 짧은 답: storage engine 내부 SST 병합이 table-format manifest와 snapshot commit까지 해결한다고 착각하거나, table file rewrite가 key-value engine의 WAL·memtable 문제를 해결한다고 착각한다.
