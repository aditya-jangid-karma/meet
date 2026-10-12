"""Read invoice PDFs with the local Qwen model and append their details to
invoices.xlsx. Fills only what an invoice actually shows. Property is filled
with the RAW location text Qwen reads (Ship-To preferred) for a human to
confirm; Integration Package is left blank for a human. Never touches Bottomline.

Run (the USER runs this -- it calls the live Qwen on the Mac):
    .venv\\Scripts\\python.exe automation\\invoice_reader.py ^
        --host http://<YOUR-MAC>:11434

Offline preview (no Qwen, no writing):  add --dry-run
"""
import argparse
import base64
import sys
import time
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

from reader_pdf import render_pdf
from reader_qwen import extract_invoice
from reader_qwen_utility import extract_utility_invoice
from utility_lookup import UtilityLookup
from reader_directory import load_known_vendors, match_vendor, _normalise
from vendor_lookup import load_master, load_aliases, load_alias_examples, Lookup
from master_index import build_index, extra_for_confident_match

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
DEFAULT_XLSX = Path(r"Z:\Res-1-indexer\input\invoices.xlsx")
DEFAULT_PDF_DIR = Path(r"Z:\Res-1-indexer\input\pdfs")
MASTERS_DIR = PROJECT / "masters"
VENDORS_CSV = MASTERS_DIR / "vendors.csv"
ALIASES_CSV = MASTERS_DIR / "aliases.csv"
PROPERTIES_CSV = MASTERS_DIR / "properties.csv"
PROPERTY_ALIASES_CSV = MASTERS_DIR / "property_aliases.csv"


def _key(header):
    """'Invoice Due Date' -> 'invoice_due_date'. Mirrors invoice_recorder's
    header_to_key so the two agree on column names."""
    cleaned = "".join(c if (c.isalnum() or c.isspace()) else " "
                      for c in str(header))
    return "_".join(cleaned.lower().split())


def to_base64(png_bytes_list):
    return [base64.b64encode(b).decode("ascii") for b in png_bytes_list]


# Date formats we accept from an invoice, tried in order. US month-first is
# tried before day-first so an ambiguous "07/08/2026" reads as July 8 (the US
# convention Bottomline expects), not August 7.
_DATE_FORMATS = ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%Y-%m-%d", "%Y/%m/%d",
                 "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%d/%m/%Y")


def _to_mmddyyyy(value):
    """Return the date as MM/DD/YYYY. Blank stays blank. A value we cannot
    parse is returned unchanged -- we never invent or reshuffle a date we do
    not understand; it stays visible for a human to fix."""
    if value in (None, ""):
        return value
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return text


def last_data_row(sheet, columns):
    """The highest row that actually holds invoice data.

    openpyxl's `sheet.max_row` counts empty-but-formatted cells, so on a sheet
    with styling/validation reaching far down it reports a row hundreds below
    the real data -- which made the first live run append into that gap. This
    scans the key columns instead and returns the last row with a real value
    (or the header row, 1, when the sheet is empty)."""
    key_cols = [columns[k] for k in ("image_name", "vendor", "invoice_number")
                if k in columns]
    if not key_cols:                       # no recognised headers: use them all
        key_cols = [c.column for c in sheet[1] if c.value]
    last = 1                               # header row
    for row in sheet.iter_rows(min_row=2):
        if any(row[c - 1].value not in (None, "") for c in key_cols):
            last = row[0].row
    return last


def existing_image_names(sheet):
    """Normalised image names already in the sheet (the duplicate guard)."""
    col = None
    for cell in sheet[1]:
        if cell.value and _key(cell.value) == "image_name":
            col = cell.column
            break
    if col is None:
        return set()
    names = set()
    for row in sheet.iter_rows(min_row=2):
        value = row[col - 1].value
        if value not in (None, ""):
            names.add(_normalise(value))
    return names


def append_invoice(sheet, columns, fields, image_name, row,
                   raw_vendor=None, qwen_status=None,
                   raw_property=None, property_status=None,
                   integration_package=None):
    """Write ONE row at `row` (the caller finds it with last_data_row()+1, NOT
    sheet.max_row, which is unreliable). invoice_number is stored as TEXT so
    leading zeros survive; dates are forced to MM/DD/YYYY.

    raw_vendor / qwen_status are the vendor_lookup helper columns
    ("Qwen Vendor (raw)" / "Qwen Status"). raw_property / property_status are the
    matching property helper columns ("Qwen Property (raw)" / "Property Status"),
    and integration_package is the property's package (YARDI/INTACCT) when a
    confident property match gave us one -- a HINT for the recorder, blank on
    review. Every one of these is written ONLY when the sheet actually has that
    column (the skip rule in the write loop)."""
    r = row
    to_write = {
        "image_name": image_name,
        "vendor": fields.get("vendor"),
        "vendor_code": fields.get("vendor_code"),
        "property": fields.get("property"),
        "property_code": fields.get("property_code"),
        "invoice_number": fields.get("invoice_number"),
        "invoice_date": _to_mmddyyyy(fields.get("invoice_date")),
        "invoice_due_date": _to_mmddyyyy(fields.get("due_date")),
        "amount": fields.get("amount"),
        "cycle_from": _to_mmddyyyy(fields.get("service_period_start")),
        "cycle_to": _to_mmddyyyy(fields.get("service_period_end")),
        "late_fee": fields.get("late_fee"),
        "gl_code": fields.get("gl_code"),
        "account_number": fields.get("account_number"),
        "service_address": fields.get("service_address"),
        "integration_package": integration_package,
        "qwen_vendor_raw": raw_vendor,
        "qwen_status": qwen_status,
        "qwen_property_raw": raw_property,
        "property_status": property_status,
    }
    for key, value in to_write.items():
        if value in (None, "") or key not in columns:
            continue
        cell = sheet.cell(row=r, column=columns[key], value=str(value))
        if key == "invoice_number":
            cell.number_format = "@"   # keep 007458 as text, not 7458


def _columns(sheet):
    return {_key(c.value): c.column for c in sheet[1] if c.value}


def main():
    parser = argparse.ArgumentParser(
        description="Read invoice PDFs with local Qwen; fill invoices.xlsx.")
    parser.add_argument("--host", default=None,
                        help="Ollama address on the Mac, e.g. "
                             "http://192.168.1.42:11434. Required unless --dry-run.")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR,
                        help="Folder of invoice PDFs. Default: the mapped drive.")
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX,
                        help="invoices.xlsx to append to. Default: mapped drive.")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--poppler-path", default=None,
                        help="Poppler bin folder, if it is not on PATH.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only read this many PDFs. Use for a first test.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List the PDFs that would be read. No Qwen, no write.")
    parser.add_argument("--utility", action="store_true",
                        help="Process files as Utility Bills (Pepco, Gas, Water, etc.).")
    args = parser.parse_args()

    if not args.pdf_dir.exists():
        sys.exit(f"STOPPED: no PDF folder at {args.pdf_dir}")
    if not args.xlsx.exists():
        sys.exit(f"STOPPED: no spreadsheet at {args.xlsx}")
    if not args.dry_run and not args.host:
        sys.exit("STOPPED: --host is required for a real run (or use --dry-run).")

    workbook = load_workbook(args.xlsx)
    sheet = (workbook["Invoices"] if "Invoices" in workbook.sheetnames
             else workbook.active)
    columns = _columns(sheet)
    seen = existing_image_names(sheet)

    all_pdfs = sorted(p for p in args.pdf_dir.glob("*.pdf"))
    if not all_pdfs:
        sys.exit(f"STOPPED: no PDFs found in {args.pdf_dir}")

    # Prioritize unseen PDFs so --limit tests actually process new files
    unseen_pdfs = [p for p in all_pdfs if _normalise(p.stem) not in seen]
    if unseen_pdfs:
        pdfs = unseen_pdfs[:args.limit] if args.limit is not None else unseen_pdfs
    else:
        pdfs = all_pdfs[:args.limit] if args.limit is not None else all_pdfs

    master_rows = load_master(VENDORS_CSV)
    aliases = load_aliases(ALIASES_CSV)
    # Feed a few of the most-repeated past corrections into the Qwen prompt
    # itself, so it stops making the same misread at the source. This is a
    # nudge only -- the Lookup below still validates whatever Qwen returns.
    alias_examples = load_alias_examples(ALIASES_CSV, limit=5)
    lookup = None
    known = None
    if master_rows:
        lookup = Lookup(master_rows, aliases, code_col="ERP Vendor ID")
    else:
        print(f"\n*** WARNING: could not read the vendor master at "
              f"{VENDORS_CSV} (missing or empty). Falling back to the OLD "
              "vendor matching (known vendors already in this spreadsheet) "
              "so this run does not crash. Ask Puneet/Manish to check the "
              "masters folder. ***\n")
        known = load_known_vendors(args.xlsx)

    property_rows = load_master(PROPERTIES_CSV, name_col="Property Name")
    property_lookup = None
    package_index = {}
    if property_rows:
        property_aliases = load_aliases(PROPERTY_ALIASES_CSV)
        property_lookup = Lookup(property_rows, property_aliases,
                                 name_col="Property Name",
                                 code_col="Property Code")
        package_index = build_index(property_rows, "Property Name", "Package")
    else:
        print(f"\n*** NOTE: no property master at {PROPERTIES_CSV}; property "
              "is written RAW for review and Integration Package left blank "
              "(today's behaviour). ***\n")

    utility_lookup = None
    if args.utility:
        utility_lookup = UtilityLookup(MASTERS_DIR)
        print("  [Mode: UTILITY BILLS ACTIVE - Using address & unit crosswalk]")

    if args.dry_run:
        print(f"\nDRY RUN -- {len(pdfs)} PDF(s) in {args.pdf_dir}. Nothing "
              "sent to Qwen, nothing written.\n")
        for pdf in pdfs:
            mark = "  (already recorded -- would skip)" if _normalise(
                pdf.stem) in seen else ""
            print(f"  {pdf.name}{mark}")
        return

    review, written, skipped = [], 0, 0
    per_invoice_times = []                          # seconds per PDF actually read
    next_row = last_data_row(sheet, columns) + 1   # right after the visible data
    batch_start = time.perf_counter()
    for pdf in pdfs:
        image_name = pdf.stem
        if _normalise(image_name) in seen:
            skipped += 1
            continue
        started = time.perf_counter()               # stopwatch: render + Qwen call
        images = to_base64(render_pdf(pdf, dpi=args.dpi,
                                      max_pages=args.max_pages,
                                      poppler_path=args.poppler_path))
        if args.utility:
            fields = extract_utility_invoice(args.host, images, alias_examples=alias_examples)
        else:
            fields = extract_invoice(args.host, images, alias_examples=alias_examples)
        elapsed = time.perf_counter() - started
        per_invoice_times.append(elapsed)
        if fields is None:
            review.append(pdf.name)
            print(f"  review: {pdf.name} (Qwen reply unusable)  [{elapsed:.1f}s]")
            continue

        raw_vendor = fields.get("vendor")
        if lookup is not None:
            m = lookup.match(raw_vendor)
            fields["vendor"] = m.value   # canonical only when READ_OK
            fields["vendor_code"] = m.code
            qwen_status = m.status
        else:
            canonical = match_vendor(raw_vendor, known)
            if canonical:
                fields["vendor"] = canonical
                qwen_status = "READ_OK"
            else:
                qwen_status = "NEEDS_REVIEW"

        raw_property = fields.get("property")
        property_status = None
        package = None

        if args.utility:
            # 1. Format Invoice Number: <Account>-<YYYYMMDD>
            acct = str(fields.get("account_number") or "").strip()
            inv_dt = fields.get("invoice_date")
            parsed_dt = None
            if inv_dt:
                for fmt in _DATE_FORMATS:
                    try:
                        parsed_dt = datetime.strptime(str(inv_dt).strip(), fmt)
                        break
                    except ValueError:
                        pass
            if acct and parsed_dt:
                fields["invoice_number"] = f"{acct}-{parsed_dt.strftime('%Y%m%d')}"
            elif acct:
                fields["invoice_number"] = acct

            # 2. Assign Amount (Current Charges)
            curr = fields.get("current_charges") or fields.get("amount")
            fields["amount"] = str(curr).replace("$", "").replace(",", "").strip() if curr else ""

            # 3. Match Property using Service Address
            srv_addr = fields.get("service_address") or raw_property
            raw_property = srv_addr
            if utility_lookup is not None and srv_addr:
                um = utility_lookup.match(srv_addr, utility_type=fields.get("utility_type"))
                fields["property"] = um.property_name
                fields["property_code"] = um.property_code
                package = um.integration_package
                property_status = um.status
                if um.gl_code:
                    fields["gl_code"] = um.gl_code

            # 4. Default GL code fallback based on utility type
            if not fields.get("gl_code"):
                u_type = str(fields.get("utility_type") or "").lower()
                if "elec" in u_type:
                    fields["gl_code"] = "436313"
                elif "gas" in u_type:
                    fields["gl_code"] = "436323"
                elif "water" in u_type or "sewer" in u_type:
                    fields["gl_code"] = "436311"
        else:
            if property_lookup is not None and raw_property:
                pm = property_lookup.match(raw_property)
                fields["property"] = pm.value          # canonical only when READ_OK
                fields["property_code"] = pm.code
                property_status = pm.status
                package = extra_for_confident_match(pm, package_index) or None

        append_invoice(sheet, columns, fields, image_name, next_row,
                       raw_vendor=raw_vendor, qwen_status=qwen_status,
                       raw_property=raw_property, property_status=property_status,
                       integration_package=package)
        next_row += 1
        seen.add(_normalise(image_name))
        written += 1
        print(f"  filled: {pdf.name} -> {fields['vendor']}  [{elapsed:.1f}s]")

    workbook.save(args.xlsx)
    batch_elapsed = time.perf_counter() - batch_start
    print(f"\nDone. {written} written, {skipped} already-recorded skipped, "
          f"{len(review)} sent to human review.")
    processed = len(per_invoice_times)
    if processed:
        average = sum(per_invoice_times) / processed
        print(f"Time: {batch_elapsed:.1f}s total for {processed} invoice(s) "
              f"actually read -- {average:.1f}s average "
              f"(fastest {min(per_invoice_times):.1f}s, "
              f"slowest {max(per_invoice_times):.1f}s). "
              "Skipped duplicates are not counted; they never reach Qwen.")
    if review:
        print("Human review (Qwen reply unusable): " + ", ".join(review))
    print("Property is matched to masters\\properties.csv when possible "
          "(canonical name + Integration Package hint); anything uncertain is "
          "written RAW with Property Status = NEEDS_REVIEW for you to confirm. "
          "Then run invoice_recorder.py.")


if __name__ == "__main__":
    main()
