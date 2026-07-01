# Karmada 실험 coverage review

## 목적

실험 00~32까지 진행한 Karmada 검증이 서로 과하게 겹치는지, 빠진 영역은 무엇인지 점검한다.

---

## 전체 흐름 요약

```text
00~04: 기본 전파, cluster 선택, replica weight, OverridePolicy
05~11: 장애, taint, failover, WorkloadRebalancer
12~17: ScaleX-POD 역할 label, Resource Pool, scheduler-estimator, spreadConstraints
18~19, 24~25: ArgoCD -> Karmada GitOps, prune/restore, ApplicationSet, prune 안전장치
20~23, 26: Pull mode, agent 복구, 신규 cluster label 영향, Pull mode 재균형, 네트워크 단절/복구
27: Kueue member-local Job admission과 Karmada placement 역할 분리
28: ArgoCD -> Karmada -> DataX -> Kueue end-to-end 구조
29: Kueue 관측/알림 runbook과 pending/admitted snapshot 검증
30: Kueue controller/webhook 장애 시 Karmada FullyApplied=False와 복구 후 재시도 확인
31: Kueue quota 증감 시 pending/running Job 반응 확인
32: scheduler-estimator addon 설치, scheduler 연결, Aggregated scheduling 검증
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
| 16, 27, 32 | 모두 scheduling/admission 관련 | 16/32는 Karmada scheduler-estimator, 27은 member cluster 내부 Kueue Job admission이라 계층이 다르고, 32는 estimator 설치형 검증 |
| 18, 27, 28, 29, 30, 31 | 모두 GitOps/Job 배포와 관련 | 18은 ArgoCD -> Karmada 기본 sync, 27은 Karmada + Kueue만, 28은 세 도구를 end-to-end로 연결, 29는 운영 관측/알림, 30은 Kueue controller 장애, 31은 quota 운영 변경 |

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
16. ArgoCD -> Karmada -> Kueue end-to-end 동작
17. Kueue pending/admitted 관측과 알림 기준
18. Kueue controller/webhook 장애와 복구 후 재시도 절차
19. Kueue quota 증가/감소의 운영 의미
20. scheduler-estimator 설치형 capacity-aware scheduling 기본 동작
```

---

## 아직 남은 영역

```text
1. 실제 ScaleX-POD 이전 migration checklist
2. Kueue GitOps 배포 구조
3. ArgoCD AppProject migration
4. Kueue preemption/running Job 회수 정책
5. scheduler-estimator 운영 적용 여부와 secret 회전 절차
6. 관측/알림: Cluster READY Unknown, agent health, binding drift
7. policy naming/label convention 최종화
```

---

## 정리 판단

```text
실험들이 일부 같은 기능을 반복하지만, 반복 단위가 기능 중복이 아니라 운영 시나리오 확장이다.
따라서 현재 실험 세트는 유지해도 된다.
ScaleX-POD 설계 판단에 필요한 핵심 기능 검증은 00~32에서 완료된 것으로 본다.
이후 작업은 실제 이전 또는 운영 고도화 실험으로 분리한다.
```

운영 모델 문서:

- [`scalex-pod-operating-model.md`](./scalex-pod-operating-model.md)

권장 묶음:

```text
기본기: 00~04
장애/재균형: 05~11, 15, 23
ScaleX-POD placement: 12~17, 22, 32
GitOps: 18~19, 24~25
Pull mode: 20~23, 26
Queue/admission: 27~31
```
