import pandas as pd
import glob
import os

expected = {
    'C111A': 13, 'C136A': 9, 'C110A': 5, 'C229A': 3, 'C296A': 2,
    'C194A': 0, 'C260A': 0, 'C153D': 0, 'C110C': 0, 'C230A': 0,
    'C101A': 0, 'C226B': 5, 'C335A': 1, 'C106A': 1, 'C151A': 1,
    'C105A': 0, 'C198A': 0, 'C226A': 0, 'C257A': 0, 'C114A': 0,
    'C112A': 0, 'C115A': 0, 'C360A': 0, 'C151B': 0, 'C333A': 132,
    'C362A': 0, 'C387A': 0, 'C284A': 0, 'C359A': 0, 'C330A': 0,
    'C113A': 0, 'C235A': 0, 'C241A': 0
}

files = glob.glob('Team C/team_c_output/*_Final_Report.xlsx')
actual = {}

for f in files:
    try:
        df = pd.read_excel(f, sheet_name='Overview', skiprows=3)
        for _, row in df.iterrows():
            code = str(row['Client Code']).strip()
            if code and code != 'nan':
                overdue = row['Overdue Tasks']
                if pd.isna(overdue) or overdue == '': overdue = 0
                actual[code] = int(overdue)
    except Exception as e:
        print(f"Error reading {f}: {e}")

print(f"{'Client':<10} | {'Expected':<10} | {'Actual (Our Script)':<20} | {'Match?':<10}")
print("-" * 60)
for code, exp in expected.items():
    act = actual.get(code, 0)
    match = "YES" if exp == act else "NO"
    print(f"{code:<10} | {exp:<10} | {act:<20} | {match:<10}")

