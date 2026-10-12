# -*- coding: utf-8 -*-
import pandas as pd

df = pd.read_excel('Team-I_Client_Overdue_Tasks.xlsx')
# Replace C221E with C221B
df.loc[df['Client Code'] == 'C221E', 'Client Code'] = 'C221B'
df.to_excel('Team-I_Client_Overdue_Tasks.xlsx', index=False)
print('Corrected C221E to C221B')
