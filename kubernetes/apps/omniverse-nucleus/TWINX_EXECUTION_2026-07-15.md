# Omniverse Nucleus TwinX 실행 기록 — 2026-07-15

> 이 문서는 계획서가 아니라 TwinX에서 실제 수행한 Nucleus 실행 기록이다.
> Secret 원문 값은 기록하지 않으며, 이 실행에서는 `eecs-k8s`/`c-k8s` 코드를 변경하지 않았다.

## 1. 결론

TwinX에는 SmartX `eecs-k8s`/`c-k8s` 이관 코드를 반영하지 않고, `TwinX-Ops`의 기존 `argocd/omniverse` root Application 아래에 raw app으로 Nucleus를 추가했다.

```text
TwinX-Ops raw app:
  argocd/omniverse/apps/omniverse-nucleus-twinx/install.yaml

TwinX-Ops root values:
  argocd/omniverse/values.yaml
```

배포 결과:

```text
namespace: omniverse
StatefulSet: omniverse-nucleus-twinx
Pod: omniverse-nucleus-twinx-0
Pod readiness: 12/12 Running/Healthy
LoadBalancer: 10.38.38.245
PVC: 10Gi RBD, Retain
Argo app health: Healthy
Argo sync 표시: OutOfSync
argocd app diff: rc=0
```

`argocd app diff rc=0`인데 Argo CD status가 `OutOfSync`로 남아 있는 표시 불일치가 있었다. live diff 기준으로는 차이가 없었으므로, 이 문서는 실제 Kubernetes 상태와 diff 결과를 기준으로 기록한다.

## 2. 변경하지 않은 대상

이번 실행의 안전 경계다.

```text
기존 namespace oos-sim
기존 oos-sim Isaac/OVAS/Streaming 워크로드
기존 외부 Nucleus 10.38.38.32
기존 외부 Nucleus credential/Secret
eecs-k8s
c-k8s
```

수행하지 않은 작업:

- `oos-sim` 리소스를 수정하거나 삭제하지 않았다.
- 기존 외부 Nucleus `10.38.38.32`를 교체하거나 마이그레이션하지 않았다.
- 기존 Secret 원문을 문서화하거나 복사하지 않았다.
- `eecs-k8s`/`c-k8s`에는 코드 변경을 하지 않았다. 해당 저장소들은 계획만 유지한다.

## 3. TwinX-Ops 적용 구조

### 3.1 raw app 위치

Nucleus는 TwinX에서 먼저 독립 raw manifest로 실행했다.

```text
argocd/omniverse/apps/omniverse-nucleus-twinx/install.yaml
```

이 raw manifest에는 Nucleus 실행에 필요한 Service, StatefulSet, PVC template 설정이 포함된다. namespace는 child Application의 `CreateNamespace=true`로 생성한다. Helm chart로 새로 감싸지 않고, `argocd/omniverse`의 기존 child Application 패턴에 맞춰 등록했다.

### 3.2 root values 등록

상위 root Application에는 `argocd/omniverse/values.yaml`에서 child Application을 등록했다.

```text
application name: omniverse-nucleus-twinx
namespace: omniverse
source path: argocd/omniverse/apps/omniverse-nucleus-twinx
```

이 등록은 TwinX-Ops root values의 app 목록만 확장한다. 기존 `argocd/omniverse` chart/template 구조는 변경 대상이 아니다.

### 3.3 namespace

신규 namespace를 사용했다.

```text
namespace: omniverse
```

이 선택으로 기존 `oos-sim` 워크로드와 리소스 이름 충돌을 피했다.

## 4. 스토리지와 외부 접속

### 4.1 LoadBalancer

Nucleus 외부 접속용 LoadBalancer IP:

```text
10.38.38.245
```

최초 revision에는 이전 MiniX annotation `metallb.io/loadBalancerIPs: 10.34.48.221`과 TwinX용 `spec.loadBalancerIP: 10.38.38.245`가 동시에 남아 있었다. MetalLB webhook은 두 필드의 동시 사용을 거부했다. 최종 manifest는 `metallb.io/loadBalancerIPs: 10.38.38.245` 하나만 유지하고 `spec.loadBalancerIP`는 제거했다.

### 4.2 RBD PVC

Nucleus 데이터 PVC:

```text
size: 10Gi
backend: RBD
reclaim policy: Retain
```

`Retain`은 PVC 삭제 실수 시 underlying RBD image가 즉시 삭제되는 것을 막기 위한 Kubernetes lifecycle 보호장치다. 백업을 대체하지는 않는다.

## 5. 이미지

Nucleus Compose Stack의 12개 컨테이너 이미지는 TwinX Harbor digest 이미지로 고정했다.

```text
registry: Harbor
image count: 12
reference policy: digest pinning
```

문서에는 Secret 원문이나 registry credential을 기록하지 않는다. 이미지 reference는 실행 manifest에서 digest로 추적한다.

## 6. Argo CD 실행 메모

### 6.1 stale operation 종료

Argo CD에 stale operation이 남아 있었다.

```text
실행 중이던 revision: 70fed21
당시 Git 최신 revision: f6f2e07
```

Application의 operation state를 `Terminating`으로 전환해 이전 작업을 종료한 뒤 최신 revision 기준으로 다시 sync했다. 이 클러스터의 Application CRD에서는 별도 status subresource patch가 `NotFound`를 반환했기 때문에, Application 본체의 status를 merge patch하는 방식으로 종료했다.

### 6.2 최종 revision

수정은 다음 순서로 반영됐다.

```text
70fed21  feat: add TwinX Nucleus
f6f2e07  fix: correct TwinX Nucleus services
7f1c74f  fix: resolve TwinX Nucleus API
4c49253  fix: separate Nucleus ports
```

최종 실행 기준은 `4c49253`이다.

### 6.3 최신 sync

stale operation 종료 후 최신 `TwinX-Ops` revision으로 root/child Application sync를 진행했다.

결과:

```text
Pod: 12/12 Running/Healthy
Argo health: Healthy
Argo sync status: OutOfSync
argocd app diff: rc=0
```

따라서 현재 남은 이슈는 리소스 차이가 아니라 Argo CD 표시 상태 불일치로 본다. 후속 확인 시에는 `argocd app diff`와 live Kubernetes 리소스를 함께 확인한다.

## 7. Kubernetes manifest 정리 사항

### 7.1 MetalLB 설정 충돌 제거

LoadBalancer Service에서 MetalLB annotation과 `spec.loadBalancerIP`가 동시에 IP를 지정하는 형태를 정리했다.

목표:

```text
LoadBalancer IP: 10.38.38.245
표현 방식: 중복 지정 제거
```

### 7.2 Service selector 정리

Service selector가 실제 Pod label과 정확히 맞도록 정리했다.

목표:

```text
Service -> omniverse-nucleus-twinx-0 Pod endpoint 연결
불필요하거나 맞지 않는 selector 제거
```

### 7.3 Compose-to-one-Pod 포트 충돌 원인

NVIDIA Nucleus Compose Stack의 여러 service를 Kubernetes StatefulSet의 하나의 Pod 안에 12개 container로 옮기면서, Compose에서는 분리돼 있던 container-local port가 동일 Pod network namespace 안에서 충돌했다.

충돌한 포트:

| 포트 | 충돌 container | 원인 |
| --- | --- | --- |
| `3030` | `nucleus-lft-lb` vs `nucleus-lft` | Compose service별 network namespace가 Pod 하나로 합쳐지며 같은 listen port 충돌 |
| `9500` | `nucleus-api` vs `nucleus-log-processor` | 같은 Pod network namespace에서 동일 port 사용 |

### 7.4 포트 충돌 해결

Pod 내부 container port를 분리하고, 외부/내부 Service port는 기존 기대값을 유지했다.

| 대상 | container listen port | Service port 매핑 |
| --- | --- | --- |
| LFT | `3031` | `3030 -> 3031` |
| log processor | `9501` | `9500 -> 9501` |

`nucleus-api`에는 localhost 기반 내부 이름 해석이 필요해 hostAlias를 추가했다.

```text
nucleus-api hostAlias: 127.0.0.1
```

이 조합으로 Compose service 간 기대 포트는 Service에서 유지하면서, 한 Pod 내부의 실제 listen port 충돌은 제거했다.

## 8. 검증 결과

검증된 상태:

```text
namespace omniverse 생성
LoadBalancer 10.38.38.245 할당
RBD PVC 10Gi Bound
StatefulSet Ready
Pod omniverse-nucleus-twinx-0 Running
container readiness 12/12
Argo health Healthy
argocd app diff rc=0
```

현재 주의할 상태:

```text
Argo sync status: OutOfSync
argocd app diff: rc=0
판단: 표시 불일치. live diff는 없음.
```

## 9. eecs-k8s/c-k8s 상태

이번 TwinX 실행에서 `eecs-k8s`와 `c-k8s`는 계획만 유지했다.

```text
eecs-k8s: 코드 변경 없음
c-k8s: 코드 변경 없음
```

SmartX/eecs-k8s 기준의 재현·변경 계획은 기존 문서를 따른다.

- [`SMARTX_EECS_MIGRATION_PLAN.md`](./SMARTX_EECS_MIGRATION_PLAN.md)
- [`SMARTX_EECS_EXECUTION.md`](./SMARTX_EECS_EXECUTION.md)

TwinX raw app 실행 기록은 이 문서가 기준이다.

## 10. isaac-twinx 포털과의 현재 경계

`isaac-twinx` 애플리케이션 소스 자체는 원격 `main`과 일치한다.

```text
local HEAD: bd7d6f09e8623ceeedd79cd9a6b3c4cea13f1504
origin/main: bd7d6f09e8623ceeedd79cd9a6b3c4cea13f1504
deployed portal image tag: sha-bd7d6f09e8623ceeedd79cd9a6b3c4cea13f1504
test result: 37 passed
```

따라서 일반 GPU/MIG inventory, DRA v1 resource 생성, instance launch/delete, Nucleus env 주입 기능은 최신 소스에 들어 있다. 이번 Nucleus 장애 수정은 포털 Python 코드가 아니라 `TwinX-Ops`의 Nucleus manifest 수정이므로 `isaac-twinx` 저장소에 중복 복사하지 않는다.

다만 현재 TwinX에 배포된 포털은 아직 **읽기 전용 preview 설정**이다.

```text
portal LoadBalancer: 10.38.38.243
WRITE_ENABLED: false
ISAAC_SIM_IMAGE: 비어 있음
OMNI_SERVER: omniverse://10.38.38.32/
new TwinX Nucleus: omniverse://10.38.38.245/
```

즉, 포털 소스와 이미지까지는 최신이지만 새 Nucleus `10.38.38.245`를 사용하는 실제 launch/delete 배포로 전환한 상태는 아니다. Harbor에는 다음 Isaac Sim 이미지가 준비돼 있으나 포털 manifest에는 아직 주입하지 않았다.

```text
10.38.38.210/library/isaac-sim:6.0-netai-bd7d6f0
digest: sha256:5511d44476458ba5cb415d991a2f6bc3c24cdfff36a39eca22f3dbcfa9c69e31
```

다음 단계는 `argocd/omniverse/apps/isaac-twinx-preview/install.yaml`의 클러스터별 설정에서만 다음을 변경하는 것이다.

1. `ISAAC_SIM_IMAGE`를 위 digest image로 설정한다.
2. `OMNI_SERVER`를 `omniverse://10.38.38.245/`로 설정한다.
3. `NUCLEUS_SECRET_NAME`을 신규 TwinX client credential Secret 참조로 바꾼다.
4. namespace `omniverse` 범위의 create/delete RBAC를 추가한다.
5. 마지막에 `WRITE_ENABLED=true`로 전환한 뒤 launch, WebRTC, delete, GPU 반환을 검증한다.

이 전환 전까지는 `10.38.38.243` 포털을 GPU/MIG inventory 확인용으로만 사용한다.

