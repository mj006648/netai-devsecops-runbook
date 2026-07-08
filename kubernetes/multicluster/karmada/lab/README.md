# Karmada kind lab archive

이 디렉터리는 ScaleX-POD 운영 모델을 만들기 위해 수행한 kind 기반 Karmada 실험 기록과 demo manifest archive다.

## 구성

| 경로 | 내용 |
| --- | --- |
| [`experiments/`](./experiments/) | 실험 00~33 상세 기록 |
| [`manifests/`](./manifests/) | 실험에 사용한 demo Kubernetes/Karmada manifest |
| [`argocd/`](./argocd/) | ArgoCD -> Karmada API Server 연동 예제 |
| [`experiment-coverage-review.md`](./experiment-coverage-review.md) | 실험 coverage와 남은 영역 리뷰 |

## 최종 실험 결론

- Karmada는 ScaleX-POD 멀티클러스터 placement/propagation 계층으로 사용 가능하다.
- TowerX 단일 ArgoCD가 여러 repo와 여러 destination을 관리하는 구조가 가능하다.
- `scalex-federation`는 Karmada 전파 repo, `datax/twinx/edgex-k8s`는 cluster-local repo로 분리한다.
- Kueue는 Karmada를 대체하지 않고, 필요 시 member cluster 내부 Job admission/quota 계층으로 둔다.

현재 설계 기준은 [상위 README](../README.md)를 따른다.
