import os
import time
import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "YOUR_HUBSPOT_ACCESS_TOKEN")
BASE_URL = "https://api.hubapi.com/crm/v3/objects/companies"
PROPERTIES_URL = "https://api.hubapi.com/crm/v3/properties/companies"
OUTPUT_FILE_PARQUET = "hubspot_companies.parquet"
OUTPUT_FILE_CSV = "hubspot_companies.csv"

# The exact columns wanted
TARGET_COLUMNS = [
    "Team",
    "Group Code",
    "Client Code",
    "Status",
    "Company Name",
    "Primary Business (Industry)",
    "Secondary Business (Industry)",
    "Other Business (Industry)",
    "Communication Channel",
    "Secondary Communication Channel",
    "Primary Software",
    "Secondary Software",
    "Other Software (Including third party apps)",
    "City",
    "State",
    "Country",
    "Time zone",
    "Shift Type",
    "Client Hours",
    "Client Hours (1st 15)",
    "Client Hours (2nd 15)",
    "Loom Completion %",
    "Workflow Completion %",
    "Business Size (CY Turnover)",
    "Business Size (PY Turnover)",
    "Corporate Entity (CY Turnover)",
    "Corporate Entity (PY Turnover)",
    "Unit Count (Residential)",
    "Square Ft (Commercial)",
    "L1",
    "L2",
    "L3",
    "Client Communication Email",
    "Sub Codes",
    "Client Name as per Team Logger",
    "Name as per Karma Zoho Books",
    "Billing",
    "Billing Frequency",
    "Entity",
    "Starting Month for Billing with Partner",
    "Meeting",
    "Projected $",
    "Historical Projected $",
    "Exit Reason",
    "Exit Reason Others",
    "Group Name",
    "Team Lead",
    "First Year Sharing %",
    "Second Year Sharing %",
    "Third Year Sharing %",
    "Name as per KPO Zoho Books",
    "Extra Remarks",
    "Emails (Numbers) Only Client's Domains",
    "Slack (Y/N)",
    "Teams (Y/N)",
    "Whatsapp Group (Numbers)"
]

def create_session():
    """Create a persistent session with automatic retry on rate limits (429) and server errors."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    })
    
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    return session

def get_property_mapping(session):
    """Fetch HubSpot property definitions and map target labels to internal API property names."""
    print("🔍 Fetching property definitions from HubSpot...")
    response = session.get(PROPERTIES_URL)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch properties metadata: {response.status_code} - {response.text}")
    
    properties_data = response.json().get("results", [])
    label_to_name = {}
    name_to_label = {}
    
    for prop in properties_data:
        p_name = prop.get("name")
        p_label = prop.get("label", "").strip()
        
        if p_label:
            label_to_name[p_label.lower()] = p_name
        if p_name:
            label_to_name[p_name.lower()] = p_name
            name_to_label[p_name] = p_label

    label_to_name["company name"] = "name"
    label_to_name["time zone"] = "timezone"

    internal_properties = []
    rename_map = {}
    missing_columns = []

    for col in TARGET_COLUMNS:
        clean_col = col.strip().lower()
        if clean_col in label_to_name:
            int_name = label_to_name[clean_col]
            if int_name not in internal_properties:
                internal_properties.append(int_name)
            rename_map[int_name] = col
        else:
            missing_columns.append(col)

    print(f"✅ Mapped {len(internal_properties)} properties successfully.")
    if missing_columns:
        print(f"⚠️ Warning: Could not automatically map these {len(missing_columns)} columns (they will be blank):")
        for m in missing_columns:
            print(f"   - {m}")

    return internal_properties, rename_map

def fetch_all_companies(session, internal_properties):
    all_companies = []
    after = None
    page_count = 0
    start_time = time.time()

    print("\n🚀 Starting HubSpot extraction...")

    while True:
        params = {
            "limit": 100,
            "properties": ",".join(internal_properties),
            "archived": "false"
        }
        if after:
            params["after"] = after

        response = session.get(BASE_URL, params=params)
        
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}: {response.text}")
            break

        data = response.json()
        results = data.get("results", [])
        
        for item in results:
            row = {"hubspot_id": item.get("id")}
            row.update(item.get("properties", {}))
            all_companies.append(row)

        page_count += 1
        if page_count % 50 == 0:
            elapsed = time.time() - start_time
            print(f"📦 Fetched {len(all_companies):,} companies ({page_count} pages) in {elapsed:.1f}s...")

        # looks for next page
        paging = data.get("paging", {})
        next_page = paging.get("next", {})
        after = next_page.get("after")

        if not after:
            print("✅ All pages fetched!")
            break

    total_time = time.time() - start_time
    print(f"\n🎉 Finished! Total: {len(all_companies):,} companies in {total_time:.1f} seconds.")
    return all_companies

def main():
    session = create_session()
    
    # 1. Map target columns to internal HubSpot property names
    internal_properties, rename_map = get_property_mapping(session)
    
    # 2. Fetch companies from HubSpot
    companies = fetch_all_companies(session, internal_properties)
    
    if not companies:
        print("No records retrieved.")
        return

    # 3. Process DataFrame
    print("\n📊 Formatting and organizing columns...")
    df = pd.DataFrame(companies)
    df.rename(columns=rename_map, inplace=True)

    # Ensure all target columns exist in the DataFrame
    for col in TARGET_COLUMNS:
        if col not in df.columns:
            df[col] = None

    final_cols = ["hubspot_id"] + [col for col in TARGET_COLUMNS if col in df.columns]
    df = df[final_cols]

    # 4. Save to files
    try:
        df.to_parquet(OUTPUT_FILE_PARQUET, index=False)
        print(f"📁 Saved to Parquet: {OUTPUT_FILE_PARQUET}")
    except Exception as e:
        print(f"⚠️ Parquet save skipped (install pyarrow with `pip install pyarrow`): {e}")

    df.to_csv(OUTPUT_FILE_CSV, index=False, encoding="utf-8-sig")
    print(f"📁 Saved to CSV: {OUTPUT_FILE_CSV}")

if __name__ == "__main__":
    main()