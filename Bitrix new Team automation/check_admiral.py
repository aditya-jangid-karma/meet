import requests

url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
params = {
    'filter[GROUP_ID]': 454, # C365A
    'filter[>DEADLINE]': '2026-09-27T23:59:59',
    'filter[<DEADLINE]': '2026-09-29T00:00:00',
    'filter[!STATUS]': '5'
}
resp = requests.get(url, params=params, verify=False).json()
tasks = resp.get('result', {}).get('tasks', [])

print(f"Total 'Due Today' tasks fetched for C365A: {len(tasks)}")
for t in tasks:
    print(f"Task: {t.get('title')}, Deadline: {t.get('deadline')}, Responsible: {t.get('responsible', {}).get('name')}, Status: {t.get('status')}")
