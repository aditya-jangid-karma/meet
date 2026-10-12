"""
Data models for the PO and Estimate automation pipeline.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class LineItem:
    item_code: str
    description: str
    quantity: float
    unit_price: float
    line_total: float
    unit_of_measure: str = "MTS"

@dataclass
class VendorDocumentData:
    supplier_name: str
    supplier_po_number: str
    order_number: str
    po_date: str
    ship_from: str
    ship_to: str
    ship_via: str
    line_items: List[LineItem] = field(default_factory=list)
    currency: str = "USD"
    total_amount: float = 0.0
    source_file_path: Optional[str] = None
    raw_extracted_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SheetOrderData:
    order_number: str
    supplier_name: str
    item_code: str
    standardized_description: str
    quantity: float
    supplier_price: float
    customer_price: float
    pi_number: Optional[str] = None
    row_index: Optional[int] = None
    comments: Optional[str] = None
    status: Optional[str] = None

@dataclass
class ValidationGateResult:
    gate_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationReport:
    passed: bool
    order_number: str
    gates: List[ValidationGateResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class QBOResult:
    purchase_order_id: Optional[str] = None
    purchase_order_number: Optional[str] = None
    estimate_id: Optional[str] = None
    estimate_number: Optional[str] = None
    success: bool = False
    error: Optional[str] = None

@dataclass
class PipelineExecutionResult:
    run_id: str
    order_number: str
    status: str  # 'SUCCESS', 'VALIDATION_FAILED', 'QBO_FAILED', 'ERROR'
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    validation_report: Optional[ValidationReport] = None
    qbo_result: Optional[QBOResult] = None
    sheet_updated: bool = False
    message: str = ""
