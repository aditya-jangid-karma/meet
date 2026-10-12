import os
import time
from playwright.sync_api import sync_playwright

DOWNLOAD_DIR = os.path.abspath("./downloaded_invoices")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def run_firstenergy_automation(home_url, username, password):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Visible so you can track navigation & handle security checks if needed
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-infobars"
            ],
            downloads_path=DOWNLOAD_DIR
        )
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            accept_downloads=True
        )
        
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        print(f"Step 1: Navigating to home page: {home_url}")
        try:
            page.goto(home_url, timeout=60000, wait_until="commit")
            time.sleep(4)
        except Exception as e:
            print(f"Navigation error: {e}")

        # --- ROUTE DISCOVERY TO FIND LOGIN PAGE ---
        print("Step 2: Searching for login routes/endpoints on the page...")
        login_page_found = False
        
        # Direct check if login form is already present on current view
        if page.locator("input[id*='user' i], input[name*='user' i]").count() > 0:
            print("Login fields detected directly on the current page.")
            login_page_found = True
        else:
            # Look for navigation links containing 'Log In' or 'Sign In'
            possible_selectors = [
                "a:has-text('Log In')",
                "a:has-text('Sign In')",
                "a[href*='log_in']",
                "a[href*='login']",
                "text=Log In / Register"
            ]
            
            for selector in possible_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible(timeout=3000):
                        print(f"Found login route using selector: '{selector}'. Clicking through...")
                        element.click()
                        time.sleep(5)
                        login_page_found = True
                        break
                except:
                    continue
            
            # Fallback explicit route if element search fails
            if not login_page_found:
                print("Direct link click failed. Navigating directly to known FirstEnergy login endpoint...")
                page.goto("https://www.firstenergycorp.com/log_in.html", timeout=60000, wait_until="commit")
                time.sleep(5)

        # --- AUTOMATED LOGIN & RETRY LOOP ---
        login_successful = False
        attempt = 1

        while not login_successful:
            print(f"\n--- Login Attempt #{attempt} ---")
            try:
                print("Locating username and password inputs...")
                # Wait for user field to render
                user_field_selector = "input[id*='user' i], input[name*='user' i], input[placeholder*='Username' i], input[type='text']"
                pass_field_selector = "input[id*='pass' i], input[name*='pass' i], input[placeholder*='Password' i], input[type='password']"
                
                page.wait_for_selector(user_field_selector, timeout=15000)

                # Clear and input credentials
                page.locator(user_field_selector).first.fill("")
                page.locator(user_field_selector).first.fill(username)
                
                page.locator(pass_field_selector).first.fill("")
                page.locator(pass_field_selector).first.fill(password)
                
                print("Credentials entered. Submitting form...")
                # Find and click login button
                submit_btn = page.locator("button[type='submit'], input[type='submit'], button:has-text('LOG IN'), button:has-text('Sign In')").first
                submit_btn.click()

                # Evaluate outcome
                print("Waiting for response and checking next page load...")
                time.sleep(6)

                # Check for common error indicators on failure
                error_count = page.locator(".error-message, .alert-danger, :text('Invalid'), :text('incorrect')").count()
                
                if error_count > 0:
                    print(f"Login failed (Attempt #{attempt}): Invalid credentials or error message identified. Retrying...")
                    attempt += 1
                    time.sleep(3)
                    continue

                # If no error page, check if we need manual MFA/OTP intervention or reached the dashboard
                print("\n[SUCCESS / MFA CHECKPOINT] Form submitted successfully.")
                
                # Check if an OTP code prompt or dashboard element is present, or prompt user interactively if security blocks it
                if page.locator("input[placeholder*='code' i], text='Verification'").count() > 0:
                    input("MFA verification code requested by site. Complete it in the browser, then press Enter here...")
                
                login_successful = True
                print("Login sequence completed successfully! Dashboard loaded.")

            except Exception as e:
                print(f"Error encountered during login process (Attempt #{attempt}): {e}")
                print("Retrying login cycle...")
                attempt += 1
                time.sleep(5)
                try:
                    page.goto("https://www.firstenergycorp.com/log_in.html", timeout=30000, wait_until="commit")
                    time.sleep(3)
                except:
                    pass

        # Proceed to post-login tasks (e.g. pulling invoice data)
        print("Executing automated tasks on account dashboard...")
        time.sleep(5)
        browser.close()

if __name__ == "__main__":
    # HOME_URL = "https://www.firstenergycorp.com/fehome.html"
    HOME_URL = "https://b2clogin.firstenergycorp.com/d8077861-d8d1-43a9-82f7-65b6e0ecffad/oauth2/v2.0/authorize?p=B2C_1A_SIGNIN&response_type=code&client_id=2f79a955-d5e8-4456-a198-ae2a9ec4f5a9&scope=2f79a955-d5e8-4456-a198-ae2a9ec4f5a9%20openid%20offline_access&state=TVcxY1FCdHYyUXZPUUx1TWItV1FpYm1jN0lsZmZEdlBBcGRLSUUtS1NaOD18L2NvbnRlbnQvY3VzdG9tZXIvbXlfYWNjb3VudC5odG1sfHxudWxs&redirect_uri=https://www.firstenergycorp.com/login/customer/oauth2/code/&nonce=LCi4t_h1BS0zjR2wWizToC5QYIsOyQv6Xre7C_3DrQA"
    USER = "TriStateMHP"
    PASS = "@Coare2021"
    
    run_firstenergy_automation(
        home_url=HOME_URL,
        username=USER,
        password=PASS
    )