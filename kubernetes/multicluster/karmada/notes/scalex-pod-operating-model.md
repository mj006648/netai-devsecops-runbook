# ScaleX-POD 멀티클러스터 운영 모델

## 목적

이 문서는 MiniX/kind Karmada 실험 00~33의 결과를 바탕으로, 실제 ScaleX-POD에서 ArgoCD, Karmada, Kueue와 repo ownership을 어떤 역할로 나눠 사용할지 정리한다.

실험은 끝났고, 이 문서는 다음 단계의 기준 문서다.

```text
MiniX/kind lab: 기능 검증 공간
ScaleX-POD: 실제 Tower / TwinX / EdgeX / DataX / Resource Pool / Pull Edge가 합쳐진 멀티클러스터 단위
```

---

## 0. 최종 판단

실험 00~32를 기준으로, ScaleX-POD의 기본 운영 모델은 다음 구조로 잡는다.

```text
GitHub repository
  -> ArgoCD on Tower
    -> Karmada API Server on Tower
      -> Karmada scheduler/controller
        -> TwinX / EdgeX / DataX / Resource Pool / Pull Edge
          -> member-local controllers
```

도구별 책임은 명확히 분리한다.

```text
ArgoCD: Git desired state를 Karmada API Server에 sync한다.
Karmada: ScaleX-POD member cluster 선택, 전파, override, 재균형을 담당한다.
Kueue: DataX/TwinX 내부에서 Job admission, queue, quota, backpressure를 담당한다.
```

채택 판단:

```text
1. Karmada는 ScaleX-POD 멀티클러스터 placement/propagation 계층으로 사용 가능하다.
2. ArgoCD는 Karmada API Server를 destination으로 삼는 GitOps 계층으로 둔다.
3. Kueue는 Karmada가 선택한 member cluster 내부의 Job admission 계층으로 둔다.
4. Resource Pool과 Pull Edge는 Karmada placement label, Pull mode, WorkloadRebalancer로 운영할 수 있다.
5. scheduler-estimator는 설치형 검증은 끝났지만 기본 운영 필수값이 아니라 capacity-aware scheduling 요구가 있을 때 켠다.
6. scalex-k8s는 federation repo, twinx/datax/edgex-k8s는 cluster-local repo로 분리한다. 같은 live resource는 두 계층에서 동시에 관리하지 않는다.
```

남은 항목은 기능 검증이 아니라 운영화 작업이다.

```text
1. Kueue queue/resourceflavor GitOps 배포 구조 확정
2. ArgoCD AppProject migration
3. 실제 ScaleX-POD 이전 checklist
4. 관측/알림/rollback runbook 보강
5. Kueue preemption/running Job 회수 정책 검토
```

---

## 1. ScaleX-POD 정의

ScaleX-POD는 단순히 하나의 Kubernetes cluster가 아니다.
여러 목적의 cluster를 하나의 운영 단위로 묶은 멀티클러스터 POD다.

```text
ScaleX-POD
  Tower          : control plane / GitOps / Karmada control plane
  TwinX          : GPU/render/AI serving 계열 workload
  EdgeX          : edge workload, 현장 가까운 실행 위치
  DataX          : data, batch, analytics, AI training/job 계열 workload
  Resource Pool  : fallback/general capacity pool
  Pull Edge      : 방화벽/NAT/현장망 제약이 큰 Pull mode member cluster
```

MiniX는 이 구조를 바로 실제로 만들기 전, 작은 실험 cluster 하나 또는 kind lab으로 기능을 확인하는 단계다.

---

## 2. 핵심 결론

```text
ArgoCD는 Git desired state를 Karmada API Server에 제출한다.
Karmada는 ScaleX-POD 안에서 어느 member cluster로 보낼지 결정한다.
Kueue는 선택된 member cluster 내부에서 Job admission과 quota를 제어한다.
```

따라서 세 도구는 같은 일을 하는 것이 아니다.

| 도구 | 책임 | 보면 안 되는 것 |
| --- | --- | --- |
| ArgoCD | GitOps sync, self-heal, prune, ApplicationSet | cluster placement 자체를 대신하지 않음 |
| Karmada | multi-cluster placement, propagation, failover, rebalancing | Git source-of-truth 자체를 관리하지 않음 |
| Kueue | member-local Job queue, admission, quota, pending/backpressure | multi-cluster placement를 대신하지 않음 |

---

## 3. 권장 전체 구조

```text
GitHub repository
  -> ArgoCD on Tower
    -> Karmada API Server on Tower
      -> Karmada scheduler/controller
        -> TwinX / EdgeX / DataX / Resource Pool / Pull Edge
          -> member-local controllers
             - Kueue on DataX/TwinX for batch/AI Job admission
             - storage/network/runtime controllers per member cluster
```

### 기본 배포 흐름

```text
1. 사용자가 GitHub에 workload manifest와 Karmada policy를 변경한다.
2. ArgoCD가 Tower에서 GitHub 변경을 감지한다.
3. ArgoCD Application destination은 Karmada API Server다.
4. ArgoCD가 일반 Kubernetes resource와 Karmada policy를 Karmada API Server에 sync한다.
5. Karmada가 PropagationPolicy/OverridePolicy를 기준으로 member cluster를 선택한다.
6. member cluster에 Work가 적용된다.
7. Job workload라면 member cluster 내부 Kueue가 admitted 여부를 결정한다.
8. 운영자는 ArgoCD, Karmada, Kueue 상태를 함께 확인한다.
```

---

## 4. GitHub repository 구성 원칙

### 4.1 Repo split 원칙

ScaleX-POD repo는 federation 계층과 cluster-local 계층을 분리한다.

```text
SmartX-Team/scalex-k8s
  = TowerX ArgoCD + Karmada가 보는 federation repo
  = 멀티클러스터에 전파할 resource + PropagationPolicy/OverridePolicy 관리

SmartX-Team/twinx-k8s
SmartX-Team/datax-k8s
SmartX-Team/edgex-k8s
  = 각 cluster-local ArgoCD가 보는 단일 클러스터 repo
  = 이 클러스터에 어떤 앱을 설치할 것인가 관리
```

흐름은 다음과 같이 분리한다.

```text
scalex-k8s
  -> TowerX ArgoCD
    -> Karmada API Server
      -> EdgeX / DataX / TwinX

twinx-k8s
  -> TwinX ArgoCD
    -> TwinX cluster

datax-k8s
  -> DataX ArgoCD
    -> DataX cluster

edgex-k8s
  -> EdgeX ArgoCD
    -> EdgeX cluster
```

판단 기준:

| repo | 질문 | 관리 대상 |
| --- | --- | --- |
| `scalex-k8s` | 어떤 리소스를 어느 클러스터들에 전파할 것인가? | 멀티클러스터 workload, PropagationPolicy, OverridePolicy, WorkloadRebalancer, placement profile |
| `*-k8s` | 이 클러스터에 어떤 앱을 설치할 것인가? | CNI/CSI/storage/ingress/GPU operator, cluster-local app, cluster-local namespace/RBAC/values/patches |

단일 소유권 원칙:

```text
1. 같은 live resource를 TowerX/Karmada와 cluster-local ArgoCD가 동시에 관리하지 않는다.
2. Karmada로 전파한 resource는 member cluster의 *-k8s repo에 다시 선언하지 않는다.
3. cluster-local platform은 기본적으로 각 *-k8s에서 관리한다.
4. federation resource에는 scalex.io/management-plane=federation 같은 ownership label을 붙인다.
```

관련 검증:

- [`../experiments/2026-07-07-33-scalex-repo-split-poc.md`](../experiments/2026-07-07-33-scalex-repo-split-poc.md)


운영 repo에는 workload YAML과 Karmada policy가 함께 있어야 한다.

```text
workload YAML        : 무엇을 배포할지
PropagationPolicy    : 어디에 배포할지
OverridePolicy       : cluster별로 무엇을 다르게 할지
Kueue queue resource : member cluster 내부에서 어떤 quota/admission을 줄지
ArgoCD Application   : 어떤 Git path를 어느 API server로 sync할지
```

권장 예시:

```text
kubernetes/
  karmada/
    argocd/
      applications/
      applicationsets/
      projects/
    manifests/
      <app-name>/
        00-namespace.yaml
        10-deployment-or-job.yaml
        20-service.yaml
        30-propagation-policy.yaml
        40-override-policy.yaml
      <batch-app-name>/
        member/
          kueue-queues.yaml
        karmada/
          namespace.yaml
          job.yaml
          propagation-policy.yaml
    runbooks/
    notes/
```

### 왜 YAML과 policy를 같이 두는가?

```text
Deployment/Job만 보면 어디로 갈지 알 수 없다.
PropagationPolicy만 보면 무엇이 배포되는지 알 수 없다.
OverridePolicy만 보면 cluster별 차이만 보이고 전체 app 의도가 보이지 않는다.
```

따라서 하나의 app 단위에서는 workload와 policy를 같이 리뷰해야 한다.

---

## 5. AppProject와 prune 안전장치

ArgoCD가 Karmada API Server를 destination으로 사용할 때 prune은 단일 cluster 삭제가 아니다.
Karmada API Server resource가 삭제되면 member cluster resource까지 삭제될 수 있다.

권장 원칙:

```text
1. 운영 app은 default AppProject에 몰아넣지 않는다.
2. 목적별 AppProject를 만든다.
3. source repo, destination namespace, 허용 resource kind를 제한한다.
4. prune=true는 검증된 app에만 켠다.
5. ApplicationSet generator 변경은 고위험 변경으로 본다.
6. Pull/Edge cluster READY Unknown 상태에서는 prune을 금지한다.
```

관련 문서:

```text
kubernetes/multicluster/karmada/runbooks/argocd-prune-safety.md
kubernetes/multicluster/karmada/argocd/projects/karmada-guarded-project.yaml
```

---

## 6. Karmada placement label 모델

ScaleX-POD member cluster에는 역할 label을 명확히 둔다.

권장 label 축:

```text
scalex.io/role       : gpu-render, edge-gpu, data, resource-pool, pull-edge
scalex.io/pool       : gpu, data, general, edge-pull
scalex.io/location   : edge, core, site-a, site-b
scalex.io/workload   : render, edge, data, general
scalex.io/storage    : ssd, hdd, ceph, local
scalex.io/fallback   : true/false
scalex.io/connectivity: push, pull
```

주의:

```text
labelSelector는 새 cluster가 들어올 때 기존 policy에 갑자기 매칭될 수 있다.
신규 member cluster label 부여 전에는 반드시 policy selector audit을 한다.
```

관련 문서:

```text
kubernetes/multicluster/karmada/runbooks/new-cluster-label-impact-checklist.md
```

---

## 7. workload 배치 원칙

### TwinX

```text
GPU/render/AI serving workload 우선 배치
중요 workload는 Resource Pool fallback을 따로 설계
```

### EdgeX

```text
현장 가까운 edge workload 배치
Pull Edge와 같은 label을 공유할 때 broad selector 주의
```

### DataX

```text
data, analytics, batch, AI training Job 배치
Kueue로 Job admission과 quota를 제어
```

### Resource Pool

```text
general workload 또는 fallback capacity
장애/점검 시 임시 수용 가능
복구 후 WorkloadRebalancer로 원래 placement로 재균형
```

### Pull Edge

```text
방화벽/NAT/현장망 제약이 있는 cluster
Karmada Pull mode agent 사용
네트워크 단절 시 기존 workload는 유지될 수 있으나 desired state 반영은 지연됨
```

---

## 8. 장애/복구 운영 모델

### 새 workload 회피

```text
Cluster taint NoSchedule 또는 policy selector 조정으로 신규 배치를 막는다.
```

### 기존 workload 이동

```text
NoExecute taint + failover 설정으로 기존 workload를 이동시킨다.
단, toleration이 있는 workload는 유지된다.
```

### 복구 후 재균형

```text
Karmada는 taint 제거만으로 자동 원복하지 않을 수 있다.
복구 후에는 WorkloadRebalancer를 명시적으로 사용한다.
```

### Pull mode 단절

```text
agent가 Karmada API Server와 통신하지 못하면 Cluster READY가 Unknown으로 갈 수 있다.
기존 workload는 계속 Running일 수 있다.
차단 중 desired state 변경은 member에 바로 반영되지 않는다.
복구 후에도 바로 수렴하지 않을 수 있으므로 agent log와 Work sync를 확인한다.
```

---

## 9. Kueue 운영 모델

Kueue는 DataX/TwinX 같은 member cluster 내부에서 batch/AI Job의 입장을 제어한다.

권장 흐름:

```text
1. Kueue controller는 member cluster에 설치한다.
2. ResourceFlavor/ClusterQueue/LocalQueue는 해당 member cluster에 존재한다.
3. ArgoCD가 Karmada API Server로 Job을 sync한다.
4. Karmada가 Job을 DataX/TwinX로 전파한다.
5. member cluster Kueue가 quota를 보고 Job을 admitted 또는 Suspended로 둔다.
```

중요:

```text
ArgoCD Synced + Karmada FullyApplied = Job 실행 완료가 아니다.
Kueue Workload admitted 상태까지 봐야 한다.

Kueue controller/webhook 장애는 quota pending이 아니라 Karmada FullyApplied=False로 보일 수 있다.
controller 복구 후에도 빠른 수렴을 위해 Karmada resource update 재시도가 필요할 수 있다.
quota 증가는 pending Job을 admitted로 전환할 수 있지만, quota 감소는 이미 running Job을 즉시 내리지 않는다.
```

관련 문서:

```text
kubernetes/multicluster/karmada/runbooks/kueue-observability.md
```

---

## 10. 관측 모델

운영 dashboard는 세 계층을 분리해서 보여줘야 한다.

```text
ArgoCD layer
  Application sync/health/revision

Karmada layer
  Cluster READY
  ResourceBinding Scheduled/FullyApplied
  Work 상태

Kueue/member layer
  Kueue controller ready
  ClusterQueue pending/admitted
  LocalQueue pending/admitted
  Workload admitted
  Job Suspended/Running/Complete
```

알림도 분리한다.

```text
GitOps sync 실패
Karmada placement 실패
member apply 실패
Kueue quota 대기
Kueue controller 장애
member cluster 연결 장애
```

---

## 11. 운영 의사결정

### 지금 확정해도 되는 것

```text
1. Tower에 ArgoCD와 Karmada control plane을 둔다.
2. ArgoCD destination은 Karmada API Server를 기본으로 한다.
3. app workload와 Karmada policy는 Git에서 같이 리뷰한다.
4. DataX/TwinX batch/AI Job은 Kueue로 admission을 제어한다.
5. Resource Pool은 fallback과 general capacity로 쓴다.
6. Pull Edge는 Pull mode로 별도 운영한다.
7. prune, label 변경, ApplicationSet 변경은 고위험 변경으로 본다.
8. scheduler-estimator는 설치형 검증은 끝났지만, 기본값은 비활성화하고 capacity-aware scheduling 요구가 있을 때 운영 적용을 판단한다.
```

### 아직 보류하는 것

```text
1. 실제 ScaleX-POD 이전 작업
2. Kueue queue/resourceflavor GitOps 배포 방식을 ArgoCD direct로 할지, member bootstrap으로 할지
3. Kueue preemption/running Job 회수 정책을 쓸지 여부
4. Kueue MultiKueue와 Karmada 역할을 같이 쓸지 여부
5. 운영 AppProject migration 시점
6. scheduler-estimator를 실제 운영에 상시 적용할지 여부와 member kubeconfig secret 회전 방식
```

---

## 12. 실험 결과 mapping

```text
기본 전파/선택/override: 00~04
장애/failover/rebalance: 05~11, 15, 23
ScaleX-POD role/resource pool/spread: 12~17, 22
ArgoCD GitOps/prune/ApplicationSet/AppProject: 18~19, 24~25
Pull mode: 20~23, 26
Kueue: 27~31
scheduler-estimator: 16, 32
```

결론:

```text
ScaleX-POD 설계 판단에 필요한 핵심 기능 검증은 완료됐다.
이후 작업은 실제 이전 또는 운영 고도화 실험으로 분리한다.
```

---

## 13. 다음 단계 선택지

이전 작업을 아직 하지 않는다면 다음 중 하나를 선택한다.

```text
A. Kueue GitOps 배포 구조 검토
B. ArgoCD AppProject migration 실험
C. Kueue preemption/running Job 회수 정책 검토
D. 실제 ScaleX-POD 이전 checklist 작성
E. scheduler-estimator 운영 적용 여부 결정
F. Kueue MultiKueue와 Karmada 역할 비교
```

권장 순서:

```text
1. Kueue GitOps 배포 구조
2. ArgoCD AppProject migration
3. Kueue preemption/running Job 회수 정책
4. 실제 ScaleX-POD 이전 checklist
5. scheduler-estimator 운영 적용 여부 결정
```
