# I/O 내구성 교육용 데모

이 디렉터리는 Python 표준 라이브러리만 사용하는 작은 교육용 예제입니다. 한 임시 파일에 대해 다음 순서를 관찰합니다.

1. Python 버퍼를 통한 파일 쓰기
2. 파일 객체 `flush()`
3. 파일 `os.fsync()`
4. 같은 디렉터리 안에서 `os.replace()`
5. 가능한 경우 디렉터리 `os.fsync()`

출력은 JSON이며 바이트 수, 체크섬 일치 여부, 단계별 시간, 디렉터리 `fsync` 상태, 주의사항을 포함합니다. 이 예제는 **교육용일 뿐**이며 프로세스 크래시, OS 크래시, 컨트롤러 리셋, 전원 장애를 주입하지 않습니다. 콜드 캐시 상태를 보장하지 않고, 출력 시간은 장치 벤치마크나 논문/논문형 근거가 아닙니다.

## 저장소 루트에서 실행

```bash
python3 kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py
```

기존 디렉터리를 스크래치 부모로 지정할 수 있습니다. 데모는 항상 그 아래에 자기 소유 `TemporaryDirectory` 자식 디렉터리를 만들고 제거하며, 부모 경로 자체를 덮어쓰거나 삭제하지 않습니다.

```bash
python3 kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --scratch-parent /tmp
```

허용되는 최대 데모 페이로드로 실행합니다.

```bash
python3 kubernetes/storage/data-systems-foundations/examples/io_durability_demo.py --size-mib 16
```

테스트를 실행합니다.

```bash
python3 -m unittest discover -s kubernetes/storage/data-systems-foundations/examples -p 'test_*.py'
```

## 제한과 가정

- Python 표준 라이브러리만 사용합니다. 외부 서비스나 의존성은 없습니다.
- 최소 Python 버전은 **3.10**입니다. 코드가 `Path | None`, `list[str] | None` 같은 PEP 604 타입 표기법을 사용합니다.
- 기본 페이로드는 1 MiB이고 `--size-mib`는 1..16 MiB로 제한됩니다.
- 1 MiB 쓰기라도 “flush 전에는 커널에 전혀 쓰이지 않는다”는 뜻이 아닙니다. Python 버퍼 또는 하위 파일 객체가 이미 일부 `write(2)` 계열 syscall을 수행했을 수 있습니다. 이 데모의 초점은 `flush()`와 `fsync()`를 명시적으로 호출하는 순서입니다.
- `--scratch-parent`는 이미 존재하는 디렉터리여야 합니다. 프로그램은 그 아래에 임시 자식 디렉터리를 만들고 정리합니다.
- sudo, raw device 접근, cache drop, mount 변경, 원격 서비스, 외부 패키지는 사용하지 않습니다.
- `os.replace()`는 같은 디렉터리 안에서 호출합니다. 지원 플랫폼에서 이는 이름 가시성의 원자성을 설명하기 위한 것이며, 그 자체로 영속성을 증명하지 않습니다.
- 파일 닫기(`close`)를 `fsync()`와 동등하다고 보지 않습니다.
- `os.replace()` 뒤에 디렉터리 `fsync()`를 시도합니다. OS나 파일시스템에서 지원하지 않는 것으로 알려진 경우 JSON은 `unknown_not_tested`를 보고하며 원자적 영속성을 보장한다고 주장하지 않습니다. `EIO` 같은 실제 I/O 오류는 실패로 전파합니다.
- 실제 크래시/전원 장애 내구성은 OS, 파일시스템, 마운트 옵션, 스토리지 컨트롤러, 캐시 정책, 하드웨어에 따라 달라집니다.
