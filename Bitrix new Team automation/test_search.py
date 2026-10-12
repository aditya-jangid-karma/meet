import requests

url = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/im.search.chat.list.json"
params = {'FIND': 'Rahul'}
resp = requests.get(url, params=params, verify=False).json()
print("Chat search:")
print(resp.get('result', []))

url2 = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/user.search.json"
params2 = {'FIND': 'Rahul Gajera'}
resp2 = requests.get(url2, params=params2, verify=False).json()
print("\nUser search:")
print(resp2.get('result', []))
