"""고정 정책으로 인증된 주체의 행위를 판정하는 교육 모형."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    subject: str
    verb: str
    resource: str
    namespace: str


RULES = {
    ("alice", "get", "pods", "research"),
    ("alice", "list", "pods", "research"),
    ("build-bot", "create", "deployments", "staging"),
}


def authorize(request: Request) -> bool:
    """네 속성이 정확히 일치하는 규칙이 있을 때만 허용한다."""
    key = (request.subject, request.verb, request.resource, request.namespace)
    return key in RULES


def main() -> None:
    cases = [
        (Request("alice", "get", "pods", "research"), True),
        (Request("alice", "delete", "pods", "research"), False),
        (Request("alice", "get", "pods", "production"), False),
        (Request("build-bot", "create", "deployments", "staging"), True),
    ]
    for request, expected in cases:
        actual = authorize(request)
        assert actual is expected, (request, actual, expected)
        print(f"{request.subject:9} {request.verb:6} {request.resource:11} "
              f"{request.namespace:10} -> {'허용' if actual else '거부'}")


if __name__ == "__main__":
    main()
