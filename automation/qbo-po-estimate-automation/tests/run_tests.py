"""
Test runner for QBO PO & Estimate Automation.
Executes all unit and integration tests using Python's standard unittest.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.models import VendorDocumentData, SheetOrderData, LineItem
from core.validator import OrderValidator
from pipeline.orchestrator import OrderProcessingPipeline
from services.audit_logger import AuditLogger

class TestValidationGates(unittest.TestCase):
    def setUp(self):
        self.vendor = VendorDocumentData(
            supplier_name="A-TEX INTERNATIONAL CO., LIMITED",
            supplier_po_number="AT-26209",
            order_number="7207",
            po_date="09/18/2026",
            ship_from="SHANGHAI, CHINA",
            ship_to="BUENAVENTURA, COLOMBIA",
            ship_via="BY SEA",
            line_items=[
                LineItem(
                    item_code="AT-2080-1",
                    description='TEXTILES / ORDER#7207 / 92%RAYON - 8%POLYESTER / 280-295GM / 58/59"',
                    quantity=22400.0,
                    unit_price=1.30,
                    line_total=29120.0
                )
            ]
        )
        self.sheet = SheetOrderData(
            order_number="7207",
            supplier_name="A-TEX INTERNATIONAL CO., LIMITED",
            item_code="AT-2080-1",
            standardized_description='TEXTILES / ORDER#7207 / 92%RAYON - 8%POLYESTER / 280-295GM / 58/59"',
            quantity=22400.0,
            supplier_price=1.30,
            customer_price=1.85,
            row_index=638
        )
        self.validator = OrderValidator()

    def test_order_7207_passes_all_gates(self):
        report = self.validator.validate(self.vendor, self.sheet)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.errors), 0)
        self.assertEqual(len(report.gates), 10)

    def test_quantity_mismatch_fails(self):
        self.vendor.line_items[0].quantity = 20000.0
        report = self.validator.validate(self.vendor, self.sheet)
        self.assertFalse(report.passed)
        self.assertTrue(any("Quantity mismatch" in e for e in report.errors))

    def test_rate_mismatch_fails(self):
        self.vendor.line_items[0].unit_price = 1.35
        report = self.validator.validate(self.vendor, self.sheet)
        self.assertFalse(report.passed)
        self.assertTrue(any("Purchase rate mismatch" in e for e in report.errors))

    def test_supplier_mismatch_fails(self):
        self.vendor.supplier_name = "OTHER SUPPLIER"
        report = self.validator.validate(self.vendor, self.sheet)
        self.assertFalse(report.passed)
        self.assertTrue(any("Supplier mismatch" in e for e in report.errors))

    def test_duplicate_fails(self):
        report = self.validator.validate(self.vendor, self.sheet, existing_qbo_po=True)
        self.assertFalse(report.passed)
        self.assertTrue(any("Duplicate detected" in e for e in report.errors))

    def test_negative_margin_fails(self):
        self.sheet.customer_price = 1.00
        report = self.validator.validate(self.vendor, self.sheet)
        self.assertFalse(report.passed)
        self.assertTrue(any("Customer price invalid" in e for e in report.errors))

    def test_pipeline_end_to_end(self):
        test_db = PROJECT_ROOT / "data" / "test_run_log.db"
        audit = AuditLogger(db_path=str(test_db))
        pipeline = OrderProcessingPipeline(audit_logger=audit)
        sample_json = PROJECT_ROOT / "samples" / "sample_order_7207.json"
        res = pipeline.process_file(str(sample_json))
        self.assertIn(res.status, ["SUCCESS", "VALIDATION_FAILED"])
        self.assertEqual(res.order_number, "7207")
        if res.status == "SUCCESS":
            self.assertTrue(bool(res.qbo_result.estimate_number))
            self.assertTrue(res.sheet_updated)
        else:
            self.assertTrue(any("Duplicate" in err for err in res.validation_report.errors))
        if test_db.exists():
            test_db.unlink()

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestValidationGates)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
