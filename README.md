# NetAI 운영 런북

[GIST NetAI Lab](https://netai.smartx.kr/)에서 **TwinX**와 **MiniX** 클러스터를 운영하면서 쌓은 운영 런북이다.
네트워킹, 스토리지, 정책, 관측, 애플리케이션, 장애 대응 과정에서 실제로 겪은 문제와 해결 절차를 정리한다.

> 주 대상은 랩 내부 운영자다. 완성된 가이드라기보다 운영 중 계속 업데이트하는 작업 노트에 가깝다.
> 공개 저장소로 두는 이유는 비슷한 문제를 만난 사람이 그대로 참고할 수 있게 하기 위해서다.

## 구성

- **[networking/](networking/)** — netplan, Cilium, MTU, 보조 IP, 노드 라우팅
- **[storage/](storage/)** — Rook-Ceph 설치, 복구, 튜닝, LVM 준비
- **[policy/](policy/)** — Kyverno, cert-manager, webhook 수명 주기
- **[observability/](observability/)** — Prometheus, Grafana, OpenTelemetry
- **[apps/](apps/)** — TwinX/MiniX에서 운영하는 앱, 포털, 카탈로그 서비스, 쿼리 엔진
- **[incidents/](incidents/)** — 시간순 장애 대응 기록과 사후 정리

## 노트 작성 형식

각 노트는 새벽 3시에 봐도 바로 따라갈 수 있도록 아래 흐름으로 작성한다.

- **증상** — 실제로 관측되는 현상
- **진단** — 확인에 사용한 정확한 명령
- **원인** — 왜 발생했는지
- **해결** — 복구 절차
- **재발 방지** — 다음에 같은 문제를 피하는 방법

## Discussions

정식 문서로 정리하기 전의 질문이나 메모는 [Discussions](https://github.com/mj006648/netai-devsecops-runbook/discussions)에 남긴다.

## License
MIT
