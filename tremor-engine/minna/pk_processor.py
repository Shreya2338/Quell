import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Tuple, Any

@dataclass
class DoseEvent:
    timestamp: float  # Minutes or epoch time
    dose_amount_mg: float

@dataclass
class TremorRecord:
    timestamp: float
    intensity: float  # Normalized tremor score (0 to 4)
    linear_acceleration: float
    dyskinesia_flag: bool

# --- STEP 2: Synthetic Test Dataset Generator ---
def generate_synthetic_test_dataset(num_days: int = 3) -> Tuple[List[DoseEvent], List[TremorRecord]]:
    """
    Generates synthetic test datasets containing medication timestamps, 
    doses, and corresponding tremor/acceleration curves.
    """
    np.random.seed(42)
    doses = []
    tremors = []
    
    for day in range(num_days):
        day_start = day * 1440.0  # Total minutes in a day
        dose_times = [day_start + 480.0, day_start + 780.0, day_start + 1080.0]  # 3 doses per day
        
        for dt in dose_times:
            doses.append(DoseEvent(timestamp=dt, dose_amount_mg=100.0))
            
            # Simulate a 6-hour (360 min) window post-dose in 5-minute increments
            for t_offset in range(0, 360, 5):
                t = dt + t_offset
                
                # Pharmacodynamic curve simulation:
                if t_offset < 20:
                    intensity = 3.5 - (t_offset / 20.0) * 1.5
                    lin_acc = 1.2 + np.random.normal(0, 0.1)
                elif 20 <= t_offset <= 240:
                    intensity = 0.5 + np.random.normal(0, 0.05)
                    lin_acc = 0.4 + np.random.normal(0, 0.05)
                else:
                    wear_off_progress = (t_offset - 240) / 120.0
                    intensity = 0.5 + wear_off_progress * 3.0 + np.random.normal(0, 0.1)
                    lin_acc = 0.5 + np.random.normal(0, 0.05)
                
                intensity = max(0.0, min(4.0, intensity))
                dyskinesia = True if (t_offset < 45 and intensity < 0.3 and lin_acc > 1.5) else False
                
                tremors.append(TremorRecord(
                    timestamp=t,
                    intensity=intensity,
                    linear_acceleration=lin_acc,
                    dyskinesia_flag=dyskinesia
                ))
                
    return doses, tremors

# --- STEP 3: Calculate Pharmacokinetic Metrics ---
def calculate_pk_metrics(dose: DoseEvent, tremor_df: pd.DataFrame) -> Dict[str, float]:
    """
    Measures pharmacokinetic performance for a given dose.
    """
    post_dose = tremor_df[
        (tremor_df['timestamp'] >= dose.timestamp) & 
        (tremor_df['timestamp'] <= dose.timestamp + 360.0)
    ].copy()
    
    if post_dose.empty:
        return {"latency_to_onset": 0.0, "peak_efficacy_duration": 0.0, "wear_off_rate": 0.0}
    
    baseline_tremor = post_dose.iloc[0]['intensity']
    
    effective_mask = post_dose['intensity'] <= (baseline_tremor * 0.5)
    effective_rows = post_dose[effective_mask]
    latency_to_onset = (effective_rows.iloc[0]['timestamp'] - dose.timestamp) if not effective_rows.empty else 30.0
    
    peak_efficacy_duration = len(effective_rows) * 5.0  # 5 minutes per interval
    
    wear_off_period = post_dose[post_dose['timestamp'] >= (dose.timestamp + latency_to_onset + peak_efficacy_duration)]
    if len(wear_off_period) > 1:
        time_diffs = wear_off_period['timestamp'] - wear_off_period.iloc[0]['timestamp']
        intensity_diffs = wear_off_period['intensity'] - wear_off_period.iloc[0]['intensity']
        wear_off_rate = float(intensity_diffs.iloc[-1] / max(1.0, time_diffs.iloc[-1]))
    else:
        wear_off_rate = 0.05
        
    return {
        "latency_to_onset": latency_to_onset,
        "peak_efficacy_duration": peak_efficacy_duration,
        "wear_off_rate": wear_off_rate
    }

# --- STEPS 4 & 5: Dosing Optimization & Clinical Guardrails ---
def calculate_optimal_next_dose(
    last_dose: DoseEvent, 
    pk_metrics: Dict[str, float], 
    dyskinesia_flagged: bool
) -> float:
    """
    OptimalNextDoseTime = DoseTime + PeakEfficacyDuration - LatencytoOnset
    Enforces min 3.5h spacing and freezes advancement if dyskinesia is flagged.
    """
    dose_time = last_dose.timestamp
    peak_duration = pk_metrics["peak_efficacy_duration"]
    latency = pk_metrics["latency_to_onset"]
    
    if dyskinesia_flagged:
        return dose_time + 240.0  # Default to safe 4-hour interval
        
    raw_optimal_time = dose_time + peak_duration - latency
    min_spacing = 210.0  # 3.5 hours in minutes
    optimal_time = max(dose_time + min_spacing, raw_optimal_time)
    
    return optimal_time

# --- STEP 6: Vibrotactile Gap Scheduling ---
def schedule_vibrotactile_therapy(
    last_dose: DoseEvent, 
    next_dose_time: float, 
    pk_metrics: Dict[str, float]
) -> List[Dict[str, float]]:
    """
    Schedules 4-6 Hz vibrotactile therapy during wearing-off gaps 
    where medication cannot be safely shifted earlier.
    """
    wear_off_start = last_dose.timestamp + pk_metrics["latency_to_onset"] + pk_metrics["peak_efficacy_duration"]
    
    # If wearing-off occurs before the next scheduled dose, schedule vibration therapy
    vibration_sessions = []
    if wear_off_start < next_dose_time:
        # Schedule therapy during the gap up until the next dose
        vibration_sessions.append({
            "start_time": wear_off_start,
            "end_time": next_dose_time,
            "target_frequency_hz": 5.0,  # Center of 4-6 Hz therapeutic band
            "actuation_state": 1         # 1 = Active / ON
        })
        
    return vibration_sessions

# --- STEPS 7, 8, & 9: UI Data Formatters for Shreya ---

def format_heatmap_dataset(tremor_records: List[TremorRecord], dose_events: List[DoseEvent]) -> Dict[str, Any]:
    """
    Step 7: Formats data for the 24h Heatmap (X: hour 0-24, Y: day of week, 
    Color: tremor intensity, Dot markers: medication times).
    """
    days_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heatmap_grid = []
    
    for r in tremor_records:
        # Convert absolute minutes to day index and hour of day
        total_mins = r.timestamp
        day_index = int(total_mins // 1440) % 7
        hour_of_day = (total_mins % 1440) / 60.0
        
        heatmap_grid.append({
            "day": days_map[day_index],
            "hour": round(hour_of_day, 2),
            "intensity": round(float(r.intensity), 2)
        })
        
    dose_markers = []
    for d in dose_events:
        total_mins = d.timestamp
        day_index = int(total_mins // 1440) % 7
        hour_of_day = (total_mins % 1440) / 60.0
        dose_markers.append({
            "day": days_map[day_index],
            "hour": round(hour_of_day, 2),
            "dose_mg": d.dose_amount_mg
        })
        
    return {
        "heatmap_cells": heatmap_grid,
        "dose_markers": dose_markers
    }

def format_timeseries_dataset(tremor_records: List[TremorRecord], dose: DoseEvent, pk_metrics: Dict[str, float]) -> Dict[str, Any]:
    """
    Step 8: Formats time vs tremor intensity line graph data including 
    horizontal spans for efficacy duration and wear-off trends.
    """
    time_series = [{"timestamp": r.timestamp, "intensity": round(float(r.intensity), 2)} for r in tremor_records]
    
    latency = pk_metrics["latency_to_onset"]
    duration = pk_metrics["peak_efficacy_duration"]
    wear_off_start = dose.timestamp + latency + duration
    
    annotations = {
        "dose_time": dose.timestamp,
        "latency_end_time": dose.timestamp + latency,
        "peak_efficacy_end_time": wear_off_start,
        "wear_off_rate": pk_metrics["wear_off_rate"]
    }
    
    return {
        "series": time_series,
        "annotations": annotations
    }

def format_actuation_dataset(vibration_sessions: List[Dict[str, float]], tremor_records: List[TremorRecord]) -> Dict[str, Any]:
    """
    Step 9: Formats actuation state bar graph data (vibration ON/OFF periods) 
    alongside synchronized tremor intensity data.
    """
    actuation_bars = []
    for session in vibration_sessions:
        actuation_bars.append({
            "start_time": session["start_time"],
            "end_time": session["end_time"],
            "state": session["actuation_state"],
            "frequency_hz": session["target_frequency_hz"]
        })
        
    return {
        "actuation_periods": actuation_bars,
        "tremor_overlay": [{"timestamp": r.timestamp, "intensity": round(float(r.intensity), 2)} for r in tremor_records]
    }

if __name__ == "__main__":
    doses, tremors = generate_synthetic_test_dataset(num_days=1)
    df = pd.DataFrame([vars(t) for t in tremors])
    metrics = calculate_pk_metrics(doses[0], df)
    
    opt_time_normal = calculate_optimal_next_dose(doses[0], metrics, dyskinesia_flagged=False)
    vib_sessions = schedule_vibrotactile_therapy(doses[0], opt_time_normal, metrics)
    
    # Test UI formatters (Steps 7, 8, 9)
    heatmap_data = format_heatmap_dataset(tremors, doses)
    timeseries_data = format_timeseries_dataset(tremors, doses[0], metrics)
    actuation_data = format_actuation_dataset(vib_sessions, tremors)
    
    print("--- UI Formatter Outputs ---")
    print("Heatmap Cells Count:", len(heatmap_data["heatmap_cells"]))
    print("Timeseries Annotations:", timeseries_data["annotations"])
    print("Actuation Periods:", actuation_data["actuation_periods"])
