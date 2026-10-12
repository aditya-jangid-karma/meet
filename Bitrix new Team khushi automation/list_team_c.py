import pandas as pd
df = pd.read_excel('Team-C_Client_Overdue_Tasks.xlsx')
# Sort by L1 then Client Code for better readability
df = df.sort_values(by=['L1 (Project Lead)', 'Client Code'])
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
print(df[['Client Code', 'Client', 'L1 (Project Lead)']].to_string(index=False))
