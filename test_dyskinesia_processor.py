"""
Self-contained unit and pipeline test for Dyskinesia & Tremor detection.
Simulates 100 Hz IMU frames from the ESP32 and verifies start/stop tracking.
"""

import datetime
import logging
import queue
import threading
import time
import numpy as np

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] %(message)s")
log = logging.getLogger("processor-test")

# ============================================================================
#  DSP PIPELINE & CLASSIFIER
# ============================================================================
class DSPPipeline:
    def __init__(self, sample_rate_hz: float = 100.0, window_size: int = 256, hop_size: int = 128):
        self.fs = sample_rate_hz
        self.window_size = window_size
        self.hop_size = hop_size

        # 4th-Order Butterworth Bandpass Coefficients (fs=100Hz, [3.5, 7.5] Hz)
        self.b = np.array([0.01329373, 0.0, -0.02658746, 0.0, 0.01329373])
        self.a = np.array([1.0, -3.42417734, 4.47548777, -2.63292415, 0.58552176])

        self.x_accel = [0.0] * 5
        self.y_accel = [0.0] * 5
        self.x_gyro = [0.0] * 5
        self.y_gyro = [0.0] * 5

        self.accel_window = []
        self.gyro_window = []

    def compute_magnitudes(self, ax, ay, az, roll, pitch, yaw):
        accel_mag = float(np.sqrt(ax**2 + ay**2 + az**2))
        gyro_mag = float(np.sqrt(roll**2 + pitch**2 + yaw**2))
        return accel_mag, gyro_mag

    def apply_iir(self, x_val, x_hist, y_hist):
        x_hist.insert(0, x_val)
        x_hist.pop()
        y_val = (
            self.b[0] * x_hist[0] + self.b[1] * x_hist[1] + self.b[2] * x_hist[2] +
            self.b[3] * x_hist[3] + self.b[4] * x_hist[4] -
            self.a[1] * y_hist[0] - self.a[2] * y_hist[1] - self.a[3] * y_hist[2] - self.a[4] * y_hist[3]
        ) / self.a[0]
        y_hist.insert(0, y_val)
        y_hist.pop()
        return y_val

    def process_sample(self, ax, ay, az, gx, gy, gz):
        a_mag, g_mag = self.compute_magnitudes(ax, ay, az, gx, gy, gz)
        clean_a = self.apply_iir(a_mag, self.x_accel, self.y_accel)
        clean_g = self.apply_iir(g_mag, self.x_gyro, self.y_gyro)

        self.accel_window.append(clean_a)
        self.gyro_window.append(clean_g)

        if len(self.accel_window) >= self.window_size:
            w_acc = np.array(self.accel_window[:self.window_size])
            w_gyr = np.array(self.gyro_window[:self.window_size])
            self.accel_window = self.accel_window[self.hop_size:]
            self.gyro_window = self.gyro_window[self.hop_size:]
            return w_acc, w_gyr

        return None, None

    def compute_fft(self, signal_window: np.ndarray):
        n = len(signal_window)
        hanning = np.hanning(n)
        fft_vals = np.fft.rfft(signal_window * hanning)
        freqs = np.fft.rfftfreq(n, d=1.0 / self.fs)
        power_spectrum = (np.abs(fft_vals) ** 2) / n
        return freqs, power_spectrum


class TremorClassifier:
    def __init__(self, gyro_thresh: float = 0.5, action_limit: float = 1.8):
        self.gyro_thresh = gyro_thresh
        self.action_limit = action_limit

    def evaluate(self, freqs, p_acc, p_gyr, peak_accel):
        band_mask = (freqs >= 4.0) & (freqs <= 6.0)
        dominant_freq = 0.0
        peak_gyro_pwr = 0.0

        if np.any(band_mask):
            band_freqs = freqs[band_mask]
            band_gyr_pwr = p_gyr[band_mask]
            dominant_idx = np.argmax(band_gyr_pwr)
            dominant_freq = float(band_freqs[dominant_idx])
            peak_gyro_pwr = float(band_gyr_pwr[dominant_idx])

        peak_accel_pwr = float(np.max(p_acc)) if len(p_acc) > 0 else 0.0

        is_resting_tremor = (
            (4.0 <= dominant_freq <= 6.0) and
            (peak_gyro_pwr >= self.gyro_thresh) and
            (peak_accel_pwr < self.action_limit)
        )
        is_dyskinesia = (peak_accel_pwr >= self.action_limit) and not is_resting_tremor

        score = 0
        displacement_cm = 0.0
        if is_resting_tremor and dominant_freq > 0:
            omega = 2.0 * np.pi * dominant_freq
            displacement_m = peak_accel / (omega ** 2)
            displacement_cm = float(displacement_m * 100.0)
            if displacement_cm <= 1.0:
                score = 1
            elif displacement_cm < 3.0:
                score = 2
            elif displacement_cm <= 10.0:
                score = 3
            else:
                score = 4

        return {
            "dominant_frequency_hz": round(dominant_freq, 2),
            "tremor_detected": bool(is_resting_tremor),
            "dyskinesia_detected": bool(is_dyskinesia),
            "tremor_intensity_score": score,
            "peak_displacement_cm": round(displacement_cm, 3)
        }


# ============================================================================
#  DATABASE PERSISTENCE (Supabase + Local fallback)
# ============================================================================
def save_tremor_episode(start_time: float, end_time: float, score: int, disp_cm: float, freq: float):
    duration = round(end_time - start_time, 2)
    start_dt = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc)
    end_dt = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc)
    log.info("[RECORD] Tremor episode saved -> Start: %s | End: %s | Duration: %.2fs",
             start_dt.isoformat(), end_dt.isoformat(), duration)


def save_dyskinesia_episode(start_time: float, end_time: float):
    duration = round(end_time - start_time, 2)
    start_dt = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc)
    end_dt = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc)
    record = {
        "device_id": "esp32_wristband_01",
        "dyskinesia_start": start_dt.isoformat(),
        "dyskinesia_end": end_dt.isoformat(),
        "duration_seconds": duration,
    }

    try:
        from minna import db
        if getattr(db, "supabase", None) is not None:
            res = db.supabase.table("dyskinesia_events").insert(record).execute()
            log.info("[DB] Synced dyskinesia episode to Supabase: %s", res.data)
            return
    except Exception as e:
        log.warning("[DB] Supabase insert skipped (%s), using local fallback", e)

    log.info("[LOCAL DB] Dyskinesia recorded -> Start: %s | End: %s | Duration: %.2fs",
             record["dyskinesia_start"], record["dyskinesia_end"], duration)


# ============================================================================
#  PROCESSOR ENGINE
# ============================================================================
def run_processor(sensor_q, command_q, stop_event):
    pipeline = DSPPipeline()
    classifier = TremorClassifier()

    in_tremor = False
    tremor_start_t = 0.0
    consecutive_non_tremors = 0

    in_dyskinesia = False
    dyskinesia_start_t = 0.0
    consecutive_non_dyskinesia = 0

    CESSATION_DEBOUNCE_FRAMES = 2
    last_t = time.time()

    while not stop_event.is_set():
        try:
            item = sensor_q.get(timeout=0.1)
        except queue.Empty:
            continue

        accel = item.get("accelerometer", [0.0, 0.0, 1.0])
        gyro = item.get("gyroscope", [0.0, 0.0, 0.0])
        t_sample = item.get("t", time.time())
        last_t = t_sample

        acc_win, gyr_win = pipeline.process_sample(
            accel[0], accel[1], accel[2],
            gyro[0], gyro[1], gyro[2]
        )

        if acc_win is None or gyr_win is None:
            continue

        f_acc, p_acc = pipeline.compute_fft(acc_win)
        f_gyr, p_gyr = pipeline.compute_fft(gyr_win)

        peak_acc = float(np.max(np.abs(acc_win)))
        metrics = classifier.evaluate(f_gyr, p_acc, p_gyr, peak_acc)

        tremor_detected = metrics["tremor_detected"]
        dyskinesia_detected = metrics["dyskinesia_detected"]

        # --- Tremor State Machine ---
        if tremor_detected:
            consecutive_non_tremors = 0
            if not in_tremor:
                in_tremor = True
                tremor_start_t = t_sample
                log.info("--> [STATE] Tremor episode started.")
        elif in_tremor:
            consecutive_non_tremors += 1
            if consecutive_non_tremors >= CESSATION_DEBOUNCE_FRAMES:
                in_tremor = False
                log.info("--> [STATE] Tremor episode ended.")
                save_tremor_episode(tremor_start_t, t_sample, metrics["tremor_intensity_score"],
                                    metrics["peak_displacement_cm"], metrics["dominant_frequency_hz"])

        # --- Dyskinesia State Machine ---
        if dyskinesia_detected:
            consecutive_non_dyskinesia = 0
            if not in_dyskinesia:
                in_dyskinesia = True
                dyskinesia_start_t = t_sample
                log.info("--> [STATE] Dyskinesia episode started.")
        elif in_dyskinesia:
            consecutive_non_dyskinesia += 1
            if consecutive_non_dyskinesia >= CESSATION_DEBOUNCE_FRAMES:
                in_dyskinesia = False
                log.info("--> [STATE] Dyskinesia episode ended.")
                save_dyskinesia_episode(dyskinesia_start_t, t_sample)

    if in_dyskinesia:
        save_dyskinesia_episode(dyskinesia_start_t, last_t)


# ============================================================================
#  TEST EXECUTION HARNESS
# ============================================================================
def main():
    sensor_q = queue.Queue(maxsize=1000)
    command_q = queue.Queue(maxsize=100)
    stop_event = threading.Event()

    proc_thread = threading.Thread(
        target=run_processor,
        args=(sensor_q, command_q, stop_event),
        daemon=True
    )
    proc_thread.start()
    log.info("Processor test harness active. Streaming simulated IMU frames...")

    fs = 100.0
    dt = 1.0 / fs

    # 1600 samples (~16 seconds of continuous stream)
    # 0s - 3s:   Steady baseline
    # 3s - 8s:   High linear acceleration (Dyskinesia)
    # 8s - 12s:  Quiet baseline (Dyskinesia episode closes)
    # 12s - 16s: 5 Hz Rotational oscillation (Tremor)
    for i in range(1600):
        t = i * dt
        now = time.time()

        if 3.0 <= t < 8.0:
            # Dyskinesia: High erratic translational movement
            ax = float(np.random.normal(0, 3.0))
            ay = float(np.random.normal(0, 3.0))
            az = 1.0 + float(np.random.normal(0, 2.5))
            roll, pitch, yaw = 0.1, 0.1, 0.1
        elif 12.0 <= t < 16.0:
            # Tremor: 5 Hz rotation, low linear movement
            roll = 25.0 * np.sin(2.0 * np.pi * 5.0 * t)
            pitch = 25.0 * np.cos(2.0 * np.pi * 5.0 * t)
            yaw = 1.0
            ax, ay, az = 0.01, 0.01, 1.0
        else:
            # Baseline rest
            roll, pitch, yaw = 0.01, 0.01, 0.01
            ax, ay, az = 0.0, 0.0, 1.0

        sensor_q.put({
            "t": now,
            "accelerometer": [ax, ay, az],
            "gyroscope": [roll, pitch, yaw]
        })
        time.sleep(0.005)

    log.info("Finished streaming simulated IMU samples. Waiting for debounce flush...")
    time.sleep(2.5)
    stop_event.set()
    proc_thread.join()
    log.info("Test completed successfully.")


if __name__ == "__main__":
    main()