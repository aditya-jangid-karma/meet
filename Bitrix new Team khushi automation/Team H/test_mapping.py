import pandas as pd
import os
def load_l1_mapping():
    orig_mapping = 'Team_H_Overdue_Tasks.xlsx'
    l1_mapping = {}
    if os.path.exists(orig_mapping):
        try:
            orig_overview = pd.read_excel(orig_mapping, sheet_name='Overview', skiprows=3)
            for _, row in orig_overview.iterrows():
                code = row.get('Client Code')
                l1 = row.get('L1 (Project Lead)')
                if pd.notna(code):
                    c = str(code).strip()
                    l1_mapping[c] = str(l1).strip() if pd.notna(l1) else 'Unknown'
        except Exception as e:
            print(f"Warning: Could not read {orig_mapping}: {e}")
            
    # Hardcoded overrides just in case
    l1_mapping['C149A'] = 'Zeel Patel'
    l1_mapping['C283A'] = 'Krishnakumar Bang'
    l1_mapping['C352A'] = 'Zeel Patel'
    l1_mapping['C326A'] = 'Krishnakumar Bang'
    return l1_mapping

mapping = load_l1_mapping()
print("C326A mapped to:", mapping.get('C326A'))
