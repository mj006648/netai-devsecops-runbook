# Hardware Notes

Kubernetes 바깥의 물리 인프라 기록입니다. PSU, BMC/IPMI, NIC cabling, rack, PXE/UEFI provisioning, 서버 하드웨어 이슈를 정리합니다.

| Last update | Area | Topic | Document |
| --- | --- | --- | --- |
| 2026-09-23 | Inventory / GPU expansion | TwinX GPU 노드 5대 CPU·DIMM·NUMA·PCIe 실측, 기존 카드 점유와 추가 12장 장착 상한·병목 | [GPU 노드 증설 실측](inventory/twinx-gpu-node-expansion-2026-09-23.md) |
| 2026-09-22 | NPU | A7 SLOT10→18 이동 확인, 4장 NUMA1·Gen5 x16, binning·전력 제한·power-sense 경고 및 진단 범위 | [이동 후 진단](npu/a7-rngd-post-move-diagnostics-2026-09-22.md) |
| 2026-09-22 | Learning | 전기·비트·논리회로·CPU·RAM·PCIe·RAID·GPU/NPU·NIC·전원·냉각, NVLink·UALink·CXL 최신 기술과 A7 설계 실습 | [서버 하드웨어 학습 교재](learning/server-hardware/README.md) |
| 2026-09-21 | NPU / GPU / NIC | A7 GPU·NPU 슬롯 배치안, RAM 2/24 DIMM, 기존 200G NIC, 공유 대역폭·전원 조사 | [A7 증설 검토](npu/a7-expansion-plan-2026-09-21.md) |
| 2026-09-21 | NPU | A7 RNGD PCIe·NUMA 배치, SLOT10→18 이전 권고 및 binning·전력 제한 차이 | [NPU 작업일지](npu/a7-rngd-slot-numa-binning-2026-09-21.md) |
| 2026-07-13 | Provisioning | Supermicro E300의 KISS PXE 설치 중 HWE package 및 UEFI NVRAM/GRUB 실패 복구 | [E300 Ubuntu 24.04 PXE/UEFI recovery](provisioning/supermicro-e300-ubuntu-24-04-pxe-uefi-recovery-2026-07-13.md) |
| 2026-07-01 | Power | Supermicro SYS-210P-FRDN6T 외부 AC-to-48V DC PSU 불안정 및 AC 전환 문의 | [SYS-210P DC PSU troubleshooting](power/supermicro-sys-210p-dc-psu-2026-07-01.md) |

## Directories

- **[learning/server-hardware/](learning/server-hardware/README.md)** — 전기·비트·논리회로부터 A7 서버 설계까지: 읽기 전용 실습, 동작 추적·계산 문제·해설, 용어 사전
- **[inventory/](inventory/twinx-gpu-node-expansion-2026-09-23.md)** — GPU 노드별 실장 카드·PCIe 레인·NUMA·메모리와 증설 상한
- **[npu/](npu/)** — NPU 전용 작업일지: 장착, PCIe/NUMA, binning, 상태·진단·이전 검증

- **[provisioning/](provisioning/)** — KISS/PXE, Ubuntu autoinstall, BIOS/UEFI, GRUB, 첫 OS boot
- **[power/](power/)** — PSU, AC/DC conversion, rack power, vendor support 문의
