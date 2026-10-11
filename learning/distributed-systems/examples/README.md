# 실행 가능한 교육용 모델

세 파일은 Python 표준 라이브러리만 사용한다.
고정된 작은 사건에서 상태를 직접 계산하고 불변식을 `assert`로 검증한다.
실제 분산 제품이나 전체 Raft 구현이 아니다.

```bash
python3 replication_model.py
python3 raft_commit_model.py
python3 retry_dedup_model.py
```

- `replication_model.py`: 비동기 복제의 적용 전·후 읽기를 계산한다.
- `raft_commit_model.py`: 현재 term 항목의 과반수로 commit index를 계산한다.
- `retry_dedup_model.py`: 응답 유실 뒤 같은 요청 ID 재시도의 실행 횟수를 계산한다.
