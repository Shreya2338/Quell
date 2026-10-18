"""
Processor: DSP pipeline, tremor and dyskinesia classifiers, episode tracking,
Peter Tass vibration commands, Supabase persistence, and email notification alerts.

Consumes sensor_q (100 Hz IMU frames from the ESP32), pushes vibrate commands to
command_q, persists completed episodes to database, and triggers email notifications.
"""

import datetime
import logging
import queue
import time
from mailer import sendemail 
from typing import Optional, Dict

import numpy as np

# Note: send_email is imported from your external email service module
# e.g.: from email_service import send_email

log = logging.getLogger("processor")

# 250 Hz Peter Tass Coordinated Reset carrier, 500 ms burst duration
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

    def compute_magnitudes(self, ax: float, ay: float, az: float, roll: float, pitch: float, yaw: float):
        accel_mag = float(np.sqrt(ax**2 + ay**2 + az**2))
        gyro_mag = float(np.sqrt(roll**2 + pitch**2 + yaw**2))
        return accel_mag, gyro_mag

    def apply_iir(self, x_val: float, x_hist: list, y_hist: list) -> float:
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

    def process_sample(self, ax: float, ay: float, az: float, gx: float, gy: float, gz: float):
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
    Evaluates resting tremor (4-6 Hz band, MDS-UPDRS scoring) vs voluntary motion/dyskinesia.
    """
    def __init__(self, gyro_thresh: float = 0.5, action_limit: float = 1.8):
        self.gyro_thresh = gyro_thresh
        self.action_limit = action_limit

    def evaluate(self, freqs: np.ndarray, p_acc: np.ndarray, p_gyr: np.ndarray, peak_accel: float) -> dict:
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

        # Resting tremor: 4-6 Hz, elevated rotation, low linear acceleration
        is_resting_tremor = (
            (4.0 <= dominant_freq <= 6.0) and
            (peak_gyro_pwr >= self.gyro_thresh) and
            (peak_accel_pwr < self.action_limit)
        )

        # Dyskinesia: High linear acceleration outside the resting tremor harmonic
        is_dyskinesia = (peak_accel_pwr >= self.action_limit) and not is_resting_tremor

        # MDS-UPDRS severity estimation from double-integrated acceleration displacement
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
#  DATABASE PERSISTENCE & ALERTS
# ============================================================================
def save_tremor_episode(start_time: float, end_time: float, score: int, disp_cm: float, freq: float):
    """
    Persists tremor episode data to Supabase (or local fallback) and triggers email alert.
    """
    duration = round(end_time - start_time, 2)
    start_dt = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc)
    end_dt = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc)

    # 1. Trigger Email Alert with Tremor Level, Start/End Timestamps, and Length
    try:
        send_email(
            to_email="caregiver@quell.local",
            title="Alert: Tremor Episode Detected",
            body=(
                f"Tremor Level (MDS-UPDRS): {score}\n"
                f"Start Time: {start_dt.isoformat()}\n"
                f"End Time: {end_dt.isoformat()}\n"
                f"Length: {duration} seconds\n"
                f"Dominant Frequency: {freq} Hz\n"
                f"Peak Displacement: {disp_cm} cm"
            )
        )
    except NameError:
        log.warning("[EMAIL] send_email function not yet imported or defined.")
    except Exception as e:
        log.warning("[EMAIL] Failed to send tremor notification email: %s", e)

    # 2. Database Sync
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
        if res and getattr(db, "supabase", None) is not None:
            log.info("[DB] Synced tremor episode to Supabase: %s", res)
            return
    except Exception as e:
        log.warning("[DB] Supabase unavailable (%s), using local log", e)

    log.info("[LOCAL DB] Tremor episode recorded (Duration: %.2fs, Score: %d): %s",
             duration, score, record)


def save_dyskinesia_episode(start_time: float, end_time: float):
    """
    Persists dyskinesia episode start/stop timestamps to DB and triggers email alert.
    """
    duration = round(end_time - start_time, 2)
    start_dt = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc)
    end_dt = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc)

    # 1. Trigger Email Alert with strictly start and end timestamps
    try:
        send_email(
            to_email="caregiver@quell.local",
            title="Alert: Dyskinesia Episode Detected",
            body=(
                f"Dyskinesia episode detected.\n"
                f"Start Time: {start_dt.isoformat()}\n"
                f"End Time: {end_dt.isoformat()}\n"
                f"Duration: {duration} seconds"
            )
        )
    except NameError:
        log.warning("[EMAIL] send_email function not yet imported or defined.")
    except Exception as e:
        log.warning("[EMAIL] Failed to send dyskinesia notification email: %s", e)

    # 2. Database Sync
    record = {
        "device_id": "esp32_wristband_01",
        "dyskinesia_start": start_dt.isoformat(),
        "dyskinesia_end": end_dt.isoformat(),
        "duration_seconds": duration,
    }

    try:
        from minna import db
        if hasattr(db, "insert_dyskinesia_event"):
            res = db.insert_dyskinesia_event(dyskinesia_start=start_dt, dyskinesia_end=end_dt)
            if res and getattr(db, "supabase", None) is not None:
                log.info("[DB] Synced dyskinesia episode to Supabase: %s", res)
                return
        elif getattr(db, "supabase", None) is not None:
            res = db.supabase.table("dyskinesia_events").insert(record).execute()
            log.info("[DB] Synced dyskinesia episode to Supabase: %s", res.data)
            return
    except Exception as e:
        log.warning("[DB] Supabase dyskinesia insert failed (%s), using local log", e)

    log.info("[LOCAL DB] Dyskinesia episode recorded (Start: %s, End: %s, Duration: %.2fs)",
             record["dyskinesia_start"], record["dyskinesia_end"], duration)


# ============================================================================
#  PROCESSOR PROCESS TARGET
# ============================================================================
def _send_burst(command_q):
    try:
        command_q.put_nowait({
            "type": "vibrate",
            "length": BURST_LENGTH_MS,
            "intensity": BURST_INTENSITY_PCT
        })
    except queue.Full:
        log.warning("command_q full, skipping vibration burst")


def run_processor(sensor_q, command_q, stop_event):
    """
    Consumes sensor_q (100 Hz IMU samples from ESP32), runs DSP pipeline,
    tracks tremor and dyskinesia episodes, triggers vibration bursts, and persists records.
    """
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] %(message)s")
    log.info("Processor pipeline started.")
    pipeline = DSPPipeline()
    classifier = TremorClassifier()

    # --- Tremor Episode State Machine ---
    in_tremor = False
    tremor_start_t = 0.0
    tremor_max_score = 0
    tremor_max_disp = 0.0
    tremor_dominant_freq = 0.0
    consecutive_non_tremors = 0

    # --- Dyskinesia Episode State Machine ---
    in_dyskinesia = False
    dyskinesia_start_t = 0.0
    consecutive_non_dyskinesia = 0

    # Number of quiet frames required before considering an episode concluded
    CESSATION_DEBOUNCE_FRAMES = 2
    last_t = time.time()

    while not stop_event.is_set():
        try:
            item = sensor_q.get(timeout=0.2)
        except queue.Empty:
            continue

        accel = item.get("accelerometer", [0.0, 0.0, 1.0])
        gyro = item.get("gyroscope", [0.0, 0.0, 0.0])
        t_sample = item.get("t", time.time())
        last_t = t_sample

        # Ingest into 4th-order Butterworth filter & sliding buffer
        acc_win, gyr_win = pipeline.process_sample(
            accel[0], accel[1], accel[2],
            gyro[0], gyro[1], gyro[2]
        )

        if acc_win is None or gyr_win is None:
            continue

        # 256-sample window full -> compute FFT power spectra
        f_acc, p_acc = pipeline.compute_fft(acc_win)
        f_gyr, p_gyr = pipeline.compute_fft(gyr_win)

        peak_acc = float(np.max(np.abs(acc_win)))
        metrics = classifier.evaluate(f_gyr, p_acc, p_gyr, peak_acc)

        freq = metrics["dominant_frequency_hz"]
        tremor_detected = metrics["tremor_detected"]
        dyskinesia_detected = metrics["dyskinesia_detected"]
        score = metrics["tremor_intensity_score"]
        disp_cm = metrics["peak_displacement_cm"]

        log.info("Tremor: %s | Dyskinesia: %s | Freq: %.2f Hz | Score: %d | Disp: %.2f cm",
                 tremor_detected, dyskinesia_detected, freq, score, disp_cm)

        # ---------------- Tremor Episode Handling ----------------
        if tremor_detected:
            consecutive_non_tremors = 0
            if not in_tremor:
                in_tremor = True
                tremor_start_t = t_sample
                tremor_max_score = score
                tremor_max_disp = disp_cm
                tremor_dominant_freq = freq
                log.info("--> [STATE] Tremor episode started.")
            else:
                tremor_max_score = max(tremor_max_score, score)
                tremor_max_disp = max(tremor_max_disp, disp_cm)

            _send_burst(command_q)  # Trigger / re-trigger Peter Tass burst

        elif in_tremor:
            consecutive_non_tremors += 1
            if consecutive_non_tremors >= CESSATION_DEBOUNCE_FRAMES:
                in_tremor = False
                log.info("--> [STATE] Tremor episode ended. Persisting and alerting...")
                save_tremor_episode(
                    tremor_start_t, t_sample,
                    tremor_max_score, tremor_max_disp,
                    tremor_dominant_freq
                )

        # -------------- Dyskinesia Episode Handling --------------
        if dyskinesia_detected:
            consecutive_non_dyskinesia = 0
            if not in_dyskinesia:
                in_dyskinesia = True
                dyskinesia_start_t = t_sample
                log.info("--> [STATE] Dyskinesia episode started at %s", dyskinesia_start_t)

        elif in_dyskinesia:
            consecutive_non_dyskinesia += 1
            if consecutive_non_dyskinesia >= CESSATION_DEBOUNCE_FRAMES:
                in_dyskinesia = False
                log.info("--> [STATE] Dyskinesia episode ended. Persisting and alerting...")
                save_dyskinesia_episode(dyskinesia_start_t, t_sample)

    # ------------------ Process Termination Cleanup ------------------
    if in_tremor:
        save_tremor_episode(
            tremor_start_t, last_t,
            tremor_max_score, tremor_max_disp,
            tremor_dominant_freq
        )
    if in_dyskinesia:
        save_dyskinesia_episode(dyskinesia_start_t, last_t)

    log.info("Processor stopped.")