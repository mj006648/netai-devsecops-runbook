# 03. B-tree와 LSM index

[이 책 목차](README.md) · [이전: Page, record와 buffer pool](02-pages-records-and-buffer-pools.md) · [다음: Scan, filter와 join](04-scans-filters-and-joins.md)

Index는 table의 모든 row를 읽지 않고 candidate를 찾는 physical structure다. B-tree는 정렬된 page tree를, LSM(Log-Structured Merge) tree는 memory write와 immutable run·compaction을 사용한다.

이 장의 SQL, page 수와 출력은 교육용 단순화이며 실제 PostgreSQL에서 실행한 결과가 아니다.

## 1. 먼저 알아야 할 단어

| 용어 | 뜻과 실제 위치 |
| --- | --- |
| Index | Search key에서 row location 또는 value로 가는 보조 structure |
| B-tree | 높이가 균형인 multi-way search tree |
| Root page | B-tree 탐색이 시작되는 최상위 page |
| Internal page | Key range와 child pointer를 저장하는 page |
| Leaf page | 정렬된 key와 row reference/value를 저장하는 page |
| Fan-out | Internal node 하나가 가리킬 수 있는 child 수 |
| LSM tree | Write를 memory와 sequential file로 모아 나중에 merge하는 structure |
| Memtable | LSM의 mutable in-memory sorted structure |
| SSTable | Sorted String Table의 약자로 immutable sorted file |
| Compaction | 여러 sorted run을 merge하며 오래된 version을 정리하는 작업 |

용어는 이름만 외우지 않고 어느 memory·file·catalog object에 존재하는지 연결한다.

## 2. 실제로 존재하는 객체

- Catalog의 index definition

- B-tree root/internal/leaf pages

- Leaf entry의 key와 row identifier

- LSM memtable와 WAL

- Level별 SSTable files

- Bloom filter와 sparse index metadata

- Compaction output file와 obsolete input

객체마다 owner와 lifetime이 다르므로 SQL text와 storage byte를 같은 대상으로 보지 않는다.

## 3. 입력에서 결과까지

```mermaid
flowchart LR
    I["입력"] --> P["해석·계획"]
    P --> E["실행 주체"]
    E --> M["중간 상태"]
    M --> O["결과"]
```

1. Query predicate에서 searchable key를 만든다.

2. Planner가 index condition과 expected selectivity를 계산한다.

3. B-tree는 root에서 key range를 비교한다.

4. Internal child pointer를 따라 leaf에 도달한다.

5. Leaf에서 matching entry range를 순회한다.

6. Row reference로 table page를 읽거나 covering value를 사용한다.

7. LSM write는 WAL 뒤 memtable에 들어간다.

8. Memtable이 차면 immutable 상태를 거쳐 SSTable로 flush된다.

9. Read는 memtable과 후보 SSTable을 확인한다.

10. Compaction이 overlapping run을 merge하고 obsolete version을 제거한다.

## 4. 연결되는 숫자 예제

- B-tree fan-out 200

- 1,000,000 leaf entries

- leaf pages 5,000이라고 가정

- level 1 internal pages 25

- root 1 page이면 root→internal→leaf 약 3 page path

숫자는 단위를 맞추고 어느 층의 추정값인지 표시해야 한다.

## 5. 왜 이 구조가 필요한가

B-tree의 B는 binary가 아니다. 한 page에 많은 key와 child를 담아 fan-out을 높인다.

Range scan은 leaf 정렬과 sibling traversal을 이용하지만 random table lookup이 많으면 heap access가 비쌀 수 있다.

LSM은 write amplification, read amplification, space amplification 사이 trade-off가 있다.

Bloom filter는 key가 없을 가능성을 빠르게 알려 주지만 false positive가 있어 실제 file 확인이 남는다.

Compaction은 background 작업이지만 CPU·I/O와 tail latency를 사용한다.

Index가 많으면 read 후보는 늘지만 INSERT/UPDATE와 storage 비용도 늘어난다.

## 6. 실행 중 관찰 질문

- 입력 row 수와 출력 row 수는 각각 얼마인가?

- Memory object와 durable file object는 무엇인가?

- 어느 component가 다음 상태를 만들었는가?

- 추정치와 실제 측정치를 섞지 않았는가?

- Failure 뒤 재시도하면 side effect가 중복되는가?

- Cache가 차가울 때와 따뜻할 때 결과가 달라지는가?

## 7. 흔한 오해와 반례

- 오해: B-tree는 항상 세 level이다.

- 오해: Index lookup은 table page를 절대 읽지 않는다.

- 오해: LSM은 write가 항상 한 번만 device에 기록된다.

- 오해: Bloom filter가 true면 key가 반드시 있다.

- 오해: Index column 순서는 WHERE에 적은 순서와 무관하다.

반례는 구현이 틀렸다는 뜻보다 적용 조건이 빠졌음을 보여 준다.

## 8. 작은 설계 점검

1. Logical object와 physical object를 각각 적는다.

2. Read path와 write path를 따로 그린다.

3. Memory에서만 끝난 상태와 durable 상태를 구분한다.

4. Concurrent transaction 또는 worker가 끼어드는 지점을 찾는다.

5. Cost를 row, page, byte, network 단위로 손계산한다.

6. 공식 문서의 보장과 교육용 가정을 구분한다.

## 9. 문제

1. Fan-out 200인 B-tree가 낮은 높이를 갖는 이유는?

2. Bloom filter가 positive면 key 존재를 확정하는가?

3. Index를 추가하면 write가 느려질 수 있는 이유는?

## 10. 해설

1. 한 internal page가 많은 child를 가리켜 entry 수가 커져도 level 증가가 느리기 때문이다.

2. 아니다. False positive가 가능해 SSTable index/data 확인이 필요하다.

3. Table 변경마다 index entry와 WAL·page 또는 LSM run도 갱신해야 하기 때문이다.

## 11. 공식 자료

- [PostgreSQL current documentation](https://www.postgresql.org/docs/current/)

- [CMU 15-445/645 Fall 2024](https://15445.courses.cs.cmu.edu/fall2024/syllabus.html)

다음 장에서는 이 장의 logical object가 더 구체적인 storage 또는 execution state로 바뀌는 과정을 이어서 본다.


## 보강: 같은 키 조회가 만드는 서로 다른 중간 상태

B-tree 조회는 root page의 separator key를 비교해 child page 번호를 고르고 leaf page에서 key와 row pointer를 찾는다. LSM-tree 조회는 먼저 mutable memtable, immutable memtable, 여러 SSTable의 key range와 Bloom filter를 확인한다. SSTable은 정렬되어 한번 기록된 뒤 제자리 변경하지 않는 파일이다. Bloom filter의 “없음”은 파일 읽기를 건너뛸 수 있는 강한 답이지만 “있을 수 있음”은 실제 key 존재를 보장하지 않는다. Compaction은 겹치는 SSTable을 읽어 새 정렬 파일로 병합하므로 읽기 증폭을 줄이는 대신 배경 I/O와 쓰기 증폭을 만든다.
