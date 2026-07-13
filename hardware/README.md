# Hardware Notes

Kubernetes 바깥의 물리 인프라 기록입니다. PSU, BMC/IPMI, NIC cabling, rack, PXE/UEFI provisioning, 서버 하드웨어 이슈를 정리합니다.

| Last update | Area | Topic | Document |
| --- | --- | --- | --- |
| 2026-07-13 | Provisioning | Supermicro E300의 KISS PXE 설치 중 HWE package 및 UEFI NVRAM/GRUB 실패 복구 | [E300 Ubuntu 24.04 PXE/UEFI recovery](provisioning/supermicro-e300-ubuntu-24-04-pxe-uefi-recovery-2026-07-13.md) |
| 2026-07-01 | Power | Supermicro SYS-210P-FRDN6T 외부 AC-to-48V DC PSU 불안정 및 AC 전환 문의 | [SYS-210P DC PSU troubleshooting](power/supermicro-sys-210p-dc-psu-2026-07-01.md) |

## Directories

- **[provisioning/](provisioning/)** — KISS/PXE, Ubuntu autoinstall, BIOS/UEFI, GRUB, 첫 OS boot
- **[power/](power/)** — PSU, AC/DC conversion, rack power, vendor support 문의
