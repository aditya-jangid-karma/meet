import os

filepath = 'Team B/process_team_b.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("Team_I_Detailed_Tasks.xlsx", "Team_B_Detailed_Tasks.xlsx")
content = content.replace("Team I", "Team B")
content = content.replace("team_i", "team_b")
content = content.replace("team_I", "team_B")
content = content.replace("team_val == 'I':", "team_val == 'B':")
content = content.replace("Team-I_Client_Overdue_Tasks.xlsx", "Team-B_Client_Overdue_Tasks.xlsx")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated process_team_b.py")
