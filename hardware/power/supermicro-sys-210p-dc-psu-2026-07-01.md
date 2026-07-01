# Supermicro SYS-210P DC PSU Troubleshooting

## Current status

- edgebox3/4가 전원 복구되지 않아 Kubernetes 작업을 진행할 수 없는 상태다.
- BMC도 접근되지 않으므로 OS/Kubernetes 이전의 전원 계층 문제로 본다.
- 현재 이 이슈는 **Kubernetes 장애가 아니라 hardware/power blocker**로 분류한다.
- Supermicro에 공식 문의 후, 기존 -48V DC 구성을 유지할지 direct AC 입력 구성으로 전환할지 결정해야 한다.

## Scope

- System family: Supermicro SYS-210P edge server
- 사용 중인 것으로 보이는 모델: `SYS-210P-FRDN6T`
- 매뉴얼에서 확인한 chassis 후보: `CSE-211M-R000NDP`
- 매뉴얼에서 확인한 internal redundant DC PSU 후보: `PWS-601D-1R`, 600W, -48V DC
- 현장에서 확인한 외부 AC-to-48V DC power supply: `S-1200-48`

공개 저장소에는 serial number, asset tag, rack 사진, 내부 IPMI credential을 기록하지 않는다.

## Symptom

- 외부 `S-1200-48` PSU LED가 꺼져 있을 때가 있다.
- LED가 잠깐 켜져도 옆의 정상 PSU보다 밝기가 매우 약하다.
- edgebox chassis 쪽에는 약한 전원 표시만 보이고 실제 boot가 되지 않는다.
- 잠시 후 외부 PSU가 다시 꺼지는 현상이 있다.
- PSU를 서버에서 분리해 별도로 확인했을 때도 출력 또는 LED 상태가 안정적이지 않았다.

## Diagnosis

Cluster 측에서 보이는 증상은 node `NotReady` 또는 미응답이지만, BMC까지 죽어 있으므로 Kubernetes 문제로 단정하지 않는다.

```bash
# 전원 복구 후 cluster-side 상태 확인용이다.
# 전원 자체가 없을 때는 이 명령만으로 원인을 판단하지 않는다.
kubectl get nodes | grep -E 'edgebox3|edgebox4'
```

현장에서 확인할 항목:

1. 외부 PSU로 들어가는 AC 입력이 정상인지 확인한다.
2. 외부 `S-1200-48`의 DC 출력 전압과 polarity를 확인한다.
3. DC 출력 terminal/wiring이 느슨하거나 손상되지 않았는지 확인한다.
4. 정상 동작 중인 옆 PSU와 LED 밝기, fan, 출력 안정성을 비교한다.
5. 가능하면 known-good 48V DC supply로 edgebox를 테스트한다.
6. 외부 PSU와 배선을 분리해서 확인하기 전까지 internal server PSU 고장으로 단정하지 않는다.

## Root cause

아직 확정되지 않았다.

현재 가설:

- 외부 AC-to-48V DC PSU 또는 DC terminal/wiring이 불안정할 가능성이 가장 크다.
- Kubernetes/Kubespray 업그레이드 작업 자체가 서버 물리 전원을 차단했을 가능성은 낮다.
- BMC까지 접근되지 않으므로 OS, kubelet, Cilium 이전 계층의 문제다.

## Fix

아직 영구 조치는 적용하지 않았다.

안전한 다음 단계:

1. `SYS-210P-FRDN6T`를 -48V DC 입력 구성에서 direct AC 입력 구성으로 공식 전환할 수 있는지 Supermicro에 확인한다.
2. AC 전환이 지원된다면 호환되는 Supermicro part number와 필요한 수량을 확인한다.
3. PSU module 외에 power distribution board, rear power cage, cable, inlet module, conversion kit 등이 필요한지 확인한다.
4. AC 전환이 지원되지 않는다면 현재 -48V DC 구성을 유지하기 위한 공식 replacement part 또는 권장 구성을 확인한다.
5. `S-1200-48`과 동급의 third-party 외부 AC-to-48V DC PSU로 교체해도 되는지, 가능하다면 요구 전기 스펙을 확인한다.

## Vendor inquiry draft

```text
Hello Supermicro Support Team,

We are currently using Supermicro SYS-210P-FRDN6T Edge Servers.

According to the user manual MNL-2412, this system appears to use the CSE-211M-R000NDP chassis and PWS-601D-1R 600W -48V DC redundant power supplies.

In our current environment, the servers are powered through external AC-to-48V DC power supplies, model S-1200-48. Recently, some of these external power supplies have shown unstable behavior. The LED is sometimes off, sometimes very dim, and even when the server receives a faint power indication, the server does not boot. When tested separately from the server, the external power supply output also appears unstable. Therefore, we suspect that the external AC-to-48V DC power supply may be faulty.

We would like to confirm the following:

1. Is it officially possible to convert SYS-210P-FRDN6T / CSE-211M-R000NDP from the current -48V DC input configuration to a direct AC input configuration?
2. If AC conversion is supported, could you please provide the exact Supermicro part numbers and required quantities for the compatible AC PSU modules or conversion kit?
3. If AC conversion is supported, are any additional parts required, such as a power distribution board, rear power cage, cable, inlet module, or other accessories?
4. If AC conversion is not supported, what replacement part or recommended configuration should we use to maintain the current -48V DC power setup?
5. Is it acceptable to replace the current external S-1200-48 AC-to-48V DC power supply with an equivalent third-party unit? If so, could you please provide the recommended electrical specifications?

Reference information:

- Server model: SYS-210P-FRDN6T
- Chassis: CSE-211M-R000NDP
- Current internal DC PSU: PWS-601D-1R
- Current external AC-to-48V DC power supply: S-1200-48
- Current symptom: external PSU LED is dim or unstable, server shows only faint power indication and does not boot

We are still checking the official system serial numbers and can provide them later if required.

Thank you.

Best regards,
Changhyeon Im
```

## Verification

전원 복구는 아래 조건이 모두 만족될 때 확인된 것으로 본다.

- BMC가 접근된다.
- chassis 전원이 정상적으로 들어온다.
- OS가 boot된다.
- Kubernetes node가 `Ready`로 돌아오거나, 최소한 OS 계층에서 진단 가능한 상태가 된다.
- 전원 안정화 후 kubelet과 Cilium 상태를 확인한다.

```bash
kubectl get nodes | grep -E 'edgebox3|edgebox4'
```

## Prevention

- BMC까지 죽은 powered-off node는 Kubespray/Cilium 장애로 분류하지 않는다.
- PSU model, wiring 방식, vendor 답변을 이 문서에 계속 누적한다.
- edgebox3/4는 전원 안정화 전까지 Kubernetes upgrade 대상에서 제외한다.
- PSU 교체 또는 AC 전환 전에는 Supermicro 공식 호환 part number를 확인한다.

## Remaining risks

- Supermicro가 지원하는 AC conversion part가 아직 확인되지 않았다.
- `S-1200-48`이 third-party 외부 PSU라면 Supermicro는 internal server PSU 쪽만 보증할 수 있다.
- DC terminal이나 배선이 손상된 경우 외부 PSU만 교체해도 문제가 재발할 수 있다.
