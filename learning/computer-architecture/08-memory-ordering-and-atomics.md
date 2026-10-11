# 08. 메모리 순서와 원자 연산

[← 이전](07-coherence-and-false-sharing.md) · [목차](README.md) · [다음 →](09-mmu-tlb-and-page-walks.md)

동시에 실행되는 여러 작업이 같은 데이터를 주고받을 때 “최신 값을 본다”라는 말만으로는 충분하지 않다. 한 번의 값 갱신이 중간에 찢어지는지, 서로 다른 주소의 쓰기가 어느 순서로 보이는지, 한 thread가 준비한 data를 다른 thread가 언제 안전하게 사용할 수 있는지를 각각 구분해야 한다.

## 1. 먼저 구분할 실행 객체와 약속

**프로세스**는 실행 중인 프로그램이다. **CPU 코어**는 프로그램의 명령 흐름을 실행하는 하드웨어 단위다. **명령(instruction)**은 CPU에게 덧셈·읽기·쓰기 같은 일을 지시하는 기계어이고, **ISA(Instruction Set Architecture, 명령어 집합 구조)**는 프로그램과 CPU 사이에서 그 명령의 의미를 정한 계약이다. **컴파일러(compiler)**는 소스 코드를 기계 명령으로 변환하는 프로그램이다. 이 장에서는 **load**를 메모리에서 값을 읽는 연산, **store**를 메모리에 값을 쓰는 연산이라는 뜻으로 사용한다. 여러 작업이 같은 위치를 읽고 쓸 때의 약속은 소스 언어와 CPU 양쪽에서 지켜야 한다.

**스레드(thread)**는 명령을 순서대로 실행하는 소프트웨어 실행 흐름이다. 운영체제가 하나의 프로세스 안에 여러 thread를 만들고 서로 다른 CPU core에서 실행할 수 있다. **shared 메모리(공유 메모리)**는 여러 thread가 주소를 통해 접근할 수 있는 data다.

**atomicity(원자성)**는 한 operation이 다른 실행 주체에게 중간 단계 없이 하나의 사건처럼 보이는 성질이다. 일반 카운터++는 load, add, store 세 단계라 두 thread가 끼어들 수 있다. atomic fetch-add는 같은 atomic object에 대한 read-modify-write를 하나의 원자 사건으로 수행하도록 언어와 ISA가 약속한다.

**캐시 coherence(캐시 일관성)**는 같은 메모리 location의 여러 캐시 copy와 쓰기 권한을 조정한다. 한 주소에 대한 write가 모두에게 무작위로 뒤섞이지 않게 하지만, 서로 다른 주소 x와 y의 관찰 순서를 자동으로 정하지 않는다.

**메모리 ordering(메모리 순서)**은 여러 load와 store가 다른 실행 주체에게 어떤 순서로 관찰될 수 있는지를 정한다. compiler는 언어 규칙 안에서 instruction을 재배치할 수 있고 CPU는 store buffer와 비순차 실행으로 내부 진행을 바꿀 수 있다. 메모리 model은 그 결과 중 프로그램이 관찰해도 되는 경우를 정한다.

**publication(공개)**은 한 thread가 만든 일반 data를 다른 thread가 사용할 준비가 되었음을 synchronization object를 통해 알리는 pattern이다. data를 쓰고 flag를 release로 저장하며, 소비자가 그 flag 값을 acquire로 읽는 흐름이 대표적이다.

**happens-before(HB, 선행 관계)**는 “실제 시간이 먼저였다”라는 감상이 아니라 language 메모리 model이 정의한 순서 관계다. 한 스레드 안의 sequenced-before와 스레드 사이 synchronizes-with를 연결해 만든다. 데이터 write가 데이터 read보다 happens-before면 규칙을 지킨 프로그램에서 그 전달을 근거로 값을 사용할 수 있다.

~~~mermaid
flowchart LR
  S[소스의 atomic·lock] --> C[compiler의 순서 보존·재배치]
  C --> I[ISA load·store·AMO·fence]
  I --> H[core·store buffer·cache coherence]
  H --> O[다른 thread가 허용된 결과 관찰]
~~~

## 2. 왜 코어 내부 순서와 관찰 순서가 다른가

store instruction이 실행되었어도 캐시 ownership을 얻고 shared hierarchy에 반영될 때까지 기다릴 수 있다. CPU가 매 store마다 멈추지 않도록 **store buffer**라는 코어-local queue에 주소와 값을 임시로 둔다. 같은 core의 뒤 load는 자신의 older store와 주소가 같으면 buffer에서 값을 전달받을 수 있지만, 다른 core는 아직 그 store를 못 볼 수 있다.

load도 캐시 miss를 기다리는 동안 뒤의 독립 operation이 먼저 실행될 수 있다. CPU는 ISA 메모리 model이 허용하는 범위에서 이 지연을 숨긴다. language 컴파일러 역시 두 access 사이에 dependency와 synchronization이 없으면 소스 순서를 바꿀 수 있다.

따라서 소스 줄 순서, compiler가 만든 명령 순서, 코어 내부 완료 순서, 다른 core의 관찰 순서는 같은 목록이 아니다. 올바른 concurrent program은 language와 ISA가 제공하는 atomic, fence, lock을 사용해 필요한 관계를 명시한다.

## 3. store buffering litmus test

초기 x=0, y=0이고 x와 y는 atomic object라고 하자.

~~~text
Thread 0                    Thread 1
Sx: x.store(1, order)       Sy: y.store(1, order)
Ly: r1=y.load(order)        Lx: r2=x.load(order)
~~~

각 thread의 store가 자기 store buffer에 있고 상대 주소 load가 shared cache의 초기값을 읽으면 r1=0, r2=0이 가능할 수 있다. coherence가 고장 난 것이 아니다. x와 y 각각의 modification order는 유지되지만 서로 다른 주소 사이 전역 순서가 약하기 때문이다.

### 3.1 sequential consistency

**sequential consistency(SC, 순차 일관성)**는 모든 메모리 operation이 각 thread의 프로그램 order를 지키는 하나의 전역 순서에 놓인 것처럼 보이는 model이다. C++ seq_cst atomic에는 추가적인 단일 순서 제약이 있다.

r1=r2=0을 만들려면 Ly가 Sy보다 먼저, Lx가 Sx보다 먼저여야 한다. 스레드 순서 Sx<Ly와 Sy<Lx를 연결하면 Sx<Ly<Sy<Lx<Sx라는 순환이 생긴다. 전역 순서는 순환할 수 없으므로 모두 seq_cst일 때 (0,0)은 금지된다.

| 전역 순서 예 | r1 | r2 |
|---|---:|---:|
| Sx, Ly, Sy, Lx | 0 | 1 |
| Sy, Lx, Sx, Ly | 1 | 0 |
| Sx, Sy, Ly, Lx | 1 | 1 |

### 3.2 relaxed와 release/acquire

**relaxed atomic**은 해당 atomic object의 read와 write가 찢어지지 않고 그 object의 modification order에 참여하게 하지만, 다른 object의 순서를 전달하는 synchronization을 만들지 않는다. store buffering에서 (0,0)이 허용될 수 있다.

두 store를 release, 두 load를 acquire로 바꾸어도 load가 어떤 값을 읽었는지 봐야 한다. acquire load가 상대 release store가 쓴 1을 읽을 때에만 그 release와 acquire 사이 synchronizes-with가 생긴다. 두 load가 모두 초기 0을 읽으면 어느 것도 상대 release에서 읽지 않았으므로 synchronization 관계가 없다. 따라서 release/acquire 표기만으로 (0,0)이 일반적으로 금지된다고 말하면 틀리다.

RISC-V 기본 메모리 모형 RVWMO는 약한 순서를 허용한다. Ztso extension은 더 강한 TSO 성질을 선택적으로 제공한다. “RISC-V는 항상 TSO”라고 가정하지 않고 구현 extension과 compiler가 선택한 fence·atomic instruction을 확인한다.

## 4. message passing과 publication 전체 추적

초기 데이터=0, flag=0이고 flag는 atomic, data는 일반 object라고 하자.

~~~text
Producer                           Consumer
P1: data = 42                      C1: v = flag.load(acquire)
P2: flag.store(1, release)         C2: if (v == 1) use(data)
~~~

| 단계 | 주체 | 사건 | 관계와 결과 |
|---:|---|---|---|
| 1 | Producer | 데이터=42 | P1은 P2보다 sequenced-before |
| 2 | Producer | flag release store 1 | 앞선 데이터 write를 공개하는 사건 |
| 3A | Consumer | acquire load가 1을 읽음 | P2와 C1 synchronizes-with |
| 4A | Consumer | 조건 안에서 데이터 read | P1 happens-before, 42 사용 가능 |
| 3B | Consumer | acquire load가 0을 읽음 | release에서 읽지 않음, 동기화 없음 |
| 4B | Consumer | data를 사용하지 않고 retry | publication이 아직 완료되지 않음 |

“acquire를 사용했으니 언제나 데이터=42”가 아니다. acquire가 release가 쓴 1을 실제로 읽어야 한다. 0을 읽은 시도에서는 data를 접근하지 않고 다시 확인하거나 wait해야 한다.

flag store를 relaxed로 낮추면 데이터 write를 publication과 연결하는 release 관계가 없다. x86 같은 강한 hardware에서 우연히 원하는 결과가 자주 나와도 C++ program의 portable guarantee가 되지 않는다.

## 5. 데이터 race와 하드웨어 race를 구분한다

C++에서 **데이터 race(데이터 경쟁)**는 같은 메모리 위치에 대한 서로 다른 스레드의 충돌하는 접근 사이에 happens-before가 없고, 적어도 하나가 원자적이지 않은 경우를 포함한다. 읽기와 쓰기 또는 두 쓰기는 충돌할 수 있다. 두 접근이 모두 비원자적이어야 한다는 뜻은 아니다. 객체 수명의 시작·종료와 겹치는 접근도 규칙에 포함되므로 값의 읽기·쓰기만으로 객체 수명까지 보호했다고 볼 수 없다. 데이터 race가 있으면 프로그램 behavior는 undefined다. compiler는 “정의된 program에는 이런 race가 없다”고 가정해 load를 register에 한 번만 두거나 loop를 바꿀 수 있다.

교육용 CPU trace에서 두 일반 load/store를 그대로 실행해 lost update 결과를 그릴 수 있다. 이는 hardware가 만들 수 있는 한 interleaving을 이해하는 모형이지, 데이터 race가 있는 C++ source의 가능한 결과 목록을 보장하는 것이 아니다. language UB이면 컴파일러 transformation 때문에 교육 추적 밖의 결과도 가능하다.

Java, Rust, Linux kernel 메모리 model은 각기 규칙이 다르다. 사용하는 language와 runtime의 공식 메모리 model을 먼저 정하고 ISA instruction과 fence로 lowering되는 과정을 본다.

## 6. atomic read-modify-write

초기 카운터=0에서 두 thread가 일반 카운터++를 실행한다.

| 순서 | T0 | T1 | 결과 |
|---:|---|---|---|
| 1 | load 0 |  |  |
| 2 |  | load 0 |  |
| 3 | add→1 |  |  |
| 4 |  | add→1 |  |
| 5 | store 1 |  | 카운터=1 |
| 6 |  | store 1 | 카운터=1 |

두 번 증가했지만 최종 1이다. coherence는 두 store 순서를 정했지만 load-add-store 전체를 묶지 않았다.

atomic fetch_add라면 한 operation이 old value를 읽고 새 값을 쓰는 사건이다. 한 thread가 old=0을 받고 1을 쓰면 다른 thread는 old=1을 받고 2를 쓴다. 누가 먼저인지는 달라도 최종 2다.

RISC-V는 A extension에서 AMO와 LR/SC 같은 기작을 제공할 수 있다. **LR/SC(load-reserved/store-conditional)**는 load-reserved 뒤 같은 reservation set에 간섭이 없을 때만 store-conditional이 성공하는 pattern이다. SC가 실패하면 software가 retry한다. 예약 크기와 실패 조건은 단순 변수 크기보다 넓을 수 있어 무한 성공을 가정하지 않는다.

## 7. compare-exchange와 ABA

**compare-exchange(CAS)**는 메모리 값이 expected와 같을 때 desired로 바꾸고 성공 여부를 반환한다. lock-free stack의 head 포인터 갱신 등에 쓴다.

ABA 문제는 head가 A에서 B를 거쳐 다시 A가 되어 CAS가 “변화 없음”으로 오인하는 상황이다. 같은 주소 bit가 돌아왔어도 object 수명이나 next pointer가 바뀌었을 수 있다. version tag, hazard 포인터, epoch reclamation 같은 메모리 reclamation 기법이 필요할 수 있다. atomic CAS 하나가 데이터 structure 전체의 수명 안전성을 자동 해결하지 않는다.

## 8. fence의 역할과 한계

**fence(메모리 장벽)**는 fence 앞뒤 특정 종류의 메모리 연산 관찰 순서를 제한하는 ISA 명령 또는 language primitive다. RISC-V FENCE는 predecessor와 successor access 집합을 지정한다. 컴파일러 barrier와 하드웨어 fence도 구분한다. 컴파일러 barrier는 컴파일러 이동을 제한하지만 CPU ordering instruction을 반드시 만들지는 않는다.

fence를 많이 넣으면 우연히 test를 통과할 수 있지만 protocol이 명확하지 않으면 portable proof가 아니다. 어느 store를 어느 load가 읽고, 어떤 happens-before가 필요한지 먼저 적은 뒤 최소 ordering을 선택한다.

I/O access는 ordinary cacheable memory와 ordering 규칙이 다를 수 있다. device register에 command를 쓰기 전에 descriptor memory가 준비되어야 하는 경우 DMA API와 I/O fence 규칙을 따른다.

## 9. lock과 mutex

**mutex**는 한 시점에 하나의 thread만 critical section에 들어가게 하는 synchronization object다. lock acquire는 이전 owner의 unlock release와 연결되어 보호 data를 publish한다. mutual exclusion뿐 아니라 메모리 ordering도 제공한다.

spinlock은 기다리는 thread가 CPU를 양보하지 않고 반복 확인한다. 짧은 kernel critical section에는 쓸 수 있지만 오래 기다리면 CPU를 낭비한다. user-space mutex는 경쟁이 없을 때 atomic fast path, 경쟁 시 futex 같은 kernel wait를 사용할 수 있다.

lock-free는 모든 operation이 wait-free라는 뜻이 아니다. system 전체가 계속 진전한다는 progress guarantee이고 특정 thread는 반복 실패할 수 있다. correctness, progress, reclamation을 별도로 증명한다.

## 10. 최신 연구와 검증 방법

weak-메모리 program의 가능한 실행은 직관으로 모두 찾기 어렵다. **litmus test**는 몇 개 load/store와 초기값, 허용 결과를 작은 형태로 적어 hardware와 model을 비교한다. herd 계열 도구나 모형 checker가 관계 graph를 열거할 수 있다.

컴파일러 mapping 연구는 C++ atomic order가 RISC-V RVWMO나 Arm instruction과 fence로 올바르게 내려가는지 검증한다. 하드웨어 연구는 speculative load와 store queue가 ordering violation을 감지하고 replay하는지 확인한다. security 연구는 speculative execution과 캐시 side effect가 language-level ordering 밖의 timing channel을 만드는 문제를 다룬다.

실험에서 forbidden 결과를 한 번 못 봤다고 증명한 것은 아니다. 반복 횟수, 코어 pinning, 컴파일러 option, generated assembly, ISA extension, OS와 microcode를 기록한다. 실제 관찰과 formal model의 금지·허용을 함께 확인한다.

## 11. 문제와 전체 풀이

### 문제 1
store buffering의 네 operation이 relaxed일 때 (r1,r2)=(0,0)이 가능한 이유는?

**풀이:** 각 store가 자기 core의 buffer에 남아 상대 core에 보이기 전에 상대 주소 load가 초기값을 읽을 수 있다. x와 y 각각의 atomicity와 coherence는 유지되어도 서로 다른 주소의 전역 SC 순서는 없다.

### 문제 2
store는 release, load는 acquire인데 두 load가 0을 읽었다. synchronizes-with가 있는가?

**풀이:** 없다. acquire가 상대 release가 쓴 값을 읽지 않았기 때문이다. acquire라는 표기만으로 임의의 release와 연결되지 않는다.

### 문제 3
message passing에서 acquire가 flag=1을 읽었다. 데이터=42를 쓸 수 있는 이유는?

**풀이:** 데이터 write가 release보다 앞서고, acquire가 그 release의 1을 읽어 synchronizes-with가 생긴다. 관계를 연결하면 데이터 write가 소비자의 데이터 read보다 happens-before다.

### 문제 4
C++ 일반 int를 두 thread가 동기화 없이 읽고 쓰는 trace를 하드웨어 interleaving만으로 설명하면 왜 부족한가?

**풀이:** 적어도 하나가 write인 conflicting non-atomic access에 HB가 없으면 데이터 race이고 C++ behavior는 undefined다. 컴파일러 transformation까지 고려해야 하므로 단순 하드웨어 명령 순서가 소스 behavior 목록이 아니다.

### 문제 5
atomic counter는 여러 field의 불변식도 자동 보호하는가?

**풀이:** 아니다. 한 object의 read-modify-write 원자성만 보장한다. balance와 count를 함께 바꿔야 하면 lock, transaction, versioned protocol처럼 여러 object의 일관성을 다루는 기법이 필요하다.

### 문제 6
volatile 카운터++가 atomic fetch-add를 대신할 수 있는가?

**풀이:** 일반 C/C++ volatile은 access 제거와 device 의미에 관한 성질이지 스레드 atomicity와 HB를 만들지 않는다. load-add-store 사이에 다른 thread가 들어와 증가를 잃는다.

## 공식 자료

- [RISC-V Memory Models](https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/#memory-models)
- [RISC-V Ratified Specifications](https://docs.riscv.org/)
- [C++ memory model reference](https://eel.is/c++draft/intro.races)

[← 이전](07-coherence-and-false-sharing.md) · [목차](README.md) · [다음 →](09-mmu-tlb-and-page-walks.md)
