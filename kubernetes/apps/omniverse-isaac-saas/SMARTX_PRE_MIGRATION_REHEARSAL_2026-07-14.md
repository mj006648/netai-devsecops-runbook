# Isaac SaaS SmartX 사전 이관 리허설 — 2026-07-14

> 목적: 외부 `eecs-k8s`/`c-k8s`를 변경하기 전에 개인 `smartx-k8s` 엔진과 `twinx-k8s` preset으로 SmartX app catalog 구조를 만들고, 렌더 결과를 MiniX에 적용해 포털과 기존 Isaac Sim 인스턴스가 유지되는지 확인한 실행 기록이다.
> 이 문서는 “어떻게 이관하는가”가 아니라 “어디까지 실제로 검증했는가”만 기록한다. 구현 절차는 [`SMARTX_MIGRATION_PLAN.md`](./SMARTX_MIGRATION_PLAN.md)를 본다.

---

## 1. 결론

개인 저장소에서 다음 구조를 만들고 push 후 fresh clone 기준으로 다시 렌더했다.

```text
mj006648/smartx-k8s
  -> 공통 apps/omniverse-isaac-saas chart

mj006648/twinx-k8s
  -> feature 활성화
  -> patches/omniverse-isaac-saas/values.yaml
```

검증 결과:

```text
Helm lint: 성공
앱 chart render: 7개 Kubernetes resource kind 생성
SmartX root render: twinx-omniverse-isaac-saas Application 생성
preset valueFiles: 정확한 patch 경로 확인
MiniX apply: 포털 rollout 성공
포털 health: 성공
live GPU inventory: Kubernetes DRA 상태 반영
기존 Isaac Sim instance: Running 유지
WebRTC TCP endpoint: 연결 가능
EndpointSlice: Ready
```

최종 Argo CD 이관은 아니다.

```text
개인 SmartX/TwinX shape 검증: 완료
실제 eecs-k8s/c-k8s 변경: 하지 않음
kind-twinx Argo CD sync: control plane이 내려가 있어 하지 않음
MiniX 적용 방식: Helm render 결과를 kubectl apply
GUI WebRTC 2.0.0 영상/입력: 사용자 확인 완료
instance 삭제/GPU 반환: 사용자 UI Delete 후 검증 완료
```

---

## 2. 사용한 저장소와 commit

| 역할 | 저장소 | branch | 검증 commit |
| --- | --- | --- | --- |
| 포털·Isaac Sim source | `mj006648/isaac-twinx` | `main` | `c171142` source + GHCR portal image |
| 개인 SmartX engine | `mj006648/smartx-k8s` | `main` | `31f3682` |
| 개인 TwinX preset | `mj006648/twinx-k8s` | `default` | `4565d2c` |
| 실행 기록 | `mj006648/netai-devsecops-runbook` | `main` | 이 문서 |

외부 저장소는 변경하지 않았다.

```text
SJoon99/eecs-k8s: Isaac SaaS 변경 없음
SJoon99/c-k8s: Isaac SaaS 변경 없음
```

Nucleus의 과거 이관 작업과 이번 Isaac 개인 리허설을 혼동하지 않는다.

---

## 3. 개인 SmartX engine에 추가한 파일

```text
apps/omniverse-isaac-saas/
├── Chart.yaml
├── README.md
├── manifest.yaml
├── patches.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl
    ├── serviceaccount.yaml
    ├── role.yaml
    ├── rolebinding.yaml
    ├── clusterrole.yaml
    ├── clusterrolebinding.yaml
    ├── deployment.yaml
    └── service.yaml
```

수정한 공통 파일:

```text
apps/template/features.yaml
values.yaml
```

참고:

```text
apps/template/defaults.yaml -> ../../values.yaml symlink
```

따라서 default feature 이름 등록은 symlink 대상인 root `values.yaml`에 반영했다.

---

## 4. 추가한 feature graph

```yaml
org.ulagbulag.io/omniverse:
  requires: []

org.ulagbulag.io/omniverse/isaac-saas:
  requires:
    - nvidia.com/gpu
    - nvidia.com/gpu/dynamic-resource-allocation
    - org.ulagbulag.io/omniverse/nucleus
    - org.ulagbulag.io/registry/container/harbor

org.ulagbulag.io/omniverse/nucleus:
  requires:
    - org.ulagbulag.io/omniverse
```

이번 개인 engine에는 실제 Nucleus chart를 새로 복사하지 않았다.

```text
omniverse/nucleus feature = 리허설에서 논리적/선행 설치 dependency
Nucleus live service = MiniX에 기존 설치된 Nucleus 사용
```

실제 eecs-k8s에는 Nucleus app과 feature가 이미 있으므로 Isaac 이관 시 Nucleus key를 중복 추가하지 않는다.

---

## 5. TwinX preset에 추가한 파일과 값

수정:

```text
values.yaml
README.md
patches/README.md
```

추가:

```text
patches/omniverse-isaac-saas/values.yaml
```

활성화한 feature:

```yaml
features:
  - org.ulagbulag.io/omniverse/isaac-saas
  - scalex.io/healthcheck
```

Isaac patch에 넣은 값의 종류:

```text
portal immutable image
Isaac Sim immutable image digest
portal/instance imagePullSecret 이름
DRA resource.k8s.io/v1, driver, DeviceClass
Nucleus URI와 credential Secret 이름/key
portal LoadBalancer IP
A100 WebRTC incompatible 정책
```

넣지 않은 것:

```text
GPU node 목록
GPU UUID 목록
가용 GPU 개수
사용자 instance 목록
Secret 원문
```

---

## 6. 리허설 image 기준

### 6.1 포털

```text
ghcr.io/mj006648/isaac-twinx
immutable tag: sha-333c1a8dac899e47c202b556da80ef1000e7a87e
```

### 6.2 Isaac Sim runtime

```text
repository: 10.34.48.223/omniverse/isaac-sim
digest: sha256:5be32513c96b71a0b7224c87bd59b119f2e52b4461dd950dce14518acdcc0049
```

이 runtime image는 다음을 포함한다.

```text
NVIDIA Isaac Sim 6.0
WebRTC/headless launcher
SmartX Extension 9개
Extension source commit f2606b43c437d1e3b70e16edb011fc3b237bb2e4
Nucleus runtime config 처리
```

Nucleus password는 image에 포함하지 않았다.

---

## 7. Helm 검증

master에서 push된 commit을 fresh clone한 뒤 렌더했다.

### 7.1 app chart

성공한 resource kind:

```text
ServiceAccount
Role
RoleBinding
ClusterRole
ClusterRoleBinding
Service
Deployment
```

### 7.2 SmartX root chart

생성 확인:

```text
twinx-omniverse-isaac-saas
```

Application의 preset values 경로 확인:

```text
$cluster/patches/omniverse-isaac-saas/values.yaml
```

engine source 확인:

```text
ssh://git@github.com/mj006648/smartx-k8s.git
```

확인한 값:

```text
portal immutable SHA
runtime immutable digest
Nucleus endpoint
portal LoadBalancer IP
Secret resource 미렌더링
```

push된 정확한 commit의 fresh clone render 결과:

```text
engine 964c4c1: 성공
preset 2a616de: 성공
```

---

## 8. kind-twinx 상태

master kubeconfig에는 다음 Kind context가 남아 있었다.

```text
kind-datax
kind-edgex
kind-scalex-scheduler-lab
kind-tower
kind-twinx
```

그러나 `kind-twinx` API endpoint는 연결 거부 상태였다.

```text
127.0.0.1:34611 connection refused
active Kind TwinX control-plane 없음
```

따라서 이번 리허설에서는 Kind cluster를 새로 만들거나 기존 상태를 복구하지 않았다. SmartX root render는 성공했지만 live Argo CD multi-source sync 증거는 아니다.

---

## 9. MiniX 실제 적용

개인 SmartX app chart와 TwinX preset patch를 Helm으로 렌더한 뒤 실제 MiniX에 적용했다.

```text
적용 방식: helm template 결과 + kubectl apply
Argo CD ownership: 아님
목적: chart/preset이 기존 standalone manifest를 대체할 수 있는지 검증
```

적용된 포털 image:

```text
ghcr.io/mj006648/isaac-twinx:sha-333c1a8dac899e47c202b556da80ef1000e7a87e
```

결과:

```text
7개 resource configured
portal Deployment rollout 성공
portal Service External IP 10.34.48.222 유지
/healthz 성공
```

MiniX `minix-root-app`은 여전히 이 포털 chart를 소유하지 않는다. 실제 이관 시에는 SmartX root Application/Argo CD ownership으로 바꿔야 한다.

---

## 10. live GPU inventory 결과

적용 후 포털은 Kubernetes API에서 live inventory를 읽었다.

```text
GPU count: 1
available: 0
allocated: 1
```

현재 기존 instance가 GPU를 사용 중이므로 `available=0`, `allocated=1`이 정상이다.

포털이 읽은 대상:

```text
Nodes
NVIDIA DRA ResourceSlices
모든 namespace의 ResourceClaims
```

이 결과로 다음을 확인했다.

- chart/preset에 node 이름을 넣지 않아도 포털이 live node를 표시한다.
- GPU UUID를 patch에 넣지 않아도 ResourceSlice에서 읽는다.
- 기존 ResourceClaim을 읽어 GPU 사용 중 상태를 계산한다.
- preset은 inventory 데이터가 아니라 DRA driver/class와 정책만 제공하면 된다.

---

## 11. 기존 Isaac Sim instance 영향

chart 기반 포털 rollout 후에도 기존 instance는 유지됐다.

```text
instance: minix-e2e
status: Running
node: gpu
stream IP: 10.34.48.224
```

포털 Deployment 교체가 사용자별 동적 Deployment/Service/ResourceClaim을 삭제하지 않았음을 확인했다.

---

## 12. WebRTC 자동 검증

GUI client 없이 확인 가능한 범위는 통과했다.

```text
TCP 10.34.48.224:49100 연결 가능
EndpointSlice address 1개 Ready
UDP 47998 노출
TCP 49100 노출
Isaac Sim streaming app 시작 log 확인
WebRTC component load 확인
Nucleus endpoint config 확인
fatal log 0
```

2026-07-15 사용자 확인:

```text
Isaac Sim WebRTC Streaming Client 2.0.0
Stream IP 10.34.48.224
영상 표시 정상
키보드/마우스 입력 정상
```

정량적인 latency 측정은 이번 범위에 포함하지 않았다.

---

## 13. write/delete 상태

초기 리허설 당시 외부 포털은 read-only였다.

```text
WRITE_ENABLED=false
public create POST: HTTP 403
```

2026-07-15 사용자의 MiniX 실험 요청에 따라 개인 TwinX preset만 임시로 변경했다.

```text
ui.writeEnabled: true
AUTH_ENABLED=false
portal: 10.34.48.222
live /api/config writeEnabled: true
```

공통 SmartX chart 기본값은 false로 유지한다. 현재 설정은 인증 없는 실험용이므로 create/delete와 GPU 반환 검증이 끝나면 preset을 false로 되돌린다.

사용자 WebRTC 확인을 위해 당시 instance를 의도적으로 유지했다.

2026-07-15 사용자 UI Delete로 다음 항목을 모두 완료했다.

```text
instance Delete: 완료
ResourceClaim 삭제: 완료
GPU Available 반환: 완료
Isaac Sim GPU process 종료: 완료
```

검증에 사용한 `minix-e2e` instance는 삭제했으며 ResourceClaim 0개, GPU process 0개, GPU inventory 1 total / 1 available 상태를 확인했다.

2026-07-15에는 개인 TwinX preset의 runtime image를 Nucleus path 보정 r4 digest로 갱신하고 live portal을 rollout했다.

```text
TwinX preset commit: 4565d2c
new instance image: 10.34.48.223/omniverse/isaac-sim@sha256:70399e7db9883341bae8539c8485ac5b17702cdb3a15ea218c687ccc1780c50f
deleted minix-e2e image: r3 digest
```

기존 instance 삭제와 GPU 반환을 확인했다. 초기 수동 E2E 검증용 `isaac-twinx-e2e` Deployment/ClusterIP Service도 최신 포털이 대체하므로 삭제했다. 새 instance를 만들면 r4 image와 `OMNI_PROJECT_PATH=Projects/demonstration`이 함께 적용된다.

같은 날 Nucleus 실데이터 browse/read/write를 확인한 뒤 Content Browser 역할을 분리한 r5로 갱신했다. r4로 실행 중인 `test1`은 사용자 시험을 위해 유지하고, 포털의 새 instance 기본 image만 r5 immutable digest로 변경했다.

```text
TwinX preset commit: 459e34d
portal source/image: 146b39b / ghcr.io/mj006648/isaac-twinx:sha-146b39b5141ccf234c4c6ac3e3b6d210b255ab3f
new instance image: 10.34.48.223/omniverse/isaac-sim@sha256:cbd29a70ce7d743430ed6794db4aa673cd31fe1141783025f014c2092a9cda68
Nucleus direct browse/read/write: Result.OK
Content Browser: Isaac asset root와 Omniverse > NetAI Nucleus mounted server 분리
```

수동 Helm 적용 중 `--namespace omniverse`를 빠뜨려 ClusterRoleBinding subject가 잠시 `default` namespace를 가리켰고 포털 inventory API가 503을 반환했다. namespace를 명시해 재렌더·적용한 뒤 `resourceslices` list 권한과 `/api/gpus`, `/api/instances` 200을 다시 확인했다. 이는 chart의 `.Release.Namespace`가 잘못된 것이 아니라 수동 렌더 명령의 namespace 누락이었다.

---

## 14. 이 리허설이 증명한 것과 증명하지 않은 것

### 증명

- standalone manifest를 SmartX app chart로 나눌 수 있다.
- cluster-specific 값을 preset patch로 분리할 수 있다.
- SmartX feature가 app Application을 생성한다.
- 포털이 immutable image로 rollout된다.
- 포털은 preset에 GPU 목록이 없어도 live inventory를 표시한다.
- 포털 교체가 기존 동적 instance를 자동 prune하지 않는다.
- WebRTC network endpoint가 준비된다.
- WebRTC 2.0.0 client에서 실제 영상과 입력이 동작한다.
- 포털 Delete가 동적 Deployment, Service, ResourceClaim을 제거한다.
- instance 삭제 후 DRA GPU가 Available로 반환되고 GPU process가 종료된다.

### 미증명

- 실제 eecs-k8s/c-k8s branch에서의 merge/sync
- 실제 GPU 대상 클러스터의 Argo CD multi-source credential
- Keycloak 인증 후 사용자별 mutation 권한
- 운영 Harbor TLS/OpenBao/External Secrets

---

## 15. 실제 이관 때 달라질 값

리허설 preset은 MiniX live endpoint를 사용한다. 실제 대상에는 다음을 교체한다.

| 리허설 값 종류 | 실제 이관 시 |
| --- | --- |
| MiniX portal LB IP | 대상 클러스터 예약 IP |
| MiniX Nucleus URI | 대상 Nucleus URI |
| MiniX Harbor repository | 대상 Harbor project/repository |
| MiniX Secret 이름 | 대상 cluster Secret/ExternalSecret 이름 |
| 개인 GHCR portal image | 조직이 승인한 registry/image digest |
| TwinX personal repo branch | 실제 cluster preset targetRevision |

GPU node/UUID는 교체 대상이 아니다. 처음부터 patch에 없으며 live API에서 읽는다.

---

## 16. 다음 작업

1. 새 r5 instance에서 `Omniverse > NetAI Nucleus` 표시와 USD 열기/저장을 사용자 GUI로 확인한다.
2. 실제 GPU 대상 cluster preset을 확정한다.
3. [`SMARTX_MIGRATION_PLAN.md`](./SMARTX_MIGRATION_PLAN.md)에 따라 eecs-k8s chart를 반영한다.
4. 대상 cluster preset patch를 반영한다.
5. Tower Argo CD에서 root/app sync와 ownership을 확인한다.
6. 실행 결과를 별도 execution 문서에 기록한다.
7. MiniX mutation 시험 종료 후 `ui.writeEnabled=false`로 되돌린다.
---

## 17. 한 문장 결론

개인 `smartx-k8s` 공통 chart와 `twinx-k8s` preset 분리는 push된 commit, Helm render, MiniX 실제 apply, live DRA inventory, WebRTC 영상/입력, delete/GPU 반환, Nucleus browse/read/write와 r5 mounted-server 설정까지 검증했으며, 새 r5 GUI 표시를 확인한 뒤 같은 파일 경계를 실제 eecs-k8s와 GPU cluster preset에 옮기면 된다.
