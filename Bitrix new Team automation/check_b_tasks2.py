import requests

url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
params = {
    'filter[GROUP_ID]': 71,
    'filter[!STATUS]': '5',
    'select[]': ['ID', 'TITLE', 'STATUS', 'DEADLINE', 'RESPONSIBLE_ID']
}
resp = requests.get(url, params=params, verify=False).json()
tasks = resp.get('result', {}).get('tasks', [])
print(f"Total active tasks: {len(tasks)}")
with_deadline = 0
for t in tasks:
    if t.get('deadline'):
        with_deadline += 1
        print(f"{t.get('deadline')} - {t.get('status')} - {t.get('title')} ")
print(f"Tasks with deadline: {with_deadline}")
