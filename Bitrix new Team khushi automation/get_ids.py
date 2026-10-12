import os
import ast

base_dir = r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
teams = ["B", "C", "D", "F", "H", "I"]

print("=========================================")
print("BITRIX CHAT & CHANNEL IDs BY TEAM")
print("=========================================\n")

for t in teams:
    send_path = os.path.join(base_dir, f"Team {t}", f"send_team_{t.lower()}.py")
    if os.path.exists(send_path):
        with open(send_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        testing_channel = ""
        lead_chats = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith("TESTING_CHANNEL"):
                testing_channel = line.split("=")[1].strip().strip('"').strip("'")
            elif line.startswith("LEAD_CHATS"):
                # Extract dictionary string
                dict_str = line.split("=", 1)[1].strip()
                try:
                    lead_chats = ast.literal_eval(dict_str)
                except Exception as e:
                    pass
                    
        print(f"--- TEAM {t} ---")
        print(f"Testing Channel ID: {testing_channel}")
        if lead_chats:
            for name, chat_id in lead_chats.items():
                print(f"  - {name.replace('_', ' ')}: {chat_id}")
        else:
            print("  - No L1 Lead Chats configured.")
        print()
