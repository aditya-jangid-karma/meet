from datetime import datetime
import os
import glob
import base64
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UPLOAD_URL = "https://karma.bitrix24.in/rest/1488/zazz4zw38crxbf1p/disk.folder.uploadfile"
COMMIT_URL = "https://karma.bitrix24.in/rest/1488/zazz4zw38crxbf1p/im.disk.file.commit"
MESSAGE_URL = "https://karma.bitrix24.in/rest/1488/zazz4zw38crxbf1p/im.message.add"

FOLDER_ID = "15372"
TESTING_CHANNEL = "345986"

LEAD_CHATS = {'Manish_Makvana': '274404', 'Jay_Rupareliya': '274406', 'Drav_Siriya': '173312'}

def upload_file_to_disk(file_path):
    if not os.path.exists(file_path):
        return None
    filename = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        file_data = f.read()
    b64_data = base64.b64encode(file_data).decode('utf-8')
    payload = {
        "id": FOLDER_ID,
        "data": {"NAME": filename},
        "fileContent": [filename, b64_data],
        "generateUniqueName": True
    }
    resp = requests.post(UPLOAD_URL, json=payload, verify=False)
    resp_data = resp.json()
    if 'result' in resp_data and 'ID' in resp_data['result']:
        return resp_data['result']['ID']
    print(f"Upload failed for {filename}: {resp_data}")
    return None

def main():
    target_dir = f"team_d_output"
    if os.path.exists(target_dir):
        os.chdir(target_dir)

    for lead_name, chat_id in LEAD_CHATS.items():
        today_str = datetime.today().strftime("%d-%m-%Y")
        excel_file = f"{lead_name}_{today_str}.xlsx"
        img_file = f"{lead_name}_{today_str}.png"
        
        display_name = lead_name.replace("_", " ")

        if os.path.exists(excel_file):
            print(f"\nProcessing {excel_file} for {display_name}...")
            excel_disk_id = upload_file_to_disk(excel_file)
            img_disk_id = upload_file_to_disk(img_file) if os.path.exists(img_file) else None
            
            if excel_disk_id:
                print(f"Sending reports to Lead Chat {chat_id} and Testing Channel...")
                
                # Send to L1 Chat
                if img_disk_id:
                    requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": " ", "DISK_ID": [img_disk_id]}, verify=False)
                requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": f"Here is the latest overdue task report for {display_name}:\n{excel_file}", "DISK_ID": [excel_disk_id]}, verify=False)
                
                # Send to Testing Channel
                if img_disk_id:
                    requests.post(COMMIT_URL, json={"CHAT_ID": TESTING_CHANNEL, "MESSAGE": " ", "DISK_ID": [img_disk_id]}, verify=False)
                requests.post(COMMIT_URL, json={"CHAT_ID": TESTING_CHANNEL, "MESSAGE": f"[Team D] Here is the latest overdue task report for {display_name}:\n{excel_file}", "DISK_ID": [excel_disk_id]}, verify=False)
        else:
            print(f"\nNo tasks found for {display_name}. Sending ZERO TASKS message to {chat_id} and Testing Channel...")
            success_msg = f"[Team D] {display_name} does not have any active overdue tasks right now!"
            
            # Send to L1 Chat
            requests.post(MESSAGE_URL, json={"CHAT_ID": chat_id, "MESSAGE": success_msg}, verify=False)
            
            # Send to Testing Channel
            requests.post(MESSAGE_URL, json={
                "CHAT_ID": TESTING_CHANNEL,
                "MESSAGE": success_msg
            }, verify=False)

    print(f"\nSuccessfully dispatched Team D reports/messages!")

if __name__ == '__main__':
    main()
