from playwright.sync_api import sync_playwright
from fp.fp import FreeProxy

# Automatically fetches a working US proxy IP
us_proxy_ip = FreeProxy(country_id=['US'], https=True).get()
print(f"Using US Proxy: {us_proxy_ip}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, proxy={"server": us_proxy_ip})
    page = browser.new_context().new_page()

    # Access the restricted website
    page.goto("https://www.swgas.com")
    print("Successfully accessed via script proxy!")
    browser.close()
