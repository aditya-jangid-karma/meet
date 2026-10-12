import os

directories = [
    r"c:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation",
    r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
]
teams = ["B", "C", "D", "F", "H", "I"]

old_webhook = "311/ddg2z5eo9ouw706q"
new_webhook = "1488/zazz4zw38crxbf1p"

for base_dir in directories:
    for t in teams:
        send_path = os.path.join(base_dir, f"Team {t}", f"send_team_{t.lower()}.py")
        if os.path.exists(send_path):
            with open(send_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if old_webhook in content:
                content = content.replace(old_webhook, new_webhook)
                with open(send_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"[{'SERVER' if '10.0.8.33' in base_dir else 'LOCAL'}] Updated webhook for Team {t}")

print("Successfully replaced webhooks across all files!")
