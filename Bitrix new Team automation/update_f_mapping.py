import pandas as pd
import os

df = pd.read_excel('Team-F_Client_Overdue_Tasks.xlsx')

# Update Rentlink C135A to Pratik Tamakuwala
df.loc[df['Client Code'] == 'C135A', 'L1 (Project Lead)'] = 'Pratik Tamakuwala'

# Add Suresh Baldaniya's projects
new_rows = pd.DataFrame([
    {'Client Code': 'C119A', 'Client': 'COARE Communities', 'L1 (Project Lead)': 'Suresh Baldaniya', 'Overdue Tasks': 0, 'Team': 'Team F'},
    {'Client Code': 'C119B', 'Client': 'Personal Books', 'L1 (Project Lead)': 'Suresh Baldaniya', 'Overdue Tasks': 0, 'Team': 'Team F'}
])

df = pd.concat([df, new_rows], ignore_index=True)
df.to_excel('Team-F_Client_Overdue_Tasks.xlsx', index=False)

print("Updated Team-F_Client_Overdue_Tasks.xlsx")
print(df)
