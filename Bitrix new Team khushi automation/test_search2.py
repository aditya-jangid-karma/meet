import requests

webhook = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/"

def search_im(query):
    url = webhook + "im.search.chat.list.json"
    resp = requests.post(url, json={'FIND': query}, verify=False).json()
    print(f"IM Search '{query}': {resp}")

search_im('Anurag')
search_im('Allies')
search_im('Compliance')
