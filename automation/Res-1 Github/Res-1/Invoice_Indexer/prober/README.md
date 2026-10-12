# `prober/` — the Vendor Master PROBER

**What it is in one sentence:** a script that types each vendor code from our
master into Bottomline, reads back what Bottomline says that code really is, and
writes the comparison to a spreadsheet. It never saves anything into Bottomline.

---

## Why this folder exists

The Invoice_Indexer project has three separate automations. They used to all sit
together in `automation\`, which made it hard to tell which file belonged to
which job:

| Automation | What it does | Where it lives |
|---|---|---|
| READER | Reads invoice PDFs with Qwen → `invoices.xlsx` | `automation\` |
| RECORDER | Types an invoice into Bottomline and **stops** before saving | `automation\` |
| **PROBER** | **Asks Bottomline what each vendor code is** | **`prober\` (here)** |

The prober was split out on **2026-09-10**. Nothing about how it works changed
in that move — only where the two files sit.

---

## The two files

| File | What it is |
|---|---|
| `verify_master.py` | The prober itself. ~2,200 lines, heavily commented. |
| `selftest_verify_master.py` | 214 offline tests. No browser, no login, no Bottomline. |

### It still borrows four things from `automation\`

The prober does **not** carry its own copy of these — it imports the same ones
the RECORDER uses, so a fix in one place fixes both:

| Borrowed from `automation\` | What it gives the prober |
|---|---|
| `invoice_recorder.py` | Login session, the typing helpers, `probe_dropdown()`, `log_line()` |
| `selectors.json` | The map of which CSS selector is which form box |
| `fill_plan.py` | `DEFAULT_ORDER`, `KNOWN_PACKAGES` |
| `harvest_aliases.py` | `normalise_package()` — see the warning below |

Because those stayed behind, both files start by adding `automation\` to the
list of folders Python searches:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "automation"))
```

**If you delete that line, nothing runs** — every import fails immediately with
`ModuleNotFoundError`. Read it right to left: this file → `prober\` →
`Invoice_Indexer\` → then into `automation`.

> ⚠️ **Two `normalise_package` functions exist and they are NOT interchangeable.**
> `fill_plan`'s keeps `"YARDI (2)"`; `harvest_aliases`' returns `"YARDI"`.
> The master writes the bracket number, the Bottomline screen does not. The
> prober needs **`harvest_aliases`'** version. Importing the other one sends
> every row down the no-package branch and reports all 875 coded vendors as
> `WRONG_PACKAGE`.

---

## How to run it

From the `Invoice_Indexer` folder, with the virtual environment active:

```
python prober\verify_master.py --limit 25 --skip-phase0
```

Then open **any** invoice for indexing in the browser window it opens. The
prober does not care which invoice — it just needs a form with boxes on it, and
it only ever reads from that form.

### The flags

| Flag | What it does |
|---|---|
| `--limit N` | Only probe the first N vendors. Leave it off for all 959. |
| `--batch-size N` | Rows per save. Default 25. Output is appended per batch, so a crash loses at most one batch. |
| `--resume` | Carry on from the last finished batch instead of starting over. |
| `--skip-phase0` | Skip the package calibration. **Names, codes and addresses are still checked** — only the package column goes unjudged, reported as `UNVERIFIED_PACKAGE` rather than guessed. |
| `--no-address` | Never open the Vendor Address popup. Everything except the street line still gets captured. |
| `--no-pause` | Do not stop and ask when a vendor fails to load. |
| `--typing-delay MS` | Milliseconds between keystrokes. Default 220. **Raise this if a run reports a lot of `NOT_FOUND`** — typing faster than Bottomline's suggestion list loads looks exactly like a code that does not exist. |

### Running the tests

```
python prober\selftest_verify_master.py
```

Expected: `Ran 214 tests` then `OK`. These run anywhere — no login, no browser,
no internet. Run them before and after any edit.

---

## What it produces

Three files in `masters\`, **all three gitignored** because they carry real
vendor names and addresses (hard rule #1):

| File | What it is |
|---|---|
| `vendors_probed.csv` | The 19-column result. One row per vendor. |
| `master_review.xlsx` | The same thing, formatted for reading. |
| `.probe_checkpoint.json` | Which batch finished, so `--resume` knows where to pick up. |

A **fresh run** (without `--resume`) moves the previous `vendors_probed.csv`
into `masters\archive\` before starting, so nothing is overwritten.

Run logs go to `logs\probe_<date>_<time>.txt` — also gitignored.

### The 19 columns

The design point: **what our master claims and what Bottomline answers sit in
separate columns and are never merged.** A disagreement shows up as two
different values side by side instead of one quietly overwriting the other.

| Group | Columns | Source |
|---|---|---|
| Our claim | `Vendor Name`, `ERP Vendor ID`, `Claimed Package` | `masters\vendors.csv` |
| Bottomline's answer | `Bottomline Name`, `Bottomline Code`, `Matched Package` | the Vendor Address popup |
| What was on screen | `Code Box Held`, `Screen Package`, `Screen Property Code`, `Screen Property`, `Screen Vendor` | the indexing form |
| The address | `Street`, `City`, `State`, `ZIP` | the popup |
| Evidence | `Verdict`, `Match Count`, `Dropdown Sample`, `Probed At` | the run |

### The verdicts

| Verdict | Meaning |
|---|---|
| `CONFIRMED` | Popup showed our code, under the package we claimed. |
| `UNVERIFIED_PACKAGE` | Name and code hold; the package could not be judged (this is what `--skip-phase0` produces). |
| `CODE_MISMATCH` | The popup showed a **different** code. Needs a human. |
| `WRONG_PACKAGE` | Resolved, but under the other package. |
| `NOT_FOUND` | Resolved under neither package. |
| `AMBIGUOUS` | 2+ dropdown matches — the code is not unique. |
| `PACKAGE_LEARNED` | Master claimed no package; exactly one matched. |
| `NO_CODE` | Master row had nothing to probe. |

**Match Count** is how many vendors Bottomline's autocomplete offered after the
code was typed. 1 is clean; 0 means nothing matched; 2+ means the code is not
unique. The script only ever **counts** — it never clicks the dropdown and
never selects anything.

---

## ⚠️ Known faults as of 2026-09-10 — read before trusting output

A 25-row run completed on 2026-09-10 (log `probe_2026-09-10_1550.txt`). The
open→read→close popup sequence worked 25 out of 25 times. **But three faults in
the output remain unfixed.** Full write-up:
`notes\2026-09-10_prober-three-faults.md`.

1. **Wrong vendor's address recorded silently** (2 of 25 rows). When a code does
   not exist, Bottomline leaves the *previous* vendor on the form, and the popup
   shows that previous vendor. `form_confirms()` at `verify_master.py:1210` was
   supposed to catch this and does not — it is currently a rubber stamp. **This
   is the one that writes wrong data under a right-looking name. Fix first.**
2. **`Match Count` and `Dropdown Sample` are one row behind** (18 of 25). The
   dropdown is counted before Bottomline's answer lands, so it counts leftovers.
   `Screen Vendor` lags the same way.
3. **YARDI addresses do not split** (3 of 3 YARDI rows). YARDI popups end with a
   `United States` line; the parser looks at the last line for `City, ST ZIP`,
   finds a country, and dumps everything into `Street`.

Faults 2 and 3 are wrong-but-visible, which is much safer than fault 1.

---

## Technical notes for whoever maintains this

**Libraries used:** `playwright` (sync API — drives a real Chromium browser),
`openpyxl` (writes the .xlsx), `python-dotenv` (reads the login from `.env`),
plus the standard library (`csv`, `json`, `re`, `ast`, `subprocess`,
`unittest`, `pathlib`).

**Every block of JavaScript in this file must be a raw string** — written
`r"""..."""`, not `"""..."""`. This is not a style preference. On 2026-09-09 a
JavaScript comment inside a normal Python string contained `\n`; Python turned
those two characters into a real line break, which split the comment in half and
left stray code behind it. Every call then died with
`SyntaxError: Invalid or unexpected token`, and a bare `except Exception` was
swallowing it, so the popup silently "never had any text" for two days.
`selftest_verify_master.py` now has a test that fails if any `*_JS` block is not
a raw string, and a second that runs `node --check` over each one.

**ExtJS, the UI framework Bottomline uses, sets three traps:**

1. A **modal mask** (`div.x-mask`) covers the page while a dialog is open, so a
   normal Playwright click cannot reach the × — it gets intercepted. The close
   is done by a JavaScript click instead.
2. **`data-ref` attributes are reused at every nesting level.** Asking for the
   first `[data-ref="innerCt"]` returns the window *header* (whose text is just
   "Vendor Address"), not the body. The read now walks a list of candidate
   containers and rejects any whose only line is the heading.
3. **Component IDs auto-increment** — the same dialog is `window-1787` on one
   run and `window-1800` on the next. Never hard-code them. Use the stable
   attribute `[auto_id="vendor_address_window"]`.

**The visible rhythm** (`POPUP_SETTLE_MS = 400`, `POPUP_HOLD_MS = 800`): after
clicking Vendor Address the script pauses 400ms before reading, and holds the
popup open 800ms before closing, so an operator watching the browser can see
open → read → close happen. This costs ~1.2s per vendor, about 20 extra minutes
across all 959. Both constants sit together near the top of the file and can be
turned down once the output is trusted.

**`say()` vs `log_line()`:** `say()` writes to the log file *and* prints to the
terminal. `invoice_recorder.log_line()` was deliberately left alone — it is
shared with the RECORDER, which commits real data into Bottomline, and changing
its output behaviour was not the prober's business.
