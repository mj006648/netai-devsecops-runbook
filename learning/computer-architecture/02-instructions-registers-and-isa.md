# 02. 명령어·레지스터·ISA

[← 이전](01-digital-logic-and-clock.md) · [목차](README.md) · [다음 →](03-functions-abi-and-program-loading.md)

**명령어(instruction)**는 CPU가 해석할 수 있게 비트로 표현한 작업이다. **연산 코드(opcode)**는 작업 종류, **피연산자(operand)**는 작업에 필요한 값이나 위치다. **PC(Program Counter, 프로그램 카운터)**는 명령 주소를 가리키는 상태다. 아래의 작은 ISA는 인코딩을 배우기 위한 별도 교육 모형이다.

## 명령어 비트를 읽는 법

ISA는 opcode, operand 위치, 레지스터 수, 주소 계산, 예외를 정의하는 계약이다.
opcode는 “더하라”처럼 연산 종류를 나타내고 operand는 사용할 값이나 그 위치를 나타낸다.
레지스터 operand는 작은 번호로 인코딩되며 PC는 fetch할 명령 주소를 가진다.

아래는 실제 제품 인코딩이 아닌 이 장 전용 16비트 교육 ISA다.
상위 4비트 opcode, 다음 4비트 목적, 다음 두 4비트는 원본 레지스터다.

```text
15..12 opcode | 11..8 rd | 7..4 rs1 | 3..0 rs2
ADD opcode=0001
```

`ADD r3,r1,r2`는 `0001 0011 0001 0010₂`, 즉 `0x1312`다.
decoder는 비트를 잘라 opcode=1, rd=3, rs1=1, rs2=2를 얻는다.
`r1=9,r2=6`이면 ALU는 15를 만들고 정상 완료 뒤 r3에 기록한다.
이 배치는 RISC-V 인코딩이 아니다. 실제 ISA를 설명할 때는 반드시 그 명세의 형식을 사용해야 한다.

load-store ISA에서는 산술 명령이 보통 메모리 값을 직접 operand로 쓰지 않는다.
`LOAD r1,4(r2)`가 주소 `r2+4`에서 값을 레지스터로 옮기고, ADD가 레지스터 값을 계산하며, STORE가 결과를 메모리로 되돌린다.
`r2=0x1000`이면 유효주소는 `0x1004`다.

고정 16비트 명령이면 순차 PC는 2바이트 증가한다.
PC `0x2000`에서 위 명령을 fetch한 뒤 분기가 없다면 다음 PC 후보는 `0x2002`다.
실제 ISA는 16·32비트 또는 가변 길이를 쓸 수 있어 증가량을 ISA 규칙으로 판단해야 한다.

```mermaid
flowchart LR
  P[PC] --> F[명령 비트 fetch]
  F --> D[opcode·operand 분리]
  D --> R[레지스터 읽기]
  R --> E[ALU 또는 주소 계산]
  E --> W[목적 상태 기록]
```

### 문제 1
교육 ISA에서 `ADD r5,r2,r7`의 16비트는?

**풀이:** opcode 0001, rd 0101, rs1 0010, rs2 0111을 이어 `0001 0101 0010 0111₂=0x1527`이다.

### 문제 2
`LOAD r4,12(r3)`, r3=`0x8000`의 유효주소는?

**풀이:** 12는 `0xC`이므로 `0x8000+0xC=0x800C`다.
번역과 권한 검사가 성공한 뒤 그 주소의 값이 r4에 들어간다.

### 문제 3
명령 폭이 2바이트이고 PC가 `0x10fe`라면 순차 다음 PC는?

**풀이:** `0x10fe+2=0x1100`이다.
분기·예외가 있으면 선택되는 다음 PC는 달라질 수 있다.

## 공식 자료

[RISC-V Unprivileged ISA](https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/)

[← 이전](01-digital-logic-and-clock.md) · [목차](README.md) · [다음 →](03-functions-abi-and-program-loading.md)
