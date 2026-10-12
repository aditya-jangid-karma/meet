import os
import pandas as pd
from markitdown import MarkItDown

md_converter = MarkItDown()

# Define the folder paths relative to where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Ensure the input and output directories exist
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print("=========================================")
    print("  Document to Markdown Converter (CLI)   ")
    print("=========================================\n")
    print("Support File Types: .xlsx, .csv, .docx, .pdf\n")

    supported_exts = ('.xlsx', '.csv', '.docx', '.pdf')
    
    # Get all supported files from the input directory
    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(supported_exts)]

    if not files:
        print(f"No supported files (.xlsx, .csv, .docx, .pdf) found in:")
        print(f"-> {INPUT_DIR}")
        print("\nPlease place your files in the 'input' folder and run this script again.\n")
        return

    print(f"Found {len(files)} files to process in the 'input' folder...\n")
    success_count = 0

    for filename in files:
        file_path = os.path.join(INPUT_DIR, filename)
        name_without_ext, ext = os.path.splitext(filename)
        output_path = os.path.join(OUTPUT_DIR, f"{name_without_ext}.md")
        ext_lower = ext.lower()

        print(f"Converting: {filename} ...", end=" ")

        try:
            if ext_lower in ['.xlsx', '.csv']:
                # Convert Excel/CSV using Pandas
                if ext_lower == '.xlsx':
                    # Note: Skipping first 4 rows based on previous financial report format. 
                    df = pd.read_excel(file_path, skiprows=4)
                else:
                    # CSV files usually don't need row skipping
                    df = pd.read_csv(file_path)
                
                # Remove 'Unnamed: X' from empty column headers
                df.columns = ["" if str(col).startswith("Unnamed:") else col for col in df.columns]
                
                df = df.fillna("")
                markdown_table = df.to_markdown(index=False)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"## {name_without_ext}\n\n")
                    f.write(markdown_table)
            
            elif ext_lower in ['.docx', '.pdf']:
                # Convert Word/PDF using MarkItDown
                result = md_converter.convert(file_path)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(result.text_content)
            
            print("SUCCESS")
            success_count += 1
            
        except Exception as e:
            print(f"FAILED\n  -> Error: {str(e)}")

    print(f"\n=========================================")
    print(f"Finished! Successfully converted {success_count} out of {len(files)} files.")
    print(f"Check the 'output' folder for your Markdown files.")
    print(f"=========================================\n")

if __name__ == "__main__":
    main()
