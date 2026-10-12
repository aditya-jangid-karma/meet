import pandas as pd
df = pd.read_excel('All Other Teams\\Team_H_Detailed_Tasks.xlsx', sheet_name='Overview')
active = df[df['Due Today'] > 0]
if not active.empty:
    print(active[['Project', 'Due Today']].head(3))
