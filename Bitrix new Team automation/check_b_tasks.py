import requests

groups_url = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json"
start = 0
gid = None
while True:
    resp = requests.get(f"{groups_url}?start={start}", verify=False).json()
    for g in resp.get('result', []):
        if 'C101C' in g['NAME']:
            gid = g['ID']
            print(f"Found Group: {g['NAME']} (ID: {gid})")
    if 'next' not in resp:
        break
    start = resp['next']

if gid:
    url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
    params = {
        'filter[GROUP_ID]': gid,
        'filter[!STATUS]': '5',
        'select[]': ['ID', 'TITLE', 'STATUS', 'DEADLINE', 'RESPONSIBLE_ID']
    }
    resp = requests.get(url, params=params, verify=False).json()
    tasks = resp.get('result', {}).get('tasks', [])
    print(f"Total active tasks: {len(tasks)}")
    for t in tasks[:5]:
        print(f"{t.get('deadline')} - {t.get('status')} - {t.get('title')} ")
