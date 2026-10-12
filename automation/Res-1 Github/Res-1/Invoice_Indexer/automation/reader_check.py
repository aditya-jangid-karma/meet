"""Quick check that the reader's dependencies import. Run:
    python automation\\reader_check.py
Prints OK for each, or a clear message on the one that is missing.
Poppler is a separate binary (not a Python package) and is checked last.
"""
import shutil
import sys


def main():
    ok = True
    for name in ("pdf2image", "PIL", "openpyxl"):
        try:
            __import__(name)
            print(f"OK   {name}")
        except Exception as error:  # noqa: BLE001
            ok = False
            print(f"MISSING {name} -- {error}")

    poppler = shutil.which("pdftoppm")
    if poppler:
        print(f"OK   poppler (pdftoppm) at {poppler}")
    else:
        print("MISSING poppler -- pdftoppm.exe not on PATH. Install the Poppler "
              "Windows build and either add its bin\\ to PATH or pass "
              "--poppler-path to invoice_reader.py.")
        ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
