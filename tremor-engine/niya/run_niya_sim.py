import datetime
import os
import sys
import numpy as np

# Ensure root workspace paths can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared.contracts import TelemetryPayload
from niya.dsp_pipeline import DSPPipeline
from niya.tremor_classifier import TremorClassifier
from niya.tass_actuator import TassActuator


import numpy as np

def generate_mock_imu_sample(sample_idx: int):
    """
    Simulates:
      - 0s to 12s:  Calm baseline resting (Noise only -> Tremor: False)
      - 12s to 28s: Strong 5.0 Hz Parkinsonian resting tremor -> Tremor: True
      - 28s to 40s: Return to baseline (Triggers Tremor Ended -> writes to Supabase)
    """
    t = sample_idx / 1000.0  # 1 kHz sample clock
    
    # 12s - 28s: Inject strong 5.0 Hz resting tremor on gyro axes
    if 12.0 <= t < 28.0:
        freq = 5.0
        # High rotational oscillation (roll/pitch), low noise
        roll = 35.0 * np.sin(2 * np.pi * freq * t) + np.random.normal(0, 0.1)
        pitch = 25.0 * np.cos(2 * np.pi * freq * t) + np.random.normal(0, 0.1)
        yaw = 1.0 + np.random.normal(0, 0.05)
        # Low linear acceleration (stationary resting hand)
        ax = 0.01 * np.sin(2 * np.pi * freq * t)
        ay = 0.01 * np.cos(2 * np.pi * freq * t)
        az = 1.0 # 1g baseline gravity
    else:
        # Calm baseline
        roll = float(np.random.normal(0, 0.1))
        pitch = float(np.random.normal(0, 0.1))
        yaw = 1.0 + float(np.random.normal(0, 0.05))
        ax = float(np.random.normal(0, 0.005))
        ay = float(np.random.normal(0, 0.005))
        az = 1.0

    return ax, ay, az, roll, pitch, yaw

def run_testing_harness(total_seconds: float = 120.0, sample_rate_hz: int = 100):
    """
    Runs continuous multi-state testing harness:
    100 Hz generation -> 256-sample window -> 128-sample sliding step (~1.28s)
    """
    pipeline = DSPPipeline()
    classifier = TremorClassifier()
    actuator = TassActuator()
    device_id = "esp32_wristband_01"

    total_samples = int(total_seconds * sample_rate_hz)
    base_time = datetime.datetime.now(datetime.timezone.utc)

    tremor_frames = 0
    non_tremor_frames = 0
    total_payloads = 0

    print(f"=== Starting DSP Test Harness ===")
    print(f"Total Duration: {total_seconds}s ({total_samples} raw IMU samples at {sample_rate_hz} Hz)")
    print(f"Sliding Window: 256 samples with 128 hop (~1.28s cadence)\n")

    for i in range(total_samples):
        t = i / float(sample_rate_hz)
        ax, ay, az, roll, pitch, yaw = generate_motion_sample(t)

        accel_win, gyro_win = pipeline.process_sample(ax, ay, az, roll, pitch, yaw)

        # Triggers whenever 128 new samples fill the 256 circular buffer
        if accel_win is not None:
            f_acc, p_acc = pipeline.compute_fft(accel_win)
            f_gyr, p_gyr = pipeline.compute_fft(gyro_win)

            metrics = classifier.evaluate_motion(
                f_gyr, p_acc, p_gyr,
                raw_accel_peak=float(np.max(np.abs(accel_win)))
            )
            vibe_state = actuator.update_state(metrics["tremor_detected"], delta_time_sec=1.28)

            simulated_timestamp = base_time + datetime.timedelta(seconds=t)

            payload = TelemetryPayload(
                device_id=device_id,
                timestamp=simulated_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                event_type="telemetry",
                dominant_frequency_hz=metrics["dominant_frequency_hz"],
                tremor_intensity_score=metrics["tremor_intensity_score"],
                tremor_detected=metrics["tremor_detected"],
                dyskinesia_detected=metrics["dyskinesia_detected"],
                vibration_active=vibe_state
            )

            total_payloads += 1
            if metrics["tremor_detected"]:
                tremor_frames += 1
            else:
                non_tremor_frames += 1

            status = "TREMOR" if metrics["tremor_detected"] else "NORMAL"
            print(f"[{t:05.1f}s | {status:6s}] Freq: {metrics['dominant_frequency_hz']:04.2f} Hz | "
                  f"Score: {metrics['tremor_intensity_score']} | "
                  f"Actuator: {vibe_state} | "
                  f"Payload: {payload.model_dump_json()}")

    print("\n=== Test Harness Summary ===")
    print(f"Total Sliding Payloads Emitted: {total_payloads}")
    print(f"Tremor Frames Detected:        {tremor_frames}")
    print(f"Non-Tremor Frames Detected:    {non_tremor_frames}")
    if total_payloads > 0:
        print(f"Tremor Ratio:                  {(tremor_frames / total_payloads) * 100:.1f}%")


if __name__ == "__main__":
    # Runs 120 seconds of simulation by default (yielding ~91 evaluated frames)
    run_testing_harness(total_seconds=120.0)