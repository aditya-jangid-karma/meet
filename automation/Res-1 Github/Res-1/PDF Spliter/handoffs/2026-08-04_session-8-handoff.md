# Handoff — Windows PC connected to the shared drive (Part C mapping done); code still pending

**Date:** 2026-08-04 (Session 8)
**Session focus:** Begin the Windows-side setup from Deliverable A's guide. Outcome: the Windows PC now successfully connects to the shared folder (drive mapping / Part C done). No code was written; Part C (Excel format) and Deliverable B are still pending.

> **Privacy note:** By the user's explicit instruction, this handoff deliberately records **no** details about the separate AI/file-host machine (its address, account names, credentials, or its setup steps). That machine's setup is complete and verified — treat it as a done, external prerequisite. Do **not** reconstruct or write those details here or in memory.

---

## 1. What happened this session

### Server side confirmed complete (details intentionally omitted)
At the start of the session we confirmed the AI + file-hosting side is fully set up and verified — it (1) shares its folder over the office network and (2) serves the local Qwen model to other PCs. Per the user's instruction, no specifics about that machine are recorded. For the next session's purposes: **the shared folder and the Qwen endpoint are live and reachable; nothing is left to do there.**

### Started the Windows PC setup — mapped the shared drive (guide Part C)
Began following the Windows section of `notes/2026-07-30_mac-windows-server-setup.html` on the first Windows PC. The goal of Part C is to map the network shared folder as drive `Z:`.

### Fixed a network-credentials snag
Windows threw **"The username or password is incorrect"** at the *Enter network credentials* prompt. Two things were needed to get past it:
- **Username format:** typing just the account name made Windows try to log in against the *local Windows PC's* own name (shown as `Domain: KARMACPA`) instead of the server. Fixed by entering the username in **`<server-address>\<account>`** form so Windows authenticates against the server, not the local PC.
- **Credential refresh:** the account's password had recently been changed, so the saved/sharing password was stale. After refreshing it and re-entering, and clearing any cached Windows login for that server (`net use * /delete /y` from Command Prompt, and removing the entry in **Credential Manager → Windows Credentials** if present), the connection succeeded.

The user confirmed **"Completed"** — the Windows PC can now reach the shared folder. **Part C is done.**

---

## 2. Current state of files

| File | Status |
|---|---|
| `notes/2026-07-30_mac-windows-server-setup.html` | Unchanged. Deliverable A (setup guide), complete and verified in-browser last session. User is actively following its Windows section. |
| `invoice_boundary_detector.py` | **Unchanged.** Still the Session-4 version, 736 lines, 15 self-tests. No Qwen code, no page router, no archiving yet — Deliverable B not started. |
| `config.json` | **Unchanged.** Still Windows Tesseract path, empty `known_vendors`, **no `llm` block yet.** Part E of the guide will add the `llm` block + `Z:\` paths. |
| `handoffs/2026-08-04_session-7-handoff.md` | Unchanged — prior record. |
| `handoffs/2026-08-04_session-8-handoff.md` | **CREATED** this session (this file). |
| `2026-07-27_vendors-from-pdfs.md` | Unchanged. The 30/30 answer key new code must be verified against. |
| `output/reports/predictions.xlsx` | Unchanged — old Session-3 data/format. Real pipeline not run this session. |
| `input/` | Unchanged — 30 PDFs, still 10 duplicate pairs + Staples invoice 4×. Not de-duplicated. |
| `README.md` | Unchanged — still stale. |
| `requirements.txt` | Unchanged (PyMuPDF, pytesseract, Pillow, openpyxl, tqdm). Plan adds no new dependency (stdlib `urllib.request` for Qwen). |
| `C:\Users\Dhruv Champaneria\.claude\plans\just-like-windows-can-lucky-flame.md` | Unchanged — source-of-truth plan, still lives outside the project folder. |

---

## 3. What still needs to happen

### Must do
1. **Finish the Windows PC setup — guide Parts D–F:**
   - **Part D:** install Python 3, `pip install -r requirements.txt`, install Windows Tesseract.
   - **Part E:** edit `config.json` — set the `Z:\` input/output/processed paths, the Windows `tesseract_cmd`, add the `llm` block (`enabled: true`, `host` = the server's Qwen endpoint, `text_model`/`vision_model` = `qwen2.5vl:7b`).
   - **Part F:** first test run, including the reachability check that the PC can actually reach the Qwen endpoint.
2. **Claude: present Part C — the Excel-format proposal** (the B6 checkpoint). Must cover the batch/date column, how appended batches are visually separated, locked vs. editable columns, placement of the new "vendor source" (text/vision/rules) and "page type" (digital/scanned) columns, and how `--score` (reads columns **D**, **G**, **H**) keeps working across batches. Preserve the `Proposed Summary Sheet` tab and the verdict dropdown on column **G**. **Hard checkpoint — get explicit approval before coding.**
3. **Claude: build Deliverable B** (only after Part C approval): page router with escalation (B1), `config.json` `llm` block (B2), `extract_structural_text()` / `classify_page()` / `ask_qwen_vendor()` (B3), wiring into `read_pdf_pages()`/`build_pages()` (B4), `archive_processed()` + `--no-archive` (B5), Excel append per the approved format (B6), extended self-tests (B7).
4. **Verify against the answer key** — target 30/30 vs. `2026-07-27_vendors-from-pdfs.md`.

### Nice to have
- Repeat Parts C–F for the 2nd/3rd Windows PC when ready (guide's "Adding another PC" checklist).
- Back up `input/` before the first archiving run.
- De-duplicate `input/` (10 duplicate pairs + Staples 4× — double-payment risk). Ask before deleting.
- Update the stale `README.md`.
- Copy the plan file into the project; move older stray handoff into `handoffs/` if any remain.

---

## 4. Important rules

- **Do NOT record details about the AI/file-host machine** (its address, account, credentials, or setup) in handoffs, notes, or memory — user's explicit instruction this session. That side is a completed, external prerequisite.
- **NO git actions** anywhere — local-only project (CLAUDE.md hard rule #4).
- **Ask before Terminal/PowerShell**, per task. **The user runs the real/long pipeline and `--score` themselves** — hand them commands, don't execute. See `memory/user-runs-real-pipeline-manually.md`.
- **Script runs ON WINDOWS** (revised design); the host machine only serves the shared folder + Qwen. Windows PCs install Python + Tesseract + the script.
- **Model is `qwen2.5vl:7b`** (exact tag), serves both text and vision routes.
- **Config must default `host` to `http://localhost:11434` if absent**, and `detect_vendor()` must stay unchanged and offline-testable — with Qwen off/unreachable the script behaves exactly as today, and self-tests pass with no network.
- **Ollama/Qwen never receives a PDF** — only extracted text or a base64 page image.
- **The vendor bug is a detection-LOGIC gap, NOT OCR.** Do not chase OCR quality to fix vendors.
- **Privacy: client financial data — local AI only.** Flag loudly if any design would send invoices to a cloud service.
- **Never modify original PDFs. No PDF splitting, ever. No renamed PDF copies.** Archiving *relocates* files only (via `shutil.move`), never renames/edits/overwrites.
- **`build_excel_report` must OPEN the existing `predictions.xlsx`**, preserving the `Proposed Summary Sheet` tab. Verdict dropdown on column **G**; `--score` reads cols **D** / **G** / **H**.
- **Never read/edit secrets** without asking. **Plain English first, code second** — Team D are non-engineers.
- **One `config.json` + one script.** No new code files; documentation deliverables are fine.
