# 06. Parquet, Arrow, Iceberg를 bytes에서 snapshot까지 연결하기

작성·문헌 확인일: **2026-09-21**. 이 장은 CSV·row store·columnar file·in-memory columnar layout·table format catalog를 한 번에 섞지 않도록 낮은 층의 역할을 분리한다. 공식 문서와 규격은 시간이 지나며 바뀌므로, 실제 실험에서는 Apache Parquet·Arrow·Iceberg·Nessie의 릴리스 번호와 엔진 커넥터 버전을 함께 고정한다. 여기서의 파일 이름, metadata, SQL 모양은 모두 **개념 설명용 가상 표현**이며, 운영 환경에서 실행할 명령이나 완전한 schema가 아니다. Lakehouse 논문별 긴 연구 해설은 [기존 리뷰](../lakehouse/02-paper-reviews.md)와 [단계별 walkthrough](../lakehouse/04-end-to-end-walkthrough.md)를 참고하고, 이 장은 하위 파일 구조와 읽기 경로에 집중한다.

## 1. CSV, row layout, column layout은 서로 다른 읽기 비용을 만든다

CSV는 텍스트 행을 delimiter로 나열한 교환 형식에 가깝다. CSV 파일은 사람이 보기 쉽고 append가 단순하지만, type, null, nested 구조, 압축 단위, column statistics를 표준적으로 풍부하게 담지 않는다. Row-store layout은 한 row의 여러 column 값을 가까이 둔다. OLTP에서 한 고객 row 전체를 자주 읽고 update할 때 row-store는 locality가 좋다. Columnar layout은 같은 column 값을 연속적으로 배치해 scan, compression, vectorized execution에 유리하게 만든다. 분석 쿼리가 200개 column 중 5개만 읽는다면 columnar file은 projection으로 나머지를 건너뛸 수 있다. 반대로 한 row를 자주 point update하는 workload에서는 immutable columnar file을 다시 쓰거나 delete 표현을 추가해야 할 수 있다. 따라서 “columnar가 row보다 빠르다”가 아니라 “쿼리가 어떤 column과 row 범위를 읽는가”로 판단한다.

```text
동일 데이터의 배치 차이

CSV/row-oriented view
  row1: time=09:00, device=A, temp=20, rpm=1000
  row2: time=09:01, device=A, temp=21, rpm=1005

Columnar view
  time:   09:00, 09:01, ...
  device: A,     A,     ...
  temp:   20,    21,    ...
  rpm:    1000,  1005,  ...
```

### 1.1 worked example: 1억 행에서 3개 column만 읽기

가상 dataset에 100개 column과 1억 행이 있다고 하자. 분석 쿼리가 `event_time`, `device_id`, `temperature_c`만 필요로 한다면 row file은 보통 row 전체를 decode하거나 적어도 많은 불필요 bytes를 지나야 한다. Parquet 같은 columnar file은 필요한 column chunk만 선택해 읽을 수 있다. 그러나 predicate가 아주 넓어서 모든 row group을 열어야 하거나, 압축 해제 CPU가 병목이면 I/O 절감이 그대로 wall-clock 절감으로 변하지 않을 수 있다. 이 예제는 원리 설명이며 실제 수치는 측정하지 않았다.

## 2. Parquet 파일은 row group, column chunk, page, footer로 읽는다

Parquet 공식 concepts 문서는 file이 하나 이상의 row group으로 구성되고, row group은 각 column당 정확히 하나의 column chunk를 가지며, column chunk는 page들로 나뉜다고 설명한다. [Parquet Concepts](https://parquet.apache.org/docs/concepts/) 같은 문서는 row group을 row의 논리적 수평 partition, column chunk를 특정 column의 chunk, page를 encoding과 compression 관점의 단위로 설명한다. [Parquet Concepts](https://parquet.apache.org/docs/concepts/) Parquet file format 문서는 파일 끝에 File Metadata와 그 길이, magic number가 있으며, metadata가 column chunk 위치를 담는다고 설명한다. [Parquet File Format](https://parquet.apache.org/docs/file-format/) Reader는 먼저 footer metadata를 읽어 관심 있는 column chunk 위치를 찾은 뒤, 필요한 chunk를 순차적으로 읽는다. [Parquet File Format](https://parquet.apache.org/docs/file-format/) Metadata가 뒤에 있는 이유는 writer가 데이터를 한 번 흘려 쓰고 마지막에 metadata를 완성할 수 있게 하기 위해서다. [Parquet File Format](https://parquet.apache.org/docs/file-format/)

```text
Parquet 파일 단순도

PAR1
  RowGroup 0
    ColumnChunk time       → pages
    ColumnChunk device_id  → pages
    ColumnChunk temp       → pages
  RowGroup 1
    ColumnChunk time       → pages
    ColumnChunk device_id  → pages
    ColumnChunk temp       → pages
  ...
  File Metadata footer: schema, row groups, chunk offsets, stats 등
  footer length
PAR1
```

### 2.1 worked example: projection과 row group pruning은 다른 단계다

가상 Parquet file에 10개 row group이 있고 각 row group은 100만 행을 담는다고 하자. 쿼리가 `temperature_c` 한 column만 읽으면 projection은 다른 column chunks를 건너뛴다. 쿼리 조건이 `event_time BETWEEN 09:00 AND 10:00`이면 row group statistics가 시간 범위를 보고 일부 row group을 건너뛸 수 있다. Projection은 “어떤 column bytes를 읽을까”의 문제다. Predicate pushdown 또는 pruning은 “어떤 row group/page/file을 열 필요가 없을까”의 문제다. 둘 다 성공하면 I/O가 줄지만, 하나가 성공했다고 다른 하나도 자동 성공하는 것은 아니다.

## 3. Encoding과 compression은 page 안의 다른 층이다

Parquet encoding 문서는 plain, dictionary, RLE/bit-packing, delta, byte-stream split 등 여러 encoding을 정의한다. [Parquet Encodings](https://parquet.apache.org/docs/file-format/data-pages/encodings/) Dictionary encoding은 column chunk의 dictionary page에 값 사전을 저장하고 data page에는 dictionary id를 저장할 수 있지만, 사전이 너무 커지면 plain encoding으로 fallback할 수 있다. [Parquet Encodings](https://parquet.apache.org/docs/file-format/data-pages/encodings/) Parquet compression 문서는 data page와 dictionary page의 data block이 codec으로 압축될 수 있다고 설명하며, Snappy, GZIP, Brotli, ZSTD, LZ4_RAW 등을 정의한다. [Parquet Compression](https://parquet.apache.org/docs/file-format/data-pages/compression/) Encoding은 값을 더 표현하기 좋은 byte sequence로 바꾸는 단계다. Compression은 그 byte sequence를 codec으로 더 작게 만드는 단계다. 높은 압축률이 항상 빠른 쿼리를 뜻하지 않는다. CPU decode 비용, column selectivity, storage bandwidth, vectorization, codec 지원이 함께 영향을 준다.

```text
한 column page의 개념 처리

logical values
    ↓ encoding: dictionary/RLE/delta/plain 등
encoded page payload
    ↓ compression: snappy/zstd/gzip 등
compressed page bytes
    ↓ file write
Parquet page inside column chunk
```

### 3.1 worked example: device_id column의 dictionary

가상 column `device_id`가 `A`, `B`, `C` 세 값만 반복한다고 하자. Dictionary page는 `A→0`, `B→1`, `C→2` 같은 mapping을 담을 수 있다. Data page는 `0,0,1,2,0,...` 같은 작은 id sequence를 RLE/bit-packing으로 저장할 수 있다. 조건이 `device_id='Z'`라면 dictionary나 statistics를 보고 해당 page 또는 row group을 건너뛰는 reader도 있을 수 있다. 하지만 dictionary 사용 여부와 predicate pushdown 구현은 writer·reader·column cardinality에 따라 다르므로, 문서에는 “가능한 구조”와 “우리 엔진에서 확인한 동작”을 분리해 써야 한다.

## 4. Statistics와 Bloom filter는 pruning 힌트이지 정답 계산기가 아니다

Parquet metadata는 file metadata와 page header metadata로 나뉘며, file metadata는 offset과 size 정보를 제공한다. [Parquet Metadata](https://parquet.apache.org/docs/file-format/metadata/) Parquet Bloom filter 문서는 column statistics와 dictionary가 predicate pushdown에 쓰일 수 있고, Bloom filter가 high-cardinality column에서도 membership pruning을 도울 수 있다고 설명한다. [Parquet Bloom Filter](https://parquet.apache.org/docs/file-format/bloomfilter/) Bloom filter는 “definitely no” 또는 “probably yes”로 답하며 false positive가 있을 수 있지만 false negative는 없도록 설계된다. [Parquet Bloom Filter](https://parquet.apache.org/docs/file-format/bloomfilter/) Parquet format version 문서는 Bloom filters가 older reader가 무시해도 correctness는 유지되는 forward-compatible feature 예라고 설명한다. [Parquet Format Versions](https://parquet.apache.org/docs/file-format/versions/) 따라서 Bloom filter가 없거나 reader가 무시하면 더 많이 읽을 수는 있지만, 그 자체로 결과가 틀려야 하는 것은 아니다. Statistics도 min/max, null count, value count 같은 metadata가 writer에 의해 적절히 작성되고 reader가 해석해야 pruning에 쓰인다. NaN, timezone, collation, binary sort order, encrypted footer 같은 세부는 포맷과 구현 문서를 확인해야 한다.

### 4.1 worked example: row group min/max pruning

가상 row group 0의 `event_time` min/max가 09:00–09:59이고, row group 1이 10:00–10:59라고 하자. 쿼리 조건이 09:15–09:20이면 row group 1은 metadata만 보고 제외할 수 있다. 하지만 row group 0 안에서도 실제로는 09:15–09:20 행만 필요한데, page index나 더 세밀한 filter를 쓰지 않으면 row group 0의 column chunk를 열어야 할 수 있다. File-level pruning은 파일 자체를 제외한다. Row-group predicate pushdown은 파일 안 row group을 제외한다. Page-level index 활용은 더 세밀하지만 writer와 reader 지원, metadata 읽기 비용을 함께 본다.

## 5. Metadata를 읽는 비용도 비용이다

Columnar file은 footer와 metadata로 많은 bytes를 피할 수 있지만, metadata 자체도 읽고 parse해야 한다. 작은 Parquet file이 수십만 개 있으면 각 file footer open과 range read가 planning 병목이 될 수 있다. Iceberg는 directory listing 대신 manifest tree를 이용해 file 목록과 metrics를 추적하지만, manifest가 너무 많거나 query pattern과 맞지 않으면 metadata planning 비용이 커질 수 있다. Iceberg maintenance 문서는 manifest list와 manifest files의 metadata가 불필요한 data file을 prune하는 데 쓰이며, metadata tree가 table data 위의 index처럼 동작한다고 설명한다. [Apache Iceberg Maintenance](https://iceberg.apache.org/docs/latest/maintenance/) 그렇다고 manifest rewrite가 항상 우선은 아니다. 데이터 파일 읽기가 병목인지, footer/manifest metadata가 병목인지, catalog call이 병목인지, object store request latency가 병목인지 분리해 측정해야 한다.

```text
분석 query planning 비용 분해

Catalog: 현재 metadata 위치 확인
  ↓
Table metadata JSON 읽기
  ↓
Snapshot 선택
  ↓
Manifest list 읽기
  ↓
필요한 manifest만 읽기
  ↓
Data file footer 또는 split metadata 읽기
  ↓
실제 column chunks 읽기
```

## 6. Arrow는 in-memory columnar format이지 lakehouse storage engine이 아니다

Apache Arrow columnar format 문서는 language-independent in-memory data structure specification, metadata serialization, serialization protocol을 포함한다고 설명한다. [Apache Arrow Columnar Format](https://arrow.apache.org/docs/format/Columnar.html) Arrow layout은 sequential scan을 위한 data adjacency, constant-time random access, SIMD/vectorization-friendly 특성, shared memory에서 pointer swizzling 없이 relocatable한 zero-copy access 가능성을 목표로 한다. [Apache Arrow Columnar Format](https://arrow.apache.org/docs/format/Columnar.html) 이 말은 Arrow가 모든 storage engine을 대체한다는 뜻이 아니다. Arrow IPC file format은 존재하지만, Arrow 자체가 transaction catalog, WAL, compaction scheduler, object store commit protocol을 제공하는 table engine은 아니다. 또 “zero-copy” 가능성은 shared memory와 layout 조건에 대한 말이지, GPU가 항상 host memory를 복사 없이 처리한다는 보장이 아니다. GPU, NIC, process boundary, compression, encryption, endian, device memory placement가 개입하면 copy가 필요할 수 있다. 따라서 문서에는 “Arrow-compatible memory layout을 사용했다”와 “end-to-end GPU zero-copy를 측정했다”를 구분해야 한다.

### 6.1 worked example: Parquet에서 Arrow batch로 읽기

가상 reader가 Parquet `temperature_c` column chunk를 읽는다. 먼저 footer에서 column chunk 위치를 찾고 compressed pages를 읽는다. Page를 decompress하고 encoding을 decode해 Arrow array buffer를 만든다. 이후 compute kernel은 Arrow array를 vectorized하게 처리할 수 있다. 이 경로에는 이미 storage → CPU memory copy, decompression, decoding이 있었다. 따라서 결과 batch가 Arrow layout이라고 해서 Parquet file bytes가 GPU kernel로 그대로 zero-copy 처리됐다고 쓰면 과장이다.

## 7. Iceberg write path는 data file 작성과 table commit을 분리한다

Iceberg spec은 table이 directory가 아니라 개별 data file을 추적하며, writer가 data file을 제자리에 만들고 명시적 commit에서 table에 추가한다고 설명한다. [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/) Table state는 metadata file에 유지되고, 변화는 새 metadata file을 만든 뒤 old metadata pointer를 atomic swap하는 방식으로 게시된다. [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/) Snapshot은 어느 시점 table state이며, manifest list와 manifests를 통해 data files를 찾는다. [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/) Iceberg reliability 문서는 commits가 current table metadata file path를 atomic operation으로 교체해 table data와 metadata update의 atomicity와 serializable isolation 기반을 제공한다고 설명한다. [Apache Iceberg Reliability](https://iceberg.apache.org/docs/latest/reliability/) 동시 writer는 optimistic concurrency로 새 metadata를 만들고, swap 실패 시 현재 상태에서 assumptions를 다시 검증한 뒤 재시도하거나 실패한다. [Apache Iceberg Reliability](https://iceberg.apache.org/docs/latest/reliability/)

```text
Iceberg append write path 단순도

1. Engine writes new data files
     data/part-000.parquet
     data/part-001.parquet
2. Engine writes new manifest with those files and metrics
     metadata/m-123.avro
3. Engine writes new manifest list for snapshot S2
     metadata/snap-S2.avro
4. Engine writes new table metadata JSON referencing S2
     metadata/v2.metadata.json
5. Catalog atomically swaps table pointer from v1 to v2
6. New readers can load v2 and choose snapshot S2
```

### 7.1 worked example: commit 전 파일은 공식 table이 아니다

가상 writer가 `part-001.parquet`를 object store에 올렸지만 catalog commit 전에 crash났다고 하자. 파일은 storage에 존재할 수 있지만 current snapshot의 manifest가 참조하지 않으면 공식 table scan의 일부가 아니다. 반대로 commit이 성공했는데 client가 timeout을 받았다면, 같은 data를 다시 append하면 중복이 생길 수 있다. Iceberg commit atomicity는 table metadata pointer의 게시를 다루지만, application-level idempotency까지 자동으로 보장하지 않는다. 이 점은 [기존 end-to-end walkthrough](../lakehouse/04-end-to-end-walkthrough.md)의 commit 실패·재시도 예제와 연결해서 읽는다.

## 8. Iceberg read path는 pinned snapshot에서 file과 row로 내려간다

Reader는 catalog에서 현재 metadata location을 얻고 table metadata JSON을 읽는다. 그 다음 query가 사용할 snapshot을 고정한다. 최신 snapshot을 사용할 수도 있고, time travel이나 reproducibility 요구 때문에 과거 snapshot ID를 고정할 수도 있다. Snapshot은 manifest list를 가리키고, manifest list는 필요한 manifests를 고르는 통계와 counts를 담는다. [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/) Manifest는 data file 또는 delete file 목록, partition tuple, metrics, tracking 정보를 담는 immutable Avro metadata file이다. [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/) Reader는 manifest와 data file metrics로 file pruning을 수행한 뒤, 남은 Parquet/ORC/Avro file을 각 file format reader로 읽는다. 이 과정에서 Iceberg는 table-level file set consistency를 제공하고, Parquet는 file 내부 columnar layout과 statistics를 제공한다.

```text
Iceberg read path 단순도

Catalog pointer
  → table metadata JSON
      → snapshot S2 pinned
          → manifest list
              → manifests
                  → data files + delete files
                      → Parquet footer
                          → row groups / column chunks / pages
                              → rows visible after deletes
```

### 8.1 pruning의 세 층

File pruning은 Iceberg manifest metrics나 partition stats를 이용해 data file 전체를 제외하는 단계다. Row-group predicate pushdown은 Parquet footer statistics로 file 내부 row group을 제외하는 단계다. Projection은 남은 row group에서도 필요한 column chunk만 읽는 단계다. 세 단계는 서로 보완하지만 같은 기능이 아니다. File pruning이 잘 되어도 각 file 안에서 불필요 column을 모두 읽으면 낭비가 남는다. Projection이 잘 되어도 너무 많은 작은 files를 열면 metadata와 object request 비용이 커진다. Row-group pushdown이 잘 되어도 footer를 읽고 해석하는 비용은 남는다.

## 9. Nessie reference와 Iceberg per-table snapshot을 구분한다

Nessie introduction은 Git-like branch와 tag를 data lake에 제공하며, commit을 특정 시점 모든 table의 consistent snapshot, branch를 commit을 추가할 수 있는 reference, tag를 특정 commit을 가리키는 reference로 설명한다. [Project Nessie Introduction](https://projectnessie.org/guides/introduction/) Nessie spec은 Iceberg table content object가 table metadata pointer와 Iceberg snapshot, schema, partition spec, sort order ID 같은 on-reference-state를 포함한다고 설명한다. [Project Nessie Specification](https://projectnessie.org/develop/spec/) Iceberg snapshot은 한 table 안의 file set version이다. Nessie branch/tag는 catalog reference이며 여러 table name과 그 table states를 특정 commit graph 위에서 관리할 수 있다. 따라서 “branch main의 commit X”와 “table orders의 snapshot 123”은 같은 식별자가 아니다. Nessie가 있다면 catalog reference가 어떤 Iceberg table metadata와 snapshot을 가리키는지 기록해야 한다. Nessie 없이 Hive/REST/JDBC catalog를 쓰는 Iceberg table도 per-table snapshot history를 가질 수 있다.

### 9.1 worked example: 두 table의 실험 branch

가상 branch `exp-1`이 `camera_frames` table snapshot C10과 `detections` table snapshot D20을 함께 가리킨다고 하자. Main branch는 같은 시간에 C11과 D21로 진행할 수 있다. 실험 query가 `exp-1` reference를 사용하면 두 table의 조합을 재현하기 쉽다. 하지만 각 table 내부에는 여전히 자기 Iceberg snapshot ID와 metadata file이 있다. 문서에는 “Nessie reference = 여러 table 상태를 고르는 catalog-level 이름”, “Iceberg snapshot = 한 table의 file set”이라고 명시한다.

## 10. Copy-on-Write와 Merge-on-Read는 처리 방식이고, Deletion Vector는 삭제 표현이다

Iceberg configuration 문서는 delete, update, merge mode를 `copy-on-write` 또는 `merge-on-read`로 설정할 수 있다고 설명한다. [Apache Iceberg Configuration](https://iceberg.apache.org/docs/latest/configuration/)

Copy-on-Write와 Merge-on-Read는 변경을 언제 반영할지에 대한 처리 방식이다. Copy-on-Write는 변경 결과가 반영된 data file을 다시 쓰는 방향이다. Merge-on-Read는 기존 data file을 즉시 모두 다시 쓰지 않고, delete file 또는 deletion vector 같은 삭제 표현과 새로 추가된 data file을 read time에 함께 적용하는 방향이다.

Deletion Vector는 COW/MOR와 같은 층위의 “세 번째 update mode”가 아니다. Iceberg spec v3는 binary deletion vectors를 추가하고, deletion vectors가 특정 data file의 삭제된 row positions를 bitmap으로 표현한다고 설명한다. [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/) 즉 DV는 특히 position delete를 표현하는 format 기능이며, reader가 data file을 읽을 때 삭제 row를 제외하도록 돕는다.

Update는 보통 “기존 row 삭제 + 새 row 추가”로 모델링된다. MOR에서 DV가 기존 row의 삭제를 표시하더라도, 변경된 새 값은 별도의 data file에 append되거나 다른 방식으로 data file에 기록되어야 한다. DV는 raw data file bytes를 즉시 작게 만들지 않는다.

따라서 “COW, MOR, DV 중 무엇이 낫다”라고 비교하지 않는다. 비교 축은 COW 대 MOR이고, 그 안에서 delete files, deletion vectors, reader support, table format version, compaction budget, read frequency, update locality가 비용을 바꾼다고 적는다.

```text
값 하나 수정의 세 가지 개념 경로

COW mode:
  old data file → rewrite affected rows into replacement data file → new snapshot

MOR mode with delete files:
  old data file + delete file + new data file for changed/inserted rows → reader merges

MOR mode with deletion vector:
  old data file + DV bitmap for deleted positions + new data file for changed/inserted rows
      → reader masks deleted old rows and reads replacement rows
```

### 10.1 worked example: 128 MiB 파일에서 한 row 삭제

가상 Parquet file이 128 MiB이고 그 안의 한 row를 삭제한다고 하자. COW는 영향을 받은 file을 새 file로 다시 쓸 수 있다. MOR position delete는 삭제 row의 file path와 position을 별도 delete file에 기록할 수 있다. MOR에서 DV를 지원한다면 해당 data file의 position bitmap에 삭제 표시를 둘 수 있다.

Update라면 한 단계가 더 필요하다. 삭제된 old row를 대신할 new row bytes는 새 data file 등에 기록되어야 한다. DV는 old row를 가리는 표현이지, 새 값을 저장하는 장소가 아니다.

COW는 읽기가 단순해질 수 있지만 적은 변경에도 큰 rewrite가 생길 수 있다. MOR은 write를 작게 만들 수 있지만 read 때 delete 적용, replacement row 병합, metadata 관리 비용이 생긴다. 이 계산은 설명용이며 실제 rewrite 크기, compression ratio, reader cost는 측정해야 한다.

## 11. Iceberg metadata tables는 디버깅 창이지 원본 데이터 대체물이 아니다

Iceberg Spark docs는 snapshots, history, entries, manifests, files, all_data_files, all_entries 같은 metadata tables를 예로 보여 준다. [Apache Iceberg Spark Queries](https://iceberg.apache.org/docs/latest/spark-queries/) `files`류 metadata table은 현재 snapshot의 data/delete files와 metrics를 보는 데 유용하다. `snapshots`는 snapshot ID, operation, manifest list, summary를 확인하는 데 유용하다. `all_*` metadata tables는 여러 snapshot에 걸친 metadata를 볼 수 있지만, 같은 file이나 manifest가 여러 snapshot에 나타날 수 있다는 주의가 필요하다. [Apache Iceberg Spark Queries](https://iceberg.apache.org/docs/latest/spark-queries/) 이 metadata query는 운영에서 원인을 찾는 관측 도구이지, raw sensor frames나 LiDAR point cloud bytes를 대신 저장하는 공간이 아니다. 아래는 실행 명령이 아니라 관찰 질문을 표현한 **개념 SQL 조각**이다.

```text
개념 SQL 조각, 운영 실행용 아님

-- 어떤 snapshot들이 있고, 각 snapshot은 어떤 manifest list를 가리키는가?
SELECT snapshot_id, operation, manifest_list FROM table.snapshots;

-- 현재 snapshot이 어떤 data/delete file을 참조하는가?
SELECT content, file_path, record_count, file_size_in_bytes FROM table.files;
```

## 12. Table file bytes와 외부 raw asset reference를 섞지 않는다

Iceberg의 `data file bytes`라고 쓰면 Parquet/ORC/Avro 같은 행 데이터를 담는 data files의 bytes를 뜻하도록 제한한다. Delete files, deletion vector blobs, manifests, manifest lists, table metadata JSON은 data file bytes가 아니라 table을 관리하기 위한 별도 파일·메타데이터 범위다.

전체 저장량을 말해야 한다면 “Iceberg 관리 저장량”처럼 범위를 명시한다. 이 값은 정의에 따라 data files + delete 관련 파일 + manifests/manifest lists + table metadata를 포함할 수 있다. 어떤 범위까지 더했는지 문서와 측정표에 적어야 한다.

자율주행이나 로보틱스 dataset에서는 raw camera frame, LiDAR packet, rosbag, video, calibration blob이 table 외부 object로 따로 저장되고, table에는 URI, checksum, timestamp, bounding box, feature summary만 들어갈 수 있다. 이 경우 Iceberg 관리 저장량이 50 GiB라고 해서 raw asset 총량도 50 GiB라고 말할 수 없다. 반대로 raw camera/LiDAR asset이 1 TiB라고 해서 Iceberg data files가 1 TiB이거나 GPU가 1 TiB를 직접 처리한다고 말해서도 안 된다. Table은 raw assets를 참조하는 manifest 역할을 할 수 있지만, 참조된 외부 bytes의 보존·권한·checksum·lifecycle은 별도 계약이다. 문서에는 “Iceberg-managed table bytes”, “Iceberg data file bytes”, “external raw asset bytes”를 따로 집계한다. 또 “GPU input bytes”는 실제 decoder와 transfer 경로에서 측정한 값만 사용한다.

### 12.1 worked example: 카메라 프레임 catalog table

가상 table `camera_index`가 다음 column을 가진다고 하자. `frame_id`, `capture_time`, `vehicle_id`, `image_uri`, `image_sha256`, `width`, `height`, `label_count`. Parquet table에는 URI와 metadata rows가 저장된다. 실제 JPEG 또는 raw Bayer frame은 object store의 다른 prefix에 저장된다. 쿼리로 특정 시간대의 `image_uri` 10만 개를 찾는 것은 Iceberg table scan이다. 그 URI가 가리키는 image 10만 개를 decode하는 것은 별도 asset I/O와 compute workload다. 이 둘을 합쳐 “Iceberg가 image 1 TiB를 scan했다”고 쓰면 계층을 잘못 표현한 것이다.

## 13. 안전한 문서 표현 규칙

“Parquet supports Bloom filters”라고 쓰려면 reader와 writer 구현 지원 여부를 별도 확인한다. “Arrow zero-copy”라고 쓰려면 어느 process boundary와 memory domain에서 copy가 없었는지 적는다. “Iceberg snapshot”이라고 쓰면 snapshot ID와 catalog reference, table metadata file을 가능한 함께 기록한다. “Nessie branch”라고 쓰면 branch가 가리키는 commit hash와 각 table snapshot을 구분한다.

“Predicate pushdown으로 빨라졌다”라고 쓰려면 file pruning, row group pruning, page index, projection 중 어느 효과인지 측정 evidence를 붙인다. “COW보다 MOR이 빠르다”라고 쓰지 말고, write latency, read latency, compaction cost, storage amplification의 측정 범위를 표시한다. DV는 COW/MOR와 나란한 mode가 아니라 delete representation이라고 쓴다.

“Raw 1 TiB를 GPU zero-copy 처리했다” 같은 문장은 실제 measurement와 transfer path 없이는 금지한다. “metadata만 읽었다”라고 쓰려면 catalog, table metadata, manifest list, manifest, Parquet footer 중 어디까지 읽었는지 구체화한다.

## 14. 전체 경로를 한 장으로 연결한다

```text
External raw assets, optional
  camera.raw / lidar.pcd / video.mp4
        ↑ referenced by URI/checksum, not automatically table bytes

Iceberg table commit path
  rows or metadata records
    → Parquet data files
    → Iceberg manifest entries with metrics
    → manifest list for snapshot
    → table metadata JSON with current snapshot
    → catalog commit, optionally Nessie reference

Query read path
  catalog reference
    → pinned table snapshot
    → file pruning via manifests
    → Parquet footer and row group pruning
    → column projection and page decoding
    → Arrow or engine-native in-memory batches
    → CPU/GPU compute only if measured path supports it
```

이 도식은 “어디에서 bytes가 줄어드는가”와 “어디에서 consistency가 생기는가”를 분리하게 해 준다. Parquet는 file 내부 layout과 metadata를 제공한다. Arrow는 in-memory columnar interchange와 compute-friendly layout을 제공한다. Iceberg는 table의 file set, snapshot, commit protocol을 제공한다. Nessie는 catalog reference와 branch/tag/commit semantics를 제공한다. GPU 가속은 이 모든 층 위에서 특정 reader, decoder, transfer, kernel이 실제로 지원하고 측정해야 말할 수 있는 실행 특성이다.

## 15. 복습 문제

1. Parquet row group과 column chunk의 관계는 무엇인가?
   - 짧은 답: 파일은 row group들로 나뉘고, 각 row group은 dataset의 각 column에 대해 하나의 column chunk를 가진다.
2. Projection과 predicate pushdown은 어떻게 다른가?
   - 짧은 답: Projection은 필요한 column만 읽는 것이고, predicate pushdown/pruning은 조건에 맞지 않는 file·row group·page를 제외하는 것이다.
3. Arrow를 storage engine이라고 부르면 왜 부정확한가?
   - 짧은 답: Arrow는 in-memory columnar format과 serialization protocol이며, table commit, WAL, catalog, compaction 같은 storage engine 기능을 자체로 제공하지 않는다.
4. Iceberg write에서 data file upload와 catalog commit을 분리해야 하는 이유는 무엇인가?
   - 짧은 답: 파일 존재만으로 공식 table 상태가 되지 않으며, 새 metadata pointer를 atomic commit해야 독자가 일관된 snapshot으로 볼 수 있기 때문이다.
5. Nessie branch와 Iceberg snapshot의 차이는 무엇인가?
   - 짧은 답: Nessie branch는 catalog-level reference로 여러 table 상태를 commit graph에서 가리킬 수 있고, Iceberg snapshot은 한 table의 data/delete file 집합 version이다.
