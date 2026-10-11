# 02. 명령어·레지스터·ISA

[← 이전](01-digital-logic-and-clock.md) · [목차](README.md) · [다음 →](03-functions-abi-and-program-loading.md)

01장에서 gate와 flip-flop이 비트를 계산하고 저장하는 원리를 배웠다. 이번 장은 그 회로가 소프트웨어에 어떤 약속으로 보이는지 설명한다. 명령 바이트를 field로 나누고, register 번호와 즉시값을 해석하며, PC와 주소가 어떻게 다음 상태를 고르는지 숫자로 추적한다.

## 1. ISA는 바이너리 계약이다

**ISA(Instruction Set Architecture)**는 소프트웨어와 하드웨어 사이의 관찰 가능한 계약이다. CPU가 이해할 명령 종류만 나열하는 표가 아니다. 다음 항목을 함께 정의한다.

- 명령의 bit encoding과 길이
- 소프트웨어에 보이는 register와 폭
- 정수·부동소수점 연산 결과와 예외
- load와 store의 주소 계산, 정렬, byte 순서
- branch, jump, trap 뒤의 PC
- 여러 hart가 메모리를 관찰하는 순서
- 사용자·감독자 같은 특권 수준과 선택 extension

**기계어(machine code)**는 ISA 명령을 bit로 표현한 것이다. **assembly language**는 사람이 기계어를 읽기 쉽도록 mnemonic과 register 이름으로 적은 표현이다. ADD라는 문자열을 CPU가 읽는 것이 아니라 assembler가 정해진 bit pattern으로 바꾼다.

**명령(instruction)**은 한 건축적 상태 전이 요청이다. **opcode**는 동작 계열을 식별하는 field다. **operand**는 입력값 또는 위치이며 register, immediate, memory address를 만드는 base와 offset일 수 있다. **field**는 명령 bit 중 특정 뜻을 가진 연속 또는 분산된 부분이다.

ISA와 **microarchitecture**를 구분한다. ISA가 ADD 결과를 정해도 CPU가 내부에서 ripple-carry adder, carry-lookahead, 여러 pipeline stage 중 무엇을 쓰는지는 정하지 않는다. RISC-V라는 이름만으로 cache 크기, branch predictor, clock, 성능을 알 수 없다.

RISC-V 명세는 base integer ISA와 선택 extension을 모듈로 정의한다. RV32I는 32비트 integer register를 갖는 base, RV64I는 64비트 base를 뜻한다. M은 integer multiply/divide, A는 atomic, F와 D는 floating-point 같은 extension이다. 제품이 어떤 extension과 privileged 기능을 구현했는지는 별도로 확인해야 한다.

## 2. register는 값과 역할을 연결하는 이름이다

**register**는 ISA가 번호로 노출한 빠른 상태 위치다. RISC-V base integer ISA에는 x0부터 x31까지 integer register가 있다. x0을 읽으면 0이고 쓰기는 버려진다. 나머지 register가 항상 특정 변수 전용인 것은 아니다. compiler와 ABI가 순간마다 인자, 임시값, stack pointer 같은 역할을 배정한다.

RV32I에서 XLEN은 32이고 일반 integer register는 32비트 값을 담는다. RV64I의 XLEN은 64다. 같은 bit pattern도 signed인지 unsigned인지에 따라 해석이 다르다. 예를 들어 RV32에서 0xffffffff는 unsigned 4,294,967,295이고 2의 보수 signed -1이다. register 자체에 “나는 signed”라는 tag가 붙는 것은 아니다. 어떤 명령과 프로그래밍 언어 형이 bit를 어떻게 해석하는지가 의미를 만든다.

**PC(program counter)**는 현재 또는 다음 명령 주소와 관련된 건축적 상태다. RISC-V base instruction은 32비트, 즉 4바이트이고 compressed extension C가 있으면 16비트 명령도 섞일 수 있다. 따라서 PC 증가량은 실제 해독한 명령 길이를 따라야 한다. 분기, jump, exception이면 순차 주소 대신 다른 주소가 선택된다.

**hart(hardware thread)**는 RISC-V 명세에서 독립적으로 명령을 fetch하고 실행하는 hardware thread를 뜻한다. core 하나에 hart 하나일 수도, SMT로 여러 hart가 있을 수도 있다. process, OS thread, hart는 같은 개념이 아니다. OS가 software thread를 어느 hart에서 실행할지 schedule한다.

## 3. 교육용 16비트 ISA로 field를 배운다

먼저 field 자르기 자체를 보기 위해 실제 제품이 아닌 16비트 교육 ISA를 사용한다.

~~~text
15..12 opcode | 11..8 rd | 7..4 rs1 | 3..0 rs2
ADD opcode = 0001
SUB opcode = 0010
~~~

ADD r3,r1,r2는 다음처럼 encoding한다.

~~~text
opcode  rd    rs1   rs2
0001    0011  0001  0010
~~~

이어 붙이면 0001 0011 0001 0010₂=0x1312다. decoder는 오른쪽에서 4비트씩 잘라 rs2=2, rs1=1, rd=3, opcode=1을 얻는다. r1=9, r2=6이면 ALU 결과는 15이고 정상 retire 뒤 r3=15다.

두 번째 trace로 0x2a47을 해독하자.

- 상위 nibble 2이므로 opcode=SUB
- 다음 nibble a는 rd=10
- 다음 nibble 4는 rs1=4
- 마지막 nibble 7은 rs2=7
- r4=30, r7=11이면 결과는 19

이 ISA에서 명령 길이는 2바이트이므로 PC=0x2000에서 순차 다음 후보는 0x2002다. 이 규칙을 RISC-V에 그대로 적용하면 안 된다. 교육 ISA는 field 추출 연습용이다.

~~~mermaid
flowchart LR
  P[PC] --> F[명령 byte fetch]
  F --> J[field 분리]
  J --> O[opcode 해석]
  J --> R[register 번호]
  J --> I[immediate 조립·확장]
  R --> E[ALU·주소 장치]
  I --> E
  O --> E
  E --> W[결과 또는 다음 PC]
~~~

## 4. 실제 RISC-V R-type encoding

RV32I와 RV64I의 기본 32비트 R-type 형식은 다음 field를 사용한다.

~~~text
31..25 funct7 | 24..20 rs2 | 19..15 rs1 | 14..12 funct3 | 11..7 rd | 6..0 opcode
~~~

ADD의 integer register-register opcode는 0110011₂이고 funct3=000, funct7=0000000이다. SUB는 같은 opcode와 funct3를 사용하지만 funct7=0100000으로 구분한다. 같은 opcode field만 보고 정확한 동작을 결정할 수 없는 이유다.

ADD x5,x6,x7을 encoding해 보자.

| field | 값 | 폭 | bit 위치 |
|---|---:|---:|---|
| funct7 | 0000000 | 7 | 31..25 |
| rs2 | 00111 | 5 | 24..20 |
| rs1 | 00110 | 5 | 19..15 |
| funct3 | 000 | 3 | 14..12 |
| rd | 00101 | 5 | 11..7 |
| opcode | 0110011 | 7 | 6..0 |

숫자식으로 조립하면 다음과 같다.

- rs2: 7을 bit 20으로 이동 → 0x00700000
- rs1: 6을 bit 15로 이동 → 0x00030000
- rd: 5를 bit 7로 이동 → 0x00000280
- opcode: 0x33
- OR 결과: 0x007302b3

따라서 32비트 instruction word는 0x007302b3다. little-endian memory에 연속 byte로 저장되면 낮은 주소부터 b3 02 73 00이 된다. “instruction 값의 16진수 표기”와 “memory에 놓인 byte 순서”를 구분해야 한다.

다시 0x407302b3을 해독하면 opcode, rd, rs1, rs2, funct3는 같고 funct7이 0100000이다. 따라서 SUB x5,x6,x7이다. x6=20, x7=3이면 x5=17이 된다. 단 한 field의 bit가 ADD와 SUB를 구분한다.

이 encoding은 현재 RISC-V unprivileged ISA의 실제 R-type 규칙을 설명한 것이다. 하지만 특정 CPU가 내부에서 이 명령을 몇 micro-operation으로 바꾸는지, latency가 몇 cycle인지는 ISA의 보장이 아니다.

## 5. immediate는 작은 상수와 offset을 싣는다

**immediate**는 명령 bit 안에 직접 들어 있는 상수다. 모든 즉시값이 연속 field인 것은 아니다. RISC-V는 register field 위치를 여러 형식에서 일정하게 유지하려고 immediate bit를 나누어 배치하기도 한다.

I-type은 대략 다음 구조다.

~~~text
31..20 immediate[11:0] | 19..15 rs1 | 14..12 funct3 | 11..7 rd | 6..0 opcode
~~~

ADDI x5,x6,-16을 생각하자. 12비트 2의 보수 -16은 0xff0이다. instruction이 실행될 때 immediate를 XLEN으로 **sign extension(부호 확장)**한다. RV32라면 0xfffffff0, RV64라면 0xfffffffffffffff0의 bit pattern이 된다. x6=100이면 결과는 84다.

부호 확장은 원래 폭의 최상위 sign bit를 새 상위 bit에 복제한다. 12비트 0x7ff는 +2047이고 0x800은 -2048이다. 0xff0을 unsigned 4080으로 더하면 ADDI -16의 의미를 잘못 해석한다.

**zero extension(0 확장)**은 새 상위 bit를 0으로 채운다. signed load와 unsigned load의 차이도 확장 방식에서 나타난다. RV64에서 LB는 읽은 8비트의 sign bit를 복제하고 LBU는 0으로 채운다. memory byte가 0x80이면 LB 결과는 64비트 signed -128의 pattern이고 LBU 결과는 128이다.

## 6. load와 store의 주소 계산

RISC-V는 load-store ISA다. integer 산술 명령이 memory 값을 직접 두 operand로 쓰지 않는다. load가 memory에서 register로 값을 가져오고, 산술이 register 값을 계산하며, store가 register 값을 memory에 쓴다.

~~~text
LW x5, 12(x6)
ADD x7, x5, x8
SW x7, 16(x6)
~~~

x6=0x1000이면 첫 effective address는 0x1000+12=0x100c다. 주소 변환과 read 권한 검사가 성공하고 그 위치의 네 byte가 2a 00 00 00이라면 little-endian 32비트 값은 42다. LW는 RV64에서도 32비트 값을 읽고 sign extension한다. 이어 x8=5라면 ADD 결과 x7=47이다. SW의 주소는 0x1010이며 x7의 낮은 32비트를 네 byte로 저장한다.

**effective address**는 instruction이 base register와 offset으로 계산한 가상주소다. 이후 MMU가 물리주소로 번역한다. effective address, physical address, 그 위치의 data는 서로 다른 값이다.

## 7. endianness는 byte 순서 규칙이다

**endianness**는 여러 byte로 된 값을 memory의 증가하는 주소에 어떤 순서로 놓는지 정한다. little-endian은 가장 낮은 significance의 byte를 가장 낮은 주소에 둔다. big-endian은 가장 높은 significance의 byte를 가장 낮은 주소에 둔다.

32비트 값 0x12345678을 주소 0x1000에 저장하면 다음과 같다.

| 주소 | little-endian | big-endian |
|---|---:|---:|
| 0x1000 | 0x78 | 0x12 |
| 0x1001 | 0x56 | 0x34 |
| 0x1002 | 0x34 | 0x56 |
| 0x1003 | 0x12 | 0x78 |

endianness는 register 안의 bit 번호가 거꾸로 된다는 뜻이 아니다. byte를 memory 주소에 배열하는 규칙이다. 한 byte를 읽으면 차이가 보이지 않고 여러 byte를 조립할 때 드러난다.

RISC-V base ISA는 byte-address invariant한 big-endian 또는 little-endian memory system을 정의할 수 있지만 실제 platform ABI와 구현이 어느 방식을 사용하는지 확인해야 한다. 흔한 RISC-V software platform이 little-endian이라는 관찰을 ISA의 모든 가능한 profile에 무조건 적용하지 않는다.

## 8. alignment와 misaligned access

**alignment(정렬)**은 객체나 memory access 주소가 특정 크기의 배수에 맞는 성질이다. 4바이트 word가 주소 0x1000에 있으면 4바이트 정렬이고 0x1002라면 정렬되지 않았다.

정렬된 access는 한 cache line, bus transaction, page 안에서 처리될 가능성이 높다. misaligned access는 두 영역을 걸쳐 여러 access와 조립이 필요할 수 있다. ISA와 execution environment에 따라 hardware가 처리하거나 exception을 내거나 software handler가 흉내 낼 수 있다. “RISC-V이면 misaligned load가 언제나 성공한다” 또는 “항상 trap이다”라고 단정하면 안 된다. platform과 access 종류의 규칙을 확인한다.

특히 주소 0x0fff에서 4바이트를 읽으면 0x1000 page 경계를 넘는다. 첫 page는 read 가능하고 둘째는 금지라면 일부 byte를 읽었다고 전체 load가 정상 retire하는 것이 아니다. ISA와 exception model이 프로그램에 보일 원자성과 fault 상태를 정한다.

## 9. PC, branch, jump

순차 실행에서 32비트 instruction 뒤 후보 PC는 현재 PC+4다. branch는 조건이 참이면 PC-relative offset을 더한 target을 고르고 거짓이면 순차 주소를 고른다.

교육용으로 PC=0x2000의 BEQ x5,x6,+16을 보자.

- x5=9, x6=9이면 조건이 참 → target=0x2010
- x5=9, x6=8이면 거짓 → next=0x2004
- +16은 현재 instruction 주소 기준이라는 ISA 규칙을 사용한다
- pipeline이 이미 순차 경로를 fetch했더라도 retire 결과는 올바른 경로와 일치해야 한다

**jump**는 조건 없이 PC를 target으로 바꾸고 함수 호출에서는 return address도 register에 남길 수 있다. RISC-V JAL은 현재 PC+4를 rd에 기록하고 PC-relative target으로 이동한다. rd=x1이면 ABI에서 흔히 return address 역할을 하지만 ISA는 x1을 “함수 전용”으로 강제하지 않는다.

exception이나 interrupt가 발생하면 privilege architecture가 정한 trap vector로 PC를 바꾸고 원인과 이전 PC에 관한 상태를 기록한다. 단순히 PC+4를 적용하면 안 된다.

## 10. 산술 overflow와 언어의 반례

RISC-V base integer ADD는 XLEN 폭의 아래 bit를 결과로 남긴다. RV32에서 0x7fffffff+1은 0x80000000이다. ISA는 integer overflow exception을 자동으로 발생시키지 않는다. software가 필요한 조건을 검사할 수 있다.

하지만 C의 signed integer overflow는 언어 수준에서 undefined behavior다. “RISC-V ADD가 wrap하므로 C signed int도 항상 wrap한다”는 추론은 틀리다. compiler는 undefined behavior가 발생하지 않는다고 가정해 최적화할 수 있다. unsigned C 연산은 폭을 기준으로 modulo arithmetic이 정의되어 있다.

또 다른 반례는 register 역할이다. assembly에서 x10에 값을 넣을 수 있다고 해서 C 함수 인자를 아무 register에 넣어 호출해도 되는 것이 아니다. ISA는 x10을 일반 register로 정의하지만 RISC-V psABI calling convention은 첫 integer 인자와 반환값에 a0, 즉 x10을 사용한다. 서로 다른 목적 파일이 협력하려면 ISA뿐 아니라 ABI를 지켜야 한다.

## 11. compiler가 instruction을 고르는 과정

C의 <code>return *p + bias;</code>를 RV64 대상으로 생각하자. p와 bias가 psABI에 따라 a0(x10), a1(x11)에 들어온다면 compiler는 개념적으로 다음을 선택할 수 있다.

~~~text
lw   a0, 0(a0)
addw a0, a0, a1
ret
~~~

실제 결과는 최적화 수준, 자료형, ABI, extension에 따라 달라진다. ADD와 ADDW도 다르다. RV64 ADD는 64비트 전체를 더하고 ADDW는 낮은 32비트를 더한 뒤 32비트 결과를 64비트로 sign extension한다. C int가 보통 32비트인 ABI에서는 이런 구분이 중요하다.

compiler가 source 변수 하나를 항상 register 하나에 고정하지 않는다. 값이 상수로 접히거나 사라지고, register가 부족하면 stack에 spill되며, debug build와 optimized build의 instruction이 다를 수 있다. source 줄과 machine instruction 사이에는 일대일 대응이 없다.


## 12. branch immediate를 실제로 조립하는 이유

RISC-V B-type branch의 immediate는 instruction 안에서 한 덩어리로 놓이지 않는다. register field 위치를 다른 형식과 공유하고, branch target이 적어도 2바이트 단위로 정렬된다는 성질을 이용하기 위해 immediate bit가 여러 위치에 나뉜다.

개념적으로 B-type offset bit는 다음처럼 조립한다.

~~~text
imm[12] | imm[10:5] | rs2 | rs1 | funct3 | imm[4:1] | imm[11] | opcode
~~~

가장 낮은 imm[0]은 instruction에 저장하지 않고 0으로 간주한다. 따라서 표현한 값은 2바이트 배수다. field를 이어 쓴 모양 그대로 unsigned 숫자로 읽으면 target을 잘못 계산한다. 흩어진 bit를 원래 위치로 모으고 imm[12]를 기준으로 sign extension한 뒤 현재 PC에 더해야 한다.

교육용으로 PC=0x1000이고 조립된 13비트 offset이 +24라면 taken target은 0x1018이다. 조건이 거짓이면 32비트 instruction의 순차 주소 0x1004다. offset=-16이면 13비트 2의 보수 pattern을 sign extension해 target 0x0ff0을 얻는다. 현재 PC가 기준이며 “다음 PC에 offset을 더한다”라고 잘못 계산하면 4바이트 차이가 난다.

이 분산 field는 compiler와 assembler가 처리하므로 일반 C programmer가 매번 손으로 조립할 필요는 없다. 그러나 disassembler, JIT compiler, binary instrumentation, linker relocation을 연구하려면 bit 위치와 sign extension을 정확히 알아야 한다.

## 13. 불법 instruction과 선택 extension

decoder가 모든 32비트 pattern을 유효 명령으로 받아들이는 것은 아니다. 구현하지 않은 extension의 opcode나 예약 encoding을 실행하면 illegal-instruction exception이 발생할 수 있다. binary가 실행될 CPU의 ISA string과 필요한 extension을 맞춰야 한다.

예를 들어 compiler가 M extension의 MUL을 생성했는데 target이 RV64I만 구현했다면 bit pattern이 memory에 잘 놓여 있어도 정상 곱셈을 기대할 수 없다. operating system이 일부 instruction을 emulate할 수 있는 환경도 있지만 성능과 지원 여부는 platform 계약이다.

ISA version과 extension 목록은 build artifact에 기록하고 실행 환경에서 확인하는 편이 좋다. “RISC-V CPU”라는 이름만으로 V, A, floating-point, compressed instruction이 모두 있다고 가정하면 portability가 깨진다.

## 14. instruction fetch의 byte와 execute의 word

little-endian system에서 32비트 instruction word 0x007302b3는 memory에 b3 02 73 00 순서로 있다. fetch unit은 PC가 가리키는 byte들을 가져와 ISA가 정한 instruction word로 조립한 뒤 field를 해독한다. debugger의 memory dump와 disassembler의 word 표기가 반대로 보이는 이유다.

PC가 page 끝 0x0ffe이고 32비트 instruction이 시작되면 instruction byte가 다음 page까지 걸칠 수 있다. compressed extension과 instruction-address alignment 규칙, 두 page의 execute permission과 mapping이 모두 관련된다. 단순히 첫 두 byte가 cache에 있다는 사실만으로 전체 instruction fetch가 성공했다고 결론 내릴 수 없다.


## 15. 문제와 전체 풀이

### 문제 1. 교육 ISA encoding

16비트 교육 ISA에서 ADD r5,r2,r7을 encoding하라. opcode=0001이고 각 register field는 4비트다.

**풀이:** opcode 0001, rd=0101, rs1=0010, rs2=0111을 이어 0001 0101 0010 0111₂다. 16진수로 0x1527이다. 이 값은 교육 ISA이며 RISC-V encoding이 아니다.

### 문제 2. 실제 RISC-V field

0x007302b3가 ADD x5,x6,x7인지 확인하라.

**풀이:** bits 6..0은 0x33으로 register-register opcode다. rd=(word>>7)&0x1f=5, funct3=0, rs1=6, rs2=7, funct7=0이다. opcode, funct3, funct7 조합이 ADD이므로 ADD x5,x6,x7이다. little-endian memory byte는 b3 02 73 00이다.

### 문제 3. sign extension

RV64에서 12비트 immediate 0xff0을 해석하고 x6=100인 ADDI 결과를 구하라.

**풀이:** 12비트 최상위 bit가 1이므로 signed 값은 4080-4096=-16이다. 64비트로 sign extension하면 0xfffffffffffffff0이다. 100+(-16)=84이므로 목적 register 값은 84다.

### 문제 4. byte 순서와 주소

little-endian memory의 0x1000부터 byte가 78 56 34 12일 때 32비트 load 값은 무엇인가?

**풀이:** 가장 낮은 주소의 0x78이 least-significant byte다. 조립하면 0x12345678이다. big-endian으로 같은 byte 배열을 해석하면 0x78563412가 된다. byte 자체가 바뀐 것이 아니라 조립 규칙이 다르다.

### 문제 5. ISA와 ABI 반례

ISA가 x1부터 x31을 일반 register로 계산에 쓸 수 있게 한다. 그렇다면 함수가 callee-saved register를 저장하지 않고 바꿔도 항상 올바른가?

**풀이:** 아니다. ISA 수준에서 register 쓰기는 합법이어도 ABI가 그 register의 값을 callee가 보존하라고 정했다면 호출 규약 위반이다. caller는 값이 유지된다고 가정해 코드를 생성한다. 함수 내부 계산만 맞아 보여도 return 뒤 caller 상태를 망가뜨린다. ISA 적합성과 binary interface 적합성은 다른 조건이다.

## 16. 공식 자료와 경계

현재 ratified RISC-V 사양 목록에서 어떤 base와 extension이 ratified인지 확인하고, 실제 platform이 채택한 profile과 psABI를 따로 확인한다. snapshot 문서는 개념을 찾아보는 데 유용하지만 제품 계약은 해당 제품이 명시한 ISA version과 extension을 기준으로 해야 한다.

- [RISC-V Ratified Specifications](https://docs.riscv.org/)
- [RISC-V Unprivileged ISA Manual](https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/)
- [RISC-V ELF psABI](https://github.com/riscv-non-isa/riscv-elf-psabi-doc)

[← 이전](01-digital-logic-and-clock.md) · [목차](README.md) · [다음 →](03-functions-abi-and-program-loading.md)
