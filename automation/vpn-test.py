import subprocess
import time
import requests
import pyautogui
from playwright.sync_api import sync_playwright

# Path to Proton VPN executable on Windows
PROTON_VPN_PATH = r"C:\Users\Meet Patel\Downloads\ProtonVPN_v5.1.7_x64.exe" 

def verify_ip_location():
    """Queries ipapi.co to detect current public IP and country code."""
    try:
        res = requests.get("https://ipapi.co/json/", timeout=8)
        data = res.json()
        country = data.get("country_code")
        ip = data.get("ip")
        print(f"  [IP Check] Current IP: {ip} | Country: {country}")
        return country
    except Exception as e:
        print(f"  [IP Check Failed] {e}")
        return None


def force_connect_us_protonvpn(max_attempts=10):
    """
    Launches/Focuses Proton VPN GUI and clicks 'Change server' 
    until a US IP address is acquired.
    """
    print("[VPN] Opening/Focusing Proton VPN...")
    subprocess.Popen([PROTON_VPN_PATH])
    time.sleep(3)

    for attempt in range(1, max_attempts + 1):
        country = verify_ip_location()
        
        if country == "US":
            print("[VPN SUCCESS] Connected to a United States endpoint!")
            return True

        print(f"[VPN Attempt {attempt}/{max_attempts}] Current location is {country}. Triggering 'Change server'...")

        # Bring Proton VPN window to focus via shortcut
        pyautogui.hotkey('win', 'down') # minimize others if needed
        
        # NOTE: You can refine coordinates based on your screen resolution
        # Or use image matching: pyautogui.click('change_server_button.png')
        # Standard shortcut inside Proton VPN to switch server:
        pyautogui.hotkey('ctrl', 'shift', 'c') 

        print("[VPN] Waiting 12 seconds for reconnect...")
        time.sleep(12)

    raise TimeoutError("Could not acquire a US server after maximum attempts.")


def run_sop_workflow():
    with sync_playwright() as p:
        # Browser traffic automatically routes through system Proton VPN
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            print("\n[SOP 1/3] Accessing portal & performing login...")
            page.goto("https://example-us-website.com/login", timeout=30000)
            page.fill("input[name='email']", "meet.patel@kgsoffice.com")
            page.fill("input[name='password']", "a=L[t^d;IgmU+]Js")
            page.click("button[type='submit']")

            page.wait_for_selector(".dashboard", timeout=20000)
            print("[SOP 1/3] Login verified.")

            print("[SOP 2/3] Extracting required data...")
            page.goto("https://example-us-website.com/target-page")
            page.wait_for_selector(".data-table")

            rows = page.locator(".data-table tr").all_text_contents()
            print(f"Scraped {len(rows)} items.")

            print("[SOP 3/3] Performing operational step...")
            page.click("#execute-btn")
            print("Operation completed successfully!")

        except Exception as e:
            print(f"[ERROR] Workflow failed: {e}")
            page.screenshot(path="proton_error.png")

        finally:
            browser.close()


if __name__ == "__main__":
    # Required installation: pip install pyautogui requests playwright
    try:
        if force_connect_us_protonvpn(max_attempts=8):
            run_sop_workflow()
    except Exception as err:
        print(f"[ABORT] Pipeline stopped: {err}")