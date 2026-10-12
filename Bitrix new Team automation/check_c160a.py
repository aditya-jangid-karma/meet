import requests

# Find C160A group ID
groups_url = "https://karma.bitrix24.in/rest/1/4ge56nup4fuub38j/sonet_group.get.json?filter[NAME]=%C160A%"
resp = requests.get(groups_url, verify=False).json()
gids = [g['ID'] for g in resp.get('result', [])]
print(f"C160A Group IDs: {gids}")

if not gids:
    import sys
    sys.exit()

gid = gids[0]

# Fetch 'Due Today'
url = f'https://karma.bitrix24.in/rest/1/euiyos3e551clsi5/tasks.task.list'
params = {
    'filter[GROUP_ID]': gid,
    'filter[>DEADLINE]': '2026-09-27T23:59:59',
    'filter[<DEADLINE]': '2026-09-29T00:00:00',
    'filter[!STATUS]': '5'
}
resp = requests.get(url, params=params, verify=False).json()
tasks = resp.get('result', {}).get('tasks', [])

print(f"Total 'Due Today' tasks fetched for C160A: {len(tasks)}")
for t in tasks[:10]:
    print(f"Task: {t.get('title')}, Deadline: {t.get('deadline')}, Status: {t.get('status')}")
