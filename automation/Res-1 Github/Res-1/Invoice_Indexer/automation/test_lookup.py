from pathlib import Path
from utility_lookup import UtilityLookup

MASTERS = Path(r"C:\Users\Meet Patel\Desktop\automation\Res-1 Github\Res-1\Invoice_Indexer\masters")
lookup = UtilityLookup(MASTERS)

test_addresses = [
    "1 Fairfax Court, Chevy Chase, MD",
    "1100 Eastern Ave N.E. Apt - 101, Washington, DC",
    "8401 Manchester Road, Silver Spring, MD",
    "4716 Bradley Blvd., Chevy Chase, MD",
    "2399 Jones Lane, Wheaton, MD",
    "80B Bureau Drive, Gaithersburg, MD",
    "1900 Savannah Terrace SE",
    "5837 Fisher Road, Temple Hills, MD",
]

print(f"Total addresses loaded in catalog: {len(lookup.address_to_property)}")

for addr in test_addresses:
    res = lookup.match(addr)
    print(f"\nInput: '{addr}'")
    print(f"  -> Property: '{res.property_name}', Code: '{res.property_code}', Package: '{res.integration_package}', Status: '{res.status}', How: '{res.matched_by}'")
