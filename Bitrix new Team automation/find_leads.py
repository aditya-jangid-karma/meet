import pandas as pd
import glob
import os

projects_to_find = [
    "C268A Ember of Hope LLC",
    "C126A 9th Street Deli",
    "C157A LLM LLC"
]

files = glob.glob("Team-*_Client_Overdue_Tasks.xlsx")

for f in files:
    try:
        df = pd.read_excel(f)
        for p in projects_to_find:
            # Check if any part of the project name is in the Client Code column
            # Sometimes there are spaces or case differences
            match = df[df['Client Code'].astype(str).str.contains(p.split(' ')[0], case=False, na=False)]
            if not match.empty:
                lead = match.iloc[0]['L1 (Project Lead)']
                client_code = match.iloc[0]['Client Code']
                print(f"[{f}] Project: '{client_code}' --> Lead: {lead}")
    except Exception as e:
        pass
