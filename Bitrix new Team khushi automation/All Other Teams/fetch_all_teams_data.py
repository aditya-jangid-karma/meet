import requests
import pandas as pd
import re
import os
from datetime import datetime, timedelta
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

    pattern = r'^([A-Za-z0-9]+)\s*-\s*(.*?)\s*-\s*([^-]+?)\s*(?:-|\()\s*([A-Za-z0-9]+)\)?$'
    
    TARGET_TEAMS = ['B', 'BD', 'C', 'CZ', 'D', 'E', 'F', 'G', 'H', 'HZ', 'I', 'Z']
    teams_data = {t: {} for t in TARGET_TEAMS}
    
    for g in groups:
        project_name = g.get('NAME', '')
        gid = str(g['ID'])
        match = re.match(pattern, project_name)
        if match:
            team, client, person, code = match.groups()
            team_val = team.strip().upper()
            if team_val in TARGET_TEAMS:
                safe_name = f"{code.strip()} {client.strip()}"[:31]
                safe_name = re.sub(r'[\\/*?:\[\]]', '', safe_name)
                teams_data[team_val][gid] = {
                    'Full Name': project_name,
                    'Sheet Name': safe_name
                }
    
    out_dir = r"."
    
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
    
    for team_prefix, team_projects in teams_data.items():
        if not team_projects:
            continue
            
        print(f"\nProcessing Team {team_prefix} (Found {len(team_projects)} projects)...")
        group_ids = list(team_projects.keys())
        
        all_overdue = {}
        all_today = {}
        all_tomorrow = {}
        
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
                if k.startswith('overdue_'):
                    gid = k.replace('overdue_', '')
                    task_type = 'overdue'
                elif k.startswith('today_'):
                    gid = k.replace('today_', '')
                    task_type = 'today'
                elif k.startswith('tomorrow_'):
                    gid = k.replace('tomorrow_', '')
                    task_type = 'tomorrow'
                    
                tasks = v.get('tasks', [])
                valid_tasks = []
                for t in tasks:
                    resp_name = t.get('responsible', {}).get('name', '').lower()
                    if 'dismissed' not in resp_name:
                        valid_tasks.append(t)
                        
                if task_type == 'overdue': all_overdue[gid] = valid_tasks
                elif task_type == 'today': all_today[gid] = valid_tasks
                elif task_type == 'tomorrow': all_tomorrow[gid] = valid_tasks

        out_file = os.path.join(out_dir, f'Team_{team_prefix}_Detailed_Tasks.xlsx')
        
        with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
            projects_with_tasks = 0
            sorted_gids = sorted(team_projects.keys(), key=lambda x: team_projects[x]['Sheet Name'])
            
            overview_data = []
            for gid in sorted_gids:
                o_tasks = all_overdue.get(gid, [])
                td_tasks = all_today.get(gid, [])
                tm_tasks = all_tomorrow.get(gid, [])
                if o_tasks or td_tasks or tm_tasks:
                    overview_data.append({
                        'Project': team_projects[gid]['Full Name'],
                        'Overdue Tasks': len(o_tasks),
                        'Due Today': len(td_tasks),
                        'Due Tomorrow': len(tm_tasks)
                    })
                
            if overview_data:
                pd.DataFrame(overview_data).sort_values(by='Overdue Tasks', ascending=False).to_excel(writer, sheet_name='Overview', index=False)
            else:
                pd.DataFrame([{'Message': f'No active tasks found for Team {team_prefix}'}]).to_excel(writer, sheet_name='Overview', index=False)
                
            for gid in sorted_gids:
                o_tasks = all_overdue.get(gid, [])
                td_tasks = all_today.get(gid, [])
                tm_tasks = all_tomorrow.get(gid, [])
                
                if not o_tasks and not td_tasks and not tm_tasks:
                    continue
                    
                sheet_name = team_projects[gid]['Sheet Name']
                
                task_list = []
                def add_tasks(tasks, type_label):
                    for t in tasks:
                        resp_name = t.get('responsible', {}).get('name', f"User {t.get('responsibleId')}")
                        deadline = t.get('deadline', '')
                        if deadline: deadline = deadline.split('T')[0]
                        status_map = {'-1': 'Overdue (Old)', '1': 'New', '2': 'Pending', '3': 'In Progress', '4': 'Supposedly Completed', '6': 'Deferred'}
                        status_code = str(t.get('status', ''))
                        status_text = status_map.get(status_code, status_code)
                        task_list.append({
                            'Type': type_label,
                            'Task ID': t.get('id'),
                            'Task Title': t.get('title'),
                            'Deadline': deadline,
                            'Responsible Person': resp_name,
                            'Status': status_text
                        })
                        
                add_tasks(o_tasks, 'Overdue')
                add_tasks(td_tasks, 'Due Today')
                add_tasks(tm_tasks, 'Due Tomorrow')
                    
                if task_list:
                    df_tasks = pd.DataFrame(task_list)
                    df_tasks.to_excel(writer, sheet_name=sheet_name, index=False)
                    projects_with_tasks += 1
                    
        print(f"Saved {projects_with_tasks} project sheets to {out_file}")
        
    print("\nAll teams processed successfully!")

if __name__ == '__main__':
    main()

