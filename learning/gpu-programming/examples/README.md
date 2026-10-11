# GPU 없는 Python 계산 모형

세 파일은 Python 3 표준 라이브러리와 고정 입력만 사용한다. File, network, CUDA, GPU에 접근하지 않는다.

```text
python3 -B learning/gpu-programming/examples/coalescing_model.py
python3 -B learning/gpu-programming/examples/tiled_matmul_model.py
python3 -B learning/gpu-programming/examples/collective_cost_model.py
```

| 파일 | 작은 계약 | 검증하지 않는 것 |
| --- | --- | --- |
| coalescing_model.py | Lane 주소와 32-byte sector 집합 | 실제 GPU transaction·bandwidth |
| tiled_matmul_model.py | Tile phase와 정확한 integer 결과 | CUDA barrier·shared memory |
| collective_cost_model.py | Ring byte volume과 α·β 단위 | NCCL·network·topology 성능 |

Assert는 선택한 입력의 계산을 고정한다. 실제 GPU 성능을 측정했다는 주장이 아니다.
