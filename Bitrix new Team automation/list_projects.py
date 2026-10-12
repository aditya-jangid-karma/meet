import pandas as pd
import glob
import os

files = ["Team-D_Client_Overdue_Tasks.xlsx", "Team-F_Client_Overdue_Tasks.xlsx", "Team-H_Client_Overdue_Tasks.xlsx"]

for f in files:
    try:
        df = pd.read_excel(f)
        print(f"\n--- {f} ---")
        for idx, row in df.iterrows():
            print(f"{row['Client Code']} --> {row['L1 (Project Lead)']}")
    except Exception as e:
        print(f"Error reading {f}")
