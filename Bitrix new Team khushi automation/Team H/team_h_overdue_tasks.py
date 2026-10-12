import requests
import pandas as pd
import re
from datetime import datetime
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GROUPS_URL = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json"
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

def main():
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

    # Regex to capture: Team - Client - Person - Code
    pattern = r'^([A-Za-z0-9]+)\s*-\s*(.*?)\s*-\s*([^-]+?)\s*(?:-|\()\s*([A-Za-z0-9]+)\)?$'
    
    team_h_projects = {}
    for g in groups:
        project_name = g.get('NAME', '')
        gid = str(g['ID'])
        match = re.match(pattern, project_name)
        
        if match:
            team, client, person, code = match.groups()
            team_val = team.strip().upper()
            if team_val == 'H':
                # Use Client Code + Client Name for sheet name, ensuring it's valid for Excel
                safe_name = f"{code.strip()} {client.strip()}"[:31]
                safe_name = re.sub(r'[\\/*?:\[\]]', '', safe_name)
                team_h_projects[gid] = {
                    'Full Name': project_name,
                    'Sheet Name': safe_name
                }
                
    print(f"Found {len(team_h_projects)} projects for Team H.")
    
    today = datetime.now().strftime('%Y-%m-%d')
    group_ids = list(team_h_projects.keys())
    
    print("Fetching overdue tasks for Team H projects...")
    
    all_overdue_tasks = {}
    
    # Process in chunks of 50 for Batch API
    for i in range(0, len(group_ids), 50):
        chunk = group_ids[i:i+50]
        cmd = {}
        for gid in chunk:
            # Fetch tasks where deadline is before today and not completed
            cmd[f'g_{gid}'] = f'tasks.task.list?filter[GROUP_ID]={gid}&filter[<DEADLINE]={today}T00:00:00&filter[!STATUS]=5'
        
        batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
        results = batch_resp.get('result', {}).get('result', {})
        
        for k, v in results.items():
            gid = k.replace('g_', '')
            # Bitrix batch tasks.task.list returns {'tasks': [...]}
            tasks = v.get('tasks', [])
            if tasks:
                all_overdue_tasks[gid] = tasks

    out_file = 'Team_H_Detailed_Overdue_Tasks.xlsx'
    print(f"Generating Excel File: {out_file}...")
    
    with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
        projects_with_tasks = 0
        
        # Sort projects alphabetically by sheet name
        sorted_gids = sorted(all_overdue_tasks.keys(), key=lambda x: team_h_projects[x]['Sheet Name'])
        
        # Create an Overview sheet
        overview_data = []
        for gid in sorted_gids:
            tasks = all_overdue_tasks[gid]
            overview_data.append({
                'Project': team_h_projects[gid]['Full Name'],
                'Overdue Tasks Count': len(tasks)
            })
            
        if overview_data:
            pd.DataFrame(overview_data).sort_values(by='Overdue Tasks Count', ascending=False).to_excel(writer, sheet_name='Overview', index=False)
        else:
            pd.DataFrame([{'Message': 'No overdue tasks found for Team H'}]).to_excel(writer, sheet_name='Overview', index=False)
            
        # Create individual project sheets
        for gid in sorted_gids:
            tasks = all_overdue_tasks[gid]
            sheet_name = team_h_projects[gid]['Sheet Name']
            
            task_list = []
            for t in tasks:
                resp_info = t.get('responsible', {})
                resp_name = resp_info.get('name', f"User {t.get('responsibleId')}")
                
                # Format deadline
                deadline = t.get('deadline', '')
                if deadline:
                    deadline = deadline.split('T')[0]
                    
                status_map = {
                    '-1': 'Overdue (Old)',
                    '1': 'New',
                    '2': 'Pending',
                    '3': 'In Progress',
                    '4': 'Supposedly Completed',
                    '6': 'Deferred'
                }
                status_code = str(t.get('status', ''))
                status_text = status_map.get(status_code, status_code)
                
                task_list.append({
                    'Task ID': t.get('id'),
                    'Task Title': t.get('title'),
                    'Deadline': deadline,
                    'Responsible Person': resp_name,
                    'Status': status_text
                })
                
            if task_list:
                df_tasks = pd.DataFrame(task_list)
                # Sort tasks by deadline (oldest first)
                df_tasks = df_tasks.sort_values(by='Deadline')
                df_tasks.to_excel(writer, sheet_name=sheet_name, index=False)
                projects_with_tasks += 1
                
        if projects_with_tasks == 0:
            print("No Team H projects have overdue tasks!")

    print(f"Done! Saved {projects_with_tasks} project sheets to {out_file}")

if __name__ == "__main__":
    main()
