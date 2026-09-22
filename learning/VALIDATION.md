# 인프라 교재 검증 기록 — 2026-09-22

[통합 학습 안내](README.md)

대상은 서버 하드웨어·데이터 시스템 교재의 상세 보강과, 신규 Linux·커널 및 네트워크·eBPF 교재다. 검증 환경의 Python은 **3.12.3**, 운영체제 계열은 Linux다. 이 기록은 문서·교육 예제의 검증이며 운영 클러스터의 성능·장애 내성을 인증하지 않는다.

## 문서와 예제 검사

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

## 기존 I/O 검사를 재실행하는 명령

저장소 루트에서 실행한다. Python 표준 라이브러리만 사용하며, 실제 파일 예제는 자신이 만든 작은 임시 파일을 정리한다.

~~~bash
python3 -B -m unittest discover -s kubernetes/storage/data-systems-foundations/examples -p 'test_*.py'
python3 -B kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 1
python3 -B kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 16
~~~

다른 본문 예제는 각 장의 실행 블록·전제·예상 결과를 함께 읽고 실행한다. Linux 전용 API를 쓰는 예제를 다른 OS의 보장으로 일반화하지 않는다. multiprocessing 실습은 Python의 기본 시작 방식 변화에 의존하지 않도록 Linux에서 명시적으로 `fork` 문맥을 사용한다. 다른 Python 버전 자체를 이번에 실행 검증한 것은 아니다.

## 검토에서 바로잡은 대표 내용

- 기존 파일 교체의 crash 설명에 기존 상태의 영속성 전제와 파일·디렉터리 동기화 범위를 명시했다.
- Linux `pwrite`와 `O_APPEND`의 예외, 부분 `pread`, `mmap`/`msync` 정렬 조건을 보완했다.
- 작은 모형 파일시스템의 block과 실제 장치 쓰기 단위를 구별하고 상대 symlink의 기준을 수정했다.
- Ethernet MAC frame 크기와 preamble·SFD·IFG를 포함한 선로 점유 시간을 분리했다.
- IPv4 라우터의 TTL·header checksum 갱신, TLS 1.3의 인증서 암호화 범위를 수정했다.
- native XDP와 generic XDP, `skb` 생성과 TC ingress의 순서를 구별했다.
- RCU의 객체 수명 보장을 preemption 금지로 일반화하지 않도록 수정했다.
- EEVDF의 fair scheduling 적용 범위, namespace·cgroup·파일 권한의 경계를 명시했다.

## 이 검증에 포함되지 않은 것

실제 전원 차단·장치 고장, 물리 네트워크 캡처·장애 주입, 운영 eBPF load/attach, Kubernetes·HDFS·Ceph·S3·DB의 실배포, 커널 빌드·부팅, 장치 최대 처리량 시험은 수행하지 않았다. 각 장의 관련 내용은 원리·공식 계약·교육 모형이며 이번 실행 결과로 포장하지 않는다.

공식 자료는 해당 주장 가까이에 연결했다. Linux 내부 구현, 장치 사양, Cilium 동작은 버전·설정에 의존할 수 있다. 수치를 운영 설계에 적용할 때는 정확한 제품·버전·토폴로지·측정 조건을 다시 대조한다.
