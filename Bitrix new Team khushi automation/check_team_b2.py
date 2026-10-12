import pandas as pd

df = pd.read_excel('Team_B_Detailed_Tasks.xlsx')
print(df.columns.tolist())
print(df.head(2))
