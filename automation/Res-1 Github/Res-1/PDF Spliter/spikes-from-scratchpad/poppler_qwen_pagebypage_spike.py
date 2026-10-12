"""
SPIKE — Poppler + Qwen Vision, one page at a time
=================================================
THROWAWAY PROTOTYPE. Not part of the automation. Does not touch
invoice_boundary_detector.py, does not read config.json, does not move,
split, rename or delete anything. It renders page images to a temp folder,
asks the local Qwen vision model about each page, and PRINTS the result.

What it proves:
    PDF -> Poppler renders each page to a PNG -> each PNG goes to Qwen on its
    own -> Qwen returns small structured JSON per page -> PYTHON (not the
    model) works out the invoice boundaries from those page results.

Run:
    python poppler_qwen_pagebypage_spike.py "path\\to\\file.pdf"

Common options:
    --model qwen2.5vl:7b       exact Ollama tag (must match `ollama list`)
    --host  http://localhost:11434
    --dpi   200                render resolution
    --pages 1,2                only send these pages (fast iteration)
    --poppler "C:\\poppler\\bin"  if pdftoppm.exe is not on PATH
    --keep-images              leave the PNGs on disk and print where they are

Needs: Poppler (pdftoppm.exe) + Ollama running locally. No pip installs —
standard library only.
"""

import os
import re
import sys
import json
import time
import base64
import shutil
import argparse
import tempfile
import subprocess
import urllib.request
import urllib.error
from pathlib import Path


# ===========================================================================
# SECTION 0 — SETTINGS THAT DIFFER PER MACHINE
# Plain English: nothing about one particular PC belongs in the code. Each of
# these can be given three ways, and the first one found wins:
#     1. a command-line option        (--poppler / --host / --model)
#     2. an environment variable      (POPPLER_PATH / OLLAMA_HOST / QWEN_MODEL)
#     3. the fallback below
# That way this file can move to the client's PC or server unchanged - they
# set their own environment variables and nothing here is edited.
# ===========================================================================

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("QWEN_MODEL", "qwen2.5vl:7b")
DEFAULT_POPPLER = os.environ.get("POPPLER_PATH")  # None = look on PATH


# ===========================================================================
# SECTION 1 — THE PROMPT
# Plain English: what we ask Qwen about ONE page image.
#
# The order of the fields is deliberate and is the main lesson from the first
# run. The model writes its answer one field at a time, and each field it has
# already written influences the next. When "page_type" came FIRST, the model
# committed to a verdict before it had looked at anything, and called a
# remittance stub an invoice. So now it must first WRITE DOWN what it sees -
# the heading, the label on the main number, the invoice numbers listed - and
# only then classify. Evidence first, verdict last.
#
# The real giveaway on these documents is the LABEL next to the main number:
# a real invoice says "Invoice Number", a summary page says "Summary Number".
# The first prompt never mentioned that, so the model never used it.
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


# ===========================================================================
# SECTION 2 — RENDER (Poppler)
# Plain English: turn every page of the PDF into a PNG image using Poppler's
# pdftoppm. We render into a temporary folder, never next to the original PDF,
# and the original PDF is only ever READ.
# ===========================================================================

def find_pdftoppm(poppler_dir: str | None) -> str:
    """Locate pdftoppm.exe. Fails loudly - no silent fallback to another renderer."""
    if poppler_dir:
        exe = Path(poppler_dir) / "pdftoppm.exe"
        if not exe.exists():
            sys.exit(
                f"\nPoppler not found at: {exe}\n"
                f"--poppler must point at the 'bin' folder that contains pdftoppm.exe.\n"
            )
        return str(exe)

    found = shutil.which("pdftoppm")
    if not found:
        sys.exit(
            "\npdftoppm.exe not found on PATH.\n"
            "Install Poppler for Windows, then either add its bin folder to PATH\n"
            "or re-run with:  --poppler \"C:\\path\\to\\poppler\\bin\"\n"
        )
    return found


def render_pages(pdf_path: Path, out_dir: Path, dpi: int, pdftoppm: str) -> list:
    """Render every page to PNG. Returns [(page_number, image_path), ...] in order."""
    prefix = out_dir / "page"
    cmd = [pdftoppm, "-png", "-r", str(dpi), str(pdf_path), str(prefix)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"\nPoppler failed (exit {result.returncode}):\n{result.stderr}\n")

    images = list(out_dir.glob("page*.png"))
    if not images:
        sys.exit(f"\nPoppler ran but produced no images in {out_dir}\n")

    # pdftoppm writes page-1.png, page-2.png ... (zero-padded once there are
    # 10+ pages). Sort by the NUMBER, not by text, or page 10 sorts before 2.
    def page_num(p: Path) -> int:
        m = re.search(r"(\d+)$", p.stem)
        return int(m.group(1)) if m else 0

    return [(page_num(p), p) for p in sorted(images, key=page_num)]


# ===========================================================================
# SECTION 3 — ASK QWEN (one page image per request)
# Plain English: send ONE page image to the local model and get back small
# structured JSON. One page per request is deliberate - sending the whole
# document at once was tested before and did not work.
# ===========================================================================

def ask_qwen(image_path: Path, host: str, model: str, num_ctx: int, timeout: int,
             num_thread: int | None = None) -> dict:
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    options = {
        "num_ctx": num_ctx,        # 4096 default is too small for a page image
        "temperature": 0,          # deterministic - we need repeatable answers
    }
    if num_thread:
        # How many CPU threads Ollama may use. Left unset it picks its own
        # number, which on this machine is about half the logical cores.
        options["num_thread"] = num_thread
    payload = {
        "model": model,
        "prompt": PROMPT,
        "images": [b64],
        "stream": False,
        "format": "json",          # ask Ollama to guarantee valid JSON back
        "options": options,
    }
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        sys.exit(f"\nOllama returned HTTP {e.code}:\n{detail}\n"
                 f"If it says 'model not found', check the tag with: ollama list\n")
    except urllib.error.URLError as e:
        sys.exit(f"\nCould not reach Ollama at {host}: {e.reason}\n"
                 f"Check Ollama is running:  ollama list\n")

    raw = body.get("response", "")
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        # Show what the model actually said - do not paper over it.
        out = {"_unparsed": raw}
    # Ollama reports exactly how much work it did. "prompt tokens" is almost
    # entirely the page image, and it is what makes a page slow.
    if isinstance(out, dict):
        out["_prompt_tokens"] = body.get("prompt_eval_count")
        out["_reply_tokens"] = body.get("eval_count")
    return out


# ===========================================================================
# SECTION 4 — ENFORCE THE PAGE TYPE (Python applies the rule)
# Plain English: the model's job is to READ the page and report what is printed
# on it. Deciding what that means is Python's job, so the decision is the same
# every time instead of depending on the model's mood.
#
# If the model reports a heading of "Remittance" and then still calls the page
# an INVOICE, Python corrects it - and PRINTS that it did. The disagreement is
# shown, never hidden, because it is exactly the evidence we are testing for.
# ===========================================================================

SUMMARY_WORDS = ("remittance", "summary", "statement", "index")


def enforce_page_type(data: dict):
    """Returns (page_type, override_reason). override_reason is None if the
    model already agreed with the rule."""
    model_said = str(data.get("page_type") or "").upper()
    heading = str(data.get("document_heading") or "")
    label = str(data.get("primary_number_label") or "")
    listed = data.get("invoice_numbers_listed")
    listed = listed if isinstance(listed, list) else []

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
# SECTION 5 — ASSEMBLE (Python decides, not the model)
# Plain English: the model only ever sees one page, so it cannot know where an
# invoice ENDS. Python walks the page results in order and works out the
# invoice structure. An INVOICE page starts a new invoice, unless it repeats
# the invoice number we are already inside. CONTINUATION pages extend the
# invoice above them. SUMMARY and OTHER pages belong to no invoice.
# ===========================================================================

def assemble(page_results: list) -> list:
    invoices = []
    current = None

    for page_no, data in page_results:
        ptype = str(data.get("page_type") or "").upper()
        number = data.get("invoice_number")

        if ptype == "INVOICE":
            same_as_open = current is not None and number and number == current["invoice_number"]
            if same_as_open:
                current["pages"].append(page_no)
            else:
                current = {
                    "invoice_number": number,
                    "vendor": data.get("vendor"),
                    "total": data.get("invoice_total"),
                    "pages": [page_no],
                }
                invoices.append(current)

        elif ptype == "CONTINUATION" and current is not None:
            current["pages"].append(page_no)

        else:
            # SUMMARY / OTHER / unreadable: belongs to no invoice, and closes
            # whatever invoice was open so a later page cannot attach to it.
            current = None

    return invoices


# ===========================================================================
# SECTION 6 — MAIN
# ===========================================================================

def main():
    ap = argparse.ArgumentParser(description="Poppler + Qwen page-by-page spike")
    ap.add_argument("pdf", help="path to the PDF to analyse")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--model", default="qwen2.5vl:7b", help="exact tag from `ollama list`")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--timeout", type=int, default=300, help="seconds per page")
    ap.add_argument("--num-thread", type=int, default=None,
                    help="CPU threads Ollama may use (unset = let Ollama decide)")
    ap.add_argument("--pages", default=None,
                    help="only send these pages, e.g. 1,2 (for fast iteration)")
    ap.add_argument("--poppler", default=None, help="poppler bin folder, if not on PATH")
    ap.add_argument("--keep-images", action="store_true")
    args = ap.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        sys.exit(f"\nPDF not found: {pdf_path}\n")

    pdftoppm = find_pdftoppm(args.poppler)
    work_dir = Path(tempfile.mkdtemp(prefix="qwen_spike_"))

    print(f"PDF     : {pdf_path.name}")
    print(f"Model   : {args.model}   Host: {args.host}")
    print(f"Render  : Poppler @ {args.dpi} dpi -> {work_dir}")
    print()

    pages = render_pages(pdf_path, work_dir, args.dpi, pdftoppm)

    partial = False
    if args.pages:
        wanted = {int(n) for n in re.findall(r"\d+", args.pages)}
        pages = [(n, p) for (n, p) in pages if n in wanted]
        partial = True
        if not pages:
            sys.exit(f"\n--pages {args.pages} matched no pages in this PDF.\n")

    print(f"Rendered {len(pages)} page image(s). Sending one at a time.\n")

    page_results = []
    started = time.time()

    for page_no, img in pages:
        t0 = time.time()
        data = ask_qwen(img, args.host, args.model, args.num_ctx, args.timeout,
                        args.num_thread)
        elapsed = time.time() - t0

        if "_unparsed" in data:
            print(f"  Page {page_no}: MODEL DID NOT RETURN VALID JSON  ({elapsed:.1f}s)")
            print(f"    raw: {data['_unparsed'][:300]}")
            page_results.append((page_no, data))
            continue

        page_type, override = enforce_page_type(data)
        data["page_type"] = page_type
        page_results.append((page_no, data))

        listed = data.get("invoice_numbers_listed")
        listed = listed if isinstance(listed, list) else []

        ptok, rtok = data.get("_prompt_tokens"), data.get("_reply_tokens")
        speed = f"  {ptok/elapsed:.0f} tok/s" if ptok else ""
        print(f"  Page {page_no}: {page_type:<13} ({elapsed:.1f}s"
              f"{f', {ptok} image+prompt tokens, {rtok} reply' if ptok else ''}{speed})")
        print(f"      heading  : {data.get('document_heading') or '-'}")
        print(f"      label    : {data.get('primary_number_label') or '-'}"
              f"  ->  {data.get('primary_number') or '-'}")
        print(f"      inv# seen : {', '.join(str(x) for x in listed) if listed else '(none)'}")
        print(f"      vendor   : {data.get('vendor') or '-'}")
        if page_type == "INVOICE":
            print(f"      invoice  : #{data.get('invoice_number') or '-'}"
                  f"   total {data.get('invoice_total') or '-'}")
        if override:
            print(f"      OVERRIDE : {override}")
        print()

    total_time = time.time() - started
    invoices = assemble(page_results)

    print("=" * 72)
    if partial:
        print(f"PARTIAL RUN (--pages {args.pages}) - the invoice count below covers")
        print("only the pages sent, so treat it as per-page evidence, not a result.")
        print("-" * 72)
    print(f"RESULT: {len(invoices)} invoice(s) found")
    for i, inv in enumerate(invoices, start=1):
        pg = ", ".join(str(p) for p in inv["pages"])
        print(f"  {i}. pages {pg:<10} {inv['vendor'] or '(no vendor)'}"
              f"  #{inv['invoice_number'] or '(no number)'}"
              f"  {inv['total'] or '(no total)'}")
    starts = ", ".join(str(inv["pages"][0]) for inv in invoices)
    print(f"\n  Invoices start on page(s): {starts or '(none)'}")
    print(f"  Total time: {total_time:.1f}s for {len(pages)} page(s)"
          f"  ({total_time / max(len(pages), 1):.1f}s per page)")
    print("=" * 72)

    if args.keep_images:
        print(f"\nPage images kept at: {work_dir}")
    else:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
