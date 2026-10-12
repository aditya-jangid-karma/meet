import requests
groups = []
start = 0
while True:
    resp = requests.get(f'https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json?start={start}', verify=False).json()
    batch = resp.get('result', [])
    groups.extend(batch)
    if 'next' in resp:
        start = resp['next']
    else:
        break

c160a_gid = None
for g in groups:
    if 'C160A' in g['NAME']:
        c160a_gid = g['ID']
        print(f"Found C160A: {g['ID']} - {g['NAME']}")
        break

if c160a_gid:
    url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
    params = {
        'filter[GROUP_ID]': c160a_gid,
        'filter[>DEADLINE]': '2026-09-27T23:59:59',
        'filter[<DEADLINE]': '2026-09-29T00:00:00',
        'filter[!STATUS]': '5'
    }
    resp = requests.get(url, params=params, verify=False).json()
    tasks = resp.get('result', {}).get('tasks', [])

    print(f"Total 'Due Today' tasks fetched for C160A: {len(tasks)}")
    for t in tasks[:10]:
        print(f"Task: {t.get('title')}, Deadline: {t.get('deadline')}, Status: {t.get('status')}")
