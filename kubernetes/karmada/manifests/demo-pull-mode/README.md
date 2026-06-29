# demo-pull-mode 실험

이 manifest는 Pull mode로 등록된 member cluster가 Karmada API Server에서 work를 가져가 실제 workload를 생성하는지 확인한다.

## 목적

ScaleX-POD에서는 EdgeX처럼 control plane에서 member API endpoint로 직접 접근하기 어려운 위치의 cluster가 생길 수 있다. 이때 Push mode 대신 Pull mode를 쓰면 member cluster 내부의 `karmada-agent`가 Karmada API Server에 접속해서 배포 대상을 가져간다.

## 구성

```text
대상 cluster label: scalex.io/connectivity=pull
workload: demo-pull-mode-nginx Deployment replicas=2 + Service
namespace: demo-pull-mode
```

## 적용

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config apply -f kubernetes/karmada/manifests/demo-pull-mode/
```

## 확인

```bash
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get cluster pullx -o wide --show-labels
kubectl --kubeconfig ~/.kube/karmada-apiserver.config get rb -n demo-pull-mode -o wide
kubectl --context kind-pullx -n demo-pull-mode get deploy,pod,svc -o wide
```

## 기대 결과

```text
pullx cluster MODE: Pull
pullx karmada-agent: Running
Deployment/Pod/Service: pullx에 생성
다른 Push mode cluster: demo-pull-mode workload 없음
```
