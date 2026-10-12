import requests

COMMIT_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.disk.file.commit"
MSG_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.message.add"

print("Testing commit with no file...")
resp1 = requests.post(COMMIT_URL, json={"CHAT_ID": "345986", "MESSAGE": "Test from AI without file"}, verify=False)
print("Commit Response:", resp1.json())

print("Testing message add...")
resp2 = requests.post(MSG_URL, json={"CHAT_ID": "345986", "MESSAGE": "Test from AI with message.add"}, verify=False)
print("Message Add Response:", resp2.json())
