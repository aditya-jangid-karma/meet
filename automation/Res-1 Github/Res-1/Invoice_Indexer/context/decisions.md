# Decisions — Invoice_Indexer

Why things are the way they are. Newest at the bottom.
**Read this before undoing anything that looks odd** — most of it looks odd for a reason.

---

## 2026-08-07 — Session 1

### Fill and stop. Never press Save.
The script types into the indexing screen and stops. A human reviews every box
and presses the buttons.
**Why:** these are live client invoices. A wrong value that saves itself is a
correction, a re-open, and an explanation. A wrong value sitting on screen is
just something you retype. The cost of the two is not comparable.

### The spreadsheet is the seam.
The script reads a spreadsheet rather than reading the PDFs directly.
**Why:** it keeps a human between the document and the client's system, and it
means a future AI extraction step (Phase 2) can fill the spreadsheet without any
change to the filling script.

---

## 2026-08-10 — Session 2

### Everything installs into the project, nothing globally.
`.venv/` for the libraries; `PLAYWRIGHT_BROWSERS_PATH` redirects the ~150 MB
browser download into `.browsers/`.
**Why:** Playwright normally puts the browser in a shared Windows cache outside
the project. Redirecting it means deleting the `Invoice_Indexer` folder removes
every trace of this project from the PC.

### Task 2 (the offline practice form) was cancelled.
**Why:** the user asked to record real selectors directly. Judged low risk —
the recorder only watches; it never types, clicks, submits or saves. The worst
outcome from a bug is "record it again," not damage.
**What it cost:** the practice form was going to prove the password-refusal works
*before* touching the real system. That proof happened *after* instead, by reading
the real capture file. Same evidence, one step later. ✅ Done, it held.

### CMD, not PowerShell.
All commands are handed over in CMD syntax.
**Why:** the user cannot use PowerShell. Note `set VAR=value` takes **no quotes**
in CMD — quotes become part of the value and break the path silently.

---

## 2026-08-10 — Session 3

### The recorder is armed in two phases.
Phase 1 the browser opens with **no listener loaded at all** — you log in
unwatched. Phase 2 you press ENTER and only then is the listener injected.
**Why:** filtering the login out afterwards is weaker than never seeing it. There
is nothing present to observe the login.
**The subtlety:** injecting on page-load alone would miss the already-open invoice
screen, so the recorder also walks every frame and injects directly. Without that
it would record nothing and simply look broken.

### The field map keys off `name`, never `id`.
**Why:** Bottomline runs on ExtJS, which generates ids like `textfield-1752-inputEl`
at page-build time. The `name` attributes are hand-authored and stable.
The recorder's own `suggest()` preferred `id` — exactly wrong for this site — and
was rewritten to prefer `name` and to reject any id with 3+ consecutive digits.

### Fields are typed, never pasted.
**Why:** `page.fill()` fires no keystrokes, so the ExtJS autocompletes never wake
up and no code is stored. The box looks filled and is empty underneath.

### Scope stops before "Convert to Invoice".
The workflow is two screens. The script only touches the first.
**Why:** confirmed with the user. It also made a `Property_Id` vs `property_id`
case-sensitivity risk moot, since the lowercase one lives on the second screen.

### GL account was dropped entirely.
**Why:** there is no GL account field on this screen. Confirmed 2026-08-10.

### The green-triangle suppression is hand-written XML.
Excel's "number stored as text" warning is suppressed by writing `<ignoredErrors>`
directly into `xl/worksheets/sheet1.xml`, between `<pageMargins>` and
`<legacyDrawing>`.
**Why:** the warning's "Convert to Number" button is the single action that
quietly destroys the design (`312.00` → `312`, dates → serial numbers).
**Why by hand:** openpyxl accepts the instruction and **silently discards it**.
This was only caught by unzipping the workbook and reading the raw XML.
> ⚠️ **Fragile.** Any openpyxl script that *saves* the workbook strips it out
> again. `invoice_recorder.py` only ever reads, so normal use is safe.

### A startup guard refuses to run on a column mismatch.
**Why:** a missing spreadsheet column looks exactly like an empty cell. A real bug
during development had the map saying `due_date` while the sheet said
"Invoice Due Date" — every invoice would have saved with no due date, no error,
and nothing to notice. **Never remove `check_columns_match()`.**

### Subagent output is re-verified, not trusted.
**Why:** the spreadsheet was built by a Sonnet subagent. All six of its claims
held when re-checked — but a seventh problem it had introduced (a "leave a row
blank" instruction that was impossible, because it had pre-filled all 500 Row IDs)
was only found by reading the output directly.

---

## 2026-08-13 — Session 5 (context system onboarding)

### The context files replace the handoff notes.
`context/` is now the source of truth. `handoffs/` is kept as history but is no
longer written to.
**Why:** the handoff notes were 200+ lines each and had to be re-read in full at
the start of every session. HOTcontext is capped at 50 lines and the allied files
are read only when a task actually needs them.

### `.x-boundlist-item` is promoted from "inferred" to "observed".
**Why:** the 2026-08-10 18:35 live run reported "2 matches" for Property and
"3 matches" for Integration Package. It could not have counted them if the
selector were wrong. `selectors.json` still describes it as an educated guess —
that comment is now out of date.

### The Image Name check was never broken — the script just never got to the page.
Three live runs logged "image name box not found on screen". The selector
`input[name="Image_Index_Name"]` is correct. That box only exists once an image
has been opened for indexing, and the script had no way to open one — it assumed
a human had already navigated there.
**Why this matters:** the fix is navigation, not a selector. Corrected 2026-08-13
after the user pointed it out; an earlier reading of the logs blamed the selector.

---

## 2026-08-13 — Session 5, self-navigation design

The script will find and open each invoice itself instead of relying on a human
to have one open. Decisions taken during design, before any code:

### The script navigates; the human still presses Convert.
Script opens the image, fills it, and waits. The operator reviews and presses
**Convert to Invoice**; the script sees the queue return and moves on.
**Why:** keeps the founding rule intact — the script never presses Convert, Save,
Save as Exception or Delete. It gains navigation, not authority.

### The spreadsheet leads; the queue follows.
Row order in the sheet drives the run. For each row the script finds that Image
Name in the queue.
**Why:** the user chose it — it keeps the operator in control of what gets done
and in what order. *Trade-off accepted:* the queue cannot be searched by image
name, so the script must read the grid itself.

### The queue is indexed once, up front, across every page.
Set **Records per page → 200**, then walk all pages and build one lookup of
image name → page.
**Why:** the queue runs ~210 rows over 9 pages at the default 25. Hunting page by
page *per invoice* would mean walking the grid once per row. One pass at 200 per
page means 2 pages total.
**This also satisfies the "check everywhere before skipping" rule** — a name is
only declared missing after every page has been read.

### A missing image name is skipped, not fatal.
Reported at the end of the run.
**Why:** one absent image should not strand a batch of forty.

### A duplicate image name stops the run and asks.
**Why:** the same document twice in an indexing queue usually means something
upstream went wrong. Guessing which one to take is exactly the kind of silent
choice this project refuses to make.

### The `Next` button on the indexing page is deliberately ignored.
The script returns to the queue and finds the next image by name instead.
**Why:** going back and re-finding by name is slower but self-verifying — the
script proves it is on the right invoice every time rather than trusting that
`Next` went where it expected. Revisit as a speed-up once V1 is trusted.

### ExtJS ids have a stable prefix and a volatile suffix.
`shared-button-process-1353` → target as `a[id^="shared-button-process-"]`.
**Why:** only the trailing number is generated. The `shared-button-*` prefix is
semantic and survives reloads. This gives a reliable handle for icon buttons that
have no visible text. **Does not apply to bare ids like `#button-1338`**, which
carry no meaning at all.

### 🔴 The delete icon sits on the same toolbar as Index Selected.
Both act on whatever rows are ticked.
**Why it is called out here:** a loose selector on that toolbar could bin a
client's invoice. Index Selected must be targeted exactly, delete goes in
`never_click`, and the script must confirm the indexing page actually opened
before doing anything else.

### Confirmed: the indexing screen is not in an iframe.
**Evidence, not assumption:** every field in `selectors_recorded.prev.json`
carries `"in_frame": false`, and the recorder injects into every frame and tags
which one each field came from.

### OPEN — what to do if the operator never presses Convert.
The user is deciding this themselves. Interim behaviour for V1: wait
indefinitely, with a way to quit. **Revisit before V2.**

### The recorder now captures clicks on ANY element.
It previously accepted only `input`, `select`, `textarea`, `button` and `a`.
**Why it had to change:** ExtJS draws grid rows and their tick boxes as plain
`<div>`s, so every click on the queue screen was being silently discarded. A
recording of the queue would have come back empty and looked like the recorder
was broken. Typing is still restricted to real form fields, which is what keeps
the password guard meaningful.

### Four new captured attributes: `class_list`, `tooltip`, `ancestors`, `id_stem`.
**Why:** the queue's controls have no `name` and no visible text. "Index Selected"
exists **only** in `data-qtip`, ExtJS's own tooltip attribute — every other
attribute we were capturing is blank for it. That is why identifying that button
took two rounds of screenshots.
**Deliberately NOT captured: the text of the containing grid row.** It would make
row-matching easier but would pull real vendor names and amounts into
`selectors_recorded.json`, which today holds no client data at all. Ancestors are
structure only — tags and classes, never text.

### The recorder warns when two elements share an id stem.
**Why:** in the run-1 capture, `Convert to Invoice` was
`shared-button-generictextbutton-1780` and `Save as Exception` was
`shared-button-generictextbutton-1778` — the same stem. A selector built on that
stem could press either, and one of them is on the never-click list. The stem
trick is useful but is not safe without a uniqueness check.

### `selectors_recorded.run1-15fields.json` is kept deliberately. Do not delete.
**Why:** the recorder rotates `.json` → `.prev.json` on every run, so the original
15-field capture — the evidence the entire field map was built from — was one
recording away from being overwritten. Copied and verified 2026-08-13.

### The 2026-08-13 queue recording — what it proved.
Captured 17:42, 25 entries, covering login → Image Management → page size → paging
→ tick a row → Index Selected → index the invoice → Convert to Invoice.

**Security check passed.** No password or OTP entry, no typed values anywhere, and
nothing from the login screen — the first entry is already past it. *(The one
`type="checkbox"` entry is "Filter by Header Property:" on the indexing form, not
a credential.)*

**The widened click capture was necessary and it worked.** The row tick box has
**no id at all** and is a `<div>` — the old input/button/link-only rule would have
dropped it silently and the whole recording would have been wasted.

**Targeting found — better than expected.** Bottomline has hand-authored classes
in places, which beat anything ExtJS generates:

| Control | Handle | Quality |
|---|---|---|
| Row tick box | `tr.x-grid-row` → `.x-grid-checkcolumn-cell-inner` | structural, good |
| **Index Selected** | `a.process-comp-btn` / `.process-btn` | **custom class, excellent** |
| Next / previous page | `.x-tbar-page-next` / `.x-tbar-page-prev` | ExtJS semantic, good |
| Page number box | `input[name="inputItem"]` | real name, good |
| "Images to be Indexed" | `a.x-menu-item-link` + its text | text-based, acceptable |

**One weak point: the Records-per-page dropdown.** Its `name` *is* its generated
id (`combo-1329-inputEl`), so there is no stable handle. It needs targeting by
position within the toolbar, or the 200-per-page step has to be dropped.

### 🔴 Convert to Invoice does NOT return to the queue.
The capture shows `Convert to Invoice` (entry 24) followed immediately by
`property_id` — the Property box on the **second** screen (entry 25).
**Why this matters:** the design assumed the script could wait for the queue to
reappear as its signal that the operator had finished. It cannot. Convert opens
the second screen, and the operator must complete and Save *there* before the
queue comes back. **The "advance to the next invoice" step has to be redesigned.**

### Vendor Code and Property Code are real, readable boxes.
`Image_Index_VendorSite_Id_Code` ("Vendor Code:") and `property_id_code`
("Property Code:") both appear on the indexing screen.
**Why this matters:** confirming that a dropdown pick actually stored its
underlying code was previously a to-do with no known way to do it. It is now
simply "read that box and check it is not empty."

### Still unverified: the Image Name box.
`Image_Index_Name` did **not** appear in the capture — it is read-only, so the
operator never clicked it and the recorder only sees what is used. The selector
in `selectors.json` remains inference. **Needs confirming another way.**

### Known gap in the recorder: dropdown items are still not captured.
`addressable()` recognises `x-grid-`, `x-btn`, `x-tab` and similar, but **not**
`x-boundlist-item`, so clicks on an open autocomplete list are discarded.
Low priority — the live run of 2026-08-10 already proved `.x-boundlist-item`
works — but worth knowing before anyone re-records to chase a dropdown problem.

### JS embedded in Python gets syntax-checked with a real engine.
`LISTENER_JS` is pulled out via the Python AST and parsed by `node --check`
(falling back to the project's own Chromium via `new Function`, which compiles
without executing).
**Why:** a Python syntax check passes happily over broken JavaScript inside a
string. The error would only appear in the browser, wasting a live recording run.
**Also:** hand-rolled bracket counting was tried first and gave a false failure —
it read the apostrophe in a comment ("grid row's checkbox") as an opening quote.
Use a real parser.

---

## 2026-08-13 — Session 6, spec signed off and V1 built

Spec: `docs/specs/2026-08-13_self-navigation-design.md`.
Build plan: `docs/plans/2026-08-13_self-navigation-build.md`.

### A read-only probe was built to see boxes nobody clicks.
`automation/page_probe.py` opens a screen and lists every box with its real
`name`. It types nothing, clicks nothing, saves nothing.
**Why it was needed:** a *recorder* only sees what a human uses. `Image_Index_Name`
is read-only, so it never appeared in any capture and its selector stayed a
guess — and it is the box the whole safety check depends on.
**Result: all 8 selectors in the field map confirmed against the live screen.**
Nothing in the map is inference any more.
**It masks values on purpose** — prints a character count and the first 8
characters only, so vendor names and amounts never reach a log file. Password
boxes are skipped entirely.

### 🔴 The image name is NOT a GUID. The format varies.
Observed live: `skm_c250i26080508080` (a scanner filename), one starting
`washingt…`, and `202608125042_42968745` from the user's own sheet.
**Why this matters more than it looks:** the Image Name column is not just
checked — **it is how the script finds the invoice in the queue.** A wrong
format means zero matches and every row silently skipped. The README still
tells the user it is a GUID. **Not yet fixed — Task 5.**

### The page header is a second, independent identity check.
`.top-page-header-text` reads `Image Index - <name>`.
**Why two checks:** the header proves *which screen* is open, the Image Name box
proves *which invoice*. Neither catches both. This also satisfies the standing
requirement to confirm the indexing page actually opened before doing anything —
the delete icon shares a toolbar with Index Selected.
**Use `top-page-header-text` only.** The other two classes on that element are
generic ExtJS and match other screens' headings.

### "Copy selector" in Chrome is the wrong tool for this site.
It returns the generated id (`#textfield-1735-bodyEl`) — and `-bodyEl` is the
wrapper, not the input, so it has no value to read.
**Use Copy *element* instead**, which shows the real `class` and `name`.

### Safety check failure = retry twice, then skip. Never fill blind.
Decided by the user, replacing Claude's "stop the run" recommendation.
**Why retry:** the likeliest cause of a mismatch is mechanical — ExtJS redrew the
queue and the tick landed on a neighbouring row. Worth one more attempt.
**Why a cap:** without one, a genuinely mis-named image loops forever unattended.
**Why skip rather than stop:** consistent with the missing-image rule. Nothing
was typed, nothing is half-done, and one bad row should not strand forty.
**The old behaviour is deleted** — it printed "safety check skipped" and filled
anyway. A safety feature that silently switches itself off is worse than none.

### Name matching ignores case, spacing and a trailing ".pdf".
Applied to **both** sides of every comparison, so the two can never be
normalised differently.
**Why case is safe to ignore:** Excel and operators are inconsistent about it,
and two images in one queue differing only by case is implausible. If it ever
happened, the duplicate check stops the run rather than guessing.

### Paging is verified, not assumed.
After clicking Next, the script reads the page-number box and stops if it is not
the page it asked for.
**Why:** reading page 1 twice would declare a genuinely present invoice missing.
**Also:** ExtJS greys the Next button out with the class `x-item-disabled`, not
the HTML `disabled` attribute — `is_enabled()` alone reports it as clickable and
the script would page forever.

### 🔴 Unverified: which grid column holds the image name.
The recording never captured it. The code takes the **first cell in the row that
contains any text**, which skips the tick-box column.
**Guard:** the run prints `First names seen: [...]` on page 1 so the operator can
see immediately whether the wrong column is being read.

### `load_selectors()` filters the map — a bug caught before it ran live.
It returns only four keys, so the new `queue` and `page_header` selectors would
have been silently dropped and the navigator would have failed with a `KeyError`
mid-run, on screen, during a live session. Both are now passed through, and the
script refuses to start if the `queue` block is missing.

### The 200-per-page step was dropped.
**Why:** the records-per-page dropdown's only handle is its own generated id, and
it sits on the same toolbar as the delete icon. It saves seconds once per run.
Paging at 25 costs ~9 page loads instead of 2 and uses selectors that are solid.

### Offline tests use `unittest`, not pytest.
**Why:** pytest is not in the venv, and adding a dependency means another install
step for a non-engineer. `unittest` ships with Python. Run via
`6 - Test The Navigator.bat`, which opens no browser and reads no spreadsheet.

---

## 2026-08-14 — Session 7, first live fill, and two root causes

### 🔴 `.x-boundlist-item` had to become `.x-boundlist-item:visible`.
**This is the most important entry on this page.**

ExtJS does not destroy a dropdown when it closes — it leaves the whole list in
the page, hidden. So the bare selector matched items from **every** combo box on
the screen, open or closed.

**Evidence (`logs/run_2026-08-14_1631.txt`):** while reading the *Property*
dropdown, the script resolved to a leftover from the *Integration Package* box —
`<li data-boundview="customcombo-1736-picker" class="x-boundlist-item
x-boundlist-selected">YARDI</li>` — and spent 30 seconds trying to click
something invisible before throwing.

**Two consequences, and the second is the dangerous one:**
1. clicks time out on hidden leftovers;
2. **the match COUNT was wrong.** That Property dropdown had no real match, but
   the stale `YARDI` item made the count 1 — which the new package check reads as
   *"confirmed"*. The only thing that stopped a wrong integration package being
   recorded is that clicking an invisible element happens to fail.

**This also overturns the 2026-08-13 entry above** which promoted the selector
from "inferred" to "observed" on the grounds that it "could not have counted
matches if it were wrong". It *was* counting — it was counting the wrong things
as well. A count is not evidence unless you can see what was counted, which is
why the log now prints the item *names* alongside the number.

`queue.menu_item` carries `:visible` for the same reason: an ExtJS menu stays in
the page while hidden, so the "Images to be Indexed" item was found, waited on
for 30 seconds, and then threw.

### Waiting is on a condition, never a duration.
`read_queue()` used to sleep a flat 1.5s after clicking Next and then look at the
page-number box **once**. It won fifteen times and lost on the sixteenth,
stopping a run at "expected page 17, got 16" on a queue that genuinely had 17
pages. It now polls until the page number actually changes, 15-second ceiling.
**Why it matters beyond the bug:** a fixed sleep is a gamble dressed up as a
check. `go_to_queue_page()` still has one — see `todos.md`.

### Getting back to the queue is a ladder, and can never end the run.
Menu item → the queue's own remembered URL (captured once, after the first
successful read) → menu item again, verifying arrival after each rung.
**Why:** Convert to Invoice opens a second screen where the menu item is not
reliably reachable, and one failed click used to `sys.exit()` a run with invoices
still to do. If every rung fails the operator is asked to click back by hand;
only a deliberate `q` stops the run.
**Note the ordering with the entry above:** the ladder is a safety net, not the
fix. The fix was `:visible`.

### The integration package is decided FIRST, and the property dropdown proves it.
Old order: fill everything, taking the package straight from the spreadsheet.
New order: select a package → type the property → **a property only appears in
the dropdown if it belongs to the package on screen**, so that dropdown is the
test. Property found → package confirmed. Not found → try the other package.
Then the vendor, then invoice number / date / due date / amount.
**Why:** decided by the user 2026-08-14. It replaces the operator's reference
sheet with something the script can demonstrate.
**What it costs:** the script now makes an accounting classification it did not
make before. Absence from a dropdown is weaker evidence than it looks — a
spelling difference looks identical to "wrong package" — which is why every
attempt is logged with the names it saw.

### Only YARDI and INTACCT exist, and nothing else is ever typed.
The sheet's own value is tried first; the other follows. A blank cell falls back
to YARDI then INTACCT. **An unrecognised value (a typo, a retired package) is
ignored, never passed through to Bottomline.**

### A blank Property column skips the invoice.
**Why:** the property dropdown is the only proof of the package. Without one
there is nothing to prove it with, and selecting a package on the spreadsheet's
word alone is exactly the unproven guess this design removed.

### A vendor that does not match never re-opens the package decision.
The property decides the package. If the vendor then fails, the operator picks by
hand (or types `s`).
**Why:** a vendor spelled differently in the sheet is a known, already-observed
failure (Steps Appliance Repair LLC, 2026-08-10). Letting that flip the package
would quietly route an invoice into the other accounting system.

### The filling order lives in code, not in `selectors.json`'s key order.
**Why:** the old loop walked the field map in whatever order the keys happened to
sit in the file — fragile, and it cannot express "package first, then test, then
the rest". `fill_plan.py` now states the order explicitly. A column added to the
map but not to `fill_plan.py` is still filled, on the end, rather than dropped.

### A rehearsal harness was built: `automation/rehearse_fill.py`.
Drives the **real** filling code against a fake screen — no browser, no
Bottomline, no spreadsheet — through seven situations including both skips.
**Why:** the first time anyone sees a new decision about a client's books being
made should not be on a live screen with a real invoice open.
**Its limit, stated plainly:** the fake answers the way we *believe* Bottomline
answers. It proves the script's reasoning, never Bottomline's behaviour.

### The image name format VARIES. Neither "it is a GUID" nor "it is not" is right.
FTP-imported documents carry GUIDs (`6e1f92f5-2ee3-4c1f-b09a-0541b564e7d2`);
scanner documents carry names like `skm_c250i26080508080`. Both were observed on
the live queue. The 2026-08-13 entry above says "NOT a GUID" — too strong.
**What the docs should say:** copy it exactly out of the queue.

### The queue's row order is not stable between reads.
Two runs minutes apart returned different rows in positions 2 and 3. Every
invoice shares the same Scanned Date, so tied rows come back in whatever order
the server likes. **Why it matters:** the script records "this invoice is on page
7" during the read and jumps back there later. A reshuffle means a spurious skip
— safe, never wrong data, but it will look like a missing invoice.

---

## 2026-08-14 — Session 8, evening. Debugging only; no code changed.

### The project moved, and is now inside a git repo.
`Desktop\Res1\` → `Desktop\TeamD-Git\Res-1-\Invoice_Indexer`. The repo root holds
both `Invoice_Indexer` and `PDF Spliter`.
**The standing rule is unchanged and was re-confirmed by the user on the day:
Claude must not run or suggest ANY git command.** Classification advice — what is
safe to commit, what must be handed over another way — is still wanted.
**What this invalidates:** the "No git, local-only by decision" line in
`context.md` and the header of both `.gitignore` files. Corrected in `context.md`.

### Client data is not yet excluded from the repo. — FILE GAPS CLOSED 2026-08-19
Secrets *are* covered (`.env`, `*session*.json`, `logs/`, `.venv/`, `.browsers/`).
Three things are **not**, and all three are client data:
`input/*.xlsx` (the root rule only blocks `**/input/*.pdf`), `notes/*.png`, and
`automation/selectors_recorded.run1-15fields.json`, which carries the live tenant
hostname. Text-level leaks also survive into committed files — a real vendor name
in `selectors.json` and in four docs, and the hostname in `context.md`.

**RESOLVED IN PART, 2026-08-19.** All three file-level gaps are now closed in
`Invoice_Indexer/.gitignore`:
- `automation/selectors_recorded*.json` — one wildcard replaces the old two-line
  pair, so the `run1-15fields` capture is covered. It STAYS ON DISK; ignoring is
  not deleting, and the "do not delete" rule is unchanged. `selectors.json` (the
  hand-built map) is deliberately NOT ignored.
- `input/*.xlsx` — closed at project level. **The root `Res-1-/.gitignore` still
  only blocks `**/input/*.pdf`**, so any sibling project has the same gap.
- `notes/**/*.png` — the double star is deliberate: the 2026-08-19 cleanup moved
  the screenshots into `notes/screenshots/`, which a single star would miss.

**STILL OPEN — the text-level leaks.** No `.gitignore` pattern can touch text
sitting INSIDE tracked files. The vendor name in `selectors.json` and the four
docs, and the hostname in `context.md`, are all still there. Closing the file
gaps did NOT close these. They need editing out by hand.

**Also corrected 2026-08-19:** the "LOCAL-ONLY, no git repository" headers in
both `Res-1-/.gitignore` and `Invoice_Indexer/.gitignore` — invalidated by the
entry above, and left stale until now. Both now state that the repository exists
and that these rules are live.

### 🔴 A reported bug was not a bug — and the reason matters more than the bug.
The fault reported was "it cannot reload itself to the URL and exits".
`logs/run_2026-08-14_1657.txt` shows the opposite: the menu rung failed, **the URL
rung succeeded**, and the run then ended normally because it had one row to do.
**Why it was misread:** `return_to_queue()` is handed the file-only logger, so
every message it produces lands in `logs/` and none of it reaches the operator.
From the console, a healthy fallback and a crash look identical.
**The general lesson, worth more than the fix:** a subsystem built specifically to
*recover* from failure must report what it did, out loud, at the time. A recovery
nobody can see gets diagnosed as the failure it just prevented. See `todos.md` 0c.

### A count is not evidence — restated, and this time it went the right way.
The 16:57 log line `property 'Mills Place' under INTACCT: 1 match(es)
['Mills Place']` is the first live proof the `:visible` fix holds: the count is 1
*and* the thing counted is visibly a property. This is exactly the check the
2026-08-14 entry above asked for, and it only exists because that entry changed
the log to print names alongside numbers. Keep doing that.

---

## 2026-08-17 — Session 9, console fix + Status column

### The logger now prints to the console as well as the file.
`note` was `lambda text: log_line(log_path, text)` — file-only. It is now a small
function that does `print(text)` **and** `log_line(...)`.
**Why:** `return_to_queue()` is handed `note`, so every recovery message it
produced landed only in `logs/` and the operator saw nothing. A healthy fallback
therefore looked identical to a crash — the exact cause of the 2026-08-14 false
bug report (see the Session 8 entry above, and `todos.md` 0c). `log_line` itself
was left alone, so the places that deliberately log-only-then-print separately
(the login block) do not double-print.

### A Status column (PENDING/DONE) drives what gets recorded.
`input/invoices.xlsx` now has a `Status` column. **DONE = skip that row; blank or
PENDING = record it.** Blank is treated as PENDING so older sheets without the
column keep working. `status` was added to `IGNORED_COLUMNS` so it is read but
never typed into Bottomline (same treatment as `notes`).
**Why the operator, not just the script, can set it:** the value is plain text and
hand-editable — set a DONE row back to blank/PENDING to make it record again.

### DONE is written back automatically, but only after the operator confirms.
`mark_row_done()` writes `DONE` into the row's Status column when the operator
presses ENTER at the "Done?" prompt — i.e. after they have reviewed and pressed
Convert. Pressing `q` deliberately does **not** mark it.
**Why ENTER, not the moment boxes are typed:** typing is not completion — the human
still converts and saves on the second screen. ENTER is the first point we know the
invoice was actually finished. **Why not `q`:** a run stopped there is safer left
un-marked, so the next run sees the row again. If the column does not exist yet it
is created with the header `Status`, so the sheet stays usable.
**Proven live 2026-08-17:** one run filled 6 invoices and stamped all 6 DONE. This
also closed the long-standing "only ever one invoice per run" doubt.

### 🔴 REGRESSION this created: the recorder now SAVES the workbook.
The Session 3 green-triangle entry above says the "number-stored-as-text"
suppression is hand-written XML that **openpyxl silently discards on save**, and
concluded "*`invoice_recorder.py` only ever reads, so normal use is safe.*"
**That is no longer true.** `mark_row_done()` calls `workbook.save()`, so every
successful row now strips the `<ignoredErrors>` block back out. The green ⚠️
triangles return, and Excel's "Convert to Number" button — the one action that
turns `007458` into `7458` and dates into serial numbers — is offered to the
operator again.
**Not yet resolved.** Options for next session: re-inject the XML after each save,
save once at the end instead of per-row, or accept the cosmetic warning and rely
on operator discipline. Flagged in `HOTcontext.md` and `todos.md`.

---

## 2026-08-19 — Session 10, auto-navigation + status-driven runs

### The script navigates to the queue itself after login.
The old flow paused after login and asked the operator to click to "Images to be
Indexed" by hand. Now, once the operator confirms they are logged in, the script
opens the queue itself and only asks if that fails.
**Why:** removes a manual step the script already had every piece to do — it
reuses the exact `return_to_queue()` menu click it uses mid-run.
**How it degrades:** if it cannot reach a loaded queue it falls back to the old
manual prompt. A missed click never blocks a run and nothing is typed off a
screen that failed the check.

### The "Images to be Indexed" item lives inside a menu that must be OPENED first.
Live proof 2026-08-18 19:11: `a.x-menu-item-link:visible` found 0 matches right
after login — the item is hidden until its parent toolbar button is opened.
`selectors.json` gained `menu_opener` (`.x-btn-inner`) + `menu_opener_text`
("Image Management"). `_reveal_menu()` **hovers** the opener first (opens a
hover-menu, harmless to a click-menu) and only **clicks** it if hovering did not
reveal the item — clicking a hover-menu's own button can toggle it shut.
**Selected by visible text, never the id** (`hoverButton-1054-…` regenerates every
load). This helps mid-run returns too, not just login.

### Landing on the queue FRAME is not the same as the rows being loaded.
Live proof 2026-08-18 19:11: auto-nav reached the queue, read it immediately, got
**0 rows**, and declared all 18 invoices "not in the queue" — a clean-looking run
that recorded nothing. The paging toolbar and page box render before the grid's
rows arrive over the network.
**Fix:** `wait_for_queue_rows()` waits for at least one real grid row before the
read is trusted. And if the queue still reads as 0 invoices, the run **STOPS
loudly** instead of skipping everything and reporting success.
**The lesson (again):** a check that passes on the frame, not the data, is a
gamble dressed as a check — same shape as the flat-sleep bug in Session 7.

### The Status column is the only thing that decides what records — not a row number.
`--start-row` counted DATA rows (header not counted), so `--start-row 8` started
at Excel line 9 and silently jumped Excel line 8 (observed 2026-08-18). Normal
runs now take **no flag**: DONE rows skip, everything else records, and the script
prints its plan up front ("N to record, M DONE" + the exact Excel lines).
`--start-row` is kept only as an advanced override, with honest help text.
**Trap to remember:** the operator's "row 7" is one behind the script's "Row 7"
because of the header — a live source of confusion, now stated in the help.

### The per-invoice "fill? [y/s/q]" prompt was removed.
Decided by the user: once the image-name check (`confirm_right_invoice`: the open
PDF's Image Name must equal the spreadsheet's, on both the heading and the Image
Name box) has passed, the open document IS this row's invoice — there is nothing
left for a human to decide, so the script fills it.
**Review is not lost:** the operator still reviews everything at the "Done?" prompt
before pressing Convert/Save, and that is also where they stop a run now.

### 🔴 OPEN BUG — the Property box may not clear between package attempts.
Live 2026-08-18 19:20: two invoices with property "Heather Hill" got **0 dropdown
matches under BOTH INTACCT and YARDI** and were skipped — yet the SAME "Heather
Hill" matched "Heather Hills" earlier in the very same run. The user observed the
previous value still sitting in the Property box when the script switched package.
**Lead theory (the user's, and it is plausible):** `clear_box()` /
`establish_package()` in `invoice_recorder.py` is not truly emptying the Property
field before the next probe, so the stale text produces 0 matches.
**Claude was wrong to call this "just timing / no bug" — it is an open
investigation.** Next session: reproduce with those two invoices, watch whether
the box actually empties, fix the clear.

---

## 2026-08-24 — Session 11, Qwen extracts Property (raw), for a human to confirm

### The READER now fills Property — but with RAW text, not a canonical name.
Reverses the earlier "Property blank by design (D9)". Qwen's schema and prompt
(`reader_qwen.py`) gained a nullable `property` field; `invoice_reader.py` writes
it into the Property column. The prompt rule: property = the property/location
being billed, exactly as printed; **if both a Bill-To and a Ship-To appear, take
the Ship-To**; it may sit in the line-item description; `null` if none shown; never
invented. `_parse` defaults it to `None`, so an older reply without the field is
still valid.
**Why now:** the user asked for property extraction. **Why RAW, not matched:**
there is **no property reference list** to map an address to a canonical Bottomline
property. Rather than have Qwen guess a name the recorder then fails to match, it
writes what it actually saw and a human confirms it. This is a *capture-for-review*
aid, not clean auto-fill.
**How it ties to the recorder:** the 2026-08-14 rule "a blank Property column skips
the invoice" is unchanged — the property dropdown is still the package proof. So a
raw value that does not match a real property will (correctly) be skipped by the
recorder until a human fixes it.
**Tests:** two offline cases added (`selftest_reader.py`) — schema marks `property`
optional, and a present value is written raw. Suite now 19, all green.

### Deferred: a property reference list, and a "Qwen Status" column.
A real address→property lookup (like the vendor matcher) is the only way to turn
raw text into a canonical name automatically — parked until such a list exists.
Also logged in `todos.md`: add a `Qwen Status` column the reader stamps
(READ_OK / NEEDS_REVIEW / PROPERTY_GUESSED) so operators see which auto-filled rows
were uncertain; it must join `IGNORED_COLUMNS` so it is never typed into Bottomline.
Neither is built — both need design + approval first.

---

## 2026-08-31 — Session 12, maker-log design PIVOT (no code)

### The maker log is a Google Form + Sheet, filled by hand — NOT a local app.
An earlier design in this project (`docs/specs/2026-08-31_maker-log-design.md` and
its build plan) had a local **Flask app + SQLite**, with the recorder POSTing
pre-filled drafts. **All of that is dropped.**
**Why:** the whole point of that app was to be the "single writer" that makes
concurrent logging safe — but a **Google Form already IS that**. Google's server
serialises every submission into the responses Sheet (exactly the "Picture C" the
old spec chose), and the team already fills such a form today. The safe-concurrency
problem the app existed to solve was already solved by a tool they own.
**The agreed shape:** keep filling a Google Form **by hand** at review time — one
invoice, one pause, one entry (no bulk queue of drafts to confirm later; the
recorder pauses on each invoice and the human logs it right then). The Form writes
to a Google Sheet **workbook** (Maker Log tab now; a Checker tab later). Excel =
**File → Download → .xlsx** on demand. **No Flask, no SQLite, no Apps Script, no
server, and no recorder change** for v1.
**Pre-fill considered and dropped:** the script could open a pre-filled Form link
to save typing, but that pops a browser tab mid-automation (steals focus from the
recorder), so the user chose fully-by-hand. The recorder is therefore left
completely untouched by the maker log.
**Checker step:** explicitly LATER — the workbook is shaped so a Checker tab can be
added, but it is not built now.

### Build against a REPLICA Form + Sheet, never the live one.
The team's live Form/Sheet is in daily use. All setup and testing happens on a copy
(`REPLICA — Maker Log Form` + a new linked Sheet); the live pair is untouched until
the replica is proven. The linked form could not be reached from the sheet the user
had open (no `Form` menu), so the replica is being built fresh with the same
questions: Image Name (short), Image Action (Approve/Delete), Invoice Number
(short), Remark (short, optional), Remark Detail (paragraph, optional), Image Type
(`Intacct - Expense` / `Yardi - Expense`); "Collect email addresses" ON supplies the
Email column, Timestamp is automatic.
**Status:** replica half-built — shell + "collect email" done; the 6 questions, the
Sheet link, and a test submission still to do.

### Deferred (its own project): moving `input/invoices.xlsx` itself to Google.
The user asked to also turn the recorder's INPUT queue into a Google Sheet. Flagged
as a separate, bigger effort — unlike the human-typed log, the recorder **reads
every row and writes DONE back**, so a cloud sheet means the script must talk to
Google (Sheets API + credentials, a real rewrite of its read/write layer, plus rate
limits/latency). Not started; needs its own design + approval, and the "why"
(collaborative queue editing vs. live viewing vs. both) pinned down first. This
supersedes the older parked "OneDrive move" question, which was the same concern in
a different form.

---

## 2026-09-01 — Session 13, launchers consolidated + masters design + recorder bug root-caused

### 8 operator bats → 2 (`Read Invoices.bat`, `Record Invoices.bat`).
The folder used to show 8 numbered `.bat` launchers. They are now **2**, each a
small menu. `Read Invoices.bat` = read for real / preview (dry-run) / test the
reader. `Record Invoices.bat` = dry-run / fill / resume-from-row / rehearse /
test-navigator / show-fields / re-record-fields. Old `1`–`8` were **deleted**;
every function was folded into the two menus (the Python scripts underneath are
untouched).
**Why:** the operator (a non-engineer) only ever needs "read" and "record"; the
tests and diagnostics are still there but no longer clutter the folder.
**New capability found in the process:** there was **no** reader launcher before
— the reader only ran as a hand-typed command. `Read Invoices.bat` fills that gap.
**Reader settings:** the Poppler path is one editable `set "POPPLER=..."` line
(fixed install); the Mac's Ollama address is **prompted each run** (`set /p`), so
no device IP is baked into the file — the `192.168.1.42` in the hint text is only
an example.

### Duplicate detection is by PDF FILE NAME, not invoice data.
Confirmed by reading `existing_image_names()` / the read loop in
`invoice_reader.py`: a PDF is "already done" iff its **file name (stem)** is in the
sheet's **Image Name** column. Editing the invoice number / vendor / amount in
Excel does NOT make a PDF look new again; only the file name matters.
**The four ways this breaks (told to the user):** renaming a done PDF → re-read
(duplicate row); two different invoices sharing a file name → the second wrongly
skipped; blanking the Image Name cell → PDF re-read; a missing/renamed Image Name
column → every PDF treated as new.

### Masters verification design — APPROVED in chat, spec written (no code).
Spec: `docs/specs/2026-09-01_vendor-master-verification-design.md`. Gives the
reader a real **vendor master** (names + addresses; the user has one; no codes)
and teaches it to match against it, moving non-exact reads to **review** rather
than auto-filling. Key decisions:
- **D1 file-first, no webapp yet.** Masters live as plain files the script reads
  offline; a local SQLite + webapp is designed *toward* but built only if
  hand-editing becomes the bottleneck. Considered and parked: SQLite-only, and a
  Google-Sheet master (rejected for v1 — puts client vendor data on Google).
- **D2 learn the matcher, not the model.** Corrections go into an **alias file**
  (`what Qwen wrote → correct vendor`) the lookup consults — the local Qwen is
  **never retrained** (retraining = heavy ML, non-deterministic, unauditable; an
  alias file is a plain, auditable CSV that *always* applies next time).
- **D3 corrections captured in the spreadsheet** (fix the Vendor cell; a step
  diffs it against a new `Qwen Vendor (raw)` helper column and records the alias).
- **D4 non-exact = review, never auto-fill.** **D5 new vendors added to the master
  only with a human OK.** **D6 one source-agnostic lookup module** (vendors now,
  properties later). **D7 vendors first (v1).**
- **D8 prompt-nudge IN v1**, fed from the alias file: a few recorded misreads are
  injected into Qwen's prompt as examples so the model improves at the source — a
  *nudge* on top of the guaranteed alias fix, capped so the prompt never bloats.
Two ignored helper columns added to invoices.xlsx: `Qwen Vendor (raw)` and
`Qwen Status` (both join `IGNORED_COLUMNS`, like `Status`).

### 🔴 The recorder dropdown bugs are ONE timing flaw — root-caused, fix NOT applied.
Investigated `fill_autocomplete()` / `probe_dropdown()` / `type_into()` /
`clear_box()`. The suggestion list is read at a **single instant** right after
typing: `items.first.wait_for(visible)` can pass on **leftover items from a
previous dropdown** (the same stale-item trap as the 2026-08-14 `:visible` fix),
and `items.count()` runs **before ExtJS's debounced query has re-rendered**. That
one flaw explains BOTH reported symptoms — bug 0f ("Heather Hill" 0 matches on
some rows but matches on others = a timing race) and "the script types the full
name and doesn't pause for the suggestions to load". Separately, `clear_box()`
empties with `fill("")` (no keystrokes), so ExtJS may not reset its previous
search between package attempts — the "old value stays in the Property box" the
user saw.
**Fix designed, not written (user moved to session-end before approving):** a
settle-wait helper that lets the query fire then polls until the list stops
changing (replacing the single-instant read in both functions), plus a
keystroke-based clear in `clear_box()`, plus a `press()` method on `FakeBox` in
`rehearse_fill.py` so the offline harness still runs.
**Honesty note:** this is a live-DOM timing bug. It is **unverifiable offline**
(the rehearsal uses a deterministic fake screen); only a live recorder run proves
the cure. Next session: get OK, apply, run offline regression tests, then the USER
re-tests live. Do NOT mark 0f fixed until that live run confirms it.

---

## 2026-09-01 — Session 14, recorder fix APPLIED + masters paused for a 2nd Qwen setup

### The Session-13 dropdown fix is now in the code (not just designed).
Applied to `invoice_recorder.py`, with `rehearse_fill.py` updated to match. Four
changes, all serving the one root cause (a suggestion list read at a single
instant / a clear that fires no keystrokes):
- **Settle-wait** (`wait_for_dropdown_to_settle`, guarded by `_dropdown_signature`)
  polls the ExtJS list until its contents are identical across consecutive reads
  before the count is trusted — replacing the single-instant `items.count()`. An
  empty list keeps polling to the deadline; polls are counted, not wall-clock.
- **Keystroke clear** — `clear_box()` and the new `retype_full_then_clear()` empty
  a box with `Control+a` then `Delete` (real keystrokes), not `fill("")`, so ExtJS
  actually resets its debounced search. `fill("")` looked empty but left the old
  query filtering — the "stale property between packages" the user saw.
- **Retype-full-then-clear between packages** — before re-probing the property
  under the other package, the script types the **whole** property name end-to-end
  and then keystroke-clears it. The user asked for this specifically: typing the
  full value first makes the next typed attempt behave, where a bare clear did not.
- **Staged prefix typing** (`type_and_settle_staged`, stages 60→75→100%) — type
  ~60% of the name and settle; **escalate to 75% then 100% ONLY when nothing loads
  (0 items)**; on >1 matches, hand to the operator as usual WITHOUT escalating; on
  exactly 1, take it. Property is typed slower (`PROPERTY_TYPING_DELAY_MS = 100`)
  so suggestions have time to appear. **This is the user's spec, chosen over a more
  complex "prefix-load then find-exact-in-list" design Claude first proposed.**
**Why the double "cleared the property box" narration is left as-is:** the user
said to leave it — it is cosmetic (two clear calls log twice), not a bug.
**Offline verified, logic intact:** `rehearse_fill.py` = 5 FILLED / 2 SKIPPED
(unchanged outcomes), `selftest_queue.py` = 47/47 — on both the fix run and the
staged-typing run. **Still UNVERIFIABLE offline** (deterministic fake screen).
**Bug 0f (todos) stays OPEN** until the USER live-runs the two "Heather Hill"
invoices. The user will start that run themselves — Claude does not.

### `rehearse_fill.py` had to change so the fake screen survives the new typing.
`FakeBox.press()` now treats `Delete`/`Backspace` as an empty-the-box (Control+a is
a no-op), and `FakeScreen.type_text` now **appends** rather than replaces — because
staged typing sends incremental chunks (`"Gateway S"` then `"tat"` then `"ion"`).
`type_into` still clears via `fill("")` first, so full-value types still land whole.
**Why it matters:** without the append, the harness would mis-narrate staged typing
and the offline regression would be meaningless. Verified: the narration shows the
chunks and the escalation correctly.

### Masters build is PAUSED until the team picks ONE Qwen setup.
The project may be shared with another user whose Qwen setup **involves no Mac at
all**, while the current reader calls Ollama on a Mac over the LAN (`--host
http://<mac>:11434`, model `qwen2.5vl:7b`, endpoint `/api/generate`, Poppler-
rasterised images, strict JSON schema). Before the masters lookup is wired into a
reader path, the two setups must be reconciled.
**Action taken:** a copy-paste **prompt was drafted (in chat, not saved to a file)**
for the other user's Claude to report its setup — model/tag, runtime (Ollama vs
LM Studio vs cloud), host/port/endpoint, image pipeline, hardware, speed, launch
command, and portability — masking any secrets/IPs. Once that report comes back,
compare and choose, THEN build the masters.
**Why pause rather than build anyway:** the masters lookup is source-agnostic and
reader-independent by design, but the *prompt-nudge* (D8) edits Qwen's prompt in
`reader_qwen.py`; standing that up against a reader path the team is about to
replace would be wasted, re-done work.

---

## 2026-09-02 — Session 15, ONE Qwen setup decided + first live read + timing

### The two Qwen setups are reconciled into ONE: a single host.
The Session-14 pause ("pick ONE Qwen setup") is resolved. The other user's report
showed the SAME model (`qwen2.5vl:7b`) and identical reading settings — the only
real fork was WHERE Ollama runs. Decision, written up in
`docs/2026-09-02_qwen-single-host-setup.md`: **Mac runs Qwen ONLY** (the model
lives in one place, the GPU does the inference); **the Server runs the reader
script AND holds `invoices\` + `invoices.xlsx`** on its own local disk; the two
are linked by the reader's existing `--host http://<MAC-ADDRESS>:11434`.
**Why files on the server, not the Mac:** the script reads/writes the Excel on its
own local disk — no network hop — avoiding the mapped-drive "save silently didn't
happen" clobber. **Why the model on one machine:** every other PC installs nothing
AI-related; a new user just gets the script + the address. **Trade-off accepted:**
a run now needs BOTH the server and the Mac up, and Ollama must listen on
`OLLAMA_HOST=0.0.0.0:11434` (default localhost-only = "connection refused" from
across the LAN). Three placeholders remain before it is do-it-yourself: the Mac's
fixed IP/hostname, the server share path, and confirming Python+Poppler on the
server. **The host is a role, not a machine** — moving Qwen later is `install
Ollama → pull the model → set OLLAMA_HOST=0.0.0.0`, then change the one `--host`.

### First LIVE Qwen read of the masters-v1 reader — after a ConnectionRefused.
The reader was run for real this session. It first threw
`ConnectionRefusedError [WinError 10061]` from `reader_qwen._post` — the target
machine answered but nothing was listening on `:11434` (Ollama down, or not bound
to `0.0.0.0`). The user resolved it and the read completed.
**Why it matters:** masters v1 (vendor_lookup + the 872-row master) had been
**offline-verified only**; this is the first time it ran against a live Qwen read.
**Diagnostic lesson worth keeping:** `ConnectionRefused` (target reachable, port
closed) is a *different* failure from a timeout / host-unreachable (Mac asleep,
wrong IP) — the fix is "start/expose Ollama", not "find the Mac".

### Per-invoice + batch TIMING added to `invoice_reader.py` (print-only).
The user asked how long a batch and a single invoice take. Added `import time`, a
per-PDF stopwatch around **render + Qwen call** (each `filled:`/`review:` line now
ends `[NN.Ns]`), and a batch stopwatch that prints a `Time:` summary
(total / average / fastest / slowest) after `Done.`.
**Why timed there:** it is the true wall-clock cost of an invoice (Poppler render
on the PC + Qwen on the Mac together — the number the user actually cares about).
**Deliberately not timed:** already-recorded PDFs that are skipped never reach
Qwen, so they are excluded from the numbers. **No behaviour change** — reading,
matching and what is written to the sheet are untouched; this is instrumentation.
If a render-vs-Qwen split is ever wanted (to see which machine is the bottleneck),
it is a second timer — not built yet.

### PROPERTY alias/lookup — design OPENED (brainstorming), paused on one question.
The user asked to give PROPERTIES the same alias/master/lookup machinery vendors
have (anticipated as D6/D7; property master data already sits in the workbook as
Property Names / Intacct / Yardi sheets). Classified **bounded-leaning-
architectural** — it reuses the vendor pattern but properties differ in a way that
decides the whole design, so **no code until a design is approved**.
**The blocking question:** a vendor has ONE canonical spelling; a property appears
in the workbook as THREE things (Property **Name**, **Intacct** code, **Yardi**
code). So when a human corrects a property cell, the alias must map the raw text
**to which one?** — almost certainly whatever the recorder types into Bottomline.
Answer that first; the rest falls out of the vendor design (a `property_lookup`
module, a property harvest, and a property master flattened from the workbook
sheets). Ties to the standing recorder rule that a blank/unmatched Property skips
the invoice (the dropdown is the package proof).

---

## 2026-09-03 — Session 16, property master BUILT + ERP-ID typing + pause-not-skip

Spec: `docs/specs/2026-09-03_property-master-erp-lookup.md`. Plan:
`docs/plans/2026-09-03_property-master-erp-lookup.md`. Built via
**subagent-driven development** — 7 tasks across two rounds, each a fresh
implementer + an independent reviewer, both offline-verified before the next
task started. (The skill's usual git machinery — worktrees, per-task commits,
`git diff` review packages — was dropped entirely: this project is git-free by
standing rule, so reviewers read the actual changed files instead.)

### The blocking question from Session 15 is answered: a property's canonical target is its NAME, and the package is a separate, second fact about it.
Not one of "Property Name vs Intacct code vs Yardi code" — a property has a
name (what gets typed/matched) **and** a package (YARDI or INTACCT, which sheet
it's from). `masters/properties.csv` has both: `Property Name, Package,
Property Code` (the last blank for Intacct). Same shape as the vendor master
(`Vendor Name, ..., ERP Vendor ID`), so the SAME `vendor_lookup.Lookup` module
serves both master types unchanged (D6 from Session 13, now actually used).

### Guarantee A: the alias file can only ever point INTO the master, verified in code.
The user's core worry, going in: an alias/nicknames file could, over time,
become a second, rival "master" that drifts from the real one. Checked directly
against `harvest_aliases.py`'s existing logic (`harvest()`, the `else` branch):
a correction that lands on a name **in** the master becomes an alias; a
correction to a name **NOT** in the master is *never* aliased — it is only
reported as "brand-new, needs a human OK before adding to the master." This
was already true for vendors and is now generalised (`--property` flag, same
function, `name_col`/`corrected_key`/`raw_key` parameters default to the old
vendor values so nothing about vendor behaviour changed) rather than
re-implemented, so the guarantee is inherited, not re-proven from scratch.

### Vendor ERP Vendor ID is now typed instead of the name — but only on a confident match.
`masters/vendors.csv` had an `ERP Vendor ID` column all along; the recorder
never used it. **User's insight:** typing the code makes Bottomline load the
vendor deterministically (like an autocomplete keyed by ID), which is more
reliable than typing a name and hoping the dropdown resolves it — the exact
fragility behind the original "0 matches" bug (todos.md #3).
**The safety rule, and why it matters more than the feature:** a WRONG code is
more dangerous than a wrong name, because a code loads *something* confidently
— it looks correct on review, which is exactly the kind of error a human's eye
slides past. So the code is only ever typed when the vendor name is a
**confident** match (an alias or an exact hit — `Match.status == "READ_OK"`).
Anything less (a close/uncertain match, or no code in the master) falls back
to typing the plain name, exactly as before. This is `master_index.py`'s
`value_to_type()` — a small, independently unit-tested module, reused
unchanged everywhere a "master name → a second column, but only if confident"
lookup is needed (vendor code, and now the Yardi property code below).

### The Yardi property CODE is wired in the same way — confirmed LIVE by the user first.
Before building anything, the user tested by hand: typing a Yardi property's
code into Bottomline's Property box does load the property, the same as the
ERP Vendor ID does for vendors. Only then was it wired in: for the YARDI
package specifically, a confident property match tries its **code** first;
if that doesn't resolve, it falls back to the **name** (today's dropdown
probe). **Intacct properties have no code at all** — they stay name-only,
always. This mirrors the vendor rule exactly, including the same safety
guard (`value_to_type` again — an uncertain property name never tries a
guessed code).

### Pause-not-skip: an invoice that can't be auto-placed is now finished by a human, not abandoned.
**The old behaviour:** if a property wasn't found under either package, or the
sheet had no Property at all, `establish_package()` returned `None` and the
**whole invoice was skipped** — vendor and every detail field went untyped.
**User's decision, replacing that:** the script now hands the browser to the
operator — pick the Integration Package AND the Property yourself, press
Enter — and the run **continues** to vendor + details for that invoice. Typing
`s` still skips it, exactly like every other manual fallback already in this
file (the vendor dropdown has always worked this way; this brings the
property/package step up to the same standard).
**Includes a genuinely blank Property, by explicit user choice — overriding
Claude's own recommendation.** Claude argued a blank Property might mean a
legitimately property-less invoice (general overhead) and should keep skipping
silently; the user chose to pause and ask every time instead, on the reasoning
that a human deciding "this invoice truly has no property" is better than the
script assuming it. That is now the standing rule.
**Why a misread here can never cause harm:** in the fallback path the OPERATOR
fills every box by hand on screen. The script only reads back whichever
package ends up selected, and only for its own **log line** — never to decide
what gets typed or saved. If that read-back fails (box unreadable, or shows
unrecognised text), it logs the placeholder `"UNCONFIRMED"` rather than `None`
— this distinction was proven with a standalone offline harness during code
review (calling the handoff function directly with a faked `input()`), not
just read by eye: every non-skip answer returns a truthy package value, so
`main()`'s existing "package is None → skip" check can never misfire on an
invoice the operator just finished.
**One cosmetic, deferred finding:** the operator-facing "what was tried"
summary can undersell what was actually attempted (it won't always mention a
tried-and-failed Yardi code in that one printed line), because of how the
last-attempted value is threaded through. Every individual attempt is still in
the log file regardless, and nothing wrong is ever typed into Bottomline —
this is a wording gap, not a behaviour bug, and was left as-is.

### `masters/properties.csv` was built from the real workbook, and it fought back twice — both correctly, by refusing to guess.
Two real-file surprises, both caught by the script **refusing to run rather
than silently producing a wrong master**:
1. **The Intacct sheet ("All Units - Intacct") is a printed REPORT, not a
   table** — banner rows, blank spacer rows between every unit, and the real
   header on row 6. The builder scans for the header instead of assuming row 1.
2. **The Yardi sheet's code-column header changed mid-session.** An early
   read (this same session, earlier) showed it as `Property`; by the time the
   real master was generated, the live file's header read `Property Code`.
   The first generation attempt failed loudly with a clear "column not found"
   error — exactly the intended behaviour — rather than silently building a
   master with a mismatched/blank code column. A raw `repr()` dump of the
   header row confirmed the actual text, and the run was redone with
   `--yardi-code-header "Property Code"`.
   **The lesson, worth keeping:** a live client workbook can change between
   two reads in the *same* session (autosave, someone else editing it, a
   sync). Never trust an earlier inspection's column names as still current —
   re-check the live file before generating from it.
**Also confirmed, not a bug:** the `Property Names` sheet (a human-typed list)
holds "Barclay One" as a short label, but the real per-unit Yardi table only
ever uses "Barclay One Associates LP" for that property's 82 unit rows — the
short form simply isn't a value in the canonical source, so `Property Names`
staying excluded (it "may not match the software's exact spelling," per the
user) is doing exactly its job.
**Result:** 152 properties (16 YARDI with a code, 136 INTACCT without).

### Two new helper columns, one new alias file, following the existing pattern exactly.
`Qwen Property (raw)` and `Property Status` join `invoices.xlsx` (both in
`IGNORED_COLUMNS`, never typed into Bottomline — same treatment as the vendor
pair). `masters/property_aliases.csv` is a **separate** file from the vendor
aliases, so the two nickname lists never tangle, even though both ultimately
run through the same `Lookup`/`harvest_aliases` machinery.
