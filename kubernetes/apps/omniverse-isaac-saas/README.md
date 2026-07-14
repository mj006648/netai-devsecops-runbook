# Omniverse Isaac SaaS SmartX 이관 문서

이 디렉터리는 `SmartX-Team/Omniverse/isaac-saas`를 우리 SmartX/eecs-k8s 구조에 맞게 이관하기 위한 문서다.

## 문서 역할

| 파일 | 역할 |
| --- | --- |
| [`ISAAC_UI_MVP_SCOPE.md`](./ISAAC_UI_MVP_SCOPE.md) | 현재 구현의 단일 기준 문서. 원본 분석, 유지/변경/제거 범위, GPU 선택, 이미지/Nucleus/Extension, SmartX 반영, 검증 절차 |
| [`SMARTX_MIGRATION_PLAN.md`](./SMARTX_MIGRATION_PLAN.md) | 기존 링크 호환을 위한 이전 안내. 상세 설계는 포함하지 않음 |
| [`MINIX_GPU_DRA_POC_2026-07-13.md`](./MINIX_GPU_DRA_POC_2026-07-13.md) | MiniX Kubernetes 1.34.3 업그레이드, GPU Operator DRA 전환, RTX 3090 정확 선택 검증 실행 기록 |
| [`MINIX_ISAAC_SIM_E2E_2026-07-14.md`](./MINIX_ISAAC_SIM_E2E_2026-07-14.md) | MiniX Harbor 설치, Isaac Sim 6.0 이미지, DRA 인스턴스, Nucleus 설정, WebRTC 실제 통합 실행 기록 |

## 읽는 순서

1. 목표 기능과 구현 범위는 `ISAAC_UI_MVP_SCOPE.md`를 읽는다.
2. Kubernetes 업그레이드와 GPU DRA 사전 검증은 `MINIX_GPU_DRA_POC_2026-07-13.md`를 읽는다.
3. Harbor, 실제 이미지, Nucleus, WebRTC 통합 결과는 `MINIX_ISAAC_SIM_E2E_2026-07-14.md`를 읽는다.
4. 기존 `SMARTX_MIGRATION_PLAN.md` 링크는 이전 안내용이므로 별도로 읽지 않아도 된다.

설계 기준은 `ISAAC_UI_MVP_SCOPE.md`, 클러스터 전제는 GPU DRA PoC, 실제 통합 증거는 Isaac Sim E2E 실행 기록을 기준으로 한다.
