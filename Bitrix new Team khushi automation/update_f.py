import os

filepath = 'Team F/process_team_f.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("Team_I_Detailed_Tasks.xlsx", "Team_F_Detailed_Tasks.xlsx")
content = content.replace("Team I", "Team F")
content = content.replace("team_i", "team_f")
content = content.replace("team_I", "team_F")
content = content.replace("team_val == 'I':", "team_val == 'F':")
content = content.replace("Team-I_Client_Overdue_Tasks.xlsx", "Team-F_Client_Overdue_Tasks.xlsx")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated process_team_f.py")
