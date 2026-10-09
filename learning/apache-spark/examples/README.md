# Spark 실습 파일

설치·실행·예상 결과와 실행 여부는 [11장](../11-local-labs.md)을 따른다. 이 디렉터리의 프로그램은 교육용 입력을 사용하며 이번 교재 작성 때 실행하지 않았다.

| 파일 | 역할 |
| --- | --- |
| [requirements.txt](requirements.txt) | PySpark 4.0.4 버전 고정 |
| [batch_sensor_lab.py](batch_sensor_lab.py) | 정제·집계·join·Parquet 재읽기 |
| [streaming_rate_lab.py](streaming_rate_lab.py) | 가상 연속 입력과 micro-batch 관찰 |

저장소 최상위에서 실행하며 로컬 Java 17/21과 별도 Python 환경이 필요하다. 임시 출력은 정상 종료할 때 정리한다. checkpoint를 남겨 복구하는 실험은 본 예제와 별도로 설계한다.
