import os

filepath = 'Team C/process_team_c.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace specific Team D references with Team C references
content = content.replace("Team_D_Detailed_Tasks.xlsx", "Team_C_Detailed_Tasks.xlsx")
content = content.replace("Team D", "Team C")
content = content.replace("team_d", "team_c")
content = content.replace("team_D", "team_C")
# Fix the Excel file read which might have been hardcoded or variable
# It was likely read_excel('../Team-D_Client_Overdue_Tasks.xlsx') or something.
content = content.replace("Team-D_Client_Overdue_Tasks.xlsx", "Team-C_Client_Overdue_Tasks.xlsx")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated process_team_c.py")
