import requests

url = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/user.get.json"
resp = requests.get(url, verify=False).json()
for u in resp.get('result', [])[:10]:
    print(f"{u.get('ID')} - {u.get('NAME')} {u.get('LAST_NAME')}")
