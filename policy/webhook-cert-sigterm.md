# Webhook controller가 주기적으로 SIGTERM 재시작되는 문제

## Symptom
- CRD admission webhook이나 cluster add-on의 webhook controller가 일정 주기로 `SIGTERM`을 받고 재시작된다.
  보통 몇 분에서 한 시간 간격으로 반복된다.
- Pod는 그 외에는 정상처럼 보인다. OOM, panic, 재시작 직전 readiness failure가 없다.
- 재시작 주기가 controller 내부 certificate rotation cadence와 비슷하다.

## Diagnosis
```bash
kubectl -n <ns> get pods -l <selector> -o wide
kubectl -n <ns> describe pod <pod>     # 마지막 종료 이유 확인
kubectl -n <ns> logs <pod> --previous | tail -50
kubectl -n <ns> get events --sort-by=.lastTimestamp | tail -30

# webhook이 사용하는 TLS secret 확인
kubectl -n <ns> get secret <webhook-secret> -o yaml | grep -E 'annotations|managed-by|owner'
```

각 재시작 직전에 controller log에 certificate regeneration 또는 `rotating webhook cert`가 찍히고,
secret annotation에 여러 manager, 예를 들면 controller 자체와 cert-manager 또는 Helm hook이 같이 보이면
거의 확실하게 certificate ownership conflict다.

## Root cause
두 주체가 동시에 webhook TLS secret을 소유하려고 한다.

1. Controller 내장 certificate manager
   - 시작 시점과 주기적으로 secret을 재생성하고, “정상” material을 로드하기 위해 pod를 재시작한다.
2. 외부 certificate source
   - 보통 cert-manager의 `Certificate` resource 또는 Helm `post-install` hook이 secret을 다시 쓴다.

각 reconcile이 상대방을 다시 trigger한다. Controller process는 “자기” 인증서를 다시 읽기 위해 매 cycle마다
`SIGTERM`을 받고, 그 직후 외부 source가 다시 secret을 덮어쓰면서 같은 일이 반복된다.

## Fix — certificate owner를 하나만 둔다

**Option A — controller가 자체 인증서를 관리하게 둔다**
대부분의 in-cluster webhook에서는 이쪽이 더 안전하다.

- 해당 webhook에 대한 외부 cert-manager `Certificate`를 끈다.
- `certManager.create: true`, `useCertManagerCerts: true` 같은 Helm value를 제거한다.
- 외부에서 발급한 secret을 삭제해서 controller가 다음 시작 시 self-signed pair를 새로 만들게 한다.

**Option B — cert-manager에 완전히 위임한다**
controller가 실제로 `--disable-internal-cert-manager` 같은 flag를 지원할 때만 선택한다.

- 사용 중인 controller version에 해당 flag가 있는지 확인한다.
- Helm values 또는 deployment args로 설정한다.
- Secret의 end-to-end ownership을 cert-manager 하나로 고정한다.

둘 중 어느 쪽도 깨끗하게 disable되지 않으면 Option A를 선택한다. Mixed mode가 SIGTERM loop의 원인이다.

## 검증
```bash
# restart count가 더 이상 증가하지 않는지 확인
kubectl -n <ns> get pods -l <selector>

# webhook secret annotation이 더 이상 흔들리지 않는지 확인
kubectl -n <ns> get secret <webhook-secret> -o yaml | grep annotations
```

## Prevention
- Webhook을 가진 controller마다 TLS secret을 누가 소유하는지 이 런북에 기록한다.
- 알려진 webhook controller에 대해 `kube_pod_container_status_restarts_total` alert를 건다.
  이런 느린 restart 증가는 crash bug보다 certificate ownership 문제인 경우가 많다.

## 참고
- 관련 문서: [`policy/kyverno-cert-manager.md`](kyverno-cert-manager.md)
