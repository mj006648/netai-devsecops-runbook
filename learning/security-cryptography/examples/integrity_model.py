"""공개 해시 비교와 비밀키 기반 HMAC 검증을 비교하는 교육 모형."""

import hashlib
import hmac


def tag(key: bytes, message: bytes) -> bytes:
    return hmac.new(key, message, hashlib.sha256).digest()


def verify(key: bytes, message: bytes, supplied: bytes) -> bool:
    expected = tag(key, message)
    return hmac.compare_digest(expected, supplied)


def main() -> None:
    demo_key = b"fixed-classroom-key-not-for-production"
    original = b"amount=100&to=bob"
    changed = b"amount=900&to=bob"
    original_tag = tag(demo_key, original)

    assert verify(demo_key, original, original_tag)
    assert not verify(demo_key, changed, original_tag)

    public_hash = hashlib.sha256(original).hexdigest()
    attacker_hash = hashlib.sha256(changed).hexdigest()
    assert attacker_hash != public_hash
    print("원본 HMAC 검증: 성공")
    print("변조 메시지에 원본 HMAC 사용: 실패")
    print("공개 해시는 누구나 다시 계산할 수 있으므로 송신자 인증 수단이 아닙니다.")


if __name__ == "__main__":
    main()
