# Handoff — Windows setup finished + Qwen whole-PDF vs page-by-page experiments (page-by-page wins)

**Date:** 2026-08-05 (Session 9)
**Session focus:** Finish the Windows setup (Parts C–F), then run a hands-on experiment to see whether the local Qwen model can read a whole invoice PDF — comparing "send the whole PDF at once" vs "one page at a time." Outcome: setup is fully verified and working; page-by-page Qwen is clearly the better approach and is close to accurate after a prompt tweak that hasn't been re-tested yet.

> **Privacy note (unchanged):** No details about the AI/file-host machine (address, account, credentials) are recorded here or anywhere. That side is a completed, external prerequisite. The Mac's Qwen address lives only in `config.json`, which the user fills in and which Claude may NOT read (see rules).

---

## 1. What happened this session

### Finished Windows setup — Parts C–F all verified
- **Part C** (map shared drive as `Z:`) was already done. **Part D** (Python + Tesseract + script in the project folder) confirmed done.
- **Part E** — Claude edited `config.json`: pointed `paths` at `Z:\` (kept the old `output_reports` key **and** added the guide's new `output_folder`/`processed_folder` keys so both today's script and future code work), and added the `llm` block with the `host` left as a placeholder for the user to fill. **The user then filled in the real Mac address themselves.**
- **Part F** — `--selftest` passed (15/15). Qwen reachability confirmed with `curl.exe http://<mac>:11434/api/tags` (the earlier "404" was just PowerShell's `curl` alias — real `curl.exe` works). A small real run produced correct **vendors** on 3 sample PDFs (rules-based).
- Fixed a recurring **`Z:` "username or password is incorrect"** drop mid-session — same fix as Part C: `net use Z: /delete /y`, remap with `<server>\<account>` username format, clear stale Credential Manager entry.

### `config.json` access REVOKED (new hard rule)
After the Part E edit, the user revoked Claude's access to `config.json` as a **hard rule**. Saved to memory (`config-json-access-revoked.md`). Claude must never read/edit it again; instead tell the user which line to change.

### Documentation: `project-overview.md` created
- A **Sonnet agent** wrote `project-overview.md` (architecture, script walkthrough, config described without opening it, rules/checkpoints, status, glossary).
- A **Haiku agent** appended an **"Advanced / Future Design"** section (parked Part C Excel batch format, batch identification via folders+archiving, how `--score` works, how the Page Detail sheet works).

### Excel "batch format" (Part C) — PARKED
Proposed accumulating-batches format (append instead of wipe; new columns I=Vendor source, J=Page type, K=Batch; row-shading per batch; light cell-locking; `--score` untouched because A–H don't move). **User parked this for later.** Not approved, not built.

### Qwen integration — brainstormed, then narrowed to a timing/accuracy experiment
- Discussed a routing design (scanned PDF → Qwen vision; digital PDF → Tesseract text → Qwen verifier; image files → Qwen vision; Qwen off → rules-only). **User parked that whole routing design "for part 2."**
- For "part 1," user wanted a simpler question answered first: **can we just pass a whole PDF to Qwen, and how long does it take / how accurate is it?**
- **Key technical fact established:** Qwen (`qwen2.5vl:7b` via Ollama) does **not** accept PDFs — only **images**. So pages must be rendered to PNG (PyMuPDF) and base64-sent. Also Ollama's default context window (4096 tokens) is too small; must raise `num_ctx`.

### Built two throwaway spike scripts (in the temp scratchpad — see rules about persistence)
- `qwen_pdf_timing_spike.py` — sends **all** pages in one request.
- `qwen_pdf_pagebypage_spike.py` — sends **one page per request**, then assembles structure in code.
Both take the Qwen host as a CLI arg (never read `config.json`), render at a `--dpi`, and set `--num-ctx`.

### Established ground truth for 3 test PDFs (via a Sonnet agent, read-only)
- **`1f30c44b… - Copy.pdf` (Staples, 4 pages):** p1 = summary+remittance, p2 = extended-summary/index, **p3 = invoice 6069091799 ($67.65), p4 = invoice 6069091800 ($93.79)**. **TRUE = 2 invoices on pages 3 & 4.** (The rules tool had this wrong.)
- **`1f6c9090… - Copy.pdf` and `…9ea.pdf` (Cockey's, 3 pages each, duplicates):** each page is a separate one-page invoice (3171819/May, 3182811/Jun, 3205194/Jul, all $1,036.32). **TRUE = 3 invoices on pages 1,2,3.** (The rules tool was correct on these.)

### Experiment results (all on the Staples 4-page file)
| Approach | Result vs truth (2 invoices, pp3&4) | Time |
|---|---|---|
| Whole-doc @150dpi | Count 2 ✅, vendor Staples ✅, but pages **inverted** (said 1&2), misread inv#…99→…90, dropped p4 ❌ | 51s |
| Whole-doc @350dpi | Worse — self-contradictory, called summary# an invoice#, couldn't read inv#2 ❌ | 83s |
| **Page-by-page @200dpi** | **p3 & p4 nailed** (INVOICE, Staples, correct numbers) ✅; remittance p1 excluded ✅; but **p2 index miscounted as INVOICE** → 3 vs 2 ❌; vendor on non-invoice pages = the customer ❌ | 155s (~39s/pg) |

**Conclusion:** whole-PDF-to-Qwen does not work at any resolution with this 7B model; **page-by-page is the promising path** — it read the actual invoices and their vendor correctly.

### Applied 2 prompt tweaks to the page-by-page spike (NOT yet re-run)
To fix the two remaining page-by-page errors, `build_prompt()` in `qwen_pdf_pagebypage_spike.py` was edited to: (1) a page that merely **lists/indexes multiple invoice numbers** is **SUMMARY, not INVOICE**; (2) **vendor = the company that ISSUED the invoice (seller / remit-to payee), NOT the customer being billed.** **These tweaks have not been tested — that's the very next step.**

---

## 2. Current state of files

| File | Status |
|---|---|
| `config.json` | **UPDATED this session** (Part E: `Z:\` paths + `llm` block). **ACCESS NOW REVOKED — do not read/edit.** User has filled in the real Mac `host`. |
| `invoice_boundary_detector.py` | **Unchanged.** Still the Session-4 version (736 lines, 15 self-tests, rules-based). No Qwen code. |
| `project-overview.md` | **CREATED this session** (root). Full reference doc + an "Advanced / Future Design" section. |
| `notes/2026-07-30_mac-windows-server-setup.html` | Unchanged. Setup guide (Deliverable A). Windows setup Parts C–F now all complete against it. |
| `2026-07-27_vendors-from-pdfs.md` | Unchanged. 30-PDF vendor answer key. |
| `handoffs/2026-08-05_session-9-handoff.md` | **CREATED this session** (this file). |
| `handoffs/2026-08-04_session-8-handoff.md` | Unchanged — prior record. |
| `input/` | Unchanged — 30 PDFs, still 10 duplicate pairs + Staples 4×. Not de-duplicated. |
| `output/reports/predictions.xlsx` | Refreshed by the small Part-F test run (3 PDFs, rules-based). |
| `README.md` | Unchanged — still stale. |
| `requirements.txt` | Unchanged. Spikes add no dependency (stdlib `urllib` + existing PyMuPDF). |
| **SCRATCHPAD** `qwen_pdf_timing_spike.py` | **CREATED this session** — whole-doc spike. Lives in the TEMP scratchpad (may not persist — see rules). |
| **SCRATCHPAD** `qwen_pdf_pagebypage_spike.py` | **CREATED + prompt-tweaked this session** — page-by-page spike. Lives in the TEMP scratchpad. **The tweaked prompt is untested.** |

Scratchpad path: `C:\Users\DHRUVC~1\AppData\Local\Temp\claude\C--Users-Dhruv-Champaneria-Desktop-Res1\00377f0e-e716-466b-9eb9-8275710ef43e\scratchpad\`

---

## 3. What still needs to happen

### Must do (immediate next step)
1. **Re-run the tweaked page-by-page spike** on the Staples file and check whether page 2 is now correctly SUMMARY (giving the correct **2 invoices on pages 3 & 4**) and whether vendor now reads the seller, not the customer. Command (user runs it, fills in Mac address):
   ```
   python "<scratchpad>\qwen_pdf_pagebypage_spike.py" "Z:\input\1f30c44b-7c0a-4116-8099-552223fc5309 - Copy.pdf" http://<YOUR-MAC-ADDRESS>:11434
   ```
2. If clean, **test on more PDFs** (e.g. the Cockey's file — expect 3 invoices on pages 1,2,3 — and a couple of other vendors) to see if page-by-page holds up broadly, and note the per-PDF time.

### Nice to have / later
- **Decide integration path:** if page-by-page proves reliable, plan how it becomes real code (Deliverable B). Still gated by parked decisions (the routing design "part 2" and the Excel batch format).
- **Documentation queued (user said LATER, not now):** add to `project-overview.md` (a) the routing flow (scanned→vision, digital→Tesseract→Qwen verifier, image→vision, Qwen-off→rules), and (b) the offline-safe fallback behavior.
- **Preserve the spikes:** they live in a TEMP scratchpad that may be cleared. If worth keeping, move them into `automation/` (they are drafts, so `automation/` is the right home) — ask the user first.
- De-duplicate `input/` (double-payment risk). Back up `input/` before any archiving. Update stale `README.md`. Roll setup out to 2nd/3rd Windows PC.

---

## 4. Important rules

- **`config.json` access is REVOKED (hard rule, this session).** Never read or edit it. Tell the user which line to change. See `memory/config-json-access-revoked.md`.
- **Qwen needs IMAGES, not PDFs.** Render pages to PNG (PyMuPDF) and base64-send. **Raise Ollama `num_ctx`** (default 4096 is too small; a 4-page doc ≈ 5,600 tokens).
- **Whole-PDF-to-Qwen does NOT work with `qwen2.5vl:7b`** at any dpi — use **page-by-page**.
- **The user runs all Qwen/pipeline calls themselves** — hand them exact commands, don't execute. See `memory/user-runs-real-pipeline-manually.md`.
- **Excel batch format = PARKED. Routing design = PARKED "for part 2".** Don't build either without the user re-opening them.
- **Do NOT record the AI/file-host machine's address/account/credentials** anywhere.
- **Model tag is exactly `qwen2.5vl:7b`.** Config must default `host` to `http://localhost:11434` if absent; `detect_vendor()` stays unchanged and offline-safe (Qwen off ⇒ behaves exactly as today).
- **Qwen/Ollama never receives a PDF** — only extracted text or a base64 page image. **Local AI only** (client financial data). Flag loudly if any design would send invoices to a cloud service.
- **Never modify/split/rename original PDFs.** Archiving (future) only *relocates* via `shutil.move`.
- **NO git — local-only project.** **Ask before Terminal/PowerShell**, per task. **Plain English first, code second** (Team D are non-engineers). **One `config.json` + one script**; the spikes are throwaway experiments kept OUT of the project folder (in scratchpad).
