# -*- coding: utf-8 -*-
import pandas as pd

data = [
    ['C101C', 'ResidentialOne - Compliance', 'UNKNOWN LEAD', 0, 'Team B']
]

df = pd.DataFrame(data, columns=['Client Code', 'Client', 'L1 (Project Lead)', 'Overdue Tasks', 'Team'])
df.to_excel('Team-B_Client_Overdue_Tasks.xlsx', index=False)
print('Created Team-B_Client_Overdue_Tasks.xlsx')
