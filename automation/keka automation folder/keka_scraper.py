'''
pip install playwright pandas openpyxl
playwright install chromium
'''
import os
import time
import shutil
import re
import glob
import json
import pandas as pd
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR = os.path.join(os.environ['USERPROFILE'], r"AppData\Local\Google\Chrome\User Data")
AUTOMATION_USER_DATA_DIR = os.path.join(BASE_DIR, "ChromeAutomationProfile")


def sync_profile_copy():
    print("Preparing Chrome profile (this allows you to keep Chrome open)...")
    src = os.path.join(USER_DATA_DIR, "Default")
    dst = os.path.join(AUTOMATION_USER_DATA_DIR, "Default")
    
    def ignore_caches(dir, contents):
        return [c for c in contents if "Cache" in c or c == "lockfile" or c.startswith("Singleton")]
        
    try:
        if os.path.exists(AUTOMATION_USER_DATA_DIR):
            for _ in range(3):
                try:
                    shutil.rmtree(AUTOMATION_USER_DATA_DIR, ignore_errors=True)
                    break
                except Exception:
                    time.sleep(1)
            
        os.makedirs(AUTOMATION_USER_DATA_DIR, exist_ok=True)
        shutil.copytree(src, dst, ignore=ignore_caches, dirs_exist_ok=True)
        
        local_state_src = os.path.join(USER_DATA_DIR, "Local State")
        if os.path.exists(local_state_src):
            shutil.copy2(local_state_src, os.path.join(AUTOMATION_USER_DATA_DIR, "Local State"))
    except Exception as e:
        print(f"Minor issue copying profile: {e}")


def seed_chrome_prefs():
    # Force Chrome to download directly to our folder without asking
    prof_dir = os.path.join(AUTOMATION_USER_DATA_DIR, "Default")
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
    prefs["download"]["default_directory"] = BASE_DIR
    prefs["download"]["prompt_for_download"] = False

    try:
        with open(prefs_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
    except Exception as e:
        pass


def clean_downloaded_data(file_path):
    # I left this function here in case you want to use it later!
    print("\nProcessing the downloaded file...")
    print("Keeping columns A, M, N, O and updating Asset IDs...")
    
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        cols_to_keep = [0, 12, 13, 14]
        available_cols = [c for c in cols_to_keep if c < len(df.columns)]
        df = df.iloc[:, available_cols]
        
        if len(df.columns) > 0:
            col_a = df.columns[0]
            df[col_a] = df[col_a].astype(str)
            df[col_a] = df[col_a].str.replace(r'^MS-?', 'M', regex=True)
            df[col_a] = df[col_a].str.replace(r'^FS-?', 'F', regex=True)
            df[col_a] = df[col_a].str.replace(r'^WS-?', 'W', regex=True)
            
        if ext == '.csv':
            df.to_csv(file_path, index=False)
        else:
            df.to_excel(file_path, index=False)
            
        print("Data cleaning complete! The file is ready.")
    except Exception as e:
        print(f"Error while cleaning data: {e}")


def main():
    sync_profile_copy()
    seed_chrome_prefs() 
    
    with sync_playwright() as p:
        print("Launching Playwright browser...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=AUTOMATION_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            accept_downloads=True,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
            no_viewport=True,
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        try:
            print("Opening Keka...")
            page.goto("https://karmacpa.keka.com/#/org/assets/reports/allassets", wait_until="domcontentloaded", timeout=60000)
            
            print("Waiting 15 seconds for dashboard to load...")
            page.wait_for_timeout(15000)
            
            def select_dropdown(header_name, option_name):
                print(f" -> Selecting {header_name} : {option_name}")
                
                header_regex = re.compile(f"^\\s*{header_name}\\s*$", re.IGNORECASE)
                headers = page.get_by_text(header_regex).all()
                visible_headers = [h for h in headers if h.is_visible()]
                if visible_headers:
                    visible_headers[0].click(force=True)
                else:
                    page.get_by_text(header_name).first.click(force=True)
                
                page.wait_for_timeout(1000)
                
                option_regex = re.compile(f"^\\s*{option_name}\\s*$", re.IGNORECASE)
                options = page.get_by_text(option_regex).all()
                visible_opts = [opt for opt in options if opt.is_visible()]
                
                if visible_opts:
                    visible_opts[-1].click(force=True)
                else:
                    print(f"    [WARNING] Option '{option_name}' not found!")
                    
                page.wait_for_timeout(500)
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

            print("Applying filters...")
            select_dropdown("ASSET CATEGORY", "Office Hardware")
            select_dropdown("ASSET TYPE", "Desk")
            select_dropdown("ASSET STATUS", "Select All")
            
            print("Clicking Run...")
            run_btn = page.locator("button", has_text=re.compile(r"Run", re.IGNORECASE)).first
            if run_btn.count() > 0:
                run_btn.click(force=True)
            page.wait_for_timeout(2000)
            
            print("Clicking Download menu...")
            dl_btn = page.get_by_text(re.compile(r"^\s*Download\s*$", re.IGNORECASE)).last
            if dl_btn.count() == 0:
                dl_btn = page.get_by_text(re.compile(r"Download", re.IGNORECASE)).first
            dl_btn.click(force=True)
            page.wait_for_timeout(1000)
            
            print("Clicking 'Download Excel'...")
            excel_btn = page.get_by_text(re.compile(r"Download Excel", re.IGNORECASE)).last
            if excel_btn.count() == 0:
                excel_btn = page.get_by_text(re.compile(r"Excel", re.IGNORECASE)).last
            excel_btn.click(force=True)
            
            print("\n" + "="*60)
            print("Script has finished clicking 'Download Excel'!")
            print("The script will now stay open and do nothing for 1 minute.")
            print("You can manually click the banner when it appears.")
            print("You can close this program yourself when you are done.")
            print("="*60 + "\n")
            
            # Wait for 60 seconds
            page.wait_for_timeout(60000)
            
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            print("Closing browser...")
            context.close()

if __name__ == "__main__":
    main()