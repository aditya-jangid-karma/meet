"""
page_probe.py -- LOOK ONLY. Lists every box on whatever Bottomline screen you
have open, so we can learn each box's real internal name.

WHAT IT DOES
    Opens Bottomline, logs you in, and then waits. You navigate to the screen
    you want examined and press ENTER. It reads the page and prints every
    input / dropdown / text area it can find, with the internal `name` the
    filling script would use to target it.

WHAT IT NEVER DOES
    It never types into a box, never clicks a button, never presses Save,
    Convert to Invoice, Save as Exception or Delete, and never changes
    anything on any screen. The only typing it does at all is your username
    and password on the login page -- exactly the same login step
    invoice_recorder.py already performs.

WHY IT EXISTS
    Some boxes on the indexing screen are read-only, so the selector recorder
    never sees them -- a recorder only captures what a human clicks or types
    into. The Image Name box is one of those, and it is the box the whole
    safety check depends on. This script reads the page directly instead of
    waiting for someone to click something.

ABOUT VALUES
    It does NOT print the contents of the boxes. It prints how many characters
    a box holds and its first 8 characters only. That is enough to recognise
    an image name (a long GUID) without copying client vendor names or amounts
    into a log file. Password boxes are skipped entirely and never read.

USAGE
    python page_probe.py

    You will be asked to press ENTER each time you want the current screen
    read. Type q and press ENTER to finish.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

# Playwright's copy of Chrome lives inside the project, not in your Windows
# user folder. Must be set before playwright is imported.
BROWSERS_DIR = PROJECT / ".browsers"
if BROWSERS_DIR.exists():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS_DIR))

SESSION_FILE = HERE / ".bottomline_session.json"
LOG_DIR = PROJECT / "logs"

# Attributes worth reading off each box. Deliberately does not include
# "value" -- that is handled separately and masked, see value_preview().
ATTRIBUTES = ("name", "id", "type", "class", "readonly", "disabled",
              "aria-label", "data-qtip", "placeholder")

# ExtJS builds ids like "textfield-1735-inputEl" when the page loads, so a
# long run of digits is the giveaway that an id was generated and will change
# next time. Same rule the selector recorder uses.
GENERATED_ID = re.compile(r"\d{3,}")


def value_preview(value):
    """Describe a box's contents without reproducing them.

    Returns something like: 36 chars, starts "37a9b5cf"
    Enough to recognise an image name; not enough to leak a vendor or amount.
    """
    if not value:
        return "(empty)"
    text = value.strip()
    if not text:
        return "(blank spaces)"
    return f'{len(text)} chars, starts "{text[:8]}"'


def label_for(element):
    """Find the caption ExtJS draws beside a box, e.g. "Vendor Name:".

    ExtJS wraps each box and its caption in a container carrying the class
    x-form-item. We walk up to that container and read its label. Captions are
    screen furniture, not client data, so they are safe to record in full.
    """
    try:
        holder = element.locator(
            "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '),"
            " ' x-form-item ')][1]//label"
        ).first
        if holder.count() > 0:
            return " ".join(holder.inner_text(timeout=1000).split())
    except Exception:
        pass
    return ""


def is_password_box(attrs):
    """Same guard the recorder uses. Never read, never printed, never logged."""
    if (attrs.get("type") or "").lower() == "password":
        return True
    haystack = " ".join(
        (attrs.get(key) or "") for key in ("id", "name", "aria-label", "placeholder")
    ).lower()
    return any(word in haystack for word in
               ("password", "passwd", "pwd", "secret", "otp", "mfa"))


def describe_frame(frame, frame_label, out):
    """Read every box in one frame and write a description of each."""
    found = 0
    skipped_passwords = 0

    try:
        boxes = frame.locator("input, select, textarea")
        total = boxes.count()
    except Exception as error:
        out(f"  (could not read this frame: {error})")
        return 0, 0

    for position in range(total):
        box = boxes.nth(position)
        try:
            attrs = {key: box.get_attribute(key) for key in ATTRIBUTES}
        except Exception:
            continue  # element vanished mid-scan; ExtJS redraws constantly

        if is_password_box(attrs):
            skipped_passwords += 1
            continue

        # Hidden plumbing fields ExtJS creates for itself. Listing them buries
        # the real boxes in noise.
        if (attrs.get("type") or "").lower() == "hidden":
            continue

        found += 1
        name = attrs.get("name") or ""
        element_id = attrs.get("id") or ""
        caption = label_for(box)

        try:
            value = box.input_value(timeout=1000)
        except Exception:
            value = box.get_attribute("value") or ""

        read_only = attrs.get("readonly") is not None
        disabled = attrs.get("disabled") is not None
        state = []
        if read_only:
            state.append("READ-ONLY")
        if disabled:
            state.append("disabled")

        out("")
        out(f"[{found}] name = {name if name else '*** NO NAME -- cannot be targeted this way ***'}")
        if caption:
            out(f"     label   : {caption}")
        out(f"     tag     : {box.evaluate('el => el.tagName.toLowerCase()')}"
            f"   type: {attrs.get('type') or '-'}")
        if element_id:
            flag = "  (generated - do NOT use)" if GENERATED_ID.search(element_id) else ""
            out(f"     id      : {element_id}{flag}")
        if attrs.get("data-qtip"):
            out(f"     tooltip : {attrs['data-qtip']}")
        if state:
            out(f"     state   : {', '.join(state)}")
        out(f"     value   : {value_preview(value)}")
        out(f"     frame   : {frame_label}")

    return found, skipped_passwords


def main():
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

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"page_fields_{datetime.now():%Y-%m-%d_%H%M}.txt"
    log_file = log_path.open("w", encoding="utf-8")

    def out(text=""):
        print(text)
        log_file.write(text + "\n")
        log_file.flush()

    out("PAGE PROBE -- look only. Nothing is typed, clicked or saved.")
    out(f"Started {datetime.now():%Y-%m-%d %H:%M}")

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
                print(f"Could not complete the login automatically: {error}")
                print("Log in by hand in the browser window, then carry on below.")

        print("\nIf a security code was requested, complete it now in the browser.")

        scan_number = 0
        while True:
            print("\n" + "=" * 70)
            answer = input(
                "Navigate to the screen you want read, then press ENTER.\n"
                "(or type q then ENTER to finish): "
            ).strip().lower()
            if answer == "q":
                break

            scan_number += 1
            out("")
            out("=" * 70)
            out(f"SCAN {scan_number}   {datetime.now():%H:%M:%S}")
            out("=" * 70)

            total_found = 0
            total_passwords = 0
            for index, frame in enumerate(page.frames):
                frame_label = "main page" if index == 0 else f"frame {index}"
                found, passwords = describe_frame(frame, frame_label, out)
                total_found += found
                total_passwords += passwords

            out("")
            out("-" * 70)
            out(f"SCAN {scan_number} SUMMARY: {total_found} boxes listed.")
            if total_passwords:
                out(f"{total_passwords} password box(es) found and deliberately"
                    " skipped -- never read.")
            out("-" * 70)

        try:
            context.storage_state(path=str(SESSION_FILE))
        except Exception:
            pass  # not fatal -- next run just logs in again

        browser.close()

    log_file.close()
    print(f"\nSaved to: {log_path}")
    print("Nothing was typed, clicked or changed in Bottomline.")


if __name__ == "__main__":
    main()
