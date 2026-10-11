# 11. io_uring ordering, error와 fsync

[이 책 목차](README.md) · [이전: io_uring registration, polling과 feature 탐지](10-io-uring-registration-polling-and-features.md) · [다음: Network I/O와 kernel 관찰](12-network-io-and-kernel-observation.md)

io_uring은 여러 I/O 요청을 커널에 미리 맡겨 겹쳐 진행할 수 있게 한다. 성능은 이 동시성에서 나오지만, 제출한 순서와 끝난 순서를 혼동하면 데이터 순서와 버퍼 수명이 깨진다. 이 장의 요청·수치·완료 순서는 실행 결과가 아닌 교육용 가상 모형이다. 파일을 만들거나 수정하거나 동기화 호출을 실행하지 않았다.

## SQE와 CQE는 요청과 결과를 나누는 실제 객체다

**io_uring**은 사용자 공간과 Linux 커널이 submission queue와 completion queue를 공유해 비동기 I/O를 교환하는 인터페이스다. 애플리케이션이 준비한 요청 항목이 **SQE(Submission Queue Entry, 제출 큐 항목)**다. SQE에는 read·write 같은 opcode, fd, buffer 주소, 길이, offset, flags와 요청 식별값 user_data가 들어간다. SQE는 사용자 공간 ring 메모리에 있다가 submit될 때 커널이 처리할 요청이 된다. 요청이 terminal 상태가 되기 전까지 그 요청이 참조하는 객체를 살아 있게 해야 한다.

**CQE(Completion Queue Entry, 완료 큐 항목)**는 커널이 끝난 요청의 결과를 사용자 공간에 알리는 항목이다. user_data, 결과값 res와 flags가 핵심이다. res가 음수면 -errno 오류, 0이나 양수면 opcode별 성공 결과다. CQE를 읽었다는 것은 그 요청에 대한 커널 결과를 받았다는 뜻이며 업무 transaction 전체가 끝났다는 뜻은 아니다.

요청을 커널이 볼 수 있게 넘기는 일을 **제출(submit)**, 요청이 성공·오류·취소 중 하나의 terminal 결과에 도달해 CQE가 생기는 일을 **완료(complete)**라고 한다. A, B, C SQE를 그 순서로 submit해도 서로 독립이면 C, A, B 순서로 complete할 수 있다.

~~~mermaid
sequenceDiagram
    participant U as userspace
    participant R as io_uring
    participant D as device/filesystem
    U->>R: SQE A read block 1
    U->>R: SQE B read block 2
    U->>R: SQE C write log
    R->>D: A B C 병행 issue
    D-->>R: B complete
    D-->>R: C complete
    D-->>R: A complete
    R-->>U: CQE B C A
~~~

### 문제 1: 세 요청의 가능한 completion 순서

서로 독립인 A, B, C를 A→B→C 순서로 제출했다. 세 요청이 모두 성공할 때 가능한 완료 순서를 모두 쓰고, 애플리케이션이 어떻게 원래 요청을 찾는지 설명하라.

세 항목의 순열은 \(3!=6\)개이므로 A-B-C, A-C-B, B-A-C, B-C-A, C-A-B, C-B-A가 모두 가능하다. CQ 배열 위치를 작업 번호로 쓰지 말고 SQE마다 고유 user_data를 넣어 CQE와 상태 객체를 연결한다. 조건을 바꾸어 B가 A의 출력 buffer를 입력으로 써야 한다면 독립 요청이 아니므로 A 결과를 확인한 뒤 B를 준비하거나 지원되는 dependency를 표현해야 한다.

## ordering은 시작·완료·공개 순서를 따로 정한다

**순서 보장(ordering)**은 어느 연산이 다른 연산보다 먼저 issue되거나 완료되거나 외부에 공개돼야 하는지 정하는 규칙이다. 세 순서는 다르다. SQ에 먼저 넣은 submission order, 실제 CQE가 온 completion order, 애플리케이션이 record를 committed로 보이는 publish order를 분리한다.

**dependency(의존성)**는 뒤 요청의 올바른 실행이 앞 요청의 성공 결과에 의존하는 관계다. read한 byte를 CPU에서 변환해 write한다면 다음 흐름이 필요하다.

~~~text
READ submit
→ READ CQE의 res 확인
→ error·EOF·short read 처리
→ CPU가 결과 변환
→ 완성된 write buffer로 WRITE submit
→ WRITE CQE 확인
→ 내구성이 필요하면 FSYNC submit
~~~

kernel link는 userspace 변환을 자동 삽입하지 않는다. read가 채우기 전의 buffer를 write SQE에 미리 연결하면 오래된 byte를 쓸 수 있다.

**IOSQE_IO_LINK(link)**는 SQE flag로 특정 요청 chain의 앞 단계가 성공한 뒤 다음 단계를 진행하게 한다. 앞 요청이 실패하면 뒤 요청은 -ECANCELED로 취소될 수 있다. 여기서 성공은 opcode의 커널 결과다. write가 요청 8192 중 4096을 반환한 **부분 I/O(partial I/O)**는 양수 결과여서 link 관점에서 다음 요청이 진행될 수 있지만 애플리케이션 record는 절반만 쓰였다.

**IOSQE_IO_HARDLINK(hardlink)**는 앞 요청 실패에도 뒤 chain을 계속 진행시키는 flag다. 여러 filename이 inode 하나를 가리키는 filesystem hard link와 다른 개념이다. cleanup처럼 앞 결과와 무관하게 실행할 단계에 쓸 수 있지만 error 처리를 대신하지 않는다.

**IOSQE_IO_DRAIN(drain)**은 같은 ring에서 앞서 제출한 요청들이 완료된 뒤 해당 요청을 issue하게 하는 장벽이다. 특정 chain의 link와 범위가 다르다. drain은 완료 순서를 정할 뿐 저장장치 cache flush나 내구성을 만들지 않는다.

### 문제 2: link와 hardlink의 세 결과

A=WRITE, B=FSYNC, C=상태 기록을 normal link로 묶었다. A가 -EIO면 B와 C에 어떤 결과가 가능한가? A-B는 hardlink이고 B-C는 normal link라면 무엇이 달라지는가?

normal chain에서는 A가 최초 -EIO로 실패하고 B와 C가 -ECANCELED가 될 수 있다. 취소 CQE는 B 자체의 장치 오류가 아니라 앞 dependency 실패의 결과일 수 있으므로 세 CQE를 모두 기록한다. A-B hardlink면 A 실패 뒤에도 B가 실행된다. B가 성공하면 C도 진행할 수 있지만 빠진 data가 fsync로 생기지는 않는다. B가 실패하면 normal B-C link 때문에 C는 취소될 수 있다. 조건을 바꾸어 C가 실패 보고라면 hardlink만으로 보고를 보장하지 말고 CQE를 읽는 userspace 상태 machine이 A 오류를 직접 기록해야 한다.

## cancel과 timeout도 별도 요청이며 race한다

**취소(cancel)**는 아직 끝나지 않은 대상 요청을 중단하도록 커널에 부탁하는 별도 operation이다. 이미 완료됐거나 취소 불가능한 실행 단계에 들어갔다면 취소가 원하는 결과를 만들지 못할 수 있다. cancel 요청의 CQE와 대상 요청의 terminal CQE를 모두 처리해야 한다.

**timeout**은 정한 시간이 지나면 완료되는 io_uring operation이다. target과 연결한 linked timeout으로 deadline을 표현할 수 있다. **deadline**은 끝나야 하는 마지막 시각이고 timeout은 이를 감시하는 장치다.

~~~mermaid
sequenceDiagram
    participant U as application
    participant R as READ
    participant T as LINK_TIMEOUT
    U->>R: read submit
    U->>T: 20ms deadline
    alt read wins
      R-->>U: res=4096
      T-->>U: -ECANCELED
    else timeout wins
      T-->>U: -ETIME
      R-->>U: -ECANCELED 또는 race 결과
    end
~~~

timeout이 먼저 보였다고 device가 즉시 멈췄거나 DMA가 buffer를 더 이상 만지지 않는다고 가정하지 않는다. **buffer lifetime(버퍼 수명)**은 메모리를 준비한 때부터 커널·device가 참조할 가능성이 끝나고 애플리케이션 소비자도 사용을 마친 때까지다. 대상 terminal CQE와 API의 notification 조건 전에 free·재사용하면 다른 요청이 같은 주소를 덮는 use-after-free가 생긴다.

### 문제 3: timeout과 read의 세 관측 순서

20 ms timeout을 read와 연결했다. 가능한 교육용 관측을 세 가지로 나누고 buffer를 언제 반환할지 설명하라.

첫째 read CQE 4096이 먼저 오고 timeout은 -ECANCELED가 될 수 있다. 둘째 timeout -ETIME 뒤 target read -ECANCELED가 올 수 있다. 셋째 경계 race에서 timeout과 read 성공이 거의 함께 관측될 수 있어 둘의 CQE로 최종 상태를 결정해야 한다. 어느 경우도 timeout CQE 하나만 보고 buffer를 pool에 돌리지 않는다. target terminal CQE와 multishot·zero-copy notification 같은 추가 수명 조건이 있으면 그것까지 기다린다. 조건을 바꾸어 buffer slice를 parser thread에 넘겼다면 kernel 수명 뒤에도 parser reference가 끝나야 재사용할 수 있다.

## error는 CQE마다 읽고 최초 원인을 보존한다

**오류(error)**는 요청 계약을 완료하지 못한 결과다. negative res는 -EIO, -ENOSPC, -ECANCELED처럼 errno를 음수로 전달한다. positive short result도 애플리케이션이 요구한 길이를 만족하지 못했다면 논리적 오류로 처리해야 한다. read의 0은 일반 파일 EOF나 TCP orderly shutdown처럼 객체별 의미가 있다.

세 요청 WRITE→FSYNC→PUBLISH에서 가능한 결과를 나누자.

| WRITE CQE | FSYNC CQE | PUBLISH | 결론 |
|---|---|---|---|
| full 8192 | 0 | 성공 | 요구 범위의 commit 후보 |
| short 4096 | 0 | 실행 금지 | 남은 4096 처리 전 불완전 |
| -ENOSPC | -ECANCELED | 실행 금지 | write가 최초 원인 |
| full 8192 | -EIO | 실행 금지 | byte 수용 뒤 durability 실패 |
| full 8192 | 0 | 자체 -EIO | 저장은 됐어도 공개 실패 |

write 때 page cache가 byte를 받아 성공했다가 실제 writeback이나 fsync에서 공간·장치 오류가 처음 보일 수 있다. 뒤 CQE만 log하고 caller에 성공을 돌려주면 실패가 사라진다.

### 문제 4: partial write 뒤 fsync 성공

8192바이트 record write가 4096을 반환했고 linked fsync CQE가 0이다. durable record인가? 상태 machine이 해야 할 계산을 써라.

아니다. res=4096은 첫 4096만 처리됐다는 positive partial result다. buffer pointer를 4096만큼 전진시키고 file offset도 4096 더하며 remaining을 \(8192-4096=4096\)으로 줄여 다시 write해야 한다. 나머지 full completion 뒤 fsync를 제출한다. 이미 먼저 실행된 fsync는 현재 존재하는 일부 byte만 동기화했을 수 있다. 조건을 바꾸어 두 번째 write가 -ENOSPC면 record 전체를 committed로 공개하지 않고 부분 record를 복구할 length·checksum protocol이 필요하다.

## fsync는 dirty 상태와 durable 계약의 경계다

프로그램 write가 성공해도 byte는 kernel page cache의 **dirty page**, 즉 파일보다 새 값이 RAM에만 반영된 page에 있을 수 있다. kernel이 이를 device로 보내는 writeback은 나중에 일어날 수 있다. **fsync**는 해당 file의 변경 data와 필요한 metadata를 저장 계층으로 보내 완료를 기다리는 system call 계약이다. io_uring의 IORING_OP_FSYNC는 이를 비동기 request로 표현한다.

**durable(내구성이 있다)**는 정의한 failure 뒤에도 data를 복구할 수 있다는 뜻이다. 어느 failure인지 반드시 붙인다. process crash, kernel panic, power loss, device loss, node loss, remote replica loss는 서로 다르다. FSYNC CQE 0은 file fsync 계약의 성공이지 parent directory, 다른 file, remote replica, backup까지 자동 보장하지 않는다.

새 file을 안전하게 이름으로 공개하는 전형적 흐름은 temporary file 생성, 전체 data write와 partial 처리, file fsync, temp→final rename, parent directory fd fsync, commit 알림이다. rename은 이름 교체의 atomicity를 제공할 수 있지만 crash 뒤 새 directory entry가 남는 내구성과 같은 말이 아니다.

~~~mermaid
flowchart TD
 C[temp file create] --> W[data full write]
 W --> FF[file fsync]
 FF --> R[rename temp to final]
 R --> DF[parent directory fsync]
 DF --> P[commit publish]
~~~

### 문제 5: 장애 지점마다 보이는 상태

위 흐름에서 전원 장애가 file fsync 전, file fsync 뒤 rename 전, rename 뒤 directory fsync 전에 각각 발생했다고 하자. 무엇을 안전하게 주장할 수 있는가?

file fsync 전에는 write CQE가 성공했어도 data가 power loss 뒤 남는다고 주장할 수 없다. file fsync 뒤 rename 전에는 temp file 내용이 durable 후보지만 final name으로 공개되지 않았다. rename 뒤 directory fsync 전에는 실행 중 final name이 보였어도 crash recovery 뒤 directory entry 지속성은 filesystem 계약에 따라 불확실할 수 있다. directory fsync까지 성공한 뒤에만 이 전형적 계약의 commit을 알린다. 실제 filesystem journal mode와 remote storage는 별도 확인 대상이다.

## device completion과 filesystem durability는 층이 다르다

NVMe command completion은 device가 command를 완료했다는 신호다. buffered write에서는 application buffer→page cache→filesystem writeback→block layer→device cache·media의 여러 단계가 있다. **flush**는 device volatile write cache 내용을 persistent media 쪽으로 내보내도록 요청하는 operation이고, **FUA(Force Unit Access)**는 특정 write가 volatile cache에만 머물지 않도록 요구하는 device 의미다. filesystem이 journal과 metadata 순서를 고려해 이 기능을 조합한다.

Direct I/O는 page cache data 경로를 줄일 수 있어도 filename rename이나 parent directory metadata를 동기화하지 않는다. 빠른 NVMe completion과 application transaction durability를 같은 사건으로 보면 안 된다.

### 문제 6: 세 request의 모든 terminal 조합에서 commit 판단

A=8192-byte WRITE, B=FSYNC, C=commit-log WRITE라고 하자. 관측이 C 성공→A full→B 성공 순이면 commit할 수 있는가? B 성공→A short→C 성공이면 어떤가? A error→C 성공→B cancel이면 어떤가?

첫 경우 CQE 도착 순서는 뒤섞였어도 dependency가 올바르게 설정되고 A full, B 0, C full이라는 모든 terminal 결과와 publish protocol을 만족하면 commit 후보가 된다. 둘째는 A short라 record가 불완전하므로 B와 C 성공이 있어도 commit할 수 없다. 셋째는 A가 최초 실패이고 B cancel은 그 결과이며 C 성공은 별도 log write 성공일 뿐 data를 복구하지 못한다. 조건을 바꾸어 C가 commit marker라면 A와 B 검증 전 C를 독립 제출한 설계 자체가 오류다.

## 필요한 dependency만 직렬화한다

독립 I/O 64개의 단일 지연을 교육용으로 200 µs라 하자. 모두 직렬이면 \(64×200=12,800\) µs, 즉 12.8 ms다. queue depth 16으로 이상적 네 wave에 처리되면 약 \(4×200=800\) µs와 overhead다. 실제 device·filesystem은 이 단순값과 다르지만 모든 요청에 drain을 붙이면 병렬성을 잃는 방향은 같다.

논리 record 내부 WRITE→FSYNC 같은 dependency만 link하고 서로 다른 record group은 병행할 수 있다. 완료 순서와 공개 순서를 분리하기 위해 stream_id, logical_seq, step을 user_data 상태에 둔다.

~~~text
CQE arrival: 1043, 1041, 1042
기존 commit frontier: 1040
1041 성공 뒤 frontier 1041
1042 성공 뒤 frontier 1042
이미 성공한 1043 확인 뒤 frontier 1043
~~~

**commit frontier**는 연속 순서 중 어디까지 durable·visible하다고 발표할 수 있는지 나타내는 번호다. 1041이 실패하면 1043이 먼저 끝나도 protocol이 gap을 허용하지 않는 한 건너뛰지 않는다.

### 문제 7: ordering을 과하게 건 경우

독립 read 64개마다 drain을 붙여 사실상 한 개씩 실행했다. 200 µs 모형에서 직렬 시간과 queue depth 16 이상 시간을 비교하고, 언제 drain이 필요한지 설명하라.

직렬 모형은 12.8 ms, 16개 병행 네 wave는 약 0.8 ms+overhead다. 차이는 약 16배 방향이다. drain은 checkpoint가 이전 ring 요청 전체 완료 뒤 issue돼야 하는 등 전역 선행 집합이 있을 때 쓴다. file별 dependency라면 link나 userspace 상태 machine이 더 좁을 수 있다. 조건을 바꾸어 device가 실제 병렬성을 제공하지 않거나 queue가 이미 포화면 이상적 16배는 나오지 않지만 불필요한 장벽이 이득을 만들지는 않는다.

## 한 record의 상태 machine이 buffer와 장애를 함께 소유한다

~~~text
PREPARE: length·payload·checksum을 immutable buffer에 완성
WRITE: reserved offset에 남은 byte 제출
  res < 0 → FAILED
  0 <= res < remaining → pointer·offset·remaining 갱신 후 재제출
  full → SYNC
SYNC: 계약에 맞는 FSYNC/DATASYNC 제출
  res < 0 → DURABILITY_FAILED
  res == 0 → 필요하면 RENAME
RENAME: final name으로 공개
DIRSYNC: parent directory 동기화
COMMITTED: caller에게 성공 발표
CLEANUP: 모든 terminal CQE와 consumer 종료 뒤 buffer·fd 해제
~~~

같은 file에 concurrent append하면 offset 예약과 record interleaving도 관리한다. O_APPEND, filesystem atomic 범위, opcode 지원을 실행 kernel과 filesystem에서 probe한다. IOSQE_CQE_SKIP_SUCCESS 같은 CQE 억제 기능은 오류 attribution과 drain caveat를 검토하지 않고 일반 최적화로 적용하지 않는다.

### 문제 8: buffer를 일찍 재사용한 corruption

A WRITE가 buffer X의 8192바이트를 참조한다. submit 직후 애플리케이션이 X를 B record로 덮었고 A CQE는 아직 없다. 가능한 결과와 올바른 수명을 설명하라.

kernel이나 device가 X를 언제 읽는지에 따라 A가 원래 byte, 새 B byte, 섞인 값을 쓸 수 있어 data corruption이다. submit은 buffer 복사를 보장하는 순간이 아니다. A의 terminal CQE까지 X를 변경·free하지 않고, fixed buffer나 zero-copy notification에 추가 수명 계약이 있으면 그것도 만족한다. 조건을 바꾸어 kernel이 submit 때 copy하는 특정 opcode라면 계약이 다를 수 있으므로 opcode 문서를 기준으로 한다. “io_uring은 비동기”라는 일반 문장으로 lifetime을 추측하지 않는다.

이 장의 핵심 경계는 명확하다. SQE 순서, CQE 순서, logical publish 순서는 독립적으로 설계한다. link·hardlink·drain·cancel·timeout은 요청 graph를 표현하지만 partial I/O와 application error를 대신 처리하지 않는다. fsync 성공 범위와 원하는 failure model을 맞추고, 모든 terminal CQE를 받은 뒤에만 buffer와 상태를 해제한다.


## 세 요청의 완료표를 상태 전이로 검증한다

교육용 요청 A=READ 4096, B=WRITE 4096, C=FSYNC를 생각하자. 세 요청이 독립 제출됐다면 앞서 본 여섯 CQE 순서가 가능하지만, B가 A의 결과를 쓰고 C가 B의 전체 byte를 동기화해야 한다면 올바른 상태 전이는 제한된다. A full을 확인하고 CPU 변환을 끝낸 뒤 B를 제출하며, B full 뒤 C를 제출해야 한다. 이때 관측 CQE 순서는 논리적으로 A-B-C지만 각 단계의 error가 뒤 제출 자체를 막는다.

| A 결과 | B 상태 | C 상태 | buffer 처리 |
|---|---|---|---|
| 4096 full | 아직 미제출→제출 | B full 뒤 제출 | read buffer는 transform 끝까지 유지 |
| 0 EOF | 미제출 | 미제출 | protocol상 EOF 처리 뒤 반환 |
| -EIO | 미제출 | 미제출 | A 실패 기록 뒤 반환 |
| full 뒤 B=2048 | remaining 2048 재제출 | 아직 미제출 | write buffer 전체 유지 |
| full 뒤 B=-ENOSPC | terminal 실패 | 미제출 | 복구 기록 뒤 consumer 종료 시 반환 |
| A·B full, C=-EIO | 완료 | durability 실패 | retry 정책이 참조하면 유지 |

반대로 A, B, C가 독립 read 세 개라면 A-C-B 같은 순서를 정상 처리하고 각 buffer는 자기 CQE 기준으로 해제할 수 있다. “요청이 세 개”라는 개수로 순서를 정하지 않고 data dependency graph로 정한다.

### 추가 풀이: cancel 성공처럼 보여도 원본 CQE가 필요한 이유

cancel CQE가 성공을 나타냈지만 target CQE를 아직 읽지 못했다고 하자. cancel operation이 대상을 찾고 취소를 요청했다는 결과와 target의 실제 terminal 결과는 같은 사건이 아니다. target이 이미 device completion과 race했다면 data byte나 error CQE가 따로 올 수 있다. target user_data를 outstanding table에 남기고 terminal CQE를 소비한 뒤 buffer, fd reference와 timer state를 정리한다. 조건을 바꾸어 multishot target이면 MORE 없는 CQE가 수명 종료 기준인지 해당 opcode 계약을 확인한다.

### 추가 풀이: caller 성공을 언제 돌려주는가

8192바이트 write full CQE가 2 ms, fsync CQE가 12 ms, rename CQE가 13 ms, directory fsync CQE가 20 ms에 왔다. power-loss 뒤 final name까지 남는 계약이면 2 ms나 12 ms에 성공을 돌려서는 안 된다. 13 ms에도 directory entry의 crash 지속성이 남아 있다. 네 단계가 모두 성공한 20 ms 이후 commit을 발표한다. caller deadline이 15 ms라면 durability를 몰래 낮추지 않고 timeout·unknown outcome 정책과 idempotent retry 식별자를 설계한다.

## 공식 근거

- [io_uring(7)](https://man7.org/linux/man-pages/man7/io_uring.7.html)
- [io_uring_enter(2)](https://man7.org/linux/man-pages/man2/io_uring_enter.2.html)
- [fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)
- [Linux kernel io_uring documentation](https://docs.kernel.org/io_uring/index.html)

[이 책 목차](README.md) · [이전: io_uring registration, polling과 feature 탐지](10-io-uring-registration-polling-and-features.md) · [다음: Network I/O와 kernel 관찰](12-network-io-and-kernel-observation.md)
