import requests
import json
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

cmd = {
    'today_123': 'tasks.task.list?filter[GROUP_ID]=230&filter[>=DEADLINE]=2026-09-28T00:00:00&filter[<=DEADLINE]=2026-09-28T23:59:59&filter[!STATUS]=5',
    'tomorrow_123': 'tasks.task.list?filter[GROUP_ID]=230&filter[>=DEADLINE]=2026-09-29T00:00:00&filter[<=DEADLINE]=2026-09-29T23:59:59&filter[!STATUS]=5'
}

batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
results = batch_resp.get('result', {}).get('result', {})

print("today_123:", len(results.get('today_123', {}).get('tasks', [])))
print("tomorrow_123:", len(results.get('tomorrow_123', {}).get('tasks', [])))
