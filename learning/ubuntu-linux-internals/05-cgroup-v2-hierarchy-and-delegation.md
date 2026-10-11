# 05. cgroup v2 hierarchy와 delegation

[이 책 목차](README.md)

[← 이전: memory와 PSI](04-memory-pages-reclaim-and-psi.md) · [다음: CPU quota·weight·cpuset →](06-cpu-quota-weight-and-cpuset.md)

## cgroup이 필요한 이유

cgroup은 process들을 계층으로 묶어 resource를 측정하고 제어한다.
namespace가 “무엇이 보이는가”를 나눈다면 cgroup은 “얼마나 쓰고 어디에 귀속되는가”를 다룬다.
cgroup v2는 controller들을 하나의 통합 hierarchy에 둔다.

![cgroup v2 tree](assets/cgroup-tree.svg)

```mermaid
flowchart TD
    R[/sys/fs/cgroup] --> S[system.slice]
    R --> U[user.slice]
    S --> A[app-a.service]
    S --> B[app-b.service]
    U --> X[user-1000.slice]
```

## 실제 file

각 cgroup directory에는 interface file이 보인다.

| file | 의미 |
|---|---|
| `cgroup.procs` | 소속 process ID |
| `cgroup.threads` | thread ID view |
| `cgroup.controllers` | child에 사용할 수 있는 controller |
| `cgroup.subtree_control` | child subtree에 활성화한 controller |
| `cgroup.events` | populated/frozen 같은 상태 |
| `cgroup.type` | domain/threaded 등 type |

controller별로 `cpu.max`, `cpu.weight`, `memory.current` 같은 file이 추가된다.
file에 쓰는 일은 runtime kernel 상태를 바꾸므로 이 교재는 수행하지 않는다.

## limit file은 같은 강도가 아니다

`memory.high`는 넘을 때 reclaim과 throttling 압력을 주는 보호선이다.
그 자체가 즉시 cgroup OOM을 일으키는 hard limit은 아니다.
`memory.max`는 reclaim으로 줄일 수 없으면 cgroup OOM으로 이어질 수 있는 hard limit이다.

| file | 입력 의미 | 결과 경계 |
|---|---|---|
| `memory.high` | byte 상한선 | reclaim/throttle, 사용량이 잠시 넘을 수 있음 |
| `memory.max` | hard byte limit | 회수 실패 시 cgroup OOM 가능 |
| `pids.max` | task 수 limit | 새 task 생성 실패 가능 |
| `io.max` | device별 BPS/IOPS limit | 해당 I/O를 지연시켜 rate 제한 |

`io.max`는 `MAJ:MIN` device와 read/write BPS/IOPS 조건으로 표현한다.
filesystem writeback이 해당 cgroup과 device에 올바르게 귀속되는지는 filesystem 지원 조건을 확인한다.
buffered write syscall의 빠른 return만 보고 I/O limit이 적용되지 않았다고 결론 내리지 않는다.
뒤의 writeback 경로에서 delay가 나타날 수 있다.

## controller 활성화 흐름

부모가 `cgroup.controllers`에 controller를 갖고 있어야 한다.
부모의 `cgroup.subtree_control`에 활성화해야 child가 interface를 얻는다.

```text
root controllers: cpu memory io pids
root subtree_control: +cpu +memory
child에 cpu.*와 memory.* interface 제공
```

위 `+` 표기는 write operation 문법 설명일 뿐 실행 지시가 아니다.
실제 systemd 관리 hierarchy에 임의 write하지 않는다.

## no internal process rule

domain controller를 child에 배포하는 cgroup에는 일반 process를 함께 두지 않는 규칙이 핵심이다.
resource를 소비하는 process는 leaf child로 옮긴다.

```text
잘못된 개념:
parent에 process P
parent가 +cpu를 child에 배포

권장 구조:
parent: controller 배포만
├─ workload-a: process A
└─ workload-b: process B
```

root cgroup에는 예외적 역할이 있다.
정확한 오류 조건은 kernel cgroup v2 문서를 따른다.

## domain과 threaded

domain cgroup은 일반 process 자원 domain이다.
threaded subtree는 한 process의 thread들을 더 세분화해 threaded controller로 다루는 구조다.

`cgroup.type`은 `domain`, `domain threaded`, `threaded`, invalid 상태 등을 표현할 수 있다.
모든 controller가 threaded mode를 지원하는 것은 아니다.
처음에는 service/process 단위 domain hierarchy를 우선 이해한다.

## delegation

delegation은 subtree 관리 권한을 제한된 주체에게 넘기는 일이다.
directory write permission만 넓게 주는 것으로 끝나지 않는다.

위임자는 다음 경계를 지켜야 한다.

1. delegatee가 자기 subtree 밖 task를 이동하지 못한다.
2. ancestor resource policy를 바꾸지 못한다.
3. 허용 controller와 file만 관리한다.
4. process 이동 권한과 ownership을 올바르게 제한한다.

systemd는 unit와 slice를 통해 hierarchy를 관리한다.
직접 filesystem을 수정하면 manager 상태와 충돌할 수 있다.

## 작은 위임 사례

관리자가 `tenant.slice` 아래 `tenant-a.scope`를 위임했다고 하자.

| 주체 | 허용 범위 | 금지 범위 |
|---|---|---|
| host manager | 전체 tree·ancestor policy | 없음 |
| tenant A manager | 자기 child 생성·자기 task 배치 | sibling/parent 변경 |
| workload | 할당된 leaf에서 실행 | 임의 ancestor 이동 |

tenant A가 child `batch`와 `interactive`를 만들 수 있어도 host의 `system.slice`를 변경할 수 없어야 한다.

## process 이동

PID를 `cgroup.procs`에 쓰면 process 소속을 바꾸는 operation이다.
permission, namespace, delegation 경계를 통과해야 한다.
multi-thread process와 threaded cgroup에서는 이동 단위 규칙이 더 복잡하다.

이 문서는 write command를 제공하지 않는다.
read-only 관측만 예로 든다.

```bash
findmnt -t cgroup2
cat /sys/fs/cgroup/cgroup.controllers
cat /sys/fs/cgroup/cgroup.subtree_control
cat /sys/fs/cgroup/cgroup.type
```

실행하지 않은 예이며 mount path는 환경에 따라 다를 수 있다.

## systemd 연결

slice unit은 cgroup tree의 내부 grouping과 연결된다.
service/scope unit은 process를 leaf cgroup에 둔다.
`Delegate=` 같은 systemd 설정은 제한된 subtree 관리를 맡기는 데 사용된다.
정확한 허용 file과 controller는 systemd version과 정책을 확인한다.

## 반례

directory가 보인다고 write 권한이 있는 것은 아니다.
controller가 `cgroup.controllers`에 보여도 `subtree_control`에 활성화되지 않았을 수 있다.
cgroup namespace로 path가 짧게 보여도 host ancestor limit은 계속 적용된다.
child limit 합이 parent capacity를 물리적으로 늘리지 않는다.

## 문제

## controller와 subtree가 만들어지는 순서

부모 cgroup의 controller는 그 부모가 상위에서 받은 resource control 능력이다.
부모가 subtree_control에 controller를 활성화하면 child들에 해당 interface가 나타난다.
domain 부모는 자원 배포자 역할을 하므로 일반 process는 leaf로 내려보낸다.
delegation은 특정 subtree directory와 허용 interface의 관리권을 다른 manager에게 준다.
delegatee는 자기 child를 만들 수 있지만 ancestor와 sibling policy를 바꾸면 안 된다.
threaded subtree는 일부 controller에서 process 내부 thread 단위 조직이 필요할 때 쓰며 일반 domain과 규칙이 다르다.
단순 directory ownership만으로 이 모든 경계가 안전해지지 않는다.

1. `cgroup.controllers`와 `cgroup.subtree_control` 차이는?
2. no internal process rule이 필요한 구조적 이유는?
3. delegation이 단순 chmod보다 복잡한 이유는?

## 해설

1. 전자는 사용 가능 controller, 후자는 child subtree에 실제 활성화한 controller다.
2. domain resource 분배의 부모와 소비 leaf 역할을 분리해 계층 의미를 유지한다.
3. task 이동, ancestor policy, controller file, subtree 경계를 함께 제한해야 하기 때문이다.

## 공식 자료

- [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [systemd resource control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- [systemd delegation](https://systemd.io/CGROUP_DELEGATION/)

[← 이전: memory와 PSI](04-memory-pages-reclaim-and-psi.md) · [다음: CPU quota·weight·cpuset →](06-cpu-quota-weight-and-cpuset.md)
