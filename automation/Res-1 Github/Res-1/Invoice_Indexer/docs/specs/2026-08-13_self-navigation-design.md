# Spec — Self-Navigation for the Invoice Indexer

**Date:** 2026-08-13
**Status:** ✅ SIGNED OFF 2026-08-13 — build may proceed
**Supersedes:** `docs/specs/2026-08-07_invoice-recording-design.md` (navigation sections only)

---

## 1. What this changes, in one paragraph

Today the script assumes a human has already opened an invoice for indexing. It
does not, so it never finds the Image Name box and every run stops. After this
change the script opens the queue itself, finds each invoice by name, opens it,
fills it, and waits for you. **It gains navigation, not authority** — it still
never presses Convert to Invoice, Save, Save as Exception or Delete.

---

## 2. The run, start to finish

1. Script logs in and opens **Images to be Indexed**.
2. It reads the queue **once**, paging through at 25 rows per page, and builds a
   list of `image name → which page it is on`.
3. For each row in your spreadsheet, in your row order:
   a. Find that image name in the list. Not there → skip it, report at the end.
   b. Go to its page, tick that row, press **Index Selected**.
   c. **Confirm the right invoice opened** (section 4). Wrong one → stop.
   d. Fill the seven boxes. Confirm the vendor and property codes loaded.
   e. Print "ready for your review" and wait.
4. You check every box by eye, press **Convert to Invoice**, complete the second
   screen, and press **Save** there.
5. You press **ENTER** in the black console window.
6. Script returns to the queue via the **Images to be Indexed** menu item and
   moves to your next row.

---

## 3. Decisions locked in this session

| # | Decision | Why |
|---|---|---|
| 1b | **You press ENTER when screen 2 is done.** Script waits indefinitely; Q quits. | Convert to Invoice opens a *second* screen — it does not return to the queue. The old "wait for the queue to reappear" signal does not exist. |
| 1b | Return to the queue via the **menu item**, not a stored address. Stored URL is the fallback. | The menu route was captured and observed working. The address bar was never confirmed to change between screens. |
| 1c | **Drop the 200-per-page step.** Page through at 25. | Its handle is a generated id (`combo-1329-inputEl`). It saves seconds once per run and sits on the same toolbar as the delete icon. Not worth it. |
| 1d | **`Image_Index_Name` is confirmed.** Verified live 2026-08-13 18:39. | Was an educated guess. Now observed, labelled "Image Name:". |

---

## 4. How the script proves it opened the right invoice

**Two independent checks. Both must pass before a single character is typed.**

1. **The page header** — `.top-page-header-text` must read `Image Index - <name>`.
   Wrong prefix means the indexing screen did not open at all.
2. **The Image Name box** — `input[name="Image_Index_Name"]` must equal the
   Image Name in the spreadsheet row.

**Why two.** The header proves *which screen* you are on; the box proves *which
invoice*. The delete icon sits on the same toolbar as Index Selected, so
"did the right thing actually happen" cannot be assumed.

### ✅ DECIDED 2026-08-13 — verify first, then retry, never fill blind

**Order of operations is fixed: check first, type second.** Nothing from the
spreadsheet is typed until both checks in this section have passed.

**If either check fails — mismatch, or the box cannot be read at all:**

1. Type nothing. Go back to the queue and search for that image name again.
2. Try **twice**. A grid that redrew under the click usually behaves on the
   second pass.
3. Still wrong after two attempts → **skip that row**, report it at the end of
   the run, and move to the next spreadsheet row.

**Why retry instead of stopping.** The likeliest cause of a mismatch is a
mechanical one — ExtJS redrew the queue and the tick landed on a neighbouring
row. That is worth one more attempt. It is not worth stranding a batch of forty.

**Why a cap.** Without one, an image whose name genuinely differs from the
spreadsheet would loop forever with nobody watching.

**Why skip rather than stop.** Consistent with the existing rule for an image
that is not in the queue at all. In both cases nothing has been typed, nothing
is half-done, and the run summary names every row that was left alone.

**The old behaviour is removed.** The script previously printed "safety check
skipped" and **filled anyway**. A safety feature that silently switches itself
off is worse than none, because the operator believes it is on.

---

## 5. Verified selectors

**All eight confirmed against the live screen on 2026-08-13** by `page_probe.py`.
Nothing below is inference.

### Boxes the script fills
| Field | Selector | Label on screen |
|---|---|---|
| Vendor | `input[name="Image_Index_VendorSite_Id"]` | Vendor: |
| Property | `input[name="Property_Id"]` | Property: |
| Invoice Number | `input[name="Image_Index_Ref"]` | Invoice Number: |
| Invoice Date | `input[name="Image_Index_Invoice_Date"]` | Invoice Date: |
| Invoice Due Date | `input[name="Image_Index_Due_Date"]` | Invoice Due Date: |
| Amount | `input[name="Image_Index_Amount"]` | Amount: |
| Integration Package | `input[name="integration_package_id"]` | Integration Package: |

### Boxes the script only reads
| Purpose | Selector |
|---|---|
| Which invoice is open | `input[name="Image_Index_Name"]` |
| Which screen is open | `.top-page-header-text` |
| Vendor code loaded? | `input[name="Image_Index_VendorSite_Id_Code"]` |
| Property code loaded? | `input[name="property_id_code"]` |

### Queue screen
| Control | Selector |
|---|---|
| Row tick box | `tr.x-grid-row` → `.x-grid-checkcolumn-cell-inner` |
| Index Selected | `a.process-comp-btn` |
| Next page | `.x-tbar-page-next` |
| Page number box | `input[name="inputItem"]` |
| Images to be Indexed menu | `a.x-menu-item-link` + its text |

### Never clicked
`Convert to Invoice`, `Save`, `Save as Exception`, `Delete`.
Delete shares the queue toolbar with Index Selected — Index Selected is targeted
by its own custom class, never by position.

---

## 6. Rules carried forward, unchanged

- **Selectors key off `name`, never `id`.** ExtJS generates the ids fresh on
  every page load. Confirmed again 2026-08-13: every single id on the indexing
  screen carries a generated number.
- **Type, never paste.** `page.fill()` fires no keystrokes, so ExtJS
  autocompletes never wake up and no code is stored — the box looks filled and
  is empty underneath. 45 ms per character.
- **Vendor, Property and Integration Package are dropdowns.** Type, wait, click
  the match (`.x-boundlist-item`). Then confirm the code box is not empty.
- **A missing spreadsheet column looks exactly like an empty cell.** The startup
  column guard stays.
- **Dates and amounts are typed exactly as Excel displays them.** Never
  converted, never guessed. A real date cell stops the run.

---

## 7. Stop conditions

The script **stops the whole run** and explains itself when:

1. The same image name appears twice in the queue.
2. A vendor or property was picked but its code box stayed empty.
3. A login screen appears mid-batch (session expired).
4. Any spreadsheet column in the field map is missing.
5. A spreadsheet cell holds a real Excel date rather than text.

The script **skips that one row**, reports it at the end, and carries on when:

6. The image name is not in the queue at all.
7. The page header is not `Image Index - …` after two attempts.
8. The Image Name box does not match the spreadsheet row after two attempts.

**The difference in one line:** 1–5 mean something is wrong with the *setup* and
every remaining row would hit it too. 6–8 mean something is wrong with *that one
invoice*, and the other thirty-nine are fine.

**In every case above, nothing has been typed.** The checks run before the first
character.

---

## 8. Documentation fix included in this work

**The guide's Image Name instruction is wrong.** It says the image name is a
GUID like `37a9b5cf-08f4-405c-9cb5-cc194e166377`. Live evidence shows real names
such as `skm_c250i26080508080` (a scanner filename) and one beginning
`washingt…`. **The format varies.**

This matters more than it looks: the Image Name column is not just checked, it
is **how the script finds the invoice in the queue**. A wrong format means zero
matches and every invoice skipped.

New instruction: *copy the image name exactly as it appears in the queue list.*

---

## 9. Not in V1 — deliberately

- Pressing Convert to Invoice, or anything on the second screen.
- The `Next` button on the indexing page. The script returns to the queue and
  re-finds by name instead — slower, but it proves it is on the right invoice
  every time.
- 200 rows per page.
- Filling the spreadsheet from PDFs automatically (Phase 2).
- Multi-line GL splits.

---

## 10. Known open items — not blocking this spec

- Vendor "Steps Appliance Repair LLC" returned 0 dropdown matches. Spelling, not
  selector. Needs the exact Bottomline spelling.
- Whether ExtJS commits plain fields on change + blur. Four fields typed cleanly
  on 2026-08-10, but nobody confirmed the values stuck after leaving the screen.
- Whether the login form really is "first text box + first password box".

---

## 11. Sign-off

- [x] Section 2 (the run) matches how the work is actually done.
- [x] Section 4 settled: **verify first, retry twice, then skip.** Never fill blind.
- [x] The script fills and stops. The operator presses every button.

**Signed:** Dhruv (Team D) — verbally, in session
**Date:** 2026-08-13

*Sign-off covers V1 as scoped in section 9. Anything outside that list is a new
conversation, not an extension of this one.*
