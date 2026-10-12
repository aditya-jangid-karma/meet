import os

teams = {
    'H': {
        "Zeel_Patel": "6170",
        "Krishnakumar_Bang": "6164",
        "Rahul_Gajera": "137360"
    },
    'D': {
        "Manish_Makvana": "274404",
        "Jay_Rupareliya": "274406",
        "Drav_Siriya": "173312"
    },
    'C': {
        "Anurag_Singh": "chat6144",
        "Jenishkumar_Mavani": "chat6144",
        "Himanshu_Agarwal": "chat6148",
        "Nikita_Patel": "chat6148",
        "Jay_Makwana": "chat6086",
        "Kapil_Dugar": "chat6146",
        "Namit_Sultania": "chat6146"
    },
    'I': {
        "Govind_Prajapati": "chat245246",
        "Jhanvi_Bajaj": "chat6186",
        "Krupa_Vyas": "chat245254"
    },
    'B': {
        "Vishvesh_Narola": "chat1541"
    }
}

for team_letter, leads_dict in teams.items():
    code = f'''import os
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

LEAD_CHATS = {repr(leads_dict)}

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
    target_dir = f"team_{team_letter.lower()}_output"
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
                requests.post(COMMIT_URL, json={{"CHAT_ID": TESTING_CHANNEL, "MESSAGE": f"[Team {team_letter}] Here is the latest overdue task report for {{display_name}}:\\n{{excel_file}}", "DISK_ID": [excel_disk_id]}}, verify=False)
        else:
            print(f"\\nNo tasks found for {{display_name}}. Sending ZERO TASKS message to {{chat_id}} and Testing Channel...")
            success_msg = f"[Team {team_letter}] {{display_name}} does not have any active overdue tasks right now!"
            
            # Send to L1 Chat
            requests.post(MESSAGE_URL, json={{"CHAT_ID": chat_id, "MESSAGE": success_msg}}, verify=False)
            
            # Send to Testing Channel
            requests.post(MESSAGE_URL, json={{
                "CHAT_ID": TESTING_CHANNEL,
                "MESSAGE": success_msg
            }}, verify=False)

    print(f"\\nSuccessfully dispatched Team {team_letter} reports/messages!")

if __name__ == '__main__':
    main()
'''
    with open(f"Team {team_letter}/send_team_{team_letter.lower()}.py", "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Uncommented and fully updated send_team_{team_letter.lower()}.py")

