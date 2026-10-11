# 03. 함수 호출·ABI·프로그램 적재

[← 이전](02-instructions-registers-and-isa.md) · [목차](README.md) · [다음 →](04-pipelines-hazards-and-forwarding.md)

02장에서 instruction bit, register, PC를 배웠다. 그러나 함수 하나는 혼자 실행되지 않는다. caller가 argument를 넘기고 callee가 일부 register를 보존하며, linker가 서로 다른 object file의 symbol을 연결하고 loader가 process 주소 공간을 준비해야 한다. 이 장은 C 함수 호출 한 번을 source, ABI, ELF, virtual address, stack frame, return까지 추적한다.

## 1. 함수와 호출은 제어 흐름의 약속이다

**함수(function)**는 이름과 interface를 가진 코드 묶음이다. **호출자(caller)**는 함수를 부르는 쪽이고 **피호출자(callee)**는 불린 함수다. caller는 argument와 return address를 준비하고 callee로 PC를 바꾼다. callee는 계산한 return value를 약속된 위치에 둔 뒤 caller의 다음 instruction으로 돌아간다.

source 수준의 호출은 한 문장처럼 보이지만 machine 수준에서는 다음 문제가 생긴다.

- argument를 어느 register와 memory에 둘 것인가
- return value를 어디에 둘 것인가
- 현재 PC 다음 위치를 어떻게 기억할 것인가
- caller와 callee 중 누가 register를 보존할 것인가
- stack pointer를 어떤 alignment로 유지할 것인가
- 큰 구조체, variadic argument, exception unwind 정보를 어떻게 표현할 것인가

ISA만으로는 이 질문의 답이 모두 정해지지 않는다. ISA가 jump와 register를 제공하고, 그 위의 ABI가 협업 규칙을 정한다.

## 2. ABI와 calling convention

**ABI(Application Binary Interface, 응용 바이너리 인터페이스)**는 이미 machine code로 번역된 구성 요소가 서로 협력하기 위한 규약이다. calling convention뿐 아니라 자료형 크기와 alignment, object file 형식, symbol naming, relocation, system call interface 일부 등을 포함할 수 있다.

**calling convention(호출 규약)**은 ABI 중 함수 호출에 직접 관련된 부분이다. argument register, return register, stack layout, register 보존 책임을 정한다. 서로 다른 source language와 compiler가 만든 object file도 같은 ABI를 따르면 연결할 수 있다.

RISC-V psABI의 integer calling convention에서는 x10~x17을 a0~a7이라는 argument register 이름으로 사용한다. a0와 a1은 return value에도 쓰인다. x1은 ra(return address), x2는 sp(stack pointer) 역할을 맡는다. x8~x9와 x18~x27은 s0~s11이라는 callee-saved register다. t0~t6와 a0~a7은 caller-saved다.

이 이름은 register의 hardware 종류가 다르다는 뜻이 아니다. ISA에서 x10은 일반 integer register지만 ABI가 a0라는 역할을 부여한다. hand-written assembly가 역할을 어기면 instruction 자체는 합법이어도 다른 binary와 협력하지 못한다.

## 3. caller-saved와 callee-saved

**caller-saved register**는 호출 뒤 값이 유지된다고 기대할 수 없다. caller가 그 값을 계속 써야 한다면 호출 전에 stack이나 다른 안전한 곳에 저장한다. **callee-saved register**는 callee가 값을 바꾸려면 원래 값을 저장했다가 return 전에 복구해야 한다.

왜 두 종류를 나눌까? 모든 호출에서 모든 register를 저장하면 불필요한 memory traffic이 커진다. 짧게 쓰는 임시값은 caller-saved에 두고, 여러 호출을 가로질러 오래 사는 값은 callee-saved에 두면 compiler가 비용을 선택할 수 있다.

반례를 보자. caller가 s1에 loop limit 100을 보관하고 f를 호출한다. f가 s1을 7로 바꾸고 복구하지 않으면 f 내부 결과는 맞아도 caller의 loop가 잘못된다. ISA는 s1 쓰기를 허용하지만 psABI 위반이다.

반대로 caller가 t0 값이 호출 뒤 유지될 것이라고 가정하면 caller가 잘못이다. callee는 t0를 자유롭게 임시값으로 쓸 수 있다. 보존 책임은 “누가 실제로 값을 바꿨는가”만이 아니라 ABI가 어느 분류로 정했는가에 달렸다.

## 4. stack과 stack frame

**stack**은 함수 호출의 중첩 구조를 관리하는 memory 영역이다. 일반적으로 최근 호출이 먼저 return하는 LIFO 구조로 사용한다. RISC-V의 stack은 관례상 낮은 주소 방향으로 자란다. **SP(stack pointer)**는 현재 stack의 기준 주소를 가리킨다.

**stack frame**은 한 함수 호출이 사용하는 stack 구역이다. 저장한 return address, callee-saved register, memory에 내려놓은 local variable, register에 못 둔 temporary, outgoing argument 공간이 포함될 수 있다. 모든 함수가 반드시 같은 모양의 frame을 갖는 것은 아니다. compiler는 필요 없는 frame을 없애거나 frame pointer를 생략할 수 있다.

**frame pointer**는 frame 안의 위치를 일정한 기준으로 접근하기 위한 register다. stack pointer가 함수 중간에 변해도 local과 saved state를 안정된 offset으로 찾는 데 유용하다. optimized code에서는 unwind 정보가 충분하면 별도 frame pointer를 쓰지 않을 수 있다.

RISC-V psABI는 procedure entry에서 stack pointer alignment 규칙을 정한다. 표준 ABI를 따르는 코드가 임의로 alignment를 깨면 vector나 여러 byte 객체 접근, 다른 함수 호출에서 문제가 생길 수 있다.

### 4.1 숫자로 보는 frame

호출 직전 sp=0x8000이고 callee가 48바이트 frame을 만든다고 하자. stack이 낮은 주소로 자라므로 새 sp는 0x8000-0x30=0x7fd0이다.

| 주소 범위 또는 위치 | 교육용 내용 |
|---|---|
| 0x7ff8 | 저장한 ra |
| 0x7ff0 | 저장한 s0 |
| 0x7fe8 | 저장한 s1 |
| 0x7fe0 | 8바이트 local |
| 0x7fd0~0x7fdf | spill·padding |
| sp=0x7fd0 | frame의 현재 아래 경계 |

이 배치는 교육 예다. 실제 compiler가 선택한 offset과 frame 크기는 optimization, local type, 호출 여부에 따라 다르다. return 전에는 s1, s0, ra를 원래 값으로 복구하고 sp에 48을 더해 0x8000으로 되돌린다.

frame 크기가 alignment 배수인지도 확인한다. 48은 16의 배수다. 40바이트만 빼면 sp가 0x7fd8이 되어 16바이트 alignment가 깨질 수 있다. compiler는 실제 저장량보다 큰 frame을 잡아 padding을 둘 수 있다.

## 5. call과 return을 instruction으로 추적한다

다음 C 함수를 생각하자.

~~~c
long twice_plus(long x, long bias) {
    return x * 2 + bias;
}

long caller(void) {
    return twice_plus(7, 5) + 1;
}
~~~

RISC-V psABI에서 caller는 a0=7, a1=5를 준비한다. JAL instruction이 callee로 이동하면서 return address를 ra에 기록할 수 있다. callee는 a0를 두 배로 만들고 a1을 더해 a0=19를 반환한다. caller는 return 뒤 a0에 1을 더해 20을 반환한다.

교육용 주소 trace를 적는다.

| 단계 | PC 또는 주체 | 상태 변화 |
|---:|---|---|
| 1 | caller PC=0x401000 | a0=7, a1=5 준비 |
| 2 | call at 0x401008 | ra=0x40100c, PC=0x402000 |
| 3 | callee | a0=14, 이어 a0=19 |
| 4 | return | PC=ra=0x40100c |
| 5 | caller continuation | a0=20 |
| 6 | caller의 return | 자신의 저장된 return 경로로 이동 |

실제 JAL의 target 범위와 encoding, linker relaxation 여부는 다를 수 있다. 핵심은 call site의 다음 주소와 callee entry를 분리하고, nested call이 있으면 현재 ra를 보존해야 한다는 점이다.

callee가 다시 다른 함수를 호출하면 새 call이 ra를 덮어쓴다. 따라서 자신의 caller로 돌아갈 ra가 필요하면 stack에 저장하거나 callee-saved 위치로 옮겨야 한다. leaf function, 즉 다른 함수를 호출하지 않는 함수는 조건에 따라 ra 저장을 생략할 수 있다.

~~~mermaid
sequenceDiagram
  participant C as caller
  participant S as stack frame
  participant F as callee
  C->>C: a0·a1에 argument 배치
  C->>F: JAL, ra에 다음 PC
  F->>S: 필요한 ra·s-register 저장
  F->>F: 계산, a0에 return value
  F->>S: 저장 상태 복구
  F-->>C: ra로 return
  C->>C: a0 결과 계속 사용
~~~

## 6. argument가 register보다 많거나 큰 경우

integer argument가 a0~a7보다 많으면 나머지를 stack으로 전달할 수 있다. 정확한 위치와 alignment는 psABI를 따른다. “아홉 번째 인자는 무조건 sp+0”처럼 문맥 없이 외우면 숨은 return pointer나 자료형 alignment 때문에 틀릴 수 있다.

큰 구조체를 값으로 반환하면 register 두 개에 다 들어가지 않을 수 있다. caller가 return object를 쓸 memory 주소를 숨은 argument로 전달하고 callee가 그 위치에 쓸 수 있다. source에는 pointer가 보이지 않아도 ABI lowering 과정에서 생긴다.

**variadic function**은 printf처럼 argument 수와 type이 호출마다 달라질 수 있는 함수다. 고정 parameter와 가변 parameter를 register와 stack에서 일관되게 찾는 ABI 규칙이 필요하다. format string과 실제 argument type이 맞지 않으면 ABI가 byte를 전달했어도 language 수준 해석이 잘못되어 undefined behavior가 생길 수 있다.

부동소수점 register를 사용하는 calling convention과 integer-only convention도 구분한다. 같은 함수 이름이라도 ABI variant가 다르면 argument 위치가 달라 binary 호환이 깨질 수 있다. compiler option과 library ABI를 맞춰야 한다.

## 7. object file, section, segment

compiler는 source file마다 보통 **object file**을 만든다. object file에는 machine code만 있는 것이 아니라 symbol table, relocation, debug 정보, 여러 section이 들어간다.

**section**은 linking 관점에서 같은 성격의 내용을 묶은 단위다. 예를 들어 .text는 code, .rodata는 read-only data, .data는 초기값이 있는 writable data, .bss는 실행 시작 시 0으로 초기화할 영역을 표현할 수 있다. 이름과 세부는 toolchain과 object format 규칙을 따른다.

**segment**는 loader가 process address space에 mapping할 단위다. 여러 section이 같은 permission과 page 조건에 따라 하나의 loadable segment에 묶일 수 있다. section과 segment를 같은 말로 쓰면 linker 관점과 loader 관점을 혼동한다.

~~~mermaid
flowchart LR
  S1["source a.c"] --> O1["a.o: text·symbol·relocation"]
  S2["source b.c"] --> O2["b.o: text·symbol·relocation"]
  O1 --> LD["static linker"]
  O2 --> LD
  LIB["library"] --> LD
  LD --> ELF["ELF executable 또는 shared object"]
  ELF --> K["kernel loader"]
  K --> V["virtual memory segments"]
  V --> D["dynamic linker가 필요한 symbol 해결"]
  D --> P["초기 PC·SP로 실행"]
~~~

## 8. symbol과 relocation

**symbol**은 함수나 전역 객체 같은 항목에 이름을 붙인 linker 수준 표현이다. 정의된 symbol, 다른 object에서 찾을 undefined symbol, visibility와 binding 정보가 있다.

**relocation**은 최종 주소가 정해지면 수정해야 할 위치와 계산 방법을 기록한다. compiler가 a.o를 만들 때 b.o의 함수 f 주소를 모를 수 있다. call instruction이나 address materialization 위치에 relocation entry를 남기고 linker가 최종 배치 뒤 값을 계산한다.

예를 들어 call site가 0x401000이고 f가 0x402000이라면 PC-relative 차이는 0x1000이다. 실제 RISC-V relocation은 instruction field 분할, range, pair relocation, relaxation 규칙을 따르므로 단순히 0x1000을 한 field에 쓰는 것으로 끝나지 않을 수 있다.

**linker relaxation**은 더 일반적인 instruction sequence를 최종 주소가 정해진 뒤 짧거나 빠른 형태로 바꾸는 최적화다. object file에서 본 instruction과 최종 executable의 instruction이 달라질 수 있다. disassembly를 비교할 때 어느 단계의 파일인지 밝혀야 한다.

## 9. 정적 linking과 동적 linking

**정적 linking**은 필요한 library code 일부를 executable에 포함해 symbol을 해결할 수 있다. 실행 파일이 커질 수 있지만 배포 시 외부 shared object 의존성이 줄 수 있다. 모든 OS 자원과 의존성이 완전히 사라진다는 뜻은 아니다.

**동적 linking**은 shared object를 실행 시 process에 mapping하고 필요한 symbol을 연결한다. 여러 process가 read-only code page를 공유할 수 있고 library를 별도로 갱신할 수 있지만, ABI와 version 호환, search path, 시작 비용을 관리해야 한다.

**GOT(Global Offset Table)**는 position-independent code가 data나 symbol 주소를 간접적으로 얻는 데 사용하는 table이고, **PLT(Procedure Linkage Table)**는 외부 함수 호출을 dynamic linker의 resolution 경로와 연결하는 데 사용될 수 있다. 구체 사용은 architecture와 linker option에 따라 달라진다.

**lazy binding**은 외부 함수를 처음 호출할 때 주소를 해결하고 이후 table을 갱신하는 방식이다. 시작 시간을 줄일 수 있지만 첫 호출 지연과 보안 설정에 영향을 준다. immediate binding을 선택할 수도 있다. RELRO 같은 hardening은 relocation 뒤 table 일부를 read-only로 바꿔 공격 표면을 줄인다.

## 10. ELF와 loader의 실제 역할

ELF header는 파일 종류, target machine, entry point, program header 위치 같은 정보를 담는다. **program header table**은 loader가 어떤 file offset을 어느 virtual address에 어떤 permission으로 mapping할지 설명한다.

교육용 executable의 program header가 다음을 뜻한다고 하자.

| file offset | file size | memory size | virtual address | permission |
|---:|---:|---:|---:|---|
| 0x1000 | 0x1800 | 0x1800 | 0x400000 | R-X |
| 0x3000 | 0x0400 | 0x0800 | 0x600000 | RW- |

첫 segment는 code와 read-only 내용을 0x400000에 실행 가능하게 mapping한다. 둘째는 file의 0x400 byte를 0x600000에 mapping하지만 memory size가 0x800이므로 나머지 0x400 byte는 0으로 초기화될 수 있다. 이것이 .bss와 연결되는 전형적 형태다.

file offset 0x1120이 첫 segment 안에 있다면 대응 virtual address는 0x400000+(0x1120-0x1000)=0x400120이다. file offset, virtual address, physical address는 같은 숫자일 필요가 없다. demand paging에서는 virtual mapping이 먼저 생기고 첫 access 때 page cache와 physical frame이 연결될 수 있다.

loader는 stack과 초기 process 정보를 준비한다. argc, argv 문자열과 pointer, environment, auxiliary vector가 stack 근처에 놓일 수 있다. **auxiliary vector**는 page size, program header 위치, dynamic linker에 필요한 platform 정보를 key-value 형태로 전달한다.

최종적으로 kernel이 직접 main을 첫 PC로 두는 것이 일반 규칙은 아니다. ELF entry point는 C runtime 시작 코드나 dynamic linker 경로를 가리킬 수 있다. runtime이 초기화, constructor, TLS 설정을 마친 뒤 main을 호출한다.

## 11. virtual address, permission, ASLR

code segment는 보통 read와 execute permission, writable data는 read와 write permission을 가진다. W^X 정책은 같은 page를 writable과 executable로 동시에 두지 않아 code injection 위험을 줄이려는 원칙이다. 모든 platform의 절대 규칙이라고 단정하지 말고 실제 OS 정책을 확인한다.

**ASLR(Address Space Layout Randomization)**은 executable, shared library, heap, stack 등의 virtual address를 실행마다 바꾸어 공격자가 주소를 예측하기 어렵게 한다. position-independent executable과 shared object는 고정 절대주소 의존을 줄여 임의 위치 mapping을 돕는다.

ASLR이 source나 instruction 의미를 바꾸는 것은 아니다. symbol의 실행 시 주소가 달라지고 relocation과 PC-relative addressing이 이를 처리한다. debug log의 주소를 다른 실행에 그대로 적용할 수 없는 이유다.

**TLS(Thread-Local Storage)**는 thread마다 별도 인스턴스를 가져야 하는 전역 형태 데이터를 제공한다. 일반 global처럼 symbol 이름은 하나여도 현재 thread의 TLS base를 이용해 실제 주소를 찾는다. process 전체의 같은 virtual address에 단순히 하나만 존재한다고 생각하면 안 된다.

## 12. system call과 함수 호출의 차이

일반 함수 호출은 같은 privilege level의 code로 PC를 바꾸고 ABI에 따라 register와 stack을 사용한다. **system call**은 ISA가 제공하는 환경 호출 instruction을 통해 kernel에 서비스를 요청한다. privilege 전환, trap 처리, kernel의 별도 ABI가 관련된다.

C library의 read 함수는 내부에서 system call wrapper를 호출할 수 있지만 둘은 같은 층이 아니다. library가 buffering이나 error 변환을 추가할 수 있고 어떤 기능은 system call 없이 사용자 공간에서 처리할 수도 있다. function return address와 exception return 상태도 다른 메커니즘이다.

## 13. unwind, exception, debugging

**stack unwinding**은 현재 frame에서 caller frame으로 거슬러 올라가는 과정이다. debugger의 backtrace, language exception 처리, profiler가 사용한다. optimized code가 frame pointer를 생략해도 compiler가 생성한 unwind metadata로 saved register와 return address 위치를 찾을 수 있다.

tail call optimization은 현재 함수의 frame을 정리하고 다른 함수로 jump해 현재 frame을 남기지 않을 수 있다. inline optimization은 callee body를 caller 안에 넣어 실제 call 자체를 없앨 수 있다. source의 함수 호출 수와 runtime stack frame 수가 항상 일치하지 않는다.

coroutine과 user-level scheduler는 하나의 OS thread stack만 단순히 따르지 않을 수 있다. 각 coroutine의 저장 상태와 stack, continuation을 runtime이 관리한다. ABI 기본을 알아야 이런 최신 runtime의 context switch 비용과 unwind 한계를 분석할 수 있다.

## 14. 전체 trace: source에서 return까지

main이 다른 object file의 <code>sum(7,5)</code>를 호출한다고 하자.

1. compiler는 main.o에 argument 준비와 미해결 sum call, relocation을 만든다.
2. sum.c의 compiler 결과 sum.o는 a0와 a1을 더해 a0에 두는 code와 sum symbol 정의를 가진다.
3. linker는 sum symbol 주소를 정하고 call relocation을 적용해 ELF를 만든다.
4. kernel loader는 ELF program header에 따라 code와 data segment를 virtual address에 mapping한다.
5. dynamic dependency가 있으면 dynamic linker가 shared object와 relocation을 처리한다.
6. runtime entry code가 stack의 argc, argv 등을 읽고 main을 호출한다.
7. main은 a0=7, a1=5를 준비하고 call한다.
8. call instruction은 ra에 다음 PC를 기록하고 sum entry로 이동한다.
9. sum의 ADD는 12를 만들고 a0에 둔다.
10. return은 ra를 다음 PC로 사용하고 main이 a0=12를 관찰한다.
11. main이 끝나면 runtime과 kernel 경로를 통해 process 종료 상태가 전달된다.

이 trace에서 source 함수, symbol, file offset, virtual address, physical page, register 값은 서로 다른 대상이다. 하나의 숫자 “주소”로 뭉뚱그리면 linker 오류와 page fault와 잘못된 function pointer를 구분하기 어렵다.

## 15. 문제와 전체 풀이

### 문제 1. stack frame 계산

sp=0x9000에서 48바이트 frame을 만들면 새 sp는 얼마인가? 16바이트 alignment도 확인하라.

**풀이:** 48=0x30이므로 새 sp는 0x9000-0x30=0x8fd0이다. 0x8fd0은 16으로 나누어떨어지므로 alignment가 유지된다. return 전에 저장 register를 복구하고 sp를 0x9000으로 되돌린다.

### 문제 2. nested call과 ra

f가 caller에서 호출되어 ra=0x40100c를 가진 상태로 g를 다시 호출한다. f가 ra를 저장하지 않으면 어떤 문제가 생기는가?

**풀이:** g를 부르는 call이 ra를 f 안의 다음 주소로 덮어쓴다. g에서 돌아온 뒤 f가 원래 caller 주소 0x40100c를 잃는다. f는 nested call 전 ra를 stack 등 ABI에 맞는 위치에 저장하고 g return 뒤 복구해야 한다. leaf function이라면 이 저장이 필요 없을 수 있다.

### 문제 3. file offset과 virtual address

file offset 0x1000부터인 segment가 virtual address 0x400000에 mapping된다. segment 안 file offset 0x1260의 virtual address는?

**풀이:** segment 시작에서 차이는 0x1260-0x1000=0x260이다. virtual address는 0x400000+0x260=0x400260이다. physical address는 page table과 현재 residency에 따라 별도로 정해지므로 이 계산만으로 알 수 없다.

### 문제 4. ABI 위반

callee가 s1을 임시값으로 바꾸고 복구하지 않았지만 자신의 return value는 맞다. 올바른 함수인가?

**풀이:** psABI에서 s1은 callee-saved이므로 올바르지 않다. caller는 호출 전 s1 값이 유지된다고 가정할 수 있다. callee가 바꾸려면 저장·복구해야 한다. ISA가 s1 쓰기를 허용한다는 사실은 ABI 의무를 없애지 않는다.

### 문제 5. linker와 loader

다른 object file의 함수 주소를 해결하는 일과 ELF segment를 process virtual address에 mapping하는 일을 각각 누가 하는가?

**풀이:** static linker가 symbol 정의와 참조를 연결하고 relocation을 적용해 실행 이미지를 만든다. 실행 시 kernel loader가 program header에 따라 segment를 virtual address에 mapping하고 초기 stack과 PC를 준비한다. shared object의 runtime symbol resolution은 dynamic linker가 추가로 수행할 수 있다. 세 역할을 모두 “compiler가 실행한다”라고 부르면 단계별 오류를 찾을 수 없다.

## 16. 공식 자료와 다음 장

RISC-V psABI는 현재 calling convention, ELF 사용, relocation 규칙을 설명하는 기준 문서다. ABI 문서의 draft 표시는 문서 전체가 불안정하다는 뜻으로 단순 해석하지 말고 각 부분의 상태와 사용하는 toolchain 계약을 확인한다. Linux ELF 문서는 kernel 구현 맥락을 제공한다.

- [RISC-V ELF psABI Specification](https://github.com/riscv-non-isa/riscv-elf-psabi-doc)
- [System V ABI](https://gitlab.com/x86-psABIs/x86-64-ABI)
- [Linux kernel ELF documentation](https://docs.kernel.org/core-api/elf.html)
- [RISC-V Ratified Specifications](https://docs.riscv.org/)

다음 장에서는 function의 instruction들이 pipeline에 겹칠 때 data hazard, forwarding, stall이 어떻게 생기는지 추적한다.

[← 이전](02-instructions-registers-and-isa.md) · [목차](README.md) · [다음 →](04-pipelines-hazards-and-forwarding.md)
