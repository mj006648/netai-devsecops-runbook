# 02. Page, record와 buffer pool

[이 책 목차](README.md) · [이전: 관계, SQL과 NULL](01-relations-sql-and-null.md) · [다음: B-tree와 LSM index](03-btree-and-lsm-indexes.md)

DBMS는 row마다 device I/O를 요청하지 않고 고정 크기 page를 읽고 쓴다. Record layout, page header, free space, buffer frame과 dirty state를 알면 scan 비용과 WAL·checkpoint를 연결할 수 있다.

이 장의 SQL, page 수와 출력은 교육용 단순화이며 실제 PostgreSQL에서 실행한 결과가 아니다.

## 행이 페이지의 바이트가 되기까지

**페이지(page)**는 저장 엔진이 데이터 파일과 메모리 사이에서 읽고 쓰며 무결성을 관리하는 고정 크기 블록이다. 운영체제의 가상 메모리 페이지나 웹 페이지와 이름은 같지만 이 장에서는 데이터베이스 파일의 블록을 뜻한다. 페이지 크기는 엔진과 설정에 따라 다르며 여기서는 8 KiB를 손계산에 사용한다. **레코드(record)**는 논리 행의 한 버전을 자료형 규칙에 따라 바이트로 인코딩한 저장 단위다. 레코드에는 사용자 열 외에도 NULL 표시, 길이, 트랜잭션 가시성 정보가 들어갈 수 있다.

**힙(heap)**은 정렬된 키 순서를 본질적으로 보장하지 않는 테이블 저장 구조다. 메모리 자료구조의 이진 힙과 다른 뜻이다. 새 레코드는 여유 공간이 있는 힙 페이지에 놓이고, 인덱스는 키에서 힙 위치로 가는 별도 경로를 제공할 수 있다. 힙의 물리 위치는 행의 업무 식별자가 아니다. 갱신이나 페이지 정리로 레코드 버전의 위치가 달라질 수 있기 때문이다.

가변 길이 레코드를 다루는 **슬롯 페이지(slotted page)**는 페이지 머리말, 슬롯 배열, 빈 공간, 레코드 payload를 분리한다. **슬롯(slot)**은 레코드의 시작 오프셋과 길이 등을 가진 작은 간접 참조 항목이다. 상위 구조가 `(page 42, slot 7)`을 가리키는 동안 페이지 내부 정리 과정이 payload를 7000번 오프셋에서 6500번으로 옮겨도 slot 7의 오프셋만 바꾸면 참조를 유지할 수 있다.

## 슬롯과 payload 삭제를 숫자로 추적하기

8,192바이트 페이지에서 머리말 128바이트, 슬롯 하나 4바이트라고 하자. 레코드 A, B, C의 payload 크기가 각각 100, 300, 200바이트다. 슬롯은 앞쪽에서 자라고 payload는 뒤쪽에서 역방향으로 쌓인다고 단순화한다.

| 상태 | 슬롯 배열 | 살아 있는 payload | 연속 빈 공간 계산 |
|---|---:|---:|---:|
| 초기 | 0B | 0B | `8192-128=8064B` |
| A 삽입 | 4B | 100B | `8192-128-4-100=7960B` |
| B 삽입 | 8B | 400B | `8192-128-8-400=7656B` |
| C 삽입 | 12B | 600B | `8192-128-12-600=7452B` |

B를 삭제했다고 payload 300바이트가 즉시 하나의 연속 빈 구간으로 합쳐진다고 가정하면 안 된다. 구현은 slot 2를 미사용으로 표시하고 B 자리를 구멍으로 남길 수 있다. 이때 총 재사용 가능 공간은 늘어도 가장 큰 연속 공간은 다를 수 있다. 350바이트 레코드 D를 넣으려면 페이지 내부 압축으로 C나 A의 payload를 옮겨 300바이트 구멍과 기존 빈 공간을 연결하거나, 다른 페이지를 선택할 수 있다. 압축 뒤에도 A와 C의 슬롯 번호를 유지하고 슬롯 안 오프셋만 바꾸는 것이 간접 참조의 장점이다.

삭제도 곧바로 바이트를 0으로 덮는 것과 같지 않다. MVCC 엔진에서는 오래된 스냅샷이 삭제 전 버전을 볼 수 있어야 하므로 레코드를 논리적으로 죽은 상태로 표시하고 나중에 안전한 시점에 회수할 수 있다. 따라서 DELETE 직후 파일 크기, 페이지의 재사용 가능 공간, 질의에 보이는 행 수는 서로 다른 값이다.

## 버퍼 풀, 프레임, pin, latch의 역할

**버퍼 풀(buffer pool)**은 데이터베이스 페이지 사본을 보관하는 DBMS 관리 메모리 영역이다. 그 안의 **프레임(frame)** 하나가 페이지 하나를 담는다. 페이지 ID는 파일과 블록 번호 같은 논리 주소이고, 프레임 번호는 현재 프로세스 메모리 안의 자리다. 페이지 42가 오늘 frame 7에 있어도 교체 후 다음에는 frame 19에 들어갈 수 있다.

**pin**은 실행기가 프레임을 사용하는 동안 버퍼 관리자가 그 프레임을 다른 페이지로 교체하지 못하게 잡는 참조다. 여러 사용자가 같은 프레임을 pin하면 pin count가 늘어난다. 사용이 끝난 주체는 반드시 unpin해야 한다. pin 누락은 교체 가능한 프레임을 줄여 메모리가 충분해 보여도 모든 프레임이 사용 중인 상황을 만들 수 있다.

**latch**는 메모리 안의 페이지나 버퍼 관리자 자료구조를 아주 짧은 임계 구역에서 보호하는 동기화 장치다. 트랜잭션의 행 잠금(lock)은 다른 트랜잭션과의 논리 충돌을 제어하고, latch는 슬롯 배열을 옮기는 순간 같은 메모리 구조를 동시에 망가뜨리지 않게 한다. latch를 잡은 채 저장 장치 I/O 같은 긴 작업을 기다리면 다른 작업이 막힐 수 있어 구현은 보호 범위를 세심하게 정한다.

**dirty** 프레임은 메모리 페이지가 데이터 파일의 저장 사본보다 새롭다는 뜻이다. dirty는 손상되었다는 뜻도, 커밋되었다는 뜻도 아니다. 아직 커밋되지 않은 변경이 포함될 수도 있고, 커밋된 변경이 아직 데이터 파일에 쓰이지 않은 상태일 수도 있다. **WAL(Write-Ahead Log)**은 데이터 페이지보다 먼저 기록하는 변경 설명 로그다. 페이지를 디스크에 쓰기 전에 그 페이지 변경을 복구하는 데 필요한 WAL이 먼저 durable해야 한다는 순서 규칙이 핵심이다.

## cache miss와 dirty victim 교체를 시점별로 추적하기

버퍼 풀이 세 프레임뿐이고 현재 상태가 다음과 같다고 하자.

| frame | page | pin count | dirty | 최근 사용 |
|---:|---:|---:|---|---|
| 0 | 10 | 1 | 아니오 | 오래됨 |
| 1 | 20 | 0 | 예 | 가장 오래됨 |
| 2 | 30 | 0 | 아니오 | 최근 |

실행기가 page 40을 요구한다. page table에 40이 없으므로 miss다. frame 0은 가장 오래되었어도 pin count 1이라 victim이 될 수 없다. 정책이 frame 1을 고른다고 하자.

1. 버퍼 관리자는 frame 1을 교체 대상으로 예약해 다른 스레드가 동시에 재사용하지 못하게 한다.
2. page 20이 dirty이므로 해당 페이지의 page LSN보다 WAL의 durable 위치가 뒤에 있는지 확인한다.
3. 필요한 WAL이 아직 로그 버퍼에만 있다면 로그 관리자가 WAL을 먼저 flush한다.
4. 그다음 frame 1의 page 20 이미지를 데이터 파일의 올바른 블록에 쓴다.
5. page table에서 `20 → frame 1` 대응을 제거한다.
6. 저장 관리자에게 page 40 읽기를 요청해 frame 1의 내용을 채운다.
7. checksum과 머리말을 확인한 뒤 `40 → frame 1` 대응을 게시하고 요청자를 위해 pin count를 1로 만든다.
8. 실행기가 레코드 처리를 끝내면 unpin해 count를 0으로 내린다.

이 순서를 뒤집어 dirty page를 먼저 쓰고 WAL을 나중에 쓰면, 데이터 파일에는 변경 일부가 있는데 장애 뒤 그 변경을 설명할 로그가 없는 상태가 생길 수 있다. 이것이 write-ahead라는 이름의 이유다. 실제 엔진은 동시 I/O, 상태 비트, background writer를 사용하므로 세부 단계는 더 복잡하지만 로그 선행이라는 불변 조건을 중심으로 읽는다.

모든 unpinned frame이 즉시 교체되는 것은 아니다. 교체 정책은 최근성, 사용 비트, 접근 빈도 등을 근사해 victim을 고른다. 반대로 모든 프레임이 pinned이면 정책이 아무리 좋아도 즉시 쓸 victim이 없다. 요청은 기다리거나 별도 오류 경로를 탈 수 있다. “buffer pool이 3페이지”라는 용량과 “현재 교체 가능한 페이지가 몇 개인가”는 다른 질문이다.

## SELECT가 인덱스에서 페이지와 가시성을 거쳐 반환되는 예

```sql
SELECT name
FROM accounts
WHERE account_id = 73 AND active = TRUE;
```

인덱스 루트 page 5는 frame 0에 있고 pin count 0이라고 하자. 실행기는 이를 pin하고 키 73이 잎 page 18에 있음을 찾은 뒤 unpin한다. page 18이 miss이면 위 교체 절차로 읽고, 잎 엔트리 `(heap page 42, slot 7)`을 얻는다. 힙 page 42가 frame 2에 이미 있으면 hit이므로 장치 읽기는 없다. 실행기는 frame 2를 pin하고 짧은 shared latch 아래 slot 7의 오프셋과 길이를 안정적으로 읽는다.

slot 7이 가리키는 첫 레코드 버전의 `active=TRUE`라도 현재 스냅샷에 보이지 않을 수 있다. 예를 들어 다른 트랜잭션이 만들고 아직 커밋하지 않은 버전이면 이전 버전을 찾아야 한다. 보이는 버전의 `active`가 TRUE일 때만 name을 반환한다. 마지막으로 latch와 pin을 해제한다. 이 경로에서 인덱스 후보 발견, 버퍼 hit, 레코드 가시성, SQL 조건 TRUE는 서로 다른 관문이다.

## UPDATE와 flush의 전후 상태

같은 계정의 잔액을 100에서 80으로 바꾼다고 하자. 실행기는 보이는 기존 버전을 확인하고 새 버전 또는 제자리 변경을 엔진 규칙에 따라 만든다. 변경을 설명하는 WAL 레코드가 LSN 900이고 수정된 page 42의 page LSN도 900이 된다. frame 2는 dirty로 표시된다. COMMIT에 필요한 WAL이 durable 위치 900까지 기록되면 클라이언트가 성공을 받을 수 있다. 이때 데이터 파일 page 42는 여전히 옛 값 100을 담을 수 있다.

나중에 checkpoint나 교체가 frame 2를 flush하면 데이터 파일도 새 페이지 이미지를 얻는다. flush 직전 durable WAL 위치가 850이라면 먼저 900까지 WAL을 기록해야 한다. 장애가 WAL durable 뒤 데이터 page flush 전에 발생하면 복구가 로그를 재생해 80을 복원한다. 이 설명은 WAL 기반 복구의 핵심 순서이며 정확한 redo/undo와 full-page image 정책은 엔진마다 다르다.

## 관측값과 반례

- buffer hit가 99%여도 남은 1%가 느린 임의 읽기이고 많은 요청이 그 I/O를 기다리면 지연이 클 수 있다.
- dirty page 수가 많다는 사실만으로 데이터 손실을 뜻하지 않는다. WAL durable 위치, checkpoint 진행, 쓰기 처리량과 함께 본다.
- 페이지당 평균 100행이라는 통계로 모든 페이지가 100행이라고 단정할 수 없다. 가변 길이 값과 죽은 버전 때문에 편차가 생긴다.
- 파일 크기가 줄지 않아도 삭제 공간이 내부에서 재사용될 수 있다. 반대로 논리 행 수가 줄었어도 오래된 스냅샷 때문에 즉시 회수하지 못할 수 있다.
- DBMS 버퍼 풀과 운영체제 페이지 캐시가 함께 있으면 같은 데이터가 두 계층에 있을 수 있다. 어느 계층의 hit 수치인지 확인한다.

## 유도 문제 5개와 해설

### 문제 1

8 KiB 페이지에 머리말 128B, 슬롯 4B, 고정 72B 레코드를 넣는다. 다른 오버헤드를 무시하면 최대 몇 개인가?

**해설:** 레코드 하나당 슬롯과 payload가 `4+72=76B`를 쓴다. 사용 가능 공간은 `8192-128=8064B`이고 `floor(8064/76)=106`이다. 106개는 8,056B를 써 8B가 남고 107개는 넘친다. 실제 레코드 정렬과 머리말은 이 단순 결과를 바꿀 수 있다.

### 문제 2

300B payload를 삭제했는데 350B 새 레코드를 같은 페이지에 바로 넣을 수 있는가?

**해설:** 삭제 구멍 300B만 보면 부족하다. 페이지 다른 곳의 연속 빈 공간과 합칠 수 있는지, 압축이 허용되는지, 슬롯을 재사용할 수 있는지를 알아야 한다. 총 free space와 가장 큰 연속 free space를 구분해야 답할 수 있다.

### 문제 3

가장 오래된 frame의 pin count가 2이고 두 번째 오래된 frame은 unpinned dirty다. 어느 것을 victim으로 고를 수 있는가?

**해설:** pinned frame은 사용 중이므로 교체하면 안 된다. 정책은 두 번째 frame을 후보로 삼을 수 있지만 dirty이므로 WAL 선행 조건을 확인하고 필요하면 WAL flush 뒤 page write를 해야 한다. 오래되었다는 한 기준만으로 victim을 확정하지 않는다.

### 문제 4

WAL durable 위치가 1,200이고 dirty page의 page LSN이 1,150이면 페이지를 쓸 수 있는가? page LSN이 1,250이면 무엇이 먼저인가?

**해설:** 1,150 변경을 설명하는 로그는 durable 위치 안에 있으므로 WAL 선행 조건을 만족한다. page LSN 1,250이면 로그를 최소 1,250까지 먼저 durable하게 만든 뒤 페이지를 쓴다.

### 문제 5

인덱스가 `(page 42, slot 7)`을 찾았고 page 42가 buffer hit다. 왜 결과 행 반환이 아직 보장되지 않는가?

**해설:** slot은 후보 레코드 위치를 제공할 뿐이다. 레코드가 현재 스냅샷에 보이는지, 삭제되었는지, 잔여 SQL 조건이 TRUE인지 확인해야 한다. hit는 저장 장치 읽기를 피했다는 뜻이지 논리 조건을 만족했다는 뜻이 아니다.

![02. Page, record와 buffer pool 흐름](assets/page-buffer-path.svg)

## 1. 먼저 알아야 할 단어

| 용어 | 뜻과 실제 위치 |
| --- | --- |
| Page | Storage와 memory 사이 I/O·관리의 고정 크기 block |
| Record | 한 row version을 byte로 encode한 저장 단위 |
| Slot | Page 안 record 위치를 간접 참조하는 entry |
| Slotted page | Header와 slot array로 variable-length record를 관리하는 page 형식 |
| Buffer pool | Disk page를 memory frame에 cache하는 DBMS 영역 |
| Frame | Buffer pool에서 page 하나가 들어가는 memory slot |
| Page ID | Database file과 page number를 식별하는 logical address |
| Pin count | Executor가 frame을 사용 중이어서 eviction하면 안 되는 횟수 |
| Dirty | Memory page가 storage copy보다 새로워 flush가 필요함 |
| Eviction | 새 page 공간을 위해 victim frame을 재사용하는 과정 |

용어는 이름만 외우지 않고 어느 memory·file·catalog object에 존재하는지 연결한다.

## 2. 실제로 존재하는 객체

- Data file의 page 42

- Page header의 slot count와 free-space pointer

- Slot 7이 가리키는 record offset

- Buffer table의 pageID→frame mapping

- Frame metadata의 pin/dirty/reference bit

- Storage device의 durable page image

객체마다 owner와 lifetime이 다르므로 SQL text와 storage byte를 같은 대상으로 보지 않는다.

## 3. 입력에서 결과까지

```mermaid
flowchart LR
    I["입력"] --> P["해석·계획"]
    P --> E["실행 주체"]
    E --> M["중간 상태"]
    M --> O["결과"]
```

1. Executor가 page ID 42의 record를 요청한다.

2. Buffer manager가 page table에서 42를 찾는다.

3. Hit이면 frame pin count를 올린다.

4. Miss이면 free frame 또는 victim을 고른다.

5. Dirty victim이면 WAL rule과 flush 상태를 확인하고 page write를 수행한다.

6. Storage manager가 page 42를 frame에 읽는다.

7. Checksum과 page header를 검증할 수 있다.

8. Executor가 slot array로 record offset을 찾는다.

9. Update는 record와 page를 바꾸고 frame을 dirty로 표시한다.

10. 사용이 끝나면 unpin하고 나중에 checkpoint/background writer가 flush할 수 있다.

## 4. 연결되는 숫자 예제

- page size 8KiB = 8192 bytes

- header 128 bytes

- slot entry 4 bytes × 100 = 400 bytes

- record 평균 72 bytes × 100 = 7200 bytes

- 남는 공간 = 8192-128-400-7200 = 464 bytes

숫자는 단위를 맞추고 어느 층의 추정값인지 표시해야 한다.

## 5. 왜 이 구조가 필요한가

Page size는 DBMS·table space에 따라 다르므로 8KiB는 이 장의 교육 모형이다.

Variable-length record는 page 안에서 이동해도 slot number를 유지할 수 있어 indirect reference가 유용하다.

Buffer pool hit는 storage read를 피하지만 CPU filter와 visibility 검사는 남는다.

Pin과 lock은 다르다. Pin은 frame lifetime, lock은 concurrency 의미를 다룬다.

OS page cache와 DBMS buffer pool이 동시에 존재하면 double caching을 고려해야 한다.

Dirty page를 flush했다고 transaction commit이 되는 것이 아니며 WAL durability와 transaction state가 별도다.

## 6. 실행 중 관찰 질문

- 입력 row 수와 출력 row 수는 각각 얼마인가?

- Memory object와 durable file object는 무엇인가?

- 어느 component가 다음 상태를 만들었는가?

- 추정치와 실제 측정치를 섞지 않았는가?

- Failure 뒤 재시도하면 side effect가 중복되는가?

- Cache가 차가울 때와 따뜻할 때 결과가 달라지는가?

## 7. 흔한 오해와 반례

- 오해: Page는 SQL row 하나와 같다.

- 오해: Buffer hit이면 query cost가 0이다.

- 오해: Dirty frame은 즉시 device에 기록된다.

- 오해: Pin count가 0이면 반드시 eviction된다.

- 오해: Record address는 영구 business key다.

반례는 구현이 틀렸다는 뜻보다 적용 조건이 빠졌음을 보여 준다.

## 8. 작은 설계 점검

1. Logical object와 physical object를 각각 적는다.

2. Read path와 write path를 따로 그린다.

3. Memory에서만 끝난 상태와 durable 상태를 구분한다.

4. Concurrent transaction 또는 worker가 끼어드는 지점을 찾는다.

5. Cost를 row, page, byte, network 단위로 손계산한다.

6. 공식 문서의 보장과 교육용 가정을 구분한다.

## 9. 문제

1. 8KiB page에 header 128B, slot 4B, record 72B라면 100개 뒤 여유는?

2. Pin count와 row lock의 차이는?

3. Commit 때 모든 dirty page를 flush해야 하는가?

## 10. 해설

1. 8192-128-400-7200=464B다.

2. Pin은 memory frame 재사용 방지이고 row lock은 concurrent transaction 충돌을 제어한다.

3. WAL 기반 system에서는 관련 WAL durability가 먼저 보장되면 data page는 이후 flush할 수 있다.

## 11. 공식 자료

- [PostgreSQL current documentation](https://www.postgresql.org/docs/current/)

- [CMU 15-445/645 Fall 2024](https://15445.courses.cs.cmu.edu/fall2024/syllabus.html)

다음 장에서는 이 장의 logical object가 더 구체적인 storage 또는 execution state로 바뀌는 과정을 이어서 본다.


## 보강: page 42 cache miss의 실제 경로

![페이지와 버퍼 풀 읽기 경로](assets/page-buffer-path.svg)

Page는 저장 엔진이 파일과 메모리 사이에서 옮기는 고정 크기 블록이고 record는 그 안의 행 표현이다. executor가 page 42를 요구하면 buffer manager는 `(relation file, fork, block 42)` 같은 buffer tag로 hash table을 조회한다. miss이면 교체 가능한 frame 7을 고르고 파일 block 42를 읽는다. frame을 pin한다는 말은 “이 요청이 사용하는 동안 교체하지 말라”는 참조를 잡는다는 뜻이다. 필터가 레코드를 처리한 뒤 pin을 놓지만, page 사본은 재사용을 위해 버퍼 풀에 남을 수 있다.
