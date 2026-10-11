# 04. Memory page·reclaim·PSI

[이 책 목차](README.md)

[← 이전: CPU scheduling](03-cpu-scheduling-and-pressure.md) · [다음: cgroup v2 hierarchy →](05-cgroup-v2-hierarchy-and-delegation.md)

프로그램이 메모리를 달라고 할 때 커널은 RAM 칩의 연속 구간을 그대로 넘겨주지 않는다. 먼저 그 프로세스가 사용할 수 있는 주소 범위를 만들고, 실제로 읽거나 쓰는 순간에 물리 메모리의 작은 블록을 연결할 수 있다. 물리 메모리가 부족해지면 다시 만들 수 있는 복사본을 버리거나, 보존해야 하는 내용을 저장 장치로 내보내 재사용할 블록을 확보한다. 이 과정이 오래 걸리면 프로그램은 메모리 용량을 아직 넘지 않았더라도 멈춰 기다린다.

이 장은 주소 하나가 실제 RAM에 도달하는 과정, page 종류별 회수 비용, 두 프로세스가 동시에 메모리를 요구할 때의 시간표, 기다린 시간을 나타내는 PSI 수치를 연결한다.

## 1. 주소 공간과 page는 무엇인가

**process(프로세스)**는 실행 중인 프로그램 한 인스턴스다. 운영체제는 프로세스마다 독립적인 주소의 세계를 제공한다. 이 숫자 범위를 **virtual address space(가상 주소 공간)**라고 한다. 같은 숫자 0x400000이라도 서로 다른 두 프로세스에서는 다른 물리 데이터에 연결될 수 있다.

프로그램의 load와 store 명령이 사용하는 숫자가 **virtual address(가상 주소)**다. CPU의 **MMU(Memory Management Unit)**는 이 주소를 메모리 장치가 사용할 **physical address(물리 주소)**로 번역하고 접근 권한을 검사한다. 물리 주소는 RAM에서 실제 저장 블록을 선택하는 주소다.

주소 공간 전체를 바이트마다 따로 관리하면 표가 너무 커진다. Linux와 하드웨어는 연속된 고정 크기 묶음으로 나눈다. 가상 주소 쪽 묶음이 **page(페이지)**이고, 물리 메모리 쪽 같은 크기의 저장 블록이 **page frame(페이지 프레임)**이다. 일반적인 한 구성에서는 기본 page가 4096바이트지만 크기는 아키텍처와 구성에 따라 다르다.

**page table(페이지 테이블)**은 가상 page와 물리 frame의 연결, present 상태, 읽기·쓰기·실행 권한을 기록하는 커널 관리 자료 구조다. 각 프로세스 주소 공간에 대응하는 표가 있고 메모리에 존재한다. 프로세스가 생성되거나 mapping이 바뀌면 커널이 갱신하며, 프로세스가 끝나고 참조가 사라지면 관련 구조도 회수된다.

최근 번역은 CPU 안의 작은 **TLB(Translation Lookaside Buffer)**에 저장된다. TLB hit이면 저장된 번역을 사용하고, TLB miss이면 page table을 단계적으로 읽는 page-table walk가 필요하다. TLB miss는 번역 캐시에 항목이 없다는 뜻이며, 물리 page가 없다는 뜻은 아니다.

~~~mermaid
flowchart TD
    A[task가 virtual address 접근] --> T{TLB hit?}
    T -->|예| P{권한 허용?}
    T -->|아니오| W[page table walk]
    W --> P
    P -->|예·present| R[physical frame 접근]
    P -->|없음 또는 특별 처리| F[page fault handler]
    F -->|합법·자원 확보| M[frame 할당·memcg charge·PTE 연결]
    M --> R
    F -->|불법 또는 실패| E[signal·allocation 실패·OOM 가능]
~~~

그림에서 task는 실행 중인 스레드다. page fault handler는 커널 코드이며, mapping을 만들 수 있는 합법적 접근이면 frame과 PTE를 준비한 뒤 원래 명령을 다시 실행한다. 접근할 수 없는 주소라면 signal을 보내고, 자원을 확보하지 못하면 allocation 실패나 OOM 경로로 갈 수 있다.

## 2. VMA와 mapping의 수명

커널은 주소 공간 안의 연속 구간마다 시작·끝 주소, 접근 권한, 연결된 파일 같은 정보를 관리한다. 이런 구간을 **VMA(Virtual Memory Area, 가상 메모리 영역)**라고 한다. 실행 파일의 코드, heap, stack, 공유 라이브러리, mmap으로 연결한 파일은 서로 다른 VMA가 될 수 있다.

**mapping(매핑)**은 가상 주소 범위에 어떤 데이터 원본과 권한을 연결할지 정한 관계다. VMA를 만들었다고 모든 page frame이 즉시 생기는 것은 아니다. 예를 들어 10 GiB 범위를 예약해도 실제로 100 MiB만 touch하면 나머지에는 물리 page가 없을 수 있다.

**touch(최초 실제 접근)**는 프로그램이 주소를 load하거나 store해 하드웨어와 커널이 그 page를 실제로 준비하게 만드는 접근을 뜻한다. malloc은 사용자 공간 할당기가 쓸 수 있는 가상 범위를 반환할 수 있지만, page의 물리 할당과 memory cgroup charge는 처음 쓰는 fault 시점에 일어날 수 있다. 그래서 malloc 성공과 모든 메모리 사용 성공은 같은 보장이 아니다.

VMA는 unmap, 실행 파일 교체, 프로세스 종료 때 사라진다. 물리 page의 수명은 별도다. 공유 파일 page는 한 프로세스가 unmap해도 다른 mapping이나 page cache가 참조하면 남을 수 있다. 한 주소의 수명을 곧바로 한 물리 page의 수명으로 보면 안 된다.

## 3. page fault는 오류라는 뜻이 아니다

CPU가 현재 page-table 상태와 권한만으로 접근을 끝낼 수 없을 때 커널 handler로 들어가는 사건이 **page fault(페이지 폴트)**다. fault는 “느린 경로로 처리가 필요하다”는 뜻이며 항상 프로그램 오류는 아니다.

**minor fault(경미한 폴트)**는 필요한 데이터를 저장 장치에서 새로 읽는 작업 없이 해결할 수 있는 fault다. 예를 들어 zero-filled anonymous page를 처음 쓰며 새 frame을 연결하거나, 이미 page cache에 있는 file page를 PTE에 연결하거나, copy-on-write 복사를 만드는 경우가 포함될 수 있다.

**major fault(중대한 폴트)**는 fault를 해결하기 위해 저장 장치 I/O가 필요했던 경우다. mmap한 파일 page가 page cache에 없어 저장 장치에서 읽거나 swap에 있던 anonymous page를 읽는 경우가 예다. major라는 이름은 오류의 심각도가 아니라 I/O를 동반한 비용 분류다.

정확한 trace를 보자. 4 KiB page에서 프로세스가 새 heap 주소 0x70001234에 처음 쓴다고 하자.

1. page 시작 주소는 0x70001000이고 내부 offset은 0x234다.
2. TLB에 번역이 없어 page table을 확인한다.
3. PTE는 아직 present가 아니지만 VMA는 읽기·쓰기를 허용한다.
4. CPU가 커널 fault handler로 들어간다.
5. 커널은 물리 frame을 확보하고, 보안상 초기 내용을 노출하지 않도록 0으로 준비한다.
6. memory cgroup을 사용한다면 해당 frame 사용량을 charge한다.
7. PTE에 frame과 쓰기 권한을 연결하고 TLB가 새 번역을 사용할 수 있게 한다.
8. 원래 store를 재시도해 offset 0x234 위치에 값을 쓴다.

저장 장치에서 읽지 않았으므로 이 조건은 minor fault가 될 수 있다. 반면 주소가 VMA 밖이면 frame을 만들지 않고 SIGSEGV 같은 signal 경로로 갈 수 있다.

## 4. anonymous, file-backed, clean, dirty의 실제 의미

page를 회수하려면 “현재 RAM 내용을 버려도 다시 만들 수 있는가?”를 먼저 묻는다.

**anonymous page(익명 page)**는 일반 heap·stack처럼 파일 시스템의 원본 파일에 직접 연결되지 않은 사용자 메모리다. 프로세스가 값을 쓰면 그 최신 내용은 RAM에만 있다. 그대로 버리면 프로그램 상태가 사라지므로 swap에 기록하거나 계속 보존해야 한다.

**file-backed page(파일 기반 page)**는 실행 파일, mmap 파일, buffered I/O의 page cache처럼 파일의 특정 offset에 연결된 page다. **page cache**는 파일 데이터를 RAM에 보관해 같은 데이터를 다시 읽을 때 저장 장치 접근을 줄이는 커널 cache다.

**clean page**는 RAM 내용이 backing storage의 내용과 같아 RAM 복사본을 버려도 원본에서 다시 읽을 수 있는 page다. **dirty page**는 RAM 내용이 backing storage보다 새롭다는 표시다. dirty file page를 버리기 전에는 최신 내용을 파일 시스템과 장치에 반영해야 한다.

**writeback(쓰기 되돌림)**은 dirty page 내용을 backing storage로 보내 clean 상태로 만드는 과정이다. 요청을 제출한 순간과 저장이 완료된 순간은 다르다. 장치가 느리거나 queue가 밀리면 page는 writeback 중으로 남고 회수가 지연될 수 있다.

| page 종류 | clean/dirty 의미 | reclaim 시 필요한 일 | 다시 접근할 때 |
| --- | --- | --- | --- |
| clean file | storage와 같음 | RAM 복사본 해제 가능 | file read fault 가능 |
| dirty file | RAM이 더 최신 | writeback 완료 뒤 해제 가능 | cache에 없으면 file read |
| anonymous | 직접 file 원본 없음 | swap-out 또는 유지 | swap-in fault 가능 |
| pinned/unevictable | 이동·회수 제한 | 사용 주체가 참조를 놓아야 함 | 원래 목적 동안 계속 유지 |

**pinned page**는 장치 DMA나 특정 커널 사용처럼 물리 위치와 수명을 안정적으로 유지해야 해 보통 즉시 회수할 수 없는 page다. unevictable은 일반적인 회수 후보에서 제외된 상태를 뜻한다. free가 적어도 모든 사용량이 같은 비용으로 회수되는 것은 아니다.

## 5. RSS, PSS, VSZ와 page cache를 섞지 않는다

**VSZ 또는 VIRT**는 프로세스가 mapping한 전체 가상 주소 범위의 크기다. 물리 RAM에 실제 존재하는 양이 아니다. 10 GiB를 mmap하고 100 MiB만 touch하면 VSZ는 10 GiB이고 resident한 양은 훨씬 작을 수 있다.

**RSS(Resident Set Size)**는 현재 RAM에 resident하며 그 프로세스 mapping에 연결된 page 양을 나타내는 관점이다. 공유 라이브러리 page 하나가 여러 프로세스 RSS에 각각 포함될 수 있어 RSS 합계가 물리 사용량과 같지 않을 수 있다.

**PSS(Proportional Set Size)**는 공유 page 비용을 공유하는 프로세스 수에 비례해 나눈다. 12 MiB 공유 page를 세 프로세스만 공유하면 각 PSS에 약 4 MiB씩 귀속하는 방식이다. 실제 accounting의 세부 시점과 반올림은 도구에 따라 달라질 수 있다.

copy-on-write는 처음에는 같은 물리 page를 공유하다 한 프로세스가 쓸 때 별도 page를 복사한다. 공유 상태와 쓰기 뒤의 RSS·PSS가 달라진다. host 사용량을 볼 때 사용자 RSS 외에도 page cache와 커널 메모리, slab, 장치용 page가 있음을 기억한다.

## 6. reclaim을 시작하는 주체와 watermarks

**reclaim(메모리 회수)**은 재사용 가능한 물리 frame을 확보하기 위해 page를 해제하거나 backing storage로 내보내는 커널 작업이다. 물리 메모리는 유한하고, page는 프로세스 데이터·파일 cache·커널 자료 구조 등 여러 용도로 계속 바뀐다.

커널은 zone마다 여유 page 수에 기준선을 둔다. 이 기준을 **watermark(수위 기준)**라고 부른다. 여유량이 낮아지면 kswapd라는 커널 스레드를 깨워 미리 회수할 수 있다. **background reclaim(백그라운드 회수)**은 allocation을 요청한 업무 task와 별도인 커널 스레드가 여유를 회복하려는 작업이다.

여유가 더 부족하거나 할당이 즉시 필요하면 allocation을 요청한 task가 직접 회수에 참여할 수 있다. 이것이 **direct reclaim(직접 회수)**다. 업무 task의 실행 시간이 scan과 writeback 대기로 바뀌므로 사용자 요청 latency에 직접 나타난다.

회수가 실패한다고 곧바로 host RAM이 정확히 0바이트라는 뜻은 아니다. 요청 조건을 만족하는 zone이나 NUMA node에 page가 없거나, cgroup limit 안에서 회수할 후보가 없거나, page가 pinned·dirty·활발히 재사용되는 상황일 수 있다.

## 7. 최근 사용 판단, LRU와 refault

커널은 모든 page의 미래 사용을 알 수 없다. 과거 접근 정보를 이용해 다시 쓸 가능성이 낮은 후보를 찾는다. 오래 쓰지 않은 것을 먼저 본다는 생각을 **LRU(Least Recently Used, 가장 오래 사용되지 않은 것 우선)**라고 부른다.

Linux 구현은 커널 버전과 설정에 따라 전통적인 active/inactive 목록이나 multi-generational LRU 같은 기법을 사용할 수 있다. 이를 완벽한 “마지막 접근 시각 정렬 목록”으로 이해하면 안 된다. page 접근 bit와 scan 결과를 바탕으로 근사적으로 hot과 cold를 구분한다.

**working set(작업 집합)**은 일정 시간 동안 실제로 반복 사용하는 page들의 집합이다. 작업 집합이 사용 가능한 메모리보다 크면 방금 버린 page를 곧 다시 읽는 일이 반복될 수 있다.

**refault(재폴트)**는 회수되어 resident하지 않게 된 page를 다시 접근해 fault하는 사건이다. clean file page A를 버린 뒤 짧은 시간 안에 다시 읽으면 A는 실제 작업 집합에 가까웠다는 신호다. 커널은 eviction과 refault 사이에 얼마나 많은 다른 page가 돌았는지 같은 정보를 이용해 어떤 page 집합을 보호할지 판단할 수 있다.

단순히 “cache를 많이 버렸으니 free가 늘어 성공”이라고 평가하면 안 된다. refault와 저장 장치 읽기가 급증하면 회수로 확보한 공간보다 재읽기 비용이 더 클 수 있다. **thrashing(스래싱)**은 유용한 계산보다 page를 내보내고 다시 가져오는 데 대부분 시간을 쓰는 상태다.

## 8. swap의 역할과 오해

**swap**은 anonymous page 내용을 RAM 밖의 backing storage에 보관할 수 있게 하는 공간과 기작이다. **swap-out**은 anonymous 내용을 swap에 기록하고 RAM frame을 회수하는 과정이며, **swap-in**은 나중에 접근할 때 내용을 다시 읽는 과정이다.

swap이 있다고 RAM처럼 빠른 용량이 그대로 늘어나는 것은 아니다. 저장 장치는 RAM보다 지연이 크고, 활발히 쓰는 page가 반복 이동하면 성능이 크게 떨어진다. 반대로 거의 쓰지 않는 anonymous page를 swap으로 보내 자주 쓰는 file cache와 active page에 RAM을 제공하면 전체 성능이 나아질 수 있다.

swap이 없으면 anonymous page를 보존한 채 회수할 선택지가 줄어든다. 그러나 swap 유무 하나만으로 OOM 시점을 결정할 수 없다. reclaim 가능한 clean file page, cgroup limit, pinned 메모리, allocation 조건을 함께 본다.

## 9. 1 GiB cgroup과 두 프로세스 압박 전체 trace

memory.max가 1024 MiB인 cgroup에 프로세스 A와 B가 있다고 하자. 시작 사용량은 다음과 같다.

| 소유·종류 | 양 |
|---|---:|
| A anonymous | 420 MiB |
| B anonymous | 180 MiB |
| shared clean file cache | 250 MiB |
| dirty file page | 100 MiB |
| 기타 charge | 50 MiB |
| 합계 | 1000 MiB |

A가 새 anonymous 주소 80 MiB를 쓰고, 거의 동시에 B가 file mapping 40 MiB를 읽는다. 총 120 MiB 새 resident 수요가 생겨 단순 합은 1120 MiB다. hard limit 안으로 들어오려면 적어도 약 96 MiB를 회수해야 하지만, 동시 charge와 메타데이터 때문에 실제 목표는 더 클 수 있다.

| 시각 | A | B | 커널의 page 상태 | 관측 |
|---:|---|---|---|---|
| t0 | 계산 중 | 계산 중 | 총 1000 MiB | pressure 낮음 |
| t1 | 80 MiB 첫 store fault | 40 MiB file fault | charge 요청 120 MiB | minor·major fault 가능 |
| t2 | direct reclaim 참여 | storage read 대기 | clean file 100 MiB 선택 | PSI some 증가 |
| t3 | 일부 진행 | I/O 대기 | clean 100 MiB drop, dirty 20 MiB writeback 시작 | memory.current는 limit 근처 |
| t4 | 남은 page fault 진행 | file page 40 MiB 도착 | dirty writeback 완료 후 공간 사용 | I/O와 PSI 증가 |
| t5 | 계산 복귀 | 계산 복귀 | 새 anonymous 80, file 40 resident | refault 가능 |

clean file cache에서 120 MiB 이상을 바로 버릴 수 있다면 writeback 없이 성공할 수 있다. 그러나 그 cache의 일부를 B가 즉시 다시 읽으면 major fault와 refault가 발생한다. clean 후보가 20 MiB뿐이고 swap이 없으며 dirty writeback이 느리면 A와 B가 direct reclaim과 I/O에 오래 묶이고 cgroup OOM까지 갈 수 있다.

중요한 점은 두 task의 기다림이 같은 이유가 아닐 수 있다는 것이다. A는 charge할 frame을 얻기 위해 reclaim하고, B는 file 데이터를 읽기 위해 storage를 기다린다. PSI memory는 생산적인 실행이 메모리 부족 때문에 방해받은 시간을 모으지만, 원인을 세부 page 종류별로 자동 설명해 주지는 않는다. memory.stat, memory.events, fault와 I/O를 함께 본다.

## 10. cgroup memory limit과 OOM

**memory cgroup(memcg)**은 cgroup 계층별로 메모리 사용을 귀속하고 보호·제한하는 커널 기능이다. page를 새로 charge할 때 현재 cgroup과 조상 사용량을 확인한다. task가 다른 cgroup으로 이동해도 이미 존재하는 모든 page charge가 자동으로 즉시 이동한다고 가정하면 안 된다.

memory.max는 cgroup의 hard limit다. 사용량이 한계에 도달하고 범위 안에서 충분히 줄일 수 없으면 그 cgroup의 OOM killer가 동작할 수 있다. host 전체에 free RAM이 있어도 특정 cgroup은 조상·자기 limit 때문에 OOM을 겪을 수 있다.

**OOM(Out Of Memory)**은 필요한 memory allocation을 계속할 방법을 찾지 못한 상태다. 커널은 시스템이나 cgroup이 진행할 수 있게 victim task를 선택해 종료할 수 있다. OOM은 모든 page가 동일하게 부족한 단순 숫자가 아니라 reclaim 진전, 제한 범위, allocation 종류의 결과다.

memory.high는 초과 시 task를 throttle하고 reclaim 압력을 주는 경계이고, memory.max는 최종 hard limit이다. high가 일시 초과될 수 있고 max도 특정 상황에서 순간적으로 보이는 값이 넘을 수 있으므로 한 snapshot만으로 사건 순서를 단정하지 않는다.

## 11. PSI가 세는 것은 사용량이 아니라 멈춘 시간이다

**PSI(Pressure Stall Information, 자원 압박 대기 정보)**는 CPU·메모리·I/O 자원 부족 때문에 task가 생산적인 일을 하지 못한 wall-clock 시간을 집계하는 Linux 인터페이스다. memory PSI는 “메모리 사용률”이나 “swap 비율”이 아니다.

memory.pressure의 **some**은 관측 범위에서 적어도 일부 non-idle task가 메모리 압박 때문에 stall한 시간 비율이다. **full**은 모든 non-idle task가 동시에 stall한 시간 비율이다. 다른 계산 task가 계속 일하면 some은 늘어도 그 구간 전체가 full은 아니다.

~~~text
some avg10=20.00 avg60=8.00 avg300=3.00 total=5400000
full avg10=5.00 avg60=2.00 avg300=1.00 total=900000
~~~

avg10·avg60·avg300은 최근 10·60·300초 경향을 백분율로 나타내는 이동 평균이다. total은 누적 stall 시간을 microsecond 단위로 보여 준다. avg10=20을 “바로 앞 정확히 10초 중 2초”로 역산하지 않는다. 정확한 사용자 지정 구간은 시작과 끝 total 차이를 사용한다.

시작 some total이 5,400,000 µs이고 10초 뒤 6,900,000 µs라면 증가량은 1,500,000 µs = 1.5초다. 구간의 some 비율은 1.5 / 10 × 100 = 15%다.

두 allocation task가 800 ms 동안 writeback을 기다리고 계산 task C는 계속 실행했다고 하자. wall-clock에서 일부 task가 막혔으므로 some은 최대 그 구간만큼 늘 수 있다. 모든 non-idle task가 막힌 것은 아니므로 800 ms 전부가 full로 계산되지는 않는다. 이후 C도 같은 압박 경로에 300 ms 막혀 세 task 모두 멈추면 그 겹치는 300 ms가 full 증가에 기여할 수 있다. task별 대기 시간을 단순 합산해 800 ms × 2로 계산하는 것이 아니라 wall-clock 압박 구간을 집계한다.

PSI trigger는 “1초 창 안에 some stall이 누적 150 ms를 넘으면 알림”처럼 threshold와 window를 지정할 수 있다. 알림은 원인 진단 완료가 아니라 조사가 필요한 압박 구간을 알려 주는 신호다.

## 12. 관측 파일을 같은 범위와 시간으로 읽기

~~~bash
cat /proc/meminfo
cat /proc/self/status
cat /proc/pressure/memory
cat /sys/fs/cgroup/memory.current
cat /sys/fs/cgroup/memory.stat
cat /sys/fs/cgroup/memory.events
cat /sys/fs/cgroup/memory.pressure
~~~

위 명령은 읽기 전용 관측 예다. /proc/meminfo는 host 전체, /proc/self/status는 명령을 실행한 프로세스, /proc/pressure/memory는 시스템 PSI, cgroup 파일은 해당 계층 범위를 나타낸다. 서로 다른 범위의 숫자를 직접 나누지 않는다.

memory.current는 byte 사용량, memory.stat은 anonymous·file·slab 등의 구성, memory.events는 high·max·oom 같은 사건의 누적 count, memory.pressure는 stall 시간이다. 같은 timestamp에 시작값을 기록하고 동일 구간 뒤 delta를 비교한다.

가능한 네 조합을 구분한다.

| memory.current | PSI | 가능한 해석 |
|---|---|---|
| 낮음 | 낮음 | 여유 있고 stall 적음 |
| 높음 | 낮음 | 한계 근처지만 안정적 작업 집합 |
| 비슷하게 유지 | 높음 | allocation과 reclaim 반복 |
| 감소 | 잠시 높음 | 회수·writeback 중 사용량 감소 |

사용량 그래프만으로 reclaim 비용을 보거나 PSI만으로 어떤 page가 문제인지 알 수 없다.

## 13. 최신 메모리 계층 연구와 연결

CXL 같은 연결을 통해 DRAM보다 느리거나 대역폭이 다른 메모리를 추가하면 page를 어느 계층에 둘지 새로운 문제가 생긴다. ISA 관점에서 같은 load 결과가 나오더라도 page 위치와 다른 tenant의 연결망 경쟁이 시간에 영향을 준다.

Memstrata는 CXL 메모리를 포함한 VM 메모리 계층과 공동 사용자의 contention을 다룬 OSDI 2024 연구다. 이 결과를 “Ubuntu가 모든 page를 자동으로 최적으로 배치한다”는 보장으로 읽으면 안 된다. 연구의 workload, hypervisor, 하드웨어 topology, tier 용량과 경쟁 조건에서 제안 메커니즘이 어떤 page를 이동시키고 간섭을 어떻게 다루는지 확인해야 한다.

공정한 재실험에서는 같은 VM 메모리 크기와 입력을 사용하고, page가 시작한 tier, 이동량, major/minor fault, refault, 대역폭, PSI, 꼬리 latency를 함께 기록한다. 단독 실행과 여러 tenant 동시 실행을 나누면 위치 효과와 contention 효과를 구별할 수 있다.

## 14. 완전 풀이 문제

### 문제 1. VSZ와 RSS

프로세스가 10 GiB를 mmap하고 100 MiB만 썼다. VSZ 10 GiB, RSS 약 100 MiB가 가능한 이유는?

**풀이:** mmap은 가상 주소 범위와 VMA를 만들 수 있지만 모든 page frame을 즉시 만들지 않는다. 실제 touch한 page에서 fault와 물리 할당이 일어나므로 resident 양은 훨씬 작을 수 있다. page table·공유 page 등 세부 비용 때문에 정확히 100 MiB와 같다고 고정하지 않는다.

### 문제 2. minor와 major fault

이미 page cache에 있는 file page를 처음 mapping하는 fault와 storage에서 읽어야 하는 fault를 분류하라.

**풀이:** 이미 RAM page cache에 있어 PTE 연결만 필요하면 보통 minor fault다. page가 없어 저장 장치 I/O를 기다려야 하면 major fault다. 둘 다 합법적 demand paging일 수 있으며 프로그램 오류라는 뜻이 아니다.

### 문제 3. clean과 dirty 회수

clean file page 100 MiB와 dirty file page 100 MiB 중 어느 것이 즉시 회수하기 쉬운가?

**풀이:** 일반적으로 clean file page다. backing file과 같아 RAM 복사본을 버릴 수 있다. dirty page는 최신 내용을 writeback하고 완료를 확인해야 한다. 장치 속도와 writeback 상태에 따라 비용이 달라진다.

### 문제 4. 주소와 page offset

4 KiB page에서 주소 0x12345의 page 시작과 offset을 구하라.

**풀이:** 4 KiB는 0x1000이다. 하위 세 16진수가 offset이므로 0x345다. page 시작은 0x12000이다. 이 계산만으로 물리 주소는 알 수 없고 page table의 PFN이 필요하다.

### 문제 5. cgroup OOM

host에 8 GiB free가 있지만 memory.max 1 GiB인 cgroup이 1 GiB를 사용하고 회수 후보가 없다. 새 64 MiB allocation은 어떻게 될 수 있는가?

**풀이:** host 여유와 별개로 cgroup hard limit 안에서 charge가 불가능하다. reclaim을 시도하고 충분히 줄이지 못하면 cgroup OOM이 발생해 victim이 선택될 수 있다. 새 malloc 호출보다 실제 touch의 charge 시점에 드러날 수 있다.

### 문제 6. PSI 구간 계산

some total이 20초 구간에서 8,000,000 µs에서 11,000,000 µs로 증가했다. 구간 비율은?

**풀이:** 증가는 3,000,000 µs = 3초다. 3/20 × 100 = 15%다. avg10 값이 아니라 동일 구간의 total delta로 계산했다.

### 문제 7. some과 full

두 task가 500 ms stall했지만 셋째 계산 task가 계속 실행했다. full도 500 ms 증가하는가?

**풀이:** some은 일부 task가 막힌 wall-clock 구간에 증가할 수 있다. 모든 non-idle task가 동시에 막힌 것이 아니므로 그 500 ms 전체가 full은 아니다. 셋째 task까지 겹쳐 막힌 구간만 full에 기여할 수 있다.

### 문제 8. refault 반례

clean file cache를 대량 drop해 memory.current가 내려갔지만 직후 major fault와 I/O가 급증했다. 성공적인 최적화인가?

**풀이:** 공간 확보에는 성공했지만 실제 작업 집합을 버려 재접근 비용을 만든 refault·thrashing 가능성이 있다. 처리량과 latency, fault, refault, storage I/O를 함께 비교해야 한다. free memory 증가 하나만으로 성공을 판단하지 않는다.

## 공식 자료

- [Linux memory concepts](https://docs.kernel.org/admin-guide/mm/concepts.html)
- [Linux page reclaim](https://docs.kernel.org/mm/page_reclaim.html)
- [Linux PSI](https://docs.kernel.org/accounting/psi.html)
- [cgroup v2 memory controller](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [Memstrata: CXL memory tiering](https://www.usenix.org/conference/osdi24/presentation/zhong-yuhong)

[← 이전: CPU scheduling](03-cpu-scheduling-and-pressure.md) · [다음: cgroup v2 hierarchy →](05-cgroup-v2-hierarchy-and-delegation.md)
