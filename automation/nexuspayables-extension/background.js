// background.js

// Replace this URL with the Google Apps Script Web App URL after deployment
const GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyr7zXZTLlKzzu3mBdYTidht-i-MZFplqGQ1wrfsKxMdtY8K5ye7O7Em_zhRhfwBEv6og/exec";

// Shows a short-lived colored badge on the toolbar icon so the user gets
// visual confirmation of a save without opening the console.
//   "…" (grey)   = sending
//   "✓" (green)  = saved to the sheet
//   "!" (red)    = failed / rejected / not configured
function setBadge(tabId, text, color, title) {
    const target = (typeof tabId === "number") ? { tabId } : {};
    try {
        chrome.action.setBadgeText({ ...target, text });
        if (color) chrome.action.setBadgeBackgroundColor({ ...target, color });
        if (title) chrome.action.setTitle({ ...target, title });
    } catch (e) {
        console.warn("NexusPayables Extension: could not set badge.", e);
    }
}

// Clears the badge after a delay so it doesn't linger permanently.
function clearBadgeLater(tabId, ms = 5000) {
    setTimeout(() => setBadge(tabId, "", null, "NexusPayables Capturer"), ms);
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "saveToSheet") {
        console.log("NexusPayables Extension: Received data to save.", request.data);

        const tabId = sender.tab && sender.tab.id;

        // Check if URL is configured
        if (!GOOGLE_SCRIPT_URL || GOOGLE_SCRIPT_URL === "YOUR_GOOGLE_APPS_SCRIPT_WEB_APP_URL_HERE") {
            console.error("NexusPayables Extension Error: Google Script URL is not configured. Please update background.js.");
            setBadge(tabId, "!", "#c0392b", "NexusPayables: Script URL not configured");
            clearBadgeLater(tabId);
            sendResponse({ ok: false, reason: "not_configured" });
            return true;
        }

        // Sending…
        setBadge(tabId, "…", "#7f8c8d", "NexusPayables: saving…");

        fetch(GOOGLE_SCRIPT_URL, {
            method: 'POST',
            body: JSON.stringify(request.data),
            headers: {
                'Content-Type': 'text/plain;charset=utf-8' // Text/plain avoids CORS preflight issues for GAS
            }
        })
        .then(response => response.text())
        .then(data => {
            // The Apps Script returns "Success", "Ignored: ...", or "Error: ...".
            const ok = /^success/i.test((data || "").trim());
            if (ok) {
                console.log("NexusPayables Extension: Successfully saved to Google Sheets.", data);
                setBadge(tabId, "✓", "#27ae60", "NexusPayables: saved to sheet");
            } else {
                console.warn("NexusPayables Extension: Save was not successful.", data);
                setBadge(tabId, "!", "#c0392b", "NexusPayables: not saved — " + (data || "").slice(0, 80));
            }
            clearBadgeLater(tabId);
            sendResponse({ ok, data });
        })
        .catch(error => {
            console.error("NexusPayables Extension Error: Failed to save to Google Sheets.", error);
            setBadge(tabId, "!", "#c0392b", "NexusPayables: request failed");
            clearBadgeLater(tabId);
            sendResponse({ ok: false, error: String(error) });
        });

        return true; // Keep message channel open for the async sendResponse above
    }

    if (request.action === "captureIncomplete") {
        // Fields were missing, so nothing was sent. Show a red badge as feedback.
        const tabId = sender.tab && sender.tab.id;
        console.warn("NexusPayables Extension: capture incomplete, nothing sent.", request.data);
        setBadge(tabId, "!", "#c0392b", "NexusPayables: missing fields — not saved");
        clearBadgeLater(tabId);
    }
});
