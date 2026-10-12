import requests
import urllib3

# Suppress the SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# The Bitrix API endpoint specifically for sending plain text messages
MESSAGE_URL = "https://karma.bitrix24.in/rest/1488/zazz4zw38crxbf1p/im.message.add"
TESTING_CHANNEL_ID = "345986"

# The data we are sending
payload = {
    "CHAT_ID": TESTING_CHANNEL_ID,
    "MESSAGE": "Hello! This is a quick test message."
}

print("Sending test message to Bitrix...")

# Fire the request!
response = requests.post(MESSAGE_URL, json=payload, verify=False)

# Check the results
if response.status_code == 200:
    print("Success! Check your Bitrix Testing Channel.")
    print("Bitrix Response:", response.json())
else:
    print("Failed to send message.")
    print(f"Error {response.status_code}: {response.text}")