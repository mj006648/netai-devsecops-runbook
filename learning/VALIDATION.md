# 인프라 교재 검증 기록

[통합 학습 안내](README.md)

## 2026-10-07 — 입문 설명·깊이·사진·구조도 개편

통합 안내와 연결된 서버 하드웨어·Linux·네트워크·데이터 시스템·AI 인프라의 **59개 장 전체**를 수정했다. [처음 읽는 사람의 지도](START-HERE.md), [공통 용어사전](GLOSSARY.md), [실물 사진 안내](HARDWARE-GALLERY.md)를 추가했다. A7 같은 연구실 고유명, 전문용어의 역할, 부품의 위치, 시간 순서, 계산 전제와 관측 한계를 본문에 보강했다. 예제 프로그램의 기존 구현과 운영 장비 설정은 변경하지 않았다.

검증 환경은 Linux, Python **3.12.3**, Google Chrome headless다. 아래 결과는 문서와 작은 교육 예제의 검증이다.

| 검사 | 결과 | 확인한 범위 |
| --- | --- | --- |
| 교재 구조·링크 | 통과 | 59개 장, 상대 파일·제목 앵커·이미지 링크, 표 열 수, 코드 블록 닫힘, Bash 구문 |
| Python 예제 | 42개 실제 실행 통과 | Python 코드 블록 35개와 shell heredoc 안의 Python 7개; 별도 임시 작업 디렉터리·실행 제한 시간 적용 |
| 기존 I/O 단위 테스트 | 12개 통과 | 부분 쓰기·오류 보고·정리·기존 파일 보존 등 |
| 기존 I/O 실제 실행 | 1 MiB·16 MiB 통과 | 실제 byte 수·SHA-256 일치·임시 디렉터리 제거·파일과 디렉터리 동기화 호출 성공 |
| Mermaid 흐름도 | 66개 파싱·SVG 렌더 통과 | 임시 HTML에서 Mermaid 11.17.2를 사용한 실제 브라우저 검사; 저장소 의존성 추가 없음 |
| SVG 구조도 | 15개 검사 통과 | XML, 제목·설명, 본문 연결 확인; 대표 메모리·GPU·DDR·Linux 도식은 Chrome 렌더 화면에서도 한글·글자 잘림 확인 |
| 실물 사진 | 11개 검사 통과 | JPEG 파일 형식, 저작자·원본·개별 라이선스 기록과 본문 연결 |
| 독립 내용 검토 | 지적 사항 수정 후 재확인 | 작성자와 별도 검토자가 기작·수식·단위·용어 선행 정의를 검토 |
| 변경 공백 | 통과 | `git diff --check` |

Python 코드 블록 35개는 Linux 5개, 네트워크 5개, 데이터 시스템 5개, AI 인프라 20개다. heredoc 7개를 합해 42개이며 같은 예제를 이중 집계하지 않았다. 실행 중에는 PID·주소·시간·할당량처럼 환경에 따라 달라지는 출력을 고정 정답으로 비교하지 않는다. Bash 블록은 구문을 검사했으며, 운영 장비 조회·설정 명령을 일괄 실행한 결과가 아니다.

교차 검토에서는 파일을 여는 이름 탐색 경로와 이미 열린 파일의 읽기·쓰기 경로를 분리했고, Attention의 scaling·mask 전제와 유효 배치의 data-parallel 크기를 바로잡았다. GPU 측정에는 예열·반복·분포·첫 실행 비용을 구분했다. DRAM rank와 분산 실행 rank, DRAM bank와 GPU 공유 메모리 bank, M.2/U.2 형태와 명령 프로토콜, QSFP 형태와 실제 링크 지원을 서로 다른 개념으로 설명했다. 중간에 갑자기 등장하던 약어와 SVG의 한글 표시도 수정했다.

사진은 실제 제품의 원본이며 [저작자·출처·라이선스](../hardware/learning/server-hardware/assets/photos/README.md)를 함께 보관한다. 사진만으로 메모리 rank·실제 링크 속도·장치 호환성을 판정하지 않는다. Mermaid 검사는 [공식 비동기 API](https://mermaid.js.org/config/usage)의 `parse`와 `render`를 사용했다. 이는 해당 버전에서의 검증이며 GitHub나 다른 뷰어의 모든 버전·화면에서 같은 레이아웃을 보장한다는 뜻은 아니다.

### 이번 검사를 재실행하는 명령

저장소 루트에서 실행한다. 통합 검사기는 기존 AI 교재 검사기를 재사용하며 Python 표준 라이브러리만 필요하다. `--run-python`은 저장소의 신뢰하는 교육 예제를 실제로 실행하는 옵션이다. Mermaid의 브라우저 검사는 아래 표준 라이브러리 검사와 별도로 수행했다.

~~~bash
python3 -B learning/validate_docs.py --run-python --output /tmp/netai-learning-validation.json
python3 -B -m unittest discover -s kubernetes/storage/data-systems-foundations/examples -p 'test_*.py'
python3 -B kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 1
python3 -B kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 16
git diff --check
~~~

실제 GPU 실행·분산 학습, 장비 장착·호환성 시험, 운영 클러스터 배포, 전원 차단·장애 주입은 이번 검증에 포함하지 않았다. I/O 실습에서 동기화 호출이 성공한 것은 실제 전원 장애 시험을 통과했다는 뜻이 아니다. 계산은 본문에 적은 가정과 제품·버전별 제약을 함께 읽는다.

## 2026-09-22 — 이전 검증

대상은 서버 하드웨어·데이터 시스템 교재의 상세 보강과, 신규 Linux·커널 및 네트워크·eBPF 교재다. 검증 환경의 Python은 **3.12.3**, 운영체제 계열은 Linux다. 이 기록은 문서·교육 예제의 검증이며 운영 클러스터의 성능·장애 내성을 인증하지 않는다.

### 문서와 예제 검사

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| 상대 파일 링크 | 통과 | 네 교재·통합 안내·분야별 목차에서 대상 파일 존재 확인 |
| Markdown 표·코드 fence·공백 | 통과 | 표 열 수, 코드 블록 닫힘, details 짝, 후행 공백 |
| Python 정적 구문 | 22개 통과 | 본문 Python 블록과 shell heredoc에서 추출하여 AST 파싱 |
| Python 실제 실행 | 22개 통과 | 각 예제를 별도 프로세스·임시 작업 디렉터리에서 실행; 전체 예제별 timeout 적용 |
| Bash 구문 | 39개 통과 | 이 검증 기록의 재실행 블록 1개 포함; `bash -n`으로 검사; 운영 장비 조회 명령을 일괄 실행한 것은 아님 |
| 기존 I/O 단위 테스트 | 12개 통과 | 쓰기 순서·부분 쓰기·오류 보고·정리·기존 파일 보존 |
| 기존 I/O 실제 실행 | 1 MiB·16 MiB 통과 | byte 수·SHA-256·임시 디렉터리 정리·동기화 호출 결과 |
| 독립 내용 검토 | 지적 사항 반영 | 커널·하드웨어·네트워크·파일시스템의 기작·보장 범위·산술 |

Python 예제 22개는 네트워크 5개, 데이터 시스템 6개, Linux 11개다. 주소 변환 모형, 파일 descriptor와 offset, 작은 파일시스템 이미지, sparse file, 프로세스·스레드, mmap, socketpair, IPv4/TCP 파서 등을 포함한다. 메모리 사용량·PID·할당량·경쟁 상태 결과는 환경에 따라 달라지므로 하나의 고정 숫자를 기대하지 않는다.

파서 실습에는 정상 입력뿐 아니라 잘린 헤더, 다른 IP 버전, 잘못된 IHL·총 길이·프로토콜·fragment·TCP data offset 등의 거부 예제를 포함했다. 체크섬 검증이나 실제 wire traffic의 유효성 판정까지 구현한 예제는 아니다.

### 기존 I/O 검사를 재실행하는 명령

저장소 루트에서 실행한다. Python 표준 라이브러리만 사용하며, 실제 파일 예제는 자신이 만든 작은 임시 파일을 정리한다.

~~~bash
python3 -B -m unittest discover -s kubernetes/storage/data-systems-foundations/examples -p 'test_*.py'
python3 -B kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 1
python3 -B kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 16
~~~

다른 본문 예제는 각 장의 실행 블록·전제·예상 결과를 함께 읽고 실행한다. Linux 전용 API를 쓰는 예제를 다른 OS의 보장으로 일반화하지 않는다. multiprocessing 실습은 Python의 기본 시작 방식 변화에 의존하지 않도록 Linux에서 명시적으로 `fork` 문맥을 사용한다. 다른 Python 버전 자체를 이번에 실행 검증한 것은 아니다.

### 검토에서 바로잡은 대표 내용

- 기존 파일 교체의 crash 설명에 기존 상태의 영속성 전제와 파일·디렉터리 동기화 범위를 명시했다.
- Linux `pwrite`와 `O_APPEND`의 예외, 부분 `pread`, `mmap`/`msync` 정렬 조건을 보완했다.
- 작은 모형 파일시스템의 block과 실제 장치 쓰기 단위를 구별하고 상대 symlink의 기준을 수정했다.
- Ethernet MAC frame 크기와 preamble·SFD·IFG를 포함한 선로 점유 시간을 분리했다.
- IPv4 라우터의 TTL·header checksum 갱신, TLS 1.3의 인증서 암호화 범위를 수정했다.
- native XDP와 generic XDP, `skb` 생성과 TC ingress의 순서를 구별했다.
- RCU의 객체 수명 보장을 preemption 금지로 일반화하지 않도록 수정했다.
- EEVDF의 fair scheduling 적용 범위, namespace·cgroup·파일 권한의 경계를 명시했다.

### 이 검증에 포함되지 않은 것

실제 전원 차단·장치 고장, 물리 네트워크 캡처·장애 주입, 운영 eBPF load/attach, Kubernetes·HDFS·Ceph·S3·DB의 실배포, 커널 빌드·부팅, 장치 최대 처리량 시험은 수행하지 않았다. 각 장의 관련 내용은 원리·공식 계약·교육 모형이며 이번 실행 결과로 포장하지 않는다.

공식 자료는 해당 주장 가까이에 연결했다. Linux 내부 구현, 장치 사양, Cilium 동작은 버전·설정에 의존할 수 있다. 수치를 운영 설계에 적용할 때는 정확한 제품·버전·토폴로지·측정 조건을 다시 대조한다.
