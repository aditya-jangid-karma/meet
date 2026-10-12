# Invoice Indexer

**Types invoices from a spreadsheet into Bottomline Nexus, and stops before saving.**

Written for Team D. You do not need to be a programmer to run this, and you should not need to be one to maintain it either. Everything below is in plain English first.

---

## 1. What problem this solves

Indexing an invoice in Bottomline means keying the same seven facts into a web form: vendor, property, invoice number, invoice date, due date, amount, and which accounting system it feeds. About four to six minutes each, several hundred times a month, and every one of those minutes is spent typing something that already exists somewhere else.

This tool does the typing. You put the invoices in a spreadsheet, it fills the form. **You still press the buttons.**

### What it deliberately does NOT do

| It does not | Why |
|---|---|
| Press **Save** | A wrong value typed is nothing. A wrong value saved is a correction in a client's AP system. |
| Press **Convert to Invoice** | Same reason. It fills the indexing screen and stops there. |
| Read the invoice PDF | That is Phase 2 — see section 11. A human fills the spreadsheet today. |
| Decide GL coding | Bottomline has no GL field on this screen. Not in scope. |
| Work out which invoice is which | You confirm every row. It also checks the Image Name automatically — see section 5. |

---

## 2. Quick start

Four batch files sit in this folder. Double-click them; you never need a command prompt.

| File | What it does | Safe? |
|---|---|---|
| **1 - Dry Run (safe preview).bat** | Prints what it *would* type. No browser, no Bottomline, nothing touched. | Completely safe |
| **2 - Fill Invoices.bat** | The real thing. Opens Bottomline and fills forms. Never saves. | Touches the live system |
| **3 - Resume From A Row.bat** | Same, but starts partway down the list after a batch stopped. | Touches the live system |
| **4 - Re-record Bottomline Fields.bat** | Only when Bottomline changes its screen. See section 9. | Read-only; records nothing you type |

**The routine:** fill in `input\invoices.xlsx` → run **1** and read the output → run **2**.

Always run **1** first. It costs ten seconds and catches typos before they reach a client's system.

---

## 3. How it works

Three programs, joined by two files on disk.

```
  ┌──────────────────────────┐
  │  selector_recorder.py    │   Run rarely. Watches you index one invoice
  │  (learns the form)       │   by hand and writes down the internal names
  └───────────┬──────────────┘   of the boxes you used.
              │ writes
              ▼
      selectors_recorded.json     Raw evidence. Not used directly.
              │
              │ a human reads it and writes...
              ▼
        selectors.json            THE FIELD MAP. Which box is which.
              │
              │ read by
              ▼
  ┌──────────────────────────┐
  │  invoice_recorder.py     │◄── input\invoices.xlsx  (you fill this in)
  │  (does the typing)       │
  └───────────┬──────────────┘
              │ writes
              ▼
          logs\run_*.txt          A record of every run.
```

**Why the split?** The recorder knows nothing about invoices or spreadsheets. The filling script knows nothing about how the field map was made. Either can be replaced without touching the other.

---

## 4. The spreadsheet — `input\invoices.xlsx`

One row per invoice. Two tabs: **Invoices** (where you type) and **How to use** (a guide inside the file itself).

Columns are colour-coded:

| Colour | Meaning |
|---|---|
| **Blue** | The script types this into Bottomline. Required. |
| **Purple** | Image Name — the script *reads* this to confirm it is on the right document. |
| **Amber** | Integration Package. Leave blank and the script skips that box for you to set by hand. |
| **Grey** | For humans. The script ignores these entirely. |

### The Text format rule — the single most important thing in this file

Every data cell is formatted as **Text** on purpose. That is what stops Excel turning `2026-03-03` into a serial number, or dropping the `.00` off `312.00`. The script types what you see.

Excel will show a **green triangle** saying "number stored as text". That warning has been switched off inside the file, because clicking its "Convert to Number" button is the one action that quietly breaks everything.

**If a column does get reformatted anyway**, the script copes rather than failing silently:

- A **number** is typed with the same decimals Excel is showing. `496` displayed as `496.00` is typed as `496.00`.
- A **real date** stops the run. There is no way to guess which date format Bottomline wants, and guessing would put a wrong date on a client's invoice.
- It **prints a warning** naming any column that is no longer Text.

> ⚠️ **The one thing it cannot recover:** leading zeros. Invoice number `007458` stored as a number becomes `7458` before the script ever sees it. If your invoice numbers have leading zeros, that column must stay Text.

### A row counts as "used" when

Vendor, Invoice Number **or** Amount has a value. The pre-filled Row ID does not count, so you never need to delete it.

---

## 5. The two safety features

### The Image Name check

Before typing anything, the script reads the **Image Name** box on screen and compares it to the Image Name in your spreadsheet row. If they differ, it stops and offers to skip.

**Why this matters more than it sounds.** The invoices were bulk-imported, so their order in Bottomline has nothing to do with the order of your spreadsheet. Without this check, entering Ferguson's invoice against Apex's document would fill perfectly, error at nothing, and surface months later when somebody reconciled. This makes it structurally impossible rather than something you have to catch by eye.

The comparison forgives capitals and surrounding spaces, nothing else.

**Leave the Image Name blank** and the script says the safety check was skipped and carries on. That is allowed, but you lose the protection.

### It asks before every row

You see the whole row and press `y` before anything is typed.

---

## 6. Why it types instead of pasting

Vendor, Property and Integration Package are not plain text boxes. They are search boxes that show a dropdown, and **you have to pick from that dropdown for the underlying code to be stored.**

A dropdown only appears in response to real keystrokes. Setting the text in one go — what a paste does — fires no keystrokes, so no dropdown appears and no code is stored. The box would *look* filled and be empty underneath.

So the script types every field one character at a time, 45 ms apart, exactly as a person would.

### How dropdowns are handled

| Situation | What happens |
|---|---|
| Exactly one match | It picks it, and prints what it picked |
| No match | It stops, explains, and hands you the browser |
| Several matches | It lists them and hands you the browser |

When it hands over, you pick the right one yourself and press Enter to carry on.

---

## 7. The Python libraries, in plain English

| Library | What it is for |
|---|---|
| **Playwright** | Drives a real Chrome window — clicking, typing, reading what is on screen. It is what lets a script use a website the way a person does. Also downloads and manages its own copy of Chrome. |
| **openpyxl** | Reads `.xlsx` files. Used to pull each invoice row out of the spreadsheet, including each cell's format so numbers can be typed the way Excel shows them. |
| **python-dotenv** | Reads the `.env` file, where the Bottomline address, username and password live. Keeps credentials out of the code. |

All three are installed inside `.venv\` — a private folder just for this project. Nothing is installed onto Windows generally.

---

## 8. Technical notes for whoever maintains this

### Selectors use `name`, never `id`

Bottomline runs on **ExtJS**, a JavaScript framework that invents element ids at page-build time. A capture produced `#textfield-1752-inputEl` for Invoice Number. Those numbers are not stable.

The `name` attributes are hand-authored on Bottomline's side and are meaningful:

| Screen label | Selector used |
|---|---|
| Image Name: | `input[name="Image_Index_Name"]` (read only) |
| Vendor: | `input[name="Image_Index_VendorSite_Id"]` |
| Property: | `input[name="Property_Id"]` |
| Invoice Number: | `input[name="Image_Index_Ref"]` |
| Invoice Date: | `input[name="Image_Index_Invoice_Date"]` |
| Invoice Due Date: | `input[name="Image_Index_Due_Date"]` |
| Amount: | `input[name="Image_Index_Amount"]` |
| Integration Package: | `input[name="integration_package_id"]` |

**Never replace these with the `#` ids from a raw capture.** `selectors.json` says so in the file itself.

### The column-name guard

`selectors.json` keys must match spreadsheet headers, lower-cased with spaces turned into underscores. `Invoice Due Date` → `invoice_due_date`.

If a key has no matching column the script **refuses to start**. This exists because the failure is otherwise silent — a missing column looks exactly like an empty cell, so the field would be reported blank, skipped, and every invoice saved without it. That bug happened during development (`due_date` vs `invoice_due_date`) and the guard is what catches the next one.

### Things that are inferred, not observed

Three assumptions were made from how ExtJS normally behaves, not from anything captured. All three fail loudly rather than silently.

| Assumption | Symptom if wrong | Fix |
|---|---|---|
| Dropdown items have class `.x-boundlist-item` | "no dropdown match" on a vendor you know exists | Change `dropdown_item_selector` in `selectors.json` — right-click the dropdown, Inspect, read the real class |
| ExtJS commits a plain field on `change` + blur | A value looks typed but does not stick | Needs investigation in `commit_plain_field()` |
| Login form is the first text box + first password box | Login does not complete | Log in by hand; the script waits for you |

### The browser lives inside the project

Playwright normally downloads Chrome to `%USERPROFILE%\AppData\Local\ms-playwright`. Both scripts set `PLAYWRIGHT_BROWSERS_PATH` to `.browsers\` inside this folder **before importing Playwright**, so everything stays together. Deleting `Invoice_Indexer\` removes every trace from the PC.

### The green-triangle suppression is fragile

The `<ignoredErrors>` setting that hides Excel's "number stored as text" warning is written directly into the workbook's XML, because openpyxl accepts the instruction and silently discards it.

**Any openpyxl script that SAVES `invoices.xlsx` strips it out again.** `invoice_recorder.py` only ever reads the file, so normal use is safe. If you ever write a script that saves it, re-inject the snippet afterwards.

---

## 9. When something goes wrong

### "STOPPED: no field map found"
`selectors.json` is missing. Restore it, or re-record (section 9 below).

### "STOPPED: the field map and the spreadsheet do not agree"
A column was renamed, added or removed. The message names the mismatch. Fix either the header in Excel or the key in `selectors.json` so they use the same name.

### "STOPPED: the spreadsheet has no filled-in rows"
Nothing has Vendor, Invoice Number or Amount filled in.

### "STOPPED: you appear to be logged out"
The session expired mid-batch. It stops rather than typing invoice data into a login page. Log in again and use **3 - Resume From A Row** with the row number it printed.

### "STOPPED on row N: could not use the 'X' box"
Bottomline has moved or renamed a field. Nothing further was changed. Re-record (below), update `selectors.json`, then resume from row N.

### "cell X holds a real date, not text"
A date column was reformatted and Excel converted the value. Select that column → Format Cells → Text → retype the date.

### The dropdown never appears
Most likely `dropdown_item_selector` in `selectors.json` no longer matches. See section 8.

---

## 10. When Bottomline changes its screen

1. Run **4 - Re-record Bottomline Fields.bat** and paste your Bottomline address.
2. A browser opens. **Nothing is recorded yet.** Log in and open an invoice.
3. Come back to the black window and press **ENTER**. Only now does it start watching.
4. Index the invoice as normal, then close the browser.
5. It writes `automation\selectors_recorded.json` — the previous capture is kept as `selectors_recorded.prev.json`.
6. **A human must now read that file and update `automation\selectors.json`.** The recorder can report that a box is called `Image_Index_Ref`; only a person can confirm that means "Invoice Number."
7. Prefer the `name`-based selector every time.

**The recorder never records what you type**, and refuses password boxes outright — it drops anything whose type, autocomplete hint, or name suggests a password, one-time code or MFA field. The listener is not even loaded into the browser until you press ENTER, so the login screen is never seen at all.

---

## 11. Secrets and hard rules

| Rule | Detail |
|---|---|
| **`.env` is a secret** | Holds the Bottomline address, username and password. Never email it, never paste it into chat, never put it in a shared folder. |
| **`.bottomline_session.json` is a secret** | A saved login. Anyone holding it can act as you in Bottomline until it expires. Same treatment as the password. |
| **This project is local-only** | There is no git repository and none is planned. `.gitignore` exists purely as insurance. |
| **Logs contain client data** | Vendor names and invoice numbers. They live in `logs\` and are gitignored. |
| **The script never saves** | If a future change makes it press Save, that is a decision for the whole team, not a code tweak. |

### Creating `.env`

In Notepad, save a file called `.env` in this folder containing exactly:

```
BOTTOMLINE_URL=
BOTTOMLINE_USERNAME=
BOTTOMLINE_PASSWORD=
```

Your own values after each `=`. No quotes, no spaces around the `=`.

---

## 12. Setting up on a new PC

Open **Command Prompt** (not PowerShell) and run these in order:

```cmd
cd /d "C:\Users\<you>\Desktop\Res1\Invoice_Indexer"
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
set PLAYWRIGHT_BROWSERS_PATH=C:\Users\<you>\Desktop\Res1\Invoice_Indexer\.browsers
python -m playwright install chromium
```

⚠️ **No quotes around the path on the `set` line.** In Command Prompt, quotes become part of the value and the path breaks.

Check it worked:

```cmd
python -c "import playwright, openpyxl, dotenv; print('all three imported OK')"
```

Then create `.env` (section 11). The batch files handle everything after that.

---

## 13. What is not built

| Not built | Why |
|---|---|
| **Qwen reading the PDF (Phase 2)** | The spreadsheet is the seam. Something else can fill it later without changing anything here. |
| Pressing Save automatically | Deliberate. Revisit after the team has watched it work. |
| Multi-line GL splits | Bottomline has no GL field on this screen. |
| The screen after "Convert to Invoice" | Out of scope. The script stops before that button. |
| Retry / recovery | Only "stop and tell the human" is built, on purpose. |
| Automated tests | Verification is by observation at each checkpoint. |

---

## 14. File map

| Path | What it is |
|---|---|
| `1 - Dry Run (safe preview).bat` | Safe preview, no browser |
| `2 - Fill Invoices.bat` | The real run |
| `3 - Resume From A Row.bat` | Restart a batch partway |
| `4 - Re-record Bottomline Fields.bat` | Re-learn the form |
| `automation\selector_recorder.py` | Learns the field names |
| `automation\invoice_recorder.py` | Does the typing |
| `automation\selectors.json` | **The field map.** Hand-maintained. |
| `automation\selectors_recorded.json` | Raw capture. Evidence, not used directly. |
| `automation\selectors_recorded.prev.json` | The capture before that. |
| `automation\.bottomline_session.json` | **Secret.** Saved login. Created on first run. |
| `input\invoices.xlsx` | The invoices you fill in |
| `input\invoices.xlsx.bak` | Backup from the green-triangle fix. Safe to delete. |
| `logs\run_*.txt` | One per run. Contains client data. |
| `.env` | **Secret.** You create this. |
| `.venv\` | The private Python environment |
| `.browsers\` | Playwright's own copy of Chrome |
| `docs\specs\`, `docs\plans\` | Original design documents |
| `handoffs\` | Session notes |

---

*Last updated 2026-08-10. If you change how any of this works, change this file in the same sitting.*
