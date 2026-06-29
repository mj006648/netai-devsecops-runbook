# demo-appset-edge

ApplicationSet 실험에서 사용하는 Edge 계열 workload다.

## 배치 의도

```text
selector: scalex.io/location=edge
replicas: 2
expected: edgex=1, pullx=1
```

`pullx`는 Pull mode cluster이므로, 이 workload는 ApplicationSet -> Karmada -> Push/Pull 혼합 전파를 확인하는 데 사용한다.
