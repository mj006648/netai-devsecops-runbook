# netplan secondary IP 추가 후 노드가 NotReady 되는 문제

## 증상
- Primary interface에 secondary IP 예: `.190` ~ `.199/24`를 추가하는 netplan 변경을 적용한 뒤
  노드가 `NotReady`가 되고, 해당 노드의 pod가 outbound connectivity를 잃는다.
- API server 또는 Cilium 로그에서 node-to-control-plane traffic의 source IP가
  primary node IP가 아니라 secondary address로 보인다.

## 진단
```bash
# outbound traffic에 kernel이 어떤 source IP를 고르는지 확인
ip route get 8.8.8.8

# netplan이 설치한 route 확인
ip route show
```

`ip route get` 결과의 `src`가 primary node IP가 아니라 `<secondary-IP>`라면,
secondary address가 source-IP selection을 가져간 상태다.

## 원인
netplan의 flat `addresses:` list로 같은 subnet에 여러 주소를 넣으면 kernel route가 아래처럼 생긴다.

```text
192.168.x.0/24 dev eno1 proto kernel scope link src 192.168.x.199
```

이 route의 `src` 필드에 들어간 주소가 해당 subnet outbound traffic의 기본 source가 된다.
그 결과 kubelet/Cilium이 알고 있는 node IP와 API server가 실제로 보는 source IP가 달라지고,
노드가 `NotReady`로 표시된다.

## 해결 — secondary IP는 `/32`로 고정하고 명시적인 `from` route를 둔다
```yaml
network:
  version: 2
  ethernets:
    eno1:
      addresses:
        - 192.168.x.10/24                # primary, 기존 node IP
        - 192.168.x.190/32               # secondary는 /32
        - 192.168.x.191/32
      routing-policy:
        - from: 192.168.x.190/32
          table: 100
        - from: 192.168.x.191/32
          table: 100
      routes:
        - to: 0.0.0.0/0
          via: 192.168.x.1
          table: 100
```

적용과 확인:
```bash
sudo netplan apply
ip route get 8.8.8.8                      # src = primary node IP
ip route get 8.8.8.8 from 192.168.x.190   # table 100 사용
```

노드는 `Ready`로 돌아오고, `.190–.199`에 명시적으로 bind하는 앱은 그대로 동작한다.

## 재발 방지
- K8s node IP와 같은 `/24`에 secondary IP를 추가할 때 netplan flat `addresses:` list에 그대로 넣지 않는다.
  항상 `/32 + from route` 방식을 사용한다.
- Kubernetes 노드에서 netplan을 변경한 뒤에는 `ip route get <external>`로 source IP가 바뀌지 않았는지 확인한다.

## 참고
- Discussion: [#1](https://github.com/mj006648/netai-devsecops-runbook/discussions/1)
