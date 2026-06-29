# demo-argocd-kueue-datax

이 예제는 ArgoCD, Karmada, Kueue를 함께 쓰는 end-to-end 구조를 확인한다.

```text
GitHub
  -> ArgoCD on Tower
    -> Karmada API Server
      -> datax member cluster
        -> Kueue admission/queue
```

## 구성

```text
member/
  Kueue ResourceFlavor, ClusterQueue, LocalQueue
  적용 위치: kind-datax

karmada/
  Namespace, Job, PropagationPolicy
  적용 위치: Karmada API Server
  적용 주체: ArgoCD Application
```

## 주의

Kueue CRD는 현재 datax member cluster에만 설치되어 있다. 따라서 Kueue queue 리소스는 Karmada API Server에 제출하지 않고 datax에 먼저 준비한다.

## 기대 결과

```text
1. ArgoCD가 GitHub main의 karmada/ 경로를 Karmada API Server로 sync한다.
2. Karmada가 Job A/B를 datax로 전파한다.
3. datax Kueue는 cpu=1 quota 때문에 Job 하나만 admitted 한다.
4. 다른 Job은 Suspended/Pending 상태로 남는다.
5. ArgoCD/Karmada 관점의 sync 성공과 member Kueue admission 상태를 함께 봐야 한다.
```
