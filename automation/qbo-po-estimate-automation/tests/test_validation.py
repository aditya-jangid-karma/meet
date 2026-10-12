"""
Unit tests for the OrderValidator (10 Validation Gates).
"""

import pytest
from core.models import VendorDocumentData, SheetOrderData, LineItem
from core.validator import OrderValidator

@pytest.fixture
def valid_order_7207():
    vendor = VendorDocumentData(
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
    sheet = SheetOrderData(
        order_number="7207",
        supplier_name="A-TEX INTERNATIONAL CO., LIMITED",
        item_code="AT-2080-1",
        standardized_description='TEXTILES / ORDER#7207 / 92%RAYON - 8%POLYESTER / 280-295GM / 58/59"',
        quantity=22400.0,
        supplier_price=1.30,
        customer_price=1.85,
        row_index=638
    )
    return vendor, sheet

def test_order_7207_passes_all_gates(valid_order_7207):
    vendor, sheet = valid_order_7207
    validator = OrderValidator()
    report = validator.validate(vendor, sheet)
    assert report.passed is True
    assert len(report.errors) == 0
    assert len(report.gates) == 10
    assert all(gate.passed for gate in report.gates)

def test_gate_5_fails_on_quantity_mismatch(valid_order_7207):
    vendor, sheet = valid_order_7207
    vendor.line_items[0].quantity = 20000.0  # Mismatch (20,000 vs 22,400)
    validator = OrderValidator()
    report = validator.validate(vendor, sheet)
    assert report.passed is False
    assert any("Quantity mismatch" in err for err in report.errors)

def test_gate_6_fails_on_rate_mismatch(valid_order_7207):
    vendor, sheet = valid_order_7207
    vendor.line_items[0].unit_price = 1.35  # Mismatch ($1.35 vs $1.30)
    validator = OrderValidator()
    report = validator.validate(vendor, sheet)
    assert report.passed is False
    assert any("Purchase rate mismatch" in err for err in report.errors)

def test_gate_1_fails_on_supplier_mismatch(valid_order_7207):
    vendor, sheet = valid_order_7207
    vendor.supplier_name = "DIFFERENT SUPPLIER CORP"
    validator = OrderValidator()
    report = validator.validate(vendor, sheet)
    assert report.passed is False
    assert any("Supplier mismatch" in err for err in report.errors)

def test_gate_9_fails_on_duplicate_transaction(valid_order_7207):
    vendor, sheet = valid_order_7207
    validator = OrderValidator()
    report = validator.validate(vendor, sheet, existing_qbo_po=True)
    assert report.passed is False
    assert any("Duplicate detected" in err for err in report.errors)

def test_gate_7_fails_on_negative_margin(valid_order_7207):
    vendor, sheet = valid_order_7207
    sheet.customer_price = 1.00  # Selling at $1.00 when cost is $1.30!
    validator = OrderValidator()
    report = validator.validate(vendor, sheet)
    assert report.passed is False
    assert any("Customer price invalid" in err for err in report.errors)
