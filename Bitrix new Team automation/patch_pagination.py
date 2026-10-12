import os

target_block = '''    for i in range(0, len(group_ids), 16):
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
            elif task_type == 'tomorrow': tomorrow_tasks[gid] = valid_tasks'''

replacement_block = '''    for i in range(0, len(group_ids), 16):
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
            for k, start_val in next_pages.items():
                next_cmd[k] = base_cmd[k] + f'&start={start_val}'
                
            active_cmd = next_cmd'''

for file_path in ['Team D/process_team_d.py', 'Team H/process_team_h.py']:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if target_block in content:
        content = content.replace(target_block, replacement_block)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Patched pagination in {file_path}")
    else:
        print(f"Could not find exact block in {file_path}")
