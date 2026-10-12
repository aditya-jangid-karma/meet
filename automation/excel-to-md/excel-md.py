import os
import pandas as pd
from markitdown import MarkItDown

md_converter = MarkItDown()

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Settings
MAX_TABLE_ROWS = 2000  # Cap table rows in Markdown to avoid viewer crashes
SUPPORTED_EXTS = ('.xlsx', '.xls', '.csv', '.docx', '.pptx', '.pdf', '.html', '.txt')

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def find_dynamic_header_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Intelligently finds the first non-empty row to use as column headers
    instead of relying on a hardcoded skiprows.
    """
    if raw_df.empty:
        return raw_df

    # Drop completely empty rows and columns
    df_clean = raw_df.dropna(how='all').dropna(axis=1, how='all')
    if df_clean.empty:
        return pd.DataFrame()

    # Find first row with at least 2 non-null values (or the first non-empty row)
    header_idx = 0
    for i, (_, row) in enumerate(df_clean.iterrows()):
        if row.count() >= 2:
            header_idx = i
            break

    # Re-assign header
    new_header = df_clean.iloc[header_idx]
    df_result = df_clean.iloc[header_idx + 1:].copy()
    df_result.columns = [
        f"Col_{idx+1}" if pd.isna(val) or str(val).strip() == "" or str(val).startswith("Unnamed:") 
        else str(val).strip()
        for idx, val in enumerate(new_header)
    ]

    return df_result.reset_index(drop=True)


def process_excel(file_path: str, name_without_ext: str) -> str:
    """Reads all sheets from an Excel file and converts each to Markdown."""
    excel_file = pd.ExcelFile(file_path)
    md_sections = [f"# {name_without_ext}\n"]

    for sheet_name in excel_file.sheet_names:
        md_sections.append(f"## Sheet: {sheet_name}\n")
        
        try:
            # Read raw without assuming header row
            raw_df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            df = find_dynamic_header_df(raw_df)

            if df.empty:
                md_sections.append("*(Empty sheet)*\n")
                continue

            total_rows = len(df)
            if total_rows > MAX_TABLE_ROWS:
                df = df.iloc[:MAX_TABLE_ROWS]
                warning_note = f"\n> ⚠️ *Table truncated to first {MAX_TABLE_ROWS:,} rows (out of {total_rows:,} total rows).*\n"
            else:
                warning_note = ""

            df = df.fillna("")
            table_md = df.to_markdown(index=False)
            md_sections.append(f"{table_md}\n{warning_note}")

        except Exception as sheet_err:
            md_sections.append(f"*(Could not parse sheet: {sheet_err})*\n")

    return "\n".join(md_sections)


def process_csv(file_path: str, name_without_ext: str) -> str:
    """Converts CSV file to Markdown."""
    raw_df = pd.read_csv(file_path, header=None)
    df = find_dynamic_header_df(raw_df)
    
    if df.empty:
        return f"# {name_without_ext}\n\n*(Empty CSV file)*\n"

    total_rows = len(df)
    warning_note = ""
    if total_rows > MAX_TABLE_ROWS:
        df = df.iloc[:MAX_TABLE_ROWS]
        warning_note = f"\n> ⚠️ *Table truncated to first {MAX_TABLE_ROWS:,} rows (out of {total_rows:,} total rows).*\n"

    df = df.fillna("")
    return f"# {name_without_ext}\n\n{df.to_markdown(index=False)}\n{warning_note}"


def main():
    print("==================================================")
    print("   Advanced Document to Markdown Converter (CLI)   ")
    print("==================================================\n")

    # 1. Discover all files recursively
    all_files = []
    for root, _, files in os.walk(INPUT_DIR):
        for f in files:
            if f.lower().endswith(SUPPORTED_EXTS):
                rel_dir = os.path.relpath(root, INPUT_DIR)
                all_files.append((root, rel_dir, f))

    if not all_files:
        print(f"No supported files {SUPPORTED_EXTS} found in:")
        print(f"-> {INPUT_DIR}")
        print("\nPlease place your files in the 'input' folder and run again.\n")
        return

    print(f"Found {len(all_files)} file(s) across input directories...\n")
    success_count = 0

    # 2. Process each file
    for root, rel_dir, filename in all_files:
        src_path = os.path.join(root, filename)
        name_without_ext, ext = os.path.splitext(filename)
        ext_lower = ext.lower()

        # Preserve folder structure in output directory
        target_out_dir = os.path.join(OUTPUT_DIR, rel_dir) if rel_dir != "." else OUTPUT_DIR
        os.makedirs(target_out_dir, exist_ok=True)
        out_path = os.path.join(target_out_dir, f"{name_without_ext}.md")

        print(f"Converting: {os.path.join(rel_dir, filename) if rel_dir != '.' else filename} ...", end=" ")

        try:
            if ext_lower in ['.xlsx', '.xls']:
                md_text = process_excel(src_path, name_without_ext)
            elif ext_lower == '.csv':
                md_text = process_csv(src_path, name_without_ext)
            else:
                # Word (.docx), PowerPoint (.pptx), PDF (.pdf), HTML (.html)
                result = md_converter.convert(src_path)
                md_text = result.text_content
                if not md_text.strip() and ext_lower == '.pdf':
                    md_text = f"# {name_without_ext}\n\n> ⚠️ *Note: This PDF appears to be a scanned image with no selectable text (requires OCR).*"

            with open(out_path, "w", encoding="utf-8") as out_file:
                out_file.write(md_text)

            print("✅ SUCCESS")
            success_count += 1

        except Exception as e:
            print(f"❌ FAILED\n  -> Error: {str(e)}")

    print(f"\n==================================================")
    print(f"Finished! Successfully converted {success_count} / {len(all_files)} files.")
    print(f"Check output folder: {OUTPUT_DIR}")
    print(f"==================================================\n")


if __name__ == "__main__":
    main()