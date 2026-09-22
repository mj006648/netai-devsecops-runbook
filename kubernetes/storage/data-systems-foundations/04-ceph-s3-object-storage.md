# 04. Ceph와 S3/Object Storage: RADOS부터 Table Metadata까지

[학습 목차](README.md) · 이전: [03. HDFS](03-hdfs-distributed-files.md) · 관련: [Lakehouse 학습 노트](../lakehouse/README.md)

이 문서는 배포 runbook이 아니라 박사과정 준비용 학습 노트다. 실제 Ceph 또는 AWS 계정에 접속하는 명령, 주소, credential, bucket 이름을 쓰지 않는다. 숫자와 경로는 모두 설명용 가정이며 특정 클러스터 실측값이 아니다. Kubernetes PV/PVC/CSI는 이 장에서 “storage
engine”이 아니라 연결 API로만 다룬다.

## 1. 먼저 Ceph의 계층을 분리한다

Ceph는 block, file, object interface를 한 시스템에서 제공하지만 모든 것이 같은 API라는 뜻은 아니다. 공식 architecture 문서는 Ceph Storage Cluster가 RADOS를 기반으로 하고, RBD·RGW·CephFS 같은 client interface가 그 위에 얹힌다고
설명한다. [Ceph Architecture](https://docs.ceph.com/en/reef/architecture/)

| 계층 | 대표 이름 | 사용자에게 보이는 추상화 | 내부 책임 |
| --- | --- | --- | --- |
| RADOS | pool, object, PG, OSD, CRUSH | librados object API | 객체 배치, 복제/EC, 복구, 재배치 |
| RBD | Ceph Block Device | block device image | image를 여러 RADOS object로 stripe |
| CephFS | POSIX-like filesystem | directory, file, inode | MDS metadata + RADOS file data |
| RGW | RADOS Gateway | S3/Swift HTTP object API | bucket/object API를 RADOS object로 변환 |
| Kubernetes | PV, PVC, StorageClass, CSI | Pod가 mount/use 하는 volume | 외부 storage driver 호출과 lifecycle 관리 |

RBD, CephFS, RGW는 서로 대체 가능한 “세 이름”이 아니다. RBD는 VM disk나 Kubernetes block/filesystem volume에 가까운 interface다. CephFS는 shared filesystem semantics를 제공하려고 MDS를 둔다. RGW는 HTTP object API와
bucket index, auth, access control을 제공한다.

초기 용어를 더 낮은 층에서 고정한다.

| 용어 | 뜻 | 처음 보는 사람을 위한 해석 |
| --- | --- | --- |
| RADOS | Ceph storage cluster의 핵심 object store | Ceph 내부의 실제 저장·복제·복구 엔진 |
| Pool | RADOS object가 들어가는 논리 저장 공간 | replication/EC, CRUSH rule 같은 정책 묶음 |
| PG | Placement Group | object들을 너무 잘게 직접 배치하지 않도록 묶는 shard |
| OSD | Object Storage Daemon | 디스크/블록 장치를 맡아 object를 저장하고 복구에 참여하는 daemon |
| CRUSH | 배치 계산 알고리즘과 topology map | 중앙 lookup table 대신 규칙과 지도에서 위치를 계산하는 방식 |
| Acting set | 특정 PG를 현재 담당하는 OSD 집합 | client write/read와 recovery가 실제로 만나는 OSD들 |
| Primary OSD | acting set에서 client 요청 조정 역할을 맡은 OSD | 모든 데이터를 혼자 저장한다는 뜻은 아니다 |

비유하면 RADOS는 창고 회사, pool은 보관 정책이 정해진 구역, PG는 화물 묶음, OSD는 실제 창고 칸, CRUSH는 어느 칸에 둘지 정하는 지도와 규칙이다. 이 비유의 한계는 Ceph가 정적 창고 목록을 사람이 매번 조회하는 구조가 아니라, client와 daemon이 cluster map을 보고 같은 결론을 계산한다는 점이다.

## 2. RADOS object는 S3 object와 같지 않다

Ceph 공식 문서는 S3/Swift API object가 Ceph Storage Cluster의 RADOS object와 반드시 1:1 대응하지 않는다고 설명한다. [Ceph Object Storage](https://docs.ceph.com/en/reef/architecture/#ceph-object-storage)
큰 S3 object 하나는 여러 RADOS object로 mapping될 수 있다. RBD image도 여러 RADOS object로 striping된다. [Ceph Block Device](https://docs.ceph.com/en/reef/architecture/#ceph-block-device) CephFS
file data도 RADOS object로 mapping된다. [Ceph File System](https://docs.ceph.com/en/reef/architecture/#ceph-file-system)

따라서 “object”라는 단어를 볼 때마다 어느 계층의 object인지 묻는다.

```text
S3 API object:
  key = raw/2026/09/21/sensor-A.bin
  body = HTTP PUT payload

RGW internal representation:
  bucket index entry
  head object
  optional tail objects

RADOS object:
  pool 안의 flat object id
  PG로 mapping되고 OSD set에 저장됨
```

같은 bytes라도 API boundary가 다르면 consistency, listing, auth, metadata 책임이 달라진다.

## 3. Object → PG → OSD 흐름

Ceph data placement 문서는 pool, placement group, CRUSH map이 object placement의 핵심이라고 설명한다. [Data Placement Overview](https://docs.ceph.com/en/reef/rados/operations/data-placement/)
PG는 pool 안에서 object들을 묶어 OSD에 배치하는 shard다. [Placement Groups](https://docs.ceph.com/en/latest/rados/operations/placement-groups/) CRUSH는 cluster topology와 failure domain을 사용해
object replica 또는 chunk를 어디에 둘지 계산한다. [Ceph Architecture](https://docs.ceph.com/en/reef/architecture/)

ASCII로 쓰면 다음과 같다.

```text
Client write "object X" to pool P
  |
  v
Hash(object id) + pool id
  |
  v
Placement Group PG 12.a
  |
  v
CRUSH rule chooses acting set
  |
  +--> OSD.3 on host h1 / rack r1
  +--> OSD.8 on host h5 / rack r2
  +--> OSD.11 on host h6 / rack r2
```

Client는 monitor에서 cluster map을 받아 placement를 계산할 수 있다. 중앙 metadata server가 모든 data I/O 경로에 반드시 끼어드는 구조가 아니다. Ceph는 OSD들이 peering, recovery, backfill 같은 작업을 수행하며 동적으로 균형을 맞춘다.

## 4. Failure domain은 CRUSH rule의 일부다

Failure domain은 “어떤 단위가 함께 망가질 수 있는가”라는 모델이다. 예시는 disk, OSD, host, chassis, rack, room, datacenter다. CRUSH map은 topology를 담고, CRUSH rule은 replica나 EC chunk를 어느 failure domain에 분산할지
정한다. 공식 문서는 CRUSH가 single point of failure와 bottleneck을 피하도록 물리 topology를 사용한다고 설명한다. [Data Placement Overview](https://docs.ceph.com/en/reef/rados/operations/data-placement/)

설명용 예제:

```text
pool size = 3
failure domain = host
object X replicas = OSD.1(host A), OSD.5(host B), OSD.9(host C)

host A failure:
  replica 1개 손실
  host B/C replica로 read 가능
  recovery가 새 host D에 3번째 replica를 다시 만듦
```

만약 host A와 host B가 실제로 같은 전원 PDU와 top-of-rack switch를 공유하는데 CRUSH에는 다른 rack처럼 표시돼 있으면 장애 모델이 거짓이 된다. 반대로 좋은 CRUSH rule도 OSD 수와 rack 수가 부족하면 원하는 분산을 완전히 만족할 수 없다.

## 5. Replication과 Erasure Coding은 비용 함수가 다르다

Replicated pool은 object를 여러 OSD에 복사한다. Ceph pool 문서는 일반적으로 `size=3`이면 각 RADOS object를 세 replica로 저장한다고 설명한다. [Pools](https://docs.ceph.com/en/reef/rados/operations/pools/)
Erasure-coded pool은 data chunks `k`와 coding chunks `m`으로 나눠 일부 chunk 손실을 복구한다. [Erasure code profiles](https://docs.ceph.com/en/reef/rados/operations/erasure-code-profile/)

설명용 계산:

```text
사용자 데이터 1 TiB

Replication size=3:
  raw payload ≈ 3 TiB
  tolerate model: replica 위치와 failure overlap에 의존

EC k=4, m=2:
  chunks = 6
  overhead factor = (4+2)/4 = 1.5
  raw payload ≈ 1.5 TiB
  tolerate model: 2 chunk loss까지 복구 가능하다는 설계
```

이 계산은 단순 payload overhead다. 실제 비용에는 small write amplification, CPU, network, recovery, latency, metadata pool, BlueStore overhead가 붙는다. EC는 “공짜로 같은 내구성을 더 싸게”가 아니다. RGW의 큰
immutable-ish object와 RBD/CephFS small random write는 비용 곡선이 다르다.

`k=4, m=2` EC를 object 하나로 더 자세히 풀면 다음과 같다. Ceph EC 문서는 `k` data chunks와 `m` coding chunks를 사용해 `m`개 OSD 손실까지 견딜 수 있는 형식을 설명한다. [Erasure code](https://docs.ceph.com/en/reef/rados/operations/erasure-code/)

```text
------------- logical object 256 MiB -------------+
---64MiB---+---64MiB---+---64MiB---+---64MiB---+
 data D0   + data D1   + data D2   + data D3   +

 coding C0 + coding C1                              # parity/equation chunks

 total chunks = 6
 raw bytes    = 6 × 64 MiB = 384 MiB
 overhead     = 384 / 256 = 1.5x
 can recover  = any 4 of 6 chunks are enough, assuming failures match the model
```

여기서 “any 4 of 6”은 수학적 EC 조건을 단순화한 설명이다. 실제 장애 허용은 CRUSH failure domain, OSD 상태, recovery 중 추가 장애, `min_size`, client timeout, scrub 발견 시점에 영향을 받는다. 또 4 KiB 작은 overwrite가 들어오면 필요한 chunk 읽기, 새 coding chunk 계산, 여러 OSD write가 생길 수 있다. 그래서 EC pool은 capacity 효율만 보고 고르면 안 되고, workload의 write 크기와 update 패턴을 함께 본다.

## 6. BlueStore는 “모든 object를 ext4 일반 파일로 저장”이 아니다

Ceph glossary는 BlueStore가 raw block device나 partition에 직접 object를 저장하고 mounted filesystem과 상호작용하지 않으며, RocksDB key/value database로 object name을 disk location에 mapping한다고 설명한다.
[Ceph Glossary: BlueStore](https://docs.ceph.com/en/reef/glossary/#term-BlueStore) 따라서 “Ceph object 하나 = ext4 파일 하나”라는 오래된 FileStore식 직관을 BlueStore에 적용하면 틀린다. OSD host의 block
device, BlueStore allocator, RocksDB metadata, WAL/DB device 구성은 RADOS object API 아래의 구현 세부다.

중요한 분리:

| 질문 | 잘못된 단순화 | 더 정확한 관점 |
| --- | --- | --- |
| Object는 파일인가? | ext4 파일 하나 | BlueStore가 raw device 위에 object data와 metadata를 관리 |
| RocksDB는 payload 저장소인가? | 모든 bytes가 RocksDB에 있음 | 주로 metadata mapping과 small metadata 경로 |
| filesystem tune이 전부인가? | ext4 directory tuning | OSD, BlueStore, device, DB/WAL, CRUSH까지 함께 봄 |

이 장은 tuning 문서가 아니므로 세부 설정을 제안하지 않는다. 핵심은 storage engine의 하위 구현을 POSIX file tree로 오해하지 않는 것이다.

## 7. Write ACK, durability, visibility

Ceph architecture는 librados interface가 direct, parallel object access와 compound operations, dual-ack semantics를 제공한다고 설명한다. [Native Protocol and
librados](https://docs.ceph.com/en/reef/architecture/#native-protocol-and-librados) 정확한 ACK 의미는 client library, pool type, OSD commit/apply 경로, 설정에 의존한다. 학습 단계에서는 최소한 다음을 분리한다.

| 질문 | Ceph/RADOS 관점 | RGW/S3 관점 |
| --- | --- | --- |
| ACK | primary/replica 또는 EC acting set이 write를 어떤 수준까지 처리했는가 | HTTP response가 성공했는가 |
| Durability | pool size/min_size, OSD commit, failure domain, recovery 상태에 의존 | RGW가 성공을 돌려준 뒤 backend에 안전하게 저장됐는가 |
| Visibility | RADOS object read가 새 값을 보는가 | GET/HEAD/LIST가 새 S3 object 상태를 보는가 |
| Listing | RADOS namespace listing과 다름 | bucket index가 반영돼야 함 |

ACK를 받았다는 말만으로 “모든 interface에서 즉시 같은 방식으로 보인다”고 쓰면 안 된다. RBD client에게 보이는 block write, CephFS client에게 보이는 file metadata, RGW S3 GET/LIST는 다른 protocol boundary를 지난다.

Quorum과 split-brain caveat도 여기서 분리한다. Ceph monitor는 cluster map과 중요한 상태를 다루므로 quorum 개념이 핵심이다. 반면 RADOS object write 경로의 성공 조건은 pool type, size, min_size, primary/replica 상태, OSD map epoch 같은 Ceph 내부 규칙을 따른다. “quorum”이라는 단어를 보았다고 모든 쓰기가 Paxos식 다수결 key-value DB처럼 동작한다고 쓰면 안 된다.

```text
Monitor quorum 질문:
  이 cluster map과 leader를 누가 인정하는가?

OSD acting set 질문:
  이 PG의 primary와 replica/chunk OSD가 누구이며 write가 어느 수준까지 완료됐는가?

Split-brain 질문:
  network partition 뒤 양쪽이 서로 다른 cluster map이나 object history를 정답이라고 믿는가?
```

Ceph는 이런 상황을 피하려고 monitor quorum, OSDMap epoch, peering, PG state, recovery 절차를 둔다. 입문자가 기억할 문장은 짧다. “복제본이 여러 개 있다”는 말과 “누가 최신이고 누가 쓰기를 받을 권한이 있는지 합의했다”는 말은 다르다.

## 8. RGW bucket index와 object visibility

RGW developer 문서는 bucket이 object 목록을 bucket index에 저장하고, index entry가 ListObjectsV2 같은 API에 필요한 metadata를 가진다고 설명한다. [Rados Bucket
Index](https://docs.ceph.com/en/reef/dev/radosgw/bucket_index/) 같은 문서는 RGW가 object operation에 read-after-write consistency를 보장해야 한다고 설명한다. [RGW Consistency
Guarantee](https://docs.ceph.com/en/reef/dev/radosgw/bucket_index/#consistency-guarantee) RGW는 API object를 head object와 tail object로 저장하고, head object를 마지막에 써서 read request에 보이는
atomic commit처럼 사용한다. [Rados Object Model](https://docs.ceph.com/en/reef/dev/radosgw/bucket_index/#rados-object-model) head object와 bucket index는 서로 다른 RADOS object이므로 index
transaction으로 조정한다. [Index Transaction](https://docs.ceph.com/en/reef/dev/radosgw/bucket_index/#index-transaction)

단순 경로:

```text
HTTP PUT key=sensor/raw/001.bin
  |
  v
RGW auth / bucket lookup / multipart or single PUT handling
  |
  v
Write tail RADOS objects if needed
  |
  v
Write head object as visibility point
  |
  v
Prepare/commit bucket index update for listing
  |
  v
HTTP 200/201 response
```

GET path는 object head를 찾고 필요한 RADOS object들을 읽어 response body를 만든다. LIST path는 bucket index를 읽는다. 따라서 “GET은 되는데 LIST가 이상하다” 같은 질문은 data object와 bucket index를 분리해 생각해야 한다.

## 9. AWS S3 consistency와 S3-compatible 구현

AWS 문서는 Amazon S3가 모든 Region에서 object PUT/DELETE에 strong read-after-write consistency를 제공하고, GET/LIST가 성공한 PUT 이후 데이터를 반환한다고 설명한다. [Amazon S3 data consistency
model](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel) 또한 single key update는 atomic이며, 동시에 같은 key를 쓰는 경우 object locking은 application이 설계해야 한다고
설명한다. [Amazon S3 data consistency model](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel)

하지만 이 claim을 모든 S3-compatible system에 자동 전파하면 안 된다. Ceph RGW는 자체 consistency 설계를 가진다. MinIO, Ceph RGW multisite, cloud provider S3-compatible endpoint, gateway cache는 각각 문서를 확인해야
한다. 특히 Ceph multisite는 최소 두 storage cluster와 zone/zonegroup 구성을 다루며, geographically distributed 단일 Ceph cluster는 low latency WAN 없이는 권장되지 않는다고 문서가 말한다. [Ceph RGW
Multi-Site](https://docs.ceph.com/en/reef/radosgw/multisite/)

정리:

```text
AWS S3 strong consistency: AWS S3 서비스에 대한 문서 claim
S3-compatible API: HTTP API surface가 비슷하다는 의미
RGW multisite consistency: zone sync와 conflict/failover 설계 확인 필요
Application correctness: retry, idempotency, table commit protocol까지 포함
```

## 10. S3 HTTP PUT, multipart upload, range GET

S3는 filesystem write syscall이 아니라 HTTP API다. AWS 문서는 multipart upload가 object 하나를 여러 part로 올리고 complete 시 S3가 part들을 조립한다고 설명한다. [Multipart upload
overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html) part는 독립적으로, 순서와 다르게 업로드할 수 있고, complete request 후 하나의 object가 된다. [Multipart upload
process](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html#mpuoverview) 대용량 read는 Range header나 partNumber를 사용해 일부 bytes를 가져올 수 있다. [Downloading
objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/download-objects.html)

ASCII path:

```text
PUT object:
  Client --HTTP PUT/multipart--> S3/RGW endpoint
  Endpoint --backend writes--> object storage
  Client <--HTTP success/failure--

Range GET:
  Client --GET key + Range: bytes=0-1048575--> endpoint
  Endpoint reads needed backend object/chunks
  Client <--206 Partial Content--
```

Range GET는 임의 위치 update가 아니다. Multipart upload는 여러 part를 완성해 하나의 object version을 만드는 방식이지, 완성된 object의 중간 bytes를 POSIX처럼 수정하는 기능이 아니다.

Multipart publish 실패도 반드시 시간순으로 본다.

```text
t0  CreateMultipartUpload returns upload id U1.
t1  UploadPart 1,2,3 succeed.
t2  UploadPart 4 fails or client loses network.
t3  Object key K is still not published as the completed object.
t4  Client can retry part 4 or abort multipart upload.
t5  CompleteMultipartUpload succeeds.
t6  Only now K becomes one completed object according to that service's consistency rules.
```

완료 전 uploaded parts는 비용과 lifecycle의 대상이 될 수 있지만, 일반 reader가 key K의 완성 object로 읽는 상태가 아니다. Complete 요청이 성공했는데 client가 timeout을 받으면 더 조심해야 한다. 실제로 publish됐는지 HEAD/GET, versioning 상태, idempotency 설계를 확인하지 않고 같은 데이터를 새 object로 다시 쓰면 중복이나 orphan이 생길 수 있다. AWS S3의 구체적 보장은 AWS S3 문서 범위에서 말하고, RGW나 다른 S3-compatible 구현은 그 구현의 문서를 따로 확인한다.

## 11. Rename과 append를 POSIX처럼 가정하지 않는다

AWS general-purpose bucket에서 일반적인 rename/move는 새 key로 copy한 뒤 source key를 delete하는 조합으로 이해한다. AWS 문서는 rename을 copy 후 original에 delete marker를 추가하는 방식으로 설명하지만, delete marker는 versioning-enabled 또는 suspended bucket의 simple DELETE에서 생기는 표식이고, versioning이 꺼진 bucket에서는 DeleteObject가 객체를 영구 삭제한다는 점을 구분해야 한다. [Copying, moving, and renaming objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/copy-object.html), [DeleteObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_DeleteObject.html), [Working with delete markers](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeleteMarker.html)
CopyObject는 5 GB 이하를 single atomic operation으로 복사할 수 있고, 더 큰 object는 multipart copy가 필요하다. [CopyObject](https://docs.aws.amazon.com/AmazonS3/latest/userguide/copy-object.html) 따라서 일반 S3/RGW rename을 POSIX filesystem metadata rename과 같은 비용·원자성으로 가정하지 않는다. 예외적으로 AWS는 S3 Express One Zone storage class의 directory bucket에서 같은 directory bucket 내부 객체를 data movement 없이 원자적으로 바꾸는 `RenameObject`를 제공하지만, 이 한정 API를 general-purpose bucket이나 Ceph RGW 같은 일반 S3-compatible 구현에 그대로 가정하면 안 된다. [Renaming objects in directory buckets](https://docs.aws.amazon.com/AmazonS3/latest/userguide/directory-buckets-objects-rename.html)

Append도 마찬가지다. 일반 S3 object workflow는 complete object PUT 또는 multipart complete 중심이다. 일부 vendor가 append API를 제공하더라도 “S3-compatible”이라는 말만으로 generic POSIX append가 있다고 가정하지 않는다.
Lakehouse table format이 object store에서 commit protocol을 신중하게 설계하는 이유가 여기에 있다.

## 12. Bucket index, Iceberg metadata, raw assets는 다르다

Bucket index는 bucket 안에 어떤 object key가 있는지 API listing을 지원하기 위한 RGW/S3 계층 metadata다. Iceberg metadata는 table schema, snapshot, manifest list, data file set을 관리하는 table format 계층
metadata다. Raw assets는 sensor binary, Parquet, image, model artifact 같은 실제 payload file/object다. Iceberg spec은 table metadata file이 schema, partition config, properties, snapshots를
추적한다고 설명한다. [Apache Iceberg Spec](https://iceberg.apache.org/spec/)

세 계층을 섞으면 장애 분석이 틀린다.

```text
Bucket index:
  "raw/sensor-A/001.parquet" key가 LIST에 보이는가?

Iceberg metadata:
  snapshot S42가 이 parquet 파일을 live data file로 참조하는가?

Raw asset:
  parquet object bytes가 손상 없이 저장돼 있고 reader가 해석할 수 있는가?
```

S3 LIST에 파일이 보인다고 Iceberg table에 공식 반영됐다는 뜻은 아니다. Iceberg snapshot이 파일을 참조한다고 object store 권한이 모든 reader에게 열렸다는 뜻도 아니다. Raw object가 존재한다고 schema evolution, delete file, snapshot
isolation이 자동 제공되는 것도 아니다.

## 13. Kubernetes PV/PVC/CSI는 storage engine이 아니다

Kubernetes 공식 문서는 PersistentVolume subsystem이 storage 제공 세부와 소비 방식을 추상화한다고 설명한다. [Kubernetes Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
PV는 cluster storage resource이고 PVC는 사용자의 storage request다. [Kubernetes Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) CSI는 Kubernetes 같은
orchestrator가 임의 storage system을 workload에 노출하는 표준 interface다. [Kubernetes CSI volumes](https://kubernetes.io/docs/concepts/storage/volumes/#csi) StorageClass는 admin이 제공하는 storage
class를 설명하고 dynamic provisioning parameter를 담는다. [Kubernetes StorageClasses](https://kubernetes.io/docs/concepts/storage/storage-classes/)

따라서 다음 식은 틀렸다.

```text
PVC == storage engine
CSI == database
StorageClass == durability guarantee itself
```

더 정확한 식은 다음이다.

```text
PVC asks for storage
StorageClass selects/provisions through a driver
CSI driver calls Ceph/RBD/CephFS/EBS/etc.
Actual semantics come from the backend and driver mode
```

RBD-backed PVC는 block volume으로 보일 수 있다. CephFS-backed PVC는 shared filesystem으로 보일 수 있다. RGW/S3는 보통 PVC mount가 아니라 HTTP object API로 애플리케이션이 직접 사용한다.

Pod 안에서 보이는 경로까지 따라가면 더 분명하다.

```text
1. Developer writes Pod spec:
   volumeMounts:
   - name: data
     mountPath: /var/lib/app/data

2. Developer writes PVC:
   storageClassName: ceph-rbd
   accessModes: [ReadWriteOnce]
   resources.requests.storage: 100Gi

3. Kubernetes control plane:
   PVC를 만족할 PV를 찾거나 CSI driver로 dynamic provisioning 요청

4. Node + CSI driver:
   backend volume을 attach/map 하고 node filesystem 또는 block device로 준비

5. Container process:
   /var/lib/app/data 라는 경로에서 POSIX file API를 사용
```

이때 `/var/lib/app/data`는 container mount namespace 안의 경로다. 그 아래 bytes의 durability, replication, snapshot, multi-writer 가능 여부는 mountPath 문자열이 아니라 StorageClass, CSI driver, backend mode, access mode, filesystem, application sync 방식이 결정한다. 같은 PVC라도 RBD filesystem volume인지 raw block volume인지, CephFS인지, cloud disk인지에 따라 의미가 달라진다.

## 14. 센서 파일 접근을 끝까지 추적하기

가상 데이터: `sensor-A`가 10분마다 64 MiB binary chunk를 만든다고 하자. 목표는 raw object 저장 뒤 Parquet 변환본을 Iceberg table에서 읽는 것이다. 이 흐름은 설명용이며 실제 endpoint나 credential을 포함하지 않는다.

```text
1. Pod receives sensor bytes
   - PVC가 있으면 Kubernetes가 CSI driver를 통해 backend volume을 attach/mount한다.
2. Application uploads raw object
   - HTTP PUT or multipart upload to AWS S3, Ceph RGW, or another S3-compatible endpoint.
   - Success response is API-level ACK, not table-level commit.
3. RGW maps API object to RADOS
   - Bucket index records listable key metadata; head/tail objects store payload representation.
   - RADOS maps backend objects to PGs and OSD acting sets.
4. OSDs store bytes
   - Replicated pool copies replicas, or EC pool stores data/coding chunks.
   - CRUSH failure domain determines placement boundaries; BlueStore handles raw device storage.
5. Batch job converts raw to Parquet and commits Iceberg metadata
   - Query readers trust catalog/table metadata, not object-store LIST, as table truth.
```

장애가 나면 “Pod mount”, “HTTP PUT 성공”, “bucket index 반영”, “RADOS PG 상태”, “Iceberg commit 여부”를 분리한다.

## 15. Worked numerical examples

예제 A: replicated pool.

```text
Object size = 256 MiB
Pool size = 3
Raw payload before overhead = 768 MiB
Failure model = three replicas across CRUSH-selected failure domains
```

예제 B: EC pool `k=4, m=2`.

```text
Object logical size = 256 MiB
Data chunks = 4 × 64 MiB
Coding chunks = 2 × 64 MiB
Raw payload before overhead = 384 MiB
Overhead factor = 1.5
```

예제 C: multipart upload.

```text
Object logical size = 1 GiB
Part size = 128 MiB
Part count = 8
CompleteMultipartUpload publishes one object from 8 uploaded parts
Reader sees object after completion according to service consistency semantics
```

이 숫자는 이해를 위한 산술이다. 실제 성능, 압축률, billing, BlueStore allocation, checksum, recovery cost를 측정한 값이 아니다.

## 16. RBD, CephFS, RGW를 한 요청으로 비교하기

같은 “센서 파일 저장” 요구도 interface에 따라 완전히 다른 시스템 경로를 탄다.

```text
RBD-backed PVC:
  app writes /var/lib/app/data/a.bin
  → guest/container filesystem updates blocks
  → kernel block I/O
  → RBD image objects
  → RADOS pool PGs and OSDs

CephFS-backed PVC:
  app writes /mnt/shared/a.bin
  → CephFS client talks to MDS for metadata
  → file data maps to RADOS objects
  → RADOS pool PGs and OSDs

RGW/S3:
  app PUT https://object.example/bucket/a.bin
  → RGW auth and bucket index logic
  → head/tail RADOS objects
  → RADOS pool PGs and OSDs
```

RBD는 block device라서 filesystem metadata는 보통 client node 쪽 filesystem이 만든다. CephFS는 shared filesystem metadata를 MDS가 조정한다. RGW는 bucket, key, HTTP method, ACL/policy, bucket index가 핵심이다. 세 경로 모두 RADOS를 쓸 수 있지만, 사용자가 보는 consistency와 metadata 책임은 같지 않다.

## 17. 흔한 오해

- “Ceph는 S3다” → Ceph는 RADOS 위에 RBD, CephFS, RGW 등 여러 interface를 제공한다.
- “RADOS object와 S3 object는 1:1이다” → RGW API object는 여러 RADOS object로 mapping될 수 있다.
- “BlueStore object는 ext4 파일이다” → BlueStore는 raw block device/partition 위에서 직접 관리한다.
- “EC는 replication보다 항상 좋고, AWS S3 consistency는 모든 S3-compatible에 그대로 적용된다” → 구현·pool·multisite 조건별로 확인해야 한다.
- “PVC나 S3 LIST를 보면 storage/table semantics를 다 안다” → backend driver와 table metadata snapshot을 따로 봐야 한다.

## 18. 복습 질문

**질문 1.** RBD, CephFS, RGW의 차이를 한 문장씩 말하라. 짧은 답: RBD는 block device, CephFS는 POSIX-like filesystem, RGW는 S3/Swift-compatible HTTP object gateway다.

**질문 2.** RADOS object placement는 어떤 단계를 거치는가? 짧은 답: object id가 pool 안에서 PG로 mapping되고, CRUSH rule이 PG acting set OSD와 failure domain을 결정한다.

**질문 3.** BlueStore를 ext4 파일 모음으로 설명하면 왜 틀린가? 짧은 답: BlueStore는 mounted filesystem이 아니라 raw block device/partition에 object를 직접 저장하고 RocksDB로 mapping metadata를 관리한다.

**질문 4.** AWS S3 strong consistency claim을 Ceph RGW multisite에 그대로 적용해도 되는가? 짧은 답: 안 된다. AWS S3 서비스 claim과 S3-compatible 구현, RGW multisite sync semantics는 별도로 확인해야 한다.

**질문 5.** Kubernetes PVC는 왜 storage engine이 아닌가? 짧은 답: PVC는 storage 요청 API이고 실제 저장·복제·consistency semantics는 CSI driver 뒤의 backend가 제공한다.

**질문 6.** EC `k=4, m=2`에서 256 MiB object의 단순 raw payload는 얼마인가? 짧은 답: data chunk 4개와 coding chunk 2개, 총 6개 chunk가 필요하므로 384 MiB이고 overhead는 1.5배다.

**질문 7.** multipart upload에서 part 1-3 업로드 성공 후 complete 전에 client가 죽으면 object가 완성 publish됐는가? 짧은 답: 아니다. CompleteMultipartUpload가 성공해야 하나의 완성 object로 게시된다. 미완료 part는 별도 정리 대상이 될 수 있다.

**질문 8.** Pod의 `/var/lib/app/data` 경로만 보고 storage semantics를 알 수 있는가? 짧은 답: 없다. PVC, StorageClass, CSI driver, backend, access mode, filesystem, sync 방식까지 봐야 한다.
