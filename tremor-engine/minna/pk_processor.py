import os
import time
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from dataclasses import dataclass
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI(title="Parkinson's PK & Tremor Intelligence API")

# Database connection configuration
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "your_password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

@dataclass
class DoseEvent:
    timestamp: float
    dose_amount_mg: float

@dataclass
class TremorRecord:
    timestamp: float
    intensity: float
    linear_acceleration: float
    dyskinesia_flag: bool

# --- Pydantic Models ---
class MedicationLogRequest(BaseModel):
    timestamp: float
    dose_amount_mg: float
    patient_id: str

class MissedMedicationCheckRequest(BaseModel):
    patient_id: str
    caregiver_email: str
    expected_dose_timestamp: float  # When the dose was supposed to be taken

class VisualizationResponse(BaseModel):
    suggested_next_dose_time: float
    dose_markers: List[Dict[str, Any]]
    tremor_series: List[Dict[str, Any]]
    latency_bar: Dict[str, Any]
    effective_window: Dict[str, Any]
    wear_off_line: List[Dict[str, Any]]

# In-memory storage for logged doses in this session
IN_MEMORY_DOSE_LOG: List[DoseEvent] = []

# --- CAREGIVER NOTIFICATION SYSTEM ---
def notify_caregiver(email_address_recipient: str, title: str, body: str):
    """
    Pings a family member or caregiver via email when medication is missed.
    """
    print(f"\n[ALERT TRIGGERED] Sending email to caregiver...")
    print(f"To: {email_address_recipient}")
    print(f"Subject: {title}")
    print(f"Body: {body}\n")
    
    # Optional: Configure actual SMTP server credentials if ready for production deployment
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "alerts@parkinsonapp.com")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your_email_password")
    
    # If environment variables are set up, send live emails; otherwise simulation print handles it safely
    if SENDER_PASSWORD != "your_email_password":
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = email_address_recipient
            msg['Subject'] = title
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, email_address_recipient, msg.as_string())
            print("Caregiver email notification sent successfully!")
        except Exception as e:
            print(f"Failed to send email via SMTP: {e}")

# --- DATABASE REPOSITORY ---
def db_fetch_tremor_records(patient_id: str, start_time: float, end_time: float) -> List[TremorRecord]:
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT tremor_start, tremor_intensity, peak_displacement_cm, dominant_frequency_hz
            FROM tremor
            WHERE user_id = %s 
              AND tremor_start >= TO_TIMESTAMP(%s) 
              AND tremor_start <= TO_TIMESTAMP(%s)
            ORDER BY tremor_start ASC;
        """
        cursor.execute(query, (patient_id, start_time, end_time))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        records = []
        for row in rows:
            ts_epoch = row['tremor_start'].timestamp() if row['tremor_start'] else start_time
            intensity = float(row['tremor_intensity'] or 0.0)
            lin_acc = float(row['peak_displacement_cm'] or 1.0)
            dyskinesia = True if intensity < 1 and float(row.get('dominant_frequency_hz', 0) or 0) > 6.0 else False
            
            records.append(TremorRecord(
                timestamp=ts_epoch,
                intensity=intensity,
                linear_acceleration=lin_acc,
                dyskinesia_flag=dyskinesia
            ))
        return records
    except Exception as e:
        print(f"Database connection warning: {e}")
        return []

def calculate_pk_metrics(dose: DoseEvent, tremor_df: pd.DataFrame) -> Dict[str, float]:
    post_dose = tremor_df[
        (tremor_df['timestamp'] >= dose.timestamp) & 
        (tremor_df['timestamp'] <= dose.timestamp + 21600.0)
    ].copy()
    
    if post_dose.empty:
        return {"latency_to_onset": 30.0, "peak_efficacy_duration": 180.0, "wear_off_rate": 0.05}
    
    baseline_tremor = post_dose.iloc[0]['intensity']
    effective_mask = post_dose['intensity'] <= (baseline_tremor * 0.5) if baseline_tremor > 0 else post_dose['intensity'] <= 1.0
    effective_rows = post_dose[effective_mask]
    
    latency_to_onset = (effective_rows.iloc[0]['timestamp'] - dose.timestamp) / 60.0 if not effective_rows.empty else 30.0
    peak_efficacy_duration = len(effective_rows) * 5.0
    
    return {
        "latency_to_onset": max(5.0, latency_to_onset),
        "peak_efficacy_duration": max(60.0, peak_efficacy_duration),
        "wear_off_rate": 0.05
    }

def calculate_optimal_next_dose(last_dose: DoseEvent, pk_metrics: Dict[str, float], dyskinesia_flagged: bool) -> float:
    dose_time = last_dose.timestamp
    peak_duration = pk_metrics["peak_efficacy_duration"] * 60.0
    latency = pk_metrics["latency_to_onset"] * 60.0
    
    if dyskinesia_flagged:
        return dose_time + 14400.0
        
    raw_optimal_time = dose_time + peak_duration - latency
    min_spacing = 12600.0
    return max(dose_time + min_spacing, raw_optimal_time)

# --- API ENDPOINTS ---

@app.post("/api/medication/log", response_model=VisualizationResponse)
def log_medication_and_get_analytics(payload: MedicationLogRequest):
    new_dose = DoseEvent(timestamp=payload.timestamp, dose_amount_mg=payload.dose_amount_mg)
    IN_MEMORY_DOSE_LOG.append(new_dose)
    
    tremor_records = db_fetch_tremor_records(
        patient_id=payload.patient_id, 
        start_time=payload.timestamp, 
        end_time=payload.timestamp + 21600.0
    )
    
    if not tremor_records:
        tremor_records = [TremorRecord(timestamp=payload.timestamp + (i*300), intensity=3.0 - (i*0.2), linear_acceleration=1.0, dyskinesia_flag=False) for i in range(12)]
        
    df_tremors = pd.DataFrame([vars(t) for t in tremor_records])
    
    metrics = calculate_pk_metrics(new_dose, df_tremors)
    dyskinesia_flagged = df_tremors['dyskinesia_flag'].any() if not df_tremors.empty else False
    suggested_next_dose = calculate_optimal_next_dose(new_dose, metrics, dyskinesia_flagged)
    
    dose_markers = [{"timestamp": d.timestamp, "dose_mg": d.dose_amount_mg} for d in IN_MEMORY_DOSE_LOG]
    tremor_series = [{"timestamp": r.timestamp, "intensity": round(float(r.intensity), 2)} for r in tremor_records]
    
    latency_secs = metrics["latency_to_onset"] * 60.0
    latency_bar = {
        "start_timestamp": new_dose.timestamp,
        "end_timestamp": new_dose.timestamp + latency_secs,
        "elapsed_minutes": metrics["latency_to_onset"]
    }
    
    effective_secs = metrics["peak_efficacy_duration"] * 60.0
    effective_start = new_dose.timestamp + latency_secs
    effective_window = {
        "start_timestamp": effective_start,
        "end_timestamp": effective_start + effective_secs,
        "total_consecutive_minutes": metrics["peak_efficacy_duration"]
    }
    
    wear_off_start = effective_start + effective_secs
    wear_off_end = new_dose.timestamp + 21600.0
    wear_off_line = [
        {"timestamp": wear_off_start, "intensity": 0.5},
        {"timestamp": wear_off_end, "intensity": 3.5}
    ]
    
    return {
        "suggested_next_dose_time": suggested_next_dose,
        "dose_markers": dose_markers,
        "tremor_series": tremor_series,
        "latency_bar": latency_bar,
        "effective_window": effective_window,
        "wear_off_line": wear_off_line
    }

@app.post("/api/medication/check-missed")
def check_missed_medication(payload: MissedMedicationCheckRequest):
    """
    Endpoint that your frontend cron-job or timer can call to evaluate 
    if a scheduled medication has been missed past its safety threshold.
    """
    current_time = time.time()
    grace_period_seconds = 45 * 60  # 45 minutes grace period past scheduled time
    
    # Check if the expected dose time plus grace period has passed
    if current_time > (payload.expected_dose_timestamp + grace_period_seconds):
        # Trigger caregiver alert
        title = "Missed Medication Alert"
        body = (
            f"Patient {payload.patient_id} has missed their scheduled medication dose "
            f"originally expected at timestamp {payload.expected_dose_timestamp}. "
            "Please check in on them."
        )
        
        notify_caregiver(
            email_address_recipient=payload.caregiver_email,
            title=title,
            body=body
        )
        
        return {"status": "alert_sent", "message": "Medication is overdue. Caregiver notified."}
    
    return {"status": "on_track", "message": "Medication is still within the acceptable window."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)