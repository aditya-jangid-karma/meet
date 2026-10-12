import os
import shutil

base_dir = r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"

# 1. Cleanup Unnecessary Files
to_delete = [
    os.path.join(base_dir, "All Other Teams"),
    os.path.join(base_dir, "Bitrix-Testing-ch.py"),
    os.path.join(base_dir, "test_runner.py")
]

deleted_items = []
for item in to_delete:
    if os.path.exists(item):
        if os.path.isdir(item):
            shutil.rmtree(item)
        else:
            os.remove(item)
        deleted_items.append(os.path.basename(item))

print(f"DELETED: {', '.join(deleted_items)}")

# 2. Safely disable actual Chat sends, leaving only Testing Channel
teams = ["B", "C", "D", "F", "H", "I"]
for t in teams:
    send_file = os.path.join(base_dir, f"Team {t}", f"send_team_{t.lower()}.py")
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
        print(f"Disabled L1 chat sends in Team {t}")

