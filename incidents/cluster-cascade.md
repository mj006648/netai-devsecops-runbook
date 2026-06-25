# 클러스터 연쇄 장애 — OTel → Cilium hostNetwork → Rook-Ceph 재구축

## 요약
3일 동안 관측(OpenTelemetry), CNI/host networking(Cilium), 스토리지(Rook-Ceph) 문제가
연쇄적으로 이어졌고, 최종적으로 Rook-Ceph 전체 재설치까지 진행한 장애 대응 기록이다.

## 타임라인 (TwinX git log, 2026-04-29 → 2026-05-01)

**2026-04-29 — API 서버 과부하**
- otel-operator가 custom resource churn과 webhook traffic을 많이 만들어 API 서버 부하를 키웠다.
- 완화 조치: ArgoCD에서 **otel-operator 비활성화** 후 추가 확산을 막았다.

**2026-04-30 — host networking + otel collector 업데이트**
- overloaded CNI/admission 경로를 우회하도록 otel collector 경로에 `hostNetwork: true`를 적용했다.
- 동시에 otelcol 버전과 설정을 업데이트했다.

**2026-05-01 — Rook-Ceph 전체 재구축**
- 관련 커밋: `c65c4de` … `2ed16e8`.
- 이전 재부팅과 zombie LVM/GPT metadata 때문에 fresh OSD prepare가 막히는 등 스토리지 상태가 drift됐다.
- 적용한 순서:
  1. ArgoCD에서 Ceph 의존 앱을 모두 비활성화한다.
  2. 정리 작업을 수행한다. LV/VG/PV 삭제, signature zap.
  3. Rook-Ceph operator를 재설치한다.
  4. operator → cluster 순서로 활성화하고 OSD가 올라올 때까지 기다린다.
  5. 의존 앱을 순서대로 다시 활성화한다.

## 복구 순서에서 배운 점
1. **네트워크를 먼저 안정화한다.** Pod-to-pod 통신과 webhook reachability가 불안정하면
   Ceph를 재시작하거나 앱을 roll해도 계속 다른 형태로 실패한다.
   - Cilium MTU와 host MTU를 확인한다.
     ([`networking/mtu-cilium.md`](../networking/mtu-cilium.md))
   - 새 webhook-bearing controller에는 필요 시 `NotIn rm352-*` affinity를 적용한다.
     ([`networking/rm352-pod-comms.md`](../networking/rm352-pod-comms.md))
2. **API/webhook 압력을 줄인다.** otel-operator 비활성화와 collector `hostNetwork` 전환은
   근본 해결이 아니라 load-shedding이다. 하지만 스토리지 재구축 시간을 벌어줬다.
3. **그다음 스토리지다.** [`storage/rook-ceph-reinstall.md`](../storage/rook-ceph-reinstall.md)
   절차를 사용하고, 재설치 전에 [`storage/lv-preparation.md`](../storage/lv-preparation.md)로
   stale LVM을 먼저 지운다.
4. **마지막으로 관측과 앱을 올린다.** 스토리지가 healthy가 된 뒤 otel을 다시 올리고,
   문서화된 의존 순서(cnpg → nessie → trino → infra → spark → superset)로 앱을 roll한다.

## 장애 중 사용한 빠른 진단 명령
```bash
# 빠른 3종 점검
kubectl get nodes -o wide
kubectl -n rook-ceph get pods -o wide | grep -E 'osd|mon|mgr'
ceph -s

# API 서버가 실제로 과부하인지 확인
kubectl -n kube-system top pod -l component=kube-apiserver
kubectl get --raw /metrics | grep apiserver_request_duration_seconds_count | head

# webhook traffic 자체가 부하를 만드는지 확인
kubectl get validatingwebhookconfiguration,mutatingwebhookconfiguration

# Cilium identity / endpoint 상태 확인
kubectl -n kube-system exec ds/cilium -- cilium status --brief
```

## 재발 방지
- 이 저장소에 클러스터 bring-up / bring-down 순서를 하나의 authoritative 문서로 유지한다.
  장애 후에는 반드시 업데이트한다.
- API server p99 latency, webhook call count, OSD restart rate, Cilium identity churn 같은
  선행 지표에 **일찍** alert를 건다. 사용자 증상은 이미 늦은 신호다.
- admission webhook을 운영하는 controller를 늘릴 때 신중하게 결정한다.
  장애 상황에서 webhook 하나하나가 API 서버 부하를 증폭한다.

## 참고
- TwinX commits 2026-04-29 (otel-operator disable), 2026-04-30 (hostNetwork on, otelcol update),
  2026-05-01 (`c65c4de`..`2ed16e8`, Rook-Ceph rebuild)
