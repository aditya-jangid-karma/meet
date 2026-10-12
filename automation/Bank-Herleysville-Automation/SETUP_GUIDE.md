# Harleysville Bank Statement Automation — Setup Guide (New Device)

This guide explains how to set up the automation on a **different Windows PC / user account**.
The main script is `Automation_Updated-code_bank-herleysville.py`.

> **What it does:** logs into Harleysville Bank online, pulls each account's transactions for
> the target date range, exports them to `.xls`, and consolidates everything into one
> master workbook (`HSB MM.DD.YYYY.xlsx`). MFA one-time codes are read automatically from a
> Gmail inbox that receives the bank's SMS codes.

---

## 1. Prerequisites

Install these on the new machine first:

| Requirement | Notes |
|---|---|
| **Windows 10/11** | The script is optimized for Windows paths. |
| **Python 3.10+** | Tick **"Add Python to PATH"** during install. Verify: `python --version` |
| **Google Chrome** | Must be the real Chrome (script uses `channel="chrome"`), signed in normally at least once. |
| **Access to the OTP Gmail inbox** | The Google account that receives the bank's SMS one-time codes. You must be able to sign into it in a browser during the first run. |

---

## 2. Copy the project files

Copy the **whole folder** `Bank-Herleysville-Automation` to the new device (e.g., to the Desktop or Documents folder).

Files that must come along:

- `Automation_Updated-code_bank-herleysville.py`  ← the script
- `client_secrets_for_Bank-Herleysville-Automation.json`  ← Google OAuth client (reusable)
- `requirements.txt`

**Do NOT copy** `token.json` — that is this device's saved Gmail login. The new device will generate a fresh `token.json` on the first run (see step 5).

> ⚠️ `client_secrets_...json` and the bank password are **secrets**. Transfer the folder over a trusted channel (USB / secure drive), not public email.

---

## 3. Install Python dependencies

Open **PowerShell** in the project folder and run:

```bash
pip install -r requirements.txt
```

Playwright uses your installed Google Chrome automatically. If you ever see a browser-launch error, run:

```bash
python -m playwright install chromium
```

---

## 4. Configuration (No code edits required!)

The script is fully dynamic. It auto-detects your Windows username, saves output directly to `C:\Users\<YourUser>\Desktop\Bank_Statements`, and finds its own credentials file automatically. **You do not need to edit any paths in the Python code.**

### Bank credentials

The bank username/password are read from environment variables, falling back to values hardcoded in the script. **Recommended:** set them as environment variables instead of typing them into the script file. 

In PowerShell (to set them permanently for your user):

```bash
setx HARLEYSVILLE_USER "DMCAccounting"
setx HARLEYSVILLE_PASS "your-bank-password-here"
```
*(Note: Restart your PowerShell window after running `setx` for the variables to take effect).*

If you prefer, you can temporarily edit `BANK_USER` and `BANK_PASS` at the top of the python script, but remember to remove the password before sharing the file.

---

## 5. First run — Gmail authorization

The **first** time the script runs on the new device it will open a browser asking you to sign into the **OTP Gmail account** and grant read-only Gmail access. Approve it. This creates `token.json` so future runs are completely automatic.

Notes:
- Sign in with the **same Gmail inbox** that receives the bank's SMS codes.
- If Google shows an "unverified app" screen, choose **Advanced → Go to … (unsafe)** — this is your own internal OAuth app.
- There is a manual fallback: if the Gmail fetch fails, the script will pause and prompt you to type the 6-digit code by hand in the console.

---

## 6. Run it

From the project folder in PowerShell:

```bash
python .\Automation_Updated-code_bank-herleysville.py
```

Output goes to `C:\Users\<USERNAME>\Desktop\Bank_Statements\<Month-Year>\`:
- one raw `.xls` per account,
- the consolidated master file `HSB MM.DD.YYYY.xlsx`,
- `execution_summary.log`, `progress.json`, and `end_balances.json`.

### Date range logic (automatic)
- Run on/after the 16th → current month's **1st–15th**.
- Run on the 1st–15th → the **entire previous month**.

---

## 7. Resiliency & Re-running behavior

- **Browser Preservation:** The script runs in its own isolated automation profile. It **will not** close or interfere with your existing Chrome windows while you work.
- **Crash Recovery:** If the Harleysville portal crashes or forcefully drops the connection during a download, the script will automatically recover the downloaded file, restart the background browser, and continue working without you needing to intervene.
- **Resume Capability:** The script tracks finished accounts in `progress.json` and **skips** them if you re-run it.
- **Force a Full Re-run:** Delete the progress file for that month:
  ```bash
  del "C:\Users\<USERNAME>\Desktop\Bank_Statements\<Month-Year>\progress.json"
  ```
- **File Locking:** If you leave the master `HSB ....xlsx` workbook open in Excel, the script detects the lock and saves the new data to a timestamped file (e.g., `HSB 08.31.2026_172545...xlsx`) instead of crashing.

---

## 8. Checklist for the new device

- [ ] Python 3.10+ installed and added to PATH
- [ ] Google Chrome installed
- [ ] Project folder copied (script + client_secrets + requirements.txt), **without** token.json
- [ ] `pip install -r requirements.txt` run in PowerShell
- [ ] Bank password set via `setx` environment variable
- [ ] First run completed + Gmail authorized (token.json created)
- [ ] Confirmed output workbook + logs generated successfully
