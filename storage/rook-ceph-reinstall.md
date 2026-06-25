# Rook-Ceph 전체 재설치 — 단계별 bring-up 런북

## 언제 사용하는가
- 스토리지 노드 예: `l40s` 재부팅 이후 OSD 상태가 유실됐고, 부분 복구가 어렵다고 판단된 경우
- Ceph에 의존하는 여러 앱을 올바른 순서로 복구해야 하며, 순서를 틀리면 장애 chain이 다시 발생할 수 있는 경우

## 사전 점검
- [ ] cluster가 유실된 OSD를 인지했는지 확인한다. `ceph osd tree`, `ceph -s`.
      Ceph가 아직 해당 OSD가 돌아오길 기대하는 중이면 Rook을 재시작하지 않는다.
- [ ] 필요한 pool-level config를 기록한다. `ceph osd pool ls detail`, CRUSH rule, RBD pool / RGW config.
- [ ] 의존 workload를 조용히 멈춘다. 단순 disruption이 아니라 scale-to-zero가 안전하다.
- [ ] 먼저 node networking이 정상인지 확인한다.
      ([`networking/mtu-cilium.md`](../networking/mtu-cilium.md),
      [`networking/rm352-pod-comms.md`](../networking/rm352-pod-comms.md))

## 1단계 — 영향 노드의 stale storage state 제거

[`storage/lv-preparation.md`](lv-preparation.md)를 따른다.

- Rook이 남긴 old LV / VG / PV를 제거한다.
- 각 disk에서 GPT와 Ceph signature를 zap한다.
- 해당 host에서 `ceph-volume lvm list`가 비어 있는지 확인한다.

> 실제 경험: 이 클러스터에서는 zombie GPT/LVM metadata 때문에 rebuild 중 LV creation이 막힌 적이 있다.
> `pvremove` 전에 `sgdisk --zap-all` + `wipefs -a`를 실행하는 순서가 더 안전하다.

## 2단계 — Rook operator와 core mon 복구

```bash
kubectl -n rook-ceph scale deploy rook-ceph-operator --replicas=1
kubectl -n rook-ceph get pods -l app=rook-ceph-mon -w
ceph -s
```

Mon quorum이 healthy이고 mgr가 올라오기 전까지 다음 단계로 넘어가지 않는다.

## 3단계 — 정리한 노드에서 OSD 재준비

```bash
kubectl -n rook-ceph delete job -l app=rook-ceph-osd-prepare,rook-ceph-osd-prepare-node=<node>
kubectl -n rook-ceph get pods -l app=rook-ceph-osd -o wide | grep <node>
ceph osd tree
```

의존 앱을 활성화하기 전에 backfill / recovery가 안정화될 때까지 기다린다.

## 4단계 — 의존 앱을 순서대로 재활성화

이 클러스터에서 Rook-Ceph 재설치 후 명시적으로 다시 켜야 하는 ArgoCD app 순서:

1. **cnpg (pg-resources)** — Postgres operator와 cluster instance. Catalog backend가 여기에 의존한다.
2. **nessie** — Iceberg catalog. Postgres가 먼저 살아 있어야 한다.
3. **trino** — query engine. Catalog와 object storage에 의존한다.
4. **infra** — 운영 지원 서비스.
5. **spark** — compute. Catalog와 object storage에 의존한다.
6. **superset** — BI / dashboard. 사용자-facing이므로 마지막에 올린다.

각 앱마다:

```bash
# ArgoCD-managed setup 기준
kubectl -n argocd patch app <name> --type=merge -p '{"spec":{"syncPolicy":{"automated":{}}}}'

# 또는 workload를 원래 replica 수로 복구
kubectl -n <ns> scale deploy <name> --replicas=<original>
kubectl -n <ns> rollout status deploy/<name>
```

## 5단계 — 검증
- `ceph -s`가 `HEALTH_OK` 또는 예상된 warning만 보여준다.
- 모든 OSD가 `up` / `in` 상태다.
- Backfill이 완료됐고 `degraded`, `misplaced` object가 없다.
- 재활성화한 앱이 각각 smoke test를 통과한다.
- RGW와 RBD에 대해 controlled write/read가 성공한다.

## 재발 방지
- 위 단계적 순서를 이 저장소에 유지하고, 재설치 후에는 실제 결과를 반영해 업데이트한다.
- 모든 의존 앱을 동시에 올리지 않는다. 단계적 복구가 문제를 더 빨리 드러내고 cascade 재발을 줄인다.

## 참고
- TwinX commits 2026-05-01: `c65c4de`..`2ed16e8` (full Rook-Ceph rebuild)
- 관련 문서: [`storage/lv-preparation.md`](lv-preparation.md),
  [`incidents/cluster-cascade.md`](../incidents/cluster-cascade.md)
