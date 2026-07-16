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

## 10. isaac-twinx 포털과의 최종 검증 경계

Nucleus 장애 수정 이후 포털을 실제 write 모드로 전환하고, 신규 Nucleus `10.38.38.245`를 사용하는 두 Isaac Sim 인스턴스를 실행했다.

```text
isaac-twinx source/origin: 47dcfee
tests: 38 passed
portal: 10.38.38.243
WRITE_ENABLED: true
OMNI_SERVER: omniverse://10.38.38.245/
Isaac Sim digest: sha256:c3a5b1b3402f3f2d6185fccee158023da59e99748ce096c33d5a2404fdea9bb7
```

검증 결과:

```text
L40S index 7과 sv4000-1 A6000 동시 Running/Ready
각 Pod에서 omni.client stat(OMNI_SERVER): Result.OK
Nucleus entry present: True
Nucleus HTTP 8080: 200
Extension 9개 image 포함과 Kit 검색 경로 등록 확인
MiniX 10.34.48.*와 외부 Nucleus 10.38.38.32의 image/runtime hardcoding 없음
portal DELETE: 두 인스턴스 모두 HTTP 204
Deployment/Service/ResourceClaim 잔여: 0
두 DRA GPU: Available 반환
```

Extension은 모두 이미지에 포함·등록하지만 자동 활성화하지 않는다. 각 기능의 backend/asset과 Isaac Sim 6.0 호환성을 확인한 뒤 Extension Manager에서 필요한 것만 활성화한다.

`10.38.38.32`는 기존 연구 환경으로 계속 보호하며, 이번 검증의 Isaac Sim은 새 Kubernetes Nucleus `10.38.38.245`에만 연결했다. 상세한 GPU UUID, Stream IP, image build와 삭제 증거는 다음 문서를 기준으로 한다.

- [`../omniverse-isaac-saas/TWINX_ISAAC_SIM_E2E_2026-07-15.md`](../omniverse-isaac-saas/TWINX_ISAAC_SIM_E2E_2026-07-15.md)
