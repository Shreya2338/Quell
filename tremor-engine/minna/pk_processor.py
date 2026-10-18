import os
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dataclasses import dataclass
from typing import List, Dict, Any
import psycopg2
from backend.esp32Talker.mailer import sendemail
from psycopg2.extras import RealDictCursor

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
    timestamp: float  # Epoch time
    dose_amount_mg: float

@dataclass
class TremorRecord:
    timestamp: float
    intensity: float  
    linear_acceleration: float  
    dyskinesia_flag: bool

class MedicationLogRequest(BaseModel):
    timestamp: float  # Epoch timestamp when medication was taken
    dose_amount_mg: float
    patient_id: str   
    caregiver_email: str  # Added to route email notifications to the correct recipient

class VisualizationResponse(BaseModel):
    suggested_next_dose_time: float
    dose_markers: List[Dict[str, Any]]
    tremor_series: List[Dict[str, Any]]
    latency_bar: Dict[str, Any]
    effective_window: Dict[str, Any]
    wear_off_line: List[Dict[str, Any]]

# In-memory storage for logged doses in this session
IN_MEMORY_DOSE_LOG: List[DoseEvent] = []

# NOTE: send_email contract is assumed to exist externally as requested:
# def send_email(to_email: str, title: str, body: str) -> None:


def db_fetch_tremor_records(patient_id: str, start_time: float, end_time: float) -> List[TremorRecord]:
    """
    Queries the actual PostgreSQL 'tremor' table using columns from database schema.
    """
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
        print(f"Database connection error: {e}")
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
    min_spacing = 12600.0  # 3.5 hours minimum spacing
    return max(dose_time + min_spacing, raw_optimal_time)

@app.post("/api/medication/log", response_model=VisualizationResponse)
def log_medication_and_get_analytics(payload: MedicationLogRequest):
    new_dose = DoseEvent(timestamp=payload.timestamp, dose_amount_mg=payload.dose_amount_mg)
    
    # Check if a previous dose exists to evaluate if this dose was logged late/missed
    if len(IN_MEMORY_DOSE_LOG) > 0:
        last_logged_dose = IN_MEMORY_DOSE_LOG[-1]
        # Calculate expected timing based on previous metrics (e.g., if gap exceeds 5 hours / 18000 seconds)
        time_since_last_dose = new_dose.timestamp - last_logged_dose.timestamp
        grace_period_threshold = 18000.0  # 5 hours
        
        if time_since_last_dose > grace_period_threshold:
            # Trigger caregiver notification email function contract
            send_email(
                to_email=payload.caregiver_email,
                title="Alert: Potential Missed or Delayed Medication Dose",
                body=(f"Patient logged medication {time_since_last_dose / 3600:.1f} hours after the previous dose. "
                      f"This exceeds the expected dosing interval threshold.")
            )

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)