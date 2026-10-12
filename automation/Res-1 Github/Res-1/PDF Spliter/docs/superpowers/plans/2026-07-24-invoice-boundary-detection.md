# Invoice Boundary Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single Python script that reads multi-invoice PDFs, predicts which page each new invoice starts on, explains why, and writes a reviewer-friendly Excel report — without ever splitting the PDFs.

**Architecture:** One heavily-commented script, `invoice_boundary_detector.py`, organized into labeled sections (CONFIG → READER → FEATURES → VENDOR → RULES → CONFIDENCE → NAMING → REPORT → SCORER → SELFTEST → MAIN). One `config.json` holds all tunables. Built walking-skeleton style: a thin end-to-end slice first, then each section is strengthened.

**Tech Stack:** Python 3.10+, PyMuPDF (`fitz`), pytesseract (+ installed Tesseract), Pillow, openpyxl, tqdm (optional). `json` is built-in.

## Global Constraints

_Every task's requirements implicitly include this section. Values copied verbatim from the spec._

- **NO PDF splitting.** The script must never write or cut PDF files. It only reads PDFs and writes `.xlsx`/`.txt`/copies.
- **Never modify originals.** Renaming writes a **copy** to `output/renamed/`; source PDFs in `input/` are never touched.
- **NO git actions** (CLAUDE.md hard rule #4). This project is local-only. No `git init/add/commit/push` anywhere. Task checkpoints are local saves + verification runs, never commits.
- **One config file:** `config.json` (read with built-in `json`). One script: `invoice_boundary_detector.py`.
- **No secrets in code.** The Tesseract path lives in `config.json` (it is a local file path, not a secret).
- **Testing:** automated checks live in the script's `--selftest` mode; I/O behavior is verified by running on the sample PDFs. No separate test framework.
- **Plain-English comments:** every section begins with a comment block a non-engineer can follow.
- **Default rule weights:** Invoice # changed +100, Vendor changed +40, Invoice header +30, Same vendor −20, Continuation pattern −40. **Break threshold:** total score ≥ 50.
- **Python:** 3.10+ (uses `str | None` hints, matching the existing `ocr_extract.py`).

---

## File map

- Create: `config.json` — all tunables (paths, tesseract path, dpi, thresholds, rule weights, known vendors).
- Create: `invoice_boundary_detector.py` — the one script (all sections).
- Create (by running): `output/reports/predictions.xlsx`, `output/renamed/*.pdf`, `ocr_debug/*.txt` (dev output).
- Reuse (read-only reference): `Tesseract_Testing/ocr_extract.py` — source of the OCR approach and regex patterns.
- Input: `input/*.pdf` — the user places sample PDFs here before running.

**Terminology:** a **PageRecord**, **FeatureRecord**, **VendorResult**, **PagePrediction**, and **PdfSummary** are plain Python `dict`s with the keys listed in each task. We use dicts (not classes) to match the existing script's simple style.

---

## Task 1: Project skeleton — config, argparse, selftest harness

**Files:**
- Create: `config.json`
- Create: `invoice_boundary_detector.py`

**Interfaces:**
- Produces: `load_config(path: str = "config.json") -> dict`; a `--selftest` CLI mode that runs `run_selftests() -> int` (0 = all passed, 1 = a check failed); a `main()` entrypoint dispatching on `--score` / `--selftest` / (default) flags.

- [ ] **Step 1: Create `config.json`**

```json
{
  "paths": {
    "input_folder": "input",
    "output_reports": "output/reports",
    "output_renamed": "output/renamed",
    "ocr_debug": "ocr_debug"
  },
  "tesseract_cmd": "C:\\Users\\Dhruv Champaneria\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe",
  "ocr": { "dpi": 300 },
  "thresholds": { "break_at_score": 50 },
  "rule_weights": {
    "invoice_number_changed": 100,
    "vendor_changed": 40,
    "invoice_header_detected": 30,
    "same_vendor": -20,
    "continuation_pattern": -40
  },
  "known_vendors": []
}
```

- [ ] **Step 2: Write the failing selftest for `load_config`**

Create `invoice_boundary_detector.py` with a SELFTEST section containing this check (and an empty everything-else for now):

```python
def _check_load_config():
    cfg = load_config("config.json")
    assert cfg["thresholds"]["break_at_score"] == 50, "break threshold should load from config"
    assert cfg["rule_weights"]["invoice_number_changed"] == 100, "weights should load from config"
    assert isinstance(cfg["known_vendors"], list), "known_vendors must be a list"

SELFTESTS = [_check_load_config]

def run_selftests() -> int:
    failed = 0
    for check in SELFTESTS:
        try:
            check()
            print(f"PASS  {check.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {check.__name__}: {e}")
    print(f"\n{len(SELFTESTS) - failed}/{len(SELFTESTS)} checks passed.")
    return 1 if failed else 0
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python invoice_boundary_detector.py --selftest`
Expected: FAIL — `NameError: name 'load_config' is not defined` (or the argparse/main not wired yet).

- [ ] **Step 4: Implement the script skeleton (top matter, CONFIG, MAIN)**

```python
"""
Invoice Boundary Detection Engine
=================================
Reads multi-invoice PDFs and PREDICTS which page each new invoice starts on,
then writes a reviewer-friendly Excel report. It NEVER splits the PDFs.

Run modes:
    python invoice_boundary_detector.py            → read PDFs, predict, write Excel
    python invoice_boundary_detector.py --score    → read the reviewed Excel, print accuracy
    python invoice_boundary_detector.py --selftest  → run built-in logic checks

Requirements:
    pip install PyMuPDF pytesseract Pillow openpyxl tqdm
    Tesseract-OCR installed (path set in config.json)
"""

import os
import io
import re
import sys
import json
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Third-party (installed via pip). Imported lazily inside functions that need
# them so that --selftest can run pure-logic checks without them installed.

SCRIPT_DIR = Path(__file__).resolve().parent


# ===========================================================================
# SECTION 1 — CONFIG
# Plain English: this reads config.json, the ONE settings file. It holds the
# folder paths, where Tesseract lives, the OCR image quality (dpi), the score
# needed to call a page a "new invoice", the points each rule is worth, and
# the list of known vendor names. Non-engineers tune behavior HERE, not in code.
# ===========================================================================

def load_config(path: str = "config.json") -> dict:
    config_path = SCRIPT_DIR / path
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# (Other sections are added by later tasks.)


# ===========================================================================
# SECTION 10 — MAIN
# Plain English: the front door. It looks at the command-line flag and decides
# which mode to run.
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Invoice boundary detection (no splitting).")
    parser.add_argument("--score", action="store_true", help="Score a reviewed Excel file.")
    parser.add_argument("--selftest", action="store_true", help="Run built-in logic checks.")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(run_selftests())

    if args.score:
        print("Score mode is implemented in a later task.")
        return

    print("Prediction mode is implemented in a later task.")


if __name__ == "__main__":
    main()
```

(Place the SELFTEST section from Step 2 just above SECTION 10.)

- [ ] **Step 5: Run to verify it passes**

Run: `python invoice_boundary_detector.py --selftest`
Expected: `PASS  _check_load_config` and `1/1 checks passed.`

- [ ] **Step 6: Checkpoint (no git)**

Save the files. Confirm `python invoice_boundary_detector.py` prints the "Prediction mode is implemented in a later task." line. Mark Task 1 done. (No commit — hard rule #4.)

---

## Task 2: READER — OCR every page, record failures with reasons

**Files:**
- Modify: `invoice_boundary_detector.py` (add SECTION 2 — READER; extend MAIN to write debug text)

**Interfaces:**
- Consumes: `load_config`.
- Produces: `read_pdf_pages(pdf_path: Path, config: dict) -> list[dict]`. Each dict (**PageRecord**) has keys: `pdf_name` (str), `page_number` (int, 1-based), `text` (str), `read_status` ("ok" | "failed"), `read_reason` (str | None). Also `collect_pdfs(folder: Path) -> list[Path]`.

- [ ] **Step 1: Write the failing selftest for `collect_pdfs`**

Add to the SELFTESTS list a check that does not need OCR:

```python
def _check_collect_pdfs_sorted(tmp=SCRIPT_DIR):
    # Uses whatever PDFs exist in input/; just verifies the function returns a
    # sorted list of Path objects ending in .pdf (empty is acceptable).
    cfg = load_config("config.json")
    pdfs = collect_pdfs(SCRIPT_DIR / cfg["paths"]["input_folder"])
    assert isinstance(pdfs, list), "collect_pdfs must return a list"
    assert all(str(p).lower().endswith(".pdf") for p in pdfs), "only .pdf paths"
    assert pdfs == sorted(pdfs), "collect_pdfs must be sorted"
```

Append `_check_collect_pdfs_sorted` to `SELFTESTS`.

- [ ] **Step 2: Run to verify it fails**

Run: `python invoice_boundary_detector.py --selftest`
Expected: FAIL — `NameError: name 'collect_pdfs' is not defined`.

- [ ] **Step 3: Implement SECTION 2 — READER**

```python
# ===========================================================================
# SECTION 2 — READER (OCR)
# Plain English: opens each PDF, turns every page into a 300-dpi image
# (PyMuPDF), and reads the text off that image with Tesseract OCR. We OCR
# EVERY page (even digital ones) for uniform behavior. If a page cannot be
# read, we DO NOT silently skip it — we record WHY (the error message) so the
# reviewer sees the reason later.
# ===========================================================================

def collect_pdfs(folder: Path) -> list:
    """Return a sorted list of all *.pdf paths directly under `folder`."""
    if not folder.exists():
        return []
    return sorted(folder.glob("*.pdf"))


def read_pdf_pages(pdf_path: Path, config: dict) -> list:
    """OCR every page of one PDF. Returns a list of PageRecord dicts."""
    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = config["tesseract_cmd"]
    dpi = config["ocr"]["dpi"]
    pdf_name = pdf_path.name
    records = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        # Whole file unreadable: one record explaining why.
        return [{
            "pdf_name": pdf_name, "page_number": 1, "text": "",
            "read_status": "failed", "read_reason": f"could not open PDF: {e}",
        }]

    for page_index, page in enumerate(doc, start=1):
        try:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img)
            records.append({
                "pdf_name": pdf_name, "page_number": page_index, "text": text,
                "read_status": "ok", "read_reason": None,
            })
        except Exception as e:
            records.append({
                "pdf_name": pdf_name, "page_number": page_index, "text": "",
                "read_status": "failed",
                "read_reason": f"OCR failed on page {page_index}: {e}",
            })
    doc.close()
    return records
```

- [ ] **Step 4: Run selftest to verify it passes**

Run: `python invoice_boundary_detector.py --selftest`
Expected: both checks PASS.

- [ ] **Step 5: Wire a temporary debug run into MAIN**

Replace the default-mode body in `main()` with:

```python
    # Default = prediction mode (built up over the walking-skeleton tasks).
    config = load_config()
    input_folder = SCRIPT_DIR / config["paths"]["input_folder"]
    debug_folder = SCRIPT_DIR / config["paths"]["ocr_debug"]
    debug_folder.mkdir(parents=True, exist_ok=True)

    pdfs = collect_pdfs(input_folder)
    if not pdfs:
        print(f"No PDFs found in {input_folder}. Put sample PDFs there and re-run.")
        return

    for pdf_path in pdfs:
        pages = read_pdf_pages(pdf_path, config)
        lines = [f"{p['page_number']}: [{p['read_status']}] {p['read_reason'] or ''}\n"
                 f"{p['text'][:400]}" for p in pages]
        out = debug_folder / (pdf_path.stem + ".txt")
        out.write_text("\n\n".join(lines), encoding="utf-8")
        print(f"{pdf_path.name}: {len(pages)} page(s) → {out.name}")
```

- [ ] **Step 6: Run on samples to verify OCR + reasons**

Precondition: user has placed at least 2 sample PDFs in `input/`.
Run: `python invoice_boundary_detector.py`
Expected: for each PDF, a line like `Victory Court....pdf: 3 page(s) → Victory Court....txt`, and matching `.txt` files under `ocr_debug/` whose pages show OCR text (and any `[failed]` reason).

- [ ] **Step 7: Checkpoint (no git)**

Confirm the debug `.txt` files contain readable text. Mark Task 2 done.

---

## Task 3: FEATURES — extract fields from page text

**Files:**
- Modify: `invoice_boundary_detector.py` (add SECTION 3 — FEATURES)

**Interfaces:**
- Consumes: page `text` strings from READER.
- Produces: `extract_features(text: str) -> dict`. **FeatureRecord** keys: `invoice_number`, `date`, `due_date`, `vendor_raw`, `bill_to`, `total`, `po_number`, `currency` (each `str | None`). Also `find_doc_number(text) -> str | None`.

- [ ] **Step 1: Write failing selftests (test-first)**

Add these checks and append them to `SELFTESTS`:

```python
def _check_invoice_number():
    assert find_doc_number("Invoice #: INV-1001") == "INV-1001"
    assert find_doc_number("no numbers here") is None

def _check_total_and_date():
    f = extract_features("Invoice No: 77\nDate: 03/14/2026\nTotal Due: $1,234.56")
    assert f["invoice_number"] == "77", f["invoice_number"]
    assert f["date"] == "03/14/2026", f["date"]
    assert f["total"] == "1,234.56", f["total"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `python invoice_boundary_detector.py --selftest`
Expected: FAIL — `find_doc_number`/`extract_features` not defined.

- [ ] **Step 3: Implement SECTION 3 — FEATURES**

```python
# ===========================================================================
# SECTION 3 — FEATURES
# Plain English: given the text of one page, pull out the useful fields using
# pattern matching (regular expressions). These patterns are adapted from the
# earlier ocr_extract.py. Anything not found comes back as None.
# ===========================================================================

_DOC_NUMBER_PATTERNS = [
    re.compile(r"(?:invoice|inv)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.I),
    re.compile(r"(?:statement)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.I),
    re.compile(r"(?:bill|receipt|credit\s*memo|debit\s*memo)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.I),
]
_PO_PATTERN = re.compile(r"(?:purchase\s*order|po)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.I)
_DATE_PATTERNS = [
    re.compile(r"(?:invoice\s*date|statement\s*date|bill\s*date|dated|date)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", re.I),
    re.compile(r"(?:invoice\s*date|statement\s*date|bill\s*date|dated|date)\s*[:\-]?\s*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{2,4})", re.I),
]
_DUE_DATE_PATTERNS = [
    re.compile(r"(?:due\s*date|payment\s*due|pay\s*by|due\s*on)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", re.I),
]
_AMOUNT_PATTERNS = [
    re.compile(r"(?:total\s*(?:due|amount|balance)?|amount\s*due|balance\s*due|grand\s*total|net\s*amount)\s*[:\-]?\s*\$?\s*([\d,]+\.\d{2})", re.I),
]
_BILL_TO_PATTERNS = [
    re.compile(r"(?:bill\s*to|sold\s*to|ship\s*to|customer|client|attn)\s*[:\-]?\s*(.+?)(?:\n|$)", re.I),
]
_CURRENCY_PATTERN = re.compile(r"\b(USD|CAD|EUR|GBP)\b|(\$)")


def _first(patterns: list, text: str) -> str | None:
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip()
    return None


def find_doc_number(text: str) -> str | None:
    return _first(_DOC_NUMBER_PATTERNS, text)


def extract_features(text: str) -> dict:
    currency = None
    m = _CURRENCY_PATTERN.search(text)
    if m:
        currency = m.group(1) if m.group(1) else "USD"
    return {
        "invoice_number": find_doc_number(text),
        "date": _first(_DATE_PATTERNS, text),
        "due_date": _first(_DUE_DATE_PATTERNS, text),
        "vendor_raw": None,  # filled by VENDOR section (Task 4)
        "bill_to": _first(_BILL_TO_PATTERNS, text),
        "total": _first(_AMOUNT_PATTERNS, text),
        "po_number": (_PO_PATTERN.search(text).group(1).strip() if _PO_PATTERN.search(text) else None),
        "currency": currency,
    }
```

- [ ] **Step 4: Run selftest to verify pass**

Run: `python invoice_boundary_detector.py --selftest`
Expected: all checks PASS.

- [ ] **Step 5: Checkpoint (no git)**

Mark Task 3 done.

---

## Task 4: VENDOR — layered detection with confidence

**Files:**
- Modify: `invoice_boundary_detector.py` (add SECTION 4 — VENDOR; set `vendor_raw`/vendor into feature flow)

**Interfaces:**
- Consumes: page `text`, `config["known_vendors"]`.
- Produces: `detect_vendor(text: str, config: dict) -> dict`. **VendorResult** keys: `vendor_name` (str | None), `confidence` ("high" | "med" | "low"), `source` ("known-list" | "top-of-page" | "domain" | "label" | "none"). Also `sanitize_filename(name: str) -> str`.

- [ ] **Step 1: Write failing selftests (test-first)**

```python
def _check_vendor_known_list():
    cfg = {"known_vendors": ["Ferguson Facility Supply"]}
    v = detect_vendor("Charges from Ferguson Facility Supply for July", cfg)
    assert v["vendor_name"] == "Ferguson Facility Supply"
    assert v["confidence"] == "high" and v["source"] == "known-list"

def _check_vendor_domain():
    cfg = {"known_vendors": []}
    v = detect_vendor("Questions? billing@acmeplumbing.com", cfg)
    assert v["vendor_name"] and "acmeplumbing" in v["vendor_name"].lower()
    assert v["source"] == "domain"

def _check_sanitize_filename():
    assert sanitize_filename('A/B:C*?"') == "A_B_C___"
```

Append all three to `SELFTESTS`.

- [ ] **Step 2: Run to verify they fail**

Run: `python invoice_boundary_detector.py --selftest`
Expected: FAIL — `detect_vendor`/`sanitize_filename` not defined.

- [ ] **Step 3: Implement SECTION 4 — VENDOR**

```python
# ===========================================================================
# SECTION 4 — VENDOR
# Plain English: figure out WHO the invoice is from. Vendor drives file naming
# and a key rule, so we try several methods, most reliable first:
#   1) known-vendor list (config)   2) top-of-page company line
#   3) email/website domain          4) old "From:/Vendor:" label
# We attach a confidence and never trust a guess silently.
# ===========================================================================

_LABEL_VENDOR = re.compile(r"(?:from|vendor|supplier|remit\s*to|sold\s*by|billed?\s*by)\s*[:\-]?\s*(.+?)(?:\n|$)", re.I)
_DOMAIN = re.compile(r"[\w.\-]+@([A-Za-z0-9\-]+)\.(?:com|net|org|co)", re.I)
_COMPANY_SUFFIX = re.compile(r"\b([A-Z][A-Za-z&'.\- ]{2,40}?(?:LLC|Inc|Incorporated|Co|Company|Corp|Ltd|Supply|Services|Plumbing|Electric))\b")
_ILLEGAL_FILENAME = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(name: str) -> str:
    return _ILLEGAL_FILENAME.sub("_", name).strip()


def detect_vendor(text: str, config: dict) -> dict:
    known = config.get("known_vendors", [])

    # 1) Known-vendor list (case-insensitive substring).
    lowered = text.lower()
    for name in known:
        if name.lower() in lowered:
            return {"vendor_name": name, "confidence": "high", "source": "known-list"}

    # 2) Top-of-page company line (first ~8 non-empty lines, look for a suffix).
    top = "\n".join([ln for ln in text.splitlines() if ln.strip()][:8])
    m = _COMPANY_SUFFIX.search(top)
    if m:
        return {"vendor_name": m.group(1).strip(), "confidence": "med", "source": "top-of-page"}

    # 3) Email/website domain.
    m = _DOMAIN.search(text)
    if m:
        return {"vendor_name": m.group(1).strip(), "confidence": "med", "source": "domain"}

    # 4) Label fallback.
    m = _LABEL_VENDOR.search(text)
    if m and len(m.group(1).strip()) >= 3:
        return {"vendor_name": m.group(1).strip(), "confidence": "low", "source": "label"}

    return {"vendor_name": None, "confidence": "low", "source": "none"}
```

- [ ] **Step 4: Run selftest to verify pass**

Run: `python invoice_boundary_detector.py --selftest`
Expected: all checks PASS. (Note: `_check_vendor_domain` expects the top-of-page suffix rule not to fire first on that short text — it won't, since there's no company-suffix line.)

- [ ] **Step 5: Checkpoint (no git)**

Mark Task 4 done.

---

## Task 5: RULES + CONFIDENCE — score boundaries with reasons

**Files:**
- Modify: `invoice_boundary_detector.py` (add SECTION 5 — RULES and SECTION 6 — CONFIDENCE)

**Interfaces:**
- Consumes: two adjacent enriched page dicts (a **page** = its FeatureRecord plus `text` and a `vendor` VendorResult and `page_number`).
- Produces: `score_boundary(prev: dict, curr: dict, config: dict) -> dict`. **PagePrediction** keys: `page_number` (int), `decision` ("Break" | "Continue"), `confidence` ("high"|"med"|"low"), `total_score` (int), `fired_rules` (list[str]). Also `predict_boundaries(pages: list[dict], config: dict) -> list[dict]` (page 1 is always a Break).

- [ ] **Step 1: Write failing selftests (test-first)**

```python
def _mk_page(n, text="", inv=None, vendor=None):
    return {"page_number": n, "text": text,
            "features": {"invoice_number": inv},
            "vendor": {"vendor_name": vendor}}

def _check_invoice_number_changed_breaks():
    cfg = load_config("config.json")
    prev = _mk_page(1, inv="1001", vendor="Acme")
    curr = _mk_page(2, inv="1002", vendor="Acme")
    pred = score_boundary(prev, curr, cfg)
    assert pred["decision"] == "Break", pred
    assert any("Invoice number changed" in r for r in pred["fired_rules"]), pred

def _check_continuation_continues():
    cfg = load_config("config.json")
    prev = _mk_page(1, text="Invoice # 1001", inv="1001", vendor="Acme")
    curr = _mk_page(2, text="continued... page 2 of 3", inv=None, vendor="Acme")
    pred = score_boundary(prev, curr, cfg)
    assert pred["decision"] == "Continue", pred

def _check_first_page_always_break():
    cfg = load_config("config.json")
    preds = predict_boundaries([_mk_page(1, inv="1001")], cfg)
    assert preds[0]["decision"] == "Break"
```

Append the three `_check_*` functions to `SELFTESTS`.

- [ ] **Step 2: Run to verify they fail**

Run: `python invoice_boundary_detector.py --selftest`
Expected: FAIL — `score_boundary`/`predict_boundaries` not defined.

- [ ] **Step 3: Implement SECTION 5 — RULES and SECTION 6 — CONFIDENCE**

```python
# ===========================================================================
# SECTION 5 — RULES
# Plain English: each rule is a small, independent check comparing the current
# page to the previous one. If it "fires", it returns points (+/-) and a plain
# reason. Points come from config so non-engineers can tune them. Positive
# points push toward "a new invoice starts here" (Break); negative points push
# toward "same invoice" (Continue).
# ===========================================================================

_HEADER_HINT = re.compile(r"\b(invoice|statement|bill\s*to|remit\s*to|invoice\s*date)\b", re.I)
_CONTINUATION_HINT = re.compile(r"\b(continued|page\s*\d+\s*of\s*\d+|carried\s*forward)\b", re.I)


def rule_invoice_number_changed(prev, curr, w):
    a = prev["features"].get("invoice_number")
    b = curr["features"].get("invoice_number")
    if a and b and a != b:
        return w["invoice_number_changed"], f"Invoice number changed ({a} -> {b})"
    return None

def rule_vendor_changed(prev, curr, w):
    a = (prev.get("vendor") or {}).get("vendor_name")
    b = (curr.get("vendor") or {}).get("vendor_name")
    if a and b and a != b:
        return w["vendor_changed"], f"Vendor changed ({a} -> {b})"
    return None

def rule_invoice_header_detected(prev, curr, w):
    if _HEADER_HINT.search(curr.get("text", "")):
        return w["invoice_header_detected"], "Invoice header keywords on this page"
    return None

def rule_same_vendor(prev, curr, w):
    a = (prev.get("vendor") or {}).get("vendor_name")
    b = (curr.get("vendor") or {}).get("vendor_name")
    if a and b and a == b:
        return w["same_vendor"], f"Same vendor as previous page ({a})"
    return None

def rule_continuation_pattern(prev, curr, w):
    txt = curr.get("text", "")
    if _CONTINUATION_HINT.search(txt) or (not curr["features"].get("invoice_number") and not _HEADER_HINT.search(txt)):
        return w["continuation_pattern"], "Looks like a continuation page"
    return None

RULES = [
    rule_invoice_number_changed,
    rule_vendor_changed,
    rule_invoice_header_detected,
    rule_same_vendor,
    rule_continuation_pattern,
]


# ===========================================================================
# SECTION 6 — CONFIDENCE
# Plain English: add up all the rule points for a page. If the total reaches
# the threshold in config, we say a NEW invoice starts here (Break); otherwise
# it CONTINUES the current one. Confidence = how far the total is from the line.
# ===========================================================================

def _confidence_from_margin(margin: int) -> str:
    if margin >= 40:
        return "high"
    if margin >= 15:
        return "med"
    return "low"


def score_boundary(prev: dict, curr: dict, config: dict) -> dict:
    w = config["rule_weights"]
    threshold = config["thresholds"]["break_at_score"]
    total, reasons = 0, []
    for rule in RULES:
        out = rule(prev, curr, w)
        if out is not None:
            pts, why = out
            total += pts
            reasons.append(f"{why} ({pts:+d})")
    decision = "Break" if total >= threshold else "Continue"
    return {
        "page_number": curr["page_number"],
        "decision": decision,
        "confidence": _confidence_from_margin(abs(total - threshold)),
        "total_score": total,
        "fired_rules": reasons,
    }


def predict_boundaries(pages: list, config: dict) -> list:
    """Page 1 always starts an invoice (Break). Pages 2..n are scored."""
    preds = []
    for i, page in enumerate(pages):
        if i == 0:
            preds.append({
                "page_number": page["page_number"], "decision": "Break",
                "confidence": "high", "total_score": config["thresholds"]["break_at_score"],
                "fired_rules": ["First page of the PDF"],
            })
        else:
            preds.append(score_boundary(pages[i - 1], page, config))
    return preds
```

- [ ] **Step 4: Run selftest to verify pass**

Run: `python invoice_boundary_detector.py --selftest`
Expected: all checks PASS.

- [ ] **Step 5: Checkpoint (no git)**

Mark Task 5 done.

---

## Task 6: Assemble enriched pages + PdfSummary (pipeline glue)

**Files:**
- Modify: `invoice_boundary_detector.py` (add `build_pages` + `summarize_pdf`; rewire MAIN default mode)

**Interfaces:**
- Consumes: READER, FEATURES, VENDOR, CONFIDENCE.
- Produces: `build_pages(records: list[dict], config: dict) -> list[dict]` (each page = `{page_number, text, read_status, read_reason, features, vendor}`); `summarize_pdf(pdf_name: str, pages: list[dict], preds: list[dict]) -> dict`. **PdfSummary** keys: `pdf_name`, `page_count`, `split_points` (list of `{page, vendor}`), `invoice_count`, `distinct_vendors` (list[str]), `is_mixed_vendor` (bool), `renamed_to` (str | None, set in Task 8).

- [ ] **Step 1: Write failing selftest (test-first)**

```python
def _check_summary_counts_splits():
    cfg = load_config("config.json")
    pages = [
        {"page_number": 1, "text": "Invoice # 1", "features": {"invoice_number": "1"}, "vendor": {"vendor_name": "Acme"}},
        {"page_number": 2, "text": "continued", "features": {"invoice_number": None}, "vendor": {"vendor_name": "Acme"}},
        {"page_number": 3, "text": "Invoice # 2", "features": {"invoice_number": "2"}, "vendor": {"vendor_name": "Beta"}},
    ]
    preds = predict_boundaries(pages, cfg)
    s = summarize_pdf("x.pdf", pages, preds)
    assert s["invoice_count"] == 2, s
    assert [sp["page"] for sp in s["split_points"]] == [1, 3], s
    assert s["is_mixed_vendor"] is True, s
```

Append `_check_summary_counts_splits` to `SELFTESTS`.

- [ ] **Step 2: Run to verify it fails**

Run: `python invoice_boundary_detector.py --selftest`
Expected: FAIL — `summarize_pdf` not defined.

- [ ] **Step 3: Implement the glue**

```python
# ---- Pipeline glue: turn raw PageRecords into enriched pages, then summarize.
def build_pages(records: list, config: dict) -> list:
    pages = []
    for r in records:
        feats = extract_features(r["text"])
        vend = detect_vendor(r["text"], config)
        feats["vendor_raw"] = vend["vendor_name"]
        pages.append({
            "page_number": r["page_number"], "text": r["text"],
            "read_status": r["read_status"], "read_reason": r["read_reason"],
            "features": feats, "vendor": vend,
        })
    return pages


def summarize_pdf(pdf_name: str, pages: list, preds: list) -> dict:
    split_points = []
    for page, pred in zip(pages, preds):
        if pred["decision"] == "Break":
            split_points.append({"page": page["page_number"],
                                  "vendor": (page["vendor"] or {}).get("vendor_name")})
    distinct = []
    for sp in split_points:
        if sp["vendor"] and sp["vendor"] not in distinct:
            distinct.append(sp["vendor"])
    return {
        "pdf_name": pdf_name,
        "page_count": len(pages),
        "split_points": split_points,
        "invoice_count": len(split_points),
        "distinct_vendors": distinct,
        "is_mixed_vendor": len(distinct) > 1,
        "renamed_to": None,
    }
```

- [ ] **Step 4: Run selftest to verify pass**

Run: `python invoice_boundary_detector.py --selftest`
Expected: all checks PASS.

- [ ] **Step 5: Rewire MAIN default mode to full prediction (in-memory)**

Replace the debug loop in `main()` default mode with:

```python
    config = load_config()
    input_folder = SCRIPT_DIR / config["paths"]["input_folder"]
    pdfs = collect_pdfs(input_folder)
    if not pdfs:
        print(f"No PDFs found in {input_folder}. Put sample PDFs there and re-run.")
        return

    all_summaries, all_page_details = [], []
    for pdf_path in pdfs:
        records = read_pdf_pages(pdf_path, config)
        pages = build_pages(records, config)
        preds = predict_boundaries(pages, config)
        summary = summarize_pdf(pdf_path.name, pages, preds)
        apply_naming(pdf_path, summary, pages, config)   # Task 8
        all_summaries.append(summary)
        for page, pred in zip(pages, preds):
            all_page_details.append({"pdf_name": pdf_path.name, "page": page, "pred": pred})
        splits = ", ".join(str(sp["page"]) for sp in summary["split_points"])
        print(f"{pdf_path.name}: {summary['invoice_count']} invoice(s), splits at [{splits}]")

    out_dir = SCRIPT_DIR / config["paths"]["output_reports"]
    out_dir.mkdir(parents=True, exist_ok=True)
    build_excel_report(all_summaries, all_page_details, out_dir / "predictions.xlsx", config)  # Task 7
    print(f"\nReport written to {out_dir / 'predictions.xlsx'}")
```

(`apply_naming` and `build_excel_report` are added in Tasks 7–8; until then, comment those two lines out to run.)

- [ ] **Step 6: Checkpoint (no git)**

Mark Task 6 done.

---

## Task 7: REPORT — styled Excel with dropdowns

**Files:**
- Modify: `invoice_boundary_detector.py` (add SECTION 8 — REPORT)

**Interfaces:**
- Consumes: `all_summaries` (list of PdfSummary), `all_page_details` (list of `{pdf_name, page, pred}`).
- Produces: `build_excel_report(summaries: list, page_details: list, out_path: Path, config: dict) -> None` writing a two-sheet `.xlsx` with a data-validation dropdown on the "Reviewer verdict" column.

- [ ] **Step 1: Implement SECTION 8 — REPORT**

```python
# ===========================================================================
# SECTION 8 — REPORT
# Plain English: write the Excel a human reviews. Sheet 1 "Summary" = one row
# per PDF with the predicted split pages and a DROPDOWN to judge it. Sheet 2
# "Page Detail" = one row per page explaining WHY (which rules fired). Styling
# is clean and lightly colored; the dropdown uses Excel data validation.
# ===========================================================================

def _format_splits(summary: dict) -> str:
    parts = []
    for sp in summary["split_points"]:
        parts.append(f"p{sp['page']} - {sp['vendor']}" if summary["is_mixed_vendor"] and sp["vendor"]
                     else f"p{sp['page']}")
    return ", ".join(parts)


def build_excel_report(summaries: list, page_details: list, out_path: Path, config: dict) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")

    wb = Workbook()

    # ---- Sheet 1: Summary
    ws = wb.active
    ws.title = "Summary"
    cols = ["PDF", "Pages", "New invoice starts at", "# invoices",
            "Vendors", "Reviewer verdict", "Correct split pages (if wrong)"]
    ws.append(cols)
    for c in range(1, len(cols) + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill, cell.font = header_fill, header_font

    verdicts = '"✅ Correct,⚠️ Partially correct,❌ Incorrect,🔍 Needs a closer look"'
    dv = DataValidation(type="list", formula1=verdicts, allow_blank=True)
    ws.add_data_validation(dv)

    for row_i, s in enumerate(summaries, start=2):
        ws.append([
            s.get("renamed_to") or s["pdf_name"],
            s["page_count"], _format_splits(s), s["invoice_count"],
            ", ".join(s["distinct_vendors"]) or "(none detected)", "", "",
        ])
        dv.add(ws.cell(row=row_i, column=6))  # dropdown on "Reviewer verdict"
    for width, col in zip([34, 7, 34, 10, 24, 22, 26], "ABCDEFG"):
        ws.column_dimensions[col].width = width

    # ---- Sheet 2: Page Detail
    wd = wb.create_sheet("Page Detail")
    dcols = ["PDF", "Page", "Decision", "Confidence", "Score", "Why (rules fired)", "Read issue"]
    wd.append(dcols)
    for c in range(1, len(dcols) + 1):
        cell = wd.cell(row=1, column=c)
        cell.fill, cell.font = header_fill, header_font
    green = PatternFill("solid", fgColor="C6EFCE")
    for d in page_details:
        page, pred = d["page"], d["pred"]
        wd.append([
            d["pdf_name"], pred["page_number"], pred["decision"], pred["confidence"],
            pred["total_score"], "; ".join(pred["fired_rules"]),
            page.get("read_reason") or "",
        ])
        if pred["decision"] == "Break":
            wd.cell(row=wd.max_row, column=3).fill = green
    for cell in wd["F"]:
        cell.alignment = wrap
    for width, col in zip([30, 6, 10, 12, 8, 60, 30], "ABCDEFG"):
        wd.column_dimensions[col].width = width

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
```

- [ ] **Step 2: Uncomment the `build_excel_report` call in MAIN (Task 6, Step 5)**

- [ ] **Step 3: Run on samples and open the Excel**

Run: `python invoice_boundary_detector.py`
Expected: `output/reports/predictions.xlsx` is created. Open it: Summary sheet has one row per PDF; the "Reviewer verdict" cells show a **dropdown** with the four options; Page Detail sheet lists per-page reasons, Break rows shaded green.

- [ ] **Step 4: Checkpoint (no git)**

Mark Task 7 done.

---

## Task 8: NAMING — rename single-vendor copies, leave originals

**Files:**
- Modify: `invoice_boundary_detector.py` (add SECTION 7 — NAMING)

**Interfaces:**
- Consumes: `summary` (PdfSummary), original `pdf_path`, `config["paths"]["output_renamed"]`.
- Produces: `apply_naming(pdf_path: Path, summary: dict, pages: list, config: dict) -> None` — sets `summary["renamed_to"]` and copies the file when single-vendor. Uses a module-level `_vendor_counts` dict for `_01/_02` dedup. Also `_dedup_name(base: str) -> str`.

- [ ] **Step 1: Write failing selftest (test-first)**

```python
def _check_dedup_name():
    reset_vendor_counts()
    assert _dedup_name("Acme") == "Acme"
    assert _dedup_name("Acme") == "Acme_01"
    assert _dedup_name("Acme") == "Acme_02"
    assert _dedup_name("Beta") == "Beta"
```

Append `_check_dedup_name` to `SELFTESTS`.

- [ ] **Step 2: Run to verify it fails**

Run: `python invoice_boundary_detector.py --selftest`
Expected: FAIL — `_dedup_name`/`reset_vendor_counts` not defined.

- [ ] **Step 3: Implement SECTION 7 — NAMING**

```python
# ===========================================================================
# SECTION 7 — NAMING
# Plain English: if a whole PDF is from ONE vendor, we make a COPY named after
# that vendor (never touching the original). If the same vendor appears again,
# we add _01, _02, ... If a PDF has MULTIPLE vendors, we do NOT rename it — the
# Excel shows the vendor at each split point instead.
# ===========================================================================

_vendor_counts: dict = {}

def reset_vendor_counts():
    _vendor_counts.clear()

def _dedup_name(base: str) -> str:
    n = _vendor_counts.get(base, 0)
    _vendor_counts[base] = n + 1
    return base if n == 0 else f"{base}_{n:02d}"


def apply_naming(pdf_path, summary: dict, pages: list, config: dict) -> None:
    # Mixed-vendor or no vendor → never rename.
    if summary["is_mixed_vendor"] or not summary["distinct_vendors"]:
        return
    vendor = summary["distinct_vendors"][0]
    safe = sanitize_filename(vendor)
    new_stem = _dedup_name(safe)
    out_dir = Path(SCRIPT_DIR) / config["paths"]["output_renamed"]
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{new_stem}.pdf"
    shutil.copy2(str(pdf_path), str(dest))   # COPY — original untouched
    summary["renamed_to"] = dest.name
```

Also call `reset_vendor_counts()` once at the start of MAIN's default mode (before the PDF loop) so counts are fresh each run.

- [ ] **Step 4: Run selftest to verify pass**

Run: `python invoice_boundary_detector.py --selftest`
Expected: all checks PASS.

- [ ] **Step 5: Run on samples; verify copies + originals intact**

Uncomment the `apply_naming(...)` line in MAIN. Run: `python invoice_boundary_detector.py`
Expected: single-vendor PDFs appear as renamed copies under `output/renamed/`; every original file in `input/` is unchanged (same names, same count); the Excel Summary shows the renamed name for those rows.

- [ ] **Step 6: Checkpoint (no git)**

Mark Task 8 done.

---

## Task 9: SCORER — accuracy from the reviewed Excel

**Files:**
- Modify: `invoice_boundary_detector.py` (add SECTION 9 — SCORER; wire `--score` in MAIN)

**Interfaces:**
- Consumes: a reviewed `predictions.xlsx` (Summary sheet with "Reviewer verdict" + "Correct split pages (if wrong)" filled).
- Produces: `score_reviewed_report(xlsx_path: Path) -> dict` returning metrics `{pdfs, boundaries_predicted, boundaries_true, true_positives, false_positives, false_negatives, precision, recall, f1}`; and `_parse_pages(cell: str) -> set[int]`.

- [ ] **Step 1: Write failing selftests (test-first)**

```python
def _check_parse_pages():
    assert _parse_pages("1, 5, 9") == {1, 5, 9}
    assert _parse_pages("p1, p4") == {1, 4}
    assert _parse_pages("") == set()

def _check_prf_math():
    # tp=2, fp=1, fn=1 -> precision=2/3, recall=2/3, f1=2/3
    m = _prf(tp=2, fp=1, fn=1)
    assert round(m["precision"], 3) == 0.667 and round(m["recall"], 3) == 0.667
    assert round(m["f1"], 3) == 0.667
```

Append both to `SELFTESTS`.

- [ ] **Step 2: Run to verify they fail**

Run: `python invoice_boundary_detector.py --selftest`
Expected: FAIL — `_parse_pages`/`_prf` not defined.

- [ ] **Step 3: Implement SECTION 9 — SCORER**

```python
# ===========================================================================
# SECTION 9 — SCORER  (run with --score, AFTER a human fills the Excel)
# Plain English: compare what the script predicted against what the reviewer
# said was correct, and report accuracy (Precision/Recall/F1). If the reviewer
# marked a row "Correct", the predicted split pages ARE the truth. Otherwise we
# use the pages they typed in "Correct split pages (if wrong)".
# ===========================================================================

def _parse_pages(cell: str) -> set:
    if not cell:
        return set()
    return {int(n) for n in re.findall(r"\d+", str(cell))}

def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": precision, "recall": recall, "f1": f1}


def score_reviewed_report(xlsx_path: Path) -> dict:
    from openpyxl import load_workbook
    wb = load_workbook(xlsx_path)
    ws = wb["Summary"]
    tp = fp = fn = pdfs = pred_total = true_total = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] in (None, ""):
            continue
        pdfs += 1
        predicted = _parse_pages(row[2])            # "New invoice starts at"
        verdict = (row[5] or "")                     # "Reviewer verdict"
        correction = _parse_pages(row[6])            # "Correct split pages (if wrong)"
        truth = predicted if "Correct" in verdict and "Partially" not in verdict else correction
        if not truth and not correction and "Correct" in verdict:
            truth = predicted
        pred_total += len(predicted)
        true_total += len(truth)
        tp += len(predicted & truth)
        fp += len(predicted - truth)
        fn += len(truth - predicted)

    metrics = _prf(tp, fp, fn)
    metrics.update({"pdfs": pdfs, "boundaries_predicted": pred_total,
                    "boundaries_true": true_total})
    return metrics
```

- [ ] **Step 4: Wire `--score` into MAIN**

Replace the `if args.score:` block in `main()` with:

```python
    if args.score:
        config = load_config()
        xlsx = SCRIPT_DIR / config["paths"]["output_reports"] / "predictions.xlsx"
        if not xlsx.exists():
            print(f"No report at {xlsx}. Run prediction mode first, then fill the Excel.")
            return
        m = score_reviewed_report(xlsx)
        print("Accuracy from reviewed report:")
        print(f"  PDFs reviewed        : {m['pdfs']}")
        print(f"  Boundaries predicted : {m['boundaries_predicted']}")
        print(f"  Boundaries (truth)   : {m['boundaries_true']}")
        print(f"  True positives       : {m['true_positives']}")
        print(f"  False positives      : {m['false_positives']}")
        print(f"  False negatives      : {m['false_negatives']}")
        print(f"  Precision            : {m['precision']:.3f}")
        print(f"  Recall               : {m['recall']:.3f}")
        print(f"  F1 score             : {m['f1']:.3f}")
        return
```

- [ ] **Step 5: Run selftest to verify pass**

Run: `python invoice_boundary_detector.py --selftest`
Expected: all checks PASS.

- [ ] **Step 6: End-to-end score check**

Open `output/reports/predictions.xlsx`, fill a few "Reviewer verdict" dropdowns (and "Correct split pages" where you mark something wrong), save, then run: `python invoice_boundary_detector.py --score`
Expected: prints Precision/Recall/F1 and the counts without error.

- [ ] **Step 7: Checkpoint (no git)**

Mark Task 9 done.

---

## Task 10: README + requirements + full-run polish

**Files:**
- Create: `README.md` (project root)
- Create: `requirements.txt`
- Modify: `invoice_boundary_detector.py` (optional tqdm progress bar in MAIN)

**Interfaces:** none new.

- [ ] **Step 1: Create `requirements.txt`**

```
PyMuPDF
pytesseract
Pillow
openpyxl
tqdm
```

- [ ] **Step 2: Create `README.md`**

Write a plain-English guide (for a CPA/CA) covering: what the tool does, the hard rule that it never splits PDFs, how to install (`pip install -r requirements.txt` + note Tesseract is already installed), where to put PDFs (`input/`), how to run the three modes, how to review the Excel (dropdowns + "correct split pages"), how to read the accuracy output, and how to tune `config.json` (weights/threshold/known vendors). Include the library table from the spec (§16). Match the explanatory style of `Tesseract_Testing/README.md`.

- [ ] **Step 3: (Optional) Add a tqdm progress bar**

In MAIN's PDF loop, wrap `pdfs` with `tqdm(pdfs, desc="PDFs", unit="file")` (import `from tqdm import tqdm` at top). If tqdm is not installed, skip.

- [ ] **Step 4: Full end-to-end run**

Run: `python invoice_boundary_detector.py` then `python invoice_boundary_detector.py --score` (after filling the Excel).
Expected: report regenerates; renamed copies present; originals untouched; scorer prints metrics; `--selftest` still passes.

- [ ] **Step 5: Checkpoint (no git)**

Mark Task 10 done. Update the handoff note.

---

## Self-Review (completed by author)

**Spec coverage:** Objective → Tasks 6–7. OCR/reasons → Task 2 (spec §13). Features → Task 3 (§7 FeatureRecord). Vendor layered detection → Task 4 (§9). Rules+confidence → Task 5 (§6). Excel summary+detail+dropdowns+styling → Task 7 (§10). Naming copy/dedup/mixed-annotate + originals safe → Task 8 (§11). Accuracy P/R/F1 → Task 9 (§12). Config-driven tunables → Task 1 + `config.json` (§3/§17). One script/one config → all tasks (§5/§6). No-split + no-git + copy-only → Global Constraints. README + libs → Task 10 (§16). Build phase order → Tasks map to spec §15 (Phase 0=Task 1, 1=Task 2, 2=Tasks 6–7, 3=Task 3, 4=Task 4, 5=Tasks 5–6, 6=Task 8, 7=Task 9).

**Placeholder scan:** README body in Task 10 Step 2 is described rather than fully written — acceptable because it is prose documentation, not code; contents are enumerated. All code steps contain complete code.

**Type consistency:** PageRecord/FeatureRecord/VendorResult/PagePrediction/PdfSummary dict keys are consistent across Tasks 2–9. `score_boundary`/`predict_boundaries`/`summarize_pdf`/`apply_naming`/`build_excel_report`/`score_reviewed_report` signatures match their call sites in MAIN.

**Adaptations from the standard template (intentional, per project rules):** git commits replaced by local "Checkpoint" steps (hard rule #4); pytest replaced by an in-script `--selftest` harness (one-script constraint); test-first kept for pure-logic tasks, run-on-samples verification for I/O tasks.
