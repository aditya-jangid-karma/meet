# Architecture — Invoice_Indexer

How the pieces fit together. Written for a CPA, not an engineer.
Read `README.md` in the project root for the day-to-day operating manual.

---

## The problem in one paragraph

Invoices arrive in Bottomline Nexus as scanned images. Someone has to open each
one and type seven pieces of information into an indexing screen. This project
does the typing, reading the values from a spreadsheet you control. It fills the
boxes and **stops** — a human reviews every box and presses the buttons.

---

## The flow

```
input/invoices.xlsx          <- you fill this in (one row per invoice)
        |
        |  openpyxl reads it, cell by cell, as text
        v
automation/invoice_recorder.py
        |
        |  reads automation/selectors.json to learn WHICH box is WHICH
        |  reads .env for the Bottomline address and login
        v
Chromium browser (from .browsers/, opened by Playwright)
        |
        v
automation/queue_navigator.py
        |
        |  reads the whole "Images to be Indexed" queue ONCE, page by page,
        |  and builds a list of image name -> which page it is on
        |
        |  then, for each spreadsheet row:
        |     finds that image name, ticks the row, presses Index Selected
        |     PROVES the right invoice opened (two checks) before anything else
        v
back in invoice_recorder.py
        |
        |  PHASE A  select an integration package, then type the property.
        |           A property only appears in the dropdown if it belongs to
        |           that package -- so the dropdown IS the test. Not there?
        |           try the other package. Neither? skip the invoice.
        |           (the ordering rules live in automation/fill_plan.py)
        |  PHASE B  the vendor
        |  PHASE C  invoice number, invoice date, due date, amount
        |
        |  everything is typed one character at a time
        v
  STOPS. You review and press "Convert to Invoice" yourself, finish the
  second screen, press Save THERE, then press ENTER in the black window.
        |
        |  on ENTER, the script stamps DONE into that row's Status column in
        |  input/invoices.xlsx (a future run skips DONE rows). Pressing q does
        |  not stamp it. The Status cell stays hand-editable.
        |
        |  queue_navigator gets back to the queue: the menu item, then the
        |  queue's own remembered address, then the menu item again. If every
        |  route fails it asks YOU to click back -- it never ends the run.
        v
logs/run_YYYY-MM-DD_HHMM.txt  <- a record of every run
```

**Why the navigator is a separate file:** the parts that make decisions — is
this the same image name, which page is it on, did the right screen open — can
then be tested with no browser, no Bottomline and no spreadsheet. Run those
tests any time with `6 - Test The Navigator.bat`.

---

## The files that matter

| File | What it is |
|---|---|
| `automation/invoice_recorder.py` | The main script. Reads the sheet, fills the screen, stops. |
| `automation/queue_navigator.py` | **Finds invoices in the queue and opens them.** Also holds the two checks that prove the right invoice is on screen. Added 2026-08-13. |
| `automation/fill_plan.py` | **Which integration package an invoice belongs to, and the order the boxes are filled in.** Pure decisions, no browser. Added 2026-08-14. It never invents a package name — anything that is not YARDI or INTACCT is ignored rather than typed. |
| `automation/rehearse_fill.py` | Walks the real filling code through a **pretend** Bottomline so you can read what it will do before it does it live. Seven situations, including the two where an invoice is deliberately left alone. Double-click `7 - Rehearse The Filling.bat`. |
| `automation/selftest_queue.py` | Offline tests for both halves of the decision-making — the navigator and the fill plan. No browser, no Bottomline, no spreadsheet. |
| `automation/selector_recorder.py` | A one-off tool. Watches you index an invoice by hand and writes down what each box is called. You only run this if Bottomline changes its screen. |
| `automation/page_probe.py` | A one-off tool. **Look only** — opens a screen and lists every box with its real name. Use it when you need a box the recorder cannot see, because a recorder only captures what a human clicks. That is how the read-only Image Name box was finally confirmed. |
| `automation/selectors.json` | **The field map.** Which spreadsheet column goes into which Bottomline box. Hand-written and signed off, not auto-generated. |
| `automation/selectors_recorded.json` | Raw output of the recorder. Evidence, not configuration. |
| `automation/selectors_recorded.prev.json` | The previous raw capture, kept automatically so a re-record never destroys the old one. |
| `input/invoices.xlsx` | Your spreadsheet. Two tabs: `Invoices` and a "How to use" guide. |
| `logs/run_*.txt` | One file per run. Append-only. |
| `1`–`7 *.bat` | Double-click launchers so nobody has to use a command line. `5` lists the boxes on a screen; `6` runs the offline tests; `7` rehearses the filling against a fake screen. None of those three can change anything. |
| `.env` | Bottomline address, username, password. **Never opened by Claude.** |
| `automation/.bottomline_session.json` | A saved login, so you are not asked for a security code every run. **This is a credential.** |

---

## The Python libraries, and why each one is here

**`playwright`** — drives a real Chromium browser. Chosen over "screen scraping"
or sending data straight to a server because Bottomline has no documented way in;
the only supported interface is the screen a human uses. Playwright presses keys
the way a person does, so the page cannot tell the difference.

**`openpyxl`** — reads `.xlsx` files, and **since 2026-08-17 also writes to one**:
`mark_row_done()` stamps `DONE` into the Status column after a row is finished.
⚠️ **This re-introduces the green-triangle problem** — see the note in
`decisions.md`: every save strips the hand-written "number-stored-as-text"
suppression back out. The old "used read-only, so it's safe" guarantee no longer
holds. Handling this is an open item in `todos.md` (0e).

**`python-dotenv`** — loads `.env` so the password never appears in the code, in
the spreadsheet, or in a log.

**`unittest`** — comes with Python, nothing to install. Runs the offline tests in
`selftest_queue.py`. Deliberately not `pytest`: adding a dependency means another
install step on every PC, for a test suite that needs nothing special.

Everything installs into `.venv/` inside the project. The browser downloads into
`.browsers/` inside the project. **Deleting the `Invoice_Indexer` folder removes
every trace of this project from the PC** — nothing is installed system-wide.

---

## Three technical points worth understanding

### 1. Boxes are addressed by `name`, never by `id`

Bottomline is built on a framework called **ExtJS**. ExtJS invents an `id` for
every box fresh each time the page loads — `textfield-1752-inputEl`. Those are
useless as permanent addresses.

The `name` attributes (`Image_Index_Ref`, `Image_Index_Amount`) are written by
Bottomline's own developers and stay put. **The field map uses `name` throughout.
Never swap these back to the `#id` values from the raw capture.**

### 2. The script types; it does not paste

Vendor, Property and Integration Package are not text boxes. They are search
boxes that produce a dropdown, and the underlying code is only stored when you
**pick from that dropdown**.

A dropdown only appears in response to real keystrokes. Pasting a value sets the
text but fires no keystrokes — so no dropdown, no code stored, and the box would
**look filled while being empty underneath**. Every field is therefore typed at
45 milliseconds per character.

### 3. Text format in the spreadsheet is not cosmetic

The template makes every cell **Text** so that what you see is what gets typed.
If a column is reformatted to a number format, Excel hands the script `496` while
*displaying* `496.00`.

`cell_to_text()` handles this: text is used untouched; a number is typed with the
same decimals Excel is displaying; **a real date stops the run**, because guessing
a date format would put a wrong date on a client's invoice.

> ⚠️ The one thing that cannot be recovered: **leading zeros.** Invoice number
> `007458` stored as a number is already `7458` before the script sees it.

---

## The safety features

**The "right invoice" check — two reads, both must pass.** Before typing
anything, the script checks:

1. **The page heading** (`.top-page-header-text`) must read `Image Index - <name>`.
   This proves the *indexing screen* opened at all. It matters because the delete
   icon sits on the same toolbar as Index Selected.
2. **The Image Name box** must match the Image Name column in the spreadsheet row.
   This proves the *right invoice* opened.

Neither check catches what the other catches. Together they make it impossible to
record one vendor's invoice against another vendor's document — a failure that
would otherwise fill perfectly, error at nothing, and only surface at
reconciliation months later.

**If either fails:** nothing is typed. The script goes back to the queue and
tries once more, then skips that row and reports it at the end. It never fills
blind. *(The older behaviour — printing "safety check skipped" and filling
anyway — was deleted on 2026-08-13. A safety feature that silently switches
itself off is worse than not having one.)*

**The duplicate check.** If the same image name appears twice in the queue, the
run stops. The same document twice usually means something upstream went wrong,
and picking one at random is exactly the kind of silent choice this project
refuses to make.

**The integration package check.** Since 2026-08-14 the script does not take the
package from the spreadsheet on trust. It selects one, types the property, and
only proceeds if the property actually appears in that package's dropdown. If the
property appears under neither package, the invoice is left completely untouched
and reported at the end.

> ✅ **2026-08-14: this ran against Bottomline and filled a real invoice.** The
> queue was read, the right invoice opened and verified, the package confirmed,
> and all the boxes typed. 47 offline tests cover the decision-making.
>
> 🔴 **Still unproven:** no invoice has yet failed under the first package and
> succeeded under the second. Until that happens, the belief the package check
> rests on — that the property dropdown only shows properties belonging to the
> selected package — has not been demonstrated. See `todos.md` item 0b.

**The column guard.** `check_columns_match()` refuses to start if the field map
names a column the spreadsheet does not have. Without it the failure is silent —
a missing column and an empty cell look identical, so every invoice would save
with that value missing and nothing to notice. This is a real bug that happened
during development. **Never remove this guard.**

---

## What the script will never do

Press **Save**, **Convert to Invoice**, **Save as Exception**, or **Delete**.
Those four are listed in `selectors.json` under `never_click` specifically so
they can be avoided. The script fills and stops, by design.

---

## Planned — the "maker log" (a record of every indexed invoice)

> ⚠️ **Not built as code. Design settled 2026-08-31; being set up by hand in
> Google, not programmed.** An earlier version of this section described a local
> **Flask app + SQLite** — that was **DROPPED**. See `decisions.md` (2026-08-31,
> Session 12) for the full pivot and the reasoning.

**The need.** Every indexed invoice is logged — Timestamp, Email, Image Name,
Image Action (Approve / Delete), Invoice Number, Remark, Remark Detail, Image
Type. The team keeps this in a Google Form today and wants to carry on, with the
record downloadable as Excel.

**The shape (settled).** Keep it a **Google Form → Google Sheet**, filled **by
hand** at review time — one invoice, one pause, one entry. The Form is the single
safe writer: Google serialises every submission into the Sheet, so many people
submitting at once never lose a row. This is the "Picture C" safety the team
already relies on with their current form — **there is nothing to build for it.**
The Sheet is one **workbook with tabs** (Maker Log now; a Checker tab later).
**Excel is just File → Download → .xlsx**, produced on demand.

**What this deliberately is NOT.** No local app, no Flask, no SQLite, no Apps
Script, no server to host, and **no change to the recorder**. A pre-fill (the
script opening a ready-filled Form link to save typing) was considered and
dropped, because it would pop a browser tab mid-automation and steal focus from
the recorder. The recorder stays untouched.

**Setup approach.** Build and test on a **REPLICA** Form + Sheet first, never the
live pair (`REPLICA — Maker Log Form` + a new linked Sheet). The Checker step is
explicitly later; the workbook is only shaped to allow it.

**Separate, deferred idea:** moving `input/invoices.xlsx` (the recorder's INPUT
queue) into Google too. That is a much bigger job than the log — the recorder
reads every row and writes DONE back, so a cloud queue means the script must talk
to Google directly (Sheets API + credentials, a real rewrite of its read/write
layer). Not started; its own design + approval first. See `decisions.md`.
