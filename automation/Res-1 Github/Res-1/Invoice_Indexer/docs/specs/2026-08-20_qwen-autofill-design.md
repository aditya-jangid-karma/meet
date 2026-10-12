# Spec — Auto-Filling the Spreadsheet from PDFs with a Local AI (Qwen)

**Date:** 2026-08-20
**Status:** ✅ APPROVED 2026-08-20 (design) — build may proceed. Test run of the
path move (separate work) still pending.
**Relates to:** `context/todos.md` "Phase 2" (auto-fill) and item #5 (history).
This is the "fill the sheet" half; the recorder that types the sheet into
Bottomline is unchanged.

---

## 1. What this adds, in one paragraph

Today a human types each invoice's details into `invoices.xlsx` by hand before
the recorder can run. This change adds a **reader**: a local AI model (Qwen,
already running on the office Mac) looks at each invoice PDF and writes the
details into the sheet for you. It **reads and fills only** — it never touches
Bottomline, never presses anything, and every value it writes is still reviewed
by a human before the recorder types it in. The spreadsheet stays the seam: the
reader fills it, the recorder reads it, and neither knows about the other.

---

## 2. The two-machine setup (unchanged from the existing office design)

| Machine | Job |
|---|---|
| **Windows PC** | Runs this reader script (Python + Poppler). Drops/reads PDFs and the Excel on the mapped drive. |
| **Office Mac** | Runs the local AI (**Ollama** serving **`qwen2.5vl:7b`**) at `http://<mac>:11434`, and hosts the shared folder mapped as a drive on Windows. |

**Privacy — the hard line.** The AI is **local only**. Invoice images go to the
Mac's Qwen over the office network and nowhere else. No cloud AI, no API key. If
any future change would send an invoice or its data to a cloud service, stop and
raise it loudly.

---

## 3. The pipeline, start to finish (one invoice)

1. **Render.** Poppler turns the invoice PDF's pages into PNG images at
   **200 DPI** (up to **3 pages** — `VISION_MAX_PAGES = 3`).
2. **Ask Qwen once.** A single Ollama call with **all of that invoice's page
   images attached together** (so a total on page 2 sits in the same view as the
   header on page 1). **Images only — no page text is ever put in the prompt.**
   The call carries a **JSON Schema** (Ollama's `format`) so the model can only
   answer with valid, structured JSON, and **`num_ctx = 32768`**.
3. **Read the answer.** Parse the JSON. If it will not parse, **retry once**. If
   it still will not parse, **send the invoice to human review** — nothing is
   written for that invoice.
4. **Match against the directory** (section 6). The vendor Qwen returns is looked
   up against the vendors already in `invoices.xlsx`; a match reuses the exact
   recorded spelling, no match passes through as a new vendor.
5. **Write to `invoices.xlsx`** (section 5) — one row per invoice.
6. **Human reviews** the filled sheet, then runs the recorder as usual. The
   recorder's own "Done?" review before Convert is the final gate.

```
PDF ──Poppler 200dpi──► PNG(s) ──one Ollama call, images only──► Qwen (Mac)
                                   JSON Schema + num_ctx=32768        │
   write row ◄── directory-match ◄── parse JSON (1 retry) ◄──────────┘
   to invoices.xlsx        (vendor)        else ► human review
```

---

## 4. Decisions locked in this session

| # | Decision | Why |
|---|---|---|
| D1 | **LLM-only. No Tesseract, no OCR branch.** | The team chose the simplest path: every PDF goes Poppler → Qwen. No scan/confidence gate. |
| D2 | **No pdfplumber, no label-guard.** | The label-guard exists to protect a *payment-reduction* decision. This script does no payment math — it only fills boxes for a human to review — so there is nothing for it to protect. |
| D3 | **One call per invoice, all its page images together — never one call per multi-invoice bundle.** | A single call holding all pages keeps related figures in one attention window. Asking one call to find invoice *boundaries* across a bundle is what makes a vision model invert pages and drop a document. |
| D4 | **Each PDF is treated as a single invoice.** No split stage. | These PDFs come from Bottomline's "Images to be Indexed" queue, where each item is already one document. Bundle-splitting is a separate, pre-Bottomline concern and is out of scope here. |
| D5 | **`num_ctx = 32768`** (not the Ollama default). | A measured value, not a guess. Page images are large; too small a window **silently truncates** and looks like a model error — a lower setting has been seen to drop a page-2 line item. The cost of the larger window is RAM only, not speed. |
| D6 | **200 DPI for the images.** | Enough for the model to read invoice text reliably; higher DPI costs more with no accuracy gain for this model. |
| D7 | **`due_date` filled only if it is printed on the invoice**, otherwise left blank. | Many invoices show no due date. Do not invent one. |
| D8 | **`integration_package` always left blank — a human fills it.** | It is INTACCT/YARDI routing, an internal accounting decision, not printed on the invoice. Revisit when the team decides a rule. |
| D9 | **`property` always left blank — a human fills it.** | Which building/unit is an internal mapping, not a reliable invoice fact. |
| D10 | **`invoices.xlsx` is the bootstrap master list** until real master lists exist. | The team has no vendor/property/chart-of-accounts master yet. The sheet's own distinct values serve as the growing directory. |

---

## 5. What Qwen returns, and where it lands

Qwen answers with JSON constrained to these fields. Each maps to a column the
recorder already reads (`header_to_key` turns the human header into the key).

| JSON field | Sheet column | Filled by | Notes |
|---|---|---|---|
| `vendor` | Vendor | Qwen → directory-match | Canonical spelling used if the vendor is already known. |
| `invoice_number` | Invoice Number | Qwen | Kept as text — never let a leading zero (`007458`) become a number. |
| `invoice_date` | Invoice Date | Qwen | As printed. |
| `due_date` | Invoice Due Date | Qwen | **Only if printed**, else blank (D7). |
| `amount` | Amount | Qwen | The invoice total. |
| — | Property | **Human** | Left blank (D9). |
| — | Integration Package | **Human** | Left blank (D8). |
| — | Image Name | (existing) | The recorder's key to find the invoice in the queue; set by whatever names the PDF, not by Qwen. **Open — see section 8.** |

The JSON Schema names these fields, marks which may be null (`due_date`), and
forbids extra keys, so an unparseable or off-format answer is caught at step 3.

---

## 6. The directory-match layer (the guardrail that actually applies)

**What it is:** after Qwen answers, Python takes the returned `vendor` and
searches the vendors **already recorded in `invoices.xlsx`**. This validates the
model's output against a known list — it reads the model's *answer* and the
*sheet*, never the PDF.

- **Match found** → write the **canonical recorded spelling** into the row.
- **No match** → write Qwen's spelling as-is; this is a **new vendor** joining
  the directory the next time round.

**Why it earns its place:** the recorder has already failed once with
"vendor: 0 matches" because the sheet's spelling did not match Bottomline's
dropdown (`context/todos.md` #3). Feeding a canonical, previously-accepted
spelling makes the dropdown match on the first try.

**Bootstrap reality (D10):** early on the sheet is nearly empty, so most vendors
pass through unmatched. That is expected, not a fault — the list fills as you
record. When a real vendor/property/chart-of-accounts master arrives, this layer
points at that instead, with no change to the rest of the pipeline.

---

## 7. Error handling — nothing silent, nothing invented

| Situation | What happens |
|---|---|
| Qwen unreachable / Mac asleep | Stop loudly; write nothing. (Same spirit as the recorder's empty-queue guard.) |
| JSON will not parse | Retry the call **once**; still bad → **human review**, no row written. |
| A required field missing | That invoice → human review, not a half-filled row. |
| `num_ctx` too small | Prevented by D5. Truncation is silent, so the fix is the setting, not detection. |
| Vendor not in the directory | Not an error — written as a new vendor (section 6). |

The overarching rule matches the recorder's: **a value that "looks filled but is
wrong" is worse than a blank.** When in doubt, blank it and send to human review.

---

## 8. Out of scope / open items

- **No multi-invoice splitting** (D4). If a bundle ever appears, it is handled
  outside this script.
- **`integration_package` rule** (D8) — parked until the team defines it.
- **`Image Name`** — the recorder finds each invoice in the queue by its Image
  Name. How the reader learns/sets the Image Name for each PDF is **not settled
  here** and must be resolved before this is wired end to end. (Options: the PDF
  filename already is the queue image name; or a human supplies it.)
- **Qwen host address** goes in a small config the **user fills** (the Mac
  address); it is not hard-coded in the script and Claude does not read it.
- **PDF input location** on the mapped drive (which folder the invoice PDFs sit
  in) — to be fixed as a path, alongside the `invoices.xlsx` path already moved.
- **No automated number cross-check** (D2). The safety net is human review at the
  recorder's "Done?" step before Convert.

---

## 9. Dependencies

- **Poppler** (chosen this session) — renders PDF pages to PNG. The repo already
  ships a `poppler-windows` build under the PDF Splitter's `Tesseract_Testing/`.
- **Ollama + `qwen2.5vl:7b`** on the Mac — already installed and serving.
- **Python stdlib** for the HTTP call (`urllib.request`) and JSON — no new
  heavyweight dependency expected.
- **openpyxl** — already used by the recorder to read/write the sheet.

---

## 10. What this does NOT change

- **The recorder (`automation/invoice_recorder.py`) is untouched.** It still
  reads `invoices.xlsx` and types into Bottomline exactly as today.
- **No git actions** — local-only project.
- **The spreadsheet stays the seam.** This reader is a drop-in front end: remove
  it and a human simply fills the sheet by hand as before.
