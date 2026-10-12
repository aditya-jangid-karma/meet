# Handoff — Locked the Excel/naming design + chose build approach (still in brainstorming)

**Date:** 2026-07-23 (Session 2)
**Session focus:** Continue Superpowers brainstorming for the Invoice Boundary Detection engine. Finished the clarifying-questions phase, nailed down the Excel report + file-naming behavior, and chose the build approach. Still NO code — next step is presenting the formal design. Session ended by user request.

---

## 1. What happened this session

### Resumed and reconnected context
Ran `/resume` (memory is still empty; read CLAUDE.md + the Session 1 handoff). Picked up exactly at the open question Q4.

### Q4 evolved into the real Excel design (big update — supersedes Session 1's per-page grid idea)
The reviewer-facing Excel is now a **report**, not a raw per-page grid:
- **Main sheet = per-PDF summary.** One row per PDF: `PDF name | # pages | new-invoice-starts-at (predicted split pages) | # invoices found | Reviewer verdict (dropdown)`.
- **For MIXED-vendor PDFs, the split points show the vendor at each point**, e.g. `p1 – Vendor A, p5 – Vendor B, p9 – Vendor C`.
- **Reviewer verdict is an Excel data-validation DROPDOWN.** Agreed options: **✅ Correct / ⚠️ Partially correct / ❌ Incorrect / 🔍 Needs a closer look**.
- **Plus one adjacent cell "Correct split pages (if wrong)"** where the reviewer types the true pages (e.g. `1, 6, 9`) ONLY when marking Incorrect/Partially. This is what lets us still compute real Precision/Recall/F1 later, while keeping review fast (dropdown for the ones that are right).
- **Backing sheet = per-page detail:** one row per page with the per-page Break/Continue call, confidence, score, and **which rules fired** (satisfies the brief's "explain WHY every prediction" requirement). Reviewers only open it when they want the reasoning.
- **Styling:** "colorful yet professional" — clean header band, subtle row shading, color-coded verdict cells (green/amber/red). Not a rainbow. (openpyxl for styling + data-validation dropdowns.)

### File-naming / renaming rule (confirmed)
The script detects the vendor(s) in each PDF and auto-decides:
- **Single-vendor PDF** (all invoices inside are one vendor) → **rename** to the vendor name, with dedup suffixes when a vendor repeats across files: first = `Vendor Name`, second = `Vendor Name_01`, third = `Vendor Name_02`, …
- **Mixed-vendor PDF** (more than one vendor inside) → **do NOT rename;** keep the original filename and instead annotate the vendor at each split point in the Excel (as above).
- The script decides single-vs-mixed on its own by comparing detected vendors — no manual sorting.
- **SAFETY DEFAULT (per CLAUDE.md "don't modify originals"):** renaming happens on a **COPY** written into an `output/renamed/` folder. The original source PDFs in the OneDrive-synced folder are **left untouched**, so a misread vendor never damages a real file. (Can be flipped to in-place rename later via config, but safe-by-default for now.)

### Environment
- **Tesseract OCR is already installed** on the user's PC ✅ (biggest setup hurdle cleared).
- Still TBD at build time: confirm Python is installed; install Python libraries (pdfplumber/PyMuPDF, pytesseract, pdf2image, openpyxl, etc.); Poppler may be needed for PDF→image conversion for OCR.

### HARD GUARDRAIL re-confirmed by user (do not violate)
**This version must NOT split PDFs.** It only DETECTS proposed split points and writes them + reasoning to Excel for manual review — this is purely to validate detection accuracy first. Design decision: build the tool with **no PDF-writing capability at all**, so it physically cannot split even by accident. Actual splitting = a separate, later spec, only after accuracy is proven.

### Build approach CHOSEN
Presented 3 options; user chose **Approach A — "Walking skeleton, then add rules."** Build the thinnest end-to-end pipeline first (read a PDF → run 1–2 simple rules → produce the real formatted Excel + accuracy scorer), prove the whole chain, THEN add remaining rules/features one at a time. Rationale: no sample data yet, non-engineer maintainers, and the review workflow is what most needs early validation. (Approach B = full pipeline in one pass; Approach C = Jupyter notebook — rejected, fails maintainability.)

## 2. Current state of files

| File | Status |
|---|---|
| `Invoice_Boundary_Detection_Project_Summary.md` | Unchanged — original brief. Still the north star. |
| `CLAUDE.md` / `Claude.MD` | Unchanged — project rules. |
| `2026-07-23_session-1-handoff.md` | Unchanged — Session 1 record. |
| `2026-07-23_session-2-handoff.md` | **CREATED** — this file (latest; read this one first next time). |
| `docs/superpowers/specs/` | Still does NOT exist — the design doc goes here NEXT session once sections are approved. |
| (no code files) | Nothing built yet — correct for this stage. |

## 3. What still needs to happen

### Must do (resume here next session)
1. **Present the formal design in sections, getting approval after EACH** (this is the immediate next Superpowers step now that Approach A is chosen). Sections to cover:
   - **Folder/project structure** (input/, output/renamed/, output/reports/, config, src modules, tests, README per folder per CLAUDE.md).
   - **Modules & responsibilities** — e.g. `reader` (text-first + OCR fallback), `features` (extract Invoice #, Vendor, Date, PO, Total, etc.), `rules` (independent pluggable rules, each returns a score), `confidence` (combine scores vs thresholds → Break/Continue), `report` (build the styled Excel + dropdowns), `scorer` (read reviewed Excel back → Precision/Recall/F1).
   - **Data models** — page record, feature record, prediction record, per-PDF summary.
   - **Config file** — rule weights + thresholds (config-driven so they can be tuned when real PDFs arrive; brief's suggested weights: Invoice# changed +100, Vendor changed +40, Invoice header +30, Same vendor −20, Continuation pattern −40).
   - **Error handling** — brief's exception list: blank pages, OCR failures, rotated/landscape pages, separator sheets, credit notes, statements, packing slips, duplicates, missing pages, low OCR confidence, mixed formats.
   - **Testing** — hand-made test PDFs (no real samples yet); unit tests per rule.
2. **Write the design doc** to `docs/superpowers/specs/2026-07-23-invoice-boundary-detection-design.md` and commit.
   - NOTE: repo is NOT a git repo yet → will need `git init` first. **ASK before running any terminal command** (CLAUDE.md hard rule).
3. **Spec self-review** (placeholders/consistency/scope/ambiguity), then **user reviews the spec**.
4. **Invoke `writing-plans`** to turn the approved spec into an implementation plan. (From brainstorming, writing-plans is the ONLY next skill — do not invoke any other implementation skill.)

### Nice to have
- Draft 2 hand-made test PDFs (one single-vendor batch, one mixed-vendor batch) to exercise the pipeline once building starts.
- Decide default confidence thresholds for "auto-approve vs needs manual review" (deferred — propose config-driven defaults in the design).

## 4. Important rules

- **NO PDF SPLITTING in this version** — detection + Excel review only. Build with no PDF-writing capability. (User emphasized this twice.)
- **Never modify original files** — script renames COPIES into `output/renamed/`; originals in OneDrive stay untouched.
- **NEVER commit secrets** — API keys, passwords, tokens, `.env`, QBO/AppFolio/FCCB creds. Guide the user on push-vs-manual.
- **NEVER use Terminal/PowerShell without explicit permission** for that specific task — ask first (relevant: `git init`, pip installs).
- **NEVER read/edit secrets files** without asking.
- **Work one small step at a time; wait for confirmation.** One question at a time in brainstorming.
- **Plain English first, code second** — Team D are CPAs/bookkeepers, not engineers. Walk through non-trivial commands; use exact file paths.
- **Superpowers hard gate:** no code/implementation skill until design is presented → approved → written to spec → user-reviewed; then `writing-plans` only.
- **Every folder needs a README** (explanatory, covers libraries/technical aspects) so a CPA/CA can maintain it long-term.
- **Naming:** date-prefixed `YYYY-MM-DD_short-slug.md` (slug ≤ 4 words); never put PII in filenames.
