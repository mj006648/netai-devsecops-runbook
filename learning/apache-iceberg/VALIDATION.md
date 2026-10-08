# 이 교재의 검증 범위

[교재 목차](README.md)

확인일: 2026-10-08. 이 문서는 실행한 검증과 검증하지 않은 범위를 구분한다. 최신 버전의 기술 근거는 [07장](07-latest-and-compatibility.md), 공식 자료 목록은 [12장](12-exercises-and-glossary.md)에 있다.

## 문서와 그림

저장소 루트에서 다음 검사를 실행한다.

```bash
python3 -B learning/validate_docs.py --run-python
bash -n learning/apache-iceberg/examples/run-local-lab.sh
git diff --check
```

통합 검사는 상대 링크·앵커·표·코드 fence·Bash/Python 구문·SVG XML과 접근성 설명을 확인한다. Python 예제는 임시 디렉터리에서 실행한다. 이 교재의 외부 의존성 있는 Spark 프로그램은 아래의 별도 실습 명령으로 실행한다.

SVG 8장은 Chrome에서 렌더링하고 연락시트로 텍스트·화살표·잘림을 확인했다. Mermaid는 11.17.2로 parse와 SVG render를 확인했다. 실제 GitHub의 Mermaid 버전·폰트·모바일 폭에 따른 표시 차이는 생길 수 있다.

## 실제 Spark 실습

```bash
bash learning/apache-iceberg/examples/run-local-lab.sh
```

실행 조합은 Java 21, Python 3.12.3, PySpark 4.0.4, Iceberg Spark runtime `4.0_2.13:1.12.0`이다. 로컬 CPU 두 thread와 파일 warehouse를 사용한다. 성공 시 `ALL ASSERTIONS PASSED`가 출력된다.

| 검증한 행동 | 확인한 증거 |
| --- | --- |
| v2 생성·append·UPDATE·DELETE·MERGE | 작업 뒤 정렬한 행과 금액의 정확한 기대값 |
| Snapshot과 time travel | 초기 snapshot으로 조회한 초기 세 행 |
| 컬럼 rename | metadata JSON에서 이전·새 컬럼명의 field ID 일치 |
| Partition evolution | 현재 파일에 spec ID 0과 1이 함께 존재 |
| 동일 테이블 v3 upgrade | metadata의 format-version 값 3 |
| v3 row lineage | 새 행 ID·sequence 존재, UPDATE 뒤 ID 보존과 변경 sequence 증가 |
| v3 DV | 삭제 반영, Puffin 엔트리의 참조 데이터 파일·offset·길이 존재 |

## 검증하지 않은 범위

이 실습은 한 프로세스의 교육용 HadoopCatalog 경로다. 여러 writer의 동시 커밋, 분산 Spark·Flink, REST/Hive/Glue 카탈로그, S3/Ceph/MinIO, 원천 CDC exactly-once, 서버 장애·네트워크 분할, 운영 GC를 검증하지 않았다.

실습에서 equality delete의 모든 적용 규칙, v3 defaults·variant·ns 시각·공간 타입·암호화를 모두 실행한 것은 아니다. 이 부분은 공식 명세와 릴리스 문서에 근거해 설명하고 엔진별 실제 지원을 구별했다. v4는 개발 중이고 Iceberg 1.12.0에서 테이블 read/write를 지원하지 않아 실행 대상으로 사용하지 않았다.

운영 도입 전에는 사용하는 엔진·카탈로그·저장소 조합의 기능·동시성·보존·복구 시험을 별도로 수행한다. 교재의 작은 실행 시간을 운영 성능 수치로 사용하지 않는다.
