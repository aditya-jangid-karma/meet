import requests
import datetime
from datetime import timedelta

BATCH_URL = "https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/batch.json"
gid = 586 # Harrison Capital

today_dt = datetime.datetime.now()
tomorrow_dt = today_dt + timedelta(days=1)
yesterday_dt = today_dt - timedelta(days=1)
day_after_dt = today_dt + timedelta(days=2)

today_str = today_dt.strftime('%Y-%m-%d')
tomorrow_str = tomorrow_dt.strftime('%Y-%m-%d')
yesterday_str = yesterday_dt.strftime('%Y-%m-%d')
day_after_str = day_after_dt.strftime('%Y-%m-%d')

start_of_today = f"{today_str}T00:00:00"
start_today_gt = f"{yesterday_str}T23:59:59"
end_today_lt = f"{tomorrow_str}T00:00:00"
start_tomorrow_gt = f"{today_str}T23:59:59"
end_tomorrow_lt = f"{day_after_str}T00:00:00"

cmd = {
    'overdue': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[<DEADLINE]={start_of_today}&filter[!STATUS]=5',
    'today': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]={start_today_gt}&filter[<DEADLINE]={end_today_lt}&filter[!STATUS]=5',
    'tomorrow': f'tasks.task.list?filter[GROUP_ID]={gid}&filter[>DEADLINE]={start_tomorrow_gt}&filter[<DEADLINE]={end_tomorrow_lt}&filter[!STATUS]=5'
}

batch_resp = requests.post(BATCH_URL, json={'halt': 0, 'cmd': cmd}, verify=False).json()
results = batch_resp.get('result', {}).get('result', {})

print("Harrison Capital (586) Tasks with NEW correct filters:")
print("Overdue:", len(results.get('overdue', {}).get('tasks', [])))
print("Due Today:", len(results.get('today', {}).get('tasks', [])))
print("Due Tomorrow:", len(results.get('tomorrow', {}).get('tasks', [])))
