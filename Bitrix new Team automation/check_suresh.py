import pandas as pd
try:
    df = pd.read_excel('Team D/Team-D_Client_Overdue_Tasks.xlsx')
    suresh = df[df['L1 (Project Lead)'].str.contains('Suresh', case=False, na=False)]
    if suresh.empty:
        print("Suresh is NOT in Team D mapping.")
    else:
        print("Suresh IS in Team D mapping:")
        print(suresh)
except Exception as e:
    print(e)
