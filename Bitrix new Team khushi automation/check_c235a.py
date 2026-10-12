import requests

groups_url = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json"
start = 0
c235a_gid = None
while True:
    resp = requests.get(f"{groups_url}?start={start}", verify=False).json()
    for g in resp.get('result', []):
        if 'C235A' in g['NAME']:
            c235a_gid = g['ID']
            break
    if c235a_gid or 'next' not in resp:
        break
    start = resp['next']

url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
params = {
    'filter[GROUP_ID]': c235a_gid,
    'filter[<DEADLINE]': '2026-09-29T00:00:00',
    'filter[!STATUS]': '5',
    'select[]': ['ID', 'TITLE', 'STATUS', 'DEADLINE', 'RESPONSIBLE_ID']
}

resp = requests.get(url, params=params, verify=False).json()
tasks = resp.get('result', {}).get('tasks', [])
for t in tasks:
    print(f"Task: {t.get('title')}, Status: {t.get('status')}, Deadline: {t.get('deadline')}, Resp: {t.get('responsible', {}).get('name')}")
