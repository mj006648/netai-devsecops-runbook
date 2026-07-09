# Omniverse Nucleus on Kubernetes PoC

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

