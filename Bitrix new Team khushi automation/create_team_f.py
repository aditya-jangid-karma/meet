# -*- coding: utf-8 -*-
import pandas as pd

data = [
    ['C131A', 'The Letap Group', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C298A', 'McCracken Property Management LLC', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C312A', 'Tripoint Residential LLC', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C117A', 'AirMGR', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C118A', 'Anderson Law', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C322A', 'Beniterra Inc', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C272A', 'Contemporary Living LLC', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C127A', 'CYBR International', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C118B', 'HBA LLC', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C368B', 'JJP Realty LLC', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C135A', 'Rentlink', '-', 0, 'Team F'],
    ['C123A', 'Step Stones Acquisition LLC', 'Pratik Tamakuwala', 0, 'Team F'],
    ['C132A', 'Valjato Engineering', 'Pratik Tamakuwala', 0, 'Team F']
]

df = pd.DataFrame(data, columns=['Client Code', 'Client', 'L1 (Project Lead)', 'Overdue Tasks', 'Team'])
df.to_excel('Team-F_Client_Overdue_Tasks.xlsx', index=False)
print('Created Team-F_Client_Overdue_Tasks.xlsx')
