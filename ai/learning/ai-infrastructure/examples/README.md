# AI 교재의 계산 예제 검사

[교재 목차](../README.md) · [여섯 로컬 실습](../11-local-labs-and-research.md)

저장소 루트에서 실행한다. Python 표준 라이브러리와 Bash만 사용한다.

```bash
python3 -B ai/learning/ai-infrastructure/examples/check_lessons.py
python3 -B ai/learning/ai-infrastructure/examples/check_lessons.py --run-python
```

첫 명령은 AI 교재 Markdown의 상대 파일 링크 존재, 표 열 수, 코드 fence, details 쌍, 후행 공백, Python AST 구문과 Bash 구문을 검사한다. URL 접속 가능성이나 Markdown의 링크 anchor까지 확인하는 도구는 아니다.

두 번째 명령은 정적 검사가 통과한 뒤, 교재의 `python` 코드 블록을 하나씩 독립 임시 디렉터리에서 실행한다. 각 예제의 assertion과 종료 결과를 검사하고 15초 시간 제한을 둔다. `text` 의사코드와 Bash 블록은 실행하지 않는다.

`--run-python`은 코드를 실제 실행하는 선택이다. 임시 디렉터리는 작업 파일을 분리하는 기능이며 보안 sandbox가 아니다. 이 교재의 표준 라이브러리 예제를 검토하고 실행하는 용도다. GPU·원격 endpoint·운영 클러스터를 검사하지 않는다.

새 실습을 추가할 때는 블록 하나로 독립 실행되게 하고, 필요한 전제와 기대값·확인하지 못하는 범위를 본문에 적는다. 외부 framework를 설명하기 위한 의사코드는 `text` fence로 구별한다.
