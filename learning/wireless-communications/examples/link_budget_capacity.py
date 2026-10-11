"""자유공간 링크와 AWGN 용량의 작은 계산 모형.

안테나 이득, 손실, 290 K 근처의 열잡음 밀도와 noise figure를 가정한다.
실제 기지국·단말의 측정값이나 실제 사용자 속도가 아니다.
"""

import math


def calculate():
    speed_of_light_mps = 3e8  # 이 모형의 근삿값
    frequency_hz = 3.5e9
    distance_m = 1000.0
    bandwidth_hz = 20e6
    tx_dbm = 23.0
    tx_gain_dbi = 2.0
    rx_gain_dbi = 0.0
    extra_loss_db = 2.0
    noise_figure_db = 7.0
    thermal_density_dbm_hz = -174.0  # 약 290 K
    wavelength_m = speed_of_light_mps / frequency_hz
    path_loss_db = 20 * math.log10(4 * math.pi * distance_m / wavelength_m)
    received_dbm = tx_dbm + tx_gain_dbi + rx_gain_dbi - path_loss_db - extra_loss_db
    noise_dbm = thermal_density_dbm_hz + 10 * math.log10(bandwidth_hz) + noise_figure_db
    snr_db = received_dbm - noise_dbm
    snr_linear = 10 ** (snr_db / 10)
    capacity_bps = bandwidth_hz * math.log2(1 + snr_linear)
    return wavelength_m, path_loss_db, received_dbm, noise_dbm, snr_db, capacity_bps


if __name__ == "__main__":
    wavelength, loss, received, noise, snr, capacity = calculate()
    print("가정: 자유공간·원거리·간섭 없음·290 K 근처의 잡음·고정 이득")
    print(f"파장: {wavelength:.5f} m")
    print(f"자유공간 경로 손실: {loss:.2f} dB")
    print(f"수신 전력: {received:.2f} dBm")
    print(f"잡음 전력: {noise:.2f} dBm")
    print(f"SNR: {snr:.2f} dB")
    print(f"이상적 AWGN 용량 상한: {capacity / 1e6:.2f} Mbit/s")
    print("실제 속도에는 fading·간섭·오버헤드·MCS·자원 배정 등이 추가된다.")
