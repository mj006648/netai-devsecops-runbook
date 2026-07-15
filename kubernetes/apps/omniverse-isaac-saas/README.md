# Omniverse Isaac SaaS SmartX 이관 문서

이 디렉터리는 원본 `SmartX-Team/Omniverse/isaac-saas`를 필요한 기능만 남긴 `isaac-twinx` MVP로 축소하고, MiniX에서 실제 검증한 뒤 SmartX `eecs-k8s` 공통 app catalog와 GPU cluster preset으로 옮기는 전 과정을 분리해 기록한다.

## 문서 역할

| 파일 | 역할 | 언제 읽는가 |
| --- | --- | --- |
| [`ISAAC_UI_MVP_SCOPE.md`](./ISAAC_UI_MVP_SCOPE.md) | 제품/설계 기준. 원본에서 무엇을 유지·변경·제거했는지, UI·GPU 선택·image·Nucleus·Extension 경계를 설명 | 무엇을 만들었고 왜 기능을 뺐는지 이해할 때 |
| [`MINIX_GPU_DRA_POC_2026-07-13.md`](./MINIX_GPU_DRA_POC_2026-07-13.md) | MiniX Kubernetes 1.34.3 업그레이드, GPU Operator DRA 전환, RTX 3090 exact selection 실행 기록 | 클러스터/DRA 전제를 확인할 때 |
| [`MINIX_ISAAC_SIM_E2E_2026-07-14.md`](./MINIX_ISAAC_SIM_E2E_2026-07-14.md) | Harbor, Isaac Sim 6.0 image, DRA instance, Nucleus, WebRTC endpoint의 실제 통합 실행 증거 | standalone 구현이 실제로 동작했는지 확인할 때 |
| [`SMARTX_PRE_MIGRATION_REHEARSAL_2026-07-14.md`](./SMARTX_PRE_MIGRATION_REHEARSAL_2026-07-14.md) | 개인 `smartx-k8s`/`twinx-k8s` chart·preset 렌더와 MiniX 적용 결과 | 실제 eecs/c 변경 전 SmartX 구조 검증 결과를 볼 때 |
| [`TWINX_CONTROL1_GPU_MIG_PREVIEW_2026-07-15.md`](./TWINX_CONTROL1_GPU_MIG_PREVIEW_2026-07-15.md) | 실제 TwinX GPU/MIG inventory와 `TwinX-Ops/argocd/omniverse` 읽기 전용 포털 준비·안전 검증 기록 | 이기종 GPU/MIG와 TwinX Argo 배포 경계를 확인할 때 |
| [`SMARTX_MIGRATION_PLAN.md`](./SMARTX_MIGRATION_PLAN.md) | 실제 구현 가이드. eecs-k8s/c-k8s의 어느 파일에 어떤 코드를 넣고 왜 넣는지, 검증·rollback까지 설명 | 실제 이관 코드를 작성하거나 검토할 때 |
| [`../omniverse-nucleus/TWINX_EXECUTION_2026-07-15.md`](../omniverse-nucleus/TWINX_EXECUTION_2026-07-15.md) | TwinX-Ops raw app으로 새 `omniverse` namespace에 Nucleus를 실행한 기록. 기존 `oos-sim`과 외부 Nucleus `10.38.38.32` 비변경 경계 포함 | TwinX Isaac 실행 환경의 Nucleus 경계를 확인할 때 |

## 권장 읽는 순서

### 전체 흐름을 처음 이해할 때

1. `ISAAC_UI_MVP_SCOPE.md`
2. `MINIX_GPU_DRA_POC_2026-07-13.md`
3. `MINIX_ISAAC_SIM_E2E_2026-07-14.md`
4. `SMARTX_PRE_MIGRATION_REHEARSAL_2026-07-14.md`
5. `TWINX_CONTROL1_GPU_MIG_PREVIEW_2026-07-15.md`
6. `SMARTX_MIGRATION_PLAN.md`
7. Nucleus 경계가 필요하면 `../omniverse-nucleus/TWINX_EXECUTION_2026-07-15.md`

### 바로 eecs-k8s/c-k8s 이관 작업을 할 때

1. `SMARTX_MIGRATION_PLAN.md`에서 저장소·파일·values 경계를 확인한다.
2. `SMARTX_PRE_MIGRATION_REHEARSAL_2026-07-14.md`에서 이미 검증한 commit과 render 결과를 확인한다.
3. `TWINX_CONTROL1_GPU_MIG_PREVIEW_2026-07-15.md`에서 실제 이기종 GPU/MIG와 Argo 안전 경계를 확인한다.
4. `MINIX_ISAAC_SIM_E2E_2026-07-14.md`에서 live 성공 기준을 확인한다.
5. 기능 범위에 의문이 있을 때만 `ISAAC_UI_MVP_SCOPE.md`로 돌아간다.

## 문서 간 중복 방지 원칙

```text
MVP_SCOPE      = 무엇을 만들고 왜 뺐는가
DRA_POC        = Kubernetes/GPU 기반이 준비됐는가
MINIX_E2E      = standalone 앱과 image가 실제로 실행됐는가
REHEARSAL      = SmartX chart/preset 모양으로도 동작했는가
TWINX_PREVIEW  = 실제 이기종 GPU/MIG cluster에 안전하게 올릴 모양인가
MIGRATION_PLAN = 실제 eecs-k8s/cluster preset에 어떤 코드를 넣는가
```

같은 실행 결과를 여러 문서에 복사하지 않는다. 구현 가이드는 실행 증거 문서로 링크하고, 실행 증거는 제품 범위를 다시 설명하지 않는다.

## 현재 상태

```text
MiniX Kubernetes 1.34.3 + NVIDIA DRA: 검증 완료
isaac-twinx portal: 구현/테스트/배포 완료
Isaac Sim 6.0 r5 image + Extension 9개: build/push/runtime pull 검증 완료
Nucleus endpoint/Secret 주입과 포트 도달성: 확인 완료
Nucleus asset browse/read/write: 실행 Pod의 Omniverse Client로 확인 완료
Nucleus Content Browser 분리: Isaac asset root는 read-only Isaac Sim collection, 서버 root는 r5의 Omniverse > NetAI Nucleus로 분리
WebRTC 2.0.0 영상/입력: 사용자 확인 완료
MiniX 10.34.48.222 Create/Delete: 실험을 위해 임시 활성화
개인 SmartX/TwinX chart/preset 리허설: 완료
TwinX control1 일반 GPU/MIG 자동 inventory source: 검증 완료
TwinX-Ops 읽기 전용 raw manifest와 내부 Harbor image: push 완료
TwinX Isaac preview Argo CD sync와 live 웹 확인: 완료, 10.38.38.243 read-only inventory
TwinX Nucleus raw app: omniverse namespace, LB 10.38.38.245, RBD 10Gi Retain, Pod 12/12 Running/Healthy; 기존 oos-sim 및 외부 Nucleus 10.38.38.32 비변경; eecs-k8s/c-k8s 코드 변경 없음
isaac-twinx source/origin/deployed portal image: bd7d6f0 일치, 37 tests passed
TwinX portal -> 신규 Nucleus 10.38.38.245 실제 launch/delete 전환: 아직 하지 않음, 현재 WRITE_ENABLED=false 및 기존 10.38.38.32 설정 유지
실제 eecs-k8s/c-k8s Isaac 반영: 아직 하지 않음
instance 삭제/GPU 반환: 사용자 UI Delete 후 검증 완료
기존 minix-e2e instance와 구버전 isaac-twinx-e2e 포털: 삭제 완료
live portal API/RBAC: ClusterRoleBinding 대상 namespace를 omniverse로 교정, /api/gpus와 /api/instances 200 확인
현재 test1: r4로 계속 실행 중, 새 instance부터 r5 사용
```

Nucleus 자체의 eecs-k8s/c-k8s 이관과 C 클러스터 배포는 이미 완료됐으며, 관련 문서는 [`../omniverse-nucleus/`](../omniverse-nucleus/)에 있다. TwinX에서는 `eecs-k8s`/`c-k8s`를 변경하지 않고 `TwinX-Ops` raw app으로 새 `omniverse` namespace에 Nucleus를 실행했으며, 기존 `oos-sim`과 외부 Nucleus `10.38.38.32`는 변경하지 않았다. 세부 기록은 [`../omniverse-nucleus/TWINX_EXECUTION_2026-07-15.md`](../omniverse-nucleus/TWINX_EXECUTION_2026-07-15.md)를 기준으로 한다.
