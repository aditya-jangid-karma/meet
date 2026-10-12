import os

directories = [
    r"c:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation\Team H",
    r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation\Team H"
]

for d in directories:
    send_file = os.path.join(d, "send_team_h.py")
    if os.path.exists(send_file):
        with open(send_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Fix the empty if statement indentation error
        content = content.replace(
            'if img_disk_id:\n                    # requests.post(COMMIT_URL, json={"CHAT_ID": chat_id',
            'if img_disk_id:\n                    pass\n                    # requests.post(COMMIT_URL, json={"CHAT_ID": chat_id'
        )
        
        with open(send_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed IndentationError in {send_file}")

