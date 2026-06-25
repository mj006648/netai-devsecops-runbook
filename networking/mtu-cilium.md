# MTU 불일치로 인한 OSD flapping 및 클러스터 불안정

## 증상
- Ceph OSD가 디스크 오류 없이 반복적으로 up/down flapping한다.
- `ceph -s`에 slow ops가 보이고, PG가 `peering` 또는 `inactive`에 머문다.
- 작은 패킷의 pod-to-pod 통신은 되지만 큰 트래픽은 멈춘다.
  예: 작은 JSON `curl`은 되지만 image pull이나 streaming query는 hang.
- `dmesg`에 `fragmentation needed`, `packet too big` 경고가 보일 수 있다.

## 진단
```bash
# host NIC와 pod interface의 MTU 비교
ip link show <host-iface>
kubectl exec -n rook-ceph <osd-pod> -- ip link show

# don't-fragment ping으로 실제 동작 가능한 크기 찾기
ping -M do -s 8900 <other-node-IP>
# 성공할 때까지 -s 값을 낮춘다. 성공값은 effective MTU - 28 정도다.
```

host에서 실제 가능한 크기가 pod 안에서 보이는 MTU보다 훨씬 작다면,
pod가 광고된 MTU만큼 패킷을 채워 보낼 때 wire에서 조용히 drop될 수 있다.

## 원인
Cilium VXLAN/Geneve tunneling은 패킷당 약 50 byte의 overhead를 사용한다.
Host NIC와 pod MTU가 따로 설정되어 있거나, Cilium을 auto-detect로 둔 뒤 host MTU를 나중에 바꾸면
큰 패킷, 특히 Ceph replication/scrub traffic이 fragment되지 못하고 drop될 수 있다.
Overlay 안에서는 Path MTU Discovery가 항상 안정적으로 전파되지 않는다.

## 현재 클러스터 설정 (TwinX)
```yaml
# kubespray roles/network_plugin/cilium/defaults/main.yml
cilium_mtu: "0"      # host에서 auto-detect
```

Auto-detect는 **모든 노드의 primary interface가 이미 의도한 MTU를 가진 상태에서 Cilium이 시작될 때만** 맞게 동작한다.
Cilium이 떠 있는 상태에서 host MTU를 바꿔도 자동 재탐지되지 않으므로 Cilium을 roll해야 한다.

## 해결
1. 일관된 MTU stack을 정한다. 예: host `9000`, Cilium effective `8950`.
   먼저 모든 노드에 host MTU를 적용한다.
2. 둘 중 하나를 선택한다.
   - `cilium_mtu: "0"`을 유지하고 Cilium을 roll해서 다시 탐지하게 한다.
     ```bash
     kubectl -n kube-system rollout restart ds/cilium
     ```
   - 또는 Cilium MTU를 명시적으로 고정한다.
     ```yaml
     cilium_mtu: "8950"
     ```
3. 영향을 받은 노드를 drain/uncordon해서 pod가 새 MTU를 반영하도록 한다.
4. OSD flapping이 멈추고 PG가 `active+clean`으로 돌아오는지 확인한다.

## 재발 방지
- Kubernetes 노드의 host MTU를 바꿀 때는 반드시 CNI도 즉시 roll해서 재탐지하게 한다.
- 클러스터 bring-up smoke test에 다른 노드의 pod 간 `ping -M do -s <effective> <other-pod-IP>`를 추가한다.
- Ceph OSD restart rate에 alert를 건다. 네트워크 또는 CNI 변경 후 같은 문제가 다시 드러나는 경우가 많다.

## 참고
- TwinX: `kubespray/roles/network_plugin/cilium/defaults/main.yml`
