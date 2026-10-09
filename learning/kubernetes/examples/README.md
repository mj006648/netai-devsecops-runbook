# Kubernetes 실습 Manifest

[13장](../13-local-labs.md)의 kind 전용 클러스터에서 사용하는 교육용 예제다. 이번 문서 작성 과정에서는 적용하지 않았다.

| 파일 | 역할 |
| --- | --- |
| [namespace.yaml](namespace.yaml) | 실습 namespace 생성 |
| [configmap.yaml](configmap.yaml) | 교육용 설정 값 전달 |
| [deployment.yaml](deployment.yaml) | Nginx Pod 두 개·자원·probe 설정 |
| [service.yaml](service.yaml) | Pod selector와 내부 Service 연결 |

명령은 `--context kind-netai-textbook`을 명시하며 적용 순서는 13장을 따른다. 연구실의 기존 클러스터에 일괄 적용하는 예제로 사용하지 않는다.
