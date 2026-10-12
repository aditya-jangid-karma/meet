import re

pattern = r'^([A-Za-z0-9]+)\s*-\s*(.*?)\s*-\s*([^-]+?)\s*(?:-|\()\s*(C\d+[A-Z]+)'
name = 'H - Harrison Capital - Seth Sierk - C326A'
match = re.search(pattern, name)
if match:
    print('Matched:', match.groups())
else:
    print('No match')
