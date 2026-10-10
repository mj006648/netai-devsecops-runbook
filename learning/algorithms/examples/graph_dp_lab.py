"""Graph 순회, 최단 경로, 동적 계획법의 작은 정확성 예제."""

from collections import deque
from heapq import heappop, heappush


def bfs(graph, start):
    order = []
    queue = deque([start])
    visited = {start}
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return order


def dfs(graph, start):
    order = []
    stack = [start]
    visited = set()
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        stack.extend(reversed(graph[node]))
    return order


def dijkstra(graph, source):
    if any(weight < 0 for edges in graph.values() for _, weight in edges):
        raise ValueError("Dijkstra에는 음수가 아닌 간선 가중치가 필요합니다")
    dist = {node: float("inf") for node in graph}
    dist[source] = 0
    heap = [(0, source)]
    while heap:
        distance, node = heappop(heap)
        if distance != dist[node]:
            continue
        for neighbor, weight in graph[node]:
            candidate = distance + weight
            if candidate < dist[neighbor]:
                dist[neighbor] = candidate
                heappush(heap, (candidate, neighbor))
    return dist


def min_coin_table(amount, coins):
    dp = [0] + [amount + 1] * amount
    for value in range(1, amount + 1):
        for coin in coins:
            if coin <= value:
                dp[value] = min(dp[value], 1 + dp[value - coin])
    return dp


def greedy_coin_count(amount, coins):
    count = 0
    for coin in sorted(coins, reverse=True):
        count += amount // coin
        amount %= coin
    return count


def knapsack_01(capacity, items):
    dp = [0] * (capacity + 1)
    for weight, value in items:
        for current in range(capacity, weight - 1, -1):
            dp[current] = max(dp[current], value + dp[current - weight])
    return dp[capacity]


def run_examples():
    graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    assert bfs(graph, "A") == ["A", "B", "C", "D"]
    assert dfs(graph, "A") == ["A", "B", "D", "C"]

    weighted = {
        "A": [("B", 4), ("C", 1)],
        "B": [("D", 1)],
        "C": [("B", 2), ("D", 5)],
        "D": [],
    }
    assert dijkstra(weighted, "A") == {"A": 0, "B": 3, "C": 1, "D": 4}

    try:
        dijkstra({"A": [("B", -1)], "B": []}, "A")
    except ValueError:
        pass
    else:
        raise AssertionError("음수 간선을 거부해야 합니다")

    assert min_coin_table(6, [1, 3, 4]) == [0, 1, 2, 1, 1, 2, 2]
    assert greedy_coin_count(6, [1, 3, 4]) == 3
    assert knapsack_01(5, [(2, 3), (3, 4)]) == 7


if __name__ == "__main__":
    run_examples()
    print("graph_dp_lab: 선택한 정확성 예제가 통과했습니다")
