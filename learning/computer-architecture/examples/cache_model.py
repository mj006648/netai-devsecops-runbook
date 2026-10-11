"""4KiB, 64B line, 2-way cache 교육 모형."""

CAPACITY = 4096
LINE = 64
WAYS = 2
SETS = CAPACITY // LINE // WAYS


def fields(address: int) -> tuple[int, int, int]:
    offset = address % LINE
    line_number = address // LINE
    set_index = line_number % SETS
    tag = line_number // SETS
    return tag, set_index, offset


assert SETS == 32
assert fields(0x1234) == (2, 8, 52)
print("sets", SETS)
print("0x1234 -> tag,set,offset", fields(0x1234))
