import csv
import json
import os
import shutil
import sys
import time
import difflib
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
MASTERS_DIR = PROJECT / "masters"
LOG_DIR = PROJECT / "logs"

VENDORS_CSV = MASTERS_DIR / "vendors.csv"
ACTIVE_VENDORS_CSV = MASTERS_DIR / "Active vendors.csv"
VALIDATED_CSV = MASTERS_DIR / "validated_vendors.csv"
INVALID_CSV = MASTERS_DIR / "invalid_vendors.csv"
ALIASES_CSV = MASTERS_DIR / "aliases.csv"
SELECTORS_FILE = HERE / "selectors.json"
EXTENSION_PATH = r"C:\Users\Meet Patel\Desktop\automation\nexuspayables-extension"

# --- Chrome Profile Sync Logic ---
_HOME = os.path.expanduser("~")
REAL_USER_DATA_DIR = os.path.join(_HOME, "AppData", "Local", "Google", "Chrome", "User Data")
REAL_PROFILE_DIR = "Default"
AUTOMATION_USER_DATA_DIR = os.path.join(_HOME, "ChromeAutomationProfile")
AUTOMATION_PROFILE_DIR = "Default"

BROWSERS_DIR = PROJECT / ".browsers"
if BROWSERS_DIR.exists():
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_DIR)

def sync_profile_copy():
    print("Syncing browser profile from local Chrome WITHOUT closing existing windows...")
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
        shutil.copytree(src, dst, ignore=ignore_locks, dirs_exist_ok=True, copy_function=safe_copy)
        print("Browser profile synced (live locked files skipped).")
    except Exception as e:
        print(f"Profile sync warning (continuing anyway): {str(e).splitlines()[0]}")

def get_field_by_label(page, label_text):
    try:
        if label_text == "Vendor Address":
            loc = page.locator("[placeholder*='Vendor Address']").first
            if loc.count() > 0:
                tag = str(loc.evaluate("el => el.tagName")).lower()
                val = loc.input_value() if tag in ['input', 'textarea'] else loc.inner_text()
                if val and val.strip():
                    return val.strip()

        # We use evaluate to strictly match the label text, ignoring colons/asterisks,
        # but preventing "Vendor" from matching "Vendor Code".
        val = page.evaluate("""(labelText) => {
            const labels = Array.from(document.querySelectorAll('label'));
            const targetLabel = labels.find(l => {
                let text = l.innerText || l.textContent || "";
                text = text.replace(/[:*]/g, '').trim().toLowerCase();
                return text === labelText.toLowerCase();
            });
            
            if (!targetLabel) return "";
            
            // Go up to the x-form-item container
            let container = targetLabel.closest('.x-form-item');
            if (container) {
                let input = container.querySelector('input, textarea');
                if (input && input.value) return input.value;
                
                let displayField = container.querySelector('.x-form-display-field');
                if (displayField && displayField.innerText) return displayField.innerText;
            }
            
            // Ultimate Fallback: just look at the next sibling or input right after it
            let next = targetLabel.nextElementSibling;
            while(next) {
                let input = next.querySelector('input, textarea') || (next.tagName==='INPUT'?next:null);
                if (input && input.value) return input.value;
                next = next.nextElementSibling;
            }
            return "";
        }""", label_text)
        
        if val:
            return val.strip()
        return ""
    except Exception:
        return ""

def write_log(filepath, message):
    print(message)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def clean_name(n):
    if not n: return ""
    # Strip everything in parentheses (e.g. "(Manassas/20111)")
    n = re.sub(r'\(.*?\)', '', n)
    # Strip common suffixes and punctuation to find the core name
    n = n.lower().replace(",", "").replace(".", "").replace(" llc", "").replace(" inc", "").replace(" corp", "").strip()
    return n

def verify_data(v, scraped_pkg, scraped_v_code, scraped_v_name, scraped_v_addr, scraped_v_city="", scraped_v_zip=""):
    critical_mismatches = []
    warning_mismatches = []
    
    if scraped_pkg.upper() != v["package"].upper():
        critical_mismatches.append(f"Package ('{v['package']}' vs '{scraped_pkg}')")
    if scraped_v_code.strip().lower() != v["erp_id"].strip().lower():
        critical_mismatches.append(f"Code ('{v['erp_id']}' vs '{scraped_v_code}')")
        
    orig_name_clean = clean_name(v["raw_name"])
    def_erp_clean = clean_name(v["default_erp"])
    scraped_name_clean = clean_name(scraped_v_name)
    
    match_orig = difflib.SequenceMatcher(None, orig_name_clean, scraped_name_clean).ratio()
    match_def = difflib.SequenceMatcher(None, def_erp_clean, scraped_name_clean).ratio() if def_erp_clean else 0

    def is_substring(a, b):
        return len(a) > 3 and len(b) > 3 and (a in b or b in a)

    if (match_orig < 0.60 and match_def < 0.60 
        and not is_substring(orig_name_clean, scraped_name_clean) 
        and not is_substring(def_erp_clean, scraped_name_clean)):
        
        if v["default_erp"]:
            critical_mismatches.append(f"Name ('{v['raw_name']}' or '{v['default_erp']}' vs '{scraped_v_name}')")
        else:
            critical_mismatches.append(f"Name ('{v['raw_name']}' vs '{scraped_v_name}')")

    scraped_addr_clean = scraped_v_addr.lower().replace(",", "").replace(".", "").replace("\n", " ").strip()
    check_string = f"{scraped_addr_clean} {scraped_v_city.lower()} {scraped_v_zip.lower()}"
    
    if v["city"] and v["city"].lower() not in check_string:
        warning_mismatches.append(f"City '{v['city']}' missing")
    if v["zip"] and v["zip"].lower() not in check_string:
        warning_mismatches.append(f"Zip '{v['zip']}' missing")
        
    if not critical_mismatches:
        if not warning_mismatches:
            return "TRUE", "Matches perfectly."
        else:
            return "TRUE", "Address Warning: " + "; ".join(warning_mismatches)
    else:
        details = "Mismatches: " + "; ".join(critical_mismatches)
        if warning_mismatches:
            details += " | Address Warning: " + "; ".join(warning_mismatches)
        return "FALSE", details

def append_alias(raw_name, correct_name):
    if not ALIASES_CSV.exists():
        with open(ALIASES_CSV, "w", encoding="utf-8-sig") as f:
            f.write("raw,correct,count,last_seen\n")
    
    with open(ALIASES_CSV, "a", encoding="utf-8-sig") as f:
        date_str = datetime.now().strftime("%Y-%m-%d")
        f.write(f'"{raw_name}","{correct_name}",1,{date_str}\n')

def mark_vendor_inactive_in_csv(erp_id):
    """Updates the original vendors.csv file to mark the vendor as Inactive."""
    rows = []
    with open(VENDORS_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        if "Status" not in fieldnames:
            fieldnames.append("Status")
        for r in reader:
            if r.get("ERP Vendor ID", "").strip() == erp_id:
                r["Status"] = "Inactive"
            rows.append(r)
            
    with open(VENDORS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [!] Marked ERP ID '{erp_id}' as Inactive in vendors.csv")

def attempt_search(page, selectors, log_path, search_term):
    vendor_input = page.locator(selectors["fill"]["vendor"]).first
    vendor_input.click()
    vendor_input.press("Control+a")
    vendor_input.press("Delete")
    vendor_input.type(search_term, delay=50)

    try:
        dropdown_item = page.locator(selectors["dropdown_item_selector"]).first
        dropdown_item.wait_for(state="visible", timeout=4000)
        dropdown_text = dropdown_item.inner_text().strip()
        dropdown_item.click()
        page.keyboard.press("Tab") # Force ExtJS to trigger the backend data fetch
        
        # Smart Wait: ExtJS often takes 1-5 seconds to fetch the Address from the server
        v_addr = ""
        for _ in range(10):
            time.sleep(0.5)
            v_addr = get_field_by_label(page, "Vendor Address")
            if v_addr:
                break
        
        v_code = get_field_by_label(page, "Vendor Code")
        v_name = get_field_by_label(page, "Vendor")
        v_type = get_field_by_label(page, "Vendor Type")
        
        dropdown_city, dropdown_zip = "", ""
        if "(" in dropdown_text and ")" in dropdown_text:
            inside_parens = dropdown_text.rsplit("(", 1)[-1].split(")")[0]
            if "/" in inside_parens:
                parts = inside_parens.split("/")
                dropdown_city = parts[0].strip()
                dropdown_zip = parts[1].strip()

        if not v_name or v_name.strip() == search_term.strip():
            if "(" in dropdown_text:
                v_name = dropdown_text.rsplit("(", 1)[0].strip()
            else:
                v_name = dropdown_text.strip()
                
        return True, (v_code, v_name, v_type, v_addr, dropdown_city, dropdown_zip)
    except Exception:
        return False, None

def main():
    load_dotenv(PROJECT / ".env")
    url = os.getenv("BOTTOMLINE_URL", "").strip()
    username = os.getenv("BOTTOMLINE_USERNAME", "").strip()
    password = os.getenv("BOTTOMLINE_PASSWORD", "").strip()

    if not all([url, username, password]):
        sys.exit("Missing credentials in .env file.")

    with open(SELECTORS_FILE, "r") as f:
        selectors = json.load(f)

    if not VENDORS_CSV.exists():
        sys.exit(f"{VENDORS_CSV} not found.")

    # 1) Load Active Vendors map
    active_vendors_map = {}
    if ACTIVE_VENDORS_CSV.exists():
        with open(ACTIVE_VENDORS_CSV, "r", encoding="utf-8-sig") as f:
            # Check headers dynamically because of interleaved structure
            reader = csv.reader(f)
            headers = next(reader, [])
            vendor_idx = headers.index("Vendor Name") if "Vendor Name" in headers else 0
            def_erp_idx = headers.index("Default ERP Vendor") if "Default ERP Vendor" in headers else 5
            
            for row in reader:
                if len(row) > max(vendor_idx, def_erp_idx):
                    v_name = row[vendor_idx].strip()
                    d_erp = row[def_erp_idx].strip()
                    if v_name:
                        active_vendors_map[v_name] = d_erp

    vendors_to_process = []
    with open(VENDORS_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            erp_id = row.get("ERP Vendor ID", "").strip()
            pkg = row.get("Integration Package", "").strip()
            if not erp_id: continue
            
            pkg_clean = "INTACCT" if "INTACCT" in pkg.upper() else "YARDI" if "YARDI" in pkg.upper() else ""
            if pkg_clean:
                raw_name = row.get("Vendor Name", "").strip()
                # Try getting the exact match or a left-stripped match (some have leading spaces)
                def_erp = active_vendors_map.get(raw_name, active_vendors_map.get(raw_name.lstrip(), ""))
                
                vendors_to_process.append({
                    "erp_id": erp_id, 
                    "package": pkg_clean, 
                    "raw_name": raw_name,
                    "default_erp": def_erp,
                    "address": row.get("Address", "").strip(),
                    "city": row.get("City", "").strip(),
                    "zip": row.get("Zip", "").strip()
                })

    fieldnames = ["integrationPackage", "vendorCode", "vendor", "vendorType", "vendorAddress", "status", "verifier", "defaultErpVendor", "details"]
    
    if not VALIDATED_CSV.exists() or VALIDATED_CSV.stat().st_size == 0:
        with open(VALIDATED_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
    if not INVALID_CSV.exists() or INVALID_CSV.stat().st_size == 0:
        with open(INVALID_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    batch_size = 25
    total = len(vendors_to_process)
    
    # Sync the profile before launching Playwright
    sync_profile_copy()
    
    with sync_playwright() as playwright:
        # Launch using the synced local automation profile
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(AUTOMATION_USER_DATA_DIR),
            headless=False,
            channel="chrome",
            args=[
                f"--disable-extensions-except={EXTENSION_PATH}",
                f"--load-extension={EXTENSION_PATH}",
                "--start-maximized", 
                "--no-first-run", 
                "--no-default-browser-check"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("Navigating to Nexus...")
        page.goto(url)
        page.wait_for_timeout(2000)

        if page.locator("input[type='password']").count() > 0:
            print("Logging in...")
            page.locator("input[type='text'], input[type='email']").first.fill(username)
            page.locator("input[type='password']").first.fill(password)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

        print("Clicking on 'Image Management'...")
        image_management_btn = page.locator("text='Image Management'").first
        image_management_btn.wait_for(state="visible", timeout=20000)
        image_management_btn.click()
        page.wait_for_timeout(4000)

        print("Clicking 'Select All' and 'Index Selected'...")
        # Wait for either the header checkbox or the row checkbox to appear
        page.wait_for_selector(f".x-column-header-checkbox, .x-grid-hd-checker, .x-column-header .x-grid-checkcolumn, {selectors['queue']['row_tick_box']}", timeout=20000)
        
        select_all_checkbox = page.locator(".x-column-header-checkbox, .x-grid-hd-checker, .x-column-header .x-grid-checkcolumn").first
        if select_all_checkbox.is_visible():
            select_all_checkbox.click()
        else:
            page.locator(selectors["queue"]["row_tick_box"]).first.click()
            
        page.wait_for_timeout(1000)
        page.locator(selectors["queue"]["index_selected"]).first.click()

        page.wait_for_selector(selectors["page_header"], timeout=15000)
        print("Indexing screen ready.")

        for i in range(0, total, batch_size):
            batch = vendors_to_process[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            
            LOG_DIR.mkdir(exist_ok=True)
            log_path = LOG_DIR / f"vendor_harvest_batch_{batch_num:02d}_{datetime.now():%Y%m%d_%H%M}.log"
            
            write_log(log_path, "=" * 60)
            write_log(log_path, f"STARTING BATCH {batch_num} (Records {i+1} to {min(i+batch_size, total)} of {total})")
            write_log(log_path, "=" * 60)

            results = []

            for v in batch:
                pkg = v["package"]
                write_log(log_path, f"\nProcessing: ERP ID '{v['erp_id']}' | Raw Name '{v['raw_name']}'")
                
                pkg_input = page.locator(selectors["fill"]["integration_package"]).first
                pkg_input.click()
                pkg_input.press("Control+a")
                pkg_input.press("Delete")
                pkg_input.type(pkg, delay=30)
                try:
                    page.locator(selectors["dropdown_item_selector"]).filter(has_text=pkg).first.click(timeout=2000)
                except Exception:
                    pass
                time.sleep(1)

                found = False
                extracted_data = None
                search_terms = [v["erp_id"], v["raw_name"]]
                
                for term in search_terms:
                    write_log(log_path, f"  -> Searching by: '{term}'")
                    found, extracted_data = attempt_search(page, selectors, log_path, term)
                    if found:
                        break
                        
                # 3. Interactive Fallback
                if not found:
                    write_log(log_path, "  -> Auto-Healing Failed. Prompting user...")
                    print(f"\n[NOT FOUND] ERP: {v['erp_id']} | Name: {v['raw_name']}")
                    while True:
                        print("  Options:")
                        print("    1) Search by Vendor Code")
                        print("    2) Search by Vendor Name")
                        print("    3) Mark Inactive & Skip")
                        choice = input("  >>> Choose 1, 2, or 3 (or press Enter to skip): ").strip()
                        
                        if choice == '1':
                            user_term = input("  >>> Enter Vendor Code: ").strip()
                            write_log(log_path, f"  -> User manual search by Code: '{user_term}'")
                            found, extracted_data = attempt_search(page, selectors, log_path, user_term)
                            if found: break
                            print("  ...still not found. Try another?")
                        elif choice == '2':
                            user_term = input("  >>> Enter Vendor Name: ").strip()
                            write_log(log_path, f"  -> User manual search by Name: '{user_term}'")
                            found, extracted_data = attempt_search(page, selectors, log_path, user_term)
                            if found: break
                            print("  ...still not found. Try another?")
                        elif choice == '3':
                            write_log(log_path, f"  -> User marked vendor as Inactive")
                            mark_vendor_inactive_in_csv(v["erp_id"])
                            break
                        elif not choice:
                            # Just skip if they press Enter empty
                            break
                
                if found:
                    v_code, v_name, v_type, v_addr, d_city, d_zip = extracted_data
                    verifier, details = verify_data(v, pkg, v_code, v_name, v_addr, d_city, d_zip)
                    
                    if v_name.lower().strip() != v["raw_name"].lower().strip():
                        write_log(log_path, f"  -> Saving Alias: '{v['raw_name']}' -> '{v_name}'")
                        append_alias(v["raw_name"], v_name)

                    write_log(log_path, f"  -> Extracted: Code='{v_code}', Type='{v_type}'")
                    write_log(log_path, f"  -> Verifier: {verifier} | Details: {details}")
                    
                    results.append({
                        "integrationPackage": pkg, "vendorCode": v_code, "vendor": v_name,
                        "vendorType": v_type, "vendorAddress": v_addr, "status": "FOUND",
                        "verifier": verifier, "defaultErpVendor": v["default_erp"], "details": details
                    })
                else:
                    write_log(log_path, "  -> Final Status: NOT FOUND")
                    results.append({
                        "integrationPackage": pkg, "vendorCode": v["erp_id"], "vendor": v["raw_name"],
                        "vendorType": "", "vendorAddress": "", "status": "NOT FOUND",
                        "verifier": "FALSE", "defaultErpVendor": v["default_erp"], "details": "Vendor not found in dropdown."
                    })

            # Write to separate files based on Verifier status
            with open(VALIDATED_CSV, "a", newline="", encoding="utf-8-sig") as f_val, \
                 open(INVALID_CSV, "a", newline="", encoding="utf-8-sig") as f_inv:
                 
                val_writer = csv.DictWriter(f_val, fieldnames=fieldnames)
                inv_writer = csv.DictWriter(f_inv, fieldnames=fieldnames)
                
                for r in results:
                    if r["verifier"] == "TRUE":
                        val_writer.writerow(r)
                    else:
                        inv_writer.writerow(r)

            issues = [r for r in results if r["status"] == "NOT FOUND" or r["verifier"] == "FALSE"]
            write_log(log_path, "=" * 60)
            write_log(log_path, f"BATCH {batch_num} SUMMARY: {len(batch)} processed. {len(batch)-len(issues)} Perfect, {len(issues)} with Issues.")
            if issues:
                write_log(log_path, "--- DETAILED ISSUES ---")
                for iss in issues:
                    if iss["status"] == "NOT FOUND":
                        write_log(log_path, f"  [NOT FOUND] ERP ID: {iss['vendorCode']} | Name: {iss['vendor']}")
                    else:
                        write_log(log_path, f"  [MISMATCH] ERP ID: {iss['vendorCode']} | Name: {iss['vendor']} -> {iss['details']}")
            write_log(log_path, "=" * 60)
            
            print(f"\nBatch {batch_num} finished. Check {log_path.name} for details.")
            if i + batch_size < total:
                cmd = input(">>> Press [Enter] to process the next batch of 25, or 'q' to quit: ")
                if cmd.strip().lower() == 'q':
                    print("Exiting.")
                    break
            else:
                print("All batches complete!")

        context.close()

if __name__ == "__main__":
    main()
