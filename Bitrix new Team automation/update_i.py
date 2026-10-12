import os

filepath = 'Team I/process_team_i.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("Team_C_Detailed_Tasks.xlsx", "Team_I_Detailed_Tasks.xlsx")
content = content.replace("Team C", "Team I")
content = content.replace("team_c", "team_i")
content = content.replace("team_C", "team_I")
content = content.replace("team_val == 'C':", "team_val == 'I':")
content = content.replace("Team-C_Client_Overdue_Tasks.xlsx", "Team-I_Client_Overdue_Tasks.xlsx")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated process_team_i.py")
