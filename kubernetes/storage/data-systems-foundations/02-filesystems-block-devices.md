# 02. 파일시스템에서 블록 장치와 SSD까지

[학습 목차](README.md) · 이전: [Linux I/O](01-linux-read-write.md) · 다음: [HDFS](03-hdfs-distributed-files.md)

이 장은 Linux 파일을 로컬 장치에 저장하는 일반적인 구조를 설명한다. ext4는 구체적인 학습 예시이며 모든 파일시스템이나 Ceph BlueStore가 ext4 방식으로 동작한다는 뜻은 아니다.

## 1. 파일 이름만으로 데이터 위치를 찾을 수 없는 이유

파일시스템에는 “이름으로 찾기”와 “파일 offset에서 데이터 찾기”가 필요하다.

~~~text
디렉터리 entry: 이름 → inode
inode: 크기·권한·상태·데이터 매핑 정보
extent 등 매핑: 파일의 논리 offset → 장치의 block 범위
block I/O: 실제 주소와 길이를 가진 요청
~~~

Directory entry와 inode를 구분하면 hard link, rename, 열린 파일의 unlink를 이해할 수 있다. 이름을 바꾸는 작업과 payload를 모두 복사하는 작업은 같지 않다. 파일을 열어 둔 참조와 이름을 제거하는 동작 역시 다른 상태다. [Linux VFS](https://docs.kernel.org/filesystems/vfs.html)

## 2. 10 KiB 파일은 몇 개의 block을 쓰는가?

다음은 **block 크기 4 KiB, 압축·inline data·sparse 없음**을 가정한 단순 예시다.

~~~text
파일 길이: 10 KiB
block 0: 4 KiB
block 1: 4 KiB
block 2: 마지막 2 KiB의 유효 데이터
~~~

내용을 담는 데 세 block의 공간이 필요할 수 있지만 이것이 모든 파일시스템에서 정확히 12 KiB의 총 물리 사용량이라는 뜻은 아니다. inode·directory·journal 등 메타데이터 비용이 따로 있고, 공유·압축·inline 기능은 다른 결과를 만들 수 있다.

따라서 apparent size와 allocated size를 구분한다. 크기만 늘린 sparse file에는 실제 데이터 block을 아직 할당하지 않은 hole이 있을 수 있다. 파일 길이만큼 실제 장치 쓰기를 했다고 가정하지 않는다.

## 3. Extent는 왜 필요한가?

연속된 block을 하나하나 나열하는 대신 “논리 block A부터 N개가 물리 block B부터 이어진다”는 구간으로 표현할 수 있다.

~~~text
교육용 표현
logical 0..255   → physical 1000..1255
logical 256..511 → physical 8000..8255
~~~

연속된 큰 구간이면 적은 매핑 정보로 파일을 표현할 수 있다. 반대로 분산된 작은 구간이 많으면 매핑과 I/O가 복잡해질 수 있다. 단, logical 연속과 SSD NAND 물리 연속은 같지 않다. 장치 내부 FTL이 다시 매핑하기 때문이다.

ext4는 block group과 공간 할당 정책을 통해 배치 비용을 관리한다. 파일시스템 block group을 HDFS block으로 혼동하지 않는다. [ext4 구조](https://docs.kernel.org/filesystems/ext4/overview.html)

## 4. 작은 쓰기와 지연 할당

애플리케이션의 작은 쓰기를 즉시 각각의 물리 block 쓰기로 확정하면 비효율적일 수 있다. 파일시스템과 writeback은 요청을 모으고 배치 결정을 늦춰 더 큰 I/O를 만들 수 있다.

장점은 syscall·할당·장치 요청 비용을 줄일 가능성이다. 대가는 메모리에 아직 완료되지 않은 작업이 남고, 동기화 시점이나 압박 상황에 지연이 몰릴 수 있다는 점이다.

**논문 질문:** 요청 하나의 빠른 반환을 측정했는가, 지속적인 처리 능력과 마지막 동기화까지 측정했는가? 이 구분이 없으면 cache와 batching의 효과를 장치 성능으로 오해할 수 있다.

## 5. Journal은 무엇을 복구하는가?

파일 하나를 늘리는 과정에서도 여러 메타데이터가 바뀔 수 있다. 전원이 중간에 끊기면 일부만 바뀐 상태가 남을 수 있으므로, journal은 변경의 복구 가능한 기록을 먼저 남긴다.

~~~text
교육용 흐름
메타데이터 변경 준비
  → journal에 필요한 기록
  → journal transaction의 완료 조건 충족
  → 실제 최종 위치에 반영
  → 이후 journal 공간 재사용
~~~

ext4의 기본적인 metadata journaling을 “모든 사용자 데이터 내용이 항상 원자적으로 보호된다”로 확대해서는 안 된다. data 모드에 따라 사용자 데이터와 journal의 관계가 다르다. [ext4 journal](https://docs.kernel.org/filesystems/ext4/journal.html)

또한 filesystem journal과 DB WAL은 같은 로그가 아니다. 파일시스템은 파일 구조의 일관성을, DB는 row·index·transaction의 복구를 관리한다. 실제 보장 범위는 각 구현과 동기화 설정에 의존한다.

## 6. 논리 block 장치와 실제 저장장치 사이

애플리케이션에서 보이는 볼륨이 물리 디스크 한 개라는 보장은 없다.

~~~text
파일시스템
  → partition 또는 logical volume
  → device mapper / RAID / 가상 block 장치 등
  → 실제 장치 또는 원격 block backend
~~~

같은 물리 NVMe를 여러 logical volume으로 나누어도 물리 장애 영역이 여러 개가 되지 않는다. Kubernetes PVC 세 개나 OSD 세 개가 있다는 사실만으로 물리 장치 세 개의 독립성을 얻었다고 말하면 안 된다.

논문에는 논리 리소스 개수뿐 아니라 CPU·장치·컨트롤러·네트워크를 공유하는 지점을 기록한다.

## 7. HDD와 SSD는 병목 구조가 다르다

HDD에서는 기계적 탐색과 회전 대기가 작은 랜덤 I/O의 주요 비용이 될 수 있다. SSD에서는 기계적 탐색은 없지만 flash 프로그램·지우기, 매핑, 내부 병렬성, controller, garbage collection 등이 중요하다.

그래서 “SSD이면 순차·랜덤 차이가 전혀 없다”도 틀리고 “HDD에서 좋던 설정이 SSD에도 항상 좋다”도 틀리다. 장치 기술에 대한 원리 설명은 [OSTEP의 SSD 장](https://pages.cs.wisc.edu/~remzi/OSTEP/file-ssd.pdf)을 참고한다.

## 8. SSD가 기존 바이트를 단순히 제자리 수정하지 않는 이유

NAND flash에는 프로그램 단위와 지우기 단위가 다르고, 기존 위치를 원하는 대로 반복 덮어쓰는 데 제약이 있다. SSD는 FTL을 통해 호스트 logical 주소를 내부 위치에 매핑한다.

교육용 예시:

~~~text
호스트: LBA X의 내용을 A에서 B로 변경
SSD 내부:
  새 위치에 B 기록
  X의 매핑을 새 위치로 변경
  이전 A의 위치는 더 이상 유효하지 않음
  나중에 유효 page 이동과 erase로 공간 회수
~~~

이 개념도는 특정 SSD의 실제 순서·원자성을 보장하는 명세가 아니다. 장치 firmware와 전원 보호 설계에 따라 달라진다. NAND 단위 크기나 내구성 수치를 제품 확인 없이 고정하지 않는다.

## 9. Write amplification을 계층별로 계산한다

교육용 예시: 애플리케이션이 논리적으로 1 MiB를 변경했는데 DB가 3 MiB를, 장치가 최종적으로 6 MiB를 썼다고 하자.

~~~text
애플리케이션 → DB/파일 계층 쓰기 증폭: 3 / 1 = 3
DB/파일 → 장치 내부 쓰기 증폭:       6 / 3 = 2
애플리케이션 → 최종 물리 쓰기:        6 / 1 = 6
~~~

실제 관측에서는 각 계층의 bytes 정의와 측정 기간을 맞춰야 한다. 요청에 포함되지 않은 background 작업을 섞거나 같은 I/O를 여러 번 세면 비율이 왜곡된다. SMART/NVMe counter도 단위·지원 여부를 확인해야 한다.

Iceberg compaction, LSM compaction, SSD GC가 겹치는 연구에서는 “무슨 계층의 amplification인가?”가 핵심 질문이다.

## 10. 요청 queue와 NVMe 병렬성

Linux block 계층은 여러 CPU가 요청을 제출하고 장치의 여러 hardware queue를 활용할 수 있도록 구성된다. blk-mq의 software staging queue와 hardware dispatch queue는 애플리케이션의 thread 수와 같은 단위가 아니다. [Linux blk-mq](https://docs.kernel.org/block/blk-mq.html)

~~~text
여러 application 요청
  → 파일시스템 / block 요청
  → software queue
  → hardware dispatch queue
  → 장치 실행
  → completion 처리
~~~

queue depth를 늘리면 장치 병렬성을 활용할 수 있지만, 포화 이후에는 대기시간만 증가할 수 있다. 앱 동시성 32가 실제 device queue depth 32를 의미하지도 않는다. cache hit·요청 병합·내부 비동기성이 중간에 있기 때문이다.

## 11. Flush/FUA와 전원 보호

호스트가 장치 완료를 받았다는 말과, 어떤 휘발성 cache까지 안정 저장됐다는 말은 구분해야 한다. 파일시스템의 동기화 요청은 하위 장치·가상화·원격 backend가 그 계약을 제대로 수행한다는 전제를 가진다.

Power-loss protection은 장치의 특성이므로 모델과 설정을 확인해야 한다. 커널 API를 호출했다는 사실만으로 전원 보호 회로나 실제 power-cut 테스트를 검증했다고 쓰지 않는다.

여기서 임의의 power-cut, controller reset, device cache 설정 변경 실습은 제공하지 않는다. 연구용 장애 실험은 복구 가능한 전용 환경과 별도 안전 절차가 필요하다.

## 12. 장치 사용률 숫자 하나로 판단하면 안 된다

iostat의 await에는 요청 queue 대기와 처리 시간이 포함된다. 병렬 처리 장치에서 util이 높거나 낮은 것만으로 최대 성능에 도달했는지 단정하기 어렵다. [iostat 매뉴얼](https://man7.org/linux/man-pages/man1/iostat.1.html)

예를 들어 애플리케이션이 메타데이터 요청을 한 번씩 직렬로 보내면 NVMe 전체가 바쁘지 않아도 애플리케이션은 느릴 수 있다. 반대로 높은 처리량 때문에 util이 높지만 사용자 지연은 허용 범위일 수 있다.

확인할 조합:

- 애플리케이션의 완료 지연과 요청 크기
- 실제 IOPS와 bytes/s
- queue 길이와 await
- CPU·메모리·writeback 상태
- 동일 장치를 사용하는 다른 작업

## 13. 개념 확인

**Q1. 파일 크기와 물리 할당량은 항상 같은가?**

아니다. sparse·압축·metadata·공유 등에 따라 다르다.

**Q2. ext4 journal이 있으면 DB WAL은 불필요한가?**

아니다. 보호하는 객체와 복구 단위가 다르다.

**Q3. LVM으로 나눈 볼륨 세 개는 독립 디스크 세 개인가?**

아니다. 하위 물리 장치와 장애 영역을 확인해야 한다.

**Q4. 앱 thread 수를 두 배로 늘리면 SSD 처리량도 두 배가 되는가?**

아니다. 중간 계층과 병목·장치 포화에 따라 달라진다.

**Q5. compaction 후 조회가 빨라지면 무조건 실행하는 것이 좋은가?**

아니다. 재작성 비용·추가 공간·다른 작업 간섭까지 포함해 판단한다.
