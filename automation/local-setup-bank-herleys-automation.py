from datetime import datetime
import base64
import os
import re
import shutil
import subprocess
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from playwright.sync_api import sync_playwright

# --- Configuration ---
BASE_DOWNLOAD_DIR = r"C:\Users\Meet Patel\Desktop\Bank_Statements"

# Set to False once the toolbar detection is confirmed working, to let it
# run through all accounts even if a rare one fails.
STOP_ON_FIRST_FAILURE = True
START_DATE = "07/01/2026"
END_DATE = "07/31/2026"

# Smart month-year folder, e.g. Bank_Statements\August-2026\
DOWNLOAD_DIR = os.path.join(BASE_DOWNLOAD_DIR, datetime.now().strftime("%B-%Y"))

# Login Credentials
BANK_USER = os.environ.get("HARLEYSVILLE_USER", "DMCAccounting")
BANK_PASS = os.environ.get("HARLEYSVILLE_PASS", "a3XRaQ?1J1}3")

# Gmail API config - the OTP-relay inbox
GMAIL_CREDENTIALS_FILE = r"C:\Users\Meet Patel\Desktop\automation\Bank-Herleysville-Automation\client_secrets_for_Bank-Herleysville-Automation.json"
GMAIL_TOKEN_FILE = r"C:\Users\Meet Patel\Desktop\automation\Bank-Herleysville-Automation\token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SMS_SENDER_SUBJECT = "SMS From 86434 To 15623144365"

# Profile Cloning Paths
REAL_USER_DATA_DIR = r"C:\Users\Meet Patel\AppData\Local\Google\Chrome\User Data"
REAL_PROFILE_DIR = "Default"
AUTOMATION_USER_DATA_DIR = r"C:\Users\Meet Patel\ChromeAutomationProfile"
AUTOMATION_PROFILE_DIR = "Default"

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def close_all_chrome():
    print("🔪 Closing any running Chrome windows first...")
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
    time.sleep(2)


def sync_profile_copy():
    print("📋 Syncing your Meet login into the automation profile...")
    src = os.path.join(REAL_USER_DATA_DIR, REAL_PROFILE_DIR)
    dst = os.path.join(AUTOMATION_USER_DATA_DIR, AUTOMATION_PROFILE_DIR)
    os.makedirs(AUTOMATION_USER_DATA_DIR, exist_ok=True)

    local_state_src = os.path.join(REAL_USER_DATA_DIR, "Local State")
    local_state_dst = os.path.join(AUTOMATION_USER_DATA_DIR, "Local State")
    if os.path.exists(local_state_src):
        shutil.copy2(local_state_src, local_state_dst)

    def ignore_locks(dir, contents):
        return [c for c in contents if c.startswith("Singleton") or c == "lockfile"]

    if os.path.exists(dst):
        shutil.rmtree(dst, ignore_errors=True)

    shutil.copytree(src, dst, ignore=ignore_locks)
    print("✅ Profile synced.")


def dismiss_cookie_banner(page):
    try:
        page.get_by_text("Accept", exact=True).click(timeout=4000)
        print("    - Dismissed cookie banner.")
    except Exception:
        pass


def get_gmail_service():
    creds = None
    if os.path.exists(GMAIL_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GMAIL_CREDENTIALS_FILE):
                raise FileNotFoundError(f"Missing {GMAIL_CREDENTIALS_FILE}.")
            flow = InstalledAppFlow.from_client_secrets_file(
                GMAIL_CREDENTIALS_FILE, GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

        with open(GMAIL_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_otp_from_gmail(requested_after_ms):
    print("📧 Fetching OTP via Gmail API...")
    service = get_gmail_service()

    otp_code = None
    for attempt in range(8):
        results = (
            service.users()
            .messages()
            .list(userId="me", q=f'subject:"{SMS_SENDER_SUBJECT}" newer_than:1h', maxResults=10)
            .execute()
        )

        messages = results.get("messages", [])
        for m in messages:
            msg = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
            msg_time_ms = int(msg.get("internalDate", "0"))
            if msg_time_ms < requested_after_ms:
                continue

            body_text = _extract_gmail_body_text(msg)
            matches = re.findall(r"Harleysville Bank.*?code is (\d{6})", body_text, re.IGNORECASE | re.DOTALL)
            if matches:
                otp_code = matches[-1]
                print(f"    ✅ Found fresh Harleysville OTP Code: {otp_code}")
                break

        if otp_code:
            break

        print(f"    - No new SMS yet, waiting... (attempt {attempt + 1}/8)")
        time.sleep(5)

    if not otp_code:
        otp_code = input("Type the 6-digit code from the SMS email and press Enter: ").strip()

    return otp_code


def _extract_gmail_body_text(message):
    def decode_part(data):
        return base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8", errors="ignore")

    payload = message.get("payload", {})
    if "body" in payload and payload["body"].get("data"):
        return decode_part(payload["body"]["data"])

    text_chunks = []
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            text_chunks.append(decode_part(part["body"]["data"]))
        elif part.get("body", {}).get("data"):
            text_chunks.append(decode_part(part["body"]["data"]))

    return "\n".join(text_chunks) if text_chunks else message.get("snippet", "")


def _get_toolbar_icons(page, debug_dir=None):
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)

    viewport = page.viewport_size or {"width": 1512, "height": 900}
    page_width = viewport["width"]

    selector = (
        "button, a[role='button'], div[role='button'], span[role='button'], "
        "[role='button'], button svg, button i, button img, "
        "[class*='icon' i], [class*='btn' i] svg, [class*='btn' i] i"
    )
    all_candidates_loc = page.locator(selector)
    count = all_candidates_loc.count()

    seen_boxes = set()
    candidates = []
    for idx in range(count):
        el = all_candidates_loc.nth(idx)
        try:
            box = el.bounding_box()
        except Exception:
            continue
        if not box or box["width"] == 0 or box["height"] == 0:
            continue

        key = (round(box["x"]), round(box["y"]))
        if key in seen_boxes:
            continue
        seen_boxes.add(key)

        right_side = box["x"] > page_width * 0.35
        near_top = box["y"] < 520
        icon_sized = box["width"] < 80 and box["height"] < 80
        if right_side and near_top and icon_sized:
            clickable = el.locator("xpath=ancestor-or-self::*[self::button or self::a or @role='button'][1]")
            target = clickable if clickable.count() > 0 else el
            candidates.append((box["y"], box["x"], target))

    candidates.sort(key=lambda c: (round(c[0] / 10), c[1]))
    return [btn for _, _, btn in candidates]


def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"📂 Statements will be saved to: {DOWNLOAD_DIR}")

    close_all_chrome()
    sync_profile_copy()

    print("\n🌐 Launching Chrome (synced Meet profile) via Playwright...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=AUTOMATION_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )

        page = context.pages[0] if context.pages else context.new_page()

        # PHASE 1: LOGIN
        print("🏦 Navigating to harleysvillebank.com...")
        page.goto("https://harleysvillebank.com", timeout=60000)
        dismiss_cookie_banner(page)

        if "online.harleysvillebank.com" not in page.url:
            print("🔐 Filling login widget...")
            desktop_form = page.locator("#desktop-username").locator("xpath=ancestor::form[1]")
            page.locator("#desktop-username").fill(BANK_USER)
            desktop_form.locator("input[type='password']").first.fill(BANK_PASS)

            try:
                remember_checkbox = desktop_form.locator("input[type='checkbox']").first
                if remember_checkbox.count() > 0:
                    remember_checkbox.check(timeout=3000)
                else:
                    desktop_form.get_by_text(re.compile("remember", re.IGNORECASE)).click(timeout=3000)
            except Exception:
                print("    ⚠️ Could not find 'Remember me' - continuing without it.")

            desktop_form.get_by_role("button", name="LOGIN", exact=False).click()

            print("⏳ Checking whether MFA is required...")
            try:
                page.wait_for_selector("text=Please select a target", timeout=15000)
                mfa_required = True
            except Exception:
                mfa_required = False

            if mfa_required:
                print("📱 MFA required. Selecting SMS target...")
                sms_btn = page.get_by_text(re.compile("SMS", re.IGNORECASE)).first
                sms_btn.wait_for(state="visible", timeout=10000)

                sms_requested_at_ms = int(time.time() * 1000) - 3000
                sms_btn.click(timeout=8000)

                page.wait_for_selector("text=Enter your Secure Access Code", timeout=15000)
                otp_code = get_otp_from_gmail(sms_requested_at_ms)

                page.bring_to_front()
                print("    - Submitting OTP...")
                page.get_by_placeholder("Secure Access Code").fill(otp_code)
                page.get_by_role("button", name="Submit").click()
            else:
                print("✅ MFA bypassed.")

            print("⏳ Waiting for account data to load...")
            page.wait_for_url("**/landingPage", timeout=30000)
        else:
            print("✅ Already logged in.")

        # PHASE 2: DASHBOARD & DOWNLOADING
        print("⏳ Waiting for dashboard (ACCOUNTS) to load...")
        page.wait_for_selector("text=ACCOUNTS", timeout=35000)
        print("🏦 Dashboard detected. Scanning for accounts...")
        page.wait_for_timeout(2000)

        account_cards = page.locator("text='Available Balance'")
        account_count = account_cards.count()

        if account_count == 0:
            print("❌ Could not find any accounts. Script terminating.")
            return

        print(f"🔍 Found {account_count} accounts. Starting download sequence...\n")

        for i in range(account_count):
            print(f"➡️ Processing Account {i + 1} of {account_count}...")

            account_cards = page.locator("text='Available Balance'")
            card = account_cards.nth(i).locator(
                "xpath=ancestor::*[self::div][.//text()[contains(.,'Available Balance')]][1]"
            )
            try:
                card.click(timeout=8000)
            except Exception:
                account_cards.nth(i).click(timeout=8000)

            try:
                page.wait_for_selector("text=Transactions", timeout=15000)
                page.wait_for_timeout(1500)

                try:
                    account_name = (
                        page.locator("text=Last Updated:")
                        .locator("xpath=preceding::*[self::h1 or self::h2][1]")
                        .inner_text(timeout=5000)
                    )
                except Exception:
                    account_name = f"Account_{i + 1}"

                safe_name = re.sub(r'[\\/*?:"<>|]', "_", account_name).strip()[:60] or f"Account_{i + 1}"
                print(f"    - Account: {account_name}")

                toolbar = _get_toolbar_icons(page, debug_dir=os.path.join(DOWNLOAD_DIR, "_debug"))
                if len(toolbar) < 3:
                    raise RuntimeError(f"Could not reliably locate toolbar icons (found {len(toolbar)}).")

                print("    - Opening filter panel...")
                filter_opened = False
                for candidate_idx, candidate_btn in enumerate(toolbar):
                    try:
                        candidate_btn.scroll_into_view_if_needed()
                        candidate_btn.click(timeout=4000, force=True)
                    except Exception:
                        continue

                    try:
                        page.wait_for_selector("text=Time Period", timeout=3000)
                        print(f"    ✅ Filter panel opened via toolbar icon #{candidate_idx}")
                        filter_opened = True
                        break
                    except Exception:
                        continue

                if not filter_opened:
                    raise RuntimeError("Filter panel could not be opened.")

                print("    - Selecting 'Custom Date' time period...")
                try:
                    time_period_input = page.locator("text=Time Period").locator("xpath=following::input[1]")
                    time_period_input.click(timeout=5000)
                    page.wait_for_selector("text=Custom Date", timeout=5000)
                    page.get_by_text("Custom Date", exact=True).first.click(timeout=5000)
                except Exception as dropdown_err:
                    print(f"    ⚠️ Could not select Custom Date dropdown option: {dropdown_err}")

                page.wait_for_selector("text=Start Date", timeout=8000)
                page.wait_for_timeout(500)

                print(f"    - Setting dates: {START_DATE} to {END_DATE}")

                def _pick_q2_calendar_date(label_text, date_str):
                    target = datetime.strptime(date_str, "%m/%d/%Y")
                    target_month_name = MONTH_NAMES[target.month - 1]
                    target_year = target.year
                    target_date_attr = target.strftime("%Y-%m-%d")

                    q2_el = page.locator(f"q2-calendar[label='{label_text}']").first
                    q2_el.wait_for(state="visible", timeout=5000)

                    popover_opened = False
                    for _ in range(3):
                        try:
                            q2_el.click(timeout=5000)
                            page.wait_for_timeout(400)
                            popover = page.locator(".q2-calendar-dropdown, .calendar-dropdown, div.dropdown-menu, q2-calendar .card, q2-calendar .popover").last
                            if popover.count() == 0:
                                popover = page.locator("text=TODAY").locator("xpath=ancestor::*[position()<=6]").last
                            popover_opened = True
                            break
                        except Exception:
                            page.wait_for_timeout(500)
                            continue

                    if not popover_opened:
                        return False

                    try:
                        for _ in range(36):
                            header_el = q2_el.locator("text=" + target_month_name)
                            if header_el.count() > 0 and q2_el.locator(f"text={target_year}").count() > 0:
                                break
                            
                            nav_btn = q2_el.locator("button, [role='button']").filter(has_text=re.compile(r"^[><«»‹›]$")).last
                            if nav_btn.count() > 0:
                                nav_btn.click(timeout=2000)
                                page.wait_for_timeout(300)
                            else:
                                break

                        day_cell = q2_el.locator(f"[data-date='{target_date_attr}'], td[data-date='{target_date_attr}']").first
                        if day_cell.count() > 0:
                            day_cell.click(timeout=5000)
                        else:
                            q2_el.get_by_text(str(target.day), exact=True).last.click(timeout=5000)
                        
                        page.wait_for_timeout(400)
                    except Exception as e:
                        print(f"    ⚠️ Error setting {label_text}: {e}")
                        return False

                    return True

                start_ok = _pick_q2_calendar_date("Start Date", START_DATE)
                end_ok = _pick_q2_calendar_date("End Date", END_DATE)

                if not (start_ok and end_ok):
                    raise RuntimeError(f"Could not fill date fields (start_ok={start_ok}, end_ok={end_ok}).")

                print("    - Applying filters...")
                page.get_by_role("button", name="Apply Filters").click(timeout=8000)
                
                # Stabilization pause for table re-rendering
                page.wait_for_timeout(3000)

                # --- CHECK FOR ZERO TRANSACTIONS AFTER FILTERING ---
                no_transactions_msg = page.locator("text='There are no transactions that match your filter'")
                if no_transactions_msg.count() > 0 and no_transactions_msg.is_visible():
                    print("    ℹ️ No transactions found for this date filter. Skipping download for this account.")
                else:
                    print("    - Opening export menu...")
                    
                    export_toolbar_btn = page.locator("button:has(svg), [role='button']:has(svg)").nth(-2)

                    try:
                        export_toolbar_btn.click(timeout=8000, force=True)
                    except Exception:
                        page.locator("button svg").last.click(force=True)

                    page.wait_for_timeout(1000)
                    print("    ✅ Export menu opened successfully.")
                    print("    - Selecting 'Spreadsheet (xls)'...")

                    export_option = page.get_by_text("Spreadsheet (xls)", exact=True)
                    export_option.wait_for(state="attached", timeout=8000)
                    file_ext = "xls"

                    with page.expect_download(timeout=20000) as download_info:
                        export_option.evaluate("node => node.click()")

                    download = download_info.value
                    file_path = os.path.join(DOWNLOAD_DIR, f"{safe_name}.{file_ext}")
                    download.save_as(file_path)
                    print(f"    ✅ Downloaded: {file_path}")

            except Exception as e:
                print(f"    ⚠️ FAILED to process Account {i + 1}. Error: {str(e).splitlines()[0]}")
                if STOP_ON_FIRST_FAILURE:
                    context.close()
                    return

            print("    - Returning to dashboard...")
            try:
                back_link = (
                    page.locator("a:has-text('Back'), button:has-text('Back')")
                    .filter(has_not=page.locator(".ember-sr-only"))
                    .first
                )
                back_link.click(timeout=8000, force=True)
            except Exception:
                page.goto(
                    "https://online.harleysvillebank.com/HarleysvilleBankOnline/uux.aspx#/landingPage",
                    timeout=30000,
                )

            page.wait_for_selector("text=ACCOUNTS", timeout=20000)
            page.wait_for_timeout(1500)

        print("\n🎉 All account downloads completed!")
        context.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to close...")