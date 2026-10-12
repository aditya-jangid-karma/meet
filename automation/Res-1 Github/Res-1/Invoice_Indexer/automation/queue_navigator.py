"""
queue_navigator.py -- finding invoices in the Bottomline indexing queue.

Split out of invoice_recorder.py so the decision-making below can be tested
without a browser, without Bottomline, and without touching a client system.
Run those tests with:  python automation\\selftest_queue.py

WHAT THIS FILE IS FOR
    The script used to assume a human had already opened an invoice for
    indexing. It had no way to get there itself, so it never found the Image
    Name box and every run stopped. This file is how it navigates: read the
    queue once, find each invoice by name, open it, and prove the right one
    opened before a single character is typed.

WHAT IT NEVER DOES
    It never presses Convert to Invoice, Save, Save as Exception or Delete.
    It gains navigation, not authority.

See docs/specs/2026-08-13_self-navigation-design.md, signed off 2026-08-13.
"""

import re

# The heading Bottomline puts at the top of the indexing screen. If the page
# does not start with this, the indexing screen did not open and the script is
# somewhere it did not intend to be.
HEADER_PREFIX = "Image Index -"

# Collapses runs of any whitespace into a single space.
WHITESPACE = re.compile(r"\s+")

# Pulls the 17 out of "Page 1 of 17" on the paging toolbar.
#
# Deliberately anchored on the word "Page". The same toolbar also carries
# "Displaying 1 - 25 of 417", and matching a bare "of <number>" would happily
# read the ROW count as a page count and walk 417 pages of a 17-page queue.
# The page number itself lives in an <input>, whose value is not part of the
# toolbar's text, so what this actually sees is "Page  of 17" -- hence \d* .
PAGE_TOTAL = re.compile(r"page\s*\d*\s*of\s*([\d,]+)", re.IGNORECASE)


def normalise_name(text):
    """Put an image name into the one form used for every comparison.

    Applied to BOTH sides of every comparison -- the spreadsheet value and the
    value read off the screen -- so the two can never be normalised differently.

    Rules, and why each exists:
      * strip and collapse whitespace -- Excel cells pick up stray spaces
      * ignore case -- operators and Excel are inconsistent about it, and two
        images in one queue differing only by case is implausible. If it ever
        did happen, build_queue_index() reports it as a duplicate and the run
        stops rather than guessing.
      * drop a trailing ".pdf" -- the queue shows names without an extension,
        but operators often paste the filename with one. Either form works.
    """
    if not text:
        return ""
    cleaned = WHITESPACE.sub(" ", str(text)).strip().lower()
    if cleaned.endswith(".pdf"):
        cleaned = cleaned[:-4].strip()
    return cleaned


def image_name_from_header(header_text):
    """Pull the image name out of "Image Index - <name>".

    Returns None if the heading is not an indexing screen at all. That None is
    the signal that Index Selected did not do what was expected -- which
    matters, because the delete icon sits on the same toolbar.

    Note it splits on the FIRST dash only, so an image name containing its own
    dashes survives intact.
    """
    if not header_text:
        return None
    text = WHITESPACE.sub(" ", str(header_text)).strip()
    if not text.lower().startswith(HEADER_PREFIX.lower()):
        return None
    return text[len(HEADER_PREFIX):].strip() or None


def build_queue_index(entries):
    """Turn [(image name, page number), ...] into a lookup, plus a duplicate list.

    Returns (index, duplicates):
      index      -- normalised name -> page number it was found on
      duplicates -- normalised names that appeared more than once

    Blank names are ignored rather than indexed. ExtJS grids render spacer and
    placeholder rows that carry no name, and indexing them would create a
    phantom entry that no spreadsheet row could ever match.
    """
    index = {}
    seen_twice = []

    for raw_name, page_number in entries:
        key = normalise_name(raw_name)
        if not key:
            continue
        if key in index:
            if key not in seen_twice:
                seen_twice.append(key)
            continue  # keep the first page seen; the run stops on duplicates anyway
        index[key] = page_number

    return index, seen_twice


def total_pages_from_toolbar(text):
    """Read how many pages the queue has out of the paging toolbar's text.

    "Page 1 of 17" -> 17.

    Returns None when the text carries no page count. None means "could not
    tell", NOT "one page" -- the caller falls back to watching the Next button
    rather than acting on a guessed number. A wrong number here would either
    cut the queue short (invoices silently declared missing) or overrun it.

    Why this exists: read_queue used to decide whether another page existed by
    looking for the word "disabled" in the CSS class of the Next arrow. In
    ExtJS that marker sits on the button WRAPPING the arrow, not on the arrow
    itself, so the answer risked being "yes, more pages" even on the last one.
    The queue states its own length on screen; believing it is far safer than
    inferring it from how a button is styled.
    """
    if not text:
        return None
    match = PAGE_TOTAL.search(WHITESPACE.sub(" ", str(text)))
    if not match:
        return None
    total = int(match.group(1).replace(",", ""))
    return total if total > 0 else None


# ---------------------------------------------------------------------------
# Everything below drives a real browser. Nothing below is covered by
# selftest_queue.py -- it is proved by the first live run instead.
# ---------------------------------------------------------------------------

# How long to wait for the grid to redraw after changing page, in milliseconds.
GRID_REDRAW_WAIT = 1500

# How long to keep CHECKING that the queue really changed page, and how often.
#
# This replaced a single flat GRID_REDRAW_WAIT sleep followed by one look at
# the page-number box. That sleep was a gamble: it won fifteen times and lost
# on the sixteenth, stopping the 2026-08-14 run at "expected page 17, got 16"
# on a queue that genuinely had 17 pages. Waiting for the condition instead of
# a duration costs nothing when the page is quick and does not misreport a
# slow page as a broken one.
PAGE_CHANGE_TIMEOUT = 15000
PAGE_CHECK_INTERVAL = 250

# Spec section 4: two attempts, then skip the row. Without a cap, an image whose
# name genuinely differs from the spreadsheet would loop forever unattended.
MAX_ATTEMPTS = 2

# A queue this long means something is wrong with the paging, not with the
# queue. Roughly 210 rows at 25 a page is 9 pages; 50 is a generous ceiling.
MAX_QUEUE_PAGES = 50


def row_image_name(row):
    """Read the image name out of one queue row.

    Takes the first cell that actually contains text, rather than the first
    cell full stop. The leading column is the tick box, which renders no text
    of its own -- so "first cell" would return an empty string for every row.
    """
    cells = row.locator("td")
    for position in range(cells.count()):
        try:
            text = cells.nth(position).inner_text(timeout=2000).strip()
        except Exception:
            continue  # cell vanished mid-read; ExtJS redraws constantly
        if text:
            return text
    return ""


def read_current_page(page, selectors):
    """Return the image name shown in each row of the queue page on screen."""
    names = []
    rows = page.locator(selectors["queue"]["grid_row"])
    for position in range(rows.count()):
        names.append(row_image_name(rows.nth(position)))
    return names


def next_page_available(page, selectors):
    """Is there another queue page after this one?

    ExtJS greys a paging button out with the class x-item-disabled rather than
    the HTML disabled attribute, so is_enabled() alone reports it as clickable
    and the script would page forever.
    """
    button = page.locator(selectors["queue"]["next_page"]).first
    if button.count() == 0:
        return False
    classes = (button.get_attribute("class") or "")
    if "disabled" in classes:
        return False
    try:
        return button.is_enabled()
    except Exception:
        return False


def current_page_number(page, selectors):
    """Which queue page does the page-number box say we are on? 0 if unreadable."""
    box = page.locator(selectors["queue"]["page_number_box"]).first
    try:
        return int((box.input_value(timeout=3000) or "0").strip())
    except Exception:
        return 0  # box missing or mid-redraw; the caller keeps checking


def wait_for_queue_page(page, selectors, expected):
    """Keep checking until the queue shows page `expected`, or time runs out.

    Returns the page number actually on screen -- equal to `expected` when the
    move worked. The caller compares and stops the run if it does not, so a
    genuine paging failure is still caught; it is simply no longer confused
    with a page that took two seconds instead of one.
    """
    waited = 0
    shown = current_page_number(page, selectors)
    while shown != expected and waited < PAGE_CHANGE_TIMEOUT:
        page.wait_for_timeout(PAGE_CHECK_INTERVAL)
        waited += PAGE_CHECK_INTERVAL
        shown = current_page_number(page, selectors)
    return shown


def read_total_pages(page, selectors, log):
    """Read "Page 1 of 17" off the paging toolbar. Returns 17, or None.

    Anchored on the page-number box -- the one paging element already proved
    against the live screen -- and then walks up to the toolbar containing it,
    rather than relying on a selector for the count itself that was never
    recorded. Nothing here clicks or changes anything; it only reads.

    None means "could not tell"; the caller falls back to the Next button.
    """
    try:
        box = page.locator(selectors["queue"]["page_number_box"]).first
        toolbar = box.locator('xpath=ancestor::*[contains(@class, "x-toolbar")][1]')
        if toolbar.count() == 0:
            log("Could not find the paging toolbar -- falling back to the Next button.")
            return None
        text = toolbar.first.inner_text(timeout=3000)
    except Exception as error:
        log(f"Could not read the paging toolbar ({error}) -- falling back to "
            "the Next button.")
        return None

    total = total_pages_from_toolbar(text)
    if total is None:
        log(f"The paging toolbar reads '{WHITESPACE.sub(' ', text).strip()}' -- no "
            "page count in it. Falling back to the Next button.")
    return total


def read_queue(page, selectors, log):
    """Walk every page of the queue once and build the name -> page lookup.

    Done ONCE per run, up front. Hunting page by page for each invoice would
    mean walking the whole grid once per spreadsheet row.

    It also satisfies the check-everywhere-before-skipping rule: a name is only
    declared missing after every page has been read.
    """
    entries = []
    page_number = 1

    # Ask the queue how long it is. Believing its own count beats inferring the
    # end from how the Next arrow is styled -- see total_pages_from_toolbar.
    total_pages = read_total_pages(page, selectors, log)
    if total_pages is not None:
        log(f"The queue reports {total_pages} page(s).")
        if total_pages > MAX_QUEUE_PAGES:
            raise RuntimeError(
                f"The queue reports {total_pages} pages, more than the "
                f"{MAX_QUEUE_PAGES}-page ceiling this script will read. That is "
                "either a genuinely huge backlog or a misread toolbar; either "
                "way somebody should look before it walks the lot. Nothing was "
                "typed."
            )

    while True:
        names = read_current_page(page, selectors)
        for name in names:
            entries.append((name, page_number))
        log(f"Queue page {page_number}: {len(names)} rows read")

        # Sanity line for the operator. If these do not look like image names,
        # the grid's column order differs from what was recorded and the run
        # should be stopped -- everything after this depends on reading the
        # right column.
        if page_number == 1:
            sample = [n for n in names if n][:3]
            log(f"First names seen: {sample}  <-- do these look like image names?")

        if total_pages is not None:
            if page_number >= total_pages:
                break
        elif not next_page_available(page, selectors):
            break

        if page_number >= MAX_QUEUE_PAGES:
            raise RuntimeError(
                f"Stopped after {MAX_QUEUE_PAGES} queue pages -- the Next button "
                "never greyed out. Nothing was typed."
            )

        page.locator(selectors["queue"]["next_page"]).first.click()

        # Confirm the page actually changed before reading it. Without this the
        # script can read page 1 twice and declare a genuinely present invoice
        # missing.
        expected = page_number + 1
        shown = wait_for_queue_page(page, selectors, expected)
        if shown != expected:
            log(f"STOPPED: asked for queue page {expected}, the page box still "
                f"says {shown} after {PAGE_CHANGE_TIMEOUT // 1000} seconds.")
            raise RuntimeError(
                f"Queue paging went wrong -- asked for page {expected}, still on "
                f"{shown} after {PAGE_CHANGE_TIMEOUT // 1000} seconds. Nothing "
                "was typed."
            )
        page_number = expected

    index, duplicates = build_queue_index(entries)
    log(f"Queue read: {len(index)} invoices across {page_number} page(s).")
    return index, duplicates


def go_to_queue_page(page, selectors, page_number):
    """Jump straight to a queue page using the page-number box."""
    box = page.locator(selectors["queue"]["page_number_box"]).first
    box.fill(str(page_number))
    box.press("Enter")
    page.wait_for_timeout(GRID_REDRAW_WAIT)


def tick_row_and_open(page, selectors, wanted_name, page_number, log):
    """Go to the right queue page, tick the matching row, press Index Selected.

    Returns True only if a row matching wanted_name was found and clicked.
    """
    go_to_queue_page(page, selectors, page_number)

    target = normalise_name(wanted_name)
    rows = page.locator(selectors["queue"]["grid_row"])

    for position in range(rows.count()):
        row = rows.nth(position)
        if normalise_name(row_image_name(row)) != target:
            continue

        tick = row.locator(selectors["queue"]["row_tick_box"]).first
        if tick.count() == 0:
            log(f"The row for '{wanted_name}' has no tick box -- leaving it alone.")
            return False
        tick.click()
        page.wait_for_timeout(400)

        # Targeted by Bottomline's own class. The delete icon is on this same
        # toolbar and acts on whatever is ticked -- never select this button by
        # position.
        page.locator(selectors["queue"]["index_selected"]).first.click()
        page.wait_for_timeout(GRID_REDRAW_WAIT)
        return True

    log(f"'{wanted_name}' was not on queue page {page_number}.")
    return False


def confirm_right_invoice(page, selectors, wanted_name, log):
    """The safety net. Both checks must pass or nothing gets typed.

    Check 1 -- the page header proves WHICH SCREEN is open.
    Check 2 -- the Image Name box proves WHICH INVOICE is open.

    Why two: the header catches "Index Selected did not open anything", the box
    catches "it opened the wrong invoice". Neither one catches both.
    """
    try:
        header_text = page.locator(selectors["page_header"]).first.inner_text(timeout=5000)
    except Exception:
        log("Safety check FAILED: the page heading could not be read.")
        return False

    from_header = image_name_from_header(header_text)
    if from_header is None:
        log(f"Safety check FAILED: the heading reads '{header_text}', not "
            "'Image Index - ...'. The indexing screen did not open.")
        return False

    try:
        on_screen = page.locator(
            selectors["verify"]["image_name"]).first.input_value(timeout=5000)
    except Exception:
        log("Safety check FAILED: the Image Name box could not be read.")
        return False

    wanted = normalise_name(wanted_name)
    if normalise_name(from_header) != wanted:
        log(f"Safety check FAILED: the heading says '{from_header}', the "
            f"spreadsheet says '{wanted_name}'.")
        return False
    if normalise_name(on_screen) != wanted:
        log(f"Safety check FAILED: the Image Name box says '{on_screen}', the "
            f"spreadsheet says '{wanted_name}'.")
        return False

    log(f"Safety check passed: '{wanted_name}' is open.")
    return True


def _queue_screen_signals(grid_present, page_number_box_present):
    """Pure decision: do these two landmarks add up to 'this is the queue screen'?

    Split out from queue_screen_visible() below so it can be tested without a
    browser -- see selftest_queue.py.

    Either landmark on its own is enough. The grid can be genuinely empty on
    a cleared queue while the page-number box still sits on the toolbar, and
    for a moment during a redraw the reverse can be true. Both being absent
    at once is the only case this calls "not there".
    """
    return bool(grid_present or page_number_box_present)


def queue_screen_visible(page, selectors):
    """Is the screen in front of us actually the indexing queue right now?

    Looks for the same two landmarks read_queue() already depends on: the
    grid of rows, and the page-number box on the paging toolbar. A stray
    exception reading either one is treated as "not found" rather than
    raised -- a screen mid-redraw should read as "not there yet", not blow up
    the check that is supposed to be the safety net.
    """
    try:
        grid_present = page.locator(selectors["queue"]["grid_row"]).first.count() > 0
    except Exception:
        grid_present = False
    try:
        box_present = page.locator(selectors["queue"]["page_number_box"]).first.count() > 0
    except Exception:
        box_present = False
    return _queue_screen_signals(grid_present, box_present)


def wait_for_queue_screen(page, selectors):
    """Keep checking until the queue's landmarks appear, or time runs out.

    Same polling shape as wait_for_queue_page() above, for the same reason: a
    click that will succeed eventually should not be judged a failure just
    because the page hadn't redrawn yet on the first look.
    """
    waited = 0
    if queue_screen_visible(page, selectors):
        return True
    while waited < PAGE_CHANGE_TIMEOUT:
        page.wait_for_timeout(PAGE_CHECK_INTERVAL)
        waited += PAGE_CHECK_INTERVAL
        if queue_screen_visible(page, selectors):
            return True
    return False


def wait_for_queue_rows(page, selectors, log, timeout_ms=PAGE_CHANGE_TIMEOUT):
    """Wait until the queue grid actually holds at least one invoice row.

    wait_for_queue_screen() only proves the queue's FRAME is up -- the paging
    toolbar and page-number box render before the grid's rows finish loading
    over the network. Reading the grid in that gap returns 0 rows, and every
    invoice is then wrongly declared 'not in the queue'. Observed 2026-08-18
    19:11: auto-navigation reached the queue, read it immediately, got 0 rows,
    and skipped all 18 invoices.

    Returns True the moment a row appears. Returns False if none appear within
    the timeout -- which is either a genuinely empty queue or a screen that is
    not really the queue. The caller decides what to do with that (fall back to
    asking the operator, and warn if the queue really did read as empty).
    """
    waited = 0
    while waited < timeout_ms:
        try:
            if page.locator(selectors["queue"]["grid_row"]).count() > 0:
                return True
        except Exception:
            pass  # grid mid-redraw; keep waiting
        page.wait_for_timeout(PAGE_CHECK_INTERVAL)
        waited += PAGE_CHECK_INTERVAL
    log("The queue frame opened but no invoice rows loaded within "
        f"{timeout_ms // 1000} seconds.")
    return False


def return_routes(has_queue_url):
    """The order routes back to the queue are tried in, as plain labels.

    Kept as a pure function, separate from anything that touches a browser,
    so the ordering itself can be proved right without opening one -- see
    selftest_queue.py.

    "queue_url" only appears in the ladder when a queue address was actually
    captured this run (invoice_recorder.py does that once, right after the
    queue is first read). Without one, the two menu-click attempts still run;
    the ladder just has one fewer rung.
    """
    routes = ["menu"]
    if has_queue_url:
        routes.append("queue_url")
    routes.append("menu")
    return routes


_ROUTE_LABELS = {
    "menu": "the 'Images to be Indexed' menu item",
    "queue_url": "the remembered queue address",
}


def _reveal_menu(page, selectors, log):
    """Open the toolbar menu that holds 'Images to be Indexed', if one is set.

    Bottomline keeps the menu items INSIDE a top-level button ('Image
    Management'); the item is not in the page until that button is opened. A
    bare click on the item therefore finds nothing -- the 2026-08-18 failure,
    'Could not find the Images to be Indexed menu item', seen right after login.

    Gentlest trigger first: HOVER (opens a hover-menu, harmless to a click-menu)
    and only CLICK the opener if hovering did not reveal the item -- clicking a
    hover-menu's own button can toggle it shut, so the click is a fallback, not
    the first move.

    Controlled by the optional 'menu_opener' / 'menu_opener_text' selectors.
    With neither set it returns False at once and changes nothing, so a field
    map without them behaves exactly as before. Returns True once the menu item
    is visible.
    """
    opener_selector = selectors["queue"].get("menu_opener")
    if not opener_selector:
        return False

    opener_text = selectors["queue"].get("menu_opener_text", "")
    where = (f'{opener_selector}:has-text("{opener_text}")'
             if opener_text else opener_selector)
    label = opener_text or opener_selector

    item_selector = (f'{selectors["queue"]["menu_item"]}:has-text('
                     f'"{selectors["queue"]["menu_item_text"]}")')

    def item_showing():
        try:
            return page.locator(item_selector).first.is_visible()
        except Exception:
            return False  # mid-redraw or not there yet -- treat as not showing

    for how in ("hover", "click"):
        try:
            opener = page.locator(where).first
            if opener.count() == 0:
                log(f"Could not find the '{label}' menu button.")
                return False
            if how == "hover":
                opener.hover()
            else:
                opener.click()
        except Exception as error:
            log(f"Could not {how} the '{label}' menu button ({error}).")
            continue

        # Give the menu a moment to animate open, checking for the item as we go.
        waited = 0
        while waited < 2000:
            if item_showing():
                return True
            page.wait_for_timeout(200)
            waited += 200

    return False


def _try_menu_click(page, selectors, log):
    """One click of the menu item. Returns True only if a click really happened.

    The click itself is wrapped, not just the search for the item. Finding the
    menu item is no guarantee it can be clicked: after Convert to Invoice it
    can be on the page but covered by another panel, still animating, or
    detached the instant it is reached -- and Playwright raises, it does not
    return False, in all three cases.

    An exception escaping this function used to fly straight out of the whole
    ladder, past the operator prompt, and end the run: the exact failure this
    ladder exists to prevent, arriving through a different door. Observed live
    on 2026-08-14 with row 1 already filled and two invoices still to do.
    """
    try:
        # The menu items sit inside a top-level toolbar button ('Image
        # Management') and are not in the page until it is opened. Reveal it
        # first when an opener is configured; with none configured this is a
        # no-op and the old direct-click behaviour stands unchanged.
        _reveal_menu(page, selectors, log)

        item = page.locator(
            f'{selectors["queue"]["menu_item"]}:has-text('
            f'"{selectors["queue"]["menu_item_text"]}")'
        ).first
        if item.count() == 0:
            log("Could not find the 'Images to be Indexed' menu item.")
            return False
        item.click()
        return True
    except Exception as error:
        log(f"The 'Images to be Indexed' menu item could not be clicked ({error}).")
        return False


def _try_goto_queue_url(page, queue_url, log):
    """Go straight to the queue's own address. Returns True only if it was tried."""
    if not queue_url:
        return False
    try:
        page.goto(queue_url)
        return True
    except Exception as error:
        log(f"Could not navigate straight to the remembered queue address ({error}).")
        return False


def return_to_queue(page, selectors, log, queue_url=None):
    """Get back to Images to be Indexed, trying more than one way if needed.

    This used to be a single click of the menu item, with the browser Back
    button ruled out because it would replay a form submission. That one
    route was enough as long as the menu item stayed reachable -- but
    Convert to Invoice's second screen does not reliably expose it, and a
    route that only sometimes works used to end the whole run right there.

    Now it is a short ladder, tried in this order (see return_routes()):
      1. click the menu item -- the original, still-preferred way back.
      2. go straight to the queue's own remembered address, if one was
         captured earlier this run. That address is a known-good spot; no
         new selector is needed to use it.
      3. one more click of the menu item, in case the first attempt was
         simply too early for the screen to be ready.

    Each attempt is followed by actually looking for the queue on screen
    (wait_for_queue_screen) rather than assuming a click that "worked"
    landed anywhere useful -- a click can succeed and still land nowhere
    near the queue. The first rung whose landing checks out wins.
    """
    for route in return_routes(has_queue_url=bool(queue_url)):
        label = _ROUTE_LABELS[route]

        # No rung may ever raise out of this ladder. Each one is wrapped here
        # as well as internally, so that a route failing in a way nobody
        # anticipated costs us that route and nothing more. Ending a run with
        # invoices still to do is always the worse outcome than trying the
        # next way round -- and if every route fails, the caller hands the
        # browser to the operator rather than stopping.
        try:
            if route == "menu":
                attempted = _try_menu_click(page, selectors, log)
            else:
                attempted = _try_goto_queue_url(page, queue_url, log)

            if not attempted:
                continue

            arrived = wait_for_queue_screen(page, selectors)
        except Exception as error:
            log(f"Trying {label} raised an error ({error}) -- moving on to the "
                "next route back.")
            continue

        if arrived:
            log(f"Back at the queue (via {label}).")
            return True

        log(f"Tried {label}, but the queue screen never showed up.")

    log("Could not get back to Images to be Indexed by any route tried.")
    return False


def open_invoice(page, selectors, wanted_name, page_number, log, queue_url=None):
    """Open one invoice and prove it is the right one. Retries once.

    Returns True when the invoice is open and verified -- the ONLY condition
    under which the caller may type anything.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        log(f"Opening '{wanted_name}' (attempt {attempt} of {MAX_ATTEMPTS})")

        if tick_row_and_open(page, selectors, wanted_name, page_number, log):
            if confirm_right_invoice(page, selectors, wanted_name, log):
                return True

        if attempt < MAX_ATTEMPTS:
            log("Going back to the queue to try once more.")
            return_to_queue(page, selectors, log, queue_url)

    log(f"SKIPPED '{wanted_name}': could not open and verify it after "
        f"{MAX_ATTEMPTS} attempts. Nothing was typed.")
    return_to_queue(page, selectors, log, queue_url)
    return False
