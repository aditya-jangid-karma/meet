# HOT Context — always loaded, kept UNDER 50 lines (hard rule)

## Project
- Invoice_Indexer — a READER (Qwen reads PDFs → fills invoices.xlsx) and a
  RECORDER (types the sheet into Bottomline Nexus; fills boxes and STOPS, a human
  presses Convert). Lives in Desktop\TeamD-Git\Res-1-\Invoice_Indexer (git repo;
  **Claude must not run/suggest git**).

## Last session
- **2026-09-03** — BUILT property master + vendor ERP-ID typing + pause-not-skip
  (spec+plan+7 tasks, subagent-driven dev, all reviewed clean); generated the
  real masters/properties.csv (152 rows) from the live workbook.

## Active now
- **masters/properties.csv LIVE** (152 rows: 16 YARDI w/ Property Code, 136
  INTACCT no code), built from "HOC - YARDI" + "All Units - Intacct" sheets.
  "Property Names" sheet is NOT canonical — never used as a source.
- **Recorder changes**: types the vendor's ERP Vendor ID on a confident match
  only (else the name); tries a YARDI property's CODE first (user confirmed
  live it loads the property), else the name; when a property can't be placed
  under EITHER package (or is blank), PAUSES for the human to finish it in the
  browser and CONTINUES the invoice — never silently skips any more. Full
  detail: decisions.md Session 16.
- **Property aliasing** mirrors vendor's: masters/property_aliases.csv,
  harvest_aliases.py --property. Same "alias only points INTO the master"
  guarantee, verified in code (guarantee A).

## Broken / blocked
- 🟡 **Push failing** (since 2026-09-02) — local push routes through a
  broken/empty WSL. NEED: which push tool + is WSL used.
- 🟡 **Bug 0f (property dropdown) still not live-verified** — now entangled
  with today's establish_package rework (same function). ONE live test covers
  0f + ERP-ID typing + Yardi code typing + the pause flow together.
- 🟡 **add_helper_columns.py NOT yet run** on the real invoices.xlsx.

## Next step
1. Run add_helper_columns.py on the real invoices.xlsx (file CLOSED first).
2. USER live-tests the recorder — one run covers 0f + ERP-ID + Yardi code +
   pause-flow (decisions.md Session 16 has exactly what to watch for).
3. After a live pass: harvest_aliases.py --property (preview → --apply).

## Notes for next session
- **Never open** .env or automation/.bottomline_session.json.
- **Do not delete** automation/selectors_recorded.run1-15fields.json.
- Keep invoices.xlsx CLOSED during any read/record run.
- masters/ + Vendor&PropertyMaster.xlsx gitignored (client data). Git push PAUSED.
- **Live workbook headers can drift mid-session** (Yardi's code column read as
  "Property" earlier, "Property Code" later THE SAME DAY) — re-verify column
  names against the live file, don't trust a stale read.
