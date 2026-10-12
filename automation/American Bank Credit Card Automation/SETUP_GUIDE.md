# American Express Statement Automation — Setup Guide

This script logs into American Express, sets a custom date range (the previous week ending on Friday), filters by individual Card Members, explicitly excludes pending transactions, and exports a detailed PDF statement for each member using Chrome's silent printing.

---

## 1. Prerequisites

Install these on the target machine first:
* **Windows 10/11**: The script relies on Windows paths and commands (`taskkill`).
* **Python 3.10+**: Make sure to check **"Add Python to PATH"** during installation.
* **Google Chrome**: The script takes control of the local Google Chrome installation to use its printing engine.

---

## 2. Installation

Open **PowerShell** or **Command Prompt** in this folder and run:

```bash
# 1. Install required Python packages (Playwright)
pip install -r requirements.txt

# 2. Install Playwright browser dependencies (Crucial for first-time setup!)
python -m playwright install chromium
```

---

## 3. Configuration (Credentials)

The script uses environment variables for the Amex credentials to keep them secure. If they aren't set, it falls back to the default credentials hardcoded in the script.

To permanently set the credentials for your user account on a new machine, run these commands in PowerShell:

```bash
setx AMEX_USER_ID "your-amex-username"
setx AMEX_PASSWORD "your-amex-password"
```
*(Note: Restart your PowerShell window after running `setx` for the variables to take effect).*

---

## 4. Important Warning Before Running

⚠️ **Closes Chrome Automatically:** At the very start of the execution, the script runs a command to forcefully close any existing Google Chrome windows (`taskkill /F /IM chrome.exe`). 
**Please save your work and close Chrome before running the script**, otherwise it will force-close your browsing session.

---

## 5. How to Run

Run the script via PowerShell:

```bash
python American-Automation-fix-date-ready_backup_1788261753.py
```

### Where do the files go?
The script automatically saves the final PDFs into your **Downloads** folder under a subfolder named `Amex_Statements`:
`C:\Users\<YourUsername>\Downloads\Amex_Statements`

The filenames will look like:
`Amex Credit card-12005 Statement from MM-DD-YYYY to MM-DD-YYYY - [MemberName].pdf`

---

## 6. Troubleshooting

* **"Browser launch failed" or "Timeout"**: Run `python -m playwright install chromium` to ensure the backup browser is installed. Also, check Task Manager to ensure no ghost `chrome.exe` processes are stuck.
* **PDFs aren't downloading**: Ensure Google Chrome is installed. The script relies on Chrome's specific `--kiosk-printing` feature to bypass the Print dialog.
* **Missing "Pending" transactions in the final PDF**: This is intentional. The script specifically audits and unchecks any transaction marked as "Pending" before printing.
