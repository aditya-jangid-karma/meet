import os
import glob
import base64
import requests
import urllib3
import excel2img

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UPLOAD_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/disk.folder.uploadfile"
COMMIT_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.disk.file.commit"

FOLDER_ID = "15372"

# Mapping of Leads to their specific Bitrix CHAT_ID
LEAD_CHATS = {
    "Zeel_Patel": "6170",
    "Krishnakumar_Bang": "6164",
    "Rahul_Gajera": "137360"
}

def upload_file_to_disk(file_path):
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
    return None

files = glob.glob('*_Final_Report.xlsx')

for f in files:
    # Identify the lead from the filename
    lead_name = None
    for key in LEAD_CHATS.keys():
        if f.startswith(key):
            lead_name = key
            break
            
    if not lead_name:
        print(f"Skipping {f} - unknown lead.")
        continue
        
    chat_id = LEAD_CHATS[lead_name]
    print(f"\nProcessing {f} for {lead_name} (Chat ID: {chat_id})...")
    
    img_name = f.replace('.xlsx', '_New_Screenshot.png')
    
    # Generate screenshot if not exists
    if not os.path.exists(img_name):
        try:
            excel2img.export_img(f, img_name, "Overview", None)
        except Exception as e:
            print(f"Failed to generate screenshot: {e}")
            continue
            
    excel_disk_id = upload_file_to_disk(f)
    img_disk_id = upload_file_to_disk(img_name)
    
    if excel_disk_id and img_disk_id:
        print(f"Sending to lead chat {chat_id}...")
        
        # Message 1: Screenshot (no text)
        payload1 = {
            "CHAT_ID": chat_id,
            "MESSAGE": " ", # Space to avoid empty message error
            "DISK_ID": [img_disk_id]
        }
        requests.post(COMMIT_URL, json=payload1, verify=False)
        
        # Message 2: Excel file with caption
        payload2 = {
            "CHAT_ID": chat_id,
            "MESSAGE": f"Here is the latest overdue task report:\n{f}",
            "DISK_ID": [excel_disk_id]
        }
        requests.post(COMMIT_URL, json=payload2, verify=False)
        
        print("Sending to Testing Channel (345986)...")
        # Testing Channel Message 1
        payload1_test = {
            "CHAT_ID": "345986",
            "MESSAGE": " ",
            "DISK_ID": [img_disk_id]
        }
        requests.post(COMMIT_URL, json=payload1_test, verify=False)
        
        # Testing Channel Message 2
        payload2_test = {
            "CHAT_ID": "345986",
            "MESSAGE": f"Here is the latest overdue task report for {lead_name}:\n{f}",
            "DISK_ID": [excel_disk_id]
        }
        requests.post(COMMIT_URL, json=payload2_test, verify=False)

print("Successfully dispatched all reports to the lead channels!")
