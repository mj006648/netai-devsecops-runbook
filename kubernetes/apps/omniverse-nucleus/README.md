# Omniverse Nucleus StatefulSet PoC

> Runbook copy note: 이 디렉터리는 `MiniX`에 실제 ArgoCD로 적용한 Omniverse Nucleus manifest와 문서를 `netai-devsecops-runbook`에 옮긴 검토/재현용 사본이다.
> 현재 실제 적용 원본은 `mj006648/MiniX:argocd/minix/apps/omniverse-nucleus-poc`이고, 이 runbook 사본은 MiniX commit `1be29969` 기준으로 동기화했다.


> 자세한 재현 절차와 설계 판단은 [`RUNBOOK.md`](./RUNBOOK.md)를 먼저 읽는다.
> `README.md`는 현재 상태/검증 결과 요약이고, `RUNBOOK.md`는 왜 이렇게 했는지와 NVIDIA Compose Stack을 Kubernetes로 옮긴 과정을 정리한 실행 런북이다.


## 디렉터리 구조 정리

```text
kubernetes/apps/omniverse-nucleus/
├── README.md
├── RUNBOOK.md
├── manifests/
│   └── nucleus/                 # 실제 Nucleus 배포에 필요한 manifest 5개
│       ├── 00-storageclass.yaml
├── 00-namespace.yaml
│       ├── 10-headless-service.yaml
│       ├── 10-internal-services.yaml
│       ├── 10-loadbalancer-service.yaml
│       └── 20-statefulset.yaml
└── experiments/
    └── rbd-smoke/               # 과거 RBD PVC 검증용. Nucleus 배포에는 필요 없음
        ├── 00-namespace-pvc.yaml
        ├── 10-rbd-write-pod.yaml
        └── 20-rbd-readback-pod.yaml
```

- `manifests/nucleus/`: 다음에 실제로 참고/적용할 Nucleus manifest.
- `experiments/rbd-smoke/`: RBD PVC가 붙고 데이터가 유지되는지 먼저 확인했던 실험 기록. 최종 Nucleus 배포에는 적용하지 않는다.
- 실제 운영 원본은 `MiniX:argocd/minix/apps/omniverse-nucleus-poc/`이고, 이 runbook repo는 검토/재현용 사본이다.

이 앱은 실제 NVIDIA Omniverse Nucleus 이미지를 배포하기 전, ArgoCD가 `StatefulSet + Rook-Ceph RBD PVC + Service` 구조를 정상적으로 만들 수 있는지 검증하기 위한 PoC이다.

## 현재 범위

- NVIDIA NGC `nvidia/omniverse/nucleus-compose-stack:2023.2.10` 기반 실제 Nucleus 서비스 사용
- Compose stack의 12개 서비스를 Kubernetes StatefulSet의 12개 컨테이너로 변환
- `rook-ceph-block` RBD StorageClass 사용
- `volumeClaimTemplates`로 Pod 전용 PVC 생성
- Nucleus 실제 데이터/로그 경로(`/omni/data`, `/omni/log`, 일부 `/omni/temp`, `/omni/scratch-meta-dump`)를 RBD PVC로 마운트
- `nvcr.io/nvidia/omniverse/*` 실제 Nucleus 이미지 사용


## 현재 클러스터 주의사항

2026-07-09 기준 kube-scheduler-master가 CrashLoopBackOff 상태라 신규 Pod가 일반 scheduler 경로로 배치되지 않는다.
PoC에서는 RBD PVC 마운트와 StatefulSet 구조 검증을 먼저 하기 위해 임시로 nodeName: com3을 지정했다. 처음에는 com1을 사용했지만 CPU request 여유가 부족해 Pod 생성이 반복 실패했고, com3의 allocatable 여유가 더 커서 변경했다.

- 최종 운영 전에는 nodeName: com3을 제거해야 한다.
- kube-scheduler가 정상화되면 일반 scheduler가 node labels/taints/affinity 기준으로 Pod를 배치한다.

## 다음 단계

현재는 NGC artifact를 확보했고 실제 이미지를 사용한다. 다음 항목은 아직 운영화 전 보완 대상이다.

- kube-scheduler 정상화 후 `nodeName: com1` 제거
- 운영 DNS/TLS 적용 여부 결정
- Nucleus admin/service password를 OpenBao/External-Secrets로 이관
- readiness/liveness probe 추가
- PVC 용량을 운영 크기로 확장

## 확인 명령

```bash
kubectl -n omniverse get sts,pvc,pod,svc
kubectl -n omniverse logs sts/omniverse-nucleus
kubectl -n omniverse port-forward svc/omniverse-nucleus 8080:8080
```

브라우저 또는 curl:

```bash
curl http://127.0.0.1:8080/
```

## 2026-07-09 실행 결과

### 성공한 것

- MiniX ArgoCD child Application omniverse-nucleus-poc 생성 확인
- ArgoCD 상태: Synced / Healthy
- StatefulSet omniverse-nucleus: 1/1 Ready
- PVC nucleus-data-omniverse-nucleus-0: rook-ceph-block, 10Gi, Bound
- Pod omniverse-nucleus-0: com1 노드에서 Running
- 초기 smoke 단계에서는 PVC marker 파일 생성을 확인했고, 실제 Nucleus 전환 후에는 `/omni/data`, `/omni/log` 등이 `/dev/rbd1`로 마운트됨을 확인
- Pod 내부에서 localhost와 Service DNS 양쪽 HTTP 응답 확인

검증 출력 요약:



### 발견한 문제와 해결

1. ArgoCD repo-server가 MiniX repo를 읽지 못함
   - 원인: trident-ui/streamlit/bin/python3가 /usr/bin/python3를 가리키는 out-of-bounds symlink였다.
   - 해결: trident-ui/streamlit 가상환경과 trident-ui/__pycache__를 Git 추적에서 제거하고 .gitignore에 추가했다.
   - 관련 커밋: 00b772a6 chore: remove tracked Streamlit virtualenv

2. 신규 Pod가 Pending에 머묾
   - 원인: kube-scheduler-master가 CrashLoopBackOff 상태였고, lease 갱신 시 API Server timeout이 발생했다.
   - 해결: 운영 최종안은 아니지만 PoC 검증을 위해 StatefulSet template에 임시 nodeName: com3을 지정했다.
   - 관련 커밋: 032fe33d test: pin Nucleus PoC during scheduler outage


3. `nucleus-api`가 `nucleus-resolver-cache`에 연결하지 못하고 CrashLoopBackOff
   - 원인: Kubernetes Service는 기본적으로 Ready Pod만 Endpoint로 넣는다. Nucleus compose stack은 같은 Pod 안의 여러 컨테이너가 bootstrap 중 서로의 Service DNS로 접근해야 해서, `nucleus-api -> nucleus-resolver-cache`가 Pod Ready 이전에 막혔다.
   - 해결: compose 내부 통신용 Service들에 `publishNotReadyAddresses: true`를 추가했다.


4. `nucleus-log-processor`가 `nucleus-api:3006`에 연결하지 못하고 CrashLoopBackOff
   - 원인: Docker Compose에서는 같은 네트워크 안의 컨테이너 포트가 바로 보이지만, Kubernetes Service는 `ports`에 명시된 포트만 프록시한다.
   - 해결: 외부 LoadBalancer가 아니라 내부 `nucleus-api` ClusterIP Service에만 `service-api` 포트 3006을 추가했다. 이 포트는 관리용 성격이 있으므로 외부 노출 금지.


5. LoadBalancer 8080이 Navigator UI가 아니라 metrics로 연결됨
   - 원인: 같은 Pod 안에서 `utl-monpx`가 8080을 사용하고, Nucleus Navigator UI는 80을 사용한다. Service `targetPort: 8080`은 Pod IP의 8080으로 가므로 metrics가 응답했다.
   - 해결: 외부 접속 주소는 `http://10.34.48.221:8080/` 그대로 두고, `omniverse-nucleus` LoadBalancer Service의 `web` 포트 `targetPort`만 80으로 변경했다.

### 남은 작업

- kube-scheduler / kube-controller-manager CrashLoop 원인 복구
- scheduler 복구 후 20-statefulset.yaml에서 nodeName: com3 제거
- 실제 접속 도메인/IP와 TLS/Ingress 노출 방식 확정
- readiness/liveness probe 추가
- 실제 운영 전에 Nucleus 데이터 백업/복구 절차 확정

## 실제 Nucleus 전환 내역

2026-07-09에 placeholder `python:3.12-alpine` 컨테이너를 제거하고 NVIDIA Enterprise Nucleus Compose Stack 기반 구성으로 전환했다.

### 사용한 artifact

```bash
ngc registry resource download-version nvidia/omniverse/nucleus-compose-stack:2023.2.10
```

다운로드 위치는 로컬 작업용이며 Git에는 커밋하지 않는다.

```text
.artifacts/ngc/nucleus-compose-stack_v2023.2.10/
.artifacts/nucleus-stack-2023.2.10/
```

### 실제 이미지

현재 StatefulSet에는 다음 실제 NVIDIA Nucleus 이미지가 들어간다.

```text
nvcr.io/nvidia/omniverse/nucleus-api:1.14.55
nvcr.io/nvidia/omniverse/nucleus-lft:1.14.55
nvcr.io/nvidia/omniverse/nucleus-lft-lb:1.14.55
nvcr.io/nvidia/omniverse/nucleus-log-processor:1.14.55
nvcr.io/nvidia/omniverse/nucleus-resolver-cache:1.14.55
nvcr.io/nvidia/omniverse/utl-monpx:1.14.55
nvcr.io/nvidia/omniverse/nucleus-discovery:1.5.6
nvcr.io/nvidia/omniverse/nucleus-auth:1.5.9
nvcr.io/nvidia/omniverse/nucleus-navigator:3.3.7
nvcr.io/nvidia/omniverse/nucleus-search:3.2.14
nvcr.io/nvidia/omniverse/nucleus-thumbnails:1.5.15
nvcr.io/nvidia/omniverse/nucleus-tagging:3.1.36
```


### MetalLB 접속 IP

`omniverse-nucleus` Service는 MetalLB `LoadBalancer`로 노출한다. 현재 MetalLB 정책상 `spec.loadBalancerIP`와 `metallb.io/loadBalancerIPs`를 동시에 쓰면 할당이 실패하므로, Git manifest에는 `metallb.io/loadBalancerIPs` annotation만 사용한다.

```text
LoadBalancer IP: 10.34.48.221
Service: omniverse/omniverse-nucleus
```

Nucleus compose stack의 `SERVER_IP_OR_HOST`와 외부 advertised URL도 같은 IP로 맞췄다. 브라우저 접속은 우선 다음 주소를 사용한다.

```text
http://10.34.48.221:8080/
```

운영 단계에서 DNS를 붙이면 `SERVER_IP_OR_HOST`와 Service annotation/loadBalancerIP를 DNS/IP 정책에 맞춰 다시 조정한다.

### Runtime Secret

다음 Secret은 Git에 넣지 않고 클러스터에 직접 생성했다.

```text
nvcr-io             # nvcr.io imagePullSecret
nucleus-secrets     # auth signing key, discovery token, salts, SAML blank metadata
nucleus-passwords   # admin/service password
```

관리자 계정은 compose 기본값에 맞춰 `omniverse`이다. 비밀번호는 아래 명령으로 클러스터에서 조회한다.

```bash
kubectl -n omniverse get secret nucleus-passwords   -o jsonpath='{.data.master-password}' | base64 -d; echo
```

### 배포 구조

```text
ArgoCD Application omniverse-nucleus-poc
  -> StatefulSet omniverse-nucleus
     -> 12 containers from NVIDIA Nucleus Compose Stack
     -> PVC nucleus-data-omniverse-nucleus-0
        -> rook-ceph-block RBD
        -> /var/lib/omni/nucleus-data
  -> Service omniverse-nucleus
  -> Internal Services nucleus-api, nucleus-auth, nucleus-discovery, ...
```

### 검증 명령

```bash
kubectl -n argocd get app omniverse-nucleus-poc -o wide
kubectl -n omniverse get sts,pvc,pod,svc -o wide
kubectl -n omniverse get pod omniverse-nucleus-0 -o jsonpath='{range .status.containerStatuses[*]}{.name}{"\t"}{.ready}{"\t"}{.state}{"\n"}{end}'
kubectl -n omniverse logs omniverse-nucleus-0 -c nucleus-api --tail=100
kubectl -n omniverse logs omniverse-nucleus-0 -c nucleus-auth --tail=100
kubectl -n omniverse port-forward svc/omniverse-nucleus 8080:8080
```




## 2026-07-10 데이터 보호 정책 보강

현재 Nucleus PVC의 PV reclaimPolicy를 `Delete`에서 `Retain`으로 패치했고, Nucleus 전용 StorageClass `rook-ceph-block-nucleus-retain`도 추가했다. 단, 현재 live StatefulSet/PVC는 이미 `rook-ceph-block`으로 생성되어 있어 그대로 유지한다.

```bash
PV=$(kubectl -n omniverse get pvc nucleus-data-omniverse-nucleus-0 -o jsonpath='{.spec.volumeName}')
kubectl patch pv "$PV" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

보호 범위는 다음처럼 구분한다.

| 장애/삭제 상황 | 데이터 보존 기대 | 필요한 보호장치 |
| --- | --- | --- |
| Nucleus Pod 재시작/삭제 | 유지 | StatefulSet + PVC |
| StatefulSet 삭제 | PVC가 남으면 유지 | `persistentVolumeClaimRetentionPolicy: Retain` |
| PVC 실수 삭제 | PV/RBD 보존 가능 | PV `persistentVolumeReclaimPolicy: Retain` |
| 단일 OSD/노드 장애 | Ceph 복제로 유지 기대 | Ceph pool `replicated.size: 3`, `failureDomain: host` |
| Ceph cluster/pool 자체 손상 | 보장 불가 | VolumeSnapshot, RBD mirroring, 외부 백업 필요 |
| 사이트/클러스터 전체 손실 | 보장 불가 | 별도 클러스터/오브젝트 스토리지/NAS 등 off-cluster backup 필요 |

중요: StorageClass의 `reclaimPolicy: Retain`은 앞으로 새로 만들어질 PV에 적용된다. 이미 생성된 Nucleus PV는 StorageClass를 바꿔도 자동 변경되지 않으므로 현재 PV를 직접 patch했다. 운영 전에는 Nucleus 전용 StorageClass 예: `rook-ceph-block-retain`을 만들고, 처음 PVC를 만들 때부터 그 StorageClass를 쓰는 방향이 좋다.

## 2026-07-10 로그인 및 RBD persistence 확인

Isaac Sim/Nucleus 클라이언트에서 `10.34.48.221`로 접속 후 `omniverse` 계정 로그인이 성공했다. `nucleus-auth` 로그에서 다음 이벤트를 확인했다.

```text
InternalCredentials.auth: username=omniverse
status=OK
```

현재 live 상태:

```text
ArgoCD Application: omniverse-nucleus-poc / Synced / Healthy
Pod: omniverse-nucleus-0 / 12/12 Running
PVC: nucleus-data-omniverse-nucleus-0 / Bound / rook-ceph-block / 10Gi
Dedicated SC prepared: rook-ceph-block-nucleus-retain / reclaimPolicy Retain
LoadBalancer: 10.34.48.221
```

RBD 마운트 확인 결과, 실제 persistent 데이터는 `/dev/rbd1`로 붙은 다음 경로에 저장된다.

```text
/omni/data
/omni/log
/omni/temp
/omni/scratch-meta-dump
/var/lib/omni/nucleus-data/empty
```

실제 Nucleus 데이터베이스/메타데이터 파일도 RBD 위의 `/omni/data`에서 확인했다.

```text
/omni/data/usergroups.1.0
/omni/data/meta.1.1
/omni/data/content.1.1
/omni/data/omniobjects.1.0
/omni/data/__version_tag
```

따라서 `omniverse-nucleus-0` Pod가 삭제되어도 StatefulSet이 같은 PVC `nucleus-data-omniverse-nucleus-0`를 다시 붙이면 데이터는 유지된다. 단, PVC 자체를 삭제하면 PV reclaimPolicy가 `Delete`이므로 underlying RBD image도 삭제되어 데이터가 사라질 수 있다.

## 2026-07-09 최종 검증 결과: 실제 Nucleus + RBD + MetalLB

검증 당시 manifest Git revision: `4ba532c4` (`fix: route Nucleus web port to Navigator`)

검증 상태:

```text
ArgoCD Application: omniverse-nucleus-poc / Synced / Healthy
StatefulSet: omniverse-nucleus / 1/1 Ready
Pod: omniverse-nucleus-0 / 12/12 Running / node=com3
PVC: nucleus-data-omniverse-nucleus-0 / rook-ceph-block / 10Gi / Bound
LoadBalancer IP: 10.34.48.221
Web URL: http://10.34.48.221:8080/
```

HTTP 검증:

```bash
curl -fsS -D - http://10.34.48.221:8080/
```

응답 요약:

```text
HTTP/1.1 200 OK
Server: nginx/1.28.1
<title>Omniverse Navigator</title>
<base id="public-url" href="http://10.34.48.221:8080/" />
```

이번 PoC에서 실제로 확인한 것:

- NVIDIA NGC Enterprise Nucleus Compose Stack `2023.2.10` artifact 기반 실제 이미지 사용
- Compose의 12개 서비스를 Kubernetes StatefulSet의 12개 컨테이너로 구동
- Rook-Ceph RBD PVC를 Nucleus 실제 데이터/로그 경로로 마운트
- MetalLB LoadBalancer IP `10.34.48.221`로 외부 접속 노출
- 내부 Compose DNS 대체용 ClusterIP Service 구성
- Kubernetes와 Compose 차이로 발생한 bootstrap 문제 해결
  - Ready 전 Endpoint 필요: `publishNotReadyAddresses: true`
  - 내부 Service API 3006 필요: `nucleus-api` ClusterIP에만 `service-api` 포트 추가
  - Navigator UI 포트 보정: 외부 8080 -> Pod targetPort 80

주의:

- 현재 `nodeName: com3`는 kube-scheduler / kube-controller-manager 불안정 상태를 우회하기 위한 임시 설정이다.
- 운영 전에는 control-plane 안정화 후 `nodeName`을 제거하고 node affinity/toleration/resource request 기반으로 배치해야 한다.
- `nvcr-io`, `nucleus-secrets`, `nucleus-passwords`는 Git에 넣지 않고 런타임 Secret으로 생성했다. 운영 전에는 OpenBao + External-Secrets로 이관해야 한다.
- NGC API Key 또는 Docker registry credential은 개인 키를 그대로 재사용하지 말고, 테스트 후 revoke/rotate하고 조직 정책에 맞게 Secret Store에 넣어야 한다.

---

## 부록: 2026-07-09 RBD smoke 기존 기록

아래 내용은 이 디렉터리에 먼저 작성되어 있던 Rook-Ceph RBD smoke 검증 기록이다. 현재 최신 Nucleus manifest는 위 요약과 `RUNBOOK.md`, `manifests/nucleus/` YAML 파일을 기준으로 본다.

> 목적: SmartX/eecs-k8s 앱 카탈로그에 넣기 전에, `ssh chang@master` 환경의 실제 Kubernetes 클러스터에서 **Rook-Ceph RBD PVC를 Nucleus DATA_ROOT로 사용할 수 있는지**를 먼저 검증한다.

## 현재 결론

- **SmartX 연동 전 수동 PoC부터 진행한다.**
- 실험 대상 클러스터는 `kubernetes-admin@cluster.local`이다.
- KIND 클러스터(`kind-datax`, `kind-twinx`, `kind-edgex`, `kind-tower`)에는 RBD StorageClass가 없고 `local-path`만 있다.
- 실제 클러스터에는 `rook-ceph-block` StorageClass가 있으며 provisioner는 `rook-ceph.rbd.csi.ceph.com`이다.
- 2026-07-09 1차 smoke 결과, `rook-ceph-block` PVC는 **Bound / attach / ext4 mount / write / Pod 재생성 후 readback**까지 성공했다.
- 아직 Nucleus 본체는 배포하지 않았다. 이유는 `master`에 `nvcr.io` 인증과 Nucleus compose artifact가 아직 없기 때문이다.

## 왜 바로 SmartX에 넣지 않는가

Omniverse Nucleus Enterprise는 공식적으로 Docker Compose stack 형태로 제공된다. 따라서 바로 `smartx-k8s/apps/omniverse-nucleus`를 만들기 전에 다음을 먼저 확인해야 한다.

1. NGC에서 받은 compose artifact 안의 컨테이너 이미지, env, volume, port 구조
2. Kubernetes에서 RBD PVC가 Nucleus data directory로 정상 동작하는지
3. 필요한 Secret/License/EULA/NGC 인증 처리 방식
4. Nucleus client가 필요한 TCP 포트 노출 방식

이 PoC가 성공하면 그 다음 단계에서 SmartX/eecs-k8s 앱 카탈로그와 `twinx-k8s` preset으로 이식한다.

## 공식 문서 근거

- Planning: <https://docs.omniverse.nvidia.com/nucleus/latest/enterprise/installation/planning.html>
- Install: <https://docs.omniverse.nvidia.com/nucleus/latest/enterprise/installation/install-ove-nucleus.html>
- Architecture: <https://docs.omniverse.nvidia.com/nucleus/latest/architecture.html>
- Ports: <https://docs.omniverse.nvidia.com/nucleus/latest/ports_connectivity.html>
- Sizing: <https://docs.omniverse.nvidia.com/nucleus/latest/sizing-guide.html>
- NGC Enterprise Nucleus collection: <https://catalog.ngc.nvidia.com/orgs/nvidia/omniverse/collections/enterprise-nucleus/-/artifacts>

핵심 제약:

- 공식 설치 방식은 Docker Compose stack + `.env` 파일 기반이다.
- Enterprise Nucleus는 전용 서버 배포를 권장한다.
- 데이터 저장소는 transactional 성격이 있으므로 SMB/CIFS, NFS, iSCSI 같은 원격 마운트는 지원되지 않는다고 경고한다.
- Kubernetes에서는 CephFS/RWX보다 **Rook-Ceph RBD / RWO / 단일 StatefulSet replica** 방향으로 먼저 검증한다.
- Nucleus 주요 포트는 Web `8080`, API `3009/3019`, metrics `3010`, tagging `3020`, LFT `3030`, auth `3100/3180`, discovery `3333`, search `3400`이다.

## 2026-07-09 환경 확인

### Context별 StorageClass

```text
kind-datax      -> local-path only
kind-edgex      -> local-path only
kind-twinx      -> local-path only
kind-tower      -> local-path only
kubernetes-admin@cluster.local -> rook-ceph-block, rook-ceph-fs, object bucket classes
```

### 실제 PoC 대상

```text
context: kubernetes-admin@cluster.local
namespace: omniverse-nucleus-poc
StorageClass: rook-ceph-block
provisioner: rook-ceph.rbd.csi.ceph.com
pool: replicapool
fstype: ext4
accessMode: ReadWriteOnce
```

### Rook-Ceph 상태

```text
CephCluster: rook-ceph
Phase: Ready
Health: HEALTH_WARN
BlockPool: replicapool Ready, replicated size 3, failureDomain host
```

> `HEALTH_WARN`은 운영상 확인이 필요하지만, RBD PVC provision/attach/write smoke는 성공했다.

## RBD PVC smoke 결과

사용한 manifests: [`manifests/00-namespace-pvc.yaml`](./manifests/00-namespace-pvc.yaml), [`manifests/10-rbd-write-pod.yaml`](./manifests/10-rbd-write-pod.yaml), [`manifests/20-rbd-readback-pod.yaml`](./manifests/20-rbd-readback-pod.yaml)

### 1차 write

```text
PVC: rbd-smoke
STATUS: Bound
VOLUME: pvc-1cc18f75-e2ef-4dbe-a78a-d6c7f6c8b46f
CAPACITY: 1Gi
STORAGECLASS: rook-ceph-block
Pod: rbd-smoke Running on com3
Mount: /dev/rbd1 -> /data
```

로그:

```text
2026-07-09T08:13:29+00:00
rbd smoke ok
Filesystem                Size      Used Available Use% Mounted on
/dev/rbd1               973.4M     28.0K    957.4M   0% /data
```

### Pod 삭제 후 readback

`rbd-smoke` Pod를 삭제하고 같은 PVC를 `rbd-smoke-readback` Pod에 다시 붙였다.

결과:

```text
--- readback ---
2026-07-09T08:13:29+00:00
rbd smoke ok
--- after append ---
2026-07-09T08:13:29+00:00
rbd smoke ok
readback-at=2026-07-09T08:25:20+00:00
Filesystem                Size      Used Available Use% Mounted on
/dev/rbd1               973.4M     28.0K    957.4M   0% /data
```

판정:

```text
Rook-Ceph RBD PVC 동적 생성: 성공
Pod attach/mount: 성공
파일 쓰기: 성공
Pod 재생성 후 데이터 유지: 성공
```


### 재현 명령

```bash
CTX="kubernetes-admin@cluster.local"
BASE="kubernetes/apps/omniverse-nucleus/manifests"

kubectl --context "$CTX" apply -f "$BASE/00-namespace-pvc.yaml"
kubectl --context "$CTX" apply -f "$BASE/10-rbd-write-pod.yaml"
kubectl --context "$CTX" -n omniverse-nucleus-poc wait --for=condition=Ready pod/rbd-smoke --timeout=180s
kubectl --context "$CTX" -n omniverse-nucleus-poc logs pod/rbd-smoke

kubectl --context "$CTX" -n omniverse-nucleus-poc delete pod rbd-smoke --wait=true
kubectl --context "$CTX" apply -f "$BASE/20-rbd-readback-pod.yaml"
kubectl --context "$CTX" -n omniverse-nucleus-poc logs pod/rbd-smoke-readback
```

## 트러블슈팅 기록

### default ServiceAccount 미생성

Namespace 직후 Pod를 바로 생성했을 때 다음 오류가 발생했다.

```text
error looking up service account omniverse-nucleus-poc/default: serviceaccount "default" not found
```

해결:

```text
ServiceAccount/default를 manifest에 명시적으로 추가한다.
```

### readback Pod Pending

`rbd-smoke` 삭제 후 `rbd-smoke-readback`을 생성했을 때, 이벤트 없이 Pending 상태가 유지된 적이 있었다. smoke 목적은 같은 RBD PVC 재부착/데이터 유지 확인이었기 때문에, 최초 Pod가 붙었던 `com3`에 `nodeName: com3`을 임시 지정해서 readback을 완료했다.

운영용 Nucleus manifest에서는 `nodeName`을 고정하지 말고, 필요하면 nodeSelector/affinity로 TwinX Nucleus 전용 노드군을 지정한다.

## 정리 상태

2026-07-09 smoke test 후 실제 클러스터의 테스트 namespace는 정리했다.

```bash
kubectl --context kubernetes-admin@cluster.local delete ns omniverse-nucleus-poc --ignore-not-found
```

확인 결과:

```text
namespace/omniverse-nucleus-poc deleted
```

## NGC / Nucleus artifact 상태

2026-07-09 `master` 확인 결과:

```text
~/.docker/config.json: present
nvcr.io auth: false
ngc CLI: not found
local nucleus/omniverse compose artifact: not found
```

따라서 다음 단계에서 필요하다.

```text
1. NVIDIA Developer Program 가입된 NGC 계정
2. NGC API key
3. nvcr.io imagePullSecret
4. Enterprise Nucleus Server compose stack artifact
```

## 다음 실험 계획

### Phase 1. Nucleus compose artifact 확보

NGC에서 Enterprise Nucleus Server collection의 compose stack을 받는다.

확인할 파일:

```text
nucleus-stack.env
nucleus-stack-no-ssl.yml 또는 SSL variant compose file
generate-sample-insecure-secrets.sh
VERSION
base_stack/
```

분석할 항목:

```text
container images
required env
required secrets
DATA_ROOT
volumes
ports
service dependencies
health checks
```

### Phase 2. Kubernetes raw manifest 변환

처음부터 Helm/SmartX로 가지 말고 raw manifest로 변환한다.

예상 구조:

```text
Namespace: omniverse-nucleus-poc
StatefulSet: omniverse-nucleus
Replica: 1
PVC: rook-ceph-block / RWO / initially 500Gi target, small size for test if needed
Service: ClusterIP + optional NodePort/port-forward
Secret: NGC imagePullSecret + Nucleus required secrets
ConfigMap/Secret: nucleus-stack.env equivalent
```

### Phase 3. 접속 검증

처음에는 Ingress/TLS보다 port-forward 또는 NodePort로 확인한다.

```bash
kubectl --context kubernetes-admin@cluster.local -n omniverse-nucleus-poc port-forward svc/omniverse-nucleus 8080:8080
```

성공 기준:

```text
PVC Bound
Pod Running
Nucleus 서비스 로그 정상
Navigator/Web UI 접속
Pod 재시작 후 DATA_ROOT 데이터 유지
Isaac Sim 또는 Omniverse client에서 nucleus:// 접속 가능
```

## SmartX 연동 시 예상 구조

PoC 성공 후에만 진행한다.

```text
eecs-k8s 또는 smartx-k8s fork
  apps/omniverse-nucleus/
    manifest.yaml
    values.yaml
    patches.yaml
    templates/

twinx-k8s
  values.yaml
    features:
      - scalex.io/omniverse/nucleus
  patches/omniverse-nucleus/values.yaml
```

feature graph 예시:

```yaml
scalex.io/omniverse:
  requires: []

scalex.io/omniverse/nucleus:
  requires:
    - scalex.io/omniverse
    - org.ulagbulag.io/csi/block
```

Rook-Ceph를 명시 의존성으로 강하게 묶을지 여부는 TwinX 운영 구조를 보고 결정한다.

### Sync wave 기준

파일명 앞의 `00`, `10`, `20`은 사람이 읽기 쉽게 정렬하기 위한 prefix이다. ArgoCD의 실제 적용 순서는 파일명이 아니라 각 manifest의 annotation으로 명시한다.

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "<wave>"
```

현재 기준:

| Wave | Manifest | 이유 |
| --- | --- | --- |
| `0` | `00-storageclass.yaml`, `00-namespace.yaml` | namespace가 먼저 있어야 namespaced resource를 만들 수 있음 |
| `1` | `10-headless-service.yaml`, `10-internal-services.yaml`, `10-loadbalancer-service.yaml` | Nucleus Pod가 뜨기 전에 내부 DNS/Service 이름을 먼저 준비 |
| `2` | `20-statefulset.yaml` | Secret/PVC/Service 전제가 준비된 뒤 실제 Nucleus Pod 실행 |

따라서 파일명 prefix는 문서 가독성용이고, 운영 기준은 `argocd.argoproj.io/sync-wave`이다.

### Nucleus 전용 StorageClass

신규 운영 설치 또는 PVC 재생성 마이그레이션부터는 기본 `rook-ceph-block` 대신 Nucleus 전용 StorageClass를 사용하는 것이 좋다.

```text
StorageClass: rook-ceph-block-nucleus-retain
reclaimPolicy: Retain
allowVolumeExpansion: true
provisioner: rook-ceph.rbd.csi.ceph.com
pool: replicapool
```

이 StorageClass는 PVC 삭제 실수 시 RBD image가 즉시 삭제되는 것을 막기 위한 것이다.

현재 PoC manifest의 StatefulSet은 live PVC와의 호환을 위해 `storageClassName: rook-ceph-block`을 유지한다. Kubernetes StatefulSet의 `volumeClaimTemplates`는 생성 후 변경이 까다롭기 때문에, 이미 떠 있는 Nucleus에서 이 값을 Git으로 바로 바꾸면 ArgoCD sync 실패 또는 재생성 절차가 필요할 수 있다.

운영 신규 설치라면 첫 Sync 전에 `20-statefulset.yaml`의 `storageClassName`을 아래처럼 바꾸는 방향이 좋다.

```yaml
volumeClaimTemplates:
- spec:
    storageClassName: rook-ceph-block-nucleus-retain
```

기존 PVC를 전용 StorageClass로 옮기려면 단순 patch가 아니라 snapshot/restore 또는 새 PVC 마이그레이션 절차로 진행한다.
 단, 이미 생성된 PVC `nucleus-data-omniverse-nucleus-0`는 생성 당시 `rook-ceph-block`을 사용했으므로 StorageClass 이름이 자동으로 바뀌지는 않는다. 현재 live PV는 별도로 `Retain`으로 patch 완료했다.
