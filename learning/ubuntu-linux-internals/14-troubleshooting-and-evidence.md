# 14. 문제 해결과 증거 수집

![실행 경로 그림](assets/cgroup-tree.svg)

![실행 경로 그림](assets/cpu-memory-pressure.svg)

[이전: 13. Container·Kubernetes·GPU·RAN](13-containers-kubernetes-gpu-and-ran.md) · [목차](README.md) · [다음: 15. 안전한 로컬 모형 실습](15-safe-local-model-labs.md)

![사용자 프로그램에서 커널·cgroup·장치로 이어지는 Ubuntu 실행 계층](assets/ubuntu-stack.svg)

문제 해결은 가장 먼저 떠오른 원인을 증명하는 일이 아니다. 같은 “Spark 작업이 멈췄다”는 증상을 CPU 제한, memory reclaim, storage queue, shuffle network, JVM 정지, lock, io_uring completion 처리 오류가 모두 만들 수 있다. 관측 가능한 사실과 해석을 분리하고, 같은 시간축의 수치가 어떤 가설을 강하게 하거나 약하게 하는지 추적해야 한다.

이 장의 모든 출력은 설명을 위해 만든 **가상 관측값** 이다. 이 서버나 실제 Spark cluster에서 측정한 값이 아니다. 경로와 field 존재 여부는 kernel, cgroup 구성, container namespace, 권한에 따라 달라질 수 있다.

## 1. 관측, 지표, 증거, 가설

**관측(observation)** 은 특정 시각과 범위에서 읽은 값이다. “14:03:00에 executor cgroup memory.current가 6.2GiB였다”가 관측이다. **지표(metric)** 는 반복해서 같은 의미로 수집할 수 있게 이름·단위·범위를 정한 관측량이다. **증거(evidence)** 는 경쟁 가설을 구분하는 데 쓰는 관측과 수집 조건의 묶음이다. 값 하나는 증거 조각일 수 있지만 수집 범위와 시간 없이 원인을 확정하지 못한다.

**가설(hypothesis)** 은 증상을 만들 수 있는 구체 기작에 대한 예상이다. “느리다”는 가설이 아니다. “executor cgroup이 CPU quota를 period마다 소진해 runnable thread가 throttled된다”처럼 주체, 자원, 상태 전이를 적는다. 가설마다 참일 때 함께 보여야 할 관측과 거짓일 때의 반대 관측을 미리 쓴다.

~~~mermaid
flowchart LR
    S["Spark stage 진척 정지"] --> H1["CPU quota"]
    S --> H2["memory reclaim"]
    S --> H3["device queue"]
    S --> H4["CQ 처리 오류"]
    H1 --> E["같은 60초 구간의 차분과 순간값"]
    H2 --> E
    H3 --> E
    H4 --> E
    E --> N["가설 순위와 다음 최소 분리 관측"]
~~~

## 2. 순간값과 누적 counter

**gauge, 순간값** 은 읽은 시점의 상태량이다. memory.current, block device의 in-flight I/O 수, process의 resident memory가 예다. 서로 다른 시점의 gauge 차이는 증가·감소를 말하지만 그 사이 최대값을 알려 주지 않는다.

**counter, 누적 카운터** 는 kernel이나 application의 어떤 기준 시점부터 사건이나 시간을 더한 값이다. cpu.stat의 usage_usec, nr_throttled, PSI total, /proc/diskstats의 completed I/O가 예다. 절대값 1,000,000은 오래 실행해서 큰 것일 수 있다. 증상 시작 전 C0와 종료 후 C1의 **delta, 차분** C1-C0를 시간 구간 Δt와 함께 본다.

counter가 reset, wrap, process/cgroup 재생성으로 작아질 수 있다. boot ID, process start time, cgroup inode 또는 workload attempt ID를 함께 기록해야 “음수 delta”를 실제 감소로 잘못 읽지 않는다.

**ratio와 moving average** 는 또 다른 종류다. PSI avg10은 최근 10초 경향을 백분율로 요약하고 total은 절대 stall microseconds 누적값이다. avg10 두 개를 빼는 것은 구간 stall time 계산이 아니다. custom 60초 비율은 total delta/60초로 별도 계산하되 PSI가 task stall을 집계하는 의미를 지켜야 한다.

## 3. process, thread, CPU time, wall time

**process** 는 주소 공간과 file descriptor, credential 같은 실행 자원을 가진 kernel 관리 단위다. **thread** 는 process 안에서 scheduler가 CPU에 올리는 실행 흐름이다. Spark executor JVM 하나에 task thread, GC thread, shuffle thread가 여러 개 있을 수 있다.

**CPU time** 은 thread들이 실제 CPU에서 user code 또는 kernel code를 실행한 누적 시간이다. /proc/PID/stat의 utime과 stime 같은 field는 clock tick 단위 누적값이며 system의 USER_HZ로 환산해야 한다. 여러 thread가 여러 core에서 동시에 실행하면 60초 wall 구간에 process CPU time이 60초보다 클 수 있다.

**wall time** 은 시작부터 종료까지 사람이 보는 경과 시간이다. 60초 wall 동안 CPU time이 12초 늘었다면 나머지 48초를 전부 I/O wait라고 부를 수 없다. sleep, futex, network, scheduler wait, throttling, page fault 등 여러 상태가 포함될 수 있다.

**iowait** 은 /proc/stat의 CPU aggregate accounting field로 볼 수 있지만 특정 process가 I/O 때문에 기다린 정확한 시간은 아니다. kernel 문서도 iowait 계산에 한계가 있음을 전제로 해석해야 한다. process CPU time이 낮고 system iowait가 높다는 조합은 storage 가설을 강화할 수 있으나 per-process 인과 증명은 아니다.

## 4. cgroup 범위를 먼저 찾는다

cgroup v2는 process들을 hierarchy로 조직하고 CPU, memory, I/O 같은 controller가 자원 accounting과 제한을 적용하게 한다. /proc/PID/cgroup의 0::/path 항목으로 PID가 속한 v2 경로를 찾을 수 있다. container 안에서 보이는 경로와 host 경로가 namespace 때문에 다를 수 있으므로 어느 관점에서 읽었는지 적는다.

같은 Spark application에도 driver와 executor가 서로 다른 cgroup일 수 있다. host 전체 /proc/pressure와 executor cgroup의 cpu.pressure를 섞으면 범위가 달라진다. ancestor limit은 child가 완화할 수 없으므로 leaf의 cpu.max만 보지 않고 유효 ancestor 경계도 확인한다.

이 장의 read-only 예시는 값을 바꾸지 않는다.

~~~text
cat /proc/PID/cgroup
cat /sys/fs/cgroup/PATH/cpu.stat
cat /sys/fs/cgroup/PATH/memory.current
cat /sys/fs/cgroup/PATH/memory.events
cat /sys/fs/cgroup/PATH/io.pressure
cat /proc/pressure/io
~~~

pseudo-file은 disk의 오래된 text가 아니라 kernel이 현재 상태를 file interface로 내보낸 것이다. field 단위와 kernel version을 공식 문서에서 확인한다.

## 5. 사례 정의: “Spark 작업이 멈춤”

14:03:00부터 14:04:00까지 stage 37의 completed task가 2,400에서 2,403으로 거의 늘지 않았다고 하자. executor-7의 task p95 wall time은 2초에서 48초로 증가했다. driver는 살아 있고 executor lost event는 없다. 증상 범위는 같은 shuffle partition들을 읽는 executor-7과 executor-8이며, map output을 이미 가진 일부 executor는 정상이다.

먼저 신원을 고정한다.

| 객체 | 가상 신원 |
|---|---|
| Spark application | app-20261011-0042 |
| stage/attempt | stage 37, attempt 0 |
| executor | 7, PID 24810 |
| cgroup | /workload.slice/spark-executor-7.scope |
| 장치 | nvme0n1 |
| 관찰 창 | monotonic 14:03:00~14:04:00, 60초 |
| host boot ID | 같은 값 유지 |
| executor start time | 관찰 전후 동일 |

“멈춤”을 task 완료율 저하로 수치화했다. process가 종료됐다는 뜻도, CPU가 0이라는 뜻도 아니다.

## 6. 경쟁 가설과 구분 관측

| 가설 | 예상되는 동반 관측 | 약하게 만드는 관측 |
|---|---|---|
| H1 CPU quota | nr_throttled와 throttled_usec 큰 delta, CPU pressure, period성 | throttling 거의 없음 |
| H2 memory reclaim | memory.high event, memory PSI, pgscan/refault 증가 | current가 경계 아래, delta 거의 없음 |
| H3 storage queue | io PSI, device busy/weighted time, latency, queue 증가 | device와 cgroup I/O 모두 낮음 |
| H4 io_uring completion 처리 | submitted-completed gap 증가, unknown ID/error, device는 한가할 수도 있음 | terminal CQE와 pending 수가 일치 |
| H5 shuffle network | retransmit, remote fetch wait, NIC queue/drop | local storage wait가 지배 |
| H6 JVM/lock/GC | safepoint, futex wait, GC pause와 task 정체 일치 | thread가 block I/O에 대기 |

한 가설의 관측이 다른 가설에서도 나올 수 있다. memory reclaim이 storage I/O를 만들고 io PSI를 높일 수 있으므로 page reclaim과 application read I/O를 분리해야 한다.

## 7. CPU quota를 60초 차분으로 판정한다

executor cgroup의 cpu.max가 200000 100000이라고 하자. quota 200,000µs를 100,000µs period마다 허용하므로 평균 2 CPU 상한이다. 예약이 아니라 상한이며 runnable work가 없으면 쓰지 않는다.

가상 cpu.stat snapshot은 다음과 같다.

| field | t0 | t1 | delta |
|---|---:|---:|---:|
| usage_usec | 9,100,000,000 | 9,142,000,000 | 42,000,000 |
| nr_periods | 91,000 | 91,600 | 600 |
| nr_throttled | 8,200 | 8,208 | 8 |
| throttled_usec | 120,000,000 | 120,240,000 | 240,000 |

60초에 CPU time 42초이므로 평균 0.7 CPU를 썼다. 600 period 중 8 period가 throttled됐고 throttled time delta는 0.24초다. 일부 순간 제한은 있었지만 60초 정체 대부분을 설명하기에는 작다는 방향이다. host idle 62%만으로 CPU 가설을 배제할 수는 없지만, 이 cgroup 차분은 H1을 약하게 한다.

nr_throttled는 “thread 8개가 멈췄다”가 아니라 throttling이 발생한 period 수 관련 counter다. throttled_usec도 task wall latency와 그대로 같지 않다. kernel version의 cpu.stat 정의를 확인한다.

## 8. process CPU와 wall trace

같은 60초에 PID 24810의 전체 thread user CPU time이 10초, system CPU time이 2초 늘었다고 하자. 합계 12 CPU초다. cgroup usage 42초와 다른 까닭은 cgroup에 executor helper 또는 sidecar process가 더 있거나, PID의 thread 집계·수집 시점 범위가 다를 수 있다. 두 숫자가 다르다고 즉시 오류로 버리지 않고 cgroup.procs와 thread 범위를 맞춘다.

wall 60초 중 process CPU 12초였다는 사실은 48초 I/O 대기를 증명하지 않는다. 1초 간격으로 주요 task thread의 state와 kernel stack category를 표본화했다고 가정하자. 45개 표본이 uninterruptible sleep과 block I/O wait 경로, 5개가 futex, 10개가 running/runnable이면 storage 가설이 강해진다. 표본은 시간 전체를 완전 기록한 것이 아니므로 비율에 신뢰 구간과 sampling bias가 있다.

## 9. memory pressure를 분리한다

가상 memory 경계와 gauge는 다음과 같다.

| 값 | t0 | t1 |
|---|---:|---:|
| memory.current | 6.2GiB | 6.3GiB |
| memory.high | 8GiB | 8GiB |
| memory.max | 10GiB | 10GiB |

memory.events 차분은 high=0,max=0,oom=0,oom_kill=0이다. cgroup memory.pressure some total은 60초 동안 30,000µs 증가했고 full은 0이다. 이 관찰 창에는 high 경계 사건과 OOM이 없고 memory stall도 0.03초 수준이라는 가상 결과다. H2는 약해진다.

memory.current<high만으로 reclaim이 전혀 없다고 말할 수는 없다. node 전체 pressure, ancestor cgroup, direct reclaim, page cache refault를 더 볼 수 있다. 그러나 “memory.max에 가까워 멈췄다”는 구체 가설과는 맞지 않는다.

## 10. PSI를 정확히 읽는다

PSI는 CPU, memory, I/O 자원 부족으로 task가 stall된 시간 영향을 집계한다. **some** 은 적어도 일부 task가 해당 자원을 기다린 시간 비중이고, **full** 은 모든 non-idle task가 동시에 막힌 시간 비중이다. system-level CPU full은 의미상 별도 주의가 있으며 호환을 위해 0으로 보일 수 있다.

executor cgroup io.pressure가 다음이라고 하자.

~~~text
t0 some avg10=4.00 avg60=2.00 avg300=0.80 total=700000000
t1 some avg10=42.00 avg60=28.00 avg300=8.50 total=718000000
t0 full avg10=0.50 avg60=0.20 avg300=0.10 total=30000000
t1 full avg10=15.00 avg60=9.00 avg300=2.00 total=30600000
~~~

some total delta는 18,000,000µs=18초, full delta는600,000µs=0.6초다. 60초 구간에 일부 task I/O stall이 크게 존재했고, 모든 non-idle task가 동시에 막힌 시간은 상대적으로 짧았다. avg10이 avg60보다 큰 것은 끝부분에 pressure가 더 심해졌다는 경향과 맞지만 정확한 시계열은 아니다.

PSI는 장치 latency 그 자체가 아니다. page fault나 writeback 등 I/O stall 기작이 포함될 수 있다. 다음 층의 byte와 device queue를 확인한다.

## 11. cgroup I/O와 장치 통계

cgroup io.stat은 해당 cgroup에 charge된 장치별 byte와 operation counter를 제공할 수 있다. 가상 delta가 rbytes=800MiB, rios=6,400, wbytes=20MiB, wios=200이라고 하자. workload가 주로 shuffle block을 읽는다는 Spark 관찰과 방향이 맞는다.

장치 /proc/diskstats의 field는 누적 counter와 in-flight gauge가 섞여 있다. 다음은 교육용 nvme0n1 차분이다.

| 항목 | t0 | t1 | delta |
|---|---:|---:|---:|
| reads completed | 1,200,000 | 1,206,000 | 6,000 |
| sectors read | 12,000,000 | 13,536,000 | 1,536,000 |
| read time ms | 2,400,000 | 2,520,000 | 120,000 |
| I/O in progress | 64 | 72 | gauge 64→72 |
| time doing I/O ms | 1,000,000 | 1,059,000 | 59,000 |
| weighted I/O time ms | 5,000,000 | 6,800,000 | 1,800,000 |

sector를 512B로 해석하는 해당 interface 계약에서 1,536,000 sectors는 750MiB다. cgroup 800MiB와 정확히 같지 않을 수 있다. 수집 경계, readahead, 다른 cgroup, 계층 장치 mapping을 확인한다.

completed read당 read time의 단순 비는 120,000/6,000=20ms다. 동시 I/O가 있으므로 wall time 120초라는 뜻이 아니다. time doing I/O delta 59,000ms는 60초 창 대부분 장치가 active였음을 시사한다. weighted time 1,800,000ms를 60,000ms로 나눈 약30은 구간 평균 outstanding I/O의 근사로 읽을 수 있지만 kernel field 정의와 stacking을 확인해야 한다. in-flight 72는 t1 순간값이며 60초 최대가 아니다.

이 조합은 H3 device queue saturation을 강하게 한다. CPU와 memory 가설보다 증상과 같은 범위·시간에 큰 변화가 있다.

## 12. queue, throughput, latency를 함께 본다

**queue** 는 service를 기다리는 request 집합이다. **latency** 는 request 하나가 제출된 뒤 완료될 때까지 경과 시간이고, **throughput** 은 초당 완료 byte 또는 operation 수다. queue가 늘어도 throughput이 잠시 높을 수 있다. 들어오는 속도가 완료 속도보다 더 높으면 pending이 쌓이고 tail latency가 폭증한다.

Little의 법칙 L=λW는 안정된 장기 평균에서 system 안 평균 request 수 L, 처리율 λ, 평균 체류시간 W의 관계를 설명한다. 6,000 reads/60s=100 reads/s이고 평균 outstanding 약30이라면 단순 W≈30/100=0.3s다. 앞의 read time/completion 20ms와 크게 다르다. field 집계 범위, merge, in-progress, 다른 I/O, 안정 상태 가정이 맞지 않음을 보여 준다. 숫자가 안 맞으면 원하는 하나를 고르지 말고 정의와 범위를 재검사한다.

## 13. SQ와 CQ는 어디서 관측하는가

io_uring을 쓰는 native shuffle plugin이 있다고 가정하자. **SQ(Submission Queue)** 는 user space가 kernel에 처리 요청을 넘기는 ring이고, SQE는 한 요청 entry다. **CQ(Completion Queue)** 는 kernel이 완료 결과를 돌려주는 ring이고 CQE는 request ID와 result를 담는다.

Linux가 모든 application의 “제출 총계와 completion 총계”를 일반 /proc field로 제공한다고 가정하면 안 된다. 다음 값은 plugin의 자체 계측이라고 명시한다.

| application counter | t0 | t1 | delta |
|---|---:|---:|---:|
| SQE submitted | 5,000,000 | 5,020,000 | 20,000 |
| terminal CQE consumed | 4,999,880 | 5,019,780 | 19,900 |
| pending requests | 120 | 220 | +100 |
| CQE negative result | 10 | 12 | +2 |
| unknown user_data | 0 | 0 | 0 |
| completion p95 | 18ms | 310ms | gauge/window summary |

pending은 submitted minus terminal completion을 같은 request lifetime과 reset 경계에서 계산해야 한다. +100은 queue 증가지만 device queue가 이미 높고 negative/unknown ID가 거의 없으므로 “CQE를 잃는 bug”보다 “kernel/device completion이 늦다”는 H3와 맞는다.

만약 device는 한가한데 CQ ring에 완료가 쌓이고 application consumed counter만 멈춘다면 H4 consumer thread 정체를 의심한다. SQ/CQ 수치만으로 kernel, device, application 중 어디가 병목인지 단정하지 않는다.

Spark가 io_uring을 사용하지 않는 구성이라면 이 관측은 아예 적용하지 않는다. Java NIO, Netty, native plugin의 실제 I/O 경로를 먼저 확인한다.

## 14. 오류와 short completion

CQE result가 음수면 일반적으로 -errno 형식 실패이고, 0 이상이면 opcode별 성공 결과다. -22는 22 byte가 아니라 EINVAL 범주의 오류다. read 4096B 요청에 result=1200이면 short read 성공일 수 있다. 0은 일반 file의 현재 offset에서 EOF일 수 있다.

out-of-order completion은 정상일 수 있으므로 submission 배열 순번이 아니라 user_data로 원래 request와 buffer를 찾는다. cancel CQE가 왔다고 대상 buffer를 즉시 해제하지 않는다. 대상 operation과 cancel이 경쟁할 수 있어 대상의 terminal state가 final release를 소유하게 한다.

가상 사례의 negative delta 2개는 전체 20,000 요청의 정체를 설명하지 못하지만 해당 errno와 opcode는 별도 조사한다. 소수 오류를 무시하는 것과 전체 병목 원인으로 확대하는 것 모두 피한다.

## 15. 조건 변경으로 원인을 분리한다

읽기 관측만으로 H3가 가장 강해졌지만 인과를 더 확인하려면 격리된 재현 환경에서 한 조건만 바꾼다. 운영에서 즉시 설정을 바꾸는 절차가 아니다.

가상 대조 실험은 같은 shuffle data와 snapshot, executor memory/CPU를 유지하고 I/O 동시 요청 상한만 64에서16으로 낮춘다. 입력 결과 checksum은 같아야 한다.

| 조건 | outstanding 상한 | throughput | completion p95 | device weighted queue | stage 시간 |
|---|---:|---:|---:|---:|---:|
| A | 64 | 750MiB/60s | 310ms | 약30 | 60s에도 미완 |
| B | 16 | 720MiB/60s | 55ms | 약12 | 68s 완료 |

이 역시 가상 수치다. B는 peak throughput이 조금 낮지만 queue와 tail latency가 줄고 stage가 예측 가능하게 끝났다. “더 많은 병렬 I/O가 항상 빠르다”는 가설을 반박하며 queue saturation 기작과 맞는다. 그러나 cache, task 배치, 장치 background 작업이 같았는지 반복 실험이 필요하다.

다른 분리 방법은 동일 file을 page cache hit로 읽는 조건과 direct device read 조건을 나누거나, 같은 executor에서 local cached shuffle과 remote fetch를 나누는 것이다. 한 번에 Spark partition 수, executor 수, file size까지 모두 바꾸면 원인을 알 수 없다.

## 16. 최종 결론의 강도

이 가상 사례에서 쓸 수 있는 결론은 다음과 같다.

> 14:03~14:04 executor cgroup에서 CPU throttling과 memory pressure 증가는 작았고, io PSI some 18초 증가, 장치 active 59초, weighted queue 근사30, application pending +100과 completion p95 310ms가 같은 시간에 나타났다. storage queue saturation이 가장 강한 후보다. 격리된 가상 조건 변경에서 outstanding 상한을 줄였을 때 queue와 p95가 감소했다. 실제 인과 결론에는 반복 재현과 stack별 계측이 더 필요하다.

“NVMe가 고장났다”까지는 말할 수 없다. 다른 tenant I/O, filesystem writeback, device firmware pause, virtual block layer도 같은 장치 통계를 만들 수 있다. 원인 범위를 device path로 좁혔을 뿐이다.

## 17. 증거 기록표

| 필드 | 기록 내용 |
|---|---|
| 시간 | monotonic와 wall clock, timezone, 수집 간격 |
| 신원 | boot ID, PID start, cgroup path, Spark attempt |
| 증상 | completed tasks/s, wall latency, 범위 |
| 원시값 | t0와 t1 전체 text, 단위 |
| 파생값 | delta와 식, reset 검증 |
| 가설 | 예상 동반·반대 관측 |
| 변경 | 격리 환경에서 바꾼 한 변수 |
| 정확성 | result count/checksum |
| 결론 | 지지 수준과 남은 대안 |
| 한계 | sampling, namespace, version, 권한 |

원시값을 덮어쓰지 않고 파생 계산을 별도 column으로 둔다. 나중에 field 정의를 바로잡아도 다시 계산할 수 있어야 한다.

## 18. 흔한 잘못된 결론

- host CPU idle이 높으니 executor는 CPU를 기다리지 않는다고 단정한다. cgroup quota와 affinity를 놓친다.
- memory.current<max이므로 reclaim이 없다고 단정한다. high, ancestor와 node pressure를 놓친다.
- PSI avg10이 40이니 request latency가 40ms라고 읽는다. 단위와 의미가 다르다.
- /proc/diskstats 누적 read_ms를 현재 latency로 읽는다. 구간 delta가 필요하다.
- process CPU time이 낮으니 나머지는 전부 iowait라고 계산한다. 여러 wait 상태를 놓친다.
- SQ submitted와 CQ consumed 차이를 kernel 유실로 단정한다. 정상 pending과 application consumer 지연을 놓친다.
- correlation을 causation으로 선언한다. 조건 변경과 반대 증거가 없다.

## 19. 안전 경계

/proc와 cgroup pseudo-file 읽기도 접근 정책과 개인정보·운영 보안 범위 안에서 수행한다. 권한이 없으면 우회하지 않는다. sysctl -w, cgroup limit 변경, cache drop, process signal, device reset은 상태 변경이다. 이 장의 읽기 전용 수집과 별개로 승인, 복구 계획, 영향 범위, 중단 기준이 필요하다.

운영 증거 수집 자체가 부하를 만들 수 있다. 고주파 stack sampling, 모든 syscall trace, 장치 debug는 sampling 비용을 먼저 시험한다. 필요한 가설을 구분하는 최소 관측에서 시작한다.

## 20. 완전 풀이 문제

### 문제 1. 누적값과 차분

nr_throttled가 t0=8,200,t1=8,208이다.

**풀이:** 관찰 창 delta는8이다. 전체 수명 동안 8,208번이라는 절대값보다 60초 증상 중 8 증가가 직접 관련된다. cgroup 재생성 여부와 nr_periods delta600도 함께 본다.

### 문제 2. CPU share

cpu.max=200000 100000이다.

**풀이:** quota/period=2 CPU 평균 상한이다. thread마다2 CPU가 아니며 cgroup 전체 합이다. quota가 max이면 상한이 없다는 별도 표현이므로 parser가 숫자로 가정하면 안 된다.

### 문제 3. CPU time과 wall

60초 wall에 process CPU가12초 늘었다.

**풀이:** 평균0.2 CPU를 쓴 계산은 가능하지만 나머지48초가 전부 I/O wait라는 결론은 불가능하다. sleep, futex, scheduler, throttling 등 상태를 sampling한다.

### 문제 4. PSI total

io some total이 18,000,000µs 늘었다.

**풀이:** 18초의 누적 stall 증가다. request 하나가18초 느렸다는 뜻이 아니다. cgroup 안 적어도 일부 task의 I/O stall 집계이며 avg10과 device 통계로 시간 모양을 보완한다.

### 문제 5. memory 경계

current=6.3GiB,high=8GiB,max=10GiB이고 event delta가 모두0이다.

**풀이:** 이 cgroup의 high/max 직접 압박 가설은 약해진다. node 또는 ancestor pressure 가능성은 남으므로 범위를 확장해 확인한다.

### 문제 6. device read 평균

read_ms delta120,000, reads delta6,000이다.

**풀이:** 단순히20ms/completed read다. 동시 I/O가 있어 wall elapsed와 같지 않으며 merged request와 field 정의를 확인한다. p95 latency도 이 평균에서 알 수 없다.

### 문제 7. sectors를 byte로

1,536,000 sectors, sector unit512B다.

**풀이:** 786,432,000B=750MiB다. 장치의 물리 sector 크기를 임의로 대입하지 않고 해당 통계 interface가 정의한 unit을 쓴다.

### 문제 8. SQ/CQ gap

20,000 제출,19,900 terminal completion, pending이120→220이다.

**풀이:** delta gap100과 pending 증가100이 일치한다. 유실보다 정상 미완료 queue 설명과 맞는다. request reset과 error/cancel도 terminal count에 포함됐는지 확인한다.

### 문제 9. 조건 변경

outstanding64에서16으로 줄자 throughput은 조금 줄고 p95와 queue가 크게 줄었다.

**풀이:** queue saturation 가설을 강화한다. 결과 checksum과 다른 자원 조건이 같아야 하며 여러 번 반복해 장치 background 변동을 분리한다.

### 문제 10. 결론 범위

io PSI와 device busy가 높다.

**풀이:** storage path pressure와 강한 상관이라고 말할 수 있다. 장치 hardware 고장이라고 확정하려면 error log, 다른 workload, filesystem/block layer와 격리 시험이 더 필요하다.

## 공식 근거

- [Linux kernel: cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)
- [Linux kernel: Pressure Stall Information](https://docs.kernel.org/accounting/psi.html)
- [Linux kernel: The proc filesystem](https://docs.kernel.org/filesystems/proc.html)
- [Linux kernel: I/O statistics fields](https://docs.kernel.org/admin-guide/iostats.html)
- [Linux kernel: io_uring](https://docs.kernel.org/io_uring/)
- [io_uring_setup(2)](https://man7.org/linux/man-pages/man2/io_uring_setup.2.html)
