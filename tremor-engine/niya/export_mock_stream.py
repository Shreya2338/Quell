import json
import datetime
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared.contracts import TelemetryPayload
from niya.dsp_pipeline import DSPPipeline
from niya.tremor_classifier import TremorClassifier
from niya.tass_actuator import TassActuator

def generate_telemetry_file(output_path="data/processed/mock_telemetry_stream.json"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pipeline = DSPPipeline()
    classifier = TremorClassifier()
    actuator = TassActuator()
    
    records = []
    base_time = datetime.datetime.now(datetime.timezone.utc)
    
    # Simulate 600 seconds (10 minutes) at 100 Hz = 60,000 samples
    for i in range(60000):
        t = i / 100.0
        # Inject resting tremor between t=120s and t=360s; otherwise steady
        has_tremor = (120.0 <= t <= 360.0)
        
        freq = 5.0 if has_tremor else 1.0
        amp = 18.0 if has_tremor else 1.0
        
        roll = amp * np.sin(2 * np.pi * freq * t) + np.random.normal(0, 0.4)
        pitch = amp * np.cos(2 * np.pi * freq * t) + np.random.normal(0, 0.4)
        yaw = 1.0 + np.random.normal(0, 0.2)
        ax = 0.04 * np.sin(2 * np.pi * freq * t)
        ay = 0.02 * np.cos(2 * np.pi * freq * t)
        az = 1.0

        accel_win, gyro_win = pipeline.process_sample(ax, ay, az, roll, pitch, yaw)

        if accel_win is not None:
            f_acc, p_acc = pipeline.compute_fft(accel_win)
            f_gyr, p_gyr = pipeline.compute_fft(gyro_win)
            metrics = classifier.evaluate_motion(f_gyr, p_acc, p_gyr, raw_accel_peak=float(np.max(np.abs(accel_win))))
            vibe_state = actuator.update_state(metrics["tremor_detected"], delta_time_sec=1.28)

            timestamp = (base_time + datetime.timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%SZ")
            payload = TelemetryPayload(
                device_id="esp32_wristband_01",
                timestamp=timestamp,
                event_type="telemetry",
                dominant_frequency_hz=metrics["dominant_frequency_hz"],
                tremor_intensity_score=metrics["tremor_intensity_score"],
                tremor_detected=metrics["tremor_detected"],
                dyskinesia_detected=metrics["dyskinesia_detected"],
                vibration_active=vibe_state
            )
            records.append(payload.model_dump())

    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Exported {len(records)} sliding-window telemetry frames to {output_path}")

if __name__ == "__main__":
    generate_telemetry_file()
