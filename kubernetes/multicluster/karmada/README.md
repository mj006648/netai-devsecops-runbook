# ScaleX Karmada 운영 계획

이 문서가 **현재 계획의 입구**입니다. 먼저 이 파일만 보면 됩니다.

운영 계획/모델은 이 `README.md`에 통합하고, 실제 장애/운영 명령은 [`RUNBOOK.md`](./RUNBOOK.md), 과거 실험 기록은 [`lab/`](./lab/)에 둡니다.

---

## 1. 최종 목표

ScaleX는 실제 클러스터 4개와 운영 repo 5개로 구성합니다.

```text
실제 클러스터 4개:
  - TowerX  : 제어 클러스터
  - DataX   : data/batch/analytics cluster
  - EdgeX   : edge/GPU cluster
  - TwinX   : digital twin/render/AI serving cluster

운영 repo 5개:
  - tower-k8s
  - scalex-federation
  - datax-k8s
  - edgex-k8s
  - twinx-k8s

엔진/참조:
  - smartx-k8s   : 공통 엔진/app catalog/feature graph
  - mobilex-k8s  : 참고용 preset 구조. 우리가 관리하거나 Argo CD에 연결하지 않음
```

---

## 2. 최종 구조

```text
tower-k8s
  -> TowerX Argo CD
    ├─ tower-k8s
    │   -> TowerX cluster
    │
    ├─ scalex-federation
    │   -> Karmada API Server
    │     -> DataX / EdgeX / TwinX
    │
    ├─ datax-k8s
    │   -> DataX cluster
    │
    ├─ edgex-k8s
    │   -> EdgeX cluster
    │
    └─ twinx-k8s
        -> TwinX cluster
```

핵심은 **Argo CD 서버는 TowerX에 하나만 둔다**는 것입니다.

---

## 3. repo별 역할

| repo | 역할 | 여기에 두는 것 | 여기에 두지 않는 것 |
| --- | --- | --- | --- |
| `tower-k8s` | TowerX 제어 클러스터 repo | Argo CD, Karmada Control Plane, AppProject, root/child Application | 일반 서비스 workload |
| `scalex-federation` | Karmada federation repo | 멀티클러스터 workload, PropagationPolicy, OverridePolicy, WorkloadRebalancer | Cilium/CSI/GPU Operator 같은 cluster-local 인프라 |
| `datax-k8s` | DataX cluster-local repo | DataX 전용 앱, DataX CNI/CSI/storage/ingress/GPU 설정 | TwinX/EdgeX 리소스 |
| `edgex-k8s` | EdgeX cluster-local repo | EdgeX 전용 앱, EdgeX CNI/CSI/storage/ingress/GPU 설정 | DataX/TwinX 리소스 |
| `twinx-k8s` | TwinX cluster-local repo | TwinX 전용 앱, TwinX CNI/CSI/storage/ingress/GPU 설정 | DataX/EdgeX 리소스 |

---

## 4. scalex-federation에 들어가는 예시

`scalex-federation`은 “공통 앱 repo”가 아닙니다. **Karmada placement가 필요한 앱만** 둡니다.

예시:

```text
scalex-federation/federation/apps/render-demo/
  resources.yaml
  propagation-policy.yaml
```

의미:

```text
render-demo Deployment/Service를
TwinX에는 replica 3개,
EdgeX에는 replica 1개로 나누어 배치한다.
```

다른 예시:

```text
scalex-federation/federation/apps/data-hold-job/
  resources.yaml
  propagation-policy.yaml
```

의미:

```text
TowerX Argo CD가 Job을 Karmada API Server에 넣고,
Karmada가 DataX에만 전파한다.
```

---

## 5. 어디에 둘지 헷갈릴 때

```text
1. TowerX 제어용인가?
   -> tower-k8s

2. 두 개 이상 클러스터에 Karmada policy로 배치해야 하는가?
   -> scalex-federation

3. 특정 클러스터 하나에서만 쓰는가?
   -> datax-k8s / edgex-k8s / twinx-k8s

4. Cilium, CSI, GPU Operator 같은 클러스터 기본 인프라인가?
   -> 각 cluster-local *-k8s
```

중요:

```text
같은 live resource를 scalex-federation과 각 *-k8s에 동시에 선언하지 않는다.
```

---

## 6. 문서 역할

| 문서 | 역할 |
| --- | --- |
| `README.md` | 현재 계획 요약. 먼저 읽는 문서 |
| `RUNBOOK.md` | 운영 중 확인/장애/rollback 명령 절차 |
| `CONCEPTS.md` | Karmada 개념 설명 |
| `lab/` | 과거 kind 실험 기록 archive |

---

## 7. 현재 PoC 상태

검증된 것:

```text
1. TowerX 단일 Argo CD가 여러 repo를 sync할 수 있음
2. scalex-federation -> Karmada API Server -> DataX/EdgeX/TwinX 전파 가능
3. datax-k8s/edgex-k8s/twinx-k8s는 각 cluster destination으로 직접 sync 가능
4. Kueue는 지금 필수가 아니며 Job admission/quota가 필요해질 때 member cluster 내부에 도입
```

현재 정리 완료:

```text
1. ScaleX federation repo 이름을 scalex-federation으로 정리
2. lab cluster를 TowerX/DataX/EdgeX/TwinX 4개로 정리
3. Argo CD UI에서 최종 5개 Application만 보이도록 정리
```

다음 작업:

```text
1. 실제 앱을 datax-k8s/edgex-k8s/twinx-k8s/scalex-federation 중 어디에 둘지 분류
2. scalex-federation에는 Karmada placement가 필요한 workload만 추가
3. 각 cluster-local *-k8s에는 CNI/CSI/GPU/Ingress와 클러스터 전용 앱을 추가
```
