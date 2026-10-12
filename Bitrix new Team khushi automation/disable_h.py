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
            
        # Comment out the line that sends the image to chat_id
        content = content.replace(
            'requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": " ", "DISK_ID": [img_disk_id]}, verify=False)',
            '# requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": " ", "DISK_ID": [img_disk_id]}, verify=False)'
        )
        
        # Comment out the line that sends the excel to chat_id
        content = content.replace(
            'requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": f"Here is the latest overdue task report for {display_name}:\\n{excel_file}", "DISK_ID": [excel_disk_id]}, verify=False)',
            '# requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": f"Here is the latest overdue task report for {display_name}:\\n{excel_file}", "DISK_ID": [excel_disk_id]}, verify=False)'
        )
        
        # Comment out the zero tasks message to chat_id
        content = content.replace(
            'requests.post(MESSAGE_URL, json={"CHAT_ID": chat_id, "MESSAGE": success_msg}, verify=False)',
            '# requests.post(MESSAGE_URL, json={"CHAT_ID": chat_id, "MESSAGE": success_msg}, verify=False)'
        )
        
        with open(send_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Disabled L1 chat sends in {send_file}")

