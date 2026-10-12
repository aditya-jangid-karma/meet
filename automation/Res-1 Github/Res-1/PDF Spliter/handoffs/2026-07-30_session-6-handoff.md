# Handoff — Designed the Qwen + Mac/Windows local-server architecture (plan written, NOT yet approved)

**Date:** 2026-07-30 (Session 6)
**Session focus:** Answer the user's setup questions about running Qwen locally and design how Windows PCs, a Mac running Qwen, and the existing Python script fit together. Outcome: every architectural decision is now made and a full plan is written — but **the plan was not approved and NO code was changed.** Next session starts by getting the plan approved, then building.

---

## 1. What happened this session

### Cleared up the central misconception about how Qwen receives a PDF
The user's opening question was "how will the script send the PDF to Qwen?" The answer, which reshaped the whole design: **Ollama cannot accept a PDF file — ever.** Its API accepts only two things:
- **text** (for a text model), or
- **a base64-encoded image** (for a vision model).

So the PDF is always opened and converted **on whichever machine runs the Python script**. Qwen only ever receives a few KB of text or one page image. This means "moving PDFs to the Mac" is a *file-sharing* problem, entirely separate from the AI, and the two should be designed separately.

### Explored the OneDrive route, then the user revoked it
Confirmed that OneDrive does sync on macOS and gives a real local path (`~/Library/CloudStorage/OneDrive-<Company>/...`), with the caveat that "Files On-Demand" leaves files as online-only placeholders until you set the folder to *Always Keep on This Device*. The user considered this and then **explicitly rejected the OneDrive approach**, preferring a **local server between the Mac and Windows**. OneDrive is off the table — do not re-propose it.

### Settled the architecture — the Mac does everything (option "A1")
Agreed design: the Mac is simultaneously the **file server**, the **AI server**, and **the machine that runs the Python script**. Windows machines install nothing at all.

```
Windows PC                      Mac (does all the work)
-----------                     -----------------------
Z:\input\  ──drop PDFs──►  /Users/<mac-user>/Res1/input/
                                        │
                           invoice_boundary_detector.py
                                        │
                           Qwen 2.5-VL @ localhost:11434
                                        │
Z:\output\reports\  ◄──────  output/reports/predictions.xlsx
Z:\input\_processed\ ◄─────  input/_processed/
```

The bridge is **macOS File Sharing (SMB)**, built into macOS, mapped on Windows as drive `Z:`. No transfer script is needed — Windows and macOS speak SMB natively. Because the script runs on the Mac, **Ollama stays on `localhost` and is never exposed to the network**, and page images never leave the machine.

### Confirmed the single code integration point
Read the script. `detect_vendor()` at **[invoice_boundary_detector.py:184](../invoice_boundary_detector.py#L184)** is a choke point called from exactly one place — `build_pages()` at **[line 317](../invoice_boundary_detector.py#L317)**. That is the only spot Qwen needs to plug into, which confirms the user's requirement that "the rest of the flow stays the same." Also noted: `read_pdf_pages()` at **[line 68](../invoice_boundary_detector.py#L68)** already renders a PNG per page at **[line 90](../invoice_boundary_detector.py#L90)** and throws it away after OCR — the vision path can reuse that for free.

### The user proposed a page router — accepted, with one correction
The user's idea: image → straight to Qwen vision; scanned PDF → straight to Qwen vision; digital/OCR-readable → extract text *structurally* and send the text. This was accepted as **better than the original plan**, for two reasons:
- PyMuPDF can pull structural text (position-sorted blocks, true reading order) in milliseconds, which is both faster **and cleaner** than the current 300-dpi OCR that Session 5 showed scrambles line order and merges columns.
- For the current 30 digital PDFs, Tesseract would barely run at all — **the ~6.5-minute OCR pass should collapse to seconds.**

**The correction (important — do not lose this):** a page can be fully digital, with 1000+ characters of line items and addresses, and *still have no vendor anywhere in its text*, because the vendor is a **logo image**. That is exactly the Happy Summers / Quill / Chadwell case this project exists to fix. Routing purely on "has text → text path" would send those pages down the path that cannot see the answer. So the router needs an **escalation step**: try the text path first, and if Qwen returns no vendor, retry that single page with vision.

### Found a data-loss risk in the Excel report
`build_excel_report()` at **[line 368](../invoice_boundary_detector.py#L368)** currently **regenerates** the Summary and Page Detail sheets on every run. That is harmless today, but once files are processed in batches it becomes destructive: if a reviewer fills verdict dropdowns in **column G** for batch 1 and someone then drops in batch 2 and re-runs, **those verdicts are wiped.** The user chose "one master file, completely formatted" and asked to **be shown a proposed format before it is built.** This is an open checkpoint.

### Wrote the plan (two deliverables) — rejected twice, not approved
`ExitPlanMode` was rejected twice. The first rejection asked for the page-router change and for the server setup to be split out; both were incorporated. The second rejection was simply "pause the session, write the handoff." **The plan itself has not been reviewed or approved.**

The plan now has **two independent deliverables**:
- **A — a standalone, non-technical Mac/Windows server setup guide**, to be written as a self-contained HTML file (same style as last session's n8n guide) so the user can follow it alone on the Mac, with Claude's help there. Includes a copy-pasteable "context for Claude on the Mac" section.
- **B — the code changes** (router, Qwen calls, archiving, Excel appending, self-tests).

**A must be done before B can be tested.**

---

## 2. Current state of files

| File | Status |
|---|---|
| `C:\Users\Dhruv Champaneria\.claude\plans\just-like-windows-can-lucky-flame.md` | **CREATED** this session (lives OUTSIDE the project folder — note the path). The full two-deliverable plan. **NOT APPROVED.** Consider copying it into the project next session. |
| `invoice_boundary_detector.py` | **Unchanged.** Still the Session-4 version, 736 lines, 15 self-tests. **No Qwen code, no router, no archiving.** All of this session's work was design only. |
| `config.json` | **Unchanged.** `known_vendors` still empty; `tesseract_cmd` still points at the **Windows** Tesseract path — this must change to a macOS path (`/opt/homebrew/bin/tesseract`) when moving to the Mac. No `llm` block yet. |
| `2026-07-27_vendors-from-pdfs.md` | Unchanged. **Now serving as the verification answer key** — independently verified vendors for all 30 PDFs. Target for the new code is 30/30 against this file. |
| `2026-07-27_n8n-workflow-setup.html` | Unchanged. Still valid as reference; n8n was deferred (manual runs first). Its formatting is the model for Deliverable A. |
| `output/reports/predictions.xlsx` | Unchanged — still old Session-3 data/format. Real pipeline not run this session. |
| `input/` | Unchanged — 30 PDFs, still containing **10 duplicate pairs plus the same Staples invoice 4 times**. Not de-duplicated. |
| `Terminal output.md` | Unchanged. Session-4 diagnostic evidence. Can be deleted once no longer needed. |
| `README.md` | Unchanged — **stale**. Describes old renamed-PDF behavior and a 7-col Summary. Will also need Mac/Windows setup notes. |
| `requirements.txt` | Unchanged (PyMuPDF, pytesseract, Pillow, openpyxl, tqdm). The plan deliberately adds **no new dependency** — Qwen calls use stdlib `urllib.request`. |
| `handoffs/2026-07-23_session-1/2-handoff.md`, `2026-07-24_session-3/4-handoff.md` | Unchanged — prior records. |
| `2026-07-27_session-5-handoff.md` | Unchanged, but sits in the **project root** rather than `handoffs/`. Worth moving for consistency (ask first). |
| `Invoice_Boundary_Detection_Project_Summary.md` | Unchanged. |
| `docs/superpowers/specs/...`, `docs/superpowers/plans/...` | Unchanged. |
| `Tesseract_Testing/` | Unchanged — reference only, still stale. |
| `MEMORY.md` + `memory/user-runs-real-pipeline-manually.md` | Unchanged. |
| `notes/2026-07-30_mac-windows-server-setup.html` | **NOT CREATED YET** — this is Deliverable A, pending plan approval. |

---

## 3. What still needs to happen

### Must do
1. **Get the plan approved.** Read `C:\Users\Dhruv Champaneria\.claude\plans\just-like-windows-can-lucky-flame.md`, re-present it, and get a decision. Nothing gets built before this.
2. **Build Deliverable A — the Mac/Windows server setup guide** (`notes/2026-07-30_mac-windows-server-setup.html`). Non-technical, self-contained, offline-readable. The user will follow it themselves on the Mac.
3. **User builds the server on the Mac** using that guide (File Sharing on, `Z:` mapped on Windows, Python + Tesseract installed, Ollama confirmed, `config.json` paths switched to macOS).
4. **Present the proposed Excel format** and get approval — this is an explicit user request and a hard checkpoint. Must cover: batch/date column, how batches are visually separated, locked vs. editable columns, where the new "vendor source" and "page type" columns go, and how `--score` (reads columns **D**, **G**, **H**) survives across batches.
5. **Build Deliverable B — the code changes**: page router with escalation, `ask_qwen_vendor()`, archiving, Excel appending, extended self-tests.
6. **Verify against the answer key** — run the batch and compare the vendor column to `2026-07-27_vendors-from-pdfs.md`. Target 30/30.

### Nice to have
- **Back up `input/` before the first archiving run** (strongly recommended — archiving moves originals).
- **De-duplicate `input/`** — 10 duplicate pairs + the 4-way Staples duplicate are a real double-payment risk. Archiving does NOT solve this; it needs its own follow-up. Ask before deleting anything.
- Update the stale `README.md`.
- Move `2026-07-27_session-5-handoff.md` into `handoffs/`.
- Revisit n8n / an automatic folder watcher once manual runs are proven.
- Optionally pull a lighter text model (e.g. `qwen2.5`) purely for speed on the text route — `qwen2.5vl` handles both routes, so nothing extra is required.

---

## 4. Important rules

### Decisions locked this session — do not re-litigate
- **Script runs ON THE MAC** (option A1). Windows machines install nothing.
- **Model is `qwen2.5vl`** (vision), already installed via Ollama on the Mac. It serves both the text and vision routes, so no second download is needed.
- **The bridge is a local SMB file share** hosted by the Mac, mapped on Windows as `Z:`. **OneDrive was explicitly rejected — do not re-propose it.**
- **Processed PDFs move to `input/_processed/`** — this is how re-reading is avoided. The user chose this after being warned it bumps against the "never touch originals" rule.
- **One master Excel file with appending**, format to be approved before coding.
- **Manual trigger** for now — someone runs the command on the Mac. n8n/watchers deferred.

### Carried forward from earlier sessions
- **NO git actions** anywhere — local-only project (CLAUDE.md hard rule #4).
- **Ask before Terminal/PowerShell**, per task. **The user runs the real/long pipeline and `--score` themselves** — hand them the command, don't execute. See `memory/user-runs-real-pipeline-manually.md`.
- **The vendor bug is a detection-LOGIC gap, NOT OCR.** Proven in Session 5. Do not chase OCR quality to fix vendors.
- **Privacy: client financial data.** Local AI only. Flag loudly if any design would send invoices to a cloud service.
- **Never modify original PDFs. No PDF splitting, ever. No renamed PDF copies** — column B "Proposed PDF Name" is text only. (Archiving *relocates* files; it must never rename, split, edit or overwrite them.)
- **`build_excel_report` must OPEN the existing `predictions.xlsx`**, preserving the user's `Proposed Summary Sheet` tab. Verdict dropdown on **column G**; `--score` reads cols **D** / **G** / **H**.
- **`detect_vendor()` must stay unchanged and offline-testable** — its self-tests at [lines 564–576](../invoice_boundary_detector.py#L564) run with no network. With Ollama off, the script must still behave exactly as it does today.
- **Never read/edit secrets** without asking (`tesseract_cmd` is a local path, not a secret).
- **Plain English first, code second.** Team D (Puneet, Dhruv, Manish, Vijayesh) are **non-engineers**.
- **One `config.json` + one script.** No new code files — documentation deliverables are fine.

### New rule discovered this session
- **Ollama never receives a PDF.** Only text or a base64 image. Any design that says "send the PDF to Qwen" is wrong and needs rethinking.
