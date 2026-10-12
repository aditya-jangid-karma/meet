# Handoff — Switched Excel output to the new 8-column format; mid-investigation on a vendor-detection bug

**Date:** 2026-07-24 (Session 4)
**Session focus:** (1) Change the script so its output goes into the existing `predictions.xlsx` in the reviewer's new "Proposed Summary Sheet" format, with NO PDF renaming — done and verified. (2) Start debugging why vendor detection often returns no vendor — root-cause investigation done from code review; a read-only diagnostic was written and the user is about to run it. Awaiting its output before proposing a fix.

---

## 1. What happened this session

### Resumed and caught up
Ran `/resume`: read CLAUDE.md, found no MEMORY.md yet, read the Session 3 handoff. The tool was already built (10 sections, 15/15 self-tests) and had been run once on 30 real PDFs.

### Reworked the Excel output to the reviewer's new format (approved, built, verified)
The user had manually added a third tab, **"Proposed Summary Sheet"** (header row only, 8 columns), to `output/reports/predictions.xlsx`, and wants the script to write its results into the **`Summary`** tab using that exact layout — and to **stop making renamed PDF copies** (just type the proposed name as text in column B). After confirming the plan and getting an explicit "go", these edits were made to `invoice_boundary_detector.py`:

1. **`summarize_pdf`** — renamed the `renamed_to` field to `proposed_name`.
2. **`build_excel_report`** — now **opens the existing `predictions.xlsx`** with `load_workbook` (or starts a fresh workbook if none exists) instead of building a new one from scratch and overwriting the file. This **preserves the user's "Proposed Summary Sheet" template tab.** It deletes+recreates the `Summary` tab at index 0 in the new **8-column** format (PDF Original Name · Proposed PDF Name · Pages · New invoice starts at · # invoices · Vendors · Reviewer verdict · Correct split pages), with the verdict dropdown now on **column G**. It also deletes+recreates `Page Detail` at index 1 (kept, unchanged in purpose). Added a friendly `PermissionError` message telling the user to close Excel if the file is open at save time.
3. **Section 7 (was "NAMING", now "PROPOSED NAME")** — replaced `apply_naming` (which did `shutil.copy2` to copy/rename a PDF) with **`assign_proposed_name`**, which only computes the name and stores it as **text** (`summary["proposed_name"]`): single vendor → `Vendor.pdf` (deduped `_01`, `_02`); mixed → `(mixed vendors)`; none → `(no vendor detected)`. **No files are copied or written to disk.** Kept `_vendor_counts` / `reset_vendor_counts` / `_dedup_name`.
4. **`main()`** — calls `assign_proposed_name(summary)` instead of `apply_naming(...)`.
5. **`score_reviewed_report` (`--score`)** — updated column indices for the new layout: verdict = `row[6]` (col G), predicted = `row[3]` (col D), correction = `row[7]` (col H). Reads the `Summary` sheet (sheet name unchanged).
6. **Self-test `_check_score_skips_unreviewed_rows`** — updated its mock sheet to the new 8-column layout.
7. Removed the now-unused `import shutil`.

**Verification:** `--selftest` → **15/15 pass**. A separate read-only check ran `build_excel_report` against a **copy** of the real `predictions.xlsx` (never the real file) and confirmed all 16 checks: Summary written in the 8-col format, dropdown on col G, proposed name as text (single + `(mixed vendors)`), original filename untouched in col A, the "Proposed Summary Sheet" template tab preserved header-only, and Page Detail present. Sheet order after a run: `[Summary, Page Detail, Proposed Summary Sheet]`.

### User runs the real pipeline manually
When offered a full real run (~6.5 min OCR), the user chose to run it themselves. Saved this as a memory (see below). **Important consequence:** the real `predictions.xlsx` has NOT been regenerated this session — its `Summary`/`Page Detail` tabs still hold the **old** Session-3 data/format. The new 8-column `Summary` only appears after the user runs `python invoice_boundary_detector.py`.

### Started debugging vendor detection (root cause NOT yet confirmed — awaiting evidence)
User reported vendor detection frequently fails to get the vendor name, guessing the logo is a scanned image the script can't read. Phase-1 investigation was done by **reading the code** (following the systematic-debugging skill — no fixes yet). Findings:
- **The reader OCRs a rasterized 300-dpi *image* of every page and never uses the PDF's embedded digital text** (`read_pdf_pages` uses `get_pixmap` → `pytesseract`, not `page.get_text()`). So even on a clean digital PDF, OCR misreads (common on stylized headers) can corrupt the vendor name.
- **`known_vendors` is empty**, so `detect_vendor` layer 1 (highest confidence) never fires.
- Layers 2–4 are pattern-restrictive: layer 2 needs a company **suffix** (LLC/Inc/Co/Supply/Services/Plumbing/Electric…) in the first 8 lines; layer 3 needs an **email domain**; layer 4 needs a **From/Vendor/Remit-to label**. A vendor shown as a plain header/logo with none of these → vendor = None.
- The user's logo hunch is partly right: a logo is a raster image; the current renderer *does* feed it to OCR, but Tesseract is unreliable on stylized logo fonts.

A **read-only diagnostic** was written to gather evidence (see file table). The user is running it (Option B) and will paste the output. **Do not propose the vendor fix until that output is seen.** The leading hypothesis to confirm: read the PDF's real digital text when present and fall back to OCR only for truly scanned pages, plus tighten vendor patterns / populate `known_vendors`.

---

## 2. Current state of files

| File | Status |
|---|---|
| `invoice_boundary_detector.py` | **UPDATED** this session (7 edits above). 15/15 self-tests pass. Report-writing verified against a copy of the real file. |
| `config.json` | Unchanged — `known_vendors` still **empty** (relevant to the vendor bug). `output_renamed` path is now unused (kept, harmless). |
| `output/reports/predictions.xlsx` | Unchanged this session. Holds 3 tabs: `Summary` + `Page Detail` (still **old** Session-3 format/data) and `Proposed Summary Sheet` (user's manual template, header-only). Will get the new 8-col `Summary` only after the next real run. |
| `output/renamed/` | Emptied — **user deleted** the renamed PDFs. The script no longer creates this folder at all (renaming removed). |
| `README.md` | Unchanged — now **slightly stale**: still describes the old renamed-PDF behavior and 7-col Summary. Update when convenient (not done to keep scope tight). |
| `requirements.txt` | Unchanged (PyMuPDF, pytesseract, Pillow, openpyxl, tqdm). |
| `input/` | Unchanged — 30 sample PDFs. |
| `docs/superpowers/specs/2026-07-24-invoice-boundary-detection-design.md`, `docs/superpowers/plans/2026-07-24-invoice-boundary-detection.md` | Unchanged. |
| `MEMORY.md` + `memory/user-runs-real-pipeline-manually.md` | **CREATED** in the user's memory dir (`C:\Users\Dhruv Champaneria\.claude\projects\c--Users-Dhruv-Champaneria-Desktop-Res1\memory\`). |
| Scratchpad: `diagnose_vendor.py` | **CREATED** (read-only vendor diagnostic — the file the user is about to run). Located at `C:\Users\DHRUVC~1\AppData\Local\Temp\claude\c--Users-Dhruv-Champaneria-Desktop-Res1\5e64d54d-aa30-4aca-aaed-dae5ee8c1dd6\scratchpad\`. NOTE: scratchpad is session-specific and may not survive into a new session — if gone, recreate it (it prints, per PDF page 1: digital `get_text` vs OCR text, plus `detect_vendor()` on each). |
| Scratchpad: `read_sheet.py`, `verify_report.py`, `verify_copy.xlsx` | Temp only — used to read the sheet and verify report-writing on a copy. Not needed going forward. |
| `2026-07-23_session-1/2-handoff.md`, `2026-07-24_session-3-handoff.md` | Unchanged — prior records. |
| `Tesseract_Testing/` | Unchanged — reference only; still stale (dead poppler-windows, old README). |

---

## 3. What still needs to happen

### Must do (in order)
1. **Get the diagnostic output.** User runs `diagnose_vendor.py` (Option B) and pastes the result. Command:
   `python "C:\Users\DHRUVC~1\AppData\Local\Temp\claude\c--Users-Dhruv-Champaneria-Desktop-Res1\5e64d54d-aa30-4aca-aaed-dae5ee8c1dd6\scratchpad\diagnose_vendor.py" 5`
2. **From that evidence, confirm the vendor root cause and propose a targeted fix** (likely: use embedded `page.get_text()` when the page has real text, OCR only scanned pages; and/or tighten `detect_vendor` + seed `known_vendors`). Validate the plan with the user before editing (they want to approve script changes).
3. **User runs the real pipeline manually** (`python invoice_boundary_detector.py`, ~6.5 min, Excel closed) to regenerate `Summary` in the new format.
4. **Review the Summary tab**, fill the "Reviewer verdict" dropdowns, then run `python invoice_boundary_detector.py --score`.
5. **Add real vendor names to `config.json` → `known_vendors`** as they're identified (biggest lever for vendor accuracy).

### Nice to have
- Update `README.md` for the new 8-col Summary + no-renaming behavior.
- Clean up `Tesseract_Testing/poppler-windows/` and its stale README (needs explicit approval).
- Empty `ocr_debug/` folder — safe to delete.

### Deferred (future, separate project)
- Actual PDF splitting (only after `--score` shows high accuracy). OneDrive integration for `input/`.

---

## 4. Important rules

- **NO git actions** anywhere — local-only project (CLAUDE.md hard rule #4).
- **NO PDF splitting, ever, in this version.** And **no renamed PDF copies** now either — column B "Proposed PDF Name" is **text only**; nothing is written to `output/renamed/`.
- **Never modify original PDFs** in `input/`.
- **Ask before Terminal/PowerShell use, per specific task** (CLAUDE.md rule #2). The user is protective here and **prefers to run the real/long pipeline and `--score` themselves** — hand them the command, don't execute it. Quick `--selftest` runs and read-only diagnostics/verifications (esp. against copies) are fine to run *with their OK*. See `memory/user-runs-real-pipeline-manually.md`.
- **`build_excel_report` must OPEN the existing `predictions.xlsx`, not overwrite the whole file** — this preserves the user's `Proposed Summary Sheet` tab. Only `Summary` and `Page Detail` are regenerated.
- **The `Summary` tab uses the reviewer's 8-column format**; the verdict dropdown lives in **column G**; `--score` reads columns D (predicted) / G (verdict) / H (correction).
- **Never read/edit secrets** without asking (`tesseract_cmd` in config is a local path, not a secret).
- **Debug with the systematic-debugging skill** — no vendor fixes until the diagnostic evidence is reviewed.
- **Plain English first, code second.** Team D (Puneet, Dhruv, Manish, Vijayesh) are **non-engineers**.
- **One `config.json` + one script.** No new files split off.
