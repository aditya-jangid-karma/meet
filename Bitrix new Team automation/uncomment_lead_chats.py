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
                
            if "# LEAD_CHATS =" in content:
                content = content.replace("# LEAD_CHATS =", "LEAD_CHATS =")
                with open(send_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Uncommented LEAD_CHATS in {send_path}")
