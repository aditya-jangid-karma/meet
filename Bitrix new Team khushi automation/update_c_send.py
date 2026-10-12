import os

filepath = 'Team C/send_team_c.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("team_d_output", "team_c_output")
content = content.replace("Team D", "Team C")

# Find the channels dictionary and replace it
import re
channels_regex = r"channels\s*=\s*\{.*?\}"
replacement = '''channels = {
    "testing": "345986",
    # Please add the channel IDs for Team C L1s here:
    "Anurag_Singh": "",
    "Himanshu_Agarwal": "",
    "Jay_Makwana": "",
    "Jenishkumar_Mavani": "",
    "Kapil_Dugar": "",
    "Namit_Sultania": "",
    "Nikita_Patel": ""
}'''

content = re.sub(channels_regex, replacement, content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated send_team_c.py")
