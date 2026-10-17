import datetime
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared.contracts import TelemetryPayload
from niya.dsp_pipeline import DSPPipeline
from niya.tremor_classifier import TremorClassifier
from niya.tass_actuator import TassActuator

def run_simulation():
    pipeline = DSPPipeline()
    classifier = TremorClassifier()
    actuator = TassActuator()
    device_id = "esp32_wristband_01"

    print("Running Person 1 DSP Simulator (100 Hz input, 256-sample sliding FFT)...")
    
    # Simulate 500 samples (5 seconds) with a 5 Hz sinusoidal tremor injected
    for i in range(500):
        t = i / 100.0
        # Simulated 5 Hz Parkinsonian resting tremor on roll/pitch
        roll = 15.0 * np.sin(2 * np.pi * 5.0 * t) + np.random.normal(0, 0.5)
        pitch = 10.0 * np.cos(2 * np.pi * 5.0 * t) + np.random.normal(0, 0.5)
        yaw = 1.0 + np.random.normal(0, 0.2)
        ax = 0.05 * np.sin(2 * np.pi * 5.0 * t)
        ay = 0.02 * np.cos(2 * np.pi * 5.0 * t)
        az = 1.0 # 1g baseline gravity

        accel_win, gyro_win = pipeline.process_sample(ax, ay, az, roll, pitch, yaw)

        # Triggered every 128 samples (~1.28s) once buffer fills to 256
        if accel_win is not None:
            f_acc, p_acc = pipeline.compute_fft(accel_win)
            f_gyr, p_gyr = pipeline.compute_fft(gyro_win)

            metrics = classifier.evaluate_motion(f_gyr, p_acc, p_gyr, raw_accel_peak=float(np.max(np.abs(accel_win))))
            vibe_state = actuator.update_state(metrics["tremor_detected"], delta_time_sec=1.28)

            payload = TelemetryPayload(
                device_id=device_id,
                timestamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                event_type="telemetry",
                dominant_frequency_hz=metrics["dominant_frequency_hz"],
                tremor_intensity_score=metrics["tremor_intensity_score"],
                tremor_detected=metrics["tremor_detected"],
                dyskinesia_detected=metrics["dyskinesia_detected"],
                vibration_active=vibe_state
            )
            print("Emitted Payload:", payload.model_dump_json())

if __name__ == "__main__":
    run_simulation()
