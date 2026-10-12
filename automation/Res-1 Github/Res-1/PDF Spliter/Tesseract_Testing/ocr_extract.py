"""
OCR Invoice/Statement Extractor
--------------------------------
Scans all subfolders under Tesseract_Testing for PDFs,
runs OCR on every page, detects invoice/statement boundaries,
and extracts structured fields into .txt output files.

Requirements:
    pip install PyMuPDF pytesseract tqdm Pillow
    Tesseract-OCR installed and on PATH
"""

import os
import re
import sys
import logging
from pathlib import Path
from datetime import datetime

import io
import fitz  # PyMuPDF — converts PDF pages to images (replaces Poppler)
from PIL import Image
import pytesseract
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR  # .txt files land in Tesseract_Testing/
LOG_FILE = SCRIPT_DIR / "ocr_errors.log"

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\Dhruv Champaneria\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ocr_extract")

# ---------------------------------------------------------------------------
# Patterns used to detect document boundaries and extract fields
# ---------------------------------------------------------------------------

# Patterns that signal the start of a new invoice / statement / document.
# Each pattern captures the document number in group 1.
DOC_NUMBER_PATTERNS = [
    re.compile(r"(?:invoice|inv)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.IGNORECASE),
    re.compile(r"(?:statement)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.IGNORECASE),
    re.compile(r"(?:bill|receipt|credit\s*memo|debit\s*memo)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.IGNORECASE),
    re.compile(r"(?:purchase\s*order|po)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.IGNORECASE),
    re.compile(r"(?:order)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{1,30})", re.IGNORECASE),
]

# Broader fallback: looks for a standalone "# 123456" or "No. ABC-789" style
GENERIC_DOC_NUMBER = re.compile(
    r"(?:^|\n)\s*(?:#|no\.?|number)\s*[:\-]?\s*([A-Z0-9][\w\-/]{3,30})",
    re.IGNORECASE,
)

# Field extraction patterns
DATE_PATTERNS = [
    re.compile(r"(?:date|dated|invoice\s*date|statement\s*date|bill\s*date|due\s*date)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", re.IGNORECASE),
    re.compile(r"(?:date|dated|invoice\s*date|statement\s*date|bill\s*date|due\s*date)\s*[:\-]?\s*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{2,4})", re.IGNORECASE),
    re.compile(r"(?:date|dated|invoice\s*date|statement\s*date|bill\s*date|due\s*date)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\.?\s+\d{2,4})", re.IGNORECASE),
]

AMOUNT_PATTERNS = [
    re.compile(r"(?:total\s*(?:due|amount|balance)?|amount\s*due|balance\s*due|grand\s*total|net\s*amount)\s*[:\-]?\s*\$?\s*([\d,]+\.\d{2})", re.IGNORECASE),
    re.compile(r"(?:total|amount|balance)\s*[:\-]?\s*\$\s*([\d,]+\.\d{2})", re.IGNORECASE),
]

VENDOR_PATTERNS = [
    re.compile(r"(?:from|vendor|supplier|company|billed?\s*by|sold\s*by)\s*[:\-]?\s*(.+?)(?:\n|$)", re.IGNORECASE),
]

BILL_TO_PATTERNS = [
    re.compile(r"(?:bill\s*to|billed?\s*to|sold\s*to|ship\s*to|customer|client|attn)\s*[:\-]?\s*(.+?)(?:\n|$)", re.IGNORECASE),
]

DUE_DATE_PATTERNS = [
    re.compile(r"(?:due\s*date|payment\s*due|pay\s*by|due\s*on)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", re.IGNORECASE),
    re.compile(r"(?:due\s*date|payment\s*due|pay\s*by|due\s*on)\s*[:\-]?\s*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{2,4})", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def find_doc_number(text: str) -> str | None:
    """Return the first invoice/statement/document number found in text."""
    for pattern in DOC_NUMBER_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    m = GENERIC_DOC_NUMBER.search(text)
    if m:
        return m.group(1).strip()
    return None


def extract_first(patterns: list[re.Pattern], text: str) -> str | None:
    """Return the first match from a list of compiled regex patterns."""
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip()
    return None


def extract_fields(text: str) -> dict:
    """Pull structured fields out of OCR text for one document segment."""
    return {
        "Document Number": find_doc_number(text),
        "Date": extract_first(DATE_PATTERNS, text),
        "Due Date": extract_first(DUE_DATE_PATTERNS, text),
        "Vendor / Company": extract_first(VENDOR_PATTERNS, text),
        "Bill To": extract_first(BILL_TO_PATTERNS, text),
        "Total / Amount Due": extract_first(AMOUNT_PATTERNS, text),
    }


def segment_pages(pages_text: list[str]) -> list[dict]:
    """
    Group pages into document segments based on detected document numbers.

    Logic:
      - Scan each page for a document number.
      - If a NEW number appears (different from the current segment's number),
        start a new segment.
      - Pages with no detected number are appended to the current segment.
      - If no numbers are found at all, the entire PDF is one segment.

    Returns a list of dicts:
        {"doc_number": str|None, "pages": [int], "text": str}
    """
    segments: list[dict] = []
    current_number = None
    current_text_parts: list[str] = []
    current_pages: list[int] = []

    for i, page_text in enumerate(pages_text):
        detected = find_doc_number(page_text)

        if detected and detected != current_number:
            # Save previous segment (if any)
            if current_text_parts:
                segments.append({
                    "doc_number": current_number,
                    "pages": list(current_pages),
                    "text": "\n".join(current_text_parts),
                })
            # Start new segment
            current_number = detected
            current_text_parts = [page_text]
            current_pages = [i + 1]
        else:
            current_text_parts.append(page_text)
            current_pages.append(i + 1)

    # Final segment
    if current_text_parts:
        segments.append({
            "doc_number": current_number,
            "pages": list(current_pages),
            "text": "\n".join(current_text_parts),
        })

    return segments


def format_output(pdf_name: str, segments: list[dict]) -> str:
    """Build the final structured text output for one PDF."""
    lines = []
    lines.append(f"{'=' * 70}")
    lines.append(f"  Source file: {pdf_name}")
    lines.append(f"  Processed : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Documents found: {len(segments)}")
    lines.append(f"{'=' * 70}\n")

    for idx, seg in enumerate(segments, start=1):
        fields = extract_fields(seg["text"])
        page_range = ", ".join(str(p) for p in seg["pages"])

        lines.append(f"--- Document {idx} (pages: {page_range}) ---")
        for label, value in fields.items():
            display = value if value else "(not detected)"
            lines.append(f"  {label:<25s}: {display}")
        lines.append("")  # blank line between documents

    return "\n".join(lines)


def collect_pdfs(base_dir: Path) -> list[Path]:
    """Recursively find all PDF files under base_dir."""
    return sorted(base_dir.rglob("*.pdf"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pdf_files = collect_pdfs(SCRIPT_DIR)

    if not pdf_files:
        log.warning("No PDF files found under %s", SCRIPT_DIR)
        return

    log.info("Found %d PDF(s) to process.", len(pdf_files))

    # Outer progress bar: per PDF
    for pdf_path in tqdm(pdf_files, desc="PDFs", unit="file"):
        pdf_name = pdf_path.name
        log.info("Processing: %s", pdf_path)

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            log.error("SKIPPED %s — could not open PDF: %s", pdf_name, e)
            continue

        pages_text: list[str] = []

        # Inner progress bar: per page
        for page_num, page in enumerate(
            tqdm(doc, total=doc.page_count, desc=f"  Pages ({pdf_name})", unit="pg", leave=False),
            start=1,
        ):
            try:
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img)
                pages_text.append(text)
            except Exception as e:
                log.error(
                    "SKIPPED page %d of %s — OCR failed: %s", page_num, pdf_name, e
                )
                pages_text.append("")  # placeholder so page numbering stays correct

        doc.close()

        # Segment the pages into separate documents
        try:
            segments = segment_pages(pages_text)
        except Exception as e:
            log.error("SKIPPED %s — segmentation failed: %s", pdf_name, e)
            continue

        # Build and write output
        output_text = format_output(pdf_name, segments)
        out_filename = pdf_path.stem + ".txt"
        out_path = OUTPUT_DIR / out_filename

        try:
            out_path.write_text(output_text, encoding="utf-8")
            log.info("Saved: %s  (%d document(s))", out_path.name, len(segments))
        except Exception as e:
            log.error("Could not write %s: %s", out_path, e)

    log.info("Done. Check %s for any errors.", LOG_FILE.name)


if __name__ == "__main__":
    main()
