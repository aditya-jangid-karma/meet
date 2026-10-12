import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import glob
import os
import re
import excel2img
import base64
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UPLOAD_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/disk.folder.uploadfile"
COMMIT_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.disk.file.commit"
CHAT_ID = "345986"
FOLDER_ID = "15372"

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

header_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
header_font = Font(color="FFFFFF", bold=True)
alt_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

for f in files:
    print(f"\nProcessing {f}...")
    wb = openpyxl.load_workbook(f)
    
    # 1. Read all tasks from 'All Client Groups'
    ws_all = wb['All Client Groups']
    
    tasks_by_person = {}
    
    # Structure of All Client Groups:
    # Row with project name
    # Header: Task ID, Client Nam, Task Title, Deadline, Responsible Person, Status
    # Tasks
    
    for row in range(1, ws_all.max_row + 1):
        cell_id = ws_all.cell(row=row, column=1).value
        # Check if it's a task row (has ID and is not 'Task ID' header)
        if cell_id and str(cell_id).isdigit():
            t_id = cell_id
            c_nam = ws_all.cell(row=row, column=2).value
            t_title = ws_all.cell(row=row, column=3).value
            deadline = ws_all.cell(row=row, column=4).value
            person = str(ws_all.cell(row=row, column=5).value).strip()
            status = ws_all.cell(row=row, column=6).value
            
            if person and person.lower() != 'none':
                if person not in tasks_by_person:
                    tasks_by_person[person] = []
                tasks_by_person[person].append({
                    'Task ID': t_id,
                    'Client': c_nam,
                    'Task Title': t_title,
                    'Deadline': deadline,
                    'Status': status
                })
                
    # 2. Add to Overview Tab (Col H & I)
    ws_over = wb['Overview']
    
    ws_over.cell(row=4, column=7, value='Responsible Person').fill = header_fill
    ws_over.cell(row=4, column=7).font = header_font
    ws_over.cell(row=4, column=8, value='Task Count').fill = header_fill
    ws_over.cell(row=4, column=8).font = header_font
    
    row_idx = 5
    # Sort persons by task count descending
    sorted_persons = sorted(tasks_by_person.items(), key=lambda x: len(x[1]), reverse=True)
    
    for person, tasks in sorted_persons:
        ws_over.cell(row=row_idx, column=7, value=person)
        c = ws_over.cell(row=row_idx, column=8, value=len(tasks))
        c.alignment = Alignment(horizontal='center')
        
        # Color the task count red if it's overdue
        c.fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        c.font = Font(color="C00000", bold=True)
        
        row_idx += 1
        
    # AutoFilter on H4:I... doesn't work well if there's already one on A:F, but we can try
    # We will just leave it without filter or extend the filter. Since it's disjoint, we won't add a filter object.
    
    ws_over.column_dimensions['F'].width = 5
    ws_over.column_dimensions['G'].width = 30
    ws_over.column_dimensions['H'].width = 15

    # 3. Create sheets for each Responsible Person
    for person, tasks in sorted_persons:
        safe_name = re.sub(r'[\\/*?:\[\]]', '', person)[:31] # Excel sheet name limit
        
        # If sheet exists, remove it
        if safe_name in wb.sheetnames:
            del wb[safe_name]
            
        ws_p = wb.create_sheet(safe_name)
        
        # Headers
        headers = ['Task ID', 'Client Name', 'Task Title', 'Deadline', 'Status']
        for col_idx, h in enumerate(headers, 1):
            c = ws_p.cell(row=1, column=col_idx, value=h)
            c.fill = header_fill
            c.font = header_font
            
        # Data
        for idx, t in enumerate(tasks):
            r = idx + 2
            ws_p.cell(row=r, column=1, value=t['Task ID'])
            ws_p.cell(row=r, column=2, value=t['Client'])
            ws_p.cell(row=r, column=3, value=t['Task Title'])
            ws_p.cell(row=r, column=4, value=t['Deadline'])
            ws_p.cell(row=r, column=5, value=t['Status'])
            
            if r % 2 == 1:
                for c_idx in range(1, 6):
                    ws_p.cell(row=r, column=c_idx).fill = alt_fill
                    
        ws_p.column_dimensions['A'].width = 12
        ws_p.column_dimensions['B'].width = 25
        ws_p.column_dimensions['C'].width = 60
        ws_p.column_dimensions['D'].width = 15
        ws_p.column_dimensions['E'].width = 15
        ws_p.freeze_panes = 'A2'
        
    wb.save(f)
    print(f"Saved {f}")
    
    # 4. Generate Screenshot for send_to_leads
    img_name = f.replace('.xlsx', '_New_Screenshot.png')
    excel2img.export_img(f, img_name, "Overview", None)
    
print("All files built successfully!")
