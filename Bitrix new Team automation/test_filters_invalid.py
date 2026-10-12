import requests
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"
gid = 572
cmd = {
    'op_greater_future': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]=2026-12-31T00:00:00&filter[!STATUS]=5',
    'op_greatereq_future': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>=DEADLINE]=2026-12-31T00:00:00&filter[!STATUS]=5',
    'op_less_past': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[<DEADLINE]=2025-01-01T00:00:00&filter[!STATUS]=5',
}
batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
results = batch_resp.get('result', {}).get('result', {})

print("op_greater_future:", len(results.get('op_greater_future', {}).get('tasks', [])))
print("op_greatereq_future:", len(results.get('op_greatereq_future', {}).get('tasks', [])))
print("op_less_past:", len(results.get('op_less_past', {}).get('tasks', [])))
