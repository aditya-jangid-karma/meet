"""One-time helper: add the two Qwen vendor-lookup columns to invoices.xlsx
if they are not already there.

PLAIN ENGLISH -- what this does:
  invoice_reader.py can now optionally write two extra columns so a human
  can see exactly what Qwen read off the invoice ("Qwen Vendor (raw)") and
  whether that vendor was auto-matched with confidence or needs a human to
  check it ("Qwen Status"). Those columns only get written if they already
  exist as headers in row 1 of the "Invoices" sheet -- invoice_reader.py
  never creates columns itself. Run this script ONCE against your real
  invoices.xlsx to add whichever of the two headers are missing.

  If both headers are already present, nothing is changed and nothing is
  saved (running this script twice, or against a file that already has the
  columns, is always safe).

Run:
    .venv\\Scripts\\python.exe automation\\add_helper_columns.py --xlsx PATH\\TO\\invoices.xlsx

This file only depends on openpyxl (to open/save the workbook) and the
_key() header-normalisation helper already used by invoice_reader.py, so the
two agree on what counts as "the qwen_vendor_raw column" / "the qwen_status
column".
"""
import argparse
from pathlib import Path

from openpyxl import load_workbook

from invoice_reader import _key

QWEN_VENDOR_RAW_HEADER = "Qwen Vendor (raw)"
QWEN_STATUS_HEADER = "Qwen Status"
QWEN_PROPERTY_RAW_HEADER = "Qwen Property (raw)"
PROPERTY_STATUS_HEADER = "Property Status"


def add_helper_columns(xlsx_path):
    """Open xlsx_path, add whichever of the two helper headers are missing
    to row 1 of the Invoices sheet (or the active sheet if there is no sheet
    named "Invoices"), and save only if something actually changed. Returns
    a list of the header names that were added (empty list = nothing to do)."""
    workbook = load_workbook(xlsx_path)
    sheet = (workbook["Invoices"] if "Invoices" in workbook.sheetnames
             else workbook.active)

    existing_keys = {_key(cell.value) for cell in sheet[1] if cell.value}
    # First empty column right after the last header currently in row 1.
    next_col = max((cell.column for cell in sheet[1] if cell.value),
                   default=0) + 1

    added = []
    if _key(QWEN_VENDOR_RAW_HEADER) not in existing_keys:
        sheet.cell(row=1, column=next_col, value=QWEN_VENDOR_RAW_HEADER)
        added.append(QWEN_VENDOR_RAW_HEADER)
        next_col += 1
    if _key(QWEN_STATUS_HEADER) not in existing_keys:
        sheet.cell(row=1, column=next_col, value=QWEN_STATUS_HEADER)
        added.append(QWEN_STATUS_HEADER)
        next_col += 1
    if _key(QWEN_PROPERTY_RAW_HEADER) not in existing_keys:
        sheet.cell(row=1, column=next_col, value=QWEN_PROPERTY_RAW_HEADER)
        added.append(QWEN_PROPERTY_RAW_HEADER)
        next_col += 1
    if _key(PROPERTY_STATUS_HEADER) not in existing_keys:
        sheet.cell(row=1, column=next_col, value=PROPERTY_STATUS_HEADER)
        added.append(PROPERTY_STATUS_HEADER)
        next_col += 1

    if not added:
        print("nothing to do -- both helper columns are already present.")
        return added

    workbook.save(xlsx_path)
    print(f"Added column(s) to {xlsx_path}: " + ", ".join(added))
    return added


def main():
    parser = argparse.ArgumentParser(
        description="Add the 'Qwen Vendor (raw)' / 'Qwen Status' helper "
                     "columns to invoices.xlsx if they are missing. Safe to "
                     "run more than once.")
    parser.add_argument("--xlsx", type=Path, required=True,
                        help="Path to the invoices.xlsx to update.")
    args = parser.parse_args()

    if not args.xlsx.exists():
        raise SystemExit(f"STOPPED: no spreadsheet at {args.xlsx}")

    add_helper_columns(args.xlsx)


if __name__ == "__main__":
    main()
