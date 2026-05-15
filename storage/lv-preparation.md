# Ceph OSDs won't come up after node reboot — stale LVM PVs

## Symptom
- After rebooting a storage node (e.g. `l40s`), its OSDs stay `down`.
- `rook-ceph-osd-prepare-<node>` pod completes but no OSDs come back.
- `pvs` / `vgs` on the host shows the old VGs/LVs from the previous
  bring-up still present and tied to disks Rook expects to consume.

## Diagnosis
```bash
# On the host
sudo pvs
sudo vgs
sudo lvs
sudo ceph-volume lvm list

# From the cluster
kubectl -n rook-ceph logs job/rook-ceph-osd-prepare-<node>
```
The prepare job will refuse to claim disks that already have LVM metadata
from a previous OSD lifetime.

## Root cause
Rook-Ceph's OSD prepare path expects to create its own LVs on raw block
devices. If LVM metadata from a previous deployment still exists on those
disks, prepare skips them rather than risk wiping data.

## Fix — wipe stale LVM and re-prepare OSDs
> **Destructive**: this destroys the data on those OSDs. Only run when the
> OSDs are already lost (e.g. after a rebuild) and the cluster has enough
> healthy replicas elsewhere — or when you're doing a full reinstall.

```bash
# 1. Remove the LVs / VGs / PVs Rook left behind
sudo lvremove -y /dev/<vg>/<lv>
sudo vgremove -y <vg>
sudo pvremove -y /dev/<disk>

# 2. Zap any residual GPT / Ceph signatures
sudo wipefs -a /dev/<disk>
sudo sgdisk --zap-all /dev/<disk>
sudo dd if=/dev/zero of=/dev/<disk> bs=1M count=100

# 3. Restart the OSD prepare job
kubectl -n rook-ceph delete job -l app=rook-ceph-osd-prepare,rook-ceph-osd-prepare-node=<node>
# The operator will re-create the prepare job and claim the disks.
```

Verify OSDs come up:
```bash
kubectl -n rook-ceph get pods -l app=rook-ceph-osd -o wide | grep <node>
ceph -s
```

## Prevention
- Before rebooting a storage node for an extended outage, capture which
  disks back which OSDs (`ceph-volume lvm list`) so reattach decisions
  are easier.
- For staged reinstalls, follow the ordered activation list in
  `incidents/` rather than bringing all OSDs up at once.

## References
- Lab memory: `project_rook_ceph_reinstall`
