# Handoff — Started brainstorming the Invoice Boundary Detection engine (spec phase)

**Date:** 2026-07-23 (Session 1)
**Session focus:** Begin the Superpowers build flow (brainstorm → spec → plan) for the Rule-Based Invoice Boundary Detection engine. We are mid-brainstorming; no code written yet, by design.

---

## 1. What happened this session

### Read the project brief
Read `Invoice_Boundary_Detection_Project_Summary.md` — the design/spec brief for a rule-based engine that reads multi-invoice PDFs and predicts **which page each new invoice starts on**, WITHOUT splitting the PDF until accuracy is proven. It lays out 6 phases: (1) OCR/text extraction, (2) feature extraction, (3) rule engine, (4) confidence engine, (5) prediction mode → Excel, (6) splitting (deferred).

### Chose the Superpowers process
User asked to follow the Superpowers plugin and "complete the plan and spec first." Invoked the `superpowers:brainstorming` skill. The hard gate: NO code, NO implementation skill, until a design is presented AND the user approves it, then it gets written to a spec doc, reviewed, and only then does `writing-plans` run.

### Scope decision (flagged and agreed in spirit)
Recommended treating **Phases 1–5 (detect boundaries + output Excel + measure accuracy)** as THIS spec, and deferring **Phase 6 (actual PDF splitting)** to a later spec — matches the brief's own "don't split until accuracy is proven" philosophy. User has not objected.

### Clarifying questions answered so far (brainstorming)
- **Q1 — PDF type:** **C = MIXED** (some digital/text-based, some scanned images). → Reader must "try text extraction first, fall back to OCR." Tesseract OCR will need a one-time Windows system install.
- **Q2/Q3 — Input location:** PDFs live in a **OneDrive-synced LOCAL folder** (a dummy/test OneDrive for now). Treated as a plain local folder path — NO cloud API/auth needed in v1. Script reads from that folder, writes Excel to an output folder. Forward-compatible with real OneDrive automation later.
- **Q3 — Sample data:** **NONE yet.** Consequences: (a) rule weights/thresholds must be **config-driven** with sensible defaults, tuned later when real PDFs arrive; (b) build a couple of **hand-made test PDFs** to prove pipeline mechanics; (c) the **accuracy-measurement loop is the most important early deliverable** because that's the tuning tool.

### Question left UNANSWERED (this is the resume point)
- **Q4 — Validation loop mechanism.** Proposed flow: script writes `predictions.xlsx` (one row per page: PDF name, page #, Prediction Break/Continue, Confidence, Score, Triggered Rules, + a blank **Actual** column) → reviewer fills in the Actual column in Excel → run script in **"score" mode** to compute Precision/Recall/F1/false-pos/false-neg. Sub-choice offered:
  - **A.** Reviewer fills EVERY page's Actual value (rigorous, slower).
  - **B.** Reviewer only marks pages the script got WRONG, blank = correct (faster — recommended).
  - **C.** Team has its own Excel way — describe it.
  - **USER HAS NOT ANSWERED YET.** The session was handed off at this exact point.

## 2. Current state of files

| File | Status |
|---|---|
| `Invoice_Boundary_Detection_Project_Summary.md` | Unchanged — the source brief/spec for the engine. Read it first. |
| `CLAUDE.md` / `Claude.MD` | Unchanged — project rules (Team D, non-engineers, plain English, ask before terminal, never commit secrets). |
| `2026-07-23_session-1-handoff.md` | **CREATED** — this file. |
| `docs/superpowers/specs/` | Does NOT exist yet — the brainstorming design doc will go here as `YYYY-MM-DD-invoice-boundary-detection-design.md` once the design is approved. |
| (no code files) | Nothing built yet — correct for this stage. |

## 3. What still needs to happen

### Must do (resume the brainstorming exactly here)
1. **Get the user's answer to Q4** (validation loop: A / B / C above).
2. Ask the remaining clarifying questions, roughly:
   - **Environment/setup:** Is Python installed? Are they OK doing a one-time Tesseract OCR install on Windows? (They are non-engineers — this needs a plain-English walkthrough.)
   - **Confidence thresholds / review workflow:** what confidence counts as "auto-approved" vs "manual review" (brief mentions both).
   - Anything about vendor variety / expected volume (light touch, since no samples yet).
3. **Propose 2–3 approaches** with trade-offs + a recommendation (per brainstorming skill).
4. **Present the design in sections**, getting approval after each (architecture, modules, data models, config, error handling, testing).
5. **Write the design doc** to `docs/superpowers/specs/2026-07-23-invoice-boundary-detection-design.md` and commit (note: repo is NOT currently a git repo — may need `git init` first, ASK before running terminal per CLAUDE.md).
6. **Spec self-review** (placeholders, consistency, scope, ambiguity), then **user reviews the spec**.
7. **Invoke `writing-plans`** to turn the approved spec into an implementation plan. (Do NOT invoke any other implementation skill from brainstorming — writing-plans is the only next step.)

### Nice to have
- Draft 2 hand-made test PDFs (one single-invoice, one multi-invoice across vendors) to validate the pipeline once building starts.
- Decide default rule weights (brief suggests: Invoice # changed +100, Vendor changed +40, Invoice header +30, Same vendor −20, Continuation pattern −40).

## 4. Important rules

- **NEVER commit secrets** — API keys, passwords, tokens, `.env`, QBO/AppFolio/FCCB creds. Guide the user on what to push vs. handle manually. (`.gitignore` helps but stay alert.)
- **NEVER use Terminal/PowerShell without explicit permission** for that specific task — ask first. (Relevant: `git init`, installing Tesseract/Python libs will all need permission.)
- **NEVER read/edit secrets files** (`.env` or similar) without asking.
- **Work one small step at a time; wait for confirmation** before the next step (global rule + brainstorming's one-question-at-a-time).
- **Plain English first, code second** — Team D are CPAs/bookkeepers, not engineers. Walk through non-trivial commands; reference exact file paths.
- **Superpowers hard gate:** no implementation/code until the design is presented, approved, written to a spec, and user-reviewed. Terminal state of brainstorming = invoke `writing-plans`, nothing else.
- **Every folder needs a README** (per CLAUDE.md) written in explanatory manner covering the technical aspects/libraries so a CPA/CA can maintain it long-term.
- **Naming:** date-prefixed `YYYY-MM-DD_short-slug.md` (slug ≤ 4 words); never put PII in filenames.
