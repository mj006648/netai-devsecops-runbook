# Omniverse Nucleus Kubernetes Runbook

이 문서는 NVIDIA Omniverse Nucleus를 Kubernetes 위에 올리는 PoC 결과와, 이후 SmartX/twinx-k8s 구조로 옮기기 위한 기준을 정리한다.

> 최종 기준: **신규 설치는 처음부터 Nucleus 전용 Rook-Ceph RBD StorageClass `rook-ceph-block-nucleus-retain`을 사용한다.** 기존 MiniX live PoC에서 나중에 PV를 `Retain`으로 패치한 것은 과거 이행 기록일 뿐이며, 신규 설치 절차의 기본 흐름이 아니다.

## 0. 현재 결론

- Nucleus는 공식 Kubernetes chart가 아니라 NVIDIA Enterprise Nucleus Server Compose Stack으로 제공된다.
- Kubernetes에서는 Compose Stack의 서비스 12개를 우선 하나의 StatefulSet Pod 안의 12개 container로 옮겨 검증했다.
- 데이터는 노드 로컬 디스크가 아니라 Rook-Ceph RBD PVC에 저장한다.
- 신규 설치 기준 manifest는 `manifests/nucleus/` 아래에 둔다.
- RBD PVC write/readback은 선행 검증을 완료했으며, 최종 문서에는 Nucleus 배포에 필요한 manifest만 남긴다.

## 1. 최종 권장 구조

```text
ArgoCD Application omniverse-nucleus-poc
  -> 00-storageclass.yaml
     -> StorageClass rook-ceph-block-nucleus-retain
        -> reclaimPolicy: Retain
  -> 00-namespace.yaml
     -> Namespace omniverse
  -> 10-*.yaml
     -> Headless/ClusterIP/LoadBalancer Services
  -> 20-statefulset.yaml
     -> StatefulSet omniverse-nucleus
        -> Pod omniverse-nucleus-0
        -> 12 NVIDIA Nucleus containers
        -> PVC nucleus-data-omniverse-nucleus-0
           -> Rook-Ceph RBD
           -> /omni/data, /omni/log, /omni/temp, /omni/scratch-meta-dump
```

### 왜 전용 StorageClass를 처음부터 쓰는가

기본 `rook-ceph-block` StorageClass는 보통 `reclaimPolicy: Delete`로 운영된다. 이 경우 PVC를 실수로 삭제하면 동적으로 생성된 PV와 underlying RBD image까지 삭제될 수 있다.

Nucleus는 데이터 서버이므로 신규 설치에서는 처음부터 아래 StorageClass를 사용한다.

```text
StorageClass: rook-ceph-block-nucleus-retain
provisioner: rook-ceph.rbd.csi.ceph.com
pool: replicapool
allowVolumeExpansion: true
reclaimPolicy: Retain
volumeBindingMode: Immediate
```

이 설정의 의미:

- PVC 삭제 실수 시 RBD image가 즉시 삭제되는 것을 막는다.
- PVC 용량 확장을 허용한다.
- Nucleus 전용 스토리지 정책을 기본 RBD StorageClass와 분리한다.

주의: `Retain`은 Kubernetes 삭제 lifecycle 보호장치이지 백업이 아니다. Ceph cluster/pool 자체 장애까지 보호하려면 snapshot, off-cluster backup, RBD mirroring이 별도로 필요하다.

## 2. 실제 파일 구조

```text
kubernetes/apps/omniverse-nucleus/
├── README.md
├── RUNBOOK.md
├── manifests/
│   └── nucleus/
│       ├── 00-storageclass.yaml
│       ├── 00-namespace.yaml
│       ├── 10-headless-service.yaml
│       ├── 10-internal-services.yaml
│       ├── 10-loadbalancer-service.yaml
│       └── 20-statefulset.yaml
```

| 파일 | 역할 | 적용 여부 |
| --- | --- | --- |
| `00-storageclass.yaml` | Nucleus 전용 Retain RBD StorageClass | 신규 설치 필수 |
| `00-namespace.yaml` | `omniverse` namespace 생성 | 필수 |
| `10-headless-service.yaml` | StatefulSet용 headless service | 필수 |
| `10-internal-services.yaml` | Compose service DNS를 Kubernetes Service DNS로 대체 | 필수 |
| `10-loadbalancer-service.yaml` | MetalLB 외부 접속 IP/port 제공 | 환경에 맞게 수정 |
| `20-statefulset.yaml` | NVIDIA Nucleus 12개 container + RBD PVC 정의 | 필수 |

파일명 앞의 `00`, `10`, `20`은 사람이 읽기 위한 정렬 prefix이다. ArgoCD의 실제 순서는 manifest의 annotation으로 제어한다.

| Sync wave | Manifest | 이유 |
| --- | --- | --- |
| `0` | StorageClass, Namespace | PVC/Namespaced resource 전제 생성 |
| `1` | Services | Pod 부팅 전에 내부 DNS 이름 준비 |
| `2` | StatefulSet | Secret/PVC/Service 준비 후 실제 Nucleus 실행 |

## 3. NVIDIA 공식 방식과 Kubernetes 변환

NVIDIA 공식 배포 흐름은 Docker Compose이다.

```text
NGC artifact download
  -> nucleus-stack.env 수정
  -> docker login nvcr.io
  -> docker compose pull
  -> docker compose up -d
```

이번 PoC에서는 다음처럼 바꿨다.

| NVIDIA Compose 방식 | Kubernetes PoC 방식 | 이유 |
| --- | --- | --- |
| `docker compose up` | ArgoCD + StatefulSet | GitOps 관리 |
| Compose service 12개 | StatefulSet Pod 안의 container 12개 | Compose stack 전체를 먼저 검증 |
| Docker bind/named volume | Rook-Ceph RBD PVC | 클러스터 스토리지 사용 |
| Compose service name DNS | Kubernetes ClusterIP Service | `nucleus-api`, `nucleus-auth` 이름 유지 |
| host `8080` | MetalLB LoadBalancer `10.34.48.221:8080` | 외부 접속 |
| `.env` 평문 | Kubernetes env + Secret | GitOps/Secret 분리 |

참고 공식 문서:

- Planning Your Installation: https://docs.omniverse.nvidia.com/nucleus/latest/enterprise/installation/planning.html
- Installing an Enterprise Nucleus Server: https://docs.omniverse.nvidia.com/nucleus/latest/enterprise/installation/install-ove-nucleus.html
- Networking and TCP/IP Ports: https://docs.omniverse.nvidia.com/nucleus/latest/ports_connectivity.html
- Backups and Data Restoration: https://docs.omniverse.nvidia.com/nucleus/latest/enterprise/backing-up-and-restoring-nucleus.html
- NGC Enterprise Nucleus collection: https://catalog.ngc.nvidia.com/orgs/nvidia/omniverse/collections/enterprise-nucleus/-/artifacts

## 4. StatefulSet을 쓰는 이유

Nucleus는 무상태 웹앱이 아니라 데이터 서버에 가깝다. 따라서 Deployment보다 StatefulSet이 맞다.

- Pod 이름이 안정적이다: `omniverse-nucleus-0`
- PVC 이름이 안정적이다: `nucleus-data-omniverse-nucleus-0`
- `volumeClaimTemplates`로 Pod 전용 RBD PVC를 만들 수 있다.
- 단일 writer 데이터 서버 구조를 명확히 표현할 수 있다.

현재 PoC는 `replicas: 1`만 검증했다. Nucleus를 replica 수만 늘려 HA로 만드는 것은 검증하지 않았다.

## 5. 왜 Pod가 `12/12`인가

`kubectl get pod`의 `12/12`는 Pod 1개 안에 container가 12개 있고, 12개 모두 Ready라는 뜻이다. NVIDIA Compose Stack의 12개 service를 하나의 StatefulSet Pod 안에 옮겼기 때문에 `1/1`이 아니라 `12/12`로 보인다.

대표 container:

```text
nucleus-api
nucleus-lft
nucleus-lft-lb
nucleus-log-processor
nucleus-resolver-cache
utl-monpx
nucleus-discovery
nucleus-auth
nucleus-navigator
nucleus-search
nucleus-thumbnails
nucleus-tagging
```

## 6. RBD 마운트 기준

Nucleus persistent 데이터는 RBD PVC를 filesystem으로 mount한 뒤 아래 경로에 저장된다.

```text
/omni/data
/omni/log
/omni/temp
/omni/scratch-meta-dump
/var/lib/omni/nucleus-data/empty
```

검증 당시 `/omni/data`에서 실제 Nucleus 데이터 파일을 확인했다.

```text
/omni/data/usergroups.1.0
/omni/data/meta.1.1
/omni/data/content.1.1
/omni/data/omniobjects.1.0
/omni/data/__version_tag
```

컨테이너 입장에서는 실제 물리 위치가 Ceph RBD인지 로컬 디스크인지 중요하지 않다. Kubernetes/Ceph CSI가 RBD block device를 노드에 attach하고 filesystem으로 mount한다. 다만 RBD는 기본적으로 `ReadWriteOnce` 단일 writer로 보는 것이 안전하므로 `replicas: 1` StatefulSet과 맞다.

## 7. Secret과 NGC 인증

NVIDIA image pull에는 `nvcr.io` 인증이 필요하다.

```bash
kubectl -n omniverse create secret docker-registry nvcr-io \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password='<NGC_API_KEY>'
```

Git에 넣지 않는 값:

```text
NGC API Key
Nucleus admin password
Nucleus service password
Auth signing key
Discovery token
Salt 값
SAML metadata 실제 값
NVIDIA Compose artifact 원본
```

PoC runtime Secret:

```text
nvcr-io             # nvcr.io imagePullSecret
nucleus-secrets     # auth signing key, discovery token, salts, SAML blank metadata
nucleus-passwords   # admin/service password
```

운영 전에는 직접 생성한 Secret을 OpenBao + External-Secrets로 바꾼다.

## 8. 접속과 계정

현재 PoC 접속 주소:

```text
http://10.34.48.221:8080/
```

기본 관리자 계정은 NVIDIA Compose 기본값에 맞춘 `omniverse`이다. 비밀번호는 Git에 적지 않고 `nucleus-passwords` Secret의 `master-password`에서 온다.

비밀번호 조회:

```bash
kubectl -n omniverse get secret nucleus-passwords \
  -o jsonpath='{.data.master-password}' | base64 -d; echo
```

관리자 비밀번호 변경:

```bash
kubectl -n omniverse patch secret nucleus-passwords \
  --type merge \
  -p '{"stringData":{"master-password":"<NEW_ADMIN_PASSWORD>"}}'

kubectl -n omniverse rollout restart statefulset/omniverse-nucleus
```

새 사용자 예시:

1. Secret에 password key 추가
2. `20-statefulset.yaml`의 `nucleus-auth` env에 secretKeyRef 추가
3. `CREDENTIAL_USERS` JSON에 사용자 추가
4. ArgoCD sync 또는 StatefulSet restart

실제 비밀번호는 `<NETAI_PASSWORD>` 같은 placeholder만 문서/manifest에 두고, 값은 Secret Store에 넣는다.

## 9. 데이터 보호 기준

| 상황 | 데이터 보존 기대 | 필요한 보호장치 |
| --- | --- | --- |
| Pod 재시작/삭제 | 유지 | StatefulSet + 같은 PVC 재부착 |
| StatefulSet 삭제/scale down | 유지 | `persistentVolumeClaimRetentionPolicy: Retain` |
| PVC 실수 삭제 | RBD image 보존 기대 | StorageClass/PV `reclaimPolicy: Retain` |
| 단일 OSD/노드 장애 | Ceph 복제로 유지 기대 | Ceph pool `replicated.size: 3`, `failureDomain: host` |
| Ceph pool/cluster 손상 | 보장 불가 | VolumeSnapshot, off-cluster backup, RBD mirroring |
| 사이트/클러스터 전체 손실 | 보장 불가 | 별도 클러스터/오브젝트 스토리지/NAS 백업 |

운영 권장 계층:

1. StatefulSet PVC retention policy
2. Nucleus 전용 Retain StorageClass
3. Ceph replicated pool
4. 정기 RBD VolumeSnapshot
5. off-cluster backup
6. 필요 시 RBD mirroring 기반 DR

공식 참고:

- Kubernetes StorageClass reclaimPolicy: https://kubernetes.io/docs/concepts/storage/storage-classes/#reclaim-policy
- Rook Ceph RBD block storage: https://rook.io/docs/rook/latest-release/Storage-Configuration/Block-Storage-RBD/block-storage/
- Rook Ceph CSI snapshots: https://rook.io/docs/rook/latest-release/Storage-Configuration/Ceph-CSI/ceph-csi-snapshot/
- Rook RBD mirroring/DR: https://rook.io/docs/rook/latest-release/Storage-Configuration/Block-Storage-RBD/rbd-mirroring/

## 10. 기존 MiniX live PoC 이행 노트

현재 MiniX live PoC는 Nucleus 전용 StorageClass를 만들기 전에 먼저 `rook-ceph-block`으로 PVC가 생성되었다. 그래서 live StatefulSet의 `volumeClaimTemplates.storageClassName`은 바로 바꾸지 않았다.

이유:

- StatefulSet `volumeClaimTemplates` 변경은 기존 PVC에 자동 반영되지 않는다.
- 기존 PVC의 StorageClass 이름도 자동 변경되지 않는다.
- Git에서 바로 바꾸면 ArgoCD sync 실패 또는 재생성/마이그레이션 절차가 필요할 수 있다.

대신 live PV는 아래처럼 `Retain`으로 패치했다.

```bash
PV=$(kubectl -n omniverse get pvc nucleus-data-omniverse-nucleus-0 -o jsonpath='{.spec.volumeName}')
kubectl patch pv "$PV" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
kubectl get pv "$PV" -o jsonpath='{.metadata.name} {.spec.persistentVolumeReclaimPolicy}{"\n"}'
```

따라서 구분은 다음과 같다.

| 대상 | StorageClass | 보호 상태 |
| --- | --- | --- |
| 기존 MiniX live PVC | `rook-ceph-block` | PV를 직접 `Retain`으로 패치 |
| 신규 설치/운영 권장 | `rook-ceph-block-nucleus-retain` | 처음부터 Retain PV 생성 |

기존 PVC를 전용 StorageClass로 옮기려면 snapshot/restore 또는 새 PVC 마이그레이션 절차로 진행한다.

## 11. 트러블슈팅 기록

### `nucleus-log-processor` 초기 restart

초기 부팅 중 `nucleus-log-processor`가 `nucleus-api:3006`에 너무 빨리 접근하면서 2번 재시작했다.

```text
attempting to connect to ws://nucleus-api:3006
ConnectionRefusedError: Connect call failed
```

이후 `nucleus-api`가 준비되면서 정상 Ready가 되었다. 운영 전에는 startupProbe/readinessProbe 또는 startup ordering을 더 정리한다.

### 내부 DNS/Endpoint 문제

Nucleus container들은 bootstrap 중 서로의 service name으로 먼저 붙어야 한다. Kubernetes Service는 기본적으로 Ready Pod만 endpoint로 넣기 때문에 circular bootstrap 문제가 생길 수 있다.

해결:

```yaml
publishNotReadyAddresses: true
```

내부 ClusterIP Service들에 이 옵션을 넣었다.

### `nucleus-api:3006` 포트

Compose에서는 같은 network 안의 container port가 바로 보이지만 Kubernetes Service는 선언한 port만 접근 가능하다. 따라서 내부 `nucleus-api` Service에 `service-api` port `3006`을 추가했다. 이 포트는 외부 LoadBalancer에는 열지 않는다.

### Web 8080이 metrics로 붙던 문제

Pod 내부에서 `utl-monpx`가 8080을 쓰고 Navigator UI는 80을 쓴다. 그래서 외부 Service는 `8080 -> targetPort 80`으로 둔다.

```yaml
ports:
  - name: web
    port: 8080
    targetPort: 80
```

## 12. 검증 명령

```bash
kubectl -n argocd get app omniverse-nucleus-poc -o wide
kubectl -n omniverse get sts,pvc,pod,svc -o wide
kubectl -n omniverse get pod omniverse-nucleus-0 \
  -o jsonpath='{range .status.containerStatuses[*]}{.name}{" ready="}{.ready}{" restart="}{.restartCount}{"\n"}{end}'
kubectl -n omniverse logs omniverse-nucleus-0 -c nucleus-api --tail=100
kubectl -n omniverse logs omniverse-nucleus-0 -c nucleus-auth --tail=100
curl -fsS -D - http://10.34.48.221:8080/ | head
```

정상 기준:

```text
ArgoCD Application: Synced / Healthy
StatefulSet: omniverse-nucleus 1/1 Ready
Pod: omniverse-nucleus-0 12/12 Running
Service: omniverse-nucleus LoadBalancer 10.34.48.221
Web: Omniverse Navigator 응답
```

## 13. 운영화 전에 해야 할 일

- kube-scheduler / kube-controller-manager 안정화
- `nodeName: com3` 제거
- resource requests/limits 재산정
- startupProbe/readinessProbe/livenessProbe 추가
- OpenBao + External-Secrets로 Secret 관리 전환
- 운영 DNS/TLS/Ingress 또는 Gateway 결정
- PVC 용량 산정 및 expansion 정책 확인
- RBD snapshot/restore 절차 문서화
- off-cluster backup 또는 RBD mirroring 검토
- Nucleus OIDC/Keycloak 연동 여부 검토

## 14. SmartX 구조로 옮길 때

현재 PoC는 순수 Kubernetes manifest로 검증했다. 다음 단계에서는 SmartX 방식에 맞춰 엔진/catalog와 cluster preset을 분리한다.

예상 방향:

```text
smartx-k8s 또는 eecs-k8s 엔진
  -> apps/omniverse-nucleus/
     -> manifest.yaml
     -> values.yaml
     -> templates/statefulset.yaml
     -> templates/services.yaml
     -> templates/storageclass.yaml

twinx-k8s preset
  -> values.yaml에서 feature 활성화
  -> patches/omniverse-nucleus/values.yaml
     -> loadBalancerIP
     -> storageClassName
     -> domain/TLS
     -> secretRef
```

예상 feature 이름:

```text
org.ulagbulag.io/omniverse/nucleus
```

예상 의존성:

```yaml
org.ulagbulag.io/omniverse/nucleus:
  requires:
    - org.ulagbulag.io/cni
    - org.ulagbulag.io/csi
    - org.ulagbulag.io/csi/block
    - org.ulagbulag.io/distributed-storage-cluster/ceph
```

## 15. 결론

이번 PoC에서 확인한 결론은 다음이다.

- NVIDIA Enterprise Nucleus Compose Stack `2023.2.10`의 실제 이미지를 Kubernetes에서 실행할 수 있다.
- Compose service 12개를 한 StatefulSet Pod의 12개 container로 옮기는 초기 방식은 동작한다.
- Rook-Ceph RBD PVC를 Nucleus 실제 데이터/로그 경로로 사용할 수 있다.
- MetalLB LoadBalancer IP를 통해 Nucleus Navigator와 Isaac Sim client 접속이 가능하다.
- 신규 설치/운영 이관은 처음부터 `rook-ceph-block-nucleus-retain` StorageClass를 써야 한다.
- 다만 Ceph 자체 장애에 대비하려면 Retain만으로 부족하며 snapshot/off-cluster backup/DR 설계가 필요하다.
