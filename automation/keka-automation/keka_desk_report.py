import os
import re
import time
from playwright.sync_api import sync_playwright, Page

REPORT_URL = "https://karmacpa.keka.com/#/org/assets/reports/allassets"

# Filter values 
ASSET_CATEGORY_LABEL = "Office Hardware"
ASSET_TYPE_LABEL = "Desk"
ASSET_STATUS_LABELS = ["Assigned", "Not Available", "Available"]

# Output
DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads", "keka automation folder")
OUTPUT_BASENAME = "desk"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Chrome profile 
_HOME = os.path.expanduser("~")
AUTOMATION_USER_DATA_DIR = os.path.join(_HOME, "KekaAutomationProfile")
HEADLESS = False 

def dismiss_popups(page: Page) -> None:
    selectors = [
        "button:has-text('Accept All')",
        "button:has-text('Accept')",
        "button[aria-label='Close']",
        "button[title='Close']",
        "button:has-text('No Thanks')",
        "button:has-text('Dismiss')",
        "button:has-text('Got it')",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=300):
                btn.click(force=True)
                page.wait_for_timeout(200)
        except Exception:
            pass


def wait_for_login(page: Page) -> None:
    """
    Keka requires authentication (often SSO/MFA). We navigate to the report
    URL and wait until we are actually on the report page rather than a login
    screen. Complete any login prompt manually in the opened browser window.
    """
    print("[AUTH] Opening Keka report page...")
    page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    dismiss_popups(page)

    print("[AUTH] If a login/SSO/MFA screen appears, complete it in the browser window.")
    print("[AUTH] Waiting until the assets report is loaded (up to 4 minutes)...")

    for _ in range(160):
        url = page.url.lower()
        if "assets/reports/allassets" in url:
            try:
                if page.locator(
                    "text=/asset category/i, text=/filter/i, button:has-text('Submit'), "
                    "button:has-text('Apply')"
                ).first.is_visible(timeout=500):
                    print("[AUTH] Report page detected.")
                    break
            except Exception:
                pass
        page.wait_for_timeout(1500)
    else:
        print("[AUTH WARNING] Could not confirm report page automatically; continuing anyway.")

    if "assets/reports/allassets" not in page.url.lower():
        page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
    dismiss_popups(page)


def _open_dropdown_by_label(page: Page, field_label: str):
    """
    Locate a filter control by its field label (e.g. 'Asset Category') and click
    it to open the dropdown. Returns True if a control was clicked.
    Tries several common Keka/Angular patterns.  # >>> ADJUST IF NEEDED
    """
    label_re = re.compile(re.escape(field_label), re.IGNORECASE)

    candidate_locators = [
        page.locator(
            "div,section",
            has_text=label_re,
        ).locator(
            "[role='combobox'], .ng-select-container, .select2-selection, "
            "input[readonly], .dropdown-toggle, button"
        ).first,
        page.locator(f"ng-select:has-text('{field_label}')").first,
        page.get_by_text(label_re, exact=False).locator(
            "xpath=following::*[self::div or self::button or self::input]"
            "[@role='combobox' or contains(@class,'ng-select') or "
            "contains(@class,'dropdown') or @readonly][1]"
        ).first,
    ]

    for loc in candidate_locators:
        try:
            if loc.count() > 0 and loc.is_visible():
                loc.scroll_into_view_if_needed()
                loc.click(force=True)
                page.wait_for_timeout(800)
                return True
        except Exception:
            continue
    print(f"     [FILTER WARNING] Could not open dropdown for '{field_label}'.")
    return False


def _pick_option(page: Page, option_label: str) -> bool:
    """
    Click an option in an open dropdown by its visible text (exact-ish match).
    """
    opt_re = re.compile(rf"^\s*{re.escape(option_label)}\s*$", re.IGNORECASE)
    option_locators = [
        page.get_by_role("option", name=opt_re).first,
        page.locator(".ng-option, .select2-results__option, [role='option'], li, "
                     ".dropdown-item").filter(has_text=opt_re).first,
        page.get_by_text(opt_re).first,
    ]
    for loc in option_locators:
        try:
            if loc.count() > 0 and loc.is_visible():
                loc.scroll_into_view_if_needed()
                loc.click(force=True)
                page.wait_for_timeout(500)
                return True
        except Exception:
            continue
    print(f"     [FILTER WARNING] Option '{option_label}' not found in dropdown.")
    return False


def set_single_select(page: Page, field_label: str, option_label: str) -> None:
    print(f"  -> [FILTER] {field_label} = '{option_label}'")
    if _open_dropdown_by_label(page, field_label):
        _pick_option(page, option_label)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)


def set_multi_select(page: Page, field_label: str, option_labels) -> None:
    print(f"  -> [FILTER] {field_label} = {option_labels} (multi)")
    if not _open_dropdown_by_label(page, field_label):
        return
    for opt in option_labels:
        _pick_option(page, opt)
        page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def click_submit(page: Page) -> None:
    print("  -> [SUBMIT] Applying filters...")
    for sel in [
        "button:has-text('Submit')",
        "button:has-text('Apply')",
        "button:has-text('Run')",
        "button:has-text('Generate')",
        "button[type='submit']",
    ]:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.scroll_into_view_if_needed()
                btn.click(force=True)
                print(f"     [SUBMIT] Clicked '{sel}'.")
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                return
        except Exception:
            continue
    print("     [SUBMIT WARNING] No Submit/Apply button found.")


def download_report(page: Page) -> None:
    print("  -> [DOWNLOAD] Triggering report download...")
    download_triggers = [
        "button:has-text('Download')",
        "button:has-text('Export')",
        "a:has-text('Download')",
        "a:has-text('Export')",
        "[aria-label*='Download' i]",
        "[title*='Download' i]",
        "button:has-text('Excel')",
    ]

    for sel in download_triggers:
        try:
            trigger = page.locator(sel).first
            if trigger.count() == 0 or not trigger.is_visible():
                continue
            trigger.scroll_into_view_if_needed()
            with page.expect_download(timeout=60000) as dl_info:
                trigger.click(force=True)
                page.wait_for_timeout(800)
                for follow in ["Excel", "CSV", "Download", "Export"]:
                    try:
                        item = page.get_by_text(re.compile(follow, re.IGNORECASE)).first
                        if item.count() > 0 and item.is_visible():
                            item.click(force=True)
                            break
                    except Exception:
                        pass
            download = dl_info.value
            suggested = download.suggested_filename
            ext = os.path.splitext(suggested)[1] or ".xlsx"
            target = os.path.join(DOWNLOAD_FOLDER, f"{OUTPUT_BASENAME}{ext}")
            if os.path.exists(target):
                os.remove(target)
            download.save_as(target)
            size_kb = os.path.getsize(target) / 1024
            print(f"     [SUCCESS] Saved ({size_kb:.1f} KB): {target}")
            return
        except Exception as e:
            print(f"     [DOWNLOAD] '{sel}' did not download ({str(e).splitlines()[0]}); trying next.")
            continue

    print("     [DOWNLOAD WARNING] Could not download the report. "
          "Check the download button label in the UI.")

def main():
    print("=" * 70)
    print("KEKA ASSET REPORT AUTOMATION")
    print("=" * 70)
    print(f"Output folder : {DOWNLOAD_FOLDER}")
    print(f"Output name   : {OUTPUT_BASENAME}")
    print("-" * 70)

    os.makedirs(AUTOMATION_USER_DATA_DIR, exist_ok=True)

    with sync_playwright() as p:
        print("[SYSTEM] Launching Chrome...")
        launch_kwargs = dict(
            user_data_dir=AUTOMATION_USER_DATA_DIR,
            headless=HEADLESS,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            no_viewport=True,
            accept_downloads=True,
            downloads_path=DOWNLOAD_FOLDER,
        )
        try:
            context = p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
        except Exception as e:
            print(f"[SYSTEM] Chrome channel failed ({str(e).splitlines()[0]}); using bundled Chromium.")
            context = p.chromium.launch_persistent_context(**launch_kwargs)

        page = context.pages[0] if context.pages else context.new_page()

        try:
            wait_for_login(page)

            print("\n[FILTERS] Applying filters...")
            set_single_select(page, "Asset Category", ASSET_CATEGORY_LABEL)
            set_single_select(page, "Asset Type", ASSET_TYPE_LABEL)
            set_multi_select(page, "Asset Status", ASSET_STATUS_LABELS)

            click_submit(page)
            download_report(page)

        except Exception as e:
            print(f"\n[CRITICAL ERROR] {e}")
            try:
                page.screenshot(path=os.path.join(DOWNLOAD_FOLDER, "error_screenshot.png"),
                                full_page=True)
                print("[INFO] Saved error_screenshot.png for debugging.")
            except Exception:
                pass
        finally:
            print("\n[TEARDOWN] Closing browser in 5s...")
            time.sleep(5)
            try:
                context.close()
            except Exception:
                pass
            print("=" * 70)
            print("DONE.")
            print("=" * 70)


if __name__ == "__main__":
    main()
