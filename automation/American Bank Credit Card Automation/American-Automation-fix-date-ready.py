import glob
import json
import os
import re
import shutil
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright, Page

# ==============================================================================
# CONFIGURATION & CREDENTIALS
# ==============================================================================
LOGIN_URL = "https://www.americanexpress.com/en-us/account/login?inav=iNavLnkLog"
STATEMENTS_URL = "https://global.americanexpress.com/activity/days-30"

AMEX_USER_ID = os.environ.get("AMEX_USER_ID", "Amexsiddhi1531")
AMEX_PASSWORD = os.environ.get("AMEX_PASSWORD", "Team%karmacpa1234")

CARD_MEMBERS = ["Prinesh", "Rashmi", "Pranav", "Priti"]

USER_DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
TARGET_DOWNLOAD_DIR = os.path.join(USER_DOWNLOADS_DIR, "Amex_Statements")
os.makedirs(TARGET_DOWNLOAD_DIR, exist_ok=True)

_HOME = os.path.expanduser("~")
REAL_USER_DATA_DIR = os.path.join(_HOME, "AppData", "Local", "Google", "Chrome", "User Data")
REAL_PROFILE_DIR = "Default"
AUTOMATION_USER_DATA_DIR = os.path.join(_HOME, "ChromeAutomationProfile")
AUTOMATION_PROFILE_DIR = "Default"

SYNC_REAL_PROFILE = os.environ.get("SYNC_REAL_PROFILE", "0") == "1"


# ==============================================================================
# CHROME PROFILE & PROCESS MANAGEMENT
# ==============================================================================

def sync_profile_copy():
    print("[SYSTEM] Syncing browser profile from local Chrome without closing existing windows...")
    src = os.path.join(REAL_USER_DATA_DIR, REAL_PROFILE_DIR)
    dst = os.path.join(AUTOMATION_USER_DATA_DIR, AUTOMATION_PROFILE_DIR)
    os.makedirs(AUTOMATION_USER_DATA_DIR, exist_ok=True)

    local_state_src = os.path.join(REAL_USER_DATA_DIR, "Local State")
    local_state_dst = os.path.join(AUTOMATION_USER_DATA_DIR, "Local State")
    if os.path.exists(local_state_src):
        try:
            shutil.copy2(local_state_src, local_state_dst)
        except Exception:
            pass

    SKIP_NAMES = {
        "Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache",
        "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache", "Media Cache",
        "Service Worker", "Crashpad", "Component Cache", "extensions_crx_cache",
        "optimization_guide_model_store", "lockfile",
    }

    def ignore_locks(directory, contents):
        return [c for c in contents if c.startswith("Singleton") or c in SKIP_NAMES]

    if os.path.exists(dst):
        for _ in range(5):
            try:
                shutil.rmtree(dst, ignore_errors=True)
                break
            except Exception:
                time.sleep(1)

    try:
        shutil.copytree(src, dst, ignore=ignore_locks, dirs_exist_ok=True)
        print("[SYSTEM] Chrome profile sync complete (caches skipped).")
    except Exception as e:
        print(f"[SYSTEM WARNING] Partial profile copy warning (non-fatal): {e}")


def seed_chrome_prefs():
    """
    Pre-seed the automation profile so that, combined with the --kiosk-printing
    launch flag, window.print() silently saves a PDF (destination 'Save as PDF')
    into the Downloads folder without showing any dialog.
    """
    prof_dir = os.path.join(AUTOMATION_USER_DATA_DIR, AUTOMATION_PROFILE_DIR)
    os.makedirs(prof_dir, exist_ok=True)
    prefs_path = os.path.join(prof_dir, "Preferences")

    prefs = {}
    if os.path.exists(prefs_path):
        try:
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
        except Exception:
            prefs = {}

    prefs.setdefault("download", {})
    prefs["download"]["default_directory"] = USER_DOWNLOADS_DIR
    prefs["download"]["prompt_for_download"] = False

    prefs.setdefault("savefile", {})
    prefs["savefile"]["default_directory"] = USER_DOWNLOADS_DIR

    app_state = {
        "recentDestinations": [{"id": "Save as PDF", "origin": "local", "account": ""}],
        "selectedDestinationId": "Save as PDF",
        "version": 2,
    }
    prefs.setdefault("printing", {})
    prefs["printing"].setdefault("print_preview_sticky_settings", {})
    prefs["printing"]["print_preview_sticky_settings"]["appState"] = json.dumps(app_state)

    try:
        with open(prefs_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
        print("[SYSTEM] Chrome print prefs seeded (Save as PDF).")
    except Exception as e:
        print(f"[SYSTEM WARNING] Could not seed Chrome prefs: {e}")


# ==============================================================================
# DATE CALCULATION LOGIC
# ==============================================================================

def calculate_weekly_date_range(reference_date: datetime = None) -> dict:
    if reference_date is None:
        reference_date = datetime.now()

    # Find the most recently completed week (Saturday to Friday)
    # weekday(): Monday is 0, Tuesday is 1, ..., Friday is 4, Sunday is 6
    days_since_friday = (reference_date.weekday() - 4) % 7
    
    end_date = reference_date - timedelta(days=days_since_friday)
    start_date = end_date - timedelta(days=6)

    return {
        "ui_start": start_date.strftime("%m/%d/%Y"),
        "ui_end": end_date.strftime("%m/%d/%Y"),
        "ui_combined": f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}",
        "iso_start": start_date.strftime("%Y-%m-%d"),   # for URL param (startDate)
        "iso_end": end_date.strftime("%Y-%m-%d"),       # for URL param (endDate)
        "file_start": start_date.strftime("%m-%d-%Y"),  # for filename (MM-DD-YYYY)
        "file_end": end_date.strftime("%m-%d-%Y"),
    }


# ==============================================================================
# HELPER ACTIONS
# ==============================================================================

def dismiss_popups(page: Page) -> None:
    selectors = [
        "button#accept-all-cookies",
        "button:has-text('Accept All')",
        "button[aria-label='Close']",
        "button[title='Close']",
        "button:has-text('No Thanks')",
        "button:has-text('Dismiss')",
        "div:has(iframe[src*='recaptcha' i]) button[aria-label*='Close' i]",
        "div:has(iframe[src*='recaptcha' i]) button",
        "[class*='close' i]:has-text('✕')",
        "[class*='close' i]:has-text('×')",
    ]
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=300):
                btn.click(force=True)
                page.wait_for_timeout(200)
        except Exception:
            pass


def login_to_amex(page: Page) -> None:
    print("[AUTH] Navigating to standard login portal...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    dismiss_popups(page)

    if "account/login" not in page.url.lower():
        print("[AUTH SUCCESS] Active session already authenticated!")
    else:
        print("[AUTH] Entering credentials...")
        user_input = page.locator("input#elButton_username, input#userId, input[name='userId'], input[name*='user' i]").first
        pass_input = page.locator("input#elButton_password, input#password, input[name='password'], input[name*='pass' i]").first

        user_input.wait_for(state="visible", timeout=15000)
        user_input.fill("")
        user_input.press_sequentially(AMEX_USER_ID, delay=50)
        page.wait_for_timeout(300)

        pass_input.fill("")
        pass_input.press_sequentially(AMEX_PASSWORD, delay=50)
        page.wait_for_timeout(300)

        print("[AUTH] Submitting login...")
        login_btn = page.locator("button#elButton_submit, button#login-submit, button[type='submit'], button:has-text('Log In')").first
        if login_btn.count() > 0 and login_btn.is_visible():
            login_btn.click()
        else:
            pass_input.press("Enter")

        print("[AUTH] Waiting for authentication to complete...")
        print("[AUTH] Note: If CAPTCHA or verification appears, solve it in the browser window...")

        for _ in range(120):
            if "account/login" not in page.url.lower():
                print("[AUTH SUCCESS] Successfully authenticated!")
                break
            try:
                error_banner = page.locator("text=temporarily unavailable, text=We're sorry").first
                if error_banner.count() > 0 and error_banner.is_visible():
                    print("[AUTH NOTICE] Temporary session error detected. Retrying submit...")
                    page.wait_for_timeout(2000)
                    if login_btn.count() > 0 and login_btn.is_visible():
                        login_btn.click()
            except Exception:
                pass
            page.wait_for_timeout(1500)
        else:
            print("[AUTH WARNING] Still on login page after wait; continuing anyway.")

    page.wait_for_timeout(3000)

    print(f"[ROUTING] Navigating to Statements & Activity page ({STATEMENTS_URL})...")
    page.goto(STATEMENTS_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    dismiss_popups(page)
    print("[ROUTING SUCCESS] Successfully reached Statements & Activity.")


# ==============================================================================
# STEP 1: CUSTOM DATE RANGE (with verification)
# ==============================================================================

def _fill_and_verify_date(inp, value: str) -> bool:
    digits = value.replace("/", "")
    try:
        inp.click()
        inp.fill("")
        inp.fill(value)
        cur = inp.input_value()
        if digits in cur.replace("/", ""):
            return True
        inp.click()
        for _ in range(12):
            inp.press("Backspace")
        inp.press_sequentially(value, delay=60)
        inp.press("Tab")
        cur = inp.input_value()
        return digits in cur.replace("/", "")
    except Exception as e:
        print(f"     [DATE WARNING] {e}")
        return False


def _apply_date_via_ui(page: Page, date_range_info: dict) -> None:
    """Fallback: drive the 'Date Period' dropdown -> Custom Date Range -> input."""
    print("     [DATE] Falling back to UI date picker...")
    date_dropdown = page.locator(
        "button:has-text('Last 30 Days'), button:has-text('Date Period'), "
        "button:has-text('Days'), button[aria-label*='Date' i]"
    ).first
    date_dropdown.click(force=True)
    page.wait_for_timeout(1000)

    custom_btn = page.locator(
        "button:has-text('Custom Date Range'), [role='button']:has-text('Custom Date Range')"
    ).first
    if custom_btn.count() > 0 and custom_btn.is_visible():
        custom_btn.click(force=True)
        page.wait_for_timeout(1000)

    # Amex uses a SINGLE range input "MM/DD/YYYY - MM/DD/YYYY".
    inputs = page.locator(
        "input[placeholder*='MM/DD/YYYY' i], input[aria-label*='Date' i], input[type='text']"
    ).all()
    visible_inputs = [inp for inp in inputs if inp.is_visible()]
    if visible_inputs:
        _fill_and_verify_date(visible_inputs[0], date_range_info["ui_combined"])

    done_btn = page.locator("button:has-text('Done'), button:has-text('Apply')").first
    if done_btn.count() > 0 and done_btn.is_visible():
        done_btn.click(force=True)
    page.wait_for_timeout(2000)


def apply_custom_date_range(page: Page, date_range_info: dict) -> None:
    """
    Set the date range by navigating directly to the activity URL with
    startDate/endDate params (confirmed reliable). Falls back to the UI
    date picker if the header doesn't reflect the range.
    """
    sd = date_range_info["iso_start"]
    ed = date_range_info["iso_end"]
    url = f"https://global.americanexpress.com/activity?startDate={sd}&endDate={ed}"
    print(f"  -> [DATE RANGE] Applying range via URL: {sd} to {ed}")

    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    dismiss_popups(page)

    # Verify the header shows the range (e.g. "Aug 22 - Aug 28, 2026").
    verified = False
    try:
        if f"startDate={sd}" in page.url and f"endDate={ed}" in page.url:
            verified = True
    except Exception:
        pass

    if verified:
        print("     [DATE] Date range confirmed in URL.")
    else:
        print("     [DATE WARNING] URL did not reflect the range; trying UI picker.")
        try:
            _apply_date_via_ui(page, date_range_info)
        except Exception as e:
            print(f"     [DATE WARNING] UI fallback failed: {str(e).splitlines()[0]}")

    page.wait_for_timeout(1500)


# ==============================================================================
# STEP 2: CARD MEMBER FILTER
# ==============================================================================

def apply_card_member_filter(page: Page, member_name: str) -> None:
    print(f"  -> [FILTER] Setting filter for card member: '{member_name}'")

    # Open the Filters dialog
    filter_btn = page.get_by_role("button", name=re.compile(r"^\s*Filter", re.IGNORECASE)).first
    if filter_btn.count() == 0 or not filter_btn.is_visible():
        filter_btn = page.locator("button:has-text('Filter'), button[aria-label*='Filter' i]").first
    filter_btn.click(force=True)
    page.wait_for_timeout(1800)

    # Card Member options are radio buttons with accessible names like
    # "Prinesh R Patel ••••17038". Select by first-name match.
    member_pattern = re.compile(re.escape(member_name), re.IGNORECASE)
    selected = False

    try:
        radio = page.get_by_role("radio", name=member_pattern).first
        if radio.count() > 0:
            radio.scroll_into_view_if_needed()
            radio.check(force=True)
            selected = True
            print(f"     [FILTER] Selected radio for '{member_name}'.")
    except Exception:
        pass

    if not selected:
        # Fallback: click the label/text containing the member name
        try:
            lbl = page.locator("label, [role='radio'], div").filter(has_text=member_pattern).first
            if lbl.count() > 0 and lbl.is_visible():
                lbl.scroll_into_view_if_needed()
                lbl.click(force=True)
                selected = True
                print(f"     [FILTER] Clicked label for '{member_name}'.")
        except Exception:
            pass

    if not selected:
        print(f"     [FILTER WARNING] Could not select card member '{member_name}'.")

    page.wait_for_timeout(800)

    # Click "Apply Changes"
    apply_btn = page.get_by_role("button", name=re.compile(r"Apply Changes", re.IGNORECASE)).first
    if apply_btn.count() == 0 or not apply_btn.is_visible():
        apply_btn = page.locator("button:has-text('Apply Changes'), button:has-text('Apply')").first
    try:
        apply_btn.scroll_into_view_if_needed()
        apply_btn.click(force=True)
    except Exception as e:
        print(f"     [FILTER WARNING] Apply Changes click failed: {str(e).splitlines()[0]}")

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)


# ==============================================================================
# STEP 3: TRANSACTION SELECTION & PENDING EXCLUSION
# ==============================================================================

def select_transactions_excluding_pending(page: Page) -> None:
    print("  -> [SELECTION] Loading all transactions (scrolling)...")

    # Scroll to the bottom to make sure every transaction row is rendered,
    # then back up to the top.
    for _ in range(8):
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(300)
    page.mouse.wheel(0, -20000)
    page.wait_for_timeout(600)

    # 1. Click "Select All on Page" (becomes "Unselect All on Page (N Selected)").
    try:
        select_all = page.get_by_text(re.compile(r"^\s*Select All on Page", re.IGNORECASE)).first
        if select_all.count() > 0 and select_all.is_visible():
            select_all.click(force=True)
            print("     [SELECTION] Clicked 'Select All on Page'.")
        else:
            cb = page.locator("input[type='checkbox'][aria-label*='Select All' i], input#select-all").first
            if cb.count() > 0 and not cb.is_checked():
                cb.check(force=True)
                print("     [SELECTION] Checked select-all checkbox.")
    except Exception as e:
        print(f"     [SELECTION WARNING] Select-all failed: {str(e).splitlines()[0]}")

    page.wait_for_timeout(1500)

    try:
        status = page.get_by_text(re.compile(r"Unselect All on Page", re.IGNORECASE)).first
        if status.count() > 0:
            print(f"     [SELECTION] {status.inner_text().strip()}")
    except Exception:
        pass

    # 2. Uncheck PENDING rows by finding the 'Pending' status and clicking its row's checkbox
    print("  -> [SELECTION] Identifying & unchecking 'Pending' rows...")
    found = 0
    pending_deselected = 0
    try:
        # Find all cells with exactly the text 'Pending' (ignoring case/whitespace)
        pending_cells = page.get_by_text(re.compile(r"^\s*pending\s*$", re.IGNORECASE)).all()
        
        for cell in pending_cells:
            try:
                # Find the nearest ancestor that contains a checkbox (i.e. the transaction row)
                cb = cell.locator("xpath=ancestor::*[.//input[@type='checkbox'] or .//*[@role='checkbox']][1]//input[@type='checkbox']").first
                if cb.count() == 0:
                    cb = cell.locator("xpath=ancestor::*[.//input[@type='checkbox'] or .//*[@role='checkbox']][1]//*[@role='checkbox']").first
                
                if cb.count() == 0:
                    continue
                
                # Verify it's actually checked
                is_chk = False
                try:
                    is_chk = cb.is_checked()
                except Exception:
                    pass
                if not is_chk and cb.get_attribute("aria-checked") == "true":
                    is_chk = True
                
                if is_chk:
                    found += 1
                    cb.scroll_into_view_if_needed()
                    
                    # CRITICAL FIX: Playwright's uncheck() or center-clicking the label 
                    # clicks the center of the row, expanding the transaction details instead of toggling the box.
                    # We fix this by clicking the exact top-left corner (where the checkbox is visually located) 
                    # of the immediate parent container.
                    parent = cb.locator("xpath=..").first
                    if parent.count() > 0:
                        # Click near the top-left of the parent element (the checkbox column)
                        parent.click(force=True, position={"x": 10, "y": 10})
                    else:
                        cb.click(force=True, position={"x": 5, "y": 5})
                    
                    page.wait_for_timeout(200)
                    pending_deselected += 1
            except Exception:
                continue
    except Exception as e:
        print(f"     [SELECTION WARNING] Pending detection failed: {str(e).splitlines()[0]}")
        
    page.wait_for_timeout(800)
    
    # 3. Count remaining selected transactions to ensure we don't print an empty list
    remaining_checked = 0
    try:
        all_checkboxes = page.locator("input[type='checkbox'], [role='checkbox']").all()
        for cb in all_checkboxes:
            is_chk = False
            try:
                is_chk = cb.is_checked()
            except Exception:
                pass
            if not is_chk and cb.get_attribute("aria-checked") == "true":
                is_chk = True
                
            if is_chk:
                lbl = (cb.get_attribute("aria-label") or "").lower()
                cb_id = (cb.get_attribute("id") or "").lower()
                if "select all" not in lbl and "select-all" not in cb_id:
                    remaining_checked += 1
    except Exception:
        pass
        
    print(f"  -> [AUDIT] Pending rows found: {found}; unchecked: {pending_deselected}. Remaining checked: {remaining_checked}")
    return remaining_checked


# ==============================================================================
# STEP 4 & 5: PRINT -> GENERATE PDF VIA CHROME DEVTOOLS (Page.printToPDF)
# ==============================================================================

def clean_old_downloads():
    """Remove any leftover 'American Express - Account Activity*.pdf' from Downloads."""
    pattern = os.path.join(USER_DOWNLOADS_DIR, "American Express - Account Activity*.pdf")
    for f in glob.glob(pattern):
        try:
            os.remove(f)
        except Exception:
            pass


def wait_for_pdf_and_save(target_file_name: str, timeout_s: int = 180) -> str:
    """Wait for the kiosk-printed PDF to appear in Downloads, then move + rename it."""
    target_path = os.path.join(TARGET_DOWNLOAD_DIR, target_file_name)
    found_file = None

    for _ in range(timeout_s):
        candidates = glob.glob(os.path.join(USER_DOWNLOADS_DIR, "American Express - Account Activity*.pdf"))
        # ignore partially-written .crdownload files
        candidates = [c for c in candidates if not c.endswith(".crdownload")]
        if candidates:
            newest = max(candidates, key=os.path.getmtime)
            # ensure it finished writing (size stable)
            try:
                s1 = os.path.getsize(newest)
                time.sleep(1.0)
                s2 = os.path.getsize(newest)
                if s1 == s2 and s1 > 0:
                    found_file = newest
                    break
            except Exception:
                pass
        time.sleep(1)

    if found_file and os.path.exists(found_file):
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        try:
            shutil.move(found_file, target_path)
            return target_path
        except Exception as e:
            print(f"  [PDF WARNING] Could not move file: {e}")
    return ""


def print_and_save_pdf(page: Page, context, formatted_file_name: str) -> None:
    print("  -> [PRINT] Initiating detailed statement print (silent Save as PDF)...")

    clean_old_downloads()

    page.mouse.wheel(0, -2500)
    page.wait_for_timeout(800)

    # 1. Click the toolbar Print button to open the Amex print modal.
    print_triggers = [
        page.get_by_role("button", name=re.compile(r"^\s*Print\s*$", re.IGNORECASE)).first,
        page.locator("button:has-text('Print')").first,
        page.locator("[aria-label*='Print' i]").first,
    ]
    clicked = False
    for pt in print_triggers:
        try:
            if pt.count() > 0 and pt.is_visible():
                pt.scroll_into_view_if_needed()
                pt.click(force=True)
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        print("  [WARNING] Print toolbar button not found.")
        return

    page.wait_for_timeout(1500)

    # 2. Ensure 'Include all additional transaction details' is checked.
    try:
        include_cb = page.locator("div[role='dialog'] input[type='checkbox']").first
        if include_cb.count() > 0:
            if not include_cb.is_checked():
                include_cb.check(force=True)
        else:
            include_lbl = page.locator("label:has-text('Include')").first
            if include_lbl.count() > 0 and include_lbl.is_visible():
                include_lbl.click(force=True)
        print("  -> [PRINT] 'Include all additional transaction details' is ON.")
    except Exception:
        pass

    # Wait for the modal to fully render all details (crucial for 100+ transactions)
    page.wait_for_timeout(5000)

    # 3. Click the modal's blue 'Print' button. With --kiosk-printing, the
    #    resulting window.print() silently saves a PDF to Downloads (no dialog).
    page.wait_for_timeout(2000)
    modal_print_locators = [
        page.locator("div[role='dialog'] button:has-text('Print')").last,
        page.get_by_role("button", name=re.compile(r"^\s*Print\s*$", re.IGNORECASE)).last,
        page.locator("button:has-text('Print')").last,
    ]
    for mb in modal_print_locators:
        try:
            if mb.count() > 0 and mb.is_visible():
                mb.click(force=True)
                break
        except Exception:
            continue
    page.wait_for_timeout(3000)

    print("  -> [PRINT] Waiting for the PDF to be written...")

    # 4. Wait for the silent PDF, then move + rename to the target filename.
    saved = wait_for_pdf_and_save(formatted_file_name)
    if saved and os.path.exists(saved):
        size_kb = os.path.getsize(saved) / 1024
        print(f"  [SUCCESS] Saved Detailed PDF ({size_kb:.1f} KB): {saved}")
    else:
        print(f"  [WARNING] PDF not detected. Check that Chrome was launched with "
              f"--kiosk-printing and 'Save as PDF' is the default destination.")


# ==============================================================================
# MAIN EXECUTION FLOW
# ==============================================================================

def main():
    print("=" * 75)
    print("AMEX STATEMENT EXTRACTION AUTOMATION (PDF EXPORT)")
    print("=" * 75)

    dates = calculate_weekly_date_range()
    print("[DATE CALCULATION]")
    print(f"  - UI Custom Date Range : {dates['ui_start']} to {dates['ui_end']}")
    print(f"  - Filename Date Range  : {dates['file_start']} to {dates['file_end']}")
    print("-" * 75)

    if SYNC_REAL_PROFILE:
        sync_profile_copy()
    else:
        print("[SYSTEM] Using clean automation profile (real-profile sync disabled).")
        os.makedirs(AUTOMATION_USER_DATA_DIR, exist_ok=True)

    # Seed prefs so --kiosk-printing silently saves as PDF into Downloads.
    seed_chrome_prefs()

    with sync_playwright() as p:
        print("[SYSTEM] Launching automation browser (Google Chrome)...")
        launch_kwargs = dict(
            user_data_dir=AUTOMATION_USER_DATA_DIR,
            headless=False,
            args=[
                "--start-maximized",
                "--kiosk-printing",  # window.print() saves PDF silently, no dialog
                "--disable-blink-features=AutomationControlled",
                "--disable-session-crashed-bubble",
                "--hide-crash-restore-bubble",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            no_viewport=True,
            accept_downloads=True,
            downloads_path=USER_DOWNLOADS_DIR,
            timeout=60000,
        )

        context = None
        try:
            context = p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
        except Exception as e:
            print(f"[SYSTEM WARNING] Chrome channel launch failed ({str(e).splitlines()[0]}).")
            print("[SYSTEM] Falling back to Playwright's bundled Chromium...")
            try:
                context = p.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as e2:
                print(f"[CRITICAL] Browser launch failed on both Chrome and Chromium: {str(e2).splitlines()[0]}")
                print("FIXES: 1) Close ALL chrome.exe in Task Manager.  "
                      "2) Ensure Google Chrome is installed.  "
                      "3) Run:  python -m playwright install chromium")
                return

        print("[SYSTEM] Browser launched successfully.")

        page = context.pages[0] if context.pages else context.new_page()

        try:
            login_to_amex(page)

            for idx, member in enumerate(CARD_MEMBERS, start=1):
                print(f"\n[{idx}/{len(CARD_MEMBERS)}] Processing Statement for: '{member}'")

                apply_custom_date_range(page, dates)
                apply_card_member_filter(page, member)
                valid_count = select_transactions_excluding_pending(page)

                if valid_count > 0:
                    file_name = (
                        f"Amex Credit card-12005 Statement from "
                        f"{dates['file_start']} to {dates['file_end']} - {member}.pdf"
                    )
                    print_and_save_pdf(page, context, file_name)
                else:
                    print(f"  [SKIP] '{member}' has 0 posted transactions. Skipping PDF export.")

                page.goto(STATEMENTS_URL, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
                dismiss_popups(page)

            print("\n[LOGOUT] Logging out of American Express...")
            logout_btn = page.locator("a:has-text('Log Out'), button:has-text('Log Out')").first
            if logout_btn.count() > 0:
                logout_btn.click()
                page.wait_for_timeout(2000)

        except Exception as e:
            print(f"\n[CRITICAL ERROR] Execution failed: {e}")
            try:
                page.screenshot(path=os.path.join(TARGET_DOWNLOAD_DIR, "error_screenshot.png"), full_page=True)
            except Exception:
                pass

        finally:
            print("[TEARDOWN] Closing browser session...")
            try:
                context.close()
            except Exception:
                pass
            print("\n" + "=" * 75)
            print("ALL DOWNLOADS COMPLETED.")
            print(f"Files saved at: {TARGET_DOWNLOAD_DIR}")
            print("=" * 75)


if __name__ == "__main__":
    main()