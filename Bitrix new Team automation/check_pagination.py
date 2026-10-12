import requests
import datetime
from datetime import timedelta

# Find C104A group ID
groups_url = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json"
start = 0
c104a_gid = None
while True:
    resp = requests.get(f"{groups_url}?start={start}", verify=False).json()
    for g in resp.get('result', []):
        if 'C104A' in g['NAME']:
            c104a_gid = g['ID']
            break
    if c104a_gid or 'next' not in resp:
        break
    start = resp['next']

if not c104a_gid:
    print("Could not find C104A")
    exit()

today_dt = datetime.datetime.now()
start_of_today = today_dt.strftime('%Y-%m-%d') + "T00:00:00"

url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
params = {
    'filter[GROUP_ID]': c104a_gid,
    'filter[<DEADLINE]': start_of_today,
    'filter[!STATUS]': '5',
    'select[]': ['ID']
}

all_tasks = []
start = 0
while True:
    params['start'] = start
    resp = requests.get(url, params=params, verify=False).json()
    batch = resp.get('result', {}).get('tasks', [])
    all_tasks.extend(batch)
    if 'next' in resp.get('result', {}):
        start = resp['result']['next']
    elif 'next' in resp:
        start = resp['next']
    else:
        break
        
print(f"Total REAL Overdue tasks for C104A: {len(all_tasks)}")
