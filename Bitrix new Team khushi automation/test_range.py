import requests
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"
gid = 572
cmd = {
    'range_test': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]=2025-01-01T00:00:00&filter[<DEADLINE]=2026-12-31T00:00:00&filter[!STATUS]=5'
}
batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
results = batch_resp.get('result', {}).get('result', {})

print("range_test:", len(results.get('range_test', {}).get('tasks', [])))
