"""16-bit logical address와 256-byte page의 작은 변환 모형.

실제 CPU의 multi-level page table이나 TLB 성능을 재현하지 않는다.
"""

PAGE_SIZE = 256
ADDRESS_BITS = 16
PAGE_TABLE = {0x12: 0x3A, 0x7F: 0x04}


def translate(logical: int) -> tuple[int, int, int]:
    if not 0 <= logical < 2**ADDRESS_BITS:
        raise ValueError("16-bit address 범위를 벗어났습니다")
    vpn, offset = divmod(logical, PAGE_SIZE)
    if vpn not in PAGE_TABLE:
        raise LookupError(f"VPN 0x{vpn:02x}: page fault 모형")
    frame = PAGE_TABLE[vpn]
    physical = frame * PAGE_SIZE + offset
    return vpn, offset, physical


for address in (0x1234, 0x7FFE, 0x2201):
    try:
        vpn, offset, physical = translate(address)
        print(
            f"VA 0x{address:04x} -> VPN 0x{vpn:02x}, "
            f"offset 0x{offset:02x} -> PA 0x{physical:04x}"
        )
    except LookupError as error:
        print(f"VA 0x{address:04x} -> {error}")
