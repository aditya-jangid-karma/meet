import requests
BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"
gid = 572
cmd = {
    'op_less': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[<DEADLINE]=2026-09-30T00:00:00&filter[!STATUS]=5',
    'op_greater': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]=2026-09-20T00:00:00&filter[!STATUS]=5',
    'op_greatereq': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>=DEADLINE]=2026-09-20T00:00:00&filter[!STATUS]=5',
    'op_lesseq': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[<=DEADLINE]=2026-09-30T00:00:00&filter[!STATUS]=5'
}
batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
results = batch_resp.get('result', {}).get('result', {})

print("op_less:", len(results.get('op_less', {}).get('tasks', [])))
print("op_greater:", len(results.get('op_greater', {}).get('tasks', [])))
print("op_greatereq:", len(results.get('op_greatereq', {}).get('tasks', [])))
print("op_lesseq:", len(results.get('op_lesseq', {}).get('tasks', [])))
