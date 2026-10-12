"""
Configuration and settings management for the PO & Estimate Automation system.
"""

import os
from pathlib import Path
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    BASE_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Standard production conditions note from SOP (Report 2, Section 5)
STANDARD_CUSTOMER_NOTE = (
    "Note: We will only start production after these points are met without exception.\n"
    "1) The PI must be signed by the buyer\n"
    "2) All the lab dips must be approved\n"
    "3) Please send us the detail of how the rolls or bales should be labeled\n"
    "4) All quantities have a tolerance of +-10% in quantity and weight.\n\n"
    "FOB USD, SHANGHAI-CHINA"
)

@dataclass
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # Azure Document Intelligence
    azure_doc_intel_endpoint: str = os.getenv("AZURE_DOC_INTEL_ENDPOINT", "")
    azure_doc_intel_key: str = os.getenv("AZURE_DOC_INTEL_KEY", "")
    azure_doc_intel_model_id: str = os.getenv("AZURE_DOC_INTEL_MODEL_ID", "prebuilt-purchaseOrder")

    # Google Sheets Multi-Entity IDs
    google_sheet_fantasy_id: str = os.getenv("GOOGLE_SHEET_FANTASY_ID", "1g9UyidKDODlTKgC8n7u1sMP4IqcMrw0-vMnSgGOuYKU")
    google_sheet_ruby_id: str = os.getenv("GOOGLE_SHEET_RUBY_ID", "1e6hiaiT5m6oUfpdGIiuzm5Ax4bjK6ae6kF75VkkNLl4")
    google_sheet_selecta_id: str = os.getenv("GOOGLE_SHEET_SELECTA_ID", "1uwExZrqhJ4ih2p46KcteT2n1-L9jn3TKKWRKJCTSiTY")

    google_sheet_tab_name: str = os.getenv("GOOGLE_SHEET_TAB_NAME", "PROFORMAS")
    google_service_account_file: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE", 
        str(BASE_DIR / "credentials" / "google_service_account.json")
    )
    # Verified live columns from PROFORMAS tab:
    google_sheet_supplier_col: str = "A"
    google_sheet_order_col: str = "B"
    google_sheet_fabric_col: str = "C"
    google_sheet_qty_col: str = "D"
    google_sheet_item_col: str = "E"
    google_sheet_desc_col: str = "F"
    google_sheet_cost_col: str = "G"
    google_sheet_cust_price_col: str = "J"
    google_sheet_estimate_col: str = "K"   # PROFORMA INVOICE column
    google_sheet_status_col: str = "M"

    # Entity to Sheet ID Map
    @property
    def entity_sheets(self) -> dict:
        return {
            "fantasy": self.google_sheet_fantasy_id,
            "ruby": self.google_sheet_ruby_id,
            "selecta": self.google_sheet_selecta_id,
        }

    # Entity to Email Domain Map
    @property
    def entity_emails(self) -> dict:
        return {
            "fantasygt.net": "fantasy",
            "rubygt.com": "ruby",
            "selectaglobalgroup.com": "selecta",
        }

    # QuickBooks Online
    qbo_environment: str = os.getenv("QBO_ENVIRONMENT", "sandbox")
    qbo_client_id: str = os.getenv("QBO_CLIENT_ID", "")
    qbo_client_secret: str = os.getenv("QBO_CLIENT_SECRET", "")
    qbo_realm_id: str = os.getenv("QBO_REALM_ID", "")
    qbo_refresh_token: str = os.getenv("QBO_REFRESH_TOKEN", "")
    qbo_access_token: str = os.getenv("QBO_ACCESS_TOKEN", "")
    qbo_default_customer: str = os.getenv("QBO_DEFAULT_CUSTOMER_NAME", "T3 TEXTILES S.A.S")
    qbo_shipping_terms: str = os.getenv("QBO_SHIPPING_TERMS_DEFAULT", "FOB USD, SHANGHAI-CHINA")

    # Database & Logs
    db_path: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "control_log.db"))

    # Alerting
    alert_email: str = os.getenv("ALERT_NOTIFICATION_EMAIL", "")
    alert_slack_webhook: str = os.getenv("ALERT_SLACK_WEBHOOK_URL", "")
    alert_teams_webhook: str = os.getenv("ALERT_TEAMS_WEBHOOK_URL", "")

settings = Settings()
