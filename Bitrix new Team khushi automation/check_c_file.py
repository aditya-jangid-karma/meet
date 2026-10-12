import pandas as pd
df = pd.read_excel('Team-C_Client_Overdue_Tasks.xlsx')
print("Columns:")
print(df.columns.tolist())
print("\nFirst 5 rows:")
print(df.head(5).to_string())
