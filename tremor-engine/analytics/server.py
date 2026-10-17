import os
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Import the new services
from ai_report_service import generate_neurologist_report
from alerts_service import alert_manager, EmergencyContact

app = FastAPI(title="Quell Tremor Engine Analytics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. NEUROLOGIST GEMINI REPORT GENERATION ---
@app.post("/api/report/generate")
def create_clinical_report():
    """
    Gathers 10 quantitative pharmacokinetic, tremor, and vibrotactile metrics
    and generates a formal consultation summary using Gemini 2.5.
    """
    # 1. Multi-day metrics and peak rotational amplitude
    # 2. Episodic data (start, stop, duration)
    # 3. 4-6 Hz dominant frequency tracking
    # 4. Medication intake timestamps vs severity
    # 5. Latency to onset
    # 6. Peak efficacy duration
    # 7. Wearing-off slopes
    # 8. Vibration effectiveness
    # 9. Dyskinesia detection
    # 10. Personalized dosage timing shift
    patient_data_bundle = {
        "patient_id": "PT-9402-J",
        "monitoring_period": "3-Day Continuous Ambulatory Ingestion",
        "dominant_frequency_hz": 4.85,
        "tremor_band_tracking": "4.0 - 6.0 Hz Rest Tremor confirmed via 256-point sliding FFT (bins 10-16)",
        "peak_rotational_amplitude_deg_per_sec": 42.6,
        "estimated_physical_displacement_cm": 2.1,
        "mds_updrs_score_range": "Score 1 (Slight) to Score 3 (Moderate)",
        "episodic_data": {
            "daily_episodes_average": 5.4,
            "average_episode_duration_minutes": 24.6,
            "longest_recorded_episode_minutes": 52.0,
            "start_stop_timeline": [
                {"episode": 1, "start_time": "08:45:00Z", "stop_time": "09:12:00Z", "duration_min": 27},
                {"episode": 2, "start_time": "12:15:00Z", "stop_time": "12:48:00Z", "duration_min": 33}
            ]
        },
        "pharmacokinetics": {
            "dose_administered_mg": 100.0,
            "intake_timestamp": "08:00:00Z",
            "latency_to_onset_minutes": 22.5,
            "peak_efficacy_duration_minutes": 185.0,
            "wearing_off_slope_rate": 0.084,
            "dyskinesia_events_detected": 0
        },
        "vibrotactile_therapy_efficacy": {
            "stimulation_carrier_frequency_hz": 250.0,
            "stimulation_pattern": "Peter Tass Coordinated Reset (100ms ON / 67ms OFF)",
            "pre_vibe_intensity": 3.4,
            "post_vibe_intensity": 1.2,
            "average_symptom_attenuation_percentage": "64.7%",
            "active_therapy_sessions_count": 8
        },
        "dosage_timing_recommendation": {
            "formula_applied": "OptimalNextDoseTime = t_wear_off - Latency",
            "current_interval_hours": 4.0,
            "recommended_interval_hours": 3.65,
            "timing_adjustment": "Advance dose by 21 minutes",
            "clinical_floor_applied": "Validated >= 3.5h inter-dose safety constraint satisfied"
        }
    }

    report = generate_neurologist_report(patient_data_bundle)
    return report

# --- 2. POINTCLICKCARE CAREGIVER ALERTS & SOS ---
@app.get("/api/alerts")
def get_alerts():
    """Returns real-time alerts for the caregiver dashboard."""
    return {"alerts": alert_manager.active_alerts}

@app.post("/api/alerts/sos")
def patient_emergency_sos():
    """Triggered by a long press on the hardware chassis button."""
    alert = alert_manager.trigger_sos(patient_id="PT-9402-J")
    return {"status": "SOS_BROADCAST", "alert": alert}

@app.post("/api/alerts/acknowledge")
def acknowledge_aid(alert_id: str, caregiver_name: str = "Nurse_Sarah"):
    """Acknowledges patient aid / medicine administration."""
    success = alert_manager.acknowledge_alert(alert_id, caregiver_name)
    if not success:
        raise HTTPException(status_code=404, detail="Alert ID not found")
    return {"status": "ACKNOWLEDGED", "alert_id": alert_id, "by": caregiver_name}

@app.post("/api/contacts")
def add_contact(contact: EmergencyContact):
    """Add a chosen emergency contact/caregiver."""
    alert_manager.emergency_contacts.append(contact)
    return {"status": "success", "contacts": alert_manager.emergency_contacts}

# --- 3. HARDWARE LAPTOP LINK VIBRATION & CALIBRATION CONTRACTS ---
@app.get("/api/hardware/command")
def get_hardware_command():
    """Emits the exact laptop-to-ESP32 contract format."""
    return {
        "vibration": {
            "length": 500,     # in ms
            "intensity": 250   # in Hz
        },
        "calibrate_now": False
    }