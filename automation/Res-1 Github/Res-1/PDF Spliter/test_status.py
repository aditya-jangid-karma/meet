"""
Show the state of the workflow folders
======================================
Read-only. Looks at nothing, changes nothing, deletes nothing - it just prints
what is currently sitting in each of the six folders, plus the last few register
rows, so you can see where things are without opening File Explorer.

    python test_status.py
"""

import csv
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FOLDERS = ["01_Inbox", "02_Processing", "03_Output", "04_Review", "05_Archive", "06_Reports"]


def main():
    cfg_path = SCRIPT_DIR / "ap_splitter.config.json"
    if not cfg_path.exists():
        print(f"Settings file not found: {cfg_path}")
        return
    root = Path(json.loads(cfg_path.read_text(encoding="utf-8"))["root"])

    print("=" * 68)
    print(f"WORKFLOW FOLDERS   {root}")
    print("=" * 68)

    for name in FOLDERS:
        d = root / name
        if not d.is_dir():
            print(f"  {name:15} *** MISSING ***")
            continue
        files = sorted(p.name for p in d.iterdir() if p.is_file())
        print(f"  {name:15} {len(files)} file(s)")
        for f in files:
            print(f"                    {f}")

    # Anything left in 02_Processing means a run stopped part way. The next run
    # puts it back in the inbox automatically, but it is worth knowing.
    stuck = list((root / "02_Processing").glob("*.pdf")) if (root / "02_Processing").is_dir() else []
    if stuck:
        print()
        print("  NOTE: a file is sitting in 02_Processing, so a previous run did not")
        print("        finish. The next run will move it back to 01_Inbox by itself.")

    reg = root / "06_Reports" / "invoice_register.csv"
    if reg.exists():
        with open(reg, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        print()
        print("=" * 68)
        print(f"REGISTER   {len(rows)} row(s) - last 5 shown")
        print("=" * 68)
        for r in rows[-5:]:
            print(f"  {r['processed_at']}  {r['vendor'][:24]:24} "
                  f"#{r['invoice_number']:14} p{r['source_pages']:6} {r['status']}")
    else:
        print("\n  Register not created yet (no invoice processed since the last reset).")

    log = SCRIPT_DIR / "test-log" / "test_log.csv"
    if log.exists():
        with open(log, newline="", encoding="utf-8") as f:
            n = max(0, sum(1 for _ in f) - 1)
        print(f"\n  Test log: {n} run(s) recorded  ({log})")


if __name__ == "__main__":
    main()
