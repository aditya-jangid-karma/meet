import requests

gid = 586
url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list?filter[GROUP_ID]={gid}&filter[!STATUS]=5'
resp = requests.get(url, verify=False).json()
tasks = resp.get('result', {}).get('tasks', [])
print(f"Total active tasks for Harrison Capital: {len(tasks)}")
for t in tasks:
    print(f"Task: {t.get('title')}, Deadline: {t.get('deadline')}, Responsible: {t.get('responsible', {}).get('name')}")
