import os
import json
import base64
import logging
from typing import Optional, Dict, Any
import requests

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

from core.models import VendorDocumentData, SheetOrderData, QBOResult
from config.settings import settings, STANDARD_CUSTOMER_NOTE

logger = logging.getLogger(__name__)

class QuickBooksOnlineService:
    """
    QBO API integration implementing the exact fields and rules from the SOP.
    Handles automatic OAuth token refreshing, duplicate checks, PO creation,
    and Estimate creation.
    """

    def __init__(
        self,
        realm_id: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        environment: Optional[str] = None
    ):
        self.realm_id = realm_id or settings.qbo_realm_id
        self.refresh_token = refresh_token or settings.qbo_refresh_token
        self.client_id = client_id or settings.qbo_client_id
        self.client_secret = client_secret or settings.qbo_client_secret
        self.environment = environment or settings.qbo_environment
        self.access_token = settings.qbo_access_token

        base_domain = "sandbox-quickbooks.api.intuit.com" if self.environment == "sandbox" else "quickbooks.api.intuit.com"
        self.base_url = f"https://{base_domain}/v3/company/{self.realm_id}"
        self.is_live = bool(self.realm_id and self.client_id and self.refresh_token and not str(self.realm_id).startswith("<"))

        if self.is_live and not self.access_token:
            self.refresh_oauth_token()

    def refresh_oauth_token(self) -> bool:
        """Exchange refresh token for a fresh access token."""
        try:
            auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
            headers = {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            }
            resp = requests.post(url, headers=headers, data=data, timeout=15)
            if resp.status_code == 200:
                payload = resp.json()
                self.access_token = payload.get("access_token")
                new_rt = payload.get("refresh_token")
                if new_rt:
                    self.refresh_token = new_rt
                logger.info("Successfully refreshed QBO OAuth access token.")
                return True
            else:
                logger.error(f"Failed to refresh QBO token: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error during QBO token refresh: {e}")
            return False

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def check_duplicate_order(self, order_number: str, doc_number: Optional[str] = None) -> bool:
        """Check if an active Purchase Order exists by Order # or DocNumber."""
        if not self.is_live:
            return False

        import urllib.parse

        # 1. Check by DocNumber first (if provided)
        if doc_number:
            clean_doc = str(doc_number).replace("'", "\\'")
            q_doc = f"SELECT Id, DocNumber FROM PurchaseOrder WHERE DocNumber = '{clean_doc}'"
            url_doc = f"{self.base_url}/query?query={urllib.parse.quote(q_doc)}"
            try:
                resp = requests.get(url_doc, headers=self._headers(), timeout=15)
                if resp.status_code == 200:
                    pos = resp.json().get("QueryResponse", {}).get("PurchaseOrder", [])
                    if pos:
                        logger.info(f"Duplicate PO found by DocNumber '{doc_number}': ID {pos[0].get('Id')}")
                        return True
            except Exception as e:
                logger.error(f"Error querying duplicate DocNumber in QBO: {e}")

        # 2. Check by Order # in Memo
        if order_number:
            clean_order = str(order_number).replace("'", "\\'")
            q_memo = f"SELECT Id, DocNumber, Memo FROM PurchaseOrder WHERE Memo LIKE '%{clean_order}%'"
            url_memo = f"{self.base_url}/query?query={urllib.parse.quote(q_memo)}"
            try:
                resp = requests.get(url_memo, headers=self._headers(), timeout=15)
                if resp.status_code == 200:
                    pos = resp.json().get("QueryResponse", {}).get("PurchaseOrder", [])
                    if pos:
                        logger.info(f"Duplicate PO found by Memo Order #{order_number}: ID {pos[0].get('Id')}")
                        return True
            except Exception as e:
                logger.error(f"Error querying duplicate Memo in QBO: {e}")

        return False

    def verify_master_entities(
        self, 
        vendor_name: str, 
        customer_name: str, 
        item_code: str
    ) -> Dict[str, bool]:
        """Verify Vendor, Customer, and Item exist in QBO."""
        if not self.is_live:
            return {"vendor": True, "customer": True, "item": True}

        # Check in live QBO via query endpoints
        return {
            "vendor": self._entity_exists("Vendor", vendor_name),
            "customer": self._entity_exists("Customer", customer_name),
            "item": self._entity_exists("Item", item_code)
        }

    def _get_entity_id(self, entity_type: str, name: str) -> Optional[str]:
        """Fetch numeric ID for a QBO entity."""
        if not self.is_live or not name:
            return "1"
        import urllib.parse
        clean_name = name.replace("'", "\\'")
        if entity_type.lower() == "item":
            query = f"SELECT Id, Name FROM Item WHERE Name = '{clean_name}'"
        else:
            query = f"SELECT Id, DisplayName FROM {entity_type} WHERE DisplayName = '{clean_name}'"

        url = f"{self.base_url}/query?query={urllib.parse.quote(query)}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=15)
            if resp.status_code == 200:
                res = resp.json().get("QueryResponse", {}).get(entity_type, [])
                if res:
                    return str(res[0].get("Id"))
            else:
                logger.warning(f"QBO query failed for {entity_type}: {resp.text}")
        except Exception as e:
            logger.warning(f"Error resolving {entity_type} ID in QBO: {e}")
        return None

    def _entity_exists(self, entity_type: str, name: str) -> bool:
        return bool(self._get_entity_id(entity_type, name))

    def _format_date(self, date_str: str) -> str:
        """Format date to YYYY-MM-DD for QuickBooks API."""
        if not date_str:
            return "2026-09-18"
        parts = date_str.replace("-", "/").split("/")
        if len(parts) == 3:
            if len(parts[2]) == 4:  # MM/DD/YYYY
                return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            elif len(parts[0]) == 4:  # YYYY/MM/DD
                return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        return date_str

    def build_purchase_order_payload(
        self, 
        vendor_data: VendorDocumentData, 
        sheet_data: SheetOrderData
    ) -> Dict[str, Any]:
        """Build exact Purchase Order payload required by QBO."""
        qty = sheet_data.quantity
        rate = sheet_data.supplier_price
        total = round(qty * rate, 2)
        vendor_id = self._get_entity_id("Vendor", sheet_data.supplier_name) or "1"
        item_id = self._get_entity_id("Item", sheet_data.item_code) or "1"

        payload = {
            "DocNumber": vendor_data.supplier_po_number,
            "TxnDate": self._format_date(vendor_data.po_date),
            "VendorRef": {
                "value": vendor_id,
                "name": sheet_data.supplier_name
            },
            "ShipMethodRef": {
                "name": vendor_data.ship_via
            },
            "Memo": f"Order #{sheet_data.order_number}",
            "Line": [
                {
                    "DetailType": "ItemBasedExpenseLineDetail",
                    "Amount": total,
                    "Description": sheet_data.standardized_description,
                    "ItemBasedExpenseLineDetail": {
                        "ItemRef": {
                            "value": item_id,
                            "name": sheet_data.item_code
                        },
                        "UnitPrice": rate,
                        "Qty": qty
                    }
                }
            ]
        }
        return payload

    def build_estimate_payload(
        self, 
        vendor_data: VendorDocumentData, 
        sheet_data: SheetOrderData
    ) -> Dict[str, Any]:
        """Build exact Sales Estimate payload required by QBO."""
        qty = sheet_data.quantity
        rate = sheet_data.customer_price
        total = round(qty * rate, 2)
        customer_id = self._get_entity_id("Customer", settings.qbo_default_customer) or "1"
        item_id = self._get_entity_id("Item", sheet_data.item_code) or "1"

        # Auto-generate next Estimate / PI DocNumber if not set in QBO
        next_doc_num = None
        try:
            q_max = "SELECT DocNumber FROM Estimate ORDERBY MetaData.CreateTime DESC MAXRESULTS 10"
            import urllib.parse
            url_max = f"{self.base_url}/query?query={urllib.parse.quote(q_max)}"
            r_max = requests.get(url_max, headers=self._headers(), timeout=10)
            if r_max.status_code == 200:
                est_list = r_max.json().get("QueryResponse", {}).get("Estimate", [])
                nums = [int(e["DocNumber"]) for e in est_list if e.get("DocNumber") and str(e["DocNumber"]).isdigit()]
                if nums:
                    next_doc_num = str(max(nums) + 1)
        except Exception:
            pass

        if not next_doc_num:
            next_doc_num = "1801"

        customer_notes = f"Total: {qty:,.0f} MTS.\n\n{STANDARD_CUSTOMER_NOTE}"

        payload = {
            "DocNumber": next_doc_num,
            "TxnDate": self._format_date(vendor_data.po_date),
            "CustomerRef": {
                "value": customer_id,
                "name": settings.qbo_default_customer
            },
            "CustomerMemo": {
                "value": customer_notes
            },
            "PrivateNote": f"Order #{sheet_data.order_number}",
            "ShipMethodRef": {
                "name": vendor_data.ship_via
            },
            "GlobalTaxCalculation": "NotApplicable",
            "Line": [
                {
                    "DetailType": "SalesItemLineDetail",
                    "Amount": total,
                    "Description": sheet_data.standardized_description,
                    "SalesItemLineDetail": {
                        "ItemRef": {
                            "value": item_id,
                            "name": sheet_data.item_code
                        },
                        "UnitPrice": rate,
                        "Qty": qty
                    }
                }
            ]
        }
        return payload

    def create_transactions(
        self, 
        vendor_data: VendorDocumentData, 
        sheet_data: SheetOrderData
    ) -> QBOResult:
        """Create PO and Estimate transactions."""
        po_payload = self.build_purchase_order_payload(vendor_data, sheet_data)
        est_payload = self.build_estimate_payload(vendor_data, sheet_data)

        if not self.is_live:
            # Simulated execution (returns deterministic sample result matching Order 7207)
            logger.info("Executing in Mock / Sandbox simulation mode.")
            logger.info(f"Generated QBO PO Payload:\n{json.dumps(po_payload, indent=2)}")
            logger.info(f"Generated QBO Estimate Payload:\n{json.dumps(est_payload, indent=2)}")
            return QBOResult(
                purchase_order_id="MOCK-PO-9001",
                purchase_order_number=vendor_data.supplier_po_number,
                estimate_id="MOCK-EST-5001",
                estimate_number="1793",  # Matches completed example in Report 2
                success=True
            )

        # Live QBO execution
        try:
            # 1. Create Purchase Order
            po_resp = requests.post(
                f"{self.base_url}/purchaseorder",
                headers=self._headers(),
                json=po_payload,
                timeout=30
            )
            if po_resp.status_code not in (200, 201):
                err_msg = f"QBO PO creation failed: {po_resp.text}"
                logger.error(err_msg)
                return QBOResult(success=False, error=err_msg)
            
            po_data = po_resp.json().get("PurchaseOrder", {})
            po_id = po_data.get("Id")
            po_num = po_data.get("DocNumber")

            # 2. Attach PDF if present and is actually a PDF file
            if vendor_data.source_file_path and os.path.exists(vendor_data.source_file_path):
                if vendor_data.source_file_path.lower().endswith(".pdf"):
                    self._attach_file_to_qbo("PurchaseOrder", po_id, vendor_data.source_file_path)

            # 3. Create Estimate
            est_resp = requests.post(
                f"{self.base_url}/estimate",
                headers=self._headers(),
                json=est_payload,
                timeout=30
            )
            if est_resp.status_code not in (200, 201):
                err_msg = f"QBO Estimate creation failed: {est_resp.text}"
                logger.error(err_msg)
                return QBOResult(
                    purchase_order_id=po_id,
                    purchase_order_number=po_num,
                    success=False,
                    error=err_msg
                )

            est_data = est_resp.json().get("Estimate", {})
            est_id = est_data.get("Id")
            est_num = est_data.get("DocNumber")

            return QBOResult(
                purchase_order_id=po_id,
                purchase_order_number=po_num,
                estimate_id=est_id,
                estimate_number=est_num,
                success=True
            )

        except Exception as e:
            logger.exception("Unexpected error communicating with QBO")
            return QBOResult(success=False, error=str(e))

    def _attach_file_to_qbo(self, entity_type: str, entity_id: str, file_path: str):
        """Upload file via QBO Attachable API."""
        try:
            upload_url = f"{self.base_url}/upload"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            metadata = {
                "AttachableRef": [{
                    "EntityRef": {"type": entity_type, "value": entity_id}
                }],
                "FileName": os.path.basename(file_path),
                "ContentType": "application/pdf"
            }
            files = {
                "file_metadata_01": (None, json.dumps(metadata), "application/json"),
                "file_content_01": (os.path.basename(file_path), open(file_path, "rb"), "application/pdf")
            }
            requests.post(upload_url, headers=headers, files=files, timeout=30)
            logger.info(f"Attached {file_path} to QBO {entity_type} {entity_id}.")
        except Exception as e:
            logger.warning(f"Could not attach file to QBO: {e}")
