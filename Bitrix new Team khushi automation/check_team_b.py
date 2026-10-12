import pandas as pd

try:
    df = pd.read_excel('Team_B_Detailed_Tasks.xlsx', skiprows=2)
    # The bitrix detailed task export has columns like "Task Name", "Project", etc.
    print(df.columns.tolist())
    print(df['Project'].dropna().unique())
except Exception as e:
    print(f"Error: {e}")
