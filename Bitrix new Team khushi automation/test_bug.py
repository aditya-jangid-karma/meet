import requests

BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"
# Get a real group ID that has tasks
resp = requests.get('https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json', verify=False).json()
gids = [g['ID'] for g in resp['result'][:5]]

cmd = {}
for gid in gids:
    cmd[f'all_{gid}'] = f'tasks.task.list?filter[GROUP_ID]={gid}&filter[!STATUS]=5'
    
batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
results = batch_resp.get('result', {}).get('result', {})

for gid in gids:
    tasks = results.get(f'all_{gid}', {}).get('tasks', [])
    print(f"Group {gid} has {len(tasks)} active tasks")
    if tasks:
        print("First task deadline:", tasks[0].get('deadline'))
