"""master_index.py -- look up a SECOND master column (the property's Package,
or a vendor's ERP Vendor ID) for a name we have matched, but ONLY when the
match was confident.

WHY THIS EXISTS (plain English):
    vendor_lookup.Lookup tells us the correct NAME and how sure it is
    (READ_OK vs NEEDS_REVIEW). Sometimes we also need another value tied to
    that name -- the integration package a property belongs to, or the ERP
    Vendor ID that makes Bottomline load a vendor automatically. This module
    fetches that value, and refuses to fetch it unless the name match was a
    confident one, so an uncertain name never drags a confident-looking code
    or package along with it (see spec P5/P6, rule D4).

Depends only on vendor_lookup (_normalise) -- no new libraries.
"""
from vendor_lookup import _normalise


def build_index(rows, name_col, value_col):
    """Map normalised master name -> that row's value_col (stripped).

    A blank/missing value becomes "" (not dropped) so callers can tell "known
    name, no value" from "unknown name". A row with a blank name is skipped --
    there is nothing to key it by. First occurrence wins on duplicates."""
    index = {}
    for row in rows:
        name = row.get(name_col)
        if not name:
            continue
        index.setdefault(_normalise(name), str(row.get(value_col) or "").strip())
    return index


def extra_for_confident_match(match, index):
    """The indexed value for a CONFIDENT match, else "".

    Confident means match.status == "READ_OK" (an alias or exact hit). On
    anything less we return "" so the caller acts only on the raw name."""
    if match.status != "READ_OK":
        return ""
    return index.get(_normalise(match.value), "")


def value_to_type(raw_name, lookup, index):
    """The text to type into a search box: the indexed value (e.g. the ERP
    Vendor ID) when the name is a confident match, otherwise the raw name
    unchanged -- so an uncertain name still goes through the dropdown for a
    human to see, never a guessed code."""
    match = lookup.match(raw_name)
    extra = extra_for_confident_match(match, index)
    return extra if extra else raw_name
