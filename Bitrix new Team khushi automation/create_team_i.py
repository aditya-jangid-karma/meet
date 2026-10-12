# -*- coding: utf-8 -*-
import pandas as pd

data = [
    ['C270A', 'Prime Capital Group LLC', '-', 16, ''],
    ['C321A', 'Blkswan Holdings', 'Govind Prajapati', 246, 'Team-I Blkswan'],
    ['C348A', 'Essence Development', 'Govind Prajapati', 0, 'Team-I Blkswan'],
    ['C390A', 'God Bless America Construction LLC', 'Govind Prajapati', 0, 'Team-I Blkswan'],
    ['C348B', 'NorthStar Engagement', 'Govind Prajapati', 0, 'Team-I Blkswan'],
    ['C227A', 'Cathedral Church', 'Jhanvi Bajaj', 21, 'Team-I SMG'],
    ['C227B', 'Cathedral School', 'Jhanvi Bajaj', 5, 'Team-I SMG'],
    ['C225A', 'Investor Management Solutions', 'Jhanvi Bajaj', 5, 'Team-I SMG'],
    ['C355A', 'G&H Operating Group', 'Jhanvi Bajaj', 4, 'Team-I SMG'],
    ['C216A', 'Grease Trap Cleaners', 'Jhanvi Bajaj', 4, 'Team-I SMG'],
    ['C218A', 'RPM', 'Jhanvi Bajaj', 3, 'Team-I SMG'],
    ['C220A', 'SMG', 'Jhanvi Bajaj', 0, 'Team-I SMG'],
    ['C271A', 'Brickment Home', 'Krupa Vyas', 52, 'Team-I Brickment'],
    ['C222B', 'Legacy Home Holdings LLC', 'Krupa Vyas', 36, 'Team-I Brickment'],
    ['C221B', 'Murray Townhomes I LLC', 'Krupa Vyas', 24, 'Team-I Brickment'],
    ['C222C', 'Maz Cleveland', 'Krupa Vyas', 14, 'Team-I Brickment'],
    ['C221E', 'Real Estate Interest LLC', 'Krupa Vyas', 14, 'Team-I Brickment'],
    ['C236A', 'Anemos Swim', 'Krupa Vyas', 13, 'Team-I Brickment'],
    ['C222D', 'Fit to Flip LLC', 'Krupa Vyas', 0, 'Team-I Brickment'],
    ['C336A', 'Small Pet Select', 'Krupa Vyas', 0, 'Team-I Brickment']
]

df = pd.DataFrame(data, columns=['Client Code', 'Client', 'L1 (Project Lead)', 'Overdue Tasks', 'Team'])
df.to_excel('Team-I_Client_Overdue_Tasks.xlsx', index=False)
print('Created Team-I_Client_Overdue_Tasks.xlsx')
