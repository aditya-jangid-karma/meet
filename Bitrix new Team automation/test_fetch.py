import requests

BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

cmd = {
    'today': 'tasks.task.list?filter[GROUP_ID]=2458&filter[>=DEADLINE]=2026-09-28T00:00:00&filter[<=DEADLINE]=2026-09-28T23:59:59&filter[!STATUS]=5',
    'tomorrow': 'tasks.task.list?filter[GROUP_ID]=2458&filter[>=DEADLINE]=2026-09-29T00:00:00&filter[<=DEADLINE]=2026-09-29T23:59:59&filter[!STATUS]=5'
}

batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
results = batch_resp.get('result', {}).get('result', {})

print("Today tasks:", len(results.get('today', {}).get('tasks', [])))
print("Tomorrow tasks:", len(results.get('tomorrow', {}).get('tasks', [])))
