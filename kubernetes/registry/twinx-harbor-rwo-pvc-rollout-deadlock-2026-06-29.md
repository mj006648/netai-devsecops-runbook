# TwinX Harbor RWO PVC Rollout Deadlock (2026-06-29)

## Summary
TwinX Harbor가 Argo CD에서 `OutOfSync / Degraded`로 보였고, `registry`와
`jobservice`의 새 Pod가 `ContainerCreating`에 오래 머물렀다.

최종 원인은 Harbor chart의 `registry`와 `jobservice`가 `rook-ceph-block`
`ReadWriteOnce` PVC를 쓰는데, rollout 중 새 Pod가 기존 PVC attach 노드와 다른 노드에
스케줄되면서 volume attach가 막힌 것이었다.

최종 GitOps fix는 TwinX-Ops PR #209로 반영했다.

```text
PR: https://github.com/SmartX-Team/TwinX-Ops/pull/209
Merge commit: 83827b5 Fix Harbor PVC rollout
```

## Final result
Argo CD sync 후 서비스 관점 상태:

```text
harbor app health: Healthy
registry: 2/2 Running on rm352-1
jobservice: 1/1 Running on rm352-1
ContainerCreating pods: gone
```

확인 당시 Harbor app은 아직 `OutOfSync`였지만, 남은 OutOfSync 대상은
`database`, `redis`, `trivy` StatefulSet의 default/normalization drift였다.
서비스 장애 원인이었던 `registry`/`jobservice` Deployment는 정상 rollout됐다.

## Symptoms

### Argo CD

```text
harbor   OutOfSync   Degraded
```

초기 sync 실패 메시지:

```text
Deployment.apps "habor-harbor-jobservice" is invalid:
spec.strategy.rollingUpdate: Forbidden: may not be specified when strategy `type` is 'Recreate'

Deployment.apps "habor-harbor-registry" is invalid:
spec.strategy.rollingUpdate: Forbidden: may not be specified when strategy `type` is 'Recreate'
```

### Pods

문제 Pod는 새 ReplicaSet 쪽이었다.

```text
habor-harbor-jobservice-57bb6875f4-vvftj   0/1   ContainerCreating   node=l40s
habor-harbor-registry-669678d7b4-j5hwj     0/2   ContainerCreating   node=l40s
```

기존 Pod는 계속 살아 있었다.

```text
habor-harbor-jobservice-56b4784fb4-zvvjm   1/1   Running   node=rm352-1
habor-harbor-registry-6b5988885d-wn8sx     2/2   Running   node=rm352-1
```

## Diagnosis

### 1. Harbor app과 Pod 상태

```bash
kubectl -n argocd get app harbor -o wide
kubectl -n argocd get app harbor \
  -o jsonpath='sync={.status.sync.status}{" health="}{.status.health.status}{" op="}{.status.operationState.phase}{" msg="}{.status.operationState.message}{"\n"}'

kubectl -n harbor get pods -o wide
kubectl -n harbor get deploy -o wide
```

### 2. stuck Pod describe

```bash
kubectl -n harbor describe pod <stuck-jobservice-pod>
kubectl -n harbor describe pod <stuck-registry-pod>
```

두 Pod 모두 PVC를 mount해야 했지만 `ContainerCreating`에 멈췄다.

```text
jobservice -> ClaimName: habor-harbor-jobservice
registry   -> ClaimName: habor-harbor-registry
```

### 3. PVC access mode와 VolumeAttachment

```bash
kubectl -n harbor get pvc habor-harbor-jobservice habor-harbor-registry -o wide
```

결과:

```text
habor-harbor-jobservice   Bound   rook-ceph-block   RWO
habor-harbor-registry     Bound   rook-ceph-block   RWO
```

VolumeAttachment 확인:

```bash
kubectl -n harbor get pvc habor-harbor-jobservice habor-harbor-registry -o json > /tmp/harbor-pvc.json
kubectl get volumeattachments.storage.k8s.io -o json > /tmp/volumeattachments.json
python3 - <<'PY'
import json
from pathlib import Path

pvcs = json.loads(Path('/tmp/harbor-pvc.json').read_text())['items']
pvs = {i['spec']['volumeName']: i['metadata']['name'] for i in pvcs}
vas = json.loads(Path('/tmp/volumeattachments.json').read_text())['items']
for va in vas:
    pv = va.get('spec', {}).get('source', {}).get('persistentVolumeName')
    if pv in pvs:
        print(pvs[pv], pv, va.get('spec', {}).get('nodeName'), va.get('status', {}).get('attached'))
PY
```

관측 결과:

```text
habor-harbor-jobservice   pvc-f573...   rm352-1   True
habor-harbor-registry     pvc-5ebc...   rm352-1   True
```

즉 PVC는 `rm352-1`에 붙어 있는데 새 Pod는 `l40s`에 스케줄되어 있었다.

### 4. Deployment strategy

```bash
for d in habor-harbor-jobservice habor-harbor-registry; do
  kubectl -n harbor get deploy "$d" \
    -o jsonpath='strategy={.spec.strategy.type}{" maxSurge="}{.spec.strategy.rollingUpdate.maxSurge}{" maxUnavailable="}{.spec.strategy.rollingUpdate.maxUnavailable}{" replicas="}{.spec.replicas}{" updated="}{.status.updatedReplicas}{" ready="}{.status.readyReplicas}{" available="}{.status.availableReplicas}{" unavailable="}{.status.unavailableReplicas}{"\n"}'
done
```

관측 결과:

```text
strategy=RollingUpdate maxSurge=25% maxUnavailable=25% replicas=1
```

`replicas=1` + `RollingUpdate` + `RWO PVC` 조합에서 새 Pod가 먼저 생기면, 기존 Pod가
PVC를 계속 잡고 있기 때문에 새 Pod가 다른 노드에서 volume을 attach할 수 없다.

## Root cause

```text
RWO PVC + RollingUpdate + cross-node scheduling
```

상세 흐름:

1. `registry`와 `jobservice`는 각각 RWO PVC를 사용한다.
2. 기존 정상 Pod는 `rm352-1`에서 PVC를 잡고 있었다.
3. rollout 중 새 ReplicaSet Pod가 먼저 만들어졌다.
4. 새 Pod가 `l40s`에 스케줄됐다.
5. RWO PVC는 아직 `rm352-1`에 attach되어 있으므로 `l40s`에 붙일 수 없다.
6. 새 Pod는 `ContainerCreating`에 멈춘다.
7. 기존 Pod는 새 Pod가 Ready 될 때까지 내려가지 않는다.
8. rollout이 progress deadline을 넘고 Harbor app이 `Degraded`가 된다.

## Failed fix: `updateStrategy: Recreate`

처음에는 Harbor chart values에 아래를 추가했다.

```yaml
updateStrategy:
  type: Recreate
```

Harbor chart values에도 다음 주석이 있기 때문에 방향은 합리적으로 보였다.

```text
The update strategy for deployments with persistent volumes(jobservice, registry):
"RollingUpdate" or "Recreate"
Set it as "Recreate" when "RWM" for volumes isn't supported
```

하지만 Harbor chart `1.19.1` 템플릿은 `Recreate`일 때도 다음 필드를 렌더링했다.

```yaml
strategy:
  type: Recreate
  rollingUpdate: null
```

현재 Kubernetes API는 이 조합을 거부했다.

```text
spec.strategy.rollingUpdate: Forbidden: may not be specified when strategy `type` is 'Recreate'
```

검증 명령:

```bash
helm template habor harbor/harbor \
  --version 1.19.1 \
  --namespace harbor \
  -f argocd/twinx-infra/apps/harbor/values.yaml \
  | grep -n -A4 'strategy:'
```

따라서 `Recreate`는 이 chart/Kubernetes 조합에서는 사용할 수 없었다.

## Final fix

`Recreate` 값을 제거하고, RWO PVC가 현재 attach된 `rm352-1`에 `registry`와
`jobservice`를 고정했다.

TwinX-Ops PR:

```text
https://github.com/SmartX-Team/TwinX-Ops/pull/209
```

최종 values 변경:

```yaml
jobservice:
  # jobservice log PVC is ReadWriteOnce and is currently attached on rm352-1.
  # Pin rollouts to the same node to avoid cross-node RWO attach deadlock.
  nodeSelector:
    kubernetes.io/hostname: rm352-1
  resources:
    requests:
      cpu: "250m"
      memory: "512Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"

registry:
  # registry storage PVC is ReadWriteOnce and is currently attached on rm352-1.
  # Pin rollouts to the same node to avoid cross-node RWO attach deadlock.
  nodeSelector:
    kubernetes.io/hostname: rm352-1
  resources:
    requests:
      cpu: "150m"
      memory: "512Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"
```

검증:

```bash
helm template habor harbor/harbor \
  --version 1.19.1 \
  --namespace harbor \
  -f argocd/twinx-infra/apps/harbor/values.yaml > /tmp/harbor-fix-rendered.yaml

# invalid field가 없어야 한다.
grep -n 'rollingUpdate: null' /tmp/harbor-fix-rendered.yaml || true

# jobservice/registry에 nodeSelector가 들어갔는지 확인한다.
python3 - <<'PY'
from pathlib import Path
import yaml

for doc in yaml.safe_load_all(Path('/tmp/harbor-fix-rendered.yaml').read_text()):
    if not isinstance(doc, dict):
        continue
    if doc.get('kind') == 'Deployment' and doc.get('metadata', {}).get('name') in (
        'habor-harbor-jobservice',
        'habor-harbor-registry',
    ):
        print(doc['metadata']['name'])
        print('  strategy:', doc['spec'].get('strategy'))
        print('  nodeSelector:', doc['spec']['template']['spec'].get('nodeSelector'))
PY
```

결과:

```text
habor-harbor-jobservice
  strategy: {'type': 'RollingUpdate'}
  nodeSelector: {'kubernetes.io/hostname': 'rm352-1'}

habor-harbor-registry
  strategy: {'type': 'RollingUpdate'}
  nodeSelector: {'kubernetes.io/hostname': 'rm352-1'}
```

server dry-run도 통과했다.

```bash
kubectl apply --dry-run=server -f /tmp/harbor-fix-deployments.yaml
```

## Post-sync verification

Argo CD sync 후 확인:

```bash
kubectl -n argocd get app harbor -o wide
kubectl -n harbor get pods -o wide
```

결과 요약:

```text
habor-harbor-jobservice-677657b689-ksp5t   1/1   Running   node=rm352-1
habor-harbor-registry-8974d795f-bpdj4      2/2   Running   node=rm352-1
```

rollout 확인:

```bash
kubectl -n harbor rollout status deploy/habor-harbor-jobservice
kubectl -n harbor rollout status deploy/habor-harbor-registry
```

관측 결과:

```text
deployment "habor-harbor-jobservice" successfully rolled out
deployment "habor-harbor-registry" successfully rolled out
```

VolumeAttachment도 기존과 동일하게 `rm352-1`에 붙어 있었다.

```text
habor-harbor-jobservice   rm352-1   attached=True
habor-harbor-registry     rm352-1   attached=True
```

## Remaining OutOfSync

최종적으로 Harbor service health는 `Healthy`였고 Pod도 모두 Ready였지만, Argo CD app은
`OutOfSync`로 남을 수 있다. 확인 당시 OutOfSync 대상은 아래 StatefulSet이었다.

```text
apps/StatefulSet harbor habor-harbor-database OutOfSync
apps/StatefulSet harbor habor-harbor-redis    OutOfSync
apps/StatefulSet harbor habor-harbor-trivy    OutOfSync
```

live/desired 비교에서 보인 차이는 주로 Kubernetes 기본값/정규화 필드였다.

예시:

```text
spec.updateStrategy: desired null vs live RollingUpdate
spec.podManagementPolicy: desired null vs live OrderedReady
spec.persistentVolumeClaimRetentionPolicy: desired null vs live Retain
volumeClaimTemplates: desired lacks volumeMode/status, live has volumeMode/status
resources cpu: desired 1000m/2000m vs live 1/2
```

따라서 이번 장애의 stop condition은 `harbor` app의 완전한 `Synced`가 아니라 다음으로 잡았다.

```text
registry/jobservice rollout successful
ContainerCreating pods gone
all Harbor pods Ready
Harbor app Health Healthy
```

StatefulSet OutOfSync는 별도 drift cleanup 항목으로 분리한다.

## OpenBao / ExternalSecret status

TwinX에는 OpenBao와 External Secrets Operator가 이미 있다.

```text
ClusterSecretStore: openbao-cluster-store
provider: vault/openbao
```

하지만 확인 당시 Harbor는 아직 OpenBao/ExternalSecret에 연결되어 있지 않았다.

```text
argocd/twinx-infra/apps/harbor/values.yaml
harborAdminPassword: "0070"
```

Harbor chart의 랜덤/민감 secret도 values에서 고정하거나 `existingSecret`으로 넘겨야 GitOps drift를 줄일 수 있다.
후속 작업 후보:

- `harborAdminPassword`를 OpenBao -> ExternalSecret -> `existingSecretAdminPassword`로 이동
- `secretKey`, `core.secret`, `core.xsrfKey`, `jobservice.secret`, `registry.secret` 고정
- `registry.credentials.htpasswdString` 또는 existing secret 사용 검토
- Harbor용 ExternalSecret manifest를 `argocd/twinx-infra/apps/harbor-resources` 같은 별도 app으로 분리

민감값은 Git에 평문으로 추가하지 않는다.

## Prevention

- RWO PVC를 사용하는 Deployment는 새 Pod가 다른 노드에 먼저 뜨는 rollout을 피한다.
- chart가 `Recreate`를 지원한다고 해도 실제 렌더링 결과와 Kubernetes server dry-run을 확인한다.
- Harbor chart `1.19.1`에서는 `Recreate`가 `rollingUpdate: null`을 렌더링하므로 이 조합을 피한다.
- GitOps 운영에서는 live `kubectl patch/delete`보다 values 변경 -> PR -> merge -> Argo sync 순서로 처리한다.
- Harbor secret은 OpenBao/ESO로 옮겨 Git에 평문이 남지 않도록 한다.

## Useful commands

### Harbor app/pod 상태

```bash
kubectl -n argocd get app harbor -o wide
kubectl -n harbor get pods -o wide
kubectl -n harbor get deploy -o wide
```

### OutOfSync 리소스만 보기

```bash
kubectl -n argocd get app harbor \
  -o jsonpath='{range .status.resources[?(@.status=="OutOfSync")]}{.group}{"/"}{.kind}{"\t"}{.namespace}{"\t"}{.name}{"\t"}{.status}{"\n"}{end}'
```

### PVC attach 위치 확인

```bash
kubectl -n harbor get pvc habor-harbor-jobservice habor-harbor-registry -o json > /tmp/harbor-pvc.json
kubectl get volumeattachments.storage.k8s.io -o json > /tmp/volumeattachments.json
python3 - <<'PY'
import json
from pathlib import Path

pvcs = json.loads(Path('/tmp/harbor-pvc.json').read_text())['items']
pvs = {i['spec']['volumeName']: i['metadata']['name'] for i in pvcs}
vas = json.loads(Path('/tmp/volumeattachments.json').read_text())['items']
for va in vas:
    pv = va.get('spec', {}).get('source', {}).get('persistentVolumeName')
    if pv in pvs:
        print(pvs[pv], pv, va.get('spec', {}).get('nodeName'), va.get('status', {}).get('attached'))
PY
```

### Harbor chart 렌더링 검증

```bash
helm template habor harbor/harbor \
  --version 1.19.1 \
  --namespace harbor \
  -f argocd/twinx-infra/apps/harbor/values.yaml > /tmp/harbor-rendered.yaml

grep -n 'rollingUpdate: null' /tmp/harbor-rendered.yaml || true
```
