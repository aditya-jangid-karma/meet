import requests
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

cmd = {
    'all_tasks': 'tasks.task.list?filter[GROUP_ID]=586&filter[!STATUS]=5'
}

batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
results = batch_resp.get('result', {}).get('result', {})

print("All tasks:")
for t in results.get('all_tasks', {}).get('tasks', []):
    print("  ", t['id'], t['deadline'])
