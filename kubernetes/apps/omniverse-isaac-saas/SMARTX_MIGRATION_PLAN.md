# Omniverse Isaac SaaS SmartX 이관 계획

> 상태: 이 문서의 초기 광범위 계획은 현재 MVP 범위로 대체되었다.
> 보존 이유: 기존 GitHub URL과 외부 링크를 깨지 않기 위한 이전 안내다.
> 원칙: 이 파일에는 상세 설계, values 예시, 실행 순서, 검증 절차를 중복 기록하지 않는다.

## 현재 기준 문서

현재 구현과 검토는 다음 문서만 기준으로 한다.

- [`ISAAC_UI_MVP_SCOPE.md`](./ISAAC_UI_MVP_SCOPE.md)

해당 문서에 다음 내용이 통합되어 있다.

- 원본 `isaac-ui`와 `isaac-sim-image`의 실제 구조
- 원본에서 유지, 변경, 제거할 기능
- 이기종 GPU node/product/UUID 선택과 DRA 설계
- Isaac Sim image, Nucleus, Extension 구성 방식
- WebRTC와 인스턴스별 LoadBalancer 설계
- `eecs-k8s`와 `c-k8s`/`twinx-k8s` 반영 위치
- 최소 RBAC, API, 구현 순서, 검증 기준

초기 계획의 상세 내용이 필요한 경우 이 파일의 Git history를 확인한다. 현재 구현에 초기 계획의 metrics, scene history, code-server, workspace, registry catalog, GPU ban 정책을 다시 적용하지 않는다.
