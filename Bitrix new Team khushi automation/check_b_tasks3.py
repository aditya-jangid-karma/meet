import requests

url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
start = 0
all_tasks = []
while True:
    params = {
        'filter[GROUP_ID]': 71,
        'filter[!STATUS]': '5',
        'select[]': ['ID', 'TITLE', 'STATUS', 'DEADLINE', 'RESPONSIBLE_ID'],
        'start': start
    }
    resp = requests.get(url, params=params, verify=False).json()
    tasks = resp.get('result', {}).get('tasks', [])
    all_tasks.extend(tasks)
    if 'next' not in resp.get('result', {}):
        if 'next' not in resp: # sometimes it's at root
            break
        else:
            start = resp['next']
    else:
        start = resp['result']['next']

print(f"Total active tasks: {len(all_tasks)}")
with_deadline = 0
for t in all_tasks:
    if t.get('deadline'):
        with_deadline += 1
        # print(f"{t.get('deadline')} - {t.get('status')} - {t.get('title')} ")
print(f"Tasks with deadline: {with_deadline}")
