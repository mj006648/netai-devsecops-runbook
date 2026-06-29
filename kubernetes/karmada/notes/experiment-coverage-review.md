# Karmada 실험 coverage review

## 목적

실험 00~27까지 진행한 Karmada 검증이 서로 과하게 겹치는지, 빠진 영역은 무엇인지 점검한다.

---

## 전체 흐름 요약

```text
00~04: 기본 전파, cluster 선택, replica weight, OverridePolicy
05~11: 장애, taint, failover, WorkloadRebalancer
12~17: ScaleX-POD 역할 label, Resource Pool, scheduler-estimator, spreadConstraints
18~19, 24~25: ArgoCD -> Karmada GitOps, prune/restore, ApplicationSet, prune 안전장치
20~23, 26: Pull mode, agent 복구, 신규 cluster label 영향, Pull mode 재균형, 네트워크 단절/복구
27: Kueue member-local Job admission과 Karmada placement 역할 분리
```

결론:

```text
완전한 중복 실험은 없다.
다만 같은 기능을 다른 운영 상황에서 반복 검증한 계열은 있다.
이 반복은 의도된 것이며, ScaleX-POD 운영 절차를 만들기 위한 시나리오 차이다.
```

---

## 겹쳐 보일 수 있는 실험과 차이

| 실험 | 겹쳐 보이는 이유 | 실제 차이 |
| --- | --- | --- |
| 01, 02 | 둘 다 namespace 전파 관찰 | 01은 twinx-only 배치 중 발견, 02는 namespace 자동 생성만 분리 검증 |
| 05, 06, 07 | 모두 failover/장애 계열 | 05는 수동 taint, 06은 실제 cluster stop, 07은 feature gate 활성화 후 재확인 |
| 08, 10 | 둘 다 NoExecute taint | 08은 eviction 동작, 10은 toleration 있는 workload와 없는 workload의 영향 범위 비교 |
| 09, 11, 15, 23 | 모두 WorkloadRebalancer | 09는 단일 Push workload, 11은 batch, 15는 Resource Pool fallback, 23은 Push/Pull 혼합 재균형 |
| 12, 13, 15, 22, 23 | 모두 ScaleX-POD label/pool과 관련 | 12는 role placement, 13은 poolx 추가, 15는 pool skew 복구, 22는 label 영향 audit, 23은 Pull cluster 편입 후 재균형 |
| 18, 19, 24, 25 | 모두 ArgoCD | 18은 sync/self-heal 기본, 19는 prune/delete/restore 운영 흐름, 24는 ApplicationSet으로 여러 Application 생성, 25는 prune 안전장치/AppProject/runbook |
| 20, 21, 26 | 모두 Pull mode | 20은 등록/전파 baseline, 21은 agent Deployment 중단/복구, 26은 agent process를 내리지 않고 네트워크 단절/복구 |
| 22, 23 | 둘 다 pullx 추가 이후 영향 | 22는 label 매칭 영향 분석, 23은 실제 replica 재균형 실행 |
| 16, 27 | 둘 다 scheduling 관련 | 16은 Karmada scheduler-estimator, 27은 member cluster 내부 Kueue Job admission이라 계층이 다름 |

---

## 현재까지 충분히 검증된 영역

```text
1. 기본 resource 전파
2. clusterAffinity labelSelector와 clusterNames 차이
3. replicaScheduling Divided/Weighted
4. OverridePolicy env/image/storageClass
5. cluster taint, NoExecute eviction, clusterTolerations
6. WorkloadRebalancer 단일/batch/fallback/Pull 혼합 시나리오
7. ScaleX-POD role/pool/location/workload label 설계 초안
8. Resource Pool fallback placement
9. spreadConstraints 기초 동작
10. scheduler-estimator 미설치 상태와 비활성화
11. ArgoCD -> Karmada API Server GitOps
12. ArgoCD self-heal/prune/restore/ApplicationSet/AppProject 안전장치
13. Pull mode 등록, agent 장애/복구, 네트워크 단절/복구
14. 신규 cluster label 영향 audit
15. Kueue member-local Job admission과 quota 기초 동작
```

---

## 아직 남은 영역

```text
1. 실제 ScaleX-POD 이전 migration checklist
2. Kueue 관측/알림과 GitOps 배포 구조
3. ArgoCD AppProject migration
4. scheduler-estimator 설치형 capacity-aware scheduling
5. 관측/알림: Cluster READY Unknown, agent health, binding drift
6. policy naming/label convention 최종화
```

---

## 정리 판단

```text
실험들이 일부 같은 기능을 반복하지만, 반복 단위가 기능 중복이 아니라 운영 시나리오 확장이다.
따라서 현재 실험 세트는 유지해도 된다.
다만 README에서는 기능별 묶음으로 보이게 정리하는 것이 좋다.
```

권장 묶음:

```text
기본기: 00~04
장애/재균형: 05~11, 15, 23
ScaleX-POD placement: 12~17, 22
GitOps: 18~19, 24~25
Pull mode: 20~23, 26
Queue/admission: 27
```
