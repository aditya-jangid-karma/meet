import requests

groups = []
start = 0
while True:
    resp = requests.get(f'https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json?start={start}', verify=False).json()
    batch = resp.get('result', [])
    groups.extend(batch)
    if 'next' in resp:
        start = resp['next']
    else:
        break

for g in groups:
    if 'Harrison' in g['NAME']:
        print(g['ID'], g['NAME'])
