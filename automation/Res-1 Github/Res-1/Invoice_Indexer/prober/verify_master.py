"""Vendor master PROBER -- ask Bottomline what it thinks each vendor code is.

WHAT THIS IS, IN ONE PARAGRAPH
------------------------------
masters/vendors.csv holds 959 vendors we BELIEVE. Every value in it arrived
from an export or a merge; not one has ever been confirmed against Bottomline
itself. This script opens one invoice, types each vendor's ERP Vendor ID into
the vendor CODE box, and writes down the name Bottomline fills in beside it.
The result is a second master built from Bottomline's own answers, compared
against the one we have, with every difference sent to a human.

HOW A RUN GOES (changed 2026-09-09 on the operator's instruction)
-----------------------------------------------------------------
Row by row, in the master's OWN order -- row 1 of the run is row 1 of
vendors.csv and batch 1 is rows 1-25, so the operator can follow along in the
spreadsheet while it works. The package is re-selected for each row; that is
slower than the old package-grouped sort and was accepted deliberately, because
a sorted run cannot be checked against the file.

When a vendor does not load, the run STOPS on that vendor and hands the browser
back. The operator fixes whatever is wrong, presses ENTER, and the script
clicks Vendor Address again and reads it -- the same vendor, not the next one.
They can also skip it, turn the pausing off, or stop the run. See
pause_until_loaded().

Each fresh run starts a clean vendors_probed.csv; the previous one is MOVED
into masters/archive/ rather than appended to or deleted. --resume is the
exception and continues the file already there.

WHAT IT NEVER DOES
------------------
It never presses the Convert, Save, Save-as-Exception or Delete buttons -- it
imports none of their names and has no code path that reaches them. It never
clicks the vendor dropdown; the Integration Package box is the only thing this
script ever clicks. It never writes masters/vendors.csv. An invoice is OPENED
so that the boxes exist on screen, and that is the only thing done to it.

The exact button names are deliberately absent from this file, and
selftest_verify_master.py reads this source and FAILS if any of them appears.
That test is why the paragraph above spells them loosely.

Libraries used
--------------
  - playwright  drives Chrome; the same session file the recorder uses
  - openpyxl    writes masters/master_review.xlsx
  - csv, json, os, datetime, pathlib, argparse  -- Python standard library
No new dependency: all of these are already installed for the recorder.

Spec: docs/specs/2026-09-08_vendor-master-prober-design.md
Tests: python prober\\selftest_verify_master.py
"""
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# WHY THIS sys.path LINE EXISTS (added 2026-09-10, when the prober moved)
# ----------------------------------------------------------------------
# This file used to sit in automation\ alongside fill_plan.py,
# harvest_aliases.py and invoice_recorder.py, so a plain "import fill_plan"
# found them as next-door neighbours. On 2026-09-10 the prober moved into its
# own folder, prober\, and those three stayed behind in automation\ because the
# RECORDER and the READER use them too -- copying them would have created a
# second set that silently drifts out of step with the first.
#
# So the folder they live in is added to the list of places Python searches.
# Without this line every "from fill_plan import ..." below dies immediately
# with ModuleNotFoundError and nothing runs at all.
#
# Path(__file__) is this file; .resolve() makes it absolute; .parent is
# prober\; .parent again is Invoice_Indexer\; then "automation".
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "automation"))

from fill_plan import DEFAULT_ORDER, KNOWN_PACKAGES

# WHICH normalise_package THIS USES, AND WHY IT MATTERS
# -----------------------------------------------------
# There are two in this codebase and they are NOT interchangeable:
#
#   fill_plan.normalise_package("YARDI (2)")       -> "YARDI (2)"   (upper only)
#   harvest_aliases.normalise_package("YARDI (2)") -> "YARDI"       (strips it)
#
# masters/vendors.csv writes the package with a trailing number in brackets;
# fill_plan and the Bottomline screen write it plain. Reconciling those two
# spellings IS todo 0h. Everything in this file reads the MASTER, so it needs
# the second one -- using fill_plan's here would send every row to the
# no-package block and report all 875 coded vendors as WRONG_PACKAGE.
from harvest_aliases import normalise_package as normalise_master_package
from invoice_recorder import (
    SESSION_FILE,
    _read_selected_package,
    clear_box,
    load_selectors,
    log_line,
    pick_only_match,
    probe_dropdown,
    retype_full_then_clear,
)
# NOTE: queue_navigator is deliberately NOT imported. The prober does not care
# WHICH invoice is open -- any indexing form will do -- so walking up to 50
# queue pages to pick one bought nothing and was the slowest part of a run.
# The operator opens an invoice; wait_for_indexing_form() proves one is there.
# Changed 2026-09-09 after the first live run.

# --------------------------------------------------------------------------
# Live terminal visibility (added 2026-09-10, operator's instruction)
# --------------------------------------------------------------------------
# log_line() (imported above from invoice_recorder) only writes to the log
# FILE -- nothing shows on screen while the run is going, so the operator has
# had to wait until a run ends (or dies) and then open the log file to see
# what happened. say() does the same file write AND prints to the terminal,
# so each step is visible live while the browser is being watched.
#
# Deliberately NOT changed inside invoice_recorder.log_line() itself: that
# function is shared with the RECORDER, which commits real data into
# Bottomline, and changing its output behaviour is not this fix's job.
_write_log_line = log_line  # aliased so the replace below cannot recurse into say() itself


def say(log_path, text):
    """Write TEXT to the log file and print it, so the operator sees it live."""
    _write_log_line(log_path, text)
    print(text)


# --------------------------------------------------------------------------
# Where things live
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
MASTERS_DIR = PROJECT / "masters"
VENDORS_CSV = MASTERS_DIR / "vendors.csv"

# The three outputs. All gitignored 2026-09-09, BEFORE this file was written --
# every one of them carries real vendor names (hard rule #1, spec section 8).
PROBED_CSV = MASTERS_DIR / "vendors_probed.csv"
REVIEW_XLSX = MASTERS_DIR / "master_review.xlsx"
CHECKPOINT_FILE = MASTERS_DIR / ".probe_checkpoint.json"
LOG_DIR = PROJECT / "logs"

# Where a previous run's vendors_probed.csv is moved to when a FRESH run starts
# (added 2026-09-09). Gitignored alongside the file it holds -- an archived
# probe carries exactly the same real vendor names and addresses as the live
# one, so hard rule #1 covers it identically.
ARCHIVE_DIR = MASTERS_DIR / "archive"

# Probe 25 -> write 25 -> compare 25 -> next 25. The operator asked for this
# shape on 2026-09-08, and it is also what caps the cost of a crash at 24 rows
# instead of 959 -- the reader lost a whole run to exactly that bug on
# 2026-09-07 by holding everything in memory until the end.
BATCH_SIZE = 25

# ROW ORDER -- the master's own, top to bottom. Changed 2026-09-09 on the
# operator's instruction, replacing a sort that put all the YARDI rows first,
# then INTACCT, then the rows naming no package (the old P8).
#
# WHAT THAT SORT BOUGHT, AND WHY IT WAS GIVEN UP ANYWAY
# -----------------------------------------------------
# Grouping the packages meant the Integration Package box was touched 3 times
# in a 959-row run instead of ~959. That is a real saving and it is now gone:
# every row re-selects its package, and a run takes longer.
#
# It was given up because it broke the one thing the operator needs while a run
# is going -- being able to follow along in vendors.csv. Sorted, "row 1" of the
# run was not row 1 of the file, so nothing on screen lined up with anything in
# the spreadsheet. A slower run you can check beats a faster one you cannot.
#
# ensure_package() still skips the work whenever the box already shows the right
# package, so consecutive rows sharing a package cost nothing extra.


# --------------------------------------------------------------------------
# Reading the master
# --------------------------------------------------------------------------

def load_master_rows(csv_path):
    """Every row of vendors.csv as a dict, keyed by the CSV's own headers.

    A missing file gives an empty list rather than an exception, so the caller
    can say "no master found" in plain English -- a far more useful thing for a
    reader who is an accountant than a traceback.

    utf-8-sig, not utf-8: the master is written by Excel, which puts a byte-order
    mark at the front. Read as plain utf-8 the first header becomes
    '﻿Vendor Name' and every lookup of "Vendor Name" silently returns None.
    """
    path = str(csv_path)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def rows_in_master_order(rows):
    """The master's rows, in the master's own order. Nothing is reordered.

    This is deliberately a plain copy rather than "just use the list", so that
    the intent is visible and testable: row 1 of a run IS row 1 of
    vendors.csv, batch 1 IS rows 1-25, and the operator can follow a live run
    line by line in the spreadsheet. Reintroducing a sort here would silently
    break that, which is exactly the kind of change nobody notices.

    The copy also stops a caller mutating the list load_master_rows() returned.
    """
    return list(rows)


def make_batches(rows, size=BATCH_SIZE):
    """Slice rows into batches of `size`; the last one may be short."""
    if size < 1:
        raise ValueError("batch size must be 1 or more")
    return [rows[start:start + size] for start in range(0, len(rows), size)]


# --------------------------------------------------------------------------
# Verdicts (spec section 5)
# --------------------------------------------------------------------------
CONFIRMED = "CONFIRMED"                    # popup showed OUR code, right package
WRONG_PACKAGE = "WRONG_PACKAGE"            # resolved under the OTHER package -- todo 0h
NOT_FOUND = "NOT_FOUND"                    # resolved under neither
AMBIGUOUS = "AMBIGUOUS"                    # 2+ matches; the code is not unique
NO_CODE = "NO_CODE"                        # nothing to probe
PACKAGE_LEARNED = "PACKAGE_LEARNED"        # claimed none, exactly one matched
UNVERIFIED_PACKAGE = "UNVERIFIED_PACKAGE"  # name and code hold, the package cannot
CODE_MISMATCH = "CODE_MISMATCH"            # popup showed a DIFFERENT code


# --------------------------------------------------------------------------
# The Vendor Address popup -- the real witness (added 2026-09-09)
# --------------------------------------------------------------------------
# WHY THIS REPLACED READING THE NAME BOX
# --------------------------------------
# Reading the name box asked "is this box non-empty?", which the vendor code
# box's unreliable clearing can answer YES to for the PREVIOUS vendor. The
# popup instead reports the vendor Bottomline actually has loaded, as
# "Name (Code)" -- so a half-cleared box becomes a VISIBLE mismatch rather than
# a silent wrong row. It also hands us city/state/zip, which is the root cause
# of the "vendor name (city/zip)" values found in the Vendor Code column.
#
# Proved by the user on the live site 2026-09-09: typing a code and clicking
# Vendor Address WITHOUT picking anything from the dropdown shows the right
# vendor. That is what keeps P3 intact -- the vendor dropdown is still never
# clicked, so nothing is ever committed into the open invoice.
#
# The parsing below is the Master Maker extension's extractAddressFromModal(),
# reimplemented in Python. That logic ran against real Nexus; this is not a
# guess. See Master Maker\content.js:308 and HANDOFF.md:88.
POPUP_HEADING = "Vendor Address"
POPUP_BUTTON = "Vendor Address"
POPUP_CLOSE = "Close dialog"
# How long to keep asking for the popup's BODY (not just its frame) before
# giving up. Raised from 2500 on 2026-09-10: the window frame appears almost
# at once, but the address lines only arrive when the getVendor call comes
# back, and the read now refuses a heading with no body under it. This is a
# CEILING, not a wait -- the polling loop stops the moment real content is
# there, so a bigger number costs nothing on a vendor that loads normally and
# only buys patience on a slow one.
POPUP_WAIT_MS = 6000
POPUP_POLL_MS = 60

# THE VISIBLE RHYTHM (operator's instruction, 2026-09-10)
# --------------------------------------------------------
# open -> pause -> read -> pause -> close, so a person watching the browser can
# actually follow what the script is doing to the screen. Before this the popup
# could open and shut inside a few hundred milliseconds, which is what made a
# wrong read so hard to catch by eye.
#
# SETTLE is after the click, before the first read: it also gives ExtJS a
# moment to fill the body in, so the first look is less likely to be at a
# half-drawn popup. HOLD is after the read, before the close: pure visibility,
# it changes no result.
#
# The cost is per vendor. At 1.2s the full 959-row master takes about 20
# minutes longer than it otherwise would -- fine while this is being watched in
# 25s. Turn both down (or to 0) once it is trusted and left to run.
POPUP_SETTLE_MS = 400
POPUP_HOLD_MS = 800

# The ExtJS window itself, named by the site. Straight out of the traceback the
# operator captured 2026-09-09:
#
#   <div role="dialog" auto_id="vendor_address_window" class="x-window ...">
#     ... subtree intercepts pointer events
#   <div role="presentation" class="x-mask x-border-box"> ... intercepts too
#
# That is a MODAL: while it is open, ExtJS lays a mask over the page and every
# real mouse click is swallowed -- which is why the run died with a 30-second
# Playwright timeout while trying to type the next code.
POPUP_WINDOW = '[auto_id="vendor_address_window"]'

# Every Playwright click in this file uses this instead of the 30s default.
# When the mask IS up, a click can never succeed, so waiting 30 seconds to be
# told so costs two minutes over four attempts and teaches nothing.
POPUP_CLICK_TIMEOUT_MS = 5000

_CLOSE_GLYPHS = {"x", "×", "✕", "✖"}
_NAME_CODE = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")
_CITY_STATE_ZIP = re.compile(r"^(.+?),\s*([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)$")


def is_phone_line(text):
    """True for '(301) 891-2600' or '301-891-2600'.

    Kept strict -- 7+ digits AND nothing but phone characters -- so that a
    street number or a ZIP line is never mistaken for a phone number and
    dropped. Same rule as the extension's isPhoneLine().
    """
    digits = re.sub(r"\D", "", text or "")
    return len(digits) >= 7 and bool(re.fullmatch(r"[\d\s()+.\-]+", text or ""))


def parse_vendor_popup(text):
    """Turn the popup's text into the pieces we care about.

    Input looks like this (confirmed on the live site 2026-09-09):

        Vendor Address
        American Pest Management (4339-001)
        6940 Columbia Gateway Drive
        #250
        Columbia, MD 21046
        (301) 891-2600

    The heading, the close glyph and the phone line are dropped -- the phone
    number is deliberately not collected. Everything else is returned split
    out. A popup that cannot be parsed returns empty strings, never None, so no
    caller has to guard for it.
    """
    lines = [line.strip() for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    lines = [line for line in lines if line.lower() not in _CLOSE_GLYPHS]

    if lines and lines[0].lower() == POPUP_HEADING.lower():
        lines.pop(0)
    if lines and is_phone_line(lines[-1]):
        lines.pop()

    found = {"name": "", "code": "", "street": "", "city": "", "state": "",
             "zip": "", "raw": "\n".join(lines)}
    if not lines:
        return found

    match = _NAME_CODE.match(lines[0])
    if match:
        found["name"] = match.group(1).strip()
        found["code"] = match.group(2).strip()
    else:
        found["name"] = lines[0]

    rest = lines[1:]
    if rest:
        match = _CITY_STATE_ZIP.match(rest[-1])
        if match:
            found["city"] = match.group(1).strip()
            found["state"] = match.group(2).strip().upper()
            found["zip"] = match.group(3).strip()
            rest = rest[:-1]
        found["street"] = " ".join(rest)
    return found


def normalise_code(code):
    """Fold case and spacing before comparing two codes. Hyphens are KEPT --
    '4339-001' and '4339001' are not the same code."""
    return " ".join(str(code or "").split()).upper()


def codes_match(one, other):
    return bool(normalise_code(one)) and normalise_code(one) == normalise_code(other)


def screen_vendor_name(text):
    """The NAME out of the Vendor box, which reads 'Name (City/ZIP)'.

    The operator's screen shows `Illustratus (Lenexa/66214)` -- Bottomline's own
    name for the vendor, with its city and postcode in brackets. The bracketed
    part is NOT a code, which is why this is kept separate from
    parse_vendor_popup(): there the brackets hold `(4339-001)` and mean
    something entirely different.

    This is what lets the name comparison keep working when the popup is not
    opened at all (--no-address). Text with no brackets comes back unchanged.
    """
    match = _NAME_CODE.match((text or "").strip())
    return match.group(1).strip() if match else (text or "").strip()


# Marks put in front of each terminal line so a run can be read at a glance
# without counting columns.
VERDICT_MARK = {
    CONFIRMED: "  OK  ",
    CODE_MISMATCH: " MISM ",
    WRONG_PACKAGE: " PKG! ",
    NOT_FOUND: " ---- ",
    AMBIGUOUS: " AMB? ",
    NO_CODE: " skip ",
    PACKAGE_LEARNED: " LEARN",
    UNVERIFIED_PACKAGE: " ~pkg ",
}


def describe_probe(row):
    """One terminal line for one probed vendor.

    The operator asked to SEE what is being captured rather than wait an hour
    and read a spreadsheet afterwards. This is also the fastest way to catch a
    run that has gone wrong: a column of ---- means the typing is outrunning
    the dropdown again, and a column of MISM means the code box is not clearing.
    """
    mark = VERDICT_MARK.get(row.get("Verdict", ""), "  ??  ")
    ours = (row.get("Vendor Name", "") or "")[:28]
    typed = row.get("ERP Vendor ID", "") or "-"
    theirs = (row.get("Bottomline Name", "")
              or screen_vendor_name(row.get("Screen Vendor", "")))[:28]
    got = row.get("Bottomline Code", "") or ""

    where = " ".join(part for part in (row.get("City", ""),
                                       row.get("State", ""),
                                       row.get("ZIP", "")) if part)

    line = f"  [{mark}] {typed:<12} {ours:<28}"
    if theirs or got:
        line += f" -> {theirs:<28} ({got})"

    # Only shown when the box held something OTHER than the code we typed --
    # i.e. Bottomline completed it as it was typed. Silent the rest of the time,
    # because a column that is always there stops being read.
    held = row.get("Code Box Held", "") or ""
    if held and not codes_match(held, typed):
        line += f"  !box='{held[:14]}'"

    if where:
        line += f"  {where}"
    return line.rstrip()


def attempt(package, code, count, popup=None, sample=None, box="", form=None):
    """One probe of one code under one package.

    `code` is what we TYPED. `popup` is parse_vendor_popup()'s output, or None
    when no popup could be read. Keeping both means the comparison that decides
    everything -- did Bottomline show back the code we asked for? -- is made
    from recorded facts rather than from a boolean somebody set earlier.

    `box` is what the vendor code box ACTUALLY held after the typing finished,
    which is not always what we asked it to hold (added 2026-09-09). Bottomline
    completes the code as it is typed -- the operator watched '762-' turn into
    '762-001' with the added part selected -- so the box can end up holding
    something we never sent it. Recording it costs one read and turns that from
    a theory into a fact the log can settle.
    """
    popup = popup or {}
    form = form or {}
    return {"package": normalise_master_package(package),
            "code": (code or "").strip(),
            "box": (box or "").strip(),
            # The five fields the Master Maker extension captures, read off the
            # form by label BEFORE any popup is opened. form_vendor_code and
            # form_vendor are what form_confirms() judges a row on.
            "form_package": form.get("integration_package", ""),
            "form_property_code": form.get("property_code", ""),
            "form_property": form.get("property", ""),
            "form_vendor_code": form.get("vendor_code", ""),
            "form_vendor": form.get("vendor", ""),
            "count": count,
            "popup_name": popup.get("name", ""),
            "popup_code": popup.get("code", ""),
            "street": popup.get("street", ""),
            "city": popup.get("city", ""),
            "state": popup.get("state", ""),
            "zip": popup.get("zip", ""),
            "sample": list(sample or [])}


def _is_hit(one):
    """Bottomline resolved the code we typed. Two independent witnesses count.

    EITHER the FORM confirms it -- the Vendor Code box echoes our code and the
    Vendor box is populated -- OR the popup showed back our code. The form is
    now the primary witness (see form_confirms and the section on reading by
    label); the popup remains a valid one, and is still what supplies the
    street line the operator needs for the master.

    Taking either means a jammed or unreadable popup can no longer turn a
    vendor that plainly loaded into a NOT_FOUND. That is exactly what happened
    on every run before 2026-09-09.

    The rest of this docstring is the original reasoning, which still holds for
    the popup half of the test:

    NOT "a popup appeared" -- the Master Maker handover recorded (HANDOFF.md:79)
    that Bottomline opens the Vendor Address popup even on an incomplete form.
    A dead code still pops a dialog. Reading the popup's existence as success
    would have produced 875 confident, wrong rows.

    NOT "the name box is non-empty" either: the vendor code box does not always
    clear, so that box can still hold the PREVIOUS vendor. Comparing codes is
    what turns that failure from a silent wrong answer into a visible one.
    """
    return form_confirms(one) or codes_match(one["popup_code"], one["code"])


def _saw_a_different_code(attempts):
    """The popup opened and named a code that is not the one we typed."""
    return any(one["popup_code"] and not _is_hit(one) for one in attempts)


def classify_probe(code, claimed_package, attempts, code_box_filters=True):
    """Turn one row's probe attempts into one verdict.

    Returns (verdict, matched_package, best_attempt). best_attempt is the
    attempt the verdict rests on, or {} when none does -- the caller reads the
    name, city, state and zip off it. matched_package is "" whenever no single
    package can be credited.

    code_box_filters comes from Phase 0. When it is False the vendor code box
    was shown NOT to narrow by package, so the package column cannot be checked
    at all -- the name and code are still verified, and the package is reported
    as UNVERIFIED rather than guessed. Guessing is the one outcome the spec
    forbids outright (P7).
    """
    if not (code or "").strip():
        return NO_CODE, "", {}

    # 2+ matches is a fact about the CODE, not the package, so it is decided
    # first and holds whether or not the box filters.
    for one in attempts:
        if one["count"] >= 2:
            return AMBIGUOUS, "", one

    hits = [one for one in attempts if _is_hit(one)]

    if not hits:
        # A popup that named someone else is NOT a dead code. It means either
        # the box did not clear or Bottomline resolved something we did not
        # ask for -- both need a human, and neither is "NOT_FOUND".
        if _saw_a_different_code(attempts):
            wrong = next(one for one in attempts if one["popup_code"])
            return CODE_MISMATCH, "", wrong
        return NOT_FOUND, "", {}

    if not code_box_filters:
        return UNVERIFIED_PACKAGE, "", hits[0]

    claimed = normalise_master_package(claimed_package)

    if not claimed:
        if len(hits) == 1:
            return PACKAGE_LEARNED, hits[0]["package"], hits[0]
        # It resolved under both, so nothing about the package was learned.
        return UNVERIFIED_PACKAGE, "", hits[0]

    for one in hits:
        if one["package"] == claimed:
            return CONFIRMED, one["package"], one
    return WRONG_PACKAGE, hits[0]["package"], hits[0]


# --------------------------------------------------------------------------
# Phase 0 -- the calibration that can stop the run (spec section 4)
# --------------------------------------------------------------------------
CALIBRATION_PER_PACKAGE = 5


def pick_calibration_rows(rows, per_package=CALIBRATION_PER_PACKAGE):
    """The rows Phase 0 runs on: ACTIVE, coded, and named uniquely in the master.

    Every exclusion here removes a second possible explanation for a Phase 0
    result. A duplicate name might resolve under both packages because the box
    does not filter -- or simply because there really are two vendors with that
    name. A calibration that cannot tell those apart is worthless, so those rows
    never enter it.
    """
    seen = {}
    for row in rows:
        name = (row.get("Vendor Name") or "").strip().upper()
        seen[name] = seen.get(name, 0) + 1

    taken = {package: 0 for package in KNOWN_PACKAGES}
    picked = []
    for row in rows:
        package = normalise_master_package(row.get("Integration Package", ""))
        if package not in taken or taken[package] >= per_package:
            continue
        if not (row.get("ERP Vendor ID") or "").strip():
            continue
        if (row.get("Status") or "").strip().upper() != "ACTIVE":
            continue
        if seen.get((row.get("Vendor Name") or "").strip().upper(), 0) != 1:
            continue
        picked.append(row)
        taken[package] += 1
    return picked


def calibration_result(claimed, matched):
    """One calibration row: the package we claim, and the packages it matched."""
    return {"claimed": normalise_master_package(claimed),
            "matched": [normalise_master_package(m) for m in matched]}


def calibration_verdict(results):
    """Read the Phase 0 table and decide whether the crawl may run.

    Returns (action, code_box_filters, reason), where action is "run" or "stop"
    and reason is a plain-English sentence for the operator.

    The STOP cases are the point of this function. If the code box resolves
    under a package we do NOT claim, our package column is wrong at scale -- and
    crawling would write 959 rows on top of that finding instead of reporting
    it. If the results are mixed, nobody understands the screen yet, and a run
    would only produce data nobody can interpret.
    """
    if not results:
        return ("stop", False,
                "Phase 0 probed nothing -- no ACTIVE, uniquely-named, coded "
                "vendor was available to calibrate with.")

    if all(one["matched"] == [one["claimed"]] for one in results):
        return ("run", True,
                "The vendor code box filters by package: every calibration code "
                "matched under its own package and no other. The package column "
                "will be verified.")

    both = set(KNOWN_PACKAGES)
    if all(set(one["matched"]) == both for one in results):
        return ("run", False,
                "The vendor code box does NOT filter by package: every "
                "calibration code matched under both. Names and codes will "
                "still be verified; the package column will be reported as "
                "UNVERIFIED, not guessed.")

    if all(len(one["matched"]) == 1 and one["matched"][0] != one["claimed"]
           for one in results):
        return ("stop", False,
                "Every calibration code resolved under the OTHER package. That "
                "means the master's package column is wrong at scale -- and THAT "
                "is the finding. Do not crawl on top of it.")

    return ("stop", False,
            "Phase 0 results are mixed -- the codes did not behave the same way "
            "as each other. Something about this screen is not understood yet. "
            "The browser is yours; nothing was written.")


# --------------------------------------------------------------------------
# Writing what Bottomline said (spec section 6)
# --------------------------------------------------------------------------
PROBED_FIELDNAMES = [
    "Vendor Name",        # what OUR master calls it
    "ERP Vendor ID",      # the code we typed
    "Claimed Package",    # what our master claims
    "Matched Package",    # what Bottomline actually resolved under
    "Bottomline Name",    # what BOTTOMLINE calls it -- the point of the exercise
    "Bottomline Code",    # the code the popup showed back. CONFIRMED means this
                          # equals ERP Vendor ID; anything else is a finding.
    "Code Box Held",      # what the vendor code box ACTUALLY contained after
                          # typing. Normally the same as ERP Vendor ID -- when
                          # it is NOT, Bottomline completed the code as it was
                          # typed and the probe asked a different question from
                          # the one intended. Added 2026-09-09.

    # The record the Master Maker extension captures, read off the FORM by label
    # before any popup is opened (content.js:122-131). "Screen Vendor" is the
    # one that matters: it is Bottomline's own answer to the code we typed, and
    # together with Code Box Held it is what form_confirms() judges a row on.
    "Screen Package",     # integrationPackage
    "Screen Property Code",  # propertyCode
    "Screen Property",    # property
    "Screen Vendor",      # vendor -- e.g. "Illustratus (Lenexa/66214)"

    "Street",
    "City",
    "State",
    "ZIP",
    "Verdict",
    "Match Count",
    "Dropdown Sample",
    "Probed At",
]


def probed_row(master_row, verdict, matched_package, best, count, sample, when):
    """One line of vendors_probed.csv -- our claim and Bottomline's answer side
    by side, so the comparison never has to go back to the master.

    `best` is the attempt the verdict rests on ({} when none does). The address
    columns come from the Vendor Address popup; the phone number is deliberately
    never collected.
    """
    best = best or {}
    return {
        "Vendor Name": master_row.get("Vendor Name", ""),
        "ERP Vendor ID": master_row.get("ERP Vendor ID", ""),
        "Claimed Package": master_row.get("Integration Package", ""),
        "Matched Package": matched_package,
        # The popup's name when there is one, otherwise the name off the
        # FORM. Both are Bottomline's own answer, so the spelling check in
        # review_sheet_for() keeps working with --no-address.
        "Bottomline Name": (best.get("popup_name", "")
                            or screen_vendor_name(best.get("form_vendor", ""))),
        "Bottomline Code": best.get("popup_code", ""),
        "Code Box Held": best.get("box", ""),
        "Screen Package": best.get("form_package", ""),
        "Screen Property Code": best.get("form_property_code", ""),
        "Screen Property": best.get("form_property", ""),
        "Screen Vendor": best.get("form_vendor", ""),
        "Street": best.get("street", ""),
        "City": best.get("city", ""),
        "State": best.get("state", ""),
        "ZIP": best.get("zip", ""),
        "Verdict": verdict,
        "Match Count": count,
        "Dropdown Sample": " | ".join(sample or []),
        "Probed At": when,
    }


def append_probed_rows(path, rows):
    """Append one batch. The header is written only when the file is created.

    Append, never rewrite (spec section 6). The reader lost a whole run on
    2026-09-07 by holding everything in memory until the end; this is the shape
    that stops the same bug costing an hour here. A crash costs the batch in
    flight -- at most 24 rows -- and nothing already on disk.
    """
    if not rows:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROBED_FIELDNAMES)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def archive_probe_csv(path, archive_dir, when=None):
    """Move a previous run's probe file aside so a FRESH run starts clean.

    Returns where it was moved to, or None when there was nothing to move.

    WHY MOVE AND NOT OVERWRITE (operator's instruction, 2026-09-09)
    ---------------------------------------------------------------
    The operator asked for each run's complete record to land in a NEW file.
    Left alone, append_probed_rows() would add today's rows underneath last
    week's, and the file would end up holding two different answers for the
    same vendor with nothing to say which was current.

    Deleting the old one would fix that and lose a run nobody can repeat
    without another hour at the screen -- so it is renamed, never removed. The
    live path stays vendors_probed.csv so --resume, the review workbook and
    every instruction written down so far keep working unchanged.

    A name that is already taken (two runs inside the same minute) gets a
    counter rather than quietly landing on top of the earlier file.
    """
    path = Path(path)
    if not path.exists():
        return None

    stamp = when or f"{datetime.now():%Y-%m-%d_%H%M}"
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    target = archive_dir / f"{path.stem}_{stamp}{path.suffix}"
    number = 2
    while target.exists():
        target = archive_dir / f"{path.stem}_{stamp}_{number}{path.suffix}"
        number += 1

    path.replace(target)
    return target


def write_checkpoint(path, batches_done, total_batches, batch_size):
    """Record the last COMPLETED batch, so --resume never re-probes it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "batches_done": batches_done,
        "total_batches": total_batches,
        "batch_size": batch_size,
        "updated": f"{datetime.now():%Y-%m-%d %H:%M}",
    }, indent=2), encoding="utf-8")


def read_checkpoint(path):
    """The saved checkpoint, or None.

    Never raises. A checkpoint half-written by a crash is exactly the moment you
    need --resume to work, and a traceback there would send the operator back to
    row 1 -- the opposite of what the file is for. Unreadable counts as absent,
    which restarts from the beginning: slow, but never wrong.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def resume_start_index(checkpoint):
    """The 0-based row index the next run picks up at."""
    if not checkpoint:
        return 0
    try:
        return int(checkpoint["batches_done"]) * int(checkpoint["batch_size"])
    except Exception:
        return 0


# --------------------------------------------------------------------------
# Comparison and the review workbook (spec section 8)
# --------------------------------------------------------------------------
REVIEW_SHEETS = ("Name Differs", "Wrong Package", "Not Found",
                 "Ambiguous", "Package Learned", "Code Mismatch")

# "Code Box Held" sits next to the two codes it has to be compared against.
# On the Code Mismatch and Not Found sheets it is the column that says whether
# the finding is about the VENDOR or about the typing.
REVIEW_HEADERS = ["Vendor Name (ours)", "Bottomline Name", "ERP Vendor ID",
                  "Bottomline Code", "Code Box Held", "Claimed Package",
                  "Matched Package", "Verdict", "City", "State", "ZIP",
                  "Probed At"]

_NOT_NAME = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalise_name_for_compare(name):
    """Fold case, punctuation and spacing away before comparing two names.

    Written here rather than reusing vendor_lookup._normalise: that one is tuned
    for MATCHING a messy spreadsheet value against the master, and if it is ever
    loosened for that job it must not quietly start hiding real spelling
    differences in this report. harvest_aliases._key was replicated for exactly
    the same reason.
    """
    upper = (name or "").upper()
    return _SPACES.sub(" ", _NOT_NAME.sub(" ", upper)).strip()


def review_sheet_for(probed):
    """The ONE review sheet a probed row belongs on, or None if it needs no human.

    Order matters. WRONG_PACKAGE is decided before the name is looked at,
    because a row that resolved under the other package is a todo-0h row first
    and a spelling question second -- and one row must never land on two sheets,
    or it gets settled twice, two different ways.
    """
    verdict = probed.get("Verdict", "")

    if verdict == NO_CODE:
        return None                      # never probed; nothing to compare
    if verdict == CODE_MISMATCH:
        return "Code Mismatch"
    if verdict == WRONG_PACKAGE:
        return "Wrong Package"
    if verdict == NOT_FOUND:
        return "Not Found"
    if verdict == AMBIGUOUS:
        return "Ambiguous"
    if verdict == PACKAGE_LEARNED:
        return "Package Learned"

    # CONFIRMED and UNVERIFIED_PACKAGE both carry a real name from Bottomline,
    # so both get the spelling check.
    ours = normalise_name_for_compare(probed.get("Vendor Name", ""))
    theirs = normalise_name_for_compare(probed.get("Bottomline Name", ""))
    if theirs and ours != theirs:
        return "Name Differs"
    return None


def route_to_sheets(probed_rows):
    """Group probed rows by review sheet.

    Every sheet name is always a key, even when empty -- that is what makes a
    sheet REBUILD EMPTY on the next run, so a difference you have already
    settled actually disappears instead of sitting there for ever.
    """
    by_sheet = {name: [] for name in REVIEW_SHEETS}
    for row in probed_rows:
        sheet = review_sheet_for(row)
        if sheet:
            by_sheet[sheet].append(row)
    return by_sheet


def summary_lines(probed_rows, phase0_reason):
    """The Summary sheet, and what is printed at the end of a run."""
    counts = {}
    for row in probed_rows:
        counts[row["Verdict"]] = counts.get(row["Verdict"], 0) + 1
    lines = [f"Phase 0: {phase0_reason}",
             f"Rows probed: {len(probed_rows)}"]
    lines += [f"{verdict}: {count}" for verdict, count in sorted(counts.items())]
    return lines


def write_review_workbook(review_path, by_sheet, lines, today):
    """Rewrite the five difference sheets plus Summary, leaving any other sheet
    exactly as it was.

    Same shape as harvest_aliases.write_review_workbook(): each sheet is rebuilt
    from scratch, so a difference a human has settled simply vanishes on the
    next run, while notes added on a sheet this script does not own survive.
    """
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    path = str(review_path)
    if os.path.exists(path):
        workbook = load_workbook(path)
    else:
        workbook = Workbook()
        # A fresh Workbook() comes with one empty default sheet we never want.
        workbook.remove(workbook.active)

    for name in REVIEW_SHEETS:
        if name in workbook.sheetnames:
            workbook.remove(workbook[name])
        sheet = workbook.create_sheet(name)
        sheet.append(REVIEW_HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"

        for row in by_sheet.get(name, []):
            sheet.append([row.get("Vendor Name", ""),
                          row.get("Bottomline Name", ""),
                          row.get("ERP Vendor ID", ""),
                          row.get("Bottomline Code", ""),
                          row.get("Code Box Held", ""),
                          row.get("Claimed Package", ""),
                          row.get("Matched Package", ""),
                          row.get("Verdict", ""),
                          row.get("City", ""),
                          row.get("State", ""),
                          row.get("ZIP", ""),
                          row.get("Probed At", "")])

        # Codes and ZIPs are TEXT, not numbers. 254 of the real ERP IDs are all
        # digits and several carry leading zeros -- left as numbers, Excel eats
        # the zeros. Same for a ZIP like 04101.
        # C/D/E are the three code columns and K is the ZIP. These letters moved
        # when "Code Box Held" was inserted at E on 2026-09-09 -- they are
        # positions, so they MUST be re-checked whenever REVIEW_HEADERS changes.
        for column in ("C", "D", "E", "K"):
            for cell in sheet[column]:
                cell.number_format = "@"

        for index, width in enumerate([38, 38, 16, 16, 16, 18, 16, 20, 22, 8,
                                       12, 18],
                                      start=1):
            sheet.column_dimensions[get_column_letter(index)].width = width

    if "Summary" in workbook.sheetnames:
        workbook.remove(workbook["Summary"])
    summary = workbook.create_sheet("Summary")
    summary.append(["Vendor master prober", today])
    for line in lines:
        summary.append([line])
    summary.column_dimensions["A"].width = 100

    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    workbook.save(path)
    workbook.close()


# --------------------------------------------------------------------------
# The browser layer -- thin, because every decision was made above
# --------------------------------------------------------------------------

# TYPING SPEED -- raised from 100 to 220 on 2026-09-09 after the first live run.
#
# 100ms was borrowed from the property NAME box and was too fast here: the code
# was typed before Bottomline's suggestion list had loaded, so the dropdown was
# counted while still empty. That failure looks EXACTLY like "this code does
# not exist" -- a wrong answer that reads as a confident one, which is the
# worst shape of bug this project has.
#
# --typing-delay overrides it, because the right number is a property of the
# operator's connection and machine, not of this script. If a run shows a
# suspicious pile of NOT_FOUND, raise this before believing the result.
VENDOR_CODE_TYPING_DELAY_MS = 220

# After the last character, give the list a moment more to finish loading
# before anything counts it. probe_dropdown() already waits for the list to
# settle; this is the additional grace the live run showed it needs.
AFTER_TYPING_SETTLE_MS = 400


# How hard to try before giving up on emptying the code box, and how long to
# let ExtJS notice between attempts.
CLEAR_ATTEMPTS = 4
CLEAR_SETTLE_MS = 150


def _read_box(page, selector):
    """(could_read, value). Never raises.

    The two are kept apart on purpose. "I read the box and it was empty" and
    "I could not read the box at all" look identical if you only return a
    string -- and clear_code_box() must never mistake the second for the first,
    or an unreadable box would be declared clean and typed into.
    """
    if not selector:
        return False, ""
    try:
        return True, (page.locator(selector).first.input_value() or "").strip()
    except Exception:
        return False, ""


def read_box_value(page, selector):
    """What a box holds right now, trimmed. Unreadable reads as "". Never raises."""
    return _read_box(page, selector)[1]


def clear_code_box(page, selector, log_path=None, attempts=CLEAR_ATTEMPTS):
    """Empty the vendor code box and PROVE it is empty. Returns True/False.

    THE BUG THIS EXISTS FOR (seen live 2026-09-09, and the recorder has it too):
    the box is typed with 'ROL1234', cleared, and one character is left behind.
    The next code is then typed onto that leftover -- 'rROL5678' -- which
    matches nothing, so a perfectly good vendor is reported as not found. The
    old code cleared once and simply assumed it worked.

    So this reads the box back after every attempt and tries again while
    anything remains. Control+a then Delete first; then Backspace, which ExtJS
    sometimes handles differently. Real keystrokes throughout -- page.fill("")
    changes the text without firing keys, so ExtJS keeps running the search for
    the OLD value (the reason clear_box() in invoice_recorder.py works the way
    it does).
    """
    for number in range(1, attempts + 1):
        try:
            box = page.locator(selector).first
            box.click()
            box.press("Control+a")
            box.press("Delete" if number % 2 else "Backspace")
        except Exception as error:
            if log_path:
                say(log_path, f"    clear attempt {number} failed: {error}")

        try:
            page.wait_for_timeout(CLEAR_SETTLE_MS)
        except Exception:
            pass

        readable, left = _read_box(page, selector)
        if readable and not left:
            if number > 1 and log_path:
                say(log_path, f"    box needed {number} attempts to clear")
            return True

        if log_path:
            say(log_path, f"    box still holds '{left}' after attempt "
                               f"{number}" if readable else
                               f"    could not read the box on attempt {number}")

    readable, left = _read_box(page, selector)
    return readable and not left


# --------------------------------------------------------------------------
# Reading the form BY LABEL -- the Master Maker extension's method
# --------------------------------------------------------------------------
# WHY THIS REPLACED THE POPUP AS THE WITNESS (2026-09-09, operator's decision)
# ---------------------------------------------------------------------------
# The extension never opens or closes a popup at all -- it says so out loud at
# content.js:207. A person clicks; it reads what is already on screen. That is
# why it never hit the failure that killed our run: we invented the problem by
# driving the popup ourselves.
#
# Everything except the addresses it reads straight off the form
# (content.js:122-131), and the form already shows what the popup was being
# opened to reveal:
#
#     Vendor Code : 762-001                      <- the code Bottomline resolved
#     Vendor      : Illustratus (Lenexa/66214)   <- name, city and ZIP
#
# So the witness is now: the Vendor Code box echoes back the code we TYPED, and
# the Vendor box is populated. That is the extension's own completeness test
# (content.js:98) plus the code comparison this script has always needed.
#
# The Vendor Address popup is still opened -- the operator confirmed the STREET
# line is needed for the master -- but it is no longer what proves a vendor
# loaded. If it jams, the row is already captured.
#
# This is a port of getInputValue() (content.js:133-196), which ran against real
# Nexus. It is reused rather than re-guessed, exactly as the popup parser was.
FIELD_LABELS = [
    ("integration_package", "Integration Package"),
    ("property_code", "Property Code"),
    ("property", "Property"),
    ("vendor_code", "Vendor Code"),
    ("vendor", "Vendor"),
]

_FIELD_BY_LABEL_JS = r"""
(labelText) => {
  // Fold away case and punctuation before comparing, so 'Vendor Code:' and
  // 'vendor code' are the same label.
  const clean = (s) => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  const cleanTarget = clean(labelText);

  const readFieldValue = (el) => {
    if (!el) return '';
    if (typeof el.value === 'string' && el.value.trim() !== '') return el.value.trim();
    return ((el.innerText || el.textContent || '')).trim();
  };

  try {
    const lower = labelText.toLowerCase();
    const xpath = "//*[contains(translate(text(), " +
      "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '" +
      lower + "')]";
    const snapshot = document.evaluate(
      xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);

    let labelNode = null;
    for (let i = snapshot.snapshotLength - 1; i >= 0; i--) {
      const node = snapshot.snapshotItem(i);
      if (node.tagName === 'SCRIPT' || node.tagName === 'STYLE') continue;
      if (node.textContent.trim().length >= 50) continue;
      // STRICT equality, not "contains" -- otherwise the label 'Vendor' also
      // matches 'Vendor Code:' and reads the wrong box (content.js:145).
      if (clean(node.textContent) === cleanTarget) { labelNode = node; break; }
    }

    if (labelNode) {
      // A real <label for="..."> pointing straight at the field.
      const labelEl = labelNode.closest ? labelNode.closest('label') : null;
      const forId = labelEl && labelEl.getAttribute('for');
      if (forId) {
        const v = readFieldValue(document.getElementById(forId));
        if (v) return v;
      }
      // Otherwise walk up and take the nearest value-bearing field. Checkboxes,
      // radios, buttons and hidden fields are excluded -- none of them is the
      // text box a label like this describes.
      let parent = labelNode.parentElement;
      let depth = 0;
      while (parent && depth < 6) {
        const fields = Array.from(parent.querySelectorAll(
          'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])' +
          ':not([type="button"]):not([type="submit"]), select, textarea,' +
          ' [contenteditable="true"]'));
        if (fields.length > 0 && fields.length <= 3) {
          const v = readFieldValue(fields[fields.length - 1]);
          if (v) return v;
        }
        parent = parent.parentElement;
        depth++;
      }
    }
  } catch (e) {
    // fall through to the placeholder / aria-label pass
  }

  const all = document.querySelectorAll(
    'input[type="text"], input:not([type]), select, textarea,' +
    ' [contenteditable="true"]');
  for (const input of all) {
    const ph = clean(input.placeholder);
    const aria = clean(input.getAttribute && input.getAttribute('aria-label'));
    if ((ph && ph === cleanTarget) || (aria && aria === cleanTarget)) {
      const v = readFieldValue(input);
      if (v) return v;
    }
  }
  return '';
}
"""


def read_field_by_label(page, label):
    """What the box labelled `label` holds right now. "" if it cannot be read.

    Never raises -- an unreadable field is "we do not know", and every caller
    treats it that way rather than as a finding.
    """
    try:
        return (page.evaluate(_FIELD_BY_LABEL_JS, label) or "").strip()
    except Exception:
        return ""


def gather_visible_data(page):
    """The five form fields the extension captures, read by their labels.

    No popup is opened and nothing is clicked -- this is a pure read of what is
    already on screen, done BEFORE anything touches the Vendor Address popup.
    That ordering is the point: if the popup later jams, the row has already
    been captured.

    Property Code and Property are read for every row, the way the extension
    does it (content.js:122-131), rather than once per run. They barely change
    while one invoice stays open -- but "barely" is an assumption, and a row
    that silently recorded the wrong property would be worse than the seconds
    it costs to read them.
    """
    return {key: read_field_by_label(page, label) for key, label in FIELD_LABELS}


def form_confirms(one):
    """True when the FORM says Bottomline resolved the code we typed.

    Two conditions, both required:
      - the Vendor Code box echoes back the code we typed, and
      - the Vendor box is populated.

    The second is the extension's own completeness test (content.js:98); the
    first is the code comparison this script has always rested on. Together they
    close the hole the popup was introduced to cover: a code box that did not
    clear leaves the OLD code on screen, which fails the first test, and a code
    that resolved to nothing leaves the vendor box empty, which fails the second.
    """
    return (codes_match(one.get("form_vendor_code", ""), one.get("code", ""))
            and bool(one.get("form_vendor", "")))


def indexing_form_is_open(page, selectors):
    """True when an indexing form is actually on screen. Never raises.

    The vendor CODE box is the landmark: it exists only on the image indexing
    screen. Checking for it is what stops the run probing a queue page, a
    dashboard, or a half-loaded frame and reading 0 matches for everything --
    which would look exactly like "none of these codes exist".
    """
    try:
        return page.locator(selectors["fill"]["vendor_code"]).count() > 0
    except Exception:
        return False


def wait_for_indexing_form(page, selectors, note, attempts=5):
    """Ask the operator to open any invoice, then PROVE one is open.

    The prober does not care which invoice it is -- it needs a form with boxes
    on it and nothing else. Asking is faster and far simpler than reading the
    whole queue, and it removes the "queue is empty" failure mode entirely.
    """
    for number in range(1, attempts + 1):
        print("\n  Open ANY invoice for indexing in the browser window.")
        print("  (Any one will do -- nothing on it will be changed.)")
        input("  Press ENTER once the indexing form is on screen... ")

        if indexing_form_is_open(page, selectors):
            note("Indexing form confirmed on screen.")
            return True
        note(f"No vendor code box found on screen -- attempt {number} of {attempts}.")

    return False


def package_already_selected(on_screen, wanted):
    """True when the box on screen already shows the package we want.

    Compared through normalise_master_package() so 'YARDI (2)' from the master
    and 'YARDI' on screen count as the same package -- the todo 0h mismatch.
    """
    return (bool(on_screen)
            and normalise_master_package(on_screen)
            == normalise_master_package(wanted))


def ensure_package(page, selectors, package, state, log_path):
    """Make sure THIS package is the one selected on screen, for THIS row.

    Every row goes package -> code -> read, in that order, because Bottomline
    scopes what a box will resolve to the package currently selected. Getting
    that order wrong does not raise an error -- it quietly answers a different
    question, which is worse.

    WHY THIS READS THE SCREEN INSTEAD OF TRUSTING A VARIABLE (2026-09-09):
    it used to skip the work whenever its own `state` said the right package
    was already chosen. That is only safe while nothing else touches the form --
    and opening and closing the Vendor Address popup does touch the form. A
    stale belief here means every row after it is probed under the WRONG
    package, and the answers still look perfectly reasonable.

    Reading the box back each row keeps P8's benefit -- when it already shows
    the right package nothing is clicked -- while removing the assumption.

    The package box is the only dropdown this script ever picks from (P3).
    """
    on_screen = _read_selected_package(page, selectors)
    if package_already_selected(on_screen, package):
        state["package"] = package
        return True

    if state.get("package") == package:
        say(log_path, f"  package DRIFTED: expected {package}, box shows "
                           f"'{on_screen}' -- re-selecting")

    box = selectors["fill"]["integration_package"]
    # NOTE the key. load_selectors() RENAMES the JSON's
    # "dropdown_item_selector" to "dropdown_item". Using the JSON spelling
    # here raised KeyError on the first package switch, live, 2026-09-09.
    items = selectors["dropdown_item"]
    clear_box(page, box)
    count, sample = probe_dropdown(page, box, package, items)
    if count != 1:
        say(log_path,
                 f"  package '{package}': {count} match(es) {sample} -- NOT selected")
        state["package"] = None
        return False

    pick_only_match(page, items)

    # Prove the pick landed. Clicking an ExtJS dropdown item can fail silently
    # (the 2026-08-14 invisible-item failure), and a package that did not take
    # would send every code after it to the wrong accounting system's list.
    on_screen = _read_selected_package(page, selectors)
    if not package_already_selected(on_screen, package):
        say(log_path, f"  package '{package}' was picked but the box shows "
                           f"'{on_screen}' -- NOT selected")
        state["package"] = None
        return False

    state["package"] = package
    say(log_path, f"  package selected: {package}")
    return True


# Reads the Vendor Address popup.
#
# WHY THIS IS A PLAIN SELECTOR NOW, AND NOT THE EXTENSION'S TEXT SEARCH
# ---------------------------------------------------------------------
# It used to be a port of Master Maker's findAddressModal() (content.js:263):
# scan every div on the page and keep the tightest one whose text starts with
# "Vendor Address". That search never once succeeded live -- and on 2026-09-10
# the reason turned out to be that the JavaScript never ran AT ALL. The comment
# inside it warning about backslash-n contained a real backslash-n, Python
# turned it into a line break, the comment broke in half and left a stray quote
# as code, and the whole block died with "SyntaxError: Invalid or unexpected
# token". popup_text() swallowed that exception and returned "" every time, so
# every vendor was reported as "showed nothing we could read" and
# close_vendor_popup() concluded there was no popup to close.
#
# It is a RAW string (r""") now so a backslash can never be re-interpreted on
# the way to the browser, and the text search is gone: the operator inspected
# the live popup in DevTools on 2026-09-10 and the markup is known, so guessing
# at it buys nothing. selftest_verify_master.py syntax-checks every _JS block
# with node, which is the test that would have caught this on day one.
#
# The markup the operator captured:
#     <div auto_id="vendor_address_window" role="dialog" ...>      <- POPUP_WINDOW
#       ... header, with the close tool ...
#       <div data-ref="innerCt" class="x-autocontainer-innerCt">   <- the data
#         <b>Illustratus (762-001)</b>
#         <div class="addressItem">8455 Lenexa Drive</div>
#         <div class="addressItem">Lenexa, KS 66214</div>
_POPUP_TEXT_JS = r"""
([windowSelector, heading]) => {
  const win = document.querySelector(windowSelector);
  if (!win) return '';
  const r = win.getBoundingClientRect();
  if (!(r.width > 0 && r.height > 0)) return '';

  const lines = (txt) =>
    (txt || '').split('\n').map((s) => s.trim()).filter(Boolean);
  const isHeading = (line) => line.toLowerCase() === heading.toLowerCase();

  // WHERE THE DATA IS, IN THE ORDER WORTH ASKING (markup captured by the
  // operator from the live popup, 2026-09-10):
  //
  //   <div auto_id="vendor_address_window">        <- POPUP_WINDOW
  //     ...header..., whose title text is "Vendor Address"
  //     <div data-ref="bodyWrap"> <div data-ref="body">
  //       <div auto_id="window_panel">             <- the panel in the body
  //         <div data-ref="innerCt">               <- THE DATA
  //           <b>A/C Control Inc (3983-001)</b>
  //           <div class="addressItem">6649 Garland Drive, Suite 9</div>
  //           <div class="addressItem">Warrenton, VA 20187</div>
  //
  // The trap: ExtJS gives EVERY container a data-ref, and reuses the same
  // names at every level -- the window header is a container too and has its
  // own data-ref="innerCt", earlier in document order than this one. So a
  // bare win.querySelector('[data-ref="innerCt"]') returns the HEADER, whose
  // text is exactly "Vendor Address". That is what the 2026-09-10 run read at
  // 240ms and reported as the vendor's answer before shutting the popup --
  // the same "the label won, not the content" mistake as 2026-09-09, in
  // different markup.
  //
  // So: ask for the address block itself first, then scope every other
  // candidate INSIDE the body, and put the same guard on all of them.
  const item = win.querySelector('.addressItem');
  const candidates = [
    item ? item.parentElement : null,
    win.querySelector('[auto_id="window_panel"] [data-ref="innerCt"]'),
    win.querySelector('.x-window-body [data-ref="innerCt"]'),
    win.querySelector('.x-window-body .x-autocontainer-innerCt'),
    win,
  ];

  // THE GUARD, ON EVERY CANDIDATE. A heading with nothing under it is not an
  // answer: it means either the header matched instead of the body, or the
  // body has not been filled in yet (ExtJS paints the frame first and waits
  // for getVendor). Either way, return '' so the caller keeps polling rather
  // than recording a title as a vendor address.
  for (const el of candidates) {
    if (!el) continue;
    const all = lines(el.innerText);
    if (!all.some((line) => !isHeading(line))) continue;
    return all.join('\n');
  }
  return '';
}
"""


def popup_text(page, log_path=None):
    """The open Vendor Address popup's text, or "". Never raises.

    log_path is optional and only for the LOW-FREQUENCY callers (the open/
    close checks). open_and_read_vendor_popup()'s polling loop calls this up
    to ~40 times while waiting for the popup to render -- passing log_path
    there would flood the log with near-duplicate lines, so it logs its own
    single summary once the loop ends instead.
    """
    try:
        text = (page.evaluate(_POPUP_TEXT_JS,
                              [POPUP_WINDOW, POPUP_HEADING]) or "").strip()
    except Exception as error:
        if log_path:
            say(log_path, f"    [popup_text] evaluate failed: {error}")
        return ""
    if log_path:
        preview = repr(text[:80]) if text else "<empty>"
        say(log_path, f"    [popup_text] sees: {preview}")
    return text


# WHAT IS ACTUALLY IN THE WINDOW -- asked only when a read came back empty.
#
# Three separate live runs were spent working out which element the text was
# being taken from. This answers that in one line in the log: how many address
# lines are present, every data-ref="innerCt" in the window with the start of
# its text, and what the window as a whole reads. It runs ONLY on the failure
# path, so a healthy run is not made noisier by it.
_POPUP_SHAPE_JS = r"""
(windowSelector) => {
  const win = document.querySelector(windowSelector);
  if (!win) return 'no window matched ' + windowSelector;
  const cut = (txt) => JSON.stringify((txt || '').trim().slice(0, 40));
  const refs = Array.from(win.querySelectorAll('[data-ref="innerCt"]'))
    .map((el) => (el.id || '(no id)') + '=' + cut(el.innerText));
  return 'addressItems=' + win.querySelectorAll('.addressItem').length
    + '  innerCt x' + refs.length + ': ' + refs.join(' | ')
    + '  window=' + cut(win.innerText);
}
"""


def popup_shape(page, log_path):
    """Log what the popup window actually contains. Failure path only."""
    try:
        say(log_path, f"    [popup_shape] {page.evaluate(_POPUP_SHAPE_JS, POPUP_WINDOW)}")
    except Exception as error:
        say(log_path, f"    [popup_shape] could not be read: {error}")


# IS THE POPUP ON SCREEN -- asked WITHOUT trying to read it.
#
# This exists because of the 2026-09-10 failure. close_vendor_popup() used to
# decide "is there a popup to close?" by calling popup_text(), so the moment
# reading broke, closing broke with it: the reader returned "", the closer read
# that as "no popup here", and the x was never clicked. Presence and content
# are different questions and are asked separately now.
_POPUP_OPEN_JS = r"""
(windowSelector) => {
  const win = document.querySelector(windowSelector);
  if (!win) return false;
  const r = win.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
}
"""


def popup_open(page, log_path=None):
    """True if the Vendor Address window is on screen. Never raises."""
    try:
        state = bool(page.evaluate(_POPUP_OPEN_JS, POPUP_WINDOW))
    except Exception as error:
        if log_path:
            say(log_path, f"    [popup_open] evaluate failed: {error}")
        return False
    if log_path:
        say(log_path, f"    [popup_open] {'YES' if state else 'no'}")
    return state


# Closes the ExtJS window by clicking its own close tool ("x") FROM JavaScript.
#
# A click dispatched from JavaScript goes straight at the element. It skips the
# hit-testing a real mouse click does, so the modal mask that blocks Playwright
# does not block this. That single difference is what turns the popup from a
# run-ending jam into a non-event.
#
# THE SELECTOR, AND WHY IT IS NOT THE ONE THE OPERATOR READ OFF THE SCREEN
# ------------------------------------------------------------------------
# The operator inspected the live popup on 2026-09-10 and gave three ids:
# #window-1800 (the box), #tool-1802 (the x), #panel-1801-innerCt (the data).
# Those numbers are ExtJS's global component counter and go up every time
# anything on the page opens -- the SAME popup was window-1787 earlier that
# day. Hard-coding them would work once and never again. So the stable parts
# are used instead: auto_id for the window (POPUP_WINDOW), and for the x, the
# class ExtJS always gives a close tool, then any tool element in the window
# -- which is what #tool-1802 is.
#
# Ext.getCmp(...).close() is kept as a second route: if ExtJS is on the page it
# is the same call the x itself makes, so it works even if the tool markup
# changes. Returns a word saying which route ran, so the log records how this
# site really behaves instead of leaving us guessing a seventh time.
POPUP_CLOSE_TOOL = '.x-tool-close, [class*="tool-close"], [id^="tool-"]'

_CLOSE_POPUP_JS = r"""
([windowSelector, toolSelector]) => {
  const win = document.querySelector(windowSelector);
  if (!win) return 'gone';
  const r = win.getBoundingClientRect();
  if (!(r.width > 0 && r.height > 0)) return 'gone';

  const tool = win.querySelector(toolSelector);
  if (tool) { tool.click(); return 'clicked-tool'; }

  if (window.Ext && Ext.getCmp && win.id) {
    const cmp = Ext.getCmp(win.id);
    if (cmp && cmp.close) { cmp.close(); return 'ext-close'; }
  }
  return 'window-found-but-no-close-tool';
}
"""


def close_vendor_popup(page, log_path=None):
    """Close the popup and PROVE it closed. Returns False if it will not go.

    A popup left open would be read as the NEXT vendor's answer -- the one
    failure mode that turns this whole approach into confident nonsense. So the
    caller treats False as a reason to stop the run, not to carry on.

    THE ORDER, AND WHY IT CHANGED (2026-09-09, after the run died)
    ---------------------------------------------------------------
    It used to try Escape, then a Playwright click on "Close dialog". Both
    failed live:
      - Escape did nothing, and it was given only 60ms to work.
      - get_by_role("button", name="Close dialog") never matched, because
        ExtJS's close control is a styled div tool, not a button with that name.
    The popup then stayed open, its modal mask swallowed every click, and the
    next thing to touch the form timed out after 30 seconds.

    So the JavaScript close tool now goes FIRST. A click dispatched from script
    goes straight at the element and skips hit-testing -- which is the whole
    reason it lands while the mask is up and a real mouse click cannot.
    Escape and the Playwright click stay on as fallbacks; they cost little and
    nothing about this site has been proven twice.

    WHAT CHANGED 2026-09-10 (operator's instruction: click the x, do not go
    hunting for the popup first)
    ---------------------------------------------------------------------
    Every check here used to be popup_text(). That tied closing to READING:
    when the reader broke, popup_text() returned "" for a popup that was
    plainly on screen, this function read that as "nothing to close", returned
    True without clicking anything, and the modal mask then blocked every
    click for the next 30 seconds. Presence is now asked with popup_open(),
    which only looks for the window -- it never tries to read it.
    """
    if not popup_open(page, log_path):
        return True

    # 1. The ExtJS close tool, clicked through JavaScript, straight through the mask.
    try:
        how = page.evaluate(_CLOSE_POPUP_JS, [POPUP_WINDOW, POPUP_CLOSE_TOOL])
        page.wait_for_timeout(POPUP_POLL_MS)
        if log_path:
            say(log_path, f"    close tool: {how}")
    except Exception as error:
        if log_path:
            say(log_path, f"    JS close failed: {error}")
    if not popup_open(page, log_path):
        return True

    # 2. Escape, with a real pause this time rather than 60ms.
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(POPUP_POLL_MS * 4)
    except Exception:
        pass
    if not popup_open(page, log_path):
        return True

    # 3. The named button. Kept last: it never matched live, and with the mask
    #    up a real click cannot land anyway -- hence the short timeout.
    try:
        page.get_by_role("button", name=POPUP_CLOSE).first.click(
            timeout=POPUP_CLICK_TIMEOUT_MS)
        page.wait_for_timeout(POPUP_POLL_MS)
    except Exception as error:
        if log_path:
            say(log_path, f"    could not click '{POPUP_CLOSE}': {error}")
    return not popup_open(page, log_path)


# Finds the Vendor Address control the way the extension does, and for the
# reason the extension says out loud (content.js:49):
#
#   "This bypasses issues where the button is dynamically re-rendered or isn't
#    a strict <button> tag."
#
# That is exactly why the first attempt at this failed live on 2026-09-09: it
# used get_by_role("button", ...), which never matched, so the click quietly
# did nothing and no popup ever opened. Match on TEXT across any element type,
# and prefer the innermost match so a wrapping div is not clicked instead.
_FIND_BUTTON_JS = r"""
(wanted) => {
  const want = wanted.toLowerCase();
  const visible = (el) => {
    if (!el || !el.getBoundingClientRect) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && el.offsetParent !== null;
  };
  let best = null;
  const all = document.querySelectorAll(
    'button, a, span, div, input, td, li, label, [role="button"]');
  for (const el of all) {
    if (!visible(el)) continue;
    const text = (el.textContent || '').trim().toLowerCase();
    const val = ((el.value || '') + '').trim().toLowerCase();
    if (text === want || val === want) {
      if (!best || best.contains(el)) best = el;   // innermost wins
    }
  }
  return best;
}
"""


def click_vendor_address(page, log_path):
    """Click the Vendor Address control. Returns the strategy that worked, or "".

    Three routes are tried and the one that worked is logged, so the next live
    run says plainly how this site is really built instead of leaving us
    guessing again.
    """
    try:
        handle = page.evaluate_handle(_FIND_BUTTON_JS, POPUP_BUTTON)
        element = handle.as_element()
        if element is not None:
            element.click()
            return "text-match"
    except Exception as error:
        say(log_path, f"    text-match click failed: {error}")

    try:
        page.get_by_role("button", name=POPUP_BUTTON, exact=True).first.click(
            timeout=POPUP_CLICK_TIMEOUT_MS)
        return "role-button"
    except Exception as error:
        say(log_path, f"    role-button click failed: {error}")

    try:
        page.get_by_text(POPUP_BUTTON, exact=True).last.click(
            timeout=POPUP_CLICK_TIMEOUT_MS)
        return "get-by-text"
    except Exception as error:
        say(log_path, f"    get-by-text click failed: {error}")

    return ""


def open_and_read_vendor_popup(page, log_path):
    """Click Vendor Address, read what it says, close it again.

    Returns parse_vendor_popup()'s dict -- empty strings if it never opened.

    Note what is NOT concluded here: that the popup opening means anything.
    Bottomline opens it even on an incomplete form (Master Maker HANDOFF.md:79),
    so a dead code still produces a dialog. Only the CODE inside it counts, and
    that comparison is made in _is_hit().
    """
    how = click_vendor_address(page, log_path)
    if not how:
        say(log_path,
                 f"    '{POPUP_BUTTON}' could not be clicked by any route -- "
                 "no popup, so nothing could be read.")
        return {}
    say(log_path, f"    opened the popup via {how} "
                  f"-- settling {POPUP_SETTLE_MS}ms before reading")
    try:
        page.wait_for_timeout(POPUP_SETTLE_MS)
    except Exception:
        pass

    waited = POPUP_SETTLE_MS
    text = ""
    polls = 0
    while waited < POPUP_WAIT_MS:
        text = popup_text(page)  # no log_path: up to ~40 polls, logged once below instead
        polls += 1
        if text:
            break
        page.wait_for_timeout(POPUP_POLL_MS)
        waited += POPUP_POLL_MS
    preview = repr(text[:80]) if text else "<empty>"
    say(log_path,
        f"    popup read after {waited}ms ({polls} poll(s)): {preview}")
    if not text:
        popup_shape(page, log_path)

    found = parse_vendor_popup(text)
    say(log_path,
        f"    popup parsed -> name={found['name']!r} code={found['code']!r} "
        f"street={found['street']!r} city={found['city']!r} "
        f"state={found['state']!r} zip={found['zip']!r}")

    say(log_path, f"    holding the popup open {POPUP_HOLD_MS}ms, then closing")
    try:
        page.wait_for_timeout(POPUP_HOLD_MS)
    except Exception:
        pass
    close_vendor_popup(page, log_path)
    return found


def probe_one_code(page, selectors, code, package, log_path,
                   typing_delay_ms=VENDOR_CODE_TYPING_DELAY_MS,
                   want_address=True):
    """Type ONE code, read the form, then read the address popup for the street.

    Nothing is picked from the vendor dropdown and nothing is committed. The
    box is cleared first and fully reset afterwards with
    retype_full_then_clear(), because ExtJS otherwise carries the previous
    search into the next probe.

    Raises RuntimeError if a popup will not close -- see close_vendor_popup().
    """
    box = selectors["fill"]["vendor_code"]
    # NOTE the key. load_selectors() RENAMES the JSON's
    # "dropdown_item_selector" to "dropdown_item". Using the JSON spelling
    # here raised KeyError on the first package switch, live, 2026-09-09.
    items = selectors["dropdown_item"]

    say(log_path, f"  -- probing '{code}' under {package} --")

    # A popup left over from the previous probe would be read as this vendor.
    if not close_vendor_popup(page, log_path):
        raise RuntimeError(
            "A Vendor Address popup would not close. Stopping rather than "
            "reading a stale popup as the next vendor's answer.")

    # A leftover character here silently corrupts THIS code and every probe
    # after it, so a box that will not empty stops the run.
    if not clear_code_box(page, box, log_path):
        raise RuntimeError(
            f"The vendor code box would not empty before typing '{code}'. "
            "Stopping rather than typing this code onto leftover text and "
            "reporting a good vendor as not found.")
    count, sample = probe_dropdown(page, box, code, items,
                                   delay_ms=typing_delay_ms)

    # One more grace period before anything is concluded. The live run counted
    # a list that had not finished loading and read it as "no such vendor".
    try:
        page.wait_for_timeout(AFTER_TYPING_SETTLE_MS)
    except Exception:
        pass
    if count == 0:
        # Re-count now the list has had its extra moment.
        try:
            count = page.locator(items).count()
        except Exception:
            pass

    # WHAT THE BOX ACTUALLY HOLDS, read before anything else touches the form.
    # Bottomline completes the code while it is being typed -- '762-' becomes
    # '762-001' with the added part selected -- so what is in the box is not
    # reliably what we sent. Until 2026-09-09 nothing ever read it back, which
    # meant a probe of the wrong text looked identical in the log to a probe of
    # the right one. Now the difference is on the record.
    box_held = read_box_value(page, box)

    # READ THE FORM BEFORE ANY POPUP IS OPENED. This is the whole lesson of the
    # Master Maker extension: everything except the street line is already on
    # screen, so it is captured first and nothing that happens to the popup
    # afterwards can cost us the row.
    form = gather_visible_data(page)
    say(log_path,
        f"    form read -> vendor_code={form.get('vendor_code', '')!r} "
        f"vendor={form.get('vendor', '')!r} "
        f"property={form.get('property', '')!r} "
        f"package={form.get('integration_package', '')!r}")

    # The street line, and only the street line, needs the popup -- the operator
    # confirmed it is needed for the master. It is no longer the witness.
    found = open_and_read_vendor_popup(page, log_path) if want_address else {}

    differs = "" if codes_match(box_held, code) else "  <- NOT what was typed"
    say(log_path,
             f"  typed '{code}' under {package}: {count} match(es) {sample} "
             f"| box holds '{box_held}'{differs} "
             f"| form: vendor_code '{form.get('vendor_code', '')}' "
             f"vendor '{form.get('vendor', '')}' "
             f"property '{form.get('property', '')}' "
             f"package '{form.get('integration_package', '')}' "
             f"-> popup: '{found.get('name', '')}' ({found.get('code', '')}) "
             f"{found.get('street', '')} {found.get('city', '')} "
             f"{found.get('state', '')} {found.get('zip', '')}")

    # A popup left open blocks EVERY click after it -- ExtJS lays a modal mask
    # over the page. This is checked HERE, before retype_full_then_clear(), and
    # not at the start of the next probe: that ordering is what turned a jammed
    # popup into a 30-second Playwright timeout and a raw traceback on
    # 2026-09-09 instead of a clean stop.
    if want_address and not close_vendor_popup(page, log_path):
        raise RuntimeError(
            "The Vendor Address popup would not close, and while it is open its "
            "modal mask blocks every click on the form. Stopping cleanly rather "
            "than timing out. Re-run with --no-address to skip the popup "
            "entirely; the vendor name, code, city and ZIP do not need it.")

    # Guarded, because it is the one browser call here that can be blocked by
    # something still on screen -- and losing the whole run to a box that would
    # not reset is a worse outcome than carrying on with a row already captured.
    try:
        retype_full_then_clear(page, box, code)
    except Exception as error:
        say(log_path, f"    could not reset the code box: {error}")

    return attempt(package, code, count, found, sample, box_held, form)


# --------------------------------------------------------------------------
# Pausing when a vendor will not load (operator's instruction, 2026-09-09)
# --------------------------------------------------------------------------
# WHAT CHANGED AND WHY
# --------------------
# Until now a vendor that did not load was written down as NOT_FOUND and the
# run moved straight on. That is fine for a genuinely dead code and wrong for
# everything else -- a slow page, a package box that had not settled, a code
# box holding a leftover character. Those are all fixable in two seconds by the
# person sitting in front of the screen, and every one of them was being filed
# as a permanent finding instead.
#
# So the run now STOPS on that vendor and hands the browser back. The operator
# fixes whatever is wrong, presses ENTER, and the script clicks Vendor Address
# again and reads it -- the same vendor, not the next one.
#
# WHAT COUNTS AS "DID NOT LOAD"
# -----------------------------
# _is_hit() -- the popup showed back THE CODE WE TYPED. So the pause fires both
# when no popup could be read at all AND when a popup named somebody else,
# because the second of those is the code box failing to clear, which is the
# bug that quietly corrupts every row after it. Seeing it is the point.
#
# Phase 0 deliberately does NOT pause. A calibration miss is a RESULT there --
# "this code does not resolve under this package" is half the table it is
# trying to build -- so stopping to fix it would destroy the measurement.
PAUSE_RETRY = "retry"
PAUSE_SKIP = "skip"
PAUSE_STOP_ASKING = "stop_asking"
PAUSE_QUIT = "quit"

# Unknown input maps to RETRY on purpose. A typo at this prompt must never be
# the thing that silently skips a vendor -- retrying costs a few seconds and
# asks again; skipping writes a wrong answer and moves on.
_PAUSE_CHOICES = {"": PAUSE_RETRY, "r": PAUSE_RETRY, "retry": PAUSE_RETRY,
                  "s": PAUSE_SKIP, "skip": PAUSE_SKIP,
                  "a": PAUSE_STOP_ASKING, "all": PAUSE_STOP_ASKING,
                  "q": PAUSE_QUIT, "quit": PAUSE_QUIT}

PAUSE_PROMPT = ("  [ENTER] look again   [s] skip this vendor   "
                "[a] stop asking for the rest of the run   [q] stop here : ")


def read_pause_choice(answer):
    """Map what the operator typed at the pause to one of the four actions."""
    return _PAUSE_CHOICES.get((answer or "").strip().lower(), PAUSE_RETRY)


def pause_message(master_row, one):
    """What the operator is shown when a vendor will not load.

    It says which vendor, what was typed, under which package, and what
    Bottomline showed instead -- everything needed to decide what to do without
    scrolling back or opening a file.
    """
    name = (master_row or {}).get("Vendor Name", "") or "(no name)"
    typed = one.get("code", "") or "(nothing)"
    package = one.get("package", "") or "(none)"
    shown = one.get("popup_name", "")
    shown_code = one.get("popup_code", "")

    lines = ["", "  " + "-" * 68,
             f"  PAUSED -- this vendor did not load.",
             f"    master row : {name}",
             f"    typed      : {typed}   under {package}",
             f"    matches    : {one.get('count', 0)}"]
    if shown_code or shown:
        lines.append(f"    but the popup showed: {shown} ({shown_code})"
                     "   <- the box may not have cleared")
    else:
        lines.append("    the Vendor Address popup showed nothing we could read")
    lines += [
        "",
        "  Fix it in the browser if you can -- re-pick the package, retype the",
        "  code, or just give the page a moment -- then choose below.",
        "  Nothing has been committed into the invoice.",
        "  " + "-" * 68]
    return "\n".join(lines)


def reprobe_after_fix(page, selectors, code, package, log_path,
                      want_address=True):
    """Click Vendor Address again and read it, after the operator fixed the screen.

    The code is deliberately NOT retyped. The operator may have just corrected
    the box by hand, and retyping would undo the very fix we stopped to let them
    make. This is the "continue from there -- clicking vendor address and
    fetching the needed data" the operator asked for, exactly and only that.
    """
    try:
        count = page.locator(selectors["dropdown_item"]).count()
    except Exception:
        count = 0

    # Read the box here too -- this is the ONE moment it is most likely to hold
    # something we never typed, because the operator has just corrected it by
    # hand. Without this the log would credit the fix to the code we sent.
    box_held = read_box_value(page, selectors["fill"]["vendor_code"])

    # Same order as probe_one_code: the form first, the popup second. If the
    # operator's fix worked, the form already proves it.
    form = gather_visible_data(page)
    found = open_and_read_vendor_popup(page, log_path) if want_address else {}

    say(log_path,
             f"  RETRY after operator fix -- '{code}' under {package}: "
             f"{count} match(es) | box holds '{box_held}' "
             f"| form: vendor_code '{form.get('vendor_code', '')}' "
             f"vendor '{form.get('vendor', '')}' "
             f"-> popup: '{found.get('name', '')}' "
             f"({found.get('code', '')})")

    if want_address:
        close_vendor_popup(page, log_path)
    return attempt(package, code, count, found, None, box_held, form)


def pause_until_loaded(page, selectors, failed, log_path, pause_state,
                       master_row, ask=input, want_address=True):
    """Stop and let the operator fix a vendor that did not load.

    Called ONCE per master row, after every package that row was going to be
    tried under has already been tried -- never after a single probe. A miss
    under the claimed package is not a failure while the other package is still
    to come, and pausing there would ask the operator to fix something the
    script was about to answer by itself a second later.

    `failed` is the last attempt made for the row. Returns a NEW attempt once
    the vendor loads, or None when the operator skips or turns pausing off (the
    caller then keeps the failed attempt and its honest verdict). Raises
    RuntimeError when they choose to stop, which main() already handles by
    keeping every finished batch and printing the --resume line.

    `pause_state` carries the "stop asking" choice across the whole run, so a
    master full of genuinely dead codes cannot turn into a hundred prompts.
    """
    code = failed.get("code", "")
    package = failed.get("package", "")
    one = failed

    while not _is_hit(one) and pause_state.get("asking", True):
        print(pause_message(master_row, one))
        say(log_path, f"  PAUSED on '{code}' under {package} -- "
                           "waiting for the operator.")
        choice = read_pause_choice(ask(PAUSE_PROMPT))

        if choice == PAUSE_QUIT:
            say(log_path, "  operator chose to stop at this vendor.")
            raise RuntimeError(
                "You chose to stop at "
                f"'{(master_row or {}).get('Vendor Name', '')}' (code '{code}').")

        if choice == PAUSE_SKIP:
            say(log_path, "  operator skipped this vendor.")
            return None

        if choice == PAUSE_STOP_ASKING:
            pause_state["asking"] = False
            say(log_path, "  operator turned the pause OFF for the rest "
                               "of the run.")
            print("  Pausing is off for the rest of this run. Vendors that do "
                  "not load are recorded as they are and the run carries on.")
            return None

        one = reprobe_after_fix(page, selectors, code, package, log_path,
                                want_address)

    return one if _is_hit(one) else None


def run_phase0(page, selectors, rows, state, log_path,
               typing_delay_ms=VENDOR_CODE_TYPING_DELAY_MS):
    """Type the calibration codes under BOTH packages and read the section 4 table.

    Runs on every invocation, not only the first: a Bottomline release could
    change this behaviour under us, and the meaning of the package column for a
    whole run depends on the answer.
    """
    picked = pick_calibration_rows(rows)
    say(log_path, f"Phase 0: calibrating on {len(picked)} vendor(s).")
    print(f"\nPhase 0 -- calibrating on {len(picked)} known vendors "
          f"({len(picked) * 2} probes, about 90 seconds).")

    matched = {id(row): [] for row in picked}
    for package in DEFAULT_ORDER:
        if not ensure_package(page, selectors, package, state, log_path):
            return ("stop", False,
                    f"Phase 0 could not select the {package} package, so nothing "
                    "could be calibrated. Nothing was probed and nothing written.")
        for row in picked:
            # want_address=False: Phase 0 only asks whether a code resolves,
            # and form_confirms() answers that without a popup. Skipping it here
            # removes 10 popup open/close cycles from the slowest part of a run.
            one = probe_one_code(page, selectors, row["ERP Vendor ID"],
                                 package, log_path, typing_delay_ms,
                                 want_address=False)
            if _is_hit(one):
                matched[id(row)].append(package)

            # Phase 0 is 90 seconds of silence otherwise, and it is the part
            # most likely to reveal that nothing is working at all.
            mark = "HIT " if _is_hit(one) else "miss"
            print(f"  [{mark}] {package:<8} {one['code']:<12} "
                  f"-> {one['popup_name'][:30] or '(no popup)'} "
                  f"({one['popup_code']})")

    results = [calibration_result(row["Integration Package"], matched[id(row)])
               for row in picked]
    action, filters, reason = calibration_verdict(results)
    say(log_path, f"Phase 0 verdict: {action} (code_box_filters={filters})")
    say(log_path, f"Phase 0 reason: {reason}")
    return action, filters, reason


def probe_batch(page, selectors, batch, code_box_filters, state, log_path, when,
                typing_delay_ms=VENDOR_CODE_TYPING_DELAY_MS,
                pause_state=None, ask=input, want_address=True):
    """Probe one batch of vendors and return their probed rows.

    Each row is probed under the package it claims. Only when that comes back
    empty is the other package tried -- and that second probe is what turns a
    silent "not found" into a WRONG_PACKAGE finding, which is todo 0h.

    A vendor that will not load stops the run and waits for the operator --
    see pause_until_loaded(), which is called ONCE per row, after every package
    that row was going to be tried under has been tried. A miss under the
    claimed package is not a failure yet while the other package is still to
    come, and pausing there would ask the operator to fix something the script
    was about to answer by itself a second later.
    """
    pause_state = {"asking": True} if pause_state is None else pause_state
    out = []
    for row in batch:
        code = (row.get("ERP Vendor ID") or "").strip()
        if not code:
            verdict, package, best = classify_probe(code, "", [])
            skipped = probed_row(row, verdict, package, best, 0, [], when)
            out.append(skipped)
            print(describe_probe(skipped))
            continue

        claimed = normalise_master_package(row.get("Integration Package", ""))
        claims_a_package = claimed in KNOWN_PACKAGES

        if not code_box_filters:
            # Phase 0 proved the box ignores the package, so a second probe
            # under the other one would return the same answer. One probe per
            # row instead of two roughly halves a 70-minute run.
            order = [claimed] if claims_a_package else [DEFAULT_ORDER[0]]
        elif claims_a_package:
            order = [claimed]
        else:
            # No claim: probe BOTH, because "matched under exactly one" is what
            # PACKAGE_LEARNED means and "matched under both" is what it does not.
            order = list(DEFAULT_ORDER)

        attempts = []
        for package in order:
            if not ensure_package(page, selectors, package, state, log_path):
                continue
            attempts.append(probe_one_code(page, selectors, code, package,
                                           log_path, typing_delay_ms,
                                           want_address))

        # The claimed package found nothing -- ask the other one before calling
        # this a dead code, or every WRONG_PACKAGE row is reported as NOT_FOUND.
        if (code_box_filters and claims_a_package
                and not any(_is_hit(one) for one in attempts)):
            for package in KNOWN_PACKAGES:
                if package == claimed:
                    continue
                if ensure_package(page, selectors, package, state, log_path):
                    attempts.append(probe_one_code(page, selectors, code,
                                                   package, log_path,
                                                   typing_delay_ms,
                                                   want_address))

        # NOTHING loaded for this row under any package it was tried with. Hand
        # the browser back rather than filing a finding the operator could have
        # fixed in two seconds (their instruction, 2026-09-09). A fix produces a
        # real attempt that is appended and classified like any other; a skip
        # returns None and the honest failure stands.
        if attempts and not any(_is_hit(one) for one in attempts):
            fixed = pause_until_loaded(page, selectors, attempts[-1], log_path,
                                       pause_state, row, ask, want_address)
            if fixed is not None:
                attempts.append(fixed)

        verdict, package, best = classify_probe(
            code, row.get("Integration Package", ""), attempts,
            code_box_filters=code_box_filters)
        count = max([one["count"] for one in attempts], default=0)
        sample = next((one["sample"] for one in attempts if one["sample"]), [])
        done = probed_row(row, verdict, package, best, count, sample, when)
        out.append(done)

        # Show it as it happens. An hour is a long time to wait before finding
        # out a run went wrong on row 3.
        print(describe_probe(done))
        say(log_path, describe_probe(done))
    return out


# Ctrl+C raises KeyboardInterrupt, a BaseException, so every `except Exception`
# in this file misses it. These two facts live at module level so the handler at
# the bottom can still write a resume line once main()'s locals are gone.
#
# This is NOT invoice_recorder.log_interrupted(): that one prints
# "python invoice_recorder.py --start-row N", which would be the wrong command
# and the wrong resume model. The prober resumes by BATCH, from its checkpoint.
_PROBE_PROGRESS = {"log_path": None, "batch": None, "total": None}


def log_probe_interrupted():
    """Print and log a resume line after a Ctrl+C. Never raises."""
    log_path = _PROBE_PROGRESS["log_path"]
    batch = _PROBE_PROGRESS["batch"]
    total = _PROBE_PROGRESS["total"]

    where = ("before the first batch" if batch is None
             else f"during batch {batch} of {total}")
    resume = "python prober\\verify_master.py --resume"

    print(f"\n\nSTOPPED by Ctrl+C {where}.")
    print(f"  Resume with:  {resume}")
    print("  Every batch already finished is safe on disk -- at most the rows")
    print("  of the batch in flight need probing again.")
    print("  Nothing was saved into Bottomline. The invoice on screen was only read.")

    if log_path is not None:
        try:
            say(log_path,
                     f"Run INTERRUPTED by Ctrl+C {where}. Resume with: {resume}")
            print(f"  Log: {log_path}")
        except Exception:
            pass


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Ask Bottomline what each vendor code really is. Types and "
                    "reads only -- nothing is ever saved.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Probe only this many vendors. Use --limit 25 for "
                             "the first real run: one batch, about 2 minutes.")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help="Vendors per write-and-compare cycle. Default 25.")
    parser.add_argument("--resume", action="store_true",
                        help="Carry on from the last completed batch.")
    parser.add_argument("--csv", type=Path, default=VENDORS_CSV,
                        help="The vendor master to probe. Defaults to "
                             "masters\\vendors.csv.")
    parser.add_argument("--typing-delay", type=int,
                        default=VENDOR_CODE_TYPING_DELAY_MS,
                        help=f"Milliseconds between keystrokes in the vendor "
                             f"code box (default {VENDOR_CODE_TYPING_DELAY_MS}). "
                             f"RAISE THIS if a run reports a lot of NOT_FOUND: "
                             f"typing faster than Bottomline's suggestion list "
                             f"loads looks exactly like a code that does not "
                             f"exist.")
    parser.add_argument("--skip-phase0", action="store_true",
                        help="Go straight to row 1 without the calibration. "
                             "The names and codes are still verified, but the "
                             "package column is reported as UNVERIFIED rather "
                             "than guessed, so no row can come back CONFIRMED. "
                             "Use this when you need the run to reach the "
                             "master no matter what.")
    parser.add_argument("--no-address", action="store_true",
                        help="Never open the Vendor Address popup. The vendor "
                             "name, code, city and ZIP all come off the FORM "
                             "and do not need it -- only the street line does. "
                             "Use this if the popup ever jams again: the run "
                             "gets faster and cannot be blocked by a modal.")
    parser.add_argument("--no-pause", action="store_true",
                        help="Do not stop when a vendor fails to load. Records "
                             "it and carries on, the way the script behaved "
                             "before 2026-09-09.")
    args = parser.parse_args()

    if args.batch_size < 1:
        sys.exit("STOPPED: --batch-size must be 1 or more.")
    if args.typing_delay < 0:
        sys.exit("STOPPED: --typing-delay cannot be negative.")
    if args.limit is not None and args.limit < 1:
        sys.exit("STOPPED: --limit must be 1 or more.")

    master_rows = load_master_rows(args.csv)
    if not master_rows:
        sys.exit(f"STOPPED: no vendors could be read from {args.csv}.")

    # The master's own order, top to bottom -- so batch 1 IS rows 1-25 of
    # vendors.csv and the operator can follow a live run in the spreadsheet.
    rows = rows_in_master_order(master_rows)
    start = resume_start_index(read_checkpoint(CHECKPOINT_FILE)) if args.resume else 0
    if start >= len(rows):
        sys.exit("STOPPED: the checkpoint says every row has already been probed.\n"
                 f"Delete {CHECKPOINT_FILE} to start again from the beginning.")
    rows = rows[start:]
    if args.limit is not None:
        rows = rows[:args.limit]

    batches = make_batches(rows, args.batch_size)
    batches_already_done = start // args.batch_size

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"probe_{datetime.now():%Y-%m-%d_%H%M}.txt"
    _PROBE_PROGRESS["log_path"] = log_path
    _PROBE_PROGRESS["total"] = len(batches)
    say(log_path, f"Probe started {datetime.now():%Y-%m-%d %H:%M}")
    say(log_path, f"{len(rows)} vendor(s), {len(batches)} batch(es) of "
                       f"{args.batch_size}, starting at master row {start + 1}")

    # A FRESH run starts on a clean sheet: the previous vendors_probed.csv is
    # moved into masters\archive\ rather than appended to, so one file never
    # ends up holding two runs' answers for the same vendor. --resume is the
    # exception -- it is meant to continue the file that is already there.
    #
    # The stale checkpoint is zeroed at the same moment. Without that, a --resume
    # after an abandoned fresh run would read "100 rows already done" from the
    # old checkpoint while the file holding those 100 rows had just been moved
    # away -- skipping a hundred vendors that were never actually probed.
    if not args.resume:
        moved = archive_probe_csv(PROBED_CSV, ARCHIVE_DIR)
        if moved:
            print(f"Previous results moved to: {moved}")
            say(log_path, f"Previous {PROBED_CSV.name} archived as {moved}")
        write_checkpoint(CHECKPOINT_FILE, 0, len(batches), args.batch_size)

    print(f"\n{len(rows)} vendor(s) to probe, in {len(batches)} batch(es) of "
          f"{args.batch_size}.")
    print("Nothing will be saved. The invoice opened is only ever read from.\n")

    from dotenv import load_dotenv
    from playwright.sync_api import sync_playwright

    load_dotenv(PROJECT / ".env")
    url = os.getenv("BOTTOMLINE_URL", "").strip()
    username = os.getenv("BOTTOMLINE_USERNAME", "").strip()
    password = os.getenv("BOTTOMLINE_PASSWORD", "").strip()
    if not url or not username or not password:
        sys.exit("STOPPED: .env is missing BOTTOMLINE_URL, BOTTOMLINE_USERNAME "
                 "or BOTTOMLINE_PASSWORD.")

    selectors = load_selectors()
    state = {"package": None}
    # Shared by every batch, so "stop asking" said once holds for the whole run.
    pause_state = {"asking": not args.no_pause}

    # On a --resume the earlier batches are already in vendors_probed.csv but
    # not in memory. Reading them back means the review workbook covers the
    # WHOLE run, not just the part after the interruption.
    all_probed = load_master_rows(PROBED_CSV) if args.resume else []
    reason = "not run"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = (browser.new_context(storage_state=str(SESSION_FILE))
                   if SESSION_FILE.exists() else browser.new_context())
        if SESSION_FILE.exists():
            print("Reusing your saved Bottomline session.")

        page = context.new_page()

        # DIAGNOSTIC (2026-09-10) -- temporary. Logs every XHR/fetch response
        # so we can see which network call actually fills in the Vendor
        # Address popup, instead of guessing from a fixed wait. Read-only:
        # it only listens, it changes nothing about what the page does.
        # Remove once that call is identified and popup_text()'s wait is
        # switched to waiting on it directly.
        def _log_network_response(response):
            try:
                rtype = response.request.resource_type
                if rtype in ("xhr", "fetch"):
                    say(log_path,
                             f"    [net] {response.status} {rtype} {response.url}")
            except Exception:
                pass
        page.on("response", _log_network_response)

        page.goto(url)
        page.wait_for_timeout(2000)

        if page.locator("input[type='password']").count() > 0:
            print("Logging in...")
            try:
                page.locator("input[type='text'], input[type='email']").first.fill(username)
                page.locator("input[type='password']").first.fill(password)
                page.keyboard.press("Enter")
            except Exception as error:
                say(log_path, f"Login attempt failed: {error}")
                print(f"Could not complete the login automatically: {error}")

        print("\nIf a security code was requested, complete it now in the browser.")
        input("Press ENTER once you are fully logged in... ")
        try:
            context.storage_state(path=str(SESSION_FILE))
        except Exception:
            pass  # not fatal -- the next run just logs in again

        def note(text):
            print(text)
            say(log_path, text)

        # ---- Phase 1: get a form on screen ----
        # The boxes do not exist until an image is open for indexing. That is
        # the ONLY reason an invoice is needed, and nothing on it is committed.
        # The OPERATOR opens it: the prober does not care which invoice it is,
        # so reading the queue to choose one was pure cost.
        if not wait_for_indexing_form(page, selectors, note):
            sys.exit("\nSTOPPED: no indexing form was found on screen, so there "
                     "are no boxes to probe.\nNothing was written.")

        # ---- Phase 2: calibrate. This can end the run. ----
        # --skip-phase0 exists because the calibration is allowed to cancel a
        # run before a single master row is touched, and four attempts have now
        # ended without producing any data at all. Skipping it is NOT a way to
        # assume the answer: code_box_filters stays False, which is what makes
        # classify_probe() report every package as UNVERIFIED_PACKAGE instead of
        # CONFIRMED. Names, codes and addresses are still verified exactly as
        # before -- only the package column goes unjudged, which is honest,
        # because without the calibration nothing about it has been measured.
        if args.skip_phase0:
            code_box_filters = False
            reason = ("SKIPPED at the operator's request. The package column "
                      "was not calibrated, so no row can be CONFIRMED -- every "
                      "match is reported as UNVERIFIED_PACKAGE. Names, codes "
                      "and addresses are verified as normal.")
            note("Phase 0 SKIPPED (--skip-phase0). The package column will not "
                 "be judged.")
        else:
            action, code_box_filters, reason = run_phase0(
                page, selectors, master_rows, state, log_path, args.typing_delay)
            print(f"\nPhase 0: {reason}\n")
            if action == "stop":
                sys.exit("STOPPED after Phase 0. Nothing was probed and nothing "
                         "was written.\nThe invoice on screen was only read "
                         "from -- close it or navigate away as you normally "
                         "would.\nTo go straight to row 1 without this check, "
                         "run again with --skip-phase0.")

        # ---- Phases 3 and 4: probe, write, compare, repeat ----
        for index, batch in enumerate(batches, start=1):
            _PROBE_PROGRESS["batch"] = index
            when = f"{datetime.now():%Y-%m-%d %H:%M}"
            note(f"Batch {index} of {len(batches)} -- {len(batch)} vendor(s)...")

            try:
                batch_rows = probe_batch(page, selectors, batch,
                                         code_box_filters, state, log_path,
                                         when, args.typing_delay, pause_state,
                                         want_address=not args.no_address)
            except RuntimeError as error:
                # Raised when a popup will not close, when the code box will not
                # empty, or when the operator chose to stop at a pause.
                # Everything from the earlier batches is already on disk, so
                # stopping here costs this batch and nothing else.
                say(log_path, f"STOPPED mid-run -- {error}")
                sys.exit(f"\nSTOPPED: {error}\n"
                         f"Batches already written are safe. Resume with:\n"
                         f"  python prober\\verify_master.py --resume")
            append_probed_rows(PROBED_CSV, batch_rows)
            all_probed.extend(batch_rows)
            write_review_workbook(REVIEW_XLSX, route_to_sheets(all_probed),
                                  summary_lines(all_probed, reason),
                                  f"{datetime.now():%Y-%m-%d}")
            write_checkpoint(CHECKPOINT_FILE, batches_already_done + index,
                             batches_already_done + len(batches), args.batch_size)
            note(f"  written: {PROBED_CSV.name} and {REVIEW_XLSX.name}")

        # ---- Phase 5: leave the invoice exactly as it was found ----
        # No navigation. The invoice was only ever typed into and read back, so
        # there is nothing to undo -- and a failed navigation at this point
        # would turn a finished run into a traceback.
        note("\nFinished probing. The invoice on screen was only read from -- "
             "close it or navigate away as you normally would.")

    print("\nDone. Nothing was saved into Bottomline.")
    for line in summary_lines(all_probed, reason):
        print(f"  {line}")
    print(f"\n  {PROBED_CSV}\n  {REVIEW_XLSX}\n  {log_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_probe_interrupted()
