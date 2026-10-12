# Design Spec — Rule-Based Invoice Boundary Detection Engine

**Date:** 2026-07-24
**Status:** Draft for review (brainstorming output; precedes the implementation plan)
**Owner:** Team D (Dhruv / Puneet / Manish / Vijayesh)
**Related:** `Invoice_Boundary_Detection_Project_Summary.md` (original brief), `Tesseract_Testing/ocr_extract.py` (prior OCR work to reuse)

---

## 1. Objective (plain English)

Build a Python tool that reads multi-invoice PDFs and **predicts which page each new invoice starts on**, then writes those proposed split points — with reasoning — into a reviewer-friendly Excel file. A human reviews the predictions in Excel, and the tool measures its own accuracy against that review.

**This version does NOT split PDFs.** It only *detects and reports* boundaries so we can prove accuracy first. Actual splitting is a separate, later project.

---

## 2. Scope

### In scope (this spec)
- Read every page of each PDF via OCR.
- Extract fields (invoice number, date, total, vendor, etc.).
- Detect invoice boundaries using independent, weighted rules + a confidence score.
- Explain *why* each boundary decision was made.
- Produce a styled Excel report with reviewer dropdowns.
- Rename single-vendor files (copies only) / annotate mixed-vendor files.
- Score accuracy (Precision / Recall / F1) from the reviewed Excel.

### Out of scope (deferred to later specs)
- **Actual PDF splitting** (the tool has NO PDF-writing capability, by design).
- Live OneDrive / cloud API integration.
- AI / machine-learning document understanding.
- Buildertrend / Nexus integration, review UI, analytics dashboard.

---

## 3. Hard constraints / guardrails

1. **No PDF splitting.** The tool must not write or cut PDFs. It only reads and reports.
2. **Never modify originals.** Any renaming happens on **copies** written to an output folder; source PDFs are never touched.
3. **No secrets in code or git.** Tesseract path and folder paths live in `config.json`, not hard-coded secrets. No API keys/passwords anywhere.
4. **Config-driven.** Rule weights, thresholds, paths, and the vendor list live in **one `config.json`** so a CPA/CA can tune them without touching code.
5. **Maintainable by non-engineers.** The single script is heavily commented in plain English, and a project README explains the libraries and logic (per CLAUDE.md).

---

## 4. Existing assets to reuse

- **`Tesseract_Testing/ocr_extract.py`** — a working OCR extractor. Reuse its approach: open PDF with **PyMuPDF (`fitz`)**, render each page to a 300-DPI image, OCR with **pytesseract**. Its regex field patterns are a starting point for feature extraction.
  - Its `segment_pages()` uses a single naive signal ("document number changed → new segment"). We keep this as a **baseline to beat**, not the final engine.
  - **Poppler is NOT used** — PyMuPDF replaced it. The `poppler-windows/` folder and the Poppler instructions in that README/handoff are stale and should be ignored/removed.
- **~20 sample PDFs** currently in the project (invoices/statements). These become our test + tuning data. (No dedicated vendor list exists yet — see §9.)

---

## 5. Architecture & folder structure

Deliberately simple: **one config file, one script.**

```
Res1/
├── input/                          ← PDFs to process (a project subfolder for now; OneDrive later). Path is set in config.json.
├── output/
│   ├── reports/                    ← the generated Excel report(s)
│   └── renamed/                    ← renamed COPIES of single-vendor PDFs (originals untouched)
├── config.json                     ← the ONE config: paths, Tesseract location, thresholds, rule weights, vendor list
├── invoice_boundary_detector.py    ← the ONE script (heavily commented, organized in labeled sections — see §6)
├── README.md                       ← plain-English guide for the team
└── docs/superpowers/specs/         ← this spec
```

**Design principle:** the logic still has clear internal boundaries (§6) — they're just organized as **labeled, commented sections inside the single script** rather than separate files. No part of the script writes PDFs.

---

## 6. The single script — internal sections

`invoice_boundary_detector.py` is one file, split into clearly-commented sections. Each section starts with a plain-English comment block explaining, for a non-technical reader, *what it does, why, and how it connects to the next section.*

| # | Section (comment-labeled) | Does what |
|---|---|---|
| 1 | **CONFIG** | Load `config.json` (paths, Tesseract location, thresholds, rule weights, vendor list) |
| 2 | **READER** | OCR every page (reuses `ocr_extract` logic); record read failures + reasons |
| 3 | **FEATURES** | Pull structured fields from each page's text |
| 4 | **VENDOR** | Determine vendor(s) with a confidence score (§9) |
| 5 | **RULES** | Independent scored rules, each returning a score + a plain-English reason |
| 6 | **CONFIDENCE** | Combine rule scores vs thresholds → Break/Continue + confidence + fired rules |
| 7 | **NAMING** | Single-vendor → rename a copy (`_01` dedup); mixed → annotate |
| 8 | **REPORT** | Build the styled Excel (summary + detail sheets, dropdowns) |
| 9 | **SCORER** | Read reviewed Excel back → Precision/Recall/F1 (runs in "score mode") |
| 10 | **MAIN / PIPELINE** | Orchestrate the flow over the input folder; pick normal vs score mode |

**Two run modes** (chosen by a simple command-line flag):
- `python invoice_boundary_detector.py` → normal: read PDFs → predict → write Excel.
- `python invoice_boundary_detector.py --score` → read the reviewed Excel → print accuracy metrics.

---

## 7. Data models (simple records passed between sections)

Plain Python dictionaries/objects handed from one section to the next:

- **PageRecord:** `pdf_name, page_number, text, read_status ("ok"/"failed"), read_reason (if failed)`
- **FeatureRecord:** `page_number, invoice_number, date, due_date, vendor_raw, bill_to, total, currency, po_number` (missing = `None`)
- **VendorResult:** `vendor_name, confidence (high/med/low), source (known-list/top-of-page/domain/label/none)`
- **PagePrediction:** `page_number, decision (Break/Continue), confidence, total_score, fired_rules (list of reasons)`
- **PdfSummary:** `pdf_name, page_count, split_pages (with vendor per split), invoice_count, renamed_to (if any)`

---

## 8. Pipeline / data flow

```
input/*.pdf
   → READER      (OCR every page → PageRecords, with reasons for any unreadable page)
   → FEATURES    (fields per page → FeatureRecords)
   → VENDOR      (vendor per invoice → VendorResults)
   → RULES       (score each page boundary)
   → CONFIDENCE  (Break/Continue + why, per page → PagePredictions)
   → NAMING      (single-vendor rename copy / mixed annotate → PdfSummary)
   → REPORT      (Excel: summary sheet + detail sheet)
[separate run, --score] SCORER: reviewed Excel → Precision/Recall/F1
```

---

## 9. Vendor detection (layered, most-reliable first)

1. **Known-vendor list** (a list inside `config.json`, **starts empty**) — if any listed vendor name appears on the page, use it. Highest reliability. Grows over time.
2. **Top-of-page company name** — read the letterhead/top region of the first page of each invoice; take the most prominent company-like line.
3. **Corroborating clues** — company suffixes (`LLC/Inc/Co/Supply`), the Remit-To/address block, and email/website **domain** (e.g. `@fergusonsupply.com` → Ferguson).
4. **Label fallback** — the old `From:/Vendor:` search, for the rare invoice that labels it.
5. **Confidence + flag** — attach high/med/low confidence; low-confidence vendors are flagged in the Excel for the reviewer. Never trusted silently.

Combination: known-list wins → else top-of-page + suffix/domain → else label → else `(needs review)`.

---

## 10. Excel report design

**Sheet 1 — Summary (main reviewer view):** one row per PDF.

| Column | Content |
|---|---|
| PDF | filename (or renamed name for single-vendor) |
| Pages | total page count |
| New invoice starts at | predicted split pages; for mixed-vendor, vendor shown per split (e.g. `p1 – Vendor A, p5 – Vendor B`) |
| # invoices | count found |
| Confidence | overall summary confidence |
| **Reviewer verdict** | **dropdown:** ✅ Correct / ⚠️ Partially correct / ❌ Incorrect / 🔍 Needs a closer look |
| Correct split pages (if wrong) | reviewer types true pages only when marking wrong (feeds accuracy) |

**Sheet 2 — Page detail (the "why"):** one row per page — page #, decision (Break/Continue), confidence, total score, **fired rules/reasons**, and read-failure reason if the page couldn't be OCR'd.

**Styling:** clean header band, subtle row shading, color-coded verdict cells (green/amber/red). Professional, lightly colored. Dropdowns via openpyxl data validation.

---

## 11. Naming logic

- **Single-vendor PDF** (all invoices inside = one vendor) → write a **renamed copy** to `output/renamed/` as `Vendor Name.pdf`; on repeats, `Vendor Name_01.pdf`, `_02`, … Original stays in `input/`.
- **Mixed-vendor PDF** (more than one vendor) → **do not rename**; keep original name and annotate the vendor at each split point in the Excel.
- Script auto-decides single vs mixed by comparing detected vendors. Illegal filename characters are sanitized.

---

## 12. Accuracy scorer

- Runs as a separate "score mode" (`--score`) after the reviewer fills the Excel.
- Reads the **Reviewer verdict** + **Correct split pages** columns as ground truth.
- Computes: total pages, total boundaries, correct predictions, false positives, false negatives, **Precision, Recall, F1**, boundary-detection accuracy.
- The naive baseline (existing `segment_pages`) can be scored too, to show the rule engine's improvement.

---

## 13. Error handling (per the brief's exception list)

- **Unreadable page** → record the reason (file won't open, image conversion fails, OCR error), place an empty-text placeholder so page numbering stays correct, and surface the reason in the log AND the Excel.
- **Blank pages / separator sheets** → treated as continuation unless a rule says otherwise; flagged.
- **Rotated / landscape pages** → auto-rotate before OCR where possible.
- **Credit notes / statements / packing slips / duplicates** → handled as their own document types by the rules where detectable; otherwise flagged for review.
- **Low OCR confidence / mixed formats** → lower the prediction confidence and flag.
- Corrupted PDF → log + skip that file, continue with the rest.

---

## 14. Testing

- Because it's a single script, verification is done by **running it on the ~20 sample PDFs** and checking the output, rather than formal unit-test files:
  - **Reader check:** run on 2–3 samples → confirm text out + reasons for any failures.
  - **Report check:** open the Excel → confirm dropdowns + formatting.
  - **End-to-end:** run on all samples → eyeball predictions, then use `--score` once a small ground-truth is filled.
- Optional: a small separate `test_checks.py` can be added later if the team wants automated checks, but it is not required for v1.
- No real vendor list yet, so vendor checks start with the top-of-page/domain layers.

---

## 15. Build & test phases (implementation order — walking skeleton)

- **Phase 0 — Setup:** folders, `config.json`, virtual env, install libs, confirm Tesseract path. *Test: script finds sample PDFs.*
- **Phase 1 — Reader:** reuse OCR logic; log reasons for unreadable pages. *Test: text + reasons on samples.*
- **Phase 2 — Excel skeleton (thin end-to-end):** naive boundaries → real styled Excel + dropdowns. *Test: open Excel, dropdowns/formatting work.*
- **Phase 3 — Field extraction:** strengthen field pulls. *Test: fields vs actual PDFs.*
- **Phase 4 — Vendor detection:** layered approach + confidence flag. *Test: vendor accuracy on samples.*
- **Phase 5 — Rule + confidence engine:** independent scored rules → Break/Continue + reasons. *Test: vs naive baseline.*
- **Phase 6 — Naming:** single-vendor rename copy / mixed annotate. *Test: copies in `output/renamed/`, originals untouched.*
- **Phase 7 — Accuracy scorer:** reviewed Excel → metrics. *Test: metrics on a small ground-truth.*
- **Then:** tune `config.json` → re-run → re-measure until accuracy is consistently high.

---

## 16. Python libraries

| Library | Role |
|---|---|
| **PyMuPDF** (`fitz`) | Open PDF, render each page to an image (replaced Poppler) |
| **pytesseract** | Bridge to the installed Tesseract OCR engine (reads the page-image → text) |
| **Pillow** (`PIL`) | Holds/passes the page-image between PyMuPDF and pytesseract |
| **openpyxl** | Build the Excel report: formatting + reviewer dropdowns |
| **tqdm** *(optional)* | Terminal progress bar |

`config.json` is read with Python's **built-in `json`** module — no extra library needed. All the above are free and installed with one `pip install`. Tesseract itself is already installed on Dhruv's PC.

---

## 17. Open items

- **Vendor list** in `config.json` starts empty; fill in real vendors over time to boost accuracy.
- **Confidence thresholds** (auto-approve vs manual review) ship with sensible defaults in `config.json`, tuned once we see real accuracy numbers.
- **Default rule weights** (starting point from the brief): Invoice # changed +100, Vendor changed +40, Invoice header +30, Same vendor −20, Continuation pattern −40.
- **Input folder** is a project subfolder for now; switches to OneDrive later (config change).
- **Version control:** this project is **local-only by hard rule** — no git actions at all. The spec and code live as plain local files. (See CLAUDE.md hard rule #4.)
