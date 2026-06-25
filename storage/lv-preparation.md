# 노드 재부팅 후 Ceph OSD가 올라오지 않음 — stale LVM PV 문제

## Symptom
- 스토리지 노드 예: `l40s`를 재부팅한 뒤 해당 노드의 OSD가 계속 `down` 상태다.
- `rook-ceph-osd-prepare-<node>` pod는 완료됐지만 OSD가 다시 올라오지 않는다.
- Host의 `pvs` / `vgs` 출력에 이전 bring-up에서 남은 VG/LV가 보이고,
  Rook이 사용해야 하는 disk에 묶여 있다.

## Diagnosis
```bash
# host에서 확인
sudo pvs
sudo vgs
sudo lvs
sudo ceph-volume lvm list

# cluster에서 prepare job log 확인
kubectl -n rook-ceph logs job/rook-ceph-osd-prepare-<node>
```

Prepare job은 이전 OSD lifecycle에서 남은 LVM metadata가 있는 disk를 자동으로 claim하지 않는다.
데이터 손상을 피하기 위해 skip한다.

## Root cause
Rook-Ceph의 OSD prepare 경로는 raw block device 위에 자체 LV를 만드는 것을 전제로 한다.
이전 deployment의 LVM metadata가 disk에 남아 있으면 prepare가 해당 disk를 지우지 않고 건너뛴다.

## Fix — stale LVM을 지우고 OSD를 다시 prepare한다

> **파괴적 작업**: 해당 OSD의 데이터를 삭제한다. 이미 OSD가 유실됐고 cluster에 충분한 replica가 있거나,
> 전체 재설치를 진행하는 경우에만 실행한다.

```bash
# 1. Rook이 남긴 LV / VG / PV 제거
sudo lvremove -y /dev/<vg>/<lv>
sudo vgremove -y <vg>
sudo pvremove -y /dev/<disk>

# 2. 남은 GPT / Ceph signature 제거
sudo wipefs -a /dev/<disk>
sudo sgdisk --zap-all /dev/<disk>
sudo dd if=/dev/zero of=/dev/<disk> bs=1M count=100

# 3. OSD prepare job 재시작
kubectl -n rook-ceph delete job -l app=rook-ceph-osd-prepare,rook-ceph-osd-prepare-node=<node>
# operator가 prepare job을 다시 만들고 disk를 claim한다.
```

OSD가 올라오는지 확인한다.

```bash
kubectl -n rook-ceph get pods -l app=rook-ceph-osd -o wide | grep <node>
ceph -s
```

## Prevention
- 스토리지 노드를 오래 내리기 전 어떤 disk가 어떤 OSD인지 `ceph-volume lvm list`로 기록한다.
  나중에 reattach 판단이 쉬워진다.
- 단계적 재설치가 필요하면 모든 OSD를 한 번에 올리지 말고 `incidents/`에 기록된 활성화 순서를 따른다.
