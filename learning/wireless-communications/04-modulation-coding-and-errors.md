# 04. 변조·부호화·오류

[이 책 목차](README.md)

[← 이전](03-sampling-iq-and-radio-chain.md) · [다음 →](05-channel-noise-and-capacity.md)

## 변조와 symbol

변조는 bit를 channel에 보낼 파형 선택으로 바꾸는 규칙이다.
symbol은 한 번의 선택이다.
constellation은 가능한 I/Q 점의 모음이다.

| 방식 | 점 | coded bit/symbol |
|---|---:|---:|
| BPSK | 2 | 1 |
| QPSK | 4 | 2 |
| 16-QAM | 16 | 4 |
| 64-QAM | 64 | 6 |

점이 많으면 같은 symbol rate에서 더 많은 bit를 보낸다.
점 간격이 가까워져 noise에 더 민감할 수 있다.

## QPSK 예

```text
00 → (+1,+1)
01 → (-1,+1)
11 → (-1,-1)
10 → (+1,-1)
```

입력 `00 10 11`은 세 symbol이 된다.
두 번째 수신점 `(0.8,-0.7)`은 `(1,-1)`과 가까워 `10`으로 판단할 수 있다.
경계 `(0.02,0.01)`은 작은 noise에도 판단이 바뀐다.

```mermaid
flowchart LR
    B[정보 bit] --> E[FEC encoder]
    E --> M[mapper]
    M --> C[channel]
    C --> L[LLR detector]
    L --> D[FEC decoder]
    D --> CRC[CRC]
    CRC --> O[accept 또는 retransmit]
```

## FEC와 code rate

FEC는 구조화된 여분 bit로 receiver가 오류 정정을 시도하게 한다.
code rate는 `정보 bit/coded bit`다.

1,000bit를 rate 1/2로 부호화하면 2,000coded bit다.
900bit를 rate 3/4로 부호화하면 1,200coded bit다.
낮은 rate는 여분이 많고 airtime도 늘어난다.

## 반복 부호 예

bit 1을 `111`로 보낸다.
관측이 `101`이면 다수결로 1을 복구한다.
`100`이면 0으로 잘못 복구한다.
실제 Wi‑Fi 부호가 아니라 정정 원리 모형이다.

## hard와 soft

hard decision은 0/1 하나만 낸다.
soft decision은 어느 쪽을 얼마나 믿는지 준다.
LLR은 두 bit 가설의 가능성 비율을 로그로 나타낸다.

```text
LLR +8: convention상 0을 강하게 믿음
LLR +0.2: 0 쪽이지만 약함
LLR -6: 1을 강하게 믿음
```

부호 convention은 구현에 따라 반대일 수 있다.

## soft 결합

반복 관측 LLR이 `-4,-3,+1`이면 합은 -6이다.
하나가 반대여도 전체는 1 쪽 증거가 강하다.
decoder는 code 구조와 여러 soft evidence를 함께 쓴다.

## CRC

CRC는 주로 오류 검출용이다.
FEC는 오류 정정 시도용이다.
FEC 복호 뒤 CRC 실패면 frame을 폐기하거나 재전송한다.
CRC 통과도 오류 확률 0은 아니다.

## ARQ와 HARQ

ARQ는 실패 frame을 재전송한다.
HARQ는 재전송 관측과 FEC 정보를 결합한다.

| 순서 | 송신 | 수신 |
|---:|---|---|
| 1 | coded block | decode+CRC |
| 2 | ACK 대기 | 실패면 NACK |
| 3 | 재전송/추가 parity | 이전 soft 정보와 결합 |
| 4 | ACK | 상위 전달 |

incremental redundancy는 같은 bit 반복이 아니라 추가 parity를 보낼 수 있다.

## 효율 계산

payload 1,000, header+CRC 200, rate 1/2:

```text
정보 block = 1200bit
coded = 2400bit
16-QAM = 4bit/symbol
필요 symbol = 600
payload/coded 효율 = 41.7%
```

재전송 한 번이면 같은 payload의 air resource가 더 든다.

## 상태표

| 주체 | 입력 | 상태 | 결과 |
|---|---|---|---|
| encoder | information bit | code block | coded bit |
| mapper | coded bit | constellation | I/Q |
| detector | I/Q·channel | 거리·noise | LLR |
| decoder | LLR | code constraint | bit 후보 |
| CRC | frame | remainder | pass/fail |
| HARQ | fail+buffer | combining | retry 결과 |

## link adaptation

receiver feedback와 error history로 MCS를 고른다.
높은 MCS는 고차 modulation/높은 code rate를 사용할 수 있다.
channel이 바뀌면 과거 측정이 오래될 수 있다.
보수적 MCS는 robust하지만 airtime이 늘어난다.

## 반례

64-QAM이 QPSK보다 항상 빠르지 않다.
재전송이 많으면 goodput이 낮아진다.
강한 FEC도 deep fade의 모든 오류를 고치지 못한다.
LLR scale이 틀리면 decoder가 잘못된 확신을 받을 수 있다.

## 문제

## LLR·FEC·CRC·HARQ를 한 frame에서 구분하기

detector는 각 coded bit가 0/1 중 어느 쪽인지와 확신도를 LLR로 만든다.
FEC decoder는 여러 LLR을 code 제약과 함께 처리해 원래 information bit 후보를 복원한다.
CRC는 복원된 frame 전체가 송신자가 붙인 검사 관계를 만족하는지 확인한다.
CRC 실패면 receiver는 그 frame을 상위에 전달하지 않는다.
HARQ controller는 실패한 전송의 soft buffer를 보관하고 송신자에게 재전송을 요구한다.
다음 redundancy가 오면 이전 LLR과 결합해 FEC decoder를 다시 실행한다.
LLR은 입력 증거, FEC는 정정 알고리즘, CRC는 최종 검출, HARQ는 시간에 걸친 재전송 절차다.

1. 64-QAM 100symbol의 coded bit는?
2. 1,200coded bit를 rate 1/2로 썼다면 information bit는?
3. CRC와 FEC 차이는?

## 해설

1. `100×6=600bit`다.
2. `1,200×1/2=600bit`다.
3. CRC는 주로 검출, FEC는 여분 구조로 정정을 시도한다.

## 공식 출처

- [MIT 6.451 hard/soft decoding](https://ocw.mit.edu/courses/6-451-principles-of-digital-communication-ii-spring-2005/download/)
- [MIT 6.02 coding readings](https://ocw.mit.edu/courses/6-02-introduction-to-eecs-ii-digital-communication-systems-fall-2012/pages/readings/)

[← 이전](03-sampling-iq-and-radio-chain.md) · [다음 →](05-channel-noise-and-capacity.md)
