# ScaleX-POD Karmada 운영 문서

이 디렉터리는 ScaleX-POD 멀티클러스터 운영을 위한 현재 기준 문서와 kind lab 실험 기록을 담는다.

## 지금 읽을 문서

| 문서 | 읽는 목적 |
| --- | --- |
| [`OPERATING_MODEL.md`](./OPERATING_MODEL.md) | TowerX 단일 ArgoCD, `tower-k8s`/`scalex-k8s`/`*-k8s` repo 책임, Karmada/Kueue 역할 분리 |
| [`RUNBOOK.md`](./RUNBOOK.md) | 운영 중 장애/점검/label/prune/Kueue 이슈 대응 절차 |
| [`CONCEPTS.md`](./CONCEPTS.md) | Karmada 기본 개념, PropagationPolicy/OverridePolicy, Push/Pull mode 이해 |
| [`lab/`](./lab/) | 과거 kind 실험 기록, demo manifest, ArgoCD 예제 archive |

## 현재 결론

```text
TowerX
  ├─ ArgoCD 1개
  ├─ Karmada Control Plane
  │
  └─ ArgoCD Applications
      ├─ tower-k8s  -> destination: TowerX cluster
      ├─ scalex-k8s -> destination: Karmada API Server
      ├─ datax-k8s  -> destination: DataX cluster
      ├─ twinx-k8s  -> destination: TwinX cluster
      └─ edgex-k8s  -> destination: EdgeX cluster
```

핵심 원칙:

```text
1. ArgoCD 서버는 TowerX에 하나만 둔다.
2. tower-k8s는 TowerX 제어 클러스터 repo다.
3. scalex-k8s는 Karmada 멀티클러스터 전용 repo다.
4. datax/twinx/edgex-k8s는 smartx-k8s preset 방식의 단일 클러스터 repo다.
5. 같은 live resource를 Karmada 전파 경로와 직접 cluster destination 경로가 동시에 관리하지 않는다.
6. Kueue는 필요 시 member cluster 내부 Job admission/quota 계층으로 도입한다.
```

## 현재 상태

- Karmada 핵심 기능 검증: 실험 00~33 완료
- 검증 환경: kind 기반 TowerX/DataX/TwinX/EdgeX/Resource Pool/Pull mode lab
- 다음 작업: 실제 `tower-k8s`, `scalex-k8s`, `datax-k8s`, `twinx-k8s`, `edgex-k8s` repo 생성 및 TowerX 단일 ArgoCD sync 검증

## 디렉터리 구조

```text
karmada/
  README.md            # 현재 문서 입구
  OPERATING_MODEL.md   # 현재 설계 기준
  RUNBOOK.md           # 운영 절차
  CONCEPTS.md          # 개념 정리
  lab/                 # 과거 실험/manifest/archive
```
