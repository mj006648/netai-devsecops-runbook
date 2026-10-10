# GPU Operator·DRA 교재 예제

| 파일 | 역할 |
| --- | --- |
| [allocation_model.py](allocation_model.py) | GPU 없이 속성 선택·공동 node 배치·예약을 배우는 교육 모형 |
| [dra-one-gpu.yaml](dra-one-gpu.yaml) | 06장의 ClaimTemplate·Pod API 연결 예시; 실제 적용하지 않음 |

실행 방법·예상 결과·한계는 [12장](../12-local-model-labs.md)을 따른다. 실제 Kubernetes API 서버나 NVIDIA GPU를 제어하지 않고 표준 라이브러리만 사용한다. Kubernetes에 제출하는 API 예시는 [06장](../06-dra-yaml-walkthrough.md)에 별도로 있다.
