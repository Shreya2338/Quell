import sqlite3
import datetime
from typing import Optional, List, Dict

DB_PATH = "quell.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                report_markdown TEXT NOT NULL
            );
        """)
        conn.commit()

def insert_report(patient_id: str, report_markdown: str, generated_at: Optional[str] = None) -> int:
    """Inserts a generated clinician consultation report into the database."""
    if not generated_at:
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reports (patient_id, generated_at, report_markdown) VALUES (?, ?, ?)",
            (patient_id, generated_at, report_markdown)
        )
        conn.commit()
        return cursor.lastrowid

def get_reports_by_patient(patient_id: str) -> List[Dict]:
    """Fetches all past archived reports for a given patient."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, patient_id, generated_at, report_markdown FROM reports WHERE patient_id = ? ORDER BY id DESC",
            (patient_id,)
        )
        return [dict(row) for row in cursor.fetchall()]