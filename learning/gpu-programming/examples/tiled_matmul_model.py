"""Tile load와 계산 phase를 분리한 작은 integer matrix 곱 모형."""


def zeros(rows, cols):
    return [[0 for _ in range(cols)] for _ in range(rows)]


def reference_matmul(a, b):
    rows, inner, cols = len(a), len(b), len(b[0])
    assert all(len(row) == inner for row in a)
    result = zeros(rows, cols)
    for row in range(rows):
        for col in range(cols):
            result[row][col] = sum(a[row][k] * b[k][col] for k in range(inner))
    return result


def tiled_matmul(a, b, tile_size):
    rows, inner, cols = len(a), len(b), len(b[0])
    result = zeros(rows, cols)
    trace = []
    for row_base in range(0, rows, tile_size):
        for col_base in range(0, cols, tile_size):
            accum = zeros(tile_size, tile_size)
            for k_base in range(0, inner, tile_size):
                tile_a = zeros(tile_size, tile_size)
                tile_b = zeros(tile_size, tile_size)
                for ty in range(tile_size):
                    for tx in range(tile_size):
                        row, col = row_base + ty, k_base + tx
                        if row < rows and col < inner:
                            tile_a[ty][tx] = a[row][col]
                        row, col = k_base + ty, col_base + tx
                        if row < inner and col < cols:
                            tile_b[ty][tx] = b[row][col]
                for ty in range(tile_size):
                    for tx in range(tile_size):
                        for kk in range(tile_size):
                            accum[ty][tx] += tile_a[ty][kk] * tile_b[kk][tx]
                trace.append((row_base, col_base, k_base, tile_a, tile_b))
            for ty in range(tile_size):
                for tx in range(tile_size):
                    row, col = row_base + ty, col_base + tx
                    if row < rows and col < cols:
                        result[row][col] = accum[ty][tx]
    return result, trace


def main():
    a = [[1, 2], [3, 4]]
    b = [[5, 6], [7, 8]]
    expected = [[19, 22], [43, 50]]
    result_two, trace_two = tiled_matmul(a, b, 2)
    result_one, trace_one = tiled_matmul(a, b, 1)
    assert reference_matmul(a, b) == expected
    assert result_two == expected and result_one == expected
    assert len(trace_two) == 1 and len(trace_one) == 8

    odd = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    odd_result, _ = tiled_matmul(odd, odd, 2)
    assert odd_result == reference_matmul(odd, odd)

    print("2x2 result: [[19, 22], [43, 50]]")
    print("tile=2 phases=1 for one output tile")
    print("boundary zero-fill: 3x3 tile=2 matched reference")
    print("model only: no CUDA barrier or shared memory was executed")


if __name__ == "__main__":
    main()
