import csv
import re
from pathlib import Path

BASE = Path(r"C:\Users\Meet Patel\Desktop\automation\Res-1 Github\Res-1\Invoice_Indexer\masters")

prop_map = {}
with open(BASE / "properties.csv", encoding="utf-8", errors="ignore") as f:
    for row in csv.reader(f):
        if row and row[0].strip():
            name = row[0].strip().lstrip('\ufeff')
            code = row[1].strip() if len(row) > 1 else ""
            pkg = row[2].strip() if len(row) > 2 else ""
            prop_map[name.lower()] = (name, code, pkg)

with open(BASE / "allunits 2026.05.01.csv", encoding="utf-8", errors="ignore") as f:
    r = csv.reader(f)
    for _ in range(7):
        next(r)
    comms = {row[0].strip() for row in r if row and row[0].strip()}

matched = [c for c in comms if c.lower() in prop_map]
unmatched = [c for c in comms if c.lower() not in prop_map]

print(f"Matched {len(matched)} / {len(comms)} communities directly")
print("Unmatched:", unmatched[:15])
