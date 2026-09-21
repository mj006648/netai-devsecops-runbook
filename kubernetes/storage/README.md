# Kubernetes Storage

Rook-Ceph, OSD, PVC, local disk, LV, and Kubernetes storage recovery runbooks.

## Quick map

| Last update | Topic | Document | Contents |
| --- | --- | --- | --- |
| 2026-09-21 | Data Systems Foundations | [데이터 시스템 저수준 기초 학습](data-systems-foundations/) | buffer·page·block·분산 저장·트랜잭션·파일 포맷의 동작 원리, 예시·복습 문답·로컬 실습 |
| 2026-09-16 | Lakehouse / Open Table Formats | [Iceberg·Open Table Format 논문 학습 노트](lakehouse/) | 초심자 개념 설명, 최신 주요 논문·기초 비교 연구, 운영 적용 가설과 미실행 검증 계획 |
| 2026-09-14 | Ceph / PG placement | [TwinX Ceph 내부 풀 배치 복구](twinx-ceph-internal-pool-placement-recovery-2026-09-10.md) | 같은 NVMe의 논리 OSD, 129 PG 복구 재검증과 Monitor 안정성 점검 |
| 2026-06-25 | Rook-Ceph | [Rook-Ceph Reinstall](rook-ceph-reinstall.md) | Rook-Ceph 전체 재설치와 단계별 bring-up 절차 |
| 2026-06-25 | Local disk / LV | [LV Preparation](lv-preparation.md) | stale LVM PV 때문에 OSD prepare가 실패하는 문제 |
