import os
import re

path = r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation\master_runner.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'print\(f"\\[uU].{8} ', 'print(f"', content)
content = content.replace("?? ", "")
content = content.replace("? ", "")
content = content.replace("? ", "")

# Fix any stray unicode characters causing issues
content = content.encode('ascii', 'ignore').decode('ascii')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
