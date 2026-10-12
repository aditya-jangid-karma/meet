"""
Reset the workflow folders for a fresh test cycle
=================================================
Deletes the TEST RESULTS ONLY - everything sitting inside the six workflow
folders, plus the saved AI answers in the temporary work folder.

It will NEVER touch:
  - any program file, settings file or the spike
  - the reference PDFs in C:\\Project\\PDF Splitter Samples
  - the test log in PDF Spliter\\test-log

It lists what it is about to delete and asks you to type YES first. Anything
other than YES cancels and nothing is removed.

    python test_reset.py
"""

import json
import shutil
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FOLDERS = ["01_Inbox", "02_Processing", "03_Output", "04_Review", "05_Archive", "06_Reports"]


def main():
    cfg_path = SCRIPT_DIR / "ap_splitter.config.json"
    if not cfg_path.exists():
        print(f"Settings file not found: {cfg_path}")
        return
    root = Path(json.loads(cfg_path.read_text(encoding="utf-8"))["root"])
    work = Path(tempfile.gettempdir()) / "ap_splitter_work"

    # Work out exactly what would go, and show it, before asking.
    doomed = []
    for name in FOLDERS:
        d = root / name
        if d.is_dir():
            doomed += [p for p in d.iterdir() if p.is_file()]

    print("=" * 68)
    print("RESET - this will delete the following test results")
    print("=" * 68)
    if not doomed and not work.exists():
        print("\n  Nothing to delete - the folders are already clean.")
        return
    for p in doomed:
        print(f"  {p.parent.name}\\{p.name}")
    if work.exists():
        cached = list((work / 'cache').glob('*.json')) if (work / 'cache').is_dir() else []
        print(f"  {work}  ({len(cached)} saved AI answer file(s))")

    print()
    print("  NOT touched: program files, settings, the spike, the test log,")
    print("               and the reference PDFs outside these folders.")
    print()
    answer = input("Type YES to delete, anything else to cancel: ").strip()
    if answer != "YES":
        print("\nCancelled. Nothing was deleted.")
        return

    for p in doomed:
        p.unlink()
        print(f"  deleted  {p.parent.name}\\{p.name}")
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
        print(f"  deleted  {work}")

    print()
    print("=" * 68)
    for name in FOLDERS:
        d = root / name
        n = len([p for p in d.iterdir() if p.is_file()]) if d.is_dir() else -1
        state = "CLEAN" if n == 0 else ("*** MISSING FOLDER ***" if n < 0 else f"{n} left")
        print(f"  {name:15} {state}")
    print("=" * 68)
    print("\nReady for a fresh test cycle. Drop one invoice into 01_Inbox.")


if __name__ == "__main__":
    main()
