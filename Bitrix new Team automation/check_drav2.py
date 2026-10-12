import pandas as pd
df = pd.read_excel('Team D/team_d_output/Drav_Siriya_Final_Report.xlsx', sheet_name='Overview', skiprows=3)
pd.set_option('display.max_columns', None)
print(df)
