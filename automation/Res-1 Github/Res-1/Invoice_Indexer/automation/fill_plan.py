"""
fill_plan.py -- deciding WHICH integration package an invoice belongs to, and
in what order the boxes get filled. No browser, no Bottomline, no spreadsheet.

Split out of invoice_recorder.py for the same reason queue_navigator.py was:
the decisions below change where a client's invoice ends up in their books, so
they are kept as plain functions that can be proved right on a laptop with no
connection to anything. Run those checks with:
    python automation\\selftest_queue.py

WHAT CHANGED, AND WHY (2026-08-14)
    The script used to fill the boxes in whatever order they happened to sit in
    selectors.json, with the Integration Package typed in like any other value,
    straight from the spreadsheet column.

    That assumed the operator already knew the right package. The new rule,
    agreed with the team on 2026-08-14, is that the script works it out and
    PROVES it: a property only appears in the Property dropdown if it belongs
    to the integration package currently selected. So selecting a package and
    then typing the property is a live test of whether the two go together.

    Package first, property as the test, invoice details last.

THE ONE THING THIS FILE REFUSES TO DO
    It never invents a package name. If the spreadsheet holds something that is
    not YARDI or INTACCT, that value is ignored rather than typed into
    Bottomline -- see package_candidates(). Typing an unrecognised package into
    a live accounting system to "see what happens" is exactly the kind of guess
    this project does not make.

WHAT CHANGED, AND WHY (2026-09-03)
    Added property_candidates_for_package(): a YARDI property may carry a CODE
    (masters\\properties.csv) that loads it deterministically, exactly like a
    vendor's ERP Vendor ID. This function decides whether to try that code
    before the name. It depends on master_index.value_to_type() -- still no
    browser, still a plain function provable offline, just one more file of
    stdlib-only logic in the chain.
"""

from master_index import value_to_type

# The only two integration packages in use. Confirmed by the team 2026-08-14.
#
# If a third is ever added, add it here AND decide where it belongs in the
# default order below -- the script tries these in sequence, so the order is a
# real decision, not a formatting detail.
KNOWN_PACKAGES = ("YARDI", "INTACCT")

# The order used when the spreadsheet gives no usable steer.
DEFAULT_ORDER = ("YARDI", "INTACCT")

# The plain boxes filled in Phase C, in the order an operator would work down
# the screen. Kept separate from the field map in selectors.json because that
# file describes WHERE each box is, not WHEN it gets filled.
DETAIL_FIELDS = ("invoice_number", "invoice_date", "invoice_due_date", "amount")

# Handled by Phases A and B, so never repeated in Phase C.
PHASE_A_AND_B_FIELDS = ("integration_package", "property", "vendor")


def normalise_package(text):
    """Put a package name into the one form used for every comparison.

    Forgives case and stray spaces -- 'intacct ' and 'INTACCT' are the same
    package, and Excel cells collect trailing spaces. Forgives nothing else.
    """
    if not text:
        return ""
    return " ".join(str(text).split()).upper()


def is_known_package(text):
    """Is this one of the packages we are willing to type into Bottomline?"""
    return normalise_package(text) in KNOWN_PACKAGES


def package_candidates(sheet_value):
    """Which integration packages to try, in the order to try them.

    The spreadsheet's own value goes first when it is one we recognise. That
    keeps the operator's knowledge as the opening guess, so a correctly filled
    sheet costs no extra typing and the search only earns its keep when the
    sheet is wrong or blank.

    A blank cell, or anything that is not YARDI or INTACCT, falls back to
    DEFAULT_ORDER. Note what does NOT happen: an unrecognised value is never
    passed through to be typed. The caller is expected to say plainly in the
    log that it was ignored -- see establish_package() in invoice_recorder.py.

    Always returns every known package, so "not under the first one" can always
    be followed by actually checking the other.
    """
    wanted = normalise_package(sheet_value)
    if wanted in KNOWN_PACKAGES:
        return [wanted] + [p for p in DEFAULT_ORDER if p != wanted]
    return list(DEFAULT_ORDER)


def package_verdict(match_count):
    """What a property dropdown's match count means for the package on screen.

    Returns one of:
      "confirmed" -- exactly one match. The property is under this package.
      "ambiguous" -- several matches. The property IS under this package, but
                     the script must not choose between them; the operator does.
      "not_here"  -- nothing matched. Treated as "this property does not belong
                     to this package", which is the whole basis of the search.

    Worth being honest about "not_here": an empty dropdown can also mean the
    property is spelled differently in the sheet than in Bottomline, or that
    the dropdown was simply slower than the script waited. Both look identical
    to "wrong package" from here. That is why a row where NEITHER package
    matches is skipped and logged rather than filled -- the script never picks
    a package it could not demonstrate.
    """
    if match_count == 1:
        return "confirmed"
    if match_count > 1:
        return "ambiguous"
    return "not_here"


def detail_fields(fill_keys):
    """The Phase C boxes to fill, in order, given the field map's keys.

    Anything in the field map that Phases A and B do not handle and that is not
    already listed in DETAIL_FIELDS gets appended on the end rather than
    dropped. So if a column is added to selectors.json later and nobody thinks
    to update this file, the new box still gets filled -- quietly ignoring it
    would be the worse failure, because a missing value on an invoice is much
    harder to notice than one in an odd order.
    """
    present = list(fill_keys)
    ordered = [key for key in DETAIL_FIELDS if key in present]
    extras = [key for key in present
              if key not in PHASE_A_AND_B_FIELDS and key not in ordered]
    return ordered + extras


def property_candidates_for_package(package, property_value, property_lookup,
                                    property_code_index):
    """Which text(s) to try in the Property box for THIS package, in order.

    A YARDI property may have a CODE that loads it deterministically -- just
    like a vendor's ERP Vendor ID -- so try that FIRST, then fall back to the
    NAME. Intacct has no codes, so it is always name-only. value_to_type
    (master_index.py) already refuses to hand back a code unless the name
    match was CONFIDENT (an alias or exact hit) -- see its own docstring -- so
    an uncertain property name never tries a guessed code here either.

    property_lookup / property_code_index may be None/{} (no property master
    loaded yet) -- in that case this always falls back to the plain name,
    exactly as before this feature existed.
    """
    if package == "YARDI" and property_lookup is not None:
        coded = value_to_type(property_value, property_lookup, property_code_index)
        if coded and coded != property_value:
            return [coded, property_value]
    return [property_value]
