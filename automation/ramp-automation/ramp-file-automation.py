## installation
# pip install pandas openpyxl playwright

import openpyxl
import pandas as pd
from playwright.sync_api import sync_playwright
import subprocess
import time
import os
import shutil
import re

# --- Configuration ---
FILE_NAME = '2026-07-28-jc-apartments-llc.csv'
SHEET_NAME = '2026-07-28-jc-apartments-llc'

REAL_USER_DATA_DIR = r"C:\Users\Meet Patel\AppData\Local\Google\Chrome\User Data"
REAL_PROFILE_DIR = "Default"

AUTOMATION_USER_DATA_DIR = r"C:\Users\Meet Patel\ChromeAutomationProfile"
AUTOMATION_PROFILE_DIR = "Default"


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


def main():
    print(f"Loading file: {FILE_NAME}")

    try:
        if FILE_NAME.lower().endswith('.csv'):
            df = pd.read_csv(FILE_NAME)
        else:
            df = pd.read_excel(FILE_NAME, sheet_name=SHEET_NAME)
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{FILE_NAME}'.")
        return
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return

    cols_lower = [str(c).strip().lower() for c in df.columns]

    if 'transaction link' not in cols_lower:
        print("❌ Error: Could not find 'Transaction Link' in the first row.")
        return
    
    link_col_name = df.columns[cols_lower.index('transaction link')]

    if 'notes' not in cols_lower:
        print("💡 'Notes' column not found, so I created one for you.")
        df['Notes'] = ""
        notes_col_name = 'Notes'
    else:
        notes_col_name = df.columns[cols_lower.index('notes')]

    # Ensure the notes column is string type so we can update it
    df[notes_col_name] = df[notes_col_name].astype(str)

    close_all_chrome()
    sync_profile_copy()

    print("\n🌐 Launching Chrome (synced Meet profile) via Playwright...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=AUTOMATION_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=[
                "--start-maximized",
                f"--profile-directory={AUTOMATION_PROFILE_DIR}",
            ],
            no_viewport=True,
        )
        
        if not context.pages:
            try:
                context.wait_for_event("page", timeout=5000)
            except Exception:
                pass
        page = context.pages[0] if context.pages else context.new_page()
        print(f"✅ Chrome ready. Active tab: {page.url}")

        total_rows = len(df)
        print(f"\n🚀 Starting extraction... ({total_rows} rows to check)")
        
        for idx, row in df.iterrows():
            url = row[link_col_name]
            excel_row_num = idx + 2 # +2 because index is 0-based and Excel has a header row

            if pd.isna(url) or not str(url).startswith('http'):
                continue

            print(f"\n[Row {excel_row_num}] Opening Link: {url}")
            try:
                # Use domcontentloaded to speed up navigation
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # 1. Find the Memo label dynamically without hard sleep
                memo_label = page.locator("xpath=//*[text()='Memo']").first
                try:
                    memo_label.wait_for(state="visible", timeout=15000)
                except Exception:
                    # Fallback to general text search if xpath fails
                    memo_label = page.locator("text=Memo").first
                    memo_label.wait_for(state="visible", timeout=10000)

                memo_text = ""
                
                # 2. Trigger the edit box
                edit_clicked = False
                textbox = page.locator("textarea, [role='textbox']").first

                if textbox.is_visible():
                    edit_clicked = True

                if not edit_clicked:
                    # Aggressively find the pencil icon by checking broader ancestor levels
                    for level in range(1, 8):
                        if edit_clicked: break
                        try:
                            ancestor = memo_label.locator(f"xpath=ancestor::*[{level}]")
                            clickables = ancestor.locator("button, [role='button'], svg")
                            
                            # Click in reverse order (pencil is usually the last icon on the right)
                            for i in range(clickables.count() - 1, -1, -1):
                                try:
                                    clickables.nth(i).click(force=True, timeout=500)
                                    try:
                                        # Wait dynamically up to 1s; proceeds INSTANTLY if it appears
                                        textbox.wait_for(state="visible", timeout=1000)
                                        edit_clicked = True
                                        break
                                    except Exception:
                                        pass
                                except Exception:
                                    continue
                        except Exception:
                            continue

                # NUCLEAR FALLBACK: Simulate a raw mouse click 300 pixels to the right of "Memo"
                if not edit_clicked:
                    try:
                        box = memo_label.bounding_box()
                        if box:
                            page.mouse.click(box["x"] + 300, box["y"] + (box["height"] / 2))
                            try:
                                textbox.wait_for(state="visible", timeout=1500)
                                edit_clicked = True
                            except Exception:
                                pass
                    except Exception:
                        pass

                if not edit_clicked:
                    raise ValueError("Found the Memo section, but could not trigger the edit text box.")

                # 3. Extract the text safely
                if edit_clicked and textbox.is_visible():
                    try:
                        memo_text = textbox.input_value().strip()
                    except Exception:
                        try:
                            memo_text = textbox.inner_text().strip()
                        except:
                            pass
                    
                    # 4. Cancel to exit safely
                    try:
                        page.get_by_role("button", name="Cancel").click(timeout=1000)
                    except Exception:
                        page.keyboard.press("Escape") # Press ESC if cancel button isn't found

                if not memo_text:
                    memo_text = "Empty Memo" 

                # Save to Dataframe
                df.at[idx, notes_col_name] = memo_text
                print(f"[Row {excel_row_num}] ✅ SUCCESS - Copied Memo: {memo_text}")

            except Exception as e:
                error_msg = str(e).split('\n')[0]
                print(f"[Row {excel_row_num}] ⚠️ FAILED - {error_msg}")
                df.at[idx, notes_col_name] = "Memo Not Found"

        context.close()

    new_filename = 'UPDATED_' + FILE_NAME
    if FILE_NAME.lower().endswith('.csv'):
        df.to_csv(new_filename, index=False)
    else:
        df.to_excel(new_filename, index=False)
    print(f"\n🎉 All done! Data saved to a new file: {new_filename}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💥 UNEXPECTED CRASH: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to close...")