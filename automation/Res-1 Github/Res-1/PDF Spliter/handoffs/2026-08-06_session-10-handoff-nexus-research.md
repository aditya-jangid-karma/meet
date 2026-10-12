# Handoff — Research only: can we create invoice entries in Bottomline/Nexus via an API key?

**Date:** 2026-08-06 (Session 10)
**Session focus:** Pure desk research into whether Bottomline's Nexus AP automation platform exposes an API that would let us create a coded invoice ("indexing") entry programmatically, and how one would get access. Outcome: question answered — the capability exists but access is gated. Research paused here at the user's request.

---

> ## ⚠️ THIS IS A SEPARATE TRACK — NOT THE PDF-SPLITTING PROJECT
>
> Sessions 1–9 are the **invoice PDF boundary-detection / splitting** project
> (`invoice_boundary_detector.py`, Qwen page-by-page spikes, `Z:` share, etc.).
>
> **This session touched none of it.** No code was written, read, or run. No files
> in the project were created or modified. The Session-9 "must do" list is still
> the live next step for that project and is untouched — see
> `handoffs/2026-08-05_session-9-handoff.md`.
>
> This note exists only so the Nexus research isn't lost. Keep the two tracks apart.

---

## 1. What happened this session

### The question asked
Team D wanted to know whether an **API key** can be obtained to make an invoice/expense entry directly in Bottomline's Nexus platform — what Nexus calls **"indexing"** (entering vendor, property/entity, invoice number, date, amount, and the GL coding lines, then dropping it into the approval workflow).

### Research method
Web research only — Bottomline's public site, their developer portal, and the published pages of their integration partners. **No Bottomline account was accessed and no credentials were sought or used.** Nothing was run in a terminal.

### Finding 1 — The capability definitely exists
**PredictAP**, an official Bottomline/Nexus integration partner, pushes **fully coded invoices** into the Nexus queue in real time at **"Open"** status — invoice header, line detail, and coding assignments. That is precisely an indexing entry, done by machine. So the endpoint is real and in production use today.

The same integration also **syncs the other direction, hourly**: vendor master, GL accounts, entity/property codes, invoice history, and payable status. That means the coding reference lists could be pulled programmatically too.

### Finding 2 — But there is no self-serve API key
There is no page where you sign up and generate a Nexus key. Specifically:
- **No public documentation** — no OpenAPI spec, no endpoint list, no field reference, no GitHub SDK, no sandbox.
- **Bottomline's public developer portal (`developer.bottomline.app`) does not include Nexus at all.** It covers only PTX Open Banking, PTX Reporting, PTX Link Management, plus Paymode and Digital Banking. NexusPayables is absent.
- Bottomline's own marketing does confirm "flexible REST APIs" for Nexus and that vendors may submit "eInvoice using APIs" — but every partner page ends at "contact us for full documentation."
- **Auth scheme for Nexus is publicly unknown.** Bottomline's *other* APIs use Client ID + Client Secret → bearer token, with admin approval per application. Reasonable to expect the same, but it is an assumption, not a documented fact.

### Finding 3 — PredictAP and the Partner Program are different things (a point that caused confusion mid-session)
- **PredictAP** = a company you *buy software from*. Their AI reads the invoice PDF, predicts the coding, and pushes it into Nexus for you. **You never receive an API key.** They hold it.
- **Nexus Integration Partner Program** = Bottomline's access channel for software vendors who want to build against the Nexus API. **This is where API credentials actually come from.**
- They are not alternatives at the same level — PredictAP is a *graduate* of the program.

### Finding 4 — The real blocker is contractual, not technical
Team D is the **external CPA firm**. If the *client* owns the Nexus subscription, then API credentials get issued to **the account holder**, not to their outsourced bookkeeper. Team D would need to be authorised under the client's agreement. **This must be settled before any build effort is spent.**

### Worked example produced
A side-by-side comparison was written out for a sample invoice (Apex Plumbing, inv. 88213, $1,847.50, split across GL 6420 and GL 6435):
- **Manual today:** ~5 screen steps, roughly **4–6 minutes** per invoice.
- **Via API:** a single `POST` carrying the same facts as JSON — **under a second** — landing the invoice already coded, image attached, at "Open".
- **What does not change:** approval workflow still runs, audit trail intact, bad data (unknown vendor, split that doesn't tie to total) still gets rejected. The API creates; it does **not** approve or pay.

> **Caveat carried forward:** the JSON in that example was **illustrative**. Field names and endpoint were inferred, not documented. Do not treat it as a spec.

### The strategic question left on the table
The API only helps if you *already know* the GL code before opening Nexus. Something still has to decide 6420 vs 6435.
- If coding is already known (rules/spreadsheet) → a plain API integration genuinely solves the bottleneck.
- If coding must be worked out per invoice → the API is only half the solution, and PredictAP should be priced before building anything.

**This question was not answered this session.**

---

## 2. Current state of files

| File | Status |
|---|---|
| `handoffs/2026-08-06_session-10-handoff-nexus-research.md` | **CREATED this session** (this file). The only file created. |
| `handoffs/2026-08-05_session-9-handoff.md` | Unchanged — still the live handoff for the PDF-splitting project. |
| `config.json` | Unchanged. **ACCESS REVOKED — do not read/edit.** |
| `invoice_boundary_detector.py` | Unchanged. Still the Session-4 version (736 lines, 15 self-tests, rules-based). |
| `project-overview.md` | Unchanged. |
| `notes/2026-07-30_mac-windows-server-setup.html` | Unchanged. |
| `2026-07-27_vendors-from-pdfs.md` | Unchanged. |
| `input/` | Unchanged — 30 PDFs, still not de-duplicated. |
| `output/reports/predictions.xlsx` | Unchanged since Session 9's Part-F test run. |
| `README.md` | Unchanged — still stale. |
| `requirements.txt` | Unchanged. |
| Scratchpad Qwen spikes | Unchanged and **untouched this session**. Still in the Session-9 temp scratchpad, still at risk of being cleared, tweaked prompt still untested. |

**No automation, script, or note file was produced.** This was research only.

---

## 3. What still needs to happen

### Must do — for the Nexus track (all are phone/email tasks, not build tasks)

1. **Establish who holds the Nexus contract.** Client or Team D? Everything downstream depends on this single fact. Start here.
2. **Contact the client's Bottomline account manager / CSM** — the highest-value contact, because they own the tenant and can escalate internally. Suggested wording:
   > "We use an external accounting team that codes invoices for us. We want to create indexed/coded invoices in Nexus programmatically rather than keying them. Please confirm: (a) whether customer-level REST API credentials for invoice creation can be provisioned on our tenant, (b) the authentication method and whether a sandbox exists, (c) any additional licensing cost, and (d) whether our external firm can be authorised to use those credentials."

   **(a) and (d) are the make-or-break items.**
3. **Answer the coding question internally:** on a typical invoice, is the GL code already known before Nexus is opened, or must it be worked out each time? This decides whether an API is a full or partial solution.

### Nice to have / later
- **Fallback contact:** Bottomline general support, **1-800-472-1321** (published on their Nexus integrations page) — ask for the "Nexus AP Automation technical/integrations team." Use only if no account manager is known.
- **Partner route:** `bottomline.com/partners`, "Technology and Innovation Partners" track — correct door **only** if Team D wants to build a reusable product across many Nexus customers, not a one-client script. No published partner email address was found; everything runs through their contact form and phone.
- **Price PredictAP** as the buy-vs-build comparison, especially if the coding decision is the real bottleneck.
- If this research resumes and grows, consider a dedicated `notes/` file for it (per CLAUDE.md, `notes/` is the home for observations) — **ask the user first.**

### Still open, unanswered
- Exact endpoint names, request schema, and required indexing fields.
- Whether Nexus API access carries a separate licence fee.
- Whether Bottomline grants customer-level (non-partner) API keys at all — **nothing public confirms they do.**

---

## 4. Important rules

- **NO git — this project is local-only.** Do not run, suggest, or act on any git command.
- **Ask before using Terminal/PowerShell**, per task. None was used this session.
- **`config.json` access is REVOKED (hard rule).** Never read or edit it; tell the user which line to change. See `memory/config-json-access-revoked.md`.
- **Never advise committing or storing secrets.** If Nexus API credentials are ever issued, they go in a `.env`-style file that is git-ignored and that Claude may not read. **Credentials are handed over manually by the user, never pasted into the repo or into chat.**
- **Do NOT record the AI/file-host machine's address, account, or credentials** anywhere.
- **The user runs all pipeline/Qwen commands themselves** — hand over exact commands, don't execute. See `memory/user-runs-real-pipeline-manually.md`.
- **Plain English first, code second** — Team D are non-engineers (Puneet, Dhruv, Manish, Vijayesh).
- **Local AI only for client financial data.** Flag loudly if any design would send invoices to a cloud service. *(Relevant here: a Nexus API integration would send invoice data to Bottomline — that is the client's own AP system of record, so it is expected and fine, but it is a different posture from the deliberately-local Qwen work. Worth stating plainly to the team.)*
- **Keep this research track separate from the PDF-splitting project.** Two different problems, two different sets of next steps. Do not merge the to-do lists.
- **Parked from Session 9 and still parked:** the Excel batch format, and the Qwen routing design ("part 2"). Don't build either without the user re-opening them.
