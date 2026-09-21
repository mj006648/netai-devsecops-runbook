# 08. 운영 장비를 건드리지 않는 로컬 실습

[학습 목차](README.md) · [실습 프로그램 설명](examples/README.md) · 다음: [학습 경로](09-study-roadmap-and-questions.md)

## 1. 안전 규칙과 검증 범위

이 장은 **Linux 읽기 전용 진단과 최대 16 MiB의 임시 파일 실습**이다. 기본 payload는 1 MiB다. 실제 HDFS·Ceph·S3·DB 클러스터에 요청을 보내지 않으며, 전원 차단이나 디스크 부하 시험도 하지 않는다.

하지 않는 것:

- raw block device에 쓰기, 포맷·partition·LVM 변경
- 전역 page cache 제거와 kernel tuning
- 다른 사람의 파일·프로세스·Pod 삭제
- 운영 서비스 중단·장애 주입
- 비밀번호·토큰·실제 endpoint를 Git에 기록

명령은 **런북 저장소 루트에서 실행**한다. Python 예제는 표준 라이브러리만 사용한다. 선택 도구가 없거나 ptrace가 금지된 환경이면 해당 단계는 건너뛰고 미실행으로 기록한다. 설치나 권한 변경을 자동으로 수행하지 않는다.

## 2. 먼저 예측해 보기

실행 전 답을 적는다.

1. Python write가 돌아오면 파일이 물리 장치에 보존됐는가?
2. flush와 fsync 중 무엇이 먼저여야 하는가?
3. 최종 파일명을 바꾼 뒤 왜 디렉터리를 동기화하는가?
4. 읽어서 checksum이 같으면 정전에도 안전함을 증명했는가?
5. 이 실습 결과를 NVMe의 최대 성능으로 써도 되는가?

실행 후 답을 수정하되, 측정하지 않은 것은 “모른다”로 남긴다.

## 3. 읽기 전용으로 내 실행 환경 알아보기

~~~bash
getconf PAGESIZE
stat -f -c 'filesystem=%T filesystem_block_size=%S' .
findmnt -T . -o TARGET,FSTYPE,OPTIONS
~~~

- 첫 명령은 이 프로세스 환경의 기본 메모리 page 크기를 확인한다.
- 두 번째는 현재 경로의 파일시스템 관련 정보를 보여준다. 출력의 계열 이름은 실제 mount의 FSTYPE과 함께 해석한다.
- 세 번째는 현재 경로가 어느 mount에 놓이는지 확인한다. 컨테이너에서는 보이는 mount와 실제 물리 저장장치가 다를 수 있다.

결과가 둘 다 4096이라고 메모리 page와 파일시스템 block이 같은 객체가 되는 것은 아니다.

~~~bash
lsblk -o NAME,TYPE,SIZE,LOG-SEC,PHY-SEC,MOUNTPOINTS
vmstat 1 2
iostat -xz -y 1 2
~~~

이는 시스템 전체를 짧게 조회하는 명령이다. 컨테이너 권한에 따라 장치가 안 보이거나 제한될 수 있다. 확인한 값은 현재 환경 설명이지 스토리지 성능 인증이 아니다. vmstat 첫 보고와 iostat의 -y 의미를 구분해 boot 이후 누적 값과 구간 값을 혼동하지 않는다.

## 4. Buffered write부터 디렉터리 동기화까지

~~~bash
PYTHONDONTWRITEBYTECODE=1 python3 kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 1
~~~

프로그램은 다음 작업을 수행한다.

1. 자신의 임시 하위 디렉터리를 생성한다.
2. 결정적인 작은 payload를 임시 파일에 쓴다.
3. Python buffer를 flush한다.
4. 파일 descriptor를 fsync한다.
5. 같은 디렉터리에서 최종 이름으로 replace한다.
6. 디렉터리 fsync를 시도한다.
7. 다시 읽어 bytes와 SHA-256을 확인한다.
8. 자신이 만든 임시 디렉터리만 정리한다.

큰 쓰기는 buffer가 자동으로 하위 syscall에 전달될 수 있다. 따라서 write 단계 시간이 순수한 메모리 복사 시간이라고 가정하지 않는다. flush의 추가 비용이 작아도 flush가 불필요하다는 뜻이 아니다.

결과 JSON에서 확인할 필드:

| 필드 | 의미 |
| --- | --- |
| educational_only | 교육용 실행이며 실험 성능 주장용이 아님 |
| actual_bytes | 실제 읽어 확인한 bytes |
| hash_match | 현재 readback이 기대 내용과 일치하는지 |
| phases | write·flush·fsync·replace·directory fsync·검증 단계 시간 |
| directory_fsync | 해당 호출의 성공 또는 지원 불확실성 |
| temporary_child_removed | 예제가 생성한 임시 하위 디렉터리 정리 여부 |

시간은 환경에 따라 달라지므로 이 문서에 빠른 예시 숫자를 미리 넣지 않는다. 결정적인 payload는 압축하기 쉬운 반복 데이터이며, 이를 실제 자율주행 데이터의 압축·처리 특성으로 일반화하지 않는다.

## 5. Syscall 순서 관찰하기 — 선택 도구

strace가 있는 Linux 환경에서 **새로 실행하는 예제 프로세스만** 추적한다. 다른 프로세스에 attach하지 않는다.

~~~bash
strace -e trace=write,fsync,rename,renameat,renameat2   python3 kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 1   >/dev/null
~~~

확인할 것은 파일 쓰기, 파일 fsync, rename 계열, 디렉터리 fsync 순서다. 플랫폼·라이브러리에 따라 실제 syscall 이름은 달라질 수 있다. write에는 JSON 출력 같은 다른 목적의 호출도 있으므로 모두 payload 기록으로 세지 않는다.

Python flush는 user-space 메서드라 strace에 “flush”라는 syscall로 나타나지 않는다. 이미 buffer가 전달됐다면 추가 write가 없을 수도 있다. strace 자체가 실행을 교란하므로 이 상태의 시간은 benchmark 결과로 사용하지 않는다.

## 6. 파일 길이와 할당량을 구분하기

아래 Python 블록은 자신이 만든 임시 디렉터리에서 1, 511, 4097 bytes 파일만 생성한다.

~~~bash
python3 - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory(prefix="file-allocation-study-") as name:
    for size in (1, 511, 4097):
        path = Path(name) / f"sample-{size}.bin"
        path.write_bytes(b"x" * size)
        info = path.stat()
        print("logical_bytes=", info.st_size,
              "allocated_512byte_units=", info.st_blocks)
PY
~~~

Linux에서 st_blocks는 512-byte 단위의 할당량을 보고하지만, 출력이 모든 파일시스템에서 동일할 것이라고 예측하지 않는다. 지연 할당·압축·inline data 등 구현에 따라 다를 수 있다. 파일시스템 전체 journal/metadata 비용을 이 값으로 모두 계산할 수도 없다.

## 7. 테스트 실행

~~~bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover   -s kubernetes/storage/data-systems-foundations/examples   -p 'test_*.py'
~~~

테스트는 다음 종류의 동작을 검사한다.

- flush → file fsync → replace → directory fsync 순서
- 잘못된 크기·입력 처리와 부분 쓰기
- 내용 검증과 임시 디렉터리 정리
- 기존 파일 보존
- 동기화 오류를 성공으로 보고하지 않는지
- 미지원 directory fsync를 확인된 내구성으로 오해하지 않는지

mock 기반 순서 검증과 실제 작은 파일 읽기·쓰기 검증을 구분한다. 둘 모두 전원 차단 시험은 아니다.

## 8. 이번 실습으로 알 수 없는 것

- 전원 손실 후 파일·디렉터리가 실제로 복구되는지
- SSD 내부 write amplification이나 최대 처리량
- HDFS packet ACK·hsync, Ceph 복제·EC의 실제 장애 내성
- S3 원격 서비스의 일관성이나 객체 보존 상태
- Iceberg 다중 writer 충돌·WAP·Trident Ready 상태

해당 주제의 원리는 다른 장에서 설명하지만, 실제 클러스터 검증은 별도 실행 명세·격리 환경·자원 예산이 필요하다.

## 9. 실습 기록 양식

~~~text
날짜:
운영체제 / Python:
실행한 명령:
파일시스템과 확인 가능한 설정:
입력 크기:
확인한 호출 순서:
bytes / hash 일치:
동기화의 성공·미지원·오류:
실행하지 않은 항목과 이유:
이 결과로 주장할 수 없는 것:
~~~

최종 질문: **“파일을 썼다” 대신 어느 계층의 어떤 완료 조건까지 확인했는지 설명할 수 있는가?**
