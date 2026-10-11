# 07. 메모리 할당·회수·swap·OOM

[이 책 목차](README.md) · [이전](06-paging-virtual-memory.md) · [다음](08-io-files-filesystems.md)

메모리 부족은 “free가 0이 되면 끝”처럼 단순하지 않다. allocator는 비어 있는 메모리 구간을 기록해 두었다가 요청자에게 나누어 주고, 반환되면 다시 사용할 수 있게 관리하는 코드와 자료구조다. 응용 프로그램의 `malloc`, process의 가상 주소 구간, kernel의 물리 page frame, 작은 kernel object는 서로 다른 allocator가 관리한다.

memory pressure는 새 요청을 편하게 줄 만큼 여유 메모리가 부족해 회수 작업이 잦아진 상태다. 이때 kernel은 다시 만들 수 있는 page를 찾아 비우는 reclaim을 수행한다. RAM 내용이 저장장치보다 최신인 dirty data는 먼저 storage에 기록하는 writeback이 필요하다. 파일 원본이 없는 anonymous page는 swap 공간으로 내보낼 수 있다. 그래도 진행할 수 없으면 OOM 정책을 적용한다. 이 장은 이 단어들을 객체와 시간 순서로 풀어낸다.

## 1. allocation은 어느 계층의 무엇을 주는가

allocation(할당)은 요청자에게 사용할 수 있는 자원의 범위를 정해 주고 소유·수명 정보를 기록하는 일이다. free는 더 이상 사용하지 않는 구간을 allocator에 반환하는 동작이고, free space는 아직 누구에게도 할당되지 않아 다시 줄 수 있는 공간이다. “메모리를 할당했다”는 말만으로는 실제 RAM page가 생겼는지 알 수 없다.

| 계층 | 요청 예 | 돌려주는 것 | 즉시 physical RAM이 필요한가 |
|---|---|---|---:|
| language/runtime | 객체 생성 | runtime이 관리하는 object | 구현에 따라 다름 |
| user allocator | `malloc(100)` | process 안의 virtual address 구간 | 항상 그렇지 않음 |
| virtual memory | `mmap`, heap 확장 | virtual address와 mapping 규칙 | demand paging이면 나중일 수 있음 |
| physical page allocator | kernel의 page 요청 | page frame 또는 folio | 예 |
| kernel object allocator | inode·task 같은 작은 object | typed kernel object 공간 | backing page에서 잘라 쓸 수 있음 |
| device/DMA allocator | 장치가 접근할 buffer | 주소·mapping·제약이 있는 memory | 연속성·pinning 제약 가능 |

virtual address를 예약해도 처음 접근할 때 page fault로 physical frame을 붙일 수 있다. 그래서 `malloc` 성공 직후 process의 resident memory가 요청 크기만큼 증가한다고 단정할 수 없다. 반대로 allocator가 free한 작은 block을 자기 arena에 보관하면 `free` 호출 뒤에도 OS가 보는 resident page 수가 즉시 줄지 않을 수 있다.

physical page frame은 RAM을 page 크기 단위로 나눈 관리 대상이다. Linux의 folio는 page cache와 memory management에서 하나 이상의 base page를 묶어 다루는 단위가 될 수 있다. 이 장의 손 계산은 4 KiB base page를 쓰지만 실제 page 크기와 huge page 지원은 architecture와 설정에 따라 다르다.

## 2. free space도 자료구조와 불변조건이 필요하다

allocator는 빈 공간의 위치와 크기를 알아야 한다. 대표 자료구조는 다음과 같다.

- free list: 빈 구간의 시작 주소와 크기를 연결 목록이나 tree에 기록한다.
- bitmap: 각 단위가 사용 중인지 bit로 표시한다.
- buddy allocator: 크기가 2의 거듭제곱인 block을 쪼개고 같은 크기 buddy를 합친다.
- slab 계열 allocator: 같은 종류의 작은 kernel object를 page 묶음에 배치하고 재사용한다.
- per-CPU cache: 작은 allocation의 전역 lock 경쟁을 줄이기 위해 CPU 가까이에 일부 free object를 둔다.

핵심 불변조건은 한 물리 byte를 동시에 서로 다른 owner에게 독점 할당하지 않는 것이다. free list에는 이미 사용 중인 block이 들어가면 안 되고, 같은 block을 두 번 free해서도 안 된다. metadata 손상은 이후 전혀 관계없는 object의 memory corruption으로 번질 수 있다.

alignment는 시작 주소가 특정 배수 경계에 놓여야 한다는 조건이다. CPU instruction, cache line, SIMD, DMA와 device descriptor가 alignment를 요구할 수 있다. 요청한 payload보다 큰 block을 주거나 앞부분을 비워야 하므로 공간 비용이 생긴다.

## 3. external fragmentation과 internal fragmentation

fragmentation은 free space가 요청에 쓰기 불편한 모양으로 나뉘거나, 할당 단위 안에 쓰지 않는 부분이 남는 현상이다. hole은 중간에 비어 있는 연속 메모리 구간을 뜻한다.

external fragmentation은 free 총량은 충분하지만 작은 구간으로 흩어져 큰 **연속** 요청을 만족하지 못하는 상태다.

```text
free hole: 3 KiB + 3 KiB, 서로 떨어져 있음
요청: physically 또는 virtually 연속된 5 KiB 한 구간
총 free: 6 KiB
결과: 가장 큰 hole이 3 KiB라 실패 가능
```

internal fragmentation은 allocator가 준 block 안에서 요청자가 쓰지 않는 공간이다. 4 KiB page 단위로 5 KiB를 담으려면 2 page=8 KiB가 필요하고 최대 3 KiB가 마지막 page 안에 남는다.

연속 16 KiB를 1 KiB block 열여섯 개로 표시하자.

```text
index:  0 1 2 3 4 5 6 7 8 9 A B C D E F
state:  A A . . B B B . . C C . . . D D
```

free 구간은 index 2~3의 2 KiB, 7~8의 2 KiB, B~D의 3 KiB로 총 7 KiB다. 가장 큰 연속 hole은 3 KiB이므로 연속 4 KiB 요청은 실패한다.

B가 사용하던 index 4~6의 3 KiB를 free하면 왼쪽 2~3, 오른쪽 7~8과 맞닿는다. coalescing으로 index 2~8의 7 KiB hole 하나를 만들 수 있다. 이웃 free block을 합치지 않으면 총량은 같아도 큰 요청을 놓친다.

virtual memory는 서로 떨어진 physical frame 네 개를 연속된 virtual 16 KiB처럼 mapping할 수 있다. 그러나 huge page, 일부 DMA, page table 자체의 높은 order allocation처럼 physical 연속성을 요구하는 요청은 여전히 실패할 수 있다.

## 4. first-fit, best-fit, buddy의 선택 비용

free hole이 8, 20, 12 KiB이고 요청이 6 KiB라고 하자.

- first-fit은 탐색 순서에서 처음 만난 8 KiB를 골라 2 KiB를 남긴다.
- best-fit은 요청 이상 중 가장 작은 8 KiB를 골라 같은 결과를 낸다.
- worst-fit은 가장 큰 20 KiB를 골라 14 KiB를 남긴다.

다음 요청과 free 순서가 달라지면 결과도 달라진다. best-fit이 지금 남는 조각을 최소화해도 작은 unusable hole을 많이 만들 수 있다. first-fit은 탐색이 빠를 수 있지만 앞부분 상태에 따라 편향된다.

buddy allocator는 큰 연속 block을 크기가 같은 두 짝으로 계속 반씩 나누고, 반환될 때 원래 한 쌍이었던 두 block이 모두 비어 있으면 다시 합치는 방식이다. 이때 서로 합칠 수 있는 원래 짝을 buddy라고 부른다. order 0은 base page 한 개, order 1은 두 page, order 2는 네 page처럼 묶는다. 빠른 나누기와 합치기가 가능하지만 2의 거듭제곱 반올림으로 internal fragmentation이 생길 수 있다.

kernel object allocator는 192-byte object를 page 안 여러 slot에 넣을 수 있다. object 하나를 free해도 그 page의 다른 object가 살아 있으면 physical page 전체를 buddy allocator로 돌려주지 못한다. “object free”와 “page frame reclaim”을 구분해야 한다.

## 5. page의 종류가 회수 방법을 결정한다

reclaim은 application이 현재 직접 쓰지 않거나 다시 만들 수 있는 physical frame을 찾아 free 상태로 돌리는 과정이다. backing은 RAM에서 page를 없앤 뒤 내용을 다시 가져올 원본이다. file-backed page의 backing은 파일이고, anonymous page는 원본 파일이 없어 swap 같은 별도 저장 위치가 필요하다. page마다 backing이 다르므로 같은 방법으로 버릴 수 없다.

| page 종류 | 현재 의미 | 회수 방법 | 잘못 버리면 |
|---|---|---|---|
| clean file-backed | storage 원본과 RAM 내용이 같음 | mapping을 제거하고 drop, 나중에 다시 읽음 | 성능 저하, 데이터 손실은 보통 없음 |
| dirty file-backed | RAM 변경이 storage보다 새로움 | writeback 성공 뒤 drop | 최신 파일 변경 손실 |
| clean executable/library | 파일에서 다시 읽을 수 있음 | drop 가능 | refault 때 I/O |
| anonymous | heap·stack처럼 원본 파일이 없음 | swap에 기록하거나 유지 | swap 없이 버리면 process data 손실 |
| pinned | DMA·`mlock` 등으로 이동·회수가 제한 | pin 해제 전 일반 회수 어려움 | 장치가 쓰는 동안 이동 시 corruption |
| unevictable | 정책·객체 성격상 LRU 회수 대상 아님 | 원인 해제 필요 | 강제 회수 시 계약 위반 |
| reclaimable kernel cache | 재생성 가능한 kernel metadata | subsystem shrinker 등으로 축소 | 과도 회수 시 CPU·I/O 증가 |

clean은 “최근에 쓰지 않았다”는 뜻이 아니다. backing storage와 내용이 같다는 뜻이다. 방금 읽은 hot clean page도 clean이다. dirty는 최근 접근 여부와 별개로 RAM 내용이 backing보다 새롭다는 뜻이다.

## 6. allocation slow path와 reclaim 시간선

새 page 요청이 빠른 free list에서 즉시 만족되지 않는 상황을 추적한다.

| 단계 | allocating task | memory manager | storage |
|---:|---|---|---|
| 1 | order와 node 조건으로 page 요청 | zone free list와 watermark 확인 | 없음 |
| 2 | fast path 실패 | 허용 범위의 다른 zone/node fallback 검토 | 없음 |
| 3 | 기다리거나 직접 참여 | reclaim candidate scan | 없음 |
| 4 | latency를 직접 부담할 수 있음 | clean file page unmap·drop | 나중 refault 가능 |
| 5 | 계속 부족 | dirty file page writeback 시작 | write command 처리 |
| 6 | blocked될 수 있음 | anonymous page를 swap-out | swap I/O |
| 7 | completion 뒤 재시도 | free frame과 accounting 갱신 | completion |
| 8 | 성공 또는 실패 | compaction·OOM 같은 다음 단계 판단 | 없음 |

background reclaim은 free memory가 너무 낮아지기 전에 kernel thread가 미리 회수해 여유를 복구하려 한다. direct reclaim은 allocation을 요청한 task가 자기 요청 경로에서 scan과 writeback 비용을 부담한다. 그래서 memory pressure는 단순한 memory 사용량이 아니라 application의 긴 allocation latency로 나타날 수 있다.

watermark는 zone별로 어느 수준에서 reclaim과 allocation 행동을 바꿀지 정하는 기준이다. 정확한 값과 fallback은 kernel version, zone, reserve, allocation flag에 따라 달라진다. “free 5%면 무조건 OOM” 같은 보편 임계값은 없다.

높은 order의 연속 page가 필요하면 총 free page가 충분해도 compaction이 필요할 수 있다. movable page를 다른 frame으로 옮겨 큰 연속 hole을 만들지만 pinned·unevictable page가 사이에 있으면 성공하지 못할 수 있다.

## 7. replacement policy를 손으로 계산한다

frame 세 개와 reference string `A B C A D B`를 사용한다. page가 없으면 fault, 있으면 hit다.

### FIFO

먼저 들어온 page를 먼저 내보낸다. hit가 들어온 순서를 새로 만들지 않는다고 가정한다.

| 접근 | frame 상태 | 결과 | 다음 victim |
|---|---|---|---|
| A | A | fault | A |
| B | A B | fault | A |
| C | A B C | fault | A |
| A | A B C | hit | A |
| D | D B C | fault, A 교체 | B |
| B | D B C | hit | B |

fault는 4회다.

### 정확한 LRU 교육 모형

가장 오래 참조되지 않은 page를 내보낸다.

| 접근 | 오래됨 → 최근 순서 | 결과 |
|---|---|---|
| A | A | fault |
| B | A B | fault |
| C | A B C | fault |
| A | B C A | hit, A를 최근으로 이동 |
| D | C A D | fault, B 교체 |
| B | A D B | fault, C 교체 |

fault는 5회다. 이 짧은 string에서는 FIFO가 LRU보다 fault가 적다. 정책 이름 하나가 모든 workload에서 항상 이긴다는 뜻이 아님을 보여 준다.

정확한 LRU는 모든 memory access마다 순서를 갱신해야 해 비용이 크다. 실제 OS는 hardware accessed bit, active/inactive list, sampling, generation과 refault feedback 등으로 최근성을 근사한다.

## 8. Linux Multi-Gen LRU를 교재 LRU와 구분한다

Linux 공식 문서의 Multi-Gen LRU는 page reclaim을 aging과 eviction의 두 절차로 설명한다. 접근된 page를 더 젊은 generation으로 분류하고, 오래된 generation에서 eviction 후보를 고른다. page table walk와 reverse mapping 정보, file과 anonymous page의 refault feedback을 사용한다.

이것은 위 표의 완전한 doubly linked LRU 순서를 그대로 구현한다는 뜻이 아니다. generation은 많은 page를 age 구간으로 묶는 근사다. scan CPU 비용, locality, file/anonymous 균형과 thrashing 방지를 함께 다룬다.

`min_ttl_ms` 같은 옵션은 일정 시간의 working set을 eviction에서 보호하는 방향을 제공하지만, 보호할 memory를 유지할 수 없으면 OOM을 더 일찍 유도할 수 있다. 문서의 권장값을 모든 server workload에 복사하지 말고 kernel 설정과 workload로 검증해야 한다.

## 9. swap은 reclaim의 한 경로다

anonymous page에는 다시 읽을 원본 파일이 없다. swap이 설정되어 있으면 kernel은 내용을 swap slot에 기록하고 physical frame을 다른 용도로 사용할 수 있다. 이후 process가 그 virtual address에 접근하면 page fault가 나고 swap-in으로 내용을 RAM에 되돌린다.

```text
anonymous page in RAM
→ swap slot 할당
→ page 내용 write
→ page table에 non-present/swap 정보
→ frame 재사용
→ 나중 접근 page fault
→ swap read
→ 새 frame에 복원
```

swap을 “느린 RAM”이라고만 부르면 중요한 차이를 놓친다. CPU는 swap slot의 byte를 register load로 직접 읽지 못한다. page fault와 storage I/O를 거쳐 RAM frame으로 복원해야 한다.

swap이 없어도 clean file cache는 drop할 수 있고 dirty file page는 writeback할 수 있다. 따라서 reclaim과 swap은 같은 말이 아니다. swap 사용량이 2 GiB라는 누적 상태만으로 지금 swap I/O가 병목이라고 단정할 수도 없다. 한 번 나간 cold page가 오래 남아 있을 수 있다.

compressed swap 계층은 page를 RAM 안의 압축 pool에 두어 storage I/O를 피할 수 있지만 CPU 압축 비용과 제한된 pool 용량이 생긴다. 실제 기능 이름과 정책은 시스템마다 확인한다.

## 10. working set과 thrashing

working set은 일정 시간 구간에 task가 활발히 다시 사용하는 page 집합이다. 여러 task의 active working set 합이 available RAM보다 크고, 방금 내보낸 page를 곧 다시 요구하면 eviction과 refault가 반복된다.

예를 들어 frame 세 개로 순환 접근 `A B C D A B C D...`를 수행하면 working set 네 page를 담지 못한다. 단순 LRU에서 거의 모든 접근이 fault가 될 수 있다. CPU는 user instruction보다 page fault 처리와 storage wait에 시간을 쓰고 throughput이 떨어진다.

동시에 실행하는 job 수를 늘리면 CPU utilization이 늘 것 같지만 각 working set이 서로를 밀어내 thrashing을 악화할 수 있다. admission control로 active job 수를 줄이는 편이 완료량을 높일 수도 있다.

refault rate, major fault, reclaim scan, writeback, I/O latency와 CPU stall을 함께 봐야 한다. free memory가 낮다는 사실 자체는 page cache를 적극 활용하는 정상 상태일 수 있다.

## 11. cgroup memory pressure는 host OOM과 다르다

memory cgroup은 process 집합의 memory 사용량과 reclaim·limit 범위를 만든다. host에 free RAM이 남아도 특정 cgroup이 `memory.max`에 닿으면 그 cgroup 안에서 강한 reclaim과 OOM이 발생할 수 있다.

cgroup v2에서 개념적으로 다음을 구분한다.

- `memory.current`: 현재 charge된 사용량
- `memory.high`: 넘으면 task를 throttle하고 강한 reclaim pressure를 주는 경계; 일반적으로 직접적인 hard OOM limit와 다름
- `memory.max`: 줄일 수 없는 상태에서 넘지 못하도록 하는 hard limit
- `memory.events`: high, max, oom, oom_kill 같은 사건 counter
- `memory.oom.group`: workload를 indivisible group처럼 함께 종료할지에 관한 정책

정확한 accounting에는 anonymous, file cache, kernel memory와 shared page charge 규칙이 얽힌다. container 안의 `free` 출력만 보고 cgroup limit을 놓치면 진단을 잘못할 수 있다.

## 12. OOM은 마지막 선택이며 victim은 보장된 답이 아니다

OOM(out of memory)은 필요한 allocation을 reclaim·compaction·허용된 fallback으로 만족하지 못해 시스템이 진행을 확보할 정책을 선택하는 상황이다. OOM killer는 process를 종료해 memory를 회수하려 할 수 있다.

단순 교육 모형에서는 “많이 쓰는 process를 죽인다”고 말하지만 실제 victim 선택은 memory 사용, 조정값, 보호 대상, shared state, OOM scope 등 여러 조건을 반영한다. kernel version과 cgroup 설정에 따라 다르므로 특정 process가 항상 선택된다고 보장하면 안 된다.

종료 signal을 보낸 순간 모든 page가 즉시 free되는 것도 아니다. task가 종료 경로를 실행하고 참조와 pinned resource가 풀려야 한다. victim이 uninterruptible I/O에 묶이면 회수가 늦을 수 있다.

OOM scope를 구분한다.

- global OOM: system이나 허용 node 범위 전체에서 memory를 찾지 못함
- cgroup OOM: 특정 memory cgroup limit 안에서 reclaim하지 못함
- NUMA/constraint failure: 다른 node에 free가 있어도 policy·cpuset·allocation flag 때문에 사용할 수 없음
- high-order failure: 총량은 있어도 필요한 연속 block을 만들지 못함

OOM log는 victim 이름 하나만 보지 말고 allocation order, constraint, memcg, node, reclaim 상태와 당시 workload를 함께 읽는다.

## 13. NUMA와 locality

NUMA에서는 CPU와 가까운 memory node가 있고 먼 node 접근은 latency와 bandwidth가 다를 수 있다. allocation policy가 local node를 선호해도 그 node만 압박을 받을 수 있다. 다른 node에 free가 있다는 사실이 즉시 같은 성능으로 사용할 수 있다는 뜻은 아니다.

task migration과 page placement가 어긋나면 CPU는 remote page를 계속 접근한다. page migration으로 locality를 개선할 수 있지만 copying 비용, page table update와 동시 접근 조정이 필요하다. pinned page는 이동이 어렵다.

memory cgroup과 cpuset이 결합되면 allowed memory node가 제한될 수 있다. host 전체 `MemAvailable` 하나로 container나 NUMA-local allocation 실패를 설명할 수 없는 이유다.

## 14. 안전하게 관측할 때의 질문

다음은 읽기 중심의 관측 예다. 값의 존재와 권한은 kernel·container 설정에 따라 다르다.

```bash
grep -E '^(MemTotal|MemFree|MemAvailable|Cached|SwapTotal|SwapFree):' /proc/meminfo
cat /proc/pressure/memory
cat /sys/fs/cgroup/memory.current
cat /sys/fs/cgroup/memory.events
```

`MemFree`는 완전히 비어 있는 memory이고 `MemAvailable`은 reclaim 가능성을 고려한 추정치다. 둘을 같은 값으로 읽지 않는다. PSI memory pressure는 task가 memory 때문에 stall된 시간을 관측하는 데 도움을 주지만 원인이 anonymous swap인지 file cache refault인지 단독으로 확정하지 않는다.

`vmstat`의 scan, steal, page-in/out counter는 관측 구간의 변화량으로 봐야 한다. boot 이후 누적값 한 번만 보고 현재 폭풍을 단정하지 않는다. production에서 debugfs 조작이나 proactive reclaim을 실행하는 것은 읽기와 다르므로 별도 실험 환경과 권한 검토가 필요하다.

## 15. 자주 틀리는 결론

- free RAM이 적다고 즉시 부족한 것은 아니다. reclaimable page cache가 클 수 있다.
- free RAM이 많아도 high-order contiguous allocation은 실패할 수 있다.
- `free()` 호출이 곧 physical page 반환은 아니다.
- clean page는 cold page와 같은 말이 아니다.
- swap 사용량이 0이 아니라고 현재 thrashing인 것은 아니다.
- swap이 없다고 reclaim이 없는 것은 아니다.
- OOM victim 선택은 가장 큰 RSS 하나로 완전히 설명되지 않는다.
- LRU라는 이름이 모든 access의 정확한 시간순 list를 뜻하지 않는다.
- cgroup OOM과 host global OOM은 범위가 다르다.

## 16. 확인 문제와 자세한 해설

### 문제 1. `malloc`과 resident memory

process가 `malloc(1 GiB)`에 성공했다. 즉시 physical RAM 1 GiB를 독점했다고 결론 내릴 수 있는가?

**해설:** 아니다. user allocator가 이미 가진 arena에서 virtual 구간을 나눴거나, kernel이 virtual mapping만 준비하고 첫 접근 때 demand paging할 수 있다. 실제 resident page는 touch 패턴, zero page, overcommit, allocator 정책에 따라 달라진다.

### 문제 2. fragmentation 계산

2 KiB, 2 KiB, 3 KiB의 서로 떨어진 free hole이 있다. 총 7 KiB인데 연속 4 KiB 요청이 실패하는 이유와 해결 가능성을 설명하라.

**해설:** 가장 큰 hole이 3 KiB라 external fragmentation 때문에 실패한다. 이웃 allocation이 free되어 coalescing되거나 movable page를 compaction해 연속 공간을 만들면 성공할 수 있다. pinned page가 사이에 있으면 compaction이 실패할 수 있다.

### 문제 3. FIFO와 LRU

frame 3개, reference `A B C A D B`에서 이 장의 규칙으로 fault 수를 계산하라.

**해설:** FIFO는 A, B, C, D에서 fault가 나고 마지막 B는 남아 있어 총 4회다. LRU는 A, B, C 뒤 A hit로 B가 least recent가 되고 D가 B를 쫓아낸다. 마지막 B가 다시 fault여서 총 5회다. 이 string 하나로 FIFO가 보편적으로 낫다는 결론은 낼 수 없다.

### 문제 4. dirty page 회수

dirty file page를 clean page처럼 즉시 drop하면 왜 안 되는가?

**해설:** RAM 내용이 backing storage보다 새로워 drop하면 최신 변경을 잃는다. writeback을 제출하고 성공을 확인한 뒤 reclaim해야 한다. writeback 중 오류와 page 재수정이 있을 수 있어 상태 전이와 error 전달도 관리해야 한다.

### 문제 5. swap과 reclaim

swap이 꺼져 있으면 kernel은 memory를 전혀 reclaim할 수 없는가?

**해설:** 아니다. clean file-backed page를 drop하고, dirty file page를 writeback하며, reclaimable kernel cache를 줄일 수 있다. 다만 anonymous page를 보존하며 frame을 비우는 선택지가 줄어 pressure와 OOM 조건이 달라진다.

### 문제 6. cgroup OOM

host에는 20 GiB available이 있지만 container의 `memory.max`가 2 GiB이고 `memory.current`가 그 근처다. container 안 allocation이 OOM일 수 있는가?

**해설:** 가능하다. reclaim과 OOM의 scope가 cgroup limit일 수 있기 때문이다. host 전체 여유와 해당 cgroup이 사용할 수 있는 예산은 다르다. `memory.events`와 cgroup 설정, charge 구성 요소를 확인한다.

### 문제 7. thrashing

네 page를 순환 재사용하는 task에 frame 세 개만 주고 거의 모든 접근에서 fault가 난다. CPU를 하나 더 주면 반드시 빨라지는가?

**해설:** 아니다. 병목은 CPU 계산이 아니라 working set을 담지 못해 생기는 eviction·refault와 I/O일 수 있다. 동시 실행을 늘리면 memory pressure가 더 커질 수도 있다. frame, admission, access locality를 바꾸고 fault·PSI·I/O를 함께 측정해야 한다.

### 문제 8. high-order failure

총 free base page는 1,000개인데 연속 2 MiB huge page allocation이 실패했다. 모순인가?

**해설:** 아니다. free page가 흩어져 있으면 필요한 연속 block이 없다. compaction이 movable page를 옮길 수 있지만 pinned·unevictable page와 node constraint 때문에 실패할 수 있다. 총량과 연속성은 다른 조건이다.

## 근거와 더 읽을 자료

- [OSTEP: Free-Space Management](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-freespace.pdf)
- [OSTEP: Swapping과 VM 정책](https://pages.cs.wisc.edu/~remzi/OSTEP/)
- [Linux kernel 문서: Memory Management Concepts](https://docs.kernel.org/admin-guide/mm/concepts.html)
- [Linux kernel 문서: Page Allocation](https://docs.kernel.org/mm/page_allocation.html)
- [Linux kernel 문서: Multi-Gen LRU](https://docs.kernel.org/admin-guide/mm/multigen_lru.html)
- [Linux kernel 문서: cgroup v2 Memory Controller](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory)
- [Linux kernel 문서: Out Of Memory Handling](https://docs.kernel.org/mm/oom.html)

---

[이전 장: 페이징과 가상 메모리](06-paging-virtual-memory.md) · [다음 장: I/O·파일·파일시스템](08-io-files-filesystems.md)
