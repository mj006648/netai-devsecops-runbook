# 교육용 로컬 모델

이 디렉터리의 세 프로그램은 데이터베이스 서버를 구현하거나 실제 PostgreSQL 동작을 재현하지 않는다. 외부 패키지, 네트워크, 데이터베이스, 파일 쓰기 없이 고정 입력으로 핵심 규칙을 손으로 따라가기 위한 Python 표준 라이브러리 모델이다.

- `mvcc_model.py`: 명시적인 `committed` XID 집합과 `self_xid`로 튜플 버전의 가시성을 판정한다. 진행 중 목록에서 사라졌다는 이유만으로 commit으로 취급하지 않으므로 aborted XID도 구별한다.
- `join_cost_model.py`: 중첩 반복 조인과 단순 해시 조인의 비교 횟수 및 메모리 한도에 따른 배치를 계산한다.
- `wal_recovery_model.py`: page LSN보다 새롭고 `committed` 집합에 든 기록만 적용하는 의도적인 교육 모형이다. 실제 PostgreSQL redo는 미커밋 트랜잭션의 WAL도 물리 복구에 적용할 수 있고, 이후 MVCC의 트랜잭션 commit 상태가 행 가시성을 판정한다. 따라서 이 파일의 commit 필터를 PostgreSQL redo 알고리즘으로 해석하면 안 된다.

각 파일의 `assert`는 입력, 중간 상태, 예상 결과를 고정한다. 실제 DBMS에는 잠금, aborted transaction, 체크포인트, 버퍼 교체, 디스크 오류처럼 더 많은 상태가 있다.
