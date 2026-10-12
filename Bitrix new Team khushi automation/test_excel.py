import pandas as pd
df = pd.read_excel('All Other Teams\\Team_H_Detailed_Tasks.xlsx', sheet_name='Overview')
zeel_df = df[df['Project'].str.contains('Zeel', na=False, case=False)]
if zeel_df.empty:
    print("No 'Zeel' in Project names. Let's look at sum of all Due Today and Tomorrow:")
    print("Total Due Today:", df['Due Today'].sum())
    print("Total Due Tomorrow:", df['Due Tomorrow'].sum())
else:
    print(zeel_df)
