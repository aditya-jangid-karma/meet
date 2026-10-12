# Handoff — Proved the vendor bug is a LOGIC gap (not OCR); built an LLM vendor list + an n8n setup guide

**Date:** 2026-07-27 (Session 5)
**Session focus:** Investigate the vendor-detection failure with real evidence and explore an n8n/local-AI direction. Outcome: confirmed the bug is a detection-*logic* gap (not OCR), proved an LLM extracts all vendors correctly (30/30), and produced two deliverables — a vendor list and a two-path n8n setup guide. **No code was changed yet** — the actual fix is still a pending decision.

---

## 1. What happened this session

### Resumed and caught up
Ran `/resume`: read CLAUDE.md, memory (`user-runs-real-pipeline-manually.md`), and the Session 4 handoff. Session 4 had left off mid-investigation on vendor detection, awaiting the output of a read-only diagnostic.

### Read the diagnostic output — it OVERTURNED last session's theory (key finding)
The user pasted the diagnostic into **`Terminal output.md`** (project root) and I read it. It ran on 5 of 30 PDFs, page 1, comparing the PDF's embedded digital text vs. OCR text and running `detect_vendor` on each. Findings:
- **These are digital PDFs with clean embedded text** (`digital-text chars=1000+`), not scanned images. Session 4's "maybe the vendor is a scanned logo the script can't read" hunch is **false** for these files.
- **OCR text is messier** (scrambled line order, merged columns, "Bn Staples" garbage) **but detection still worked**: `detect_vendor` returned the *same correct vendor* on **both** digital and OCR text (Staples, Cockey's), every time via the **email-domain** layer.
- **Conclusion — the vendor bug is NOT an OCR/text-quality problem.** The 5 sampled all *passed*; the failures are elsewhere. The invoices that fail (later confirmed: Happy Summers, Quill, Chadwell, Summit Fire) show the vendor only as a **name/logo at the top of the page** with no email domain, no "Inc/LLC" suffix in the first lines, and no From/Remit-to label — and the script **has no rule that trusts the top-of-page name.** Even flawless OCR of "Happy Summers" still gets skipped.
- **Therefore: trying a "better OCR" will NOT fix the vendor-skip.** It's a logic gap, not a text gap. The lever that works is *understanding* the page (an LLM, or at minimum a new "trust the top-of-page company name" fallback rule).

### Discussed n8n + local-vs-cloud AI (advisory, no build)
Walked through, in plain English: n8n is an *orchestrator* (great for auto-triggering + glue), not the place for the hard PDF logic. Cloud document-AI (Azure/Textract) is very accurate but **sends client financial data off the machine** — a privacy issue for a CPA firm. The user asked about **locally-hosted AI** to avoid that; confirmed **Ollama** (local models) is the privacy-safe path and n8n has native support. Emphasized: "use a local LLM for vendor detection" and "adopt n8n as a wrapper" are **two separate decisions**.

### Sonnet agent #1 — extracted vendors from all 30 PDFs (proof of concept)
Launched a background Sonnet agent, scoped strictly to `input/` (read-only, no other files, no commands). It read all 30 PDFs and wrote **`2026-07-27_vendors-from-pdfs.md`**. Results (verified by reading the file):
- **30/30 vendors identified with high confidence**, 0 failures, all digitally readable.
- **12 unique vendors:** Staples, Quill, Chadwell Supply, Ferguson Enterprises LLC #1300, Ferguson Facilities Supply, Cockey's Enterprises, Summit Fire & Security, Happy Summers, L&C Pest Management, Constellation NewEnergy, Sharp Business Systems, RMS Contractors.
- **This PROVES the fix direction:** many were identified from the top-of-page name/logo alone — exactly the invoices the pattern-rule script skips. An LLM (cloud *or* local) solves this by *understanding*, not by better text.
- **Two accounting catches:** (1) **Heavy duplication** — 10 invoices saved twice (`X.pdf` + `X - Copy.pdf`), and the Staples/Residential-ONC invoice exists as **4 identical files** (`7fcd56cc...` and `7fcd56cc... (1)`, each with a Copy). Real double-payment risk. (2) **Ferguson = two legal entities** ("Ferguson Enterprises LLC #1300" vs. "Ferguson Facilities Supply"), both billing Victory Court Inc — kept as separate rows.

### Sonnet agent #2 — built the n8n setup guide
Per the user's choice (a two-path guide), launched a second background Sonnet agent that wrote **`2026-07-27_n8n-workflow-setup.html`** — a single self-contained HTML file (inline CSS, no external links; opens by double-click, offline). Verified: valid HTML, 0 external resource links (grep), all sections present. Contents: prerequisites checklist (self-hosted n8n via Docker or `npx n8n`, Ollama + model pulls), a 12-term glossary, a Path A vs. Path B comparison table, node-by-node walkthroughs of both paths, a recommendation, testing tips, and a troubleshooting FAQ. Uses the real vendor names as examples. Each LLM step flags the local-vs-cloud privacy trade-off.
- **Path A — OCR/text → LLM:** read embedded text (OCR fallback for scans) → local Ollama model returns structured JSON (vendor, new-invoice-start, amount) → validate → write to Excel/Sheets → notify. *Recommended primary* — light, private, fits their mostly-digital PDFs.
- **Path B — straight to a vision LLM:** page→image → vision model (llama3.2-vision / qwen2-vl / minicpm-v locally, or cloud) reads + interprets in one step → JSON → output → notify. Held in reserve for scanned invoices or a one-step design.

---

## 2. Current state of files

| File | Status |
|---|---|
| `2026-07-27_vendors-from-pdfs.md` | **CREATED** this session. LLM-extracted vendor list for all 30 PDFs (table + 12 unique vendors + duplicate/Ferguson notes). Verified. |
| `2026-07-27_n8n-workflow-setup.html` | **CREATED** this session. Self-contained two-path n8n setup guide. Verified self-contained + complete. |
| `Terminal output.md` | Present (user pasted the Session-4 diagnostic output here). Source of this session's key finding. Can keep as evidence or delete later. |
| `invoice_boundary_detector.py` | **Unchanged this session.** Still the Session-4 version (15/15 self-tests, 8-col Summary output). **The vendor fix has NOT been applied** — awaiting a decision on approach. |
| `config.json` | Unchanged — `known_vendors` still **empty**. |
| `output/reports/predictions.xlsx` | Unchanged — still holds **old Session-3** data/format. The real pipeline was **not** run this session; the new 8-col Summary only appears after the user runs it. |
| `input/` | Unchanged — 30 PDFs, but confirmed to contain **duplicates** (10 `- Copy` pairs + a 4-way Staples dup). Candidate for de-duplication. |
| `README.md` | Unchanged — still **stale** (describes old renamed-PDF behavior + 7-col Summary). |
| `requirements.txt` | Unchanged (PyMuPDF, pytesseract, Pillow, openpyxl, tqdm). |
| `docs/superpowers/specs/...`, `docs/superpowers/plans/...` | Unchanged. |
| `MEMORY.md` + `memory/user-runs-real-pipeline-manually.md` | Unchanged (user runs the real/long pipeline + `--score` themselves). |
| `2026-07-23_session-1/2-handoff.md`, `2026-07-24_session-3/4-handoff.md` | Unchanged — prior records. |
| `Tesseract_Testing/` | Unchanged — reference only, still stale. |
| Scratchpad `diagnose_vendor.py` (prior session) | The user successfully ran it this session (produced `Terminal output.md`). Session-specific; may not persist. |

---

## 3. What still needs to happen

### Must do
- **DECIDE the vendor-fix approach** (this is the main open decision). Options discussed:
  1. **Local-LLM vendor step inside the existing Python script** — smallest change, keeps the one-script design, private (Ollama). Likely the best next step.
  2. **The n8n route** — guide is ready (`2026-07-27_n8n-workflow-setup.html`), Path A recommended. Bigger lift (host n8n + Ollama).
  3. **At minimum, a code-only fix:** add a "trust the top-of-page company name" fallback rule to `detect_vendor` (and optionally seed `known_vendors`). Note: hardcoding vendor names alone was rejected by the user as not a real solution.
- **Spot-check the LLM vendor list** (`2026-07-27_vendors-from-pdfs.md`) against a few actual PDFs for CPA validation — especially the **Ferguson pair** and **Sharp** — before relying on it.
- **De-duplicate `input/`** — 10 duplicate pairs + the 4-way Staples dup are a double-payment risk. (Ask before deleting anything.)

### Nice to have / still outstanding from Session 4
- User runs the real pipeline manually to regenerate `predictions.xlsx` in the 8-col format; then fill verdict dropdowns (col G) + run `--score`. (May be reprioritized depending on the direction chosen above.)
- Walk the team through the n8n HTML guide; if going that route, stand up n8n + Ollama.
- Update `README.md` (stale). Clean up `Tesseract_Testing/` + `ocr_debug/` (needs approval).

---

## 4. Important rules

- **NO git actions** anywhere — local-only project (CLAUDE.md hard rule #4).
- **Ask before Terminal/PowerShell**, per task. The user **runs the real/long pipeline and `--score` themselves** — hand them the command, don't execute. Quick read-only diagnostics/verifications (esp. against copies) are fine *with their OK*. See `memory/user-runs-real-pipeline-manually.md`.
- **NEW this session — the vendor bug is a detection-LOGIC gap, NOT OCR.** Evidence: detection works equally on clean digital text and messy OCR text. **Do not chase OCR quality to fix vendors.** The fix is *understanding* (LLM) or a top-of-page-name rule.
- **Privacy: this is client financial data.** Prefer **local AI (Ollama)**; explicitly flag whenever a design would send invoices to a cloud service (Azure/Textract/cloud LLMs).
- **Never modify original PDFs** in `input/`. **No PDF splitting, ever.** **No renamed PDF copies** — column B "Proposed PDF Name" is text only.
- **`build_excel_report` must OPEN the existing `predictions.xlsx`** (preserve the user's `Proposed Summary Sheet` tab); only `Summary` + `Page Detail` are regenerated. **8-column Summary**, verdict dropdown on **col G**, `--score` reads cols **D** (predicted) / **G** (verdict) / **H** (correction).
- **Never read/edit secrets** without asking (`tesseract_cmd` in config is a local path, not a secret).
- **Debug with the systematic-debugging skill** — evidence before fixes (this session's finding came from reading the diagnostic, not guessing).
- **Plain English first, code second.** Team D (Puneet, Dhruv, Manish, Vijayesh) are **non-engineers**.
- **One `config.json` + one script.** No new files split off (documentation/deliverables like the vendor list and n8n guide are fine).
