import requests
import pandas as pd
import re
import os
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

    # Target specific internal teams
    TARGET_TEAMS = ['BD', 'Z', 'Sachin', 'Web', 'C- Full Circle Property Management']
    
    # Organize projects by team
    teams_data = {t: {} for t in TARGET_TEAMS}
    
    for g in groups:
        project_name = g.get('NAME', '')
        gid = str(g['ID'])
        
        team_val = None
        if " - " in project_name:
            team_val = project_name.split(" - ")[0].strip()
        else:
            team_val = project_name.strip()
            
        if team_val in TARGET_TEAMS:
            safe_name = re.sub(r'[\\/*?:\[\]]', '', project_name)[:31]
            teams_data[team_val][gid] = {
                'Full Name': project_name,
                'Sheet Name': safe_name
            }
    
    out_dir = r"C:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation\teams"
    os.makedirs(out_dir, exist_ok=True)
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    for team_prefix, team_projects in teams_data.items():
        if not team_projects:
            continue
            
        print(f"\nProcessing Internal Team {team_prefix} (Found {len(team_projects)} projects)...")
        group_ids = list(team_projects.keys())
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
                tasks = v.get('tasks', [])
                if tasks:
                    all_overdue_tasks[gid] = tasks

        # Fix filename if prefix has illegal chars
        safe_prefix = re.sub(r'[\\/*?:\[\]]', '', team_prefix)
        out_file = os.path.join(out_dir, f'Team_{safe_prefix}_Detailed_Overdue_Tasks.xlsx')
        
        with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
            projects_with_tasks = 0
            sorted_gids = sorted(all_overdue_tasks.keys(), key=lambda x: team_projects[x]['Sheet Name'])
            
            overview_data = []
            for gid in sorted_gids:
                if gid in all_overdue_tasks and all_overdue_tasks[gid]:
                    tasks = all_overdue_tasks[gid]
                    overview_data.append({
                        'Project': team_projects[gid]['Full Name'],
                        'Overdue Tasks Count': len(tasks)
                    })
                
            if overview_data:
                pd.DataFrame(overview_data).sort_values(by='Overdue Tasks Count', ascending=False).to_excel(writer, sheet_name='Overview', index=False)
            else:
                pd.DataFrame([{'Message': f'No overdue tasks found for Team {team_prefix}'}]).to_excel(writer, sheet_name='Overview', index=False)
                
            for gid in sorted_gids:
                if gid not in all_overdue_tasks or not all_overdue_tasks[gid]:
                    continue
                tasks = all_overdue_tasks[gid]
                sheet_name = team_projects[gid]['Sheet Name']
                
                task_list = []
                for t in tasks:
                    resp_info = t.get('responsible', {})
                    resp_name = resp_info.get('name', f"User {t.get('responsibleId')}")
                    
                    deadline = t.get('deadline', '')
                    if deadline:
                        deadline = deadline.split('T')[0]
                        
                    status_map = {'-1': 'Overdue (Old)', '1': 'New', '2': 'Pending', '3': 'In Progress', '4': 'Supposedly Completed', '6': 'Deferred'}
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
                    df_tasks = df_tasks.sort_values(by='Deadline')
                    df_tasks.to_excel(writer, sheet_name=sheet_name, index=False)
                    projects_with_tasks += 1
                    
        print(f"Saved {projects_with_tasks} project sheets to {out_file}")
        
    print("\nAll internal teams processed successfully!")

if __name__ == "__main__":
    main()
