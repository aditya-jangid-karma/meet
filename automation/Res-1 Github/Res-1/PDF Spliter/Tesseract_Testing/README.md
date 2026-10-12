# Tesseract_Testing — OCR Invoice/Statement Extractor

## What This Does

This folder contains a Python script (`ocr_extract.py`) that reads PDF invoices or statements from subfolders, runs OCR (Optical Character Recognition) on every page, and extracts structured information like invoice numbers, dates, amounts, and vendor names into `.txt` files.

**Key feature:** If a single PDF contains multiple invoices or statements (e.g., invoice #1001 on pages 1–3 and invoice #1002 on pages 4–6), the script detects the boundary and extracts each one separately.

---

## Folder Structure

```
Tesseract_Testing/
├── ocr_extract.py          ← The main script (run this)
├── README.md               ← You are here
├── ocr_errors.log          ← Error log (created on first run)
├── *.txt                   ← Output files (one per PDF, created on run)
└── invoices/               ← Drop your PDFs in subfolders like this
    ├── invoice1.pdf
    └── invoice2.pdf
```

- **Input:** Place PDFs in any subfolder (e.g., `invoices/`). The script scans all subfolders recursively.
- **Output:** One `.txt` file per PDF, saved in the `Tesseract_Testing/` root folder. Each file lists structured fields for every invoice/statement found inside that PDF.

---

## Prerequisites (Install Before Running)

### 1. Tesseract OCR Engine

The actual OCR engine that reads text from images.

- **Download:** Go to `https://github.com/UB-Mannheim/tesseract/wiki` and download the Windows installer.
- **Install:** Run the `.exe` installer. Default path is `C:\Program Files\Tesseract-OCR`.
- **Important:** During installation, check **"Add to PATH"** so the script can find it.
- **Verify:** Open a new terminal and run `tesseract --version`. You should see a version number.

### 2. Poppler for Windows

Needed by the `pdf2image` library to convert PDF pages into images.

- **Download:** Search for "poppler windows" releases on GitHub (e.g., `https://github.com/osber/poppler/releases`).
- **Install:** Extract the ZIP to a folder like `C:\poppler`.
- **Add to PATH:** Add the `bin` folder inside (e.g., `C:\poppler\Library\bin`) to your Windows system PATH.
- **Verify:** Open a new terminal and run `pdftoppm -h`. You should see help text, not an error.

### 3. Python Packages

Run this in your terminal:

```
pip install pdf2image pytesseract tqdm
```

| Package       | Purpose                                      |
|---------------|----------------------------------------------|
| `pdf2image`   | Converts each PDF page into an image         |
| `pytesseract` | Python wrapper that calls Tesseract OCR       |
| `tqdm`        | Displays a progress bar in the terminal       |

---

## How to Run

1. Place your PDF files in any subfolder under `Tesseract_Testing/` (e.g., `invoices/`).
2. Open a terminal and navigate to the `Tesseract_Testing` folder.
3. Run:

```
python ocr_extract.py
```

4. Watch the progress bar. When done, check the `.txt` files in this folder.

---

## What the Script Extracts (Structured Fields)

For each invoice/statement detected in a PDF, the script tries to extract:

| Field               | Examples it looks for                                    |
|---------------------|----------------------------------------------------------|
| Document Number     | Invoice #, Invoice No., Statement #, Bill #, PO #, etc. |
| Date                | Invoice Date, Statement Date, Date, etc.                 |
| Due Date            | Due Date, Payment Due, Pay By, etc.                      |
| Vendor / Company    | From, Vendor, Supplier, Billed By, etc.                  |
| Bill To             | Bill To, Sold To, Ship To, Customer, Attn, etc.          |
| Total / Amount Due  | Total Due, Amount Due, Balance Due, Grand Total, etc.    |

If a field is not found, it shows `(not detected)`.

---

## How Document Splitting Works

The script looks at every page for document number patterns (Invoice #, Statement #, etc.). When it sees a **new** number on a page that differs from the current one, it starts a new segment. Pages without a detected number are grouped with the preceding segment.

For example, in a 6-page PDF:
- Page 1: Invoice # 1001 → starts segment 1
- Pages 2–3: no new number → still segment 1
- Page 4: Invoice # 1002 → starts segment 2
- Pages 5–6: no new number → still segment 2

Result: two separate document entries in the output file.

---

## Error Handling

- If a PDF cannot be converted to images (corrupted file, etc.), the script **logs the error** and **skips that file**.
- If OCR fails on a specific page, the script **logs the error**, **skips that page**, and continues with the rest.
- If segmentation or writing fails, the script **logs the error** and moves to the next PDF.
- All errors are saved to `ocr_errors.log` in this folder.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `tesseract is not installed or it's not in your PATH` | Install Tesseract and add it to PATH (see above). Or uncomment the `tesseract_cmd` line in the script and set the exact path. |
| `Unable to get page count. Is poppler installed?` | Install Poppler and add its `bin` folder to PATH. |
| `ModuleNotFoundError: No module named 'pdf2image'` | Run `pip install pdf2image pytesseract tqdm`. |
| Output says `(not detected)` for a field | The OCR may have misread the text, or the invoice uses an unusual label. Check the raw OCR quality. |

---

## Technical Details

- **Language:** Python 3.10+ (uses `str | None` type hints)
- **OCR Engine:** Tesseract via pytesseract
- **PDF-to-Image:** pdf2image (wraps Poppler's `pdftoppm`)
- **Progress Bar:** tqdm
- **Regex-Based Extraction:** All field detection uses compiled regular expressions — no external NLP or AI models needed
- **Encoding:** Output files are UTF-8 encoded
