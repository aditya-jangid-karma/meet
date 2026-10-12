import requests

url = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"

cmd = {
    'overdue_414': 'tasks.task.list?filter[GROUP_ID]=414&filter[!STATUS]=5' # 414 is C104A
}
resp = requests.post(url, json={'halt': 0, 'cmd': cmd}, verify=False).json()
print("Keys in batch response:")
print(resp.keys())
print("\nKeys in resp['result']:")
print(resp['result'].keys())
print("\nContent of next:")
if 'next' in resp['result']:
    print(resp['result']['next'])
else:
    print("No next in result")
