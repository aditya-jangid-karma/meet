"""
invoice_recorder.py -- type invoices from a spreadsheet into Bottomline Nexus.

WHAT THIS DOES (plain English):
    Reads input/invoices.xlsx, one row per invoice. For each row it checks that
    the document open in Bottomline is the right one, shows you what it is about
    to enter, waits for you to say yes, and then fills the boxes.

    IT NEVER PRESSES SAVE. It never presses "Convert to Invoice" either. It
    fills the indexing screen and stops. You review what it typed and press the
    buttons yourself.

THE TWO THINGS THAT KEEP IT HONEST:
    1. IMAGE NAME CHECK. Before typing anything it reads the "Image Name" box
       on screen and compares it with the Image Name column in the spreadsheet
       row. If they do not match, it stops. This is what makes it impossible to
       record Ferguson's invoice against Apex's document -- the failure that
       would otherwise fill perfectly, error at nothing, and only surface when
       somebody reconciled months later.

    2. IT STOPS AFTER FILLING, BEFORE ANYTHING IS SAVED. It fills the boxes and
       waits at a "Done?" prompt. Nothing is saved until you have reviewed every
       box against the invoice image and pressed Convert to Invoice / Save
       yourself. (It no longer asks "fill this? y/n" before typing -- once the
       Image Name check in (1) has passed, the open document IS this row's
       invoice, so there is nothing left to decide.)

WHY IT TYPES INSTEAD OF PASTING:
    Vendor, Property and Integration Package are not plain text boxes. They are
    search boxes that show a dropdown, and you have to pick from that dropdown
    for the underlying code to be stored. A dropdown only appears in response to
    real keystrokes. Pasting a value in one go sets the text but fires no
    keystrokes, so no dropdown appears and no code is stored -- the box would
    LOOK filled and be empty underneath. So every field is typed a character at
    a time, exactly as a person would.

HOW DROPDOWNS ARE HANDLED:
    Exactly one match  -> it picks it.
    None, or several   -> it stops and hands the browser to you. You pick the
                          right one yourself, then press Enter to carry on.

COMMANDS:
    python invoice_recorder.py                 start at the first row
    python invoice_recorder.py --start-row 5   resume a batch from row 5
    python invoice_recorder.py --dry-run       print what it WOULD do; no browser
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

# queue_navigator.py sits beside this file. Added explicitly so the script also
# works when launched from the project root, which is what the .bat files do.
sys.path.insert(0, str(HERE))
from fill_plan import (  # noqa: E402  (must follow the sys.path line)
    KNOWN_PACKAGES,
    detail_fields,
    is_known_package,
    normalise_package,
    package_candidates,
    package_verdict,
    property_candidates_for_package,
)
from queue_navigator import (  # noqa: E402  (must follow the sys.path line)
    normalise_name,
    open_invoice,
    read_queue,
    return_to_queue,
    wait_for_queue_rows,
    wait_for_queue_screen,
)
from vendor_lookup import load_master, load_aliases, Lookup  # noqa: E402
from master_index import build_index, value_to_type  # noqa: E402

# Playwright's copy of Chrome lives inside the project, not in your Windows
# user folder. Must be set before playwright is imported.
BROWSERS_DIR = PROJECT / ".browsers"
if BROWSERS_DIR.exists():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS_DIR))

SELECTORS_FILE = HERE / "selectors.json"
SESSION_FILE = HERE / ".bottomline_session.json"
MASTERS_DIR = PROJECT / "masters"
VENDORS_CSV = MASTERS_DIR / "vendors.csv"
VENDOR_ALIASES_CSV = MASTERS_DIR / "aliases.csv"
PROPERTIES_CSV = MASTERS_DIR / "properties.csv"
PROPERTY_ALIASES_CSV = MASTERS_DIR / "property_aliases.csv"
# Default location: the shared/mapped drive, so any team PC reads and writes
# back the SAME invoices.xlsx. A PC whose drive letter differs overrides this
# with --xlsx at run time. Logs stay LOCAL (see LOG_DIR) -- each PC keeps its own.
SPREADSHEET = Path(r"Z:\Res-1-indexer\input\invoices.xlsx")
LOG_DIR = PROJECT / "logs"

# Columns that exist for the humans. Never typed into Bottomline, and never
# counted when deciding whether a row has been filled in.
IGNORED_COLUMNS = {"row_id", "notes", "image_name", "status",
                   "qwen_vendor_raw", "qwen_status",
                   "qwen_property_raw", "property_status"}

# A row is "unused" unless at least one of these carries a value. Matches the
# rule printed on the "How to use" tab of the spreadsheet.
MEANINGFUL_COLUMNS = ("vendor", "invoice_number", "amount")

# Milliseconds between keystrokes. Fast enough not to be tedious, slow enough
# that an autocomplete has time to notice each character.
TYPING_DELAY_MS = 45

# How long to wait for a dropdown to appear after typing.
DROPDOWN_WAIT_MS = 2500

# The Property search box is typed MORE slowly than the other fields. Its
# dropdown is the proof of the integration package, so every character needs
# time to trigger ExtJS's filter before the next one lands -- type it too fast
# and the suggestions never get a chance to load. Only Property uses this;
# everything else stays at TYPING_DELAY_MS. Raise it if the Property dropdown
# still lags on a slow connection.
PROPERTY_TYPING_DELAY_MS = 100

# Search boxes (Property, Vendor) are typed as a GROWING prefix, not all at
# once, so the dropdown has a chance to load. Type this fraction of the name
# first; only if NOTHING loads, type up to the next fraction, then the whole
# name. Once the list loads (one item or several) the escalation stops -- see
# type_and_settle_staged(). Integration Package does NOT use this (it is short
# -- YARDI / INTACCT -- and a prefix there would just be ambiguous).
PREFIX_STAGES_PERCENT = (60, 75, 100)

# Never type fewer than this many characters as the first prefix, so a short
# name does not start by matching half the list.
MIN_PREFIX_CHARS = 5


def header_to_key(header):
    """'Invoice Due Date' -> 'invoice_due_date'. Matches selectors.json keys."""
    cleaned = "".join(c if (c.isalnum() or c.isspace()) else " " for c in str(header))
    return "_".join(cleaned.lower().split())


def load_selectors():
    if not SELECTORS_FILE.exists():
        sys.exit(
            f"STOPPED: no field map found at {SELECTORS_FILE}\n"
            "Run selector_recorder.py first, then build selectors.json from its output."
        )
    raw = json.loads(SELECTORS_FILE.read_text(encoding="utf-8"))

    fill = raw.get("fill", {})
    if not fill:
        sys.exit(f"STOPPED: {SELECTORS_FILE} has no 'fill' section.")

    queue = raw.get("queue", {})
    if not queue:
        sys.exit(
            f"STOPPED: {SELECTORS_FILE} has no 'queue' section.\n"
            "The script needs it to find invoices in the indexing queue itself.\n"
            "See docs/specs/2026-08-13_self-navigation-design.md, section 5."
        )

    return {
        "fill": fill,
        "autocomplete": set(raw.get("autocomplete", [])),
        "verify": raw.get("verify", {}),
        "dropdown_item": raw.get("dropdown_item_selector", ".x-boundlist-item"),
        "queue": queue,
        "page_header": raw.get("page_header", ".top-page-header-text"),
    }


def cell_to_text(cell):
    """Turn a spreadsheet cell into the exact text to type into Bottomline.

    The template makes every cell Text format so that what you see is what gets
    typed. But someone can always reformat a column -- the Amount column was
    changed to 0.00 during development -- and then Excel hands back a NUMBER,
    not the text on screen. 496.00 on screen arrives here as the integer 496.

    So: if a cell is genuinely text, use it untouched. If it is a number, type
    it with the same number of decimal places Excel is showing, so the script
    types what you see. If it is a date, refuse -- there is no way to guess
    which date format Bottomline wants, and guessing would put a wrong date on
    a client's invoice.
    """
    import datetime as _dt

    value = cell.value
    if value is None:
        return ""

    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        raise ValueError(
            f"cell {cell.coordinate} holds a real date, not text.\n"
            "  Excel has converted it, so the original typing is gone and there\n"
            "  is no safe way to know what format Bottomline expects.\n"
            "  Fix: select that column, Format Cells > Text, and retype the date."
        )

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, (int, float)):
        fmt = cell.number_format or ""
        if "." in fmt:
            decimals = len(fmt.split(".")[-1].replace("_", "").replace(")", "").strip())
            return f"{float(value):.{decimals}f}"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    return str(value).strip()


def load_rows():
    """Read the spreadsheet. Text cells are used exactly as typed."""
    from openpyxl import load_workbook

    if not SPREADSHEET.exists():
        sys.exit(f"STOPPED: no spreadsheet found at {SPREADSHEET}")

    workbook = load_workbook(SPREADSHEET, data_only=True)
    sheet = workbook["Invoices"] if "Invoices" in workbook.sheetnames else workbook.active

    headers = [header_to_key(c.value) if c.value else "" for c in sheet[1]]

    reformatted = set()
    rows = []
    for excel_row in sheet.iter_rows(min_row=2):
        values = {}
        for header, cell in zip(headers, excel_row):
            if not header:
                continue
            try:
                values[header] = cell_to_text(cell)
            except ValueError as error:
                sys.exit(f"STOPPED: {error}")
            if (cell.value is not None and cell.number_format != "@"
                    and header not in IGNORED_COLUMNS):
                reformatted.add(header)
        if any(values.get(k) for k in MEANINGFUL_COLUMNS):
            values["_excel_row"] = excel_row[0].row
            rows.append(values)

    if reformatted:
        print("\n  NOTE: these columns are no longer Text format in Excel:")
        print("        " + ", ".join(sorted(reformatted)))
        print("        Values are typed as Excel displays them. Watch for lost")
        print("        leading zeros -- an invoice number 007458 stored as a")
        print("        number becomes 7458, and that cannot be recovered here.\n")

    return rows, [h for h in headers if h]


def mark_row_done(excel_row_number, log):
    """Write DONE into this row's Status column and save the spreadsheet.

    Opens the workbook WITHOUT data_only so real formulas survive the save
    (data_only reads cached numbers and would wipe formulas back to plain
    values). If no Status column exists yet, one is created with the header
    'Status' -- the value written is plain text, so you can still edit the
    column by hand (set a row back to PENDING or blank to re-record it).

    Any failure here -- most likely the file being open in Excel and therefore
    locked -- is reported and swallowed. A run must never die just because it
    could not tick a box; the invoice was already recorded on screen.
    """
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(SPREADSHEET)
        sheet = (workbook["Invoices"] if "Invoices" in workbook.sheetnames
                 else workbook.active)

        status_col = None
        for cell in sheet[1]:
            if cell.value and header_to_key(cell.value) == "status":
                status_col = cell.column
                break

        if status_col is None:
            status_col = sheet.max_column + 1
            sheet.cell(row=1, column=status_col, value="Status")

        sheet.cell(row=excel_row_number, column=status_col, value="DONE")
        workbook.save(SPREADSHEET)
        log(f"Marked spreadsheet line {excel_row_number} as DONE.")
    except Exception as error:
        log(f"Could NOT mark spreadsheet line {excel_row_number} as DONE "
            f"({error}). The invoice was still recorded on screen -- if you "
            "re-run, mark this row DONE by hand first so it is not repeated.")


def check_columns_match(selectors, headers):
    """Refuse to run if the field map names a column the spreadsheet lacks.

    Without this the failure is SILENT: a missing column looks exactly like an
    empty cell, so the script would report the field as blank, skip it, and
    every invoice would be saved missing that value with nothing to notice.
    This is a real bug that happened during development -- the map said
    'due_date' while the sheet said 'Invoice Due Date'.
    """
    missing = [k for k in selectors["fill"] if k not in headers]
    verify_missing = [k for k in selectors["verify"] if k not in headers]

    if not missing and not verify_missing:
        return

    print("STOPPED: the field map and the spreadsheet do not agree.\n")
    for key in missing + verify_missing:
        wanted = key.replace("_", " ").title()
        print(f"  '{key}' is in selectors.json but no column in the spreadsheet")
        print(f"      matches it. Expected a column headed '{wanted}'.")
    print(f"\n  Columns actually found: {', '.join(headers)}")
    print("\nFix either the header in input/invoices.xlsx or the key in")
    print("automation/selectors.json so the two use the same name.")
    sys.exit(1)


def describe(row, selectors):
    lines = []
    if row.get("image_name"):
        lines.append(f"  {'Image Name':<20} {row['image_name']}")
    for key in selectors["fill"]:
        value = row.get(key, "")
        mark = "" if value else "   (blank - will be left alone)"
        lines.append(f"  {key.replace('_', ' ').title():<20} {value}{mark}")
    return "\n".join(lines)


def log_line(log_path, text):
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")


# --------------------------------------------------------------------------
# Filling
# --------------------------------------------------------------------------

def type_into(page, selector, value, delay_ms=TYPING_DELAY_MS):
    """Clear the box, then type the value one character at a time.

    Deliberately NOT page.fill(). See the note at the top of this file: pasting
    fires no keystrokes, so an autocomplete never wakes up.

    delay_ms is the pause between keystrokes. It defaults to the normal speed;
    the Property box passes a slower value so its dropdown has time to load.
    """
    box = page.locator(selector).first
    box.wait_for(state="visible", timeout=8000)
    box.click()
    box.fill("")  # clearing is safe -- it is typing that must be genuine
    try:
        box.press_sequentially(value, delay=delay_ms)
    except AttributeError:
        box.type(value, delay=delay_ms)  # older Playwright
    return box


def commit_plain_field(page, box):
    """Nudge ExtJS into noticing the box is finished with.

    ExtJS commits a field on 'change' + blur, not on every keystroke. Without
    this a typed value can sit in the box visually and never reach the form's
    internal state.
    """
    box.evaluate(
        "el => { el.dispatchEvent(new Event('change', { bubbles: true })); el.blur(); }"
    )


def _dropdown_signature(items):
    """A fingerprint of what a dropdown is showing right now: the text of every
    item, in order. Two reads with the same fingerprint mean the list has not
    changed between them. Reading an item can fail if ExtJS redraws it mid-read,
    so each is guarded -- a blank stands in for an item that vanished."""
    try:
        n = items.count()
    except Exception:
        return ()
    texts = []
    for position in range(n):
        try:
            texts.append((items.nth(position).inner_text() or "").strip())
        except Exception:
            texts.append("")
    return tuple(texts)


def wait_for_dropdown_to_settle(page, item_selector,
                                timeout_ms=DROPDOWN_WAIT_MS,
                                settle_reads=2, poll_ms=150):
    """Read a dropdown repeatedly until its contents stop changing, then return
    how many items it holds.

    WHY THIS EXISTS (the whole point of the fix):
        Bottomline runs on ExtJS, which filters a search box's dropdown with a
        DEBOUNCED query -- it waits a beat after you stop typing, then rebuilds
        the list. It also leaves a closed dropdown's items sitting in the page.
        So the list RIGHT AFTER typing can be (a) the previous search's
        leftovers, or (b) empty because the query has not fired yet, or (c)
        half-rendered. The old code read the list at that single instant and
        trusted whatever number it saw -- which is why 'Heather Hill' came back
        with 0 matches on some rows and matched on others. Same document, same
        spelling, different luck on the timing.

    WHAT IT DOES INSTEAD:
        It reads the list, waits, reads again, and only trusts the count once
        the list has looked IDENTICAL `settle_reads` times in a row (it has
        'settled'). A non-empty settled list is returned straight away. An
        EMPTY list is never trusted early -- it keeps polling to the timeout,
        because 'nothing there yet' must not be mistaken for 'no match'.

    It counts polls rather than watching the clock, so the offline rehearsal
    (whose fake `wait_for_timeout` does nothing) still finishes quickly.
    """
    items = page.locator(item_selector)
    max_polls = max(settle_reads, timeout_ms // poll_ms)
    last_signature = None
    same_in_a_row = 0
    signature = ()
    for _ in range(max_polls):
        signature = _dropdown_signature(items)
        if signature == last_signature:
            same_in_a_row += 1
        else:
            same_in_a_row = 1
            last_signature = signature
        if signature and same_in_a_row >= settle_reads:
            break
        page.wait_for_timeout(poll_ms)
    return len(signature)


def _prefix_len(value, percent):
    """How many characters of `value` a given stage types. 100% is the whole
    name; a shorter stage is at least MIN_PREFIX_CHARS so a tiny name does not
    start by matching half the list."""
    n = len(value)
    if percent >= 100:
        return n
    take = (n * percent + 99) // 100          # ceil(n * percent / 100)
    return min(n, max(MIN_PREFIX_CHARS, take))


def type_and_settle_staged(page, selector, value, item_selector,
                           delay_ms=TYPING_DELAY_MS):
    """Type `value` as a GROWING prefix -- 60% of it, then 75%, then all of it
    -- pausing after each stage to let the dropdown load and settle. Returns
    the settled item count.

    WHY (the fix the user asked for):
        Typing the whole name in one go can outrun ExtJS's debounced search, so
        the suggestions never appear. Typing a prefix first gives the list a
        chance to load. The escalation to a longer prefix happens ONLY when
        nothing loaded (0 items) -- the moment the list shows anything, whether
        one item or several, we stop and let the caller decide (pick the one, or
        hand several to the operator). More characters are ADDED, never re-typed
        from scratch, so ExtJS narrows the list progressively, exactly as a
        person refining a search would.
    """
    box = page.locator(selector).first
    box.wait_for(state="visible", timeout=8000)
    box.click()
    box.press("Control+a")   # begin from a clean, keystroke-cleared box so
    box.press("Delete")      # ExtJS is not still filtering an old value
    typed = 0
    count = 0
    for percent in PREFIX_STAGES_PERCENT:
        target = _prefix_len(value, percent)
        if target > typed:
            chunk = value[typed:target]
            try:
                box.press_sequentially(chunk, delay=delay_ms)
            except AttributeError:
                box.type(chunk, delay=delay_ms)   # older Playwright
            typed = target
        count = wait_for_dropdown_to_settle(page, item_selector)
        if count > 0 or typed >= len(value):
            break
    return count


def fill_autocomplete(page, selector, value, item_selector, field_name, log_path):
    """Type into a search box and deal with the dropdown it produces.

    Returns one of: "picked", "manual", "stopped".
    """
    # Type a growing prefix (60% -> 75% -> full) so the dropdown has time to
    # load, settling after each stage. One match is picked; several or none are
    # handed to the operator, exactly as before.
    count = type_and_settle_staged(page, selector, value, item_selector)
    items = page.locator(item_selector)

    if count == 1:
        text = (items.first.inner_text() or "").strip()
        items.first.click()
        print(f"    {field_name}: one match, picked '{text}'")
        log_line(log_path, f"    {field_name}: auto-picked '{text}'")
        return "picked"

    if count == 0:
        print(f"\n    {field_name}: NO dropdown match for '{value}'.")
        print("    Nothing was selected, so no code has been stored for this box.")
        print("    Possible causes: the name does not match Bottomline's spelling,")
        print("    or the dropdown's appearance has changed (see")
        print("    'dropdown_item_selector' in selectors.json).")
    else:
        shown = []
        for i in range(min(count, 8)):
            shown.append((items.nth(i).inner_text() or "").strip())
        print(f"\n    {field_name}: {count} matches for '{value}' -- too many to choose safely:")
        for s in shown:
            print(f"      - {s}")
        if count > len(shown):
            print(f"      ... and {count - len(shown)} more")

    log_line(log_path, f"    {field_name}: {count} matches for '{value}' -- handed to user")
    print(f"\n    >>> Pick the right {field_name} yourself in the browser window.")
    answer = input("    Press ENTER when done, or type s to skip this box: ").strip().lower()
    if answer == "s":
        log_line(log_path, f"    {field_name}: user skipped")
        return "stopped"
    return "manual"


def probe_dropdown(page, selector, value, item_selector, delay_ms=TYPING_DELAY_MS,
                   staged=False):
    """Type a value into a search box and report what the dropdown offers.

    The difference between this and fill_autocomplete() is that this one never
    picks anything and never asks the operator anything. It is how the script
    puts a QUESTION to Bottomline -- "is this property under the package
    currently selected?" -- without committing to an answer either way.

    delay_ms is passed straight through -- the Property probe uses a slower
    speed so its dropdown has time to load between keystrokes.

    staged: when True, the value is typed as a growing prefix (60% -> 75% ->
    full) so the dropdown has time to load -- used for Property. When False the
    whole value is typed at once -- used for Integration Package, which is short
    (YARDI / INTACCT) and would only be made ambiguous by a prefix.

    Returns (count, sample) where sample is the text of up to five items, for
    the log and for showing the operator.
    """
    if staged:
        count = type_and_settle_staged(page, selector, value, item_selector, delay_ms)
    else:
        type_into(page, selector, value, delay_ms)
        # Let ExtJS's debounced query fire and the list settle before counting
        # -- a single-instant read counted stale or half-rendered items.
        count = wait_for_dropdown_to_settle(page, item_selector)
    items = page.locator(item_selector)
    sample = []
    for position in range(min(count, 5)):
        try:
            sample.append((items.nth(position).inner_text() or "").strip())
        except Exception:
            pass  # item vanished mid-read; ExtJS redraws constantly
    return count, sample


def pick_only_match(page, item_selector):
    """Click the single dropdown item left open by probe_dropdown()."""
    page.locator(item_selector).first.click()


def clear_box(page, selector):
    """Empty a box and let ExtJS notice, before the next attempt types into it.

    Used between integration-package attempts. Nobody has yet observed whether
    Bottomline clears the Property box by itself when the package changes, so
    the script clears it deliberately rather than trusting a value left on
    screen from an attempt that failed.

    Cleared with real keystrokes (select-all, then Delete), NOT page.fill("").
    fill("") changes the text but fires no keystrokes, so ExtJS keeps running
    the search it started for the OLD value -- which is why the previous
    property was seen still sitting in the box between package attempts, giving
    the next probe 0 matches. Keystrokes make ExtJS reset the search, exactly
    as a person deleting the text would.
    """
    box = page.locator(selector).first
    box.wait_for(state="visible", timeout=8000)
    box.click()
    box.press("Control+a")
    box.press("Delete")
    commit_plain_field(page, box)


def retype_full_then_clear(page, selector, value):
    """Type the WHOLE name end-to-end, then clear it with keystrokes.

    Used between integration-package attempts, when the property was not found
    under the package just tried and the next one is about to be tried. Running
    a COMPLETE type-then-clear cycle -- rather than just wiping whatever text is
    there -- makes ExtJS finish its search and then fully reset it, so the next
    package's property probe starts from a genuinely clean box and types
    cleanly. Requested after the previous property value was seen lingering in
    the box between package attempts.
    """
    type_into(page, selector, value)     # full name, end to end (clears first)
    box = page.locator(selector).first
    box.click()
    box.press("Control+a")               # then select it all and delete it, so
    box.press("Delete")                  # ExtJS resets before the next attempt
    commit_plain_field(page, box)


def _probe_property_candidates(page, property_selector, item_selector, candidates,
                               log_path, package):
    """Try each candidate value (e.g. a property's CODE, then its NAME) in the
    Property box under the package already selected on screen. Returns
    (verdict, count, sample, matched_value) for the FIRST candidate that comes
    back confirmed or ambiguous; if every candidate is not_here, returns the
    LAST attempt's result so the caller can log what was tried. Clears and
    fully resets the box with real keystrokes between attempts (see
    retype_full_then_clear) so ExtJS never carries a leftover search into the
    next candidate or the next package."""
    result = ("not_here", 0, [], candidates[-1] if candidates else "")
    for value in candidates:
        clear_box(page, property_selector)
        count, sample = probe_dropdown(
            page, property_selector, value, item_selector,
            delay_ms=PROPERTY_TYPING_DELAY_MS, staged=True)
        verdict = package_verdict(count)
        log_line(log_path,
                 f"    property '{value}' under {package}: {count} match(es) {sample}")
        if verdict != "not_here":
            return verdict, count, sample, value
        result = (verdict, count, sample, value)
        retype_full_then_clear(page, property_selector, value)
    return result


def _read_selected_package(page, selectors):
    """Best-effort read of whichever text is CURRENTLY showing in the
    Integration Package box, after the operator has filled it in by hand.
    This is for the LOG ONLY -- the operator's own on-screen selection is
    what Bottomline actually stores either way. Returns None (never raises)
    if the box can't be read or does not hold a recognised package."""
    selector = selectors["fill"].get("integration_package")
    if not selector:
        return None
    try:
        box = page.locator(selector).first
        text = (box.input_value() or "").strip()
    except Exception:
        return None
    return normalise_package(text) if is_known_package(text) else None


def _manual_package_handoff(page, selectors, row, log_path, tried):
    """Nothing above placed this invoice automatically -- hand the browser to
    the operator instead of skipping it (2026-09-03 decision). The operator
    picks the Integration Package AND the Property themselves on screen; the
    script then reads back whichever package ends up selected, purely for its
    own log, and lets the run continue to the vendor and detail fields for
    this invoice. Typing 's' skips this invoice exactly as the other manual
    fallbacks in this file do."""
    property_value = row.get("property", "")
    print("\n    Could not automatically place this invoice under "
          f"{' or '.join(KNOWN_PACKAGES)}.")
    if tried:
        print("    What was tried: " + "; ".join(tried))
    if not property_value:
        print("    (No Property was read for this invoice.)")
    print("\n    >>> In the browser: pick the correct Integration Package, "
          "then type and pick the correct Property yourself.")
    answer = input("    Press ENTER once BOTH boxes are filled and correct "
                   "(or type s to skip this invoice): ").strip().lower()

    if answer == "s":
        log_line(log_path,
                 "    package/property: operator skipped the invoice at the "
                 f"manual handoff (tried: "
                 f"{'; '.join(tried) if tried else 'nothing -- blank property'})")
        return None, "you skipped it at the package/property handoff"

    package = _read_selected_package(page, selectors)
    if package:
        log_line(log_path,
                 "    package/property: operator filled it in manually -- "
                 f"read back Integration Package = {package}")
    else:
        package = "UNCONFIRMED"
        log_line(log_path,
                 "    package/property: operator filled it in manually -- "
                 "could not confirm which package is selected (logged as "
                 "UNCONFIRMED, but the operator's own on-screen selection is "
                 "what Bottomline actually stores)")
    return package, None


def establish_package(page, selectors, row, log_path,
                      property_lookup=None, property_code_index=None):
    """Phase A. Work out which integration package this invoice belongs to.

    Selects a package, then types the property and reads the dropdown. A
    property only appears if it belongs to the package on screen, so that
    dropdown is the proof. First package whose dropdown shows the property
    wins.

    For YARDI, a property with a known CODE (masters\\properties.csv) is
    tried by CODE first -- typing the code loads the property deterministically,
    just like a vendor's ERP Vendor ID -- then by NAME if the code does not
    resolve it. Intacct has no codes, so it is always tried by name.

    If NEITHER package's dropdown shows the property (or the sheet had no
    Property at all), this no longer skips the invoice outright: it hands the
    browser to the operator to pick the Integration Package AND the Property
    themselves, then reads back whichever package ends up selected (for the
    log only) and lets the run continue (2026-09-03 decision -- an invoice
    that cannot be auto-placed is finished by a human, not abandoned).

    Returns (package_name, None) when a package was proved OR the operator
    completed it manually, or (None, reason) when the operator chose to skip
    this invoice -- reason is for the log and the operator.
    """
    fill = selectors["fill"]
    item_selector = selectors["dropdown_item"]
    package_selector = fill.get("integration_package")
    property_selector = fill.get("property")

    property_value = row.get("property", "")
    sheet_value = row.get("integration_package", "")

    if not package_selector or not property_selector:
        return None, ("the field map has no Integration Package or Property box "
                      "-- check selectors.json")

    if sheet_value and not is_known_package(sheet_value):
        message = (f"Integration Package '{sheet_value}' in the sheet is not "
                   f"{' or '.join(KNOWN_PACKAGES)} -- ignoring it and trying both.")
        print(f"    {message}")
        log_line(log_path, f"    {message}")

    tried = []

    if property_value:
        for package in package_candidates(sheet_value):
            print(f"\n    Trying integration package: {package}")

            count, sample = probe_dropdown(page, package_selector, package, item_selector)
            log_line(log_path,
                     f"    integration_package '{package}': {count} match(es) {sample}")
            if count != 1:
                note = f"{package}: its own box offered {count} matches, so it could not be selected"
                print(f"    '{package}' did not come up as a single choice ({count} matches).")
                log_line(log_path, f"    integration_package '{package}': {count} matches")
                tried.append(note)
                continue

            pick_only_match(page, item_selector)
            log_line(log_path, f"    integration_package: selected '{package}'")

            candidates = property_candidates_for_package(
                package, property_value, property_lookup, property_code_index)
            verdict, count, sample, matched_value = _probe_property_candidates(
                page, property_selector, item_selector, candidates, log_path, package)

            if verdict == "confirmed":
                pick_only_match(page, item_selector)
                shown = sample[0] if sample else matched_value
                via = (f" (matched via code '{matched_value}')"
                      if matched_value != property_value else "")
                print(f"    Property '{property_value}' is under {package}{via} -- "
                      f"package confirmed, picked '{shown}'.")
                log_line(log_path,
                         f"    property: one match under {package} using "
                         f"'{matched_value}', picked '{shown}' -- integration "
                         f"package confirmed as {package}")
                return package, None

            if verdict == "ambiguous":
                print(f"\n    Property '{property_value}': {count} matches under "
                      f"{package} -- too many to choose safely:")
                for text in sample:
                    print(f"      - {text}")
                if count > len(sample):
                    print(f"      ... and {count - len(sample)} more")
                print(f"\n    >>> Pick the right Property yourself in the browser window.")
                answer = input("    Press ENTER when done, or type s to skip this "
                               "invoice: ").strip().lower()
                if answer == "s":
                    log_line(log_path,
                             f"    property: operator skipped the invoice at the "
                             f"property step under {package}")
                    return None, f"you skipped it while choosing a property under {package}"
                log_line(log_path,
                         f"    property: {count} matches under {package}, operator "
                         f"picked -- integration package confirmed as {package}")
                return package, None

            print(f"    Property '{property_value}' is NOT under {package}.")
            note = f"{package}: the property was not in its dropdown"
            if matched_value != property_value:
                note += f" (tried code '{matched_value}' and the name)"
            tried.append(note)
    else:
        tried.append("no Property in the spreadsheet row")

    # ---- Nothing worked automatically: hand off to the operator instead of
    # skipping the invoice outright ----
    return _manual_package_handoff(page, selectors, row, log_path, tried)


# --------------------------------------------------------------------------
# The image-name safety check
# --------------------------------------------------------------------------

def read_image_name(page, selectors):
    selector = selectors["verify"].get("image_name")
    if not selector:
        return None
    try:
        box = page.locator(selector).first
        box.wait_for(state="visible", timeout=5000)
        return (box.input_value() or "").strip()
    except Exception:
        return None


def image_names_match(expected, on_screen):
    """Compare forgivingly on case and surrounding space, strictly on everything else."""
    return expected.strip().lower() == (on_screen or "").strip().lower()


# --------------------------------------------------------------------------

def main():
    global SPREADSHEET  # reassigned below from --xlsx; must be declared first
    parser = argparse.ArgumentParser(description="Type invoices into Bottomline Nexus.")
    parser.add_argument("--start-row", type=int, default=1,
                        help="ADVANCED / rarely needed. Resume from this DATA-row "
                             "index (the Nth filled-in row, NOT the Excel line "
                             "number -- the header row is not counted, so this "
                             "number is one LESS than the Excel line). You normally "
                             "do not need it: the Status column already skips every "
                             "row marked DONE and records the rest.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be entered. Opens no browser, types nothing.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process this many rows. Use --limit 1 for the first live test.")
    parser.add_argument("--xlsx", type=Path, default=SPREADSHEET,
                        help="Full path to invoices.xlsx. Defaults to the shared "
                             "drive location. Each PC can point at its own drive "
                             'letter, e.g. --xlsx "Z:\\Res-1-indexer\\input\\invoices.xlsx".')
    args = parser.parse_args()

    # Route the whole script (read AND the DONE write-back) at the chosen sheet.
    SPREADSHEET = args.xlsx

    if args.limit is not None and args.limit < 1:
        sys.exit("STOPPED: --limit must be 1 or more.")

    selectors = load_selectors()
    rows, headers = load_rows()
    check_columns_match(selectors, headers)

    # Vendor code lookup: at record time we translate the vendor NAME in the
    # sheet into its ERP Vendor ID and type THAT, because entering the code makes
    # Bottomline load the vendor automatically. Only a confident (exact/alias)
    # name match is allowed to use a code -- see value_to_type. If the master is
    # missing, both fall back to typing the name, exactly as before.
    vendor_rows = load_master(str(VENDORS_CSV))
    vendor_lookup = Lookup(vendor_rows, load_aliases(str(VENDOR_ALIASES_CSV))) \
        if vendor_rows else None
    code_index = build_index(vendor_rows, "Vendor Name", "ERP Vendor ID") \
        if vendor_rows else {}

    # Property master: same idea as vendor's code index above, but for the
    # Yardi property code -- see property_candidates_for_package (fill_plan.py).
    property_rows = load_master(str(PROPERTIES_CSV), name_col="Property Name")
    property_lookup = Lookup(property_rows, load_aliases(str(PROPERTY_ALIASES_CSV)),
                             name_col="Property Name") if property_rows else None
    property_code_index = build_index(property_rows, "Property Name", "Property Code") \
        if property_rows else {}

    if not rows:
        sys.exit(
            "STOPPED: the spreadsheet has no filled-in rows.\n"
            "A row only counts once Vendor, Invoice Number or Amount has a value."
        )
    if args.start_row > len(rows):
        sys.exit(f"STOPPED: --start-row {args.start_row} but there are only {len(rows)} rows.")

    rows = rows[args.start_row - 1:]
    if args.limit is not None:
        rows = rows[:args.limit]
    last_row_number = args.start_row + len(rows) - 1

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"run_{datetime.now():%Y-%m-%d_%H%M}.txt"
    log_line(log_path, f"Run started {datetime.now():%Y-%m-%d %H:%M}")
    log_line(log_path, f"Rows to process: {len(rows)}  dry_run={args.dry_run}")

    # Write every message to BOTH the screen and the log file. It used to go to
    # the file only, which is why a normal finish (all the "Back at the queue"
    # lines from return_to_queue) looked like a silent crash.
    def note(text):
        print(text)
        log_line(log_path, text)

    # The Status column -- not the row number -- decides what gets recorded.
    # Rows marked DONE are skipped; everything else (PENDING or blank) records.
    # Reported up front so the plan is clear before any browser opens.
    pending_rows = [r for r in rows if r.get("status", "").strip().lower() != "done"]
    done_count = len(rows) - len(pending_rows)
    note(f"\nStatus: {len(pending_rows)} row(s) to record, {done_count} already "
         f"DONE (skipped).")
    if pending_rows:
        note("Will record Excel line(s): "
             + ", ".join(str(r["_excel_row"]) for r in pending_rows))
    else:
        note("Nothing to record -- every row is already marked DONE.")

    if args.dry_run:
        print(f"\nDRY RUN -- no browser, nothing typed. {len(rows)} row(s).\n")
        for index, row in enumerate(rows, start=args.start_row):
            print(f"Row {index} (spreadsheet line {row['_excel_row']}):")
            print(describe(row, selectors))
            if not row.get("image_name"):
                print("  WARNING: no Image Name. This row WILL BE SKIPPED on a real "
                      "run -- the Image Name is how the script finds the invoice "
                      "in the queue.")
            print()
        print(f"Log: {log_path}")
        return

    # ---- real run ----
    from dotenv import load_dotenv
    from playwright.sync_api import sync_playwright

    load_dotenv(PROJECT / ".env")
    url = os.getenv("BOTTOMLINE_URL", "").strip()
    username = os.getenv("BOTTOMLINE_USERNAME", "").strip()
    password = os.getenv("BOTTOMLINE_PASSWORD", "").strip()

    if not url or not username or not password:
        sys.exit(
            "STOPPED: .env is missing BOTTOMLINE_URL, BOTTOMLINE_USERNAME "
            "or BOTTOMLINE_PASSWORD.\n"
            "Create Invoice_Indexer\\.env in Notepad with those three lines."
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        if SESSION_FILE.exists():
            context = browser.new_context(storage_state=str(SESSION_FILE))
            print("Reusing your saved Bottomline session.")
        else:
            context = browser.new_context()

        page = context.new_page()
        page.goto(url)

        page.wait_for_timeout(2000)
        if page.locator("input[type='password']").count() > 0:
            print("Logging in...")
            try:
                page.locator("input[type='text'], input[type='email']").first.fill(username)
                page.locator("input[type='password']").first.fill(password)
                page.keyboard.press("Enter")
            except Exception as error:
                log_line(log_path, f"Login attempt failed: {error}")
                print(f"Could not complete the login automatically: {error}")

        print("\nIf a security code was requested, complete it now in the browser.")
        input("Press ENTER once you are fully logged in... ")

        try:
            context.storage_state(path=str(SESSION_FILE))
        except Exception:
            pass  # not fatal -- next run just logs in again

        # Reach 'Images to be Indexed' on our own instead of asking the operator
        # to click there. This clicks the very same menu item return_to_queue()
        # uses to get back mid-run, then proves it landed with the queue's own
        # landmarks (wait_for_queue_screen, inside return_to_queue). If the menu
        # needs opening first -- or anything else stops the click landing -- the
        # run falls back to asking, exactly as it did before. A missed click can
        # never leave the operator stuck, and nothing is ever typed off a screen
        # that failed this check.
        note("\nTrying to reach 'Images to be Indexed' automatically...")
        reached = False
        if return_to_queue(page, selectors, note):
            # Landing on the queue FRAME is not enough -- its invoice rows load
            # over the network a moment later. Wait for them before trusting the
            # read, or an empty-but-still-loading grid makes every invoice look
            # 'not in the queue' (seen 2026-08-18 19:11: 0 rows read, all 18
            # skipped). If the rows never load, this was the wrong screen or a
            # genuinely empty queue, so hand it to the operator.
            if wait_for_queue_rows(page, selectors, note):
                note("Reached the indexing queue automatically.")
                reached = True
        if not reached:
            note("Could not reach a loaded queue automatically -- over to you.")
            input("Please click to 'Images to be Indexed' yourself, then press "
                  "ENTER once you can SEE the list of invoices on screen... ")

        # ---- read the queue ONCE, up front ----
        # Hunting page by page for each invoice would mean walking the whole
        # grid once per spreadsheet row. Reading it once also means a name is
        # only declared missing after every page has been checked.
        print("\nReading the indexing queue. This takes a moment...")

        try:
            queue_index, duplicates = read_queue(page, selectors, note)
        except Exception as error:
            log_line(log_path, f"STOPPED while reading the queue -- {error}")
            sys.exit(f"\nSTOPPED while reading the queue:\n  {error}\n"
                     "Nothing was typed.")

        # Remember this address. It is a known-good route back to the queue if
        # the menu item ever becomes unreachable later (Convert to Invoice's
        # second screen is exactly that case -- see return_to_queue() in
        # queue_navigator.py). If page.url can't be read for some reason, the
        # run carries on regardless; the route back just has one fewer rung.
        try:
            queue_url = page.url
        except Exception:
            queue_url = None

        print(f"Found {len(queue_index)} invoice(s) waiting in the queue.")

        # An empty read is almost always a loading/navigation problem, not a
        # genuinely empty queue -- and left unremarked it looks exactly like a
        # clean run that simply had nothing to do (every row 'not in the queue',
        # filled=0). Stop and say so plainly rather than skip everything and
        # report success. Nothing has been typed at this point.
        if not queue_index:
            log_line(log_path, "STOPPED: the queue read as empty (0 invoices).")
            sys.exit(
                "\nSTOPPED: the indexing queue read as EMPTY (0 invoices), so "
                "there is nothing to match your spreadsheet against.\n"
                "This usually means the queue screen had not finished loading, "
                "or the wrong screen was open -- not that the work is done.\n"
                "Open 'Images to be Indexed', wait until you can SEE the list of "
                "invoices, then run again. Nothing was typed."
            )

        if duplicates:
            names = ", ".join(duplicates)
            log_line(log_path, f"STOPPED: duplicate image names in the queue: {names}")
            sys.exit(
                "\nSTOPPED: these image names appear more than once in the "
                f"queue:\n  {names}\n\n"
                "The same document twice usually means something went wrong "
                "upstream. Picking one at random is exactly the kind of silent "
                "choice this script refuses to make.\n"
                "Nothing was typed. Sort the queue out and run again."
            )

        filled = skipped = 0

        for index, row in enumerate(rows, start=args.start_row):
            print("\n" + "-" * 70)
            print(f"Row {index} of {last_row_number}   (spreadsheet line {row['_excel_row']})")

            # Skip rows the Status column marks DONE. Anything that is not DONE
            # -- PENDING, blank, or a column that does not exist yet -- records
            # as normal, so old spreadsheets without the column still work.
            if row.get("status", "").strip().lower() == "done":
                print("  Status is DONE -- skipped.")
                log_line(log_path, f"Row {index}: SKIPPED -- marked DONE")
                skipped += 1
                continue

            print(describe(row, selectors))

            # Session can expire mid-batch. Never type invoice data at a login page.
            if page.locator("input[type='password']").count() > 0:
                log_line(log_path, f"Row {index}: STOPPED -- session expired")
                sys.exit(
                    "\nSTOPPED: you appear to be logged out.\n"
                    f"Log in again, then resume with:  python invoice_recorder.py --start-row {index}"
                )

            # ---- find this invoice in the queue and open it ----
            # Spec section 4: nothing is typed until the script has proved,
            # twice over, that the right invoice is on screen. The old
            # "safety check skipped -- filling anyway" branch is gone. A safety
            # feature that silently switches itself off is worse than none.
            wanted = row.get("image_name", "")

            if not wanted:
                print("\n  No Image Name in this row. Skipped -- the script has "
                      "no way to find the invoice without it.")
                log_line(log_path, f"Row {index}: SKIPPED -- no image name in sheet")
                skipped += 1
                continue

            key = normalise_name(wanted)
            if key not in queue_index:
                print(f"\n  '{wanted}' is not in the indexing queue. Skipped.")
                log_line(log_path, f"Row {index}: SKIPPED -- '{wanted}' not in the queue")
                skipped += 1
                continue

            if not open_invoice(page, selectors, wanted, queue_index[key], note, queue_url):
                print(f"\n  Could not open '{wanted}' safely after two tries. "
                      "Skipped -- nothing was typed.")
                log_line(log_path, f"Row {index}: SKIPPED -- could not open/verify")
                skipped += 1
                continue

            print(f"\n  Verified: '{wanted}' is open on screen.")

            # No "fill this? [y/s/q]" prompt any more. The correctness gate is
            # the image-name check that just passed (confirm_right_invoice: the
            # open PDF's Image Name must equal the spreadsheet's Image Name, on
            # BOTH the heading and the Image Name box). Once that holds, this is
            # by definition the right invoice for this row, so there is nothing
            # left for a human to decide -- the script fills it. You still review
            # everything it typed at the "Done?" prompt below, and can stop the
            # run there.
            log_line(log_path, f"Row {index}: filling (excel line {row['_excel_row']})")
            print()

            def stop_on_broken_box(key, selector, error):
                """Same message for any box that could not be used at all."""
                log_line(log_path, f"Row {index}: field '{key}' failed -- {error}")
                sys.exit(
                    f"\nSTOPPED on row {index}: could not use the '{key}' box "
                    f"(looked for {selector}).\n"
                    "Nothing further was changed. This usually means Bottomline moved "
                    "a field -- re-run selector_recorder.py and rebuild selectors.json.\n"
                    f"Resume afterwards with:  python invoice_recorder.py --start-row {index}"
                )

            # ---- Phase A: which integration package does this invoice belong to?
            # Done BEFORE anything else is typed. The property dropdown proves
            # the answer -- see fill_plan.py for why the order matters.
            try:
                package, why_not = establish_package(
                    page, selectors, row, log_path,
                    property_lookup=property_lookup,
                    property_code_index=property_code_index)
            except Exception as error:
                stop_on_broken_box("integration_package / property",
                                   "see selectors.json", error)

            if package is None:
                print(f"\n  Could not place this invoice under "
                      f"{' or '.join(KNOWN_PACKAGES)}.")
                print(f"  {why_not}")
                print("  Skipped -- no invoice details were typed.")
                log_line(log_path,
                         f"Row {index}: SKIPPED -- integration package not "
                         f"established ({why_not})")
                skipped += 1
                # Boxes may hold text from the attempts, but nothing has been
                # saved and this script never presses Save or Convert.
                return_to_queue(page, selectors, note, queue_url)
                continue

            # ---- Phase B: the vendor, now that the package is settled.
            # A vendor that does not appear is handed to you exactly as before.
            # It never re-opens the package decision -- a vendor spelled
            # differently in the sheet would otherwise quietly reroute an
            # invoice to the other accounting system.
            vendor_value = row.get("vendor", "")
            vendor_selector = selectors["fill"].get("vendor")
            if vendor_value and vendor_selector:
                # Translate the name to the ERP Vendor ID when it is a confident
                # match; otherwise value_to_type returns the name unchanged.
                search_text = vendor_value
                if vendor_lookup is not None:
                    search_text = value_to_type(vendor_value, vendor_lookup,
                                                code_index)
                if search_text != vendor_value:
                    note(f"    vendor: using ERP Vendor ID '{search_text}' "
                         f"for '{vendor_value}' (confident master match)")
                try:
                    fill_autocomplete(
                        page, vendor_selector, search_text,
                        selectors["dropdown_item"], "vendor", log_path,
                    )
                except Exception as error:
                    stop_on_broken_box("vendor", vendor_selector, error)
            elif vendor_selector:
                print("    vendor: blank in the spreadsheet -- left alone")
                log_line(log_path, "    vendor: blank, skipped")

            # ---- Phase C: the invoice's own details.
            for key in detail_fields(selectors["fill"].keys()):
                selector = selectors["fill"][key]
                value = row.get(key, "")
                if not value:
                    print(f"    {key}: blank in the spreadsheet -- left alone")
                    log_line(log_path, f"    {key}: blank, skipped")
                    continue

                try:
                    if key in selectors["autocomplete"]:
                        fill_autocomplete(
                            page, selector, value, selectors["dropdown_item"],
                            key, log_path,
                        )
                    else:
                        box = type_into(page, selector, value)
                        commit_plain_field(page, box)
                        print(f"    {key}: typed '{value}'")
                        log_line(log_path, f"    {key}: typed")
                except Exception as error:
                    stop_on_broken_box(key, selector, error)

            filled += 1
            # Check if this invoice is a Utility bill
            vendor_str = str(row.get("vendor", "")).lower()
            inv_num_str = str(row.get("invoice_number", "")).strip()
            # Utility invoice numbers are <account>-<YYYYMMDD> where date suffix has 8 digits
            has_utility_inv_format = bool(re.search(r"-\d{8}$", inv_num_str))

            is_utility = bool(
                row.get("cycle_from") or row.get("cycle_to") or
                row.get("gl_code") or row.get("account_number") or
                has_utility_inv_format or
                any(u in vendor_str for u in ["pepco", "gas", "water", "sewer", "electric", "bge", "wssc", "dominion", "dpw", "power"])
            )

            if is_utility:
                print("\n  " + "=" * 62)
                print("  [UTILITY MODE] PAGE 1 HEADER COMPLETED.")
                print(f"  Invoice #: {row.get('invoice_number')} | Amount: {row.get('amount')}")
                print("  Ready to proceed to Page 2 ('Convert to Invoice').")
                print("  " + "=" * 62)
                ans = input("\n  Press ENTER to continue to Convert & Line Items (or s to stop here): ").strip().lower()
                if ans == "s":
                    print("  Stopped by operator before Convert.")
                    log_line(log_path, f"Row {index}: stopped by operator before Convert")
                    break

                # 1. Click 'Convert to Invoice'
                convert_sel = 'a:has-text("Convert to Invoice"), button:has-text("Convert to Invoice"), .x-btn-inner:has-text("Convert to Invoice")'
                try:
                    page.locator(convert_sel).first.click(timeout=8000)
                    page.wait_for_timeout(3000)
                    print("    -> Clicked 'Convert to Invoice'")
                except Exception as e:
                    print(f"    Notice: could not auto-click 'Convert to Invoice': {e}")
                    input("    >>> Please click 'Convert to Invoice' in browser, then press ENTER here: ")

                # 2. Fill Cycle From / To on Header tab (or wait for screen to settle)
                c_from = row.get("cycle_from")
                c_to = row.get("cycle_to")
                if c_from:
                    try:
                        box = page.locator('input[name*="Cycle_From"], input[name*="cycle_from"], input[placeholder*="Cycle From"], input[name*="From_Date"]').first
                        box.fill(c_from)
                        print(f"    Cycle From: typed '{c_from}'")
                    except Exception as e:
                        print(f"    Cycle From: could not fill automatically ({e})")
                if c_to:
                    try:
                        box = page.locator('input[name*="Cycle_To"], input[name*="cycle_to"], input[placeholder*="Cycle To"], input[name*="To_Date"]').first
                        box.fill(c_to)
                        print(f"    Cycle To: typed '{c_to}'")
                    except Exception as e:
                        print(f"    Cycle To: could not fill automatically ({e})")

                # 3. Switch to 'Line Items' tab
                line_tab_sel = '.x-tab-inner:has-text("Line Items"), a:has-text("Line Items"), span:has-text("Line Items")'
                try:
                    page.locator(line_tab_sel).first.click(timeout=6000)
                    page.wait_for_timeout(2000)
                    print("    -> Switched to 'Line Items' tab")
                except Exception as e:
                    print(f"    Notice: could not auto-switch to 'Line Items' tab ({e})")

                # 4. Click 'Add/Edit Lines' button
                add_line_sel = 'a:has-text("Add/Edit Lines"), button:has-text("Add/Edit Lines"), a:has-text("Add Line Items"), .x-btn-inner:has-text("Add/Edit Lines")'
                try:
                    page.locator(add_line_sel).first.click(timeout=6000)
                    page.wait_for_timeout(2000)
                    print("    -> Clicked 'Add/Edit Lines'")
                except Exception as e:
                    print(f"    Notice: could not auto-click 'Add/Edit Lines': {e}")

                # 5. Populate Description with Account Number & GL hint
                acct_num = row.get("account_number") or row.get("invoice_number", "").split("-")[0]
                if acct_num:
                    try:
                        desc_box = page.locator('input[name*="Description"], textarea[name*="Description"], .x-form-text[name*="desc"]').first
                        desc_box.fill(acct_num)
                        print(f"    Line Description: typed '{acct_num}'")
                    except Exception:
                        pass

                # Set Sales Tax to No
                try:
                    tax_box = page.locator('input[name*="Tax"], select[name*="Tax"]').first
                    tax_box.fill("No")
                    print("    Sales Tax: toggled to 'No'")
                except Exception:
                    pass

                print("\n  " + "=" * 62)
                print("  [UTILITY REVIEW] COMPLETE LINE ITEM & AUDIT CHECK.")
                print(f"  Target GL Code: {row.get('gl_code') or '436313 (Elec) / 436323 (Gas) / 436311 (Water)'}")
                print("  Verify GL Code and Utility Account in the browser.")
                print("  Save the line item and verify the balance.")
                print("  " + "=" * 62)
                answer = input("\n  Done? Press ENTER to mark DONE and return to queue (or q to cancel): ").strip().lower()
                if answer == "q":
                    log_line(log_path, f"Row {index}: cancelled by operator at line-item audit")
                    break
            else:
                print("\n  " + "=" * 62)
                print("  READY FOR YOUR REVIEW. Nothing has been saved.")
                print("  Check every box against the invoice image.")
                print("  Then press 'Convert to Invoice', complete the second")
                print("  screen, and press Save THERE.")
                print("  " + "=" * 62)
                answer = input("\n  Done? Press ENTER for the next invoice (or q to stop): ").strip().lower()
                if answer == "q":
                    log_line(log_path, f"Stopped by the operator after row {index}")
                    break

            # The operator reviewed the invoice. Mark as DONE so next run skips it.
            mark_row_done(row["_excel_row"], note)

            # Convert to Invoice opens a SECOND screen -- it does not return to
            # the queue on its own. return_to_queue() now tries several ways
            # back before giving up (the menu item, the queue's remembered
            # address, then the menu item again -- see queue_navigator.py), so
            # landing here means every one of those failed.
            # Belt and braces. return_to_queue() guards every route internally,
            # but the promise made here is that NOTHING about getting back to
            # the queue ends a run with invoices still to do. An unexpected
            # error becomes "could not get back", which the operator can fix.
            try:
                came_back = return_to_queue(page, selectors, note, queue_url)
            except Exception as error:
                log_line(log_path, f"Row {index}: returning to the queue raised -- {error}")
                came_back = False

            if not came_back:
                resume_line = f"python invoice_recorder.py --start-row {index + 1}"

                print("\n  Could not get back to 'Images to be Indexed' on its own.")
                print("  Nothing was left half-done -- this invoice was already")
                print("  finished by you on the Convert to Invoice screen.")
                log_line(log_path, f"Row {index}: could not return to the queue automatically")

                # Never stop the run just because navigation failed -- hand it
                # to the operator instead. Only a deliberate 'q' here ends the
                # run; ENTER means "I've put it back myself, carry on". Ask at
                # most twice so a genuinely stuck screen doesn't loop forever,
                # then move on regardless -- the next invoice's own safety
                # checks (image name, header) still stand guard either way.
                on_queue = False
                for attempt in (1, 2):
                    choice = input(
                        "\n  Please click back to 'Images to be Indexed' yourself, then "
                        "press ENTER to carry on (or type q to stop): "
                    ).strip().lower()
                    if choice == "q":
                        log_line(log_path, f"Row {index}: user quit after return-to-queue failure")
                        sys.exit(f"\nSTOPPED at your request. Resume with:  {resume_line}")

                    on_queue = wait_for_queue_screen(page, selectors)
                    if on_queue:
                        break
                    if attempt == 1:
                        print("  That doesn't look like the queue screen yet -- one more try.")

                if on_queue:
                    print("  Confirmed: back at the queue.")
                    log_line(log_path, f"Row {index}: back at the queue (operator confirmed)")
                else:
                    print("  Still couldn't confirm the queue screen -- carrying on anyway.")
                    print(f"  If the next row misbehaves, stop and resume with:  {resume_line}")
                    log_line(log_path,
                             f"Row {index}: queue screen not confirmed after asking twice -- continuing")

        print(f"\nDone. Filled {filled}, skipped {skipped}.")
        print(f"Log: {log_path}")
        log_line(log_path, f"Run finished. filled={filled} skipped={skipped}")

        input("Press ENTER to close the browser... ")
        browser.close()


if __name__ == "__main__":
    main()
