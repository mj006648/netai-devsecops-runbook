# Apache Iceberg 교재 그림

이 디렉터리의 SVG는 Apache Iceberg 입문 교재를 위해 저장소 안에서 직접 제작한 원본 벡터 그림이다. 외부 이미지, 로고, 아이콘, 웹 폰트 또는 스크립트를 포함하지 않는다. 모든 그림은 저장소 루트의 [MIT License](../../../LICENSE)를 따른다.

| 파일 | 설명 |
| --- | --- |
| `architecture.svg` | 실행 엔진, 카탈로그, 객체/파일 저장소의 역할과 읽기·쓰기 흐름 |
| `metadata-tree.svg` | catalog pointer → metadata JSON → snapshot → manifest list → manifest → 콘텐츠 파일 포인터 트리 |
| `snapshot-timeline.svg` | 스냅샷 사이 데이터 파일 공유와 현재/과거 시점 조회 |
| `commit-conflict.svg` | 두 writer의 낙관적 CAS 충돌·재시도와 별개의 unknown commit state |
| `evolution.svg` | field ID 기반 rename과 여러 partition spec의 공존 |
| `deletes.svg` | copy-on-write, v2 position/equality delete, v3 deletion vector 비교 |
| `v3-lineage.svg` | v3 `_row_id`, `_last_updated_sequence_number`의 갱신·보존 의미 |
| `maintenance.svg` | compaction, refs, snapshot expiration, orphan cleanup과 clock guard |

SVG는 `1200×700` viewBox, 고대비 색상, 한국어 `title`/`desc`, `role="img"`를 사용한다. 글꼴은 로컬 `Noto Sans CJK KR`을 우선하며, 설치된 한국어 sans-serif 글꼴로 대체될 수 있다. `foreignObject`, 외부 참조, JavaScript는 사용하지 않는다.

그림은 개념 학습용이다. SQL 구문, 프로시저 이름, 기본 보존 기간, 특정 기능 지원 여부는 사용하는 엔진과 Apache Iceberg 라이브러리 버전의 공식 문서를 함께 확인한다.
