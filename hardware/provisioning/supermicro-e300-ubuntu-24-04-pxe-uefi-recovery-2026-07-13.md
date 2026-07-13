# Supermicro E300 Ubuntu 24.04 PXE/UEFI Recovery

## Current status

- Date: `2026-07-13`
- Status: recovered
- Environment: KISS 기반 UEFI PXE 및 Ubuntu Server 24.04.4 autoinstall
- Affected asset: `e300-3/control3`
- Result: Subiquity 전체 설치 완료, 새 UEFI `Ubuntu` 항목 등록, 설치된 OS의 SSH 응답 및 Management `Commissioning` 진입 확인

이 문서는 공개 저장소에 두므로 내부 IP, SSH/IPMI credential, serial number는 기록하지 않는다.

## Scope

- System: Supermicro `SYS-E300-8D`
- Mainboard: Supermicro `X10SDV-TP8F`
- Firmware observed during diagnosis: AMI BIOS `1.0b` (`2016-11-21`)
- Target disk: Samsung SSD 960 PRO NVMe
- Installer: Ubuntu Server 24.04.4 live-server ISO
- Provisioning: KISS가 제공하는 PXE kernel/initrd, autoinstall cloud-config, ISO 및 후속 등록 작업
- Boot mode: UEFI

이 장애는 Kubernetes 자체보다 앞선 KISS/PXE, Ubuntu installer, UEFI firmware 계층에서 발생했다.

## Symptom

첫 번째 실패는 Subiquity/curtin의 `curthooks` 단계에서 HWE kernel meta package를 찾지 못한 것이었다.

```text
E: Unable to locate package linux-generic-hwe-24.04
E: Couldn't find any package by glob 'linux-generic-hwe-24.04'
E: Couldn't find any package by regex 'linux-generic-hwe-24.04'
```

HWE 선택을 우회한 뒤에는 kernel 설치를 통과했지만 GRUB가 UEFI boot entry를 등록하지 못했다.

```text
grub-install: warning: Cannot set EFI variable Boot000E.
grub-install: warning: efivarfs_set_variable: writing to fd 9 failed: Input/output error.
grub-install: error: failed to register the EFI boot entry: Input/output error.
```

설치 실패 후 PXE live environment에 임시 계정을 만들거나 `/target`의 GRUB와 late-command를 수동 실행하면 OS가 부팅될 수는 있었다. 그러나 이 방식은 Subiquity가 완료 상태에 도달하지 않아 Management의 local account 정보와 Kubernetes bootstrap 상태가 정상 설치와 달라질 수 있었다.

## Diagnosis

### 1. 최신 installer crash 풀기

다음 명령은 PXE live environment에서 실행한다. `/tmp`에만 진단 파일을 풀며 대상 OS를 수정하지 않는다.

```bash
CR=$(ls -t /var/crash/*.install_fail.crash | head -1)
OUT=$(mktemp -d /tmp/install-fail-check.XXXXXX)
apport-unpack "$CR" "$OUT"

printf 'crash=%s\noutput=%s\n' "$CR" "$OUT"
```

kernel 선택과 직접 실패 지점을 확인한다.

```bash
grep -n -A3 -B2 '^kernel:' "$OUT/CurtinCurthooksConfig"
grep -n -E 'linux-generic-hwe-24.04|Unable to locate package' "$OUT/CurtinLog"
grep -n -E 'kernel-meta-package|linux-generic-hwe-24.04' "$OUT/InstallerServerLog"
```

이 사례에서는 다음 설정이 생성됐다.

```yaml
kernel:
  package: linux-generic-hwe-24.04
```

Subiquity log에는 cloud-config의 kernel 항목이 아니라 live initrd의 marker 때문에 HWE가 선택됐다고 기록됐다.

```text
Using kernel linux-generic-hwe-24.04 due to /run/kernel-meta-package
```

따라서 autoinstall에서 HWE 옵션을 단순히 제거하는 것만으로는 GA kernel이 선택되지 않을 수 있다.

### 2. installer network 및 APT source 확인

```bash
grep -n -E 'addr_change (NEW|DEL)|default routes|has_network|Skipping mirror' \
  "$OUT/InstallerServerLog"

cat /target/etc/apt/sources.list
cat /run/kernel-meta-package
```

확인된 순서는 다음과 같았다.

1. initramfs 단계에서는 PXE NIC에 주소와 default route가 있었다.
2. autoinstall의 DHCP netplan을 적용하면서 기존 주소와 route가 잠시 제거됐다.
3. Subiquity가 이 시점에 `has_network False`를 기록했다.
4. 약 2초 뒤 DHCP 주소와 default route가 복구됐지만 mirror check는 이미 offline 경로를 선택했다.
5. 대상 APT source에는 `file:///cdrom noble main restricted`만 남았다.
6. ISO에는 GA kernel package가 있었지만 요청한 HWE meta package는 없어서 설치가 중단됐다.

즉 직접 오류는 HWE package 부재였고, 그 package를 외부 mirror에서 받지 못하게 한 선행 조건은 installer network 전환 시점의 offline 판정이었다. 케이블이 계속 끊겨 있거나 NIC link가 영구적으로 down인 상황과는 구분해야 한다.

### 3. GRUB 및 UEFI boot entry 확인

GRUB 실패는 다음처럼 추출한다.

```bash
grep -n -E 'grub|efivar|Input/output error|failed to register' \
  "$OUT/CurtinLog" | tail -120
```

PXE live environment에 `efibootmgr`가 없지만 `/target`에 package가 설치돼 있다면 다음처럼 조회할 수 있다.

```bash
LD_LIBRARY_PATH=/target/usr/lib/x86_64-linux-gnu \
  /target/usr/bin/efibootmgr -v

lsblk -no NAME,PARTUUID,FSTYPE,MOUNTPOINT /dev/nvme0n1
find /target/boot/efi/EFI -maxdepth 2 -type f -printf '%P\n' | sort
```

이 사례에서는 firmware의 `ubuntu`와 `UEFI OS` 항목이 이전 설치의 EFI partition GUID를 가리키고 있었다. 반복 설치로 새로 생성된 EFI partition은 다른 GUID를 사용했다. GRUB가 오래된 `Boot000E`를 갱신하려 할 때 firmware가 write 요청을 `Input/output error`로 거부했다.

## Root cause

장애는 두 단계로 구성됐다.

### Phase 1: KISS PXE와 installer network/HWE package 불일치

- KISS PXE가 Ubuntu 24.04.4 HWE live kernel/initrd로 부팅했다.
- `/run/kernel-meta-package`가 `linux-generic-hwe-24.04`를 지정했다.
- autoinstall network 적용 중 default route가 잠시 제거됐고 Subiquity가 offline으로 판단했다.
- offline install source인 ISO에는 요청한 HWE meta package가 없었다.
- `curthooks`가 kernel package 설치 전에 실패했다.

### Phase 2: 재설치 후 남은 stale UEFI NVRAM entry

- 이전 설치에서 생성된 `ubuntu`와 `UEFI OS` NVRAM entry가 과거 EFI partition GUID를 참조했다.
- 새 설치는 EFI partition을 다시 만들면서 PARTUUID가 변경됐다.
- GRUB가 기존 boot entry를 현재 EFI partition으로 갱신하는 과정에서 firmware write가 실패했다.
- stale entry를 제거한 뒤에는 설치기가 새 `Boot0000: Ubuntu`를 만들었고, entry의 GUID와 현재 EFI PARTUUID가 일치했다.

## Fix

### Safety rules

- 실제 삭제 또는 재설치 전에 현재 `efibootmgr -v`와 `BootOrder`를 기록한다.
- PXE IPv4 entry와 Built-in EFI Shell entry는 삭제하지 않는다.
- 아래 boot number는 이 사건의 값이다. 다른 장비에서 `000E`, `000F`를 그대로 삭제하지 않는다.
- PXE live environment의 임시 사용자를 target OS 사용자로 오해하지 않는다.
- `useradd`, GRUB 수동 설치, late-command 수동 실행으로 완료 상태를 흉내 내지 않는다.
- `/run/kernel-meta-package` 변경은 RAM에만 남으므로 full reboot 전에 사라진다.

### 1. 이번 boot에서 GA kernel 선택

root shell에서 현재 값을 확인한다.

```bash
cat /run/kernel-meta-package
```

이 장비에서 KISS/PXE 설정이 수정되기 전 사용한 one-shot workaround는 다음과 같다.

```bash
printf 'linux-generic\n' > /run/kernel-meta-package
cat /run/kernel-meta-package
```

`linux-generic`은 Ubuntu 24.04 ISO가 제공하는 GA kernel이다. 이 장비처럼 오래된 hardware에서 HWE가 필수라는 근거가 없다면 설치 복구에 사용할 수 있다. 운영 환경이 HWE를 요구하거나 후속 단계에서 HWE로 전환한다면 최종 kernel 상태를 별도로 검증한다.

### 2. stale UEFI disk entry 제거

먼저 firmware entry와 현재 EFI PARTUUID를 비교한다.

```bash
LD_LIBRARY_PATH=/target/usr/lib/x86_64-linux-gnu \
  /target/usr/bin/efibootmgr -v

lsblk -no NAME,PARTUUID,FSTYPE,MOUNTPOINT /dev/nvme0n1
```

이 사례에서 삭제한 항목은 이전 EFI partition을 가리키던 `Boot000E: ubuntu`와 `Boot000F: UEFI OS`였다. 삭제는 root 권한으로 한 항목씩 진행하고 매번 `BootOrder`를 재확인했다.

```bash
LD_LIBRARY_PATH=/target/usr/lib/x86_64-linux-gnu \
  /target/usr/bin/efibootmgr -b 000E -B

LD_LIBRARY_PATH=/target/usr/lib/x86_64-linux-gnu \
  /target/usr/bin/efibootmgr -v
```

첫 항목과 PXE entry 보존을 확인한 뒤 두 번째 stale entry를 제거했다.

```bash
LD_LIBRARY_PATH=/target/usr/lib/x86_64-linux-gnu \
  /target/usr/bin/efibootmgr -b 000F -B

LD_LIBRARY_PATH=/target/usr/lib/x86_64-linux-gnu \
  /target/usr/bin/efibootmgr -v
```

### 3. Subiquity 전체 설치 재시작

수동으로 `/target`을 완성하지 않고 Subiquity의 restart API로 autoinstall 전체를 다시 실행했다.

```bash
curl --max-time 5 --unix-socket /run/subiquity/socket \
  -X POST http://localhost/meta/restart
```

server가 process를 교체하면서 다음 응답이 나올 수 있다. restart 요청이 적용됐는지 status API로 확인한다.

```text
curl: (52) Empty reply from server
```

```bash
curl --max-time 3 --unix-socket /run/subiquity/socket \
  http://localhost/meta/status
```

`ERROR`가 아니라 `RUNNING`이면 오류 shell을 종료해 installer output으로 돌아간다.

```bash
exit
```

이 restart는 실패한 target 위에서 curthooks만 이어서 실행하는 방식이 아니다. 동일한 live ISO와 KISS cloud-config를 재사용하되 storage 구성, OS extract, kernel, GRUB, update, late-command를 다시 실행한다.

### 4. 첫 disk boot

설치 완료 후 firmware가 PXE를 다시 강제하면 방금 설치한 disk가 다시 초기화될 수 있다. IPMI의 persistent PXE override를 해제하고 다음 순서로 disk entry를 선택한다.

1. 새로 등록된 `Ubuntu`
2. `Ubuntu`가 없거나 실패하면 같은 disk의 `UEFI OS` fallback

PXE network, `IP4 Intel...`, IBA, Built-in EFI Shell은 target OS 부팅 항목이 아니다. BIOS 화면에 같은 SSD의 `Ubuntu`, `ubuntu`, `UEFI OS`가 함께 보여도 서로 다른 OS 세 개를 의미하지 않는다. UEFI NVRAM entry와 fallback path가 중복 표시된 것이다.

## Verification

### Installer state

```bash
curl --max-time 3 --unix-socket /run/subiquity/socket \
  http://localhost/meta/status
```

이 사례에서는 `RUNNING`, `UU_RUNNING`을 거쳐 installer가 자체적으로 reboot를 실행했다.

```text
The system will reboot now!
```

### UEFI entry와 현재 partition 일치

```bash
LD_LIBRARY_PATH=/target/usr/lib/x86_64-linux-gnu \
  /target/usr/bin/efibootmgr -v

lsblk -no NAME,PARTUUID,FSTYPE,MOUNTPOINT /dev/nvme0n1
```

복구 후에는 다음 조건을 확인했다.

- 새 `Boot0000: Ubuntu`가 생성됐다.
- `BootOrder`의 첫 항목이 `0000`이었다.
- `Boot0000`이 참조한 GPT partition GUID와 현재 EFI PARTUUID가 일치했다.
- `EFI/BOOT/BOOTX64.EFI`, `EFI/ubuntu/grubx64.efi`, `EFI/ubuntu/shimx64.efi`가 존재했다.

### OS 및 KISS 후속 상태

계정 없이도 SSH banner와 host key가 올라왔는지 확인할 수 있다.

```bash
ssh-keyscan -T 5 <node-address>
```

최종 확인 항목:

- 설치된 Ubuntu의 OpenSSH가 응답한다.
- KISS/Management sheet에서 node가 `Commissioning`을 거쳐 정상 상태로 전환된다.
- PXE live environment에 만든 임시 계정은 target OS에 남지 않는다.
- 운영 계정과 Kubernetes bootstrap은 KISS의 정상 후속 흐름에서 생성 또는 관리한다.

## Prevention

- KISS PXE entry에서 GA와 HWE kernel/initrd를 명확히 구분하고 선택한 live kernel과 target APT source가 호환되는지 검증한다.
- offline 설치를 지원하려면 KISS local ISO 또는 APT mirror에 선택한 kernel meta package를 제공한다.
- autoinstall에서 GA kernel을 의도한다면 kernel 항목을 생략하는 것에 의존하지 말고 `linux-generic`을 명시한다.
- installer netplan 적용 후 주소와 default route가 안정화된 다음 mirror 판정을 수행하도록 KISS cloud-config와 network 흐름을 점검한다.
- 반복 UEFI 설치 전 기존 disk boot entry의 partition GUID가 현재 disk와 일치하는지 확인한다.
- IPMI PXE override는 one-shot으로 사용하고 설치 완료 후 persistent override가 남지 않게 한다.
- target OS의 계정, GRUB, late-command를 수동으로 조립한 상태를 정상 PXE 완료로 간주하지 않는다.
- 오래된 firmware의 NVRAM write 문제가 반복되면 BIOS update 가능성과 `grub.update_nvram: false` plus fallback boot 정책을 별도 change plan으로 검토한다.

## Remaining risks

- KISS PXE의 HWE 선택과 installer network timing이 영구 수정되지 않으면 다른 node에서 같은 HWE package 오류가 재발할 수 있다.
- `linux-generic` one-shot workaround는 reboot하면 사라지며 KISS template의 영구 변경이 아니다.
- GA kernel로 첫 부팅한 뒤 운영 정책이 HWE를 요구하면 HWE 전환과 Kubernetes node 상태를 별도로 검증해야 한다.
- firmware가 다시 stale UEFI entry를 만들거나 NVRAM write를 거부할 가능성이 있다.
- Management가 `Commissioning`에서 최종 정상 상태로 전환되는지 별도 운영 확인이 필요하다.

