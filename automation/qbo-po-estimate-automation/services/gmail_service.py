"""
Gmail Intake & Exception Draft Service.
- Polls Gmail label (e.g. '1. Work Pending/Work Pending - H') for unread or new supplier proforma PDFs.
- Automatically saves exceptions into the Gmail 'Drafts' folder (NEVER sends emails).
"""

import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)

class GmailService:
    def __init__(
        self,
        user: Optional[str] = None,
        password: Optional[str] = None,
        target_label: Optional[str] = None,
        drafts_folder: str = '"[Gmail]/Drafts"'
    ):
        self.user = user or os.getenv("GMAIL_USER", "team@karmags.com")
        self.password = (password or os.getenv("GMAIL_APP_PASSWORD", "")).replace(" ", "")
        self.target_label = target_label or os.getenv("GMAIL_LABEL", "1. Work Pending/Work Pending - H")
        self.drafts_folder = drafts_folder

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Establish authenticated SSL connection to Gmail IMAP."""
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(self.user, self.password)
        return mail

    def create_thread_reply_draft(
        self,
        approved_orders: List[str],
        discrepancies: Optional[List[Dict[str, Any]]] = None,
        to_email: str = "exports@fantasygt.net",
        subject: str = "Re: ORDER 7321 7255 7256 7260 NEW PI TO T3",
        in_reply_to: str = "<SA1PR13MB6541619D8E10DB0E277DAE01A1932@SA1PR13MB6541.namprd13.prod.outlook.com>"
    ) -> bool:
        """
        Creates a draft reply following the exact client communication format:
        'We have made the P/I for Orders X, Y, Z and sent them to T3 for approval.
         For Order No. W, we noticed a difference in quantity and price...'
        """
        try:
            msg = MIMEMultipart()
            msg["To"] = to_email
            msg["From"] = self.user
            msg["Subject"] = subject
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to

            lines = ["Hi Team,\n"]
            if approved_orders:
                orders_str = ", ".join(approved_orders)
                lines.append(f"We have made the P/I for Orders {orders_str} and sent them to T3 for approval.\n")

            if discrepancies:
                for disc in discrepancies:
                    ord_no = disc.get("order_number", "")
                    diff_desc = disc.get("description", "")
                    lines.append(f"For Order No. {ord_no}, we noticed a difference in the order details: {diff_desc}\n")

            lines.append("Please check and confirm.\n")
            lines.append("Thank you.")

            body = "\n".join(lines)
            msg.attach(MIMEText(body, "plain"))

            mail = self._connect()
            try:
                res = mail.append(
                    self.drafts_folder,
                    "\\Draft",
                    imaplib.Time2Internaldate(time.time()),
                    msg.as_bytes()
                )
                logger.info(f"Thread reply draft successfully saved in Gmail: {res}")
                return True
            finally:
                mail.logout()

        except Exception as e:
            logger.error(f"Failed to create thread reply draft: {e}")
            return False

    def fetch_pending_proforma_attachments(
        self,
        download_dir: Path,
        search_query: str = "UNSEEN"
    ) -> List[Dict[str, Any]]:
        """
        Inspects the target label for incoming messages and extracts PDF attachments.
        Returns list of metadata dicts with local file paths.
        """
        download_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []

        mail = self._connect()
        try:
            # Quote the folder name properly for IMAP
            quoted_label = f'"{self.target_label}"'
            status, count = mail.select(quoted_label)
            if status != "OK":
                logger.error(f"Could not select label {quoted_label}")
                return []

            status, data = mail.search(None, search_query)
            if status != "OK" or not data[0]:
                return []

            msg_ids = data[0].split()
            logger.info(f"Found {len(msg_ids)} messages matching '{search_query}' in {self.target_label}")

            for mid in msg_ids:
                status, msg_data = mail.fetch(mid, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode subject
                subject_header = decode_header(msg.get("Subject", "No Subject"))[0]
                if isinstance(subject_header[0], bytes):
                    subject = subject_header[0].decode(subject_header[1] or "utf-8", errors="ignore")
                else:
                    subject = str(subject_header[0])

                from_sender = msg.get("From", "")

                for part in msg.walk():
                    if part.get_content_maintype() == "multipart":
                        continue
                    if part.get("Content-Disposition") is None:
                        continue

                    filename = part.get_filename()
                    if filename and filename.lower().endswith(".pdf"):
                        # Decode attachment filename
                        fn_header = decode_header(filename)[0]
                        if isinstance(fn_header[0], bytes):
                            filename = fn_header[0].decode(fn_header[1] or "utf-8", errors="ignore")

                        safe_filename = f"{mid.decode()}_{filename}"
                        file_path = download_dir / safe_filename

                        with open(file_path, "wb") as f:
                            f.write(part.get_payload(decode=True))

                        logger.info(f"Downloaded PDF attachment: {file_path}")
                        downloaded.append({
                            "message_id": mid.decode(),
                            "subject": subject,
                            "sender": from_sender,
                            "file_path": str(file_path),
                            "filename": filename
                        })

            return downloaded

        finally:
            mail.logout()
