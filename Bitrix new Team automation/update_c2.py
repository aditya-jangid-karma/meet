import os

filepath = 'Team C/process_team_c.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("team_val == 'D':", "team_val == 'C':")
content = content.replace("team_d_output", "team_c_output")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated process_team_c.py team_val and out_dir")
