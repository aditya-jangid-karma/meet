import os
import time
import json
import shutil
import calendar
import subprocess
import openpyxl
import pandas as pd
from datetime import date, timedelta, datetime
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
BASE_DIR = r"C:\Users\Meet Patel\Desktop\automation\hellogm"

PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")
os.makedirs(BASE_DIR, exist_ok=True)

# --- LOGIN CREDENTIALS (used only if the login page appears) ---
OTELIER_EMAIL = "bookkeeping@tortoiseig.com"
OTELIER_PASSWORD = "#X1BIB=iq&=F"

HOTELS = [
    "Country Inn & Suites Huntersville",
    "Extended Stay America - Columbia - West - Stoneridge Dr",
    "Motel 6 Greenville SC I-85",
    "Studio 6 Greenville SC I-85",
    "Suburban Spartanburg",
    "Wingate Concord Charlotte Area"
]

_HOME = os.path.expanduser("~")
REAL_USER_DATA_DIR = os.path.join(_HOME, "AppData", "Local", "Google", "Chrome", "User Data")
REAL_PROFILE_DIR = "Default"
AUTOMATION_USER_DATA_DIR = os.path.join(_HOME, "ChromeAutomationProfile")
AUTOMATION_PROFILE_DIR = "Default"

# ==============================================================================
# STYLING CONSTANTS (EXACT OTELIER EXCEL LOOK)
# ==============================================================================
HEADER_FILL = PatternFill(start_color="8EA9DB", end_color="8EA9DB", fill_type="solid")  # Steel Blue
YELLOW_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")  # Yellow Highlight for Non-comment rows
HEADER_FONT = Font(name="Aptos Narrow", size=11, bold=True, color="000000")
DATA_FONT = Font(name="Aptos Narrow", size=11, color="000000")
THIN_BORDER = Border(
    left=Side(style="thin", color="000000"),
    right=Side(style="thin", color="000000"),
    top=Side(style="thin", color="000000"),
    bottom=Side(style="thin", color="000000")
)
DASH_VALUES = {"-", "–", "—", ""}

# ==============================================================================
# TIME FORMATTING HELPER
# ==============================================================================
def format_duration(seconds: float) -> str:
    """Formats elapsed seconds into a clean, human-readable string (e.g. 2m 14.5s)."""
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{int(hours)}h {int(mins)}m {secs:.1f}s"
    elif mins > 0:
        return f"{int(mins)}m {secs:.1f}s"
    else:
        return f"{secs:.2f}s"

# ==============================================================================
# PROGRESS TRACKING & RESUME MANAGEMENT
# ==============================================================================
def load_progress():
    """Loads the progress tracking JSON file if it exists."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[PROGRESS WARNING] Could not read {PROGRESS_FILE} ({e}). Starting fresh tracker.")
    return {"completed_tasks": {}, "completed_hotels": {}, "all_completed": False}

def save_progress(progress_data):
    """Saves the progress tracking data atomically to progress.json."""
    try:
        temp_file = PROGRESS_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(progress_data, f, indent=4)
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
        os.rename(temp_file, PROGRESS_FILE)
    except Exception as e:
        print(f"[PROGRESS ERROR] Failed to save progress.json: {e}")

def get_task_key(hotel: str, month_name: str) -> str:
    return f"{hotel}::{month_name}"

def is_month_completed(progress_data, hotel: str, month_name: str, expected_file_path: str) -> bool:
    """Checks if a month task is recorded as COMPLETED and the file actually exists on disk."""
    task_key = get_task_key(hotel, month_name)
    task_info = progress_data.get("completed_tasks", {}).get(task_key)
    if task_info and task_info.get("status") == "COMPLETED":
        saved_path = task_info.get("file_path", expected_file_path)
        if os.path.exists(saved_path) and os.path.getsize(saved_path) > 0:
            return True
    return False

def mark_month_completed(progress_data, hotel: str, month_name: str, file_path: str, sheet_stats: dict):
    task_key = get_task_key(hotel, month_name)
    progress_data.setdefault("completed_tasks", {})[task_key] = {
        "status": "COMPLETED",
        "hotel": hotel,
        "month": month_name,
        "file_path": file_path,
        "sheet_stats": sheet_stats,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_progress(progress_data)

def mark_hotel_completed(progress_data, hotel: str, combined_file_path: str, sheet_counts: dict):
    progress_data.setdefault("completed_hotels", {})[hotel] = {
        "status": "COMPLETED",
        "combined_file_path": combined_file_path,
        "sheet_counts": sheet_counts,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_progress(progress_data)

# ==============================================================================
# UI SYNCHRONIZATION & DATA WAIT HELPERS
# ==============================================================================
def wait_for_data_load(page, stage_description="data", extra_wait_sec=5):
    """
    Ensures network requests have settled, loading spinners have disappeared,
    and the UI has fully populated before proceeding.
    """
    print(f"[WAIT] Waiting for {stage_description} to load completely...")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    spinners_selector = (
        ".spinner, .loader, [class*='loading' i], [class*='spinner' i], "
        ".ngx-spinner-overlay, .loading-indicator, [role='progressbar'], .k-loading-mask"
    )
    try:
        page.locator(spinners_selector).first.wait_for(state="hidden", timeout=6000)
    except Exception:
        pass

    page.wait_for_timeout(extra_wait_sec * 1000)
    print(f"[READY] {stage_description} is ready.")

# ==============================================================================
# CHROME PROFILE & PROCESS MANAGEMENT
# ==============================================================================
def close_all_chrome():
    print("[SYSTEM] Ensuring no locked Chrome instances are running...")
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
    time.sleep(1.5)

def sync_profile_copy():
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

# ==============================================================================
# LOGIN HANDLING
# ==============================================================================
def is_login_page(page):
    """Detect whether we've landed on the login screen rather than the dashboard."""
    try:
        url = (page.url or "").lower()
        if any(k in url for k in ["login", "signin", "sign-in", "auth", "account/login"]):
            return True
    except Exception:
        pass
    try:
        pwd = page.locator("input[type='password']").first
        if pwd.count() > 0 and pwd.is_visible(timeout=1500):
            return True
    except Exception:
        pass
    return False

def handle_login(page):
    """If the login page appears, enter credentials and submit."""
    if not is_login_page(page):
        print("[AUTH] Already logged in (no login page detected).")
        return

    print("[AUTH] Login page detected. Entering credentials...")

    email_input = page.locator(
        "input[type='email'], input[name*='email' i], input[id*='email' i], "
        "input[name*='user' i], input[placeholder*='email' i]"
    ).first
    try:
        email_input.wait_for(state="visible", timeout=10000)
        email_input.click()
        email_input.fill("")
        email_input.fill(OTELIER_EMAIL)
        print("[AUTH] Email entered.")
    except Exception as e:
        print(f"[AUTH WARNING] Could not fill email: {str(e).splitlines()[0]}")

    pwd_input = page.locator("input[type='password']").first
    if pwd_input.count() == 0 or not pwd_input.is_visible():
        for label in ["Next", "Continue", "Sign in", "Log in"]:
            try:
                b = page.get_by_role("button", name=label).first
                if b.count() > 0 and b.is_visible():
                    b.click(force=True)
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                continue
        pwd_input = page.locator("input[type='password']").first

    try:
        pwd_input.wait_for(state="visible", timeout=10000)
        pwd_input.click()
        pwd_input.fill("")
        pwd_input.fill(OTELIER_PASSWORD)
        print("[AUTH] Password entered.")
    except Exception as e:
        print(f"[AUTH WARNING] Could not fill password: {str(e).splitlines()[0]}")

    submitted = False
    for label in ["Sign in", "Log in", "Login", "Submit", "Continue"]:
        try:
            b = page.get_by_role("button", name=label).first
            if b.count() > 0 and b.is_visible():
                b.click(force=True)
                submitted = True
                break
        except Exception:
            continue
    if not submitted:
        try:
            page.locator("button[type='submit']").first.click(force=True)
            submitted = True
        except Exception:
            pass
    if not submitted:
        try:
            pwd_input.press("Enter")
            submitted = True
        except Exception:
            pass

    print("[AUTH] Waiting for authentication to complete...")
    for _ in range(40):
        page.wait_for_timeout(1500)
        if not is_login_page(page):
            print("[AUTH SUCCESS] Logged in.")
            return
    print("[AUTH WARNING] Still on login page. If MFA/CAPTCHA appeared, complete it manually.")

# ==============================================================================
# DATE CALCULATION LOGIC (FULL YEAR / YTD)
# ==============================================================================
def get_last_thursday_for_current_month():
    """Finds the most recent last Thursday for the current month."""
    today = date.today()
    offset = (today.weekday() - 3) % 7
    if offset == 0:
        offset = 7
    return today - timedelta(days=offset)

def get_ytd_target_dates(year=None):
    """
    Generates target dates for each month up to the current month:
    - Past months: Last day of the month (Jan 31, Feb 28/29, Mar 31, etc.)
    - Current month: Current month's last Thursday
    """
    today = date.today()
    if year is None:
        year = today.year

    current_last_thursday = get_last_thursday_for_current_month()
    target_dates = []

    for m in range(1, today.month + 1):
        month_name = calendar.month_name[m]
        if m < today.month:
            last_day = calendar.monthrange(year, m)[1]
            target_date = date(year, m, last_day)
            desc = f"{month_name} End ({last_day})"
        else:
            target_date = current_last_thursday
            desc = f"{month_name} (Last Thursday: {target_date.strftime('%m/%d/%Y')})"
        
        target_dates.append({
            "month_num": m,
            "month_name": month_name,
            "target_date": target_date,
            "input_date_str": target_date.strftime("%m/%d/%Y"),
            "file_date_str": target_date.strftime("%m-%d-%Y"),
            "description": desc
        })

    return target_dates

# ==============================================================================
# 'COMMENTS' FILTERING: REMOVE COMMENTED ROWS & KEEP NON-COMMENTED (UNADDRESSED)
# ==============================================================================
def get_comment_column(df: pd.DataFrame):
    """Finds the Comment / Comments column name (case-insensitive) if present."""
    for col in df.columns:
        if 'comment' in str(col).lower():
            return col
    return None

def is_non_comment_value(val) -> bool:
    """Returns True if the cell represents a non-comment / unaddressed alert ('-', '', NaN)."""
    if pd.isna(val) or val is None:
        return True
    val_str = str(val).strip()
    return val_str in DASH_VALUES or val_str.lower() in ["nan", "none"]

def filter_keep_only_non_comment_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes rows that have actual written comments (already addressed).
    Retains ONLY rows where Comment is '-' or blank (pending/unaddressed).
    """
    if df.empty:
        return pd.DataFrame()

    comment_col = get_comment_column(df)
    if comment_col is None:
        return df.copy()

    mask = df[comment_col].apply(is_non_comment_value)
    df_filtered = df[mask].copy().reset_index(drop=True)

    date_cols = [c for c in df_filtered.columns if 'date' in str(c).lower()]
    if date_cols:
        sort_dt = pd.to_datetime(df_filtered[date_cols[0]], errors='coerce')
        df_filtered = df_filtered.assign(_sort_dt=sort_dt).sort_values(
            by="_sort_dt", ascending=True
        ).drop(columns=["_sort_dt"]).reset_index(drop=True)

    return df_filtered

# ==============================================================================
# EXCEL STYLING ENGINE (ONLY UNRESOLVED TABS, YELLOW HIGHLIGHTS, CLEAN UI)
# ==============================================================================
def style_and_write_worksheet(ws, df: pd.DataFrame):
    """
    Applies exact Otelier UI styling to the worksheet:
    - Row 1: Blank
    - Row 2: Steel Blue Header (#8EA9DB), bold Aptos Narrow 11, thin black borders
    - Row 3+: Non-comment entries highlighted with solid Yellow Fill (#FFFF00), thin gridlines, currency formatting
    - Auto column widths & row heights
    """
    if ws.max_row > 0:
        ws.delete_rows(1, ws.max_row + 1)

    if df.empty:
        return

    clean_df = df.drop(columns=["Hotel_Name", "Report_Month", "_dash_priority", "_sort_dt"], errors="ignore")
    columns = list(clean_df.columns)

    # Row 1 is intentionally left blank
    ws.row_dimensions[1].height = 15

    # Row 2: Header Row (Steel Blue Fill, Bold Font, Thin Border)
    ws.row_dimensions[2].height = 24
    for col_idx, col_name in enumerate(columns, start=1):
        cell = ws.cell(row=2, column=col_idx, value=col_name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.border = THIN_BORDER
        cell.alignment = Alignment(horizontal="left", vertical="center")

    amount_col_idx = next((i for i, c in enumerate(columns, start=1) if 'amount' in str(c).lower()), None)
    date_col_idx = next((i for i, c in enumerate(columns, start=1) if 'date' in str(c).lower()), None)

    # Row 3+: Non-comment Data Rows (All highlighted in Yellow)
    for row_idx, row_data in enumerate(clean_df.itertuples(index=False), start=3):
        ws.row_dimensions[row_idx].height = 20

        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx)

            # Format Amount Column as Currency ($#,##0.00)
            if col_idx == amount_col_idx and val is not None and str(val).strip() != "":
                try:
                    num_val = float(str(val).replace("$", "").replace(",", "").strip())
                    cell.value = num_val
                    cell.number_format = "$#,##0.00"
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                except Exception:
                    cell.value = val
                    cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.value = val
                if col_idx == date_col_idx:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

            cell.font = DATA_FONT
            cell.border = THIN_BORDER
            cell.fill = YELLOW_FILL  # Highlight all non-comment entries in Yellow

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row >= 2 and cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

def save_styled_multi_sheet_workbook(file_path: str, sheets_dict: dict):
    """
    Creates an Excel workbook containing ONLY sheets that have non-comment (unaddressed) records.
    Removes sheets that have 0 non-comment records.
    If ALL sheets are empty (everything perfectly fine), creates a clean 'Status' tab.
    """
    wb = openpyxl.Workbook()

    # Filter each sheet to keep ONLY non-comment entries and exclude empty sheets
    valid_sheets = {}
    for sheet_name, df in sheets_dict.items():
        df_non_comment = filter_keep_only_non_comment_rows(df)
        if not df_non_comment.empty:
            valid_sheets[sheet_name] = df_non_comment

    if not valid_sheets:
        ws = wb.active
        ws.title = "Status"
        ws.row_dimensions[1].height = 15
        ws.row_dimensions[2].height = 24
        
        header_cell = ws.cell(row=2, column=1, value="Status")
        header_cell.fill = HEADER_FILL
        header_cell.font = HEADER_FONT
        header_cell.border = THIN_BORDER
        header_cell.alignment = Alignment(horizontal="left", vertical="center")

        data_cell = ws.cell(row=3, column=1, value="All alerts are commented / resolved (No pending entries)")
        data_cell.font = DATA_FONT
        data_cell.border = THIN_BORDER
        data_cell.alignment = Alignment(horizontal="left", vertical="center")
        
        ws.column_dimensions["A"].width = 60
        wb.save(file_path)
        return

    default_sheet = wb.active
    wb.remove(default_sheet)

    for sheet_name, df_sheet in valid_sheets.items():
        safe_title = sheet_name[:31]
        ws = wb.create_sheet(title=safe_title)
        style_and_write_worksheet(ws, df_sheet)

    wb.save(file_path)

# ==============================================================================
# MULTI-SHEET EXCEL PROCESSING & FILTERING (PRESERVING RAW DATES UNTOUCHED)
# ==============================================================================
def filter_and_preserve_all_sheets(file_path: str, target_date_str: str, hotel: str, month_name: str) -> dict:
    """
    Reads ALL sheets from the downloaded Excel file, filters records by target_date_str,
    removes commented entries, removes tabs with 0 non-comment entries, highlights non-comment entries in YELLOW,
    and writes back.
    
    Returns a dictionary of {sheet_name: filtered_DataFrame} containing only non-empty non-comment sheets.
    """
    print(f"\n[SHEETS] Processing all sheets in: {os.path.basename(file_path)} for date <= {target_date_str}")
    target_date = pd.to_datetime(target_date_str)
    raw_sheets_dict = {}

    try:
        excel_file = pd.ExcelFile(file_path)
        all_sheet_names = excel_file.sheet_names
        print(f"   Found {len(all_sheet_names)} sheet(s): {', '.join(all_sheet_names)}")

        for sheet_name in all_sheet_names:
            try:
                probe = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, nrows=15)
                if probe.empty:
                    continue

                header_row = None
                for i in range(len(probe)):
                    row_vals = [str(v).strip().lower() for v in probe.iloc[i].tolist()]
                    if 'date' in row_vals:
                        header_row = i
                        break

                if header_row is not None:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row)
                else:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)

                df.columns = ["" if str(c).startswith("Unnamed:") else str(c).strip() for c in df.columns]

                date_col = None
                for col in df.columns:
                    if 'date' in str(col).lower():
                        date_col = col
                        break

                if date_col is not None and not df.empty:
                    dt_parsed = pd.to_datetime(df[date_col], errors='coerce')
                    df_filtered = df[dt_parsed <= target_date].copy()
                else:
                    df_filtered = df.copy()

                # Filter to keep ONLY non-comment rows
                df_non_comment = filter_keep_only_non_comment_rows(df_filtered)

                if not df_non_comment.empty:
                    df_non_comment["Hotel_Name"] = hotel
                    df_non_comment["Report_Month"] = month_name
                    raw_sheets_dict[sheet_name] = df_non_comment
                    print(f"   * [{sheet_name}]: {len(df_non_comment)} non-comment pending row(s)")
                else:
                    print(f"   - [{sheet_name}]: All records commented / resolved (tab removed)")

            except Exception as sheet_err:
                print(f"   [WARNING] Could not process sheet '{sheet_name}': {sheet_err}")

        # Save back with only tabs containing non-comment records
        save_styled_multi_sheet_workbook(file_path, raw_sheets_dict)

        print(f"[SUCCESS] Filtered & saved {len(raw_sheets_dict)} active sheet(s) in {os.path.basename(file_path)}")
        return raw_sheets_dict

    except Exception as e:
        print(f"[ERROR] Error processing multi-sheet Excel {file_path}: {e}")
        return {}

def load_existing_multi_sheet_excel(file_path: str, hotel: str, month_name: str) -> dict:
    """Loads all non-comment sheets from an already-processed monthly Excel file."""
    sheets_dict = {}
    try:
        excel_file = pd.ExcelFile(file_path)
        for sheet_name in excel_file.sheet_names:
            if sheet_name.lower() == "status":
                continue
            probe = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, nrows=5)
            header_row = 0
            for i in range(len(probe)):
                row_vals = [str(v).strip().lower() for v in probe.iloc[i].tolist()]
                if 'date' in row_vals:
                    header_row = i
                    break
            
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row)
            df.columns = ["" if str(c).startswith("Unnamed:") else str(c).strip() for c in df.columns]

            df_non_comment = filter_keep_only_non_comment_rows(df)
            if not df_non_comment.empty:
                if "Hotel_Name" not in df_non_comment.columns:
                    df_non_comment["Hotel_Name"] = hotel
                if "Report_Month" not in df_non_comment.columns:
                    df_non_comment["Report_Month"] = month_name
                sheets_dict[sheet_name] = df_non_comment
        return sheets_dict
    except Exception as e:
        print(f"[LOAD ERROR] Could not read multi-sheet file {file_path}: {e}")
        return {}

def combine_monthly_sheets(monthly_sheets_list: list) -> dict:
    """
    Takes a list of monthly sheet dictionaries and combines them by sheet name.
    Retains ONLY non-comment rows and removes sheets with 0 rows.
    Returns {sheet_name: combined_DataFrame}.
    """
    combined_by_sheet = {}
    
    all_sheets = set()
    for month_dict in monthly_sheets_list:
        all_sheets.update(month_dict.keys())

    for sheet_name in all_sheets:
        dfs_for_sheet = []
        for month_dict in monthly_sheets_list:
            if sheet_name in month_dict and not month_dict[sheet_name].empty:
                df_non_comment = filter_keep_only_non_comment_rows(month_dict[sheet_name])
                if not df_non_comment.empty:
                    dfs_for_sheet.append(df_non_comment)

        if dfs_for_sheet:
            combined_df = pd.concat(dfs_for_sheet, ignore_index=True)
            combined_df.drop_duplicates(inplace=True)
            combined_df = filter_keep_only_non_comment_rows(combined_df)
            if not combined_df.empty:
                combined_by_sheet[sheet_name] = combined_df

    return combined_by_sheet

def write_multi_sheet_excel(output_path: str, sheets_dict: dict):
    """Writes a multi-sheet dictionary keeping only tabs with non-comment rows."""
    save_styled_multi_sheet_workbook(output_path, sheets_dict)

# ==============================================================================
# RESTYLE ALL EXISTING EXCEL FILES IN FOLDER
# ==============================================================================
def restyle_all_existing_excel_files():
    """
    Restyles all existing .xlsx files in BASE_DIR:
    - Removes commented entries
    - Keeps only non-comment entries and highlights them in solid YELLOW
    - Removes tabs/sheets that have 0 non-comment entries
    """
    print("\n[STYLING] Processing & filtering all existing Excel files in folder...")
    xlsx_files = [f for f in os.listdir(BASE_DIR) if f.endswith(".xlsx") and not f.startswith("~$")]
    
    for filename in xlsx_files:
        file_path = os.path.join(BASE_DIR, filename)
        try:
            excel_file = pd.ExcelFile(file_path)
            sheets_dict = {}
            for sheet_name in excel_file.sheet_names:
                if sheet_name.lower() == "status":
                    continue
                probe = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, nrows=10)
                if probe.empty:
                    continue
                header_row = 0
                for i in range(len(probe)):
                    row_vals = [str(v).strip().lower() for v in probe.iloc[i].tolist()]
                    if 'date' in row_vals:
                        header_row = i
                        break
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row)
                df.columns = ["" if str(c).startswith("Unnamed:") else str(c).strip() for c in df.columns]
                
                df_non_comment = filter_keep_only_non_comment_rows(df)
                if not df_non_comment.empty:
                    sheets_dict[sheet_name] = df_non_comment

            save_styled_multi_sheet_workbook(file_path, sheets_dict)
            active_tabs = len(sheets_dict)
            print(f"   [FILTERED] {filename} -> {active_tabs} active tab(s) with pending non-comment records")
        except Exception as e:
            print(f"   [WARNING] Could not process {filename}: {e}")

    print("[STYLING COMPLETE] All existing Excel files updated successfully!\n")

# ==============================================================================
# MAIN AUTOMATION WITH EXECUTION TIMER & MULTI-SHEET PRESERVATION
# ==============================================================================
def main():
    overall_start_time = time.time()
    start_dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    target_dates = get_ytd_target_dates()
    progress_data = load_progress()
    
    print("\n" + "=" * 65)
    print(" STARTING HELLOGM OTELIER AUTOMATION")
    print(f" Start Time: {start_dt_str}")
    print("=" * 65)
    print(" SCHEDULED TARGET DATES FOR FULL YEAR (YTD):")
    for item in target_dates:
        print(f"   * Month {item['month_num']:02d} ({item['month_name']}): {item['input_date_str']} - [{item['description']}]")
    print(f" Progress Tracker File: {PROGRESS_FILE}")
    print("=" * 65 + "\n")

    # Check overall pending tasks
    pending_tasks_exist = False
    for hotel in HOTELS:
        safe_hotel_name = hotel.replace(':', '').replace('/', '').replace('\\', '')
        for m_info in target_dates:
            month_name = m_info["month_name"]
            file_date_str = m_info["file_date_str"]
            expected_file = os.path.join(BASE_DIR, f"{safe_hotel_name} - {month_name}_{file_date_str}.xlsx")
            if not is_month_completed(progress_data, hotel, month_name, expected_file):
                pending_tasks_exist = True
                break
        if pending_tasks_exist:
            break

    if not pending_tasks_exist:
        print("[RESUME INFO] All monthly files for all hotels are already downloaded & completed!")
        print("Proceeding to verify combined files and formatting...\n")

    sync_profile_copy()

    with sync_playwright() as p:
        context = None
        page = None

        if pending_tasks_exist:
            print("\nStarting Playwright for pending tasks...")
            launch_kwargs = dict(
                user_data_dir=AUTOMATION_USER_DATA_DIR,
                headless=False,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                no_viewport=True,
                accept_downloads=True,
                downloads_path=BASE_DIR,
                timeout=60000,
            )

            try:
                context = p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
            except Exception as e:
                print(f"[SYSTEM WARNING] Chrome channel launch failed ({str(e).splitlines()[0]}). Falling back to Chromium...")
                try:
                    context = p.chromium.launch_persistent_context(**launch_kwargs)
                except Exception as e2:
                    print(f"[CRITICAL] Browser launch failed on both Chrome and Chromium: {e2}")
                    return

            page = context.pages[0] if context.pages else context.new_page()

            try:
                print("Opening Otelier...")
                page.goto("https://rec.otelier.io/Portfolio", timeout=60000)
                page.wait_for_timeout(3000)

                handle_login(page)

                if "portfolio" not in (page.url or "").lower():
                    try:
                        page.goto("https://rec.otelier.io/Portfolio", timeout=60000)
                    except Exception:
                        pass

                wait_for_data_load(page, "Portfolio Dashboard", extra_wait_sec=8)
            except Exception as e:
                print(f"[NAVIGATION ERROR] Failed to load dashboard: {e}")
                if context:
                    context.close()
                return

        try:
            all_hotels_combined_sheets = []

            for hotel in HOTELS:
                hotel_start_time = time.time()
                print(f"\n=======================================================")
                print(f" Processing Hotel: {hotel}")
                print(f"=======================================================")

                hotel_monthly_sheets = []
                safe_hotel_name = hotel.replace(':', '').replace('/', '').replace('\\', '')
                hotel_needs_browser = False

                for m_info in target_dates:
                    month_name = m_info["month_name"]
                    file_date_str = m_info["file_date_str"]
                    expected_file = os.path.join(BASE_DIR, f"{safe_hotel_name} - {month_name}_{file_date_str}.xlsx")
                    if not is_month_completed(progress_data, hotel, month_name, expected_file):
                        hotel_needs_browser = True
                        break

                if hotel_needs_browser and page is not None:
                    print("Opening hotel dropdown...")
                    dropdown_opened = False

                    try:
                        active_hotel = page.locator("xpath=//*[contains(@class, 'sidebar') or contains(@class, 'menu') or self::aside]//*[contains(text(), 'Country') or contains(text(), 'Extended') or contains(text(), 'Motel') or contains(text(), 'Hickory') or contains(text(), 'Red Roof') or contains(text(), 'Rodeway')]").first
                        if active_hotel.is_visible(timeout=3000):
                            active_hotel.click(timeout=3000)
                            dropdown_opened = True
                    except Exception:
                        pass

                    if not dropdown_opened:
                        try:
                            print("Fallback: Visually clicking below 'Rec'...")
                            rec_btn = page.locator("xpath=//*[normalize-space(text())='Rec']").first
                            if rec_btn.is_visible(timeout=2000):
                                box = rec_btn.bounding_box()
                                if box:
                                    page.mouse.click(box["x"] + (box["width"] / 2), box["y"] + box["height"] + 45)
                                    dropdown_opened = True
                        except Exception:
                            pass

                    page.wait_for_timeout(2000)

                    print("Searching for hotel...")
                    search_box = page.locator("xpath=//input[@placeholder='Search' or @type='search' or contains(@class, 'search')]").first
                    search_box.wait_for(state="visible", timeout=10000)
                    search_box.fill(hotel)
                    page.wait_for_timeout(2000)

                    print("Selecting hotel...")
                    short_name = " ".join(hotel.split(" ")[:2])
                    try:
                        hotel_result = page.locator(f"xpath=//input[@placeholder='Search' or @type='search' or contains(@class, 'search')]/following::*[contains(text(), '{short_name}') and not(contains(@class, 'card-header'))][1]").first
                        hotel_result.click(timeout=5000, force=True)
                    except Exception:
                        print("Fallback: Using keyboard navigation to select the top search result...")
                        search_box.click(force=True)
                        page.wait_for_timeout(500)
                        search_box.press("ArrowDown")
                        page.wait_for_timeout(500)
                        search_box.press("Enter")

                    page.wait_for_timeout(4000)

                    print("Navigating to Hotel overview...")
                    overview_link = page.locator("xpath=//span[contains(text(), 'Hotel overview')] | //a[contains(text(), 'Hotel overview')]").first
                    overview_link.click()
                    wait_for_data_load(page, "Hotel Overview Page", extra_wait_sec=6)

                # 2. Iterate through each month's target date
                for m_info in target_dates:
                    month_name = m_info["month_name"]
                    input_date_str = m_info["input_date_str"]
                    file_date_str = m_info["file_date_str"]
                    new_file_name = f"{safe_hotel_name} - {month_name}_{file_date_str}.xlsx"
                    new_file_path = os.path.join(BASE_DIR, new_file_name)

                    # Check if already completed previously
                    if is_month_completed(progress_data, hotel, month_name, new_file_path):
                        print(f"[RESUME] Skipping {hotel} - {month_name} (Already completed: {new_file_name})")
                        existing_sheets = load_existing_multi_sheet_excel(new_file_path, hotel, month_name)
                        if existing_sheets:
                            hotel_monthly_sheets.append(existing_sheets)
                        continue

                    if page is None:
                        print(f"[WARNING] Browser not active for pending month {month_name}.")
                        continue

                    print(f"\n--- Processing {hotel} for {month_name} (Date: {input_date_str}) ---")

                    print(f"Entering date: {input_date_str}...")
                    date_input = page.locator(
                        "xpath=//input[not(@readonly) and not(@role='combobox') and "
                        "(contains(@value,'/20') or contains(@placeholder,'/') "
                        "or contains(translate(@placeholder,'DATE','date'),'date'))]"
                    ).first
                    if date_input.count() == 0:
                        date_input = page.locator(
                            "xpath=//input[@type='text' and not(@readonly) and not(@role='combobox')]"
                        ).first

                    date_input.wait_for(state="visible", timeout=10000)
                    date_input.click()
                    date_input.press("Control+a")
                    date_input.press("Delete")
                    date_input.type(input_date_str, delay=60)
                    page.wait_for_timeout(500)
                    date_input.press("Enter")

                    try:
                        page.locator("xpath=//*[contains(text(),'Hotel Overview')]").first.click(timeout=2000)
                    except Exception:
                        pass

                    wait_for_data_load(page, f"Data Refresh for Date {input_date_str}", extra_wait_sec=6)

                    # --- Scroll down to Guest Folio section ---
                    print("Scrolling down to 'Guest Folio' section...")
                    guest_folio = page.locator("xpath=//*[contains(text(), 'Guest Folio')]").first
                    try:
                        guest_folio.wait_for(state="visible", timeout=10000)
                        guest_folio.scroll_into_view_if_needed()
                    except Exception:
                        for _ in range(6):
                            page.mouse.wheel(0, 1200)
                            page.wait_for_timeout(300)
                    page.wait_for_timeout(1500)

                    # --- Click Monthly Alerts icon ---
                    print("Looking for 'Monthly Alerts' icon in the Guest Folio section...")
                    alerts_btn = page.locator(
                        "xpath=//*[contains(text(),'Guest Folio')]"
                        "/ancestor::*[contains(@class,'card') or contains(@class,'panel') or contains(@class,'box')][1]"
                        "//*[@title='Monthly Alerts' or @aria-label='Monthly Alerts' or @data-title='Monthly Alerts' or @data-original-title='Monthly Alerts']"
                    ).first

                    if alerts_btn.count() == 0:
                        alerts_btn = page.locator(
                            "xpath=//*[contains(text(),'Guest Folio')]"
                            "/ancestor::*[contains(@class,'card') or contains(@class,'panel') or contains(@class,'box')][1]"
                            "//button[.//i[contains(@class,'calendar') or contains(@class,'fa-th') or contains(@class,'grid') or contains(@class,'table')]]"
                            " | //*[contains(text(),'Guest Folio')]/ancestor::*[contains(@class,'card') or contains(@class,'panel') or contains(@class,'box')][1]"
                            "//i[contains(@class,'calendar') or contains(@class,'fa-th') or contains(@class,'grid') or contains(@class,'table')]"
                        ).first

                    if alerts_btn.count() == 0:
                        alerts_btn = page.locator(
                            "xpath=//*[@title='Monthly Alerts' or @aria-label='Monthly Alerts' or @data-title='Monthly Alerts']"
                        ).first

                    alerts_btn.scroll_into_view_if_needed()
                    try:
                        alerts_btn.click(timeout=5000)
                    except Exception:
                        alerts_btn.click(force=True)

                    # --- Wait for 'Monthly Guest Folio' modal ---
                    print("Waiting for 'Monthly Guest Folio' modal...")
                    modal = page.locator(
                        "xpath=//*[contains(text(),'Monthly Guest Folio')]"
                        "/ancestor::*[contains(@class,'modal') or contains(@class,'dialog') or @role='dialog'][1]"
                    ).first
                    try:
                        modal.wait_for(state="visible", timeout=25000)
                    except Exception:
                        print("   [WARNING] Modal container not detected; continuing anyway.")

                    wait_for_data_load(page, "Monthly Guest Folio Table Data", extra_wait_sec=6)

                    print("Clicking the modal's Download icon and waiting for file...")
                    download_btn = page.locator(
                        "xpath=//*[contains(text(),'Monthly Guest Folio')]"
                        "/ancestor::*[contains(@class,'modal') or contains(@class,'dialog') or @role='dialog'][1]"
                        "//*[@title='Download' or @aria-label='Download' or @data-title='Download' or @data-original-title='Download']"
                    ).first

                    if download_btn.count() == 0:
                        download_btn = page.locator(
                            "xpath=//*[contains(text(),'Monthly Guest Folio')]"
                            "/ancestor::*[contains(@class,'modal') or contains(@class,'dialog') or @role='dialog'][1]"
                            "//a[contains(@class,'download')] "
                            "| //*[contains(text(),'Monthly Guest Folio')]/ancestor::*[contains(@class,'modal') or contains(@class,'dialog') or @role='dialog'][1]"
                            "//i[contains(@class,'download')] "
                            "| //*[contains(text(),'Monthly Guest Folio')]/ancestor::*[contains(@class,'modal') or contains(@class,'dialog') or @role='dialog'][1]"
                            "//button[.//i[contains(@class,'download')]]"
                        ).first

                    if download_btn.count() == 0:
                        download_btn = page.locator(
                            "xpath=//*[@title='Download' or @aria-label='Download'] | //*[contains(@class,'download')]"
                        ).first

                    download_btn.scroll_into_view_if_needed()
                    with page.expect_download(timeout=60000) as download_info:
                        try:
                            download_btn.click(timeout=5000)
                        except Exception:
                            download_btn.click(force=True)

                    download = download_info.value

                    if os.path.exists(new_file_path):
                        try:
                            os.remove(new_file_path)
                        except Exception:
                            pass

                    download.save_as(new_file_path)
                    print(f"File downloaded successfully to: {new_file_path}")

                    # Filter ALL sheets, keep only non-comment entries, remove clean sheets, apply yellow highlight
                    filtered_sheets = filter_and_preserve_all_sheets(new_file_path, input_date_str, hotel, month_name)
                    if filtered_sheets:
                        hotel_monthly_sheets.append(filtered_sheets)

                    sheet_stats = {s_name: len(df) for s_name, df in filtered_sheets.items()}
                    mark_month_completed(progress_data, hotel, month_name, new_file_path, sheet_stats)

                    # Close Modal
                    try:
                        close_btn = page.locator(
                            "xpath=//*[contains(text(),'Monthly Guest Folio')]"
                            "/ancestor::*[contains(@class,'modal') or contains(@class,'dialog') or @role='dialog'][1]"
                            "//button[contains(@class,'close') or @aria-label='Close' or normalize-space(text())='×']"
                        ).first
                        if close_btn.count() > 0 and close_btn.is_visible():
                            close_btn.click(force=True)
                        else:
                            page.keyboard.press("Escape")
                    except Exception:
                        page.keyboard.press("Escape")

                    page.wait_for_timeout(2000)

                # 3. Combine all months for this hotel across ALL tabs with non-comment filter & full styling
                combined_file_path = os.path.join(BASE_DIR, f"{safe_hotel_name} - Full Year Combined.xlsx")
                if hotel_monthly_sheets:
                    print(f"\nCombining all {len(hotel_monthly_sheets)} months for {hotel} across active tabs...")
                    combined_hotel_sheets = combine_monthly_sheets(hotel_monthly_sheets)
                    write_multi_sheet_excel(combined_file_path, combined_hotel_sheets)

                    sheet_counts = {s: len(df) for s, df in combined_hotel_sheets.items()}
                    print(f"[SAVED] Combined Multi-Tab Excel for {hotel}: {combined_file_path}")
                    for s, cnt in sheet_counts.items():
                        print(f"   * Tab '{s}': {cnt} non-comment pending rows")

                    mark_hotel_completed(progress_data, hotel, combined_file_path, sheet_counts)
                    all_hotels_combined_sheets.append(combined_hotel_sheets)
                else:
                    print(f"[INFO] No pending non-comment data for {hotel} across any month. Generating Status file.")
                    save_styled_multi_sheet_workbook(combined_file_path, {})
                    mark_hotel_completed(progress_data, hotel, combined_file_path, {"Status": 0})

                hotel_elapsed = time.time() - hotel_start_time
                print(f"[TIMER] Finished processing {hotel} in {format_duration(hotel_elapsed)}.")

                if page is not None and hotel_needs_browser:
                    print("\nNavigating back to Portfolio page to reset state...")
                    try:
                        page.goto("https://rec.otelier.io/Portfolio", timeout=60000)
                        wait_for_data_load(page, "Portfolio Return", extra_wait_sec=5)
                    except Exception as e:
                        print(f"Failed to return to Portfolio page: {e}")

                print("Proceeding to next hotel...\n")

            # 4. Master Combined file for ALL hotels (combines every tab across all hotels)
            if all_hotels_combined_sheets:
                print("\n[MASTER] Generating ALL HOTELS Master Multi-Tab Combined File...")
                master_sheets = combine_monthly_sheets(all_hotels_combined_sheets)
                master_file_path = os.path.join(BASE_DIR, "ALL HOTELS - Full Year Combined.xlsx")
                write_multi_sheet_excel(master_file_path, master_sheets)

                print(f"[SUCCESS] ALL HOTELS Master File Created: {master_file_path}")
                for s, df in master_sheets.items():
                    print(f"   * Tab '{s}': {len(df)} non-comment pending rows across all hotels")

                progress_data["all_completed"] = True
                progress_data["master_file"] = master_file_path
                progress_data["last_run_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_progress(progress_data)

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            if context:
                print("Closing Playwright context...")
                context.close()

    total_elapsed_sec = time.time() - overall_start_time
    formatted_total_time = format_duration(total_elapsed_sec)
    end_dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 65)
    print(" AUTOMATION EXECUTION COMPLETED")
    print(f" End Time: {end_dt_str}")
    print(f" Total Duration: {formatted_total_time} ({total_elapsed_sec:.2f} seconds)")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()