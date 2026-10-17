from pydantic import BaseModel
from typing import Literal

class TelemetryPayload(BaseModel): # creates a standard for incoming data formatting
    device_id: str
    timestamp: str  # ISO 8601 UTC string (e.g., 2026-10-14T10:15:30Z)
    event_type: Literal["telemetry"] = "telemetry"
    dominant_frequency_hz: float
    tremor_intensity_score: int  # Integer 0 to 4 (MDS-UPDRS)
    tremor_detected: bool
    dyskinesia_detected: bool
    vibration_active: bool

class DosePayload(BaseModel): # dspevific logging format for medecine logging
    device_id: str
    timestamp: str  # ISO 8601 UTC string
    event_type: Literal["medication_dose"] = "medication_dose"
