# 03. 함수 호출·ABI·프로그램 적재

[← 이전](02-instructions-registers-and-isa.md) · [목차](README.md) · [다음 →](04-pipelines-hazards-and-forwarding.md)

**함수(function)**는 이름을 붙여 호출하는 코드 묶음이다. **호출자(caller)**가 호출하면 **피호출자(callee)**가 실행하고 돌아온다. **ABI(Application Binary Interface, 바이너리 인터페이스 규약)**는 인자를 어디에 놓고 어떤 레지스터를 보존할지 정한다. **스택 프레임(stack frame)**은 한 호출의 복귀 정보와 지역 상태를 놓는 메모리 구역이다.

## 함수 호출과 실행 파일 적재를 주소로 추적하기

caller는 함수를 부르는 쪽이고 callee는 불린 함수다.
calling convention은 인자 레지스터, 반환값 위치, 누가 어떤 레지스터를 보존할지 정한다.
이 규칙이 있어 서로 다른 파일과 컴파일러가 만든 함수도 연결된다.

교육용 ABI에서 첫 인자는 r1, 반환값은 r0, return address는 ra라고 하자.
caller가 `f(7)`을 부르면 r1=7, ra=`0x401008`을 준비하고 f의 주소로 PC를 바꾼다.
callee는 자신이 보존해야 하는 레지스터를 스택에 저장하고 계산한 결과를 r0에 둔 뒤 ra로 돌아간다.

스택이 낮은 주소로 자라고 호출 전 SP=`0x8000`, 프레임이 32바이트면 새 SP=`0x7fe0`이다.

| 주소 | 내용 |
|---|---|
| `0x7ff8` | 저장한 return address |
| `0x7ff0` | 저장해야 할 레지스터 |
| `0x7fe8` | 지역 변수 |
| `0x7fe0` | 정렬·임시 공간, 현재 SP |

return 전에 저장값을 복구하고 SP를 `0x8000`으로 되돌린다.
caller-saved 레지스터는 caller가 필요하면 호출 전에 저장하고, callee-saved는 callee가 바꿀 때 저장한다.
이 구분을 어기면 함수는 혼자서는 맞아 보여도 호출자를 망가뜨린다.

```mermaid
flowchart LR
  S[소스] --> C[컴파일러: 목적 파일]
  C --> K[링커: 심볼·재배치 해결]
  K --> E[실행 파일]
  E --> L[로더: 가상주소 매핑]
  L --> P[초기 PC·SP 설정]
  P --> U[사용자 코드 실행]
```

컴파일러는 소스마다 기계어와 미해결 심볼을 담은 목적 파일을 만든다.
링커는 `main`의 `f` 참조를 f의 최종 위치와 연결하고 relocation을 적용한다.
로더는 실행 파일의 코드 구간을 execute 가능한 가상주소, 데이터 구간을 적절한 read/write 주소에 매핑한다.
필요한 공유 라이브러리와 스택을 준비하고 초기 PC와 SP를 정한 뒤 사용자 코드로 제어를 넘긴다.

예를 들어 코드가 `0x400000`, 데이터가 `0x600000`, 스택 상단이 `0x7fff0000`에 매핑될 수 있다.
이는 교육 예이며 ASLR, 파일 형식, OS 정책에 따라 실제 주소는 달라진다.
파일 offset과 가상주소와 물리주소는 같은 숫자일 필요가 없다.

### 문제 1
SP=`0x9000`에서 48바이트 프레임을 잡으면?

**풀이:** 48=`0x30`이므로 새 SP는 `0x8fd0`이다.
반환 전 저장값을 복구한 뒤 원래 SP로 되돌려야 한다.

### 문제 2
return address가 `0x401020`이면 return은 무엇을 하는가?

**풀이:** ABI가 요구한 상태를 복구한 뒤 PC를 `0x401020`으로 바꾼다.
그 주소는 caller에서 호출 다음에 실행할 명령 위치다.

### 문제 3
링커와 로더의 차이는?

**풀이:** 링커는 목적 파일의 심볼과 재배치를 해결해 실행 이미지를 만든다.
로더는 실행 시 그 이미지의 구간을 프로세스 가상주소에 매핑하고 초기 PC·SP를 준비한다.

## 공식 자료

[RISC-V psABI](https://github.com/riscv-non-isa/riscv-elf-psabi-doc)

[← 이전](02-instructions-registers-and-isa.md) · [목차](README.md) · [다음 →](04-pipelines-hazards-and-forwarding.md)
