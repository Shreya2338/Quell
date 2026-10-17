import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared.constants import TREMOR_FREQ_MIN_HZ, TREMOR_FREQ_MAX_HZ

class TremorClassifier:
    def __init__(self, gyro_threshold=8.0, action_limit=18.0):
        self.gyro_thresh = gyro_threshold
        self.action_limit = action_limit

    def evaluate_motion(self, freqs, accel_power, gyro_power, raw_accel_peak):
        # Tremor band mask (4.0 Hz to 6.0 Hz)
        tremor_mask = (freqs >= TREMOR_FREQ_MIN_HZ) & (freqs <= TREMOR_FREQ_MAX_HZ)
        
        peak_idx = np.argmax(gyro_power)
        dominant_freq = freqs[peak_idx]
        peak_gyro_pwr = gyro_power[peak_idx]
        peak_accel_pwr = np.max(accel_power)

        tremor_detected = False
        dyskinesia_detected = False

        # 1. Tremor check: Dominant freq in 4-6 Hz, high gyro power, low linear movement
        if (TREMOR_FREQ_MIN_HZ <= dominant_freq <= TREMOR_FREQ_MAX_HZ) and \
           (peak_gyro_pwr > self.gyro_thresh) and (peak_accel_pwr < self.action_limit):
            tremor_detected = True

        # 2. Dyskinesia check: High non-periodic linear acceleration outside 4-6 Hz
        elif (dominant_freq < TREMOR_FREQ_MIN_HZ or dominant_freq > TREMOR_FREQ_MAX_HZ) and \
             (peak_accel_pwr >= self.action_limit):
            dyskinesia_detected = True

        # 3. MDS-UPDRS severity estimation
        # Double integration: A ≈ a_peak / (2*pi*f)^2
        # Convert g (9.81 m/s^2) to cm: * 981.0
        score = 0
        displacement_cm = 0.0
        if tremor_detected and dominant_freq > 0:
            a_peak_cms2 = raw_accel_peak * 981.0
            omega = 2.0 * np.pi * dominant_freq
            displacement_cm = a_peak_cms2 / (omega ** 2)

            if displacement_cm <= 1.0:
                score = 1
            elif displacement_cm < 3.0:
                score = 2
            elif displacement_cm <= 10.0:
                score = 3
            else:
                score = 4

        return {
            "dominant_frequency_hz": round(float(dominant_freq), 2),
            "tremor_intensity_score": score,
            "displacement_cm": round(float(displacement_cm), 2),
            "tremor_detected": tremor_detected,
            "dyskinesia_detected": dyskinesia_detected
        }
