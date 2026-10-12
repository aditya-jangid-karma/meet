# # import os
# # import time
# # from playwright.sync_api import sync_playwright

# # # Setup download directory
# # DOWNLOAD_DIR = os.path.abspath("./downloaded_invoices")
# # os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# # def run_invoice_downloader(url, username, password, requires_otp=False):
# #     with sync_playwright() as p:
# #         # Launch browser (set headless=True for background server execution)
# #         browser = p.chromium.launch(headless=False, downloads_path=DOWNLOAD_DIR)
        
# #         # Create a browser context with custom download behavior
# #         context = browser.new_context(accept_downloads=True)
# #         page = context.new_page()

# #         print(f"Navigating to {url}...")
# #         page.goto(url)

# #         # 1. Fill in Login Credentials (Adjust selectors to match target site)
# #         print("Logging in...")
# #         page.fill("input[name='username']", username)  # Replace CSS selector
# #         page.fill("input[name='password']", password)  # Replace CSS selector
# #         page.click("button[type='submit']")            # Replace CSS selector

# #         # 2. Handle OTP / Captcha (Human-in-the-loop if needed)
# #         if requires_otp:
# #             print("\n[ACTION REQUIRED] OTP / Captcha detected.")
# #             print("Please enter the code in the opened browser window...")
# #             # Wait up to 2 minutes for manual entry and dashboard redirect
# #             page.wait_for_selector(".dashboard-container", timeout=120000) 
# #         else:
# #             page.wait_for_selector(".dashboard-container", timeout=30000)

# #         # 3. Navigate to Invoice / Download Section
# #         print("Navigating to invoice section...")
# #         page.goto(f"{url}/invoices") # Adjust URL path as needed

# #         # 4. Trigger and Save File Download
# #         print("Initiating download...")
# #         with page.expect_download() as download_info:
# #             # Click the download button on the website
# #             page.click("button#download-latest-invoice") # Replace CSS selector

# #         download = download_info.value
        
# #         # Save to target folder with customized name
# #         saved_file_path = os.path.join(DOWNLOAD_DIR, download.suggested_filename)
# #         download.save_as(saved_file_path)
# #         print(f"Successfully saved file to: {saved_file_path}")

# import os
# import time
# from playwright.sync_api import sync_playwright

# DOWNLOAD_DIR = os.path.abspath("./downloaded_invoices")
# os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# def run_invoice_downloader(url, username, password, requires_otp=False):
#     with sync_playwright() as p:
#         # Launch browser with arguments to bypass bot detection blocks
#         browser = p.chromium.launch(
#             headless=False,  # Keep visible so you can see what's happening
#             args=[
#                 "--disable-blink-features=AutomationControlled",
#                 "--start-maximized",
#                 "--no-sandbox",
#                 "--disable-infobars"
#             ],
#             downloads_path=DOWNLOAD_DIR
#         )
        
#         # Create context with realistic viewport and user agent
#         context = browser.new_context(
#             viewport={"width": 1920, "height": 1080},
#             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
#             accept_downloads=True
#         )
        
#         # Inject script to hide automation footprint
#         context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
#         page = context.new_page()

#         print(f"Navigating to {url}...")
#         try:
#             # Increased timeout to 60 seconds and set load state to 'domcontentloaded'
#             page.goto(url, timeout=60000, wait_until="domcontentloaded")
#             print("Page loaded successfully!")
#         except Exception as e:
#             print(f"Failed to load page: {e}")
#             browser.close()
#             return

#         browser.close()

# if __name__ == "__main__":
#     # Example Configuration
#     WEBSITE_URL = "https://www.swgas.com"
#     USER = "ACCOUNTING@COARECOMMUNITIES.COM"
#     PASS = "@Sharidon21"
    
#     run_invoice_downloader(
#         url=WEBSITE_URL, 
#         username=USER, 
#         password=PASS, 
#         requires_otp=True  # Set to False for fully automated sites
#     )





import os
import time
from playwright.sync_api import sync_playwright

# Setup download directory
DOWNLOAD_DIR = os.path.abspath("./downloaded_invoices")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def run_invoice_downloader(url, username, password, requires_otp=False):
    with sync_playwright() as p:
        # Launch browser with anti-detection arguments to bypass bot filters
        browser = p.chromium.launch(
            headless=False,  # Keep visible so you can monitor the process and handle security checks
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-infobars"
            ],
            downloads_path=DOWNLOAD_DIR
        )
        
        # Create context with realistic viewports and user agent
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            accept_downloads=True
        )
        
        # Hide automation footprint properties from browser injection
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = context.new_page()

        print(f"Navigating to login portal: {url}")
        try:
            # Using 'commit' wait state to prevent connection timeouts on heavy security firewalls
            page.goto(url, timeout=60000, wait_until="commit")
            
            # Allow the single-page application and security scripts time to render
            print("Waiting for page elements to render...")
            time.sleep(6)
        except Exception as e:
            print(f"Failed to load page: {e}")
            browser.close()
            return

        # 1. Fill in Username and Password using visible form placeholders
        print("Entering credentials...")
        try:
            # Wait for input fields to be visible on screen
            page.wait_for_selector("input[placeholder='Username']", timeout=15000)
            
            # Fill credentials explicitly
            page.locator("input[placeholder='Username']").fill(username)
            page.locator("input[placeholder='Password']").fill(password)
            
            print("Credentials entered successfully. Clicking LOG IN...")
            # Click the submit button
            page.locator("button:has-text('LOG IN')").click()
            
        except Exception as e:
            print(f"Error interacting with login form fields: {e}")

        # 2. Handle OTP / MFA / Cloudflare Security Challenge
        if requires_otp:
            print("\n[ACTION REQUIRED] Multi-Factor Authentication (OTP) or Security Check detected.")
            input("Please complete any verification or login steps in the browser window, then press Enter *here in the terminal* once you reach your dashboard...")

        # 3. Proceed to Invoice / Download Section (Modify paths/clicks as needed for your dashboard)
        print("Successfully reached dashboard stage. Proceeding with workflow...")
        time.sleep(5) 

        browser.close()

if __name__ == "__main__":
    # Direct endpoint for Southwest Gas MyAccount login portal
    LOGIN_URL = "https://myaccount.swgas.com/Portal/#/login"
    USER = "ACCOUNTING@COARECOMMUNITIES.COM"
    PASS = "@Sharidon21"
    
    run_invoice_downloader(
        url=LOGIN_URL, 
        username=USER, 
        password=PASS, 
        requires_otp=True  # Pauses execution so you can clear verification/OTP manually
    )