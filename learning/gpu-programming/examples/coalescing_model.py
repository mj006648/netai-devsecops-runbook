"""Warp lane 주소와 32-byte sector를 계산하는 GPU 없는 모형."""


def lane_addresses(base, lanes=32, element_bytes=4, stride=1):
    return [base + lane * stride * element_bytes for lane in range(lanes)]


def touched_sectors(addresses, access_bytes=4, sector_bytes=32):
    sectors = set()
    for address in addresses:
        first = address // sector_bytes
        last = (address + access_bytes - 1) // sector_bytes
        sectors.update(range(first, last + 1))
    return sorted(sectors)


def main():
    aligned = lane_addresses(0)
    misaligned = lane_addresses(4)
    stride_two = lane_addresses(0, stride=2)

    assert aligned[0] == 0 and aligned[-1] == 124
    assert touched_sectors(aligned) == [0, 1, 2, 3]
    assert touched_sectors(misaligned) == [0, 1, 2, 3, 4]
    assert touched_sectors(stride_two) == list(range(8))

    print("aligned base=0: addresses 0..127, sectors=4")
    print("misaligned base=4: addresses 4..131, sectors=5")
    print("stride=2: sectors=8")
    print("model only: no GPU transaction or bandwidth was measured")


if __name__ == "__main__":
    main()
