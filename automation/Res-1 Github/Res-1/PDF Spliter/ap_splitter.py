"""
AP Splitter — inbox to split invoices, end to end
================================================
Takes each PDF from 01_Inbox, asks the local Qwen vision model about every page,
works out how many invoices the file contains and where each one starts, splits
them into separate PDFs named Vendor_InvoiceNumber.pdf, files them in 03_Output,
moves the original to 05_Archive, and records every invoice in a register.

Anything it cannot classify safely goes to 04_Review whole, unsplit, with a note
saying why. It is always better to hand a file back to a human than to guess.

THE ONE RULE THAT NEVER CHANGES:
    An original PDF is never edited, overwritten or deleted. Originals are only
    ever MOVED, intact, into 05_Archive. Every output is a brand new file.

Run:
    python ap_splitter.py                 process everything in 01_Inbox
    python ap_splitter.py --use-cache     reuse saved AI answers (development)

Settings live in ap_splitter.config.json beside this script.
Needs: Poppler, Ollama running locally, and `pip install pypdf openpyxl`.
"""

import os
import re
import csv
import sys
import json
import time
import base64
import shutil
import hashlib
import argparse
import tempfile
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent


# ===========================================================================
# SECTION 1 — CONFIG
# Plain English: one settings file, ap_splitter.config.json, sitting beside
# this script. Deliberately NOT called config.json - that name belongs to the
# older invoice_boundary_detector.py and holds completely different settings.
# An environment variable beats the file, so a different machine can be
# pointed somewhere else without editing anything.
# ===========================================================================

FOLDERS = {
    "inbox": "01_Inbox",
    "processing": "02_Processing",
    "output": "03_Output",
    "review": "04_Review",
    "archive": "05_Archive",
    "reports": "06_Reports",
}


def load_config() -> dict:
    path = SCRIPT_DIR / "ap_splitter.config.json"
    if not path.exists():
        sys.exit(f"\nSettings file not found: {path}\n")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Environment wins over the file, so this machine's values never get stuck
    # inside the settings file when the component moves elsewhere.
    cfg["root"] = os.environ.get("AP_SPLITTER_ROOT", cfg.get("root", ""))
    cfg["poppler_path"] = os.environ.get("POPPLER_PATH", cfg.get("poppler_path") or "")
    cfg["ollama_host"] = os.environ.get("OLLAMA_HOST", cfg.get("ollama_host", "http://localhost:11434"))
    cfg["model"] = os.environ.get("QWEN_MODEL", cfg.get("model", "qwen2.5vl:7b"))

    if not cfg["root"]:
        sys.exit("\n'root' is not set in ap_splitter.config.json.\n")
    return cfg


def folder(cfg: dict, key: str) -> Path:
    return Path(cfg["root"]) / FOLDERS[key]


def check_folders(cfg: dict) -> None:
    """Every folder must already exist. We do not invent folders - a missing
    one usually means the root is pointed at the wrong place."""
    missing = [str(folder(cfg, k)) for k in FOLDERS if not folder(cfg, k).is_dir()]
    if missing:
        sys.exit("\nThese folders are missing:\n  " + "\n  ".join(missing) +
                 f"\n\nCheck 'root' in ap_splitter.config.json (currently {cfg['root']}).\n")


# ===========================================================================
# SECTION 2 — RENDER (Poppler)
# Plain English: turn each page of the PDF into a PNG image. Qwen cannot read
# a PDF - it can only look at pictures. The original PDF is only ever READ.
# ===========================================================================

def find_pdftoppm(poppler_dir: str) -> str:
    if poppler_dir:
        found = shutil.which("pdftoppm", path=poppler_dir)
        if not found:
            sys.exit(f"\npdftoppm not found in: {poppler_dir}\n"
                     f"'poppler_path' must be the bin folder holding pdftoppm.\n")
        return found
    found = shutil.which("pdftoppm")
    if not found:
        sys.exit("\npdftoppm not found on PATH, and 'poppler_path' is empty in the settings file.\n")
    return found


def render_pages(pdf_path: Path, out_dir: Path, dpi: int, pdftoppm: str) -> list:
    """Render every page to PNG. Returns [(page_number, image_path), ...]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [pdftoppm, "-png", "-r", str(dpi), str(pdf_path), str(out_dir / "page")]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Poppler failed (exit {result.returncode}): {result.stderr.strip()}")

    images = list(out_dir.glob("page*.png"))
    if not images:
        raise RuntimeError("Poppler produced no page images")

    def page_num(p: Path) -> int:
        m = re.search(r"(\d+)$", p.stem)
        return int(m.group(1)) if m else 0

    return [(page_num(p), p) for p in sorted(images, key=page_num)]


# ===========================================================================
# SECTION 3 — THE PROMPT
# Plain English: what we ask about ONE page image.
#
# Field order is deliberate. The model answers one field at a time and what it
# has already written steers what comes next, so it must WRITE DOWN what it
# sees - heading, the label beside the main number, the invoice numbers listed
# - BEFORE it classifies. Evidence first, verdict last. When page_type came
# first, the model called a remittance stub an invoice.
#
# The giveaway on these documents is the label on the main number: a real
# invoice says "Invoice Number", a summary page says "Summary Number".
# ===========================================================================

PROMPT = """You are looking at ONE page from a document. Look only at this page.

Fill in these fields IN THE ORDER GIVEN. Return ONLY a JSON object with exactly
these keys:

1. "document_heading" - the large heading printed on the page, copied exactly.
   Examples: "Remittance", "Extended Summary", "Invoice", "Statement".
   Use null if the page has no such heading.

2. "primary_number_label" - the LABEL printed beside the page's main reference
   number, copied exactly. Examples: "Invoice Number", "Invoice #",
   "Summary Number", "Summary #", "Statement Number".

3. "primary_number" - the number that label refers to.

4. "invoice_numbers_listed" - a JSON array of EVERY distinct invoice number
   appearing anywhere on this page, including inside any table or list.
   Use [] if there are none.

5. "page_type" - decide using ONLY what you wrote in fields 1 to 4, checking
   these in order and stopping at the first match:
   - "document_heading" contains Remittance, Summary, Statement or Index
     -> "SUMMARY"
   - "primary_number_label" contains Summary, Statement or Remittance
     -> "SUMMARY"
   - "invoice_numbers_listed" holds 2 or more numbers -> "SUMMARY"
   - the page carries on line items from an earlier page, with no heading and
     no new invoice number -> "CONTINUATION"
   - "primary_number_label" refers to an Invoice and this page is one single
     invoice -> "INVOICE"
   - anything else -> "OTHER"

6. "vendor" - the company that ISSUED this document: the seller, the party
   being paid, the "remit to" payee. It is NOT the customer. Do NOT return the
   name beside "Bill To", "Sold To", "Ship To", "Customer" or "Attention". The
   seller is normally the company whose logo is at the top of the page.

7. "invoice_number" - if "page_type" is "INVOICE", the invoice number for this
   one invoice. Otherwise null.

8. "invoice_total" - if "page_type" is "INVOICE", the amount due for this one
   invoice, digits and decimal point only, no currency symbol and no thousands
   separator. Otherwise null.

Return the JSON object and nothing else."""


def ask_qwen(image_path: Path, cfg: dict) -> dict:
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": cfg["model"],
        "prompt": PROMPT,
        "images": [b64],
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": cfg.get("num_ctx", 8192),
            "temperature": 0,          # deterministic - same page, same answer
        },
    }
    req = urllib.request.Request(
        f"{cfg['ollama_host'].rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("timeout", 300)) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        sys.exit(f"\nOllama returned HTTP {e.code}:\n{detail}\n"
                 f"If it says 'model not found', check the tag with: ollama list\n")
    except urllib.error.URLError as e:
        sys.exit(f"\nCould not reach Ollama at {cfg['ollama_host']}: {e.reason}\n"
                 f"Check Ollama is running:  ollama list\n")

    raw = body.get("response", "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_unparsed": raw}      # keep the evidence, never hide it


# ===========================================================================
# SECTION 4 — ENFORCE THE PAGE TYPE
# Plain English: the model's job is to READ what is printed. Deciding what it
# means is Python's job, so the answer is the same every time. If the model
# reports a heading of "Remittance" and still calls the page an invoice,
# Python corrects it and SAYS SO - the disagreement is printed, never hidden.
# ===========================================================================

SUMMARY_WORDS = ("remittance", "summary", "statement", "index")


def enforce_page_type(data: dict, open_invoice: str | None = None):
    model_said = str(data.get("page_type") or "").upper()
    heading = str(data.get("document_heading") or "")
    label = str(data.get("primary_number_label") or "")
    listed = data.get("invoice_numbers_listed")
    listed = listed if isinstance(listed, list) else []

    # CONTINUITY WINS.
    # Plain English: if this page carries the number of the invoice we are
    # already inside, it is part of that invoice - no matter what else is
    # printed on it. The back page of an invoice often reprints engineers'
    # notes full of building numbers, and the model sometimes files those under
    # "invoice numbers"; the summary rule below then threw the page away and
    # the invoice silently lost its totals page. The page told us which invoice
    # it belonged to, so we believe that over everything else.
    number = data.get("invoice_number") or data.get("primary_number")
    if open_invoice and number and str(number).strip() == str(open_invoice).strip():
        return "INVOICE", None

    if any(w in heading.lower() for w in SUMMARY_WORDS):
        reason = f'heading is "{heading}"'
    elif any(w in label.lower() for w in SUMMARY_WORDS):
        reason = f'main number is labelled "{label}"'
    elif len(listed) >= 2:
        reason = f"{len(listed)} invoice numbers listed on the page"
    else:
        return model_said, None

    if model_said == "SUMMARY":
        return "SUMMARY", None
    return "SUMMARY", f"model said {model_said or '?'}, but {reason}"


# ===========================================================================
# SECTION 5 — ASSEMBLE
# Plain English: the model only ever sees one page, so it cannot know where an
# invoice ENDS. Python works that out. First we find the pages where a new
# invoice STARTS. Then each invoice runs from its start page up to the page
# before the next invoice starts - minus any summary pages sitting at the end,
# which belong to no invoice.
# ===========================================================================

def assemble(page_results: list) -> list:
    types = {pno: str(d.get("page_type") or "").upper() for pno, d in page_results}
    all_pages = [pno for pno, _ in page_results]

    starts, open_number = [], None
    for page_no, data in page_results:
        ptype = types[page_no]
        if ptype == "INVOICE":
            number = data.get("invoice_number")
            # A repeat of the number we are already inside is the same invoice
            # carrying on, not a new one.
            if open_number is None or not number or number != open_number:
                starts.append((page_no, data))
                open_number = number
        elif ptype == "SUMMARY":
            open_number = None

    invoices = []
    for i, (start_page, data) in enumerate(starts):
        next_start = starts[i + 1][0] if i + 1 < len(starts) else None
        span = [p for p in all_pages
                if p >= start_page and (next_start is None or p < next_start)]
        # Trailing summary pages belong to no invoice - drop them from the end.
        while len(span) > 1 and types.get(span[-1]) == "SUMMARY":
            span.pop()
        invoices.append({
            "invoice_number": data.get("invoice_number"),
            "vendor": data.get("vendor"),
            "total": data.get("invoice_total"),
            "pages": span,
        })
    return invoices


def classify_source(invoices: list) -> str:
    if len(invoices) == 1:
        return "SINGLE_INVOICE"
    vendors = {(inv.get("vendor") or "").strip().lower() for inv in invoices}
    vendors.discard("")
    return "MULTI_INVOICE_ONE_VENDOR" if len(vendors) <= 1 else "MULTI_INVOICE_MANY_VENDORS"


# ===========================================================================
# SECTION 6 — SAFETY CHECKS (the gate to 04_Review)
# Plain English: reasons to refuse to split. These are things PYTHON can check
# about the model's answer - not the model's own confidence, which was
# confidently wrong on the very first test run. When in doubt, a human looks.
# ===========================================================================

def find_problems(page_results: list, invoices: list, page_count: int) -> list:
    problems = []

    unparsed = [p for p, d in page_results if "_unparsed" in d]
    if unparsed:
        problems.append(f"model did not return valid JSON for page(s): "
                        f"{', '.join(str(p) for p in unparsed)}")

    if len(page_results) != page_count:
        problems.append(f"analysed {len(page_results)} pages but the PDF has {page_count}")

    if not invoices:
        problems.append("no invoices identified in this file")

    for inv in invoices:
        where = f"pages {', '.join(str(p) for p in inv['pages'])}"
        number = (inv.get("invoice_number") or "").strip()
        vendor = (inv.get("vendor") or "").strip()
        if not number:
            problems.append(f"invoice at {where} has no invoice number")
        elif len(number) < 3:
            problems.append(f"invoice number '{number}' at {where} looks too short")
        if not vendor:
            problems.append(f"invoice at {where} has no vendor")

    return problems


# ===========================================================================
# SECTION 7 — NAMING
# Plain English: build Vendor_InvoiceNumber.pdf, with characters Windows will
# not accept taken out. We NEVER overwrite an existing file - if the name is
# taken we add _02, _03 and flag it, because the same invoice arriving twice
# is a real double-payment risk and silently replacing it would hide that.
# ===========================================================================

_ILLEGAL = re.compile(r'[\\/:*?"<>|]')
_BRACKETS = re.compile(r"\(.*?\)")
_LEGAL_SUFFIX = re.compile(r"\b(llc|inc|incorporated|corp|corporation|co|ltd|lp|llp)\b")


def _vendor_key(name: str) -> str:
    """Reduce a supplier name to a comparable form.

    Plain English: the same supplier is printed differently on different pages -
    'QUILL LLC', 'Quill', 'Quill, Inc.' - so before comparing we strip away
    everything that varies: capitals, punctuation, anything in brackets, and
    the company-type words on the end. What is left is the part that actually
    identifies the supplier.
    """
    s = (name or "").lower()
    s = _BRACKETS.sub(" ", s)
    s = re.sub(r"[.,'`#&]", " ", s)
    s = _LEGAL_SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def canonical_vendor(read_name: str, approved: list):
    """Match what the AI read against the approved supplier list.

    Returns (name_to_file_under, status, note):
      status "approved"  - matched one supplier; the approved spelling is used
      status "ambiguous" - the name fits more than one approved supplier
                           (e.g. 'FERGUSON' fits two different Ferguson firms)
      status "new"       - matches nothing on the list; a genuinely new supplier
    """
    key = _vendor_key(read_name)
    if not key:
        return read_name, "new", "no vendor name read from the page"

    exact = [a for a in approved if _vendor_key(a) == key]
    if len(exact) == 1:
        return exact[0], "approved", ""

    # Not an exact match - is it the opening of one approved name, or of several?
    partial = [a for a in approved
               if _vendor_key(a).startswith(key + " ") or key.startswith(_vendor_key(a) + " ")]
    if len(partial) == 1:
        return partial[0], "approved", ""
    if len(partial) > 1:
        return read_name, "ambiguous", "could be " + " or ".join(partial)

    return read_name, "new", f"'{read_name}' is not on the approved supplier list"


def resolve_vendors(invoices: list, approved: list) -> None:
    """Settle the vendor for every invoice in one file, in place.

    Plain English: an invoice whose vendor is ambiguous can often be settled by
    looking at the rest of the same document - one page may print the supplier's
    full name even when another prints only the brand. So we match every invoice
    first, then use any clear answer in the file to settle the unclear ones.
    Only if the whole file cannot settle it do we flag it and move on.
    """
    if not approved:
        for inv in invoices:
            inv["vendor_as_printed"] = inv.get("vendor")
            inv["vendor_status"], inv["vendor_note"] = "approved", ""
        return

    for inv in invoices:
        printed = inv.get("vendor")
        name, status, note = canonical_vendor(printed, approved)
        inv["vendor_as_printed"] = printed
        inv["vendor"], inv["vendor_status"], inv["vendor_note"] = name, status, note

    settled = {inv["vendor"] for inv in invoices if inv["vendor_status"] == "approved"}
    for inv in invoices:
        if inv["vendor_status"] != "ambiguous":
            continue
        # Which of this invoice's candidates does the rest of the file confirm?
        candidates = [a for a in approved
                      if a in settled and _vendor_key(a).startswith(
                          _vendor_key(inv["vendor_as_printed"]) + " ")]
        if len(candidates) == 1:
            inv["vendor"], inv["vendor_status"] = candidates[0], "approved"
            inv["vendor_note"] = (f"read as '{inv['vendor_as_printed']}'; settled from "
                                  f"elsewhere in the same file")


def sanitize(name: str) -> str:
    clean = _ILLEGAL.sub("", name or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean.strip(". ")


def build_name(vendor: str, number: str) -> str:
    return f"{sanitize(vendor) or 'Unknown Vendor'}_{sanitize(number) or 'NoNumber'}.pdf"


def unique_path(out_dir: Path, filename: str):
    """Returns (path, was_duplicate). Never returns a path that already exists."""
    target = out_dir / filename
    if not target.exists():
        return target, False
    stem, suffix = target.stem, target.suffix
    n = 2
    while True:
        candidate = out_dir / f"{stem}_{n:02d}{suffix}"
        if not candidate.exists():
            return candidate, True
        n += 1


# ===========================================================================
# SECTION 8 — SPLIT
# Plain English: write each invoice's pages into its own new PDF. pypdf copies
# the pages across as they are, so nothing is re-drawn or re-compressed. If a
# file turns out to be one invoice covering every page, we copy the whole file
# byte for byte instead of rebuilding it.
# ===========================================================================

def write_invoice_pdf(source: Path, pages: list, dest: Path, whole_file: bool) -> None:
    if whole_file:
        shutil.copy2(source, dest)
        return
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(source))
    writer = PdfWriter()
    for page_no in pages:
        writer.add_page(reader.pages[page_no - 1])
    with open(dest, "wb") as f:
        writer.write(f)


# ===========================================================================
# SECTION 9 — REGISTER
# Plain English: every invoice gets a row. The CSV is the real record - it is
# appended to, never rewritten, and cannot be locked by anyone having it open.
# The Excel copy is rebuilt from the CSV for reading. If Excel has the xlsx
# open we simply say so and carry on, because the CSV already has the data.
# ===========================================================================

REGISTER_COLUMNS = [
    "processed_at", "source_file", "source_type", "vendor", "vendor_as_printed",
    "invoice_number", "invoice_total", "source_pages", "output_file", "status", "notes",
]


def append_register(reports_dir: Path, rows: list) -> None:
    if not rows:
        return
    csv_path = reports_dir / "invoice_register.csv"
    is_new = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=REGISTER_COLUMNS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def rebuild_xlsx(reports_dir: Path) -> None:
    csv_path = reports_dir / "invoice_register.csv"
    xlsx_path = reports_dir / "invoice_register.xlsx"
    if not csv_path.exists():
        return
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice Register"
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            ws.append(row)

    header_fill = PatternFill("solid", fgColor="4F81BD")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
    for width, col in zip([18, 34, 26, 30, 18, 12, 14, 38, 10, 46], "ABCDEFGHIJ"):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"

    try:
        wb.save(xlsx_path)
    except PermissionError:
        print(f"  ! {xlsx_path.name} is open in Excel, so it was not refreshed.")
        print(f"    Nothing is lost - invoice_register.csv already has every row.")


# ===========================================================================
# SECTION 10 — PROCESS ONE PDF
# Plain English: the whole life of a single file. Everything is built in a
# working folder first; the results are only moved into 03_Output and
# 05_Archive once the entire file has succeeded. That way a failure halfway
# through never leaves half an invoice set filed as if it were complete.
# ===========================================================================

def analyse_pdf(pdf_path: Path, cfg: dict, work: Path, use_cache: bool) -> tuple:
    cache_file = work / "cache" / f"{pdf_path.stem}.json"
    if use_cache and cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        print("  (using cached AI results)")
        return [(int(p), d) for p, d in cached["pages"]], cached["page_count"]

    pdftoppm = find_pdftoppm(cfg["poppler_path"])
    img_dir = work / "render" / pdf_path.stem
    if img_dir.exists():
        shutil.rmtree(img_dir, ignore_errors=True)
    pages = render_pages(pdf_path, img_dir, cfg.get("dpi", 200), pdftoppm)
    print(f"  rendered {len(pages)} page(s)")

    page_results = []
    open_invoice = None          # the invoice we are currently inside, if any
    for page_no, img in pages:
        t0 = time.time()
        data = ask_qwen(img, cfg)
        if "_unparsed" not in data:
            # Keep the model's own verdict so a later disagreement can be traced.
            data["model_page_type"] = data.get("page_type")
            page_type, override = enforce_page_type(data, open_invoice)
            data["page_type"] = page_type
            if page_type == "INVOICE":
                open_invoice = data.get("invoice_number") or data.get("primary_number")
            elif page_type == "SUMMARY":
                open_invoice = None
        else:
            page_type, override = "UNREADABLE", None
            open_invoice = None
        page_results.append((page_no, data))

        line = f"  page {page_no}: {page_type:<13} ({time.time() - t0:.0f}s)"
        if page_type == "INVOICE":
            line += f"  {data.get('vendor') or '-'}  #{data.get('invoice_number') or '-'}"
        print(line)
        if override:
            print(f"      OVERRIDE: {override}")

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"page_count": len(pages), "pages": page_results},
                                     indent=2), encoding="utf-8")
    shutil.rmtree(img_dir, ignore_errors=True)
    return page_results, len(pages)


def send_to_review(source: Path, cfg: dict, problems: list, page_results: list) -> list:
    review_dir = folder(cfg, "review")
    dest, _ = unique_path(review_dir, source.name)
    shutil.move(str(source), str(dest))

    note = dest.with_suffix(dest.suffix + ".txt")
    lines = [
        f"Sent to review: {datetime.now():%Y-%m-%d %H:%M}",
        f"File: {dest.name}",
        "",
        "WHY THIS FILE WAS NOT SPLIT:",
    ]
    lines += [f"  - {p}" for p in problems]
    lines += ["", "WHAT THE AI SAW ON EACH PAGE:"]
    for page_no, data in page_results:
        if "_unparsed" in data:
            lines.append(f"  page {page_no}: unreadable answer: {data['_unparsed'][:200]}")
            continue
        lines.append(
            f"  page {page_no}: {data.get('page_type')}"
            f" | heading={data.get('document_heading')}"
            f" | label={data.get('primary_number_label')}"
            f" | vendor={data.get('vendor')}"
            f" | invoice#={data.get('invoice_number')}"
        )
    note.write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> 04_Review ({len(problems)} problem(s)); reason written to {note.name}")

    return [{
        "processed_at": f"{datetime.now():%Y-%m-%d %H:%M}",
        "source_file": dest.name, "source_type": "REVIEW", "vendor": "",
        "invoice_number": "", "invoice_total": "", "source_pages": "",
        "output_file": "", "status": "REVIEW", "notes": "; ".join(problems),
    }]


def is_ready(pdf: Path, settle: int = 2) -> bool:
    """Is this file finished arriving?

    Plain English: when you drop a PDF into a OneDrive folder it may still be
    downloading or still being written. Grabbing it too early means reading
    half a file, which the AI would then misread. So we check the size twice,
    a couple of seconds apart, and only accept it if the size has stopped
    changing AND we can actually open it. Anything else, we leave it and look
    again on the next sweep.
    """
    try:
        first = pdf.stat().st_size
    except OSError:
        return False
    if first == 0:
        return False

    time.sleep(settle)

    try:
        if pdf.stat().st_size != first:
            return False
        with open(pdf, "rb") as f:              # locked by another program?
            return f.read(5).startswith(b"%PDF")
    except OSError:
        return False


def recover_stranded(cfg: dict) -> int:
    """A PDF sitting in 02_Processing when we start means an earlier run stopped
    part way through - the window was closed, the machine slept, Ollama went
    away. Left alone that file has silently dropped out of the workflow: it is
    not in the inbox, not in the output, and nobody is told. So we put it back
    in the inbox to be tried again. Nothing is deleted - it is only moved back.

    (Single machine only. If two copies of this script ever run at once, this
    would take a file the other one is working on.)"""
    stranded = sorted(folder(cfg, "processing").glob("*.pdf"))
    for pdf in stranded:
        dest, _ = unique_path(folder(cfg, "inbox"), pdf.name)
        shutil.move(str(pdf), str(dest))
        print(f"  recovered from {FOLDERS['processing']}: {pdf.name}")
    return len(stranded)


def process_one(inbox_pdf: Path, cfg: dict, work: Path, use_cache: bool) -> list:
    print(f"\n{inbox_pdf.name}")

    # 1. Claim it, so it is obvious this file is being worked on.
    claimed = folder(cfg, "processing") / inbox_pdf.name
    shutil.move(str(inbox_pdf), str(claimed))

    # 2. Ask the model about every page.
    page_results, page_count = analyse_pdf(claimed, cfg, work, use_cache)

    # 3. Work out the invoices, and whether we trust the answer.
    invoices = assemble(page_results)
    problems = find_problems(page_results, invoices, page_count)
    if problems:
        return send_to_review(claimed, cfg, problems, page_results)

    # Settle every vendor against the approved list BEFORE any filename is
    # built, so one supplier always files under one name.
    resolve_vendors(invoices, cfg.get("known_vendors") or [])
    for inv in invoices:
        if inv.get("vendor_status") == "ambiguous":
            print(f"  ! vendor '{inv['vendor_as_printed']}' is ambiguous - {inv['vendor_note']}")
        elif inv.get("vendor_status") == "new":
            print(f"  ! vendor '{inv['vendor_as_printed']}' is not on the approved list")
        elif inv.get("vendor_note"):
            print(f"    vendor {inv['vendor']} ({inv['vendor_note']})")

    source_type = classify_source(invoices)
    whole_file = len(invoices) == 1 and len(invoices[0]["pages"]) == page_count
    print(f"  {len(invoices)} invoice(s) - {source_type}")

    # 4. Build every output in the working folder FIRST.
    staged = work / "staged" / claimed.stem
    if staged.exists():
        shutil.rmtree(staged, ignore_errors=True)
    staged.mkdir(parents=True, exist_ok=True)

    built = []
    for inv in invoices:
        name = build_name(inv["vendor"], inv["invoice_number"])
        tmp = staged / name
        write_invoice_pdf(claimed, inv["pages"], tmp, whole_file)
        built.append((inv, tmp))

    # 5. Everything worked - now file the results.
    rows, out_dir = [], folder(cfg, "output")
    for inv, tmp in built:
        final, duplicate = unique_path(out_dir, tmp.name)
        shutil.move(str(tmp), str(final))
        notes = []
        if duplicate:
            notes.append("name already existed - possible duplicate invoice")
        if inv.get("vendor_note"):
            notes.append(inv["vendor_note"])

        vstatus = inv.get("vendor_status")
        status = ("DUPLICATE_NAME" if duplicate
                  else "AMBIGUOUS_VENDOR" if vstatus == "ambiguous"
                  else "NEW_VENDOR" if vstatus == "new"
                  else "OK")

        print(f"    -> {final.name}"
              f"   (source page{'s' if len(inv['pages']) > 1 else ''} "
              f"{', '.join(str(p) for p in inv['pages'])})"
              + ("  [DUPLICATE NAME]" if duplicate else ""))
        rows.append({
            "processed_at": f"{datetime.now():%Y-%m-%d %H:%M}",
            "source_file": claimed.name,
            "source_type": source_type,
            "vendor": inv.get("vendor") or "",
            "vendor_as_printed": inv.get("vendor_as_printed") or "",
            "invoice_number": inv.get("invoice_number") or "",
            "invoice_total": inv.get("total") or "",
            "source_pages": ", ".join(str(p) for p in inv["pages"]),
            "output_file": final.name,
            "status": status,
            "notes": "; ".join(notes),
        })

    # 6. The original is kept, untouched, in the archive.
    #    If a file of this name has been archived before, the same PDF has
    #    arrived twice - which is a far stronger double-payment signal than two
    #    invoices happening to share an output name. Say so in the register
    #    instead of quietly saving it alongside the first copy.
    already = folder(cfg, "archive") / claimed.name
    repeat_note = ""
    if already.exists():
        same = (hashlib.md5(claimed.read_bytes()).hexdigest()
                == hashlib.md5(already.read_bytes()).hexdigest())
        repeat_note = (
            f"SOURCE SEEN BEFORE - '{claimed.name}' is already in the archive and is "
            + ("an identical copy" if same
               else "DIFFERENT IN CONTENT despite the same name")
        )
        print(f"  ! {repeat_note}")

    archived, _ = unique_path(folder(cfg, "archive"), claimed.name)
    shutil.move(str(claimed), str(archived))

    if repeat_note:
        for r in rows:
            r["notes"] = f"{r['notes']}; {repeat_note}" if r["notes"] else repeat_note
            if r["status"] == "OK":
                r["status"] = "DUPLICATE_SOURCE"
    shutil.rmtree(staged, ignore_errors=True)
    return rows


# ===========================================================================
# SECTION 11 — MAIN
# ===========================================================================

def regrade_from_cache(work: Path) -> None:
    """Development aid. Re-runs the page classification and the invoice
    assembly over answers the model gave in earlier runs, WITHOUT calling the
    model at all, and prints what each file would produce today.

    Plain English: the slow part is asking the AI about each page, and those
    answers were already saved. So after changing a rule we can re-check every
    file tested so far in seconds instead of hours, and see immediately whether
    the change broke anything that used to work. It writes nothing and touches
    no invoice."""
    cache_dir = work / "cache"
    files = sorted(cache_dir.glob("*.json")) if cache_dir.is_dir() else []
    if not files:
        print(f"\nNo saved AI answers in {cache_dir} - nothing to re-grade.")
        return

    print(f"\nRe-grading {len(files)} previously processed file(s) from saved AI answers.")
    print("No PDF is read and the model is not called.\n")

    for cf in files:
        cached = json.loads(cf.read_text(encoding="utf-8"))
        pages = [(int(p), d) for p, d in cached["pages"]]

        open_invoice, changed = None, []
        for page_no, data in pages:
            if "_unparsed" in data:
                open_invoice = None
                continue
            was = str(data.get("page_type") or "").upper()
            now, _ = enforce_page_type(data, open_invoice)
            data["page_type"] = now
            if now != was:
                changed.append(f"p{page_no} {was} -> {now}")
            if now == "INVOICE":
                open_invoice = data.get("invoice_number") or data.get("primary_number")
            elif now == "SUMMARY":
                open_invoice = None

        invoices = assemble(pages)
        print(f"  {cf.stem[:52]}")
        for inv in invoices:
            pg = ", ".join(str(p) for p in inv["pages"])
            print(f"      #{str(inv['invoice_number']):12} pages {pg}")
        if changed:
            print(f"      CHANGED BY THE NEW RULES: {'; '.join(changed)}")
        print()


def run_one_sweep(cfg: dict, work: Path, use_cache: bool) -> list:
    """Process everything sitting in the inbox right now. Each file is recorded
    as soon as IT finishes, rather than all at the end, so stopping the script
    part way never loses the work already done."""
    reports = folder(cfg, "reports")
    done = []
    for pdf in sorted(folder(cfg, "inbox").glob("*.pdf")):
        if not is_ready(pdf):
            print(f"\n{pdf.name}\n  still arriving (OneDrive may be syncing it) - "
                  f"will try again on the next sweep")
            continue
        rows = process_one(pdf, cfg, work, use_cache)
        append_register(reports, rows)
        rebuild_xlsx(reports)
        done += rows
    return done


def main():
    ap = argparse.ArgumentParser(description="Split AP invoice PDFs using local Qwen vision")
    ap.add_argument("--use-cache", action="store_true",
                    help="reuse saved AI answers instead of asking the model again "
                         "(development aid - the model is slow)")
    ap.add_argument("--watch", action="store_true",
                    help="keep running and process files as they appear in 01_Inbox")
    ap.add_argument("--interval", type=int, default=10,
                    help="seconds between checks when using --watch (default 10)")
    ap.add_argument("--regrade", action="store_true",
                    help="re-check every previously processed file against the current "
                         "rules using saved AI answers; changes nothing (development aid)")
    args = ap.parse_args()

    cfg = load_config()
    check_folders(cfg)

    work = Path(os.environ.get("AP_SPLITTER_WORK",
                               Path(tempfile.gettempdir()) / "ap_splitter_work"))
    work.mkdir(parents=True, exist_ok=True)

    print(f"Root    : {cfg['root']}")
    print(f"Model   : {cfg['model']}   Host: {cfg['ollama_host']}")
    print(f"Work    : {work}")

    if args.regrade:
        regrade_from_cache(work)
        return

    if recover_stranded(cfg):
        print()

    started = time.time()
    all_rows = []

    if args.watch:
        # Keep running. Drop invoices into the inbox whenever you like and they
        # get picked up on the next sweep. Ctrl+C stops it.
        print(f"\nWatching {folder(cfg, 'inbox')}")
        print(f"Checking every {args.interval}s. Drop PDFs in as you go. "
              f"Press Ctrl+C to stop.\n")
        waiting = False
        try:
            while True:
                rows = run_one_sweep(cfg, work, args.use_cache)
                if rows:
                    all_rows += rows
                    ok = sum(1 for r in rows if r["status"] != "REVIEW")
                    rev = sum(1 for r in rows if r["status"] == "REVIEW")
                    print(f"\n  [{datetime.now():%H:%M:%S}] "
                          f"{ok} invoice(s) to {FOLDERS['output']}, "
                          f"{rev} to {FOLDERS['review']}. Watching again...\n")
                    waiting = False
                elif not waiting:
                    print(f"  [{datetime.now():%H:%M:%S}] "
                          f"waiting for files in {FOLDERS['inbox']}...")
                    waiting = True
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\nStopped.")
    else:
        if not sorted(folder(cfg, "inbox").glob("*.pdf")):
            print(f"\nNothing to do - {FOLDERS['inbox']} is empty.")
            return
        all_rows = run_one_sweep(cfg, work, args.use_cache)

    ok = sum(1 for r in all_rows if r["status"] != "REVIEW")
    review = sum(1 for r in all_rows if r["status"] == "REVIEW")
    print(f"\n{'=' * 60}")
    print(f"Done in {time.time() - started:.0f}s")
    print(f"  invoices written to {FOLDERS['output']} : {ok}")
    print(f"  files sent to {FOLDERS['review']}       : {review}")
    print(f"  register: {folder(cfg, 'reports') / 'invoice_register.csv'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
