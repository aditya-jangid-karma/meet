"""
Merge confirmed-correct vendor data from validated_vendors.csv into vendors.csv.

validated_vendors.csv is the OUTPUT of harvest_vendors.py: for each vendor in
vendors.csv, it logged into Bottomline, searched for the vendor live, and
recorded what it found. Only vendors where the live data MATCHED (verifier ==
"TRUE") end up in validated_vendors.csv -- mismatches go to invalid_vendors.csv
instead. So validated_vendors.csv is a partial, confirmed-correct subset, not
a full replacement vendor list.

This script updates ONLY "Vendor Name" and "Address" in vendors.csv, and ONLY
for rows whose "ERP Vendor ID" has a confirmed match in validated_vendors.csv.
Every other row (not yet harvested) is left untouched. "State" and
"Membership ID" have no equivalent in validated_vendors.csv, so they are
never touched by this script.

Usage:
    python merge_validated_vendors.py            # preview only, writes nothing
    python merge_validated_vendors.py --apply     # backs up vendors.csv, then writes
"""
import csv
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
MASTERS_DIR = HERE.parent / "masters"
VENDORS_CSV = MASTERS_DIR / "vendors.csv"
VALIDATED_CSV = MASTERS_DIR / "validated_vendors.csv"


def load_validated_map():
    """ERP Vendor ID (lowercased) -> confirmed {name, address} from validated_vendors.csv."""
    mapping = {}
    with open(VALIDATED_CSV, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            code = (row.get("vendorCode") or "").strip()
            if not code:
                continue
            mapping[code.lower()] = {
                "name": (row.get("vendor") or "").strip(),
                "address": (row.get("vendorAddress") or "").strip(),
            }
    return mapping


def main():
    apply = "--apply" in sys.argv

    if not VENDORS_CSV.exists():
        sys.exit(f"Not found: {VENDORS_CSV}")
    if not VALIDATED_CSV.exists():
        sys.exit(f"Not found: {VALIDATED_CSV}")

    validated = load_validated_map()

    with open(VENDORS_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    matched = 0
    changed = 0
    examples = []

    for row in rows:
        erp_id = (row.get("ERP Vendor ID") or "").strip()
        if not erp_id:
            continue
        confirmed = validated.get(erp_id.lower())
        if not confirmed:
            continue
        matched += 1

        new_name = confirmed["name"] or row.get("Vendor Name", "")
        new_addr = confirmed["address"] or row.get("Address", "")
        old_name = row.get("Vendor Name", "")
        old_addr = row.get("Address", "")

        if new_name != old_name or new_addr != old_addr:
            changed += 1
            if len(examples) < 10:
                examples.append(
                    f"  ERP ID {erp_id}:\n"
                    f"    Name:    '{old_name}' -> '{new_name}'\n"
                    f"    Address: '{old_addr}' -> '{new_addr}'"
                )
            row["Vendor Name"] = new_name
            row["Address"] = new_addr

    print(f"vendors.csv rows total:        {len(rows)}")
    print(f"Matched in validated_vendors:  {matched}")
    print(f"Rows that would actually change: {changed}")
    if examples:
        print("\nExample changes (up to 10):")
        for ex in examples:
            print(ex)

    if not apply:
        print("\nDry run only -- nothing written. Re-run with --apply to write changes.")
        return

    if changed == 0:
        print("\nNothing to change -- vendors.csv left as-is.")
        return

    backup_path = MASTERS_DIR / f"vendors.csv.backup-{date.today().isoformat()}.csv"
    with open(VENDORS_CSV, "r", encoding="utf-8-sig") as src, \
         open(backup_path, "w", newline="", encoding="utf-8-sig") as dst:
        dst.write(src.read())
    print(f"\nBacked up current vendors.csv to {backup_path.name}")

    with open(VENDORS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"vendors.csv updated: {changed} row(s) changed.")


if __name__ == "__main__":
    main()
