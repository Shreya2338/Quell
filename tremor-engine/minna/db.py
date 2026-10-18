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
    tremor_start: datetime.datetime,
    tremor_end: datetime.datetime,
    tremor_intensity: float,
    peak_displacement_cm: float,
    dominant_frequency_hz: float,
    user_id: Optional[str] = None
) -> Optional[Dict]:
    """Persists a closed tremor episode into Supabase with automatic user resolution."""
    duration = (tremor_end - tremor_start).total_seconds()
    
    record = {
        "user_id": None,  # Overrides the default and bypasses foreign key checks if nullable
        "tremor_start": tremor_start.isoformat(),
        "tremor_end": tremor_end.isoformat(),
        "tremor_intensity": int(round(tremor_intensity)),
        "duration_seconds": float(round(duration, 3)),
        "peak_displacement_cm": float(round(float(peak_displacement_cm), 3)),
        "dominant_frequency_hz": float(round(float(dominant_frequency_hz), 2)),
    }

    if not supabase:
        print(f"[Local Mock] Supabase client not initialized. Would write: {record}")
        return record

    try:
        if not user_id:
            user_res = supabase.table("users").select("user_id").limit(1).execute()
            if user_res.data:
                user_id = user_res.data[0]["user_id"]

        if user_id:
            record["user_id"] = user_id

        response = supabase.table("tremors").insert(record).execute()
        return response.data

    except Exception as e:
        print(f"[Supabase Error] Failed to insert tremor event: {e}")
        return None