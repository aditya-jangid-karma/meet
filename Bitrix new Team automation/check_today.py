import requests

url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
params = {
    'filter[>DEADLINE]': '2026-09-27T23:59:59',
    'filter[<DEADLINE]': '2026-09-29T00:00:00',
    'filter[!STATUS]': '5'
}
resp = requests.get(url, params=params, verify=False).json()
tasks = resp.get('result', {}).get('tasks', [])

print(f"Total 'Due Today' tasks fetched: {len(tasks)}")
for t in tasks[:20]:
    print(f"Task: {t.get('title')}, Status: {t.get('status')}, Responsible: {t.get('responsible', {}).get('name')}")
