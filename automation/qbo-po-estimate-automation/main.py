"""
CLI entry point for the QBO PO & Estimate Automation system.
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pipeline.orchestrator import OrderProcessingPipeline
from services.audit_logger import AuditLogger

def print_banner():
    print("=" * 70)
    print("   QBO PURCHASE ORDER & ESTIMATE AUTOMATION SYSTEM   ")
    print("   Aligned with SOP & Automation Plan (Reports 1 & 2) ")
    print("=" * 70)

def run_sample():
    print_banner()
    sample_file = PROJECT_ROOT / "samples" / "sample_order_7207.json"
    print(f"\n[+] Running pilot processing with SOP Reference Sample:")
    print(f"    File: {sample_file}\n")

    pipeline = OrderProcessingPipeline()
    result = pipeline.process_file(str(sample_file))

    print(f"\n--- EXECUTION REPORT [Run ID: {result.run_id}] ---")
    print(f"Status:       {result.status}")
    print(f"Order #:      {result.order_number}")
    print(f"Sheet Cell:   Updated = {result.sheet_updated}")
    
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        
    if result.validation_report:
        print("\n[Validation Gates Breakdown]:")
        for g in result.validation_report.gates:
            icon = "PASS" if g.passed else "FAIL"
            print(f"  [{icon}] {g.gate_name}: {g.message}")

    if result.qbo_result and result.qbo_result.success:
        print("\n[QuickBooks Online Records Created]:")
        print(f"  - Purchase Order #: {result.qbo_result.purchase_order_number} (ID: {result.qbo_result.purchase_order_id})")
        print(f"  - Estimate/PI #:    {result.qbo_result.estimate_number} (ID: {result.qbo_result.estimate_id})")

    print(f"\nResult Message: {result.message}\n")
    print("=" * 70)

def process_custom_file(file_path: str):
    print_banner()
    p = Path(file_path)
    if not p.exists():
        print(f"Error: File '{file_path}' does not exist.")
        return

    print(f"\n[+] Processing document: {file_path}")
    pipeline = OrderProcessingPipeline()
    result = pipeline.process_file(str(p))

    print(f"\nStatus: {result.status}")
    print(f"Message: {result.message}")

def list_runs():
    print_banner()
    audit = AuditLogger()
    runs = audit.get_runs(limit=10)
    print(f"\n[Latest Automation Control Log Entries ({len(runs)})]:")
    for r in runs:
        print(f"  [{r['timestamp']}] Run: {r['run_id']} | Order #{r['order_number']} | Status: {r['status']} | Estimate #: {r['estimate_number']}")

def poll_gmail_inbox(download_dir_path: str = "downloads/incoming"):
    print_banner()
    from services.gmail_service import GmailService
    gmail = GmailService()
    dl_path = PROJECT_ROOT / download_dir_path
    print(f"\n[+] Checking Gmail label: '{gmail.target_label}'")
    print(f"    Account: {gmail.user}")
    print(f"    Destination: {dl_path}\n")

    # Fetch unseen PDFs from Work Pending - H
    attachments = gmail.fetch_pending_proforma_attachments(dl_path, search_query="UNSEEN")
    if not attachments:
        # Fallback to checking ALL if no UNSEEN
        print("    No UNSEEN emails with PDF found. Searching recent messages...")
        attachments = gmail.fetch_pending_proforma_attachments(dl_path, search_query="ALL")

    print(f"Found {len(attachments)} PDF attachment(s) to process.")
    pipeline = OrderProcessingPipeline()
    for att in attachments:
        print(f"\n--- Processing: {att['filename']} from {att['sender']} ---")
        res = pipeline.process_file(att["file_path"])
        print(f"Order #{res.order_number} -> Status: {res.status}")
        if res.qbo_result and res.qbo_result.success:
            print(f"  PO Created: #{res.qbo_result.purchase_order_number}")
            print(f"  Estimate Created: #{res.qbo_result.estimate_number}")
        elif res.validation_report and not res.validation_report.all_passed:
            print(f"  [HALTED] Validation gate failed. Draft staged in Gmail.")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "run-sample":
        run_sample()
    elif args[0] == "process" and len(args) > 1:
        process_custom_file(args[1])
    elif args[0] == "poll-gmail":
        poll_gmail_inbox()
    elif args[0] == "history" or args[0] == "list-runs":
        list_runs()
    else:
        print("Usage:")
        print("  python main.py poll-gmail         # Poll '1. Work Pending/Work Pending - H' for proformas")
        print("  python main.py run-sample         # Run sample Order 7207 test")
        print("  python main.py process <file_path> # Process custom PDF/JSON")
        print("  python main.py history            # View audit control log")

