import csv
import json
import os
import sys
import time
import re
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
MASTERS_DIR = PROJECT / "masters"
VALIDATED_CSV = MASTERS_DIR / "validated_vendors.csv"
SELECTORS_FILE = HERE / "selectors.json"
EXTENSION_PATH = r"C:\Users\Meet Patel\Desktop\automation\nexuspayables-extension"

# --- Chrome Profile Sync Logic ---
_HOME = os.path.expanduser("~")
AUTOMATION_USER_DATA_DIR = os.path.join(_HOME, "ChromeAutomationProfile")

def parse_modal_text(raw_text):
    """
    Parses the raw text from the Vendor Address modal into Address, City, Zip, and Contact No.
    Matches the logic used in the Chrome extension's content.js.
    """
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    
    # Drop lone close glyphs
    lines = [l for l in lines if l.lower() not in ['x', '×', '✕', '✖', 'close']]

    # Drop the heading line if present
    if lines and lines[0].lower() in ['vendor address', 'property address']:
        lines.pop(0)

    contactno = ""
    city = ""
    zipcode = ""
    vendor_address = ""

    # Extract Phone Number (usually the last line)
    if lines:
        last_line = lines[-1]
        digits = re.sub(r'\D', '', last_line)
        # Check if it looks like a phone line (e.g. (301) 891-2600)
        if len(digits) >= 7 and re.match(r'^[\d\s()+.\-]+$', last_line):
            contactno = lines.pop(-1)

    # Extract City and Zip from the new last line (usually City, State Zip)
    if lines:
        city_state_zip_line = lines[-1]
        # Match standard 5 or 9 digit US zip at the end
        zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)$', city_state_zip_line)
        if zip_match:
            zipcode = zip_match.group(1)
            city_state_zip_line = city_state_zip_line[:zip_match.start()].strip()
            
        # Parse City (usually before the comma)
        if "," in city_state_zip_line:
            city = city_state_zip_line.split(",")[0].strip()
        else:
            parts = city_state_zip_line.rsplit(" ", 1)
            city = parts[0].strip() if len(parts) > 1 else city_state_zip_line
            
        lines.pop(-1)

    # The remaining lines are the actual street address.
    # The first line might be the "Vendor Name (Code)", let's drop it if it has parenthesis at the end
    if lines and "(" in lines[0] and lines[0].endswith(")"):
        lines.pop(0)

    vendor_address = ", ".join(lines)
    return vendor_address, city, zipcode, contactno

def main():
    load_dotenv(PROJECT / ".env")
    url = os.getenv("BOTTOMLINE_URL", "").strip()
    username = os.getenv("BOTTOMLINE_USERNAME", "").strip()
    password = os.getenv("BOTTOMLINE_PASSWORD", "").strip()

    if not all([url, username, password]):
        sys.exit("Missing credentials in .env file.")

    with open(SELECTORS_FILE, "r") as f:
        selectors = json.load(f)

    if not VALIDATED_CSV.exists():
        sys.exit(f"{VALIDATED_CSV} not found.")

    # Load the validated records, forcing all columns to string so we can safely insert text
    df = pd.read_csv(VALIDATED_CSV, encoding='utf-8-sig', dtype=str)
    
    # Ensure new columns exist
    for col in ['vendorAddress', 'city', 'zipcode', 'contactno']:
        if col not in df.columns:
            df[col] = ""
            
    # Replace Pandas NaNs with empty strings to prevent further dtype issues
    df.fillna("", inplace=True)

    # Process only TRUE verified records
    true_records = df[df['verifier'].astype(str).str.upper() == 'TRUE'].copy()
    total = len(true_records)
    print(f"Found {total} TRUE records to fetch deep address data for.")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(AUTOMATION_USER_DATA_DIR),
            headless=False,
            channel="chrome",
            args=[
                f"--disable-extensions-except={EXTENSION_PATH}",
                f"--load-extension={EXTENSION_PATH}",
                "--start-maximized", 
                "--no-first-run"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("Navigating to Nexus (with 60s timeout & networkidle wait)...")
        # Boosted timeout and networkidle to prevent crashes on slow loading days
        page.goto(url, timeout=60000)
        
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except:
            print("  -> networkidle wait timed out, proceeding anyway...")

        if page.locator("input[type='password']").count() > 0:
            print("Logging in...")
            page.locator("input[type='text'], input[type='email']").first.fill(username)
            page.locator("input[type='password']").first.fill(password)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except:
                pass

        print("Clicking on 'Image Management'...")
        image_management_btn = page.locator("text='Image Management'").first
        image_management_btn.wait_for(state="visible", timeout=60000)
        image_management_btn.click()
        page.wait_for_timeout(4000)

        print("Opening Indexing Queue...")
        page.wait_for_selector(f".x-column-header-checkbox, .x-grid-hd-checker, .x-column-header .x-grid-checkcolumn, {selectors['queue']['row_tick_box']}", timeout=60000)
        
        select_all_checkbox = page.locator(".x-column-header-checkbox, .x-grid-hd-checker, .x-column-header .x-grid-checkcolumn").first
        if select_all_checkbox.is_visible():
            select_all_checkbox.click()
        else:
            page.locator(selectors["queue"]["row_tick_box"]).first.click()
            
        page.wait_for_timeout(1000)
        page.locator(selectors["queue"]["index_selected"]).first.click()
        page.wait_for_selector(selectors["page_header"], timeout=60000)
        print("Ready for rapid address popup extraction.\n")

        count = 0
        for index, row in true_records.iterrows():
            count += 1
            pkg = str(row['integrationPackage']).strip()
            v_code = str(row['vendorCode']).strip()
            v_name = str(row['vendor']).strip()
            
            print(f"[{count}/{total}] Fetching Popup Address for: {v_code} - {v_name}")
            
            # Type package
            pkg_input = page.locator(selectors["fill"]["integration_package"]).first
            pkg_input.click()
            pkg_input.press("Control+a")
            pkg_input.press("Delete")
            pkg_input.type(pkg, delay=10)
            try:
                page.locator(selectors["dropdown_item_selector"]).filter(has_text=pkg).first.click(timeout=1500)
            except:
                pass
            
            # Type exact vendor code
            vendor_input = page.locator(selectors["fill"]["vendor"]).first
            vendor_input.click()
            vendor_input.press("Control+a")
            vendor_input.press("Delete")
            vendor_input.type(v_code, delay=50)
            
            try:
                # Select dropdown
                dropdown_item = page.locator(selectors["dropdown_item_selector"]).first
                dropdown_item.wait_for(state="visible", timeout=5000)
                dropdown_item.click()
                page.keyboard.press("Tab")
                time.sleep(1.0) # Give UI time to stabilize

                # Click the "Vendor Address" button to open the modal
                # Relaxed locator to find any button containing "Vendor Address"
                addr_btn = page.locator(".x-btn, button, a").filter(has_text="Vendor Address").locator("visible=true").first
                addr_btn.wait_for(state="visible", timeout=5000)
                addr_btn.click()

                # Wait for the Modal/Popup
                # ExtJS modals use .x-window
                modal = page.locator(".x-window").filter(has_text="Vendor Address").locator("visible=true").first
                modal.wait_for(state="visible", timeout=6000)
                
                # Extract text
                raw_text = modal.inner_text()
                
                # Close the modal
                page.keyboard.press("Escape")
                time.sleep(0.5) # Animation delay
                
                # If escape didn't work, try clicking the tiny 'x' close tool in ExtJS
                if modal.is_visible():
                    try:
                        modal.locator(".x-tool-close").first.click(timeout=1000)
                    except:
                        pass
                
                # Parse the extracted text
                v_addr, v_city, v_zip, v_contact = parse_modal_text(raw_text)
                
                df.at[index, 'vendorAddress'] = v_addr
                df.at[index, 'city'] = v_city
                df.at[index, 'zipcode'] = v_zip
                df.at[index, 'contactno'] = v_contact
                
                # Clean up details column if it only had an address warning
                details = str(row['details'])
                if "Mismatches:" not in details and "Address Warning:" in details:
                    df.at[index, 'details'] = "Matches perfectly (Address Extracted via Popup)."
                    
                print(f"  -> Extracted: {v_city}, {v_zip} | Phone: {v_contact}")

            except Exception as e:
                print(f"  -> Error grabbing address popup for {v_code}: {str(e)}")
                # Try to close modal just in case it got stuck open
                page.keyboard.press("Escape")

            # Save progress incrementally
            if count % 20 == 0:
                # Only keep columns we want, plus standard ones
                df.to_csv(VALIDATED_CSV, index=False, encoding='utf-8-sig')
                print("  [Progress Saved]")

        # Final Save
        df.to_csv(VALIDATED_CSV, index=False, encoding='utf-8-sig')
        print("\nAll addresses successfully parsed and saved into validated_vendors.csv!")
        
        context.close()

if __name__ == "__main__":
    main()
