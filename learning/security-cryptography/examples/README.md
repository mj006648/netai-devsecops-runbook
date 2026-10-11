# 로컬 교육 모형

세 파일은 Python 표준 라이브러리와 고정 입력만 사용한다. 네트워크에 연결하지 않고 파일, 환경 변수, 운영체제 권한을 바꾸지 않는다.

```bash
python3 authorization_model.py
python3 nonce_registry_model.py
python3 integrity_model.py
```

| 파일 | 관찰할 것 | 실제로 검증하지 않는 것 |
|---|---|---|
| [authorization_model.py](authorization_model.py) | 주체·동사·자원을 모두 비교하는 정책 판정 | Kubernetes API 서버나 실제 RBAC 설정 |
| [nonce_registry_model.py](nonce_registry_model.py) | 한 프로세스 메모리에서 같은 키 ID의 nonce 중복 거부 | AEAD 구현, 재시작 뒤 영속성, 다중 프로세스 원자성, 별칭이 다른 동일 키 판별 |
| [integrity_model.py](integrity_model.py) | HMAC 검증과 단순 해시 비교의 차이 | 실제 키 보관, 전자서명, 공급망 전체 |

`nonce_registry_model.py`의 집합은 프로세스가 끝나면 사라진다. 두 프로세스가 따로 실행되거나 같은 실제 키를 `key-A`, `alias-A`로 다르게 부르면 중복을 찾지 못한다. 실제 설계는 키의 암호학적 동일성을 나타내는 안정된 식별자와 재시작에도 남는 원자적 할당 상태가 필요하다. 프로세스마다 자기 목록에서 유일하다는 사실은 같은 키 전체에서 유일하다는 뜻이 아니다.

출력이 예상과 일치해도 실제 시스템의 보안 진단이나 암호 안전성 인증이 아니다. 교육 모형의 가정을 이해하는 것이 목적이다.

---

[교재 목차](../README.md) · [로컬 모형 장](../13-local-models.md)
