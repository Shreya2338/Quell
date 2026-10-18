import time
import datetime
import numpy as np
import sys
import os

# Ensure modules are discoverable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from niya.dsp_pipeline import DSPPipeline
from niya.tremor_classifier import TremorClassifier
from niya.tass_actuator import TASSActuator as TassActuator
from minna.db import insert_tremor_event, supabase

import numpy as np

import numpy as np

def generate_mock_imu_sample(t_sec: float):
    """
    - 0s to 5s:  Quiet baseline (Tremor: False)
    - 5s to 20s: Clean 5.0 Hz rotational tremor (Tremor: True, Score: 2)
    - 20s+:      Quiet baseline (Tremor: False -> Triggers episode close)
    """
    if 5.0 <= t_sec < 20.0:
        freq = 5.0
        # Adding a DC bias (+30.0) ensures the Euclidean norm does NOT double 5Hz to 10Hz
        roll = 30.0 + 25.0 * np.sin(2.0 * np.pi * freq * t_sec)
        pitch = 30.0 + 25.0 * np.cos(2.0 * np.pi * freq * t_sec)
        yaw = 1.0
        
        # Resting arm: only 1g static gravity on Z, near-zero linear acceleration
        ax = 0.005
        ay = 0.005
        az = 1.0
    else:
        # Stationary baseline rest
        roll = 1.0 + float(np.random.normal(0, 0.02))
        pitch = 1.0 + float(np.random.normal(0, 0.02))
        yaw = 1.0
        ax = 0.001
        ay = 0.001
        az = 1.0

    return ax, ay, az, roll, pitch, yaw

def run_test():
    print(f"Supabase client initialized: {supabase is not None}")
    
    pipeline = DSPPipeline()
    classifier = TremorClassifier()
    actuator = TassActuator()
    
    device_id = "test_esp32_sim"
    is_active = False
    episode_start = None
    below_threshold_count = 0
    end_grace_frames = 2
    intensity_buffer = []
    freq_buffer = []
    disp_buffer = []

    print("Running simulated stream: 1 kHz generation -> 100 Hz downsample...")
    start_wall_time = time.time()
    sample_idx = 0
    episodes_recorded = 0

    # Run for 20 simulated seconds
    while (time.time() - start_wall_time) < 20.0 and episodes_recorded < 30:
        t_sim = sample_idx * 0.001
        sample_idx += 1
        
        # 10:1 downsampling to 100 Hz evaluation
        if sample_idx % 10 != 0:
            continue

        ax, ay, az, roll, pitch, yaw = generate_mock_imu_sample(t_sim)
        accel_win, gyro_win = pipeline.process_sample(ax, ay, az, roll, pitch, yaw)

        if accel_win is not None:
            now = datetime.datetime.now(datetime.timezone.utc)
            f_acc, p_acc = pipeline.compute_fft(accel_win)
            f_gyr, p_gyr = pipeline.compute_fft(gyro_win)

            metrics = classifier.evaluate_motion(
                f_gyr, p_acc, p_gyr,
                raw_accel_peak=float(np.max(np.abs(accel_win)))
            )
            actuator.update_state(metrics["tremor_detected"], delta_time_sec=1.28)

            detected = metrics["tremor_detected"]
            score = metrics.get("tremor_intensity_score", 0.0)
            dom_f = metrics.get("dominant_frequency_hz", 0.0)
            disp = metrics.get("estimated_displacement_cm", 0.0)

            print(f"[Sim Time {t_sim:04.1f}s] Tremor: {detected} | Freq: {dom_f:.2f} Hz | Score: {score}")

            if detected:
                if not is_active:
                    is_active = True
                    episode_start = now
                    below_threshold_count = 0
                    intensity_buffer = [score]
                    freq_buffer = [dom_f]
                    disp_buffer = [disp]
                    print("  --> [STATE] Tremor episode started.")
                else:
                    below_threshold_count = 0
                    intensity_buffer.append(score)
                    freq_buffer.append(dom_f)
                    disp_buffer.append(disp)
            else:
                if is_active:
                    below_threshold_count += 1
                    if below_threshold_count >= end_grace_frames:
                        episode_end = now
                        peak_int = max(intensity_buffer) if intensity_buffer else score
                        avg_f = float(np.mean(freq_buffer)) if freq_buffer else dom_f
                        peak_d = max(disp_buffer) if disp_buffer else disp

                        print(f"  --> [STATE] Tremor episode ended. Syncing to Supabase...")
                        res = insert_tremor_event(
                            tremor_start=episode_start,
                            tremor_end=episode_end,
                            tremor_intensity=peak_int,
                            peak_displacement_cm=peak_d,
                            dominant_frequency_hz=avg_f
                        )
                        print(f"  --> [SUPABASE RESULT]: {res}")
                        episodes_recorded += 1

                        # Reset state
                        is_active = False
                        episode_start = None
                        below_threshold_count = 0
                        intensity_buffer.clear()
                        freq_buffer.clear()
                        disp_buffer.clear()

        # Small sleep to approximate real-time execution
        time.sleep(0.005)

if __name__ == "__main__":
    run_test()