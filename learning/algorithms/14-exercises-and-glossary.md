# 14. 문제·해설·용어사전

[이전](13-local-model-labs.md) · [목차](README.md)

먼저 손으로 풀고 펼쳐진 해설과 비교한다.

```mermaid
flowchart LR
    Q["문제"] --> T["작은 입력 trace"]
    T --> I["Invariant"]
    I --> C["비용"]
    C --> X["반례"]
```

## 1. Worked problems

### 문제 1. 명세

`[4,4,2]`에서 4를 찾는다. “위치 반환”만 쓰면 답이 하나인가?

**해설.** 0과 1이 가능하다. 첫 위치인지 아무 위치인지 정한다.

### 문제 2. Invariant

Maximum `[2,9,3]`의 best 변화를 쓰라.

**해설.** 2→9→9다. 각 단계에서 본 prefix의 최댓값이다.

### 문제 3. Amortized

용량 1 dynamic array에 5번 append할 때 doubling 복사는 몇 개인가?

**해설.** 용량 1→2에서 1, 2→4에서 2, 4→8에서 4, 합 7이다.

### 문제 4. Hash collision

크기 5, `k mod 5`에서 2,7,12를 넣으면?

**해설.** 모두 bucket 2다. Chaining lookup worst 세 key 비교다.

### 문제 5. Binary search

`[3,8,12,20,31,44,57,91]`에서 43을 찾는 lo/hi를 쓰라.

**해설.** 0..7→4..7→4..4→5..4, 부재다.

### 문제 6. Stable sort

`[(2,A),(1,B),(2,C)]` stable 결과는?

**해설.** `[(1,B),(2,A),(2,C)]`다. A-before-C 유지다.

### 문제 7. BFS

A→B,C; B→D; C→D에서 enqueue 시 visited하면 queue는?

**해설.** A, 이후 B,C, 이후 C,D, 이후 D다. D는 한 번만 들어간다.

### 문제 8. Dijkstra

A→B 4, A→C 1, C→B 2이면 B 최단 거리는?

**해설.** 3이다. B=4가 heap에 남아도 stale entry다.

### 문제 9. 음수 edge

A→B 2, A→C 5, C→B -10에서 고전 settled Dijkstra의 문제는?

**해설.** B=2를 먼저 확정하지만 실제 경로 A-C-B는 -5다.

### 문제 10. Greedy coin

동전 1,3,4로 6을 만들라.

**해설.** Greedy 4+1+1 세 개, optimum 3+3 두 개다.

### 문제 11. 0/1 knapsack

물건 (2,3) 하나를 앞 방향 갱신하면 용량 4 값이 6이 될 수 있다. 왜 틀렸는가?

**해설.** 같은 물건으로 만든 dp[2]를 같은 반복에서 다시 써 두 번 선택했다.

### 문제 12. NP-complete

어떤 결정 문제가 NP-hard임만 증명했다. NP-complete인가?

**해설.** 아직 아니다. NP membership, 즉 certificate의 polynomial 검증도 보여야 한다.

## 2. 추가 확인 문제

1. Min-heap과 sorted array의 차이를 예로 설명하라.
2. DFS에서 gray edge가 directed cycle을 보이는 이유를 써라.
3. MST와 shortest path tree의 목적 함수를 비교하라.
4. `T(n)=T(n/2)+1`의 차수를 구하라.
5. DP state가 미래 결정에 충분해야 하는 이유를 써라.
6. P≠NP가 증명되지 않았다는 문장을 자신의 말로 설명하라.

## 3. 용어사전

| 용어 | 뜻 |
| --- | --- |
| 알고리즘 | 허용 입력을 출력으로 바꾸는 유한 절차 |
| 문제 | 입력 집합과 정답 조건의 명세 |
| 사례 | 문제의 특정 입력 한 개 |
| 선조건 | 실행 전에 성립해야 할 약속 |
| 후조건 | 종료 뒤 보장하는 성질 |
| 불변식 | 반복의 정해진 지점마다 참인 문장 |
| 귀납법 | 기저와 단계로 모든 크기의 명제를 보이는 방법 |
| 정확성 | 모든 허용 입력에서 올바르게 종료하는 성질 |
| 시간 복잡도 | 입력 크기에 따른 연산 증가율 |
| 공간 복잡도 | 입력 크기에 따른 메모리 증가율 |
| Big-O | 증가율의 점근적 상한 |
| Big-Ω | 증가율의 점근적 하한 |
| Big-Θ | 같은 차수의 상한과 하한 |
| 최악 비용 | 가장 어려운 허용 입력의 비용 |
| 평균 비용 | 명시한 입력 분포에 대한 평균 |
| 기대 비용 | 확률 변수에 대한 기댓값 |
| 분할 상환 | 연산 연속 전체 비용을 호출당 나누는 분석 |
| 배열 | index로 접근하는 연속 위치 자료구조 |
| 연결 목록 | node를 pointer로 잇는 자료구조 |
| Hash function | key를 정수 위치 후보로 바꾸는 함수 |
| 충돌 | 서로 다른 key가 같은 hash 위치를 얻는 일 |
| Load factor | key 수를 bucket 수로 나눈 값 |
| Stack | 마지막 입력을 먼저 꺼내는 구조 |
| Queue | 첫 입력을 먼저 꺼내는 구조 |
| Priority queue | 가장 작은 또는 큰 우선순위를 먼저 꺼내는 구조 |
| Recursion | 함수가 더 작은 문제로 자신을 호출하는 방식 |
| Tree | cycle 없는 계층 연결 구조 |
| BST | 왼쪽·node·오른쪽 key 순서를 가진 tree |
| Heap | parent와 child 사이 우선순위 규칙을 가진 tree |
| Graph | 정점과 간선의 관계 구조 |
| 정점 | Graph의 대상 |
| 간선 | 두 정점의 관계 |
| BFS | Queue로 거리 층을 넓게 방문하는 순회 |
| DFS | Stack 또는 recursion으로 깊게 방문하는 순회 |
| DAG | Directed acyclic graph |
| 위상 정렬 | 모든 dependency 앞뒤를 지키는 순서 |
| Relaxation | 간선을 통해 더 짧은 거리 후보로 갱신하는 동작 |
| Dijkstra | 비음수 가중치 최단 경로 알고리즘 |
| Bellman–Ford | 음수 간선을 허용하고 반복 relaxation하는 알고리즘 |
| Stale entry | 현재 최선값보다 오래된 heap 후보 |
| Greedy | 현재의 안전한 최선 선택을 반복하는 방식 |
| Spanning tree | 모든 정점을 잇는 cycle 없는 부분 graph |
| MST | 가중치 합이 최소인 spanning tree |
| Union–Find | Disjoint component를 합치고 찾는 구조 |
| 동적 계획법 | 겹치는 부분 문제 답을 상태로 저장하는 방법 |
| 상태 | 미래 계산에 필요한 과거 정보의 요약 |
| 전이 | 작은 상태에서 큰 상태 답을 만드는 식 |
| 기저값 | 가장 작은 상태의 이미 아는 답 |
| Memoization | Top-down 호출 결과를 cache하는 방식 |
| 분할 정복 | 독립 부분 문제로 나누고 결합하는 방식 |
| Stable sort | 같은 key의 원래 상대 순서를 보존하는 정렬 |
| Decision problem | 예·아니오를 출력하는 문제 |
| Optimization problem | 목적 함수의 최선값 또는 해를 찾는 문제 |
| P | Polynomial time에 푸는 결정 문제 집합 |
| NP | Certificate를 polynomial time에 검증 가능한 결정 문제 집합 |
| Reduction | 한 문제의 instance를 답 보존하며 다른 문제로 바꾸는 변환 |
| NP-hard | NP의 모든 문제가 환원되는 난이도 성질 |
| NP-complete | NP에 속하면서 NP-hard인 결정 문제 |
| Pseudo-polynomial | 수치 값에는 polynomial이나 bit 길이에는 아닐 수 있는 비용 |
| Approximation | 최적과의 비율 보장을 가진 근사 해법 |
| Heuristic | 실용 규칙이지만 일반 보장이 없을 수 있는 방법 |

## 4. 마지막 점검표

- 입력과 정답 조건을 썼는가?
- 선조건을 실제 입력이 만족하는가?
- 작은 표에서 상태가 어떻게 변하는가?
- Invariant의 초기·유지·종료가 있는가?
- 시간과 공간을 분리했는가?
- Worst, expected, amortized를 구분했는가?
- 반례로 경계를 시험했는가?
- 시스템 비유와 실제 구현을 구분했는가?

## 참고

[MIT 6.006](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/video_galleries/lecture-videos/), [MIT 6.046J](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/), [Princeton Algorithms](https://algs4.cs.princeton.edu/home/)를 복습 경로로 사용한다.
