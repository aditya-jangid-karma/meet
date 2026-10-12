# Handoff — Plan approved, Deliverable A (Mac/Windows setup guide) built and verified; Deliverable B presented, Part C (Excel checkpoint) not yet reached

**Date:** 2026-08-04 (Session 7)
**Session focus:** Resume from Session 6, get the Qwen/Mac-Windows plan approved, and start executing it. Outcome: plan is approved (via the user's go-ahead), **Deliverable A is built and verified**, **Deliverable B was presented in chat but no code was written**, and the session paused before Part C (the Excel format checkpoint) could be presented.

---

## 1. What happened this session

### Resumed and re-presented the Session 6 plan
Ran `/resume`: read CLAUDE.md, memory (`user-runs-real-pipeline-manually.md`), and the Session 6 handoff. Session 6 had left off with a full two-deliverable plan written but not approved, at `C:\Users\Dhruv Champaneria\.claude\plans\just-like-windows-can-lucky-flame.md` (outside the project folder). Read that plan file in full and presented it back to the user in plain English (server setup guide = Deliverable A, code changes = Deliverable B, with the Excel format as an explicit checkpoint inside B6).

### Plan approved implicitly
The user responded "start on Part A, then present Part B and then C" — treated as approval to proceed. Note: the user's phrasing splits the work into **three** pieces (A, B, C) where the original plan only names two deliverables (A, B) with the Excel format as a checkpoint *inside* B6. This session treated "C" as **that same Excel-format checkpoint**, now called out as its own numbered step for clarity. Carry this A/B/C framing forward — it's now the working vocabulary for this project, not just A/B.

### Built and verified Deliverable A — the Mac/Windows server setup guide
Created **`notes/2026-07-30_mac-windows-server-setup.html`** (note: filename kept the 2026-07-30 date from the plan spec, even though it was authored 2026-08-04 — matches the plan's exact required filename). Self-contained HTML, inline CSS, no external links, modeled on the style of `2026-07-27_n8n-workflow-setup.html`. Contains all 11 sections the plan required: one-picture overview, ~10-term glossary, Part 1 (create `input/`, `input/_processed/`, `output/reports/` on the Mac), Part 2 (turn on File Sharing/SMB, find Mac name + IP, why a fixed/reserved IP matters), Part 3 (map `Z:` from Windows, test), Part 4 (Python 3, `pip3 install -r requirements.txt`, Homebrew, `brew install tesseract`), Part 5 (`ollama list`, `curl http://localhost:11434/api/tags` proof-of-life), Part 6 (before/after `config.json` — Mac `tesseract_cmd` path, `processed_folder`), Part 7 (`--selftest` then a real small run), a troubleshooting FAQ (6 items per the plan spec), and a copy-pasteable "context for Claude on the Mac" block.

**Verified, not just written:** opened the file in the Browser pane. Caught and fixed a real bug — the `.step-num` CSS class (the little blue circled step numbers) was referenced in the HTML but its style rule got dropped when adapting the n8n template, so the numbers would have rendered as plain unstyled text. Added the missing CSS rule and re-checked via screenshot; the numbered badges render correctly now (confirmed in Part 1's "Create the project folder" / "Create the three subfolders" steps).

### Presented Deliverable B in chat — no code written
Walked through B1–B7 from the plan in plain English (page router with escalation, `config.json`'s new `llm` block, the three new functions, wiring into `read_pdf_pages()`/`build_pages()`, archiving, the Excel append checkpoint, extended self-tests). **This was a chat presentation only — `invoice_boundary_detector.py` and `config.json` were NOT touched this session.**

### Session paused before Part C
The user said "Pause here for now, will be back" immediately after the Deliverable B presentation, before the Excel-format proposal (Part C / B6 checkpoint) could be shown. **Part C has not been presented yet** — this is the very next thing to do next session.

---

## 2. Current state of files

| File | Status |
|---|---|
| `notes/2026-07-30_mac-windows-server-setup.html` | **CREATED** this session. Deliverable A, complete per plan spec, verified rendering in-browser (including the step-badge CSS fix). Ready for the user to follow on the Mac. |
| `invoice_boundary_detector.py` | **Unchanged.** Still the Session-4 version, 736 lines, 15 self-tests. No Qwen code, no router, no archiving — Deliverable B is design-only so far. |
| `config.json` | **Unchanged.** `known_vendors` still empty; `tesseract_cmd` still the Windows path. No `llm` block yet. |
| `C:\Users\Dhruv Champaneria\.claude\plans\just-like-windows-can-lucky-flame.md` | Unchanged, still lives **outside** the project folder. This is the source-of-truth plan; not yet copied into the project (still a nice-to-have from Session 6). |
| `2026-07-27_vendors-from-pdfs.md` | Unchanged. Still the 30/30 answer key that new code must be verified against. |
| `2026-07-27_n8n-workflow-setup.html` | Unchanged. Used as the CSS/style template for this session's new guide. |
| `output/reports/predictions.xlsx` | Unchanged — still old Session-3 data/format. Real pipeline not run this session. |
| `input/` | Unchanged — 30 PDFs, still containing 10 duplicate pairs plus the same Staples invoice 4 times. Not de-duplicated. |
| `Terminal output.md` | Unchanged. Session-4 diagnostic evidence, can be deleted once no longer needed. |
| `README.md` | Unchanged — still stale (old renamed-PDF behavior, 7-col Summary). Will also need Mac/Windows setup notes eventually. |
| `requirements.txt` | Unchanged (PyMuPDF, pytesseract, Pillow, openpyxl, tqdm). Plan deliberately adds no new dependency for Qwen (stdlib `urllib.request`). |
| `handoffs/2026-07-23_session-1/2-handoff.md`, `2026-07-24_session-3/4-handoff.md`, `2026-07-30_session-6-handoff.md` | Unchanged — prior records. |
| `2026-07-27_session-5-handoff.md` | Unchanged, still sits in project root instead of `handoffs/` — still a pending tidy-up (ask first). |
| `Invoice_Boundary_Detection_Project_Summary.md`, `docs/superpowers/specs/...`, `docs/superpowers/plans/...` | Unchanged. |
| `Tesseract_Testing/` | Unchanged — reference only, still stale. |
| `MEMORY.md` + `memory/user-runs-real-pipeline-manually.md` | Unchanged. |

---

## 3. What still needs to happen

### Must do
1. **Present Part C — the Excel format proposal** (this is the very next step, was about to happen when the user paused). Must cover: the batch/date column, how appended batches are visually separated, which columns are locked vs. editable, where the new "vendor source" (text/vision/rules) and "page type" (digital/scanned) columns sit, and how `--score` (reads columns **D**, **G**, **H**) keeps working across batches. Get explicit approval — this is a hard checkpoint, not a formality.
2. **User builds the server on the Mac** using `notes/2026-07-30_mac-windows-server-setup.html`. Not started yet.
3. **Build Deliverable B — the code changes**, only after Part C is approved: page router with escalation (B1), `config.json`'s `llm` block (B2), `extract_structural_text()` / `classify_page()` / `ask_qwen_vendor()` (B3), wiring into `read_pdf_pages()`/`build_pages()` (B4), `archive_processed()` (B5), Excel append logic per the approved Part C format (B6), extended self-tests (B7).
4. **Verify against the answer key** — run the batch and compare the vendor column to `2026-07-27_vendors-from-pdfs.md`. Target 30/30.

### Nice to have
- Copy the plan file from `C:\Users\Dhruv Champaneria\.claude\plans\just-like-windows-can-lucky-flame.md` into the project (e.g. `docs/`) so it's not orphaned outside the repo.
- Back up `input/` before the first archiving run (archiving relocates originals).
- De-duplicate `input/` — 10 duplicate pairs + the 4-way Staples duplicate, real double-payment risk. Ask before deleting anything.
- Update the stale `README.md`.
- Move `2026-07-27_session-5-handoff.md` into `handoffs/`.

---

## 4. Important rules

### Decisions locked (from Session 6, unchanged)
- **Script runs ON THE MAC** (option A1). Windows machines install nothing.
- **Model is `qwen2.5vl`** (vision), serves both text and vision routes.
- **Bridge is a local SMB file share** hosted by the Mac, mapped as `Z:` on Windows. **OneDrive was explicitly rejected — do not re-propose it.**
- **Processed PDFs move to `input/_processed/`** after a successful Excel write — deliberate, narrow exception to "never touch originals."
- **One master Excel file with appending** — format must be shown and approved (Part C) before it's coded.
- **Manual trigger** for now; n8n/watchers deferred.

### New this session
- **The A/B/C framing is now this project's working vocabulary.** A = server setup guide (done). B = the code changes generally. C = the Excel-format checkpoint specifically, called out as its own step rather than buried inside B6. Use these labels consistently going forward.
- **Deliverable A's exact filename is `notes/2026-07-30_mac-windows-server-setup.html`** — the date in the filename is intentionally the plan's date, not the authoring date; don't "fix" it to today's date.
- Always **open and screenshot-verify** self-contained HTML deliverables in the Browser pane before calling them done — this session caught a real missing-CSS bug (`.step-num`) that would otherwise have shipped silently.

### Carried forward from earlier sessions
- **NO git actions** anywhere — local-only project (CLAUDE.md hard rule #4).
- **Ask before Terminal/PowerShell**, per task. **The user runs the real/long pipeline and `--score` themselves** — hand them the command, don't execute. See `memory/user-runs-real-pipeline-manually.md`.
- **The vendor bug is a detection-LOGIC gap, NOT OCR.** Proven in Session 5. Do not chase OCR quality to fix vendors.
- **Privacy: client financial data.** Local AI only (Ollama). Flag loudly if any design would send invoices to a cloud service.
- **Never modify original PDFs. No PDF splitting, ever. No renamed PDF copies** — column B "Proposed PDF Name" is text only. Archiving *relocates* files; must never rename, split, edit or overwrite them.
- **`build_excel_report` must OPEN the existing `predictions.xlsx`**, preserving the user's `Proposed Summary Sheet` tab. Verdict dropdown on column G; `--score` reads cols D / G / H.
- **`detect_vendor()` must stay unchanged and offline-testable** — self-tests must pass with no network. With Ollama off, the script must behave exactly as it does today.
- **Ollama never receives a PDF.** Only text or a base64 image — any design that says otherwise is wrong.
- **Never read/edit secrets** without asking (`tesseract_cmd` is a local path, not a secret).
- **Plain English first, code second.** Team D (Puneet, Dhruv, Manish, Vijayesh) are non-engineers.
- **One `config.json` + one script.** No new code files — documentation deliverables are fine.
