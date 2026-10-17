import numpy as np
from collections import deque
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared.constants import SAMPLING_RATE_HZ, FFT_WINDOW_SIZE, FFT_HOP_SIZE
from niya.filter_coeffs import get_butterworth_coefficients

class DSPPipeline:
    def __init__(self):
        self.b, self.a = get_butterworth_coefficients()
        
        # State buffers for Difference Equation (Order 4)
        self.x_accel = deque([0.0]*5, maxlen=5)
        self.y_accel = deque([0.0]*5, maxlen=5)
        self.x_gyro = deque([0.0]*5, maxlen=5)
        self.y_gyro = deque([0.0]*5, maxlen=5)

        # 256-sample sliding window buffers
        self.clean_accel_window = []
        self.clean_gyro_window = []

    def compute_magnitudes(self, ax, ay, az, roll, pitch, yaw):
        accel_mag = np.sqrt(ax**2 + ay**2 + az**2)
        gyro_mag = np.sqrt(roll**2 + pitch**2 + yaw**2)
        return float(accel_mag), float(gyro_mag)

    def apply_iir_filter(self, x_val, x_hist, y_hist):
        x_hist.appendleft(x_val)
        y_val = self.b[0] * x_hist[0]
        for k in range(1, 5):
            y_val += self.b[k] * x_hist[k] - self.a[k] * y_hist[k-1]
        y_hist.appendleft(y_val)
        return y_val

    def process_sample(self, ax, ay, az, roll, pitch, yaw):
        acc_mag, gyr_mag = self.compute_magnitudes(ax, ay, az, roll, pitch, yaw)
        clean_acc = self.apply_iir_filter(acc_mag, self.x_accel, self.y_accel)
        clean_gyr = self.apply_iir_filter(gyr_mag, self.x_gyro, self.y_gyro)

        self.clean_accel_window.append(clean_acc)
        self.clean_gyro_window.append(clean_gyr)

        # Check if 256-sample window is full
        if len(self.clean_accel_window) == FFT_WINDOW_SIZE:
            accel_frame = np.array(self.clean_accel_window)
            gyro_frame = np.array(self.clean_gyro_window)

            # 50% slide: advance by discarding the oldest 128 samples
            self.clean_accel_window = self.clean_accel_window[FFT_HOP_SIZE:]
            self.clean_gyro_window = self.clean_gyro_window[FFT_HOP_SIZE:]

            return accel_frame, gyro_frame
        return None, None

    def compute_fft(self, window_data):
        # Hanning window to prevent leakage
        hanning = np.hanning(len(window_data))
        fft_vals = np.fft.rfft(window_data * hanning)
        power_spectrum = (np.abs(fft_vals) ** 2) / len(window_data)
        freqs = np.fft.rfftfreq(len(window_data), 1.0 / SAMPLING_RATE_HZ)
        return freqs, power_spectrum
