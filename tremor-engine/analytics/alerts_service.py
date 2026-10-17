import time
from typing import List, Dict, Optional
from pydantic import BaseModel

class EmergencyContact(BaseModel):
    name: str
    relation: str # e.g. "Caregiver", "Daughter", "Nurse"
    phone: str
    email: Optional[str] = None

class CaregiverAlert(BaseModel):
    alert_id: str
    timestamp: float
    patient_id: str
    room_number: str
    alert_type: str # "WEARING_OFF_FREEZING", "MISSED_DOSE", "DYSKINESIA_RISK", "PANIC_SOS"
    severity: str # "HIGH", "CRITICAL", "MODERATE"
    reason: str # Explainability text (PointClickCare bonus)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[float] = None

class AlertManager:
    def __init__(self):
        self.emergency_contacts: List[EmergencyContact] = [
            EmergencyContact(name="Sarah Jenkins", relation="Primary Caregiver", phone="+1-416-555-0199")
        ]
        self.active_alerts: List[CaregiverAlert] = []

    def create_alert(self, patient_id: str, alert_type: str, severity: str, reason: str, room: str = "Room 204 - Bed B") -> CaregiverAlert:
        alert = CaregiverAlert(
            alert_id=f"alert_{int(time.time() * 1000)}",
            timestamp=time.time(),
            patient_id=patient_id,
            room_number=room,
            alert_type=alert_type,
            severity=severity,
            reason=reason,
            acknowledged=False
        )
        self.active_alerts.insert(0, alert)
        return alert

    def trigger_sos(self, patient_id: str = "patient_01") -> CaregiverAlert:
        """Triggered when patient long-presses button on chassis (>2.5s)"""
        return self.create_alert(
            patient_id=patient_id,
            alert_type="PANIC_SOS",
            severity="CRITICAL",
            reason="Patient initiated immediate emergency assist request via long press on wristband."
        )

    def acknowledge_alert(self, alert_id: str, caregiver_name: str) -> bool:
        for alert in self.active_alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = caregiver_name
                alert.acknowledged_at = time.time()
                return True
        return False

alert_manager = AlertManager()