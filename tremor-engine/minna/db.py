import os
import datetime
from typing import Optional, Dict
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Retrieve credentials from .env
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"[Supabase Warning] Failed to initialize client: {e}")


def insert_tremor_event(
    #device_id: str,
    tremor_start: datetime.datetime,
    tremor_end: datetime.datetime,
    tremor_intensity: float,
    peak_displacement_cm: float,
    dominant_frequency_hz: float
) -> Optional[Dict[str, Any]]:
    duration = (tremor_end - tremor_start).total_seconds()
    
    record = {
        #"device_id": str(device_id),
        "tremor_start": tremor_start.isoformat(),
        "tremor_end": tremor_end.isoformat(),
        # If duration or intensity in your Supabase table is an INTEGER / BIGINT:
        "duration_seconds": round(float(duration), 2),
        "tremor_intensity": int(round(tremor_intensity)),  # <--- CAST TO INT (1 instead of 1.0)
        "peak_displacement_cm": round(float(peak_displacement_cm), 3),
        "dominant_frequency_hz": round(float(dominant_frequency_hz), 2)
    }

    response = supabase.table("tremors").insert(record).execute()
    return response.data

