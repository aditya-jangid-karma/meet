# To-dos — Invoice_Indexer

Highest priority first. `HOTcontext.md` carries only the top few; this is the full list.
**Only Invoice_Indexer work belongs here.** PDF Splitter and Nexus research are separate tracks.

---

## 🔴 Blocking — the script cannot be trusted in production until these are done

### 0. ✅ THE FIRST LIVE RUN HAPPENED — 2026-08-14, and it filled an invoice
Row 1 of `logs/run_2026-08-14_1634.txt`: queue read, right invoice opened and
verified, package selected, property confirmed, vendor handed over, all four
detail boxes typed, stopped for review. **The navigation and the filling both
work against real Bottomline.**
- [x] `First names seen: [...]` are genuine image names — the grid column is right
- [x] The invoice count matches the real queue (331 over 2 pages of 200)
- [x] It opens and verifies the right invoice
- [x] The Vendor dropdown behaves — 3 matches, handed over as designed
- [ ] Do Vendor Code and Property Code fill in afterwards? (see item 4)

### 0b. 🔴 NEXT RUN — prove the package fallback and the invoice-to-invoice handover
**The user runs this. Claude does not.** Note the path changed 2026-08-14.
```
cd /d "C:\Users\Dhruv Champaneria\Desktop\TeamD-Git\Res-1-\Invoice_Indexer"
".venv\Scripts\python.exe" "automation\invoice_recorder.py" --start-row 1
```
`--start-row 1` deliberately, not `2`. The sheet holds only 2 filled rows, so
`--start-row 2` can only ever do one invoice — which is why no run has yet gone
from one invoice to the next.
- [x] ~~**The log line `property '...' under YARDI: N match(es) [...]`**~~ — first
      live evidence 2026-08-14 16:57:
      `property 'Mills Place' under INTACCT: 1 match(es) ['Mills Place']`. A clean
      property name, no `YARDI`/`INTACCT` leaking into a *property* count. **The
      `:visible` fix held.** One sample, so keep watching this line.
- [x] ~~**A `0 match(es) []` under the first package, then a confirm under the
      second.**~~ **CONFIRMED working 2026-08-20** — user tried it live. If it
      regresses, user will flag it again.
- [x] ~~**Does it go from one invoice to the next inside a single run?**~~ **PROVEN
      2026-08-17: one run filled 6 invoices back-to-back**, each auto-stamped DONE.
      The old "only ever one per run" doubt is closed.
- [ ] Do the typed values actually stick after leaving the screen? (see "Still
      unverified" at the bottom)

### 0c. 🔴 Found 2026-08-14 evening — three gaps, none fixed yet
A debugging session. **No code was changed.** The reported fault — "it cannot
reload itself to the URL and exits" — **was not a bug**: `run_2026-08-14_1657.txt`
shows the menu rung failing and the URL rung succeeding, exactly as designed. The
run then ended because it had one row. What the investigation did find:

- [ ] 🔴 **A run can die leaving no log line at all.** `KeyboardInterrupt` is a
      `BaseException`, so the `except Exception` guard around `return_to_queue()`
      misses it. `run_2026-08-14_1634.txt` stops dead after `Row 1: filled` — no
      `Run finished`, no `user quit` — because the process was interrupted at the
      "Done? Press ENTER" prompt with 2 invoices still to do.
      **Fix direction:** catch `KeyboardInterrupt` and log a resume line.
- [x] ~~🟡 **`return_to_queue()` is silent on the console.**~~ **FIXED 2026-08-17.**
      `note` now prints AND logs (a small function, not the file-only lambda), so
      every recovery message reaches the operator. `log_line` left untouched, so the
      login block does not double-print. This was the cause of the 08-14 false bug
      report. See `decisions.md` Session 9.
- [ ] 🟡 **A spreadsheet row vanished.** 16:31 and 16:34 both logged
      `Rows to process: 3`; the workbook was re-saved at 16:56:33; the 16:57 run
      logged `Rows to process: 1`. All 501 lines were checked — exactly 2 filled
      rows remain. Nobody knows what the third one was. Confirm nothing was lost.
      **Deprioritized 2026-08-20** — still a real mystery, per user, but parked
      until bigger items close. Not a live blocker.

### 0d. ✅ DONE 2026-08-17 — Status column (PENDING/DONE)
`input/invoices.xlsx` now has a `Status` column. DONE = skip; blank/PENDING =
record. `mark_row_done()` auto-stamps DONE when the operator presses ENTER at the
"Done?" prompt; the cell stays hand-editable. `status` added to `IGNORED_COLUMNS`
so it is never typed into Bottomline. See `decisions.md` Session 9.

### 0e. 🔴 Found 2026-08-17 — the write-back strips the green-triangle fix
`mark_row_done()` calls `workbook.save()`, and openpyxl silently discards the
hand-written `<ignoredErrors>` XML that suppresses Excel's "number stored as text"
warning (see `decisions.md`, Session 3 green-triangle entry — its "recorder only
ever reads, so safe" conclusion is now **false**).
- [ ] Decide the fix: re-inject the XML after each save, save once at the end
      instead of per-row, or accept the ⚠️ triangles and rely on operator
      discipline. **Until then, warn operators NOT to click "Convert to Number"** —
      it turns `007458` into `7458` and dates into serial numbers, unrecoverably.

### 0f. 🔴 Found 2026-08-19 — the Property box may not clear between package attempts
Live `logs/run_2026-08-18_1920.txt`: two invoices with property "Heather Hill"
(rows 17–18 / Excel 18–19) returned `0 match(es)` under **both** INTACCT and
YARDI and were skipped — yet the SAME "Heather Hill" matched "Heather Hills"
earlier in the very same run (row 13, line 86 of that log). The user watched the
old value stay in the Property box when the script switched package.
- [ ] 🟡 **FIX APPLIED 2026-09-01, OFFLINE-TESTED, awaiting a LIVE run.** ONE
      timing flaw: the ExtJS list was read at a single instant right after typing
      (`items.first.wait_for(visible)` passes on stale leftovers; `items.count()`
      runs before the debounced query re-renders), so the same "Heather Hill"
      matched on one row, not the next. Plus `clear_box()` used `fill("")` (no
      keystrokes) → ExtJS kept the old property between packages. **Now in the
      code** (`invoice_recorder.py` + `rehearse_fill.py`): settle-wait helper
      (poll till the list stops changing), keystroke clear (Ctrl+A/Delete), staged
      typing 60→75→100% (escalate only when NOTHING loads), retype-full-then-clear
      reset between packages, slower property typing. Offline green (rehearse 5/2,
      nav 47/47). **UNVERIFIABLE offline — the USER re-runs the two "Heather Hill"
      invoices live to confirm; do NOT tick this until then.** See `decisions.md`
      Sessions 13–14.
- [x] ~~🔴 **Recorder types the whole value and does not pause for the dropdown
      suggestions to load**~~ (user, 2026-09-01). SAME root cause — the settle-wait
      + slower property typing + staged prefix typing fix addresses it. Applied
      2026-09-01, offline-tested; confirmed live only when 0f above is.

### 0g. ✅ DONE 2026-08-19 — auto-navigation, status-driven runs, leaner prompts
All proven on `logs/run_2026-08-18_1920.txt` (filled 7).
- [x] Script reaches "Images to be Indexed" itself after login (opens the "Image
      Management" menu — hover, then click — via `_reveal_menu()` +
      `menu_opener`/`menu_opener_text` in `selectors.json`). Falls back to asking.
- [x] Waits for real grid rows before trusting the read (`wait_for_queue_rows()`),
      and STOPS loudly if the queue reads as 0 invoices — fixes the "looked done
      but recorded nothing" empty-read seen at 19:11.
- [x] Status column alone decides what records; no `--start-row` needed. Prints an
      upfront plan ("N to record, M DONE" + the exact Excel lines). `--start-row`
      kept as an advanced override with honest help (it is a data-row index, one
      behind the Excel line — the cause of the skipped line 8 on 2026-08-18).
- [x] Removed the per-invoice "fill? [y/s/q]" prompt — the image-name check is the
      gate; review still happens at "Done?". See `decisions.md` Session 10.

### 1. ✅ DONE — the script can now get itself to the indexing page
Built 2026-08-13 in `automation/queue_navigator.py`. 15 offline tests pass.
- [x] Agree the design with the user
- [x] Upgrade the recorder so it can see grid rows
- [x] Record the queue journey and verify the capture
- [x] Resolve 1b, 1c and 1d
- [x] Write the spec — signed off 2026-08-13
- [x] Build V1
- [ ] **Prove it live — item 0 above.**

### 1-OLD. Original diagnosis, kept for context
**Evidence:** `logs/run_2026-08-10_1832.txt` and `_1834.txt` both log
`image name box not found on screen`.

**The selector is NOT the problem.** `input[name="Image_Index_Name"]` is correct.
The box only exists once an image has been opened for indexing, and the script has
no way to get there — it assumes a human has already navigated to an open invoice
and only starts looking at that moment.

This is the root cause of the failed safety check, and it is being solved by the
self-navigation work rather than by changing any selector.

**Progress 2026-08-13:** design agreed, recorder upgraded, queue recorded. Every
navigation selector except one is now known (see `decisions.md`).
- [x] Agree the design with the user
- [x] Upgrade the recorder so it can see grid rows
- [x] Record the queue journey and verify the capture
- [ ] **Resolve 1b and 1c below, then write the spec** ← next session starts here
- [ ] Build V1 (one invoice, `--limit 1`) once the spec is signed off

### 1b. ✅ RESOLVED — the operator presses ENTER
Convert to Invoice opens the second screen; the queue does not come back on its
own. The operator completes screen 2, presses Save there, then presses ENTER in
the console. The script returns to the queue via the "Images to be Indexed" menu
item. Built and in place.

### 1c. ✅ RESOLVED — 200-per-page dropped
Paging at 25 instead. Costs ~9 page loads once per run and uses solid selectors.

### 1d. ✅ RESOLVED — `Image_Index_Name` confirmed live 2026-08-13
Confirmed by `automation/page_probe.py`, labelled "Image Name:". A second,
independent check on `.top-page-header-text` was added alongside it.

### 2. ✅ RESOLVED — the "fill anyway" branch is deleted
Failure now means: retry once, then skip the row and report it. Nothing is ever
typed on a failed check.

---

### 2b. ✅ RESOLVED 2026-08-14 — the grid column is correct
A screenshot of the live queue confirmed **Image Name is the first column with
text in it**, exactly what `row_image_name()` takes. Three live runs have since
matched invoices by name and opened the right one.

### 2c. 🟡 `go_to_queue_page()` still waits a fixed 1.5 seconds
Same bug class as the paging failure fixed in `read_queue()` on 2026-08-14, in
the other direction: this one *types* the page number, so the page-number box
shows the right value whether or not the grid actually moved. It needs a
different signal — polling the box would prove nothing.
- [ ] Find a condition that genuinely means "the grid finished reloading".
Failure mode is safe today: the row is not found, one retry, then a skip with
nothing typed.

### 2d. 🟡 The queue's row order changes between reads
Two runs minutes apart returned different invoices in grid positions 2 and 3.
Every row shares the same Scanned Date, so ties come back in whatever order the
server chooses. The script records "this invoice is on page 7" and jumps back
there later, so a reshuffle produces a spurious skip.
- [ ] Sort the grid on Image Name before reading it, so the order is stable and
      repeatable. Safe today — it can only skip, never mis-file.

### 3. Vendor returned 0 dropdown matches
**Evidence:** `logs/run_2026-08-10_1835.txt` —
`vendor: 0 matches for 'Steps Appliance Repair LLC'`.

Property and Integration Package *did* return matches on the same run, so the
dropdown selector itself is fine. The likely cause is that the spreadsheet
spelling does not match Bottomline's spelling.
- [ ] Type the vendor name into Bottomline by hand and note the exact spelling.
- [x] ~~Correct the spreadsheet, or decide the sheet should hold the vendor
      **code** rather than the name.~~ **RESOLVED DIFFERENTLY, 2026-09-03.** The
      sheet keeps the human-readable NAME (so review stays legible); the
      recorder now resolves name → ERP Vendor ID itself at record time, and
      types the CODE when the match is confident, the name otherwise. See
      `decisions.md` Session 16. **Still needs a live test** to confirm this
      actually prevents a repeat of "0 matches" for this vendor.

---

## 🟡 Should do

### 3b. ✅ DONE 2026-09-03 — PROPERTY alias/lookup BUILT (was: design opened 2026-09-02)
Answered: a property's canonical target is its NAME (the package is a separate,
second fact about it). Built `masters/properties.csv`, `masters/property_aliases.csv`,
a generalised `harvest_aliases.py --property`, and reader/recorder wiring — see
section **"🟢 Property Master + Vendor ERP-ID Recording"** near the end of this
file, and `decisions.md` Session 16 for the full design and what changed.

### 4. Confirm the vendor/property code actually loaded
`selectors.json` says the script "should confirm that happened before treating
the field as done." **It does not.** Nothing checks that the underlying code
loaded after a dropdown pick.

**Unblocked 2026-08-13** — the 13 Aug capture found both boxes, so this is now
straightforward rather than an open question:
- `input[name="Image_Index_VendorSite_Id_Code"]` — "Vendor Code:"
- `input[name="property_id_code"]` — "Property Code:"
- [ ] After a dropdown pick, read the matching code box and fail if it is empty.
      An empty code box is exactly the "looks filled, is empty underneath"
      failure the typing design exists to prevent.

### 5. The dropdown result is thrown away
In `invoice_recorder.py`, `fill_autocomplete()` returns `picked` / `manual` /
`stopped`, but the caller at line ~484 ignores the return value. A box the
operator explicitly skipped is counted as filled.
- [ ] Use the return value; count a skipped box in the run summary.

### 6. The 18:54 run never finished
`logs/run_2026-08-10_1854.txt` queued 3 rows and logs nothing after.
- [ ] Confirm nothing was half-entered into Bottomline that night.

### 7. Vendor box timed out once, then worked
`_1832.txt` timed out waiting for `Image_Index_VendorSite_Id`; `_1835.txt` used it
fine. Probably the screen was not fully loaded.
- [ ] Watch for a repeat. If it recurs, wait for the form before the first field.

---

## 🟢 Housekeeping

### 8. Task 5 of the build plan was never done ← the only unfinished build task
`docs/plans/2026-08-13_self-navigation-build.md`, Task 5.
- [ ] **`README.md` says the image name is a GUID. Do not simply reverse that.**
      Corrected 2026-08-14: the format **varies with the source**. FTP-imported
      documents genuinely do carry GUIDs
      (`6e1f92f5-2ee3-4c1f-b09a-0541b564e7d2` — the whole queue looked like this
      on 14 Aug); scanner documents carry `skm_c250i26080508080`. The 13 Aug note
      saying "it is NOT a GUID" was as wrong as the README.
      **What to write instead: copy the Image Name exactly out of the queue.**
- [ ] Add the README section describing what the script now does by itself.
- [ ] Mark `docs/plans/2026-08-07_*` and `docs/specs/2026-08-07_*` superseded.

- [x] ~~`selectors.json` calls `.x-boundlist-item` "INFERRED, NOT CAPTURED"~~ —
      corrected 2026-08-13; now records that it was observed working.
      ⚠️ **Then corrected again 2026-08-14**, because "observed working" was
      itself wrong: it was matching hidden leftovers from closed dropdowns and
      inflating match counts. Now `.x-boundlist-item:visible`. See `decisions.md`.
- [ ] `automation/README.md`, `input/README.md`, `logs/README.md`,
      `notes/README.md` are still Session-2 stubs. CLAUDE.md requires each folder
      README to explain the technical detail well enough for a CPA to maintain.
- [x] ~~`context/context.md` is an empty leftover~~ — now the standing project brief.
- [x] ~~Confirm `input/invoices.xlsx.bak` is gone (it is no longer on disk).~~ —
      ⚠️ **That claim was wrong.** The file was still on disk on 2026-08-19.
      Deleted for real during the 2026-08-19 cleanup.
- [ ] The recorder still ignores open dropdown lists — `addressable()` does not
      recognise `x-boundlist-item`. Only matters if someone re-records to chase a
      dropdown problem. **Worth more than it used to be:** the 14 Aug hidden-item
      bug would have been obvious from a recording of an open dropdown.
- [ ] Two new fields exist on the indexing screen that the map does not mention:
      `Image_Doctype_Id` ("Document Type", currently listed as dropped) and
      `checkbox-1761` ("Filter by Header Property"). Decide if either matters.
- [ ] **Do not delete `automation/selectors_recorded.run1-15fields.json`** — it is
      the original evidence behind the field map, kept out of the rotation.
- [ ] `automation/page_probe.py` is new and undocumented in `automation/README.md`.
      It is the tool for reading a screen's real field names without a recording —
      worth documenting, it will be needed again.

---

## ⏸️ Later — not now

- Handle multi-line GL splits. Only needed if they turn out to be routine — still
  unanswered.

---

## 🟢 Phase 2 — auto-fill the sheet from PDFs (Qwen) — BUILT + first live run done

**Built 2026-08-20, live-tested same day.** Poppler renders each invoice PDF →
local Qwen (`qwen2.5vl:7b`) reads it → row appended to `invoices.xlsx`. Property +
Integration Package blank for a human; the recorder is untouched. The spreadsheet
stays the seam. Spec: `docs/specs/2026-08-20_qwen-autofill-design.md`; plan:
`docs/plans/2026-08-20_qwen-autofill-build.md`; **reusable method write-up:
`docs/2026-08-20_qwen-reading-method.md`**.
- [x] Deps: `pdf2image` in requirements; Poppler for Windows installed by user
      (`C:\Users\Dhruv Champaneria\Desktop\poppler-26.02.0\Library\bin`)
- [x] `reader_directory.py` (vendor match), `reader_qwen.py` (only file that
      talks to Qwen), `reader_pdf.py` (Poppler), `invoice_reader.py` (orchestrator)
- [x] **First LIVE run worked** — Qwen read 2 invoices (Aire-Master, Caplan
      Bros.) and wrote them. Image Name = PDF filename stem confirmed via the
      dedup guard ("2 already-recorded skipped" on the second run).
- [x] 17 offline self-tests pass — `8 - Test The Reader.bat`

### Fixed 2026-08-20 (offline-tested, NOT yet re-run live)
- [x] 🔴 **Rows landed far down the sheet.** openpyxl's `max_row` is inflated by
      empty-but-formatted cells, so the 2 rows were appended into a gap ~180 rows
      below the visible data. Fixed: new `last_data_row()` scans the key columns
      for the true last row; the loop appends right after it. Tests prove it lands
      at row 3, not 201.
- [x] 🔴 **Date now forced to MM/DD/YYYY.** Prompt asks for it AND Python
      `_to_mmddyyyy()` normalises as a backstop (month-first for US; unparseable
      kept as-is, never invented). Applied to invoice_date and due_date.

### Pending — for the next session
- [x] ~~🔴 **CLEAN UP the 2 stranded rows first.**~~ **DONE 2026-09-01** — user
      deleted the 2 stray rows by hand and confirmed the reader now lands rows
      correctly at the sheet bottom. (They sat ~180 rows below the data:
      Aire-Master, Caplan Bros., with the OLD as-printed dates.)
- [ ] 🔴 **Re-run live to verify fixes.** **RAN 2026-08-24** over all PDFs (Excel
      CLOSED) — verification IN PROGRESS, not yet confirmed. Check: rows land right
      after real data; dates read MM/DD/YYYY; number keeps leading zeros; **Property
      now filled with raw text** (Ship-To where both appear). **Keep invoices.xlsx
      CLOSED during any run** — an open Excel on the `Z:` share hides/clobbers the
      write (this caused the "nothing written" scare).
      **UPDATE 2026-09-02:** the reader ran live again this session on the
      MASTERS-V1 path (after clearing a `ConnectionRefused` = Ollama not reachable
      at `--host`). First live exercise of vendor_lookup + the 872-row master.
      Still CONFIRM the checklist above against the rows it wrote.
- [ ] 🟢 **DONE 2026-09-02 — per-invoice + batch TIMING in `invoice_reader.py`.**
      Print-only: each `filled:`/`review:` line ends `[NN.Ns]`; a `Time:` summary
      (total/avg/fastest/slowest) prints after `Done.`. Times render + Qwen call
      together; skipped dupes excluded. No behaviour change. (A render-vs-Qwen
      split is a possible future second timer — not built.)
- [x] ~~🟡 **Property is blank by design (D9).**~~ **CHANGED 2026-08-24** — no
      property list exists, so Qwen now extracts the RAW property/location text
      (Ship-To preferred when both Bill-To and Ship-To appear) into the Property
      column for a human to CONFIRM before recording. Added to schema + prompt in
      `reader_qwen.py`; written in `invoice_reader.py`. 19 offline tests pass.
      ⚠️ NOT a canonical Bottomline property — human confirmation still required,
      and the recorder may not match the raw text.
- [ ] 🟡 **Add a "Qwen Status" column** to `invoices.xlsx` — a per-row flag the
      reader stamps (e.g. `READ_OK` / `NEEDS_REVIEW` / `PROPERTY_GUESSED`) so the
      operator sees at a glance which auto-filled rows Qwen was unsure about —
      especially the raw Property values that now need confirming (above). Must be
      added to the recorder's `IGNORED_COLUMNS` so it is NEVER typed into
      Bottomline (same treatment as the `Status` column). Not built yet —
      design + approve first.
- [ ] Set the real `--pdf-dir` on the mapped drive (default `Z:\Res-1-indexer\input\pdfs`).

---

## 🟢 Property Master + Vendor ERP-ID Recording — BUILT 2026-09-03

**Built via subagent-driven development, spec+plan+7 tasks, all reviewed
clean.** Spec: `docs/specs/2026-09-03_property-master-erp-lookup.md`. Plan:
`docs/plans/2026-09-03_property-master-erp-lookup.md`. Full design reasoning
and every decision: `decisions.md` Session 16.

- [x] `automation/master_index.py` — the confident-match helper (hands back a
      second column's value only on a READ_OK match); reused for both the
      vendor ERP-ID and the Yardi property code.
- [x] `automation/build_property_master.py` — turns the two workbook sheets
      into `masters/properties.csv` (Property Name, Package, Property Code).
- [x] Reader writes the canonical Property + an Integration Package hint,
      plus two new helper columns (`Qwen Property (raw)`, `Property Status`).
- [x] `harvest_aliases.py --property` — property corrections are learned the
      same way vendor corrections are, into `masters/property_aliases.csv`.
- [x] Recorder types the vendor's ERP Vendor ID on a confident match, the
      name otherwise.
- [x] Recorder tries a YARDI property's CODE first (confirmed LIVE by the
      user that it loads the property), the name otherwise; INTACCT always
      stays name-only (it has no codes).
- [x] Recorder now PAUSES (never silently skips) when a property/package
      can't be auto-placed, or when Property is blank — the human finishes
      it in the browser and the run continues.
- [x] `masters/properties.csv` generated for real: 152 rows (16 YARDI with a
      code, 136 INTACCT without). Spot-checked against the live sheets.

### Pending — for the next session
- [ ] 🔴 Run `add_helper_columns.py` on the real `invoices.xlsx` (adds the 2
      new property columns) — the file must be CLOSED first.
- [ ] 🔴 **USER live-tests the recorder** — ONE run should confirm, together:
      bug 0f (property dropdown timing, open since 2026-08-19), the ERP
      Vendor ID typing, the Yardi property code typing, AND the new
      pause-and-continue flow (try an invoice with an unmatched property).
- [ ] After a live pass with real corrections: `harvest_aliases.py --property`
      (preview first, then `--apply`).
- [ ] 🟢 Minor, deferred, cosmetic: the manual-handoff's "what was tried"
      operator message can undersell a failed Yardi-code attempt (the log
      file always has the full detail regardless). See `decisions.md`
      Session 16.
- [ ] 🟢 Minor, deferred, cosmetic: `add_helper_columns.py`'s docstring/help
      text still says it adds "two" helper columns; it now adds four.

---

## ❓ Still unverified

- Whether ExtJS commits plain fields on `change` + blur, as `commit_plain_field()`
  assumes. The 18:35 run typed four fields without complaint, but nobody has
  confirmed the values actually *stuck* after leaving the screen.
- Whether the login form really is "first text box + first password box".
- Whether ExtJS ids genuinely change between loads. Irrelevant in practice — the
  map uses `name`.
