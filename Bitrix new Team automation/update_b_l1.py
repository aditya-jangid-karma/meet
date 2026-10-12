# -*- coding: utf-8 -*-
import pandas as pd

df = pd.read_excel('Team-B_Client_Overdue_Tasks.xlsx')
df.loc[df['Client Code'] == 'C101C', 'L1 (Project Lead)'] = 'Vishvesh Narola'
df.to_excel('Team-B_Client_Overdue_Tasks.xlsx', index=False)
print('Updated Team-B mapping')
