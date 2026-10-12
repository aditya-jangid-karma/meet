# Document to Markdown Converter

This project provides a user-friendly Web UI to batch convert formatted Excel spreadsheets (`.xlsx`), Word documents (`.docx`), and PDFs (`.pdf`) into Markdown format. It was originally configured to handle complex financial reports (like 12-Month Statements, Balance Sheets, and General Ledgers) but works seamlessly for standard documents as well.

## Prerequisites

1. Install **Python 3** on your computer.
2. Install the required Python libraries. Open your terminal or command prompt in this directory and run:
   ```bash
   pip install -r requirements.txt
   ```

## Folder Structure

```text
excel-to-md/
│
├── start.bat             # 🚀 Double-click this to start the application
├── app.py                # The Flask backend server
├── requirements.txt      # List of Python dependencies
├── templates/
│   └── index.html        # The Web UI interface
└── excels/               # (Optional) You can still store files here, but the UI lets you choose any folder!
```

## How to Run (For Non-Technical Users)

1. Simply double-click the **`start.bat`** file.
2. A black terminal window will open to start the background server (do not close this window while using the tool).
3. Your default web browser will automatically open the Converter Interface (`http://127.0.0.1:5000`).
4. In the webpage:
   * Paste the path to your **Input Folder** (where your Excel/Word/PDF files are stored).
   * Paste the path to your **Output Folder** (where you want the `.md` files to be saved).
   * Adjust the **Excel Settings** if necessary (see below).
   * Click **Run Conversion**.

## Configuration & Caveats

**Skipping Title Rows in Excel:**
By default, the web interface is set to skip the first 4 rows of every Excel file (`skip_rows=4`). This is because many financial reports have 4 rows of titles and blank space before the actual table column headers begin (e.g., "Aug 2025", "Sep 2025").

* If you are converting normal Excel files that do NOT have titles at the top (data starts at Row 1 / Cell A1), **change the "Number of title rows to skip" setting in the webpage to `0`**.
* If your titles take up 2 rows instead of 4, change it to `2`.

**PDF Conversions:**
While Word (`.docx`) and Excel (`.xlsx`) files convert very cleanly into structured Markdown, PDF files can sometimes have inconsistent formatting depending on how they were originally generated. The tool extracts the text as accurately as possible, but highly complex graphical PDFs may require some manual review after conversion.
