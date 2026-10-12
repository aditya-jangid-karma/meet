import requests
resp = requests.get('https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json?filter[NAME]=%Tortoise%', verify=False).json()
groups = resp.get('result', [])
if groups:
    gid = groups[0]['ID']
    print(f"Found Tortoise group: {gid}")
    
    BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"
    cmd = {
        'all_tasks': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[!STATUS]=5'
    }
    batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
    results = batch_resp.get('result', {}).get('result', {})
    
    print("Tasks for Tortoise:")
    for t in results.get('all_tasks', {}).get('tasks', []):
        print(f"  {t['id']}: {t['deadline']}")
