import requests

groups_url = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json"
start = 0
gid = None
while True:
    resp = requests.get(f"{groups_url}?start={start}", verify=False).json()
    for g in resp.get('result', []):
        if 'C136A' in g['NAME']:
            gid = g['ID']
            break
    if gid or 'next' not in resp:
        break
    start = resp['next']

url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
params = {
    'filter[GROUP_ID]': gid,
    'filter[<DEADLINE]': '2026-09-29T00:00:00',
    'filter[!STATUS]': '5',
    'select[]': ['ID', 'TITLE', 'STATUS', 'DEADLINE', 'RESPONSIBLE_ID']
}

resp = requests.get(url, params=params, verify=False).json()
tasks = resp.get('result', {}).get('tasks', [])
print(f"Total tasks: {len(tasks)}")
c_count = 0
for t in tasks:
    print(f"{t.get('deadline')} - {t.get('status')} - {t.get('title')} ")
    c_count+=1
