# Kubernetes 실습 Manifest

[13장](../13-local-labs.md)의 kind 전용 클러스터에서 사용하는 교육용 예제다. 이번 문서 작성 과정에서는 적용하지 않았다.

| 파일 | 역할 |
| --- | --- |
| [namespace.yaml](namespace.yaml) | 실습 namespace 생성 |
| [configmap.yaml](configmap.yaml) | 교육용 설정 값 전달 |
| [deployment.yaml](deployment.yaml) | Nginx Pod 두 개·자원·probe 설정 |
| [service.yaml](service.yaml) | Pod selector와 내부 Service 연결 |
| [gateway-http-demo.yaml](gateway-http-demo.yaml) | 05A의 별도 심화 예제: GatewayClass·Gateway·HTTPRoute·Service·앱 전체 연결 |

명령은 `--context kind-netai-textbook`을 명시하며 적용 순서는 13장을 따른다. 연구실의 기존 클러스터에 일괄 적용하는 예제로 사용하지 않는다.

`gateway-http-demo.yaml`의 전제와 줄별 해설은 [05A장](../05a-gateway-api.md)에 있다. 이 파일은 기본 kind 실습의 적용 순서에 포함되지 않는다. 호환 Gateway API CRD와 Envoy Gateway controller, 접속 가능한 Gateway 주소가 별도로 필요하다. HTTP만 설명하며 TLS 인증서나 controller 설치를 자동으로 구성하지 않는다.
