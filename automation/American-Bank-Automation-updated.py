"""
================================================================================
American Express Statement Extraction Automation
Framework: Python Playwright (Synchronous) + Persistent Chrome Profile
================================================================================
"""

import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

# ==============================================================================
# CONFIGURATION & CREDENTIALS
# ==============================================================================
# Standard Login Portal (with Account Type dropdown)
LOGIN_URL = "https://www.americanexpress.com/en-us/account/login?inav=iNavLnkLog"
STATEMENTS_URL = "https://global.americanexpress.com/activity/days-30"

# Credentials from the provided image
AMEX_USER_ID = "Amexsiddhi1531"
AMEX_PASSWORD = "Team%karmacpa1234"

# Target Card Members
CARD_MEMBERS = ["Prinesh", "Rashmi", "Pranav", "Priti"]

# Destination directory for statements
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "Amex_Statements")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Chrome profile sync configuration (Matches Harleysville automation)
REAL_USER_DATA_DIR = r"C:\Users\Meet Patel\AppData\Local\Google\Chrome\User Data"
REAL_PROFILE_DIR = "Default"
AUTOMATION_USER_DATA_DIR = r"C:\Users\Meet Patel\ChromeAutomationProfile"
AUTOMATION_PROFILE_DIR = "Default"


# ==============================================================================
# CHROME PROFILE & PROCESS MANAGEMENT
# ==============================================================================

def close_all_chrome():
    """Kills running chrome instances to free up lockfiles for safe profile copying."""
    print("[SYSTEM] Ensuring no locked Chrome instances are running...")
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
    time.sleep(1.5)


def sync_profile_copy():
    """Copies user's actual Chrome profile into the automation directory."""
    print("[SYSTEM] Syncing browser profile from local Chrome...")
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

    def ignore_locks(dir, contents):
        return [c for c in contents if c.startswith("Singleton") or c in ("lockfile", "Code Cache")]

    if os.path.exists(dst):
        for _ in range(5):
            try:
                shutil.rmtree(dst, ignore_errors=True)
                break
            except Exception:
                time.sleep(1)

    try:
        shutil.copytree(src, dst, ignore=ignore_locks, dirs_exist_ok=True)
        print("[SYSTEM] Chrome profile sync complete.")
    except Exception as e:
        print(f"[SYSTEM WARNING] Partial profile copy warning (non-fatal): {e}")


# ==============================================================================
# DATE CALCULATION LOGIC
# ==============================================================================

def calculate_weekly_date_range(reference_date: datetime = None) -> dict:
    """
    Calculates the Saturday-to-Friday rolling weekly cycle dynamically.
    - If run on or after Sunday (e.g., Monday 31/08/2026), it selects:
      - Start Date: Most recent Saturday (29/08/2026)
      - End Date: Start Date + 6 days / Friday (04/09/2026)
    """
    if reference_date is None:
        reference_date = datetime.now()

    # weekday(): Monday is 0, Sunday is 6, Saturday is 5
    weekday = reference_date.weekday()
    days_since_sat = (weekday - 5) % 7

    start_date = reference_date - timedelta(days=days_since_sat)
    end_date = start_date + timedelta(days=6)

    return {
        # Format for Amex UI inputs (MM/DD/YYYY)
        "ui_start": start_date.strftime("%m/%d/%Y"),
        "ui_end": end_date.strftime("%m/%d/%Y"),
        # Format for output filename (D/M/YY or DD/MM/YY without leading slash issues)
        "file_start": f"{start_date.day}/{start_date.month}/{start_date.strftime('%y')}",
        "file_end": f"{end_date.day}/{end_date.month}/{end_date.strftime('%y')}"
    }


# ==============================================================================
# HELPER ACTIONS
# ==============================================================================

def dismiss_popups(page: Page) -> None:
    """Dismisses cookie banners, surveys, promotional modal dialogs, and CAPTCHA overlay close (X) buttons."""
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
        "[class*='close' i]:has-text('×')"
    ]
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=400):
                btn.click(force=True)
                page.wait_for_timeout(300)
        except Exception:
            pass


def login_to_amex(page: Page) -> None:
    """Performs authentication from the standard login page (with Account Type) and routes to Statements."""
    print("[AUTH] Navigating to standard login portal...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    dismiss_popups(page)

    # Check if already authenticated via session cookies
    if "account/login" not in page.url.lower():
        print("[AUTH SUCCESS] Active session already authenticated!")
    else:
        # Fill Credentials with realistic human typing
        print("[AUTH] Entering credentials...")
        user_input = page.locator("input#elButton_username, input#userId, input[name='userId'], input[name*='user' i]").first
        pass_input = page.locator("input#elButton_password, input#password, input[name='password'], input[name*='pass' i]").first

        user_input.wait_for(state="visible", timeout=15000)
        user_input.fill("")
        user_input.type(AMEX_USER_ID, delay=50)
        page.wait_for_timeout(300)
        
        pass_input.fill("")
        pass_input.type(AMEX_PASSWORD, delay=50)
        page.wait_for_timeout(300)

        # Click Log In
        print("[AUTH] Submitting login...")
        login_btn = page.locator("button#elButton_submit, button#login-submit, button[type='submit'], button:has-text('Log In')").first
        if login_btn.count() > 0 and login_btn.is_visible():
            login_btn.click()
        else:
            pass_input.press("Enter")

        print("[AUTH] Waiting for authentication to complete...")
        print("[AUTH] Note: If CAPTCHA or verification appears, solve it in the browser window...")
        
        # Wait for the user to solve CAPTCHA and complete login
        while True:
            current_url = page.url.lower()
            if "account/login" not in current_url:
                print("[AUTH SUCCESS] Successfully authenticated!")
                break

            # If "temporarily unavailable" error banner is detected, retry submit
            error_banner = page.locator("text=temporarily unavailable, text=We're sorry").first
            if error_banner.count() > 0 and error_banner.is_visible():
                print("[AUTH NOTICE] Temporary session error detected. Retrying submit...")
                page.wait_for_timeout(2000)
                if login_btn.count() > 0 and login_btn.is_visible():
                    login_btn.click()

            page.wait_for_timeout(1500)

    page.wait_for_timeout(3000)

    # Now navigate to Statements & Activity page once authenticated
    print(f"[ROUTING] Navigating to Statements & Activity page ({STATEMENTS_URL})...")
    page.goto(STATEMENTS_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    dismiss_popups(page)
    print("[ROUTING SUCCESS] Successfully reached Statements & Activity.")


def apply_custom_date_range(page: Page, start_date_str: str, end_date_str: str) -> None:
    """Selects Custom Date Range and inputs the calculated start and end dates."""
    print(f"  -> [DATE RANGE] Applying Custom Range: {start_date_str} to {end_date_str}")
    
    # 1. Click the Date Period dropdown (e.g. 'Last 30 Days')
    date_dropdown = page.locator("button:has-text('Last 30 Days'), button:has-text('Date Period'), button:has-text('Days'), button[aria-label*='Date' i]").first
    date_dropdown.click(force=True)
    page.wait_for_timeout(1000)

    # 2. Select 'Custom Date Range' option if present in dropdown
    custom_option = page.locator("button:has-text('Custom Date Range'), [role='button']:has-text('Custom Date Range'), [role='option']:has-text('Custom Date Range')").first
    if custom_option.count() > 0 and custom_option.is_visible():
        custom_option.click(force=True)
        page.wait_for_timeout(800)

    # 3. Enter Start and End Dates (MM/DD/YYYY)
    inputs = page.locator("input[placeholder*='MM/DD/YYYY' i], input[aria-label*='Date' i], input[type='text']").all()
    date_inputs = [inp for inp in inputs if inp.is_visible()]
    if len(date_inputs) >= 2:
        date_inputs[0].fill("")
        date_inputs[0].fill(start_date_str)
        page.wait_for_timeout(300)
        date_inputs[1].fill("")
        date_inputs[1].fill(end_date_str)
        page.wait_for_timeout(300)

    # 4. Click 'Done' button in Date Period popover
    done_btn = page.locator("button:has-text('Done'), button:has-text('Apply')").first
    if done_btn.count() > 0 and done_btn.is_visible():
        done_btn.click(force=True)

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)


def apply_card_member_filter(page: Page, member_name: str) -> None:
    """Opens Filter popup, selects the specified member radio button, and clicks Apply Changes."""
    print(f"  -> [FILTER] Setting filter for card member: '{member_name}'")
    
    # 1. Open Filter popup
    filter_btn = page.locator("button:has-text('Filter'), button[aria-label*='Filter' i]").first
    filter_btn.click(force=True)
    page.wait_for_timeout(1200)

    # 2. Select card member radio / label
    member_elem = page.locator(f"label:has-text('{member_name}'), span:has-text('{member_name}')").first
    if member_elem.count() > 0:
        member_elem.click(force=True)

    page.wait_for_timeout(800)

    # 3. Click 'Apply Changes' button in the Filters modal
    apply_locators = [
        page.locator("button:has-text('Apply Changes')").first,
        page.locator("div[role='dialog'] button:has-text('Apply Changes')").first,
        page.locator("button:has-text('Apply')").first
    ]
    for loc in apply_locators:
        try:
            if loc.count() > 0 and loc.is_visible():
                loc.scroll_into_view_if_needed()
                loc.click(force=True)
                break
        except Exception:
            continue

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)


def select_transactions_excluding_pending(page: Page) -> None:
    """Selects all transactions on the page, then scrolls down to uncheck any with 'Pending' status."""
    print("  -> [SELECTION] Selecting all transactions on page...")
    
    # 1. Native scroll up to ensure 'Select All on Page' checkbox is in view
    page.mouse.wheel(0, -1000)
    page.wait_for_timeout(500)

    # Click 'Select All on Page' checkbox or label
    select_all_cb = page.locator("input[type='checkbox'][aria-label*='Select All' i], label:has-text('Select All') input, input#select-all").first
    if select_all_cb.count() > 0:
        if not select_all_cb.is_checked():
            select_all_cb.check(force=True)
    else:
        btn_sel = page.locator("label:has-text('Select All'), button:has-text('Select All'), span:has-text('Select All on Page')").first
        if btn_sel.count() > 0:
            btn_sel.click(force=True)

    page.wait_for_timeout(1000)

    # 2. Scroll through the transactions table using native mouse wheel to evaluate all rows
    print("  -> [SELECTION] Scanning & scrolling table to deselect rows with 'Pending' status...")
    pending_deselected = 0

    for _ in range(5):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(400)
        
        rows = page.locator("table tbody tr, div[role='row']").all()
        for row in rows:
            try:
                row_text = row.inner_text()
                if re.search(r"\bPending\b", row_text, re.IGNORECASE):
                    cb = row.locator("input[type='checkbox']").first
                    if cb.count() > 0 and cb.is_checked():
                        cb.uncheck(force=True)
                        pending_deselected += 1
            except Exception:
                continue

    # Scroll back to the top
    page.mouse.wheel(0, -2500)
    page.wait_for_timeout(800)

    print(f"  -> [AUDIT] Excluded {pending_deselected} Pending transaction(s).")


def export_and_rename_excel(page: Page, formatted_file_name: str) -> None:
    """Triggers download popup, selects Excel option, intercepts download, and renames file."""
    print(f"  -> [DOWNLOAD] Intercepting Excel export...")
    
    # 1. Scroll to top to ensure action buttons are visible
    page.mouse.wheel(0, -2500)
    page.wait_for_timeout(600)

    # Click main Download toolbar/action button
    download_triggers = [
        page.locator("button:has-text('Download')").first,
        page.locator("[aria-label*='Download' i]").first,
        page.locator("[data-testid*='download' i]").first,
        page.get_by_role("button", name=re.compile(r"^Download$", re.IGNORECASE)).first
    ]
    
    for dt in download_triggers:
        try:
            if dt.count() > 0 and dt.is_visible():
                dt.scroll_into_view_if_needed()
                dt.click(force=True)
                break
        except Exception:
            continue

    page.wait_for_timeout(1500)

    # 2. In 'Select File Type' modal, ensure Excel is chosen
    try:
        excel_label = page.locator("label:has-text('Excel'), label[for*='excel' i]").first
        if excel_label.count() > 0 and excel_label.is_visible():
            excel_label.click(force=True)
            page.wait_for_timeout(400)
    except Exception:
        pass

    # 3. Locate and click the blue 'Download' button / link in the modal
    final_path = os.path.join(DOWNLOAD_DIR, formatted_file_name)
    with page.expect_download(timeout=45000) as download_info:
        modal_dl_locators = [
            page.locator("a[href*='format=excel' i]").first,
            page.locator("a:has-text('Download')").last,
            page.locator("button:has-text('Download')").last,
            page.get_by_role("link", name=re.compile(r"^Download$", re.IGNORECASE)).last,
            page.get_by_role("button", name=re.compile(r"^Download$", re.IGNORECASE)).last
        ]
        
        for loc in modal_dl_locators:
            try:
                if loc.count() > 0 and loc.is_visible():
                    loc.scroll_into_view_if_needed()
                    loc.click(force=True)
                    break
            except Exception:
                continue

    download = download_info.value
    download.save_as(final_path)
    print(f"  [SUCCESS] Saved: {final_path}")


# ==============================================================================
# MAIN EXECUTION FLOW
# ==============================================================================

def main():
    print("=" * 75)
    print("AMEX STATEMENT EXTRACTION AUTOMATION")
    print("=" * 75)

    dates = calculate_weekly_date_range()
    print(f"[DATE CALCULATION]")
    print(f"  - UI Custom Date Range : {dates['ui_start']} to {dates['ui_end']}")
    print(f"  - Filename Date Range  : {dates['file_start']} to {dates['file_end']}")
    print("-" * 75)

    # 1. Close active chrome and sync profile
    close_all_chrome()
    sync_profile_copy()

    with sync_playwright() as p:
        # Launch persistent Chrome context using your actual synced profile
        context = p.chromium.launch_persistent_context(
            user_data_dir=AUTOMATION_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ],
            no_viewport=True,
            accept_downloads=True,
            downloads_path=DOWNLOAD_DIR
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Login
            login_to_amex(page)

            # 2. Process each Card Member individually
            for idx, member in enumerate(CARD_MEMBERS, start=1):
                print(f"\n[{idx}/{len(CARD_MEMBERS)}] Processing Statement for: '{member}'")
                
                # STEP 1: Apply Custom Date Range FIRST
                apply_custom_date_range(page, dates["ui_start"], dates["ui_end"])

                # STEP 2: Apply Card Member Filter SECOND
                apply_card_member_filter(page, member)

                # STEP 3: Select All on Page & Deselect Pending
                select_transactions_excluding_pending(page)

                # STEP 4: Build Filename and Export to Excel
                file_name = (
                    f"Amex Credit card-12005 Statement from "
                    f"{dates['file_start'].replace('/', '-')} and {dates['file_end'].replace('/', '-')} - {member}.xlsx"
                )
                export_and_rename_excel(page, file_name)

                # Reset to base Statements page for clean next iteration
                page.goto(STATEMENTS_URL, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2000)
                dismiss_popups(page)

            # 3. Log Out
            print("\n[LOGOUT] Logging out of American Express...")
            logout_btn = page.locator("a:has-text('Log Out'), button:has-text('Log Out')").first
            if logout_btn.count() > 0:
                logout_btn.click()
                page.wait_for_timeout(2000)

        except Exception as e:
            print(f"\n[CRITICAL ERROR] Execution failed: {e}")
            page.screenshot(path=os.path.join(DOWNLOAD_DIR, "error_screenshot.png"), full_page=True)

        finally:
            print("[TEARDOWN] Closing browser session...")
            context.close()
            print("\n" + "=" * 75)
            print("ALL DOWNLOADS COMPLETED.")
            print(f"Files saved at: {DOWNLOAD_DIR}")
            print("=" * 75)


if __name__ == "__main__":
    main()