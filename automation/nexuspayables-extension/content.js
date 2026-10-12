// content.js

// This script runs inside the NexusPayables page (content script context).
console.log("NexusPayables Extension: Content script loaded.");

let capturedData = {
    integrationPackage: "",
    propertyCode: "",
    property: "",
    propertyAddress: "",
    vendorCode: "",
    vendor: "",
    vendorType: "",
    vendorAddress: ""
};

// Safely sends a message to the background worker. After the extension is
// reloaded, an already-injected content script loses chrome.runtime, so calling
// sendMessage directly throws "Cannot read properties of undefined". This guards
// that case and tells the user to refresh the page.
function sendToBackground(message) {
    try {
        if (!chrome || !chrome.runtime || !chrome.runtime.id) {
            console.warn("NexusPayables Extension: extension was reloaded — please REFRESH this page to reconnect.");
            return;
        }
        chrome.runtime.sendMessage(message, (response) => {
            if (chrome.runtime.lastError) {
                console.warn("NexusPayables Extension: message error —", chrome.runtime.lastError.message);
                return;
            }
            // Logs the Apps Script reply so we can see exactly what the sheet did:
            // { ok:true, data:"Success" } means a row was written; anything else
            // (e.g. data starting with "Error:" or "Ignored:") explains a blank sheet.
            console.log("NexusPayables Extension: Google Sheets response →", response);
        });
    } catch (e) {
        console.warn("NexusPayables Extension: could not reach background (refresh the page).", e);
    }
}

// Guard so a capture already in progress cannot be re-triggered. This is
// essential because captureAddresses() programmatically clicks the
// "Vendor Address" button, which is itself a trigger — without this flag that
// would loop forever.
let isCapturing = false;

// Use event delegation to catch the click anywhere on the document.
// This bypasses issues where the button is dynamically re-rendered or isn't a strict <button> tag.
// The pipeline is triggered by EITHER the "Convert to Invoice" button OR the
// "Vendor Address" button — clicking either one runs the capture-and-save flow.
document.addEventListener('click', (e) => {
    let target = e.target;
    let trigger = null;

    // Bubble up the DOM tree to see if they clicked a trigger button (or an icon inside it).
    while (target && target !== document && target.tagName) {
        const text = (target.textContent || "").trim();
        const val = (target.value || "").trim();
        if (text.includes('Convert to Invoice') || val.includes('Convert to Invoice')) {
            trigger = 'Convert to Invoice';
            break;
        }
        if (text.toLowerCase() === 'vendor address' || val.toLowerCase() === 'vendor address') {
            trigger = 'Vendor Address';
            break;
        }
        target = target.parentNode;
    }

    if (!trigger) return;

    // Ignore if a capture is already running (also blocks our own synthetic
    // clicks on the address buttons from re-entering the pipeline).
    if (isCapturing) {
        console.log("NexusPayables Extension: capture already in progress, ignoring '" + trigger + "' click.");
        return;
    }

    console.log("NexusPayables Extension: '" + trigger + "' clicked — starting capture!");
    // Run the capture pipeline. We intentionally do NOT block the user's own click.
    handleConvert(trigger);
}, true); // Use capture phase to ensure we intercept it even if Nexus stops propagation

// Orchestrates the full capture. Runs entirely in the BACKGROUND — the script's
// own address lookups are invisible so the user is never interrupted. We read the
// visible fields first and bail if essentials are missing (no popups at all).
// `trigger` is either "Convert to Invoice" or "Vendor Address".
async function handleConvert(trigger) {
    // Lock so no other click (including our own synthetic address-button clicks)
    // can start a second run while this one is going.
    isCapturing = true;
    try {
        // 1. Read the visible form fields first (no modals, no side effects).
        gatherVisibleData();

        // 2. If the essentials are blank, stop here. Do NOT open any address popup.
        const isMissingData = !capturedData.vendorCode || !capturedData.vendor || !capturedData.propertyCode || !capturedData.property;
        if (isMissingData) {
            console.warn("NexusPayables Extension: Form is missing essential data (like Vendor). Not storing in Excel — and NOT opening address popups. Captured:\n" + JSON.stringify(capturedData, null, 2));
            sendToBackground({ action: "captureIncomplete", data: capturedData });
            return;
        }

        // 3. Record is real — grab both addresses silently in the background, then
        //    wait for them to finish. Never interrupts the user's own work.
        try {
            await captureAddresses(trigger);
        } catch (e) {
            console.error("NexusPayables Extension: address capture failed, sending without addresses.", e);
        }

        // 4. Send.
        console.log("NexusPayables Extension: Data looks good! Sending to Google Sheets...", capturedData);
        sendToBackground({ action: "saveToSheet", data: capturedData });
    } finally {
        // Always release the lock, even if something above threw.
        isCapturing = false;
    }
}

function gatherVisibleData() {
    // Helper to find input by its preceding label or placeholder (adjust selectors based on actual DOM)
    // Assuming structure based on standard form frameworks (e.g. label next to input)
    capturedData.integrationPackage = getInputValue("Integration Package");
    capturedData.propertyCode = getInputValue("Property Code");
    capturedData.property = getInputValue("Property");
    capturedData.vendorCode = getInputValue("Vendor Code");
    capturedData.vendor = getInputValue("Vendor");
    capturedData.vendorType = getInputValue("Vendor Type");
}

function getInputValue(labelText) {
    try {
        const cleanTarget = labelText.toLowerCase().replace(/[^a-z0-9]/g, '');
        // Use XPath to find elements containing the label text.
        const xpath = `//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '${labelText.toLowerCase()}')]`;
        const snapshot = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
        
        let labelNode = null;
        for (let i = snapshot.snapshotLength - 1; i >= 0; i--) {
            let node = snapshot.snapshotItem(i);
            if (node.tagName !== 'SCRIPT' && node.tagName !== 'STYLE' && node.textContent.trim().length < 50) {
                const cleanNodeText = node.textContent.toLowerCase().replace(/[^a-z0-9]/g, '');
                // Strict match to prevent "Vendor" from accidentally matching "Vendor Code:"
                if (cleanNodeText === cleanTarget) {
                    labelNode = node;
                    break;
                }
            }
        }

        if (labelNode) {
            // Attempt 1a: a real <label for="..."> pointing straight at the field.
            const labelEl = labelNode.closest ? labelNode.closest('label') : null;
            const forId = labelEl && labelEl.getAttribute('for');
            if (forId) {
                const target = document.getElementById(forId);
                const v = readFieldValue(target);
                if (v) return v;
            }

            // Attempt 1b: walk up and grab the nearest value-bearing field.
            let parent = labelNode.parentElement;
            let depth = 0;
            while (parent && depth < 6) {
                // Text inputs, selects, textareas and custom contenteditable widgets;
                // ignore checkboxes, radios, buttons and hidden fields.
                const fields = Array.from(parent.querySelectorAll(
                    'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="button"]):not([type="submit"]), select, textarea, [contenteditable="true"]'
                ));
                if (fields.length > 0 && fields.length <= 3) {
                    const v = readFieldValue(fields[fields.length - 1]);
                    if (v) return v;
                }
                parent = parent.parentElement;
                depth++;
            }
        }
    } catch (e) {
        console.error("NexusPayables Extension: XPath error for", labelText, e);
    }

    // Attempt 2: match by placeholder or aria-label on any text-like field.
    const cleanTarget = labelText.toLowerCase().replace(/[^a-z0-9]/g, '');
    const allInputs = document.querySelectorAll('input[type="text"], input:not([type]), select, textarea, [contenteditable="true"]');
    for (let input of allInputs) {
        const ph = (input.placeholder || "").toLowerCase().replace(/[^a-z0-9]/g, '');
        const aria = (input.getAttribute && input.getAttribute('aria-label') || "").toLowerCase().replace(/[^a-z0-9]/g, '');
        if ((ph && ph === cleanTarget) || (aria && aria === cleanTarget)) {
            const v = readFieldValue(input);
            if (v) return v;
        }
    }
    return "";
}

// Reads a value from any supported field type: <input>/<select>/<textarea>
// expose .value; custom contenteditable widgets expose their text instead.
function readFieldValue(el) {
    if (!el) return "";
    if (typeof el.value === 'string' && el.value.trim() !== "") return el.value.trim();
    const txt = (el.innerText || el.textContent || "").trim();
    return txt;
}

// READ-ONLY address capture — never opens, closes, or touches any popup, so the
// website's own behavior is completely unchanged. It only reads address popups
// that are ALREADY open on screen:
//  - On a "Vendor Address" click the site itself opens the vendor popup; we wait
//    briefly for it to appear, then read it.
//  - Any other address popup that happens to be open right now is read too.
// Nothing is ever opened or closed by the script.
async function captureAddresses(trigger) {
    if (trigger === 'Vendor Address') {
        // The site is opening the vendor popup because of this click — wait a
        // moment for it to render, then read it (without touching it).
        await readVisibleAddress('vendorAddress', 'Vendor Address', 2500);
    }

    // Grab whatever address popups are open at this instant (no waiting, no opening).
    grabIfOpen('vendorAddress', 'Vendor Address');
    grabIfOpen('propertyAddress', 'Property Address');
}

// If an address popup with this heading is currently open, read it into
// capturedData. Does nothing (and opens nothing) if it is not on screen.
function grabIfOpen(key, heading) {
    const modal = findAddressModal(heading);
    if (modal) {
        const text = extractAddressFromModal(modal, heading);
        if (text) capturedData[key] = text;
    }
}

// Waits (up to maxWait ms) for an address popup with this heading to be open,
// then reads it — WITHOUT opening or closing anything. Resolves as soon as it is
// read, or when the wait elapses.
function readVisibleAddress(key, heading, maxWait) {
    maxWait = maxWait || 2500;
    return new Promise((resolve) => {
        let waited = 0;
        const step = 60;
        const poll = setInterval(() => {
            waited += step;
            const modal = findAddressModal(heading);
            const text = modal ? extractAddressFromModal(modal, heading) : "";
            if (modal && text) {
                capturedData[key] = text;
                clearInterval(poll);
                resolve();
            } else if (waited >= maxWait) {
                clearInterval(poll);
                resolve();
            }
        }, step);
    });
}

// Finds the address popup by its heading text, then climbs to the dialog ROOT
// so we can close/hide the whole popup (header + × button + backdrop), not just
// the inner text box. Works without knowing Bottomline's exact modal class.
function findAddressModal(heading) {
    const h = heading.toLowerCase();
    const candidates = document.querySelectorAll('[role="dialog"], .modal, .popup, .modal-content, .modal-body, div, section');

    // 1. Tightest visible element whose text starts with the heading = the popup content.
    let tight = null;
    let tightLen = Infinity;
    for (const el of candidates) {
        if (!isVisible(el)) continue;
        const txt = (el.innerText || "").trim();
        if (!txt || txt.length > 600) continue; // skip page-sized wrappers
        if (txt.toLowerCase().startsWith(h) && txt.length < tightLen) {
            tight = el;
            tightLen = txt.length;
        }
    }
    if (!tight) return null;

    // 2. Climb to the OUTERMOST dialog container so the header's close ("×")
    //    button is included when we look for it (it often sits in a header that
    //    is a sibling of the inner text box, not inside it).
    let root = tight;
    let node = tight.parentElement;
    for (let i = 0; i < 12 && node; i++) {
        const role = ((node.getAttribute && node.getAttribute('role')) || '').toLowerCase();
        const cls = (node.className && node.className.toString ? node.className.toString() : '').toLowerCase();
        if (role === 'dialog' || role === 'alertdialog' || /modal|dialog|popup/.test(cls)) {
            root = node; // keep going up to catch an even outer dialog wrapper
        }
        node = node.parentElement;
    }
    return root;
}

function isVisible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && el.offsetParent !== null;
}

// Extracts the address block from a specific modal element in the required format:
//   Name (Code)
//   <street lines>
//   City, ST ZIP
// The heading line and the trailing phone-number line are stripped out.
function extractAddressFromModal(modal, heading) {
    if (!modal) return "";

    let lines = (modal.innerText || "")
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0);

    // Drop lone close glyphs ("X", "×", "✕", "✖").
    lines = lines.filter(l => !['x', '×', '✕', '✖'].includes(l.toLowerCase()));

    // Drop the heading line ("Vendor Address" / "Property Address") if present.
    if (heading && lines.length && lines[0].toLowerCase() === heading.toLowerCase()) {
        lines.shift();
    }

    // Drop the last line if it is a phone number (per requirement).
    if (lines.length && isPhoneLine(lines[lines.length - 1])) {
        lines.pop();
    }

    return lines.join('\n');
}

// True for lines like "(301) 891-2600" or "301-891-2600": mostly phone chars
// with 7+ digits. Kept strict so a street/zip line isn't mistaken for a phone.
function isPhoneLine(text) {
    const digits = text.replace(/\D/g, '');
    return digits.length >= 7 && /^[\d\s()+.\-]+$/.test(text);
}
