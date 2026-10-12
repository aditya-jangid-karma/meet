"""
rehearse_fill.py -- watch the new filling order work, with no browser at all.

WHAT THIS IS FOR
    The new rule is that the script works out the integration package itself,
    by selecting one and then checking whether the property appears in the
    Property dropdown. That is a real decision about a client's books, and the
    first time anybody should see it happen is NOT on a live Bottomline screen
    with a real invoice open.

    So this stands in a pretend Bottomline. It drives the REAL code --
    establish_package(), fill_autocomplete(), type_into(), detail_fields() are
    all imported from the actual script, not copied -- against a fake screen
    that answers dropdown questions from a small table written at the bottom of
    this file. What you read is the sequence that will happen live.

WHAT IT IS NOT
    It is not a test of Bottomline, and it proves nothing about selectors. The
    fake screen answers the way we BELIEVE Bottomline answers. If that belief
    is wrong, this rehearsal will happily be wrong in exactly the same way.
    What it does prove is the script's own decision-making: which package is
    tried first, what happens when a property is not under it, what gets typed
    afterwards, and in which order.

    It never opens a browser, never reads the spreadsheet, and never touches
    the network.

WHAT IT DOES NOT COVER
    The queue: finding, opening and verifying an invoice. That half is proved
    by queue_navigator.py's own offline tests plus the live run.

USAGE
    python automation\\rehearse_fill.py

KEEPING IT HONEST
    Phase A is the real establish_package(). Phases B and C are mirrored here
    in run_one_invoice() from the main loop in invoice_recorder.py -- about ten
    lines. If that loop changes, change this too, or the rehearsal starts
    describing a script that no longer exists.
"""

import builtins
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fill_plan import detail_fields  # noqa: E402
from invoice_recorder import (  # noqa: E402
    commit_plain_field,
    establish_package,
    fill_autocomplete,
    load_selectors,
    type_into,
)


# ---------------------------------------------------------------------------
# The pretend Bottomline
# ---------------------------------------------------------------------------

class FakeItem:
    """One row of a dropdown."""

    def __init__(self, text):
        self.text = text
        self.screen = None

    def inner_text(self, timeout=None):
        return self.text

    def click(self):
        self.screen.pick(self.text)

    def wait_for(self, state=None, timeout=None):
        return True


class FakeBox:
    """One box on the screen. Records what gets typed into it."""

    def __init__(self, screen, selector):
        self.screen = screen
        self.selector = selector

    def wait_for(self, state=None, timeout=None):
        return True

    def click(self):
        return None

    def fill(self, text):
        self.screen.typed[self.selector] = text
        if text == "":
            self.screen.note(f"cleared the {self.screen.name_of(self.selector)} box")

    def press(self, keys, delay=None):
        # The live clear_box() empties a search box with real keystrokes
        # (Control+a then Delete) instead of fill(""). Mirror the visible
        # effect here -- a Delete/Backspace empties the box -- so the rehearsal
        # narrates the clear the same way it used to when clear_box() called
        # fill(""). Control+a and other keys have no effect on the fake box.
        if "Delete" in keys or "Backspace" in keys:
            self.screen.typed[self.selector] = ""
            self.screen.note(f"cleared the {self.screen.name_of(self.selector)} box")

    def press_sequentially(self, text, delay=None):
        self.screen.type_text(self.selector, text)

    def type(self, text, delay=None):  # older Playwright
        self.screen.type_text(self.selector, text)

    def evaluate(self, script):
        return None

    def input_value(self, timeout=None):
        return self.screen.typed.get(self.selector, "")


class FakeLocatorList:
    """Whatever a selector matched. Dropdown items, or a single box."""

    def __init__(self, items):
        self.items = items

    @property
    def first(self):
        if not self.items:
            return MissingThing()
        return self.items[0]

    def nth(self, position):
        return self.items[position]

    def count(self):
        return len(self.items)


class MissingThing:
    """Stands in for a selector that matched nothing, and says so loudly."""

    def wait_for(self, state=None, timeout=None):
        raise TimeoutError("nothing matched that selector")

    def click(self):
        raise RuntimeError("tried to click something that is not on screen")

    def inner_text(self, timeout=None):
        raise RuntimeError("tried to read something that is not on screen")

    def input_value(self, timeout=None):
        raise RuntimeError("tried to read something that is not on screen")


class FakeScreen:
    """The indexing screen, as far as the script can tell.

    Knows which properties and vendors sit under each integration package, and
    answers dropdown questions accordingly -- which is the single behaviour the
    whole new design rests on.
    """

    def __init__(self, selectors, world):
        self.selectors = selectors
        self.world = world
        self.typed = {}
        self.selected_package = None
        self.picked = []
        self.item_selector = selectors["dropdown_item"]

        fill = selectors["fill"]
        self.package_selector = fill["integration_package"]
        self.property_selector = fill["property"]
        self.vendor_selector = fill["vendor"]
        self.names = {selector: key for key, selector in fill.items()}

    # -- narration -------------------------------------------------------

    def name_of(self, selector):
        return self.names.get(selector, selector)

    def note(self, text):
        print(f"        [screen] {text}")

    def type_text(self, selector, text):
        # APPENDS, because the live code now types a name as a growing prefix
        # (60% -> 75% -> full), adding characters rather than re-typing from
        # scratch. type_into() still clears with fill("") before it types, so a
        # full-value type lands correctly (append onto an emptied box).
        self.typed[selector] = self.typed.get(selector, "") + text
        self.note(f"typed '{text}' into the {self.name_of(selector)} box")

    def pick(self, text):
        self.picked.append(text)
        self.note(f"picked '{text}' from the dropdown")
        if self.last_selector == self.package_selector:
            self.selected_package = text
            self.note(f"integration package on screen is now {text}")

    # -- what the dropdown would show ------------------------------------

    @property
    def last_selector(self):
        """The box most recently typed into -- the one the dropdown belongs to."""
        return self._last

    def dropdown_items(self):
        selector = getattr(self, "_last", None)
        value = (self.typed.get(selector) or "").strip().lower()
        if not value:
            return []

        if selector == self.package_selector:
            return [p for p in self.world["packages"] if p.lower().startswith(value)]

        if selector == self.property_selector:
            if not self.selected_package:
                return []
            under = self.world["properties"].get(self.selected_package, [])
            return [p for p in under if value in p.lower()]

        if selector == self.vendor_selector:
            return [v for v in self.world["vendors"] if value in v.lower()]

        return []

    # -- the Playwright-shaped surface the script actually calls ----------

    def locator(self, selector):
        if selector == self.item_selector:
            items = []
            for text in self.dropdown_items():
                item = FakeItem(text)
                item.screen = self
                items.append(item)
            return FakeLocatorList(items)
        return FakeLocatorList([FakeBox(self, selector)])


class FakePage:
    """Only the handful of things the filling code asks a page to do."""

    def __init__(self, screen):
        self.screen = screen

    def locator(self, selector):
        # Remember which box is being addressed, so the dropdown knows whose
        # it is -- the real screen knows this because only one box has focus.
        fill_selectors = set(self.screen.names)
        if selector in fill_selectors:
            self.screen._last = selector
        return self.screen.locator(selector)

    def wait_for_timeout(self, milliseconds):
        return None


# ---------------------------------------------------------------------------
# Driving one invoice through the phases
# ---------------------------------------------------------------------------

def run_one_invoice(page, selectors, row, log_path):
    """Mirrors the per-invoice part of invoice_recorder.py's main loop.

    Phase A is the real function. Phases B and C are the same ten lines the
    live script runs -- see the note at the top of this file.
    """
    package, why_not = establish_package(page, selectors, row, log_path)

    if package is None:
        print(f"\n    RESULT: skipped -- {why_not}")
        print("    Nothing else would be typed. The run moves to the next invoice.")
        return "skipped"

    vendor_value = row.get("vendor", "")
    vendor_selector = selectors["fill"].get("vendor")
    if vendor_value and vendor_selector:
        fill_autocomplete(page, vendor_selector, vendor_value,
                          selectors["dropdown_item"], "vendor", log_path)

    for key in detail_fields(selectors["fill"].keys()):
        value = row.get(key, "")
        if not value:
            print(f"    {key}: blank in the spreadsheet -- left alone")
            continue
        box = type_into(page, selectors["fill"][key], value)
        commit_plain_field(page, box)
        print(f"    {key}: typed '{value}'")

    print(f"\n    RESULT: filled under {package}. The script now STOPS and waits")
    print("    for you to review and press Convert to Invoice yourself.")
    return "filled"


# ---------------------------------------------------------------------------
# The pretend world, and the scenarios worth watching
# ---------------------------------------------------------------------------

WORLD = {
    "packages": ["YARDI", "INTACCT"],
    "properties": {
        # Two properties starting "Gateway" on purpose: that is what makes
        # scenario 6 genuinely ambiguous instead of quietly picking one.
        "YARDI": ["Gateway Station", "Gateway Court", "Washington Court 12"],
        "INTACCT": ["Riverside Plaza", "Gateway Annex"],
    },
    "vendors": ["Canon Financial Services, Inc. (CHICAGO/60693-0149)",
                "Steps Appliance Repair LLC"],
}

BASE_ROW = {
    "invoice_number": "43711901",
    "invoice_date": "08/12/2026",
    "invoice_due_date": "09/01/2026",
    "amount": "412.14",
    "vendor": "Canon Financial Services, Inc. (CHICAGO/60693-0149)",
}


def scenario(title, why, row, scripted_answer=None):
    return {"title": title, "why": why, "row": row, "answer": scripted_answer}


SCENARIOS = [
    scenario(
        "The sheet is right first time",
        "Property is under the package the operator named. No searching needed.",
        dict(BASE_ROW, property="Gateway Station", integration_package="YARDI"),
    ),
    scenario(
        "The sheet names the wrong package",
        "THE point of the change. INTACCT is tried, the property is not under "
        "it, so YARDI is tried and confirms.",
        dict(BASE_ROW, property="Gateway Station", integration_package="INTACCT"),
    ),
    scenario(
        "The package column is blank",
        "Falls back to the fixed order, YARDI then INTACCT.",
        dict(BASE_ROW, property="Riverside Plaza", integration_package=""),
    ),
    scenario(
        "The sheet names a package that does not exist",
        "'SAGE' is ignored rather than typed into Bottomline, and both real "
        "packages are tried.",
        dict(BASE_ROW, property="Riverside Plaza", integration_package="SAGE"),
    ),
    scenario(
        "The property is under neither package",
        "The invoice is left completely alone and the run carries on.",
        dict(BASE_ROW, property="Nowhere House", integration_package="YARDI"),
    ),
    scenario(
        "Several properties match",
        "'Gateway' matches under YARDI; the script refuses to choose and hands "
        "you the browser. Your pick still confirms the package.",
        dict(BASE_ROW, property="Gateway", integration_package="YARDI"),
        scripted_answer="",
    ),
    scenario(
        "No property in the spreadsheet",
        "The property dropdown is the only proof available, so without one the "
        "invoice is skipped rather than classified on trust.",
        dict(BASE_ROW, property="", integration_package="YARDI"),
    ),
]


def main():
    selectors = load_selectors()
    log_path = Path(__file__).resolve().parent.parent / "logs" / "rehearsal.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Rehearsal -- no browser, no Bottomline.\n", encoding="utf-8")

    print("=" * 74)
    print(" REHEARSAL -- no browser opens, nothing connects to Bottomline.")
    print(" The pretend screen holds:")
    for package, properties in WORLD["properties"].items():
        print(f"   {package:<8} {', '.join(properties)}")
    print("=" * 74)

    results = []
    real_input = builtins.input

    for number, case in enumerate(SCENARIOS, start=1):
        print(f"\n\n{'-' * 74}")
        print(f"SCENARIO {number}: {case['title']}")
        print(f"  Why it matters: {case['why']}")
        row = case["row"]
        print(f"  Sheet says -- property: '{row['property']}'  "
              f"integration package: '{row['integration_package']}'")
        print("-" * 74)

        screen = FakeScreen(selectors, WORLD)
        page = FakePage(screen)

        if case["answer"] is not None:
            builtins.input = lambda prompt="", _a=case["answer"]: (
                print(f"{prompt}{_a or '<ENTER>'}") or _a)
        try:
            outcome = run_one_invoice(page, selectors, row, log_path)
        finally:
            builtins.input = real_input

        results.append((case["title"], outcome))

    print(f"\n\n{'=' * 74}")
    print(" SUMMARY")
    for title, outcome in results:
        print(f"   {outcome.upper():<8} {title}")
    print("=" * 74)
    print(f"\n Rehearsal log: {log_path}")
    print(" Nothing was typed into Bottomline. No browser was opened.\n")


if __name__ == "__main__":
    main()
