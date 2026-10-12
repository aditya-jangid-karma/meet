# NexusPayables Invoice Capturer Chrome Extension

This extension captures invoice data from the NexusPayables platform and saves it directly to a Google Sheet. It works quietly in the background and respects user operations, only capturing and transmitting data when the "Convert to Invoice" button is clicked. It will ignore empty entries.

## Setup Instructions

### 1. Set up the Google Sheet and Apps Script Endpoint
To save data to a Google Sheet without setting up complex OAuth inside the extension, we use a simple Google Apps Script Web App.

1. Create a new Google Sheet (e.g., at `sheets.google.com`).
2. Copy the URL of your new Google Sheet.
3. Go to [Google Apps Script](https://script.google.com/) and create a "New project".
4. Copy the contents of the `Code.gs` file in this folder and paste it into the editor, replacing everything.
5. In the script, replace `"YOUR_GOOGLE_SHEET_URL_HERE"` with the URL you copied in step 2.
6. Click the blue **Deploy** button at the top right, and select **New deployment**.
7. Click the gear icon next to "Select type" and choose **Web app**.
8. Under "Execute as", select **Me**.
9. Under "Who has access", select **Anyone**.
10. Click **Deploy**. (You may need to "Review permissions" -> select your account -> Advanced -> "Go to script (unsafe)").
11. Copy the resulting **Web app URL**.

### 2. Configure the Extension
1. Open the `background.js` file in this directory.
2. Find the line: `const GOOGLE_SCRIPT_URL = "YOUR_GOOGLE_APPS_SCRIPT_WEB_APP_URL_HERE";`
3. Replace the placeholder string with the Web app URL you copied in the previous step. Save the file.

### 3. Load the Extension in Chrome
1. Open Google Chrome.
2. Type `chrome://extensions/` into the URL bar and hit Enter.
3. Turn on **Developer mode** (toggle switch in the top right corner).
4. Click the **Load unpacked** button in the top left.
5. Select this folder (`nexuspayables-extension`) which contains the `manifest.json`.

### 4. How to Use
1. Navigate to the NexusPayables website and open an image to be indexed (as seen in Image 3).
2. Use the application normally.
3. The extension operates automatically in the background. It mimics your requirement to fetch the Property/Vendor addresses implicitly.
4. When you click the **"Convert to Invoice"** button, the extension intercepts the data and sends it to your Google Sheet.
5. **Note:** If the form is completely empty, the extension respects your rule and will *not* push empty data to the Excel/Sheets file.

### Important Note on Selectors
Since NexusPayables is a proprietary system, the HTML structure might change or differ slightly. The `content.js` script uses heuristic lookups (looking for labels like "Property Code" and grabbing the adjacent input). If the website uses complex Div-based inputs or iFrames, the `getInputValue()` logic in `content.js` might need slight adjustments by a developer with access to inspect the live page.
