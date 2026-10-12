import re

l1_mapping = {'C326A': 'Krishnakumar Bang'}

groups = [
    {'NAME': 'H - Harrison Capital - Seth Sierk - C326A', 'ID': '586'},
    {'NAME': 'H - Harrison Capital - Seth Sierk - C326a', 'ID': '999'},
    {'NAME': 'H - Harrison Capital - Seth Sierk -  C326A ', 'ID': '123'}
]

pattern = r'^([A-Za-z0-9]+)\s*-\s*(.*?)\s*-\s*([^-]+?)\s*(?:-|\()\s*(C\d+[A-Z]+)'

for g in groups:
    project_name = g.get('NAME', '')
    match = re.match(pattern, project_name)
    if match:
        team, client, person, code = match.groups()
        team_val = team.strip().upper()
        code_val = code.strip()
        print(f"'{project_name}': code_val='{code_val}', l1='{l1_mapping.get(code_val, 'Unknown Lead')}'")
    else:
        print(f"'{project_name}': No match")
