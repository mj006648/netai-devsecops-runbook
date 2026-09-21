# 03. HDFS: 분산 파일 시스템의 기본 구조

[학습 목차](README.md) · 이전: 02 · 다음: [04. Ceph와 S3/Object Storage](04-ceph-s3-object-storage.md) · 관련: [Lakehouse 학습 노트](../lakehouse/README.md)

이 문서는 배포 절차가 아니라 박사과정 준비용 학습 노트다. 실제 클러스터 명령, 주소, 계정, 용량 측정값을 제공하지 않는다. 숫자 예제는 모두 설명용 가정이며 특정 NetAI 환경의 실측값이 아니다.

## 1. HDFS를 읽을 때 먼저 버릴 직관

HDFS는 “여러 서버의 디스크를 하나의 큰 POSIX 디스크처럼 붙인 것”이 아니다. 공식 구조 설명은 HDFS가 고장 많은 범용 하드웨어에서 큰 파일을 높은 처리량으로 읽도록 설계됐다고 설명한다. [Apache HDFS
Architecture](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html) POSIX 요구 일부를 완화하고 streaming data access를 우선한다는 점도 같은 문서의 핵심 전제다. [Apache HDFS
Architecture](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Streaming_Data_Access) 따라서 HDFS를 데이터베이스 파일시스템, 일반 사용자 홈 디렉터리, 객체 저장소와 같은 의미로
다루면 안 된다.

처음에는 세 계층을 분리한다.

| 계층 | HDFS에서의 예 | 책임 | 흔한 오해 |
| --- | --- | --- | --- |
| Namespace | `/data/sensor/day=2026-09-21/part-000` | 파일명, 디렉터리, 권한, 파일→블록 매핑 | 파일 내용 bytes도 NameNode에 있다고 착각 |
| Logical block | `blk_...` 같은 HDFS 블록 | 큰 파일을 일정 단위로 나누는 논리 조각 | OS disk block과 같은 크기라고 착각 |
| Replica payload | DataNode 로컬 저장소의 블록 파일 | 실제 bytes와 checksum 저장·전송 | 세 복제본이 하나의 RAID stripe라고 착각 |

## 2. NameNode는 metadata, DataNode는 payload

HDFS 공식 문서는 NameNode가 namespace와 client 접근을 관리하고, DataNode가 저장 장치와 실제 read/write를 담당한다고 설명한다. [NameNode and
DataNodes](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#NameNode_and_DataNodes) NameNode는 `open`, `close`, `rename` 같은 namespace 연산과 블록 위치
결정을 맡는다. DataNode는 client read/write 요청을 처리하고, NameNode 지시에 따라 블록 생성·삭제·복제를 수행한다. 중요한 문장은 “user data never flows through the NameNode”이다. [NameNode and
DataNodes](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#NameNode_and_DataNodes)

ASCII로 쓰면 다음과 같다.

```text
Client
  | 1. open/create: 경로와 권한, 블록 위치 문의
  v
NameNode  ---- metadata ----> namespace, file length, block list, replica locations
  ^
  | heartbeat / block report
  |
DataNode A ---- payload ----> HDFS block replica bytes
DataNode B ---- payload ----> HDFS block replica bytes
DataNode C ---- payload ----> HDFS block replica bytes
```

NameNode가 죽으면 metadata 접근이 막혀 파일을 찾기 어렵다. DataNode가 죽으면 해당 노드에 있던 replica 일부가 사라지지만 다른 replica가 있으면 읽을 수 있다. NameNode metadata의 중요성과 DataNode payload의 중요성은 다른 종류의 중요성이다.

## 3. FsImage, EditLog, BlockReport의 역할

NameNode metadata는 메모리에만 있는 임시 표가 아니다. 공식 문서는 namespace와 file block map이 FsImage에 저장되고, metadata 변경은 EditLog에 기록된다고 설명한다. [Persistence of File System
Metadata](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#The_Persistence_of_File_System_Metadata) checkpoint는 FsImage와 EditLog를 합쳐 일관된
metadata snapshot을 만드는 과정이다. DataNode는 시작할 때 로컬 저장소를 스캔해 자신이 가진 HDFS block 목록을 NameNode에 보고한다. 이 보고가 BlockReport다. [Persistence of File System
Metadata](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#The_Persistence_of_File_System_Metadata)

정리하면 다음과 같다.

| 항목 | 어디에 가까운가 | 담는 정보 |
| --- | --- | --- |
| FsImage | NameNode local persistent state | namespace와 block map의 checkpoint |
| EditLog | NameNode local persistent state | create, delete, replication 변경 같은 metadata transaction |
| BlockReport | DataNode→NameNode 보고 | 이 DataNode가 가진 block replica 목록 |
| Heartbeat | DataNode→NameNode liveness | DataNode가 살아 있고 명령을 받을 수 있음 |

## 4. HDFS block은 OS disk block이 아니다

공식 문서는 HDFS가 파일을 block sequence로 저장하며 block size와 replication factor가 파일 단위로 configurable이라고 말한다. [Data
Replication](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Data_Replication) 여기서 block은 HDFS 논리 블록이다. 디스크의 4 KiB block, filesystem extent,
SSD page와 같은 낮은 계층 단위가 아니다. DataNode는 각 HDFS block을 로컬 파일시스템의 별도 파일로 저장한다. [Persistence of File System
Metadata](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#The_Persistence_of_File_System_Metadata) 그 로컬 파일이 다시 ext4/xfs block, device sector,
SSD page로 나뉘는 것은 HDFS 아래 계층의 일이다.

이 분리를 놓치면 계산이 틀린다.

```text
HDFS logical block size = 128 MiB   # 설명용 설정
Linux filesystem block  = 4 KiB     # 설명용 하위 계층
SSD page / erase block  = 장치별 구현
```

HDFS block 하나가 디스크 block 하나라는 뜻이 아니다. HDFS block 하나는 수많은 OS block과 장치 page 위에 저장될 수 있다. NameNode는 HDFS block 단위의 mapping을 관리한다. OS는 DataNode 로컬 파일을 자신의 방식으로 배치한다.

## 5. 300 MiB 파일, 128 MiB block, replication 3 예제

아래 숫자는 설명용 가정이다. 파일 크기: 300 MiB. HDFS logical block size: 128 MiB. Replication factor: 3.

계산은 다음과 같다.

```text
Block 0: bytes [0, 128 MiB)       = 128 MiB
Block 1: bytes [128, 256 MiB)     = 128 MiB
Block 2: bytes [256, 300 MiB)     = 44 MiB
Logical block count              = 3
Replica count per logical block  = 3
Total block replicas             = 3 logical blocks × 3 = 9 replicas
Payload bytes before overhead    = 300 MiB × 3 = 900 MiB
```

마지막 block은 128 MiB를 꽉 채우지 않는다. 공식 문서도 마지막 block을 제외한 block은 같은 크기이며, append와 hsync 이후 variable length block 관련 설명을 둔다. [Data
Replication](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Data_Replication) 따라서 마지막 44 MiB 논리 block을 “128 MiB 전체가 실제 payload로 채워졌다”고 계산하면
과장된다. 실제 디스크 사용량은 payload 외 checksum, local filesystem metadata, reserved space, replication management 영향을 받는다. 이 예제의 900 MiB는 “사용자 payload 복제량”을 이해하기 위한 단순 계산이다.

가능한 배치 예시는 다음과 같다.

```text
Logical block B0: DN1/rack-a, DN5/rack-b, DN6/rack-b
Logical block B1: DN2/rack-a, DN7/rack-b, DN8/rack-b
Logical block B2: DN3/rack-a, DN5/rack-b, DN9/rack-b
```

HDFS는 같은 block replica를 같은 DataNode에 중복 배치하지 않는다. [Replica
Placement](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Replica_Placement:_The_First_Baby_Steps) 복제본 수는 DataNode 수와 failure domain 조건에도
제약된다.

## 6. Read path: metadata lookup 후 DataNode에서 직접 읽기

HDFS client는 먼저 NameNode에서 파일 metadata와 block 위치를 얻는다. 그 뒤 실제 bytes는 가까운 DataNode replica에서 직접 읽는다. 공식 문서는 client가 NameNode에 metadata나 file modification을 문의하고 실제 I/O는 DataNode와 직접
수행한다고 설명한다. [HDFS User Guide](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HdfsUserGuide.html)

```text
1) Client -> NameNode:
     "경로 /data/sensor/file-1의 block들과 replica 위치는?"

2) NameNode -> Client:
     B0: DN1, DN5, DN6
     B1: DN2, DN7, DN8
     B2: DN3, DN5, DN9

3) Client -> DataNode:
     가까운 replica에서 B0, B1, B2 bytes를 순서대로 읽음

4) Client:
     checksum 검증, 실패 replica 회피, 다음 replica 재시도
```

읽기는 NameNode를 data proxy로 통과하지 않는다. NameNode는 metadata 병목이 될 수 있지만 data bandwidth를 모두 운반하는 장비가 아니다. HDFS는 reader와 가까운 replica를 선호해 global bandwidth와 latency를 줄이려 한다. [Replica
Selection](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Replica_Selection)

## 7. Write path: pipeline, packet, ACK

쓰기에서도 client는 먼저 NameNode와 통신해 파일 생성 권한을 얻고, 쓰기 진행 중 새 HDFS block이 필요해질 때마다 해당 block의 DataNode pipeline을 요청·할당받는다. 그 뒤 해당 block의 bytes는 DataNode pipeline으로 흐른다. 공식 문서는 client가 첫 DataNode에 쓰면 첫 DataNode가 두 번째로 전달하고, 두 번째가 세 번째로 전달하는
pipelining을 설명한다. [Replication Pipelining](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Replication_Pipelining)

```text
Client
  | packet P42
  v
DN1 pipeline 첫 DataNode
  | packet P42
  v
DN2 pipeline middle
  | packet P42
  v
DN3 pipeline tail

ACK path:
DN3 -> DN2 -> DN1 -> Client
```

ACK는 “client가 보낸 packet이 pipeline의 DataNode들에서 처리됐다는 응답”으로 이해한다. ACK가 곧 모든 독자에게 파일 전체가 보인다는 뜻은 아니다. ACK가 곧 모든 과거 block이 영구 저장장치에 fsync됐다는 뜻도 아니다. ACK, visibility, durability는 다른
질문이다.

## 8. ACK, visibility, durability를 구분한다

Hadoop OutputStream 문서는 `hflush()`와 `hsync()`의 의미를 분리한다. [OutputStream, Syncable and
StreamCapabilities](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/filesystem/outputstream.html) `hflush()`는 새 reader가 볼 수 있게 하는 visibility 보장을 목표로 하지만
durability 보장은 아니다. [Syncable.hflush](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/filesystem/outputstream.html#Syncable.hflush()) `hsync()`는 POSIX
`fsync()`와 유사하게 durable storage까지 밀어 넣는 보장을 목표로 한다.
[Syncable.hsync](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/filesystem/outputstream.html#Syncable.hsync())

세 질문을 따로 써야 한다.

| 질문 | 대표 API/사건 | 의미 |
| --- | --- | --- |
| ACK | packet pipeline ACK | pipeline 참여 replica가 특정 packet 처리를 응답 |
| Visibility | `hflush()` 후 새 open | 새 reader가 flushed bytes를 볼 수 있음 |
| Durability | `hsync()` 성공 | 저장소가 durable medium까지 기록했다고 약속 |
| Final metadata | `close()` 후 file status/list | 길이와 mtime 같은 metadata가 최종 상태와 일치 |

공식 문서는 HDFS metadata length가 쓰기 중에 실제 contents보다 늦을 수 있고, close 후에는 metadata가 일치해야 한다고 설명한다. [Consistency and
Visibility](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/filesystem/outputstream.html#Consistency_and_Visibility) 따라서 쓰기 중인 파일의
`getFileStatus().getLen()`만 보고 데이터 가시성을 단정하지 않는다.

## 9. `hflush`, `hsync`, `close` caveat

HDFS에서 `close()`가 성공했다고 모든 상황에서 즉시 disk sync까지 완료됐다고 가정하면 위험하다. Hadoop 문서는 `dfs.datanode.synconclose`가 true가 아니면 close 시 즉시 disk sync하지 않으며, 반드시 durability가 필요하면 close 전에
`hsync()`를 호출해야 한다고 설명한다. [HDFS and
OutputStream.close](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/filesystem/outputstream.html#HDFS_and_OutputStream.close()) 또한 reference
`DFSOutputStream.hsync()`는 현재 block만 실제로 persist하는 caveat를 둔다. [HDFS hsync only syncs latest
block](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/filesystem/outputstream.html#HDFS:_hsync()_only_syncs_the_latest_block)

WAL 같은 구조를 HDFS 위에 만들 때는 특히 조심한다. commit marker 앞의 모든 bytes가 durable해야 한다면 block boundary를 넘는 쓰기와 `SYNC_BLOCK` 같은 생성 flag 의미를 검토해야 한다. 이 문서는 운영 설정을 제안하지 않는다. 핵심은 “flush가 보임, sync가
내구성, close가 최종 metadata”라는 단순식도 구현 caveat를 가진다는 점이다.

## 10. Checksum은 어디에서 작동하는가

HDFS client는 읽은 block 내용이 손상됐는지 checksum으로 검증할 수 있다. 공식 구조 문서는 client가 파일 내용을 만들 때 block checksum을 계산하고, 읽을 때 checksum mismatch가 있으면 다른 replica에서 가져올 수 있다고 설명한다. [Data
Integrity](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Data_Integrity) 이 검사는 “복제본이 3개라서 항상 올바른 값”이라는 가정을 줄여 준다. 하지만 checksum은 잘못된 애플리케이션
데이터나 센서 오류를 고쳐 주지 않는다. `temperature_c=200`이 물리적으로 이상한 값인지 판단하는 것은 HDFS가 아니라 상위 데이터 검증 문제다.

읽기 실패 경로를 단순화하면 다음과 같다.

```text
Client reads B1 from DN2
  -> checksum mismatch
  -> report bad replica / avoid DN2
  -> retry B1 from DN7 or DN8
  -> if checksum ok, application receives bytes
```

Checksum은 byte corruption에 대한 방어다. 비즈니스 의미 검증, schema evolution, 중복 제거는 별도 계층의 문제다.

## 11. Lease와 single writer

HDFS는 전통적으로 write-once-read-many 모델을 중심으로 설계됐다. 공식 문서는 파일이 write-once이며 append와 truncate 예외가 있고, 한 시점에 writer가 하나라고 설명한다. [Data
Replication](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Data_Replication) 이 제약은 높은 처리량과 단순한 coherency model을 위한 설계 선택이다. 동시에 여러 writer가
같은 파일 임의 위치를 고치는 POSIX database workload와는 맞지 않는다.

Lease는 “누가 현재 파일을 쓰는가”를 조정하는 metadata 개념으로 이해한다. Writer가 죽으면 lease recovery가 필요할 수 있다. Lease recovery가 끝나기 전에는 마지막 block 상태와 파일 길이 해석이 애매할 수 있다. 이 영역은 HBase WAL 같은 시스템이 HDFS sync
semantics를 엄격히 보는 이유와 연결된다.

## 12. Rack은 failure boundary이자 비용 boundary

Rack awareness는 단순 위치 라벨이 아니다. 공식 문서는 rack-aware placement가 reliability, availability, network bandwidth utilization을 개선하기 위한 정책이라고 설명한다. [Replica
Placement](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Replica_Placement:_The_First_Baby_Steps) replication factor 3의 일반 정책은 writer local
또는 같은 rack의 replica 하나, 다른 rack의 replica 하나, 같은 remote rack의 또 다른 replica 하나를 둔다. [Replica
Placement](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Replica_Placement:_The_First_Baby_Steps)

이 정책은 세 가지 균형을 잡는다.

```text
쓰기 비용: 모든 replica를 서로 다른 rack에 두면 inter-rack traffic 증가
읽기 비용: reader와 가까운 replica가 있으면 latency와 bandwidth 비용 감소
장애 경계: 한 rack 장애에도 적어도 다른 rack replica를 기대
```

Rack label이 틀리면 장애 경계 계산도 틀린다. 실제로 같은 전원·스위치·랙에 있는 노드를 다른 rack으로 라벨링하면 문서상 내구성은 좋아 보이지만 물리 장애에는 취약하다. 반대로 모든 노드를 같은 rack으로 라벨링하면 정책이 활용할 failure domain 정보가 부족하다.

## 13. Streaming과 append는 random update가 아니다

HDFS는 대용량 파일 streaming read/write에 잘 맞는다. 공식 문서는 batch processing과 high throughput을 강조하고 low latency interactive use를 우선하지 않는다고 설명한다. [Streaming Data
Access](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Streaming_Data_Access) Append는 파일 끝에 덧붙이는 연산이지, 임의 offset update를 일반적으로 제공하는 POSIX
write와 같지 않다. 공식 coherency model도 arbitrary point update는 지원하지 않는다고 말한다. [Simple Coherency
Model](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Simple_Coherency_Model)

센서 로그 예제에서 잘 맞는 패턴은 다음이다.

```text
좋은 패턴:
  hour=10/part-000  append or write once
  hour=11/part-000  write once
  batch job reads large ranges

나쁜 직관:
  one shared file
  many writers update arbitrary records in place
  readers expect POSIX-like immediate coherent random updates
```

이 차이는 [Lakehouse 학습 노트](../lakehouse/README.md)의 table metadata와도 연결된다. HDFS가 bytes를 잘 저장해도 “현재 테이블이 어떤 파일을 읽어야 하는가”는 Iceberg 같은 상위 계층의 문제일 수 있다.

## 14. Small files 문제

HDFS는 큰 파일에 맞춘 설계다. 공식 문서도 typical file size를 gigabytes to terabytes로 설명한다. [Large Data
Sets](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html#Large_Data_Sets) 작은 파일이 많으면 NameNode metadata가 많이 필요하고, 작업 스케줄링·open 비용이 커진다. 100 MiB
파일 하나와 1 KiB 파일 100,000개는 payload 크기가 비슷해도 metadata와 planning 비용이 다르다.

설명용 계산:

```text
Case A: 100 MiB 파일 1개
  HDFS logical blocks: 1개, metadata entry 소수

Case B: 1 KiB 파일 100,000개
  HDFS logical blocks: 파일마다 최소 1개 수준의 추적 필요
  Payload total: 약 100 MiB
  Metadata pressure: 파일 수와 block 수에 비례해 증가
```

이 숫자는 실측이 아니다. 핵심은 payload bytes만 보고 NameNode 부담을 판단하면 안 된다는 점이다.

## 15. HDFS와 object store는 무엇이 다른가

HDFS는 filesystem namespace, block mapping, DataNode pipeline, rack-aware replication을 함께 제공한다. Object store는 key→object bytes API를 중심으로 하고, rename·append·directory semantics가 HDFS와
다르다. S3의 strong consistency는 PUT/DELETE와 GET/LIST 관측에 대한 약속이지 POSIX filesystem 전체를 제공한다는 뜻이 아니다. [Amazon S3 consistency
model](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel)

비교할 때는 다음처럼 질문한다.

| 질문 | HDFS 관점 | Object store 관점 |
| --- | --- | --- |
| 큰 파일 sequential read | 핵심 설계 목표 | Range GET 등으로 가능하지만 API 의미가 다름 |
| append | 제한적으로 지원 | 일반 S3 객체는 전체 객체 PUT/multipart complete 중심 |
| rename | filesystem namespace operation | 보통 copy+delete 계열로 구현 |
| metadata bottleneck | NameNode 중심 | bucket index/catalog/listing 구현별 |
| table commit | 별도 엔진/포맷 필요 | 별도 엔진/포맷 필요 |

“HDFS가 낡았고 S3가 새롭다”처럼 시대 구분으로만 읽지 않는다. 두 시스템은 제공하는 추상화와 실패 경계가 다르다.

## 16. 센서 파일 하나를 따라가 보기

가상 센서 파일 `sensor/day=2026-09-21/hour=10/part-000`이 300 MiB라고 하자. 수집 writer는 파일을 생성한 뒤 첫 block을 쓰기 시작할 때 NameNode에서 그 block의 DataNode pipeline을 받고, block boundary를 지나 다음 block이 필요해질 때마다 다음 pipeline을 다시 요청·할당받는다. 각 block은 packet으로 나뉘어 DataNode pipeline을 통과한다. 각 packet ACK는 tail에서 writer까지 역방향으로 돌아온다. writer가 `hflush()`하면 새 reader가 flushed bytes를 볼 수 있어야 한다. writer가 `hsync()`하면 durable storage까지 기록됐다는 더 강한 약속을 기대하지만
current block caveat를 확인해야 한다. writer가 `close()`하면 파일 metadata 길이와 listing이 최종 상태와 일치해야 한다. 분석 job은 NameNode에서 block locations를 받고 가까운 DataNode replica에서 직접 읽는다. checksum mismatch가
나면 다른 replica로 재시도한다. 이 파일이 Iceberg table에 속하려면 파일 존재와 별도로 table metadata commit이 필요하다.

## 17. 자주 틀리는 말

- “NameNode에 데이터가 저장된다” → metadata를 저장하고 user data는 DataNode payload로 흐른다.
- “128 MiB block이면 마지막 block도 128 MiB 디스크를 먹는다” → 마지막 logical block payload는 작을 수 있다.
- “replication 3이면 rack 3개에 자동 분산된다” → 기본 정책은 보통 두 rack에 배치할 수 있고 rack awareness가 정확해야 한다.
- “ACK를 받았으니 SQL에서 보인다” → packet ACK, HDFS visibility, table commit visibility는 다르다.
- “`flush()`는 `hsync()`와 같다” → Hadoop Syncable 문서는 visibility와 durability를 구분한다.
- “HDFS append는 임의 레코드 update다” → append는 끝에 덧붙이는 모델이며 arbitrary point update와 다르다.
- “Object store는 HDFS의 새 이름이다” → API와 consistency, rename, append, metadata model이 다르다.

## 18. 복습 질문

**질문 1.** NameNode와 DataNode의 책임을 한 문장씩 말하라.

짧은 답: NameNode는 namespace와 block 위치 같은 metadata를 관리하고, DataNode는 실제 block replica bytes를 저장·전송한다.

**질문 2.** 300 MiB 파일, 128 MiB HDFS block, replication 3이면 logical block과 replica는 몇 개인가?

짧은 답: logical block은 128 MiB, 128 MiB, 44 MiB의 3개이고 replica는 3×3=9개다.

**질문 3.** `hflush()`와 `hsync()`의 핵심 차이는 무엇인가?

짧은 답: `hflush()`는 새 reader visibility를, `hsync()`는 visibility에 더해 durable storage 기록을 목표로 한다.

**질문 4.** Rack awareness가 잘못되면 왜 위험한가?

짧은 답: HDFS가 의존하는 failure domain 정보가 틀려서 같은 물리 장애에 여러 replica가 함께 사라질 수 있다.

**질문 5.** HDFS 파일이 존재하면 Iceberg table에 자동으로 반영되는가?

짧은 답: 아니다. 파일 bytes 저장과 table metadata commit은 별도 계층의 문제다.

## 19. 확인한 주요 원문

- Apache Hadoop, [HDFS Architecture](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html).
- Apache Hadoop, [HDFS User Guide](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HdfsUserGuide.html).
- Apache Hadoop, [OutputStream, Syncable and StreamCapabilities](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/filesystem/outputstream.html).
- AWS, [Amazon S3 data consistency model](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel).
- 로컬 배경: [Lakehouse와 Open Table Format 학습 노트](../lakehouse/README.md).
