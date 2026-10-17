import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load GEMINI_API_KEY from .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

def generate_neurologist_report(patient_data: dict) -> dict:
    """
    Generates an exportable clinical report for neurologists using Gemini 2.5.
    Compiles tremor frequency, rotational amplitude, episodic duration,
    latency to onset, wearing-off slopes, vibration efficacy, and dosing adjustments.
    """
    if not client:
        return {
            "status": "offline_fallback",
            "clinical_report_markdown": "### Offline Fallback: Clinician Summary\n*GEMINI_API_KEY is not configured in .env. Reviewing local telemetry metrics.*",
            "metrics_evaluated": patient_data
        }

    prompt = f"""
You are an expert movement-disorder neurologist specializing in Parkinson's Disease and closed-loop bio-electronic therapeutics.
Analyze the following quantitative biometric telemetry and pharmacokinetic data from the "Quell" smart neuro-wristband:

PATIENT TELEMETRY & PHARMACOKINETIC SUMMARY:
{json.dumps(patient_data, indent=2)}

Generate a comprehensive, formal Neurologist Clinical Consultation Report containing these exact required sections:

1. EXECUTIVE CLINICAL SUMMARY:
   - Patient motor state stability and overall tremor burden assessment across the multi-day period.
   - Core clinical conclusions.

2. TREMOR PHENOTYPE & EPISODIC ANALYSIS:
   - Multi-day tremor frequency trends.
   - Peak severity trends and peak rotational amplitude (deg/s and estimated displacement in cm).
   - Dominant 4.0 - 6.0 Hz frequency tracking and resting tremor power.
   - Episodic data: start/stop times, duration of episodes, and daily averages.

3. PHARMACOKINETIC & LEVODOPA DYNAMICS:
   - Direct comparison of medication intake timestamps compared directly to tremor severity curves ("On/Off" cycling).
   - Latency to onset: time elapsed from the button press until a significant reduction in tremor power.
   - Peak efficacy duration: specific window of minimum tremor activity.
   - Wearing-off slopes: quantitative rate of progressive tremor power increase before the next scheduled dose.
   - Peak-dose dyskinesia evaluation.

4. CLOSED-LOOP VIBROTACTILE (PETER TASS) THERAPY EFFICACY:
   - Measured vibration effectiveness in counteracting symptoms (% reduction in 4-6 Hz power post-actuation).
   - Efficacy of the 250 Hz Coordinated Reset sensory burst pattern in bridging wearing-off periods.

5. EVIDENCE-BASED PERSONALIZED DOSAGE TIMING RECOMMENDATIONS:
   - Quantitative evidence and recommendations suggesting personalized dosage timing adjustments.
   - Calculate using: OptimalNextDoseTime = t_wear-off - latency_to_onset.
   - Strictly enforce the clinical floor safety check: minimum interval >= 3.5 hours.
   - DO NOT recommend increasing milligram dosages or adding pills; optimize interval timing and vibrotactile bridging.

Format strictly in clean, professional Markdown with clear headings and bulleted clinical findings.
"""

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2, # Low temperature ensures factual clinical accuracy
            max_output_tokens=2500,
        )
    )

    return {
        "status": "success",
        "model": "gemini-3.8-flash",
        "metrics_evaluated": patient_data,
        "clinical_report_markdown": response.text
    }