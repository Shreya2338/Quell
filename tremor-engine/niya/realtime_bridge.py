import time
import datetime
import numpy as np
import threading
import queue
import sys
import os

# Ensure modules are discoverable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from niya.dsp_pipeline import DSPPipeline
from niya.tremor_classifier import TremorClassifier
from niya.tass_actuator import TassActuator
from minna.db import insert_tremor_event

class TremorEpisodeTracker:
    def __init__(self, device_id: str = "esp32_wristband_01", end_grace_frames: int = 3):
        self.device_id = device_id
        self.end_grace_frames = end_grace_frames  # Frames below threshold before closing episode (~3.8s)
        self.is_active = False
        self.episode_start_time: Optional[datetime.datetime] = None
        self.below_threshold_count = 0
        self.intensity_buffer = []
        self.freq_buffer = []
        self.disp_buffer = []

    def update(self, tremor_detected: bool, metrics: dict, now: datetime.datetime):
        intensity = metrics.get("tremor_intensity_score", 0.0)
        dominant_freq = metrics.get("dominant_frequency_hz", 0.0)
        disp = metrics.get("estimated_displacement_cm", 0.0)

        if tremor_detected:
            if not self.is_active:
                # Tremor starts
                self.is_active = True
                self.episode_start_time = now
                self.below_threshold_count = 0
                self.intensity_buffer = [intensity]
                self.freq_buffer = [dominant_freq]
                self.disp_buffer = [disp]
                print(f"[{now.strftime('%H:%M:%S.%f')[:-3]}] *** TREMOR STARTED ***")
            else:
                self.below_threshold_count = 0
                self.intensity_buffer.append(intensity)
                self.freq_buffer.append(dominant_freq)
                self.disp_buffer.append(disp)
        else:
            if self.is_active:
                self.below_threshold_count += 1
                if self.below_threshold_count >= self.end_grace_frames:
                    # Tremor finished
                    tremor_end = now
                    peak_intensity = max(self.intensity_buffer) if self.intensity_buffer else intensity
                    avg_freq = np.mean(self.freq_buffer) if self.freq_buffer else dominant_freq
                    peak_disp = max(self.disp_buffer) if self.disp_buffer else disp

                    print(f"[{tremor_end.strftime('%H:%M:%S.%f')[:-3]}] *** TREMOR ENDED *** | Peak: {peak_intensity} | Duration: {(tremor_end - self.episode_start_time).total_seconds()}s")

                    # Push to Supabase
                    insert_tremor_event(
                        device_id=self.device_id,
                        tremor_start=self.episode_start_time,
                        tremor_end=tremor_end,
                        tremor_intensity=peak_intensity,
                        peak_displacement_cm=peak_disp,
                        dominant_frequency_hz=avg_freq
                    )

                    # Reset episode
                    self.is_active = False
                    self.episode_start_time = None
                    self.below_threshold_count = 0
                    self.intensity_buffer.clear()
                    self.freq_buffer.clear()
                    self.disp_buffer.clear()

def run_realtime_engine(get_esp32_sample_func):
    """
    get_esp32_sample_func: Teammate's function.
    Must return a tuple/list: (ax, ay, az, roll, pitch, yaw) or None if waiting.
    Called on a 1 ms tick.
    """
    raw_queue = queue.Queue(maxsize=10000)
    pipeline = DSPPipeline()
    classifier = TremorClassifier()
    actuator = TassActuator()
    tracker = TremorEpisodeTracker()

    def ingestion_worker():
        """Continuously pulls from teammate's ESP32 function and pushes to queue."""
        while True:
            sample = get_esp32_sample_func()
            if sample:
                raw_queue.put(sample)
            else:
                time.sleep(0.0005)

    threading.Thread(target=ingestion_worker, daemon=True).start()

    print("Real-time pipeline started. Downsampling 1kHz -> 100Hz and evaluating...")

    sample_counter = 0
    DOWNSAMPLE_FACTOR = 10  # 1 ms (1000 Hz) downsampled to 10 ms (100 Hz)

    while True:
        try:
            ax, ay, az, roll, pitch, yaw = raw_queue.get(timeout=1.0)
            sample_counter += 1

            if sample_counter % DOWNSAMPLE_FACTOR != 0:
                continue  # Skip intermediate samples to keep effective rate at 100 Hz

            accel_win, gyro_win = pipeline.process_sample(ax, ay, az, roll, pitch, yaw)

            if accel_win is not None:
                now = datetime.datetime.now(datetime.timezone.utc)
                f_acc, p_acc = pipeline.compute_fft(accel_win)
                f_gyr, p_gyr = pipeline.compute_fft(gyro_win)

                metrics = classifier.evaluate_motion(
                    f_gyr, p_acc, p_gyr,
                    raw_accel_peak=float(np.max(np.abs(accel_win)))
                )
                
                vibe_state = actuator.update_state(
                    metrics["tremor_detected"], 
                    delta_time_sec=1.28
                )

                # Track start/end and sync to Supabase
                tracker.update(metrics["tremor_detected"], metrics, now)

        except queue.Empty:
            continue
        except KeyboardInterrupt:
            print("\nShutting down real-time pipeline...")
            break