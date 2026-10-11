# GPU 프로그래밍 그림

모든 SVG는 직접 작성한 1200px 벡터 그림이며 한국어 `<title>`, `<desc>`, `role="img"`를 포함한다.

| 파일 | 설명 |
| --- | --- |
| [gpu-programming-map.svg](gpu-programming-map.svg) | Host 준비에서 device kernel·result까지 |
| [thread-hierarchy.svg](thread-hierarchy.svg) | Grid→block→warp→lane 포함 관계 |
| [memory-hierarchy.svg](memory-hierarchy.svg) | Register·shared·global memory 소유 범위 |
| [coalescing-banks.svg](coalescing-banks.svg) | 32 lane×4 byte sector와 shared bank mapping |
| [tiled-matmul.svg](tiled-matmul.svg) | Tile load·barrier·multiply·다음 phase |
| [streams-collectives.svg](streams-collectives.svg) | Stream dependency와 multi-GPU ring |
