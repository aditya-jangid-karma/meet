"""
Exception Alerting Service.
Dispatches critical exceptions to Slack, Microsoft Teams, or Email.
Fires whenever a validation gate fails or an API call rejects a transaction.
"""

import json
import logging
import requests
from typing import List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

class AlertService:
    def __init__(self):
        self.slack_url = settings.alert_slack_webhook
        self.teams_url = settings.alert_teams_webhook

    def send_validation_failure_alert(
        self, 
        order_number: str, 
        errors: List[str], 
        source_doc: Optional[str] = None
    ):
        """Send an urgent notification for validation gate failures."""
        title = f"⚠️ [PO AUTOMATION ALERT] Order #{order_number} Validation Failed"
        body = (
            f"Automated processing was halted safely. No records were posted to QuickBooks Online.\n\n"
            f"**Order:** #{order_number}\n"
            f"**Source Document:** {source_doc or 'N/A'}\n"
            f"**Violations Detected:**\n" + "\n".join(f"- {err}" for err in errors)
        )
        logger.warning(f"ALERT: {title}\n{body}")

        # Send to Slack if configured
        if self.slack_url:
            try:
                requests.post(self.slack_url, json={"text": f"*{title}*\n{body}"}, timeout=5)
            except Exception as e:
                logger.error(f"Failed to post Slack alert: {e}")

        # Send to Teams if configured
        if self.teams_url:
            try:
                requests.post(self.teams_url, json={"title": title, "text": body}, timeout=5)
            except Exception as e:
                logger.error(f"Failed to post Teams alert: {e}")

        # Automatically Stage a Draft in Gmail (Draft only - never sent)
        try:
            from services.gmail_service import GmailService
            gmail = GmailService()
            gmail.create_exception_draft(
                order_number=order_number,
                errors=errors,
                source_doc_name=source_doc
            )
            logger.info(f"Exception draft safely staged in Gmail Drafts for Order #{order_number}")
        except Exception as e:
            logger.warning(f"Could not stage draft in Gmail: {e}")

    def send_system_error_alert(self, order_number: str, error_msg: str):
        """Send notification for unhandled system or network errors."""
        msg = f"🚨 [PO AUTOMATION SYSTEM ERROR] Order #{order_number}: {error_msg}"
        logger.error(msg)
        if self.slack_url:
            try:
                requests.post(self.slack_url, json={"text": msg}, timeout=5)
            except Exception:
                pass

