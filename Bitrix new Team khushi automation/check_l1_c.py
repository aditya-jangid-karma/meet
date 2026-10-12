import pandas as pd
df = pd.read_excel('Team-C_Client_Overdue_Tasks.xlsx')
print(df['L1 (Project Lead)'].unique())
