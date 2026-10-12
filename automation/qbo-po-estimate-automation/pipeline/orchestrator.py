"""
Master Automation Pipeline Orchestrator.
Executes the exact 13 stages outlined in Report 1.
"""

import uuid
import logging
from typing import Optional, Dict, Any

from core.models import PipelineExecutionResult
from core.validator import OrderValidator
from services.azure_doc_intel import AzureDocIntelExtractor
from services.google_sheets import GoogleSheetsService
from services.qbo_client import QuickBooksOnlineService
from services.audit_logger import AuditLogger
from services.alerter import AlertService

logger = logging.getLogger(__name__)

class OrderProcessingPipeline:
    def __init__(
        self,
        extractor: Optional[AzureDocIntelExtractor] = None,
        sheets_service: Optional[GoogleSheetsService] = None,
        qbo_service: Optional[QuickBooksOnlineService] = None,
        validator: Optional[OrderValidator] = None,
        audit_logger: Optional[AuditLogger] = None,
        alerter: Optional[AlertService] = None
    ):
        self.extractor = extractor or AzureDocIntelExtractor()
        self.sheets = sheets_service or GoogleSheetsService()
        self.qbo = qbo_service or QuickBooksOnlineService()
        self.validator = validator or OrderValidator()
        self.audit = audit_logger or AuditLogger()
        self.alerter = alerter or AlertService()

    def process_file(
        self, 
        file_path: str,
        require_approval: bool = False
    ) -> PipelineExecutionResult:
        """
        Execute full end-to-end automation for a given vendor PDF.
        """
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        logger.info(f"Starting pipeline execution {run_id} for {file_path}")

        try:
            # Stage 4: Document AI Extraction
            vendor_data = self.extractor.extract_from_file(file_path)
            order_number = vendor_data.order_number

            if not order_number:
                msg = "Extraction failed: No Order Number could be detected from source document."
                res = PipelineExecutionResult(
                    run_id=run_id,
                    order_number="UNKNOWN",
                    status="VALIDATION_FAILED",
                    message=msg
                )
                self.audit.record_run(res, {"file": file_path})
                self.alerter.send_validation_failure_alert("UNKNOWN", [msg], file_path)
                return res

            # Stage 5: Find G Sheet Row
            sheet_data = self.sheets.find_order_by_number(order_number)
            if not sheet_data:
                msg = f"Order #{order_number} not found in client Google Sheet ('PROFORMAS' tab)."
                res = PipelineExecutionResult(
                    run_id=run_id,
                    order_number=order_number,
                    status="VALIDATION_FAILED",
                    message=msg
                )
                self.audit.record_run(res, {"vendor_data": str(vendor_data)})
                self.alerter.send_validation_failure_alert(order_number, [msg], file_path)
                return res

            # Stage 8: Duplicate Check in QBO
            has_duplicate = self.qbo.check_duplicate_order(order_number, vendor_data.supplier_po_number)

            # Master Entities Check
            entities = self.qbo.verify_master_entities(
                vendor_name=sheet_data.supplier_name,
                customer_name="T3 TEXTILES S.A.S",
                item_code=sheet_data.item_code
            )

            # Stage 6 & 7: Validate using 10 Gates
            validation_report = self.validator.validate(
                vendor_data=vendor_data,
                sheet_data=sheet_data,
                existing_qbo_po=has_duplicate,
                qbo_vendor_exists=entities.get("vendor", True),
                qbo_customer_exists=entities.get("customer", True),
                qbo_item_exists=entities.get("item", True)
            )

            # Stop immediately if any gate fails (Safe boundary)
            if not validation_report.passed:
                msg = f"Validation failed with {len(validation_report.errors)} violations."
                res = PipelineExecutionResult(
                    run_id=run_id,
                    order_number=order_number,
                    status="VALIDATION_FAILED",
                    validation_report=validation_report,
                    message=msg
                )
                self.audit.record_run(res, {"vendor": str(vendor_data), "sheet": str(sheet_data)})
                self.alerter.send_validation_failure_alert(order_number, validation_report.errors, file_path)
                return res

            # Human-in-the-Loop check (Phase 4 rollout policy)
            if require_approval:
                logger.info(f"Order #{order_number} passed validation. Awaiting manual confirmation...")
                # In production HITL, pause or return pending status

            # Stages 9, 10, 11: Create QBO Purchase Order and Estimate
            qbo_result = self.qbo.create_transactions(vendor_data, sheet_data)
            if not qbo_result.success:
                msg = f"QuickBooks Online transaction posting failed: {qbo_result.error}"
                res = PipelineExecutionResult(
                    run_id=run_id,
                    order_number=order_number,
                    status="QBO_FAILED",
                    validation_report=validation_report,
                    qbo_result=qbo_result,
                    message=msg
                )
                self.audit.record_run(res)
                self.alerter.send_system_error_alert(order_number, msg)
                return res

            # Stage 12: Update existing G Sheet field with generated Estimate #
            sheet_updated = False
            if qbo_result.estimate_number:
                sheet_updated = self.sheets.update_estimate_number(
                    order_number=order_number,
                    estimate_number=qbo_result.estimate_number,
                    row_index=sheet_data.row_index
                )

            # Stage 13: Complete and record in control log
            success_msg = (
                f"Successfully processed Order #{order_number}. "
                f"QBO PO: {qbo_result.purchase_order_number}, "
                f"Estimate/PI: {qbo_result.estimate_number}. "
                f"Google Sheet updated: {sheet_updated}."
            )
            res = PipelineExecutionResult(
                run_id=run_id,
                order_number=order_number,
                status="SUCCESS",
                validation_report=validation_report,
                qbo_result=qbo_result,
                sheet_updated=sheet_updated,
                message=success_msg
            )
            self.audit.record_run(res)
            return res

        except Exception as e:
            logger.exception(f"Unhandled error in pipeline for {file_path}")
            res = PipelineExecutionResult(
                run_id=run_id,
                order_number="UNKNOWN",
                status="ERROR",
                message=str(e)
            )
            self.audit.record_run(res)
            self.alerter.send_system_error_alert("UNKNOWN", str(e))
            return res
