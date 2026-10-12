import requests

resp = requests.get('https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json?filter[NAME]=%Harrison%', verify=False).json()
for g in resp.get('result', []):
    print(g['ID'], g['NAME'])
