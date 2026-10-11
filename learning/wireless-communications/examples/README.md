# 무선 장비 없이 읽는 작은 계산 모형

Python 3.10 이상과 표준 라이브러리만 사용한다. 저장소 root에서 실행하는 명령은 다음과 같다.

```bash
python3 -B learning/wireless-communications/examples/link_budget_capacity.py
python3 -B learning/wireless-communications/examples/ofdm_model.py
python3 -B learning/wireless-communications/examples/ran_ai_budget.py
```

| 파일 | 입력과 확인할 결과 |
| --- | --- |
| [link_budget_capacity.py](link_budget_capacity.py) | 3.5 GHz·1 km·20 MHz의 가정에서 수신 전력, 잡음, SNR과 Shannon 상한 |
| [ofdm_model.py](ofdm_model.py) | subcarrier 8개, CP 2개, 3개 tap의 무잡음 채널에서 주파수별 복원 |
| [ran_ai_budget.py](ran_ai_budget.py) | 처리 창 1 ms, RAN 0.6 ms, 보호 여유 0.1 ms에서 AI의 허용 예산 |

입력은 교육용 가정이다. 실제 전파 측정, 5G 규격 전체 구현, CPU/GPU 성능 측정이나 deadline 보장 시험이 아니다. 식·단위·코드의 상태 변화와 생략한 조건은 [19장](../19-local-models-and-research.md)에서 읽는다.

[교재 목차](../README.md)
