import requests
import pandas as pd
import re
import os
from datetime import datetime, timedelta
import urllib3
import excel2img
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GROUPS_URL = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json"
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

import pandas as pd
df_mapping = pd.read_excel('../Team-C_Client_Overdue_Tasks.xlsx')
team_c_mapping = {}
for _, row in df_mapping.iterrows():
    team_c_mapping[str(row['Client Code'])] = str(row['L1 (Project Lead)'])


def build_grouped_sheet(ws, tasks_data):
    if not tasks_data:
        return
        
    df = pd.DataFrame(tasks_data)
    
    type_order = {'Overdue (Old)': 0, 'Due Today': 1, 'Due Tomorrow': 2}
    df['Type_Sort'] = df['Type'].map(type_order).fillna(3)
    df = df.sort_values(by=['Client', 'Type_Sort', 'Deadline'])
    
    headers = ['Type', 'Client', 'Task ID', 'Task Title', 'Deadline', 'Responsible Person', 'Status']
    header_fill = PatternFill(start_color="1A3B69", end_color="1A3B69", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    group_font = Font(size=14, bold=True)
    
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))
                         
    row_idx = 1
    
    for client, group in df.groupby('Client', sort=False):
        code = group.iloc[0].get('Client Code', '')
        ws.cell(row=row_idx, column=1, value=f"{code} {client}").font = group_font
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=len(headers))
        row_idx += 1
        
        for col_idx, h in enumerate(headers, 1):
            c = ws.cell(row=row_idx, column=col_idx, value=h)
            c.fill = header_fill
            c.font = header_font
        row_idx += 1
        
        for _, row in group.iterrows():
            vals = [
                row.get('Type', ''), row.get('Client', ''), row.get('Task ID', ''),
                row.get('Task Title', ''), row.get('Deadline', ''),
                row.get('Responsible Person', ''), row.get('Status', '')
            ]
            for col_idx, val in enumerate(vals, 1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.border = thin_border
            row_idx += 1
            
        row_idx += 1
        
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 45
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 25
    ws.column_dimensions['G'].width = 15

def main():
    out_dir = r"team_c_output"
    os.makedirs(out_dir, exist_ok=True)
    
    print("Fetching all projects from Bitrix24...")
    groups = []
    start = 0
    while True:
        resp = requests.get(f"{GROUPS_URL}?start={start}", verify=False).json()
        batch = resp.get('result', [])
        groups.extend(batch)
        if 'next' in resp:
            start = resp['next']
        else:
            break

    pattern = r'^([A-Za-z0-9]+)\s*-\s*(.*?)\s*-\s*([^-]+?)\s*(?:-|\()\s*(C\d+[A-Z]+)'
    
    team_c_projects = {}
    for g in groups:
        project_name = g.get('NAME', '')
        gid = str(g['ID'])
        match = re.match(pattern, project_name)
        if match:
            team, client, person, code = match.groups()
            team_val = team.strip().upper()
            code_val = code.strip()
            if team_val == 'C':
                l1_lead = team_c_mapping.get(code_val, 'Unknown Lead')
                safe_name = f"{code_val} {client.strip()}"[:31]
                safe_name = re.sub(r'[\\/*?:\[\]]', '', safe_name)
                team_c_projects[gid] = {
                    'Full Name': project_name,
                    'Sheet Name': safe_name,
                    'Code': code_val,
                    'Client': client.strip(),
                    'L1': l1_lead
                }
                
    print(f"Found {len(team_c_projects)} projects for Team C.")
    
    today_dt = datetime.now()
    tomorrow_dt = today_dt + timedelta(days=1)
    yesterday_dt = today_dt - timedelta(days=1)
    day_after_dt = today_dt + timedelta(days=2)
    
    today_str = today_dt.strftime('%Y-%m-%d')
    tomorrow_str = tomorrow_dt.strftime('%Y-%m-%d')
    yesterday_str = yesterday_dt.strftime('%Y-%m-%d')
    day_after_str = day_after_dt.strftime('%Y-%m-%d')
    
    start_of_today = f"{today_str}T00:00:00"
    
    start_today_gt = f"{yesterday_str}T23:59:59"
    end_today_lt = f"{tomorrow_str}T00:00:00"
    
    start_tomorrow_gt = f"{today_str}T23:59:59"
    end_tomorrow_lt = f"{day_after_str}T00:00:00"
    
    group_ids = list(team_c_projects.keys())
    
    print("Fetching tasks (Overdue, Due Today, Due Tomorrow)...")
    overdue_tasks = {}
    today_tasks = {}
    tomorrow_tasks = {}
    
    for i in range(0, len(group_ids), 16):
        chunk = group_ids[i:i+16]
        base_cmd = {}
        for gid in chunk:
            base_cmd[f'overdue_{gid}'] = f'tasks.task.list?filter[GROUP_ID]={gid}&filter[<DEADLINE]={start_of_today}&filter[!STATUS]=5'
            base_cmd[f'today_{gid}'] = f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]={start_today_gt}&filter[<DEADLINE]={end_today_lt}&filter[!STATUS]=5'
            base_cmd[f'tomorrow_{gid}'] = f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]={start_tomorrow_gt}&filter[<DEADLINE]={end_tomorrow_lt}&filter[!STATUS]=5'
            
        active_cmd = base_cmd.copy()
        
        while active_cmd:
            batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': active_cmd}, verify=False).json()
            results = batch_resp.get('result', {}).get('result', {})
            
            for k, v in results.items():
                parts = k.split('_')
                task_type = parts[0]
                gid = parts[1]
                tasks = v.get('tasks', [])
                
                # Filter out dismissed
                valid_tasks = []
                for t in tasks:
                    resp_name = t.get('responsible', {}).get('name', '').lower()
                    if 'dismissed' not in resp_name:
                        valid_tasks.append(t)
                        
                if task_type == 'overdue': overdue_tasks.setdefault(gid, []).extend(valid_tasks)
                elif task_type == 'today': today_tasks.setdefault(gid, []).extend(valid_tasks)
                elif task_type == 'tomorrow': tomorrow_tasks.setdefault(gid, []).extend(valid_tasks)
                
            next_pages = batch_resp.get('result', {}).get('result_next', {})
            next_cmd = {}
            if isinstance(next_pages, dict):
                for k, start_val in next_pages.items():
                    next_cmd[k] = base_cmd[k] + f'&start={start_val}'
                
            active_cmd = next_cmd

    # Process per L1
    l1_groups = {}
    for gid, proj in team_c_projects.items():
        l1 = proj['L1']
        if l1 not in l1_groups:
            l1_groups[l1] = []
        l1_groups[l1].append(gid)
        
    for l1, gids in l1_groups.items():
        if l1 == 'Unknown Lead':
            continue
            
        print(f"Generating Final Report for {l1}...")
        safe_l1 = re.sub(r'[\\/*?:\[\]]', '_', l1).replace(' ', '_')
        today_str = datetime.today().strftime("%d-%m-%Y")
        final_file = os.path.join(out_dir, f"{safe_l1}_{today_str}.xlsx")
        
        all_tasks_data = []
        overview_data = []
        
        client_rows = []
        overall_resp_counts = {}
        
        for gid in gids:
            o_tasks = overdue_tasks.get(gid, [])
            td_tasks = today_tasks.get(gid, [])
            tm_tasks = tomorrow_tasks.get(gid, [])
            
            if not o_tasks and not td_tasks and not tm_tasks:
                continue
                
            proj_info = team_c_projects[gid]
            code = proj_info['Code']
            client = proj_info['Client']
            
            # Count tasks by person
            person_counts = {}
            def add_to_person(task_list, key):
                for t in task_list:
                    rname = t.get('responsible', {}).get('name', 'Unknown')
                    if rname not in person_counts:
                        person_counts[rname] = {'overdue': 0, 'today': 0, 'tomorrow': 0}
                    person_counts[rname][key] += 1
                    
                    if key == 'overdue':
                        overall_resp_counts[rname] = overall_resp_counts.get(rname, 0) + 1
                        
            add_to_person(o_tasks, 'overdue')
            add_to_person(td_tasks, 'today')
            add_to_person(tm_tasks, 'tomorrow')
            
            # Sort persons by overdue count descending, then by name
            sorted_persons = sorted(person_counts.items(), key=lambda x: (x[1]['overdue'], x[1]['today'], x[1]['tomorrow']), reverse=True)
            
            # Create a row for each person
            for idx, (rname, counts) in enumerate(sorted_persons):
                client_rows.append({
                    'Client Code': code if idx == 0 else '',
                    'Client': client if idx == 0 else '',
                    'Responsible Person': rname,
                    'Overdue Tasks': counts['overdue'],
                    'Due Today': counts['today'] if counts['today'] > 0 else 0,
                    'Due Tomorrow': counts['tomorrow'] if counts['tomorrow'] > 0 else 0
                })
            
            # If a client had tasks but NO assigned people (rare), ensure we still have a row
            if not sorted_persons:
                client_rows.append({
                    'Client Code': code,
                    'Client': client,
                    'Responsible Person': 'Unknown',
                    'Overdue Tasks': len(o_tasks),
                    'Due Today': total_today,
                    'Due Tomorrow': total_tomorrow
                })
            
            # Add blank spacer row
            client_rows.append({
                'Client Code': '', 'Client': '', 'Responsible Person': '',
                'Overdue Tasks': '', 'Due Today': '', 'Due Tomorrow': ''
            })
            
            def append_to_all(tasks, t_type):
                for t in tasks:
                    status_map = {'-1': 'Overdue (Old)', '1': 'New', '2': 'Pending', '3': 'In Progress', '4': 'Supposedly Completed', '6': 'Deferred'}
                    status_code = str(t.get('status', ''))
                    deadline = t.get('deadline', '').split('T')[0] if t.get('deadline') else ''
                    rname = t.get('responsible', {}).get('name', 'Unknown')
                    all_tasks_data.append({
                        'Type': t_type,
                        'Client': client,
                        'Task ID': t.get('id'),
                        'Task Title': t.get('title'),
                        'Deadline': deadline,
                        'Responsible Person': rname,
                        'Status': status_map.get(status_code, status_code)
                    })
                    
            append_to_all(o_tasks, 'Overdue')
            append_to_all(td_tasks, 'Due Today')
            append_to_all(tm_tasks, 'Due Tomorrow')

        # Remove the very last spacer row if it exists
        if client_rows and client_rows[-1]['Client Code'] == '':
            client_rows.pop()

        if not client_rows:
            print(f"No tasks for {l1}. Skipping.")
            continue
            
        sorted_overall_resp = sorted(overall_resp_counts.items(), key=lambda x: x[1], reverse=True)
        max_rows = max(len(client_rows), len(sorted_overall_resp))
        
        for i in range(max_rows):
            c_row = client_rows[i] if i < len(client_rows) else {
                'Client Code': '', 'Client': '', 'Responsible Person': '', 
                'Overdue Tasks': '', 'Due Today': '', 'Due Tomorrow': ''
            }
            
            row_dict = {
                'Client Code': c_row['Client Code'],
                'Client': c_row['Client'],
                'Responsible Person': c_row['Responsible Person'],
                'Overdue Tasks': c_row['Overdue Tasks'],
                'Due Today': c_row['Due Today'],
                'Due Tomorrow': c_row['Due Tomorrow'],
                ' ': '',
                'Responsible Person (Total)': sorted_overall_resp[i][0] if i < len(sorted_overall_resp) else '',
                'Overdue Task Count': sorted_overall_resp[i][1] if i < len(sorted_overall_resp) else ''
            }
            overview_data.append(row_dict)
            
        with pd.ExcelWriter(final_file, engine='openpyxl') as writer:
            df_overview = pd.DataFrame(overview_data)
            df_overview.to_excel(writer, sheet_name='Overview', index=False)
            
            wb = writer.book
            
            # Write All Client Groups with grouping layout
            if all_tasks_data:
                ws_all = wb.create_sheet('All Client Groups')
                build_grouped_sheet(ws_all, all_tasks_data)
                
                # Create a tab for each unique Responsible Person
                df_all = pd.DataFrame(all_tasks_data)
                resp_persons = df_all['Responsible Person'].unique()
                for rp in resp_persons:
                    if not rp or rp == 'Unknown': continue
                    safe_name = re.sub(r'[\/*?:\[\]]', '', str(rp))[:31]
                    rp_tasks = [t for t in all_tasks_data if t.get('Responsible Person') == rp]
                    ws_rp = wb.create_sheet(safe_name)
                    build_grouped_sheet(ws_rp, rp_tasks)
            
            wb = writer.book
            ws = wb['Overview']
            
            # Insert title rows
            ws.insert_rows(1, 3)
            ws['A1'] = f"{l1} - Overdue & Upcoming Tasks"
            ws['A1'].font = Font(bold=True, size=14)
            ws['A2'] = "Filtered to exclude dismissed users"
            ws['A2'].font = Font(italic=True, size=10)
            ws['A3'] = "Includes Due Today and Due Tomorrow counts"
            ws['A3'].font = Font(italic=True, size=10)
            
            # Add Totals Row
            max_r = ws.max_row
            total_row = max_r + 1
            ws.cell(row=total_row, column=3, value="Total").font = Font(bold=True)
            
            # Sum columns D, E, F (4, 5, 6)
            for c_idx in [4, 5, 6]:
                # Safely parse numbers, treating NaN/None/'' as 0
                vals = []
                for r in range(5, max_r + 1):
                    v = ws.cell(row=r, column=c_idx).value
                    try:
                        num = float(v)
                        if pd.isna(num): num = 0
                    except:
                        num = 0
                    vals.append(num)
                
                sum_val = int(sum(vals))
                cell = ws.cell(row=total_row, column=c_idx, value=sum_val)
                cell.alignment = Alignment(horizontal='center')
                
                if c_idx == 4:
                    cell.font = Font(bold=True, color="C00000")
                    cell.fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
                elif c_idx == 5:
                    cell.font = Font(bold=True, color="B8860B")
                    cell.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
                elif c_idx == 6:
                    cell.font = Font(bold=True, color="375623")
                    cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
            
            # Styling
            header_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
            header_font = Font(color="FFFFFF", bold=True)
            red_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
            red_font = Font(color="C00000", bold=True)
            yellow_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
            yellow_font = Font(color="B8860B", bold=True)
            green_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
            green_font = Font(color="375623", bold=True)
            
            for col in range(1, 10):
                c = ws.cell(row=4, column=col)
                if c.value:
                    c.fill = header_fill
                    c.font = header_font
                    
            thin_border = Border(left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
                                 top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9'))
                    
            for row in range(5, max_r + 1):
                over_val = ws.cell(row=row, column=4).value
                if over_val != '':
                    c_over = ws.cell(row=row, column=4)
                    c_over.fill = red_fill
                    c_over.font = red_font
                    c_over.alignment = Alignment(horizontal='center')
                    c_over.border = thin_border
                    
                    c_today = ws.cell(row=row, column=5)
                    c_today.fill = yellow_fill
                    c_today.font = yellow_font
                    c_today.alignment = Alignment(horizontal='center')
                    c_today.border = thin_border
                    
                    c_tom = ws.cell(row=row, column=6)
                    c_tom.fill = green_fill
                    c_tom.font = green_font
                    c_tom.alignment = Alignment(horizontal='center')
                    c_tom.border = thin_border
                    
                c_count = ws.cell(row=row, column=9).value
                if c_count != '':
                    c_c = ws.cell(row=row, column=9)
                    c_c.fill = red_fill
                    c_c.font = red_font
                    c_c.alignment = Alignment(horizontal='center')
                    c_c.border = thin_border

            ws.auto_filter.ref = f"A4:F{max_r}"
            
            ws.column_dimensions['A'].width = 15
            ws.column_dimensions['B'].width = 35
            ws.column_dimensions['C'].width = 25
            ws.column_dimensions['D'].width = 18
            ws.column_dimensions['E'].width = 18
            ws.column_dimensions['F'].width = 18
            ws.column_dimensions['G'].width = 5
            ws.column_dimensions['H'].width = 25
            ws.column_dimensions['I'].width = 15
            
            # Removed the global styling loop for task sheets because build_grouped_sheet already handles it properly
        
        # Now OUTSIDE the with pd.ExcelWriter block
        import time
        time.sleep(2)
        try:
            import excel2img
            png_file = final_file.replace('.xlsx', '.png') # Use _Screenshot.png as requested by user
            excel2img.export_img(os.path.abspath(final_file), os.path.abspath(png_file), "Overview", None)
            print(f"Successfully generated screenshot: {png_file}")
        except Exception as e:
            print(f"Could not generate screenshot: {e}")
            
    print("\nTeam C pipeline completed! Files saved to team_c_output folder.")

if __name__ == "__main__":
    main()

