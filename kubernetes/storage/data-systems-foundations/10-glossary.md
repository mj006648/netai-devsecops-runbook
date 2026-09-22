# 10. 데이터 시스템 밑바닥 용어집

[학습 목차](README.md) · 기초: [계층 지도와 기초 용어](00-map-and-vocabulary.md) · 실습: [안전한 로컬 실습](08-guided-labs.md)

작성·근거 확인일: **2026-09-22**.

이 문서는 본문을 대신하는 요약본이 아니라 **찾아보기 사전**이다. 모르는 단어를 만났을 때 먼저 한 문장으로 감을 잡고, 어느 계층의 말인지 확인한 뒤, 연결된 장으로 돌아가 자세한 흐름을 읽는다.

표의 “full name”은 널리 쓰이는 약어의 풀네임만 적었다. `bit`, `byte`, `Parquet`, `Arrow`, `Iceberg`, `Bloom`처럼 이름 자체이거나 사람 이름에서 온 용어는 억지로 풀어 쓰지 않는다.

## 바이트·파일·Linux I/O

| 용어 | full name | 쉬운 정의 | 계층·owner | 혼동 금지 | 더 읽기 |
| --- | --- | --- | --- | --- | --- |
| bit | 이름 자체 | 0 또는 1 하나를 나타내는 가장 작은 이진 자리다. | 표현 단위 | byte와 같지 않다. | [00](00-map-and-vocabulary.md), [00a](00a-bytes-payload-and-packets.md) |
| byte | 이름 자체 | 보통 8bit를 묶은 단위이며 파일·네트워크 API가 주로 다루는 크기 단위다. | 표현·I/O 단위 | 문자 한 개와 항상 같지 않다. | [00a](00a-bytes-payload-and-packets.md), [01](01-linux-read-write.md) |
| offset | 이름 자체 | 시작점에서 몇 byte 떨어졌는지 나타내는 위치값이다. | 파일·메모리·프로토콜 공통 | 행 번호나 block 번호와 같지 않다. | [00](00-map-and-vocabulary.md), [01](01-linux-read-write.md) |
| fd | file descriptor | 프로세스가 열린 파일·파이프·소켓 등을 가리킬 때 쓰는 작은 정수 핸들이다. | Linux process fd table | 파일 이름, inode, 디스크 주소가 아니다. | [01](01-linux-read-write.md) |
| OFD | open file description | 커널 안의 열린 파일 상태로 offset과 file status flag를 담는다. | Linux 열린 파일 테이블 | fd 번호 자체와 다르며 `dup()` 뒤 공유될 수 있다. | [01](01-linux-read-write.md) |
| inode | index node | 파일 종류·권한·크기·데이터 위치 같은 파일 본체 metadata를 담는 객체다. | 파일시스템 | 파일 이름은 보통 directory entry에 있다. | [02](02-filesystems-block-devices.md) |
| dentry | directory entry cache/object | 경로 이름 lookup 결과를 표현하고 cache하는 VFS 객체다. | Linux VFS | 파일 내용 cache인 page cache와 다르다. | [02](02-filesystems-block-devices.md) |
| VFS | Virtual File System | 여러 파일시스템을 공통 객체와 연산으로 연결하는 Linux 계층이다. | Linux 커널 파일시스템 계층 | ext4나 XFS 같은 개별 파일시스템 자체가 아니다. | [01](01-linux-read-write.md), [02](02-filesystems-block-devices.md) |
| page | memory/page-cache page | 메모리 관리나 page cache에서 쓰는 고정 크기 범위다. | Linux 메모리·page cache | DB page, Parquet page, SSD page와 다르다. | [01](01-linux-read-write.md), [02](02-filesystems-block-devices.md) |
| folio | 이름 자체 | Linux 커널에서 하나 이상의 page를 묶어 다루는 메모리 관리 단위다. | Linux 메모리 관리 | 초보 단계에서는 page와 완전히 같은 말로 외우지 않는다. | [01](01-linux-read-write.md) |
| cache | 이름 자체 | 다시 쓸 가능성이 있는 데이터를 빠른 곳에 보관하는 구조다. | 모든 계층 | buffer, queue, 영구 저장과 다르다. | [00](00-map-and-vocabulary.md), [07](07-measurement-and-paper-reading.md) |
| dirty | 이름 자체 | 메모리의 내용이 하위 저장소보다 최신이라 아직 내려써야 하는 상태다. | page cache·DB buffer | “더럽다”는 오류가 아니라 미반영 변경 상태다. | [01](01-linux-read-write.md), [05](05-database-pages-wal-indexes.md) |
| writeback | 이름 자체 | dirty 데이터를 파일시스템·block 계층을 통해 하위 저장소로 내보내는 작업이다. | Linux VM·파일시스템 | `write()` syscall 반환과 같은 시점이 아닐 수 있다. | [01](01-linux-read-write.md), [02](02-filesystems-block-devices.md) |
| flush | 이름 자체 | 위 계층의 buffer나 장치 cache에 있던 작업을 아래로 밀어내라고 요청하는 동작이다. | 런타임·파일시스템·장치 | `fsync()`와 같은 보장을 항상 뜻하지 않는다. | [01](01-linux-read-write.md), [02](02-filesystems-block-devices.md) |
| fsync | file synchronize | 파일 데이터와 필요한 metadata를 안정 저장 계층으로 동기화하도록 요청하고 기다리는 syscall이다. | Linux 파일 I/O | 파일 이름이 담긴 directory entry까지 항상 대신 보장하지 않는다. | [01](01-linux-read-write.md) |
| fdatasync | file data synchronize | 파일 데이터와 이후 읽기에 필요한 metadata 중심으로 동기화하는 syscall이다. | Linux 파일 I/O | 모든 metadata 변경을 `fsync()`와 똑같이 다룬다고 보면 안 된다. | [01](01-linux-read-write.md) |
| mmap | memory map | 파일이나 anonymous memory를 프로세스 가상 주소 공간에 mapping하는 기능이다. | Linux memory·file I/O | I/O 비용이나 동기화 필요가 사라진다는 뜻이 아니다. | [01](01-linux-read-write.md), [08](08-guided-labs.md) |
| COW | Copy-on-Write | 읽는 동안 공유하다가 누군가 쓰려 할 때 사본을 만들어 분리하는 방식이다. | 메모리·파일시스템 | 처음부터 전체 복사하는 deep copy와 다르다. | [01](01-linux-read-write.md), [02](02-filesystems-block-devices.md) |
| O_DIRECT | open flag name | page cache 효과를 최소화하려고 직접 I/O를 시도하는 Linux open flag다. | Linux 파일 I/O | 비동기 I/O나 정전 내구성을 자동 제공하지 않는다. | [01](01-linux-read-write.md) |
| io_uring | 이름 자체 | submission queue와 completion queue로 많은 I/O 요청을 효율적으로 제출·수확하는 Linux 비동기 I/O 인터페이스다. | Linux I/O API | 제출 성공과 I/O 완료 성공은 다르다. | [01](01-linux-read-write.md) |

## 파일시스템·블록 장치·SSD

| 용어 | full name | 쉬운 정의 | 계층·owner | 혼동 금지 | 더 읽기 |
| --- | --- | --- | --- | --- | --- |
| block | 이름 자체 | 어떤 계층이 데이터를 나누어 다루는 덩어리이며, 계층 이름을 붙여야 정확하다. | 파일시스템·장치·HDFS 등 | filesystem block, device sector, HDFS block은 서로 다르다. | [00](00-map-and-vocabulary.md), [02](02-filesystems-block-devices.md) |
| sector | 이름 자체 | block device가 다루는 전통적 작은 주소 지정 단위다. | 저장장치 인터페이스 | 파일시스템 block과 크기·역할이 같다고 단정하지 않는다. | [02](02-filesystems-block-devices.md) |
| LBA | Logical Block Address | block device에 제시하는 논리 block 주소다. | block device | SSD 내부 NAND 물리 주소가 아니다. | [02](02-filesystems-block-devices.md) |
| extent | 이름 자체 | “논리 block 몇 개가 물리 block 어디부터 연속된다”를 나타내는 구간 매핑이다. | 파일시스템 | SSD 내부 물리 연속성을 뜻하지 않는다. | [02](02-filesystems-block-devices.md) |
| superblock | 이름 자체 | 파일시스템 전체 규칙과 주요 위치를 담는 핵심 metadata다. | 파일시스템 | 일반 파일의 데이터 block이 아니다. | [02](02-filesystems-block-devices.md) |
| bitmap | 이름 자체 | block이나 inode가 사용 중인지 bit 배열로 표시하는 구조다. | 파일시스템 공간 관리 | 이미지 파일 형식 BMP와 문맥이 다르다. | [02](02-filesystems-block-devices.md) |
| journal | 이름 자체 | crash 중간 상태를 복구하기 위해 변경 기록을 먼저 남기는 파일시스템 로그다. | 파일시스템 | DB transaction WAL과 보호 대상이 다르다. | [02](02-filesystems-block-devices.md), [05](05-database-pages-wal-indexes.md) |
| WAL | Write-Ahead Log | 데이터 페이지 변경 전에 복구용 로그를 먼저 안정 저장하는 기법이다. | 데이터베이스·저장 엔진 | 파일시스템 journal을 그대로 대체하지 않는다. | [05](05-database-pages-wal-indexes.md) |
| FTL | Flash Translation Layer | SSD가 host LBA를 내부 NAND 위치로 다시 mapping하는 계층이다. | SSD firmware | 파일시스템 extent mapping과 다르다. | [02](02-filesystems-block-devices.md) |
| GC | Garbage Collection | SSD나 LSM 등에서 더 이상 유효하지 않은 조각을 정리해 공간을 회수하는 작업이다. | SSD·저장 엔진 | 프로그래밍 언어 메모리 GC와 문맥을 구분한다. | [02](02-filesystems-block-devices.md), [05](05-database-pages-wal-indexes.md) |
| TRIM | command name | OS가 SSD에 특정 LBA 범위가 더 이상 필요 없다고 알려 주는 명령 계열이다. | block device·SSD | 데이터를 즉시 안전 삭제했다는 보장이 아니다. | [02](02-filesystems-block-devices.md) |
| PLP | Power-Loss Protection | 전원 손실 때 장치 내부 volatile 상태를 보호하도록 설계된 장치 특성이다. | 저장장치 하드웨어 | `fsync()` 호출 자체와 같은 말이 아니다. | [02](02-filesystems-block-devices.md) |
| IOPS | I/O Operations Per Second | 초당 완료되는 I/O 작업 수를 나타내는 처리량 지표다. | 성능 측정 | bytes/s나 지연시간과 같은 지표가 아니다. | [07](07-measurement-and-paper-reading.md) |
| queue | 이름 자체 | 처리할 요청을 대기시키고 순서를 관리하는 구조다. | block layer·네트워크·런타임 | cache나 buffer와 목적이 다르다. | [00](00-map-and-vocabulary.md), [02](02-filesystems-block-devices.md) |
| throughput | 이름 자체 | 단위 시간에 처리한 작업량이나 byte 양이다. | 성능 측정 | 한 요청의 latency와 다르다. | [07](07-measurement-and-paper-reading.md) |
| p99 | 99th percentile | 관측값 99%가 이 값 이하가 되도록 자른 백분위 지연 지표다. | 성능 측정 | 평균 latency와 다르며 tail 문제를 드러낸다. | [07](07-measurement-and-paper-reading.md) |

## HDFS

| 용어 | full name | 쉬운 정의 | 계층·owner | 혼동 금지 | 더 읽기 |
| --- | --- | --- | --- | --- | --- |
| HDFS | Hadoop Distributed File System | 큰 파일을 여러 DataNode에 block과 replica로 나누어 저장하는 Hadoop의 분산 파일시스템이다. | 분산 파일시스템 | POSIX 로컬 디스크를 그대로 여러 대에 붙인 것이 아니다. | [03](03-hdfs-distributed-files.md) |
| replica | 이름 자체 | 같은 HDFS block bytes를 여러 노드나 failure domain에 둔 사본이다. | HDFS payload 복제 | backup이나 snapshot과 같은 시점 복구가 아니다. | [03](03-hdfs-distributed-files.md) |
| NameNode | 이름 자체 | HDFS namespace와 file-to-block metadata를 관리하는 master 역할이다. | HDFS metadata | 사용자 payload bytes가 항상 NameNode를 통과하는 것은 아니다. | [03](03-hdfs-distributed-files.md) |
| DataNode | 이름 자체 | HDFS block replica bytes를 저장하고 client read/write에 참여하는 worker 노드다. | HDFS payload 저장 | metadata 전체를 결정하는 주체가 아니다. | [03](03-hdfs-distributed-files.md) |
| ACK | Acknowledgement | 요청의 특정 단계가 처리됐다고 되돌아오는 응답이다. | 네트워크·분산 저장 | 전체 파일 commit, table commit, 정전 내구성과 자동으로 같지 않다. | [00a](00a-bytes-payload-and-packets.md), [03](03-hdfs-distributed-files.md) |
| hflush | HDFS API name | HDFS output stream의 현재 buffered 데이터를 DataNode pipeline으로 밀어내 visible하게 만드는 동기화 계열 호출이다. | HDFS client/write pipeline | 모든 DataNode 디스크 내구성을 `hsync`처럼 보장한다고 보면 안 된다. | [03](03-hdfs-distributed-files.md) |
| hsync | HDFS API name | HDFS에서 더 강한 sync 의미로 데이터가 storage device에 동기화되도록 요구하는 계열 호출이다. | HDFS client/write pipeline | 로컬 POSIX `fsync()`와 구현·범위가 완전히 같다고 단정하지 않는다. | [03](03-hdfs-distributed-files.md) |

## Ceph·S3·Kubernetes 저장소

| 용어 | full name | 쉬운 정의 | 계층·owner | 혼동 금지 | 더 읽기 |
| --- | --- | --- | --- | --- | --- |
| RADOS | Reliable Autonomic Distributed Object Store | Ceph의 핵심 분산 object 저장 엔진이다. | Ceph 내부 저장 계층 | S3 API object와 1:1이라고 보면 안 된다. | [04](04-ceph-s3-object-storage.md) |
| OSD | Object Storage Daemon | Ceph에서 디스크나 block device를 맡아 object 저장·복구에 참여하는 daemon이다. | Ceph storage daemon | S3 object 하나를 뜻하지 않는다. | [04](04-ceph-s3-object-storage.md) |
| PG | Placement Group | Ceph object들을 배치·복구 단위로 묶는 shard다. | Ceph RADOS 배치 | Kubernetes Pod group 같은 것이 아니다. | [04](04-ceph-s3-object-storage.md) |
| CRUSH | Controlled Replication Under Scalable Hashing | Ceph가 topology와 rule을 이용해 object 위치를 계산하는 배치 알고리즘이다. | Ceph placement | 중앙 lookup table을 매번 조회하는 방식으로만 이해하면 안 된다. | [04](04-ceph-s3-object-storage.md) |
| EC | Erasure Coding | 데이터를 여러 data/parity 조각으로 나누어 일부 손실을 복구하게 하는 방식이다. | 분산 저장 내구성 | replication과 비용·복구·쓰기 특성이 다르다. | [04](04-ceph-s3-object-storage.md) |
| S3 | Simple Storage Service | bucket과 key로 object를 PUT/GET하는 object storage API 계열이다. | object storage API | POSIX 파일시스템의 부분 덮어쓰기와 다르다. | [04](04-ceph-s3-object-storage.md) |
| bucket | 이름 자체 | S3 object들이 속하는 최상위 container 이름 공간이다. | S3/object storage | POSIX directory와 같은 rename/permission 규칙을 가정하지 않는다. | [04](04-ceph-s3-object-storage.md) |
| key | 이름 자체 | bucket 안에서 object를 식별하는 문자열 이름이다. | S3/object storage | `/`가 들어가도 실제 디렉터리 tree라는 뜻은 아니다. | [04](04-ceph-s3-object-storage.md) |
| PV | PersistentVolume | Kubernetes 클러스터에 제공된 저장 볼륨 자원을 나타내는 API 객체다. | Kubernetes storage API | 실제 디스크나 Ceph pool 자체와 다르다. | [04](04-ceph-s3-object-storage.md) |
| PVC | PersistentVolumeClaim | Pod가 필요한 저장소를 요청하는 Kubernetes API 객체다. | Kubernetes storage API | 저장 엔진이 아니라 요청·바인딩 객체다. | [04](04-ceph-s3-object-storage.md) |
| CSI | Container Storage Interface | Kubernetes 같은 orchestrator가 외부 storage driver와 통신하는 표준 인터페이스다. | Kubernetes/storage driver 경계 | 파일시스템이나 block device 그 자체가 아니다. | [04](04-ceph-s3-object-storage.md) |

## 데이터베이스·로그·인덱스

| 용어 | full name | 쉬운 정의 | 계층·owner | 혼동 금지 | 더 읽기 |
| --- | --- | --- | --- | --- | --- |
| transaction | 이름 자체 | 여러 읽기·쓰기 작업을 하나의 논리적 작업 단위로 다루는 DB 개념이다. | 데이터베이스 | 파일 하나의 `write()` 호출과 다르다. | [05](05-database-pages-wal-indexes.md) |
| ACID | Atomicity, Consistency, Isolation, Durability | transaction이 가져야 할 대표 성질 네 가지를 묶은 약어다. | 데이터베이스 transaction | 파일시스템 journal만으로 자동 충족되지 않는다. | [05](05-database-pages-wal-indexes.md) |
| MVCC | Multi-Version Concurrency Control | 여러 row version을 유지해 reader와 writer의 충돌을 줄이는 동시성 제어 방식이다. | 데이터베이스 concurrency | 파일 버전관리나 snapshot backup과 같지 않다. | [05](05-database-pages-wal-indexes.md) |
| B+tree | B+ tree | 정렬된 key를 tree 구조로 관리해 point lookup과 range scan을 돕는 index 구조다. | 데이터베이스 index | hash index처럼 equality만 보는 구조와 다르다. | [05](05-database-pages-wal-indexes.md) |
| LSM | Log-Structured Merge-tree | 쓰기를 log처럼 받아 여러 sorted run으로 만들고 compaction으로 합치는 저장 구조다. | 데이터베이스·KV 저장 엔진 | B+tree의 제자리 page update 방식과 다르다. | [05](05-database-pages-wal-indexes.md) |
| SST | Sorted String Table / SSTable | key 순서로 정렬된 immutable table file을 가리키는 LSM 계열 용어다. | LSM 저장 파일 | 일반 CSV table이나 SQL table과 다르다. | [05](05-database-pages-wal-indexes.md) |
| Bloom | Bloom filter | 어떤 key가 없다는 것을 빠르게 말해 줄 수 있는 probabilistic filter다. | index 보조 구조 | 있을 수 있다는 답은 false positive일 수 있다. | [05](05-database-pages-wal-indexes.md) |
| LSN | Log Sequence Number | WAL이나 log 안의 위치와 순서를 나타내는 번호다. | 데이터베이스 log | wall-clock time이나 file offset과 같지 않다. | [05](05-database-pages-wal-indexes.md) |
| checkpoint | 이름 자체 | 특정 시점까지의 dirty page와 log 상태를 복구 기준점으로 정리하는 작업이다. | 데이터베이스·파일시스템 metadata | backup snapshot과 같은 말이 아니다. | [05](05-database-pages-wal-indexes.md), [03](03-hdfs-distributed-files.md) |

## Parquet·Arrow·Iceberg

| 용어 | full name | 쉬운 정의 | 계층·owner | 혼동 금지 | 더 읽기 |
| --- | --- | --- | --- | --- | --- |
| Parquet | Apache Parquet | columnar 분석 파일 형식으로 row group, column chunk, page, footer metadata를 사용한다. | 파일 포맷 | DB table format이나 memory layout 자체가 아니다. | [06](06-parquet-arrow-iceberg.md) |
| Arrow | Apache Arrow | in-memory columnar data layout과 관련 IPC/라이브러리 생태계다. | 메모리 포맷·실행 엔진 경계 | Parquet 같은 저장 파일 포맷과 다르다. | [06](06-parquet-arrow-iceberg.md) |
| row group | 이름 자체 | Parquet 파일 안에서 여러 row를 묶은 큰 수평 partition 단위다. | Parquet file layout | HDFS block이나 DB page와 다르다. | [06](06-parquet-arrow-iceberg.md) |
| page (Parquet) | 이름 자체 | Parquet column chunk 안의 encoding·compression 단위다. | Parquet file layout | OS memory page나 filesystem block과 다르다. | [06](06-parquet-arrow-iceberg.md) |
| Iceberg | Apache Iceberg | 여러 data file을 snapshot과 metadata로 묶어 table처럼 관리하는 open table format이다. | table format | Parquet 파일 하나나 object store 자체가 아니다. | [06](06-parquet-arrow-iceberg.md) |
| manifest | 이름 자체 | Iceberg에서 data/delete file 목록과 통계를 담는 metadata 파일 계층이다. | Iceberg metadata | 실제 data file payload와 다르다. | [06](06-parquet-arrow-iceberg.md) |
| snapshot | 이름 자체 | Iceberg table의 특정 시점 상태를 가리키는 metadata 참조다. | Iceberg table state | storage volume snapshot이나 backup과 같은 뜻으로 쓰면 안 된다. | [06](06-parquet-arrow-iceberg.md) |
| catalog | 이름 자체 | table 이름이 현재 metadata 위치를 가리키도록 관리하는 서비스나 저장소다. | Iceberg/엔진 metadata | data file 목록 전체를 직접 저장하는 곳으로 단정하지 않는다. | [06](06-parquet-arrow-iceberg.md) |
| commit | 이름 자체 | 새 table metadata를 현재 상태로 게시하는 원자적 갱신 절차다. | Iceberg catalog·DB transaction | 파일 쓰기 완료나 S3 PUT 완료와 다르다. | [06](06-parquet-arrow-iceberg.md), [05](05-database-pages-wal-indexes.md) |

## 읽는 법

1. 모르는 단어를 찾고 “계층·owner”를 먼저 본다.
2. “혼동 금지”에 적힌 다른 계층의 단어와 섞지 않는다.
3. 연결된 장으로 가서 예제와 시간표를 읽는다.
4. 실험이나 논문에서 이 단어를 쓰려면 “누가 성공을 응답했는가, 어느 byte 범위인가, crash 뒤 무엇을 보장하는가”를 함께 적는다.

## 근거와 더 읽을 자료

- [Linux I/O](01-linux-read-write.md): fd, OFD, page cache, dirty/writeback, fsync, mmap, O_DIRECT, io_uring.
- [파일시스템·블록 장치·SSD](02-filesystems-block-devices.md): inode, dentry, extent, journal, FTL, queue, flush/FUA.
- [HDFS](03-hdfs-distributed-files.md): NameNode, DataNode, replica, ACK, hflush, hsync.
- [Ceph·S3·Kubernetes 저장소](04-ceph-s3-object-storage.md): RADOS, OSD, PG, CRUSH, EC, S3, PV/PVC/CSI.
- [DB 페이지·WAL·인덱스](05-database-pages-wal-indexes.md): transaction, ACID, MVCC, B+tree, LSM, SST, Bloom filter, LSN, checkpoint.
- [Parquet·Arrow·Iceberg](06-parquet-arrow-iceberg.md): Parquet, Arrow, row group, page, Iceberg manifest/snapshot/catalog/commit.
- [성능 측정](07-measurement-and-paper-reading.md): IOPS, throughput, queue, p99와 측정 해석.
