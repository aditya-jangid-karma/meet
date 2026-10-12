# import requests
# import base64
# import os
# import urllib3
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# WEBHOOK_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/"
# CHAT_ID = "chat345986"

# files_to_send = [
#     "Krishnakumar_Bang_Detailed_Overdue.xlsx",
#     "Rahul_Gajera_Detailed_Overdue.xlsx",
#     "Zeel_Patel_Detailed_Overdue.xlsx"
# ]

# def send_files_to_bitrix():
#     print(f"Starting upload to Bitrix24 channel: {CHAT_ID}")
    
#     # STEP 1: Get the folder ID for the chat storage
#     numeric_chat_id = CHAT_ID.replace("chat", "")
#     folder_resp = requests.post(f"{WEBHOOK_URL}im.disk.folder.get.json", json={"chat_id": numeric_chat_id}, verify=False).json()
#     folder_id = folder_resp.get('result', {}).get('ID')
    
#     if not folder_id:
#         print("Error: Could not find the storage folder for this chat.")
#         return

#     for filename in files_to_send:
#         if not os.path.exists(filename):
#             print(f"Skipping {filename} - File not found locally.")
#             continue
            
#         print(f"Uploading {filename} to Bitrix Drive...")
        
#         # Read the Excel file in binary and encode it in base64
#         with open(filename, "rb") as f:
#             file_data_base64 = base64.b64encode(f.read()).decode('utf-8')

#         # STEP 2: Upload the file to the chat's folder
#         upload_payload = {
#             "id": folder_id,
#             "data": {"NAME": filename},
#             "fileContent": [filename, file_data_base64],
#             "generateUniqueName": True
#         }
#         upload_resp = requests.post(f"{WEBHOOK_URL}disk.folder.uploadfile.json", json=upload_payload, verify=False).json()
        
#         # Extract the Bitrix file ID from the upload response
#         bitrix_file_id = upload_resp.get('result', {}).get('ID')
        
#         if bitrix_file_id:
#             # STEP 3: Send the message to the channel with the file attached
#             message_payload = {
#                 "CHAT_ID": numeric_chat_id,
#                 "MESSAGE": f"Here is the latest overdue task report: {filename}",
#                 "DISK_ID": bitrix_file_id
#             }
#             requests.post(f"{WEBHOOK_URL}im.disk.file.commit.json", json=message_payload, verify=False)
#             print(f"Successfully sent {filename} to the channel!")
#         else:
#             print(f"Failed to upload {filename}. API Response: {upload_resp}")

# if __name__ == "__main__":
#     send_files_to_bitrix()






import os
import glob
import base64
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Bitrix API endpoints
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
    if not os.path.exists(file_path):
        print(f"Warning: File not found {file_path}")
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
    
    img_name = f.replace('.xlsx', '_Screenshot.png')
            
    excel_disk_id = upload_file_to_disk(f)
    img_disk_id = upload_file_to_disk(img_name) if os.path.exists(img_name) else None
    
    if excel_disk_id:
        print(f"Sending to lead chat {chat_id}...")
        
        # Message 1: Screenshot (no text)
        if img_disk_id:
            payload1 = {
                "CHAT_ID": chat_id,
                "MESSAGE": " ", # Space to avoid empty message error
                "DISK_ID": [img_disk_id]
            }
            requests.post(COMMIT_URL, json=payload1, verify=False)
        
        # Message 2: Excel file with caption
        payload2 = {
            "CHAT_ID": chat_id,
            "MESSAGE": f"Here is the latest overdue & upcoming task report:\n{f}",
            "DISK_ID": [excel_disk_id]
        }
        requests.post(COMMIT_URL, json=payload2, verify=False)
        
        print("Sending to Testing Channel (345986)...")
        # Testing Channel Message 1
        if img_disk_id:
            payload1_test = {
                "CHAT_ID": "345986",
                "MESSAGE": " ",
                "DISK_ID": [img_disk_id]
            }
            requests.post(COMMIT_URL, json=payload1_test, verify=False)
        
        # Testing Channel Message 2
        payload2_test = {
            "CHAT_ID": "345986",
            "MESSAGE": f"Here is the latest overdue & upcoming task report for {lead_name}:\n{f}",
            "DISK_ID": [excel_disk_id]
        }
        requests.post(COMMIT_URL, json=payload2_test, verify=False)

print("\nSuccessfully dispatched all reports to the lead channels!")