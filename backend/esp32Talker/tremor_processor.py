"""
Processor: DSP pipeline, tremor classifier, episode tracking and DB persistence.

Runs in its own process (see server_manager.py):
    consumes sensor_q, pushes vibrate commands to command_q, and records
    completed tremor episodes (Supabase via minna.db, local log fallback).
"""

import datetime
import logging
import queue
import time

import numpy as np

log = logging.getLogger("processor")

# Therapeutic burst sent to the ESP32. The firmware treats "intensity" as a
# PERCENT (0-100) and clamps anything higher, so 100 = full drive.
BURST_LENGTH_MS = 500
BURST_INTENSITY_PCT = 100


# ============================================================================
#  DSP PIPELINE & CLASSIFIER
# ============================================================================
class DSPPipeline:
    """
    4th-Order Butterworth Bandpass Filter (3.5 - 7.5 Hz) and sliding window buffer.
    """
    def __init__(self, sample_rate_hz: float = 100.0, window_size: int = 256, hop_size: int = 128):
        self.fs = sample_rate_hz
        self.window_size = window_size
        self.hop_size = hop_size

        # Precomputed Direct Form II Butterworth SOS/IIR Coefficients (fs=100Hz, [3.5, 7.5] Hz)
        self.b = np.array([0.01329373, 0.0, -0.02658746, 0.0, 0.01329373])
        self.a = np.array([1.0, -3.42417734, 4.47548777, -2.63292415, 0.58552176])

        # Filter state delay lines
        self.x_accel = [0.0] * 5
        self.y_accel = [0.0] * 5
        self.x_gyro = [0.0] * 5
        self.y_gyro = [0.0] * 5

        # Sliding buffers
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
    """
    Evaluates resting tremor (4-6 Hz band, MDS-UPDRS scoring) vs voluntary motion.
    """
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
    """
    Persists episode data to Supabase if configured, or falls back to a local log line.
    """
    duration = round(end_time - start_time, 2)
    start_dt = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc)
    end_dt = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc)
    record = {
        "tremor_start": start_dt.isoformat(),
        "tremor_end": end_dt.isoformat(),
        "tremor_intensity": score,
        "duration_seconds": duration,
        "peak_displacement_cm": disp_cm,
        "dominant_frequency_hz": freq,
    }

    try:
        from minna import db
        res = db.insert_tremor_event(
            tremor_start=start_dt,
            tremor_end=end_dt,
            tremor_intensity=score,
            peak_displacement_cm=disp_cm,
            dominant_frequency_hz=freq,
            user_id=None,
        )
        # insert_tremor_event returns the record itself when Supabase isn't
        # configured, so only call it a sync if the client actually exists.
        if res and db.supabase is not None:
            log.info("[DB] Synced tremor episode to Supabase: %s", res)
            return
    except Exception as e:
        log.warning("[DB] Supabase unavailable (%s), using local log", e)

    log.info("[LOCAL DB] Tremor episode recorded (Duration: %.2fs, Score: %d): %s",
             duration, score, record)


# ============================================================================
#  PROCESSOR PROCESS TARGET
# ============================================================================
def _send_burst(command_q):
    try:
        command_q.put_nowait({"type": "vibrate",
                              "length": BURST_LENGTH_MS,
                              "intensity": BURST_INTENSITY_PCT})
    except queue.Full:
        log.warning("command_q full, skipping vibration burst")


def run_processor(sensor_q, command_q, stop_event):
    """
    Consumes sensor_q, runs signal processing, classifies tremor,
    triggers vibration commands via command_q, and records completed episodes.
    """
    logging.basicConfig(level=logging.INFO,
                        format="[%(asctime)s] [%(name)s] %(message)s")
    log.info("Processor pipeline started.")
    pipeline = DSPPipeline()
    classifier = TremorClassifier()

    # Episode tracking state machine
    in_episode = False
    episode_start_t = 0.0
    episode_max_score = 0
    episode_max_disp = 0.0
    episode_dominant_freq = 0.0
    last_t = time.time()
    consecutive_non_tremors = 0
    CESSATION_DEBOUNCE_FRAMES = 2  # consecutive quiet windows needed to close an episode

    while not stop_event.is_set():
        try:
            item = sensor_q.get(timeout=0.2)
        except queue.Empty:
            continue

        accel = item.get("accelerometer", [0.0, 0.0, 1.0])
        gyro = item.get("gyroscope", [0.0, 0.0, 0.0])
        t_sample = item.get("t", time.time())
        last_t = t_sample

        # Process sample through filter & sliding ring buffer
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

        freq = metrics["dominant_frequency_hz"]
        tremor_detected = metrics["tremor_detected"]
        score = metrics["tremor_intensity_score"]
        disp_cm = metrics["peak_displacement_cm"]

        log.info("Tremor: %s | Freq: %.2f Hz | Score: %d | Disp: %.2f cm",
                 tremor_detected, freq, score, disp_cm)

        # State Machine: Open / Maintain Episode
        if tremor_detected:
            consecutive_non_tremors = 0
            if not in_episode:
                in_episode = True
                episode_start_t = t_sample
                episode_max_score = score
                episode_max_disp = disp_cm
                episode_dominant_freq = freq
                log.info("--> [STATE] Tremor episode started.")
            else:
                episode_max_score = max(episode_max_score, score)
                episode_max_disp = max(episode_max_disp, disp_cm)
            _send_burst(command_q)  # start / re-trigger therapeutic burst

        # State Machine: Close Episode on sustained quiet
        elif in_episode:
            consecutive_non_tremors += 1
            if consecutive_non_tremors >= CESSATION_DEBOUNCE_FRAMES:
                in_episode = False
                log.info("--> [STATE] Tremor episode ended. Syncing records...")
                save_tremor_episode(episode_start_t, t_sample,
                                    episode_max_score, episode_max_disp,
                                    episode_dominant_freq)

    # Shutdown: don't lose an episode that is still open
    if in_episode:
        save_tremor_episode(episode_start_t, last_t,
                            episode_max_score, episode_max_disp,
                            episode_dominant_freq)
    log.info("Processor stopped.")