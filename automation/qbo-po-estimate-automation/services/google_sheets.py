import os
import logging
from typing import Optional, Dict, Any, List

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

from core.models import SheetOrderData
from config.settings import settings

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    """
    Connects to Google Sheets API or falls back to an in-memory/file mock for testing.
    Supports Fantasy Global, Ruby Global, and Selecta Global workbooks.
    """

    def __init__(self, spreadsheet_id: Optional[str] = None, entity: str = "fantasy"):
        self.entity = entity.lower()
        if spreadsheet_id:
            self.spreadsheet_id = spreadsheet_id
        else:
            self.spreadsheet_id = settings.entity_sheets.get(self.entity, settings.google_sheet_fantasy_id)
            
        self.tab_name = settings.google_sheet_tab_name
        self.service = None
        self._mock_data: Dict[str, SheetOrderData] = {}

        # Initialize mock database with Order 7207 from the SOP
        self._init_default_sample_order()

        # Try initializing Google Sheets API client if credentials exist
        creds_file = settings.google_service_account_file
        if os.path.exists(creds_file) and self.spreadsheet_id:
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                creds = service_account.Credentials.from_service_account_file(
                    creds_file,
                    scopes=["https://www.googleapis.com/auth/spreadsheets"]
                )
                self.service = build("sheets", "v4", credentials=creds)
                logger.info(f"Google Sheets API authenticated for entity '{self.entity}' (Sheet ID: {self.spreadsheet_id}).")
            except Exception as e:
                logger.warning(f"Failed to authenticate Google Sheets API: {e}. Running in local mock mode.")

    def _init_default_sample_order(self):
        """Seed default sample from Report 2 (Order 7207, Row 638)."""
        self._mock_data["7207"] = SheetOrderData(
            order_number="7207",
            supplier_name="A-TEX INTERNATIONAL CO., LIMITED",
            item_code="AT-2080-1",
            standardized_description='TEXTILES / ORDER#7207 / 92%RAYON - 8%POLYESTER / 280-295GM / 58/59"',
            quantity=22400.0,
            supplier_price=1.30,
            customer_price=1.85,
            pi_number="1793",
            row_index=638,
            status="Ok, Made P/I and sent it T3 for approval"
        )

    def find_order_by_number(self, order_number: str) -> Optional[SheetOrderData]:
        """
        Locate the order row in the PROFORMAS tab using the Order #.
        """
        clean_order = str(order_number).strip()

        # If live API is connected
        if self.service and self.spreadsheet_id:
            try:
                range_name = f"{self.tab_name}!A1:N2000"
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name
                ).execute()
                rows = result.get("values", [])

                # Search through rows for order number in Column B (index 1)
                for idx, row in enumerate(rows, start=1):
                    if len(row) > 1 and str(row[1]).strip() == clean_order:
                        return self._map_row_to_order_data(row, idx)
            except Exception as e:
                logger.error(f"Error fetching row from Google Sheets: {e}")

        # Fallback to local store / mock
        if clean_order in self._mock_data:
            return self._mock_data[clean_order]

        return None

    def update_estimate_number(self, order_number: str, estimate_number: str, row_index: Optional[int] = None) -> bool:
        """
        Write the newly generated Estimate/PI # back into the existing sheet cell (Col K).
        Does not touch any other column or add new headers.
        """
        clean_order = str(order_number).strip()
        logger.info(f"Updating Estimate/PI #{estimate_number} for Order #{clean_order} in G Sheet.")

        # Update local mock
        if clean_order in self._mock_data:
            self._mock_data[clean_order].pi_number = estimate_number
            self._mock_data[clean_order].status = "PROCESSED"

        # Update live sheet if configured
        if self.service and self.spreadsheet_id and row_index:
            try:
                target_cell = f"{self.tab_name}!{settings.google_sheet_estimate_col}{row_index}"
                body = {"values": [[str(estimate_number)]]}
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=target_cell,
                    valueInputOption="USER_ENTERED",
                    body=body
                ).execute()
                logger.info(f"Live Cell {target_cell} updated with {estimate_number}.")
                return True
            except Exception as e:
                logger.error(f"Failed to update Google Sheet cell: {e}")
                return False

        return True

    def _map_row_to_order_data(self, row: List[Any], row_idx: int) -> SheetOrderData:
        """
        Verified column positions from PROFORMAS tab:
        0: SUPPLIER (Col A)
        1: ORDER (Col B)
        2: FABRIC NAME (Col C)
        3: QUANTITY (Col D)
        4: ITEM (Col E)
        5: DESCRIPTION (Col F)
        6: SUPPLIER PRICE (Col G)
        9: T3 PRICE (Col J)
        10: PROFORMA INVOICE (Col K)
        12: STATUS (Col M)
        """
        def clean_float(val: Any) -> float:
            if not val:
                return 0.0
            cleaned = str(val).replace("USD", "").replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0

        return SheetOrderData(
            order_number=str(row[1]).strip() if len(row) > 1 else "",
            supplier_name=str(row[0]).strip() if len(row) > 0 else "",
            item_code=str(row[4]).strip() if len(row) > 4 else "",
            standardized_description=str(row[5]).strip() if len(row) > 5 else "",
            quantity=clean_float(row[3]) if len(row) > 3 else 0.0,
            supplier_price=clean_float(row[6]) if len(row) > 6 else 0.0,
            customer_price=clean_float(row[9]) if len(row) > 9 else 0.0,
            pi_number=str(row[10]).strip() if len(row) > 10 else None,
            status=str(row[12]).strip() if len(row) > 12 else None,
            row_index=row_idx
        )
