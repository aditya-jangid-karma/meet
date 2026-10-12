import os

filepath = 'Team C/process_team_c.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the hardcoded mapping with dynamic loading
# Find the mapping dictionary
import re

mapping_regex = r"team_c_mapping = \{.*?\}\n"
replacement = '''import pandas as pd
df_mapping = pd.read_excel('../Team-C_Client_Overdue_Tasks.xlsx')
team_c_mapping = {}
for _, row in df_mapping.iterrows():
    team_c_mapping[str(row['Client Code'])] = str(row['L1 (Project Lead)'])
'''

content = re.sub(mapping_regex, replacement, content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated process_team_c.py with dynamic mapping")
