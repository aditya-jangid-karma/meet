# OCR Invoice Extractor — Setup Handoff

**Date:** 2026-07-03  
**Status:** Blocked on Poppler installation  
**Owner:** Dhruv / Team D

---

## What Was Done

1. **Script written:** `Tesseract_Testing/ocr_extract.py` — fully working OCR extractor that:
   - Scans all subfolders under `Tesseract_Testing/` for PDFs
   - Runs OCR on every page using Tesseract + pdf2image
   - Splits multi-invoice PDFs by detecting invoice/statement number boundaries
   - Extracts structured fields (Document #, Date, Due Date, Vendor, Bill To, Amount)
   - Saves one `.txt` per PDF in `Tesseract_Testing/`
   - Shows progress bar, logs errors, skips failures

2. **README written:** `Tesseract_Testing/README.md` — full install guide and troubleshooting

3. **Tesseract OCR installed:** Installation completed (default components selected)

4. **Python packages:** Still need to run `pip install pdf2image pytesseract tqdm`

---

## What's Blocking — Poppler Installation

Poppler is needed by the `pdf2image` Python library to convert PDF pages into images. Without it, the script cannot run.

**The problem:** Dhruv cloned the Poppler repo and downloaded a ZIP, but Poppler's repo is source code — it needs to be compiled, which is complex on Windows.

### What to Do Next

**Don't compile from source.** Instead, download a pre-built Windows binary:

1. Go to: https://github.com/osber/poppler/releases  
   - If that link is dead, search Google for **"poppler windows binary download"** — look for a ZIP containing a `bin/` folder with files like `pdftoppm.exe`, `pdfinfo.exe`, etc.
   - Another known source: https://blog.alivate.com.au/poppler-windows/

2. Download the latest release ZIP (e.g., `poppler-xx.xx.x.zip`)

3. Extract the ZIP to a simple path, for example: `C:\poppler`

4. Inside the extracted folder, find the `bin` directory. It should contain files like:
   - `pdftoppm.exe`
   - `pdfinfo.exe`
   - `pdftotext.exe`

5. Add that `bin` folder to Windows PATH:
   - Press `Win + S`, search **"Environment Variables"**
   - Click **"Edit the system environment variables"**
   - Click **"Environment Variables..."** button
   - Under **"System variables"**, find `Path`, click **Edit**
   - Click **New**, paste the full path to the `bin` folder (e.g., `C:\poppler\Library\bin`)
   - Click OK on all dialogs

6. **Restart your terminal** (close and reopen) for PATH changes to take effect

7. Verify by running: `pdftoppm -h` — you should see help text, not an error

---

## Remaining Steps After Poppler is Installed

1. Install Python packages: `pip install pdf2image pytesseract tqdm`
2. Open terminal, navigate to `Tesseract_Testing/`
3. Run: `python ocr_extract.py`
4. Check output `.txt` files and `ocr_errors.log`
5. If Tesseract isn't found, uncomment line 33 in `ocr_extract.py` and set the path

---

## Files

| File | Purpose |
|---|---|
| `Tesseract_Testing/ocr_extract.py` | Main script |
| `Tesseract_Testing/README.md` | Full documentation |
| `Tesseract_Testing/invoices/` | Contains 3 test PDFs |
