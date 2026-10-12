"""
Integration tests for the OrderProcessingPipeline.
"""

import os
from pathlib import Path
from pipeline.orchestrator import OrderProcessingPipeline
from services.audit_logger import AuditLogger

def test_pipeline_end_to_end_sample_order():
    test_db = Path(__file__).parent / "test_control_log.db"
    if test_db.exists():
        test_db.unlink()

    audit = AuditLogger(db_path=str(test_db))
    pipeline = OrderProcessingPipeline(audit_logger=audit)

    sample_json = Path(__file__).resolve().parent.parent / "samples" / "sample_order_7207.json"
    result = pipeline.process_file(str(sample_json))

    assert result.status == "SUCCESS"
    assert result.order_number == "7207"
    assert result.validation_report.passed is True
    assert result.qbo_result.success is True
    assert result.qbo_result.estimate_number == "1793"
    assert result.sheet_updated is True

    # Check database record
    runs = audit.get_runs()
    assert len(runs) >= 1
    assert runs[0]["order_number"] == "7207"
    assert runs[0]["status"] == "SUCCESS"

    # Cleanup
    if test_db.exists():
        test_db.unlink()
