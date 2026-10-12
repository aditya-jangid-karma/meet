import os
import re

# 1. Update existing files to remove 'chat' from IDs
teams_to_fix = ['B', 'C', 'I'] # D and H already don't use 'chat'
for t in teams_to_fix:
    path = f"Team {t}/send_team_{t.lower()}.py"
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace 'chatXXXX' with 'XXXX'
        content = re.sub(r"'chat(\d+)'", r"'\1'", content)
        content = re.sub(r'"chat(\d+)"', r'"\1"', content)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Removed 'chat' prefix from {path}")

# 2. Generate the fully updated send_team_f.py
f_leads = {
    "Pratik_Tamakuwala": "6158",
    "Suresh_Baldaniya": "319844"
}

f_code = f'''import os
import glob
import base64
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UPLOAD_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/disk.folder.uploadfile"
COMMIT_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.disk.file.commit"
MESSAGE_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.message.add"

FOLDER_ID = "15372"
TESTING_CHANNEL = "345986"

LEAD_CHATS = {repr(f_leads)}

def upload_file_to_disk(file_path):
    if not os.path.exists(file_path):
        return None
    filename = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        file_data = f.read()
    b64_data = base64.b64encode(file_data).decode('utf-8')
    payload = {{
        "id": FOLDER_ID,
        "data": {{"NAME": filename}},
        "fileContent": [filename, b64_data],
        "generateUniqueName": True
    }}
    resp = requests.post(UPLOAD_URL, json=payload, verify=False)
    resp_data = resp.json()
    if 'result' in resp_data and 'ID' in resp_data['result']:
        return resp_data['result']['ID']
    print(f"Upload failed for {{filename}}: {{resp_data}}")
    return None

def main():
    target_dir = f"team_f_output"
    if os.path.exists(target_dir):
        os.chdir(target_dir)

    for lead_name, chat_id in LEAD_CHATS.items():
        excel_file = f"{{lead_name}}_Final_Report.xlsx"
        img_file = f"{{lead_name}}_Final_Report_Screenshot.png"
        
        display_name = lead_name.replace("_", " ")

        if os.path.exists(excel_file):
            print(f"\\nProcessing {{excel_file}} for {{display_name}}...")
            excel_disk_id = upload_file_to_disk(excel_file)
            img_disk_id = upload_file_to_disk(img_file) if os.path.exists(img_file) else None
            
            if excel_disk_id:
                print(f"Sending reports to Lead Chat {{chat_id}} and Testing Channel...")
                
                # Send to L1 Chat
                if img_disk_id:
                    requests.post(COMMIT_URL, json={{"CHAT_ID": chat_id, "MESSAGE": " ", "DISK_ID": [img_disk_id]}}, verify=False)
                requests.post(COMMIT_URL, json={{"CHAT_ID": chat_id, "MESSAGE": f"Here is the latest overdue task report for {{display_name}}:\\n{{excel_file}}", "DISK_ID": [excel_disk_id]}}, verify=False)
                
                # Send to Testing Channel
                if img_disk_id:
                    requests.post(COMMIT_URL, json={{"CHAT_ID": TESTING_CHANNEL, "MESSAGE": " ", "DISK_ID": [img_disk_id]}}, verify=False)
                requests.post(COMMIT_URL, json={{"CHAT_ID": TESTING_CHANNEL, "MESSAGE": f"[Team F] Here is the latest overdue task report for {{display_name}}:\\n{{excel_file}}", "DISK_ID": [excel_disk_id]}}, verify=False)
        else:
            print(f"\\nNo tasks found for {{display_name}}. Sending ZERO TASKS message to {{chat_id}} and Testing Channel...")
            success_msg = f"[Team F] {{display_name}} does not have any active overdue tasks right now!"
            
            # Send to L1 Chat
            requests.post(MESSAGE_URL, json={{"CHAT_ID": chat_id, "MESSAGE": success_msg}}, verify=False)
            
            # Send to Testing Channel
            requests.post(MESSAGE_URL, json={{
                "CHAT_ID": TESTING_CHANNEL,
                "MESSAGE": success_msg
            }}, verify=False)

    print(f"\\nSuccessfully dispatched Team F reports/messages!")

if __name__ == '__main__':
    main()
'''
with open("Team F/send_team_f.py", "w", encoding="utf-8") as f:
    f.write(f_code)
print("Generated completely upgraded send_team_f.py with Pratik and Suresh mapped!")
