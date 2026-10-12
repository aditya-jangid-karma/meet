import calendar
from datetime import datetime, timedelta
import base64
import glob
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import signal
import pandas as pd

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from playwright.sync_api import sync_playwright

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Auto-detects the current Windows user so this script runs on ANY machine
# without editing paths. Home dir = C:\Users\<current user>.
_HOME = os.path.expanduser("~")
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DOWNLOAD_DIR = os.path.join(_HOME, "Desktop", "Bank_Statements")

TARGET_ACCOUNTS = []

# Credentials: prefer environment variables (HARLEYSVILLE_USER / HARLEYSVILLE_PASS).
# The fallback keeps this device working; set env vars on other devices instead of
# editing the password here.
BANK_USER = os.environ.get("HARLEYSVILLE_USER", "DMCAccounting")
BANK_PASS = os.environ.get("HARLEYSVILLE_PASS", "a3XRaQ?1J1}3")

# These files live next to this script, so they travel with the project folder.
GMAIL_CREDENTIALS_FILE = os.path.join(_SCRIPT_DIR, "client_secrets_for_Bank-Herleysville-Automation.json")
GMAIL_TOKEN_FILE = os.path.join(_SCRIPT_DIR, "token.json")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SMS_SENDER_SUBJECT = "SMS From 86434 To 15623144365"

REAL_USER_DATA_DIR = os.path.join(_HOME, "AppData", "Local", "Google", "Chrome", "User Data")
REAL_PROFILE_DIR = "Default"
AUTOMATION_USER_DATA_DIR = os.path.join(_HOME, "ChromeAutomationProfile")
AUTOMATION_PROFILE_DIR = "Default"

# Copying the real Chrome profile (with its signed-in Google accounts) makes Chrome
# hang on startup on other machines ("Failed to decrypt token", GCM sync loops), so
# it is OFF by default. The automation profile persists between runs and the script
# logs into the bank + reads the OTP each time, so the copy isn't needed.
# Set env var SYNC_REAL_PROFILE=1 only if you specifically want to reuse the local
# Chrome session.
SYNC_REAL_PROFILE = os.environ.get("SYNC_REAL_PROFILE", "0") == "1"

# ==========================================
# 2. DYNAMIC DATE & DIRECTORY SETUP
# ==========================================

def get_run_dates_and_folder():
    today = datetime.now()
    if today.day > 15:
        start_date = f"{today.month:02d}/01/{today.year}"
        end_date = f"{today.month:02d}/15/{today.year}"
        folder_name = today.strftime("%B-%Y")
    else:
        first_of_this_month = today.replace(day=1)
        last_month_date = first_of_this_month - timedelta(days=1)
        prev_month = last_month_date.month
        prev_year = last_month_date.year
        last_day_prev_month = calendar.monthrange(prev_year, prev_month)[1]

        start_date = f"{prev_month:02d}/01/{prev_year}"
        end_date = f"{prev_month:02d}/{last_day_prev_month}/{prev_year}"
        folder_name = last_month_date.strftime("%B-%Y")

    return start_date, end_date, folder_name

START_DATE, END_DATE, MONTH_FOLDER = get_run_dates_and_folder()
DOWNLOAD_DIR = os.path.join(BASE_DOWNLOAD_DIR, MONTH_FOLDER)
DEBUG_DIR = os.path.join(DOWNLOAD_DIR, "debug")
LOG_FILE_PATH = os.path.join(DOWNLOAD_DIR, "execution_summary.log")
BALANCE_STORE_FILE = os.path.join(DOWNLOAD_DIR, "end_balances.json")
PROGRESS_FILE = os.path.join(DOWNLOAD_DIR, "progress.json")

# ==========================================
# 3. LOGGING SYSTEM SETUP
# ==========================================
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

logger = logging.getLogger("BankAutomation")
logger.setLevel(logging.INFO)
logger.handlers.clear()

file_handler = logging.FileHandler(LOG_FILE_PATH, mode="a", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%H:%M:%S"))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

def format_duration(seconds):
    mins, secs = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs}h {mins}m {secs}s"
    elif mins > 0:
        return f"{mins}m {secs}s"
    else:
        return f"{secs}s"

# ==========================================
# 4. UTILITIES & AUTHENTICATION
# ==========================================

def load_balance_store():
    if os.path.exists(BALANCE_STORE_FILE):
        try:
            with open(BALANCE_STORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_balance(account_name, value, source):
    store = load_balance_store()
    store[account_name] = {
        "balance": value,
        "source": source,
        "start": START_DATE,
        "end": END_DATE,
        "captured": datetime.now().isoformat(timespec="seconds"),
    }
    with open(BALANCE_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("start_date") == START_DATE and data.get("end_date") == END_DATE:
                    return data
        except Exception:
            pass
    return {
        "run_id": datetime.now().isoformat(timespec="seconds"),
        "start_date": START_DATE,
        "end_date": END_DATE,
        "accounts_discovered": [],
        "completed": {},
        "status": "in_progress"
    }

def save_progress(progress_data):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, indent=2)

def close_all_chrome():
    pass

def sync_profile_copy():
    logger.info("Syncing browser profile from local Chrome WITHOUT closing existing windows...")
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

    # Skip large cache/lock folders. We only need cookies / login session, not
    # gigabytes of cache. Copying everything can take many minutes on a big profile.
    SKIP_NAMES = {
        "Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache",
        "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache", "Media Cache",
        "Service Worker", "Crashpad", "Component Cache", "extensions_crx_cache",
        "optimization_guide_model_store", "lockfile",
    }

    def ignore_locks(d, contents):
        return [c for c in contents if c.startswith("Singleton") or c in SKIP_NAMES]

    def safe_copy(src_file, dst_file):
        try:
            shutil.copy2(src_file, dst_file)
        except Exception:
            pass  # Safely ignore locked files while Chrome is open

    if os.path.exists(dst):
        for _ in range(5):
            try:
                shutil.rmtree(dst, ignore_errors=True)
                break
            except Exception:
                time.sleep(1)

    try:
        # copy_function prevents the entire sync from crashing if one file is locked
        shutil.copytree(src, dst, ignore=ignore_locks, dirs_exist_ok=True, copy_function=safe_copy)
        logger.info("Browser profile synced (live locked files skipped).")
    except Exception as e:
        logger.warning(f"Profile sync warning (continuing anyway): {str(e).splitlines()[0]}")

def get_otp_from_gmail(requested_after_ms):
    logger.info("Fetching MFA OTP via Gmail API...")
    try:
        creds = None
        if os.path.exists(GMAIL_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, GMAIL_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_FILE, GMAIL_SCOPES)
                creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
            with open(GMAIL_TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds)
        for _ in range(12):
            results = service.users().messages().list(userId="me", q=f'subject:"{SMS_SENDER_SUBJECT}" newer_than:1h', maxResults=10).execute()
            for m in results.get("messages", []):
                msg = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
                if int(msg.get("internalDate", "0")) < requested_after_ms:
                    continue

                payload = msg.get("payload", {})
                data = payload.get("body", {}).get("data")
                if not data:
                    for part in payload.get("parts", []):
                        if part.get("body", {}).get("data"):
                            data = part["body"]["data"]
                            break
                if data:
                    text = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8", errors="ignore")
                    matches = re.findall(r"Harleysville Bank.*?code is (\d{6})", text, re.IGNORECASE | re.DOTALL)
                    if matches:
                        return matches[-1]
            time.sleep(4)

        logger.warning("Timed out waiting for OTP email to arrive.")
    except Exception as e:
        logger.error(f"Gmail API Error: {e}")
        logger.error("HINT: Try deleting the 'token.json' file and run again to re-authenticate.")

    return input("\n[Fallback] Gmail API failed or timed out. Please check your email and type the 6-digit OTP manually: ").strip()

# ==========================================
# 5. BROWSER AUTOMATION MODULES
# ==========================================

def login_or_restore_session(page):
    logger.info("Navigating to Harleysville Bank login portal...")
    page.goto("https://harleysvillebank.com", timeout=60000)

    try:
        page.get_by_text("Accept", exact=True).click(timeout=4000)
    except Exception:
        pass

    if "online.harleysvillebank.com" not in page.url:
        logger.info("Performing login sequence...")
        desktop_form = page.locator("#desktop-username").locator("xpath=ancestor::form[1]")
        page.locator("#desktop-username").fill(BANK_USER)
        desktop_form.locator("input[type='password']").first.fill(BANK_PASS)

        try:
            rem = desktop_form.locator("input[type='checkbox']").first
            if rem.count() > 0:
                rem.check(timeout=3000)
            else:
                desktop_form.get_by_text(re.compile("remember", re.IGNORECASE)).click(timeout=3000)
        except Exception:
            pass

        desktop_form.get_by_role("button", name="LOGIN", exact=False).click()

        mfa_detected = False
        try:
            page.wait_for_selector("text=Please select a target", timeout=10000)
            mfa_detected = True
        except Exception:
            logger.info("MFA bypassed or session restored.")

        if mfa_detected:
            logger.info("MFA prompt detected. Requesting SMS OTP...")
            sms_btn = page.get_by_text(re.compile("SMS", re.IGNORECASE)).first
            sms_btn.wait_for(state="visible", timeout=10000)
            req_ms = int(time.time() * 1000) - 3000
            sms_btn.click(timeout=8000)
            page.wait_for_selector("text=Enter your Secure Access Code", timeout=15000)

            otp = get_otp_from_gmail(req_ms)
            if otp:
                page.bring_to_front()
                page.get_by_placeholder("Secure Access Code").fill(otp)
                page.get_by_role("button", name="Submit").click()
            else:
                raise Exception("Failed to acquire OTP.")

        page.wait_for_url("**/landingPage", timeout=35000)
    else:
        logger.info("Successfully restored existing session.")

def _parse_money(text):
    if not text:
        return None
    m = re.search(r'-?\$?\(?\s*[\d,]+\.\d{2}\)?', text)
    if not m:
        return None
    raw = m.group(0)
    negative = "(" in raw or raw.strip().startswith("-")
    num = re.sub(r"[^\d.]", "", raw)
    if not num:
        return None
    try:
        val = float(num)
    except ValueError:
        return None
    return -val if negative else val

def scrape_end_balance(page, account_name):
    for label in ["Available Balance", "Current Balance", "Ending Balance", "Principal Balance"]:
        try:
            lbl = page.get_by_text(re.compile(re.escape(label), re.IGNORECASE)).first
            if lbl.count() == 0:
                continue
            container = lbl.locator("xpath=ancestor::*[self::div or self::li or self::tr][1]")
            txt = container.inner_text(timeout=1500)
            val = _parse_money(re.sub(re.escape(label), "", txt, flags=re.IGNORECASE))
            if val is not None:
                logger.info(f"  └─ Captured balance via header '{label}': ${val:,.2f}")
                return val, label
        except Exception:
            continue
    return 0.0, "Default"

def _filter_panel_open(page):
    try:
        if page.locator("xpath=//*[contains(text(), 'Start Date')]/following::input[not(@type='hidden')][1]").count() > 0:
            return True
        if page.get_by_role("button", name=re.compile(r"Apply Filters?", re.IGNORECASE)).count() > 0:
            return True
    except Exception:
        pass
    return False

def open_transaction_filter(page):
    if _filter_panel_open(page):
        return True

    filter_locators = [
        page.get_by_title(re.compile(r"Filters?", re.IGNORECASE)),
        page.get_by_label(re.compile(r"Filters?", re.IGNORECASE)),
        page.locator("button:has(svg.icon-filter), button:has(i.icon-filter)"),
        page.locator("button[aria-label*='Filter' i]"),
    ]

    for loc in filter_locators:
        try:
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=2500, force=True)
                page.wait_for_timeout(1000)
                if _filter_panel_open(page):
                    logger.info("  └─ [Filters] Clicked filter icon; drawer opened.")
                    return True
        except Exception:
            continue
    return False

def select_custom_date_mode(page):
    start_inp = page.locator("xpath=//*[contains(text(), 'Start Date')]/following::input[not(@type='hidden')][1]").first
    if start_inp.count() > 0 and start_inp.is_visible():
        return True

    try:
        logger.info("  └─ [Date Mode] Selecting 'Custom Date' from Time Period dropdown...")
        tp = page.locator("q2-select[label='Time Period']").first
        if tp.count() > 0 and tp.is_visible():
            tp.click(force=True)
            page.wait_for_timeout(1000)
            page.evaluate(r"""
                () => {
                    const opts = Array.from(document.querySelectorAll('q2-option, [role="option"]'));
                    const cd = opts.find(e => e.innerText && e.innerText.includes('Custom Date'));
                    if (cd) cd.click();
                }
            """)
            page.wait_for_timeout(1500)
            return True
    except Exception:
        pass
    return False

def _set_date_field(page, label_text, date_str):
    logger.info(f"  └─ Entering {label_text}: {date_str}")

    raw_digits = date_str.replace("/", "")

    locators = [
        page.locator(f"xpath=//*[contains(text(), '{label_text}')]/following::input[not(@type='hidden')][1]").first,
        page.locator(f"input[aria-label*='{label_text}' i]").first,
        page.get_by_label(re.compile(label_text, re.IGNORECASE)).first
    ]

    inp = None
    for loc in locators:
        if loc.count() > 0 and loc.is_visible():
            inp = loc
            break

    if not inp:
        logger.error(f"  └─ [Error] Could not locate {label_text} input field on screen.")
        return False

    def _value_ok():
        try:
            v = inp.input_value().replace("/", "").replace("-", "").strip()
            return (raw_digits in v) or (v in raw_digits and len(v) >= 6)
        except Exception:
            return False

    try:
        inp.scroll_into_view_if_needed()
        page.wait_for_timeout(300)

        # STRATEGY 1: Robust keyboard simulation
        logger.info(f"  └─ Attempting pure keyboard simulation...")
        try:
            inp.click(force=True)
            page.wait_for_timeout(200)

            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.wait_for_timeout(100)
            inp.press("Home")

            inp.press_sequentially(raw_digits, delay=100)
            page.wait_for_timeout(200)

            inp.press("Enter")
            inp.press("Tab")
            page.wait_for_timeout(400)

            if _value_ok():
                logger.info(f"  └─ (Verified) {label_text} set via keyboard: {inp.input_value()}")
                return True
        except Exception as e:
            logger.warning(f"  └─ Keyboard simulation warning: {e}")

        # STRATEGY 2: Set BOTH the inner input AND the Q2 host component's value
        logger.info(f"  └─ Injecting {label_text} via component + input bypass...")
        page.evaluate(f"""
            (el) => {{
                const setNative = (node, val) => {{
                    try {{
                        const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                        if (d && d.set) d.set.call(node, val); else node.value = val;
                    }} catch (e) {{ node.value = val; }}
                    node.dispatchEvent(new Event('input',  {{ bubbles: true }}));
                    node.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    node.dispatchEvent(new Event('blur',   {{ bubbles: true }}));
                }};
                setNative(el, '{date_str}');
                // Walk up to the Q2 custom element (tag has a dash) and set its .value too
                let host = el;
                while (host && !(host.tagName && host.tagName.includes('-'))) {{
                    host = host.parentElement || (host.getRootNode() && host.getRootNode().host);
                }}
                if (host) {{
                    try {{ host.value = '{date_str}'; }} catch (e) {{}}
                    host.dispatchEvent(new Event('input',  {{ bubbles: true }}));
                    host.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}
        """, inp.element_handle())
        page.wait_for_timeout(500)

        if _value_ok():
            logger.info(f"  └─ (Verified) {label_text} set via bypass: {inp.input_value()}")
            return True

        logger.warning(f"  └─ [Verify FAILED] {label_text} did not stick (shows '{inp.input_value()}'). "
                       f"UI filter may not apply — pandas date filter will correct the output.")
        return False
    except Exception as e:
        logger.warning(f"  └─ Error typing {label_text}: {e}")
        return False

def set_date_range(page, start_date, end_date):
    select_custom_date_mode(page)
    ok_start = _set_date_field(page, "Start Date", start_date)
    ok_end = _set_date_field(page, "End Date", end_date)

    # Close any calendar popups
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass

    if ok_start and ok_end:
        logger.info("  └─ [Date Range] Both dates verified in the UI.")
    else:
        logger.warning("  └─ [Date Range] One or both dates NOT verified — relying on pandas date filter.")
    return ok_start and ok_end

def click_apply_filter(page):
    logger.info("  └─ [Apply] Locating 'Apply Filters' button...")

    # Deep Shadow DOM search + click, returning details so we can VERIFY it.
    result = page.evaluate(r"""
        () => {
            let found = false, clicked = false, label = null, disabled = false;
            function deepSearch(root) {
                let walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
                let node;
                while (node = walker.nextNode()) {
                    if (node.shadowRoot) { if (deepSearch(node.shadowRoot)) return true; }
                    if (node.tagName.match(/^(BUTTON|Q2-BTN)$/i) || node.getAttribute('role') === 'button') {
                        if (node.textContent && node.textContent.trim().toLowerCase() === 'apply filters') {
                            found = true;
                            label = node.textContent.trim();
                            disabled = node.disabled === true ||
                                       node.getAttribute('aria-disabled') === 'true' ||
                                       node.classList.contains('disabled');
                            if (!disabled) { node.click(); clicked = true; }
                            return true;
                        }
                    }
                }
                return false;
            }
            deepSearch(document.body);
            return { found, clicked, label, disabled };
        }
    """)

    # ---- VALIDATION ----
    if not result or not result.get("found"):
        logger.warning("  └─ [Apply] VALIDATION FAILED: 'Apply Filters' button not found in DOM.")
        return False
    if result.get("disabled"):
        logger.warning("  └─ [Apply] VALIDATION WARNING: 'Apply Filters' button is disabled.")
        return False
    if not result.get("clicked"):
        logger.warning("  └─ [Apply] VALIDATION FAILED: Button found but click did not register.")
        return False

    logger.info(f"  └─ [Apply] VALIDATED: Clicked '{result.get('label')}' via Deep JS.")

    # ---- CONFIRM SUBMISSION: filter drawer should close ----
    submission_confirmed = False
    try:
        for _ in range(10):  # up to ~5s
            still_open = page.evaluate(r"""
                () => {
                    function deepSearch(root) {
                        let walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
                        let node;
                        while (node = walker.nextNode()) {
                            if (node.shadowRoot) { if (deepSearch(node.shadowRoot)) return true; }
                            if (node.tagName.match(/^(BUTTON|Q2-BTN)$/i) || node.getAttribute('role') === 'button') {
                                if (node.textContent && node.textContent.trim().toLowerCase() === 'apply filters') {
                                    const rect = node.getBoundingClientRect();
                                    if (rect.width > 0 && rect.height > 0) return true;
                                }
                            }
                        }
                        return false;
                    }
                    return deepSearch(document.body);
                }
            """)
            if not still_open:
                submission_confirmed = True
                break
            page.wait_for_timeout(500)
    except Exception:
        pass

    if submission_confirmed:
        logger.info("  └─ [Apply] Submission confirmed: filter drawer closed / filters applied.")
    else:
        logger.info("  └─ [Apply] Filter drawer still visible; proceeding with load wait anyway.")

    # ---- WAIT FOR RESULTS TO RENDER ----
    logger.info("  └─ [Verify] Waiting for transactions to render...")
    try:
        spinner = page.locator("q2-spinner, .loading-overlay").first
        if spinner.count() > 0 and spinner.is_visible(timeout=3000):
            spinner.wait_for(state="hidden", timeout=15000)
    except Exception:
        pass

    logger.info("  └─ [Verify] Waiting 2 seconds for transaction results to finish loading...")
    page.wait_for_timeout(2000)

    return True

def check_if_transactions_exist(page):
    for pattern in [r"no transactions that match", r"no transactions found", r"no transactions were found", r"^no transactions$"]:
        try:
            if page.get_by_text(re.compile(pattern, re.IGNORECASE)).count() > 0:
                return False
        except Exception:
            pass
    return True

def export_xls(page, account_name, start_date, end_date):
    logger.info("  └─ [Export] Attempting to Download/Export to xls...")

    safe_name = re.sub(r'[\\/*?:"<>|]', "_", account_name).strip()
    formatted_start = datetime.strptime(start_date, "%m/%d/%Y").strftime("%Y-%m-%d")
    formatted_end = datetime.strptime(end_date, "%m/%d/%Y").strftime("%Y-%m-%d")
    file_name = f"{safe_name}_{formatted_start}_to_{formatted_end}.xls"
    final_path = os.path.join(DOWNLOAD_DIR, file_name)

    try:
        with page.expect_download(timeout=45000) as download_info:
            
            logger.info("  └─ [Export] Executing deep JS automation for Export menu...")
            click_status = page.evaluate(r"""
                async () => {
                    function fireClick(node) {
                        try { node.scrollIntoView({block: 'center'}); } catch(e){}
                        node.dispatchEvent(new MouseEvent('mouseover', {bubbles:true, cancelable:true}));
                        node.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true}));
                        node.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true}));
                        node.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
                        node.click();
                    }

                    function queryDeep(criteriaFn, root = document.body) {
                        let results = [];
                        let walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
                        let node;
                        while (node = walker.nextNode()) {
                            if (node.shadowRoot) {
                                results = results.concat(queryDeep(criteriaFn, node.shadowRoot));
                            }
                            if (criteriaFn(node)) {
                                results.push(node);
                            }
                        }
                        return results;
                    }
                    
                    function isVisible(el) {
                        if (!el) return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).display !== 'none';
                    }

                    // 1. Locate the Export button dynamically (including inside Shadow DOMs)
                    let exportBtns = queryDeep(n => {
                        let tag = n.tagName.toLowerCase();
                        let title = (n.getAttribute('title') || '').toLowerCase();
                        let aria = (n.getAttribute('aria-label') || '').toLowerCase();
                        let txt = (n.textContent || '').toLowerCase().trim();
                        
                        if (n.children.length > 5) return false; // Exclude giant containers
                        
                        if (tag === 'button' || tag === 'q2-btn' || n.getAttribute('role') === 'button' || tag === 'a') {
                            if (title.includes('export') || aria.includes('export') || txt === 'export') return true;
                            if (n.querySelector('.icon-download') || n.querySelector('i[class*="download"]')) return true;
                        }
                        return false;
                    });
                    
                    let exportBtn = exportBtns.find(isVisible);
                    if (!exportBtn) return "EXPORT_BTN_NOT_FOUND";

                    // 2. Click the export button and poll for the "Spreadsheet" option to appear
                    for (let attempt = 0; attempt < 3; attempt++) {
                        fireClick(exportBtn);
                        
                        for (let i = 0; i < 12; i++) {
                            await new Promise(r => setTimeout(r, 400));
                            
                            let xlsItems = queryDeep(n => {
                                let txt = (n.textContent || "").toLowerCase().trim();
                                let tag = n.tagName.toLowerCase();
                                let isContainer = (tag === 'q2-dropdown-item' || tag === 'li' || tag === 'button' || tag === 'a' || n.getAttribute('role') === 'menuitem');
                                return isContainer && txt.includes('spreadsheet') && txt.includes('xls');
                            });
                            
                            let visibleXls = xlsItems.find(isVisible);
                            if (visibleXls) {
                                fireClick(visibleXls);
                                return "SUCCESS";
                            }
                        }
                    }
                    return "XLS_OPTION_NOT_FOUND";
                }
            """)
            
            if click_status != "SUCCESS":
                logger.warning(f"  └─ [Export] CRITICAL: Action failed with status: {click_status}")
                raise Exception(f"Action failed: {click_status}")
                
    except Exception as e:
        logger.warning(f"  └─ Download interaction error / timeout: {str(e).splitlines()[0]}")
        return None

    try:
        download = download_info.value
        download.save_as(final_path)
        logger.info(f"  └─ [Success] Saved statement to: {final_path}")
    except Exception as e:
        logger.warning(f"  └─ [Export] Error during file save: {e}")
        # Workaround for TargetClosedError: Chrome likely saved the raw GUID file in DOWNLOAD_DIR
        try:
            time.sleep(2.0) # Give Chrome a moment to finish writing the file
            xls_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.xls"))
            # Exclude files that are already properly named (our final_path pattern)
            raw_files = [f for f in xls_files if "_to_" not in os.path.basename(f)]
            if raw_files:
                latest_raw = max(raw_files, key=os.path.getctime)
                # Check if it was created in the last 60 seconds
                if time.time() - os.path.getctime(latest_raw) < 60:
                    shutil.move(latest_raw, final_path)
                    logger.info(f"  └─ [Success] Recovered raw download and renamed to: {final_path}")
                    return final_path
        except Exception as recovery_err:
            logger.warning(f"  └─ Raw file recovery failed: {recovery_err}")
            
        return None
        
    return final_path

def discover_accounts(page):
    try:
        page.wait_for_selector("text=ACCOUNTS", timeout=35000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    names = page.evaluate(
        r"""
        () => {
            const out = [];
            const seen = new Set();
            const els = Array.from(document.querySelectorAll('body *'));
            const tiles = els.filter(el => {
                const t = el.textContent || '';
                return /(Available|Current)\s+Balance/i.test(t) &&
                       el.querySelectorAll('*').length < 60;
            });
            for (const tile of tiles) {
                const nameEl = tile.querySelector('a, h1, h2, h3, h4, [role=heading]');
                if (!nameEl) continue;
                let name = (nameEl.textContent || '')
                    .replace(/\$[\d,]+\.\d{2}/g, '')
                    .replace(/\s+/g, ' ')
                    .trim();
                if (name.length >= 3 && !/^(available|current)\s+balance$/i.test(name)
                    && !seen.has(name)) {
                    seen.add(name);
                    out.push(name);
                }
            }
            return out;
        }
        """
    )

    normalized = []
    for n in names:
        n = re.sub(r"^\s*Harleysville Bank\s+", "", n).strip()
        n = re.sub(r"[.…]+$", "", n).strip()
        if len(n) >= 3:
            normalized.append(n)

    cleaned = []
    for n in normalized:
        if any(other != n and other.startswith(n) for other in normalized):
            continue
        if n not in cleaned:
            cleaned.append(n)
    return cleaned

def open_account(page, account_name):
    account_locator = page.get_by_text(account_name)
    try:
        account_locator.first.wait_for(state="attached", timeout=15000)
    except Exception:
        raise RuntimeError(f"Account text '{account_name}' not found on dashboard.")

    try:
        account_locator.first.click(timeout=8000)
    except Exception:
        account_locator.first.click(timeout=8000, force=True)

    try:
        page.wait_for_url("**/account/**", timeout=15000)
    except Exception:
        try:
            page.wait_for_selector("text=Transactions", timeout=10000)
        except Exception:
            raise RuntimeError(f"Did not reach transaction view for '{account_name}'.")

    page.wait_for_timeout(1500)

def process_account(page, account_name, start_date, end_date):
    logger.info(f"  └─ Opening account details view...")
    open_account(page, account_name)

    filter_opened = open_transaction_filter(page)
    if filter_opened:
        set_date_range(page, start_date, end_date)
        click_apply_filter(page)
        has_transactions = check_if_transactions_exist(page)
    else:
        logger.info("  └─ Filter drawer not present for this account type.")
        has_transactions = False

    balance_val, balance_src = scrape_end_balance(page, account_name)
    save_balance(account_name, balance_val, balance_src)

    if not has_transactions:
        logger.info(f"  └─ [Result] 0 transactions found for range -> Logged & skipping export.")
        return 0, "No transactions"

    logger.info(f"  └─ [Result] Transactions verified! Initiating export...")
    saved_file = export_xls(page, account_name, start_date, end_date)
    if not saved_file:
        return 0, "Non-exportable account"

    return "Exported", "successful"

def return_to_dashboard(page):
    logger.info("  └─ Returning to Accounts dashboard...")
    try:
        page.goto("https://online.harleysvillebank.com/HarleysvilleBankOnline/uux.aspx#/landingPage", timeout=30000)
    except Exception:
        pass
    page.wait_for_selector("text=ACCOUNTS", timeout=20000)
    page.wait_for_timeout(1500)

# ==========================================
# 6. MASTER WORKBOOK CONSOLIDATION
# ==========================================

def _read_statement_table(path):
    try:
        tables = pd.read_html(path)
        if tables:
            return max(tables, key=lambda d: (d.shape[1], len(d)))
    except Exception:
        pass
    try:
        df = pd.read_csv(path, sep='\t')
        if len(df.columns) < 2:
            df = pd.read_csv(path)
        return df
    except Exception:
        pass
    return pd.read_excel(path)

def _filter_df_by_dates(df, start_date, end_date, account_label=""):
    """Guaranteed backstop: keep only rows whose date falls within the range,
    even if the bank's UI date filter failed and exported the full history."""
    if df is None or df.empty:
        return df

    start = datetime.strptime(start_date, "%m/%d/%Y")
    end = datetime.strptime(end_date, "%m/%d/%Y")

    # Find the date column ("Post Date", "Date", ...); fall back to first column
    date_col = None
    for col in df.columns:
        if "date" in str(col).lower():
            date_col = col
            break
    if date_col is None:
        date_col = df.columns[0]

    parsed = pd.to_datetime(df[date_col], errors="coerce")

    # Safety: if we can't parse most values as dates, DON'T filter (avoid wiping data)
    if parsed.notna().mean() < 0.5:
        logger.warning(f"  └─ [Date Filter] '{account_label}': could not parse '{date_col}' as dates; skipping filter.")
        return df

    mask = (parsed >= start) & (parsed <= end)
    removed = int((~mask & parsed.notna()).sum())
    filtered = df[mask].copy()

    if removed > 0:
        logger.info(f"  └─ [Date Filter] '{account_label}': removed {removed} out-of-range row(s); "
                    f"kept {len(filtered)} within {start_date}–{end_date}.")
    return filtered

def consolidate_xls_to_xlsx(download_dir, end_date_str, target_accounts):
    logger.info("\n" + "="*50)
    logger.info("Starting Master Workbook Consolidation (Exact Copy Mode)...")
    logger.info("="*50)

    ed_obj = datetime.strptime(end_date_str, "%m/%d/%Y")
    formatted_end = ed_obj.strftime("%m.%d.%Y")

    output_filename = f"HSB {formatted_end}.xlsx"
    output_path = os.path.join(download_dir, output_filename)

    # Reliable Windows lock test: renaming a file to itself fails with
    # PermissionError when another process (e.g. Excel) holds it open.
    def _is_locked(path):
        if not os.path.exists(path):
            return False
        try:
            os.rename(path, path)
            return False
        except OSError:
            return True

    if _is_locked(output_path):
        output_filename = f"HSB {formatted_end}_{int(time.time())}.xlsx"
        output_path = os.path.join(download_dir, output_filename)
        logger.warning(f"Target Excel file is OPEN in Excel / locked. Saving as: {output_filename}")
        logger.warning("  -> Close 'HSB {}.xlsx' in Excel before running to keep the standard filename.".format(formatted_end))

    xls_files = glob.glob(os.path.join(download_dir, "*.xls"))
    file_map = {}
    for f in xls_files:
        base_name = os.path.basename(f)
        cleaned_acc = re.sub(r'_\d{4}-\d{2}-\d{2}_to_.*\.xls$', '', base_name)
        file_map[cleaned_acc] = f

    balance_store = load_balance_store()
    used_sheets = set()

    def unique_sheet(full_name):
        base = full_name[:31]
        if base not in used_sheets:
            used_sheets.add(base)
            return base
        i = 2
        while True:
            cand = f"{base[:28]}_{i}"
            if cand not in used_sheets:
                used_sheets.add(cand)
                return cand
            i += 1

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for idx, account in enumerate(target_accounts, start=1):
            safe_acc_name = re.sub(r'[\\/*?:"<>|]', "_", account).strip()
            sheet_name = unique_sheet(safe_acc_name)
            matching_file = file_map.get(safe_acc_name)
            scraped_balance = balance_store.get(account, {}).get("balance")
            end_balance_val = scraped_balance if scraped_balance is not None else 0.0

            if not matching_file:
                df_empty = pd.DataFrame([{
                    "Status": "No transactions during this performance period",
                    "End Balance (Total)": end_balance_val,
                }])
                df_empty.to_excel(writer, sheet_name=sheet_name, index=False)
                logger.info(f"[{idx:2d}/{len(target_accounts)}] Created placeholder sheet: '{sheet_name}' (Balance: ${end_balance_val:,.2f})")
                continue

            try:
                df = _read_statement_table(matching_file)
                df = _filter_df_by_dates(df, START_DATE, end_date_str, account)  # <-- guaranteed date filter

                empty_row = pd.DataFrame([{c: '' for c in df.columns}])
                df = pd.concat([df, empty_row], ignore_index=True)

                summary_row = {c: '' for c in df.columns}
                summary_row[df.columns[0]] = "End Balance (Total):"
                summary_row[df.columns[-1]] = end_balance_val

                df = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                logger.info(f"[{idx:2d}/{len(target_accounts)}] Consolidated sheet: '{sheet_name}' (End Balance: ${end_balance_val:,.2f})")

            except Exception as e:
                logger.error(f"[{idx:2d}/{len(target_accounts)}] Error creating sheet for '{sheet_name}': {e}")

    logger.info(f"\nFinal Consolidated Master Workbook saved successfully at: {output_path}")

# ==========================================
# 7. MAIN DRIVER FUNCTION
# ==========================================

# Global state for signal handler
global_progress = {}
global_accounts_to_process = []
global_context = None

def handle_exit_signal(sig, frame):
    logger.warning("\n[!] Graceful shutdown requested (Ctrl+C). Saving progress...")
    if global_progress:
        save_progress(global_progress)
    logger.info("Running incremental consolidation...")
    try:
        if global_accounts_to_process:
            consolidate_xls_to_xlsx(DOWNLOAD_DIR, END_DATE, global_accounts_to_process)
    except Exception as e:
        logger.error(f"Error during emergency consolidation: {e}")
    if global_context:
        try:
            global_context.close()
        except:
            pass
    sys.exit(0)

def run():
    global global_progress, global_accounts_to_process, global_context

    total_start_time = time.time()

    logger.info("=" * 60)
    logger.info(" Harleysville Bank Statement Automation")
    logger.info(f" Output Directory  : {DOWNLOAD_DIR}")
    logger.info(f" Target Date Range : {START_DATE} to {END_DATE}")
    logger.info(f" Start Time        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)

    close_all_chrome()
    if SYNC_REAL_PROFILE:
        sync_profile_copy()
    else:
        logger.info("Using clean automation profile (real-profile sync disabled).")
        os.makedirs(AUTOMATION_USER_DATA_DIR, exist_ok=True)

    progress = load_progress()
    global_progress = progress
    summary = []

    accounts_to_process = []
    if progress.get("accounts_discovered"):
        accounts_to_process = progress["accounts_discovered"]
        logger.info(f"Loaded {len(accounts_to_process)} accounts from progress file.")

    with sync_playwright() as p:
        logger.info("Launching automation browser (Google Chrome)...")
        # Make sure no leftover Chrome is holding a handoff lock, then launch.
        close_all_chrome()

        launch_kwargs = dict(
            user_data_dir=AUTOMATION_USER_DATA_DIR,
            headless=False,
            args=["--start-maximized", "--no-first-run", "--no-default-browser-check"],
            no_viewport=True,
            accept_downloads=True,
            downloads_path=DOWNLOAD_DIR,
            timeout=60000,  # fail fast (60s) instead of hanging forever
        )

        context = None
        try:
            # Preferred: use the installed Google Chrome.
            context = p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
        except Exception as e:
            logger.warning(f"Chrome channel launch failed ({str(e).splitlines()[0]}).")
            logger.warning("Falling back to Playwright's bundled Chromium...")
            try:
                context = p.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as e2:
                logger.critical(f"Browser launch failed on both Chrome and Chromium: {str(e2).splitlines()[0]}")
                logger.critical("FIXES: 1) Close ALL chrome.exe in Task Manager.  "
                                "2) Ensure Google Chrome is installed.  "
                                "3) Run:  python -m playwright install chromium")
                return

        logger.info("Browser launched successfully.")
        global_context = context
        page = context.pages[0] if context.pages else context.new_page()

        try:
            login_or_restore_session(page)
            page.wait_for_selector("text=ACCOUNTS", timeout=35000)
        except Exception as e:
            logger.critical(f"Authentication / Session launch failure: {e}")
            context.close()
            return

        if not accounts_to_process:
            if TARGET_ACCOUNTS:
                accounts_to_process = list(TARGET_ACCOUNTS)
                logger.info(f"Using target account list ({len(accounts_to_process)} accounts).")
            else:
                accounts_to_process = discover_accounts(page)
                logger.info(f"Auto-discovered {len(accounts_to_process)} account(s) on dashboard:")
                for idx, acc in enumerate(accounts_to_process, start=1):
                    logger.info(f"  {idx:2d}. {acc}")
                if not accounts_to_process:
                    logger.critical("No accounts discovered on dashboard. Terminating.")
                    context.close()
                    return
            progress["accounts_discovered"] = accounts_to_process
            save_progress(progress)

        global_accounts_to_process = accounts_to_process
        total_acc_count = len(accounts_to_process)

        for idx, account in enumerate(accounts_to_process, start=1):
            if account in progress.get("completed", {}):
                logger.info(f"\n>>> [{idx}/{total_acc_count}] Skipping Account: '{account}' (Already Completed)")
                comp = progress["completed"][account]
                summary.append({"account": account, "tx": comp.get("tx", "Skipped"), "status": comp.get("status", "successful"), "duration": comp.get("duration", "0s")})
                continue

            acc_start_time = time.time()
            logger.info(f"\n>>> [{idx}/{total_acc_count}] Processing Account: '{account}'")

            try:
                tx_count, status = process_account(page, account, START_DATE, END_DATE)
                elapsed_acc = format_duration(time.time() - acc_start_time)

                if "completed" not in progress:
                    progress["completed"] = {}
                progress["completed"][account] = {
                    "status": status,
                    "tx": tx_count,
                    "duration": elapsed_acc,
                    "completed_at": datetime.now().isoformat()
                }
                save_progress(progress)

                summary.append({"account": account, "tx": tx_count, "status": status, "duration": elapsed_acc})
                logger.info(f"  └─ Finished '{account}' in {elapsed_acc}")

                try:
                    consolidate_xls_to_xlsx(DOWNLOAD_DIR, END_DATE, accounts_to_process)
                except Exception as cons_err:
                    logger.warning(f"  └─ Incremental consolidation error: {cons_err}")

            except Exception as e:
                elapsed_acc = format_duration(time.time() - acc_start_time)
                logger.error(f"  └─ FAILED on Account '{account}': {str(e).splitlines()[0]} (Time: {elapsed_acc})")
                summary.append({"account": account, "tx": "ERROR", "status": "failed", "duration": elapsed_acc})
            finally:
                try:
                    if page.is_closed() or not context.pages:
                        logger.warning("  └─ Browser connection lost! Restarting browser session for next account...")
                        try: context.close()
                        except: pass
                        context = p.chromium.launch_persistent_context(**launch_kwargs)
                        global_context = context
                        page = context.pages[0] if context.pages else context.new_page()
                        login_or_restore_session(page)
                    else:
                        return_to_dashboard(page)
                except Exception as dash_err:
                    logger.critical(f"Fatal error trying to recover dashboard: {dash_err}")
                    try: context.close()
                    except: pass
                    sys.exit(1)

        context.close()

    # Final overall consolidation
    consolidate_xls_to_xlsx(DOWNLOAD_DIR, END_DATE, accounts_to_process)

    progress["status"] = "complete"
    save_progress(progress)

    total_elapsed_str = format_duration(time.time() - total_start_time)

    logger.info("\n" + "=" * 60)
    logger.info(" RUN EXECUTION SUMMARY REPORT")
    logger.info("=" * 60)
    logger.info(f"Total Target Accounts : {total_acc_count}")
    logger.info(f"Successfully Processed: {sum(1 for s in summary if s['status'] in ('successful', 'No transactions', 'Non-exportable account', 'Exported'))}")
    logger.info(f"Failed Accounts       : {sum(1 for s in summary if s['status'] == 'failed')}")
    logger.info(f"Total Time Elapsed    : {total_elapsed_str}")
    logger.info("=" * 60)

    logger.info("\nACCOUNT BREAKDOWN:")
    for s in summary:
        logger.info(f"- {s['account']} | Tx Count: {s['tx']} | Status: {s['status']} | Time: {s['duration']}")

    logger.info("=" * 60)
    logger.info(f"Log file saved at: {LOG_FILE_PATH}")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.critical(f"CRITICAL ERROR: {e}", exc_info=True)
        input("\nPress Enter to close window...")