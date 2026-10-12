import os
import re

# 1. Fix LEAD_CHATS in Team B
path_b = "\\\\10.0.8.33\\Karma Automation\\Bitrix Team Task Automation\\Team B\\send_team_b.py"
if os.path.exists(path_b):
    with open(path_b, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace("# LEAD_CHATS = {'Vishvesh_Narola': '1541'}", "LEAD_CHATS = {'Vishvesh_Narola': '1541'}")
    content = content.replace("LEAD_CHATS = {}\nLEAD_CHATS = {'Vishvesh", "LEAD_CHATS = {'Vishvesh")
    with open(path_b, 'w', encoding='utf-8') as f:
        f.write(content)

# 2. Fix LEAD_CHATS in Team C
path_c = "\\\\10.0.8.33\\Karma Automation\\Bitrix Team Task Automation\\Team C\\send_team_c.py"
if os.path.exists(path_c):
    with open(path_c, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace("# LEAD_CHATS = {", "LEAD_CHATS = {")
    with open(path_c, 'w', encoding='utf-8') as f:
        f.write(content)

print("Uncommented LEAD_CHATS for B and C.")
