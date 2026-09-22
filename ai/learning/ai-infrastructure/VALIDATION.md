# AI 인프라 교재 검증 기록 — 2026-09-22

[학습 안내](README.md) · [로컬 실습](11-local-labs-and-research.md) · [검사 도구](examples/README.md)

이 기록은 AI 인프라 00–12장과 목차·용어·교육 예제에 대한 것이다. 기존 하드웨어·Linux·네트워크·데이터 시스템의 [검증 기록](../../../learning/VALIDATION.md)과 별도로 작성했다.

## 실행 검사

실행 환경은 **Linux, Python 3.12.3**이다. 아래 명령으로 검사했다.

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| AI Markdown 구조·상대 링크 | 통과 | 17개 문서, 상대 파일 링크 108개; 표·fence·details·공백 |
| Python 구문·실행 | 20개 통과 | 각 블록을 독립 프로세스·임시 디렉터리에서 실행 |
| Bash 구문 | 4개 통과 | `bash -n`만 수행; 운영 조회·변경 명령 실행 없음 |
| 검사 도구 오류 검출 | 7개 사례 통과 | 깨진 링크·표·Python·Bash·fence, assertion 실패, 정상 실행 |
| 기존 교재 연결·구조 | 통과 | 기존 범위 57개 Markdown, 상대 파일 링크 639개와 Python AST 22개 확인 |
| 독립 기술 검토 | 수정 후 재검토 통과 | 계산·분산 실행·첫 token·서빙 지표·복구·자원 공유 설명 |

기존 네 교재의 Python 본문과 I/O 구현은 이번 추가에서 바꾸지 않았으며, 여기의 20개 실행 결과에 그 교재의 22개 실습을 합산하지 않았다. 기존 교재 연결 검사는 목차 변경의 영향 확인이다.

```bash
python3 -B ai/learning/ai-infrastructure/examples/check_lessons.py --run-python
```

검사 도구는 상대 파일 링크의 대상 존재, 표 열 수, 코드 fence·details 쌍, 후행 공백, Python AST 구문, Bash 구문을 확인한다. Python 블록은 별도 임시 디렉터리에서 독립 실행하며 블록별 시간 제한을 둔다. Bash 블록은 `bash -n`만 실행한다.

## 계산·내용 검토

모델·GPU 실행·분산 학습·추론과 서비스·체크포인트·클러스터 설명을 독립 검토하고 지적 사항을 반영한 뒤 재검토했다. GB/GiB, 파라미터별 상태 크기, GQA의 KV head 수, GPU별 용량과 총량, gradient 평균의 분모, prefill의 첫 token, 통신량의 송·수신 구분, 지연 측정 경계를 중점 대조했다.

수정한 대표 사항은 다음과 같다.

- DDP 통신이 준비된 gradient bucket부터 backward 계산과 겹칠 수 있음을 명시했다.
- 첫 출력 token을 prefill의 마지막 logits에서 선택하는 경로를 설명하고 중복 계산을 제거했다.
- token 간격과 streamed event/chunk 간격, TPOT의 분모를 구별했다.
- goodput 계산에서 실패 요청과 성공했지만 지연 목표를 넘긴 요청을 따로 집계했다.
- MPS client 자원 제한과 MIG의 하드웨어 격리를 구별하고 지원 조건을 명시했다.
- KV cache 부족 시 offload·재계산 조건을 명시하고 vLLM·NCCL의 공식 문서로 연결했다.

교육 예제의 가상 처리량·대역폭·가격·장치 용량은 가정을 적은 계산값이다. 실제 장치나 클러스터의 관측 결과로 해석하지 않는다.

## 검증하지 않은 범위

실제 GPU·NPU 실행, PyTorch·CUDA·NCCL·vLLM 설치와 실행, 모델 다운로드·품질 평가, 다중 노드 통신, 운영 Kubernetes 자원 변경, MIG 재구성, 장치 OOM·전원 장애·분산 서비스 장애 주입은 수행하지 않았다. 고정 조건의 toy 학습·복구 결과로 실제 분산 학습의 bitwise 재현성을 보장하지 않는다.

링크 검사에서 외부 URL의 영구 가용성이나 Markdown 내부 anchor까지 자동 확인하지 않는다. 공식 문서와 원전은 작성 시 내용을 확인했으며, `main`·`stable`·`latest` 주소의 내용과 API·metric 이름은 바뀔 수 있다. 실제 환경에 적용할 때 설치 버전의 문서를 대조한다.
