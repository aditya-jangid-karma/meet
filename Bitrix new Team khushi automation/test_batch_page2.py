import requests

url = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

cmd = {
    'overdue_414': 'tasks.task.list?filter[GROUP_ID]=414&filter[!STATUS]=5'
}
resp = requests.post(url, json={'halt': 0, 'cmd': cmd}, verify=False).json()
print("\nContent of result_next:")
print(resp['result'].get('result_next'))
