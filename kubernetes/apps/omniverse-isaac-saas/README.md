# Omniverse Isaac SaaS SmartX 이관 계획

이 디렉터리는 `SmartX-Team/Omniverse/isaac-saas`를 우리 SmartX/eecs-k8s 구조에 맞게 이관하기 위한 계획 문서다.

## 문서

| 파일 | 역할 |
| --- | --- |
| [`SMARTX_MIGRATION_PLAN.md`](./SMARTX_MIGRATION_PLAN.md) | 원본 `isaac-saas` 분석 기반 SmartX 이관 계획, 변경 항목, 기대 효과, 검증 순서 |

## 핵심 방향

```text
eecs-k8s
  -> 공통 SmartX 엔진/app catalog
  -> omniverse-isaac-saas 앱 정의 추가

c-k8s 또는 twinx-k8s
  -> 클러스터 preset
  -> Nucleus 주소, Harbor 이미지, GPU 노드, DRA 여부, Secret 이름만 patch

isaac-ui
  -> ArgoCD/SmartX가 관리하는 고정 앱
  -> 사용자가 웹 UI에서 Isaac Sim 인스턴스를 동적으로 생성/삭제

Isaac Sim instance
  -> Git에 직접 나열하지 않음
  -> isaac-ui가 Kubernetes API로 Deployment/Service/ResourceClaimTemplate 생성
```
