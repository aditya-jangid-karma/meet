# Project Context — Invoice_Indexer

**This file is the standing description of the project: what it is, why it exists,
and what it is trying to achieve.** It is not a status report and is not rewritten
every session — update it only when the *purpose or shape* of the project changes.

- For "where are we today" → `HOTcontext.md`
- For "how is it wired" → `architecture.md`
- For "why was it done that way" → `decisions.md`
- For "what's left" → `todos.md`

---

## Who this is for

Team D — the external CPA / bookkeeping firm: Puneet, Dhruv, Manish, Vijayesh.
None of them are engineers. Everything in this project is written to be
maintained by an accountant, not a developer.

## The client system

**Bottomline Nexus** (`residentialone.nexuspayables.com`) — the AP platform where
invoices are received, indexed, coded and approved. Invoices arrive as scanned
images that land in an **Image Management** queue. Until somebody indexes an
image, it is just a picture — it has no vendor, no amount, no invoice number, and
cannot flow into the approval process.

## The problem

Indexing is pure manual typing and there is a lot of it. For each image, somebody
opens it, reads it, and types seven things into a form:

| # | Field | Kind of box |
|---|---|---|
| 1 | Vendor | search box with dropdown |
| 2 | Property | search box with dropdown |
| 3 | Invoice Number | plain text |
| 4 | Invoice Date | date |
| 5 | Invoice Due Date | date |
| 6 | Amount | number |
| 7 | Integration Package (YARDI / INTACCT) | dropdown |

It is slow, it is dull, and dullness is where transposition errors come from. A
wrong vendor or a wrong amount does not announce itself — it surfaces weeks later
at reconciliation, when finding it costs far more than entering it did.

## What this project does

Reads the seven values from a spreadsheet you control, opens a real browser, and
types them into Bottomline's indexing screen — exactly as a person would, keystroke
by keystroke.

**It fills the boxes and stops.** It does not press Save, Convert to Invoice, Save
as Exception, or Delete. A human reviews every box against the invoice image and
presses the buttons.

## What "done" looks like

A month's invoices indexed in a fraction of the time, with:

1. **No wrong-document entries.** The Image Name on screen is checked against the
   spreadsheet row before anything is typed.
2. **No silent failures.** Every stop condition is loud. The script would rather
   halt and be inconvenient than continue and be wrong.
3. **A reviewable trail.** Every run writes a log to `logs/`.
4. **A human at the last step.** Nothing reaches the client's books without a
   person having looked at it.

## The governing principle

> **A wrong value that saves itself is a correction, a re-open, and an
> explanation. A wrong value sitting on screen is just something you retype.**

That is why the script fills and stops, why it refuses to guess a date format,
why it hands a dropdown back rather than picking the closest match, and why it
would rather halt than proceed on an assumption. Speed is the goal; correctness
is the constraint. **Where the two conflict, correctness wins every time.**

## Scope

**In scope** — the image indexing screen only: the seven fields above, plus
reading the Image Name box as a safety check.

**Out of scope** — everything after "Convert to Invoice". That second screen has
its own Property field, its own Save, and its own workflow. The script stops
before it.

**Explicitly dropped** — GL account (no such field on this screen) and Document
Type (exists, rarely touched).

## Where this is heading

**Phase 1 (now).** A human fills the spreadsheet; the script types it in.

**Phase 2 (later).** An AI extraction step reads the invoice PDFs and fills the
spreadsheet, leaving the human to check rather than type.

**The spreadsheet is deliberately the seam between the two.** Phase 2 changes how
the spreadsheet gets filled and changes nothing about how it gets typed in. That
is why this project reads a spreadsheet instead of reading the PDFs directly.

## Related but separate

Two other tracks live in this repo and share nothing with this one. **Do not merge
their to-do lists or their handoffs.**

- **PDF Splitter** — splitting bulk PDF scans into individual invoices.
- **Nexus API research** — whether Bottomline has a programmatic interface that
  would make browser automation unnecessary. If that ever lands, this project's
  typing layer is what it replaces.

## Standing constraints

- **Git exists, but Claude never touches it.** Changed 2026-08-14: the project
  moved to `Desktop\TeamD-Git\Res-1-\Invoice_Indexer` and is now inside a real
  repo. **Claude must not run or suggest any git command** — re-confirmed by the
  user the same day. Advice on what is safe to commit is still wanted.
- **Credentials are never read by Claude** — `.env` and
  `automation/.bottomline_session.json` are off-limits. The user edits them.
- **The user runs anything that touches Bottomline.** Claude hands over the command.
- **Nothing installs system-wide.** Deleting the `Invoice_Indexer` folder removes
  every trace of this project from the PC.
