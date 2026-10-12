import os

directories = [
    r"c:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation",
    r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
]
teams = ["B", "C", "D", "F", "H", "I"]

for base_dir in directories:
    for t in teams:
        send_path = os.path.join(base_dir, f"Team {t}", f"send_team_{t.lower()}.py")
        if os.path.exists(send_path):
            with open(send_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if "# LEAD_CHATS" in content:
                print(f"[{'SERVER' if '10.0.8.33' in base_dir else 'LOCAL'}] Found commented LEAD_CHATS in Team {t}")
