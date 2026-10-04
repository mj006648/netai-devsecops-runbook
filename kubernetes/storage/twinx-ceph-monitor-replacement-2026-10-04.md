# TwinX Ceph 모니터 교체 — MON_DISK_CRIT 해소

> 검증일: 2026-10-04 / 최종 안정성 확인: 13:49 UTC
>
> 상태: **h 퇴역, e/f/m quorum 3개와 Rook 정상 재개 확인. MON_DISK_CRIT 해소.**
>
> 범위: 모니터의 회원·배치·클라이언트 참조 정리. 원본·S0·OSD·pool·MinIO·PV/PVC·기존 h DB는 보존했다.

## Current status

| 항목 | 검증 결과 |
| --- | --- |
| 버전 | Rook 1.17.6 / Ceph 19.2.2 / Argo CD 3.1.8 |
| 모니터 | e → sv4000-1, f → l40s, m → sv4000-2 |
| 기존 h | rm352-1의 회원·Deployment·Service만 퇴역; HostPath DB 보존 |
| quorum | 최종 3개를 302.5초 연속 확인 |
| Rook Operator | replica 1·Ready로 복귀 |
| OSD·PG | OSD 3개 up/in, PG 513개 active+clean |
| 클라이언트 참조 | 로컬·전역 CSI, active-mon EndpointSlice, bootstrap 모니터 주소 일치 |
| health | HEALTH_WARN; MON_DISK_CRIT·MON_DOWN 해소 |
| 남은 경고 | MON_DISK_LOW, POOL_NO_REDUNDANCY, TOO_MANY_PGS |

공개 운영 노트다. 실제 인증값·kubeconfig·keyring·인증서 본문·토큰·전체 원시 덤프는 게시하지 않는다.
이름과 수치는 이번 TwinX에서 검증한 값이며 다른 클러스터의 모니터 ID·배치·스토리지 조건을 대신하지 않는다.

## Symptom

Ceph는 원본 데이터 pool에 여유가 있는데도 `HEALTH_ERR / MON_DISK_CRIT`를 보고했다.
문제는 OSD 용량이 아니라 **mon.h가 사용하는 rm352-1의 root filesystem**이었다.
기존 h는 동작 중이었지만 중지 후 다시 기동했을 때 여유 5%로 인한 Ceph startup 보호에 막혔다.

Argo CD Application이 Healthy이거나 PG가 active+clean이라고 해서 monitor 파일시스템 위험도 해소된 것은 아니다.
원본 데이터와 모니터 DB가 서로 다른 파일시스템에 있으면 원본을 삭제해도 monitor root 공간은 늘지 않는다.

## Diagnosis

### 1. quorum·Pod·원본 저장 공간을 별도로 확인

아래는 읽기 전용 명령이다.

~~~bash
kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph status
kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph health detail
kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph quorum_status -f json
kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph df
kubectl -n rook-ceph get pods -l app=rook-ceph-mon -o wide
kubectl -n rook-ceph get cephcluster rook-ceph -o yaml
~~~

Pod의 mon-data HostPath와 실제 실행 노드를 확인한 후 **그 경로**의 파일시스템 여유를 조사한다.
이 환경의 h DB는 `/var/lib/rook/mon-h/data`였다. 다른 노드·다른 디스크의 `df` 결과로 대신 판단하지 않는다.

### 2. GitOps와 live 소유권 대조

진실소스는 TwinX의 `argocd/twinx-storage/apps/rook-ceph-cluster/values.yaml`이었다.
GitOps tracked 파일 232개와 관련 chart/template을 검토하고 실제 Application 79개의 소유권을 대조했다.

- `rook-ceph-cluster` child: 자동 sync·prune·selfHeal, chart v1.17.6 + Git main의 values.
- storage parent 및 Rook operator app: **작업 당시 live 상태는 manual**.
- bootstrap YAML의 기본 자동 설정과 live 정책을 혼동하지 않았다.
- parent·MinIO·pool recovery 앱은 함께 동기화하지 않았다.

~~~bash
kubectl -n argocd get application rook-ceph-cluster -o yaml
kubectl -n argocd get application twinx-storage-root-app -o yaml
kubectl -n argocd get application rook-ceph-operator -o yaml
kubectl -n rook-ceph get cephcluster rook-ceph -o json --show-managed-fields=true
~~~

일반 SSA dry-run은 과거 `kubectl-patch`가 가진 `spec.mon.count` 소유권과 충돌했다.
설치된 Argo CD 3.1.8의 GitOps 엔진 소스를 확인하면 normal SSA에서 `ForceConflicts=true`를 사용한다.
따라서 **Argo와 동일한 정책의 서버 dry-run**으로 비교했고 실제 적용은 기존 GitOps child 경로로 했다.
이 발견을 근거로 실제 `kubectl apply --force-conflicts`, ForceSync, Replace를 임의 실행하지 않았다.

## Root cause

### 이전 이동 시도의 Pending

9월 26일의 배치 변경은 다음 두 조건을 동시에 만들었다.

| 조건 | 내용 |
| --- | --- |
| 기존 h의 nodeSelector | rm352-1에 고정 |
| 추가한 required nodeAffinity | sv4000-1·l40s·sv4000-2만 허용 |

어느 노드도 둘을 동시에 만족할 수 없어 h가 Pending이 됐다.
HostPath-backed 모니터의 affinity만 바꾸는 것으로 DB·모니터 신원이 자동 이동하는 것은 아니다.

### 단순 4 → 3 축소도 해결책이 아님

Rook 1.17.6의 일반 클러스터에서는 초과 모니터 제거 대상이 h로 보장되지 않는다.
새 모니터를 추가한 뒤 `mon.count`만 줄이면 정상 e/f/m 중 다른 모니터가 선택될 수 있다.
이번 작업은 membership과 endpoint source of truth를 **h만** 퇴역시킨 뒤 count 3과 일치시키는 절차를 사용했다.

## Fix

### 1. 기존 세 모니터를 유지하며 네 번째를 먼저 추가

첫 GitOps 변경은 **`mon.count: 3 → 4` 한 필드**뿐이었다.
placement·이미지·HostPath·resources·health check·OSD·pool은 그대로 뒀다.

기존 세 모니터가 있는 노드 외에 Ready·schedulable·untainted 후보는 sv4000-2였고,
`allowMultiplePerNode: false`가 유지돼 새 m이 그 노드에 배치됐다.
기존 e/f/h와 새 m의 quorum 4개를 5분 이상 검증한 후 다음 단계로 넘어갔다.

### 2. 이름을 고정한 h 퇴역

공유 관리 Controller의 일시 중지는 별도 승인과 계획·코드 검토를 거쳤다.
아래는 **실행 순서 기록**이며 그대로 복사해 재실행할 명령 묶음이 아니다.

1. FSID, CephCluster UID, 대상 Deployment·Service UID, endpoint CM, Git revision, PV/PVC와 데이터 상태를 보관한다.
2. surviving e/f/m의 가용성과 `ceph mon ok-to-stop h`를 확인한다.
3. Rook operator app이 manual인지 확인하고 관리 Deployment만 잠시 pause한다. OSD·데이터 서비스는 중지하지 않는다.
4. GitOps desired count 3과 mon hostname `NotIn: [rm352-1]`을 게시·적용한다. 이때 Rook은 paused여야 한다.
5. UID/RV 조건으로 h만 중지하고 **Pod 종료 및 Ceph quorum 전파를 따로 기다린다**.
6. e/f/m quorum이 정상임을 확인한 뒤 h membership만 제거한다. 여기부터는 단순 4개 복원 대신 coherent 3개로 forward recovery한다.
7. endpoint CM을 UID·resourceVersion·old-data 조건부 JSON Patch로 갱신한다. h만 data/mapping/CSI 주소에서 제거하고 다른 필드를 보존한다.
8. 중지된 h Deployment·Service만 UID 조건으로 정리한다. PV/PVC 및 HostPath DB는 삭제하지 않는다.
9. desired spec·monmap·quorum·CM이 모두 e/f/m 3개로 일치하는 것을 확인한 후 Rook을 재개한다.
10. 로컬·전역 CSI, active-mon EndpointSlice, bootstrap 주소와 정상 quorum을 5분 이상 확인한다.

최종 mon affinity가 rm352-1을 제외해도 **남아 있는 e/f/m selector는 모두 조건을 만족한다**.
이 점이 h가 살아 있는 상태에서 먼저 rm352-1을 제외했던 이전 실패와 다르다.
Rook의 정상 순차 template 갱신 중에는 일시적인 2/3 quorum이 관측됐지만, 최종 3개 Ready를 확인했다.

### 3. 중간 중단·복구에서 확인한 것

- 최초 h Pod 종료 직후 quorum 표시가 아직 4개라 안전 검사가 중단됐다. membership·DB는 삭제하지 않았다.
- rollback은 live spec뿐 아니라 **Git에 게시된 revision**도 기준으로 했다. 아직 적용되지 않은 퇴역 commit이 나중에 적용되지 않도록 복원 revision 확인이 필요하다.
- 4개 설정은 복원됐지만 h 재기동은 기존 root 여유 5% 때문에 거부됐다. 다른 e/f/m quorum은 유지됐다.
- 실제 survivor quorum의 전파 완료를 새로 확인하고 승인된 h 퇴역을 중단 지점부터 이어갔다. 원본·DB 삭제나 경고 임계값 완화는 하지 않았다.
- local endpoint CSI의 `namespace: ""`와 global CSI의 `namespace: "rook-ceph"`는 실제 Rook 표현이 달랐다. local 값을 억지로 바꾸지 않고 clusterID·주소 집합을 검증했다.
- quorum 전파를 유한 120초 동안 기다리는 회귀 테스트를 추가했다. Pod가 사라졌다는 사실만으로 election·quorum 변경 완료를 단정하지 않는다.

## Verification

| 대상 | 사후 확인 |
| --- | --- |
| quorum·Rook | e/f/m 3개, 302.5초 안정 관측, Rook replica 1·Ready |
| 클라이언트 주소 | local/global CSI·EndpointSlice·bootstrap 일치; h 주소 제외 |
| PV/PVC | 기존 PV 36개·PVC 35개의 UID·spec 전후 동일, 추가 생성·삭제 없음 |
| 원본 | 4,514,925 objects / 1,017,489,717,144 bytes의 논리 통계 전후 동일 |
| S0 | 644개 파일의 HEAD 크기·ETag·SHA metadata 전후 동일 |
| 카탈로그·pool | 보호한 Nessie 참조, pool layout·replication 설정 동일 |
| 기존 h DB | `/var/lib/rook/mon-h/data` 보존, 마지막 확인 105,172,992 bytes |
| 코드·설정 | 유지보수 테스트 67개, Helm lint/render·서버 dry-run·실제 snapshot patch 검증 통과 |

원본 논리 통계 및 S0 HEAD 검사는 **파일 본문 전체 재해시가 아니다**.
bootstrap 참조는 메모리에서만 해석했으며 인증 키·토큰 값은 출력·보관하지 않았다.
master-thesis 원고와 Trident 제품 코드는 이 유지보수에서 변경하지 않았다.

## Prevention / remaining risks

- monitor 파일시스템과 RGW/OSD의 여유를 구분한다. `MON_DISK_CRIT`를 원본 데이터 삭제로 해결하려 하지 않는다.
- HostPath mon의 nodeSelector·nodeAffinity·저장 경로·신원을 함께 확인한다.
- 새로운 mon 합류를 먼저 증명하고 퇴역 대상을 고정한다. 임의 count 축소·generic cleanup은 하지 않는다.
- Rook pause 중 다른 관리자가 source revision·UID를 바꾸면 중지하고 현재 상태부터 확인한다.
- 실패 artifact·이전 UID·옛 DB를 근거로 blind replay하지 않는다. 퇴역 전/후의 복구 경계를 구분한다.
- `MON_DISK_LOW`, 단일 replica pool 및 PG 수 경고는 남아 있다. rm352-1의 root 부족이나 물리 디스크 장애 보호 전체가 해결된 것은 아니다.

동일한 240GB 출력 상한·margin·pool reserve·scratch 기준의 다음 전량 쓰기 reference gate는 통과했다.
이는 자원 예약이나 성능 실험 실행 완료를 뜻하지 않는다. **R2 Job은 아직 미실행**이며 실제 실행기·runtime 검증과 시작 직전 fresh gate가 필요하다.

## Evidence / references

- GitOps 적용 이력: `6c9ae1f` → `79a592b` → `4ac45c1` → `699d79c` → `cf82c7a`. 중간 rollback도 기록으로 남겼다.
- [내부 검증 결과·보존 근거 — 접근 권한 필요](https://github.com/mj006648/Trident-Lakehouse-Experiments/blob/4d8992065a9d764612ae653b8baa6f7cc7bdc90e/experiments/operations-v3/results/summary/ceph-mon-replacement-20261004.md)
- [TwinX 유지보수 코드·검증 — 접근 권한에 따름](https://github.com/SmartX-Team/TwinX-Ops/tree/cf82c7a7156d40641a40270adbfa5c8d929ba239/argocd/twinx-storage/maintenance)
- [Rook 1.17 monitor health](https://rook.io/docs/rook/v1.17/Storage-Configuration/Advanced/ceph-mon-health/)
- [Rook 1.17.6 mon 제거·failover 소스](https://github.com/rook/rook/blob/v1.17.6/pkg/operator/ceph/cluster/mon/health.go)
- [Rook 1.17.6 cluster bootstrap 재조정 소스](https://github.com/rook/rook/blob/v1.17.6/pkg/operator/ceph/cluster/cluster.go)
- [Argo CD 3.1.8이 고정한 GitOps engine](https://github.com/argoproj/argo-cd/blob/v3.1.8/go.mod) · [해당 engine의 SSA 코드](https://github.com/argoproj/gitops-engine/blob/e48120133eec/pkg/utils/kube/resource_ops.go)
