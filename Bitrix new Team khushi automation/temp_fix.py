import os

path = r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation\master_runner.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("WAIT_SECONDS = 5 * 60", "WAIT_SECONDS = 15")
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
