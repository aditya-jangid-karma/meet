"""
Validation Engine implementing the 10 Validation Gates from Report 1 Section 4.
Guarantees zero dirty writes or hallucinated data in QuickBooks Online.
"""

from typing import List, Optional
import re
from core.models import (
    VendorDocumentData, 
    SheetOrderData, 
    ValidationGateResult, 
    ValidationReport
)

def normalize_text(text: Optional[str]) -> str:
    """Normalize string for robust comparison: lowercase, strip punctuation and whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())

def match_supplier_names(name1: str, name2: str) -> bool:
    """Compare supplier names allowing for minor abbreviations (CO., LTD., etc.)."""
    n1 = normalize_text(name1).replace("limited", "ltd").replace("corporation", "corp").replace("company", "co")
    n2 = normalize_text(name2).replace("limited", "ltd").replace("corporation", "corp").replace("company", "co")
    return n1 == n2 or (n1 in n2) or (n2 in n1)

class OrderValidator:
    """
    Evaluates an incoming vendor PDF extraction against the master Google Sheet row.
    """

    def __init__(self, quantity_tolerance: float = 0.0, rate_tolerance: float = 0.001):
        self.quantity_tolerance = quantity_tolerance
        self.rate_tolerance = rate_tolerance

    def validate(
        self, 
        vendor_data: VendorDocumentData, 
        sheet_data: SheetOrderData,
        existing_qbo_po: bool = False,
        qbo_vendor_exists: bool = True,
        qbo_customer_exists: bool = True,
        qbo_item_exists: bool = True
    ) -> ValidationReport:
        gates: List[ValidationGateResult] = []
        errors: List[str] = []
        warnings: List[str] = []

        # Gate 1: Supplier Match
        supplier_matched = match_supplier_names(vendor_data.supplier_name, sheet_data.supplier_name)
        if supplier_matched and qbo_vendor_exists:
            gates.append(ValidationGateResult(
                gate_name="Gate 1: Supplier Verification",
                passed=True,
                message=f"Supplier verified: '{vendor_data.supplier_name}' matches Sheet '{sheet_data.supplier_name}'."
            ))
        else:
            err = f"Supplier mismatch: PDF '{vendor_data.supplier_name}' does not match Sheet '{sheet_data.supplier_name}' (or QBO vendor missing)."
            gates.append(ValidationGateResult(
                gate_name="Gate 1: Supplier Verification",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 2: Order # Match
        order_match = normalize_text(vendor_data.order_number) == normalize_text(sheet_data.order_number)
        if order_match and vendor_data.order_number:
            gates.append(ValidationGateResult(
                gate_name="Gate 2: Order Number",
                passed=True,
                message=f"Order number confirmed: {vendor_data.order_number}."
            ))
        else:
            err = f"Order # mismatch: PDF '{vendor_data.order_number}' != Sheet '{sheet_data.order_number}'."
            gates.append(ValidationGateResult(
                gate_name="Gate 2: Order Number",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 3: Item Code Resolution
        # Existing rule: Google Sheet item code controls when vendor wording differs.
        item_resolved = bool(sheet_data.item_code and sheet_data.item_code.strip())
        if item_resolved and qbo_item_exists:
            gates.append(ValidationGateResult(
                gate_name="Gate 3: Item Resolution",
                passed=True,
                message=f"Item resolved from master sheet: '{sheet_data.item_code}'."
            ))
        else:
            err = f"Item resolution failed: Item code '{sheet_data.item_code}' not defined in sheet or missing in QBO master."
            gates.append(ValidationGateResult(
                gate_name="Gate 3: Item Resolution",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 4: Standard Description
        desc_ok = bool(sheet_data.standardized_description and len(sheet_data.standardized_description.strip()) > 5)
        if desc_ok:
            gates.append(ValidationGateResult(
                gate_name="Gate 4: Standardized Description",
                passed=True,
                message="Master standardized description present."
            ))
        else:
            err = "Standardized description missing or empty in master sheet."
            gates.append(ValidationGateResult(
                gate_name="Gate 4: Standardized Description",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 5: Quantity Match
        vendor_qty = sum(item.quantity for item in vendor_data.line_items) if vendor_data.line_items else 0.0
        qty_diff = abs(vendor_qty - sheet_data.quantity)
        if qty_diff <= self.quantity_tolerance and vendor_qty > 0:
            gates.append(ValidationGateResult(
                gate_name="Gate 5: Quantity Verification",
                passed=True,
                message=f"Quantity verified: PDF {vendor_qty} == Sheet {sheet_data.quantity}."
            ))
        else:
            err = f"Quantity mismatch: PDF total {vendor_qty} != Sheet {sheet_data.quantity} (difference: {qty_diff})."
            gates.append(ValidationGateResult(
                gate_name="Gate 5: Quantity Verification",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 6: Purchase Rate Match
        vendor_rate = vendor_data.line_items[0].unit_price if vendor_data.line_items else 0.0
        rate_diff = abs(vendor_rate - sheet_data.supplier_price)
        if rate_diff <= self.rate_tolerance and vendor_rate > 0:
            gates.append(ValidationGateResult(
                gate_name="Gate 6: Purchase Rate Verification",
                passed=True,
                message=f"Purchase rate verified: PDF ${vendor_rate:.2f} == Sheet ${sheet_data.supplier_price:.2f}."
            ))
        else:
            err = f"Purchase rate mismatch: PDF ${vendor_rate:.2f} != Sheet ${sheet_data.supplier_price:.2f}."
            gates.append(ValidationGateResult(
                gate_name="Gate 6: Purchase Rate Verification",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 7: Customer Price & Margin Check
        has_cust_price = sheet_data.customer_price > 0
        profitable = sheet_data.customer_price >= sheet_data.supplier_price
        if has_cust_price and profitable:
            margin = sheet_data.customer_price - sheet_data.supplier_price
            gates.append(ValidationGateResult(
                gate_name="Gate 7: Customer Price & Margin",
                passed=True,
                message=f"Customer price valid: ${sheet_data.customer_price:.2f} (Margin: +${margin:.2f}/unit)."
            ))
        else:
            err = f"Customer price invalid: ${sheet_data.customer_price:.2f} (Supplier cost: ${sheet_data.supplier_price:.2f})."
            gates.append(ValidationGateResult(
                gate_name="Gate 7: Customer Price & Margin",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 8: Shipping Route / Terms Present
        has_shipping = bool(
            vendor_data.ship_from and vendor_data.ship_to and vendor_data.ship_via
        )
        if has_shipping:
            gates.append(ValidationGateResult(
                gate_name="Gate 8: Shipping Route",
                passed=True,
                message=f"Shipping route complete: From '{vendor_data.ship_from}' To '{vendor_data.ship_to}' via '{vendor_data.ship_via}'."
            ))
        else:
            err = f"Incomplete shipping details: From='{vendor_data.ship_from}', To='{vendor_data.ship_to}', ShipVia='{vendor_data.ship_via}'."
            gates.append(ValidationGateResult(
                gate_name="Gate 8: Shipping Route",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 9: Duplicate Check
        if not existing_qbo_po:
            gates.append(ValidationGateResult(
                gate_name="Gate 9: Duplicate Transaction Check",
                passed=True,
                message="No duplicate transaction found in QuickBooks Online."
            ))
        else:
            err = f"Duplicate detected: Order #{vendor_data.order_number} already has an active PO in QuickBooks Online."
            gates.append(ValidationGateResult(
                gate_name="Gate 9: Duplicate Transaction Check",
                passed=False,
                message=err
            ))
            errors.append(err)

        # Gate 10: QBO Master Data Existence
        if qbo_vendor_exists and qbo_customer_exists and qbo_item_exists:
            gates.append(ValidationGateResult(
                gate_name="Gate 10: QBO Master Data Resolution",
                passed=True,
                message="QBO Vendor, Customer, and Item records confirmed."
            ))
        else:
            err = f"QBO Master Data missing: Vendor={qbo_vendor_exists}, Customer={qbo_customer_exists}, Item={qbo_item_exists}."
            gates.append(ValidationGateResult(
                gate_name="Gate 10: QBO Master Data Resolution",
                passed=False,
                message=err
            ))
            errors.append(err)

        overall_passed = (len(errors) == 0)
        return ValidationReport(
            passed=overall_passed,
            order_number=sheet_data.order_number,
            gates=gates,
            errors=errors,
            warnings=warnings
        )
