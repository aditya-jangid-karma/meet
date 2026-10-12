import requests
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

# Let's use group 230 or any valid group that had tasks in the screenshot.
# Wait, let's find a valid group ID by querying the groups first.
resp = requests.get('https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json?filter[NAME]=%Pangia%', verify=False).json()
groups = resp.get('result', [])
if not groups:
    print("Could not find Pangia group")
else:
    gid = groups[0]['ID']
    print(f"Found group {gid}")
    
    cmd = {
        'overdue': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[<DEADLINE]=2026-09-28T00:00:00&filter[!STATUS]=5',
        'today': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>=DEADLINE]=2026-09-28T00:00:00&filter[<=DEADLINE]=2026-09-28T23:59:59&filter[!STATUS]=5',
        'tomorrow': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>=DEADLINE]=2026-09-29T00:00:00&filter[<=DEADLINE]=2026-09-29T23:59:59&filter[!STATUS]=5'
    }
    
    batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
    results = batch_resp.get('result', {}).get('result', {})
    
    print("Overdue tasks:")
    for t in results.get('overdue', {}).get('tasks', []):
        print("  ", t['id'], t['deadline'])
        
    print("Today tasks:")
    for t in results.get('today', {}).get('tasks', []):
        print("  ", t['id'], t['deadline'])
        
    print("Tomorrow tasks:")
    for t in results.get('tomorrow', {}).get('tasks', []):
        print("  ", t['id'], t['deadline'])
