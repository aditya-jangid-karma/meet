# NexusPayables Invoice Capturer — Session Handoff

_Last updated: 2026-09-08_

## What this project is
A Chrome extension (Manifest V3) that scrapes invoice fields from the Bottomline
NexusPayables AP site (`residentialone.nexuspayables.com`) and POSTs them to a
Google Apps Script web app, which appends a row to a Google Sheet.

**Files** (in `C:\Users\Meet Patel\Desktop\automation\nexuspayables-extension`):
- `content.js` — runs on the Nexus page: detects triggers, reads fields + address popups, sends data.
- `background.js` — service worker: does the `fetch()` POST to Apps Script, sets the toolbar badge.
- `Code.gs` — the Google Apps Script (`doPost`) that writes to the Sheet. **Deployed copy is what runs, not this file.**
- `manifest.json` — permissions + content-script registration.
- `mock_nexus.html` — local test page mimicking the form.
- `README.md` — setup instructions.

## Data flow
```
User clicks "Convert to Invoice" OR "Vendor Address"
  → content.js handleConvert(trigger)
      1. gatherVisibleData()  reads the 6 form fields via getInputValue()
      2. if essentials (vendorCode/vendor/propertyCode/property) blank → stop, red badge
      3. captureAddresses(trigger)  READ-ONLY: reads any address popup already open
      4. sendToBackground({action:"saveToSheet", data})
  → background.js fetch(GOOGLE_SCRIPT_URL, POST text/plain JSON)
  → Code.gs doPost() → appendRow() to the Sheet
Badge: "…" sending, "✓" green success, "!" red fail/missing/misconfigured (auto-clears 5s)
```

## Captured fields
`integrationPackage, propertyCode, property, propertyAddress, vendorCode, vendor, vendorType, vendorAddress`

## Design decisions locked in by the user (do NOT regress these)
1. **Two triggers**: clicking **"Convert to Invoice"** OR **"Vendor Address"** both save to the sheet.
2. **Do NOT change the website's behavior.** The script must NEVER open, close, hide, or
   otherwise touch any popup. It only *reads* popups the site itself opened. (Earlier
   attempts that auto-clicked/force-closed modals left popups stuck and broke the UI — all
   removed. Do not reintroduce `forceCloseModal`, suppressor CSS, global Escape, or
   backdrop-hiding.)
3. Runs in the background without interrupting the user's session.
4. Address format required: `Name (Code)` + street lines + `City, ST ZIP`, with the
   heading line and the trailing **phone number** line stripped (see `extractAddressFromModal` + `isPhoneLine`).
5. A re-entrancy guard `isCapturing` prevents overlapping runs.

## CURRENT OPEN ISSUE — blank Google Sheet (unresolved)
The extension **is capturing and sending correctly** — the page console shows
`Data looks good! Sending to Google Sheets...` with the full data object.
The data is being **rejected on the Google side**; nothing lands in the Sheet.

### Diagnostic already wired up
`content.js` `sendToBackground()` now logs the Apps Script reply to the PAGE console:
```
NexusPayables Extension: Google Sheets response → {ok: …, data: "…"}
```
Meaning of `data`:
- `"Success"` → a row WAS written (then check you're looking at the right sheet/tab).
- `"Error: ..."` → `openByUrl` failed → wrong URL or authorization not granted.
- `"Ignored: ..."` → doPost thinks a field is missing.
- No response / error → background worker or deployment URL problem.

### NEXT STEPS to resolve (start here in the new session)
1. Ask the user to reload the extension (`chrome://extensions/` refresh) **and refresh the
   Nexus tab**, click Vendor Address, and paste the `Google Sheets response →` line.
2. Most likely fixes on the Apps Script side:
   - `Code.gs` line 16 `SPREADSHEET_URL` must be the real sheet URL. Local file is now set to
     `https://docs.google.com/spreadsheets/d/1dLoiGdSDHXrKLLTolpwKXh4s69XG877gU9ijbgwl8UQ/edit`
     — **but the DEPLOYED Apps Script must have this too.**
   - Deploy → Manage deployments → edit → **Version: New version** → Deploy (editing code
     without a new version keeps serving old code).
   - "Who has access" must be **Anyone** (not "Anyone with Google account").
   - Run `doPost`/authorize once to grant Sheet permission.
3. `background.js` `GOOGLE_SCRIPT_URL` (line 4) must point to that deployment's `/exec` URL.
   Current value is a real deployed URL:
   `https://script.google.com/macros/s/AKfycbyK12C8o-henXWtc-iBNNsSVUxMM0odlg4IDdLl3Zd477mDnzQ3oZK-P_LOhNqwXdU9/exec`
   Verify it matches the *current* deployment.

## Known secondary issue (not yet addressed)
When the trigger fires on an INCOMPLETE form (blank vendor/property), the site still opens
its own Vendor Address popup (user's click) — the script correctly does nothing to it, but
the popup is the site's normal behavior. This is expected and fine per decision #2.

## Environment / reminders
- Windows 11, Git Bash available. Files under `Desktop\automation\nexuspayables-extension`.
- **Reload ritual after ANY content.js/background.js change**: refresh the extension card at
  `chrome://extensions/`, THEN refresh the Nexus tab (or you hit "extension context
  invalidated" — `sendToBackground` guards this and warns to refresh).
- Real Nexus DOM specifics learned: address popup is a `role="dialog"`-style modal with a
  header "Vendor Address"/"Property Address" and a "Close dialog" (×) button. Address text
  format confirmed e.g. `American Pest Management (4339-001) / 6940 Columbia Gateway Drive /
  #250 / Columbia, MD 21046 / (301) 891-2600`.
- `getInputValue()` capture of the 6 fields IS working on the live site (confirmed via console).

## Quick verification commands
```bash
cd "C:/Users/Meet Patel/Desktop/automation/nexuspayables-extension"
node --check content.js && node --check background.js && echo OK
```
