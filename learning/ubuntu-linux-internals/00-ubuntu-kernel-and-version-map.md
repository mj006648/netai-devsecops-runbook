# 00. Ubuntu·Linux kernel·version 지도

[← 목차](README.md) · [다음: boot·package·systemd →](01-boot-packages-and-systemd.md)

Ubuntu 화면에서 프로그램 하나를 실행하면 “Ubuntu가 실행했다”고 말하기 쉽다. 그러나 실제로는 디스크의 실행 파일, 사용자 공간 라이브러리, Linux 커널, 장치 드라이버와 하드웨어가 서로 다른 책임을 맡는다. 이 구분을 모르면 `Ubuntu 24.04`, `Linux 6.8`, `glibc 2.x`, `linux-image-...`처럼 서로 다른 버전 숫자를 한 줄에 놓고 “어느 것이 진짜 버전인가?”라고 묻게 된다. 답은 하나가 아니다. 각 숫자가 가리키는 객체와 수명이 다르다.

## 1. 먼저 물건의 위치부터 구분한다

**Linux 커널(kernel)**은 CPU의 높은 권한 모드에서 실행되며 프로세스, 가상 메모리, 파일시스템, 네트워크와 장치를 중재하는 소프트웨어다. 애플리케이션이 디스크 제어기 레지스터를 직접 건드리지 않고 `read()` 같은 시스템 호출을 하는 이유는 커널이 여러 프로그램 사이의 자원 공유와 접근 권한을 한곳에서 판단해야 하기 때문이다. 커널 이미지는 보통 `/boot` 아래 파일로 설치되지만, 부팅 뒤 실제로 실행되는 커널은 메모리에 올라간 코드와 상태다.

**사용자 공간(user space)**은 일반 애플리케이션과 라이브러리가 실행되는 낮은 권한 영역이다. shell, Python, systemd의 여러 보조 프로세스, 웹 서버는 사용자 공간 프로그램이다. 사용자 공간이라는 말은 “사용자가 직접 만든 프로그램”이라는 뜻이 아니라 커널 권한과 분리된 실행 영역이라는 뜻이다.

**Ubuntu 배포판(distribution)**은 Linux 커널 하나의 이름이 아니다. installer, APT 저장소, Debian 형식 package, systemd 설정, glibc와 shell, 보안 갱신 정책, 지원 기간을 하나의 운영 환경으로 묶은 배포물이다. 같은 Linux kernel 계열을 사용해도 Ubuntu와 다른 배포판은 기본 설정, package 버전과 패치 정책이 다를 수 있다.

**package**는 파일과 버전 metadata, dependency, 설치·제거 과정에서 필요한 script를 배포하는 단위다. kernel도 `linux-image-*`, module, header, meta-package 같은 여러 package로 설치된다. package는 디스크에 놓인 배포 단위이고, process는 그 파일을 읽어 메모리에서 실행되는 인스턴스다. 둘을 같은 것으로 보면 “업데이트했는데 왜 실행 중 버전은 그대로인가?”를 설명하지 못한다.

![Ubuntu stack](assets/ubuntu-stack.svg)

```mermaid
flowchart TD
    APP[사용자 공간 애플리케이션] -->|함수 호출| LIB[glibc·언어 runtime]
    LIB -->|system call ABI| K[실행 중 Linux kernel]
    K -->|driver 요청| DRV[커널 장치 driver]
    DRV --> HW[CPU·memory·NIC·disk]
    ARCH[Ubuntu package archive] -->|deb와 metadata| APT[APT·dpkg]
    APT -->|디스크 파일 설치| APP
    APT -->|다음 부팅용 image 설치| BOOT[/boot의 kernel·initramfs]
    BOOT -->|재부팅 때 선택| K
```

여기서 **ABI(application binary interface)**는 이미 컴파일된 프로그램과 커널이 register, 번호, 데이터 배치 같은 이진 수준 규칙으로 대화하는 약속이다. system call ABI가 안정적이기 때문에 오래전에 빌드한 프로그램도 새 커널에서 실행될 수 있다. 반면 커널 내부 module ABI는 같은 방식으로 영구 고정된 약속이 아니며 Ubuntu package의 build·ABI 식별과 맞아야 할 수 있다.

## 2. 한 번의 `read()` 요청을 층별로 끝까지 따라가기

사용자가 shell에서 `cat report.txt`를 실행했다고 하자. shell은 디스크의 `cat` 실행 파일을 찾아 새 process로 실행한다. 동적 linker는 `cat`이 사용하는 glibc 같은 shared library를 주소 공간에 연결한다. `cat`이 C library의 `read()` wrapper를 호출하면 library는 system call 번호, file descriptor, buffer 주소와 길이를 CPU가 약속한 register에 넣고 커널로 진입한다.

커널은 현재 task가 가진 file descriptor table에서 대상 open file을 찾는다. 파일시스템과 page cache를 확인하고, 필요한 데이터가 메모리에 없으면 block I/O를 장치 driver로 보낸다. driver는 실제 저장장치와 통신한다. 데이터가 준비되면 커널은 허용된 사용자 buffer에 바이트를 복사하거나 매핑하고 반환값을 설정한다. CPU는 다시 같은 task의 사용자 공간 명령을 실행한다. `cat`은 반환된 바이트 수만큼 표준 출력에 쓴다.

이 흐름에서 Ubuntu package archive는 매 요청마다 참여하지 않는다. archive와 APT는 `cat`, glibc, kernel image를 설치하는 배포 단계에 참여했다. 실제 `read()` 순간에는 메모리에 올라간 사용자 코드와 현재 실행 중인 커널이 동작한다.

| 단계 | 주체와 위치 | 입력 | 중간 상태 | 관찰 가능한 결과 |
| --- | --- | --- | --- | --- |
| 1 | shell, 사용자 공간 | 명령 문자열 | 실행 파일 경로·인자 결정 | 새 PID 생성 가능 |
| 2 | loader, 사용자 공간 | ELF와 library 목록 | 주소 공간에 code·data mapping | `/proc/PID/maps` |
| 3 | CPU와 kernel entry | fd·buffer 주소·길이 | 현재 task가 kernel mode에서 실행 | system call trace |
| 4 | VFS·filesystem | open file과 offset | page cache hit 또는 I/O 대기 | task 상태·I/O 통계 |
| 5 | driver·장치 | block 요청 | DMA·interrupt·완료 처리 | device 통계 |
| 6 | kernel과 `cat` | 완료 바이트·오류 | 사용자 buffer와 반환값 | 화면 출력 또는 오류 |

**system call**은 프로그램이 커널 서비스에 진입하는 정해진 요청 경로다. 일반 함수 호출처럼 보이지만 권한 경계를 넘으며, 커널은 사용자 주소와 길이를 그대로 믿지 않고 접근 가능 여부를 검사한다. `read()`가 라이브러리 함수 이름이면서 system call 이름으로도 보이는 이유는 glibc wrapper가 애플리케이션에 편한 호출 규약을 제공하고 실제 커널 진입을 수행하기 때문이다.

## 3. 다섯 가지 버전이 답하는 질문

| 대상 | 예시 형태 | 객체의 위치 | 답하는 질문 |
| --- | --- | --- | --- |
| Ubuntu release | `24.04 LTS` | `/etc/os-release`, archive 정책 | 어떤 userland와 지원 정책 계열인가? |
| 실행 커널 release | `6.x.y-zz-generic` | 메모리의 현재 커널 | 지금 어떤 커널 build가 CPU를 관리하는가? |
| kernel image package | `linux-image-...` | dpkg DB와 `/boot` | 어떤 부팅 가능 image가 설치됐는가? |
| 일반 package version | upstream+Ubuntu revision | dpkg·APT metadata | 어느 source와 Ubuntu patch build인가? |
| 커널 config·feature | `CONFIG_*`, runtime probe | build 설정과 실행 상태 | 특정 기능을 실제 사용할 조건이 있는가? |

`/etc/os-release`는 root filesystem의 배포판 신원을 설명한다. `uname -r`은 현재 system call에 답하는 실행 커널의 release 문자열을 보여 준다. 컨테이너에서는 root filesystem이 Ubuntu 24.04여도 커널은 host가 제공하므로 둘의 계열이 자연스럽게 다를 수 있다.

package version의 upstream 번호가 오래돼 보인다고 보안 수정이 없다고 단정할 수도 없다. **backport**는 새 upstream release 전체를 가져오지 않고 필요한 수정 patch를 기존 지원 source 계열에 적용하는 방식이다. 반대로 어떤 수정이 backport됐다는 사실만으로 새 upstream release의 모든 기능이 들어왔다고 볼 수도 없다. 정확한 판단에는 Ubuntu 보안 공지, package changelog와 실제 build를 함께 본다.

## 4. GA·HWE·flavour는 선택 경로다

**GA(general availability) kernel**은 해당 Ubuntu release의 기본 장기 지원 kernel 경로다. **HWE(hardware enablement) stack**은 더 새로운 hardware 지원을 위해 이후 kernel과 graphics stack으로 이동할 수 있는 경로다. HWE라는 이름은 “무조건 더 빠르다”나 “항상 더 안정적이다”라는 등급이 아니다. 새 장치 지원을 얻는 대신 driver 동작과 out-of-tree module 호환을 다시 확인해야 한다.

Ubuntu 공식 자료 기준으로 24.04 LTS의 GA kernel 계열은 6.8이다. Desktop은 기본적으로 HWE rolling stack을 따르고 Server는 기본 GA이며 HWE를 선택할 수 있다. 기존 문서가 2026-10-11에 확인한 공식 lifecycle 표에는 24.04.5 HWE와 26.04.0 기본 kernel을 7.0 계열로 표시한다. 이 표는 현재 이 문서를 읽는 host의 설치 상태가 아니며, 실제 release·flavour·meta-package·지원 서비스 조건은 그 host에서 다시 확인해야 한다.

| 경로 | 공식 표에 적힌 계열·시점 | 해석할 때 붙일 조건 |
| --- | --- | --- |
| 24.04.0 LTS GA | 6.8, 2024년 4월 | GA meta-package와 실제 boot image 확인 |
| 24.04.5 LTS HWE | 7.0, 2026년 8월 | HWE 전환·flavour·개별 EOL 확인 |
| 26.04.0 LTS 기본 | 7.0, 2026년 4월 | 24.04의 같은 숫자 package와 동일하다고 가정 금지 |

`generic`, cloud, low-latency 같은 **flavour**는 target workload와 kernel config가 다른 build 계열이다. `amd64`, `arm64`는 CPU instruction architecture다. release 문자열 일부가 같아도 다른 architecture의 binary를 실행할 수 없고, 외부 module은 해당 build의 header와 ABI 조건을 맞춰야 한다.

## 5. kernel update 요청을 시간순으로 추적하기

관리자가 새 kernel package를 설치하는 두 번째 예를 보자. A가 현재 실행 중인 커널이고 B가 새 image다.

| 시각 | 디스크의 package 상태 | bootloader 선택 | 메모리에서 실행 중 | 관리자가 볼 의미 |
| ---: | --- | --- | --- | --- |
| 09:00 | A 설치 | A | A | 현재와 디스크가 일치 |
| 09:10 | A와 B 설치 | 아직 A entry | A | 업데이트 설치, 적용 전 |
| 12:00 | A와 B 설치 | B 선택 | B | 재부팅 뒤 새 build 적용 |
| 12:05 | A와 B 설치 | 장애로 A 선택 | A | rollback, B 파일은 남음 |

APT는 B의 파일과 module, initramfs·boot entry 관련 상태를 디스크에 준비한다. 그러나 현재 CPU는 A의 커널 코드와 자료 구조를 계속 실행한다. 전체 kernel image 교체에는 bootloader가 다음 부팅에서 B를 메모리에 load하는 과정이 필요하다. livepatch는 일부 함수 수정의 런타임 적용 경로지만 모든 자료 구조와 driver를 새 image로 바꾸는 일반 재부팅과 같지 않다.

이 차이 때문에 “package 설치 성공”, “재부팅 성공”, “새 kernel로 부팅”, “필요 기능 사용 가능”을 네 상태로 나눠 관찰한다. B가 설치됐어도 bootloader가 A를 골랐을 수 있고, B로 부팅했어도 필요한 `CONFIG_*`, firmware, device, library가 없을 수 있다.

## 6. 읽기 전용 관측과 출력 해석

다음 명령은 host 설정을 바꾸지 않는 관측 예시이며 이 교재 작성 과정에서 실행한 결과가 아니다.

```bash
uname -r
cat /etc/os-release
dpkg-query -W 'linux-image*' 'linux-generic*'
apt-cache policy linux-generic linux-generic-hwe-24.04
```

```text
$ uname -r
6.x.y-zz-generic

$ cat /etc/os-release
NAME="Ubuntu"
VERSION_ID="..."
```

`uname -r` 한 줄은 현재 실행 build를 식별하지만 지원 종료일, HWE 설치 의도, 기능 config를 모두 알려 주지 않는다. `dpkg-query`는 설치 기록을 보여 주므로 여러 image가 동시에 나올 수 있다. `apt-cache policy`의 candidate는 설치 가능한 후보이지 현재 메모리에 실행 중인 code가 아니다. 관측 명령도 컨테이너 안인지 host인지에 따라 바라보는 root filesystem이 다를 수 있다.

## 7. 조건을 바꾸면 생기는 실패

새 NIC가 kernel B의 driver를 요구하는데 package만 설치하고 재부팅하지 않으면 A에는 그 driver가 없어 장치가 동작하지 않는다. 반대로 B로 재부팅했지만 외부 DKMS module이 B용으로 빌드되지 않았다면 그 module에 의존한 장치가 사라질 수 있다. 기능 문서가 최신 kernel에 존재해도 현재 config에서 꺼졌거나 architecture가 다르면 사용할 수 없다.

컨테이너 안 `/etc/os-release`만 보고 host kernel 취약 여부를 판정하면 틀릴 수 있다. WSL과 VM도 kernel 공급 주체와 부팅 경로가 bare metal Ubuntu와 다르므로 같은 명령 결과의 운영 의미가 달라진다.

최신 문서를 읽을 때는 “upstream에 API가 문서화됨 → Ubuntu package에 포함됨 → 현재 image로 부팅함 → config와 hardware 조건 충족 → runtime probe 성공”이라는 다섯 단계를 구분한다. 예를 들어 최신 kernel 문서의 io_uring zero-copy receive는 NIC의 header/data split과 flow steering 같은 조건을 요구한다. 문서가 있다는 사실만으로 모든 Ubuntu NIC에서 복사 없는 수신이 된다는 뜻이 아니다. FUSE의 io_uring 경로도 최신 문서가 개발 중이라고 밝히는 동안에는 안정 지원 기능으로 단정하지 않는다.

## 8. 문제와 해설

### 문제 1

`/etc/os-release`는 Ubuntu 24.04인데 `uname -r`은 host가 설치한 다른 계열이다. 모순인가?

**해설:** 컨테이너라면 모순이 아니다. 전자는 컨테이너 root filesystem의 userland 신원이고, 후자는 system call을 처리하는 공유 host kernel이다. 관찰 위치를 먼저 기록해야 한다.

### 문제 2

`apt`로 새 `linux-image` 설치가 성공했다. 새 커널 기능을 즉시 사용해도 된다고 판단할 수 있는가?

**해설:** 아니다. 현재 커널은 재부팅 전까지 옛 image일 수 있다. 재부팅 뒤 `uname -r`, boot log, config, 필요한 module·firmware와 runtime feature probe를 확인한다.

### 문제 3

package의 upstream 숫자가 취약 버전처럼 보인다. 숫자만으로 취약하다고 판정하면 안 되는 이유는?

**해설:** 배포판이 보안 patch를 기존 계열에 backport했을 수 있다. Ubuntu 보안 공지와 package revision·changelog를 확인한다. 반대로 비슷한 높은 숫자만으로 모든 patch와 설정을 보장하지도 않는다.

### 문제 4

HWE kernel이 GA보다 항상 좋은가?

**해설:** 아니다. 새 hardware와 driver를 지원할 수 있지만 driver 행동 변화, 외부 module 호환과 전환 일정이 달라진다. 필요한 hardware, 지원 경로와 검증 결과로 선택한다.

### 문제 5

동일한 `7.0` 문자열이 두 Ubuntu release 표에 있다. 같은 binary와 지원 조건인가?

**해설:** 아니다. release, package build, config, architecture, flavour와 archive 정책이 다를 수 있다. 전체 package 식별자와 공식 lifecycle을 각각 확인한다.

## 공식 자료

- [Ubuntu kernel lifecycle and enablement stack](https://ubuntu.com/kernel/lifecycle)
- [Ubuntu HWE kernels](https://documentation.ubuntu.com/kernel/reference/hwe-kernels/)
- [Ubuntu release cycle](https://ubuntu.com/about/release-cycle)
- [Linux kernel documentation](https://docs.kernel.org/)
- [io_uring zero-copy receive](https://kernel.org/doc/html/latest/networking/iou-zcrx.html)
- [FUSE over io_uring 개발 문서](https://kernel.org/doc/html/latest/filesystems/fuse/fuse-io-uring.html)

[← 목차](README.md) · [다음: boot·package·systemd →](01-boot-packages-and-systemd.md)
