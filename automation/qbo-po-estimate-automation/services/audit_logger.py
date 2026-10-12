"""
Audit Control Logger.
Maintains an isolated SQLite audit log of every automation run, extracted payload,
validation results, QBO transaction IDs, and exceptions.
Strict boundary: Completely separated from the client's master Google Sheet.
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from core.models import PipelineExecutionResult
from config.settings import settings

logger = logging.getLogger(__name__)

class AuditLogger:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS automation_runs (
                    run_id TEXT PRIMARY KEY,
                    order_number TEXT,
                    status TEXT,
                    timestamp TEXT,
                    validation_passed INTEGER,
                    validation_errors TEXT,
                    purchase_order_id TEXT,
                    purchase_order_number TEXT,
                    estimate_id TEXT,
                    estimate_number TEXT,
                    sheet_updated INTEGER,
                    message TEXT,
                    raw_data TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def record_run(
        self, 
        result: PipelineExecutionResult, 
        raw_data: Optional[Dict[str, Any]] = None
    ):
        """Record an execution run into the control log database."""
        val_passed = 1 if (result.validation_report and result.validation_report.passed) else 0
        val_errors = json.dumps(result.validation_report.errors if result.validation_report else [])
        
        po_id = result.qbo_result.purchase_order_id if result.qbo_result else None
        po_num = result.qbo_result.purchase_order_number if result.qbo_result else None
        est_id = result.qbo_result.estimate_id if result.qbo_result else None
        est_num = result.qbo_result.estimate_number if result.qbo_result else None

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO automation_runs (
                    run_id, order_number, status, timestamp, validation_passed,
                    validation_errors, purchase_order_id, purchase_order_number,
                    estimate_id, estimate_number, sheet_updated, message, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.run_id,
                result.order_number,
                result.status,
                result.timestamp,
                val_passed,
                val_errors,
                po_id,
                po_num,
                est_id,
                est_num,
                1 if result.sheet_updated else 0,
                result.message,
                json.dumps(raw_data or {})
            ))
            conn.commit()
        finally:
            conn.close()
        logger.info(f"Recorded run {result.run_id} (Status: {result.status}) into control log.")

    def get_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM automation_runs ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
