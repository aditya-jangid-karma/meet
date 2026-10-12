"""
selector_recorder.py -- learn the field names on an invoice entry screen.

WHAT THIS IS FOR (plain English):
    To type into the "Invoice Number" box, a script needs that box's internal
    name inside the page's code -- something like id="invoiceNum". You cannot
    see that name on screen, and a screenshot will not show it.

    So instead of guessing, you index one invoice by hand and this program
    watches which boxes you use and writes their names down.

WHAT IT RECORDS:
    The box's id, name, aria-label, the visible label next to it, and the
    order you used them in.

    Also, since 2026-08-13, four things needed to target the image QUEUE rather
    than just the indexing form:
      class_list  the element's CSS classes. ExtJS keeps its meaning here --
                  x-grid-item, x-grid-checkcolumn -- which is how a row's
                  tick box becomes findable at all.
      tooltip     data-qtip (ExtJS's own tooltip attribute) or title. This is
                  the ONLY place the label of an icon-only button exists.
                  "Index Selected" is invisible to every other attribute.
      ancestors   tag + classes of the 3 enclosing elements. STRUCTURE ONLY,
                  never their text. Lets a tick box be described by where it
                  sits ("the checker cell in a grid row") instead of by an id
                  that will not exist next time.
      id_stem     "shared-button-process-1353" minus the moving number. Only
                  filled in when the stem has 3+ words, because "textfield"
                  would match every text box on the page.

    Clicks are captured on ANY element from that date. ExtJS draws grid rows
    and tick boxes as plain divs, so the old input/button/link-only rule threw
    every click on the queue away.

WHAT IT NEVER RECORDS:
    What you TYPE. Not one character. It also refuses password boxes outright,
    in code -- see isPassword() in the JavaScript below. Your Bottomline
    password and your clients' invoice figures never touch disk.

    THE LOGIN SCREEN IS NEVER RECORDED AT ALL. The watching code is not even
    loaded into the browser until you say so. While you are logging in there
    is nothing listening -- not a disabled listener, not a filtered one.
    Nothing. Your username box is never seen.

WHAT IT NEVER DOES:
    It never types for you, never clicks for you, never submits anything and
    never presses Save. It only watches. You drive.

HOW TO USE IT:
    1. Run it (command at the bottom of this comment).
    2. A browser window opens. Log into Bottomline in that window YOURSELF,
       and navigate to an invoice, ready to index it.
       NOTHING IS BEING RECORDED YET.
    3. Come back to this black command window and press ENTER.
       Recording starts at that moment.
    4. Go back to the browser and index the invoice exactly as normal.
    5. When you are finished, just CLOSE the browser window.
    6. It writes selectors_recorded.json next to this script.

    python selector_recorder.py "https://your-bottomline-address"

    You can also point it at any ordinary web page with a form to check the
    program works before using it on the real system.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

# Playwright downloaded its copy of Chrome into the project folder rather than
# into your Windows user folder. This line tells it where to look. It must be
# set BEFORE playwright is imported, which is why the import sits below it.
BROWSERS_DIR = PROJECT / ".browsers"
if BROWSERS_DIR.exists():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS_DIR))

from playwright.sync_api import sync_playwright  # noqa: E402  (see note above)

OUTPUT_FILE = HERE / "selectors_recorded.json"
BACKUP_FILE = HERE / "selectors_recorded.prev.json"

# This JavaScript is injected into every page and every frame. It listens for
# you clicking or typing into something and reports back WHAT the thing is.
# It never reads .value, so what you type is never available to it.
LISTENER_JS = r"""
(() => {
  if (window.__idxRecorderInstalled) return;
  window.__idxRecorderInstalled = true;

  const MAX = 80;
  const clean = s => (s || "").replace(/\s+/g, " ").trim().slice(0, MAX);

  // Hard refusal. Anything that could be a password is dropped before we look
  // at it at all -- not filtered later, not written and removed. Dropped here.
  function isPassword(el) {
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (type === "password") return true;
    const auto = (el.getAttribute("autocomplete") || "").toLowerCase();
    if (auto.includes("password") || auto.includes("one-time-code")) return true;
    // Catch boxes that only LOOK like text, e.g. a "show password" toggle that
    // flips type="password" to type="text". Over-blocking here is harmless --
    // an invoice field is never going to be named "pwd" or "secret".
    const hint = (
      (el.id || "") + " " +
      (el.getAttribute("name") || "") + " " +
      (el.getAttribute("aria-label") || "")
    ).toLowerCase();
    return ["password", "passwd", "pwd", "secret", "otp", "mfa"].some(w => hint.includes(w));
  }

  function labelFor(el) {
    try {
      if (el.labels && el.labels.length) return clean(el.labels[0].innerText);
      const wrapping = el.closest("label");
      if (wrapping) return clean(wrapping.innerText);
      if (el.id) {
        const byFor = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
        if (byFor) return clean(byFor.innerText);
      }
      const labelled = el.getAttribute("aria-labelledby");
      if (labelled) {
        const target = document.getElementById(labelled);
        if (target) return clean(target.innerText);
      }
    } catch (e) {}
    return "";
  }

  // Bottomline is built on ExtJS, which invents ids like "textfield-1752-inputEl"
  // fresh on every page load. Anything with a long number in it is assumed
  // generated and therefore untrustworthy as a permanent address.
  function looksGenerated(id) {
    return /\d{3,}/.test(id || "");
  }

  // Not every generated id is equally useless. ExtJS builds them as
  // <meaningful stem>-<counter>, so "shared-button-process-1353" is really
  // "shared-button-process" plus a number that moves. The stem survives page
  // loads and gives us a handle on icon buttons that have no text at all.
  //
  // Only trusted when the stem has 3+ words. "textfield-1752-inputEl" reduces
  // to "textfield", which every text box on the page would match -- worse than
  // useless, because it looks specific.
  function idStem(id) {
    if (!id) return "";
    let stem = id.replace(/-inputEl$/, "").replace(/-\d+$/, "");
    if (/\d/.test(stem)) return "";
    if ((stem.match(/-/g) || []).length < 2) return "";
    return stem;
  }

  function classesOf(el) {
    // getAttribute, not .className -- on an SVG element .className is not a
    // string and would throw.
    return clean(el.getAttribute("class") || "");
  }

  // ExtJS puts its tooltips in data-qtip, not title. This is where the label
  // of an icon-only button lives -- "Index Selected" is invisible to every
  // other attribute we capture.
  function tooltipOf(el) {
    return clean(el.getAttribute("data-qtip") || el.getAttribute("title") || "");
  }

  // The three enclosing elements, as tag + classes. STRUCTURE ONLY, never text.
  // This is what lets a grid row's checkbox be described as "the checker cell
  // inside a grid row" rather than by an id that will not exist next time.
  function ancestry(el) {
    const out = [];
    let node = el.parentElement;
    for (let depth = 0; node && depth < 3; depth++) {
      const tag = node.tagName.toLowerCase();
      const cls = (node.getAttribute("class") || "")
        .split(/\s+/).filter(Boolean).slice(0, 3).join(".");
      out.push(cls ? tag + "." + cls : tag);
      node = node.parentElement;
    }
    return out;
  }

  function suggest(el) {
    const tag = el.tagName.toLowerCase();
    const name = el.getAttribute("name");
    const aria = el.getAttribute("aria-label");
    // "name" first: on this site it is hand-authored and stable
    // (Image_Index_Ref), while the id is not.
    if (name) return tag + '[name="' + name + '"]';
    if (el.id && !looksGenerated(el.id)) return "#" + el.id;
    if (aria) return tag + '[aria-label="' + aria + '"]';
    // Last resort before giving up: an ExtJS tooltip. Weak, because it is
    // display text and would change if Bottomline reworded it -- but a real
    // handle on a button that has nothing else.
    const tip = tooltipOf(el);
    if (tip) return '[data-qtip="' + tip + '"]';
    return "";
  }

  // Clicks and typing are treated differently ON PURPOSE.
  //   typing -> real form fields only. Nothing else can be typed into, and
  //             keeping this list tight keeps the password guard meaningful.
  //   clicks -> anything, because ExtJS renders grid rows, checkboxes and
  //             toolbar buttons as plain divs. The old code only accepted
  //             input/select/textarea/button/a, so every click on the queue
  //             grid was silently dropped.
  const TYPE_TAGS = ["input", "select", "textarea"];
  const CLICK_TAGS = ["input", "select", "textarea", "button", "a"];

  // A click usually lands on an inner span or div with nothing on it. Walk up
  // a few levels to whatever is actually addressable. Returns null if there is
  // nothing worth recording, which is how ordinary background clicks are
  // discarded instead of filling the file with noise.
  function addressable(el) {
    let node = el;
    for (let depth = 0; node && node.tagName && depth < 5; depth++) {
      const tag = node.tagName.toLowerCase();
      if (CLICK_TAGS.includes(tag)) return node;
      if (node.getAttribute("data-qtip")) return node;
      if (node.getAttribute("role") === "button") return node;
      const cls = node.getAttribute("class") || "";
      if (/x-grid-|x-column-header|x-tab\b|x-btn|x-checkbox|checker/.test(cls)) return node;
      node = node.parentElement;
    }
    return null;
  }

  function report(el, how) {
    try {
      if (!el || !el.tagName) return;
      if (typeof window.__recordField !== "function") return;

      if (how === "typed into") {
        if (!TYPE_TAGS.includes(el.tagName.toLowerCase())) return;
      } else {
        el = addressable(el);
        if (!el) return;
      }

      // Stays the FIRST thing checked once we know which element we are on.
      // Nothing below this line runs for a password, OTP or MFA box.
      if (isPassword(el)) return;

      const tag = el.tagName.toLowerCase();

      // Focusing a button or link is not "typing into" it. Without this,
      // buttons get labelled "typed into" and confuse the review step.
      if (tag === "button" || tag === "a") how = "clicked";

      window.__recordField({
        how: how,
        tag: tag,
        type: el.getAttribute("type") || "",
        id: el.id || "",
        name: el.getAttribute("name") || "",
        aria_label: el.getAttribute("aria-label") || "",
        placeholder: el.getAttribute("placeholder") || "",
        label_text: labelFor(el),
        button_text: (tag === "button" || tag === "a") ? clean(el.innerText) : "",
        // --- added 2026-08-13 so the queue grid can be targeted ---
        class_list: classesOf(el),
        tooltip: tooltipOf(el),
        ancestors: ancestry(el),
        id_stem: idStem(el.id),
        // ----------------------------------------------------------
        suggested_selector: suggest(el),
        // Kept so the review step can see WHY a selector was chosen, and can
        // spot a field whose only address is an id that will not survive.
        id_looks_generated: looksGenerated(el.id),
        in_frame: (window.top !== window.self)
      });
    } catch (e) {}
  }

  document.addEventListener("focusin", e => report(e.target, "typed into"), true);
  document.addEventListener("click",   e => report(e.target, "clicked"), true);
})();
"""


def main():
    parser = argparse.ArgumentParser(
        description="Record which fields you use on an invoice entry screen."
    )
    parser.add_argument("url", help="Web address to open (or a local file:// path).")
    args = parser.parse_args()

    seen = {}
    fields = []

    def record_field(info):
        """Called by the page each time you click or type into something."""
        # tooltip and class are part of the key because the queue toolbar is a
        # row of icon buttons with no text and no name. Without them, "Index
        # Selected" and the delete bin could collapse into a single entry.
        key = (
            info.get("id", ""),
            info.get("name", ""),
            info.get("suggested_selector", ""),
            info.get("button_text", ""),
            info.get("tooltip", ""),
            info.get("class_list", ""),
        )
        if key in seen:
            seen[key]["times_used"] += 1
            return

        info["times_used"] = 1
        info["order"] = len(fields) + 1
        seen[key] = info
        fields.append(info)

        shown = (
            info.get("label_text")
            or info.get("button_text")
            or info.get("tooltip")      # icon-only buttons show up here
            or info.get("id")
            or info.get("name")
            or info.get("class_list")
            or "(unnamed)"
        )
        selector = info.get("suggested_selector") or "(NO STABLE NAME -- see note at the end)"
        print(f"  [{info['order']:>2}] {info['how']:<11} {shown:<30} ->  {selector}")

    print("\n" + "=" * 70)
    print("  STEP 1  --  RECORDING IS OFF")
    print("=" * 70)
    print("  A browser window is opening now.")
    print("  Log in YOURSELF, then open an invoice, ready to index it.")
    print()
    print("  Nothing is being recorded during this. The watching code is not")
    print("  even loaded into the browser yet, so your username and password")
    print("  cannot be seen.")
    print()
    print("  When the invoice is on screen, come back HERE and press ENTER.")
    print("=" * 70 + "\n")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()

        # Defining the function is harmless -- nothing calls it until the
        # listener is loaded, and the listener is not loaded until you say so.
        context.expose_function("__recordField", record_field)

        page = context.new_page()
        page.goto(args.url)

        # ---- STEP 1: log in. No listener exists yet. ----
        # This blocks until you press Enter. That is fine and deliberate:
        # there is nothing to listen with, so there is nothing to miss.
        try:
            input("Press ENTER once you are logged in with an invoice open... ")
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled before recording started. Nothing was written.")
            try:
                browser.close()
            except Exception:
                pass
            sys.exit(1)

        if not browser.is_connected() or page.is_closed():
            print("\nThe browser was closed before recording started. Nothing was written.")
            sys.exit(1)

        # ---- STEP 2: load the listener and start recording. ----
        # Two injections are needed:
        #   add_init_script  -- covers any page or frame loaded FROM NOW ON
        #   frame.evaluate   -- covers the page and frames already on screen
        # Without the second, nothing on the invoice screen already in front
        # of you would be picked up.
        context.add_init_script(LISTENER_JS)

        installed = 0
        for frame in page.frames:
            try:
                frame.evaluate(LISTENER_JS)
                installed += 1
            except Exception:
                pass  # a cross-origin frame we are not allowed into

        print("\n" + "=" * 70)
        print(f"  STEP 2  --  RECORDING IS ON   (watching {installed} frame(s))")
        print("=" * 70)
        print("  Index the invoice as normal. Close the browser when finished.")
        print("  This program never types for you and never presses Save.")
        print("=" * 70)
        print("\nFields, as you use them:\n")

        # Idle here until you close the window. Waiting through Playwright
        # (rather than input()) is deliberate -- it keeps the connection to the
        # browser pumping, so the lines above appear live as you work.
        try:
            while browser.is_connected() and not page.is_closed():
                page.wait_for_timeout(500)
        except KeyboardInterrupt:
            print("\nStopped from the keyboard. Saving what was captured so far.")
        except Exception:
            pass  # the window was closed -- that is the normal way to finish

        try:
            browser.close()
        except Exception:
            pass

    if not fields:
        print("\nNothing was captured. Nothing was written.")
        print("Most likely one of these:")
        print("  - ENTER was pressed AFTER the indexing was already done.")
        print("    Press ENTER first, then fill the boxes.")
        print("  - The invoice form sits in a frame this program is not")
        print("    allowed to read. Say so -- that needs a different approach.")
        sys.exit(1)

    # Keep the previous capture rather than silently replacing it.
    if OUTPUT_FILE.exists():
        BACKUP_FILE.write_text(OUTPUT_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    payload = {
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "source": args.url,
        "fields": fields,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nRecorded {len(fields)} field(s).")
    print(f"Written to: {OUTPUT_FILE}")
    if BACKUP_FILE.exists():
        print(f"Previous capture kept at: {BACKUP_FILE}")
    print("\nNothing you typed was saved -- only the names of the boxes.")

    nameless = [f for f in fields if not f.get("suggested_selector")]
    if nameless:
        print(
            f"\nNOTE: {len(nameless)} field(s) had no stable name of their own "
            "(no id, no name, no aria-label).\n"
            "Those are fragile and need flagging when this file is reviewed."
        )

    # An id stem is only useful if it identifies ONE thing. In an earlier capture
    # "Convert to Invoice" was shared-button-generictextbutton-1780 and "Save as
    # Exception" was shared-button-generictextbutton-1778 -- the same stem. A
    # selector built on that stem could press either one, and one of them is on
    # the never-click list. This warning exists so that is never a surprise.
    stems = {}
    for field in fields:
        stem = field.get("id_stem")
        if stem:
            stems.setdefault(stem, []).append(field)

    shared = {stem: found for stem, found in stems.items() if len(found) > 1}
    if shared:
        print("\n" + "!" * 70)
        print("  WARNING -- these id stems match MORE THAN ONE element:")
        for stem, found in shared.items():
            labels = [
                f.get("button_text") or f.get("tooltip") or f.get("id") or "(unnamed)"
                for f in found
            ]
            print(f"    {stem}-  ->  {', '.join(labels)}")
        print()
        print("  Do NOT build a selector on these stems. It would be ambiguous,")
        print("  and an ambiguous click on this screen can press a button that")
        print("  is on the never-click list.")
        print("!" * 70)

    if any(f.get("in_frame") for f in fields):
        print(
            "\nNOTE: some fields sit inside an embedded sub-page (an iframe).\n"
            "The filling script will need to target that frame, not just the page."
        )


if __name__ == "__main__":
    main()
