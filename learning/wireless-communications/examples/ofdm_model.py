"""N=8의 무잡음 OFDM 교육 모형. 실제 NR PHY 구현이 아니다.

직접 합으로 DFT/IDFT를 계산하고 짧은 다중 경로 채널을 통과시킨다.
채널을 완전히 안다고 가정해 주파수별 나눗셈으로 equalization한다.
"""

import cmath
import math


def dft(samples):
    size = len(samples)
    return [
        sum(value * cmath.exp(-2j * math.pi * k * n / size)
            for n, value in enumerate(samples))
        for k in range(size)
    ]


def idft(carriers):
    size = len(carriers)
    return [
        sum(value * cmath.exp(2j * math.pi * k * n / size)
            for k, value in enumerate(carriers)) / size
        for n in range(size)
    ]


def channel_convolution(samples, taps):
    output = [0j] * (len(samples) + len(taps) - 1)
    for n, value in enumerate(samples):
        for delay, coefficient in enumerate(taps):
            output[n + delay] += value * coefficient
    return output


def transmit(carriers, taps, prefix_size):
    signal = idft(carriers)
    prefix = signal[-prefix_size:] if prefix_size else []
    received = channel_convolution(prefix + signal, taps)
    useful = received[prefix_size:prefix_size + len(carriers)]
    frequency_response = dft(taps + [0j] * (len(carriers) - len(taps)))
    return [value / response for value, response in zip(dft(useful), frequency_response)]


if __name__ == "__main__":
    carriers = [1+1j, 1-1j, -1+1j, -1-1j, 1+1j, -1+1j, 1-1j, -1-1j]
    taps = [1.0, 0.4, 0.2]
    recovered = transmit(carriers, taps, prefix_size=2)
    errors = [abs(actual - expected) for actual, expected in zip(recovered, carriers)]
    no_prefix = transmit(carriers, taps, prefix_size=0)
    no_prefix_error = max(abs(a - b) for a, b in zip(no_prefix, carriers))
    assert max(errors) < 1e-10
    assert no_prefix_error > 1e-3
    print("subcarrier=8, CP=2, channel taps=[1.0, 0.4, 0.2], noise=0")
    print(f"CP 있음: 최대 복원 오차 < 1e-10: {max(errors) < 1e-10}")
    print(f"CP 없음: 최대 복원 오차 {no_prefix_error:.4f}")
    print("가정: 완전한 시간·주파수 동기, 알려진 고정 채널, 채널 응답 0 없음")
    print("CP는 유효 심벌 앞에 끝부분을 복사한다. 8/(8+2)=80%가 유효 샘플이다.")
