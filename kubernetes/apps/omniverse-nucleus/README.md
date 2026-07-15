# Omniverse Nucleus Kubernetes PoC

이 디렉터리는 NVIDIA Omniverse Nucleus를 Kubernetes에서 실행하기 위해 MiniX/TwinX 환경에서 검증한 내용을 정리한 문서와 재현용 manifest 사본이다.

> 핵심 결론: **신규 설치/운영 이관에서는 처음부터 Nucleus 전용 Rook-Ceph RBD StorageClass `rook-ceph-block-nucleus-retain`을 사용한다.** 기존 MiniX live PoC는 먼저 `rook-ceph-block`으로 만들어진 PVC가 있어 그대로 유지했고, 해당 PV만 `Retain`으로 패치했다.

## 무엇을 보면 되는가


| 파일/디렉터리 | 역할 |
| --- | --- |
| [`RUNBOOK.md`](./RUNBOOK.md) | 전체 설계 판단, 재현 절차, 문제 해결, 운영 전 보강 항목 |
| [`SMARTX_EECS_MIGRATION_PLAN.md`](./SMARTX_EECS_MIGRATION_PLAN.md) | 완료된 eecs-k8s + c-k8s 이관을 재현/변경하기 위한 파일별 구현 가이드 |
| [`SMARTX_EECS_EXECUTION.md`](./SMARTX_EECS_EXECUTION.md) | eecs-k8s/c-k8s commit과 C 클러스터 12/12 Ready, PVC, LoadBalancer, HTTP 200 실제 완료 증거 |
| [`TWINX_EXECUTION_2026-07-15.md`](./TWINX_EXECUTION_2026-07-15.md) | TwinX-Ops raw app `argocd/omniverse/apps/omniverse-nucleus-twinx/install.yaml` 실행, LB `10.38.38.245`, RBD 10Gi Retain, 12/12 Running/Healthy, Argo 표시 불일치 기록 |
| [`manifests/nucleus/`](./manifests/nucleus/) | 신규 설치 기준 Nucleus Kubernetes manifest 사본 |

## 디렉터리 구조

```text
kubernetes/apps/omniverse-nucleus/
├── README.md
├── RUNBOOK.md
├── SMARTX_EECS_MIGRATION_PLAN.md
├── SMARTX_EECS_EXECUTION.md
├── TWINX_EXECUTION_2026-07-15.md
├── manifests/
│   └── nucleus/                         # 신규 설치 기준 Nucleus manifest
│       ├── 00-storageclass.yaml          # Nucleus 전용 Retain RBD StorageClass
│       ├── 00-namespace.yaml
│       ├── 10-headless-service.yaml
│       ├── 10-internal-services.yaml
│       ├── 10-loadbalancer-service.yaml
│       └── 20-statefulset.yaml
```

## C 클러스터 SmartX 배포 상태

Nucleus는 계획 단계가 아니라 실제 이관·배포 완료 상태다.

```text
eecs-k8s/main: 3bbfdde, 4c1ab24
c-k8s/main: 1042776
C cluster Pod: 12/12 Ready
StatefulSet: 1/1 Ready
PVC: Bound, 10Gi, ceph-block-noreplicas
LoadBalancer: 10.33.143.10
Navigator: HTTP 200 OK
```

Secret 원문은 이 문서에 기록하지 않는다.

## TwinX 배포 상태

TwinX는 `eecs-k8s`/`c-k8s` 코드를 변경하지 않고 `TwinX-Ops`의 `argocd/omniverse` 아래 raw app으로 실행했다.

```text
raw app: argocd/omniverse/apps/omniverse-nucleus-twinx/install.yaml
namespace: omniverse
LoadBalancer: 10.38.38.245
PVC: RBD 10Gi Retain
Pod: 12/12 Running/Healthy
기존 oos-sim: 변경 없음
기존 외부 Nucleus 10.38.38.32: 변경 없음
eecs-k8s/c-k8s: 코드 변경 없음, 계획만 유지
```

세부 실행 기록은 [`TWINX_EXECUTION_2026-07-15.md`](./TWINX_EXECUTION_2026-07-15.md)를 기준으로 한다.

## C 클러스터 빠른 확인

```bash
kubectl -n omniverse get sts,pvc,pod,svc -o wide
kubectl -n omniverse get pod omniverse-nucleus-0 \
  -o jsonpath='{range .status.containerStatuses[*]}{.name}{" ready="}{.ready}{" restart="}{.restartCount}{"\n"}{end}'
curl -fsS -D - http://10.33.143.10:8080/ | head
```

세부 명령과 당시 출력은 [`SMARTX_EECS_EXECUTION.md`](./SMARTX_EECS_EXECUTION.md)를 기준으로 한다.

## MiniX legacy PoC 검증 상태

- NVIDIA NGC `nvidia/omniverse/nucleus-compose-stack:2023.2.10` 기반 실제 Nucleus 이미지 사용
- Compose Stack의 12개 서비스를 Kubernetes StatefulSet의 12개 container로 실행
- Rook-Ceph RBD PVC write/readback 선행 검증 후, Nucleus 실제 데이터/로그 경로(`/omni/data`, `/omni/log`, `/omni/temp`, `/omni/scratch-meta-dump`)로 마운트
- MetalLB LoadBalancer IP `10.34.48.221`로 Navigator 접속
- Isaac Sim/Nucleus client에서 `omniverse` 계정 로그인 성공
- ArgoCD Application `omniverse-nucleus-poc` 기준 Synced/Healthy 확인

## 신규 설치 기준

신규 설치라면 아래 흐름으로 시작한다.

1. `00-storageclass.yaml`로 Nucleus 전용 RBD StorageClass를 먼저 만든다.
2. `20-statefulset.yaml`의 `volumeClaimTemplates.storageClassName`은 `rook-ceph-block-nucleus-retain`을 사용한다.
3. NGC key, Nucleus password, signing key 등은 Git에 넣지 않고 Kubernetes Secret 또는 OpenBao/External-Secrets로 주입한다.
4. ArgoCD sync-wave 기준으로 StorageClass/Namespace → Services → StatefulSet 순서로 적용한다.

현재 MiniX live PoC는 이미 `rook-ceph-block`으로 PVC가 생성되어 있어 바로 StorageClass를 바꾸지 않았다. 기존 PVC를 전용 StorageClass로 옮기려면 StatefulSet 단순 patch가 아니라 snapshot/restore 또는 새 PVC 마이그레이션으로 처리한다.

## MiniX legacy PoC 빠른 확인

```bash
kubectl -n argocd get app omniverse-nucleus-poc -o wide
kubectl -n omniverse get sts,pvc,pod,svc -o wide
kubectl -n omniverse get pod omniverse-nucleus-0 \
  -o jsonpath='{range .status.containerStatuses[*]}{.name}{" ready="}{.ready}{" restart="}{.restartCount}{"\n"}{end}'
curl -fsS -D - http://10.34.48.221:8080/ | head
```

## 주의

- NGC API Key와 Nucleus 비밀번호는 절대 Git에 커밋하지 않는다.
- `nodeName: com3`은 당시 scheduler 문제를 우회한 PoC 설정이다. 운영 전에는 제거하고 nodeSelector/affinity/tolerations/resource requests로 배치한다.
- `StorageClass reclaimPolicy: Retain`은 PVC 삭제 시 RBD image 즉시 삭제를 막는 Kubernetes lifecycle 보호장치일 뿐이다. Ceph 자체 장애까지 보호하려면 snapshot, off-cluster backup, RBD mirroring 같은 별도 계층이 필요하다.
