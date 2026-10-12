import requests
import openpyxl
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import re
import os
import excel2img
from datetime import datetime, timedelta
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GROUPS_URL = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json"
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

def main():
    out_dir = r"."
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
    
    teams_data = {}
    
    for g in groups:
        project_name = g.get('NAME', '')
        gid = str(g['ID'])
        match = re.match(pattern, project_name)
        if match:
            team, client, person, code = match.groups()
            team_val = team.strip().upper()
            code_val = code.strip()
            
            if team_val not in ['D', 'H'] and team_val:
                if team_val not in teams_data:
                    teams_data[team_val] = {}
                
                safe_name = f"{code_val} {client.strip()}"[:31]
                safe_name = re.sub(r'[\\/*?:\[\]]', '', safe_name)
                teams_data[team_val][gid] = {
                    'Full Name': project_name,
                    'Sheet Name': safe_name,
                    'Code': code_val,
                    'Client': client.strip()
                }
                
    print(f"Found projects for Teams: {', '.join(teams_data.keys())}")
    
    l1_groups = {}
    for team_prefix, projs in teams_data.items():
        l1_groups[f"Team_{team_prefix}"] = list(projs.keys())
        
    team_d_projects = {}
    for team_prefix, projs in teams_data.items():
        team_d_projects.update(projs)
        
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
    
    group_ids = list(team_d_projects.keys())
    
    print("Fetching tasks (Overdue, Due Today, Due Tomorrow)...")
    overdue_tasks = {}
    today_tasks = {}
    tomorrow_tasks = {}
    
    for i in range(0, len(group_ids), 16):
        chunk = group_ids[i:i+16]
        cmd = {}
        for gid in chunk:
            cmd[f'overdue_{gid}'] = f'tasks.task.list?filter[GROUP_ID]={gid}&filter[<DEADLINE]={start_of_today}&filter[!STATUS]=5'
            cmd[f'today_{gid}'] = f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]={start_today_gt}&filter[<DEADLINE]={end_today_lt}&filter[!STATUS]=5'
            cmd[f'tomorrow_{gid}'] = f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]={start_tomorrow_gt}&filter[<DEADLINE]={end_tomorrow_lt}&filter[!STATUS]=5'
            
        batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
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
                    
            if task_type == 'overdue': overdue_tasks[gid] = valid_tasks
            elif task_type == 'today': today_tasks[gid] = valid_tasks
            elif task_type == 'tomorrow': tomorrow_tasks[gid] = valid_tasks

    # l1_groups already built above!
    for l1, gids in l1_groups.items():
        if l1 == 'Unknown Lead':
            continue
            
        print(f"Generating Final Report for {l1}...")
        safe_l1 = re.sub(r'[\\/*?:\[\]]', '_', l1).replace(' ', '_')
        final_file = os.path.join(out_dir, f"{safe_l1}_Final_Report.xlsx")
        
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
                
            proj_info = team_d_projects[gid]
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
                    'Due Today': counts['today'],
                    'Due Tomorrow': counts['tomorrow']
                })
            
            # If a client had tasks but NO assigned people (rare), ensure we still have a row
            if not sorted_persons:
                client_rows.append({
                    'Client Code': code,
                    'Client': client,
                    'Responsible Person': 'Unknown',
                    'Overdue Tasks': len(o_tasks),
                    'Due Today': len(td_tasks),
                    'Due Tomorrow': len(tm_tasks)
                })
            
            # Add blank spacer row
            client_rows.append({
                'Client Code': '', 'Client': '', 'Responsible Person': '',
                'Overdue Tasks': '', 'Due Today': '', 'Due Tomorrow': ''
            })
            
            for t in o_tasks:
                status_map = {'-1': 'Overdue (Old)', '1': 'New', '2': 'Pending', '3': 'In Progress', '4': 'Supposedly Completed', '6': 'Deferred'}
                status_code = str(t.get('status', ''))
                deadline = t.get('deadline', '').split('T')[0] if t.get('deadline') else ''
                rname = t.get('responsible', {}).get('name', 'Unknown')
                all_tasks_data.append({
                    'Client': client,
                    'Task ID': t.get('id'),
                    'Task Title': t.get('title'),
                    'Deadline': deadline,
                    'Responsible Person': rname,
                    'Status': status_map.get(status_code, status_code)
                })

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
                'Task Count': sorted_overall_resp[i][1] if i < len(sorted_overall_resp) else ''
            }
            overview_data.append(row_dict)
            
        with pd.ExcelWriter(final_file, engine='openpyxl') as writer:
            df_overview = pd.DataFrame(overview_data)
            df_overview.to_excel(writer, sheet_name='Overview', index=False)
            
            df_all = pd.DataFrame(all_tasks_data)
            if not df_all.empty:
                df_all = df_all.sort_values(by=['Client', 'Deadline'])
            
            # Write All Client Groups (renamed from All Overdue Tasks to match Team H)
            df_all.to_excel(writer, sheet_name='All Client Groups', index=False)
            
            # Create a tab for each unique Responsible Person
            if not df_all.empty:
                resp_persons = df_all['Responsible Person'].unique()
                for rp in resp_persons:
                    if not rp or rp == 'Unknown': continue
                    safe_name = re.sub(r'[\\/*?:\[\]]', '', str(rp))[:31]
                    df_rp = df_all[df_all['Responsible Person'] == rp]
                    df_rp.to_excel(writer, sheet_name=safe_name, index=False)
            
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
            
            # Apply styling to all the generated data sheets (All Client Groups and Responsible Persons)
            alt_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
            for sheet_name in wb.sheetnames:
                if sheet_name == 'Overview': continue
                s = wb[sheet_name]
                s.freeze_panes = 'A2'
                
                # Headers
                for col_idx in range(1, s.max_column + 1):
                    c = s.cell(row=1, column=col_idx)
                    c.fill = header_fill
                    c.font = header_font
                    
                # Alternate colors and widths
                for r_idx in range(2, s.max_row + 1):
                    if r_idx % 2 == 1:
                        for c_idx in range(1, s.max_column + 1):
                            s.cell(row=r_idx, column=c_idx).fill = alt_fill
                            
                s.column_dimensions['A'].width = 25
                s.column_dimensions['B'].width = 15
                s.column_dimensions['C'].width = 60
                s.column_dimensions['D'].width = 15
                s.column_dimensions['E'].width = 25
                s.column_dimensions['F'].width = 15
            
        # Screenshot
        img_name = final_file.replace('.xlsx', '_Screenshot.png')
        try:
            excel2img.export_img(final_file, img_name, "Overview", None)
        except Exception as e:
            print(f"Could not generate screenshot: {e}")
            
    print("\nAll Other Teams pipeline completed!")

if __name__ == "__main__":
    main()

