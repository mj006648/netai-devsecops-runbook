# 06. 격리, 보안, 컨테이너: UID에서 KVM까지

이전: [VFS·장치·I/O](05-vfs-devices-and-io.md) · 다음: 관측·문제해결 장

보강·근거 확인일: **2026-09-22**. 이 장은 Linux가 “누가 무엇을 할 수 있는가”를 어떻게 판단하고, 컨테이너와 VM이 어떤 격리 경계를 제공하는지 설명한다. eBPF의 packet path와 observability/security hook은 네트워크 교재에서 별도 심화하고, 이 장에서는 커널 보안 경계와 연결점만 둔다.

## 1. 보안은 하나의 기능이 아니라 여러 질문의 조합이다

Linux 보안 판단은 단일 스위치가 아니다. 커널은 여러 층의 질문을 순서대로 또는 조합해서 본다.

| 질문 | 예 |
| --- | --- |
| 누구인가? | UID, GID, supplementary groups |
| 무엇을 하려는가? | open for write, mount, ptrace, bind low port |
| 대상은 무엇인가? | file inode, socket, process, cgroup, device |
| 어떤 권한 모델이 적용되는가? | DAC, ACL, capability, LSM policy |
| 어떤 이름 공간 안에서 보는가? | mount namespace, user namespace, network namespace |
| 자원 한도는 무엇인가? | cgroup memory/cpu/pids/io limit |
| syscall 자체가 허용되는가? | seccomp filter |

보안 문제를 잘 보려면 “root인가?” 하나로 끝내지 말고 어떤 권한과 namespace의 root인지 물어야 한다.

## 2. UID, GID, DAC: 가장 오래 보는 권한 모델

**UID(User ID)**는 사용자를 나타내는 숫자다. **GID(Group ID)**는 그룹을 나타낸다. 전통적인 Unix 권한은 file mode bit로 owner/group/others에 read/write/execute를 부여한다. 이것을 **DAC(Discretionary Access Control)**라고 부른다. 파일 소유자가 권한을 어느 정도 조정할 수 있기 때문이다.

~~~text
-rw-r-----  owner=alice  group=dev  file=secret.txt

owner alice: read/write 가능
group dev:   read 가능
others:      접근 불가
~~~

directory의 execute bit는 “실행”이 아니라 traversal 권한이다. directory에 `x`가 없으면 그 안의 이름을 따라 들어갈 수 없다. sticky bit, setuid/setgid bit도 별도 의미가 있다.

## 3. ACL은 mode bit보다 세밀한 예외를 둔다

POSIX ACL은 특정 사용자나 그룹에 더 세밀한 권한을 줄 수 있다. 예를 들어 owner/group/others 3분류만으로 부족할 때 “bob에게만 read 권한” 같은 예외를 표현한다.

ACL이 있으면 mode bit만 보고 결론 내리기 어렵다. 또한 filesystem과 mount option, 도구 지원이 필요하다. 운영 중 권한 문제를 분석할 때는 `ls -l` 출력의 `+` 표시나 `getfacl` 결과를 함께 봐야 한다.

## 4. capability는 root 권한을 조각낸 것이다

전통적으로 UID 0(root)은 거의 모든 일을 할 수 있었다. **Linux capabilities**는 이 강한 권한을 여러 조각으로 나눈다. man-pages `capabilities(7)`는 capability가 superuser 권한을 단위별로 나누는 방식임을 설명한다.

| capability | 예시 의미 |
| --- | --- |
| `CAP_NET_BIND_SERVICE` | 1024 미만 privileged port bind |
| `CAP_NET_ADMIN` | network 설정 변경 |
| `CAP_SYS_ADMIN` | mount 등 많은 관리 작업. 너무 넓어서 특히 주의 |
| `CAP_SYS_PTRACE` | 다른 process 추적/검사 |
| `CAP_DAC_OVERRIDE` | DAC 파일 권한 우회 |

컨테이너 보안에서 capability drop은 중요하다. “rootless가 아니더라도 필요한 capability만 남긴다”는 원칙이 여기서 나온다. 다만 capability가 줄어도 kernel attack surface가 사라지는 것은 아니다. 허용된 syscall과 namespace, device 접근, LSM 정책이 함께 중요하다.

## 5. namespace는 이름과 관점을 분리한다

**namespace**는 process가 보는 특정 global resource의 관점을 분리한다. man-pages `namespaces(7)`는 mount, PID, network, IPC, UTS, user, cgroup, time namespace를 설명한다.

| namespace | 분리되는 것 | 컨테이너에서 보이는 효과 |
| --- | --- | --- |
| mount | mount point set | 컨테이너마다 다른 root filesystem |
| PID | process ID number space | 컨테이너 안에서 자기 init이 PID 1처럼 보임 |
| network | interfaces, routing table, ports 등 | 컨테이너별 veth, loopback, iptables/nft context |
| IPC | SysV IPC, POSIX message queue 등 | IPC 객체 분리 |
| UTS | hostname/domainname | 컨테이너별 hostname |
| user | UID/GID mapping과 capability scope | 컨테이너 root가 host root와 다를 수 있음 |
| cgroup | cgroup tree view | 자원 계층 관점 분리 |
| time | boot/monotonic clock offset 일부 | 시간 관점 조정 |

namespace는 “이름을 다르게 보이게 하는 것”에 가깝다. CPU와 RAM을 얼마나 쓸 수 있는지는 cgroup이 담당한다.

## 6. cgroup은 자원 계층과 회계다

**cgroup(control group)**은 process group에 resource limit, weight, accounting을 적용하는 kernel 기능이다. container orchestrator는 cgroup으로 CPU, memory, pids, I/O 같은 자원 정책을 건다.

| controller | 대표 목적 |
| --- | --- |
| cpu | share/weight, quota, throttling |
| memory | memory.max, reclaim, OOM 범위 |
| pids | fork 폭주 제한 |
| io | block I/O weight/limit |
| cpuset | CPU와 NUMA node 배치 |

Kubernetes pod limit은 결국 host kernel cgroup 설정으로 내려간다. pod 안에서는 “내 앱이 OOMKilled”로 보이지만, kernel 입장에서는 memory cgroup limit을 넘은 group 안에서 victim을 고른 것이다.

## 7. seccomp는 syscall 입구를 필터링한다

**seccomp**는 process가 사용할 수 있는 syscall을 제한하는 기능이다. seccomp-bpf filter는 syscall 번호와 인자를 보고 allow, errno, kill, trace 같은 동작을 결정할 수 있다.

seccomp의 목적은 attack surface를 줄이는 것이다. 예를 들어 web server가 `mount`, `ptrace`, `bpf`, `init_module` 같은 syscall을 쓸 이유가 없다면 막을 수 있다.

하지만 seccomp는 완전한 sandbox가 아니다.

| 한계 | 설명 |
| --- | --- |
| 허용된 syscall의 취약점 | 허용 syscall 안의 kernel bug는 여전히 위험 |
| TOCTOU와 pointer 검사 | user memory가 syscall 중 바뀔 수 있어 kernel이 조심해야 함 |
| policy 복잡성 | 너무 좁으면 정상 app이 깨지고, 너무 넓으면 효과가 줄어듦 |
| syscall만 봄 | filesystem 내용, network policy, LSM label은 별도 층 |

## 8. LSM, SELinux, AppArmor

**LSM(Linux Security Modules)**은 kernel의 여러 지점에 security hook을 두고, SELinux, AppArmor, Smack 같은 보안 모듈이 접근 결정을 추가하게 하는 framework다. kernel.org LSM 문서는 inode permission 같은 접근 제어 hook과 security field 관리 hook을 설명한다.

| 모델 | 직관 |
| --- | --- |
| SELinux | label과 policy type enforcement 중심 |
| AppArmor | path/profile 중심의 MAC 스타일 제한 |
| commoncap | capability 로직을 LSM module 형태로 포함 |

DAC가 허용해도 LSM이 거부할 수 있다. 그래서 permission denied를 볼 때 file mode만 보면 부족하다. `audit` log, SELinux context, AppArmor profile mode(enforce/complain)를 함께 확인해야 한다.

## 9. container는 여러 kernel 기능의 조합이다

컨테이너는 하나의 kernel primitive가 아니다.

~~~text
container runtime
  → namespaces로 관점 분리
  → cgroups로 자원 제한과 회계
  → capabilities drop으로 root 권한 축소
  → seccomp로 syscall 필터
  → LSM profile로 추가 접근 제어
  → overlay filesystem/rootfs로 파일 뷰 제공
  → veth/bridge/CNI로 네트워크 연결
~~~

컨테이너의 핵심 경계는 **host kernel을 공유한다**는 점이다. 컨테이너 안 process가 syscall을 하면 host kernel이 처리한다. 따라서 kernel 취약점, 위험한 capability, device mount, privileged container, hostPath mount는 trust boundary를 크게 약화한다.

## 10. VM과 KVM은 더 두꺼운 경계를 제공한다

**KVM(Kernel-based Virtual Machine)**은 Linux kernel의 virtualization 기능이다. KVM은 hardware virtualization extension을 사용해 guest OS를 실행하고, QEMU 같은 user space VMM이 device emulation과 관리 역할을 맡을 수 있다.

컨테이너와 VM 비교:

| 항목 | 컨테이너 | VM |
| --- | --- | --- |
| 커널 | host kernel 공유 | guest kernel 별도 |
| 시작 속도 | 대체로 빠름 | 대체로 느림 |
| 이미지 | rootfs와 app 중심 | disk image와 OS 전체 |
| 격리 경계 | namespace/cgroup/seccomp/LSM + host kernel | hardware virtualization + hypervisor |
| 운영 밀도 | 높음 | 상대적으로 낮음 |

VM이 항상 안전하고 컨테이너가 항상 위험하다는 뜻은 아니다. VM escape, device emulation bug, shared folder, agent, misconfiguration도 있다. 다만 kernel을 공유하는지 여부는 근본적인 차이다.

## 11. kernel attack surface를 줄인다는 말의 실제 의미

**attack surface**는 공격자가 상호작용할 수 있는 코드와 인터페이스의 총량이다. Linux host에서는 다음이 attack surface가 된다.

| 표면 | 예 |
| --- | --- |
| syscall | `io_uring`, `bpf`, `userfaultfd`, filesystem syscall |
| device driver | GPU, NIC, USB, block device |
| network stack | packet parsing, TCP/IP, netfilter |
| filesystem parser | ext4, xfs, overlayfs, FUSE |
| eBPF verifier/JIT | program load와 kernel hook |
| LSM/namespace/cgroup path | policy와 경계 처리 코드 |

줄이는 방법은 workload가 필요 없는 capability와 syscall, device, mount, network path를 제거하는 것이다. 하지만 기능을 줄이면 운영성도 줄 수 있다. 예를 들어 observability agent는 eBPF와 perf_event가 필요할 수 있고, storage plugin은 mount 관련 capability가 필요할 수 있다. 보안 정책은 “막기”만이 아니라 필요한 일을 가장 좁은 권한으로 허용하는 설계다.

## 12. eBPF 위치 잡기

eBPF는 kernel 안에서 검증된 작은 program을 특정 hook에 붙여 실행하는 기술이다. 네트워크, tracing, security observability에서 매우 중요하다. 다만 eBPF 자체는 컨테이너 격리의 한 조각일 수도 있고, 관측 도구일 수도 있고, 네트워크 datapath 구현일 수도 있다.

이 운영체제 장에서는 경계만 잡는다.

| 질문 | 여기서의 답 |
| --- | --- |
| eBPF는 user space인가 kernel space인가? | program은 user space에서 load하지만 kernel hook에서 실행된다. |
| 왜 위험할 수 있나? | kernel context에서 실행되므로 verifier, capability, LSM 제한이 중요하다. |
| 어디서 자세히 배우나? | 별도 네트워크/eBPF 교재에서 packet path, XDP, tc, cgroup-bpf, tracing을 다룬다. |

## 13. 안전한 관찰 실습

아래 명령은 현재 process의 UID/GID와 capability 관련 `/proc` 줄을 읽는다. 값을 바꾸지 않는다.

~~~bash
python3 - <<'PY'
import os

print("uid", os.getuid(), "gid", os.getgid())
with open("/proc/self/status", "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith(("CapInh:", "CapPrm:", "CapEff:", "CapBnd:", "NoNewPrivs:", "Seccomp:")):
            print(line.strip())
PY
~~~

해석: capability는 bit mask로 표시된다. 사람이 바로 읽기 어렵지만, “현재 process가 어떤 capability set을 갖는가”를 kernel이 추적한다는 사실을 확인할 수 있다.

## 14. 오개념 정리

| 오개념 | 바로잡기 |
| --- | --- |
| root는 항상 전능하다 | user namespace와 capability bounding set, LSM, seccomp가 제한할 수 있다. |
| namespace가 자원 사용량을 제한한다 | 이름 공간 분리는 namespace, 자원 제한은 cgroup이 담당한다. |
| seccomp가 있으면 안전한 sandbox다 | syscall attack surface를 줄일 뿐, 허용 syscall과 kernel bug는 남는다. |
| 컨테이너는 VM이다 | 컨테이너는 host kernel을 공유한다. |
| SELinux/AppArmor는 file permission의 다른 이름이다 | LSM 기반 MAC 정책으로 DAC 이후 추가 제한을 줄 수 있다. |
| capability 하나만 주면 좁은 권한이다 | 특히 `CAP_SYS_ADMIN`처럼 매우 넓은 capability가 있다. |

## 15. 해설 문제

1. 컨테이너 안에서 UID 0인데 host file을 못 읽는 이유는 무엇일 수 있는가?
   - user namespace mapping, mount namespace, DAC/ACL, dropped capability, LSM profile, seccomp, read-only mount, idmapped mount 등 여러 원인이 가능하다.

2. memory cgroup OOM과 system OOM은 왜 다르게 보이는가?
   - cgroup OOM은 특정 group limit 안에서 발생할 수 있다. host 전체 free memory가 남아 있어도 pod/container limit을 넘으면 죽을 수 있다.

3. `CAP_NET_ADMIN`을 컨테이너에 주면 어떤 위험이 생기는가?
   - network interface, routing, firewall 등 network namespace 안팎의 설정 변경 능력이 커진다. namespace 구성과 runtime 정책에 따라 host 영향 가능성을 검토해야 한다.

4. VM이 container보다 격리가 두꺼운 이유는?
   - guest kernel이 별도로 있고 hardware virtualization boundary를 지나야 한다. container는 syscall을 host kernel에 직접 요청한다.

## 16. 1차 참고 자료

- Linux man-pages: [capabilities(7)](https://man7.org/linux/man-pages/man7/capabilities.7.html), [namespaces(7)](https://man7.org/linux/man-pages/man7/namespaces.7.html), [clone(2)](https://man7.org/linux/man-pages/man2/clone.2.html), [setns(2)](https://www.man7.org/linux/man-pages/man2/setns.2.html)
- Linux Kernel Documentation: [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), [Linux Security Modules](https://docs.kernel.org/security/lsm.html), [AppArmor](https://docs.kernel.org/admin-guide/LSM/apparmor.html)
- Linux man-pages: [seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html), [proc(5)](https://www.man7.org/linux/man-pages/man5/proc.5.html)
- Linux Kernel Documentation: [KVM documentation](https://docs.kernel.org/virt/kvm/index.html), [BPF documentation](https://docs.kernel.org/bpf/)
