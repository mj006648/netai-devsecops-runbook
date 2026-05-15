# Adding secondary IPs via netplan makes the node NotReady

## Symptom
- After applying a netplan change that adds secondary IPs
  (e.g. `.190` ~ `.199/24`) on the primary interface, the node goes
  `NotReady` and pods on it lose outbound connectivity.
- API server / Cilium logs show node-to-control-plane traffic arriving
  with an unexpected source IP — one of the secondary addresses, not the
  primary node IP.

## Diagnosis
```bash
# Check which source IP the kernel picks for outbound traffic
ip route get 8.8.8.8

# Inspect the routes installed by netplan
ip route show
```

If `ip route get` shows `src <secondary-IP>` instead of the primary node
IP, source-IP selection has been hijacked by the secondary address.

## Root cause
Adding multiple addresses on the same subnet via netplan's flat
`addresses:` list installs kernel routes like:

```
192.168.x.0/24 dev eno1 proto kernel scope link src 192.168.x.199
```

Whichever address wins the route's `src` field becomes the default source
for all outbound traffic on that subnet. Kubelet / Cilium then register
the node with an IP that no longer matches the source seen by the API
server, and the node is marked NotReady.

## Fix — pin secondary IPs to `/32` with explicit `from`-routes
```yaml
network:
  version: 2
  ethernets:
    eno1:
      addresses:
        - 192.168.x.10/24                # primary (unchanged)
        - 192.168.x.190/32               # secondary as /32
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

Apply and verify:
```bash
sudo netplan apply
ip route get 8.8.8.8                      # src = primary node IP
ip route get 8.8.8.8 from 192.168.x.190   # uses table 100
```

The node returns to Ready while apps that explicitly bind to `.190–.199`
still work.

## Prevention
- Never add secondary IPs in the same `/24` as a K8s node IP via netplan's
  flat `addresses:` list. Always use `/32 + from`-route.
- After any netplan change on a K8s node, run `ip route get <external>` to
  confirm source IP didn't shift.

## References
- Lab memory: `project_l40s_netplan_src`
- Discussion: [#1](https://github.com/mj006648/netai-devsecops-runbook/discussions/1)
