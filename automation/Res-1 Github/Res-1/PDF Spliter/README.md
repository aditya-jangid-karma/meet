# Invoice Boundary Detection Engine

**What this is:** a tool that reads a PDF that may contain several invoices stapled together, and guesses which page each new invoice starts on. It writes those guesses into an Excel file so a human can check them.

## The one hard rule

**This tool never splits or changes any PDF.** It only *reads* PDFs and *writes*: an Excel report, small debug text files, and — for single-vendor PDFs only — a renamed **copy** of the file. Your original PDFs in `input/` are never touched, edited, or deleted. Actual splitting into separate invoice files is a future project, only after we've proven the guesses above are accurate enough.

## How it works, in plain English

1. **Read every page.** For each PDF in the `input/` folder, the script turns every page into a picture and reads the text off it using OCR (Optical Character Recognition — software that reads text from images). This happens for every page, even ones that already have "real" text in the PDF, so behavior is consistent.
2. **Pull out clues.** From each page's text, it tries to find things like the Invoice #, the Date, the Total, and who the Vendor is.
3. **Compare each page to the one before it.** A set of independent "rules" look for signs that a *new* invoice has started — e.g., "the Invoice # changed" or "the Vendor changed" — versus signs the page is just a continuation of the same invoice — e.g., "same vendor as before" or "says 'continued...'". Each rule adds or subtracts points.
4. **Decide Break or Continue.** If the points add up to 50 or more (configurable), the script guesses "a new invoice starts here." Otherwise it guesses "this continues the previous invoice."
5. **Write the Excel report** — this is the main output you'll actually look at. See below.
6. **Rename copies for single-vendor PDFs.** If an entire PDF turned out to be one vendor, a *copy* is placed in `output/renamed/` named after that vendor (e.g., `Ferguson Facility Supply.pdf`, then `..._01.pdf` if that vendor shows up again). If a PDF has more than one vendor mixed together, it is **not** renamed — the Excel shows you where each vendor's invoice starts instead.

## Installing (one-time setup)

1. Make sure Python is installed (this project was built and tested on Python 3.13, needs 3.10 or newer).
2. Open a terminal in this folder and run:
   ```
   pip install -r requirements.txt
   ```
3. Tesseract OCR should already be installed on this PC. Its install location is set in `config.json` under `"tesseract_cmd"` — if you ever reinstall Tesseract somewhere else, update that one line.

## Running it

Put your sample/test PDFs in a folder named `input/` in this same directory (create it if it doesn't exist yet). Then, from a terminal in this folder:

| Command | What it does |
|---|---|
| `python invoice_boundary_detector.py` | Reads every PDF in `input/`, predicts split points, writes `output/reports/predictions.xlsx`, and creates renamed copies in `output/renamed/` for single-vendor PDFs. |
| `python invoice_boundary_detector.py --score` | After you've reviewed and filled in `predictions.xlsx` (see below), this reads it back and prints accuracy numbers (Precision, Recall, F1). |
| `python invoice_boundary_detector.py --selftest` | Runs the built-in checks that prove the core logic still works correctly. Useful any time you or a developer changes the script. |

## Reviewing the Excel report (`output/reports/predictions.xlsx`)

It has two tabs:

- **Summary** (the one you'll use day-to-day): one row per PDF, showing the pages it thinks new invoices start on, how many invoices it found, and the vendor(s). There's a **"Reviewer verdict" dropdown** with four choices:
  - ✅ Correct — the guess was right, nothing more to do.
  - ⚠️ Partially correct
  - ❌ Incorrect
  - 🔍 Needs a closer look
  
  If you pick anything other than ✅ Correct, also type the real starting page numbers into the **"Correct split pages (if wrong)"** cell next to it (e.g., `1, 6, 9`). This is what lets the tool measure real accuracy later — you don't have to review every single page, just correct the ones that are wrong.

- **Page Detail** (only open this if you want to know *why* the script made a call): one row per page showing its Break/Continue decision, confidence, score, and — most usefully — the plain-English reasons ("Invoice number changed (+100)", "Same vendor as previous page (-20)", etc.). Rows where it called a Break are shaded light green.

## Reading the accuracy numbers (`--score`)

After you've filled in some verdicts and run `--score`, you'll see:
- **Precision** — of all the split points the script guessed, what fraction were actually correct.
- **Recall** — of all the real split points, what fraction did the script find.
- **F1 score** — a single number balancing Precision and Recall (higher is better, 1.0 is perfect).

These numbers are how we'll judge whether the detection is good enough to eventually enable real PDF splitting — which, again, is a separate future step.

## Tuning behavior (`config.json`)

This is the ONE settings file — no code changes needed to adjust behavior:

- `"paths"` — where PDFs come from and where output goes.
- `"tesseract_cmd"` — the Tesseract OCR install location on this PC.
- `"ocr": {"dpi": 300}` — image quality for OCR. Higher = more accurate but slower.
- `"thresholds": {"break_at_score": 50}` — the score needed to call a page "a new invoice starts here." Raise it to make the tool more conservative (fewer, more confident splits); lower it to catch more possible splits at the risk of more false alarms.
- `"rule_weights"` — how many points each rule is worth. Defaults: Invoice # changed +100, Vendor changed +40, Invoice header detected +30, Same vendor as before −20, Looks like a continuation −40.
- `"known_vendors"` — a list of vendor names you already know about, e.g. `["Ferguson Facility Supply", "ABC Plumbing LLC"]`. Any vendor on this list is recognized instantly and reliably; as you review reports and see vendors it missed or is unsure about, add them here to make future runs more accurate.

## The libraries this script uses (and why)

| Library | What it's for |
|---|---|
| **PyMuPDF** (imported as `fitz`) | Opens PDF files and turns each page into an image, so OCR can read it. |
| **pytesseract** | Sends that page image to Tesseract OCR and gets back the text it can read. |
| **Pillow** (imported as `PIL`) | Handles the in-memory image between PyMuPDF and pytesseract. |
| **openpyxl** | Builds and reads the `.xlsx` Excel report — including the colored headers and the reviewer-verdict dropdown, and later reading your filled-in answers back for scoring. |
| **tqdm** (optional) | Shows a small progress bar while processing many PDFs. If it's not installed, the script still runs fine, just without the progress bar. |
| `json`, `re`, `pathlib`, `shutil` (built into Python) | Reading `config.json`, pattern-matching text (regular expressions), working with file paths, and copying files safely. |

## The one script, one config file design

Everything lives in `invoice_boundary_detector.py`, organized into clearly labeled sections (CONFIG, READER, FEATURES, VENDOR, RULES, CONFIDENCE, NAMING, REPORT, SCORER, SELFTEST, MAIN) — each with a plain-English comment block explaining what it does before the code. All the numbers you might want to tune live in `config.json`, not buried in code. This is intentional so the whole project stays easy for a non-engineer to open, read top-to-bottom, and maintain.

## Project status / what's NOT built yet

- Actual PDF splitting — deferred until detection accuracy is proven via the `--score` numbers above.
- OneDrive integration — `input/` is currently a plain local folder in this project. When splitting is implemented later, this can point at a OneDrive-synced folder instead (one line in `config.json`).
- This project has version control (git) intentionally turned OFF for now — it's local-only.
