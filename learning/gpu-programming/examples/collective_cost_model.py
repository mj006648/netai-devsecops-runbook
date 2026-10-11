"""Ring collective byte volume과 alpha-beta 시간을 계산하는 모형."""

MIB = 1024 * 1024


def ring_allreduce_bytes_per_rank(participants, message_bytes):
    if participants < 2:
        return 0
    return 2 * (participants - 1) * message_bytes / participants


def alpha_beta_seconds(steps, alpha_seconds, bytes_moved, beta_seconds_per_byte):
    return steps * alpha_seconds + bytes_moved * beta_seconds_per_byte


def main():
    bytes_per_rank = ring_allreduce_bytes_per_rank(4, 400 * MIB)
    assert bytes_per_rank == 600 * MIB

    modeled = alpha_beta_seconds(
        steps=6,
        alpha_seconds=5e-6,
        bytes_moved=1_000_000,
        beta_seconds_per_byte=1e-9,
    )
    assert abs(modeled - 1.03e-3) < 1e-15
    assert ring_allreduce_bytes_per_rank(1, 400 * MIB) == 0

    print("P=4 N=400MiB: ring bytes per rank=600MiB")
    print("6 steps, alpha=5us, beta=1ns/byte, bytes=1,000,000: 1030us")
    print("model only: no NCCL, network, or GPU was used")


if __name__ == "__main__":
    main()
